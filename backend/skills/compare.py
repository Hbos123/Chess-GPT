from __future__ import annotations

from typing import Any, Dict, List

import chess


async def compare_moves(
    *,
    tool_executor,
    context: Dict[str, Any],
    fen: str,
    moves_san: List[str],
    depth: int = 10,
) -> Dict[str, Any]:
    """
    Compare candidate SAN moves by running ToolExecutor._analyze_move for each.
    Returns a structured comparison result.
    """
    out: Dict[str, Any] = {"fen": fen, "depth": depth, "moves": []}
    board = chess.Board(fen)

    for ms in moves_san:
        ms_s = (ms or "").strip()
        if not ms_s:
            continue
        # Validate legality and pass fen as the position before move.
        try:
            mv = board.parse_san(ms_s)
            if mv not in board.legal_moves:
                out["moves"].append({"move": ms_s, "error": "illegal"})
                continue
        except Exception as e:
            out["moves"].append({"move": ms_s, "error": f"parse_error:{str(e)[:80]}"})
            continue

        r = await tool_executor._analyze_move(  # type: ignore[attr-defined]
            {"move_san": ms_s, "fen": fen, "depth": int(depth)},
            context,
        )
        out["moves"].append(r)
    return out






