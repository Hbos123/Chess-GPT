"""
Lifetime Performance Tracker
Analyzes career stats, rating progression, and improvement metrics.
"""

from typing import Dict, List, Any
from datetime import datetime, timedelta
import statistics

class LifetimeTracker:
    def __init__(self, supabase_client):
        self.supabase = supabase_client

    async def get_stats(self, user_id: str, games: List[Dict] = None) -> Dict[str, Any]:
        """Get comprehensive lifetime stats for a user."""
        # 1. Fetch raw game data if not provided
        if games is None:
            games = self.supabase.get_active_reviewed_games(user_id, limit=100)
        
        if not games:
            return self._empty_stats()

        # 2. Process rating trends
        rating_history = self._process_rating_history(games)
        
        # 3. Process win rates by time control
        win_rates = self._process_win_rates(games)
        
        # 4. Calculate improvement metrics
        improvement = self._calculate_improvement(rating_history)
        
        return {
            "total_games_analyzed": len(games),
            "rating_history": rating_history,
            "win_rates": win_rates,
            "improvement_velocity": improvement,
            "best_win_streak": self._calculate_win_streak(games),
            "peak_rating": max([r["rating"] for r in rating_history]) if rating_history else 0
        }

    def _process_rating_history(self, games: List[Dict]) -> List[Dict]:
        history = []
        for game in reversed(games):
            # Check direct fields first (metadata-only query), then fallback to metadata dict
            metadata = game.get("metadata", {})
            date = game.get("game_date") or game.get("created_at")
            rating = game.get("user_rating") or metadata.get("player_rating")
            if rating and date:
                history.append({
                    "date": date[:10],
                    "rating": rating,
                    "game_id": game.get("id")
                })
        return history

    def _process_win_rates(self, games: List[Dict]) -> Dict[str, Any]:
        tc_stats = {}
        for game in games:
            metadata = game.get("metadata", {})
            tc = game.get("time_control") or metadata.get("time_control", "unknown")
            result = game.get("result") or metadata.get("result", "unknown")
            
            if tc not in tc_stats:
                tc_stats[tc] = {"wins": 0, "losses": 0, "draws": 0, "total": 0}
            
            tc_stats[tc]["total"] += 1
            if result == "win":
                tc_stats[tc]["wins"] += 1
            elif result == "loss":
                tc_stats[tc]["losses"] += 1
            else:
                tc_stats[tc]["draws"] += 1
        
        # Convert to rates
        for tc in tc_stats:
            stats = tc_stats[tc]
            stats["win_rate"] = round(stats["wins"] / stats["total"] * 100, 1)
        
        return tc_stats

    def _calculate_improvement(self, rating_history: List[Dict]) -> Dict[str, Any]:
        if len(rating_history) < 5:
            return {"status": "insufficient_data"}
            
        recent = rating_history[-5:]
        oldest = rating_history[:5]
        
        avg_recent = statistics.mean([r["rating"] for r in recent])
        avg_oldest = statistics.mean([r["rating"] for r in oldest])
        
        delta = avg_recent - avg_oldest
        return {
            "rating_delta": round(delta, 1),
            "trend": "improving" if delta > 10 else "declining" if delta < -10 else "stable",
            "points_per_game": round(delta / len(rating_history), 2)
        }

    def _calculate_win_streak(self, games: List[Dict]) -> int:
        max_streak = 0
        current_streak = 0
        for game in games:
            if game.get("metadata", {}).get("result") == "win":
                current_streak += 1
                max_streak = max(max_streak, current_streak)
            else:
                current_streak = 0
        return max_streak

    def _empty_stats(self) -> Dict[str, Any]:
        return {
            "total_games_analyzed": 0,
            "rating_history": [],
            "win_rates": {},
            "improvement_velocity": {"status": "no_data"},
            "best_win_streak": 0,
            "peak_rating": 0
        }

