from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

import chess

from board_tools import apply_line, analyze_fen_stockfish
from light_raw_analyzer import compute_light_raw_analysis


def _clean(s: Any) -> str:
    return (str(s) if s is not None else "").strip()


def _join_san_line(moves: Any, *, max_plies: int = 10, max_chars: int = 160) -> str:
    if not isinstance(moves, list):
        return ""
    out: List[str] = []
    for m in moves[:max_plies]:
        if isinstance(m, str) and m.strip():
            out.append(m.strip())
    s = " ".join(out).strip()
    if not s:
        return ""
    return (s[:max_chars] + "…") if len(s) > max_chars else s


def _factor_keywords(factor: str) -> List[str]:
    f = (factor or "").lower()
    if "king safety" in f:
        return ["king", "castl", "shield", "backrank", "open_file", "file.open", "threat", "mate"]
    if "pawn structure" in f:
        return ["pawn", "structure", "isolated", "doubled", "backward", "chain", "lever"]
    if "piece activity" in f or "activity" in f:
        return ["activity", "mobility", "diagonal.open", "file.open", "outpost", "rook", "bishop", "knight"]
    if "center" in f or "space" in f:
        return ["center", "space", "control", "e4", "d4", "e5", "d5"]
    if "square" in f or "control" in f:
        return ["square", "control", "outpost", "weak_square", "hole"]
    return [w for w in re.split(r"[\s/_-]+", f) if w]


def _pick_tag_examples(
    *,
    factors: List[str],
    light_raw: Optional[Dict[str, Any]],
    max_examples: int = 2,
) -> List[Dict[str, Any]]:
    """
    Select concrete, citeable tag examples for the given high-level factors.
    Deterministic: first matching tags by keyword.
    """
    if not isinstance(light_raw, dict):
        return []
    tags = light_raw.get("tags")
    if not isinstance(tags, list):
        return []

    out: List[Dict[str, Any]] = []
    used = set()

    def _humanize_tag_sentence(*, factor: str, name: str, squares: List[Any], files: List[Any], pieces: List[Any], details: Dict[str, Any]) -> str:
        nm = (name or "").lower()
        sqs = [ _clean(s) for s in (squares or []) if _clean(s) ][:6]
        fls = [ _clean(f) for f in (files or []) if _clean(f) ][:3]
        pcs = [ _clean(p) for p in (pieces or []) if _clean(p) ][:3]

        # Prefer chess-geometric phrasing where possible.
        if "tag.diagonal.open." in nm:
            # e.g. tag.diagonal.open.e2-a6
            diag = name.split("tag.diagonal.open.", 1)[-1]
            diag = diag.replace(".", "").strip()
            if diag:
                core = f"your {('bishop' if any(p.startswith('B') for p in pcs) else 'piece')} has an open diagonal {diag}"
            else:
                core = "you've opened a diagonal for your pieces"
            if sqs:
                core += " through " + ", ".join(sqs)
            return f"For example, {core}."

        if "tag.file.open." in nm or "tag.file.semi." in nm:
            f0 = fls[0] if fls else None
            if f0:
                core = f"the {f0}-file is open/semi-open"
            else:
                core = "an open/semi-open file is available"
            return f"For example, {core}."

        if "center" in (factor or "").lower() or "space" in (factor or "").lower() or "control" in (factor or "").lower():
            if sqs:
                return f"For example, you have influence over squares {', '.join(sqs)}."

        if (factor or "").lower().strip() == "piece activity":
            if pcs:
                return f"For example, {pcs[0]} becomes more active."

        # Fallback: factor + some concrete geometry.
        core = (factor or "this idea").strip()
        if sqs:
            return f"For example, {core} shows up on squares {', '.join(sqs)}."
        if pcs:
            return f"For example, {core} involves {', '.join(pcs)}."
        return f"For example, {core}."

    for factor in (factors or [])[:4]:
        kws = _factor_keywords(factor)
        chosen = None
        for t in tags:
            if not isinstance(t, dict):
                continue
            name = _clean(t.get("tag_name") or t.get("name") or t.get("tag"))
            if not name or name in used:
                continue
            low = name.lower()
            if any(k in low for k in kws):
                chosen = t
                used.add(name)
                break
        if not chosen:
            continue

        name = _clean(chosen.get("tag_name") or chosen.get("name") or chosen.get("tag"))
        squares = chosen.get("squares") if isinstance(chosen.get("squares"), list) else []
        files = chosen.get("files") if isinstance(chosen.get("files"), list) else []
        pieces = chosen.get("pieces") if isinstance(chosen.get("pieces"), list) else []
        details = chosen.get("details") if isinstance(chosen.get("details"), dict) else {}

        sentence = _humanize_tag_sentence(
            factor=factor,
            name=name,
            squares=squares,
            files=files,
            pieces=pieces,
            details=details,
        )
        out.append({"factor": factor, "sentence": sentence})
        if len(out) >= max_examples:
            break

    return out


def _mentioned_piece_type(user_message: str) -> Optional[chess.PieceType]:
    m = (user_message or "").lower()
    # Keep generic: only piece-type words, no test-case-specific strings.
    if "knight" in m:
        return chess.KNIGHT
    if "bishop" in m:
        return chess.BISHOP
    if "rook" in m:
        return chess.ROOK
    if "queen" in m:
        return chess.QUEEN
    if "king" in m:
        return chess.KING
    return None


def should_run_development_counterfactuals(user_message: str) -> bool:
    m = (user_message or "").lower()
    return bool(re.search(r"\b(develop|development|activate|bring\s+out|castle|castling|get\s+out)\b", m))


def _candidate_developing_moves(fen: str, user_message: str, *, max_moves: int = 4) -> List[str]:
    try:
        b = chess.Board(fen)
    except Exception:
        return []
    piece_type = _mentioned_piece_type(user_message)

    moves: List[str] = []
    for mv in b.legal_moves:
        p = b.piece_at(mv.from_square)
        if not p:
            continue
        # Prefer non-pawn moves for "development" counterfactuals.
        if p.piece_type == chess.PAWN:
            continue
        if piece_type is not None and p.piece_type != piece_type:
            continue
        try:
            san = b.san(mv)
        except Exception:
            continue
        if san and san not in moves:
            moves.append(san)
        if len(moves) >= max_moves:
            break
    return moves


def _compute_per_ply_deltas(
    *,
    start_fen: str,
    pv_moves: List[str],
    max_plies: int = 4,
) -> List[Dict[str, Any]]:
    """
    Compute tag/theme deltas for each ply in the PV.
    
    For each transition fen_i -> fen_{i+1}:
    - Compute tags before and after the move
    - Compute theme scores before and after
    - Return gained/lost tags and theme changes
    
    Args:
        start_fen: Starting FEN
        pv_moves: List of SAN moves (max 4 plies)
        max_plies: Maximum number of plies to analyze (default 4)
        
    Returns:
        List of delta dicts, one per ply:
        [
          {
            "ply": 1,
            "move": "d4",
            "tags_gained": ["tag.diagonal.open.e2-a6", ...],
            "tags_lost": ["tag.square.weak.d4", ...],
            "theme_changes": {"S_CENTER_SPACE": +2.1, ...},
            "geometry": {"squares": ["e4", "d5"], "diagonals": ["e2-a6"], "files": ["d"]}
          },
          ...
        ]
    """
    if not isinstance(pv_moves, list) or not pv_moves:
        return []
    
    plies = min(max_plies, len(pv_moves))
    if plies == 0:
        return []
    
    deltas: List[Dict[str, Any]] = []
    current_fen = start_fen
    
    # Determine side to move from FEN
    try:
        b = chess.Board(current_fen)
        side_to_move = "white" if b.turn == chess.WHITE else "black"
    except Exception:
        side_to_move = "white"  # Default fallback
    
    # Analyze starting position
    try:
        start_analysis = compute_light_raw_analysis(current_fen)
        start_tags_list = start_analysis.tags if hasattr(start_analysis, "tags") else []
        start_tags = {}
        for t in start_tags_list:
            if isinstance(t, dict):
                tag_name = t.get("tag_name")
                if tag_name:
                    start_tags[tag_name] = t
        start_theme_scores = {}
        if hasattr(start_analysis, "theme_scores") and isinstance(start_analysis.theme_scores, dict):
            start_theme_scores = start_analysis.theme_scores.get(side_to_move, {})
    except Exception:
        start_tags = {}
        start_theme_scores = {}
    
    for i in range(plies):
        move_san = pv_moves[i] if i < len(pv_moves) else None
        if not isinstance(move_san, str) or not move_san.strip():
            break
        
        # Apply the move
        applied = apply_line(start_fen=current_fen, moves=[move_san], fmt="auto", max_plies=1)
        if not (isinstance(applied, dict) and applied.get("success")):
            break
        
        next_fen = applied.get("end_fen")
        if not isinstance(next_fen, str) or not next_fen.strip():
            break
        
        # Determine side to move after this move (flip)
        next_side_to_move = "black" if side_to_move == "white" else "white"
        
        # Analyze position after the move
        try:
            next_analysis = compute_light_raw_analysis(next_fen)
            next_tags_list = next_analysis.tags if hasattr(next_analysis, "tags") else []
            next_tags = {}
            for t in next_tags_list:
                if isinstance(t, dict):
                    tag_name = t.get("tag_name")
                    if tag_name:
                        next_tags[tag_name] = t
            next_theme_scores = {}
            if hasattr(next_analysis, "theme_scores") and isinstance(next_analysis.theme_scores, dict):
                # After the move, we're tracking the original side's position
                # So we still use the original side_to_move for comparison
                next_theme_scores = next_analysis.theme_scores.get(side_to_move, {})
        except Exception:
            next_tags = {}
            next_theme_scores = {}
        
        # Compute tag deltas
        start_tag_names = set(start_tags.keys())
        next_tag_names = set(next_tags.keys())
        tags_gained = []
        tags_lost = []
        geometry_squares = []
        geometry_diagonals = []
        geometry_files = []
        
        for tag_name in next_tag_names - start_tag_names:
            tag = next_tags.get(tag_name, {})
            tags_gained.append(tag_name)
            # Extract geometry
            sqs = tag.get("squares", [])
            if isinstance(sqs, list):
                geometry_squares.extend([_clean(s) for s in sqs if _clean(s)])
            # Check for diagonal/file tags
            if "diagonal" in tag_name.lower():
                diag_info = tag.get("details", {})
                if isinstance(diag_info, dict):
                    target = diag_info.get("target")
                    if target:
                        geometry_diagonals.append(_clean(target))
            if "file" in tag_name.lower():
                fls = tag.get("files", [])
                if isinstance(fls, list):
                    geometry_files.extend([_clean(f) for f in fls if _clean(f)])
        
        for tag_name in start_tag_names - next_tag_names:
            tags_lost.append(tag_name)
        
        # Compute theme score deltas
        theme_changes = {}
        all_theme_keys = set(start_theme_scores.keys()) | set(next_theme_scores.keys())
        for key in all_theme_keys:
            if key == "total":
                continue
            start_val = start_theme_scores.get(key, 0.0)
            next_val = next_theme_scores.get(key, 0.0)
            delta = next_val - start_val
            if abs(delta) > 0.01:  # Only include meaningful changes
                theme_changes[key] = round(delta, 2)
        
        # Build geometry summary (deduplicated)
        geometry = {
            "squares": list(set(geometry_squares))[:8],
            "diagonals": list(set(geometry_diagonals))[:4],
            "files": list(set(geometry_files))[:4],
        }
        
        deltas.append({
            "ply": i + 1,
            "move": move_san.strip(),
            "tags_gained": tags_gained[:10],  # Limit to avoid bloat
            "tags_lost": tags_lost[:10],
            "theme_changes": theme_changes,
            "geometry": geometry,
        })
        
        # Update for next iteration
        current_fen = next_fen
        start_tags = next_tags
        start_theme_scores = next_theme_scores
    
    return deltas


async def build_evidence_pack(
    *,
    fen: str,
    facts_card: Optional[Dict[str, Any]],
    light_raw: Optional[Dict[str, Any]],
    user_message: str,
    engine_queue=None,
    engine_pool_instance=None,
    dev_depth: int = 10,
) -> Dict[str, Any]:
    """
    Build a small, citeable evidence object for the explainer.
    This is engine-first: citations come from PVs / tags / deterministic move comparisons.
    """
    evidence: Dict[str, Any] = {"tag_examples": [], "development_counterfactuals": [], "pv_move_deltas": []}

    # 1) Tag examples for positional factors (if available)
    try:
        factors = []
        if isinstance(facts_card, dict):
            pf = facts_card.get("positional_factors")
            if isinstance(pf, list):
                factors = [str(x) for x in pf if str(x).strip()]
        evidence["tag_examples"] = _pick_tag_examples(factors=factors, light_raw=light_raw, max_examples=2)
    except Exception:
        evidence["tag_examples"] = []
    
    # 1.5) Per-ply deltas for PV (deterministic, move-by-move evidence)
    try:
        pv_moves = []
        if isinstance(facts_card, dict):
            top_moves = facts_card.get("top_moves")
            if isinstance(top_moves, list) and top_moves:
                # Prefer PV from recommended move, otherwise first move
                rec_move = facts_card.get("recommended_move")
                chosen = None
                for tm in top_moves:
                    if not isinstance(tm, dict):
                        continue
                    san = tm.get("san") or tm.get("move_san")
                    if rec_move and isinstance(san, str) and san.strip() == rec_move.strip():
                        chosen = tm
                        break
                if not chosen and top_moves:
                    chosen = top_moves[0]
                if chosen:
                    pv = chosen.get("pv_san")
                    if isinstance(pv, list):
                        pv_moves = [str(x).strip() for x in pv[:4] if isinstance(x, str) and str(x).strip()]
        
        if pv_moves:
            deltas = _compute_per_ply_deltas(start_fen=fen, pv_moves=pv_moves, max_plies=4)
            if deltas:
                evidence["pv_move_deltas"] = deltas
    except Exception as e:
        print(f"   ⚠️ [EVIDENCE] Per-ply delta computation failed: {type(e).__name__}: {e}")
        evidence["pv_move_deltas"] = []

    # 2) Development counterfactuals: show that "natural" developing moves score worse (optional/gated)
    if should_run_development_counterfactuals(user_message):
        try:
            cands = _candidate_developing_moves(fen, user_message, max_moves=4)
            # Don't waste time if nothing to compare.
            if len(cands) >= 1:
                base_eval = None
                if isinstance(facts_card, dict) and isinstance(facts_card.get("eval_cp"), (int, float)):
                    base_eval = int(facts_card.get("eval_cp"))

                for ms in cands[:3]:
                    # Apply the move and analyze the resulting position.
                    applied = apply_line(start_fen=fen, moves=[ms], fmt="auto", max_plies=1)
                    end_fen = applied.get("end_fen") if isinstance(applied, dict) else None
                    if not (isinstance(end_fen, str) and end_fen.strip()):
                        continue
                    r = await analyze_fen_stockfish(
                        fen=end_fen,
                        engine_queue=engine_queue,
                        engine_pool_instance=engine_pool_instance,
                        depth=int(dev_depth),
                        multipv=1,
                        max_pv_plies=12,
                    )
                    if not isinstance(r, dict) or not r.get("success"):
                        continue
                    ev = r.get("eval_cp")
                    pv = None
                    try:
                        top = r.get("top_moves")
                        if isinstance(top, list) and top and isinstance(top[0], dict):
                            pv = top[0].get("pv_san")
                    except Exception:
                        pv = None

                    line = _join_san_line(pv, max_plies=10, max_chars=160)
                    if not line:
                        # At least cite the played move as a 1-ply “line”
                        line = ms
                    else:
                        # Make the line self-contained by prefixing the user's candidate move.
                        # (PV is from the position after the candidate move.)
                        line = f"{ms} {line}".strip()
                    delta = (int(ev) - int(base_eval)) if isinstance(ev, (int, float)) and isinstance(base_eval, (int, float)) else None
                    evidence["development_counterfactuals"].append(
                        {
                            "move": ms,
                            "eval_cp": (int(ev) if isinstance(ev, (int, float)) else None),
                            "delta_cp_vs_best": delta,
                            "line_san": line,
                        }
                    )
        except Exception:
            pass

    return evidence


