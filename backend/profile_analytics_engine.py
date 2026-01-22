"""
Profile Analytics Engine
Comprehensive chess performance analytics with lifetime tracking, pattern recognition,
and advanced strength analysis.
"""

from typing import Dict, List, Optional, Any, Tuple, Set
from collections import defaultdict, Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import statistics
import math
import re


@dataclass
class LifetimePerformance:
    """Comprehensive lifetime performance data"""
    total_games: int = 0
    win_rate: float = 0.0
    draw_rate: float = 0.0
    loss_rate: float = 0.0
    average_rating: float = 0.0
    rating_progression: List[Dict[str, Any]] = field(default_factory=list)
    improvement_velocity: float = 0.0  # Rating points per month
    consistency_score: float = 0.0  # Lower variance = higher consistency
    peak_rating: float = 0.0
    peak_rating_date: Optional[str] = None
    time_control_stats: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    phase_performance: Dict[str, Dict[str, Any]] = field(default_factory=dict)


@dataclass
class AdvancedPatterns:
    """Advanced pattern recognition beyond basic habits"""
    opening_repertoire: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    time_management_patterns: Dict[str, Any] = field(default_factory=dict)
    opponent_analysis: Dict[str, Any] = field(default_factory=dict)
    common_mistakes: List[Dict[str, Any]] = field(default_factory=list)
    winning_methods: List[Dict[str, Any]] = field(default_factory=list)
    losing_patterns: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class StrengthProfile:
    """Advanced strength and weakness analysis"""
    tactical_strength: float = 0.0
    positional_strength: float = 0.0
    calculation_depth: float = 0.0
    endgame_proficiency: float = 0.0
    time_pressure_performance: float = 0.0
    piece_specific_performance: Dict[str, float] = field(default_factory=dict)
    phase_specific_skills: Dict[str, float] = field(default_factory=dict)
    strength_categories: List[str] = field(default_factory=list)
    weakness_categories: List[str] = field(default_factory=list)


@dataclass
class TrainingRecommendations:
    """Personalized training recommendations"""
    priority_drills: List[Dict[str, Any]] = field(default_factory=list)
    opening_study: List[str] = field(default_factory=list)
    tactical_training: Dict[str, Any] = field(default_factory=dict)
    positional_improvement: List[str] = field(default_factory=list)
    time_management: Dict[str, Any] = field(default_factory=dict)
    endgame_focus: List[str] = field(default_factory=list)


class ProfileAnalyticsEngine:
    """
    Comprehensive chess performance analytics engine.

    Features:
    - Lifetime performance tracking with rating progression
    - Advanced pattern recognition (openings, time, opponents)
    - Strength/weakness analysis with tactical vs positional metrics
    - Opening repertoire analysis with ECO codes
    - Training plan generation from insights
    """

    def __init__(self, supabase_client, profile_indexer=None):
        self.supabase = supabase_client
        self.profile_indexer = profile_indexer

        # Database optimization limits
        self.db_limits = {
            'max_games_per_query': 100,
            'lifetime_sample_size': 200,
            'pattern_min_occurrences': 3,
            'cache_ttl_hours': 24,
            'recent_games_limit': 50
        }

        # Analysis thresholds
        self.thresholds = {
            'min_games_for_trend': 10,
            'min_games_for_pattern': 5,
            'significant_improvement': 50,  # Rating points
            'consistency_threshold': 100,  # Rating variance
        }

    def analyze_lifetime_performance(self, user_id: str) -> LifetimePerformance:
        """
        Comprehensive career analysis with rating trends, improvement velocity, consistency.
        """
        # Get sample of games for analysis (not all games to avoid DB overload)
        games = self.supabase.get_active_reviewed_games(
            user_id,
            limit=self.db_limits['lifetime_sample_size']
        )

        if not games:
            return LifetimePerformance()

        # Group games by date for rating progression
        games_by_date = self._group_games_by_date(games)

        # Calculate rating progression
        rating_progression = self._calculate_rating_progression(games_by_date)

        # Calculate lifetime stats
        total_games = len(games)
        win_rate, draw_rate, loss_rate = self._calculate_win_rates(games)

        # Calculate improvement metrics
        improvement_velocity = self._calculate_improvement_velocity(rating_progression)
        consistency_score = self._calculate_consistency_score(rating_progression)

        # Find peak rating
        peak_rating, peak_date = self._find_peak_rating(rating_progression)

        # Analyze by time control
        time_control_stats = self._analyze_time_control_performance(games)

        # Analyze by game phase
        phase_performance = self._analyze_phase_performance(games)

        # Calculate average rating
        average_rating = self._calculate_average_rating(games)

        return LifetimePerformance(
            total_games=total_games,
            win_rate=win_rate,
            draw_rate=draw_rate,
            loss_rate=loss_rate,
            average_rating=average_rating,
            rating_progression=rating_progression,
            improvement_velocity=improvement_velocity,
            consistency_score=consistency_score,
            peak_rating=peak_rating,
            peak_rating_date=peak_date,
            time_control_stats=time_control_stats,
            phase_performance=phase_performance
        )

    def identify_patterns_and_habits(self, user_id: str, game_window_manager=None) -> AdvancedPatterns:
        """
        Advanced pattern recognition beyond basic habits.
        Uses both active (full detail) and compressed (pattern-only) games.
        """
        # Get active games (full details)
        games = self.supabase.get_active_reviewed_games(
            user_id,
            limit=60,
            include_compressed=False
        )
        
        # Get compressed games (pattern_summary only) if window manager is available
        if game_window_manager:
            compressed_games_raw = game_window_manager.get_compressed_games(user_id)
            compressed_games = [
                game_window_manager.expand_pattern_summary(cg) 
                for cg in compressed_games_raw
            ]
            games = games + compressed_games

        if not games:
            return AdvancedPatterns()

        # Analyze opening repertoire
        opening_repertoire = self._analyze_opening_repertoire(games)

        # Analyze time management patterns
        time_management_patterns = self._analyze_time_management(games)

        # Analyze opponent performance
        opponent_analysis = self._analyze_opponent_performance(games)

        # Identify common mistakes and winning methods
        common_mistakes = self._identify_common_mistakes(games)
        winning_methods = self._identify_winning_methods(games)
        losing_patterns = self._identify_losing_patterns(games)

        return AdvancedPatterns(
            opening_repertoire=opening_repertoire,
            time_management_patterns=time_management_patterns,
            opponent_analysis=opponent_analysis,
            common_mistakes=common_mistakes,
            winning_methods=winning_methods,
            losing_patterns=losing_patterns
        )

    def calculate_advanced_strengths(self, user_id: str) -> StrengthProfile:
        """
        Calculate advanced strength profile with tactical vs positional analysis.
        """
        games = self.supabase.get_active_reviewed_games(
            user_id,
            limit=self.db_limits['max_games_per_query']
        )

        if not games:
            return StrengthProfile()

        # Analyze tactical strength (blunders, missed tactics)
        tactical_strength = self._analyze_tactical_strength(games)

        # Analyze positional strength (long-term planning, structure)
        positional_strength = self._analyze_positional_strength(games)

        # Analyze calculation depth
        calculation_depth = self._analyze_calculation_depth(games)

        # Analyze endgame proficiency
        endgame_proficiency = self._analyze_endgame_proficiency(games)

        # Analyze time pressure performance
        time_pressure_performance = self._analyze_time_pressure_performance(games)

        # Analyze piece-specific performance
        piece_specific_performance = self._analyze_piece_performance(games)

        # Analyze phase-specific skills
        phase_specific_skills = self._analyze_phase_skills(games)

        # Categorize strengths and weaknesses
        strength_categories, weakness_categories = self._categorize_strengths_and_weaknesses(
            tactical_strength, positional_strength, calculation_depth,
            endgame_proficiency, time_pressure_performance
        )

        return StrengthProfile(
            tactical_strength=tactical_strength,
            positional_strength=positional_strength,
            calculation_depth=calculation_depth,
            endgame_proficiency=endgame_proficiency,
            time_pressure_performance=time_pressure_performance,
            piece_specific_performance=piece_specific_performance,
            phase_specific_skills=phase_specific_skills,
            strength_categories=strength_categories,
            weakness_categories=weakness_categories
        )

    def generate_training_plan(self, user_id: str, strengths: StrengthProfile,
                             patterns: AdvancedPatterns) -> TrainingRecommendations:
        """
        Generate personalized training recommendations based on analysis.
        """
        # Generate priority drills based on weaknesses
        priority_drills = self._generate_priority_drills(strengths, patterns)

        # Recommend opening study based on repertoire gaps
        opening_study = self._recommend_opening_study(patterns)

        # Generate tactical training plan
        tactical_training = self._generate_tactical_training(strengths, patterns)

        # Recommend positional improvement areas
        positional_improvement = self._recommend_positional_training(strengths)

        # Generate time management training
        time_management = self._generate_time_management_training(patterns)

        # Recommend endgame focus areas
        endgame_focus = self._recommend_endgame_training(strengths)

        return TrainingRecommendations(
            priority_drills=priority_drills,
            opening_study=opening_study,
            tactical_training=tactical_training,
            positional_improvement=positional_improvement,
            time_management=time_management,
            endgame_focus=endgame_focus
        )

    # ============================================================================
    # LIFETIME PERFORMANCE METHODS
    # ============================================================================

    def _group_games_by_date(self, games: List[Dict]) -> Dict[str, List[Dict]]:
        """Group games by date for rating progression analysis."""
        games_by_date = defaultdict(list)
        for game in games:
            date_str = self._extract_game_date(game)
            games_by_date[date_str].append(game)
        return dict(games_by_date)

    def _calculate_rating_progression(self, games_by_date: Dict[str, List[Dict]]) -> List[Dict[str, Any]]:
        """Calculate rating progression over time."""
        progression = []
        sorted_dates = sorted(games_by_date.keys())

        for date in sorted_dates:
            games_on_date = games_by_date[date]
            ratings = []

            for game in games_on_date:
                rating = self._extract_player_rating(game)
                if rating:
                    ratings.append(rating)

            if ratings:
                avg_rating = statistics.mean(ratings)
                progression.append({
                    'date': date,
                    'rating': round(avg_rating, 1),
                    'games_count': len(ratings),
                    'rating_range': {
                        'min': min(ratings),
                        'max': max(ratings)
                    } if len(ratings) > 1 else None
                })

        return progression

    def _calculate_improvement_velocity(self, rating_progression: List[Dict]) -> float:
        """Calculate rating improvement velocity in points per month."""
        if len(rating_progression) < self.thresholds['min_games_for_trend']:
            return 0.0

        # Calculate linear regression slope
        x_values = list(range(len(rating_progression)))
        y_values = [p['rating'] for p in rating_progression]

        if len(x_values) < 2:
            return 0.0

        # Simple linear regression
        n = len(x_values)
        sum_x = sum(x_values)
        sum_y = sum(y_values)
        sum_xy = sum(x * y for x, y in zip(x_values, y_values))
        sum_x_squared = sum(x * x for x in x_values)

        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x_squared - sum_x * sum_x)

        # Convert to points per month (assuming roughly monthly spacing)
        return round(slope * 30, 2)  # Rough estimate

    def _calculate_consistency_score(self, rating_progression: List[Dict]) -> float:
        """Calculate consistency score (0-100, higher = more consistent)."""
        if len(rating_progression) < self.thresholds['min_games_for_trend']:
            return 50.0  # Neutral score

        ratings = [p['rating'] for p in rating_progression]
        if len(ratings) < 2:
            return 50.0

        # Calculate coefficient of variation (lower = more consistent)
        mean_rating = statistics.mean(ratings)
        std_dev = statistics.stdev(ratings)

        if mean_rating == 0:
            return 50.0

        coefficient_of_variation = (std_dev / mean_rating) * 100

        # Convert to 0-100 scale (lower variation = higher score)
        consistency_score = max(0, 100 - coefficient_of_variation)

        return round(consistency_score, 1)

    def _find_peak_rating(self, rating_progression: List[Dict]) -> Tuple[float, Optional[str]]:
        """Find peak rating and date."""
        if not rating_progression:
            return 0.0, None

        peak_rating = max(p['rating'] for p in rating_progression)
        peak_entry = next((p for p in rating_progression if p['rating'] == peak_rating), None)

        return peak_rating, peak_entry['date'] if peak_entry else None

    def _analyze_time_control_performance(self, games: List[Dict]) -> Dict[str, Dict[str, Any]]:
        """Analyze performance by time control."""
        time_control_stats = defaultdict(lambda: {
            'games': 0, 'wins': 0, 'draws': 0, 'losses': 0, 'win_rate': 0.0
        })

        for game in games:
            time_control = self._extract_time_control(game)
            result = self._extract_game_result(game)

            if time_control and result:
                stats = time_control_stats[time_control]
                stats['games'] += 1

                if result == 'win':
                    stats['wins'] += 1
                elif result == 'draw':
                    stats['draws'] += 1
                else:
                    stats['losses'] += 1

        # Calculate win rates
        for tc, stats in time_control_stats.items():
            if stats['games'] > 0:
                stats['win_rate'] = round((stats['wins'] / stats['games']) * 100, 1)

        return dict(time_control_stats)

    def _analyze_phase_performance(self, games: List[Dict]) -> Dict[str, Dict[str, Any]]:
        """Analyze performance by game phase."""
        phase_stats = {
            'opening': {'games': 0, 'avg_accuracy': 0.0, 'accuracies': []},
            'middlegame': {'games': 0, 'avg_accuracy': 0.0, 'accuracies': []},
            'endgame': {'games': 0, 'avg_accuracy': 0.0, 'accuracies': []}
        }

        for game in games:
            game_review = game.get('game_review', {})
            stats = game_review.get('stats', {})
            by_phase = stats.get('by_phase', {})

            for phase in ['opening', 'middlegame', 'endgame']:
                phase_data = by_phase.get(phase, {})
                accuracy = phase_data.get('accuracy')

                if accuracy is not None:
                    phase_stats[phase]['accuracies'].append(accuracy)
                    phase_stats[phase]['games'] += 1

        # Calculate averages
        for phase, stats in phase_stats.items():
            if stats['accuracies']:
                stats['avg_accuracy'] = round(statistics.mean(stats['accuracies']), 1)
            del stats['accuracies']  # Remove raw data

        return phase_stats

    # ============================================================================
    # PATTERN RECOGNITION METHODS
    # ============================================================================

    def _analyze_opening_repertoire(self, games: List[Dict]) -> Dict[str, Dict[str, Any]]:
        """Analyze opening repertoire with ECO codes and success rates."""
        opening_stats = defaultdict(lambda: {
            'games': 0, 'wins': 0, 'draws': 0, 'losses': 0,
            'win_rate': 0.0, 'eco_codes': set(), 'avg_rating': 0.0
        })

        for game in games:
            opening_name = self._extract_opening_name(game)
            result = self._extract_game_result(game)
            eco_code = self._extract_eco_code(game)
            opponent_rating = self._extract_opponent_rating(game)

            if opening_name:
                stats = opening_stats[opening_name]
                stats['games'] += 1

                if result == 'win':
                    stats['wins'] += 1
                elif result == 'draw':
                    stats['draws'] += 1
                else:
                    stats['losses'] += 1

                if eco_code:
                    stats['eco_codes'].add(eco_code)

                if opponent_rating:
                    # Keep track of opponent ratings for averaging
                    if 'opponent_ratings' not in stats:
                        stats['opponent_ratings'] = []
                    stats['opponent_ratings'].append(opponent_rating)

        # Calculate final stats
        for opening, stats in opening_stats.items():
            if stats['games'] > 0:
                stats['win_rate'] = round((stats['wins'] / stats['games']) * 100, 1)
                stats['eco_codes'] = list(stats['eco_codes'])

                if 'opponent_ratings' in stats and stats['opponent_ratings']:
                    stats['avg_rating'] = round(statistics.mean(stats['opponent_ratings']), 0)
                    del stats['opponent_ratings']

        return dict(opening_stats)

    def _analyze_time_management(self, games: List[Dict]) -> Dict[str, Any]:
        """Analyze time management patterns."""
        time_patterns = {
            'fast_moves': {'count': 0, 'accuracy': 0.0, 'accuracies': []},
            'normal_moves': {'count': 0, 'accuracy': 0.0, 'accuracies': []},
            'slow_moves': {'count': 0, 'accuracy': 0.0, 'accuracies': []},
            'time_pressure_games': 0,
            'time_wins': 0,
            'time_losses': 0
        }

        for game in games:
            game_review = game.get('game_review', {})
            ply_records = game_review.get('ply_records', [])

            # Check for time pressure
            time_spent_total = sum(r.get('time_spent_s', 0) for r in ply_records)
            time_available = self._extract_total_time(game)

            if time_available and (time_spent_total / time_available) > 0.8:
                time_patterns['time_pressure_games'] += 1

                result = self._extract_game_result(game)
                if result == 'win':
                    time_patterns['time_wins'] += 1
                elif result == 'loss':
                    time_patterns['time_losses'] += 1

            # Analyze move timing
            for record in ply_records:
                time_spent = record.get('time_spent_s', 0)
                accuracy = record.get('accuracy_pct', 0)

                if time_spent < 5:
                    category = 'fast_moves'
                elif time_spent < 30:
                    category = 'normal_moves'
                else:
                    category = 'slow_moves'

                time_patterns[category]['count'] += 1
                time_patterns[category]['accuracies'].append(accuracy)

        # Calculate averages
        for category in ['fast_moves', 'normal_moves', 'slow_moves']:
            if time_patterns[category]['accuracies']:
                time_patterns[category]['accuracy'] = round(
                    statistics.mean(time_patterns[category]['accuracies']), 1
                )
            del time_patterns[category]['accuracies']

        # Calculate time pressure win rate
        total_time_games = time_patterns['time_wins'] + time_patterns['time_losses']
        if total_time_games > 0:
            time_patterns['time_pressure_win_rate'] = round(
                (time_patterns['time_wins'] / total_time_games) * 100, 1
            )

        return time_patterns

    def _analyze_opponent_performance(self, games: List[Dict]) -> Dict[str, Any]:
        """Analyze performance against different opponent types."""
        opponent_analysis = {
            'rating_ranges': defaultdict(lambda: {'games': 0, 'wins': 0, 'win_rate': 0.0}),
            'performance_vs_higher': {'games': 0, 'wins': 0, 'win_rate': 0.0},
            'performance_vs_lower': {'games': 0, 'wins': 0, 'win_rate': 0.0},
            'performance_vs_equal': {'games': 0, 'wins': 0, 'win_rate': 0.0}
        }

        for game in games:
            opponent_rating = self._extract_opponent_rating(game)
            player_rating = self._extract_player_rating(game)
            result = self._extract_game_result(game)

            if opponent_rating and player_rating:
                # Categorize opponent rating
                rating_diff = opponent_rating - player_rating

                if rating_diff > 200:
                    category = 'much_higher'
                elif rating_diff > 100:
                    category = 'higher'
                elif rating_diff < -200:
                    category = 'much_lower'
                elif rating_diff < -100:
                    category = 'lower'
                else:
                    category = 'equal'

                # Update rating range stats
                range_stats = opponent_analysis['rating_ranges'][category]
                range_stats['games'] += 1
                if result == 'win':
                    range_stats['wins'] += 1

                # Update general performance categories
                if rating_diff > 100:
                    opponent_analysis['performance_vs_higher']['games'] += 1
                    if result == 'win':
                        opponent_analysis['performance_vs_higher']['wins'] += 1
                elif rating_diff < -100:
                    opponent_analysis['performance_vs_lower']['games'] += 1
                    if result == 'win':
                        opponent_analysis['performance_vs_lower']['wins'] += 1
                else:
                    opponent_analysis['performance_vs_equal']['games'] += 1
                    if result == 'win':
                        opponent_analysis['performance_vs_equal']['wins'] += 1

        # Calculate win rates
        for category, stats in opponent_analysis['rating_ranges'].items():
            if stats['games'] > 0:
                stats['win_rate'] = round((stats['wins'] / stats['games']) * 100, 1)

        for perf_type in ['performance_vs_higher', 'performance_vs_lower', 'performance_vs_equal']:
            stats = opponent_analysis[perf_type]
            if stats['games'] > 0:
                stats['win_rate'] = round((stats['wins'] / stats['games']) * 100, 1)

        opponent_analysis['rating_ranges'] = dict(opponent_analysis['rating_ranges'])

        return opponent_analysis

    # ============================================================================
    # STRENGTH ANALYSIS METHODS
    # ============================================================================

    def _analyze_tactical_strength(self, games: List[Dict]) -> float:
        """Analyze tactical strength based on blunders and missed tactics."""
        tactical_scores = []

        for game in games:
            game_review = game.get('game_review', {})
            stats = game_review.get('stats', {})

            # Look for tactical indicators
            blunders = stats.get('blunders', 0)
            missed_mates = stats.get('missed_mates', 0)
            tactical_accuracy = stats.get('tactical_accuracy')

            if tactical_accuracy is not None:
                tactical_scores.append(tactical_accuracy)
            else:
                # Estimate from blunders (fewer blunders = stronger tactically)
                game_moves = stats.get('total_moves', 30)
                if game_moves > 0:
                    blunder_rate = blunders / game_moves
                    # Convert to 0-100 scale (lower blunder rate = higher score)
                    estimated_score = max(0, 100 - (blunder_rate * 500))
                    tactical_scores.append(estimated_score)

        return round(statistics.mean(tactical_scores), 1) if tactical_scores else 50.0

    def _analyze_positional_strength(self, games: List[Dict]) -> float:
        """Analyze positional strength based on planning and structure."""
        positional_scores = []

        for game in games:
            game_review = game.get('game_review', {})
            stats = game_review.get('stats', {})

            # Look for positional indicators
            positional_accuracy = stats.get('positional_accuracy')
            structural_understanding = stats.get('structural_understanding')

            if positional_accuracy is not None:
                positional_scores.append(positional_accuracy)
            elif structural_understanding is not None:
                positional_scores.append(structural_understanding)
            else:
                # Estimate from game outcomes and phase performance
                result = self._extract_game_result(game)
                middlegame_accuracy = stats.get('by_phase', {}).get('middlegame', {}).get('accuracy')

                if result == 'win' and middlegame_accuracy:
                    positional_scores.append(min(100, middlegame_accuracy + 10))
                elif middlegame_accuracy:
                    positional_scores.append(middlegame_accuracy)
                else:
                    positional_scores.append(50.0)  # Neutral

        return round(statistics.mean(positional_scores), 1) if positional_scores else 50.0

    def _analyze_calculation_depth(self, games: List[Dict]) -> float:
        """Analyze calculation depth based on move selection patterns."""
        calculation_scores = []

        for game in games:
            game_review = game.get('game_review', {})
            ply_records = game_review.get('ply_records', [])

            # Analyze move selection patterns
            deep_moves = 0
            total_moves = 0

            for record in ply_records:
                if record.get('side_moved') == self._extract_player_color(game):
                    total_moves += 1

                    # Look for indicators of deep calculation
                    time_spent = record.get('time_spent_s', 0)
                    accuracy = record.get('accuracy_pct', 0)

                    # Moves that take time and are accurate likely involve deep calculation
                    if time_spent > 30 and accuracy > 80:
                        deep_moves += 1

            if total_moves > 0:
                calculation_score = (deep_moves / total_moves) * 100
                calculation_scores.append(calculation_score)

        return round(statistics.mean(calculation_scores), 1) if calculation_scores else 50.0

    def _analyze_endgame_proficiency(self, games: List[Dict]) -> float:
        """Analyze endgame proficiency."""
        endgame_scores = []

        for game in games:
            game_review = game.get('game_review', {})
            stats = game_review.get('stats', {})
            by_phase = stats.get('by_phase', {})

            endgame_accuracy = by_phase.get('endgame', {}).get('accuracy')
            if endgame_accuracy is not None:
                endgame_scores.append(endgame_accuracy)
            else:
                # Estimate based on endgame results
                result = self._extract_game_result(game)
                endgame_moves = by_phase.get('endgame', {}).get('moves', 0)

                if endgame_moves > 5:  # Significant endgame
                    if result == 'win':
                        endgame_scores.append(80.0)
                    elif result == 'draw':
                        endgame_scores.append(60.0)
                    else:
                        endgame_scores.append(40.0)
                else:
                    endgame_scores.append(50.0)  # Neutral for short/no endgame

        return round(statistics.mean(endgame_scores), 1) if endgame_scores else 50.0

    def _analyze_time_pressure_performance(self, games: List[Dict]) -> float:
        """Analyze performance under time pressure."""
        time_pressure_scores = []

        for game in games:
            game_review = game.get('game_review', {})
            ply_records = game_review.get('ply_records', [])

            time_pressure_accuracies = []

            for record in ply_records:
                if record.get('side_moved') == self._extract_player_color(game):
                    time_spent = record.get('time_spent_s', 0)
                    accuracy = record.get('accuracy_pct', 0)
                    total_time = self._extract_total_time(game)

                    # Consider moves under time pressure (last 20% of time)
                    if total_time and time_spent > (total_time * 0.8):
                        time_pressure_accuracies.append(accuracy)

            if time_pressure_accuracies:
                avg_time_accuracy = statistics.mean(time_pressure_accuracies)
                time_pressure_scores.append(avg_time_accuracy)

        return round(statistics.mean(time_pressure_scores), 1) if time_pressure_scores else 50.0

    def _analyze_piece_performance(self, games: List[Dict]) -> Dict[str, float]:
        """Analyze performance with different pieces."""
        piece_performance = defaultdict(list)

        for game in games:
            game_review = game.get('game_review', {})
            ply_records = game_review.get('ply_records', [])
            player_color = self._extract_player_color(game)

            for record in ply_records:
                if record.get('side_moved') == player_color:
                    san = record.get('san', '')
                    accuracy = record.get('accuracy_pct', 0)

                    piece_type = self._extract_piece_from_san(san)
                    if piece_type:
                        piece_performance[piece_type].append(accuracy)

        # Calculate averages
        result = {}
        for piece, accuracies in piece_performance.items():
            if accuracies:
                result[piece] = round(statistics.mean(accuracies), 1)

        return dict(result)

    def _analyze_phase_skills(self, games: List[Dict]) -> Dict[str, float]:
        """Analyze skills in different game phases."""
        phase_skills = {
            'opening': [],
            'middlegame': [],
            'endgame': []
        }

        for game in games:
            game_review = game.get('game_review', {})
            stats = game_review.get('stats', {})
            by_phase = stats.get('by_phase', {})

            for phase in ['opening', 'middlegame', 'endgame']:
                accuracy = by_phase.get(phase, {}).get('accuracy')
                if accuracy is not None:
                    phase_skills[phase].append(accuracy)

        # Calculate averages
        result = {}
        for phase, accuracies in phase_skills.items():
            if accuracies:
                result[phase] = round(statistics.mean(accuracies), 1)
            else:
                result[phase] = 50.0  # Neutral

        return result

    def _categorize_strengths_and_weaknesses(self, tactical: float, positional: float,
                                           calculation: float, endgame: float,
                                           time_pressure: float) -> Tuple[List[str], List[str]]:
        """Categorize strengths and weaknesses based on scores."""
        categories = {
            'Tactical Vision': tactical,
            'Positional Understanding': positional,
            'Calculation Depth': calculation,
            'Endgame Proficiency': endgame,
            'Time Management': time_pressure
        }

        strengths = []
        weaknesses = []

        for category, score in categories.items():
            if score >= 70:
                strengths.append(category)
            elif score <= 40:
                weaknesses.append(category)

        return strengths, weaknesses

    # ============================================================================
    # TRAINING PLAN GENERATION
    # ============================================================================

    def _generate_priority_drills(self, strengths: StrengthProfile,
                                patterns: AdvancedPatterns) -> List[Dict[str, Any]]:
        """Generate priority training drills based on weaknesses."""
        drills = []

        # Generate drills for weaknesses
        for weakness in strengths.weakness_categories:
            if weakness == 'Tactical Vision':
                drills.extend([
                    {
                        'type': 'tactical',
                        'title': 'Tactical Pattern Recognition',
                        'description': 'Practice identifying tactical patterns like pins, forks, and skewers',
                        'difficulty': 'intermediate',
                        'estimated_time': 30,
                        'frequency': 'daily'
                    },
                    {
                        'type': 'tactical',
                        'title': 'Blunder Prevention',
                        'description': 'Study common blunder patterns and learn defensive tactics',
                        'difficulty': 'beginner',
                        'estimated_time': 20,
                        'frequency': 'daily'
                    }
                ])
            elif weakness == 'Positional Understanding':
                drills.extend([
                    {
                        'type': 'positional',
                        'title': 'Pawn Structure Analysis',
                        'description': 'Study pawn structures and their strategic implications',
                        'difficulty': 'intermediate',
                        'estimated_time': 25,
                        'frequency': '3x_week'
                    },
                    {
                        'type': 'positional',
                        'title': 'Piece Coordination',
                        'description': 'Practice coordinating pieces for maximum effectiveness',
                        'difficulty': 'advanced',
                        'estimated_time': 35,
                        'frequency': '3x_week'
                    }
                ])
            elif weakness == 'Time Management':
                drills.extend([
                    {
                        'type': 'time_management',
                        'title': 'Time Pressure Training',
                        'description': 'Practice making accurate moves under time constraints',
                        'difficulty': 'intermediate',
                        'estimated_time': 15,
                        'frequency': 'daily'
                    }
                ])

        # Add drills for common mistakes
        for mistake in patterns.common_mistakes[:3]:  # Top 3 mistakes
            drills.append({
                'type': 'mistake_prevention',
                'title': f'Preventing {mistake.get("type", "Common Mistake")}',
                'description': f'Focus on avoiding {mistake.get("description", "this error")}',
                'difficulty': 'beginner',
                'estimated_time': 20,
                'frequency': '2x_week'
            })

        return drills

    def _recommend_opening_study(self, patterns: AdvancedPatterns) -> List[str]:
        """Recommend openings to study based on repertoire gaps."""
        recommendations = []

        repertoire = patterns.opening_repertoire

        # Find openings with low win rates
        low_performance_openings = [
            opening for opening, stats in repertoire.items()
            if stats.get('win_rate', 0) < 40 and stats.get('games', 0) >= 3
        ]

        if low_performance_openings:
            recommendations.append(f"Study alternatives to: {', '.join(low_performance_openings[:3])}")

        # Recommend diversifying if repertoire is too narrow
        if len(repertoire) < 5:
            recommendations.append("Expand opening repertoire - study 2-3 new openings")

        # Recommend focusing on high-winrate openings
        high_performance_openings = [
            opening for opening, stats in repertoire.items()
            if stats.get('win_rate', 0) > 60 and stats.get('games', 0) >= 5
        ]

        if high_performance_openings:
            recommendations.append(f"Deepen knowledge in successful openings: {', '.join(high_performance_openings[:2])}")

        return recommendations

    def _generate_tactical_training(self, strengths: StrengthProfile,
                                  patterns: AdvancedPatterns) -> Dict[str, Any]:
        """Generate tactical training plan."""
        tactical_plan = {
            'focus_areas': [],
            'recommended_difficulty': 'intermediate',
            'session_structure': []
        }

        if strengths.tactical_strength < 60:
            tactical_plan['focus_areas'].append('Basic tactics (pins, forks, skewers)')
        if strengths.tactical_strength < 70:
            tactical_plan['focus_areas'].append('Complex tactics (discovered attacks, Zwischenzug)')
        if patterns.common_mistakes:
            tactical_plan['focus_areas'].append('Mistake prevention')

        tactical_plan['session_structure'] = [
            'Warm-up: 10 easy tactical puzzles',
            'Main: 20 puzzles at target difficulty',
            'Review: Analyze mistakes and learn patterns'
        ]

        return tactical_plan

    def _recommend_positional_training(self, strengths: StrengthProfile) -> List[str]:
        """Recommend positional training areas."""
        recommendations = []

        if strengths.positional_strength < 60:
            recommendations.extend([
                'Pawn structure principles',
                'Piece coordination exercises',
                'Strategic planning techniques'
            ])

        if strengths.positional_strength < 70:
            recommendations.extend([
                'Positional sacrifice evaluation',
                'Long-term planning studies'
            ])

        return recommendations

    def _generate_time_management_training(self, patterns: AdvancedPatterns) -> Dict[str, Any]:
        """Generate time management training plan."""
        time_plan = {
            'current_performance': patterns.time_management_patterns,
            'training_focus': [],
            'techniques': []
        }

        time_patterns = patterns.time_management_patterns

        if time_patterns.get('time_pressure_win_rate', 50) < 40:
            time_plan['training_focus'].append('Decision making under pressure')
            time_plan['techniques'].extend([
                'Pre-move thinking technique',
                'Time allocation planning',
                'Quick evaluation methods'
            ])

        if time_patterns.get('fast_moves', {}).get('accuracy', 50) < 60:
            time_plan['training_focus'].append('Fast move accuracy')
            time_plan['techniques'].append('Pattern recognition speed drills')

        return time_plan

    def _recommend_endgame_training(self, strengths: StrengthProfile) -> List[str]:
        """Recommend endgame training areas."""
        recommendations = []

        if strengths.endgame_proficiency < 60:
            recommendations.extend([
                'Basic endgame principles (king and pawn)',
                'Rook endgames',
                'Queen endgames'
            ])

        if strengths.endgame_proficiency < 70:
            recommendations.extend([
                'Opposite-colored bishop endgames',
                'Technical endgame techniques'
            ])

        return recommendations

    # ============================================================================
    # UTILITY METHODS
    # ============================================================================

    def _extract_game_date(self, game: Dict) -> str:
        """Extract game date in YYYY-MM-DD format."""
        date_str = game.get('game_date') or game.get('created_at', '')
        if isinstance(date_str, str) and len(date_str) >= 10:
            return date_str[:10]
        return datetime.now().strftime('%Y-%m-%d')

    def _extract_player_rating(self, game: Dict) -> Optional[float]:
        """Extract player's rating from game."""
        game_review = game.get('game_review', {})
        metadata = game_review.get('metadata', {})
        return metadata.get('player_rating')

    def _extract_opponent_rating(self, game: Dict) -> Optional[float]:
        """Extract opponent's rating from game."""
        game_review = game.get('game_review', {})
        metadata = game_review.get('metadata', {})
        return metadata.get('opponent_rating')

    def _extract_game_result(self, game: Dict) -> Optional[str]:
        """Extract game result (win/draw/loss)."""
        game_review = game.get('game_review', {})
        metadata = game_review.get('metadata', {})
        result = metadata.get('result', '').lower()

        if result in ['win', '1-0', '0-1']:
            return 'win' if result == 'win' or result == '1-0' else 'loss'
        elif result in ['draw', '1/2-1/2']:
            return 'draw'
        elif result in ['loss', '0-1', '1-0']:
            return 'loss'

        return None

    def _extract_opening_name(self, game: Dict) -> Optional[str]:
        """Extract opening name from game."""
        game_review = game.get('game_review', {})
        opening = game_review.get('opening', {})
        return opening.get('name_final') or opening.get('name')

    def _extract_eco_code(self, game: Dict) -> Optional[str]:
        """Extract ECO code from game."""
        game_review = game.get('game_review', {})
        opening = game_review.get('opening', {})
        return opening.get('eco')

    def _extract_time_control(self, game: Dict) -> Optional[str]:
        """Extract time control from game."""
        game_review = game.get('game_review', {})
        metadata = game_review.get('metadata', {})
        return metadata.get('time_control')

    def _extract_total_time(self, game: Dict) -> Optional[float]:
        """Extract total time available from time control."""
        time_control = self._extract_time_control(game)
        if not time_control:
            return None

        # Parse formats like "300+5", "600", "10+0"
        match = re.match(r'(\d+)', time_control)
        if match:
            return float(match.group(1))

        return None

    def _extract_player_color(self, game: Dict) -> Optional[str]:
        """Extract player's color from game."""
        game_review = game.get('game_review', {})
        metadata = game_review.get('metadata', {})
        return metadata.get('player_color')

    def _extract_piece_from_san(self, san: str) -> Optional[str]:
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

    def _calculate_win_rates(self, games: List[Dict]) -> Tuple[float, float, float]:
        """Calculate win, draw, loss rates from games."""
        wins = draws = losses = 0

        for game in games:
            result = self._extract_game_result(game)
            if result == 'win':
                wins += 1
            elif result == 'draw':
                draws += 1
            else:
                losses += 1

        total = len(games)
        if total == 0:
            return 0.0, 0.0, 0.0

        return (
            round((wins / total) * 100, 1),
            round((draws / total) * 100, 1),
            round((losses / total) * 100, 1)
        )

    def _calculate_average_rating(self, games: List[Dict]) -> float:
        """Calculate average player rating across games."""
        ratings = []
        for game in games:
            rating = self._extract_player_rating(game)
            if rating:
                ratings.append(rating)

        return round(statistics.mean(ratings), 1) if ratings else 0.0

    def _identify_common_mistakes(self, games: List[Dict]) -> List[Dict[str, Any]]:
        """Identify most common mistake patterns."""
        mistake_patterns = Counter()

        for game in games:
            game_review = game.get('game_review', {})
            ply_records = game_review.get('ply_records', [])

            for record in ply_records:
                accuracy = record.get('accuracy_pct', 100)
                if accuracy < 50:  # Significant mistake
                    mistake_type = self._categorize_mistake(record)
                    if mistake_type:
                        mistake_patterns[mistake_type] += 1

        # Return top mistakes
        return [
            {
                'type': mistake_type,
                'count': count,
                'description': self._describe_mistake(mistake_type),
                'frequency': round((count / len(games)) * 100, 1)
            }
            for mistake_type, count in mistake_patterns.most_common(5)
        ]

    def _identify_winning_methods(self, games: List[Dict]) -> List[Dict[str, Any]]:
        """Identify successful patterns in winning games."""
        winning_patterns = Counter()

        for game in games:
            result = self._extract_game_result(game)
            if result != 'win':
                continue

            game_review = game.get('game_review', {})
            stats = game_review.get('stats', {})

            # Analyze winning factors
            if stats.get('tactical_wins', 0) > 0:
                winning_patterns['tactical_attack'] += 1
            if stats.get('positional_wins', 0) > 0:
                winning_patterns['positional_pressure'] += 1
            if stats.get('time_pressure_win', False):
                winning_patterns['time_pressure'] += 1

        return [
            {
                'method': method,
                'count': count,
                'description': self._describe_winning_method(method)
            }
            for method, count in winning_patterns.most_common(3)
        ]

    def _identify_losing_patterns(self, games: List[Dict]) -> List[Dict[str, Any]]:
        """Identify patterns in losing games."""
        losing_patterns = Counter()

        for game in games:
            result = self._extract_game_result(game)
            if result != 'loss':
                continue

            game_review = game.get('game_review', {})
            stats = game_review.get('stats', {})

            # Analyze losing factors
            if stats.get('blunders', 0) > 2:
                losing_patterns['blunders'] += 1
            if stats.get('time_loss', False):
                losing_patterns['time_loss'] += 1
            if stats.get('positional_errors', 0) > 3:
                losing_patterns['positional_errors'] += 1

        return [
            {
                'pattern': pattern,
                'count': count,
                'description': self._describe_losing_pattern(pattern)
            }
            for pattern, count in losing_patterns.most_common(3)
        ]

    def _categorize_mistake(self, record: Dict) -> Optional[str]:
        """Categorize a mistake based on record data."""
        accuracy = record.get('accuracy_pct', 100)

        if accuracy < 30:
            return 'blunder'
        elif accuracy < 60:
            return 'significant_error'
        elif accuracy < 80:
            time_spent = record.get('time_spent_s', 0)
            if time_spent < 5:
                return 'rushed_move'
            else:
                return 'positional_error'

        return None

    def _describe_mistake(self, mistake_type: str) -> str:
        """Provide description for mistake type."""
        descriptions = {
            'blunder': 'Major tactical oversight leading to significant material loss',
            'significant_error': 'Substantial positional or tactical error',
            'rushed_move': 'Inaccurate move made too quickly',
            'positional_error': 'Poor positional judgment or planning'
        }
        return descriptions.get(mistake_type, mistake_type)

    def _describe_winning_method(self, method: str) -> str:
        """Provide description for winning method."""
        descriptions = {
            'tactical_attack': 'Winning through tactical combinations and attacks',
            'positional_pressure': 'Building and converting positional advantages',
            'time_pressure': 'Outplaying opponent in time pressure situations'
        }
        return descriptions.get(method, method)

    def _describe_losing_pattern(self, pattern: str) -> str:
        """Provide description for losing pattern."""
        descriptions = {
            'blunders': 'Multiple major tactical mistakes',
            'time_loss': 'Losing on time or under severe time pressure',
            'positional_errors': 'Accumulating positional disadvantages'
        }
        return descriptions.get(pattern, pattern)
