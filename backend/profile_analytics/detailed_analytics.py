"""
Detailed Analytics Aggregator
Computes comprehensive analytics including phase performance, opening repertoire,
piece accuracy, tag transitions, and time bucket performance.
"""

from typing import Dict, List, Any
from collections import defaultdict, Counter
import statistics
import math
from datetime import datetime as dt


class DetailedAnalyticsAggregator:
    """Aggregates detailed analytics from game reviews."""
    
    def aggregate(self, games: List[Dict]) -> Dict[str, Any]:
        """
        Aggregate detailed analytics from a list of games.
        
        Args:
            games: List of game dictionaries with game_review JSONB
            
        Returns:
            Dictionary containing all detailed analytics
        """
        if not games:
            return self._empty_analytics()
        
        return {
            "phase_analytics": self._aggregate_phases(games),
            "opening_detailed": self._aggregate_openings(games),
            "piece_accuracy_detailed": self._aggregate_pieces(games),
            "tag_transitions": self._aggregate_tag_transitions(games),
            "time_buckets": self._aggregate_time_buckets(games)
        }
    
    def _empty_analytics(self) -> Dict[str, Any]:
        """Return empty analytics structure."""
        return {
            "phase_analytics": {
                "opening": {"accuracy": 0, "games_won": 0, "games_lost": 0, "games_drawn": 0},
                "middlegame": {"accuracy": 0, "games_won": 0, "games_lost": 0, "games_drawn": 0},
                "endgame": {"accuracy": 0, "games_won": 0, "games_lost": 0, "games_drawn": 0}
            },
            "opening_detailed": {},
            "piece_accuracy_detailed": {"per_game": [], "aggregate": {}},
            "tag_transitions": {"gained": {}, "lost": {}},
            "time_buckets": {}
        }
    
    def _aggregate_phases(self, games: List[Dict]) -> Dict[str, Dict]:
        """Aggregate phase analytics with win/loss tracking."""
        phase_data = defaultdict(lambda: {
            "accuracies": [],
            "games_won": 0,
            "games_lost": 0,
            "games_drawn": 0
        })
        
        for game in games:
            game_review = game.get("game_review", {})
            if not game_review:
                continue
            
            ply_records = game_review.get("ply_records", [])
            player_color = game_review.get("metadata", {}).get("player_color", "white")
            result = game.get("result") or game_review.get("metadata", {}).get("result", "unknown")
            
            # Determine ending phase
            ending_phase = self._determine_ending_phase(ply_records, player_color)
            
            # Collect accuracies per phase
            phase_accuracies = defaultdict(list)
            for record in ply_records:
                if record.get("side_moved") != player_color:
                    continue
                phase = record.get("phase", "middlegame")
                accuracy = record.get("accuracy_pct", 0)
                phase_accuracies[phase].append(accuracy)
            
            # Update phase data
            for phase, accuracies in phase_accuracies.items():
                phase_data[phase]["accuracies"].extend(accuracies)
            
            # Track win/loss/draw for ending phase
            if ending_phase:
                if result == "win":
                    phase_data[ending_phase]["games_won"] += 1
                elif result == "loss":
                    phase_data[ending_phase]["games_lost"] += 1
                elif result == "draw":
                    phase_data[ending_phase]["games_drawn"] += 1
        
        # Calculate averages
        result = {}
        for phase in ["opening", "middlegame", "endgame"]:
            data = phase_data[phase]
            result[phase] = {
                "accuracy": round(statistics.mean(data["accuracies"]), 1) if data["accuracies"] else 0,
                "games_won": data["games_won"],
                "games_lost": data["games_lost"],
                "games_drawn": data["games_drawn"]
            }
        
        return result
    
    def _determine_ending_phase(self, ply_records: List[Dict], player_color: str) -> str:
        """Determine which phase the game ended in."""
        if len(ply_records) < 10:
            return "opening"
        
        # Check last 10 moves
        last_phases = [
            r.get("phase", "middlegame") 
            for r in ply_records[-10:] 
            if r.get("side_moved") == player_color
        ]
        
        if not last_phases:
            return "middlegame"
        
        # If majority are endgame, game ended in endgame
        endgame_count = sum(1 for p in last_phases if p == "endgame")
        if endgame_count >= len(last_phases) * 0.6:
            return "endgame"
        
        # If game is short, likely opening
        if len(ply_records) < 20:
            return "opening"
        
        return "middlegame"
    
    def _aggregate_openings(self, games: List[Dict]) -> Dict[str, Dict]:
        """Aggregate opening repertoire with frequency, accuracy, and win rates."""
        opening_data = defaultdict(lambda: {
            "games": [],
            "wins": 0,
            "losses": 0,
            "draws": 0,
            "accuracies": []
        })
        
        for game in games:
            opening_name = game.get("opening_name") or ""
            if not opening_name or opening_name == "Unknown":
                continue
            
            game_review = game.get("game_review", {})
            result = game.get("result") or game_review.get("metadata", {}).get("result", "unknown")
            
            # Get overall accuracy from game_review stats
            overall_accuracy = None
            if game_review:
                stats = game_review.get("stats", {})
                overall_accuracy = stats.get("overall_accuracy")
            
            # Fallback to calculating from ply_records
            if overall_accuracy is None:
                ply_records = game_review.get("ply_records", [])
                player_color = game_review.get("metadata", {}).get("player_color", "white")
                accuracies = [
                    r.get("accuracy_pct", 0) 
                    for r in ply_records 
                    if r.get("side_moved") == player_color
                ]
                if accuracies:
                    overall_accuracy = statistics.mean(accuracies)
            
            if overall_accuracy is not None:
                opening_data[opening_name]["accuracies"].append(overall_accuracy)
            
            opening_data[opening_name]["games"].append(game.get("id"))
            
            if result == "win":
                opening_data[opening_name]["wins"] += 1
            elif result == "loss":
                opening_data[opening_name]["losses"] += 1
            elif result == "draw":
                opening_data[opening_name]["draws"] += 1
        
        # Format results
        result = {}
        for opening_name, data in opening_data.items():
            total_games = len(data["games"])
            if total_games > 0:
                result[opening_name] = {
                    "frequency": total_games,
                    "avg_accuracy": round(statistics.mean(data["accuracies"]), 1) if data["accuracies"] else 0,
                    "win_rate": round(data["wins"] / total_games, 3) if total_games > 0 else 0,
                    "wins": data["wins"],
                    "losses": data["losses"],
                    "draws": data["draws"]
                }
        
        # Sort by frequency
        return dict(sorted(result.items(), key=lambda x: x[1]["frequency"], reverse=True))
    
    def _aggregate_pieces(self, games: List[Dict]) -> Dict[str, Any]:
        """Aggregate piece accuracy with per-game breakdowns."""
        piece_aggregate = defaultdict(lambda: {"accuracies": [], "count": 0})
        per_game_breakdowns = []
        
        for game in games:
            game_review = game.get("game_review", {})
            if not game_review:
                continue
            
            ply_records = game_review.get("ply_records", [])
            player_color = game_review.get("metadata", {}).get("player_color", "white")
            game_id = game.get("id", "")
            
            game_pieces = defaultdict(lambda: {"accuracies": [], "count": 0})
            
            for record in ply_records:
                if record.get("side_moved") != player_color:
                    continue
                
                san = record.get("san", "")
                accuracy = record.get("accuracy_pct", 0)
                piece_type = self._get_piece_type_from_san(san)
                
                if piece_type:
                    game_pieces[piece_type]["accuracies"].append(accuracy)
                    game_pieces[piece_type]["count"] += 1
                    piece_aggregate[piece_type]["accuracies"].append(accuracy)
                    piece_aggregate[piece_type]["count"] += 1
            
            # Store per-game breakdown
            game_breakdown = {
                "game_id": game_id,
                "pieces": {}
            }
            for piece_name, data in game_pieces.items():
                if data["accuracies"]:
                    game_breakdown["pieces"][piece_name] = {
                        "accuracy": round(statistics.mean(data["accuracies"]), 1),
                        "count": data["count"]
                    }
            
            if game_breakdown["pieces"]:
                per_game_breakdowns.append(game_breakdown)
        
        # Calculate aggregate accuracies
        aggregate = {}
        all_pieces = ["Pawn", "Knight", "Bishop", "Rook", "Queen", "King"]
        for piece_name in all_pieces:
            data = piece_aggregate[piece_name]
            aggregate[piece_name] = {
                "accuracy": round(statistics.mean(data["accuracies"]), 1) if data["accuracies"] else 0,
                "count": data["count"]
            }
        
        return {
            "per_game": per_game_breakdowns[-100:],  # Keep last 100 games
            "aggregate": aggregate
        }
    
    def _get_piece_type_from_san(self, san: str) -> str:
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
    
    def _calculate_tag_significance(
        self, 
        accuracy: float, 
        count: int, 
        baseline_accuracy: float,
        accuracies_list: List[float]
    ) -> float:
        """
        Calculate significance score (0-100) for tag transitions.
        
        Formula combines:
        - Frequency factor (40%): log(count+1) normalized - prevents low-count extremes
        - Deviation factor (35%): absolute deviation from baseline
        - Consistency factor (25%): inverse of variance
        
        Returns: 0-100 score where higher = more significant
        """
        # Frequency: log(count+1) normalized to log(50) ≈ 3.9
        frequency_weight = math.log(count + 1)
        frequency_factor = min(1.0, frequency_weight / math.log(50))
        
        # Deviation: distance from baseline (max at 25%)
        deviation = abs(accuracy - baseline_accuracy)
        deviation_factor = min(1.0, deviation / 25.0)
        
        # Consistency: inverse variance (lower variance = higher)
        if len(accuracies_list) > 1:
            variance = statistics.stdev(accuracies_list)
            consistency_factor = max(0, 1 - (variance / 30.0))
        else:
            consistency_factor = 0.5
        
        # Weighted combination
        significance = (
            frequency_factor * 0.4 + 
            deviation_factor * 0.35 + 
            consistency_factor * 0.25
        )
        
        return round(significance * 100, 1)
    
    def _aggregate_by_day_intervals(
        self, 
        games: List[Dict], 
        tag_name: str, 
        transition_type: str,
        player_color: str
    ) -> Dict[str, Any]:
        """
        Aggregate tag transition data by day intervals for trend visualization.
        
        Args:
            games: List of game dictionaries
            tag_name: Name of the tag to aggregate
            transition_type: "gained" or "lost"
            player_color: Player color ("white" or "black")
        
        Returns:
            {
                "dates": ["2024-01-01", "2024-01-02", ...],
                "accuracies": [75.2, 78.1, ...],
                "counts": [5, 8, ...],
                "errors": [1, 2, ...]
            }
        """
        def extract_tag_names(tags):
            tag_names = set()
            for tag in tags:
                if isinstance(tag, str):
                    tag_names.add(tag)
                elif isinstance(tag, dict):
                    tag_name = tag.get("tag_name") or tag.get("name") or tag.get("tag", "")
                    if tag_name:
                        tag_names.add(tag_name)
            return tag_names
        
        # Group transitions by game date
        daily_data = defaultdict(lambda: {"accuracies": [], "count": 0, "errors": 0})
        
        for game in games:
            game_review = game.get("game_review", {})
            if not game_review:
                continue
            
            # Extract game date (handle both datetime objects and strings)
            game_date = game.get("game_date")
            if not game_date:
                continue
            
            # Convert datetime to string if needed
            if isinstance(game_date, dt):
                game_date = game_date.strftime("%Y-%m-%d")
            elif isinstance(game_date, str):
                # Parse date to YYYY-MM-DD format
                if "T" in game_date:
                    game_date = game_date.split("T")[0]
                elif " " in game_date:
                    game_date = game_date.split(" ")[0]
            else:
                # Skip if we can't parse it
                continue
            
            ply_records = game_review.get("ply_records", [])
            
            # Track transitions for this tag on this day
            for i in range(1, len(ply_records)):
                prev_record = ply_records[i - 1]
                curr_record = ply_records[i]
                
                if curr_record.get("side_moved") != player_color:
                    continue
                
                prev_tags = extract_tag_names(prev_record.get("analyse", {}).get("tags", []))
                curr_tags = extract_tag_names(curr_record.get("analyse", {}).get("tags", []))
                
                gained = curr_tags - prev_tags
                lost = prev_tags - curr_tags
                
                # Check if this tag transition matches
                if transition_type == "gained" and tag_name in gained:
                    accuracy = curr_record.get("accuracy_pct", 0)
                    category = curr_record.get("category", "").lower() if curr_record.get("category") else ""
                    daily_data[game_date]["accuracies"].append(accuracy)
                    daily_data[game_date]["count"] += 1
                    if category in ["blunder", "mistake", "inaccuracy"]:
                        daily_data[game_date]["errors"] += 1
                elif transition_type == "lost" and tag_name in lost:
                    accuracy = curr_record.get("accuracy_pct", 0)
                    category = curr_record.get("category", "").lower() if curr_record.get("category") else ""
                    daily_data[game_date]["accuracies"].append(accuracy)
                    daily_data[game_date]["count"] += 1
                    if category in ["blunder", "mistake", "inaccuracy"]:
                        daily_data[game_date]["errors"] += 1
        
        # Sort dates and calculate daily averages
        sorted_dates = sorted(daily_data.keys())
        dates = []
        accuracies = []
        counts = []
        errors = []
        
        for date in sorted_dates:
            data = daily_data[date]
            if data["count"] > 0:
                dates.append(date)
                accuracies.append(round(statistics.mean(data["accuracies"]), 1))
                counts.append(data["count"])
                errors.append(data["errors"])
        
        return {
            "dates": dates,
            "accuracies": accuracies,
            "counts": counts,
            "errors": errors
        }
    
    def _aggregate_tag_transitions(self, games: List[Dict]) -> Dict[str, Dict]:
        """Aggregate tag transition analytics (gained/lost)."""
        gained_tags = defaultdict(lambda: {
            "accuracies": [],
            "blunders": 0,
            "mistakes": 0,
            "inaccuracies": 0,
            "count": 0
        })
        
        lost_tags = defaultdict(lambda: {
            "accuracies": [],
            "blunders": 0,
            "mistakes": 0,
            "inaccuracies": 0,
            "count": 0
        })
        
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
        
        for game in games:
            game_review = game.get("game_review", {})
            if not game_review:
                continue
            
            ply_records = game_review.get("ply_records", [])
            player_color = game_review.get("metadata", {}).get("player_color", "white")
            
            # Track transitions between consecutive moves
            for i in range(1, len(ply_records)):
                prev_record = ply_records[i - 1]
                curr_record = ply_records[i]
                
                if curr_record.get("side_moved") != player_color:
                    continue
                
                prev_tags = extract_tag_names(prev_record.get("analyse", {}).get("tags", []))
                curr_tags = extract_tag_names(curr_record.get("analyse", {}).get("tags", []))
                
                gained = curr_tags - prev_tags
                lost = prev_tags - curr_tags
                
                accuracy = curr_record.get("accuracy_pct", 0)
                category = curr_record.get("category", "").lower() if curr_record.get("category") else ""
                
                # Track gained tags
                for tag_name in gained:
                    gained_tags[tag_name]["accuracies"].append(accuracy)
                    gained_tags[tag_name]["count"] += 1
                    if category == "blunder":
                        gained_tags[tag_name]["blunders"] += 1
                    elif category == "mistake":
                        gained_tags[tag_name]["mistakes"] += 1
                    elif category == "inaccuracy":
                        gained_tags[tag_name]["inaccuracies"] += 1
                
                # Track lost tags
                for tag_name in lost:
                    lost_tags[tag_name]["accuracies"].append(accuracy)
                    lost_tags[tag_name]["count"] += 1
                    if category == "blunder":
                        lost_tags[tag_name]["blunders"] += 1
                    elif category == "mistake":
                        lost_tags[tag_name]["mistakes"] += 1
                    elif category == "inaccuracy":
                        lost_tags[tag_name]["inaccuracies"] += 1
        
        # Calculate baseline accuracy from all tag accuracies (gained + lost)
        all_tag_accuracies = []
        for tag_data in gained_tags.values():
            all_tag_accuracies.extend(tag_data["accuracies"])
        for tag_data in lost_tags.values():
            all_tag_accuracies.extend(tag_data["accuracies"])
        baseline_accuracy = statistics.mean(all_tag_accuracies) if all_tag_accuracies else 75.0
        
        # Format results with trend calculation and significance scoring
        def format_tag_data(tag_dict, games_list, player_color_str, transition_type_str):
            result = {}
            
            # Build per-game accuracy tracking for trend calculation
            tag_game_accuracies = defaultdict(lambda: {"recent": [], "older": []})
            
            def extract_tag_names(tags):
                tag_names = set()
                for tag in tags:
                    if isinstance(tag, str):
                        tag_names.add(tag)
                    elif isinstance(tag, dict):
                        tag_name = tag.get("tag_name") or tag.get("name") or tag.get("tag", "")
                        if tag_name:
                            tag_names.add(tag_name)
                return tag_names
            
            # Split games into recent (last 10) and older for trend calculation
            if len(games_list) > 10:
                recent_games = games_list[-10:]
                older_games = games_list[:-10]
            else:
                mid_point = len(games_list) // 2
                recent_games = games_list[mid_point:] if mid_point > 0 else games_list
                older_games = games_list[:mid_point] if mid_point > 0 else []
            
            # Track accuracies per tag per game for trend calculation
            recent_indices = set(range(max(0, len(games_list) - 10), len(games_list))) if len(games_list) > 10 else set(range(len(games_list) // 2, len(games_list)))
            
            for game_idx, game in enumerate(games_list):
                game_review = game.get("game_review", {})
                if not game_review:
                    continue
                
                ply_records = game_review.get("ply_records", [])
                is_recent = game_idx in recent_indices
                
                for i in range(1, len(ply_records)):
                    prev_record = ply_records[i - 1]
                    curr_record = ply_records[i]
                    
                    if curr_record.get("side_moved") != player_color_str:
                        continue
                    
                    prev_tags = extract_tag_names(prev_record.get("analyse", {}).get("tags", []))
                    curr_tags = extract_tag_names(curr_record.get("analyse", {}).get("tags", []))
                    
                    gained = curr_tags - prev_tags
                    lost = prev_tags - curr_tags
                    
                    accuracy = curr_record.get("accuracy_pct", 0)
                    
                    # Track for trend calculation
                    for tag_name in gained | lost:
                        if is_recent:
                            tag_game_accuracies[tag_name]["recent"].append(accuracy)
                        else:
                            tag_game_accuracies[tag_name]["older"].append(accuracy)
            
            for tag_name, data in tag_dict.items():
                if data["count"] > 0:
                    # Calculate significance score
                    avg_accuracy = statistics.mean(data["accuracies"]) if data["accuracies"] else 0
                    significance_score = self._calculate_tag_significance(
                        avg_accuracy,
                        data["count"],
                        baseline_accuracy,
                        data["accuracies"]
                    )
                    
                    # Filter by significance threshold (minimum 20)
                    if significance_score < 20:
                        continue
                    
                    # Calculate trend
                    trend_value = 0
                    trend_direction = "stable"
                    
                    recent_accs = tag_game_accuracies[tag_name]["recent"]
                    older_accs = tag_game_accuracies[tag_name]["older"]
                    
                    if len(recent_accs) > 0 and len(older_accs) > 0:
                        recent_avg = statistics.mean(recent_accs)
                        older_avg = statistics.mean(older_accs)
                        trend_value = recent_avg - older_avg
                        if trend_value > 2:
                            trend_direction = "improving"
                        elif trend_value < -2:
                            trend_direction = "declining"
                    elif len(recent_accs) > 0:
                        # Only recent data, compare to overall average
                        recent_avg = statistics.mean(recent_accs)
                        overall_avg = statistics.mean(data["accuracies"]) if data["accuracies"] else 0
                        trend_value = recent_avg - overall_avg
                        if trend_value > 2:
                            trend_direction = "improving"
                        elif trend_value < -2:
                            trend_direction = "declining"
                    
                    # Aggregate day intervals for trend visualization
                    day_intervals = self._aggregate_by_day_intervals(
                        games_list,
                        tag_name,
                        transition_type_str,
                        player_color_str
                    )
                    
                    result[tag_name] = {
                        "accuracy": round(avg_accuracy, 1),
                        "count": data["count"],
                        "blunders": data["blunders"],
                        "mistakes": data["mistakes"],
                        "inaccuracies": data["inaccuracies"],
                        "trend": trend_direction,
                        "trend_value": round(trend_value, 1),
                        "significance_score": significance_score,
                        "day_intervals": day_intervals
                    }
            return result
        
        return {
            "gained": format_tag_data(gained_tags, games, player_color, "gained"),
            "lost": format_tag_data(lost_tags, games, player_color, "lost")
        }
    
    def _aggregate_time_buckets(self, games: List[Dict]) -> Dict[str, Dict]:
        """Aggregate time bucket analytics with 7-bucket system."""
        # 7-bucket system
        time_buckets = {
            "<5s": {"accuracies": [], "count": 0, "blunders": 0, "mistakes": 0, "inaccuracies": 0},
            "5-15s": {"accuracies": [], "count": 0, "blunders": 0, "mistakes": 0, "inaccuracies": 0},
            "15-30s": {"accuracies": [], "count": 0, "blunders": 0, "mistakes": 0, "inaccuracies": 0},
            "30s-1min": {"accuracies": [], "count": 0, "blunders": 0, "mistakes": 0, "inaccuracies": 0},
            "1min-2min30": {"accuracies": [], "count": 0, "blunders": 0, "mistakes": 0, "inaccuracies": 0},
            "2min30-5min": {"accuracies": [], "count": 0, "blunders": 0, "mistakes": 0, "inaccuracies": 0},
            "5min+": {"accuracies": [], "count": 0, "blunders": 0, "mistakes": 0, "inaccuracies": 0}
        }
        
        bucket_ranges = [
            (0, 5, "<5s"),
            (5, 15, "5-15s"),
            (15, 30, "15-30s"),
            (30, 60, "30s-1min"),
            (60, 150, "1min-2min30"),
            (150, 300, "2min30-5min"),
            (300, float('inf'), "5min+")
        ]
        
        for game in games:
            game_review = game.get("game_review", {})
            if not game_review:
                continue
            
            ply_records = game_review.get("ply_records", [])
            player_color = game_review.get("metadata", {}).get("player_color", "white")
            
            for record in ply_records:
                if record.get("side_moved") != player_color:
                    continue
                
                time_spent = record.get("time_spent_s", 0)
                accuracy = record.get("accuracy_pct", 0)
                category = record.get("category", "").lower() if record.get("category") else ""
                
                if time_spent is None or time_spent <= 0:
                    continue
                
                # Find matching bucket
                for min_time, max_time, bucket_name in bucket_ranges:
                    if min_time <= time_spent < max_time:
                        time_buckets[bucket_name]["accuracies"].append(accuracy)
                        time_buckets[bucket_name]["count"] += 1
                        if category == "blunder":
                            time_buckets[bucket_name]["blunders"] += 1
                        elif category == "mistake":
                            time_buckets[bucket_name]["mistakes"] += 1
                        elif category == "inaccuracy":
                            time_buckets[bucket_name]["inaccuracies"] += 1
                        break
        
        # Format results
        result = {}
        for bucket_name, data in time_buckets.items():
            if data["count"] > 0:
                result[bucket_name] = {
                    "accuracy": round(statistics.mean(data["accuracies"]), 1) if data["accuracies"] else 0,
                    "count": data["count"],
                    "blunders": data["blunders"],
                    "mistakes": data["mistakes"],
                    "inaccuracies": data["inaccuracies"],
                    "blunder_rate": round(data["blunders"] / data["count"], 3) if data["count"] > 0 else 0,
                    "mistake_rate": round(data["mistakes"] / data["count"], 3) if data["count"] > 0 else 0,
                    "inaccuracy_rate": round(data["inaccuracies"] / data["count"], 3) if data["count"] > 0 else 0
                }
        
        return result
    
    def validate_analytics(self, analytics: Dict[str, Any], games: List[Dict]) -> Dict[str, Any]:
        """
        Validate analytics data for correctness.
        Returns validation report with any issues found.
        """
        issues = []
        warnings = []
        
        # Validate phase analytics
        phase_analytics = analytics.get("phase_analytics", {})
        total_phase_games = 0
        for phase in ["opening", "middlegame", "endgame"]:
            phase_data = phase_analytics.get(phase, {})
            phase_total = phase_data.get("games_won", 0) + phase_data.get("games_lost", 0) + phase_data.get("games_drawn", 0)
            total_phase_games += phase_total
            
            if phase_data.get("accuracy", 0) < 0 or phase_data.get("accuracy", 0) > 100:
                issues.append(f"Phase {phase} accuracy out of range: {phase_data.get('accuracy')}")
        
        # Validate opening analytics
        opening_detailed = analytics.get("opening_detailed", {})
        total_opening_games = sum(op.get("frequency", 0) for op in opening_detailed.values())
        for opening_name, opening_data in opening_detailed.items():
            frequency = opening_data.get("frequency", 0)
            wins = opening_data.get("wins", 0)
            losses = opening_data.get("losses", 0)
            draws = opening_data.get("draws", 0)
            
            if wins + losses + draws != frequency:
                issues.append(f"Opening {opening_name}: wins+losses+draws ({wins+losses+draws}) != frequency ({frequency})")
            
            if opening_data.get("avg_accuracy", 0) < 0 or opening_data.get("avg_accuracy", 0) > 100:
                issues.append(f"Opening {opening_name} accuracy out of range: {opening_data.get('avg_accuracy')}")
        
        # Validate piece accuracy
        piece_data = analytics.get("piece_accuracy_detailed", {})
        aggregate = piece_data.get("aggregate", {})
        for piece_name, piece_stats in aggregate.items():
            if piece_stats.get("accuracy", 0) < 0 or piece_stats.get("accuracy", 0) > 100:
                issues.append(f"Piece {piece_name} accuracy out of range: {piece_stats.get('accuracy')}")
        
        # Validate tag transitions
        tag_transitions = analytics.get("tag_transitions", {})
        for transition_type in ["gained", "lost"]:
            transitions = tag_transitions.get(transition_type, {})
            for tag_name, tag_data in transitions.items():
                count = tag_data.get("count", 0)
                errors = tag_data.get("blunders", 0) + tag_data.get("mistakes", 0) + tag_data.get("inaccuracies", 0)
                
                if errors > count:
                    issues.append(f"Tag {tag_name} ({transition_type}): errors ({errors}) > count ({count})")
                
                if tag_data.get("accuracy", 0) < 0 or tag_data.get("accuracy", 0) > 100:
                    issues.append(f"Tag {tag_name} ({transition_type}) accuracy out of range: {tag_data.get('accuracy')}")
        
        # Validate time buckets
        time_buckets = analytics.get("time_buckets", {})
        total_moves = 0
        for bucket_name, bucket_data in time_buckets.items():
            count = bucket_data.get("count", 0)
            blunders = bucket_data.get("blunders", 0)
            total_moves += count
            
            if blunders > count:
                issues.append(f"Time bucket {bucket_name}: blunders ({blunders}) > count ({count})")
            
            blunder_rate = bucket_data.get("blunder_rate", 0)
            if blunder_rate < 0 or blunder_rate > 1:
                issues.append(f"Time bucket {bucket_name} blunder_rate out of range: {blunder_rate}")
            
            if bucket_data.get("accuracy", 0) < 0 or bucket_data.get("accuracy", 0) > 100:
                issues.append(f"Time bucket {bucket_name} accuracy out of range: {bucket_data.get('accuracy')}")
        
        # Cross-validation: Check if total games match
        if len(games) > 0:
            if total_opening_games > len(games) * 1.1:  # Allow 10% margin for multiple openings per game
                warnings.append(f"Total opening games ({total_opening_games}) significantly exceeds game count ({len(games)})")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "summary": {
                "total_games": len(games),
                "total_opening_games": total_opening_games,
                "total_phase_games": total_phase_games,
                "total_moves_in_time_buckets": total_moves
            }
        }

