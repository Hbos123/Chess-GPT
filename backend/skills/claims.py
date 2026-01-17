from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import os

import chess  # type: ignore

from nnue_bridge import get_nnue_dump, compute_piece_contributions
from piece_tag_mappings import get_tag_weight_for_piece


_NNUE_CONTRIB_CACHE: Dict[str, Dict[str, Dict[str, float]]] = {}
_NNUE_CONTRIB_CACHE_MAX = 128


def _cache_get_contrib(fen: str) -> Optional[Dict[str, Dict[str, float]]]:
    return _NNUE_CONTRIB_CACHE.get(fen)


def _cache_set_contrib(fen: str, contrib: Dict[str, Dict[str, float]]) -> None:
    # very small, deterministic LRU-ish: drop first inserted if over cap
    if fen in _NNUE_CONTRIB_CACHE:
        _NNUE_CONTRIB_CACHE[fen] = contrib
        return
    if len(_NNUE_CONTRIB_CACHE) >= _NNUE_CONTRIB_CACHE_MAX:
        try:
            oldest = next(iter(_NNUE_CONTRIB_CACHE.keys()))
            _NNUE_CONTRIB_CACHE.pop(oldest, None)
        except Exception:
            _NNUE_CONTRIB_CACHE.clear()
    _NNUE_CONTRIB_CACHE[fen] = contrib


def _normalize_fen(fen: str) -> str:
    try:
        return chess.Board(fen).fen()
    except Exception:
        return (fen or "").strip()


def _piece_id(color: chess.Color, piece: chess.Piece, square_name: str) -> str:
    c = "white" if color == chess.WHITE else "black"
    pt = chess.piece_name(piece.piece_type)
    return f"{c}_{pt}_{square_name}"


def _parse_piece_id(piece_id: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    # "white_knight_f3"
    parts = (piece_id or "").split("_")
    if len(parts) >= 3:
        return parts[0], parts[1], parts[2]
    return None, None, None


def _try_get_contrib_by_fen(fen: str) -> Optional[Dict[str, Dict[str, float]]]:
    nf = _normalize_fen(fen)
    cached = _cache_get_contrib(nf)
    if cached is not None:
        return cached
    dump_timeout = float(os.getenv("NNUE_DUMP_TIMEOUT_S", "8"))
    dump = get_nnue_dump(nf, timeout=dump_timeout)
    if not dump:
        return None
    contrib = compute_piece_contributions(dump)
    _cache_set_contrib(nf, contrib)
    return contrib


def _track_piece_instances_along_line(start_fen: str, moves_san: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    Track piece identity across a SAN line.
    Identity key is initial square-based id; we update its current square as moves are played.
    """
    b = chess.Board(start_fen)
    inst: Dict[str, Dict[str, Any]] = {}
    for sq in chess.SQUARES:
        p = b.piece_at(sq)
        if not p:
            continue
        sqn = chess.square_name(sq)
        pid = _piece_id(p.color, p, sqn)
        inst[pid] = {"color": "white" if p.color == chess.WHITE else "black", "piece_type": chess.piece_name(p.piece_type), "start_square": sqn, "end_square": sqn}

    for san in moves_san:
        if not isinstance(san, str) or not san.strip():
            continue
        try:
            mv = b.parse_san(san)
        except Exception:
            break

        from_sq = chess.square_name(mv.from_square)
        to_sq = chess.square_name(mv.to_square)

        # capture: remove victim instance whose current square == to_sq before move
        try:
            victim = b.piece_at(mv.to_square)
            if victim:
                victim_color = "white" if victim.color == chess.WHITE else "black"
                victim_type = chess.piece_name(victim.piece_type)
                for k, v in list(inst.items()):
                    if v.get("end_square") == to_sq and v.get("color") == victim_color and v.get("piece_type") == victim_type:
                        inst.pop(k, None)
                        break
        except Exception:
            pass

        # mover: update instance whose current square == from_sq
        try:
            mover_piece = b.piece_at(mv.from_square)
            if mover_piece:
                mover_color = "white" if mover_piece.color == chess.WHITE else "black"
                mover_type = chess.piece_name(mover_piece.piece_type)
                for k, v in inst.items():
                    if v.get("end_square") == from_sq and v.get("color") == mover_color and v.get("piece_type") == mover_type:
                        v["end_square"] = to_sq
                        break
        except Exception:
            pass

        try:
            b.push(mv)
        except Exception:
            break

    return inst


def _extract_tag_squares(tag_obj: Any) -> List[str]:
    squares: List[str] = []
    if isinstance(tag_obj, dict):
        sqs = tag_obj.get("squares") or []
        if isinstance(sqs, list):
            squares.extend([str(s) for s in sqs if s])
        pcs = tag_obj.get("pieces") or []
        if isinstance(pcs, list):
            for p in pcs:
                if isinstance(p, str) and len(p) >= 3:
                    # "Ra1", "P e4" (some older forms), etc.
                    tok = p.replace(" ", "")
                    sq = tok[1:] if len(tok) >= 3 else ""
                    if sq:
                        squares.append(sq)
    # normalize
    out = []
    for s in squares:
        ss = str(s).strip()
        if ss:
            out.append(ss)
    return out


def _score_tags_from_nnue_deltas(
    *,
    start_fen: str,
    end_fen: str,
    moves_san: List[str],
    tags_gained_structured: List[Dict[str, Any]],
    tags_lost_structured: List[Dict[str, Any]],
    phase: str,
) -> Dict[str, Any]:
    """
    Only uses tags gained/lost on the evidence line.
    Computes NNUE per-piece contribution deltas for identity-tracked pieces, then allocates relevance to tags.
    """
    if str(os.getenv("ENABLE_CLAIM_NNUE_TAG_RELEVANCE", "true")).lower().strip() != "true":
        return {}

    c0 = _try_get_contrib_by_fen(start_fen)
    c1 = _try_get_contrib_by_fen(end_fen)
    if not c0 or not c1:
        return {"nnue_available": False}

    inst = _track_piece_instances_along_line(start_fen, moves_san)

    inst_deltas: List[Dict[str, Any]] = []
    for inst_id, meta in inst.items():
        # start lookup uses inst_id directly (start square)
        start_pid = inst_id
        # end lookup uses the same piece identity but at its end square
        color = meta.get("color")
        ptype = meta.get("piece_type")
        end_sq = meta.get("end_square")
        if not (color and ptype and end_sq):
            continue
        end_pid = f"{color}_{ptype}_{end_sq}"

        a = (c0.get(start_pid) or {}).get("total_contribution_cp", 0.0)
        b = (c1.get(end_pid) or {}).get("total_contribution_cp", 0.0)
        d = float(b) - float(a)
        inst_deltas.append(
            {
                "piece_instance_id": inst_id,
                "color": color,
                "piece_type": ptype,
                "start_square": meta.get("start_square"),
                "end_square": end_sq,
                "delta_total_contribution_cp": d,
            }
        )

    inst_deltas.sort(key=lambda x: abs(float(x.get("delta_total_contribution_cp") or 0.0)), reverse=True)
    top_inst = inst_deltas[:10]

    # Build quick lookup for matching by square
    end_square_to_inst = {d.get("end_square"): d for d in top_inst if d.get("end_square")}
    start_square_to_inst = {d.get("start_square"): d for d in top_inst if d.get("start_square")}

    tag_scores: Dict[str, Dict[str, Any]] = {}

    def _accumulate(tag_obj: Dict[str, Any], *, is_gained: bool) -> None:
        tag_name = str(tag_obj.get("tag_name") or tag_obj.get("tag") or tag_obj.get("name") or "").strip()
        if not tag_name:
            return
        ref_squares = _extract_tag_squares(tag_obj)
        matches = []
        score = 0.0
        signed = 0.0
        for sq in ref_squares:
            inst_meta = (end_square_to_inst.get(sq) if is_gained else start_square_to_inst.get(sq))
            if not inst_meta:
                continue
            dcp = float(inst_meta.get("delta_total_contribution_cp") or 0.0)
            ptype = str(inst_meta.get("piece_type") or "")
            w = float(get_tag_weight_for_piece(tag_name, ptype, phase=phase))
            if w == 0.0:
                continue
            matches.append(
                {
                    "square": sq,
                    "piece_instance_id": inst_meta.get("piece_instance_id"),
                    "piece_type": ptype,
                    "delta_cp": dcp,
                    "tag_weight": w,
                }
            )
            score += abs(dcp) * abs(w)
            signed += dcp * w

        if score <= 0.0:
            return
        cur = tag_scores.get(tag_name)
        if not cur:
            cur = {
                "tag_name": tag_name,
                "relevance_score": 0.0,
                "signed_score": 0.0,
                "matches": [],
                "sources": {"gained": 0, "lost": 0},
            }
            tag_scores[tag_name] = cur
        cur["relevance_score"] += score
        cur["signed_score"] += signed
        cur["matches"].extend(matches)
        cur["sources"]["gained" if is_gained else "lost"] += 1

    for t in tags_gained_structured or []:
        if isinstance(t, dict):
            _accumulate(t, is_gained=True)
    for t in tags_lost_structured or []:
        if isinstance(t, dict):
            _accumulate(t, is_gained=False)

    tag_ranked = sorted(tag_scores.values(), key=lambda x: float(x.get("relevance_score") or 0.0), reverse=True)
    for tr in tag_ranked:
        try:
            tr["matches"] = (tr.get("matches") or [])[:8]
        except Exception:
            pass

    return {
        "nnue_available": True,
        "top_piece_contribution_deltas": top_inst,
        "tag_relevance_ranked": tag_ranked[:12],
    }


def build_claims_from_investigation(inv: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Deterministic claim builder.

    Input is an InvestigationResult serialized dict (typically from Investigator.to_dict()).
    Output is a list of structured, auditable claims that reference evidence lines / branches.
    """
    claims: List[Dict[str, Any]] = []

    eval_d16 = inv.get("eval_d16")
    eval_d2 = inv.get("eval_d2")
    best_move_d16 = inv.get("best_move_d16")
    is_critical = inv.get("is_critical")
    overestimated_moves = inv.get("overestimated_moves") or []

    # Claim 1: baseline evaluation + best move (D16) vs shallow (D2)
    claims.append(
        {
            "claim_type": "baseline",
            "statement": "Baseline evaluation and best move from dual-depth scan",
            "support": {
                "eval_d16": eval_d16,
                "eval_d2": eval_d2,
                "best_move_d16": best_move_d16,
                "is_critical": bool(is_critical) if is_critical is not None else None,
            },
            "evidence_ref": {
                "source": "root",
                "best_move_d16": best_move_d16,
            },
        }
    )

    # Claim 2: canonical evidence line (if present)
    evidence_pgn_line = inv.get("evidence_pgn_line")
    evidence_moves = inv.get("evidence_main_line_moves") or []
    if isinstance(evidence_pgn_line, str) and evidence_pgn_line.strip():
        start_fen = inv.get("evidence_starting_fen")
        end_fen = inv.get("evidence_end_fen")
        if not end_fen:
            try:
                pm = inv.get("evidence_per_move_deltas") or []
                if isinstance(pm, list) and pm:
                    last = pm[-1]
                    if isinstance(last, dict) and last.get("fen_after"):
                        end_fen = last.get("fen_after")
            except Exception:
                end_fen = None

        phase = inv.get("game_phase") or inv.get("phase") or inv.get("gamePhase") or "middlegame"
        phase = str(phase).strip().lower()
        if phase not in ("opening", "middlegame", "endgame"):
            phase = "middlegame"

        tags_gained_struct = inv.get("evidence_tags_gained_net_structured") or []
        tags_lost_struct = inv.get("evidence_tags_lost_net_structured") or []

        nnue_tag_relevance = {}
        if isinstance(start_fen, str) and isinstance(end_fen, str) and isinstance(evidence_moves, list) and evidence_moves:
            try:
                nnue_tag_relevance = _score_tags_from_nnue_deltas(
                    start_fen=start_fen,
                    end_fen=end_fen,
                    moves_san=[m for m in evidence_moves if isinstance(m, str)],
                    tags_gained_structured=[t for t in tags_gained_struct if isinstance(t, dict)],
                    tags_lost_structured=[t for t in tags_lost_struct if isinstance(t, dict)],
                    phase=phase,
                )
            except Exception:
                nnue_tag_relevance = {}

        claims.append(
            {
                "claim_type": "evidence_line",
                "statement": "Primary evidence line (canonical short line) with tag/role deltas",
                "support": {
                    "pgn_line": evidence_pgn_line,
                    "moves": evidence_moves,
                    "eval_start": inv.get("evidence_eval_start"),
                    "eval_end": inv.get("evidence_eval_end"),
                    "eval_delta": inv.get("evidence_eval_delta"),
                    "material_start": inv.get("evidence_material_start"),
                    "material_end": inv.get("evidence_material_end"),
                    "positional_start": inv.get("evidence_positional_start"),
                    "positional_end": inv.get("evidence_positional_end"),
                    "tags_gained_net": inv.get("evidence_tags_gained_net") or [],
                    "tags_lost_net": inv.get("evidence_tags_lost_net") or [],
                    "roles_gained_net": inv.get("evidence_roles_gained_net") or [],
                    "roles_lost_net": inv.get("evidence_roles_lost_net") or [],
                    # Keep structured tags for UI linking later
                    "tags_gained_net_structured": inv.get("evidence_tags_gained_net_structured") or [],
                    "tags_lost_net_structured": inv.get("evidence_tags_lost_net_structured") or [],
                    # NEW: NNUE-driven relevance to help the LLM choose which tags to explain vs omit
                    "nnue_tag_relevance": nnue_tag_relevance,
                },
                "evidence_ref": {
                    "source": "evidence_pgn_line",
                    "pgn_line": evidence_pgn_line,
                },
            }
        )

    # Claim 3: overestimated moves as "hidden tactic candidates" (deterministic)
    if isinstance(overestimated_moves, list) and overestimated_moves:
        for mv in overestimated_moves[:8]:
            if not isinstance(mv, str) or not mv.strip():
                continue
            claims.append(
                {
                    "claim_type": "overestimated_move",
                    "statement": "D2 ranks this move above D16 best move (candidate hidden tactic / refutation zone)",
                    "support": {
                        "move": mv,
                        "best_move_d16": best_move_d16,
                        "eval_d16": eval_d16,
                        "eval_d2": eval_d2,
                    },
                    "evidence_ref": {
                        "source": "overestimated_moves",
                        "move": mv,
                    },
                }
            )

    # Claim 4: criticality flag (if present)
    if is_critical is True:
        claims.append(
            {
                "claim_type": "critical_position",
                "statement": "Position is critical: best and second-best differ materially (D16 gap)",
                "support": {
                    "best_move_d16": best_move_d16,
                    "second_best_move_d16": inv.get("second_best_move_d16"),
                    "best_move_d16_eval_cp": inv.get("best_move_d16_eval_cp"),
                    "second_best_move_d16_eval_cp": inv.get("second_best_move_d16_eval_cp"),
                },
                "evidence_ref": {"source": "root", "field": "is_critical"},
            }
        )

    # Claim 5: Threat claims (spec requirement: threats at every node with >= 60cp significance)
    # Root threat claim
    exploration_tree = inv.get("exploration_tree") or {}
    root_threat_claim = exploration_tree.get("threat_claim")
    if isinstance(root_threat_claim, dict) and root_threat_claim.get("threat_significance_cp", 0) >= 60:
        claims.append(
            {
                "claim_type": "threat",
                "statement": f"Significant threat detected: opponent has narrow options (gap: {root_threat_claim.get('threat_significance_cp')}cp)",
                "support": {
                    "threat_significance_cp": root_threat_claim.get("threat_significance_cp"),
                    "threat_eval_cp": root_threat_claim.get("threat_eval_cp"),
                    "threat_move_san": root_threat_claim.get("threat_move_san"),
                    "threat_pv_san": root_threat_claim.get("threat_pv_san", []),
                    "threatening_side": root_threat_claim.get("threatening_side"),
                    "explanation": "If this threat is ignored, opponent has limited good responses",
                },
                "evidence_ref": {
                    "source": "root_threat_analysis",
                    "threat_position_fen": root_threat_claim.get("threat_position_fen"),
                },
            }
        )
    
    # PV threat claims (threats along the principal variation)
    pv_threat_claims = exploration_tree.get("pv_threat_claims") or []
    for pv_threat in pv_threat_claims[:5]:  # Limit to first 5 PV threats
        if isinstance(pv_threat, dict) and pv_threat.get("threat_significance_cp", 0) >= 60:
            claims.append(
                {
                    "claim_type": "threat",
                    "statement": f"Threat along PV at move {pv_threat.get('pv_move_index', 0)+1} ({pv_threat.get('pv_move_san', '?')}): narrow opponent options (gap: {pv_threat.get('threat_significance_cp')}cp)",
                    "support": {
                        "threat_significance_cp": pv_threat.get("threat_significance_cp"),
                        "threat_eval_cp": pv_threat.get("threat_eval_cp"),
                        "threat_move_san": pv_threat.get("threat_move_san"),
                        "threat_pv_san": pv_threat.get("threat_pv_san", []),
                        "pv_move_index": pv_threat.get("pv_move_index"),
                        "pv_move_san": pv_threat.get("pv_move_san"),
                        "threatening_side": pv_threat.get("threatening_side"),
                        "explanation": "Along the principal variation, opponent faces a significant threat",
                    },
                    "evidence_ref": {
                        "source": "pv_threat_analysis",
                        "threat_position_fen": pv_threat.get("threat_position_fen"),
                    },
                }
            )
    
    # Branch threat claims (threats in alternate branches)
    branches = exploration_tree.get("branches") or []
    for branch_idx, branch in enumerate(branches[:3]):  # Limit to first 3 branches
        if not isinstance(branch, dict):
            continue
        branch_threat = branch.get("threat_claim")
        if isinstance(branch_threat, dict) and branch_threat.get("threat_significance_cp", 0) >= 60:
            move_played = branch.get("move_played", "?")
            claims.append(
                {
                    "claim_type": "threat",
                    "statement": f"Threat in alternate branch ({move_played}): opponent has narrow options (gap: {branch_threat.get('threat_significance_cp')}cp)",
                    "support": {
                        "threat_significance_cp": branch_threat.get("threat_significance_cp"),
                        "threat_eval_cp": branch_threat.get("threat_eval_cp"),
                        "threat_move_san": branch_threat.get("threat_move_san"),
                        "threat_pv_san": branch_threat.get("threat_pv_san", []),
                        "branch_move": move_played,
                        "threatening_side": branch_threat.get("threatening_side"),
                        "explanation": "In this alternate line, opponent faces a significant threat",
                    },
                    "evidence_ref": {
                        "source": "branch_threat_analysis",
                        "branch_index": branch_idx,
                        "threat_position_fen": branch_threat.get("threat_position_fen"),
                    },
                }
            )

    return claims


