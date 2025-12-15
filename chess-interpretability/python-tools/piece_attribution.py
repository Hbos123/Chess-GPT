from typing import Any, Dict


def compute_piece_attribution(
    dump: Dict[str, Any],
    masked_total: Dict[str, float],
    masked_classical: Dict[str, float],
    base_total_cp: float,
    base_classical_cp: float,
) -> Dict[str, Dict[str, float]]:
    """
    Compute per-piece attribution using masked evaluations:
    total_delta = base_total_cp - masked_total_cp
    classical_delta = base_classical_cp - masked_classical_cp
    nnue_contribution = total_delta - classical_delta
    """
    pieces = dump.get("pieces", {}) or {}
    result: Dict[str, Dict[str, float]] = {}
    for pid, meta in pieces.items():
        square = meta.get("square")
        masked_total_cp = masked_total.get(pid)
        masked_classical_cp = masked_classical.get(pid)

        total_delta = base_total_cp - masked_total_cp if masked_total_cp is not None else 0.0
        classical_delta = base_classical_cp - masked_classical_cp if masked_classical_cp is not None else 0.0
        nnue_delta = total_delta - classical_delta

        result[pid] = {
            "nnue_contribution": float(nnue_delta),
            "classical_contribution": float(classical_delta),
            "interactions": {},
            "total_score": float(nnue_delta + classical_delta),
            "square": square,
        }
    return result

