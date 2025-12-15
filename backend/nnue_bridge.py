"""
NNUE Bridge - Interface to patched Stockfish for NNUE dumps.
Calls the modified Stockfish engine to get per-piece masked evaluations.
"""

import subprocess
import json
import os
import glob
import time
from typing import Dict, List, Optional, Any

# Paths
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
STOCKFISH_PATH = os.path.join(PROJECT_ROOT, "Stockfish-sf_16", "src", "stockfish")
DUMP_DIR = os.path.join(PROJECT_ROOT, "nnue_dumps")


def ensure_dump_dir():
    """Ensure the dump directory exists."""
    os.makedirs(DUMP_DIR, exist_ok=True)


def get_nnue_dump(fen: str, timeout: float = 30.0) -> Optional[Dict[str, Any]]:
    """
    Call patched Stockfish to get NNUE dump for a position.
    
    Args:
        fen: FEN string of the position
        timeout: Maximum time to wait for Stockfish
    
    Returns:
        Parsed JSON dump with masked_total, masked_classical, classical_terms, etc.
        None if failed.
    """
    ensure_dump_dir()
    
    # Clear old dumps
    for f in glob.glob(os.path.join(DUMP_DIR, "eval_*.json")):
        try:
            os.remove(f)
        except:
            pass
    
    # Build commands
    commands = [
        "uci",
        "setoption name DumpNNUE value true",
        "setoption name DumpFeatures value true",
        "setoption name DumpClassical value true",
        f"setoption name DumpPath value {DUMP_DIR}",
        f"position fen {fen}",
        "eval",
        "quit",
    ]
    
    try:
        proc = subprocess.Popen(
            [STOCKFISH_PATH],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        
        proc.stdin.write("\n".join(commands) + "\n")
        proc.stdin.flush()
        proc.communicate(timeout=timeout)
        
        # Small delay for file system
        time.sleep(0.1)
        
        # Find the newest dump file
        dump_files = sorted(glob.glob(os.path.join(DUMP_DIR, "eval_*.json")))
        if not dump_files:
            print(f"[NNUE Bridge] No dump file created for FEN: {fen[:50]}...")
            return None
        
        latest_dump = dump_files[-1]
        with open(latest_dump, 'r') as f:
            dump_data = json.load(f)
        
        return dump_data
        
    except subprocess.TimeoutExpired:
        print(f"[NNUE Bridge] Stockfish timeout for FEN: {fen[:50]}...")
        proc.kill()
        return None
    except FileNotFoundError:
        print(f"[NNUE Bridge] Stockfish not found at: {STOCKFISH_PATH}")
        return None
    except Exception as e:
        print(f"[NNUE Bridge] Error: {e}")
        return None


def get_nnue_dumps_batch(fens: List[str], timeout_per_fen: float = 30.0) -> List[Optional[Dict[str, Any]]]:
    """
    Get dumps for multiple FENs.
    
    Args:
        fens: List of FEN strings
        timeout_per_fen: Timeout per position
    
    Returns:
        List of dump dicts (or None for failed positions)
    """
    results = []
    for fen in fens:
        dump = get_nnue_dump(fen, timeout=timeout_per_fen)
        results.append(dump)
    return results


def compute_piece_contributions(dump: Dict[str, Any]) -> Dict[str, Dict[str, float]]:
    """
    From dump's masked_total/masked_classical, compute per-piece contributions.
    
    contribution = base_eval - masked_eval
    (Positive contribution means the piece helps the side to move)
    
    Args:
        dump: Parsed NNUE dump
    
    Returns:
        Dict of piece_id → {
            "nnue_contribution_cp": float,
            "classical_contribution_cp": float,
            "total_contribution_cp": float
        }
    """
    base_total = float(dump.get("final_eval_cp", 0))
    base_nnue = float(dump.get("nnue_eval_cp", 0))
    base_classical = float(dump.get("classical_eval_cp", 0))
    
    masked_total = dump.get("masked_total", {})
    masked_classical = dump.get("masked_classical", {})
    
    contributions = {}
    
    for piece_id in masked_total.keys():
        masked_t = float(masked_total.get(piece_id, 0))
        masked_c = float(masked_classical.get(piece_id, 0))
        
        # Contribution = what happens when we remove the piece
        # base_eval - masked_eval = how much the piece adds
        total_contribution = base_total - masked_t
        classical_contribution = base_classical - masked_c
        nnue_contribution = total_contribution - classical_contribution
        
        contributions[piece_id] = {
            "nnue_contribution_cp": nnue_contribution,
            "classical_contribution_cp": classical_contribution,
            "total_contribution_cp": total_contribution,
        }
    
    return contributions


def get_classical_terms(dump: Dict[str, Any]) -> Dict[str, Dict[str, int]]:
    """
    Extract classical evaluation terms from dump.
    
    Args:
        dump: Parsed NNUE dump
    
    Returns:
        Dict of term_name → {"white_mg": int, "black_mg": int}
    """
    return dump.get("classical_terms", {})


def get_pieces_from_dump(dump: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    """
    Extract piece information from dump.
    
    Args:
        dump: Parsed NNUE dump
    
    Returns:
        Dict of piece_id → {"square": str}
    """
    return dump.get("pieces", {})


def parse_piece_id(piece_id: str) -> Dict[str, str]:
    """
    Parse a piece ID like "white_knight_f3" into components.
    
    Returns:
        {"color": "white", "piece_type": "knight", "square": "f3"}
    """
    parts = piece_id.split("_")
    if len(parts) >= 3:
        return {
            "color": parts[0],
            "piece_type": parts[1],
            "square": parts[2],
        }
    return {"color": "", "piece_type": "", "square": ""}


# For testing
if __name__ == "__main__":
    test_fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
    print(f"Testing NNUE dump for: {test_fen}")
    
    dump = get_nnue_dump(test_fen)
    if dump:
        print(f"Got dump with {len(dump.get('pieces', {}))} pieces")
        contributions = compute_piece_contributions(dump)
        for pid, contrib in list(contributions.items())[:5]:
            print(f"  {pid}: total={contrib['total_contribution_cp']:.1f}cp")
    else:
        print("Failed to get dump")

