import asyncio
import os
import statistics
from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional

import chess
import chess.engine

from backend.confidence_engine import (
    DEFAULT_BASELINE,
    compute_move_confidence,
    compute_position_confidence,
)

ALLOWED_COLORS = {"red", "blue", "green"}
ALLOWED_SHAPES = {"circle", "triangle", "square"}


@dataclass
class TestCase:
    name: str
    kind: Literal["move", "position"]
    fen: str
    move_san: Optional[str] = None
    baseline: int = DEFAULT_BASELINE
    branch: bool = True


def _summarize_nodes(nodes: List[Dict[str, Any]]) -> Dict[str, Any]:
    pv_nodes = [n for n in nodes if str(n.get("id", "")).startswith("pv-")]
    triangles = [n for n in nodes if n.get("shape") == "triangle"]
    red_nodes = [n for n in nodes if n.get("color") == "red"]
    blue_nodes = [n for n in nodes if n.get("color") == "blue"]
    green_nodes = [n for n in nodes if n.get("color") == "green"]
    depths = [n.get("ply_from_S0") for n in nodes if isinstance(n.get("ply_from_S0"), int)]
    return {
        "total": len(nodes),
        "pv_nodes": len(pv_nodes),
        "triangles": len(triangles),
        "red_nodes": len(red_nodes),
        "blue_nodes": len(blue_nodes),
        "green_nodes": len(green_nodes),
        "max_depth": max(depths) if depths else None,
    }


def _validate_nodes(nodes: List[Dict[str, Any]], baseline: int) -> List[str]:
    errors: List[str] = []
    pv_nodes = [n for n in nodes if str(n.get("id", "")).startswith("pv-")]
    if pv_nodes:
        indices = []
        for n in pv_nodes:
            try:
                idx = int(str(n["id"]).split("-")[1])
            except Exception:
                continue
            indices.append(idx)
        if indices:
            first_idx = min(indices)
            last_idx = max(indices)
            for n in pv_nodes:
                try:
                    idx = int(str(n["id"]).split("-")[1])
                except Exception:
                    continue
                shape = n.get("shape")
                if idx == first_idx or idx == last_idx:
                    if shape != "square":
                        errors.append(f"PV node {n['id']} expected square, got {shape}")
                else:
                    if shape == "square":
                        errors.append(f"Intermediate PV node {n['id']} should not be square")
    for n in nodes:
        shape = n.get("shape")
        color = n.get("color")
        if shape not in ALLOWED_SHAPES:
            errors.append(f"Node {n.get('id')} invalid shape {shape}")
        if color not in ALLOWED_COLORS:
            errors.append(f"Node {n.get('id')} invalid color {color}")
        if shape == "triangle" and not n.get("has_branches", False):
            errors.append(f"Triangle node {n.get('id')} missing has_branches flag")
        if shape == "square":
            node_id = str(n.get("id"))
            if not (node_id.endswith("-0") or node_id.endswith(f"-{len(pv_nodes) - 1}")):
                errors.append(f"Square node {node_id} not recognised as PV endpoint")
        # Sanity check on confidence values
        frozen = n.get("frozen_confidence")
        conf = n.get("ConfidencePercent")
        if frozen is not None and (frozen < 0 or frozen > 100):
            errors.append(f"Node {n.get('id')} frozen confidence out of range: {frozen}")
        if conf is not None and (conf < 0 or conf > 100):
            errors.append(f"Node {n.get('id')} confidence out of range: {conf}")
        if n.get("insufficient_confidence") and color == "green":
            errors.append(f"Node {n.get('id')} marked insufficient but colored green")
        if color == "red":
            frozen_effective = frozen if frozen is not None else conf
            if frozen_effective is not None and frozen_effective >= baseline:
                errors.append(
                    f"Node {n.get('id')} colored red but meets baseline {baseline} (value {frozen_effective})"
                )
    return errors


async def _run_case(engine: chess.engine.SimpleEngine, case: TestCase) -> Dict[str, Any]:
    if case.kind == "move":
        if not case.move_san:
            raise ValueError(f"Test case {case.name} missing move_san")
        payload = await compute_move_confidence(
            engine,
            case.fen,
            case.move_san,
            target_conf=case.baseline,
            branch=case.branch,
        )
    else:
        payload = await compute_position_confidence(
            engine,
            case.fen,
            target_conf=case.baseline,
            branch=case.branch,
        )
    nodes = payload.get("nodes", [])
    stats = payload.get("stats", {})
    snapshots = payload.get("snapshots", [])
    errors = _validate_nodes(nodes, case.baseline)
    summary = _summarize_nodes(nodes)
    iteration_counts = []
    for snap in snapshots:
        iter_idx = snap.get("iteration")
        if isinstance(iter_idx, int):
            iteration_counts.append(iter_idx)
    summary["snapshots"] = len(snapshots)
    summary["iterations_reported"] = stats.get("iteration")
    summary["iteration_series"] = iteration_counts
    summary["errors"] = errors
    summary["min_confidence"] = stats.get("min_confidence")
    return summary


async def run_protocol() -> None:
    stockfish_path = os.getenv("STOCKFISH_PATH", "./stockfish")
    if not os.path.exists(stockfish_path):
        raise RuntimeError(
            f"Stockfish binary not found at {stockfish_path}. Set STOCKFISH_PATH env."
        )

    cases: List[TestCase] = [
        TestCase(
            name="startpos_move_e4",
            kind="move",
            fen=chess.STARTING_BOARD_FEN,
            move_san="e4",
            baseline=80,
            branch=True,
        ),
        TestCase(
            name="sicilian_reply",
            kind="move",
            fen="rnbqkbnr/pp1ppppp/8/2p5/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
            move_san="Nf3",
            baseline=80,
            branch=True,
        ),
        TestCase(
            name="position_confidence_midgame",
            kind="position",
            fen="r1bq1rk1/ppp2ppp/2np1n2/2b1p3/4P3/2NP1N2/PPPB1PPP/R2QKB1R w KQ - 5 7",
            baseline=80,
            branch=True,
        ),
    ]

    transport, engine = await chess.engine.popen_uci(stockfish_path)
    await engine.configure({"Threads": 2, "Hash": 128})
    try:
        reports = {}
        for case in cases:
            summary = await _run_case(engine, case)
            reports[case.name] = summary
        failures = {name: data for name, data in reports.items() if data["errors"]}
        print("=== Confidence Protocol Report ===")
        for name, data in reports.items():
            print(f"\nCase: {name}")
            for key, value in data.items():
                if key == "errors" and value:
                    print(f"  {key}:")
                    for err in value:
                        print(f"    - {err}")
                else:
                    print(f"  {key}: {value}")
        if failures:
            raise SystemExit(f"Confidence protocol failures detected: {list(failures.keys())}")
        else:
            print("\n✓ All protocol checks passed.")
    finally:
        await engine.quit()
        transport.close()


if __name__ == "__main__":
    asyncio.run(run_protocol())

