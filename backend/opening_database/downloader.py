import requests
import subprocess
import zstandard as zstd
from pathlib import Path
import logging
from .config import (
    DATA_DIR, REPO_DIR, EVAL_DIR,
    CHESS_OPENINGS_REPO, CHESS_OPENINGS_TSV, LICHESS_EVALS_DB
)

logger = logging.getLogger(__name__)

class LichessDownloader:
    """Download chess-openings repo and eval database"""
    
    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        EVAL_DIR.mkdir(parents=True, exist_ok=True)
    
    def download_openings_data(self) -> Path:
        """Download openings.tsv from Lichess chess-openings repo
        
        Returns path to openings.tsv file
        """
        tsv_path = DATA_DIR / "openings.tsv"
        
        if tsv_path.exists():
            logger.info(f"Already have {tsv_path}")
            return tsv_path
        
        logger.info(f"Downloading openings.tsv from {CHESS_OPENINGS_TSV}...")
        response = requests.get(CHESS_OPENINGS_TSV)
        response.raise_for_status()
        
        with open(tsv_path, 'w', encoding='utf-8') as f:
            f.write(response.text)
        
        logger.info(f"Saved to {tsv_path}")
        return tsv_path
    
    def download_eval_database(self) -> Path:
        """Download Lichess evaluation database (zstd compressed JSONL)"""
        eval_path = EVAL_DIR / "lichess_db_eval.jsonl.zst"
        
        if eval_path.exists():
            logger.info(f"Already have {eval_path}")
            return eval_path
        
        logger.info(f"Downloading eval DB from {LICHESS_EVALS_DB}...")
        logger.info("⚠️  This is a large file (~10GB compressed), will take time...")
        
        with requests.get(LICHESS_EVALS_DB, stream=True) as r:
            r.raise_for_status()
            total_mb = 0
            
            with open(eval_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=1024*1024):  # 1MB chunks
                    f.write(chunk)
                    total_mb += len(chunk) / (1024*1024)
                    if total_mb % 100 == 0:
                        logger.info(f"Downloaded {total_mb:.0f}MB...")
        
        logger.info(f"Saved eval DB to {eval_path}")
        return eval_path



