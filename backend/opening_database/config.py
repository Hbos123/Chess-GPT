import os
from pathlib import Path

# Paths
DATA_DIR = Path("data/lichess_openings")
REPO_DIR = DATA_DIR / "chess-openings"
EVAL_DIR = DATA_DIR / "evals"

# Source URLs
CHESS_OPENINGS_REPO = "https://github.com/lichess-org/chess-openings.git"
CHESS_OPENINGS_TSV = "https://raw.githubusercontent.com/lichess-org/chess-openings/master/openings.tsv"
LICHESS_EVALS_DB = "https://database.lichess.org/evals/lichess_db_eval.jsonl.zst"

# Processing settings
MAX_PLY_DEPTH = 30  # Track up to 15 moves
MIN_EVAL_DEPTH = 20  # Only trust deep evals

# Critical position criteria
CRITICAL_CP_LOSS_THRESHOLD = 50  # 2nd best loses >50cp

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
BATCH_SIZE = 1000

def normalize_fen(fen: str) -> str:
    """Strip move counters for transposition matching"""
    parts = fen.split()
    return ' '.join(parts[:4]) if len(parts) >= 4 else fen



