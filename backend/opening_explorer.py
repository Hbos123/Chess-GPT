"""
Lichess Opening Explorer API client with caching.
"""

import aiohttp
import asyncio
import time
import urllib.parse
from typing import Dict, List, Optional
import chess


class LichessExplorerClient:
    """Client for querying the Lichess Opening Explorer API."""
    
    BASE_URL = "https://explorer.lichess.ovh"
    CACHE_TTL = 3600  # 1 hour
    
    def __init__(self):
        self._cache: Dict[str, tuple[Dict, float]] = {}  # {cache_key: (data, timestamp)}
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def close(self):
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()
    
    def _make_cache_key(self, fen: str, db: str, speeds: List[str], ratings: List[int]) -> str:
        """Create a cache key from query parameters."""
        speeds_str = ",".join(sorted(speeds))
        ratings_str = f"{ratings[0]}-{ratings[1]}"
        return f"{fen}|{db}|{speeds_str}|{ratings_str}"
    
    def _get_cached(self, cache_key: str) -> Optional[Dict]:
        """Get data from cache if valid."""
        if cache_key in self._cache:
            data, timestamp = self._cache[cache_key]
            if time.time() - timestamp < self.CACHE_TTL:
                return data
            else:
                del self._cache[cache_key]
        return None
    
    def _set_cache(self, cache_key: str, data: Dict):
        """Store data in cache with timestamp."""
        self._cache[cache_key] = (data, time.time())
    
    async def query_position(
        self,
        fen: str,
        db: str = "lichess",
        speeds: Optional[List[str]] = None,
        ratings: Optional[List[int]] = None,
        since: Optional[str] = "2020-01"
    ) -> Dict:
        """
        Query the Lichess Opening Explorer for a position.
        
        Args:
            fen: Position in FEN notation
            db: "lichess" or "masters"
            speeds: List of speeds to include (e.g., ["rapid", "classical"])
            ratings: [min_rating, max_rating] (e.g., [1600, 2000])
            since: Date filter in YYYY-MM format
        
        Returns:
            {
                "white": int, "draws": int, "black": int,
                "moves": [
                    {"uci": str, "san": str, "white": int, "draws": int, "black": int,
                     "averageRating": int, "game": {...}?, "opening": {"eco": str, "name": str}?}
                ],
                "opening": {"eco": str, "name": str}?,
                "topGames": [...]?
            }
        """
        if speeds is None:
            speeds = ["rapid", "classical"]
        if ratings is None:
            ratings = [1600, 2000]
        
        # Check cache
        cache_key = self._make_cache_key(fen, db, speeds, ratings)
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached
        
        # Build query parameters
        params = {
            "fen": fen,
            "speeds": ",".join(speeds),
            "ratings": ",".join(map(str, ratings))
        }
        
        if since and db == "lichess":
            params["since"] = since
        
        # Choose endpoint based on database
        endpoint = f"/{db}"
        
        # Make request
        session = await self._get_session()
        url = f"{self.BASE_URL}{endpoint}"
        
        try:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status != 200:
                    raise Exception(f"Lichess API error: {response.status}")
                
                data = await response.json()
                
                # Cache and return
                self._set_cache(cache_key, data)
                return data
        
        except asyncio.TimeoutError:
            raise Exception("Lichess API timeout")
        except Exception as e:
            raise Exception(f"Failed to query Lichess explorer: {str(e)}")
    
    async def parse_san_to_fen(self, moves_san: List[str]) -> str:
        """
        Convert a sequence of SAN moves to a FEN.
        
        Args:
            moves_san: List of moves in SAN notation (e.g., ["e4", "c5", "Nf3"])
        
        Returns:
            FEN string of the resulting position
        """
        board = chess.Board()
        
        for move_san in moves_san:
            try:
                move = board.parse_san(move_san)
                board.push(move)
            except Exception as e:
                raise ValueError(f"Invalid SAN move '{move_san}': {str(e)}")
        
        return board.fen()
    
    def calculate_popularity(self, move_stats: Dict) -> float:
        """
        Calculate popularity percentage for a move.
        
        Args:
            move_stats: {"white": int, "draws": int, "black": int}
        
        Returns:
            Popularity as a float between 0 and 1
        """
        total = move_stats.get("white", 0) + move_stats.get("draws", 0) + move_stats.get("black", 0)
        return total
    
    def calculate_score(self, move_stats: Dict, for_white: bool) -> float:
        """
        Calculate win rate score for a move from the perspective of one side.
        
        Args:
            move_stats: {"white": int, "draws": int, "black": int}
            for_white: True if calculating for White, False for Black
        
        Returns:
            Score between 0 and 1 (higher is better)
        """
        white = move_stats.get("white", 0)
        draws = move_stats.get("draws", 0)
        black = move_stats.get("black", 0)
        total = white + draws + black
        
        if total == 0:
            return 0.5
        
        if for_white:
            return (white + 0.5 * draws) / total
        else:
            return (black + 0.5 * draws) / total




