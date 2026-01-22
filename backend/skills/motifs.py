from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import chess  # type: ignore

from investigator import Investigator


@dataclass(frozen=True)
class MotifPolicy:
    max_pattern_plies: int = 4
    motifs_top: int = 25
    max_line_plies: int = 10
    max_branch_lines: int = 18
    # Full-tree traversal controls (deterministic caps)
    max_tree_depth: int = 7
    max_tree_nodes: int = 260
    max_total_lines: int = 140
    # Signature granularity controls (helps recurrence)
    include_granularity_coarse: bool = True
    include_granularity_mid: bool = True
    include_granularity_fine: bool = True


def _move_tokens(board: chess.Board, san: str) -> Tuple[List[str], Optional[chess.Move]]:
    """
    Deterministic tokenization for a SAN move from a specific board state.
    Returns (tokens, move_obj).
    """
    tokens: List[str] = []
    try:
        mv = board.parse_san(san)
    except Exception:
        return [f"SAN:{san}"], None

    tokens.append(f"SAN:{san}")

    # Piece type (from_piece)
    p = board.piece_at(mv.from_square)
    if p:
        name = p.piece_type
        if name == chess.PAWN:
            tokens.append("PIECE:pawn")
        elif name == chess.KNIGHT:
            tokens.append("PIECE:knight")
        elif name == chess.BISHOP:
            tokens.append("PIECE:bishop")
        elif name == chess.ROOK:
            tokens.append("PIECE:rook")
        elif name == chess.QUEEN:
            tokens.append("PIECE:queen")
        elif name == chess.KING:
            tokens.append("PIECE:king")

    # Move type tokens
    if board.is_castling(mv):
        tokens.append("TYPE:castle")
    if board.is_capture(mv):
        tokens.append("TYPE:capture")
    if mv.promotion is not None:
        tokens.append("TYPE:promotion")

    # Check token requires making the move
    try:
        board.push(mv)
        if board.is_check():
            tokens.append("TYPE:check")
        board.pop()
    except Exception:
        pass

    return tokens, mv


def _extract_lines_from_tree(exploration_tree: Dict[str, Any], *, policy: MotifPolicy) -> List[Dict[str, Any]]:
    """
    Extract a bounded set of lines from exploration_tree for motif mining.
    Each line is {line_id, root_kind, root_move, moves_san}.
    """
    lines: List[Dict[str, Any]] = []

    pv_full = exploration_tree.get("pv_full") or []
    if isinstance(pv_full, list) and pv_full:
        moves = [m for m in pv_full if isinstance(m, str) and m.strip()][: policy.max_line_plies]
        if moves:
            lines.append(
                {
                    "line_id": "pv_root",
                    "root_kind": "pv_root",
                    "root_move": None,
                    "moves_san": moves,
                }
            )

    branches = exploration_tree.get("branches") or []
    if not isinstance(branches, list):
        branches = []

    # Deterministic full-tree traversal (bounded).
    # Root identity = top-level branch move (the first move in path).
    node_count = 0

    def _stable_branch_sort_key(b: Dict[str, Any]) -> Tuple[str, float, float]:
        mv = b.get("move_played")
        mv_s = mv.strip() if isinstance(mv, str) else ""
        try:
            ev16 = float(b.get("eval_d16")) if b.get("eval_d16") is not None else 9999.0
        except Exception:
            ev16 = 9999.0
        try:
            ev2 = float(b.get("eval_d2")) if b.get("eval_d2") is not None else 9999.0
        except Exception:
            ev2 = 9999.0
        return (mv_s, ev16, ev2)

    def _walk(node: Dict[str, Any], *, depth: int, path_moves: List[str]) -> None:
        nonlocal node_count
        if node_count >= int(policy.max_tree_nodes):
            return
        if depth > int(policy.max_tree_depth):
            return
        if len(lines) >= int(policy.max_total_lines):
            return

        node_count += 1

        mv = node.get("move_played")
        pv = node.get("pv_full") or node.get("pv_san") or []
        if not isinstance(pv, list):
            pv = []

        seq: List[str] = []
        if isinstance(mv, str) and mv.strip():
            seq.append(mv.strip())
        seq.extend([m for m in pv if isinstance(m, str) and m.strip()])
        seq = seq[: policy.max_line_plies]

        if seq:
            root_move = path_moves[0] if path_moves else (mv.strip() if isinstance(mv, str) else None)
            root_kind = "overestimated_root" if root_move else "pv_root"
            path_id = " ".join([m for m in path_moves if isinstance(m, str) and m.strip()])
            line_id = f"path:{path_id}" if path_id else (f"branch:{mv}" if isinstance(mv, str) else "node")
            lines.append(
                {
                    "line_id": line_id,
                    "root_kind": root_kind,
                    "root_move": root_move,
                    "moves_san": seq,
                }
            )

        kids = node.get("branches") or []
        if not isinstance(kids, list) or not kids:
            return
        kid_dicts = [k for k in kids if isinstance(k, dict)]
        kid_dicts.sort(key=_stable_branch_sort_key)
        for k in kid_dicts:
            kmv = k.get("move_played")
            next_path = list(path_moves)
            if isinstance(kmv, str) and kmv.strip():
                next_path.append(kmv.strip())
            _walk(k, depth=depth + 1, path_moves=next_path)

    top_level = [b for b in branches if isinstance(b, dict)]
    top_level.sort(key=_stable_branch_sort_key)
    for br in top_level[: policy.max_branch_lines]:
        mv = br.get("move_played")
        start_path = [mv.strip()] if isinstance(mv, str) and mv.strip() else []
        _walk(br, depth=1, path_moves=start_path)

    return lines


def mine_motifs(
    *,
    starting_fen: str,
    exploration_tree: Dict[str, Any],
    engine_pool_instance=None,
    engine_queue=None,
    policy: Optional[MotifPolicy] = None,
) -> List[Dict[str, Any]]:
    """
    Deterministically mine motifs across branches.

    Motifs are ranked by frequency and annotated with location/concentration.
    Pattern tokens can include SAN + move-type + tag/role delta tokens.
    """
    pol = policy or MotifPolicy()

    inv = Investigator(engine_pool=engine_pool_instance) if engine_pool_instance is not None else Investigator(engine_queue=engine_queue)

    # Phase heuristic (matches Investigator._classify_game_phase style): opening has many pieces on board.
    try:
        piece_count = len(chess.Board(starting_fen).piece_map())
    except Exception:
        piece_count = 0
    phase = "opening" if piece_count > 24 else ("middlegame" if piece_count > 12 else "endgame")

    lines = _extract_lines_from_tree(exploration_tree, policy=pol)
    if not lines:
        return []

    # Helper mapping for deterministic example extraction.
    lines_by_id: Dict[str, List[str]] = {}
    try:
        for ln in lines:
            if not isinstance(ln, dict):
                continue
            lid = ln.get("line_id")
            mv = ln.get("moves_san") or []
            if isinstance(lid, str) and lid and isinstance(mv, list):
                lines_by_id[lid] = [m for m in mv if isinstance(m, str) and m.strip()]
    except Exception:
        lines_by_id = {}

    # Count occurrences
    motif_stats: Dict[str, Dict[str, Any]] = {}
    root_ids = sorted({(ln.get("root_move") or "pv_root") for ln in lines})
    total_roots = max(1, len(root_ids))
    total_lines = max(1, len(lines))

    for ln in lines:
        line_id = ln["line_id"]
        root_kind = ln["root_kind"]
        root_move = ln.get("root_move") or "pv_root"
        moves_san: List[str] = ln.get("moves_san") or []
        moves_san = [m for m in moves_san if isinstance(m, str) and m.strip()]
        if not moves_san:
            continue

        # Compute per-move deltas (tags/roles) deterministically using existing investigator helper
        try:
            per_move, _, _, _, _, _, _ = inv._compute_per_move_deltas_for_line(starting_fen, moves_san)  # type: ignore
        except Exception:
            per_move = []

        # Build token rows per ply (and 3 deterministic granularities)
        b = chess.Board(starting_fen)
        ply_tokens_fine: List[List[str]] = []
        ply_tokens_mid: List[List[str]] = []
        ply_tokens_coarse: List[List[str]] = []
        for idx, san in enumerate(moves_san):
            tokens, mv_obj = _move_tokens(b, san)
            # Advance board (for next parse)
            try:
                if mv_obj and mv_obj in b.legal_moves:
                    b.push(mv_obj)
                else:
                    # Fallback attempt by re-parsing after potential drift
                    b.push(b.parse_san(san))
            except Exception:
                # If the line isn't legal from this fen, stop extending
                break

            # Add tag/role delta tokens (if computed)
            if idx < len(per_move) and isinstance(per_move[idx], dict):
                gained_struct = per_move[idx].get("tags_gained_structured") or []
                lost_struct = per_move[idx].get("tags_lost_structured") or []
                gained_roles = per_move[idx].get("roles_gained") or []
                lost_roles = per_move[idx].get("roles_lost") or []

                def _tagname(t: Any) -> Optional[str]:
                    if isinstance(t, dict):
                        tn = t.get("tag_name") or t.get("tag") or t.get("name")
                        return str(tn) if tn else None
                    return None

                for t in gained_struct:
                    tn = _tagname(t)
                    if tn:
                        tokens.append(f"TAG+:{tn}")
                for t in lost_struct:
                    tn = _tagname(t)
                    if tn:
                        tokens.append(f"TAG-:{tn}")
                for r in gained_roles:
                    if isinstance(r, str) and ":" in r:
                        tokens.append(f"ROLE+:{r.split(':',1)[1]}")
                for r in lost_roles:
                    if isinstance(r, str) and ":" in r:
                        tokens.append(f"ROLE-:{r.split(':',1)[1]}")

            # Deterministic ordering within ply (fine)
            tokens = sorted(dict.fromkeys(tokens))
            fine = tokens

            coarse: List[str] = []
            mid: List[str] = []

            def _tag_bucket(tag_tok: str) -> Optional[str]:
                # TAG+:{name} or TAG-:{name}
                try:
                    sign = tag_tok[:5]
                    name = tag_tok[5:]
                    parts = name.split(".")
                    if len(parts) >= 3:
                        return sign + ".".join(parts[:3]) + ".*"
                    return sign + name
                except Exception:
                    return None

            for t in fine:
                if t.startswith("SAN:") or t.startswith("TYPE:"):
                    coarse.append(t)
                    mid.append(t)
                elif t.startswith("PIECE:"):
                    mid.append(t)
                elif t.startswith("TAG+:") or t.startswith("TAG-:"):
                    bkt = _tag_bucket(t)
                    if bkt:
                        mid.append(bkt)
                # roles remain fine-only (too noisy for recurrence)

            def _dedupe_sorted(xs: List[str]) -> List[str]:
                return sorted(dict.fromkeys([x for x in xs if x]))

            ply_tokens_fine.append(_dedupe_sorted(fine))
            ply_tokens_mid.append(_dedupe_sorted(mid))
            ply_tokens_coarse.append(_dedupe_sorted(coarse))

        # Generate patterns of length 1..K plies
        K = max(1, int(pol.max_pattern_plies))
        for L in range(1, K + 1):
            for start in range(0, max(0, len(ply_tokens_fine) - L + 1)):
                def _emit(granularity: str, window_rows: List[List[str]]) -> None:
                    sig = " / ".join([" ".join(r) for r in window_rows])
                    if not sig.strip():
                        return
                    sig = f"G={granularity} | " + sig

                    st = motif_stats.get(sig)
                    if not st:
                        st = {
                            "pattern_sig": sig,
                            "pattern_len_plies": L,
                            "pattern_granularity": granularity,
                            "count_total": 0,
                            "roots": set(),
                            "line_ids": set(),
                            "locations": [],
                            "root_kind_counts": {"pv_root": 0, "overestimated_root": 0},
                        }
                        motif_stats[sig] = st

                    st["count_total"] += 1
                    st["roots"].add(root_move)
                    st["line_ids"].add(line_id)
                    st["root_kind_counts"][root_kind] = st["root_kind_counts"].get(root_kind, 0) + 1
                    st["locations"].append(
                        {
                            "line_id": line_id,
                            "root_kind": root_kind,
                            "root_move": None if root_move == "pv_root" else root_move,
                            "start_ply_index": start,
                            "len_plies": L,
                        }
                    )

                if pol.include_granularity_coarse:
                    _emit("coarse", ply_tokens_coarse[start : start + L])
                if pol.include_granularity_mid:
                    _emit("mid", ply_tokens_mid[start : start + L])
                if pol.include_granularity_fine:
                    _emit("fine", ply_tokens_fine[start : start + L])

    # Rank motifs deterministically
    out: List[Dict[str, Any]] = []
    for sig, st in motif_stats.items():
        distinct_roots = len(st["roots"])
        distinct_lines = len(st.get("line_ids") or [])
        concentration_roots = distinct_roots / total_roots
        concentration_lines = distinct_lines / total_lines
        # NEW: significance includes pattern length (longer repeated patterns are more meaningful)
        # Opening preference: repetition > length; coarse/mid motifs should surface.
        try:
            len_plies = int(st["pattern_len_plies"])
        except Exception:
            len_plies = 1
        gran = str(st.get("pattern_granularity") or "fine")

        if phase == "opening":
            # In openings, fine signatures rarely repeat; prioritize recurring coarse/mid motifs.
            gran_w = 1.35 if gran == "coarse" else (1.2 if gran == "mid" else 1.0)
            count_w = float(max(1, int(st["count_total"]))) ** 1.6
            len_w = float(max(1, len_plies)) ** 0.7
            significance = count_w * len_w * (1.0 + float(concentration_lines)) * gran_w
        else:
            # Outside openings, fine motifs are more stable and useful.
            gran_w = 1.0
            if gran == "mid":
                gran_w = 1.15
            elif gran == "fine":
                gran_w = 1.3
            significance = float(st["count_total"]) * (float(max(1, len_plies)) ** 1.2) * (1.0 + float(concentration_lines)) * gran_w
        classification = "strategic_motif"
        if st["root_kind_counts"].get("overestimated_root", 0) >= st["root_kind_counts"].get("pv_root", 0) and distinct_roots <= max(2, total_roots // 3):
            classification = "hidden_tactic_candidate"

        out.append(
            {
                "motif_id": f"motif_{abs(hash(sig)) % 10_000_000}",
                "pattern": {
                    "signature": sig,
                    "len_plies": st["pattern_len_plies"],
                    "granularity": st.get("pattern_granularity") or "fine",
                },
                "location": {
                    "count_total": st["count_total"],
                    "distinct_root_branches": distinct_roots,
                    "total_root_branches_considered": total_roots,
                    "distinct_lines": distinct_lines,
                    "total_lines_considered": total_lines,
                    "concentration_roots": concentration_roots,
                    "concentration_lines": concentration_lines,
                    "root_kind_counts": st["root_kind_counts"],
                    "examples": st["locations"][:5],
                },
                # NEW: Provide example SAN windows for UI/claim-style rendering.
                # This is deterministic and does not require any new engine calls.
                "examples_san": [
                    {
                        "line_id": ex.get("line_id"),
                        "root_move": ex.get("root_move"),
                        "root_kind": ex.get("root_kind"),
                        "start_ply_index": ex.get("start_ply_index"),
                        "len_plies": ex.get("len_plies"),
                        "moves_san": (
                            (lines_by_id.get(ex.get("line_id"), []) or [])[ex.get("start_ply_index", 0): ex.get("start_ply_index", 0) + ex.get("len_plies", 1)]
                            if isinstance(ex, dict) else []
                        ),
                    }
                    for ex in (st["locations"][:5] if isinstance(st.get("locations"), list) else [])
                ],
                "significance": significance,
                "classification": classification,
            }
        )

    out.sort(key=lambda m: (-float(m.get("significance") or 0.0), -int(m["pattern"]["len_plies"]), str(m["pattern"]["signature"])))

    return out[: int(pol.motifs_top)]


