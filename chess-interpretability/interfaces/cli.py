import argparse
import json
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT / "chess-interpretability" / "python-tools"))

from end_to_end_analysis import analyze_position, DEFAULT_ENGINE_PATH, DEFAULT_DUMP_DIR  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="NNUE interpretability CLI")
    parser.add_argument("fen", help="FEN to analyze")
    parser.add_argument("--engine", default=DEFAULT_ENGINE_PATH, help="Path to patched Stockfish binary")
    parser.add_argument("--dump-dir", default=DEFAULT_DUMP_DIR, help="Dump directory")
    args = parser.parse_args()

    result = analyze_position(args.fen, engine_path=args.engine, dump_dir=args.dump_dir)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

