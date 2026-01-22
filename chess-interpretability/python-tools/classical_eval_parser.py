from typing import Any, Dict, List

TERM_MAP = [
    "MATERIAL",
    "IMBALANCE",
    "MOBILITY",
    "THREAT",
    "PASSED",
    "SPACE",
    "WINNABLE",
    "TOTAL",
]


def parse_classical_terms(dump: Dict[str, Any]) -> Dict[str, Dict[str, int]]:
    classical = dump.get("classical_terms", {})
    result: Dict[str, Dict[str, int]] = {}
    for name in TERM_MAP:
        entry = classical.get(name)
        if isinstance(entry, dict):
            result[name] = {
                "white_mg": int(entry.get("white_mg", 0)),
                "black_mg": int(entry.get("black_mg", 0)),
            }
    return result


def per_piece_classical_stub(pieces: List[str]) -> Dict[str, float]:
    """
    Placeholder: classical eval in Stockfish is not per-piece by default.
    Return zeroed contributions for now; callers can enrich with custom logic.
    """
    return {p: 0.0 for p in pieces}

