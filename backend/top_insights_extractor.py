"""
Top Insights Extractor - Extracts the top N most significant insights from scored analysis.
"""

from typing import Dict, List, Any, Optional


class TopInsightsExtractor:
    """
    Extracts the most significant insights from scored analysis data.
    """
    
    @staticmethod
    def extract_top_insights(
        scored_insights: Dict[str, Any],
        scored_insights_final: Optional[Dict[str, Any]] = None,
        piece_profiles: Optional[Dict] = None,
        profile_changes: Optional[Dict] = None,
        top_n: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Extract top N most significant insights from all scored data.
        
        Args:
            scored_insights: Scored insights from start position
            scored_insights_final: Scored insights from final position (with deltas)
            piece_profiles: Piece profiles with scores
            profile_changes: Piece profile changes with scores
            top_n: Number of top insights to return
        
        Returns:
            List of insight dicts sorted by significance_score (descending)
        """
        all_insights = []
        
        # Extract from scored_insights (start position)
        if scored_insights:
            # Engine eval
            if "engine_eval" in scored_insights:
                eval_score = scored_insights["engine_eval"]
                all_insights.append({
                    "type": "engine_evaluation",
                    "category": "evaluation",
                    "significance_score": eval_score["significance_score"],
                    "description": f"Position evaluation: {eval_score['raw_value']:.1f}cp",
                    "raw_value": eval_score["raw_value"],
                    "magnitude": TopInsightsExtractor._classify_magnitude(eval_score["significance_score"]),
                    "data": eval_score
                })
            
            # Material balance
            if "material_balance" in scored_insights:
                mat_score = scored_insights["material_balance"]
                if mat_score["significance_score"] > 10:  # Only significant imbalances
                    all_insights.append({
                        "type": "material_imbalance",
                        "category": "material",
                        "significance_score": mat_score["significance_score"],
                        "description": f"Material imbalance: {mat_score['raw_value']:.1f}cp",
                        "raw_value": mat_score["raw_value"],
                        "magnitude": TopInsightsExtractor._classify_magnitude(mat_score["significance_score"]),
                        "data": mat_score
                    })
            
            # Theme scores (top themes)
            if "theme_scores" in scored_insights:
                for side in ["white", "black"]:
                    side_scores = scored_insights["theme_scores"].get(side, {})
                    for theme_key, theme_score in side_scores.items():
                        if theme_key != "total" and theme_score["significance_score"] > 15:
                            all_insights.append({
                                "type": "theme_score",
                                "category": "positional",
                                "significance_score": theme_score["significance_score"],
                                "description": f"{side.capitalize()} {theme_key.replace('S_', '').replace('_', ' ').lower()}: {theme_score['raw_value']:.1f}",
                                "raw_value": theme_score["raw_value"],
                                "side": side,
                                "theme": theme_key,
                                "magnitude": TopInsightsExtractor._classify_magnitude(theme_score["significance_score"]),
                                "data": theme_score
                            })
            
            # Second-best gap
            if "second_best_gap" in scored_insights:
                gap_score = scored_insights["second_best_gap"]
                if gap_score["significance_score"] > 20:
                    all_insights.append({
                        "type": "move_criticality",
                        "category": "tactical",
                        "significance_score": gap_score["significance_score"],
                        "description": f"Critical move: {gap_score['raw_value']:.1f}cp gap between best and second-best",
                        "raw_value": gap_score["raw_value"],
                        "magnitude": TopInsightsExtractor._classify_magnitude(gap_score["significance_score"]),
                        "data": gap_score
                    })
        
        # Extract from scored_insights_final (deltas)
        if scored_insights_final:
            # Material delta
            if "deltas" in scored_insights_final and "material" in scored_insights_final["deltas"]:
                mat_delta = scored_insights_final["deltas"]["material"]
                if mat_delta["significance_score"] > 15:
                    all_insights.append({
                        "type": "material_change",
                        "category": "material",
                        "significance_score": mat_delta["significance_score"],
                        "description": f"Material change: {mat_delta['raw_delta']:+.1f}cp",
                        "raw_value": mat_delta["raw_delta"],
                        "magnitude": TopInsightsExtractor._classify_magnitude(mat_delta["significance_score"]),
                        "data": mat_delta
                    })
            
            # Positional deltas
            if "deltas" in scored_insights_final:
                for side in ["white", "black"]:
                    if side in scored_insights_final["deltas"] and "positional" in scored_insights_final["deltas"][side]:
                        pos_delta = scored_insights_final["deltas"][side]["positional"]
                        if pos_delta["significance_score"] > 15:
                            all_insights.append({
                                "type": "positional_change",
                                "category": "positional",
                                "significance_score": pos_delta["significance_score"],
                                "description": f"{side.capitalize()} positional change: {pos_delta['raw_delta']:+.1f}cp",
                                "raw_value": pos_delta["raw_delta"],
                                "side": side,
                                "magnitude": TopInsightsExtractor._classify_magnitude(pos_delta["significance_score"]),
                                "data": pos_delta
                            })
            
            # Theme deltas
            if "deltas" in scored_insights_final and "themes" in scored_insights_final["deltas"]:
                for side in ["white", "black"]:
                    side_themes = scored_insights_final["deltas"]["themes"].get(side, {})
                    for theme_key, theme_delta in side_themes.items():
                        if theme_delta["significance_score"] > 20:
                            all_insights.append({
                                "type": "theme_change",
                                "category": "positional",
                                "significance_score": theme_delta["significance_score"],
                                "description": f"{side.capitalize()} {theme_key.replace('S_', '').replace('_', ' ').lower()} change: {theme_delta['raw_delta']:+.1f}",
                                "raw_value": theme_delta["raw_delta"],
                                "side": side,
                                "theme": theme_key,
                                "magnitude": TopInsightsExtractor._classify_magnitude(theme_delta["significance_score"]),
                                "data": theme_delta
                            })
            
            # CP loss (if available)
            if "cp_loss" in scored_insights_final:
                cp_loss = scored_insights_final["cp_loss"]
                if cp_loss["significance_score"] > 20:
                    all_insights.append({
                        "type": "cp_loss",
                        "category": "move_quality",
                        "significance_score": cp_loss["significance_score"],
                        "description": f"CP loss: {cp_loss['raw_value']:.1f}cp",
                        "raw_value": cp_loss["raw_value"],
                        "magnitude": TopInsightsExtractor._classify_magnitude(cp_loss["significance_score"]),
                        "data": cp_loss
                    })
        
        # Extract from piece profiles (most significant pieces)
        if piece_profiles:
            piece_insights = []
            for piece_id, profile in piece_profiles.items():
                if "nnue_contribution_score" in profile:
                    score = profile["nnue_contribution_score"]
                    if score["significance_score"] > 25:  # Only very significant pieces
                        piece_insights.append({
                            "type": "piece_contribution",
                            "category": "piece_activity",
                            "significance_score": score["significance_score"],
                            "description": f"{profile.get('piece_type', 'piece').capitalize()} on {profile.get('square', '?')}: {score['raw_value']:.1f}cp contribution",
                            "raw_value": score["raw_value"],
                            "piece_id": piece_id,
                            "piece_type": profile.get("piece_type"),
                            "square": profile.get("square"),
                            "magnitude": TopInsightsExtractor._classify_magnitude(score["significance_score"]),
                            "data": score
                        })
            
            # Add top 3 piece insights
            piece_insights.sort(key=lambda x: x["significance_score"], reverse=True)
            all_insights.extend(piece_insights[:3])
        
        # Extract from profile changes (piece improvements)
        if profile_changes and "scored_changes" in profile_changes:
            for change in profile_changes["scored_changes"]:
                if "score" in change:
                    score = change["score"]
                    all_insights.append({
                        "type": "piece_improvement",
                        "category": "piece_activity",
                        "significance_score": score["significance_score"],
                        "description": change.get("description", "Piece improvement"),
                        "raw_value": score.get("raw_delta", 0),
                        "magnitude": score.get("magnitude", "moderate"),
                        "justification_tags": score.get("justification_tags", []),
                        "data": change
                    })
        
        # Sort by significance score and return top N
        all_insights.sort(key=lambda x: x["significance_score"], reverse=True)
        return all_insights[:top_n]
    
    @staticmethod
    def _classify_magnitude(significance_score: float) -> str:
        """Classify magnitude based on significance score."""
        if significance_score < 20:
            return "minor"
        elif significance_score < 40:
            return "moderate"
        elif significance_score < 70:
            return "significant"
        else:
            return "major"


















