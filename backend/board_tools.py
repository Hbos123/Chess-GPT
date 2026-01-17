from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional, Tuple

import chess
import chess.engine


MoveFormat = Literal["san", "uci", "auto"]


def _safe_san(b: chess.Board, mv: chess.Move) -> str:
    try:
        return b.san(mv)
    except Exception:
        try:
            return mv.uci()
        except Exception:
            return str(mv)


def _parse_move(b: chess.Board, token: str, fmt: MoveFormat) -> Tuple[Optional[chess.Move], Optional[str]]:
    t = (token or "").strip()
    if not t:
        return None, "empty move"
    if fmt == "uci":
        try:
            mv = chess.Move.from_uci(t)
        except Exception as e:
            return None, f"invalid uci: {str(e)[:120]}"
        return mv, None
    if fmt == "san":
        try:
            mv = b.parse_san(t)
        except Exception as e:
            return None, f"invalid san: {str(e)[:120]}"
        return mv, None
    # auto: try SAN then UCI
    try:
        mv = b.parse_san(t)
        return mv, None
    except Exception:
        try:
            mv = chess.Move.from_uci(t)
            return mv, None
        except Exception as e:
            return None, f"invalid move: {str(e)[:120]}"


def apply_line(
    *,
    start_fen: str,
    moves: List[str],
    fmt: MoveFormat = "auto",
    max_plies: int = 60,
    legal_moves_sample: int = 12,
) -> Dict[str, Any]:
    """
    Apply a SAN/UCI move list to a starting FEN on an isolated board.
    Returns a deterministic result object with error details on failure.
    """
    try:
        b = chess.Board(start_fen)
    except Exception as e:
        return {
            "success": False,
            "end_fen": None,
            "applied": [],
            "stopped_at": 0,
            "error": {"message": f"Invalid FEN: {str(e)}", "at_index": 0, "legal_moves_sample": []},
        }

    applied: List[Dict[str, Any]] = []
    plies = min(int(max_plies), len(moves or []))

    for i in range(plies):
        token = moves[i]
        mv, perr = _parse_move(b, token, fmt)
        if mv is None:
            return {
                "success": False,
                "end_fen": b.fen(),
                "applied": applied,
                "stopped_at": i,
                "error": {
                    "message": perr or "failed to parse move",
                    "at_index": i,
                    "legal_moves_sample": [_safe_san(b, m) for m in list(b.legal_moves)[:legal_moves_sample]],
                },
            }
        if mv not in b.legal_moves:
            return {
                "success": False,
                "end_fen": b.fen(),
                "applied": applied,
                "stopped_at": i,
                "error": {
                    "message": f"Illegal move: {token}",
                    "at_index": i,
                    "legal_moves_sample": [_safe_san(b, m) for m in list(b.legal_moves)[:legal_moves_sample]],
                },
            }

        san = _safe_san(b, mv)
        uci = mv.uci()
        b.push(mv)
        applied.append({"input": token, "uci": uci, "san": san})

    return {
        "success": True,
        "end_fen": b.fen(),
        "applied": applied,
        "stopped_at": None,
        "error": None,
    }


def _score_to_white_cp(score: Optional[chess.engine.PovScore]) -> int:
    """
    Convert a python-chess score object to centipawns from White's POV.
    Uses a large mate score so mates are sortable/compareable.
    """
    if score is None:
        return 0
    try:
        s = score.white()
        if s.is_mate():
            m = s.mate()
            return 10000 if (m or 0) > 0 else -10000
        return int(s.score(mate_score=10000) or 0)
    except Exception:
        return 0


def _pv_to_san(board: chess.Board, pv_moves: List[chess.Move], *, max_plies: int = 32) -> List[str]:
    tmp = board.copy()
    out: List[str] = []
    for mv in pv_moves[:max_plies]:
        if mv not in tmp.legal_moves:
            break
        out.append(_safe_san(tmp, mv))
        tmp.push(mv)
    return out


async def analyze_fen_stockfish(
    *,
    fen: str,
    engine_queue: Any = None,
    engine_pool_instance: Any = None,
    depth: int = 12,
    multipv: int = 3,
    max_pv_plies: int = 32,
) -> Dict[str, Any]:
    """
    Analyze a FEN on an isolated board, returning:
    - eval_cp (white POV, best line)
    - top_moves (ranked, with move_san/move_uci/eval_cp/pv_san)
    - lines (ranked, with eval_cp/pv_san)
    Size of top list is controlled via multipv (clamped 1..10).
    """
    try:
        board = chess.Board(fen)
    except Exception as e:
        return {"success": False, "error": f"Invalid FEN: {str(e)}"}

    d = int(depth or 12)
    mpv = max(1, min(int(multipv or 1), 10))

    info: Any = None
    if engine_pool_instance is not None:
        r = await engine_pool_instance.analyze_single(fen=board.fen(), depth=d, multipv=mpv)
        if not isinstance(r, dict) or not r.get("success"):
            return {"success": False, "error": f"Engine pool failed: {r}"}
        info = r.get("result")
    else:
        if engine_queue is None:
            return {"success": False, "error": "Stockfish engine not available"}
        info = await engine_queue.enqueue(
            engine_queue.engine.analyse,
            board,
            chess.engine.Limit(depth=d),
            multipv=mpv,
        )

    infos = info if isinstance(info, list) else ([info] if isinstance(info, dict) else [])

    lines: List[Dict[str, Any]] = []
    top_moves: List[Dict[str, Any]] = []
    for idx, entry in enumerate(infos):
        if not isinstance(entry, dict):
            continue
        score = entry.get("score")
        pv = entry.get("pv") or []
        pv_moves = [m for m in pv if isinstance(m, chess.Move)]
        pv_san = _pv_to_san(board, pv_moves, max_plies=max_pv_plies)
        eval_cp = _score_to_white_cp(score)

        line = {"rank": idx + 1, "eval_cp": eval_cp, "pv_san": pv_san}
        lines.append(line)

        mv0 = pv_moves[0] if pv_moves else None
        if isinstance(mv0, chess.Move):
            top_moves.append(
                {
                    "rank": idx + 1,
                    "move_uci": mv0.uci(),
                    "move_san": (pv_san[0] if pv_san else _safe_san(board, mv0)),
                    "eval_cp": eval_cp,
                    "pv_san": pv_san,
                }
            )

    best = top_moves[0] if top_moves else None
    return {
        "success": True,
        "fen": board.fen(),
        "depth": d,
        "multipv": mpv,
        "eval_cp": (best.get("eval_cp") if isinstance(best, dict) else 0),
        "best_move_san": (best.get("move_san") if isinstance(best, dict) else None),
        "best_move_uci": (best.get("move_uci") if isinstance(best, dict) else None),
        "top_moves": top_moves,
        "lines": lines,
    }


