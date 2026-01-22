"""
Investigation Cache - Stores investigation results by FEN to avoid recalculation
"""

import json
import os
import hashlib
from typing import Dict, Any, Optional
from pathlib import Path
from dataclasses import dataclass, asdict
from investigator import InvestigationResult


@dataclass
class CachedInvestigation:
    """Cached investigation result"""
    fen: str
    move_san: Optional[str] = None  # None for position investigations
    investigation_type: str = "move"  # "move" or "position"
    result: Dict[str, Any] = None  # InvestigationResult as dict
    timestamp: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "fen": self.fen,
            "move_san": self.move_san,
            "investigation_type": self.investigation_type,
            "result": self.result,
            "timestamp": self.timestamp
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CachedInvestigation':
        return cls(
            fen=data.get("fen", ""),
            move_san=data.get("move_san"),
            investigation_type=data.get("investigation_type", "move"),
            result=data.get("result"),
            timestamp=data.get("timestamp", 0.0)
        )


class InvestigationCache:
    """Cache for investigation results"""
    
    def __init__(self, cache_dir: str = "backend/cache/investigations"):
        """
        Initialize investigation cache.
        
        Args:
            cache_dir: Directory to store cache files
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._memory_cache: Dict[str, CachedInvestigation] = {}  # In-memory cache for fast access
    
    def _get_cache_key(
        self,
        fen: str,
        move_san: Optional[str] = None,
        investigation_type: str = "move",
        variant: Optional[str] = None
    ) -> str:
        """
        Generate cache key from FEN and move.
        
        Args:
            fen: Position FEN
            move_san: Move in SAN notation (optional)
            investigation_type: Type of investigation ("move" or "position")
            
        Returns:
            Cache key string
        """
        # Normalize FEN (remove move counters if present)
        fen_normalized = " ".join(fen.split()[:4])  # Keep only position, active color, castling, en passant
        
        key_parts = [fen_normalized, investigation_type]
        if variant:
            key_parts.append(str(variant))
        if move_san:
            key_parts.append(move_san)
        
        key_str = "|".join(key_parts)
        # Use hash for filename safety
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def _get_cache_file_path(self, cache_key: str) -> Path:
        """Get file path for cache entry"""
        return self.cache_dir / f"{cache_key}.json"
    
    def get(
        self,
        fen: str,
        move_san: Optional[str] = None,
        investigation_type: str = "move",
        variant: Optional[str] = None
    ) -> Optional[InvestigationResult]:
        """
        Get cached investigation result.
        
        Args:
            fen: Position FEN
            move_san: Move in SAN notation (optional)
            investigation_type: Type of investigation ("move" or "position")
            
        Returns:
            InvestigationResult if found, None otherwise
        """
        cache_key = self._get_cache_key(fen, move_san, investigation_type, variant)
        
        # Check memory cache first
        if cache_key in self._memory_cache:
            cached = self._memory_cache[cache_key]
            if cached.result:
                try:
                    return InvestigationResult(**cached.result)
                except Exception as e:
                    print(f"   ⚠️ [CACHE] Error reconstructing InvestigationResult from memory cache: {e}")
                    del self._memory_cache[cache_key]
        
        # Check disk cache
        cache_file = self._get_cache_file_path(cache_key)
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    data = json.load(f)
                    cached = CachedInvestigation.from_dict(data)
                    if cached.result:
                        # Store in memory cache
                        self._memory_cache[cache_key] = cached
                        return InvestigationResult(**cached.result)
            except Exception as e:
                print(f"   ⚠️ [CACHE] Error reading cache file {cache_file}: {e}")
        
        return None
    
    def set(
        self,
        fen: str,
        result: InvestigationResult,
        move_san: Optional[str] = None,
        investigation_type: str = "move",
        variant: Optional[str] = None
    ):
        """
        Cache investigation result.
        
        Args:
            fen: Position FEN
            result: InvestigationResult to cache
            move_san: Move in SAN notation (optional)
            investigation_type: Type of investigation ("move" or "position")
        """
        import time
        cache_key = self._get_cache_key(fen, move_san, investigation_type, variant)
        
        # Convert InvestigationResult to dict
        try:
            # Avoid expensive derived fields (like semantic_story) during caching.
            result_dict = result.to_dict(include_semantic_story=False)
        except Exception as e:
            print(f"   ⚠️ [CACHE] Error converting InvestigationResult to dict: {e}")
            return
        
        cached = CachedInvestigation(
            fen=fen,
            move_san=move_san,
            investigation_type=investigation_type,
            result=result_dict,
            timestamp=time.time()
        )
        
        # Store in memory cache
        self._memory_cache[cache_key] = cached
        
        # Store on disk
        cache_file = self._get_cache_file_path(cache_key)
        try:
            with open(cache_file, 'w') as f:
                json.dump(cached.to_dict(), f, indent=2)
        except Exception as e:
            print(f"   ⚠️ [CACHE] Error writing cache file {cache_file}: {e}")
    
    def get_raw_analysis(
        self,
        fen: str,
        move_san: Optional[str] = None,
        investigation_type: str = "move",
        variant: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get raw analysis data (PGN exploration, eval, etc.) from cache.
        
        Args:
            fen: Position FEN
            move_san: Move in SAN notation (optional)
            investigation_type: Type of investigation ("move" or "position")
            
        Returns:
            Dict with raw analysis data if found, None otherwise
        """
        cache_key = self._get_cache_key(fen, move_san, investigation_type, variant)
        
        # Check memory cache first
        if cache_key in self._memory_cache:
            cached = self._memory_cache[cache_key]
            if cached.result:
                return {
                    "pgn_exploration": cached.result.get("pgn_exploration", ""),
                    "eval_before": cached.result.get("eval_before"),
                    "eval_after": cached.result.get("eval_after"),
                    "eval_drop": cached.result.get("eval_drop"),
                    "best_move": cached.result.get("best_move"),
                    "pv_after_move": cached.result.get("pv_after_move", []),
                    "themes_identified": cached.result.get("themes_identified", []),
                    "tactics_found": cached.result.get("tactics_found", []),
                    "timestamp": cached.timestamp
                }
        
        # Check disk cache
        cache_file = self._get_cache_file_path(cache_key)
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    data = json.load(f)
                    cached = CachedInvestigation.from_dict(data)
                    if cached.result:
                        return {
                            "pgn_exploration": cached.result.get("pgn_exploration", ""),
                            "eval_before": cached.result.get("eval_before"),
                            "eval_after": cached.result.get("eval_after"),
                            "eval_drop": cached.result.get("eval_drop"),
                            "best_move": cached.result.get("best_move"),
                            "pv_after_move": cached.result.get("pv_after_move", []),
                            "themes_identified": cached.result.get("themes_identified", []),
                            "tactics_found": cached.result.get("tactics_found", []),
                            "timestamp": cached.timestamp
                        }
            except Exception as e:
                print(f"   ⚠️ [CACHE] Error reading cache file {cache_file}: {e}")
        
        return None
    
    def clear(self):
        """Clear all cache entries"""
        self._memory_cache.clear()
        if self.cache_dir.exists():
            for cache_file in self.cache_dir.glob("*.json"):
                try:
                    cache_file.unlink()
                except Exception as e:
                    print(f"   ⚠️ [CACHE] Error deleting cache file {cache_file}: {e}")


# Global cache instance
_investigation_cache: Optional[InvestigationCache] = None

def get_investigation_cache() -> InvestigationCache:
    """Get global investigation cache instance"""
    global _investigation_cache
    if _investigation_cache is None:
        _investigation_cache = InvestigationCache()
    return _investigation_cache

