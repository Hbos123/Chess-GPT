import json
import os
from typing import Any, Dict, Optional


def load_dump(path: str) -> Dict[str, Any]:
    """Load a single NNUE debug dump written by patched Stockfish."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def latest_dump(dump_dir: str) -> Optional[str]:
    """Return newest dump file path in dump_dir."""
    if not os.path.isdir(dump_dir):
        return None
    candidates = [
        os.path.join(dump_dir, f)
        for f in os.listdir(dump_dir)
        if f.startswith("eval_") and f.endswith(".json")
    ]
    if not candidates:
        return None
    return max(candidates, key=os.path.getmtime)


def load_latest(dump_dir: str) -> Dict[str, Any]:
    path = latest_dump(dump_dir)
    if not path:
        raise FileNotFoundError(f"No dumps found in {dump_dir}")
    return load_dump(path)

