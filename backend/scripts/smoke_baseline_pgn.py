from __future__ import annotations

import sys
import asyncio
import contextlib
import io
import json
import os
import tempfile
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

import chess  # type: ignore

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from engine_pool import EnginePool
from investigator import Investigator
from nnue_bridge import compute_piece_contributions, get_nnue_dump
from skills.claims import build_claims_from_investigation
from skills.motifs import MotifPolicy, mine_motifs


STARTING_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


@dataclass
class TimingEvent:
    name: str
    t_start_s: float
    t_end_s: float
    duration_ms: float
    meta: Dict[str, Any]


class Timer:
    def __init__(self) -> None:
        self.t0 = time.perf_counter()
        self.events: List[TimingEvent] = []

    def _now(self) -> float:
        return time.perf_counter() - self.t0

    def span(self, name: str, **meta: Any):
        timer = self

        class _Span:
            def __enter__(self_inner):
                self_inner.t1 = timer._now()
                return self_inner

            def __exit__(self_inner, exc_type, exc, tb):
                t2 = timer._now()
                timer.events.append(
                    TimingEvent(
                        name=name,
                        t_start_s=self_inner.t1,
                        t_end_s=t2,
                        duration_ms=(t2 - self_inner.t1) * 1000.0,
                        meta={
                            **meta,
                            "exc_type": str(exc_type.__name__) if exc_type else None,
                            "exc": str(exc) if exc else None,
                        },
                    )
                )

        return _Span()


def _safe_json(obj: Any) -> Any:
    try:
        json.dumps(obj)
        return obj
    except Exception:
        if isinstance(obj, dict):
            return {str(k): _safe_json(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_safe_json(v) for v in obj]
        return str(obj)


def _normalize_fen(fen: str) -> str:
    return chess.Board(fen).fen()


def _try_nnue_contrib(fen: str, timeout_s: float, timer: Timer, label: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {"fen": fen, "nnue_dump_ok": False}
    with timer.span(f"nnue_dump:{label}", fen_prefix=fen[:60], timeout_s=timeout_s):
        dump = get_nnue_dump(fen, timeout=timeout_s)
    if not dump:
        return out
    out["nnue_dump_ok"] = True
    with timer.span(f"nnue_piece_contrib:{label}", fen_prefix=fen[:60]):
        contrib = compute_piece_contributions(dump)
    # Keep a small, human-inspectable summary
    pieces = []
    for pid, stats in (contrib or {}).items():
        try:
            pieces.append(
                {
                    "piece_id": pid,
                    "total_cp": stats.get("total_contribution_cp"),
                    "nnue_cp": stats.get("nnue_contribution_cp"),
                    "classical_cp": stats.get("classical_contribution_cp"),
                }
            )
        except Exception:
            continue
    pieces.sort(key=lambda x: abs(float(x.get("total_cp") or 0.0)), reverse=True)
    out["top_pieces_by_abs_total_cp"] = pieces[:16]
    return out


async def main() -> str:
    timer = Timer()

    fen = _normalize_fen(os.getenv("SMOKE_FEN", STARTING_FEN))
    depth2 = int(os.getenv("SMOKE_D2", "2"))
    depth16 = int(os.getenv("SMOKE_D16", "16"))
    branching_limit = int(os.getenv("SMOKE_BRANCHING_LIMIT", "6"))
    max_pv_plies = int(os.getenv("SMOKE_MAX_PV_PLIES", "24"))
    pgn_max_chars = int(os.getenv("SMOKE_PGN_MAX_CHARS", "0"))
    nnue_timeout_s = float(os.getenv("SMOKE_NNUE_TIMEOUT_S", os.getenv("NNUE_DUMP_TIMEOUT_S", "8")))

    # Use an engine pool like the server (required by Investigator).
    stockfish_path = os.getenv(
        "STOCKFISH_PATH",
        os.path.join(BACKEND_DIR, "Stockfish-sf_16", "src", "stockfish"),
    )
    pool_size = int(os.getenv("SMOKE_ENGINE_POOL_SIZE", "2"))
    pool = EnginePool(pool_size=pool_size, stockfish_path=stockfish_path)

    inv_dict: Dict[str, Any] = {}
    stdout_buf = io.StringIO()
    with contextlib.redirect_stdout(stdout_buf), contextlib.redirect_stderr(stdout_buf):
        with timer.span("engine_pool_initialize", pool_size=pool_size, stockfish_path=stockfish_path):
            ok = await pool.initialize()
        if not ok:
            raise RuntimeError("EnginePool failed to initialize")

        inv = Investigator(engine_pool=pool)

        # Explicit timings requested: D16 root, D2 root, branching-only probe.
        with timer.span("root_analyze_d16_only", depth=depth16):
            d16_probe = await inv._analyze_depth(fen, depth16, get_top_2=True)
        with timer.span("root_analyze_d2_only", depth=depth2):
            d2_probe = await inv._analyze_depth(fen, depth2, get_top_2=False)
        with timer.span("branching_probe_only", branching_toggle=True, branching_limit=branching_limit):
            try:
                over = inv._find_overestimated_moves(d16_probe, d2_probe) or []
            except Exception:
                over = []
            # Probe recursion cost without building PGN (this does call analysis internally).
            for mv_san in over[:branching_limit]:
                try:
                    inv.board.set_fen(fen)
                    mv = inv.board.parse_san(mv_san)
                    if mv not in inv.board.legal_moves:
                        continue
                    inv.board.push(mv)
                    new_fen = inv.board.fen()
                    await inv._explore_branch_recursive(
                        new_fen,
                        d16_probe.get("eval") if d16_probe else 0.0,
                        depth16,
                        depth2,
                        mv_san,
                        depth_limit=5,
                        current_depth=0,
                    )
                except Exception:
                    continue

        # Full end-to-end run that actually generates exploration PGN/tree/evidence.
        with timer.span(
            "investigate_with_dual_depth",
            depth2=depth2,
            depth16=depth16,
            branching_limit=branching_limit,
            max_pv_plies=max_pv_plies,
            pgn_max_chars=pgn_max_chars,
        ):
            res = await inv.investigate_with_dual_depth(
                fen,
                scope="general_position",
                depth_2=depth2,
                depth_16=depth16,
                original_fen=fen,
                branching_limit=branching_limit,
                max_pv_plies=max_pv_plies,
                include_pgn=True,
                pgn_max_chars=pgn_max_chars,
            )
            inv_dict = res.to_dict(include_semantic_story=False)

    pgn_exploration = inv_dict.get("pgn_exploration") or ""

    claims: List[Dict[str, Any]] = []
    with contextlib.redirect_stdout(stdout_buf), contextlib.redirect_stderr(stdout_buf):
        with timer.span("build_claims_from_investigation"):
            claims = build_claims_from_investigation(inv_dict)

    # Evidence-line NNUE timing (explicitly requested) — starting position + after end of claim.
    ev_start_fen = inv_dict.get("evidence_starting_fen") or fen
    ev_end_fen = inv_dict.get("evidence_end_fen")
    if not ev_end_fen:
        pm = inv_dict.get("evidence_per_move_deltas") or []
        if isinstance(pm, list) and pm:
            last = pm[-1]
            if isinstance(last, dict) and last.get("fen_after"):
                ev_end_fen = last.get("fen_after")
    ev_end_fen = _normalize_fen(ev_end_fen) if isinstance(ev_end_fen, str) and ev_end_fen.strip() else None

    nnue_evidence = {
        "start": _try_nnue_contrib(_normalize_fen(ev_start_fen), nnue_timeout_s, timer, "evidence_start"),
        "end": _try_nnue_contrib(ev_end_fen, nnue_timeout_s, timer, "evidence_end") if ev_end_fen else {"fen": None, "nnue_dump_ok": False},
    }

    motifs: List[Dict[str, Any]] = []
    exploration_tree = inv_dict.get("exploration_tree") or {}
    motif_pol = MotifPolicy(
        max_pattern_plies=int(os.getenv("SMOKE_MOTIFS_MAX_PATTERN_PLIES", "5")),
        motifs_top=int(os.getenv("SMOKE_MOTIFS_TOP", "40")),
        max_line_plies=int(os.getenv("SMOKE_MOTIFS_MAX_LINE_PLIES", "14")),
        max_branch_lines=int(os.getenv("SMOKE_MOTIFS_MAX_BRANCH_LINES", "20")),
    )
    with contextlib.redirect_stdout(stdout_buf), contextlib.redirect_stderr(stdout_buf):
        with timer.span("mine_motifs", policy=asdict(motif_pol)):
            if isinstance(exploration_tree, dict) and exploration_tree:
                motifs = mine_motifs(
                    starting_fen=fen,
                    exploration_tree=exploration_tree,
                    engine_pool_instance=pool,
                    engine_queue=None,
                    policy=motif_pol,
                )

        with timer.span("engine_pool_shutdown"):
            await pool.shutdown()

    # Emit temp file with full outputs + timeline.
    output = {
        "meta": {
            "fen": fen,
            "depth2": depth2,
            "depth16": depth16,
            "branching_limit": branching_limit,
            "max_pv_plies": max_pv_plies,
            "pgn_max_chars": pgn_max_chars,
            "nnue_timeout_s": nnue_timeout_s,
        },
        "timings": [asdict(e) for e in timer.events],
        "stdout_log": stdout_buf.getvalue(),
        "artifacts": {
            "pgn_bundle": {"fen": fen, "pgn": pgn_exploration},
            "pgn_exploration_len": len(pgn_exploration),
            "claims": claims,
            "motifs": motifs,
            "nnue_evidence": nnue_evidence,
            "investigation": inv_dict,
        },
        "total_ms": (time.perf_counter() - timer.t0) * 1000.0,
    }

    tmp = tempfile.NamedTemporaryFile(prefix="smoke_baseline_pgn_", suffix=".json", delete=False)
    tmp.write(json.dumps(_safe_json(output), indent=2).encode("utf-8"))
    tmp.flush()
    tmp.close()
    return tmp.name


if __name__ == "__main__":
    path = asyncio.run(main())
    print(path)


