"""
Personal Review Aggregator
Aggregates statistics and metrics across multiple games
"""

from typing import List, Dict, Any, Optional
from collections import defaultdict
import statistics
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.personal_review_utils import GameFilter, extract_tags, extract_tag_names


class PersonalReviewAggregator:
    """Aggregates and analyzes game review data"""
    
    def __init__(self):
        pass
    
    def aggregate(
        self,
        analyzed_games: List[Dict],
        filters: Optional[Dict] = None,
        cohorts: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        Aggregate statistics across analyzed games
        
        Args:
            analyzed_games: List of game review results from /review_game
            filters: Optional filters to apply
            cohorts: Optional cohort definitions for comparison
            
        Returns:
            Aggregated statistics dictionary
        """
        print(f"\n🔍 AGGREGATOR.aggregate() called with {len(analyzed_games)} games")
        
        # Apply filters if provided
        if filters:
            filtered_games = GameFilter.apply_filters(analyzed_games, filters)
        else:
            filtered_games = analyzed_games
        print(f"   After filters: {len(filtered_games)} games")
        
        if not filtered_games:
            print(f"   ⚠️ No games after filtering!")
            return {"error": "No games match the specified filters"}
        
        # Calculate main statistics
        print(f"   Calculating summary...")
        summary = self._calculate_summary(filtered_games)
        
        print(f"   Calculating accuracy by rating...")
        accuracy_by_rating = self._calculate_accuracy_by_rating(filtered_games)
        
        print(f"   Calculating opening performance...")
        opening_performance = self._calculate_opening_performance(filtered_games)
        
        print(f"   Calculating theme frequency...")
        theme_frequency = self._calculate_theme_frequency(filtered_games)
        
        print(f"   Calculating phase stats...")
        phase_stats = self._calculate_phase_stats(filtered_games)
        
        print(f"   Calculating win rate by phase...")
        win_rate_by_phase = self._calculate_win_rate_by_phase(filtered_games)
        
        print(f"   Calculating mistake patterns...")
        mistake_patterns = self._calculate_mistake_patterns(filtered_games)
        
        print(f"   Calculating time management...")
        time_management = self._calculate_time_management(filtered_games)
        
        print(f"   Calculating advanced metrics...")
        advanced_metrics = self._calculate_advanced_metrics(filtered_games)
        
        print(f"   Calculating accuracy by color...")
        accuracy_by_color = self._calculate_accuracy_by_color(filtered_games)
        
        print(f"   Calculating performance by time control...")
        performance_by_time_control = self._calculate_performance_by_time_control(filtered_games)
        
        print(f"   Calculating accuracy by time spent...")
        accuracy_by_time_spent = self._calculate_accuracy_by_time_spent(filtered_games)
        
        print(f"   Calculating performance by tags...")
        performance_by_tags = self._calculate_performance_by_tags(filtered_games)
        
        print(f"   Calculating critical moment performance...")
        critical_moments = self._calculate_critical_moments(filtered_games)
        
        print(f"   Calculating advantage conversion...")
        advantage_conversion = self._calculate_advantage_conversion(filtered_games)
        
        print(f"   Calculating blunder triggers...")
        blunder_triggers = self._calculate_blunder_triggers(filtered_games)
        
        print(f"   Calculating piece activity...")
        piece_activity = self._calculate_piece_activity(filtered_games)
        
        print(f"   Calculating tilt points (accuracy vs time)...")
        tilt_points = self._calculate_tilt_points(filtered_games)
        
        print(f"   Calculating diagnostic insights (relevance formula)...")
        diagnostic_insights = self._calculate_diagnostic_insights(filtered_games, summary.get("overall_accuracy", 75))
        
        print(f"   Building result dictionary...")
        result = {
            "summary": summary,
            "accuracy_by_rating": accuracy_by_rating,
            "opening_performance": opening_performance,
            "theme_frequency": theme_frequency,
            "phase_stats": phase_stats,
            "win_rate_by_phase": win_rate_by_phase,
            "mistake_patterns": mistake_patterns,
            "time_management": time_management,
            "advanced_metrics": advanced_metrics,
            "accuracy_by_color": accuracy_by_color,
            "performance_by_time_control": performance_by_time_control,
            "accuracy_by_time_spent": accuracy_by_time_spent,
            "performance_by_tags": performance_by_tags,
            "critical_moments": critical_moments,
            "advantage_conversion": advantage_conversion,
            "blunder_triggers": blunder_triggers,
            "piece_activity": piece_activity,
            "tilt_points": tilt_points,
            "diagnostic_insights": diagnostic_insights,
            "total_games_analyzed": len(filtered_games)
        }
        
        # Cohort comparison if requested
        if cohorts:
            print(f"   Comparing cohorts...")
            result["cohort_comparison"] = self._compare_cohorts(analyzed_games, cohorts)
        
        print(f"   ✅ Aggregator complete - returning results")
        return result
    
    
    def _calculate_summary(self, games: List[Dict]) -> Dict:
        """Calculate overall summary statistics"""
        total_games = len(games)
        
        print(f"  📊 Calculating summary for {total_games} games...")
        
        # Win/loss/draw counts
        results = [g.get("metadata", {}).get("result", "unknown") for g in games]
        wins = results.count("win")
        losses = results.count("loss")
        draws = results.count("draw")
        
        # Overall accuracy and CP loss
        all_accuracies = []
        all_cp_losses = []
        blunder_count = 0
        mistake_count = 0
        
        for idx, game in enumerate(games):
            ply_records = game.get("ply_records", [])
            player_color = game.get("metadata", {}).get("player_color", "white")
            
            print(f"    Game {idx+1}: {len(ply_records)} total plies, looking for {player_color} moves")
            
            player_moves_in_game = 0
            for record in ply_records:
                side_moved = record.get("side_moved")
                
                # Debug: print first few records to see data structure
                if idx == 0 and player_moves_in_game < 3:
                    print(f"      Record: side_moved={side_moved}, player_color={player_color}, accuracy={record.get('accuracy_pct')}")
                
                if side_moved == player_color:
                    player_moves_in_game += 1
                    acc = record.get("accuracy_pct", 0)
                    try:
                        all_accuracies.append(float(acc) if acc is not None else 0.0)
                    except Exception:
                        all_accuracies.append(0.0)

                    cpl = record.get("cp_loss", 0)
                    try:
                        all_cp_losses.append(float(cpl) if cpl is not None else 0.0)
                    except Exception:
                        all_cp_losses.append(0.0)
                    
                    if record.get("category") == "blunder":
                        blunder_count += 1
                    elif record.get("category") == "mistake":
                        mistake_count += 1
            
            print(f"      → Found {player_moves_in_game} {player_color} moves")
        
        print(f"    Total player moves collected: {len(all_accuracies)}")
        
        # Defensive: ensure no None sneaks in
        all_accuracies = [x for x in all_accuracies if x is not None]
        all_cp_losses = [x for x in all_cp_losses if x is not None]
        overall_accuracy = statistics.mean(all_accuracies) if all_accuracies else 0.0
        avg_cp_loss = statistics.mean(all_cp_losses) if all_cp_losses else 0.0
        
        total_moves = len(all_accuracies)
        blunder_rate = (blunder_count / total_moves * 100) if total_moves > 0 else 0
        mistake_rate = (mistake_count / total_moves * 100) if total_moves > 0 else 0
        
        print(f"    Overall accuracy: {float(overall_accuracy):.1f}%, Avg CP loss: {float(avg_cp_loss):.1f}")
        
        return {
            "total_games": total_games,
            "wins": wins,
            "losses": losses,
            "draws": draws,
            "win_rate": (wins / total_games) if total_games > 0 else 0,  # Return as decimal 0-1
            "overall_accuracy": overall_accuracy,
            "avg_accuracy": overall_accuracy,  # Add this for compatibility
            "avg_cp_loss": avg_cp_loss,
            "blunder_rate": blunder_rate,
            "mistake_rate": mistake_rate,
            "total_moves": total_moves,
            "blunders_per_game": blunder_count / total_games if total_games > 0 else 0,
            "mistakes_per_game": mistake_count / total_games if total_games > 0 else 0
        }
    
    def _calculate_accuracy_by_rating(self, games: List[Dict]) -> List[Dict]:
        """Calculate accuracy grouped by rating bands"""
        rating_bands = defaultdict(lambda: {"accuracies": [], "count": 0})
        
        for game in games:
            rating = game.get("metadata", {}).get("player_rating", 0)
            if rating == 0:
                continue
            
            # Create rating band (e.g., 800-899, 900-999)
            band_start = (rating // 100) * 100
            band_key = f"{band_start}-{band_start + 99}"
            
            ply_records = game.get("ply_records", [])
            player_color = game.get("metadata", {}).get("player_color", "white")
            
            for record in ply_records:
                if record.get("side_moved") == player_color:
                    acc = record.get("accuracy_pct", 0)
                    try:
                        rating_bands[band_key]["accuracies"].append(float(acc) if acc is not None else 0.0)
                    except Exception:
                        rating_bands[band_key]["accuracies"].append(0.0)
                    rating_bands[band_key]["count"] += 1
        
        result = []
        for band, data in sorted(rating_bands.items()):
            if data["accuracies"]:
                result.append({
                    "rating_range": band,
                    "accuracy": statistics.mean([x for x in data["accuracies"] if x is not None]) if data["accuracies"] else 0.0,
                    "game_count": data["count"]
                })
        
        return result
    
    def _calculate_opening_performance(self, games: List[Dict]) -> List[Dict]:
        """Calculate performance by opening"""
        opening_stats = defaultdict(lambda: {
            "count": 0,
            "wins": 0,
            "losses": 0,
            "draws": 0,
            "accuracies": [],
            "cp_losses": []
        })
        
        for game in games:
            # Try to get opening from review data first, then from metadata
            opening_name = game.get("opening", {}).get("name_final", "")
            if not opening_name:
                opening_name = game.get("metadata", {}).get("opening", "Unknown Opening")
            if not opening_name or opening_name == "":
                opening_name = "Unknown Opening"
            
            result = game.get("metadata", {}).get("result", "unknown")
            
            stats = opening_stats[opening_name]
            stats["count"] += 1
            
            if result == "win":
                stats["wins"] += 1
            elif result == "loss":
                stats["losses"] += 1
            elif result == "draw":
                stats["draws"] += 1
            
            # Get player's accuracy in this game
            ply_records = game.get("ply_records", [])
            player_color = game.get("metadata", {}).get("player_color", "white")
            
            for record in ply_records:
                if record.get("side_moved") == player_color:
                    stats["accuracies"].append(record.get("accuracy_pct", 0))
                    stats["cp_losses"].append(record.get("cp_loss", 0))
        
        result = []
        for opening, stats in opening_stats.items():
            if stats["count"] > 0:
                result.append({
                    "name": opening,
                    "count": stats["count"],
                    "wins": stats["wins"],
                    "losses": stats["losses"],
                    "draws": stats["draws"],
                    "win_rate": (stats["wins"] / stats["count"] * 100),
                    "avg_accuracy": statistics.mean(stats["accuracies"]) if stats["accuracies"] else 0,
                    "avg_cp_loss": statistics.mean(stats["cp_losses"]) if stats["cp_losses"] else 0
                })
        
        # Sort by game count descending
        result.sort(key=lambda x: x["count"], reverse=True)
        return result
    
    def _calculate_accuracy_by_color(self, games: List[Dict]) -> Dict:
        """Calculate accuracy split by playing color"""
        white_games = [g for g in games if g.get('metadata', {}).get('player_color') == 'white']
        black_games = [g for g in games if g.get('metadata', {}).get('player_color') == 'black']
        
        def get_avg_accuracy(color_games):
            if not color_games:
                return 0
            accuracies = []
            for game in color_games:
                player_color = game.get('metadata', {}).get('player_color', 'white')
                for record in game.get('ply_records', []):
                    if record.get('side_moved') == player_color:
                        accuracies.append(record.get('accuracy_pct', 0))
            return statistics.mean(accuracies) if accuracies else 0
        
        def get_win_rate(color_games):
            if not color_games:
                return 0
            wins = sum(1 for g in color_games if g.get('metadata', {}).get('result') == 'win')
            return wins / len(color_games) if color_games else 0
        
        white_acc = get_avg_accuracy(white_games)
        black_acc = get_avg_accuracy(black_games)
        
        return {
            'white': {
                'accuracy': white_acc,
                'game_count': len(white_games),
                'win_rate': get_win_rate(white_games)
            },
            'black': {
                'accuracy': black_acc,
                'game_count': len(black_games),
                'win_rate': get_win_rate(black_games)
            }
        }
    
    def _calculate_performance_by_time_control(self, games: List[Dict]) -> List[Dict]:
        """Group performance by time control (blitz/rapid/classical)"""
        time_controls = defaultdict(list)
        
        for game in games:
            tc = game.get('metadata', {}).get('time_control', 'unknown')
            # Classify: <180s = blitz, <900s = rapid, else classical
            if isinstance(tc, int):
                if tc < 180:
                    category = 'blitz'
                elif tc < 900:
                    category = 'rapid'
                else:
                    category = 'classical'
            elif isinstance(tc, str):
                # Try to parse string like "600+0"
                try:
                    base_time = int(tc.split('+')[0])
                    if base_time < 180:
                        category = 'blitz'
                    elif base_time < 900:
                        category = 'rapid'
                    else:
                        category = 'classical'
                except:
                    category = 'unknown'
            else:
                category = 'unknown'
            
            time_controls[category].append(game)
        
        def get_avg_accuracy_for_tc(tc_games):
            if not tc_games:
                return 0
            accuracies = []
            for game in tc_games:
                player_color = game.get('metadata', {}).get('player_color', 'white')
                for record in game.get('ply_records', []):
                    if record.get('side_moved') == player_color:
                        accuracies.append(record.get('accuracy_pct', 0))
            return statistics.mean(accuracies) if accuracies else 0
        
        def get_win_rate_for_tc(tc_games):
            if not tc_games:
                return 0
            wins = sum(1 for g in tc_games if g.get('metadata', {}).get('result') == 'win')
            return wins / len(tc_games) if tc_games else 0
        
        results = []
        for tc, tc_games in time_controls.items():
            if tc_games:
                results.append({
                    'time_control': tc,
                    'accuracy': get_avg_accuracy_for_tc(tc_games),
                    'game_count': len(tc_games),
                    'win_rate': get_win_rate_for_tc(tc_games)
                })
        
        return sorted(results, key=lambda x: x['game_count'], reverse=True)
    
    def _calculate_accuracy_by_time_spent(self, games: List[Dict]) -> List[Dict]:
        """Calculate accuracy based on time spent per move (extracted from PGN clock times)"""
        import re
        
        print(f"   🕐 Analyzing time spent per move for {len(games)} games...")
        
        # Time ranges in seconds: <5s (instant), 5-15s (quick), 15-30s (normal), >30s (deep thought)
        time_ranges = {
            'instant': (0, 5, '<5s'),
            'quick': (5, 15, '5-15s'),
            'normal': (15, 30, '15-30s'),
            'deep': (30, float('inf'), '>30s')
        }
        
        time_data = {key: {'accuracies': [], 'move_count': 0} for key in time_ranges.keys()}
        
        games_with_clock = 0
        for game in games:
            ply_records = game.get('ply_records', [])
            player_color = game.get('metadata', {}).get('player_color', 'white')
            
            # Extract clock times from PGN to calculate time spent per move
            pgn = game.get('pgn', '')
            if not pgn or '[%clk' not in pgn:
                print(f"      ⚠️ Game has no clock data (pgn length: {len(pgn)})")
                continue  # Skip games without clock data
            
            games_with_clock += 1
            
            # Extract all clock times - handle both H:MM:SS and MM:SS formats
            # Pattern matches: [%clk 0:09:58.1] or [%clk 0:09:58] or [%clk 9:58]
            clock_pattern = r'\[%clk\s+(?:(\d+):)?(\d+):(\d+(?:\.\d+)?)\]'
            clock_matches = re.findall(clock_pattern, pgn)
            
            print(f"      📍 Game {games_with_clock}: Found {len(clock_matches)} clock times")
            
            # Convert to seconds
            clock_times = []
            for match in clock_matches:
                h, m, s = match
                h = int(h) if h else 0  # Hours might be empty
                m = int(m)
                s = float(s)
                total_seconds = h * 3600 + m * 60 + s
                clock_times.append(total_seconds)
            
            # Match clock times to player moves
            player_move_idx = 0
            for ply_idx, record in enumerate(ply_records):
                side_moved = record.get('side_moved')
                
                if side_moved == player_color and ply_idx < len(clock_times) - 1:
                    # Calculate time spent: previous_clock - current_clock
                    if ply_idx > 0:
                        time_spent = clock_times[ply_idx - 1] - clock_times[ply_idx]
                    else:
                        time_spent = 0  # First move, no previous clock
                    
                    accuracy = record.get('accuracy_pct', 0)
                    
                    if time_spent >= 0:  # Sanity check
                        # Categorize by time spent
                        for category, (min_time, max_time, _) in time_ranges.items():
                            if min_time <= time_spent < max_time:
                                time_data[category]['accuracies'].append(accuracy)
                                time_data[category]['move_count'] += 1
                                break
        
        print(f"      ✅ Processed {games_with_clock}/{len(games)} games with clock data")
        
        results = []
        for category in ['instant', 'quick', 'normal', 'deep']:
            data = time_data[category]
            if data['move_count'] > 0:
                _, _, display_name = time_ranges[category]
                results.append({
                    'time_range': display_name,
                    'accuracy': statistics.mean(data['accuracies']),
                    'move_count': data['move_count']
                })
                print(f"         {display_name}: {data['move_count']} moves, {statistics.mean(data['accuracies']):.1f}% accuracy")
        
        if not results:
            print(f"      ⚠️ No time-based data found")
        
        return results
    
    def _calculate_tag_preferences(self, games: List[Dict]) -> Dict:
        """
        Calculate tag preference patterns - when player creates or removes tags.
        
        For each tag, tracks:
        - present_accuracy: Accuracy when tag was present before move
        - created_accuracy: Accuracy when player's move created this tag
        - removed_accuracy: Accuracy when player's move removed this tag
        - preference_signal: "seeks" (creates often + low accuracy) or "avoids" (removes often + low accuracy)
        """
        print(f"   🔄 Analyzing tag preferences for {len(games)} games...")
        
        tag_prefs = defaultdict(lambda: {
            'present_accuracies': [],
            'created_accuracies': [],
            'removed_accuracies': [],
            'maintained_accuracies': [],
            'present_count': 0,
            'created_count': 0,
            'removed_count': 0,
            'maintained_count': 0
        })
        
        for game in games:
            ply_records = game.get('ply_records', [])
            player_color = game.get('metadata', {}).get('player_color', 'white')
            
            for record in ply_records:
                if record.get('side_moved') != player_color:
                    continue
                
                acc_raw = record.get('accuracy_pct', 0)
                try:
                    accuracy = float(acc_raw) if acc_raw is not None else 0.0
                except Exception:
                    accuracy = 0.0
                
                # Get tags before and after this move using shared utility
                raw_before_tags = record.get('raw_before', {}).get('tags', [])
                raw_after_tags = record.get('raw_after', {}).get('tags', [])
                tags_before = extract_tag_names(raw_before_tags)
                tags_after = extract_tag_names(raw_after_tags)
                
                # Categorize each tag
                all_tags = tags_before | tags_after
                
                for tag in all_tags:
                    in_before = tag in tags_before
                    in_after = tag in tags_after
                    
                    if in_before:
                        tag_prefs[tag]['present_accuracies'].append(accuracy)
                        tag_prefs[tag]['present_count'] += 1
                    
                    if not in_before and in_after:
                        # Created this tag
                        tag_prefs[tag]['created_accuracies'].append(accuracy)
                        tag_prefs[tag]['created_count'] += 1
                    elif in_before and not in_after:
                        # Removed this tag
                        tag_prefs[tag]['removed_accuracies'].append(accuracy)
                        tag_prefs[tag]['removed_count'] += 1
                    elif in_before and in_after:
                        # Maintained this tag
                        tag_prefs[tag]['maintained_accuracies'].append(accuracy)
                        tag_prefs[tag]['maintained_count'] += 1
        
        # Calculate averages and determine preference signals
        result = {}
        for tag, data in tag_prefs.items():
            total_interactions = data['created_count'] + data['removed_count'] + data['maintained_count']
            if total_interactions < 3:  # Need at least 3 interactions
                continue
            
            present_acc = statistics.mean(data['present_accuracies']) if data['present_accuracies'] else None
            created_acc = statistics.mean(data['created_accuracies']) if data['created_accuracies'] else None
            removed_acc = statistics.mean(data['removed_accuracies']) if data['removed_accuracies'] else None
            maintained_acc = statistics.mean(data['maintained_accuracies']) if data['maintained_accuracies'] else None
            
            # Determine preference signal
            signal = "neutral"
            strength = 0.0
            significant = False
            
            # Calculate creation vs removal ratio
            if data['created_count'] > 0 or data['removed_count'] > 0:
                creation_ratio = data['created_count'] / (data['created_count'] + data['removed_count'] + 0.01)
                
                # "seeks" = creates often AND low creation accuracy (problematic preference)
                if creation_ratio > 0.6 and created_acc is not None and created_acc < 70:
                    signal = "seeks"
                    strength = (1 - created_acc / 100) * creation_ratio
                    significant = strength > 0.3
                
                # "avoids" = removes often AND low removal accuracy (problematic avoidance)
                elif creation_ratio < 0.4 and removed_acc is not None and removed_acc < 70:
                    signal = "avoids"
                    strength = (1 - removed_acc / 100) * (1 - creation_ratio)
                    significant = strength > 0.3
            
            result[tag] = {
                'present_accuracy': round(present_acc, 1) if present_acc else None,
                'present_count': data['present_count'],
                'created_accuracy': round(created_acc, 1) if created_acc else None,
                'created_count': data['created_count'],
                'removed_accuracy': round(removed_acc, 1) if removed_acc else None,
                'removed_count': data['removed_count'],
                'maintained_accuracy': round(maintained_acc, 1) if maintained_acc else None,
                'maintained_count': data['maintained_count'],
                'preference_signal': signal,
                'preference_strength': round(strength, 2),
                'significant': significant
            }
        
        significant_count = sum(1 for v in result.values() if v['significant'])
        print(f"      ✅ Analyzed {len(result)} tag preferences, {significant_count} significant")
        
        return result
    
    def _calculate_performance_by_tags(self, games: List[Dict]) -> Dict:
        """Calculate accuracy for each tag type to identify strengths/weaknesses"""
        print(f"   🏷️  Analyzing performance by tags for {len(games)} games...")
        
        tag_stats = defaultdict(lambda: {'accuracies': [], 'move_count': 0, 'error_count': 0})
        
        total_player_moves = 0
        total_tags_found = 0
        
        for game_idx, game in enumerate(games):
            ply_records = game.get('ply_records', [])
            player_color = game.get('metadata', {}).get('player_color', 'white')
            
            player_moves_in_game = 0
            tags_in_game = 0
            
            for record in ply_records:
                side_moved = record.get('side_moved')
                
                # Only count player's moves
                if side_moved != player_color:
                    continue
                
                player_moves_in_game += 1
                total_player_moves += 1
                
                accuracy = record.get('accuracy_pct', 0)
                quality = record.get('quality', '')
                category = record.get('category', '')  # Also check category field
                # Use shared extract_tags function
                tags = extract_tags(record)
                
                if tags:
                    tags_in_game += len(tags)
                    total_tags_found += len(tags)
                
                # Process each tag
                for tag_name in tags:
                    if not tag_name:
                        continue
                    
                    tag_stats[tag_name]['accuracies'].append(accuracy)
                    tag_stats[tag_name]['move_count'] += 1
                    
                    # Count errors (mistakes, blunders, inaccuracies)
                    if quality in ['mistake', 'blunder', 'inaccuracy'] or category in ['mistake', 'blunder', 'inaccuracy']:
                        tag_stats[tag_name]['error_count'] += 1
            
            print(f"      Game {game_idx+1}: {player_moves_in_game} player moves, {tags_in_game} total tags")
        
        print(f"      📊 Total: {total_player_moves} player moves, {total_tags_found} tags found")
        print(f"      📊 Unique tag types: {len(tag_stats)}")
        
        # Calculate averages and error rates for ALL tags (no min filter)
        all_tag_results = []
        for tag, stats in tag_stats.items():
            if stats['move_count'] > 0:  # Include all tags with any occurrences
                accs = [a for a in (stats['accuracies'] or []) if a is not None]
                avg_accuracy = statistics.mean(accs) if accs else 0.0
                error_rate = (stats['error_count'] / stats['move_count']) * 100 if stats['move_count'] > 0 else 0
                
                all_tag_results.append({
                    'tag': tag,
                    'accuracy': avg_accuracy,
                    'move_count': stats['move_count'],
                    'error_count': stats['error_count'],
                    'error_rate': error_rate
                })
        
        # Sort by accuracy to find strengths and weaknesses
        sorted_by_accuracy = sorted(all_tag_results, key=lambda x: x['accuracy'], reverse=True)
        
        # Filter for summary: only tags with 5+ occurrences
        filtered_for_summary = [t for t in sorted_by_accuracy if t['move_count'] >= 5]
        
        # Get top 5 best and worst performing tags (from filtered)
        top_performing = filtered_for_summary[:5] if filtered_for_summary else sorted_by_accuracy[:5]
        bottom_performing = filtered_for_summary[-5:] if filtered_for_summary else sorted_by_accuracy[-5:]
        
        # Calculate tag preferences
        tag_preferences = self._calculate_tag_preferences(games)
        
        print(f"      ✅ Analyzed {len(all_tag_results)} total tags, {len(filtered_for_summary)} with 5+ occurrences")
        if top_performing:
            print(f"         Best: {top_performing[0]['tag']} ({float(top_performing[0].get('accuracy', 0.0) or 0.0):.1f}%)")
        if bottom_performing:
            print(f"         Worst: {bottom_performing[0]['tag']} ({float(bottom_performing[0].get('accuracy', 0.0) or 0.0):.1f}%)")
        
        return {
            'top_performing': top_performing,
            'bottom_performing': bottom_performing,
            'all_tags': sorted_by_accuracy,  # ALL tags, no filter
            'tag_preferences': tag_preferences  # NEW: Tag preference tracking
        }
    
    def _calculate_theme_frequency(self, games: List[Dict]) -> List[Dict]:
        """Calculate most common themes across all games with weakness classification"""
        theme_stats = defaultdict(lambda: {"occurrence_count": 0, "error_count": 0})
        
        for game in games:
            ply_records = game.get("ply_records", [])
            
            for record in ply_records:
                quality = record.get("quality", "")
                is_error = quality in ["blunder", "mistake", "inaccuracy"]
                
                # Use shared extract_tags function
                tags = extract_tags(record)
                
                for tag_name in tags:
                    # Extract theme name from tag (e.g., "tactic.fork" -> "fork")
                    theme_name = tag_name.split(".")[-1] if "." in tag_name else tag_name
                    if theme_name:  # Only count non-empty theme names
                        theme_stats[theme_name]["occurrence_count"] += 1
                        if is_error:
                            theme_stats[theme_name]["error_count"] += 1
        
        result = []
        for theme, stats in theme_stats.items():
            error_rate = stats["error_count"] / stats["occurrence_count"] if stats["occurrence_count"] > 0 else 0
            
            # Classify weakness level
            if error_rate > 0.4:  # 40%+ error rate
                weakness_level = 'critical'
            elif error_rate > 0.25:  # 25%+ error rate
                weakness_level = 'moderate'
            else:
                weakness_level = 'minor'
            
            result.append({
                "name": theme,
                "frequency": stats["occurrence_count"],
                "error_count": stats["error_count"],
                "error_rate": error_rate,
                "weakness_level": weakness_level
            })
        
        # Sort by frequency descending
        result.sort(key=lambda x: x["frequency"], reverse=True)
        return result
    
    def _calculate_phase_stats(self, games: List[Dict]) -> Dict:
        """Calculate statistics by game phase"""
        phase_data = {
            "opening": {"accuracies": [], "cp_losses": [], "count": 0},
            "middlegame": {"accuracies": [], "cp_losses": [], "count": 0},
            "endgame": {"accuracies": [], "cp_losses": [], "count": 0}
        }
        
        total_player_moves = 0
        for game in games:
            ply_records = game.get("ply_records", [])
            player_color = game.get("metadata", {}).get("player_color", "white")
            
            print(f"    Phase stats - Game has {len(ply_records)} ply records, player is {player_color}")
            
            for record in ply_records:
                side_moved = record.get("side_moved")
                if side_moved == player_color:
                    total_player_moves += 1
                    phase = record.get("phase", "middlegame")
                    accuracy = record.get("accuracy_pct", 0)
                    cp_loss = record.get("cp_loss", 0)
                    
                    if phase in phase_data:
                        phase_data[phase]["accuracies"].append(accuracy)
                        phase_data[phase]["cp_losses"].append(cp_loss)
                        phase_data[phase]["count"] += 1
            
        print(f"    Total player moves found: {total_player_moves}")
        print(f"    Opening moves: {len(phase_data['opening']['accuracies'])}")
        print(f"    Middlegame moves: {len(phase_data['middlegame']['accuracies'])}")
        print(f"    Endgame moves: {len(phase_data['endgame']['accuracies'])}")
        
        result = {}
        for phase, data in phase_data.items():
            if data["count"] > 0:
                result[phase] = {
                    "accuracy": statistics.mean(data["accuracies"]),
                    "avg_cp_loss": statistics.mean(data["cp_losses"]),
                    "move_count": data["count"]
                }
            else:
                result[phase] = {
                    "accuracy": None,  # Handle as NA in UI
                    "avg_cp_loss": None,
                    "move_count": 0
                }
        
        return result
    
    def _calculate_win_rate_by_phase(self, games: List[Dict]) -> Dict:
        """Calculate win rate based on performance in each phase"""
        # Count wins/losses where player had good performance in each phase
        phase_results = {
            "opening": {"wins": 0, "total": 0},
            "middlegame": {"wins": 0, "total": 0},
            "endgame": {"wins": 0, "total": 0}
        }
        
        for game in games:
            result = game.get("metadata", {}).get("result", "unknown")
            player_color = game.get("metadata", {}).get("player_color", "white")
            
            # Determine if player won
            player_won = False
            if result == "win":
                player_won = True
            elif result == "loss":
                player_won = False
            else:
                # Draw or unknown - skip
                continue
            
            # Count this game for all phases it had moves in
            ply_records = game.get("ply_records", [])
            phases_seen = set()
            
            for record in ply_records:
                if record.get("side_moved") == player_color:
                    phase = record.get("phase", "middlegame")
                    if phase in phase_results:
                        phases_seen.add(phase)
            
            # Add win/loss to each phase that had moves
            for phase in phases_seen:
                phase_results[phase]["total"] += 1
                if player_won:
                    phase_results[phase]["wins"] += 1
        
        # Calculate percentages
        return {
            phase: (stats["wins"] / stats["total"] * 100) if stats["total"] > 0 else 50.0
            for phase, stats in phase_results.items()
        }
    
    def _calculate_mistake_patterns(self, games: List[Dict]) -> Dict:
        """Analyze mistake patterns"""
        patterns = {
            "blunders_in_time_trouble": 0,
            "mistakes_after_opponent_blunder": 0,
            "repeated_opening_mistakes": defaultdict(int),
            "phase_with_most_mistakes": {"opening": 0, "middlegame": 0, "endgame": 0}
        }
        
        for game in games:
            ply_records = game.get("ply_records", [])
            player_color = game.get("metadata", {}).get("player_color", "white")
            
            for record in ply_records:
                if record.get("side_moved") == player_color:
                    category = record.get("category", "")
                    phase = record.get("phase", "middlegame")
                    
                    if category in ["mistake", "blunder"]:
                        patterns["phase_with_most_mistakes"][phase] += 1
                    
                    # Check if in time trouble (< 10 seconds)
                    time_spent = record.get("time_spent_s", 0)
                    if time_spent is not None and time_spent < 10 and category == "blunder":
                        patterns["blunders_in_time_trouble"] += 1
        
        return patterns
    
    def _calculate_time_management(self, games: List[Dict]) -> Dict:
        """Analyze time management statistics"""
        time_data = {
            "avg_time_per_move": [],
            "time_by_phase": {
                "opening": [],
                "middlegame": [],
                "endgame": []
            },
            "fast_move_accuracy": [],  # Moves under 5 seconds
            "slow_move_accuracy": []   # Moves over 30 seconds
        }
        
        for game in games:
            ply_records = game.get("ply_records", [])
            player_color = game.get("metadata", {}).get("player_color", "white")
            
            for record in ply_records:
                if record.get("side_moved") == player_color:
                    time_spent = record.get("time_spent_s")
                    if time_spent is not None and time_spent > 0:
                        time_data["avg_time_per_move"].append(time_spent)
                        
                        phase = record.get("phase", "middlegame")
                        time_data["time_by_phase"][phase].append(time_spent)
                        
                        accuracy = record.get("accuracy_pct", 0)
                        if time_spent < 5:
                            time_data["fast_move_accuracy"].append(accuracy)
                        elif time_spent > 30:
                            time_data["slow_move_accuracy"].append(accuracy)
        
        return {
            "avg_time_per_move": statistics.mean(time_data["avg_time_per_move"]) if time_data["avg_time_per_move"] else 0,
            "avg_time_opening": statistics.mean(time_data["time_by_phase"]["opening"]) if time_data["time_by_phase"]["opening"] else 0,
            "avg_time_middlegame": statistics.mean(time_data["time_by_phase"]["middlegame"]) if time_data["time_by_phase"]["middlegame"] else 0,
            "avg_time_endgame": statistics.mean(time_data["time_by_phase"]["endgame"]) if time_data["time_by_phase"]["endgame"] else 0,
            "fast_move_accuracy": statistics.mean(time_data["fast_move_accuracy"]) if time_data["fast_move_accuracy"] else 0,
            "slow_move_accuracy": statistics.mean(time_data["slow_move_accuracy"]) if time_data["slow_move_accuracy"] else 0
        }
    
    def _calculate_advanced_metrics(self, games: List[Dict]) -> Dict:
        """Calculate advanced performance metrics"""
        metrics = {
            "tactical_complexity_index": 0,
            "positional_consistency_index": 0,
            "conversion_rate": 0,
            "recovery_rate": 0,
            "overpress_ratio": 0
        }
        
        # Tactical Complexity Index: avg threat tags per 10 plies
        threat_count = 0
        total_plies = 0
        
        # Conversion Rate: fraction of games converting +200 eval to wins
        games_with_advantage = 0
        conversions = 0
        
        for game in games:
            ply_records = game.get("ply_records", [])
            result = game.get("metadata", {}).get("result", "unknown")
            player_color = game.get("metadata", {}).get("player_color", "white")
            
            had_winning_advantage = False
            
            for record in ply_records:
                total_plies += 1
                
                # Count threat tags using shared extract_tags function
                tags = extract_tags(record)
                
                for tag_name in tags:
                    if "threat" in tag_name.lower():
                        threat_count += 1
                
                # Check for winning advantage (player perspective)
                eval_cp = record.get("engine", {}).get("played_eval_after_cp", 0)
                if player_color == "white" and eval_cp >= 200:
                    had_winning_advantage = True
                elif player_color == "black" and eval_cp <= -200:
                    had_winning_advantage = True
            
            if had_winning_advantage:
                games_with_advantage += 1
                if result == "win":
                    conversions += 1
        
        if total_plies > 0:
            metrics["tactical_complexity_index"] = (threat_count / total_plies) * 10
        
        if games_with_advantage > 0:
            metrics["conversion_rate"] = (conversions / games_with_advantage) * 100
        
        return metrics
    
    def _calculate_critical_moments(self, games: List[Dict]) -> Dict:
        """Analyze performance in critical positions (large eval swings)"""
        print(f"      🔥 Analyzing critical moments...")
        
        critical_positions = []
        
        for game in games:
            ply_records = game.get("ply_records", [])
            player_color = game.get("metadata", {}).get("player_color", "white")
            
            prev_eval = None
            for record in ply_records:
                side_moved = record.get("side_moved")
                if side_moved != player_color:
                    continue
                
                eval_after = record.get("eval_after_cp", 0)
                eval_before = record.get("eval_before_cp", 0)
                
                # Check if this is a critical moment (±200cp swing threshold)
                if prev_eval is not None:
                    eval_swing = abs(eval_after - prev_eval)
                    if eval_swing >= 200:
                        acc_raw = record.get('accuracy_pct', 0)
                        try:
                            acc_f = float(acc_raw) if acc_raw is not None else 0.0
                        except Exception:
                            acc_f = 0.0
                        critical_positions.append({
                            'eval_before': eval_before,
                            'eval_after': eval_after,
                            'accuracy': acc_f,
                            'quality': record.get('quality', ''),
                            'san': record.get('san', '')
                        })
                
                prev_eval = eval_after
        
        if not critical_positions:
            return {
                'total_critical': 0,
                'avg_accuracy': 0,
                'positions_held': 0,
                'positions_lost': 0
            }
        
        total_critical = len(critical_positions)
        accs = [p.get('accuracy', 0.0) for p in critical_positions]
        accs = [a for a in accs if a is not None]
        avg_accuracy = statistics.mean(accs) if accs else 0.0
        
        # Count how many critical positions were handled well (accuracy > 80%)
        positions_held = sum(1 for p in critical_positions if (p.get('accuracy') or 0.0) > 80)
        positions_lost = total_critical - positions_held
        
        print(f"         Found {total_critical} critical moments, {float(avg_accuracy):.1f}% avg accuracy")
        
        return {
            'total_critical': total_critical,
            'avg_accuracy': avg_accuracy,
            'positions_held': positions_held,
            'positions_lost': positions_lost,
            'hold_rate': (positions_held / total_critical * 100) if total_critical > 0 else 0
        }
    
    def _calculate_advantage_conversion(self, games: List[Dict]) -> Dict:
        """Analyze ability to convert winning positions to wins"""
        print(f"      👑 Analyzing advantage conversion...")
        
        winning_positions = 0
        conversions = 0
        squandered = 0
        avg_advantage_size = []
        
        for game in games:
            ply_records = game.get("ply_records", [])
            player_color = game.get("metadata", {}).get("player_color", "white")
            result = game.get("metadata", {}).get("result", "unknown")
            
            # Check if player ever had a winning advantage (>200cp)
            had_winning_advantage = False
            max_advantage = 0
            
            for record in ply_records:
                if record.get("side_moved") != player_color:
                    continue
                
                eval_after = record.get("eval_after_cp", 0)
                
                # Adjust for player color (positive = good for white)
                if player_color == "black":
                    eval_after = -eval_after
                
                if eval_after > 200:
                    had_winning_advantage = True
                    max_advantage = max(max_advantage, eval_after)
            
            if had_winning_advantage:
                winning_positions += 1
                avg_advantage_size.append(max_advantage)
                
                if result == "win":
                    conversions += 1
                else:
                    squandered += 1
        
        conversion_rate = (conversions / winning_positions * 100) if winning_positions > 0 else 0
        avg_adv = statistics.mean(avg_advantage_size) if avg_advantage_size else 0
        
        print(f"         {conversions}/{winning_positions} winning positions converted ({conversion_rate:.1f}%)")
        
        return {
            'winning_positions': winning_positions,
            'conversions': conversions,
            'squandered': squandered,
            'conversion_rate': conversion_rate,
            'avg_advantage_size': avg_adv
        }
    
    def _calculate_blunder_triggers(self, games: List[Dict]) -> Dict:
        """Identify what triggers blunders and mistakes"""
        print(f"      ⚠️  Analyzing blunder triggers...")
        
        triggers = {
            'time_pressure': 0,  # <30s remaining
            'after_opponent_mistake': 0,
            'complex_positions': 0,  # 6+ pieces active
            'simple_positions': 0,  # <4 pieces active
            'total_blunders': 0
        }
        
        for game in games:
            ply_records = game.get("ply_records", [])
            player_color = game.get("metadata", {}).get("player_color", "white")
            
            prev_opponent_quality = None
            
            for i, record in enumerate(ply_records):
                side_moved = record.get("side_moved")
                quality = record.get("quality", "")
                
                if side_moved == player_color and quality in ["blunder", "mistake"]:
                    triggers['total_blunders'] += 1
                    
                    # Check time pressure (if available)
                    time_spent = record.get("time_spent_s", 0)
                    if time_spent and time_spent < 10:
                        triggers['time_pressure'] += 1
                    
                    # Check if after opponent's mistake
                    if prev_opponent_quality in ["blunder", "mistake"]:
                        triggers['after_opponent_mistake'] += 1
                    
                    # Check position complexity (count pieces from tags)
                    tags = extract_tags(record)
                    piece_count = sum(1 for tag_name in tags if 'piece' in tag_name.lower())
                    
                    if piece_count >= 6:
                        triggers['complex_positions'] += 1
                    elif piece_count <= 3:
                        triggers['simple_positions'] += 1
                
                # Track opponent's last move quality
                if side_moved != player_color:
                    prev_opponent_quality = quality
        
        # Calculate percentages
        total = triggers['total_blunders']
        result = {
            'total_blunders': total,
            'time_pressure_pct': (triggers['time_pressure'] / total * 100) if total > 0 else 0,
            'after_opponent_mistake_pct': (triggers['after_opponent_mistake'] / total * 100) if total > 0 else 0,
            'complex_positions_pct': (triggers['complex_positions'] / total * 100) if total > 0 else 0,
            'simple_positions_pct': (triggers['simple_positions'] / total * 100) if total > 0 else 0
        }
        
        print(f"         {total} total errors: time={result['time_pressure_pct']:.0f}%, complex={result['complex_positions_pct']:.0f}%")
        
        return result
    
    def _calculate_piece_activity(self, games: List[Dict]) -> List[Dict]:
        """Analyze accuracy by piece type moved"""
        print(f"      ♟️  Analyzing piece activity...")
        
        piece_stats = defaultdict(lambda: {'accuracies': [], 'move_count': 0, 'error_count': 0})
        
        for game in games:
            ply_records = game.get("ply_records", [])
            player_color = game.get("metadata", {}).get("player_color", "white")
            
            for record in ply_records:
                if record.get("side_moved") != player_color:
                    continue
                
                san = record.get("san", "")
                accuracy = record.get("accuracy_pct", 0)
                quality = record.get("quality", "")
                
                # Identify piece type from SAN
                piece_type = None
                if san:
                    first_char = san[0]
                    if first_char == 'K':
                        piece_type = 'King'
                    elif first_char == 'Q':
                        piece_type = 'Queen'
                    elif first_char == 'R':
                        piece_type = 'Rook'
                    elif first_char == 'B':
                        piece_type = 'Bishop'
                    elif first_char == 'N':
                        piece_type = 'Knight'
                    elif first_char in 'abcdefgh' or first_char.islower():
                        piece_type = 'Pawn'
                    elif first_char == 'O':
                        piece_type = 'Castling'
                
                if piece_type:
                    piece_stats[piece_type]['accuracies'].append(accuracy)
                    piece_stats[piece_type]['move_count'] += 1
                    
                    if quality in ['mistake', 'blunder', 'inaccuracy']:
                        piece_stats[piece_type]['error_count'] += 1
        
        # Calculate averages
        results = []
        # All pieces, even if 0 moves
        all_pieces = ['Pawn', 'Knight', 'Bishop', 'Rook', 'Queen', 'King']
        for piece in all_pieces:
            stats = piece_stats.get(piece, {'accuracies': [], 'move_count': 0, 'error_count': 0})
            if stats['move_count'] > 0:
                avg_accuracy = statistics.mean(stats['accuracies'])
                error_rate = (stats['error_count'] / stats['move_count']) * 100
                
                results.append({
                    'piece': piece,
                    'accuracy': avg_accuracy,
                    'move_count': stats['move_count'],
                    'error_count': stats['error_count'],
                    'error_rate': error_rate
                })
            else:
                results.append({
                    'piece': piece,
                    'accuracy': None, # NA
                    'move_count': 0,
                    'error_count': 0,
                    'error_rate': None
                })
        
        # Sort by accuracy (handle None)
        results = sorted(results, key=lambda x: x['accuracy'] if x['accuracy'] is not None else -1, reverse=True)
        
        if results:
            print(f"         Best: {results[0]['piece']} ({float(results[0].get('accuracy', 0.0) or 0.0):.1f}%)")
            print(f"         Worst: {results[-1]['piece']} ({float(results[-1].get('accuracy', 0.0) or 0.0):.1f}%)")
        
        return results
    
    def _compare_cohorts(self, games: List[Dict], cohorts: List[Dict]) -> Dict:
        """Compare statistics between different cohorts"""
        cohort_results = {}
        
        for cohort in cohorts:
            label = cohort.get("label", "Cohort")
            filters = cohort.get("filters", {})
            
            # Filter games for this cohort using GameFilter
            cohort_games = GameFilter.apply_filters(games, filters)
            
            if cohort_games:
                cohort_results[label] = self._calculate_summary(cohort_games)
        
        return cohort_results

    def _calculate_tilt_points(self, games: List[Dict]) -> List[Dict]:
        """Calculate raw (time, accuracy) points for scatter plot"""
        points = []
        for game in games:
            player_color = game.get("metadata", {}).get("player_color", "white")
            for record in game.get("ply_records", []):
                if record.get("side_moved") == player_color:
                    time = record.get("time_spent_s")
                    acc = record.get("accuracy_pct")
                    if time is not None and acc is not None:
                        points.append({"time": time, "accuracy": acc})
        
        # Limit to last 500 moves for performance
        return points[-500:]

    def _calculate_diagnostic_insights(self, games: List[Dict], global_avg: float) -> List[Dict]:
        """Apply relevance formula to identify significant weak/strong points"""
        import math
        
        tag_stats = defaultdict(lambda: {"accuracies": [], "count": 0})
        total_moves = 0
        
        for game in games:
            player_color = game.get("metadata", {}).get("player_color", "white")
            for record in game.get("ply_records", []):
                if record.get("side_moved") == player_color:
                    total_moves += 1
                    tags = extract_tags(record)
                    acc = record.get("accuracy_pct", 0)
                    for tag_name in tags:
                        if tag_name:
                            tag_stats[tag_name]["accuracies"].append(acc)
                            tag_stats[tag_name]["count"] += 1
        
        if not total_moves:
            return []
            
        insights = []
        for tag, data in tag_stats.items():
            if data["count"] < 3:
                continue
                
            tag_avg = statistics.mean(data["accuracies"])
            
            # relevance = (ABS(group_avg - global_avg) * 0.75) + (LOG(count + 1) / LOG(total_count + 1) * 0.25)
            relevance = (abs(tag_avg - global_avg) * 0.75) + (math.log(data["count"] + 1) / math.log(total_moves + 1) * 0.25)
            
            insights.append({
                "tag": tag,
                "count": data["count"],
                "accuracy": tag_avg,
                "relevance": relevance,
                "type": "strength" if tag_avg > global_avg else "weakness"
            })
            
        # Sort by relevance
        insights.sort(key=lambda x: x["relevance"], reverse=True)
        return insights[:15]

