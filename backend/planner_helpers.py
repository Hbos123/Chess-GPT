"""
Helper functions for Planner layer.
Provides organized legal moves and position tags to help Planner make decisions.
"""

import chess
from typing import Dict, List, Any, Optional
from parallel_analyzer import compute_themes_and_tags
from threat_detector import detect_all_threats

_LEGAL_MOVES_CACHE: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
_TAGS_CACHE: Dict[str, Dict[str, Any]] = {}


def _norm_fen_key(fen: str) -> str:
    """Normalize FEN for caching: keep position + turn + castling + ep, drop move counters."""
    try:
        return " ".join((fen or "").split()[:4])
    except Exception:
        return fen or ""


def get_legal_moves_by_piece(fen: str) -> Dict[str, List[Dict[str, Any]]]:
    """
    Get all legal moves organized by piece type.
    
    Args:
        fen: FEN string of position
        
    Returns:
        {
            "pawns": [
                {"move_san": "e4", "move_uci": "e2e4", "from_square": "e2", "to_square": "e4", "is_capture": False, "piece": "P", "is_check": False},
                ...
            ],
            "knights": [...],
            "bishops": [...],
            "rooks": [...],
            "queens": [...],
            "king": [...],
            "castling": [...]
        }
    """
    cache_key = _norm_fen_key(fen)
    cached = _LEGAL_MOVES_CACHE.get(cache_key)
    if cached is not None:
        return cached

    board = chess.Board(fen)
    side_to_move = board.turn
    
    piece_names = {
        chess.PAWN: "Pawn",
        chess.KNIGHT: "Knight",
        chess.BISHOP: "Bishop",
        chess.ROOK: "Rook",
        chess.QUEEN: "Queen",
        chess.KING: "King"
    }
    
    moves_by_piece = {
        "pawns": [],
        "knights": [],
        "bishops": [],
        "rooks": [],
        "queens": [],
        "king": [],
        "castling": []
    }
    
    for move in board.legal_moves:
        from_sq = move.from_square
        to_sq = move.to_square
        piece = board.piece_at(from_sq)
        
        if not piece:
            continue
        
        move_data = {
            "move_san": board.san(move),
            "move_uci": move.uci(),
            "from_square": chess.square_name(from_sq),
            "to_square": chess.square_name(to_sq),
            "is_capture": board.is_capture(move),
            "is_check": False,  # Will check below
            "is_promotion": move.promotion is not None,
            "piece": piece.symbol(),
            "piece_name": piece_names.get(piece.piece_type, "Unknown")
        }
        
        # Check if move gives check
        board.push(move)
        move_data["is_check"] = board.is_check()
        board.pop()
        
        # Check if move is castling
        if board.is_castling(move):
            moves_by_piece["castling"].append(move_data)
        else:
            # Organize by piece type
            if piece.piece_type == chess.PAWN:
                moves_by_piece["pawns"].append(move_data)
            elif piece.piece_type == chess.KNIGHT:
                moves_by_piece["knights"].append(move_data)
            elif piece.piece_type == chess.BISHOP:
                moves_by_piece["bishops"].append(move_data)
            elif piece.piece_type == chess.ROOK:
                moves_by_piece["rooks"].append(move_data)
            elif piece.piece_type == chess.QUEEN:
                moves_by_piece["queens"].append(move_data)
            elif piece.piece_type == chess.KING:
                moves_by_piece["king"].append(move_data)
    
    # Sort each category by priority:
    # 1. Captures first
    # 2. Checks second
    # 3. Then by piece value (queen > rook > bishop/knight > pawn)
    # 4. Then alphabetically by square
    
    def sort_key(move_data):
        return (
            not move_data["is_capture"],  # Captures first (False < True)
            not move_data["is_check"],    # Checks second
            -piece_value(move_data["piece"]),  # Higher value first
            move_data["from_square"]      # Then by square
        )
    
    for category in moves_by_piece:
        moves_by_piece[category].sort(key=sort_key)
    
    # Best-effort bounded cache (FIFO-ish)
    if len(_LEGAL_MOVES_CACHE) > 256:
        try:
            _LEGAL_MOVES_CACHE.pop(next(iter(_LEGAL_MOVES_CACHE)))
        except Exception:
            _LEGAL_MOVES_CACHE.clear()
    _LEGAL_MOVES_CACHE[cache_key] = moves_by_piece
    return moves_by_piece


def piece_value(piece_symbol: str) -> int:
    """Get piece value for sorting"""
    values = {
        "P": 1, "p": 1,
        "N": 3, "n": 3,
        "B": 3, "b": 3,
        "R": 5, "r": 5,
        "Q": 9, "q": 9,
        "K": 0, "k": 0
    }
    return values.get(piece_symbol, 0)


def get_relevant_tags(fen: str, focus: Optional[str] = None) -> Dict[str, Any]:
    """
    Get relevant tags for the position, optionally filtered by focus.
    
    Args:
        fen: FEN string of position
        focus: Optional focus (e.g., "knight", "bishop", "doubled_pawns")
        
    Returns:
        {
            "all_tags": [...],  # All tags
            "relevant_tags": [...],  # Filtered by focus if provided
            "tag_summary": "...",  # Brief summary of key tags
            "threats": {
                "white": [...],
                "black": [...]
            },
            "positional_tags": [...],  # Non-tactical tags
            "tactical_tags": [...]  # Tactical tags (threats, pins, etc.)
        }
    """
    cache_key = f"{_norm_fen_key(fen)}|focus:{(focus or '').strip().lower()}"
    cached = _TAGS_CACHE.get(cache_key)
    if cached is not None:
        return cached

    board = chess.Board(fen)
    
    # Get all tags using parallel_analyzer
    themes_and_tags = compute_themes_and_tags(fen)
    all_tags = themes_and_tags.get("tags", [])
    
    # Get threat tags separately
    white_threats = detect_all_threats(board, chess.WHITE)
    black_threats = detect_all_threats(board, chess.BLACK)
    
    # Categorize tags
    tactical_tags = []
    positional_tags = []
    
    for tag in all_tags:
        tag_name = tag.get("tag_name", "")
        if any(keyword in tag_name for keyword in ["threat", "pin", "fork", "skewer", "attack", "hanging", "capture"]):
            tactical_tags.append(tag)
        else:
            positional_tags.append(tag)
    
    # Filter by focus if provided
    relevant_tags = all_tags
    if focus:
        focus_lower = focus.lower()
        relevant_tags = [
            tag for tag in all_tags
            if (focus_lower in tag.get("tag_name", "").lower() or
                focus_lower in str(tag.get("pieces", [])).lower() or
                focus_lower in str(tag.get("squares", [])).lower() or
                focus_lower in str(tag.get("side", "")).lower())
        ]
    
    # Create tag summary
    tag_summary_parts = []
    if tactical_tags:
        tag_summary_parts.append(f"{len(tactical_tags)} tactical tags")
    if positional_tags:
        tag_summary_parts.append(f"{len(positional_tags)} positional tags")
    if white_threats:
        tag_summary_parts.append(f"{len(white_threats)} white threats")
    if black_threats:
        tag_summary_parts.append(f"{len(black_threats)} black threats")
    
    tag_summary = ", ".join(tag_summary_parts) if tag_summary_parts else "No significant tags"
    
    result = {
        "all_tags": all_tags,
        "relevant_tags": relevant_tags,
        "tag_summary": tag_summary,
        "threats": {
            "white": white_threats,
            "black": black_threats
        },
        "positional_tags": positional_tags,
        "tactical_tags": tactical_tags
    }

    if len(_TAGS_CACHE) > 256:
        try:
            _TAGS_CACHE.pop(next(iter(_TAGS_CACHE)))
        except Exception:
            _TAGS_CACHE.clear()
    _TAGS_CACHE[cache_key] = result
    return result


def prepare_planner_context(
    fen: str,
    intent_plan: Any,  # IntentPlan type
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Prepare comprehensive context for Planner.
    Includes legal moves organized by piece and relevant tags.
    
    Args:
        fen: FEN string of position
        intent_plan: IntentPlan from Interpreter
        context: Additional context
        
    Returns:
        Dict with all information Planner needs
    """
    # Get legal moves organized by piece
    legal_moves = get_legal_moves_by_piece(fen)
    
    # Get relevant tags (filter by focus if provided)
    focus = None
    if intent_plan.investigation_requests:
        # Use focus from first investigation request
        focus = intent_plan.investigation_requests[0].focus
    
    tags_info = get_relevant_tags(fen, focus=focus)
    # Keep planner context small (vLLM context window is limited).
    # We only need summaries + a small sample of tags/threats to guide planning.
    try:
        if isinstance(tags_info, dict):
            slim: Dict[str, Any] = {}
            slim["tag_summary"] = tags_info.get("tag_summary")
            # Keep only a small number of tags (relevant_tags preferred).
            rel_tags = tags_info.get("relevant_tags")
            all_tags = tags_info.get("all_tags")
            if isinstance(rel_tags, list) and rel_tags:
                slim["relevant_tags"] = rel_tags[:12]
            elif isinstance(all_tags, list) and all_tags:
                slim["relevant_tags"] = all_tags[:12]
            # Keep small threat samples, not full lists.
            thr = tags_info.get("threats")
            if isinstance(thr, dict):
                slim_thr: Dict[str, Any] = {}
                for side in ("white", "black"):
                    items = thr.get(side)
                    if isinstance(items, list):
                        slim_thr[side] = items[:8]
                if slim_thr:
                    slim["threats"] = slim_thr
            tags_info = slim
    except Exception:
        pass
    
    # Count total moves
    total_moves = sum(len(moves) for moves in legal_moves.values())
    
    cached_analysis = context.get("cached_analysis") if isinstance(context, dict) else None
    analysis_summary = summarize_cached_analysis(cached_analysis)

    # NEW: baseline intuition summary (if prefetched) to avoid reliance on raw cached_analysis.
    baseline = context.get("baseline_intuition") if isinstance(context, dict) else None
    baseline_summary = None
    try:
        if isinstance(baseline, dict):
            scan_root = baseline.get("scan_root") if isinstance(baseline.get("scan_root"), dict) else None
            if isinstance(scan_root, dict):
                baseline_summary = {
                    "root_eval_d2": scan_root.get("root", {}).get("eval_d2") if isinstance(scan_root.get("root"), dict) else None,
                    "root_eval_d16": scan_root.get("root", {}).get("eval_d16") if isinstance(scan_root.get("root"), dict) else None,
                    "root_best_move_d16_san": scan_root.get("root", {}).get("best_move_d16_san") if isinstance(scan_root.get("root"), dict) else None,
                    "claims_count": len(scan_root.get("claims") or []) if isinstance(scan_root.get("claims"), list) else 0,
                    "motifs_count": len(scan_root.get("motifs") or []) if isinstance(scan_root.get("motifs"), list) else 0,
                }
    except Exception:
        baseline_summary = None

    return {
        "fen": fen,
        "legal_moves_by_piece": legal_moves,
        "total_legal_moves": total_moves,
        "tags": tags_info,
        "intent": intent_plan.intent,
        "goal": intent_plan.goal,
        "investigation_requests": [
            {
                "investigation_type": req.investigation_type,
                "focus": req.focus,
                "purpose": req.purpose
            }
            for req in intent_plan.investigation_requests
        ],
        "side_to_move": "white" if chess.Board(fen).turn == chess.WHITE else "black",
        "analysis_summary": analysis_summary,
        "baseline_summary": baseline_summary,
    }


def summarize_cached_analysis(cached_analysis: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Create a compact summary of cached analysis data for the planner."""
    if not isinstance(cached_analysis, dict):
        return None

    summary: Dict[str, Any] = {}

    eval_cp = cached_analysis.get("eval_cp")
    if eval_cp is not None:
        summary["eval_cp"] = eval_cp

    best_move = cached_analysis.get("best_move")
    if best_move:
        summary["best_move"] = best_move

    candidate_moves = cached_analysis.get("candidate_moves") or []
    condensed_candidates = []
    for candidate in candidate_moves[:3]:
        move = candidate.get("move")
        if not move:
            continue
        pv_value = candidate.get("pv_san")
        if isinstance(pv_value, list):
            pv_str = " ".join(pv_value[:5])
        elif isinstance(pv_value, str):
            pv_str = pv_value[:100]
        else:
            pv_str = ""
        condensed_candidates.append({
            "move": move,
            "eval_cp": candidate.get("eval_cp"),
            "pv": pv_str
        })
    if condensed_candidates:
        summary["candidate_moves"] = condensed_candidates

    def _extract_insights(side_key: str) -> List[Dict[str, Any]]:
        side_data = cached_analysis.get(side_key, {})
        chunk = side_data.get("chunk_3_most_significant", {})
        insights = chunk.get("insights", []) if isinstance(chunk, dict) else []
        result = []
        for insight in insights[:2]:
            text = insight.get("insight") or insight.get("summary")
            if not text:
                continue
            trimmed = text if len(text) <= 200 else text[:200] + "..."
            result.append({
                "side": "white" if side_key.startswith("white") else "black",
                "insight": trimmed,
                "score": insight.get("significance_score")
            })
        return result

    insights = _extract_insights("white_analysis") + _extract_insights("black_analysis")
    if insights:
        summary["top_insights"] = insights[:3]

    threats = cached_analysis.get("threats")
    if isinstance(threats, dict):
        summary["threat_counts"] = {
            "white": len(threats.get("white") or []),
            "black": len(threats.get("black") or [])
        }

        def _format_threat(threat_entry: Dict[str, Any]) -> Dict[str, Any]:
            return {
                "threat": threat_entry.get("threat") or threat_entry.get("description"),
                "delta_cp": threat_entry.get("delta_cp")
            }

        white_samples = (threats.get("white") or [])[:1]
        black_samples = (threats.get("black") or [])[:1]
        sample_threats = {}
        if white_samples:
            sample_threats["white"] = [_format_threat(white_samples[0])]
        if black_samples:
            sample_threats["black"] = [_format_threat(black_samples[0])]
        if sample_threats:
            summary["sample_threats"] = sample_threats

    return summary or None



