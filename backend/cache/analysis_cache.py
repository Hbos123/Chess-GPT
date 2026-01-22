"""
Analysis Cache for Personal Review System
Hybrid in-memory + Supabase caching
"""

from typing import Dict, Any, Optional
import time
from datetime import datetime, timedelta


class AnalysisCache:
    """Hybrid caching system for game analysis results"""
    
    def __init__(self, supabase_client=None, ttl_seconds: int = 24 * 60 * 60):
        """
        Initialize cache.
        
        Args:
            supabase_client: Optional Supabase client for persistent storage
            ttl_seconds: Time-to-live for in-memory cache entries
        """
        self._memory_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_timestamps: Dict[str, float] = {}
        self.supabase_client = supabase_client
        self.ttl_seconds = ttl_seconds
    
    def _make_cache_key(self, username: str, platform: str, game_id: str, depth: int) -> str:
        """Generate cache key"""
        return f"{username}:{platform}:{game_id}:{depth}"
    
    def get_cached_analysis(
        self, 
        username: str, 
        platform: str, 
        game_id: str, 
        depth: int
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached analysis result.
        Checks in-memory cache first, then Supabase.
        
        Args:
            username: Player username
            platform: Platform name
            game_id: Game identifier
            depth: Analysis depth
            
        Returns:
            Cached analysis result or None
        """
        cache_key = self._make_cache_key(username, platform, game_id, depth)
        
        # Check in-memory cache first
        if cache_key in self._memory_cache:
            timestamp = self._cache_timestamps.get(cache_key, 0)
            age = time.time() - timestamp
            
            if age < self.ttl_seconds:
                print(f"   ✅ Cache HIT (memory): {cache_key}")
                return self._memory_cache[cache_key]
            else:
                # Expired, remove from memory
                del self._memory_cache[cache_key]
                del self._cache_timestamps[cache_key]
        
        # Check Supabase (permanent cache)
        if self.supabase_client:
            try:
                # Query games table for this game
                # We need to find the game by external_id or game_id
                result = self.supabase_client.client.table("games")\
                    .select("game_review, review_type, analyzed_at")\
                    .or_(f"external_id.eq.{game_id},id.eq.{game_id}")\
                    .maybe_single()\
                    .execute()
                
                if result.data:
                    game_review = result.data.get("game_review")
                    review_type = result.data.get("review_type", "full")
                    
                    # Check if review exists and is full analysis
                    if game_review and review_type == "full":
                        # Extract ply_records to check depth
                        ply_records = game_review.get("ply_records", [])
                        if ply_records:
                            # Check if analysis depth matches (approximate check)
                            # We'll accept cached analysis if it exists, depth matching is approximate
                            print(f"   ✅ Cache HIT (Supabase): {cache_key}")
                            
                            # Store in memory cache for faster access
                            self._memory_cache[cache_key] = game_review
                            self._cache_timestamps[cache_key] = time.time()
                            
                            return game_review
            except Exception as e:
                print(f"   ⚠️ Error checking Supabase cache: {e}")
        
        print(f"   ❌ Cache MISS: {cache_key}")
        return None
    
    def cache_analysis(
        self,
        username: str,
        platform: str,
        game_id: str,
        depth: int,
        result: Dict[str, Any]
    ) -> None:
        """
        Cache analysis result.
        Stores in both in-memory cache and Supabase.
        
        Args:
            username: Player username
            platform: Platform name
            game_id: Game identifier
            depth: Analysis depth
            result: Analysis result dictionary
        """
        cache_key = self._make_cache_key(username, platform, game_id, depth)
        
        # Store in memory cache
        self._memory_cache[cache_key] = result
        self._cache_timestamps[cache_key] = time.time()
        
        # Note: Supabase storage happens in the main endpoint when saving games
        # This cache is just for quick lookups
        print(f"   💾 Cached (memory): {cache_key}")
    
    def invalidate_cache(
        self,
        username: Optional[str] = None,
        platform: Optional[str] = None,
        game_id: Optional[str] = None
    ) -> None:
        """
        Invalidate cache entries.
        If all params are None, clears entire cache.
        
        Args:
            username: Optional username filter
            platform: Optional platform filter
            game_id: Optional game_id filter
        """
        if username is None and platform is None and game_id is None:
            # Clear entire cache
            self._memory_cache.clear()
            self._cache_timestamps.clear()
            print(f"   🗑️ Cleared entire cache")
            return
        
        # Remove matching entries
        keys_to_remove = []
        for key in self._memory_cache.keys():
            parts = key.split(":")
            if len(parts) >= 4:
                key_username, key_platform, key_game_id, _ = parts[:4]
                
                match = True
                if username and key_username != username:
                    match = False
                if platform and key_platform != platform:
                    match = False
                if game_id and key_game_id != game_id:
                    match = False
                
                if match:
                    keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del self._memory_cache[key]
            del self._cache_timestamps[key]
        
        print(f"   🗑️ Invalidated {len(keys_to_remove)} cache entries")
    
    def cleanup_expired(self) -> int:
        """
        Clean up expired cache entries.
        
        Returns:
            Number of entries removed
        """
        now = time.time()
        keys_to_remove = []
        
        for key, timestamp in self._cache_timestamps.items():
            age = now - timestamp
            if age >= self.ttl_seconds:
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del self._memory_cache[key]
            del self._cache_timestamps[key]
        
        if keys_to_remove:
            print(f"   🧹 Cleaned up {len(keys_to_remove)} expired cache entries")
        
        return len(keys_to_remove)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return {
            "memory_entries": len(self._memory_cache),
            "ttl_seconds": self.ttl_seconds,
            "has_supabase": self.supabase_client is not None
        }


