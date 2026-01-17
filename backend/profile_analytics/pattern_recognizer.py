"""
Pattern Recognizer
Identifies advanced playing patterns, opening preferences, and time management habits.
Uses both active (full detail) and compressed (pattern-only) games for comprehensive analysis.
"""

from typing import Dict, List, Any, Optional
from collections import Counter
from datetime import datetime
import statistics
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.game_window_manager import GameWindowManager

class PatternRecognizer:
    def __init__(self, supabase_client, game_window_manager: Optional[GameWindowManager] = None):
        self.supabase = supabase_client
        self.game_window_manager = game_window_manager

    async def get_patterns(self, user_id: str, games: List[Dict] = None) -> Dict[str, Any]:
        """Identify advanced patterns for a user.
        Uses both active games (full details) and compressed games (pattern data only).
        """
        if games is None:
            # Get active games (full details)
            active_games = self.supabase.get_active_reviewed_games(user_id, limit=60, include_compressed=False)
            
            # Get compressed games (pattern_summary only) if window manager is available
            compressed_games = []
            if self.game_window_manager:
                compressed_games_raw = self.game_window_manager.get_compressed_games(user_id)
                compressed_games = [
                    self.game_window_manager.expand_pattern_summary(cg) 
                    for cg in compressed_games_raw
                ]
            
            # Combine for pattern analysis
            games = active_games + compressed_games
        
        if not games:
            return {"status": "no_data"}

        return {
            "opening_repertoire": self._analyze_openings(games),
            "time_management": self._analyze_time_habits(games),
            "opponent_analysis": self._analyze_opponents(games),
            "clutch_performance": self._analyze_clutch_factor(games)
        }

    def _analyze_openings(self, games: List[Dict]) -> List[Dict]:
        openings = []
        for game in games:
            # Check direct fields first, then fallback to opening dict/metadata
            opening_data = game.get("opening", {})
            eco = game.get("opening_eco") or opening_data.get("eco", "Unknown")
            name = game.get("opening_name") or opening_data.get("name_final", "Unknown")
            
            metadata = game.get("metadata", {})
            result = game.get("result") or metadata.get("result")
            
            if name != "Unknown":
                openings.append((name, eco, result))
        
        counts = Counter([o[:2] for o in openings])
        wins = Counter([o[:2] for o in openings if o[2] == "win"])
        
        repertoire = []
        for (name, eco), count in counts.most_common(5):
            win_count = wins[(name, eco)]
            repertoire.append({
                "name": name,
                "eco": eco,
                "frequency": count,
                "win_rate": round(win_count / count * 100, 1)
            })
        return repertoire

    def _analyze_time_habits(self, games: List[Dict]) -> Dict[str, Any]:
        # Correlation between time spent and accuracy
        time_accuracy_data = []
        for game in games:
            review = game.get("game_review", {})
            ply_records = review.get("ply_records", [])
            for ply in ply_records:
                time = ply.get("time_spent_s")
                acc = ply.get("accuracy_pct")
                if time is not None and acc is not None:
                    time_accuracy_data.append((time, acc))
        
        if not time_accuracy_data:
            return {"status": "insufficient_data"}

        # Bucket by time
        buckets = {"blitz": [], "normal": [], "slow": []}
        for time, acc in time_accuracy_data:
            if time < 5:
                buckets["blitz"].append(acc)
            elif time < 20:
                buckets["normal"].append(acc)
            else:
                buckets["slow"].append(acc)
        
        return {
            "accuracy_by_time": {
                k: round(statistics.mean(v), 1) if v else 0 
                for k, v in buckets.items()
            },
            "time_usage_style": "fast" if len(buckets["blitz"]) > len(buckets["slow"]) * 2 else "deliberate"
        }

    def _analyze_opponents(self, games: List[Dict]) -> Dict[str, Any]:
        # Performance vs higher/lower rated
        vs_higher = []
        vs_lower = []
        
        for game in games:
            metadata = game.get("metadata", {})
            p_rating = game.get("user_rating") or metadata.get("player_rating")
            o_rating = game.get("opponent_rating") or metadata.get("opponent_rating")
            result = game.get("result") or metadata.get("result")
            
            if p_rating and o_rating:
                diff = o_rating - p_rating
                score = 1 if result == "win" else 0.5 if result == "draw" else 0
                if diff > 50:
                    vs_higher.append(score)
                elif diff < -50:
                    vs_lower.append(score)
        
        return {
            "win_rate_vs_higher": round(statistics.mean(vs_higher) * 100, 1) if vs_higher else 0,
            "win_rate_vs_lower": round(statistics.mean(vs_lower) * 100, 1) if vs_lower else 0
        }

    def _analyze_clutch_factor(self, games: List[Dict]) -> float:
        # Performance in the last 10 moves of close games
        clutch_scores = []
        for game in games:
            review = game.get("game_review", {})
            ply_records = review.get("ply_records", [])
            if len(ply_records) < 20: continue
            
            # Check if it was a close game heading into endgame
            last_plies = ply_records[-10:]
            accuracies = [p.get("accuracy_pct", 0) for p in last_plies]
            if accuracies:
                clutch_scores.append(statistics.mean(accuracies))
        
        return round(statistics.mean(clutch_scores), 1) if clutch_scores else 0
    
    async def save_daily_pattern_snapshot(
        self, 
        user_id: str, 
        pattern_type: str = "current"
    ) -> Optional[str]:
        """
        Save daily aggregated patterns to pattern_snapshots table.
        pattern_type: 'current' (active games) or 'historical' (compressed games)
        """
        # Get patterns for today
        patterns = await self.get_patterns(user_id)
        
        # Count active vs compressed games
        active_games = self.supabase.get_active_reviewed_games(
            user_id, limit=60, include_compressed=False
        )
        compressed_games = []
        if self.game_window_manager:
            compressed_games_raw = self.game_window_manager.get_compressed_games(user_id)
            compressed_games = compressed_games_raw
        
        # Save snapshot
        snapshot_data = {
            "user_id": user_id,
            "snapshot_date": datetime.utcnow().date().isoformat(),
            "pattern_type": pattern_type,
            "opening_repertoire": patterns.get("opening_repertoire", []),
            "time_management": patterns.get("time_management", {}),
            "opponent_analysis": patterns.get("opponent_analysis", {}),
            "clutch_performance": patterns.get("clutch_performance", {}),
            "games_count": len(active_games) + len(compressed_games),
            "active_games_count": len(active_games),
            "compressed_games_count": len(compressed_games),
        }
        
        # Upsert to database
        return self.supabase.upsert_pattern_snapshot(snapshot_data)

