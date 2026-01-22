from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Dict, Optional

import chess

from investigator import Investigator


@dataclass
class ScanPolicy:
    d2_depth: int = 2
    d16_depth: int = 16
    branching_limit: int = 4
    max_pv_plies: int = 16
    include_pgn: bool = True
    pgn_max_chars: int = 12000
    timeout_s: float = 18.0


async def scan_d2_d16(
    *,
    investigator: Investigator,
    start_fen: str,
    policy: ScanPolicy,
) -> Dict[str, Any]:
    """
    Run D2/D16 dual-depth investigation from a FEN, with bounded branching and optional PGN.
    Returns a compact response for API consumers.
    """
    try:
        b = chess.Board(start_fen)
        fen = b.fen()
    except Exception as e:
        return {"error": f"Invalid FEN: {str(e)}"}

    async def _run():
        res = await investigator.investigate_with_dual_depth(
            fen,
            scope="general_position",
            depth_16=int(policy.d16_depth),
            depth_2=int(policy.d2_depth),
            original_fen=fen,
            branching_limit=int(policy.branching_limit),
            max_pv_plies=int(policy.max_pv_plies),
            include_pgn=bool(policy.include_pgn),
            pgn_max_chars=int(policy.pgn_max_chars),
        )
        # Compact shape
        return {
            "fen": fen,
            "root": {
                "eval_d2": res.eval_d2,
                "eval_d16": res.eval_d16,
                "best_move_d16_san": res.best_move_d16,
                "best_move_d16_eval_cp": res.best_move_d16_eval_cp,
                "second_best_d16_san": res.second_best_move_d16,
                "second_best_d16_eval_cp": res.second_best_move_d16_eval_cp,
                "is_critical": res.is_critical,
                "is_winning": res.is_winning,
            },
            "top_moves_d2": res.top_moves_d2,
            "overestimated_moves": res.overestimated_moves,
            "exploration_tree": res.exploration_tree,
            "pgn_bundle": {"fen": fen, "pgn": (res.pgn_exploration if policy.include_pgn else "")},
            "pgn_exploration": res.pgn_exploration if policy.include_pgn else "",
            "commentary": res.commentary or {},
        }

    try:
        return await asyncio.wait_for(_run(), timeout=float(policy.timeout_s))
    except asyncio.TimeoutError:
        return {"error": f"scan timeout after {policy.timeout_s}s"}


