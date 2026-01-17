from __future__ import annotations

from typing import Any, Dict

from board_tools import analyze_fen_stockfish

async def evaluate_position(
    *,
    tool_executor,
    context: Dict[str, Any],
    engine_queue=None,
    engine_pool_instance=None,
    depth: int,
    lines: int = 2,
    light_mode: bool = True,
) -> Dict[str, Any]:
    """
    Engine-backed evaluation using existing ToolExecutor implementation.
    Returns the tool executor result dict.
    """
    # Prefer the in-process "temporary board" (no HTTP hop, fast, deterministic output).
    fen = (context or {}).get("board_state") or (context or {}).get("fen")
    if isinstance(fen, str) and fen.strip():
        r = await analyze_fen_stockfish(
            fen=fen,
            engine_queue=engine_queue,
            engine_pool_instance=engine_pool_instance,
            depth=int(depth),
            multipv=int(lines),
            max_pv_plies=32,
        )
        if isinstance(r, dict) and r.get("success"):
            # Back-compat with existing callers that expect candidate_moves (from /analyze_position):
            # provide a compact candidate list derived from top_moves.
            top_moves = r.get("top_moves") if isinstance(r.get("top_moves"), list) else []
            candidate_moves = []
            for tm in top_moves:
                if not isinstance(tm, dict):
                    continue
                candidate_moves.append(
                    {
                        "move": tm.get("move_san"),
                        "eval_cp": tm.get("eval_cp"),
                        "pv_san": tm.get("pv_san"),
                    }
                )
            r["candidate_moves"] = candidate_moves
            r["from_cache"] = False
            return r

    # Fallback: old tool executor path (may call /analyze_position endpoint via HTTP).
    args = {"depth": int(depth), "lines": int(lines), "light_mode": bool(light_mode)}
    return await tool_executor._analyze_position(args, context)  # type: ignore[attr-defined]


