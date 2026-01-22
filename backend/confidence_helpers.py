from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple, TYPE_CHECKING

import chess
import chess.engine

if TYPE_CHECKING:
    from engine_queue import StockfishQueue

__all__ = [
    "PVAnalysis",
    "MoveCandidate",
    "analyse_pv",
    "analyse_multipv",
    "evaluate_branch",
]


@dataclass(frozen=True)
class PVAnalysis:
    score_cp: int
    moves: List[chess.Move]


@dataclass(frozen=True)
class MoveCandidate:
    score_cp: int
    move: chess.Move
    pv: List[chess.Move]


async def analyse_pv(
    engine_queue: "StockfishQueue",
    board: chess.Board,
    *,
    depth: int,
    max_length: Optional[int] = None,
) -> PVAnalysis:
    info = await engine_queue.enqueue(
        engine_queue.engine.analyse,
        board,
        chess.engine.Limit(depth=depth)
    )
    score = _extract_score(info)
    pv_moves = _extract_pv(info)
    if max_length is not None:
        pv_moves = pv_moves[:max_length]
    return PVAnalysis(score, pv_moves)


async def analyse_multipv(
    engine_queue: "StockfishQueue",
    board: chess.Board,
    *,
    depth: int,
    multipv: int,
) -> List[MoveCandidate]:
    multipv = max(1, multipv)
    info = await engine_queue.enqueue(
        engine_queue.engine.analyse,
        board,
        chess.engine.Limit(depth=depth),
        multipv=multipv
    )
    records = info if isinstance(info, list) else [info]
    candidates: List[MoveCandidate] = []
    for record in records:
        pv = _extract_pv(record)
        if not pv:
            continue
        score = _extract_score(record)
        candidates.append(MoveCandidate(score_cp=score, move=pv[0], pv=pv))
    candidates.sort(key=lambda item: item.score_cp, reverse=True)
    return candidates


async def evaluate_branch(
    engine_queue: "StockfishQueue",
    board: chess.Board,
    move: chess.Move,
    *,
    max_depth: int,
    opponent_depth: int,
    max_ply_from_s0: int,
    ply_so_far: int,
) -> Tuple[chess.Board, int, Optional[chess.Move], int]:
    branch_board = board.copy()
    branch_board.push(move)
    branch_eval = await analyse_pv(engine_queue, branch_board, depth=max_depth)
    reply_move: Optional[chess.Move] = None
    reply_conf = _score_to_cp_value(branch_eval.score_cp)
    if branch_eval.moves and ply_so_far + 2 <= max_ply_from_s0:
        reply_move = branch_eval.moves[0]
        reply_board = branch_board.copy()
        reply_board.push(reply_move)
        reply_eval = await analyse_pv(engine_queue, reply_board, depth=opponent_depth)
        reply_conf = _score_to_cp_value(reply_eval.score_cp)
        return reply_board, reply_conf, reply_move, reply_conf
    return branch_board, reply_conf, reply_move, reply_conf


def _extract_score(info: chess.engine.InfoDict) -> int:
    score = info.get("score")
    if score is None:
        return 0
    return _score_to_cp_value(_score_to_cp_obj(score))


def _extract_pv(info: chess.engine.InfoDict) -> List[chess.Move]:
    pv = info.get("pv")
    if pv is None:
        return []
    return list(pv)


def _score_to_cp_value(score_cp: int, *, mate_as: int = 900) -> int:
    return max(-mate_as, min(mate_as, int(score_cp)))


def _score_to_cp_obj(score: chess.engine.PovScore) -> int:
    if score.is_mate():
        mate = score.relative.mate()
        mate_as = 900
        return mate_as if (mate and mate > 0) else -mate_as
    return int(score.relative.score(mate_score=900))
