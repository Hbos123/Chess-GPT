import os
import subprocess
import time
from typing import Any, Dict, Optional

from nnue_loader import load_latest
from classical_eval_parser import parse_classical_terms
from piece_attribution import compute_piece_attribution


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEFAULT_ENGINE_PATH = os.path.join(PROJECT_ROOT, "backend", "Stockfish-sf_16", "src", "stockfish")
DEFAULT_DUMP_DIR = os.path.join(PROJECT_ROOT, "chess-interpretability", "nnue-dumps")


def run_stockfish_dump(fen: str, engine_path: str = DEFAULT_ENGINE_PATH, dump_dir: str = DEFAULT_DUMP_DIR) -> None:
    """Run patched Stockfish once to emit a NNUE/classical dump for given FEN."""
    commands = [
        "uci",
        "setoption name DumpNNUE value true",
        "setoption name DumpFeatures value true",
        "setoption name DumpActivations value true",
        "setoption name DumpClassical value true",
        f"setoption name DumpPath value {dump_dir}",
        f"position fen {fen}",
        "eval",  # Use eval command to trigger dump without search
        "quit",
    ]
    proc = subprocess.Popen(
        [engine_path],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if not proc.stdin:
        raise RuntimeError("Failed to open Stockfish stdin")
    proc.stdin.write("\n".join(commands) + "\n")
    proc.stdin.flush()
    proc.communicate(timeout=30)


def run_mask_eval(fen: str, square: str, engine_path: str = DEFAULT_ENGINE_PATH, use_nnue: bool = True) -> float:
    """
    Run Stockfish maskpiece command for a given square and return eval in centipawns (float).
    use_nnue controls whether NNUE is on (True) or classical-only (False).
    """
    commands = [
        "uci",
        f"setoption name Use NNUE value {'true' if use_nnue else 'false'}",
        f"position fen {fen}",
        f"maskpiece {square}",
        "quit",
    ]
    proc = subprocess.Popen(
        [engine_path],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if not proc.stdin:
        raise RuntimeError("Failed to open Stockfish stdin")
    proc.stdin.write("\n".join(commands) + "\n")
    proc.stdin.flush()
    out, _ = proc.communicate(timeout=15)
    masked_cp: Optional[float] = None
    for line in out.splitlines():
        if "info string maskpiece" in line and "eval_cp=" in line:
            try:
                masked_cp = float(line.split("eval_cp=")[-1].strip())
            except ValueError:
                continue
    if masked_cp is None:
        raise RuntimeError(f"Could not parse masked eval for {square} (use_nnue={use_nnue})")
    return float(masked_cp)


def extract_square_from_pid(piece_id: str) -> Optional[str]:
    # piece ids are like "white_knight_g1"
    parts = piece_id.split("_")
    if not parts:
        return None
    candidate = parts[-1]
    if len(candidate) == 2 and candidate[0] in "abcdefgh" and candidate[1] in "12345678":
        return candidate
    return None


def analyze_position(fen: str, engine_path: str = DEFAULT_ENGINE_PATH, dump_dir: str = DEFAULT_DUMP_DIR) -> Dict[str, Any]:
    """Full pipeline: run engine, load latest dump, compute per-piece attribution."""
    os.makedirs(dump_dir, exist_ok=True)
    before = set(os.listdir(dump_dir))
    run_stockfish_dump(fen, engine_path=engine_path, dump_dir=dump_dir)
    time.sleep(0.2)  # allow filesystem to flush
    after = set(os.listdir(dump_dir))
    new_files = sorted(list(after - before))
    dump = load_latest(dump_dir) if not new_files else load_latest(dump_dir)

    classical_terms = parse_classical_terms(dump)
    # Base evals from dump (already centipawns)
    base_total_cp = float(dump.get("final_eval_cp", 0.0))
    base_classical_cp = float(dump.get("classical_eval_cp", 0.0))

    # Prefer masked data from dump if present; otherwise fallback to subprocess masking
    masked_total: Dict[str, float] = {}
    masked_classical: Dict[str, float] = {}
    dump_masked_total = dump.get("masked_total") or {}
    dump_masked_classical = dump.get("masked_classical") or {}
    if dump_masked_total and dump_masked_classical:
        masked_total = {k: float(v) for k, v in dump_masked_total.items()}
        masked_classical = {k: float(v) for k, v in dump_masked_classical.items()}
    else:
        for pid, meta in (dump.get("pieces", {}) or {}).items():
            sq = meta.get("square") or extract_square_from_pid(pid)
            if not sq:
                continue
            try:
                masked_total[pid] = run_mask_eval(fen, sq, engine_path=engine_path, use_nnue=True)
                masked_classical[pid] = run_mask_eval(fen, sq, engine_path=engine_path, use_nnue=False)
            except Exception:
                # Skip on error; leave zero contribution
                continue

    piece_profile = compute_piece_attribution(
        dump,
        masked_total=masked_total,
        masked_classical=masked_classical,
        base_total_cp=base_total_cp,
        base_classical_cp=base_classical_cp,
    )

    return {
        "fen": fen,
        "raw_dump": dump,
        "classical_terms": classical_terms,
        "pieces": piece_profile,
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Analyze a position with patched Stockfish NNUE debug dumps.")
    parser.add_argument("fen", help="FEN string")
    parser.add_argument("--engine", default=DEFAULT_ENGINE_PATH, help="Path to patched Stockfish binary")
    parser.add_argument("--dump-dir", default=DEFAULT_DUMP_DIR, help="Directory to read NNUE dumps from")
    args = parser.parse_args()
    result = analyze_position(args.fen, engine_path=args.engine, dump_dir=args.dump_dir)
    import json
    print(json.dumps(result, indent=2))

