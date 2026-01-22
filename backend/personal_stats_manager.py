"""
Personal Stats Manager
Manages persistent personal statistics with incremental updates
Includes Habits tracking system with significance detection
"""

from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict
import statistics
import json
import math
from datetime import datetime


def format_tag_display_name(tag_name: str) -> str:
    """
    Convert a raw tag name to a human-readable display name.
    e.g., "tag.file.semi.d" -> "Semi-Open D-File"
    e.g., "tag.diagonal.open.c1_h6" -> "Open c1-h6 Diagonal"
    """
    # Handle phase habits
    if tag_name.startswith("phase_"):
        phase = tag_name.replace("phase_", "")
        return f"{phase.capitalize()} Phase"
    
    # Remove "tag." prefix if present
    normalized = tag_name.lower().replace("tag.", "").replace("tag_", "")
    parts = normalized.split(".")
    
    # Direct display mappings for specific tag paths
    DISPLAY_MAP = {
        # File patterns
        "file.open": "Open",
        "file.semi": "Semi-Open",
        
        # Diagonal patterns
        "diagonal.open": "Open Diagonal",
        "diagonal.long": "Long Diagonal",
        
        # King safety
        "king.attackers.count": "King Attackers",
        "king.defenders.count": "King Defenders",
        "king.shield.missing": "Missing King Shield",
        "king.file.open": "Open King File",
        "king.file.semi": "Semi-Open King File",
        
        # Center control
        "center.control.core": "Core Center Control",
        "center.control.near": "Extended Center",
        
        # Rook play
        "rook.connected": "Connected Rooks",
        "rook.semi_open": "Rook on Semi-Open File",
        "rook.open_file": "Rook on Open File",
        "rook.rank7": "Rook on 7th Rank",
        
        # Bishop play
        "bishop.pair": "Bishop Pair",
        "bishop.bad": "Bad Bishop",
        "bishop.good": "Good Bishop",
        "bishop.fianchetto": "Fianchettoed Bishop",
        
        # Activity
        "activity.mobility.knight": "Knight Mobility",
        "activity.mobility.bishop": "Bishop Mobility",
        "activity.mobility.rook": "Rook Mobility",
        "activity.mobility.queen": "Queen Mobility",
        
        # Space
        "space.advantage": "Space Advantage",
        
        # Piece safety
        "piece.trapped": "Trapped Piece",
        "piece.hanging": "Hanging Piece",
        
        # Tactics
        "fork": "Fork Tactics",
        "pin": "Pin Tactics",
        "skewer": "Skewer Tactics",
        "discovered_attack": "Discovered Attacks",
        "double_attack": "Double Attacks",
    }
    
    # Check for exact matches in display map
    tag_path = ".".join(parts)
    if tag_path in DISPLAY_MAP:
        return DISPLAY_MAP[tag_path]
    
    # Check for partial matches (e.g., "file.open" matches "file.open.d")
    for pattern, display in DISPLAY_MAP.items():
        if tag_path.startswith(pattern + "."):
            suffix = tag_path[len(pattern) + 1:]
            
            # Handle file specifics (e.g., file.semi.d -> "Semi-Open D-File")
            if pattern.startswith("file."):
                return f"{display} {suffix.upper()}-File"
            
            # Handle diagonal specifics (e.g., diagonal.open.c1_h6 -> "Open c1-h6 Diagonal")
            if pattern.startswith("diagonal."):
                squares = suffix.replace("_", "-")
                return f"{display} {squares}"
            
            return f"{display} ({suffix})"
    
    # Handle key squares (e.g., key.e5 -> "e5 Control")
    if parts[0] == "key" and len(parts) >= 2:
        return f"{parts[1].upper()} Control"
    
    # Handle file patterns without exact match
    if parts[0] == "file" and len(parts) >= 3:
        type_name = "Open" if parts[1] == "open" else "Semi-Open"
        return f"{type_name} {parts[2].upper()}-File"
    
    # Handle diagonal patterns without exact match
    if parts[0] == "diagonal" and len(parts) >= 3:
        type_name = "Open" if parts[1] == "open" else "Long" if parts[1] == "long" else parts[1].title()
        squares = parts[2].replace("_", "-")
        return f"{type_name} {squares} Diagonal"
    
    # Fallback: Title case with cleanup
    return " ".join(p.title() for p in parts).replace("_", " ").replace("-", " ")


def get_tag_group(tag_name: str) -> str:
    """
    Get the group key for a tag name.
    Used for grouping related habits together.
    """
    normalized = tag_name.lower()
    
    # Group mappings
    if "file.open" in normalized or "file.semi" in normalized:
        return "files"
    if "diagonal" in normalized:
        return "diagonals"
    if "king" in normalized:
        return "king_safety"
    if "center" in normalized or "key.d" in normalized or "key.e" in normalized:
        return "center_control"
    if "rook" in normalized:
        return "rook_play"
    if "bishop" in normalized:
        return "bishop_play"
    if "activity" in normalized or "mobility" in normalized:
        return "piece_activity"
    if "space" in normalized:
        return "space"
    if "piece.trapped" in normalized or "piece.hanging" in normalized:
        return "piece_safety"
    if "phase_" in normalized:
        return "phases"
    
    return "other"


# Habit categories for grouping related tags
HABIT_CATEGORIES = {
    "tactics": ["fork", "pin", "skewer", "discovered_attack", "double_attack", "deflection", "decoy", "interference", "overload", "trapped_piece", "removing_defender", "zugzwang"],
    "positional": ["outpost", "weak_square", "pawn_structure", "piece_activity", "space_advantage", "prophylaxis", "restriction"],
    "endgame": ["king_activity", "pawn_promotion", "opposition", "breakthrough", "fortress", "stalemate_trap"],
    "time_pressure": ["quick_move", "time_scramble", "premove"],
    "attacking": ["attack", "sacrifice", "checkmate_threat", "king_hunt", "initiative"],
    "defensive": ["defense", "exchange", "simplification", "counterattack", "consolidation"]
}

# Minimum thresholds for significance
MIN_SAMPLE_SIZE = 3  # Minimum games for a habit to appear (lowered for faster feedback)
MIN_DEVIATION_PERCENT = 5  # Minimum % deviation from baseline to be significant
MAX_HABITS_DISPLAY = 12  # Maximum habits to show in dashboard


class PersonalStatsManager:
    """Manages persistent personal statistics with incremental updates."""
    
    def __init__(self, supabase_client, profile_indexer=None):
        self.supabase = supabase_client
        self.profile_indexer = profile_indexer
        self.schema_version = "2.0"  # Updated for habits tracking
    
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
            
            # Update tag transitions (gained/lost)
            self._update_tag_transitions(current_stats, ply_records, player_color, game_id)
            
            # Update accuracy by piece
            self._update_piece_accuracy(current_stats, ply_records, player_color, game_id, game_review)
            
            # Update accuracy by time control
            self._update_time_control_accuracy(current_stats, ply_records, player_color, time_control, game_id)
            
            # Update accuracy by time spent
            self._update_time_spent_accuracy(current_stats, ply_records, player_color, game_id)
            
            # Update opening stats
            if opening_name:
                self._update_opening_stats(current_stats, opening_name, result, ply_records, player_color, game_id, game_review)
            
            # Update phase stats
            self._update_phase_stats(current_stats, ply_records, player_color, game_id, result, game_review)
            
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
        # Include pgn from game row as it's stored separately from game_review
        analyzed_games = []
        for game in games:
            game_review = game.get('game_review', {})
            if game_review:
                # Merge pgn from game row into game_review for aggregator
                game_review_with_pgn = {**game_review}
                if game.get('pgn'):
                    game_review_with_pgn['pgn'] = game.get('pgn')
                analyzed_games.append(game_review_with_pgn)
        
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
                # Merge pgn from game row into game_review for aggregator
                game_review_with_pgn = {**game_review}
                if game.get('pgn'):
                    game_review_with_pgn['pgn'] = game.get('pgn')
                analyzed_games.append(game_review_with_pgn)
        
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
            "phase_stats": {},
            # New habits tracking structure
            "habits": {},
            "habits_computed_at": None
        }
    
    # =========================================================================
    # HABITS SYSTEM - Micro-habits tracking with significance detection
    # =========================================================================
    
    def _compute_endgame_habits(self, user_id: str, games: List[Dict], baseline_accuracy: float) -> List[Dict]:
        """Compute endgame phase habits from endgame_skills data."""
        habits = []
        
        # Try to get profileStats from profile_indexer if available
        try:
            if self.profile_indexer:
                profile_stats = self.profile_indexer.get_stats(user_id)
                advanced = profile_stats.get("advanced", {})
                endgame_skills = advanced.get("endgame_skills", {})
                
                if endgame_skills:
                    phases = ["opening", "middlegame", "endgame"]
                    for phase in phases:
                        phase_acc = endgame_skills.get(f"{phase}_accuracy")
                        if phase_acc is not None:
                            deviation = phase_acc - baseline_accuracy
                            extremeness = abs(deviation)
                            
                            # Build history from games
                            history = []
                            for game in games:
                                game_id = game.get("id", "")
                                game_date = game.get("game_date") or game.get("created_at", "")
                                if isinstance(game_date, str) and len(game_date) > 10:
                                    game_date = game_date[:10]
                                
                                game_review = game.get("game_review", {})
                                ply_records = game_review.get("ply_records", [])
                                player_color = game_review.get("metadata", {}).get("player_color", "white")
                                
                                phase_accuracies = []
                                for record in ply_records:
                                    if record.get("side_moved") == player_color:
                                        record_phase = record.get("phase", "middlegame")
                                        if record_phase == phase:
                                            phase_accuracies.append(record.get("accuracy_pct", 0))
                                
                                if phase_accuracies:
                                    history.append({
                                        "game_id": game_id,
                                        "game_date": game_date,
                                        "accuracy": round(statistics.mean(phase_accuracies), 1),
                                        "count": len(phase_accuracies)
                                    })
                            
                            if len(history) >= MIN_SAMPLE_SIZE:
                                habits.append({
                                    "name": f"phase_{phase}",
                                    "display_name": f"{phase.title()} Phase",
                                    "category": "phases",
                                    "habit_type": "endgame",
                                    "accuracy": round(phase_acc, 1),
                                    "baseline": round(baseline_accuracy, 1),
                                    "deviation": round(deviation, 1),
                                    "deviation_percent": round((deviation / baseline_accuracy * 100) if baseline_accuracy > 0 else 0, 1),
                                    "sample_size": len(history),
                                    "total_occurrences": sum(h["count"] for h in history),
                                    "variance": round(statistics.stdev([h["accuracy"] for h in history]) if len(history) > 1 else 0, 1),
                                    "significance": round(min(1.0, extremeness / 25.0), 2),  # Normalize to 0-1
                                    "trend": "stable",  # Will be calculated later
                                    "trend_value": 0,
                                    "sparkline": [h["accuracy"] for h in history[-10:]],
                                    "history": history[-15:],
                                    "extremeness": extremeness
                                })
        except Exception as e:
            print(f"   ⚠️ Error computing endgame habits: {e}")
        
        return habits
    
    def _compute_tag_accuracy_habits(self, user_id: str, games: List[Dict], baseline_accuracy: float) -> List[Dict]:
        """Compute habits from tags.best and tags.worst data."""
        habits = []
        
        try:
            if self.profile_indexer:
                profile_stats = self.profile_indexer.get_stats(user_id)
                tags_data = profile_stats.get("tags", {})
                best_tags = tags_data.get("best", [])
                worst_tags = tags_data.get("worst", [])
                
                # Process best tags (strengths)
                for tag_data in best_tags[:5]:  # Top 5 best
                    tag_name = tag_data.get("name", "")
                    if not tag_name:
                        continue
                    
                    win_rate = tag_data.get("win_rate", 0) / 100.0 if tag_data.get("win_rate") else None
                    avg_cp_loss = tag_data.get("avg_cp_loss", 0)
                    games_count = tag_data.get("games", 0)
                    
                    # Build history from games
                    history = []
                    for game in games:
                        game_id = game.get("id", "")
                        game_date = game.get("game_date") or game.get("created_at", "")
                        if isinstance(game_date, str) and len(game_date) > 10:
                            game_date = game_date[:10]
                        
                        game_review = game.get("game_review", {})
                        ply_records = game_review.get("ply_records", [])
                        player_color = game_review.get("metadata", {}).get("player_color", "white")
                        
                        tag_accuracies = []
                        for record in ply_records:
                            if record.get("side_moved") == player_color:
                                tags = record.get("analyse", {}).get("tags", [])
                                for tag in tags:
                                    tag_str = tag if isinstance(tag, str) else tag.get("name", tag.get("tag", ""))
                                    if tag_str and tag_str.lower() == tag_name.lower():
                                        tag_accuracies.append(record.get("accuracy_pct", 0))
                        
                        if tag_accuracies:
                            history.append({
                                "game_id": game_id,
                                "game_date": game_date,
                                "accuracy": round(statistics.mean(tag_accuracies), 1),
                                "count": len(tag_accuracies)
                            })
                    
                    if len(history) >= MIN_SAMPLE_SIZE:
                        avg_accuracy = statistics.mean([h["accuracy"] for h in history]) if history else baseline_accuracy
                        deviation = avg_accuracy - baseline_accuracy
                        extremeness = abs(deviation)
                        
                        habits.append({
                            "name": f"tag_{tag_name.lower().replace(' ', '_')}",
                            "display_name": tag_name.replace("_", " ").title(),
                            "category": "tags",
                            "habit_type": "tag",
                            "accuracy": round(avg_accuracy, 1),
                            "baseline": round(baseline_accuracy, 1),
                            "deviation": round(deviation, 1),
                            "deviation_percent": round((deviation / baseline_accuracy * 100) if baseline_accuracy > 0 else 0, 1),
                            "sample_size": len(history),
                            "total_occurrences": sum(h["count"] for h in history),
                            "variance": round(statistics.stdev([h["accuracy"] for h in history]) if len(history) > 1 else 0, 1),
                            "significance": round(min(1.0, extremeness / 25.0), 2),
                            "trend": "stable",
                            "trend_value": 0,
                            "sparkline": [h["accuracy"] for h in history[-10:]],
                            "history": history[-15:],
                            "extremeness": extremeness,
                            "win_rate": win_rate,
                            "avg_cp_loss": avg_cp_loss
                        })
                
                # Process worst tags (weaknesses) - similar logic but for weaknesses
                for tag_data in worst_tags[:5]:  # Top 5 worst
                    tag_name = tag_data.get("name", "")
                    if not tag_name:
                        continue
                    
                    win_rate = tag_data.get("win_rate", 0) / 100.0 if tag_data.get("win_rate") else None
                    avg_cp_loss = tag_data.get("avg_cp_loss", 0)
                    
                    # Build history (same as above)
                    history = []
                    for game in games:
                        game_id = game.get("id", "")
                        game_date = game.get("game_date") or game.get("created_at", "")
                        if isinstance(game_date, str) and len(game_date) > 10:
                            game_date = game_date[:10]
                        
                        game_review = game.get("game_review", {})
                        ply_records = game_review.get("ply_records", [])
                        player_color = game_review.get("metadata", {}).get("player_color", "white")
                        
                        tag_accuracies = []
                        for record in ply_records:
                            if record.get("side_moved") == player_color:
                                tags = record.get("analyse", {}).get("tags", [])
                                for tag in tags:
                                    tag_str = tag if isinstance(tag, str) else tag.get("name", tag.get("tag", ""))
                                    if tag_str and tag_str.lower() == tag_name.lower():
                                        tag_accuracies.append(record.get("accuracy_pct", 0))
                        
                        if tag_accuracies:
                            history.append({
                                "game_id": game_id,
                                "game_date": game_date,
                                "accuracy": round(statistics.mean(tag_accuracies), 1),
                                "count": len(tag_accuracies)
                            })
                    
                    if len(history) >= MIN_SAMPLE_SIZE:
                        avg_accuracy = statistics.mean([h["accuracy"] for h in history]) if history else baseline_accuracy
                        deviation = avg_accuracy - baseline_accuracy
                        extremeness = abs(deviation)
                        
                        habits.append({
                            "name": f"tag_{tag_name.lower().replace(' ', '_')}",
                            "display_name": tag_name.replace("_", " ").title(),
                            "category": "tags",
                            "habit_type": "tag",
                            "accuracy": round(avg_accuracy, 1),
                            "baseline": round(baseline_accuracy, 1),
                            "deviation": round(deviation, 1),
                            "deviation_percent": round((deviation / baseline_accuracy * 100) if baseline_accuracy > 0 else 0, 1),
                            "sample_size": len(history),
                            "total_occurrences": sum(h["count"] for h in history),
                            "variance": round(statistics.stdev([h["accuracy"] for h in history]) if len(history) > 1 else 0, 1),
                            "significance": round(min(1.0, extremeness / 25.0), 2),
                            "trend": "stable",
                            "trend_value": 0,
                            "sparkline": [h["accuracy"] for h in history[-10:]],
                            "history": history[-15:],
                            "extremeness": extremeness,
                            "win_rate": win_rate,
                            "avg_cp_loss": avg_cp_loss
                        })
        except Exception as e:
            print(f"   ⚠️ Error computing tag accuracy habits: {e}")
        
        return habits
    
    def _compute_tag_preference_habits(self, user_id: str, games: List[Dict], baseline_accuracy: float) -> List[Dict]:
        """Compute habits from tag_preferences in personal_stats."""
        habits = []
        
        try:
            stats_row = self.supabase.get_personal_stats(user_id)
            if stats_row:
                stats = stats_row.get("stats", {})
                tag_preferences = stats.get("tag_preferences", {})
                
                for tag_name, pref_data in tag_preferences.items():
                    if not tag_name:
                        continue
                    
                    preference_signal = pref_data.get("preference_signal", "neutral")
                    preference_strength = pref_data.get("preference_strength", 0)
                    created_count = pref_data.get("created_count", 0)
                    removed_count = pref_data.get("removed_count", 0)
                    created_accuracy = pref_data.get("created_accuracy")
                    removed_accuracy = pref_data.get("removed_accuracy")
                    
                    # Only create habit if there's significant preference
                    if abs(preference_strength) < 0.3:  # Threshold for significance
                        continue
                    
                    # Build history from games
                    history = []
                    for game in games:
                        game_id = game.get("id", "")
                        game_date = game.get("game_date") or game.get("created_at", "")
                        if isinstance(game_date, str) and len(game_date) > 10:
                            game_date = game_date[:10]
                        
                        game_review = game.get("game_review", {})
                        ply_records = game_review.get("ply_records", [])
                        player_color = game_review.get("metadata", {}).get("player_color", "white")
                        
                        tag_occurrences = 0
                        tag_accuracies = []
                        for record in ply_records:
                            if record.get("side_moved") == player_color:
                                tags = record.get("analyse", {}).get("tags", [])
                                for tag in tags:
                                    tag_str = tag if isinstance(tag, str) else tag.get("name", tag.get("tag", ""))
                                    if tag_str and tag_str.lower() == tag_name.lower():
                                        tag_occurrences += 1
                                        tag_accuracies.append(record.get("accuracy_pct", 0))
                        
                        if tag_occurrences > 0:
                            history.append({
                                "game_id": game_id,
                                "game_date": game_date,
                                "accuracy": round(statistics.mean(tag_accuracies), 1) if tag_accuracies else baseline_accuracy,
                                "count": tag_occurrences
                            })
                    
                    if len(history) >= MIN_SAMPLE_SIZE:
                        avg_accuracy = statistics.mean([h["accuracy"] for h in history]) if history else baseline_accuracy
                        deviation = avg_accuracy - baseline_accuracy
                        extremeness = abs(preference_strength)  # Use preference strength as extremeness
                        
                        habits.append({
                            "name": f"tag_pref_{tag_name.lower().replace(' ', '_')}",
                            "display_name": f"{tag_name.replace('_', ' ').title()} Preference",
                            "category": "tag_preferences",
                            "habit_type": "tag_pref",
                            "accuracy": round(avg_accuracy, 1),
                            "baseline": round(baseline_accuracy, 1),
                            "deviation": round(deviation, 1),
                            "deviation_percent": round((deviation / baseline_accuracy * 100) if baseline_accuracy > 0 else 0, 1),
                            "sample_size": len(history),
                            "total_occurrences": sum(h["count"] for h in history),
                            "variance": round(statistics.stdev([h["accuracy"] for h in history]) if len(history) > 1 else 0, 1),
                            "significance": round(min(1.0, extremeness), 2),
                            "trend": "stable",
                            "trend_value": 0,
                            "sparkline": [h["accuracy"] for h in history[-10:]],
                            "history": history[-15:],
                            "extremeness": extremeness,
                            "preference_signal": preference_signal,
                            "preference_strength": round(preference_strength, 2),
                            "created_accuracy": created_accuracy,
                            "removed_accuracy": removed_accuracy
                        })
        except Exception as e:
            print(f"   ⚠️ Error computing tag preference habits: {e}")
        
        return habits
    
    def _compute_time_bucket_habits(self, user_id: str, games: List[Dict], baseline_accuracy: float) -> List[Dict]:
        """Compute habits from time_buckets data."""
        habits = []
        
        try:
            if self.profile_indexer:
                profile_stats = self.profile_indexer.get_stats(user_id)
                advanced = profile_stats.get("advanced", {})
                time_buckets = advanced.get("time_buckets", [])
                
                for bucket_data in time_buckets:
                    bucket_name = bucket_data.get("bucket", "")
                    if not bucket_name:
                        continue
                    
                    avg_cp_loss = bucket_data.get("avg_cp_loss", 0)
                    error_rate = bucket_data.get("error_rate", 0)
                    moves = bucket_data.get("moves", 0)
                    
                    if moves < 10:  # Need minimum moves
                        continue
                    
                    # Build history from games
                    history = []
                    for game in games:
                        game_id = game.get("id", "")
                        game_date = game.get("game_date") or game.get("created_at", "")
                        if isinstance(game_date, str) and len(game_date) > 10:
                            game_date = game_date[:10]
                        
                        game_review = game.get("game_review", {})
                        ply_records = game_review.get("ply_records", [])
                        player_color = game_review.get("metadata", {}).get("player_color", "white")
                        
                        bucket_accuracies = []
                        for record in ply_records:
                            if record.get("side_moved") == player_color:
                                time_spent = record.get("time_spent_s", 0)
                                if time_spent and self._matches_time_bucket(time_spent, bucket_name):
                                    bucket_accuracies.append(record.get("accuracy_pct", 0))
                        
                        if bucket_accuracies:
                            history.append({
                                "game_id": game_id,
                                "game_date": game_date,
                                "accuracy": round(statistics.mean(bucket_accuracies), 1),
                                "count": len(bucket_accuracies)
                            })
                    
                    if len(history) >= MIN_SAMPLE_SIZE:
                        avg_accuracy = statistics.mean([h["accuracy"] for h in history]) if history else baseline_accuracy
                        deviation = avg_accuracy - baseline_accuracy
                        # Use error_rate as extremeness indicator (higher error = more extreme)
                        extremeness = abs(error_rate) if error_rate else abs(deviation)
                        
                        habits.append({
                            "name": f"time_{bucket_name.lower().replace(' ', '_')}",
                            "display_name": f"Time: {bucket_name.replace('_', ' ').title()}",
                            "category": "time_pressure",
                            "habit_type": "time",
                            "accuracy": round(avg_accuracy, 1),
                            "baseline": round(baseline_accuracy, 1),
                            "deviation": round(deviation, 1),
                            "deviation_percent": round((deviation / baseline_accuracy * 100) if baseline_accuracy > 0 else 0, 1),
                            "sample_size": len(history),
                            "total_occurrences": sum(h["count"] for h in history),
                            "variance": round(statistics.stdev([h["accuracy"] for h in history]) if len(history) > 1 else 0, 1),
                            "significance": round(min(1.0, extremeness / 50.0), 2),  # Normalize error_rate
                            "trend": "stable",
                            "trend_value": 0,
                            "sparkline": [h["accuracy"] for h in history[-10:]],
                            "history": history[-15:],
                            "extremeness": extremeness,
                            "avg_cp_loss": round(avg_cp_loss, 1),
                            "error_rate": round(error_rate, 1)
                        })
        except Exception as e:
            print(f"   ⚠️ Error computing time bucket habits: {e}")
        
        return habits
    
    def _matches_time_bucket(self, time_spent: float, bucket_name: str) -> bool:
        """Check if time_spent matches the time bucket."""
        # Map bucket names to time ranges
        bucket_ranges = {
            "very_fast": (0, 5),
            "fast": (5, 15),
            "normal": (15, 30),
            "slow": (30, 60),
            "very_slow": (60, float('inf'))
        }
        
        bucket_name_lower = bucket_name.lower().replace(" ", "_")
        if bucket_name_lower in bucket_ranges:
            min_time, max_time = bucket_ranges[bucket_name_lower]
            return min_time <= time_spent < max_time
        
        return False
    
    def compute_habits(self, user_id: str) -> Dict:
        """
        Compute habits with per-game history, significance, and trends.
        Returns a dictionary of habits ready for visualization.
        """
        # Get all games with full review data (reduced limit for speed)
        games = self.supabase.get_active_reviewed_games(user_id, limit=20)
        
        # Debug logging
        print(f"   🔍 [HABITS] Found {len(games)} games from get_active_reviewed_games")
        if not games:
            print(f"   ⚠️ [HABITS] No games found - checking database...")
            # Try to get any games to see what's in the database
            try:
                all_games = self.supabase.client.table("games")\
                    .select("id, review_type, analyzed_at, archived_at, game_review")\
                    .eq("user_id", user_id)\
                    .limit(10)\
                    .execute()
                if all_games.data:
                    print(f"   🔍 [HABITS] Sample games in DB:")
                    for g in all_games.data[:5]:
                        has_review = bool(g.get("game_review"))
                        review_type = g.get("review_type", "NULL")
                        analyzed = bool(g.get("analyzed_at"))
                        archived = bool(g.get("archived_at"))
                        print(f"      - ID: {g.get('id')[:8]}..., review_type: {review_type}, analyzed: {analyzed}, archived: {archived}, has_game_review: {has_review}")
                else:
                    print(f"   ⚠️ [HABITS] No games found in database at all")
            except Exception as e:
                print(f"   ⚠️ [HABITS] Error checking games: {e}")
            
            return {"habits": [], "baseline_accuracy": 0, "total_games": 0}
        
        # Check if games have required structure (game_review with ply_records that have tags)
        games_with_review = 0
        games_with_ply_records = 0
        games_with_tags = 0
        
        # Store original games list for reference
        original_games = games
        
        # Filter games to only include those with tags
        games_with_tags_list = []
        
        for game in original_games:
            game_review = game.get("game_review")
            if game_review:
                games_with_review += 1
                ply_records = game_review.get("ply_records", [])
                if ply_records:
                    games_with_ply_records += 1
                    # Check if this game has any tags in its ply_records
                    has_tags = False
                    tag_count = 0
                    for record in ply_records:
                        tags = record.get("analyse", {}).get("tags", [])
                        if tags:
                            has_tags = True
                            tag_count += len(tags)
                    
                    if has_tags:
                        games_with_tags += 1
                        games_with_tags_list.append(game)
                        print(f"   🔍 [HABITS] Game {game.get('id', 'unknown')[:8]}... has {tag_count} tags across {len(ply_records)} moves")
        
        print(f"   🔍 [HABITS] {games_with_review}/{len(original_games)} games have game_review")
        print(f"   🔍 [HABITS] {games_with_ply_records}/{len(original_games)} games have ply_records")
        print(f"   🔍 [HABITS] {games_with_tags}/{len(original_games)} games have TAGS in ply_records (will use these for habits)")
        
        # Only use games with tags for habit computation
        games = games_with_tags_list
        
        if games_with_tags == 0:
            print(f"   ⚠️ [HABITS] No games have tags in ply_records - habits cannot be computed")
            print(f"   💡 [HABITS] Games may need to be re-analyzed to include tags")
            # Return total games with ply_records checked (even though none have tags)
            return {"habits": [], "baseline_accuracy": 0, "total_games": games_with_ply_records}
        
        # Calculate overall baseline accuracy
        all_accuracies = []
        for game in games:
            game_review = game.get("game_review", {})
            stats = game_review.get("stats", {})
            if stats.get("overall_accuracy"):
                all_accuracies.append(stats.get("overall_accuracy", 0))
        
        baseline_accuracy = statistics.mean(all_accuracies) if all_accuracies else 75.0
        
        # Calculate phase baseline accuracies from game stats
        phase_baselines = {"opening": 75.0, "middlegame": 75.0, "endgame": 75.0}
        phase_accuracies_all = {"opening": [], "middlegame": [], "endgame": []}
        for game in games:
            game_review = game.get("game_review", {})
            stats = game_review.get("stats", {})
            by_phase = stats.get("by_phase", {})
            for phase in ["opening", "middlegame", "endgame"]:
                phase_stat = by_phase.get(phase, {})
                if phase_stat.get("accuracy") is not None:
                    phase_accuracies_all[phase].append(phase_stat["accuracy"])
        
        for phase in ["opening", "middlegame", "endgame"]:
            if phase_accuracies_all[phase]:
                phase_baselines[phase] = statistics.mean(phase_accuracies_all[phase])
        
        # Build per-habit history from each game
        # OPTIMIZATION: Process each game only once (combine tag and phase processing)
        habit_histories = defaultdict(list)  # habit_name -> [{game_date, accuracy, count, game_id}]
        game_phase_accuracies = {}  # game_id -> {opening: acc, middlegame: acc, endgame: acc}
        
        for game in games:
            game_id = game.get("id", "")
            game_date = game.get("game_date") or game.get("created_at", "")
            if isinstance(game_date, str) and len(game_date) > 10:
                game_date = game_date[:10]  # Just YYYY-MM-DD
            
            game_review = game.get("game_review", {})
            ply_records = game_review.get("ply_records", [])
            player_color = game_review.get("metadata", {}).get("player_color", "white")
            
            # Extract phase accuracies from game stats for this game
            stats = game_review.get("stats", {})
            by_phase = stats.get("by_phase", {})
            game_phase_accuracies[game_id] = {
                "opening": by_phase.get("opening", {}).get("accuracy"),
                "middlegame": by_phase.get("middlegame", {}).get("accuracy"),
                "endgame": by_phase.get("endgame", {}).get("accuracy")
            }
            
            # OPTIMIZATION: Sample ply_records if too many (limit to 100 moves per game for speed)
            if len(ply_records) > 100:
                # Sample evenly across the game
                step = len(ply_records) // 100
                ply_records = ply_records[::step][:100]
            
            # Collect accuracy per tag AND phase in single pass
            tag_game_data = defaultdict(lambda: {"accuracies": [], "count": 0})
            phase_data = defaultdict(lambda: {"accuracies": [], "count": 0})
            
            for record in ply_records:
                if record.get("side_moved") != player_color:
                    continue
                
                accuracy = record.get("accuracy_pct", 0)
                
                # Process tags
                tags = record.get("analyse", {}).get("tags", [])
                for tag in tags:
                    # Handle different tag formats: string, dict with tag_name, name, or tag key
                    if isinstance(tag, str):
                        tag_name = tag
                    elif isinstance(tag, dict):
                        tag_name = tag.get("tag_name", tag.get("name", tag.get("tag", "")))
                    else:
                        continue
                    if tag_name:
                        # Normalize tag name
                        tag_name = tag_name.lower().replace(" ", "_").replace("-", "_")
                        tag_game_data[tag_name]["accuracies"].append(accuracy)
                        tag_game_data[tag_name]["count"] += 1
                
                # Process phase
                phase = record.get("phase", "middlegame")
                phase_data[f"phase_{phase}"]["accuracies"].append(accuracy)
                phase_data[f"phase_{phase}"]["count"] += 1
            
            # Add tag game data to habit histories
            for tag_name, data in tag_game_data.items():
                if data["count"] >= 1:  # At least 1 occurrence in this game
                    avg_acc = statistics.mean(data["accuracies"])
                    habit_histories[tag_name].append({
                        "game_id": game_id,
                        "game_date": game_date,
                        "accuracy": round(avg_acc, 1),
                        "count": data["count"]
                    })
            
            # Add phase data to habit histories
            for phase_name, data in phase_data.items():
                if data["count"] >= 3:  # Need at least 3 moves in phase
                    avg_acc = statistics.mean(data["accuracies"])
                    habit_histories[phase_name].append({
                        "game_id": game_id,
                        "game_date": game_date,
                        "accuracy": round(avg_acc, 1),
                        "count": data["count"]
                    })
        
        # Calculate significance and trend for each habit (existing tag/phase habits)
        habits = []
        phase_habits = []  # Always include phase habits
        skipped_too_few = 0
        skipped_not_significant = 0
        
        for habit_name, history in habit_histories.items():
            is_phase_habit = habit_name.startswith("phase_")
            
            if len(history) < MIN_SAMPLE_SIZE:
                # For phase habits, use lower threshold (at least 3 games)
                if is_phase_habit and len(history) >= 3:
                    # Still include phase habits even with fewer samples
                    pass
                else:
                    skipped_too_few += 1
                    continue  # Not enough data
            
            habit_data = self._calculate_habit_metrics(
                habit_name, 
                history, 
                baseline_accuracy,
                game_phase_accuracies  # Pass phase accuracies for all habits
            )
            
            if habit_data:
                # Add extremeness for sorting
                habit_data["extremeness"] = abs(habit_data.get("deviation", 0))
                
                # Always include phase habits, even if not significant
                if is_phase_habit:
                    phase_habits.append(habit_data)
                else:
                    habits.append(habit_data)
            else:
                # For phase habits, include even if not significant (just mark as low significance)
                if is_phase_habit:
                    # Create a minimal habit entry for phase
                    habit_accuracy = statistics.mean([h["accuracy"] for h in history])
                    # Calculate phase accuracies for this phase habit
                    phase_accuracies = {"opening": None, "middlegame": None, "endgame": None}
                    phase_counts = {"opening": 0, "middlegame": 0, "endgame": 0}
                    phase_acc_list = {"opening": [], "middlegame": [], "endgame": []}
                    for entry in history:
                        game_id = entry.get("game_id", "")
                        if game_id in game_phase_accuracies:
                            game_phases = game_phase_accuracies[game_id]
                            for phase in ["opening", "middlegame", "endgame"]:
                                if game_phases[phase] is not None:
                                    phase_acc_list[phase].append(game_phases[phase])
                                    phase_counts[phase] += 1
                    for phase in ["opening", "middlegame", "endgame"]:
                        if phase_acc_list[phase]:
                            phase_accuracies[phase] = round(statistics.mean(phase_acc_list[phase]), 1)
                    
                    habit_data = {
                        "name": habit_name,
                        "display_name": self._get_habit_display_name(habit_name),
                        "category": "phases",
                        "habit_type": "phase",
                        "accuracy": round(habit_accuracy, 1),
                        "baseline": round(baseline_accuracy, 1),
                        "deviation": round(habit_accuracy - baseline_accuracy, 1),
                        "deviation_percent": round(((habit_accuracy - baseline_accuracy) / baseline_accuracy * 100) if baseline_accuracy > 0 else 0, 1),
                        "sample_size": len(history),
                        "total_occurrences": sum(h["count"] for h in history),
                        "variance": round(statistics.stdev([h["accuracy"] for h in history]) if len(history) > 1 else 0, 1),
                        "significance": 0.1,  # Low significance but still included
                        "trend": "stable",
                        "trend_value": 0,
                        "sparkline": [h["accuracy"] for h in history[-10:]],
                        "history": history[-15:],
                        "extremeness": abs(habit_accuracy - baseline_accuracy),
                        "phase_accuracies": phase_accuracies,  # Always include phase accuracies
                        "phase_counts": phase_counts
                    }
                    phase_habits.append(habit_data)
                else:
                    skipped_not_significant += 1
        
        print(f"   🔍 [HABITS] Tag habits: {len(habits)} found, Phase habits: {len(phase_habits)} (always included), {skipped_too_few} skipped (too few), {skipped_not_significant} skipped (not significant)")
        
        # Always include phase habits first, then tag habits
        # Sort phase habits by extremeness
        phase_habits.sort(key=lambda h: h.get("extremeness", 0), reverse=True)
        
        # Sort tag habits by extremeness
        habits.sort(key=lambda h: h.get("extremeness", 0), reverse=True)
        
        # Combine: phase habits first (always included), then tag habits
        all_tag_phase_habits = phase_habits + habits
        top_tag_habits = all_tag_phase_habits[:MAX_HABITS_DISPLAY]
        
        # Only compute other habit types if we don't have enough from tag/phase habits
        if len(top_tag_habits) < MAX_HABITS_DISPLAY:
            print(f"   🔍 [HABITS] Only {len(top_tag_habits)} tag/phase habits, computing other types...")
            # Compute new habit types
            endgame_habits = self._compute_endgame_habits(user_id, games, baseline_accuracy)
            tag_accuracy_habits = self._compute_tag_accuracy_habits(user_id, games, baseline_accuracy)
            tag_pref_habits = self._compute_tag_preference_habits(user_id, games, baseline_accuracy)
            time_bucket_habits = self._compute_time_bucket_habits(user_id, games, baseline_accuracy)
            
            # Merge all habits (phase habits first, then others)
            all_habits = phase_habits + habits + endgame_habits + tag_accuracy_habits + tag_pref_habits + time_bucket_habits
        else:
            print(f"   ✅ [HABITS] Have {len(top_tag_habits)} tag/phase habits, skipping other types for speed")
            # Skip expensive computations - we have enough
            endgame_habits = []
            tag_accuracy_habits = []
            tag_pref_habits = []
            time_bucket_habits = []
            # Still include phase habits even when skipping other types
            all_habits = phase_habits + habits
        
        print(f"   🔍 [HABITS] Total habits after merge: {len(all_habits)} "
              f"(phase: {len(phase_habits)}, tag: {len(habits)}, endgame: {len(endgame_habits)}, "
              f"tag_accuracy: {len(tag_accuracy_habits)}, tag_pref: {len(tag_pref_habits)}, "
              f"time_bucket: {len(time_bucket_habits)})")
        
        # Sort by extremeness (most extreme first) instead of just significance
        all_habits.sort(key=lambda h: h.get("extremeness", 0), reverse=True)
        
        # Save historical snapshots (non-blocking - fire and forget)
        try:
            import threading
            thread = threading.Thread(
                target=self._save_habit_snapshots,
                args=(user_id, all_habits, games, baseline_accuracy),
                daemon=True
            )
            thread.start()
            print(f"   🔄 [HABITS] Saving snapshots in background...")
        except Exception as e:
            print(f"   ⚠️ [HABITS] Error starting snapshot save thread: {e}")
        
        # Take top habits (but now sorted by extremeness)
        top_habits = all_habits[:MAX_HABITS_DISPLAY * 2]  # Show more since we have more types
        
        print(f"   ✅ [HABITS] Returning {len(top_habits)} top habits (from {len(all_habits)} total)")
        
        return {
            "habits": top_habits,
            "baseline_accuracy": round(baseline_accuracy, 1),
            "total_games": len(games),
            "all_habits": all_habits  # Include all for filtering
        }
    
    def _calculate_habit_metrics(self, habit_name: str, history: List[Dict], baseline: float, game_phase_accuracies: Dict = None) -> Optional[Dict]:
        """
        Calculate metrics for a single habit.
        Returns None if not significant enough.
        
        Args:
            habit_name: Name of the habit
            history: List of game history entries
            baseline: Baseline accuracy
            game_phase_accuracies: Dict mapping game_id to phase accuracies (optional)
        """
        if game_phase_accuracies is None:
            game_phase_accuracies = {}
        if not history:
            return None
        
        # Sort history by date (oldest first)
        history = sorted(history, key=lambda x: x.get("game_date", ""))
        
        # Calculate weighted average (more recent games count more)
        total_weight = 0
        weighted_sum = 0
        all_accuracies = []
        total_count = 0
        
        for i, entry in enumerate(history):
            weight = 1 + (i / len(history))  # More recent = higher weight
            weighted_sum += entry["accuracy"] * weight
            total_weight += weight
            all_accuracies.append(entry["accuracy"])
            total_count += entry["count"]
        
        habit_accuracy = weighted_sum / total_weight if total_weight > 0 else 0
        
        # Calculate deviation from baseline
        deviation = habit_accuracy - baseline
        deviation_percent = (deviation / baseline * 100) if baseline > 0 else 0
        
        # Calculate variance (consistency)
        variance = statistics.stdev(all_accuracies) if len(all_accuracies) > 1 else 0
        
        # Calculate significance score (0-1)
        # Higher = more significant
        sample_factor = min(1.0, len(history) / 15)  # Max at 15 games
        consistency_factor = max(0, 1 - (variance / 30))  # Lower variance = higher
        deviation_factor = min(1.0, abs(deviation_percent) / 25)  # Max at 25% deviation
        
        significance = (sample_factor * 0.3 + consistency_factor * 0.3 + deviation_factor * 0.4)
        
        # Skip if not significant enough
        # BUT: Lower the threshold if we have enough games to be more permissive
        min_significance = 0.2 if len(history) >= 10 else 0.3
        min_deviation = 3.0 if len(history) >= 10 else MIN_DEVIATION_PERCENT
        
        if significance < min_significance and abs(deviation_percent) < min_deviation:
            return None
        
        # Determine trend (last 5 games vs first 5 games)
        trend = "stable"
        trend_value = 0
        if len(history) >= 5:
            first_half = history[:len(history)//2]
            second_half = history[len(history)//2:]
            
            first_avg = statistics.mean([e["accuracy"] for e in first_half])
            second_avg = statistics.mean([e["accuracy"] for e in second_half])
            
            trend_value = second_avg - first_avg
            if trend_value > 3:
                trend = "improving"
            elif trend_value < -3:
                trend = "declining"
        
        # Get display name
        display_name = self._get_habit_display_name(habit_name)
        category = self._get_habit_category(habit_name)
        
        # Determine habit_type
        if habit_name.startswith("phase_"):
            habit_type = "phase"
        else:
            habit_type = "tag"  # Default for tag-based habits
        
        # Build sparkline data (last 10 games)
        sparkline = [entry["accuracy"] for entry in history[-10:]]
        
        # Calculate phase accuracies for this habit from games
        phase_accuracies = {"opening": None, "middlegame": None, "endgame": None}
        phase_counts = {"opening": 0, "middlegame": 0, "endgame": 0}
        phase_acc_list = {"opening": [], "middlegame": [], "endgame": []}
        
        # Get phase accuracies from games that contributed to this habit
        for entry in history:
            game_id = entry.get("game_id", "")
            if game_id in game_phase_accuracies:
                game_phases = game_phase_accuracies[game_id]
                for phase in ["opening", "middlegame", "endgame"]:
                    if game_phases[phase] is not None:
                        phase_acc_list[phase].append(game_phases[phase])
                        phase_counts[phase] += 1
        
        # Calculate averages
        for phase in ["opening", "middlegame", "endgame"]:
            if phase_acc_list[phase]:
                phase_accuracies[phase] = round(statistics.mean(phase_acc_list[phase]), 1)
        
        return {
            "name": habit_name,
            "display_name": display_name,
            "category": category,
            "habit_type": habit_type,
            "accuracy": round(habit_accuracy, 1),
            "baseline": round(baseline, 1),
            "deviation": round(deviation, 1),
            "deviation_percent": round(deviation_percent, 1),
            "sample_size": len(history),
            "total_occurrences": total_count,
            "variance": round(variance, 1),
            "significance": round(significance, 2),
            "trend": trend,
            "trend_value": round(trend_value, 1),
            "sparkline": sparkline,
            "history": history[-15:],  # Last 15 games for detailed chart
            "extremeness": abs(deviation),  # Add extremeness for sorting
            "phase_accuracies": phase_accuracies,  # Always include phase accuracies
            "phase_counts": phase_counts  # Include counts for context
        }
    
    def _get_habit_display_name(self, habit_name: str) -> str:
        """Convert internal habit name to human-readable display name."""
        return format_tag_display_name(habit_name)
    
    def _get_habit_category(self, habit_name: str) -> str:
        """Get category for a habit using the tag group system."""
        return get_tag_group(habit_name)
    
    def _save_habit_snapshots(self, user_id: str, habits: List[Dict], games: List[Dict], baseline_accuracy: float):
        """Save per-game habit snapshots to habit_trends table for trend persistence.
        
        OPTIMIZED: Only saves snapshots for top habits (not all 244) to reduce write load.
        """
        try:
            # Only save snapshots for top habits (most extreme) to reduce database writes
            # Sort by extremeness and take top 20 habits
            sorted_habits = sorted(habits, key=lambda h: h.get("extremeness", 0), reverse=True)
            top_habits = sorted_habits[:20]  # Only save top 20 habits
            
            snapshots = []
            game_map = {g.get("id"): g for g in games}
            
            for habit in top_habits:
                habit_key = habit.get("name", "")
                habit_type = habit.get("habit_type", "tag")
                history = habit.get("history", [])
                
                # Limit history entries per habit (last 10 games)
                recent_history = history[-10:] if len(history) > 10 else history
                
                for entry in recent_history:
                    game_id = entry.get("game_id", "")
                    game_date = entry.get("game_date", "")
                    game = game_map.get(game_id, {})
                    
                    snapshot = {
                        "habit_key": habit_key,
                        "habit_type": habit_type,
                        "game_id": game_id,
                        "game_date": game_date,
                        "accuracy": entry.get("accuracy"),
                        "count": entry.get("count", 0),
                        "baseline_accuracy": baseline_accuracy,
                    }
                    
                    # Add optional metrics based on habit type
                    if habit.get("win_rate") is not None:
                        snapshot["win_rate"] = habit.get("win_rate")
                    if habit.get("avg_cp_loss") is not None:
                        snapshot["avg_cp_loss"] = habit.get("avg_cp_loss")
                    if habit.get("error_rate") is not None:
                        snapshot["error_rate"] = habit.get("error_rate")
                    if habit.get("preference_signal"):
                        snapshot["preference_signal"] = habit.get("preference_signal")
                    if habit.get("preference_strength") is not None:
                        snapshot["preference_strength"] = habit.get("preference_strength")
                    
                    snapshots.append(snapshot)
            
            if snapshots:
                # Save in smaller batches to avoid timeout
                batch_size = 100
                for i in range(0, len(snapshots), batch_size):
                    batch = snapshots[i:i + batch_size]
                    try:
                        self.supabase.save_habit_trend_snapshots(user_id, batch)
                    except Exception as batch_error:
                        # Log but continue with next batch
                        print(f"   ⚠️ Error saving habit snapshot batch {i//batch_size + 1} (non-fatal): {batch_error}")
                        continue
        
        except Exception as e:
            # Gracefully handle if habit_trends table doesn't exist yet (migration not run)
            error_msg = str(e)
            if "habit_trends" in error_msg.lower() or "PGRST205" in error_msg:
                # Table doesn't exist yet - this is OK, just log and continue
                pass  # Don't spam logs for missing table
            else:
                print(f"   ⚠️ Error saving habit snapshots: {e}")
    
    def _load_historical_trends(self, user_id: str, habit_key: str, habit_type: str) -> List[Dict]:
        """Load historical trend data for a habit from habit_trends table."""
        try:
            trends = self.supabase.get_habit_trends(user_id, habit_key, habit_type, limit=50)
            return trends
        except Exception as e:
            print(f"   ⚠️ Error loading historical trends: {e}")
            return []
    
    def get_habits_for_frontend(self, user_id: str) -> Dict:
        """
        Get habits data formatted for frontend visualization.
        Fetches from computed_habits table first, only computes if missing or needs recomputation.
        """
        # Step 1: Try to fetch from computed_habits table (source of truth)
        computed_habits = self.supabase.get_computed_habits(user_id)
        
        if computed_habits:
            habits_data = computed_habits.get("habits_data", {})
            needs_computation = computed_habits.get("needs_computation", False)
            saved_total_games = computed_habits.get("total_games_with_tags", 0)
            
            # Check if we need to recompute
            if not needs_computation:
                # Check if games with tags changed
                current_games = self.supabase.get_active_reviewed_games(user_id, limit=20)
                current_games_with_tags = 0
                for game in current_games:
                    game_review = game.get("game_review", {})
                    ply_records = game_review.get("ply_records", [])
                    if ply_records:
                        has_tags = any(
                            len(record.get("analyse", {}).get("tags", [])) > 0
                            for record in ply_records
                        )
                        if has_tags:
                            current_games_with_tags += 1
                
                if current_games_with_tags == saved_total_games and habits_data.get("habits"):
                    # Games haven't changed and we have valid habits - return saved
                    print(f"   ✅ [HABITS] Fetching from computed_habits: {len(habits_data.get('habits', []))} habits, {saved_total_games} games")
                    return habits_data
                else:
                    print(f"   🔄 [HABITS] Games changed ({saved_total_games} → {current_games_with_tags}) or needs computation, recomputing...")
            else:
                print(f"   🔄 [HABITS] Marked for recomputation, computing...")
        else:
            print(f"   🔄 [HABITS] No computed_habits found, computing...")
        
        # Step 2: Compute fresh (only if needed)
        print(f"   🔄 [HABITS] Computing fresh habits data...")
        habits_data = self.compute_habits(user_id)
        
        # Add additional computed fields for frontend
        habits = habits_data.get("habits", [])
        baseline = habits_data.get("baseline_accuracy", 75)
        
        # Ensure all habits have extremeness calculated
        for habit in habits:
            if "extremeness" not in habit:
                habit["extremeness"] = abs(habit.get("deviation", 0))
        
        # Sort all habits by extremeness (most extreme first)
        habits.sort(key=lambda h: h.get("extremeness", 0), reverse=True)
        
        # Separate by type: strengths vs weaknesses (but keep extremeness order within groups)
        strengths = [h for h in habits if h.get("deviation", 0) > 0]
        weaknesses = [h for h in habits if h.get("deviation", 0) < 0]
        
        # Both already sorted by extremeness from above, but ensure they're in extremeness order
        strengths.sort(key=lambda h: h.get("extremeness", 0), reverse=True)
        weaknesses.sort(key=lambda h: h.get("extremeness", 0), reverse=True)
        
        # Prepare trend chart data (combine most extreme habits)
        trend_data = []
        # Take top 5 most extreme habits for trend chart
        extreme_habits = sorted(habits, key=lambda h: h.get("extremeness", 0), reverse=True)[:5]
        
        # Collect all unique dates
        all_dates = set()
        for habit in extreme_habits:
            for entry in habit.get("history", []):
                all_dates.add(entry.get("game_date", ""))
        
        sorted_dates = sorted(all_dates)
        
        # Build chart series
        for habit in extreme_habits:
            history_map = {e["game_date"]: e for e in habit.get("history", [])}
            series = []
            for date in sorted_dates:
                if date in history_map:
                    series.append({
                        "date": date,
                        "accuracy": history_map[date]["accuracy"],
                        "count": history_map[date]["count"],
                        "significant": history_map[date]["count"] >= 3
                    })
                else:
                    series.append(None)  # Gap in data
            
            trend_data.append({
                "name": habit["display_name"],
                "habit_key": habit["name"],
                "color": self._get_habit_color(habit),
                "series": series
            })
        
        # total_games should reflect only games with tags (not all games)
        # Get from habits_data which was computed by compute_habits
        total_games_with_tags = habits_data.get("total_games", 0)
        
        response = {
            "habits": habits,
            "strengths": strengths[:8],  # Show more since we have more types
            "weaknesses": weaknesses[:8],
            "baseline_accuracy": baseline,
            "total_games": total_games_with_tags,  # Only count games with tags
            "trend_chart": {
                "dates": sorted_dates,
                "series": trend_data,
                "baseline": baseline
            }
        }
        
        # Debug: Log response structure
        print(f"   ✅ [HABITS] Response: {len(habits)} habits, {len(strengths)} strengths, {len(weaknesses)} weaknesses, {total_games_with_tags} games with tags")
        
        # Save habits to computed_habits table (source of truth)
        # Save in background thread to not block response
        self._save_computed_habits_to_supabase(user_id, response)
        
        # Return response immediately - save happens in background
        # If frontend request is cancelled, data is still saved to Supabase for next fetch
        return response
    
    def _save_computed_habits_to_supabase(self, user_id: str, habits_data: Dict):
        """Save computed habits to computed_habits table (non-blocking).
        
        This is the source of truth. Habits are computed and saved to Supabase
        for fast retrieval on subsequent requests.
        """
        import threading
        def save_async():
            try:
                print(f"   💾 [HABITS] Saving {len(habits_data.get('habits', []))} habits to computed_habits table...")
                success = self.supabase.save_computed_habits(user_id, habits_data)
                if success:
                    print(f"   ✅ [HABITS] Saved computed habits to Supabase")
                else:
                    print(f"   ⚠️ [HABITS] Failed to save computed habits")
            except Exception as e:
                print(f"   ⚠️ [HABITS] Error saving to computed_habits (non-fatal): {e}")
                import traceback
                print(f"   ⚠️ [HABITS] Traceback: {traceback.format_exc()}")
        
        thread = threading.Thread(target=save_async, daemon=True)
        thread.start()
        # Note: Thread is daemon=True so it won't block server shutdown, but will complete
        # as long as server is running. Save happens in background regardless of request status.
    
    def _get_habit_color(self, habit: Dict) -> str:
        """Get color for habit based on deviation."""
        deviation = habit.get("deviation", 0)
        
        if deviation >= 10:
            return "#22c55e"  # Green
        elif deviation >= 5:
            return "#84cc16"  # Light green
        elif deviation <= -10:
            return "#ef4444"  # Red
        elif deviation <= -5:
            return "#f97316"  # Orange
        else:
            return "#6b7280"  # Gray (neutral)
    
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
    
    def _update_tag_transitions(self, stats: Dict, ply_records: List[Dict], player_color: str, game_id: str):
        """Track accuracy and error counts when tags are gained or lost."""
        if "tag_transitions" not in stats:
            stats["tag_transitions"] = {"gained": {}, "lost": {}}
        
        def extract_tag_names(tags):
            """Extract tag names from various formats."""
            tag_names = set()
            for tag in tags:
                if isinstance(tag, str):
                    tag_names.add(tag)
                elif isinstance(tag, dict):
                    tag_name = tag.get("tag_name") or tag.get("name") or tag.get("tag", "")
                    if tag_name:
                        tag_names.add(tag_name)
            return tag_names
        
        # Track transitions between consecutive moves
        for i in range(1, len(ply_records)):
            prev_record = ply_records[i - 1]
            curr_record = ply_records[i]
            
            # Only track player's moves
            if curr_record.get("side_moved") != player_color:
                continue
            
            prev_tags = extract_tag_names(prev_record.get("analyse", {}).get("tags", []))
            curr_tags = extract_tag_names(curr_record.get("analyse", {}).get("tags", []))
            
            gained_tags = curr_tags - prev_tags
            lost_tags = prev_tags - curr_tags
            
            accuracy = curr_record.get("accuracy_pct", 0)
            quality = curr_record.get("quality", "").lower()
            
            # Track gained tags
            for tag_name in gained_tags:
                if tag_name not in stats["tag_transitions"]["gained"]:
                    stats["tag_transitions"]["gained"][tag_name] = {
                        "accuracy": 0,
                        "count": 0,
                        "blunders": 0,
                        "mistakes": 0,
                        "inaccuracies": 0,
                        "game_ids": []
                    }
                
                tag_data = stats["tag_transitions"]["gained"][tag_name]
                old_count = tag_data["count"]
                old_accuracy = tag_data["accuracy"]
                
                tag_data["count"] += 1
                tag_data["accuracy"] = (old_accuracy * old_count + accuracy) / tag_data["count"]
                
                if quality == "blunder":
                    tag_data["blunders"] += 1
                elif quality == "mistake":
                    tag_data["mistakes"] += 1
                elif quality == "inaccuracy":
                    tag_data["inaccuracies"] += 1
                
                if game_id not in tag_data["game_ids"]:
                    tag_data["game_ids"].append(game_id)
            
            # Track lost tags
            for tag_name in lost_tags:
                if tag_name not in stats["tag_transitions"]["lost"]:
                    stats["tag_transitions"]["lost"][tag_name] = {
                        "accuracy": 0,
                        "count": 0,
                        "blunders": 0,
                        "mistakes": 0,
                        "inaccuracies": 0,
                        "game_ids": []
                    }
                
                tag_data = stats["tag_transitions"]["lost"][tag_name]
                old_count = tag_data["count"]
                old_accuracy = tag_data["accuracy"]
                
                tag_data["count"] += 1
                tag_data["accuracy"] = (old_accuracy * old_count + accuracy) / tag_data["count"]
                
                if quality == "blunder":
                    tag_data["blunders"] += 1
                elif quality == "mistake":
                    tag_data["mistakes"] += 1
                elif quality == "inaccuracy":
                    tag_data["inaccuracies"] += 1
                
                if game_id not in tag_data["game_ids"]:
                    tag_data["game_ids"].append(game_id)
    
    def _update_piece_accuracy(self, stats: Dict, ply_records: List[Dict], player_color: str, game_id: str, game_review: Dict = None):
        """Incrementally update accuracy by piece with per-game breakdowns."""
        if "accuracy_by_piece" not in stats:
            stats["accuracy_by_piece"] = {}
        
        if "piece_accuracy_detailed" not in stats:
            stats["piece_accuracy_detailed"] = {"per_game": [], "aggregate": {}}
        
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
        
        # Store per-game breakdown
        game_piece_breakdown = {
            "game_id": game_id,
            "pieces": {}
        }
        for piece_name, data in piece_counts.items():
            if data["accuracies"]:
                game_piece_breakdown["pieces"][piece_name] = {
                    "accuracy": round(statistics.mean(data["accuracies"]), 1),
                    "count": data["count"]
                }
        
        # Add to per_game array (limit to last 100 games to prevent unbounded growth)
        if game_piece_breakdown["pieces"]:
            stats["piece_accuracy_detailed"]["per_game"].append(game_piece_breakdown)
            # Keep only last 100 games
            if len(stats["piece_accuracy_detailed"]["per_game"]) > 100:
                stats["piece_accuracy_detailed"]["per_game"] = stats["piece_accuracy_detailed"]["per_game"][-100:]
        
        # Merge into aggregate stats
        for piece_name, data in piece_counts.items():
            if piece_name not in stats["accuracy_by_piece"]:
                stats["accuracy_by_piece"][piece_name] = {"accuracy": 0, "count": 0, "game_ids": []}
            
            if piece_name not in stats["piece_accuracy_detailed"]["aggregate"]:
                stats["piece_accuracy_detailed"]["aggregate"][piece_name] = {"accuracy": 0, "count": 0}
            
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
                
                # Update aggregate in detailed stats
                stats["piece_accuracy_detailed"]["aggregate"][piece_name]["accuracy"] = stats["accuracy_by_piece"][piece_name]["accuracy"]
                stats["piece_accuracy_detailed"]["aggregate"][piece_name]["count"] = total_count
            
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
        """Incrementally update accuracy by time spent with 7-bucket system and blunder rate tracking."""
        if "accuracy_by_time_spent" not in stats:
            stats["accuracy_by_time_spent"] = {}
        
        # 7-bucket system as specified
        time_ranges = [
            (0, 5, '<5s'),
            (5, 15, '5-15s'),
            (15, 30, '15-30s'),
            (30, 60, '30s-1min'),
            (60, 150, '1min-2min30'),
            (150, 300, '2min30-5min'),
            (300, float('inf'), '5min+')
        ]
        
        range_counts = defaultdict(lambda: {"accuracies": [], "count": 0, "blunders": 0, "mistakes": 0, "inaccuracies": 0})
        
        for record in ply_records:
            if record.get("side_moved") != player_color:
                continue
            
            time_spent = record.get("time_spent_s", 0)
            accuracy = record.get("accuracy_pct", 0)
            category = record.get("category", "").lower() if record.get("category") else ""
            
            if time_spent is None or time_spent <= 0:
                continue
            
            # Find matching bucket
            for min_time, max_time, display_name in time_ranges:
                if min_time <= time_spent < max_time:
                    range_counts[display_name]["accuracies"].append(accuracy)
                    range_counts[display_name]["count"] += 1
                    
                    # Track error counts
                    if category == "blunder":
                        range_counts[display_name]["blunders"] += 1
                    elif category == "mistake":
                        range_counts[display_name]["mistakes"] += 1
                    elif category == "inaccuracy":
                        range_counts[display_name]["inaccuracies"] += 1
                    break
        
        # Merge into stats
        for range_name, data in range_counts.items():
            if range_name not in stats["accuracy_by_time_spent"]:
                stats["accuracy_by_time_spent"][range_name] = {
                    "accuracy": 0, 
                    "count": 0, 
                    "blunders": 0,
                    "mistakes": 0,
                    "inaccuracies": 0,
                    "blunder_rate": 0,
                    "game_ids": []
                }
            
            old_count = stats["accuracy_by_time_spent"][range_name]["count"]
            old_accuracy = stats["accuracy_by_time_spent"][range_name]["accuracy"]
            old_blunders = stats["accuracy_by_time_spent"][range_name]["blunders"]
            old_mistakes = stats["accuracy_by_time_spent"][range_name]["mistakes"]
            old_inaccuracies = stats["accuracy_by_time_spent"][range_name]["inaccuracies"]
            
            new_count = data["count"]
            new_avg = statistics.mean(data["accuracies"]) if data["accuracies"] else 0
            
            total_count = old_count + new_count
            if total_count > 0:
                stats["accuracy_by_time_spent"][range_name]["accuracy"] = (
                    (old_accuracy * old_count + new_avg * new_count) / total_count
                )
                stats["accuracy_by_time_spent"][range_name]["count"] = total_count
                stats["accuracy_by_time_spent"][range_name]["blunders"] = old_blunders + data["blunders"]
                stats["accuracy_by_time_spent"][range_name]["mistakes"] = old_mistakes + data["mistakes"]
                stats["accuracy_by_time_spent"][range_name]["inaccuracies"] = old_inaccuracies + data["inaccuracies"]
                # Calculate blunder rate
                stats["accuracy_by_time_spent"][range_name]["blunder_rate"] = (
                    stats["accuracy_by_time_spent"][range_name]["blunders"] / total_count
                    if total_count > 0 else 0
                )
            
            if game_id not in stats["accuracy_by_time_spent"][range_name]["game_ids"]:
                stats["accuracy_by_time_spent"][range_name]["game_ids"].append(game_id)
    
    def _update_opening_stats(self, stats: Dict, opening_name: str, result: str, ply_records: List[Dict], player_color: str, game_id: str, game_review: Dict = None):
        """Incrementally update opening stats using total game accuracy."""
        if "opening_stats" not in stats:
            stats["opening_stats"] = {}
        
        if opening_name not in stats["opening_stats"]:
            stats["opening_stats"][opening_name] = {
                "games": 0,
                "win_rate": 0,
                "avg_accuracy": 0,
                "wins": 0,
                "losses": 0,
                "draws": 0,
                "game_ids": []
            }
        
        # Update game count
        stats["opening_stats"][opening_name]["games"] += 1
        
        # Update win/loss/draw counts
        if result == "win":
            stats["opening_stats"][opening_name]["wins"] = stats["opening_stats"][opening_name].get("wins", 0) + 1
        elif result == "loss":
            stats["opening_stats"][opening_name]["losses"] = stats["opening_stats"][opening_name].get("losses", 0) + 1
        elif result == "draw":
            stats["opening_stats"][opening_name]["draws"] = stats["opening_stats"][opening_name].get("draws", 0) + 1
        
        # Update win rate
        total_games = stats["opening_stats"][opening_name]["games"]
        wins = stats["opening_stats"][opening_name]["wins"]
        stats["opening_stats"][opening_name]["win_rate"] = wins / total_games if total_games > 0 else 0
        
        # Update accuracy using total game accuracy from game_review stats
        overall_accuracy = None
        if game_review:
            game_stats = game_review.get("stats", {})
            overall_accuracy = game_stats.get("overall_accuracy")
        
        # Fallback to calculating from ply_records if overall_accuracy not available
        if overall_accuracy is None:
            accuracies = [r.get("accuracy_pct", 0) for r in ply_records if r.get("side_moved") == player_color]
            if accuracies:
                overall_accuracy = statistics.mean(accuracies)
        
        if overall_accuracy is not None:
            old_games = stats["opening_stats"][opening_name]["games"] - 1
            old_avg = stats["opening_stats"][opening_name]["avg_accuracy"]
            stats["opening_stats"][opening_name]["avg_accuracy"] = (
                (old_avg * old_games + overall_accuracy) / stats["opening_stats"][opening_name]["games"]
            )
        
        if game_id not in stats["opening_stats"][opening_name]["game_ids"]:
            stats["opening_stats"][opening_name]["game_ids"].append(game_id)
    
    def _update_phase_stats(self, stats: Dict, ply_records: List[Dict], player_color: str, game_id: str, result: str = "unknown", game_review: Dict = None):
        """Incrementally update phase stats with win/loss tracking."""
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
        
        # Determine which phase the game ended in
        # Check last 10 moves to determine endgame phase
        ending_phase = "middlegame"
        if len(ply_records) >= 10:
            last_phases = [r.get("phase", "middlegame") for r in ply_records[-10:] if r.get("side_moved") == player_color]
            if last_phases:
                # If majority of last moves are in endgame, game ended in endgame
                endgame_count = sum(1 for p in last_phases if p == "endgame")
                if endgame_count >= len(last_phases) * 0.6:
                    ending_phase = "endgame"
                elif len(ply_records) < 20:
                    # Game ended early, likely in opening
                    ending_phase = "opening"
        
        # Merge into stats
        for phase_name, data in phase_counts.items():
            if phase_name not in stats["phase_stats"]:
                stats["phase_stats"][phase_name] = {
                    "accuracy": 0, 
                    "count": 0, 
                    "games_won": 0,
                    "games_lost": 0,
                    "games_drawn": 0,
                    "game_ids": []
                }
            
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
            
            # Track win/loss/draw for the phase the game ended in
            if phase_name == ending_phase:
                if result == "win":
                    stats["phase_stats"][phase_name]["games_won"] = stats["phase_stats"][phase_name].get("games_won", 0) + 1
                elif result == "loss":
                    stats["phase_stats"][phase_name]["games_lost"] = stats["phase_stats"][phase_name].get("games_lost", 0) + 1
                elif result == "draw":
                    stats["phase_stats"][phase_name]["games_drawn"] = stats["phase_stats"][phase_name].get("games_drawn", 0) + 1
            
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

