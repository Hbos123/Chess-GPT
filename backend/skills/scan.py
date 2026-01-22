from __future__ import annotations

from typing import Any, Dict, Optional

import chess  # type: ignore

from investigator import Investigator
from scan_service import scan_d2_d16, ScanPolicy


async def scan_d2_d16_from_fen(
    *,
    engine_pool_instance,
    engine_queue,
    start_fen: str,
    policy: ScanPolicy,
) -> Dict[str, Any]:
    inv = Investigator(engine_pool=engine_pool_instance) if engine_pool_instance is not None else Investigator(engine_queue=engine_queue)
    return await scan_d2_d16(investigator=inv, start_fen=start_fen, policy=policy)


async def scan_d2_d16_after_san(
    *,
    engine_pool_instance,
    engine_queue,
    start_fen: str,
    move_san: str,
    policy: ScanPolicy,
) -> Dict[str, Any]:
    """
    Tool-like helper: apply a SAN move to a starting FEN, then run D2/D16 scan from the resulting position.
    This is the canonical way to "investigate a different move" without extra bespoke engine calls.
    """
    b = chess.Board(start_fen)
    mv = b.parse_san(move_san)
    if mv not in b.legal_moves:
        return {
            "error": "illegal_move",
            "start_fen": start_fen,
            "move_san": move_san,
        }
    b.push(mv)
    next_fen = b.fen()
    out = await scan_d2_d16_from_fen(
        engine_pool_instance=engine_pool_instance,
        engine_queue=engine_queue,
        start_fen=next_fen,
        policy=policy,
    )
    if isinstance(out, dict):
        out["after_move"] = {"start_fen": start_fen, "move_san": move_san, "fen": next_fen}
    return out


