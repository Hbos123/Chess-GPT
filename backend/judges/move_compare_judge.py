from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


def _score_move_result(r: Dict[str, Any]) -> Tuple[int, str]:
    """
    Lower is better. Returns (score, reason).
    We primarily use cp_loss if available; else fallback to quality.
    """
    if not isinstance(r, dict):
        return 10_000, "invalid_result"
    if r.get("error"):
        return 50_000, "error"

    cp_loss = r.get("cp_loss")
    if isinstance(cp_loss, (int, float)):
        return int(cp_loss), "cp_loss"

    quality = str(r.get("quality") or "").lower().strip()
    quality_score = {
        "excellent": 10,
        "good": 50,
        "inaccuracy": 120,
        "mistake": 250,
        "blunder": 500,
    }.get(quality, 10_000)
    return quality_score, "quality"


def judge_compare_moves(compare: Dict[str, Any]) -> Dict[str, Any]:
    moves = compare.get("moves") if isinstance(compare, dict) else None
    if not isinstance(moves, list) or not moves:
        return {"winner": None, "reason": "no_moves"}

    scored: List[Dict[str, Any]] = []
    for m in moves:
        if not isinstance(m, dict):
            continue
        mv = m.get("move") or m.get("move_san") or m.get("moveSAN")
        score, by = _score_move_result(m)
        scored.append({"move": mv, "score": score, "by": by, "cp_loss": m.get("cp_loss"), "quality": m.get("quality")})

    scored_sorted = sorted(scored, key=lambda x: x.get("score", 10_000))
    winner = scored_sorted[0]["move"] if scored_sorted else None
    return {
        "winner": winner,
        "scored": scored_sorted,
        "reason": "lowest_score",
    }






