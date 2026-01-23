"""
NNUE Process Pool - Manages a pool of patched Stockfish processes for NNUE dumps.
Prevents memory spikes from concurrent subprocess spawning.
"""

import asyncio
import subprocess
import json
import os
import glob
import time
import hashlib
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timedelta

# Paths
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
STOCKFISH_PATH = os.path.join(PROJECT_ROOT, "Stockfish-sf_16", "src", "stockfish")
DUMP_DIR = os.path.join(PROJECT_ROOT, "nnue_dumps")

# Configuration
DEFAULT_TIMEOUT = float(os.getenv("NNUE_DUMP_TIMEOUT_S", "8.0"))
MAX_CONCURRENT_DUMPS = int(os.getenv("NNUE_MAX_CONCURRENT", "2"))  # Limit concurrent dumps
CACHE_TTL_SECONDS = int(os.getenv("NNUE_CACHE_TTL_S", "3600"))  # 1 hour default
MAX_RETRIES = int(os.getenv("NNUE_MAX_RETRIES", "2"))
RETRY_BASE_DELAY = float(os.getenv("NNUE_RETRY_DELAY_S", "0.5"))


@dataclass
class CachedDump:
    """Cached NNUE dump entry"""
    fen: str
    dump_data: Dict[str, Any]
    cached_at: float
    expires_at: float


class NNUEProcessPool:
    """
    Pool manager for NNUE dump processes.
    Limits concurrent subprocesses to prevent memory spikes.
    """
    
    def __init__(self, max_concurrent: int = MAX_CONCURRENT_DUMPS):
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.cache: Dict[str, CachedDump] = {}
        self._cache_lock = asyncio.Lock()
        self._ensure_dump_dir()
    
    def _ensure_dump_dir(self):
        """Ensure the dump directory exists."""
        os.makedirs(DUMP_DIR, exist_ok=True)
    
    def _normalize_fen(self, fen: str) -> str:
        """Normalize FEN for cache key."""
        try:
            import chess
            return chess.Board(fen).fen()
        except Exception:
            return (fen or "").strip()
    
    def _cache_key(self, fen: str) -> str:
        """Generate cache key from FEN."""
        nfen = self._normalize_fen(fen)
        return hashlib.sha256(nfen.encode("utf-8")).hexdigest()
    
    async def _get_from_cache(self, fen: str) -> Optional[Dict[str, Any]]:
        """Get dump from cache if valid."""
        async with self._cache_lock:
            key = self._cache_key(fen)
            cached = self.cache.get(key)
            
            if cached and time.time() < cached.expires_at:
                return cached.dump_data
            
            # Remove expired entry
            if cached:
                self.cache.pop(key, None)
            
            return None
    
    async def _set_cache(self, fen: str, dump_data: Dict[str, Any]):
        """Store dump in cache."""
        async with self._cache_lock:
            key = self._cache_key(fen)
            now = time.time()
            self.cache[key] = CachedDump(
                fen=fen,
                dump_data=dump_data,
                cached_at=now,
                expires_at=now + CACHE_TTL_SECONDS
            )
            
            # Clean up old entries (keep cache size reasonable)
            if len(self.cache) > 100:
                # Remove oldest expired entries
                now = time.time()
                expired_keys = [
                    k for k, v in self.cache.items()
                    if now >= v.expires_at
                ]
                for k in expired_keys[:50]:  # Remove up to 50 expired entries
                    self.cache.pop(k, None)
    
    async def _run_dump_process(self, fen: str, timeout: float) -> Optional[Dict[str, Any]]:
        """
        Run a single NNUE dump process.
        This is the actual subprocess execution (protected by semaphore).
        """
        # Clear old dumps before starting
        for f in glob.glob(os.path.join(DUMP_DIR, "eval_*.json")):
            try:
                # Only remove files older than 1 minute to avoid race conditions
                if os.path.getmtime(f) < time.time() - 60:
                    os.remove(f)
            except Exception:
                pass
        
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
            
            proc.stdin.write("
".join(commands) + "
")
            proc.stdin.flush()
            proc.communicate(timeout=timeout)
            
            # Small delay for file system
            await asyncio.sleep(0.1)
            
            # Find the newest dump file
            dump_files = sorted(glob.glob(os.path.join(DUMP_DIR, "eval_*.json")))
            if not dump_files:
                print(f"[NNUE Pool] No dump file created for FEN: {fen[:50]}...")
                return None
            
            latest_dump = dump_files[-1]
            with open(latest_dump, 'r') as f:
                dump_data = json.load(f)
            
            return dump_data
            
        except subprocess.TimeoutExpired:
            print(f"[NNUE Pool] Stockfish timeout for FEN: {fen[:50]}...")
            try:
                proc.kill()
            except Exception:
                pass
            return None
        except FileNotFoundError:
            print(f"[NNUE Pool] Stockfish not found at: {STOCKFISH_PATH}")
            return None
        except Exception as e:
            print(f"[NNUE Pool] Error: {e}")
            return None
    
    async def get_dump(
        self,
        fen: str,
        timeout: float = DEFAULT_TIMEOUT,
        use_cache: bool = True,
        max_retries: int = MAX_RETRIES
    ) -> Optional[Dict[str, Any]]:
        """
        Get NNUE dump with caching, retry logic, and concurrency control.
        
        Args:
            fen: FEN string of the position
            timeout: Maximum time to wait for Stockfish
            use_cache: Whether to use cache (default: True)
            max_retries: Maximum retry attempts on failure
        
        Returns:
            Parsed JSON dump or None if failed
        """
        # Check cache first
        if use_cache:
            cached = await self._get_from_cache(fen)
            if cached:
                print(f"[NNUE Pool] Cache hit for FEN: {fen[:50]}...")
                return cached
        
        # Acquire semaphore to limit concurrent processes
        async with self.semaphore:
            # Retry logic with exponential backoff
            last_error = None
            for attempt in range(max_retries + 1):
                if attempt > 0:
                    delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                    print(f"[NNUE Pool] Retry {attempt}/{max_retries} after {delay}s for FEN: {fen[:50]}...")
                    await asyncio.sleep(delay)
                
                try:
                    dump_data = await self._run_dump_process(fen, timeout)
                    
                    if dump_data:
                        # Cache successful result
                        if use_cache:
                            await self._set_cache(fen, dump_data)
                        return dump_data
                    else:
                        last_error = "No dump data returned"
                        
                except Exception as e:
                    last_error = str(e)
                    print(f"[NNUE Pool] Attempt {attempt + 1} failed: {e}")
            
            # All retries exhausted
            print(f"[NNUE Pool] Failed after {max_retries + 1} attempts: {last_error}")
            return None
    
    async def get_dumps_batch(
        self,
        fens: List[str],
        timeout_per_fen: float = DEFAULT_TIMEOUT,
        use_cache: bool = True
    ) -> List[Optional[Dict[str, Any]]]:
        """
        Get dumps for multiple FENs in parallel (respecting concurrency limit).
        
        Args:
            fens: List of FEN strings
            timeout_per_fen: Timeout per position
            use_cache: Whether to use cache
        
        Returns:
            List of dump dicts (or None for failed positions)
        """
        tasks = [
            self.get_dump(fen, timeout=timeout_per_fen, use_cache=use_cache)
            for fen in fens
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Convert exceptions to None
        return [
            r if isinstance(r, dict) else None
            for r in results
        ]
    
    def clear_cache(self):
        """Clear the cache."""
        self.cache.clear()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        async def _stats():
            async with self._cache_lock:
                now = time.time()
                valid = sum(1 for v in self.cache.values() if now < v.expires_at)
                expired = len(self.cache) - valid
                return {
                    "total_entries": len(self.cache),
                    "valid_entries": valid,
                    "expired_entries": expired,
                    "max_concurrent": self.max_concurrent,
                    "current_waiting": self.max_concurrent - self.semaphore._value
                }
        return asyncio.run(_stats()) if asyncio.get_event_loop().is_running() else {"error": "No event loop"}


# Global instance
_nnue_pool: Optional[NNUEProcessPool] = None


def get_nnue_pool() -> NNUEProcessPool:
    """Get or create the global NNUE process pool."""
    global _nnue_pool
    if _nnue_pool is None:
        _nnue_pool = NNUEProcessPool(max_concurrent=MAX_CONCURRENT_DUMPS)
    return _nnue_pool


# Backward compatibility: wrapper functions that use the pool
async def get_nnue_dump(fen: str, timeout: float = DEFAULT_TIMEOUT) -> Optional[Dict[str, Any]]:
    """
    Get NNUE dump (uses process pool for concurrency control).
    Backward-compatible wrapper for existing code.
    """
    pool = get_nnue_pool()
    return await pool.get_dump(fen, timeout=timeout, use_cache=True)


async def get_nnue_dumps_batch(fens: List[str], timeout_per_fen: float = DEFAULT_TIMEOUT) -> List[Optional[Dict[str, Any]]]:
    """
    Get dumps for multiple FENs (uses process pool).
    Backward-compatible wrapper for existing code.
    """
    pool = get_nnue_pool()
    return await pool.get_dumps_batch(fens, timeout_per_fen=timeout_per_fen, use_cache=True)


# Re-export compute functions from nnue_bridge (pure computation, no subprocess)
# These are safe to import as they don't depend on the dump process
try:
    from nnue_bridge import (
        compute_piece_contributions,
        get_classical_terms,
        get_pieces_from_dump,
        parse_piece_id
    )
except ImportError:
    # Fallback: define minimal versions if nnue_bridge not available
    def compute_piece_contributions(dump: Dict[str, Any]) -> Dict[str, Dict[str, float]]:
        """Fallback implementation if nnue_bridge not available."""
        return {}
    
    def get_classical_terms(dump: Dict[str, Any]) -> Dict[str, Dict[str, int]]:
        return dump.get("classical_terms", {})
    
    def get_pieces_from_dump(dump: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
        return dump.get("pieces", {})
    
    def parse_piece_id(piece_id: str) -> Dict[str, str]:
        parts = piece_id.split("_")
        if len(parts) >= 3:
            return {"color": parts[0], "piece_type": parts[1], "square": parts[2]}
        return {"color": "", "piece_type": "", "square": ""}
