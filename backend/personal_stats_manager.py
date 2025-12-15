"""
Personal Stats Manager
Manages persistent personal statistics with incremental updates
"""

from typing import Dict, List, Optional, Any
from collections import defaultdict
import statistics
import json
from datetime import datetime


class PersonalStatsManager:
    """Manages persistent personal statistics with incremental updates."""
    
    def __init__(self, supabase_client):
        self.supabase = supabase_client
        self.schema_version = "1.0"
    
    def get_stats(self, user_id: str, account_filter: Optional[str] = None) -> Dict:
        """
        Get current stats, trigger lazy migration if needed.
        If account_filter provided, filter to that account only.
        """
        # Try to load existing stats
        stats_row = self.supabase.get_personal_stats(user_id)
        
        if stats_row is None:
            # First access - backfill from existing games
            print(f"   📊 No stats found for user {user_id}, backfilling from games...")
            games = self.supabase.get_analyzed_games(user_id, limit=30)
            if games:
                stats = self._backfill_stats_from_games(user_id, games)
                game_ids = [g.get('id') for g in games if g.get('id')]
                self.supabase.update_personal_stats(user_id, stats, game_ids)
                return stats
            else:
                # No games yet - create empty stats
                stats = self._create_empty_stats()
                self.supabase.update_personal_stats(user_id, stats, [])
                return stats
        
        # Return stats from JSONB
        stats_data = stats_row.get('stats', {})
        
        # Check if needs recalculation
        if stats_row.get('needs_recalc', False):
            print(f"   ⚠️ Stats marked for recalculation, recalculating...")
            return self.full_recalculate(user_id)
        
        return stats_data
    
    def update_stats_from_game(self, user_id: str, game_id: str, game_review: Dict) -> bool:
        """
        Incrementally update stats from a single game review.
        Merges new data into existing stats.
        """
        try:
            # Get current stats
            current_stats = self.get_stats(user_id)
            
            # Extract metrics from game_review
            ply_records = game_review.get("ply_records", [])
            player_color = game_review.get("metadata", {}).get("player_color", "white")
            result = game_review.get("metadata", {}).get("result", "unknown")
            time_control = game_review.get("metadata", {}).get("time_control", "")
            opening_name = game_review.get("opening", {}).get("name_final", "")
            
            # Update tag accuracy
            self._update_tag_accuracy(current_stats, ply_records, player_color, game_id)
            
            # Update tag preferences
            self._update_tag_preferences(current_stats, ply_records, player_color, game_id)
            
            # Update accuracy by piece
            self._update_piece_accuracy(current_stats, ply_records, player_color, game_id)
            
            # Update accuracy by time control
            self._update_time_control_accuracy(current_stats, ply_records, player_color, time_control, game_id)
            
            # Update accuracy by time spent
            self._update_time_spent_accuracy(current_stats, ply_records, player_color, game_id)
            
            # Update opening stats
            if opening_name:
                self._update_opening_stats(current_stats, opening_name, result, ply_records, player_color, game_id)
            
            # Update phase stats
            self._update_phase_stats(current_stats, ply_records, player_color, game_id)
            
            # Update metadata
            current_stats["total_games_analyzed"] = current_stats.get("total_games_analyzed", 0) + 1
            current_stats["last_game_analyzed_at"] = datetime.now().isoformat()
            
            # Get current game_ids and add new one
            stats_row = self.supabase.get_personal_stats(user_id)
            current_game_ids = stats_row.get('game_ids', []) if stats_row else []
            if game_id not in current_game_ids:
                current_game_ids.append(game_id)
            
            # Save updated stats
            return self.supabase.update_personal_stats(user_id, current_stats, current_game_ids)
        
        except Exception as e:
            print(f"   ❌ Error updating stats from game: {e}")
            return False
    
    def remove_game_from_stats(self, user_id: str, game_id: str) -> bool:
        """
        Remove a game's contributions and recalculate.
        This is called when a game is archived.
        """
        try:
            # Get current stats
            stats_row = self.supabase.get_personal_stats(user_id)
            if not stats_row:
                return True  # No stats to update
            
            current_stats = stats_row.get('stats', {})
            current_game_ids = stats_row.get('game_ids', [])
            
            # Remove game_id from list
            if game_id in current_game_ids:
                current_game_ids.remove(game_id)
            
            # Mark for recalculation (safer than trying to subtract)
            # We'll recalc on next access
            return self.supabase.mark_stats_for_recalc(user_id, current_game_ids)
        
        except Exception as e:
            print(f"   ❌ Error removing game from stats: {e}")
            return False
    
    def full_recalculate(self, user_id: str) -> Dict:
        """
        Full recalculation from all active games.
        Uses PersonalReviewAggregator logic.
        """
        print(f"   🔄 Full recalculation for user {user_id}...")
        
        # Get all active reviewed games
        games = self.supabase.get_active_reviewed_games(user_id, limit=30)
        
        if not games:
            return self._create_empty_stats()
        
        # Convert games to format expected by aggregator
        analyzed_games = []
        for game in games:
            game_review = game.get('game_review', {})
            if game_review:
                analyzed_games.append(game_review)
        
        if not analyzed_games:
            return self._create_empty_stats()
        
        # Use aggregator to calculate stats
        from personal_review_aggregator import PersonalReviewAggregator
        aggregator = PersonalReviewAggregator()
        aggregated = aggregator.aggregate(analyzed_games)
        
        # Convert to stats format
        stats = self._convert_aggregated_to_stats(aggregated)
        stats["total_games_analyzed"] = len(games)
        stats["last_game_analyzed_at"] = datetime.now().isoformat()
        
        # Save with game IDs
        game_ids = [g.get('id') for g in games if g.get('id')]
        self.supabase.update_personal_stats(user_id, stats, game_ids)
        
        return stats
    
    def validate_stats(self, user_id: str) -> Dict:
        """
        Validate stats integrity, mark for recalc if needed.
        Returns validation report.
        """
        stats_row = self.supabase.get_personal_stats(user_id)
        if not stats_row:
            return {"valid": True, "message": "No stats to validate"}
        
        stats = stats_row.get('stats', {})
        game_ids = stats_row.get('game_ids', [])
        
        # Check if game_ids match actual games
        actual_games = self.supabase.get_active_reviewed_games(user_id, limit=100)
        actual_game_ids = {g.get('id') for g in actual_games if g.get('id')}
        stored_game_ids = set(game_ids)
        
        issues = []
        if actual_game_ids != stored_game_ids:
            issues.append(f"Game ID mismatch: stored {len(stored_game_ids)}, actual {len(actual_game_ids)}")
        
        # Check stats structure
        if not isinstance(stats, dict):
            issues.append("Stats is not a dictionary")
        
        if issues:
            # Mark for recalculation
            self.supabase.mark_stats_for_recalc(user_id, list(actual_game_ids))
            return {"valid": False, "issues": issues, "marked_for_recalc": True}
        
        return {"valid": True, "message": "Stats validated successfully"}
    
    def _backfill_stats_from_games(self, user_id: str, games: List[Dict]) -> Dict:
        """Backfill stats from existing games."""
        analyzed_games = []
        for game in games:
            game_review = game.get('game_review', {})
            if game_review:
                analyzed_games.append(game_review)
        
        if not analyzed_games:
            return self._create_empty_stats()
        
        from personal_review_aggregator import PersonalReviewAggregator
        aggregator = PersonalReviewAggregator()
        aggregated = aggregator.aggregate(analyzed_games)
        
        stats = self._convert_aggregated_to_stats(aggregated)
        stats["total_games_analyzed"] = len(games)
        stats["last_game_analyzed_at"] = datetime.now().isoformat()
        
        return stats
    
    def _create_empty_stats(self) -> Dict:
        """Create empty stats structure."""
        return {
            "schema_version": self.schema_version,
            "total_games_analyzed": 0,
            "last_game_analyzed_at": None,
            "tag_accuracy": {},
            "tag_preferences": {},
            "accuracy_by_piece": {},
            "accuracy_by_time_control": {},
            "accuracy_by_time_spent": {},
            "opening_stats": {},
            "phase_stats": {}
        }
    
    def _convert_aggregated_to_stats(self, aggregated: Dict) -> Dict:
        """Convert PersonalReviewAggregator output to stats format."""
        stats = {
            "schema_version": self.schema_version,
            "tag_accuracy": {},
            "tag_preferences": {},
            "accuracy_by_piece": {},
            "accuracy_by_time_control": {},
            "accuracy_by_time_spent": {},
            "opening_stats": {},
            "phase_stats": {}
        }
        
        # Convert tag performance
        tag_perf = aggregated.get("performance_by_tags", {})
        all_tags = tag_perf.get("all_tags", [])
        for tag_data in all_tags:
            tag_name = tag_data.get("tag", "")
            if tag_name:
                stats["tag_accuracy"][tag_name] = {
                    "accuracy": tag_data.get("accuracy", 0),
                    "count": tag_data.get("move_count", 0),
                    "game_ids": []  # Will be populated during incremental updates
                }
        
        # Convert tag preferences
        tag_prefs = tag_perf.get("tag_preferences", {})
        for tag_name, pref_data in tag_prefs.items():
            stats["tag_preferences"][tag_name] = {
                "preference_signal": pref_data.get("preference_signal", "neutral"),
                "preference_strength": pref_data.get("preference_strength", 0),
                "created_count": pref_data.get("created_count", 0),
                "removed_count": pref_data.get("removed_count", 0),
                "created_accuracy": pref_data.get("created_accuracy"),
                "removed_accuracy": pref_data.get("removed_accuracy"),
                "game_ids": []
            }
        
        # Convert piece activity
        piece_activity = aggregated.get("piece_activity", [])
        for piece_data in piece_activity:
            piece_name = piece_data.get("piece", "")
            if piece_name:
                stats["accuracy_by_piece"][piece_name] = {
                    "accuracy": piece_data.get("accuracy", 0),
                    "count": piece_data.get("move_count", 0),
                    "game_ids": []
                }
        
        # Convert time control
        time_control = aggregated.get("performance_by_time_control", [])
        for tc_data in time_control:
            tc_name = tc_data.get("time_control", "")
            if tc_name:
                stats["accuracy_by_time_control"][tc_name] = {
                    "accuracy": tc_data.get("accuracy", 0),
                    "count": tc_data.get("game_count", 0),
                    "game_ids": []
                }
        
        # Convert time spent
        time_spent = aggregated.get("accuracy_by_time_spent", [])
        for ts_data in time_spent:
            ts_range = ts_data.get("time_range", "")
            if ts_range:
                stats["accuracy_by_time_spent"][ts_range] = {
                    "accuracy": ts_data.get("accuracy", 0),
                    "count": ts_data.get("move_count", 0),
                    "game_ids": []
                }
        
        # Convert opening performance
        opening_perf = aggregated.get("opening_performance", [])
        for op_data in opening_perf:
            op_name = op_data.get("name", "")
            if op_name:
                stats["opening_stats"][op_name] = {
                    "games": op_data.get("count", 0),
                    "win_rate": op_data.get("win_rate", 0) / 100,  # Convert to decimal
                    "avg_accuracy": op_data.get("avg_accuracy", 0),
                    "game_ids": []
                }
        
        # Convert phase stats
        phase_stats = aggregated.get("phase_stats", {})
        for phase_name, phase_data in phase_stats.items():
            stats["phase_stats"][phase_name] = {
                "accuracy": phase_data.get("accuracy", 0),
                "count": phase_data.get("move_count", 0),
                "game_ids": []
            }
        
        return stats
    
    def _update_tag_accuracy(self, stats: Dict, ply_records: List[Dict], player_color: str, game_id: str):
        """Incrementally update tag accuracy."""
        if "tag_accuracy" not in stats:
            stats["tag_accuracy"] = {}
        
        tag_counts = defaultdict(lambda: {"accuracies": [], "count": 0})
        
        for record in ply_records:
            if record.get("side_moved") != player_color:
                continue
            
            accuracy = record.get("accuracy_pct", 0)
            tags = record.get("analyse", {}).get("tags", [])
            
            for tag in tags:
                tag_name = tag if isinstance(tag, str) else tag.get("name", tag.get("tag", ""))
                if tag_name:
                    tag_counts[tag_name]["accuracies"].append(accuracy)
                    tag_counts[tag_name]["count"] += 1
        
        # Merge into stats
        for tag_name, data in tag_counts.items():
            if tag_name not in stats["tag_accuracy"]:
                stats["tag_accuracy"][tag_name] = {"accuracy": 0, "count": 0, "game_ids": []}
            
            old_count = stats["tag_accuracy"][tag_name]["count"]
            old_accuracy = stats["tag_accuracy"][tag_name]["accuracy"]
            new_count = data["count"]
            new_avg = statistics.mean(data["accuracies"]) if data["accuracies"] else 0
            
            # Weighted average
            total_count = old_count + new_count
            if total_count > 0:
                stats["tag_accuracy"][tag_name]["accuracy"] = (
                    (old_accuracy * old_count + new_avg * new_count) / total_count
                )
                stats["tag_accuracy"][tag_name]["count"] = total_count
            
            if game_id not in stats["tag_accuracy"][tag_name]["game_ids"]:
                stats["tag_accuracy"][tag_name]["game_ids"].append(game_id)
    
    def _update_tag_preferences(self, stats: Dict, ply_records: List[Dict], player_color: str, game_id: str):
        """Incrementally update tag preferences."""
        if "tag_preferences" not in stats:
            stats["tag_preferences"] = {}
        
        # Simplified incremental update - full logic would require tracking before/after tags
        # For now, mark that this game contributed
        # Full recalculation will compute preferences correctly
        pass  # Will be computed during full recalculation
    
    def _update_piece_accuracy(self, stats: Dict, ply_records: List[Dict], player_color: str, game_id: str):
        """Incrementally update accuracy by piece."""
        if "accuracy_by_piece" not in stats:
            stats["accuracy_by_piece"] = {}
        
        piece_counts = defaultdict(lambda: {"accuracies": [], "count": 0})
        
        for record in ply_records:
            if record.get("side_moved") != player_color:
                continue
            
            san = record.get("san", "")
            accuracy = record.get("accuracy_pct", 0)
            
            piece_type = self._get_piece_type_from_san(san)
            if piece_type:
                piece_counts[piece_type]["accuracies"].append(accuracy)
                piece_counts[piece_type]["count"] += 1
        
        # Merge into stats
        for piece_name, data in piece_counts.items():
            if piece_name not in stats["accuracy_by_piece"]:
                stats["accuracy_by_piece"][piece_name] = {"accuracy": 0, "count": 0, "game_ids": []}
            
            old_count = stats["accuracy_by_piece"][piece_name]["count"]
            old_accuracy = stats["accuracy_by_piece"][piece_name]["accuracy"]
            new_count = data["count"]
            new_avg = statistics.mean(data["accuracies"]) if data["accuracies"] else 0
            
            total_count = old_count + new_count
            if total_count > 0:
                stats["accuracy_by_piece"][piece_name]["accuracy"] = (
                    (old_accuracy * old_count + new_avg * new_count) / total_count
                )
                stats["accuracy_by_piece"][piece_name]["count"] = total_count
            
            if game_id not in stats["accuracy_by_piece"][piece_name]["game_ids"]:
                stats["accuracy_by_piece"][piece_name]["game_ids"].append(game_id)
    
    def _update_time_control_accuracy(self, stats: Dict, ply_records: List[Dict], player_color: str, time_control: str, game_id: str):
        """Incrementally update accuracy by time control."""
        if not time_control:
            return
        
        if "accuracy_by_time_control" not in stats:
            stats["accuracy_by_time_control"] = {}
        
        # Classify time control
        tc_category = self._classify_time_control(time_control)
        if not tc_category:
            return
        
        accuracies = []
        for record in ply_records:
            if record.get("side_moved") == player_color:
                accuracies.append(record.get("accuracy_pct", 0))
        
        if not accuracies:
            return
        
        avg_accuracy = statistics.mean(accuracies)
        
        if tc_category not in stats["accuracy_by_time_control"]:
            stats["accuracy_by_time_control"][tc_category] = {"accuracy": 0, "count": 0, "game_ids": []}
        
        old_count = stats["accuracy_by_time_control"][tc_category]["count"]
        old_accuracy = stats["accuracy_by_time_control"][tc_category]["accuracy"]
        new_count = len(accuracies)
        
        total_count = old_count + new_count
        if total_count > 0:
            stats["accuracy_by_time_control"][tc_category]["accuracy"] = (
                (old_accuracy * old_count + avg_accuracy * new_count) / total_count
            )
            stats["accuracy_by_time_control"][tc_category]["count"] = total_count
        
        if game_id not in stats["accuracy_by_time_control"][tc_category]["game_ids"]:
            stats["accuracy_by_time_control"][tc_category]["game_ids"].append(game_id)
    
    def _update_time_spent_accuracy(self, stats: Dict, ply_records: List[Dict], player_color: str, game_id: str):
        """Incrementally update accuracy by time spent."""
        if "accuracy_by_time_spent" not in stats:
            stats["accuracy_by_time_spent"] = {}
        
        time_ranges = {
            'instant': (0, 5, '<5s'),
            'quick': (5, 15, '5-15s'),
            'normal': (15, 30, '15-30s'),
            'deep': (30, float('inf'), '>30s')
        }
        
        range_counts = defaultdict(lambda: {"accuracies": [], "count": 0})
        
        for record in ply_records:
            if record.get("side_moved") != player_color:
                continue
            
            time_spent = record.get("time_spent_s", 0)
            accuracy = record.get("accuracy_pct", 0)
            
            if time_spent is None or time_spent <= 0:
                continue
            
            for category, (min_time, max_time, display_name) in time_ranges.items():
                if min_time <= time_spent < max_time:
                    range_counts[display_name]["accuracies"].append(accuracy)
                    range_counts[display_name]["count"] += 1
                    break
        
        # Merge into stats
        for range_name, data in range_counts.items():
            if range_name not in stats["accuracy_by_time_spent"]:
                stats["accuracy_by_time_spent"][range_name] = {"accuracy": 0, "count": 0, "game_ids": []}
            
            old_count = stats["accuracy_by_time_spent"][range_name]["count"]
            old_accuracy = stats["accuracy_by_time_spent"][range_name]["accuracy"]
            new_count = data["count"]
            new_avg = statistics.mean(data["accuracies"]) if data["accuracies"] else 0
            
            total_count = old_count + new_count
            if total_count > 0:
                stats["accuracy_by_time_spent"][range_name]["accuracy"] = (
                    (old_accuracy * old_count + new_avg * new_count) / total_count
                )
                stats["accuracy_by_time_spent"][range_name]["count"] = total_count
            
            if game_id not in stats["accuracy_by_time_spent"][range_name]["game_ids"]:
                stats["accuracy_by_time_spent"][range_name]["game_ids"].append(game_id)
    
    def _update_opening_stats(self, stats: Dict, opening_name: str, result: str, ply_records: List[Dict], player_color: str, game_id: str):
        """Incrementally update opening stats."""
        if "opening_stats" not in stats:
            stats["opening_stats"] = {}
        
        if opening_name not in stats["opening_stats"]:
            stats["opening_stats"][opening_name] = {
                "games": 0,
                "win_rate": 0,
                "avg_accuracy": 0,
                "game_ids": []
            }
        
        # Update game count
        stats["opening_stats"][opening_name]["games"] += 1
        
        # Update win rate
        old_games = stats["opening_stats"][opening_name]["games"] - 1
        old_wins = stats["opening_stats"][opening_name]["win_rate"] * old_games if old_games > 0 else 0
        new_wins = old_wins + (1 if result == "win" else 0)
        stats["opening_stats"][opening_name]["win_rate"] = new_wins / stats["opening_stats"][opening_name]["games"]
        
        # Update accuracy
        accuracies = [r.get("accuracy_pct", 0) for r in ply_records if r.get("side_moved") == player_color]
        if accuracies:
            avg_accuracy = statistics.mean(accuracies)
            old_games = stats["opening_stats"][opening_name]["games"] - 1
            old_avg = stats["opening_stats"][opening_name]["avg_accuracy"]
            stats["opening_stats"][opening_name]["avg_accuracy"] = (
                (old_avg * old_games + avg_accuracy) / stats["opening_stats"][opening_name]["games"]
            )
        
        if game_id not in stats["opening_stats"][opening_name]["game_ids"]:
            stats["opening_stats"][opening_name]["game_ids"].append(game_id)
    
    def _update_phase_stats(self, stats: Dict, ply_records: List[Dict], player_color: str, game_id: str):
        """Incrementally update phase stats."""
        if "phase_stats" not in stats:
            stats["phase_stats"] = {}
        
        phase_counts = defaultdict(lambda: {"accuracies": [], "count": 0})
        
        for record in ply_records:
            if record.get("side_moved") != player_color:
                continue
            
            phase = record.get("phase", "middlegame")
            accuracy = record.get("accuracy_pct", 0)
            phase_counts[phase]["accuracies"].append(accuracy)
            phase_counts[phase]["count"] += 1
        
        # Merge into stats
        for phase_name, data in phase_counts.items():
            if phase_name not in stats["phase_stats"]:
                stats["phase_stats"][phase_name] = {"accuracy": 0, "count": 0, "game_ids": []}
            
            old_count = stats["phase_stats"][phase_name]["count"]
            old_accuracy = stats["phase_stats"][phase_name]["accuracy"]
            new_count = data["count"]
            new_avg = statistics.mean(data["accuracies"]) if data["accuracies"] else 0
            
            total_count = old_count + new_count
            if total_count > 0:
                stats["phase_stats"][phase_name]["accuracy"] = (
                    (old_accuracy * old_count + new_avg * new_count) / total_count
                )
                stats["phase_stats"][phase_name]["count"] = total_count
            
            if game_id not in stats["phase_stats"][phase_name]["game_ids"]:
                stats["phase_stats"][phase_name]["game_ids"].append(game_id)
    
    def _get_piece_type_from_san(self, san: str) -> Optional[str]:
        """Extract piece type from SAN notation."""
        if not san:
            return None
        
        first_char = san[0]
        if first_char == 'K':
            return 'King'
        elif first_char == 'Q':
            return 'Queen'
        elif first_char == 'R':
            return 'Rook'
        elif first_char == 'B':
            return 'Bishop'
        elif first_char == 'N':
            return 'Knight'
        elif first_char in 'abcdefgh' or first_char.islower():
            return 'Pawn'
        elif first_char == 'O':
            return 'Castling'
        
        return None
    
    def _classify_time_control(self, time_control: str) -> Optional[str]:
        """Classify time control into category."""
        if isinstance(time_control, int):
            base_time = time_control
        elif isinstance(time_control, str):
            try:
                base_time = int(time_control.split('+')[0])
            except:
                return None
        else:
            return None
        
        if base_time < 180:
            return 'blitz'
        elif base_time < 900:
            return 'rapid'
        else:
            return 'classical'

