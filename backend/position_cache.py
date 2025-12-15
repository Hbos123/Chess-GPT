"""
Position cache for dynamic FEN generation.
Stores generated positions with TTL to provide variety while maintaining performance.
"""

import time
import random
from typing import Dict, List, Optional, Tuple


class PositionCache:
    """
    Cache for generated chess positions with TTL and pooling.
    
    Maintains up to 5 positions per (topic, side, difficulty) key.
    Positions expire after TTL seconds and are regenerated.
    """
    
    def __init__(self, ttl_seconds: int = 3600, pool_size: int = 5):
        """
        Initialize position cache.
        
        Args:
            ttl_seconds: Time-to-live for cached positions (default: 1 hour)
            pool_size: Maximum positions to store per key (default: 5)
        """
        self.ttl_seconds = ttl_seconds
        self.pool_size = pool_size
        
        # Storage: {(topic, side, difficulty): [position_data, ...]}
        self._cache: Dict[Tuple[str, str, str], List[Dict]] = {}
        
        # Timestamps: {(topic, side, difficulty): creation_time}
        self._timestamps: Dict[Tuple[str, str, str], float] = {}
        
        # Stats for monitoring
        self.hits = 0
        self.misses = 0
        self.generations = 0
    
    def _make_key(self, topic: str, side: str, difficulty: str) -> Tuple[str, str, str]:
        """Create cache key from parameters."""
        return (topic, side, difficulty)
    
    def _is_fresh(self, key: Tuple[str, str, str]) -> bool:
        """Check if cached positions for key are still fresh."""
        if key not in self._timestamps:
            return False
        
        age = time.time() - self._timestamps[key]
        return age < self.ttl_seconds
    
    async def get_position(
        self, 
        topic: str, 
        side: str, 
        difficulty: str
    ) -> Optional[Dict]:
        """
        Get a cached position if available and fresh.
        
        Returns None if cache miss or expired.
        Randomly selects from pool for variety.
        """
        key = self._make_key(topic, side, difficulty)
        
        # Check if we have fresh positions
        if key in self._cache and self._is_fresh(key):
            pool = self._cache[key]
            if pool:
                self.hits += 1
                # Return random position from pool for variety
                return random.choice(pool).copy()
        
        self.misses += 1
        return None
    
    async def store_position(
        self,
        topic: str,
        side: str,
        difficulty: str,
        position_data: Dict
    ) -> None:
        """
        Store a generated position in the cache.
        
        Adds to pool (up to pool_size).
        Updates timestamp when adding to empty/expired pool.
        """
        key = self._make_key(topic, side, difficulty)
        
        # If expired or doesn't exist, reset pool
        if not self._is_fresh(key):
            self._cache[key] = []
            self._timestamps[key] = time.time()
        
        # Add to pool if not full
        pool = self._cache.get(key, [])
        if len(pool) < self.pool_size:
            pool.append(position_data)
            self._cache[key] = pool
            self.generations += 1
    
    def clear_expired(self) -> int:
        """
        Remove expired entries from cache.
        
        Returns:
            Number of entries removed
        """
        now = time.time()
        expired_keys = []
        
        for key, timestamp in self._timestamps.items():
            if now - timestamp >= self.ttl_seconds:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self._cache[key]
            del self._timestamps[key]
        
        return len(expired_keys)
    
    def get_stats(self) -> Dict:
        """Get cache statistics for monitoring."""
        total_requests = self.hits + self.misses
        hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0
        
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": f"{hit_rate:.1f}%",
            "generations": self.generations,
            "pool_count": len(self._cache),
            "total_positions": sum(len(pool) for pool in self._cache.values()),
        }
    
    def clear(self) -> None:
        """Clear all cached positions."""
        self._cache.clear()
        self._timestamps.clear()
        self.hits = 0
        self.misses = 0
        self.generations = 0

