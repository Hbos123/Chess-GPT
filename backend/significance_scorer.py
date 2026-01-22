"""
Significance Scorer - Calculates dynamic scores based on distance from average.
Measures how significant observed results are compared to typical values.
All scores are 0-100, where higher = more significant deviation from average.
"""

from typing import Dict, List, Optional, Any
import math


class SignificanceScorer:
    """
    Calculates significance scores for various chess metrics.
    Score = normalized distance from average (higher = more significant)
    """
    
    # Typical/average values for different metrics (can be learned from data)
    TYPICAL_VALUES = {
        "piece_nnue_contribution": {
            "pawn": {"mean": 0.0, "std_dev": 8.0},
            "knight": {"mean": 15.0, "std_dev": 12.0},
            "bishop": {"mean": 15.0, "std_dev": 12.0},
            "rook": {"mean": 20.0, "std_dev": 15.0},
            "queen": {"mean": 30.0, "std_dev": 20.0},
            "king": {"mean": 0.0, "std_dev": 5.0},
        },
        "piece_nnue_delta": {
            "mean": 0.0,
            "std_dev": 8.0  # Typical change per move
        },
        "theme_score": {
            "mean": 0.0,
            "std_dev": 5.0
        },
        "theme_delta": {
            "mean": 0.0,
            "std_dev": 3.0  # Typical theme change per move
        },
        "material_balance_cp": {
            "mean": 0.0,
            "std_dev": 200.0  # Typical material imbalance
        },
        "material_delta_cp": {
            "mean": 0.0,
            "std_dev": 100.0  # Typical material change
        },
        "positional_cp": {
            "mean": 0.0,
            "std_dev": 30.0
        },
        "positional_delta_cp": {
            "mean": 0.0,
            "std_dev": 25.0
        },
        "engine_eval_cp": {
            "mean": 0.0,
            "std_dev": 150.0  # Typical evaluation range
        },
        "eval_delta_cp": {
            "mean": 0.0,
            "std_dev": 50.0  # Typical eval change per move
        },
        "second_best_gap_cp": {
            "mean": 15.0,
            "std_dev": 20.0  # Typical gap between best and second best
        },
        "cp_loss": {
            "mean": 10.0,  # Average CP loss (not 0!)
            "std_dev": 30.0
        },
        "threat_strength": {
            "mean": 0.5,
            "std_dev": 0.3
        }
    }
    
    @staticmethod
    def _calculate_z_score(value: float, mean: float, std_dev: float) -> float:
        """
        Calculate z-score (absolute distance from mean in standard deviations).
        Uses absolute value to grade distance from baseline regardless of direction.
        """
        if std_dev <= 0:
            return 0.0
        return abs(value - mean) / std_dev
    
    @staticmethod
    def _z_score_to_significance(z_score: float) -> float:
        """
        Convert z-score to significance score (0-100).
        Uses sigmoid-like function: score = 100 * (1 - exp(-z_score/2))
        """
        return 100 * (1 - math.exp(-z_score / 2))
    
    @staticmethod
    def score_piece_nnue_contribution(
        nnue_contribution: float,
        piece_type: str
    ) -> Dict[str, Any]:
        """
        Score significance of a piece's NNUE contribution.
        
        Args:
            nnue_contribution: NNUE contribution in centipawns
            piece_type: Type of piece (pawn, knight, etc.)
        
        Returns:
            {
                "significance_score": float,  # 0-100
                "magnitude": str,
                "raw_value": float,
                "z_score": float
            }
        """
        typical = SignificanceScorer.TYPICAL_VALUES["piece_nnue_contribution"]
        piece_stats = typical.get(piece_type, {"mean": 0.0, "std_dev": 10.0})
        
        mean = piece_stats["mean"]
        std_dev = piece_stats["std_dev"]
        z_score = SignificanceScorer._calculate_z_score(nnue_contribution, mean, std_dev)
        significance_score = SignificanceScorer._z_score_to_significance(z_score)
        
        # Classify magnitude
        if abs(nnue_contribution) < 5:
            magnitude = "typical"
        elif abs(nnue_contribution) < 15:
            magnitude = "notable"
        elif abs(nnue_contribution) < 30:
            magnitude = "significant"
        else:
            magnitude = "exceptional"
        
        return {
            "significance_score": round(significance_score, 2),
            "magnitude": magnitude,
            "raw_value": round(nnue_contribution, 2),
            "z_score": round(z_score, 2)
        }
    
    @staticmethod
    def score_piece_improvement(
        nnue_delta: float,
        piece_type: str,
        tags_before: List[Dict] = None,
        tags_after: List[Dict] = None
    ) -> Dict[str, Any]:
        """
        Score piece improvement based on NNUE delta.
        
        Args:
            nnue_delta: Change in NNUE contribution (after - before)
            piece_type: Type of piece
            tags_before: Tags before move (for justification)
            tags_after: Tags after move (for justification)
        
        Returns:
            {
                "significance_score": float,
                "magnitude": str,
                "justification_tags": List[str],
                "raw_delta": float,
                "z_score": float
            }
        """
        typical = SignificanceScorer.TYPICAL_VALUES["piece_nnue_delta"]
        mean = typical["mean"]
        std_dev = typical["std_dev"]
        
        z_score = SignificanceScorer._calculate_z_score(nnue_delta, mean, std_dev)
        significance_score = SignificanceScorer._z_score_to_significance(z_score)
        
        # Classify magnitude
        if abs(nnue_delta) < 5:
            magnitude = "minor"
        elif abs(nnue_delta) < 15:
            magnitude = "moderate"
        elif abs(nnue_delta) < 30:
            magnitude = "significant"
        else:
            magnitude = "major"
        
        # Extract justification tags
        justification_tags = []
        if tags_before and tags_after:
            tag_names_before = {t.get("tag_name", "") for t in tags_before}
            tag_names_after = {t.get("tag_name", "") for t in tags_after}
            
            if nnue_delta > 0:
                # Improvement - show gained tags
                gained = list(tag_names_after - tag_names_before)
                justification_tags = gained[:5]
            else:
                # Worsening - show lost tags
                lost = list(tag_names_before - tag_names_after)
                justification_tags = lost[:5]
        
        return {
            "significance_score": round(significance_score, 2),
            "magnitude": magnitude,
            "justification_tags": justification_tags,
            "raw_delta": round(nnue_delta, 2),
            "z_score": round(z_score, 2)
        }
    
    @staticmethod
    def score_theme_value(theme_score: float) -> Dict[str, Any]:
        """Score significance of a theme score."""
        typical = SignificanceScorer.TYPICAL_VALUES["theme_score"]
        mean = typical["mean"]
        std_dev = typical["std_dev"]
        
        z_score = SignificanceScorer._calculate_z_score(theme_score, mean, std_dev)
        significance_score = SignificanceScorer._z_score_to_significance(z_score)
        
        return {
            "significance_score": round(significance_score, 2),
            "raw_value": round(theme_score, 2),
            "z_score": round(z_score, 2)
        }
    
    @staticmethod
    def score_theme_change(theme_delta: float) -> Dict[str, Any]:
        """Score significance of theme change."""
        typical = SignificanceScorer.TYPICAL_VALUES["theme_delta"]
        mean = typical["mean"]
        std_dev = typical["std_dev"]
        
        z_score = SignificanceScorer._calculate_z_score(theme_delta, mean, std_dev)
        significance_score = SignificanceScorer._z_score_to_significance(z_score)
        
        return {
            "significance_score": round(significance_score, 2),
            "raw_delta": round(theme_delta, 2),
            "z_score": round(z_score, 2)
        }
    
    @staticmethod
    def score_material_balance(material_balance_cp: float) -> Dict[str, Any]:
        """Score significance of material balance."""
        typical = SignificanceScorer.TYPICAL_VALUES["material_balance_cp"]
        mean = typical["mean"]
        std_dev = typical["std_dev"]
        
        z_score = SignificanceScorer._calculate_z_score(material_balance_cp, mean, std_dev)
        significance_score = SignificanceScorer._z_score_to_significance(z_score)
        
        return {
            "significance_score": round(significance_score, 2),
            "raw_value": round(material_balance_cp, 2),
            "z_score": round(z_score, 2)
        }
    
    @staticmethod
    def score_material_change(material_delta_cp: float) -> Dict[str, Any]:
        """Score significance of material change."""
        typical = SignificanceScorer.TYPICAL_VALUES["material_delta_cp"]
        mean = typical["mean"]
        std_dev = typical["std_dev"]
        
        z_score = SignificanceScorer._calculate_z_score(material_delta_cp, mean, std_dev)
        significance_score = SignificanceScorer._z_score_to_significance(z_score)
        
        return {
            "significance_score": round(significance_score, 2),
            "raw_delta": round(material_delta_cp, 2),
            "z_score": round(z_score, 2)
        }
    
    @staticmethod
    def score_positional_cp(positional_cp: float) -> Dict[str, Any]:
        """Score significance of positional CP."""
        typical = SignificanceScorer.TYPICAL_VALUES["positional_cp"]
        mean = typical["mean"]
        std_dev = typical["std_dev"]
        
        z_score = SignificanceScorer._calculate_z_score(positional_cp, mean, std_dev)
        significance_score = SignificanceScorer._z_score_to_significance(z_score)
        
        return {
            "significance_score": round(significance_score, 2),
            "raw_value": round(positional_cp, 2),
            "z_score": round(z_score, 2)
        }
    
    @staticmethod
    def score_positional_change(positional_delta_cp: float) -> Dict[str, Any]:
        """Score significance of positional change."""
        typical = SignificanceScorer.TYPICAL_VALUES["positional_delta_cp"]
        mean = typical["mean"]
        std_dev = typical["std_dev"]
        
        z_score = SignificanceScorer._calculate_z_score(positional_delta_cp, mean, std_dev)
        significance_score = SignificanceScorer._z_score_to_significance(z_score)
        
        return {
            "significance_score": round(significance_score, 2),
            "raw_delta": round(positional_delta_cp, 2),
            "z_score": round(z_score, 2)
        }
    
    @staticmethod
    def score_engine_eval(eval_cp: float) -> Dict[str, Any]:
        """Score significance of engine evaluation (how far from equal)."""
        typical = SignificanceScorer.TYPICAL_VALUES["engine_eval_cp"]
        mean = typical["mean"]
        std_dev = typical["std_dev"]
        
        z_score = SignificanceScorer._calculate_z_score(eval_cp, mean, std_dev)
        significance_score = SignificanceScorer._z_score_to_significance(z_score)
        
        return {
            "significance_score": round(significance_score, 2),
            "raw_value": round(eval_cp, 2),
            "z_score": round(z_score, 2)
        }
    
    @staticmethod
    def score_eval_change(eval_delta_cp: float) -> Dict[str, Any]:
        """Score significance of evaluation change."""
        typical = SignificanceScorer.TYPICAL_VALUES["eval_delta_cp"]
        mean = typical["mean"]
        std_dev = typical["std_dev"]
        
        z_score = SignificanceScorer._calculate_z_score(eval_delta_cp, mean, std_dev)
        significance_score = SignificanceScorer._z_score_to_significance(z_score)
        
        return {
            "significance_score": round(significance_score, 2),
            "raw_delta": round(eval_delta_cp, 2),
            "z_score": round(z_score, 2)
        }
    
    @staticmethod
    def score_second_best_gap(second_best_gap_cp: float) -> Dict[str, Any]:
        """Score significance of gap between best and second-best move."""
        typical = SignificanceScorer.TYPICAL_VALUES["second_best_gap_cp"]
        mean = typical["mean"]
        std_dev = typical["std_dev"]
        
        z_score = SignificanceScorer._calculate_z_score(second_best_gap_cp, mean, std_dev)
        significance_score = SignificanceScorer._z_score_to_significance(z_score)
        
        return {
            "significance_score": round(significance_score, 2),
            "raw_value": round(second_best_gap_cp, 2),
            "z_score": round(z_score, 2)
        }
    
    @staticmethod
    def score_cp_loss(cp_loss: float) -> Dict[str, Any]:
        """Score significance of CP loss (mistake severity)."""
        typical = SignificanceScorer.TYPICAL_VALUES["cp_loss"]
        mean = typical["mean"]
        std_dev = typical["std_dev"]
        
        z_score = SignificanceScorer._calculate_z_score(cp_loss, mean, std_dev)
        significance_score = SignificanceScorer._z_score_to_significance(z_score)
        
        return {
            "significance_score": round(significance_score, 2),
            "raw_value": round(cp_loss, 2),
            "z_score": round(z_score, 2)
        }
    
    @staticmethod
    def score_threat_strength(threat_strength: float) -> Dict[str, Any]:
        """Score significance of threat strength."""
        typical = SignificanceScorer.TYPICAL_VALUES["threat_strength"]
        mean = typical["mean"]
        std_dev = typical["std_dev"]
        
        z_score = SignificanceScorer._calculate_z_score(threat_strength, mean, std_dev)
        significance_score = SignificanceScorer._z_score_to_significance(z_score)
        
        return {
            "significance_score": round(significance_score, 2),
            "raw_value": round(threat_strength, 2),
            "z_score": round(z_score, 2)
        }
    
    @staticmethod
    def score_all_metrics_in_raw_analysis(
        raw_analysis: Dict,
        raw_before: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Score all significant metrics in a raw analysis.
        If raw_before is provided, also scores deltas.
        
        Returns:
            {
                "engine_eval": {...},
                "material_balance": {...},
                "positional_cp": {...},
                "theme_scores": {...},
                "second_best_gap": {...},
                "deltas": {
                    "material": {...},
                    "positional": {...},
                    "themes": {...},
                    "eval": {...}
                }
            }
        """
        scores = {}
        
        # Score engine evaluation
        eval_cp = raw_analysis.get("eval_cp", 0)
        scores["engine_eval"] = SignificanceScorer.score_engine_eval(eval_cp)
        
        # Score material balance
        material_balance = raw_analysis.get("material_balance_cp", 0)
        scores["material_balance"] = SignificanceScorer.score_material_balance(material_balance)
        
        # Score theme scores
        theme_scores = raw_analysis.get("theme_scores", {})
        scores["theme_scores"] = {}
        for side in ["white", "black"]:
            side_scores = theme_scores.get(side, {})
            scores["theme_scores"][side] = {}
            for theme_key, theme_value in side_scores.items():
                if theme_key != "total":
                    scores["theme_scores"][side][theme_key] = SignificanceScorer.score_theme_value(theme_value)
            # Score total theme score
            total = side_scores.get("total", 0)
            scores["theme_scores"][side]["total"] = SignificanceScorer.score_theme_value(total)
        
        # Score second-best gap if available
        engine_info = raw_analysis.get("engine_info", [])
        if len(engine_info) >= 2:
            best_eval = engine_info[0].get("eval_cp", 0)
            second_eval = engine_info[1].get("eval_cp", 0)
            gap = abs(best_eval - second_eval)
            scores["second_best_gap"] = SignificanceScorer.score_second_best_gap(gap)
        
        # Score deltas if raw_before is provided
        if raw_before:
            scores["deltas"] = {}
            
            # Material delta
            material_before = raw_before.get("material_balance_cp", 0)
            material_after = raw_analysis.get("material_balance_cp", 0)
            material_delta = material_after - material_before
            scores["deltas"]["material"] = SignificanceScorer.score_material_change(material_delta)
            
            # Positional delta (from theme scores total)
            theme_scores_before = raw_before.get("theme_scores", {})
            for side in ["white", "black"]:
                total_before = theme_scores_before.get(side, {}).get("total", 0)
                total_after = theme_scores.get(side, {}).get("total", 0)
                positional_delta = total_after - total_before
                if side not in scores["deltas"]:
                    scores["deltas"][side] = {}
                scores["deltas"][side]["positional"] = SignificanceScorer.score_positional_change(positional_delta)
            
            # Theme deltas
            scores["deltas"]["themes"] = {}
            for side in ["white", "black"]:
                scores["deltas"]["themes"][side] = {}
                themes_before = theme_scores_before.get(side, {})
                themes_after = theme_scores.get(side, {})
                for theme_key in set(list(themes_before.keys()) + list(themes_after.keys())):
                    if theme_key != "total":
                        before_val = themes_before.get(theme_key, 0)
                        after_val = themes_after.get(theme_key, 0)
                        delta = after_val - before_val
                        if abs(delta) > 0.1:  # Only significant changes
                            scores["deltas"]["themes"][side][theme_key] = SignificanceScorer.score_theme_change(delta)
            
            # Eval delta
            eval_before = raw_before.get("eval_cp", 0)
            eval_delta = eval_cp - eval_before
            scores["deltas"]["eval"] = SignificanceScorer.score_eval_change(eval_delta)
        
        return scores

