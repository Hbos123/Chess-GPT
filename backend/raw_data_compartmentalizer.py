"""
Raw Data Compartmentalizer - Structures raw analysis into LLM-accessible chunks.
Allows the LLM interpreter to selectively load specific data compartments.
"""

from typing import Dict, List, Any, Optional


class RawDataCompartmentalizer:
    """
    Organizes raw analysis data into logical compartments
    that the LLM interpreter can selectively load.
    """
    
    @staticmethod
    def compartmentalize(raw_analysis: Dict) -> Dict[str, Any]:
        """
        Split raw analysis into compartments.
        
        Returns:
            {
                "metadata": {...},
                "engine_evaluation": {...},
                "material": {...},
                "themes": {...},
                "tags": {...},
                "piece_profiles": {...},
                "positional_factors": {...},
                "tactical_factors": {...},
                "strategic_factors": {...},
                "scored_insights": {...}  # NEW: All significance scores
            }
        """
        compartments = {
            "metadata": {
                "fen": raw_analysis.get("fen"),
                "phase": raw_analysis.get("phase", "middlegame"),
                "eval_cp": raw_analysis.get("eval_cp", 0),
                "best_move_uci": raw_analysis.get("best_move_uci")
            },
            
            "engine_evaluation": {
                "eval_cp": raw_analysis.get("eval_cp", 0),
                "engine_info": raw_analysis.get("engine_info", []),
                "best_move_uci": raw_analysis.get("best_move_uci"),
                "pv": raw_analysis.get("engine_info", [{}])[0].get("pv", []) if raw_analysis.get("engine_info") else []
            },
            
            "material": {
                "material_balance_cp": raw_analysis.get("material_balance_cp", 0),
                "material_advantage": "white" if raw_analysis.get("material_balance_cp", 0) > 0 else "black" if raw_analysis.get("material_balance_cp", 0) < 0 else "equal"
            },
            
            "themes": {
                "theme_scores": raw_analysis.get("theme_scores", {}),
                "theme_details": raw_analysis.get("themes", {}),
                "top_themes": RawDataCompartmentalizer._get_top_themes(
                    raw_analysis.get("theme_scores", {})
                )
            },
            
            "tags": {
                "all_tags": raw_analysis.get("tags", []),
                "by_category": RawDataCompartmentalizer._organize_tags_by_category(
                    raw_analysis.get("tags", [])
                ),
                "by_side": RawDataCompartmentalizer._organize_tags_by_side(
                    raw_analysis.get("tags", [])
                )
            },
            
            "piece_profiles": raw_analysis.get("piece_profiles", {}),
            
            "positional_factors": {
                "center_control": RawDataCompartmentalizer._extract_center_control(
                    raw_analysis
                ),
                "space_advantage": RawDataCompartmentalizer._extract_space_advantage(
                    raw_analysis
                ),
                "development": RawDataCompartmentalizer._extract_development(
                    raw_analysis
                )
            },
            
            "tactical_factors": {
                "threats": raw_analysis.get("threats", {}),
                "tactical_tags": RawDataCompartmentalizer._extract_tactical_tags(
                    raw_analysis.get("tags", [])
                )
            },
            
            "strategic_factors": {
                "pawn_structure": raw_analysis.get("themes", {}).get("pawn_structure", {}),
                "king_safety": raw_analysis.get("themes", {}).get("king_safety", {}),
                "piece_activity": raw_analysis.get("themes", {}).get("piece_activity", {})
            }
        }
        
        # Add scored insights if available
        if "scored_insights" in raw_analysis:
            compartments["scored_insights"] = raw_analysis["scored_insights"]
        
        return compartments
    
    @staticmethod
    def _get_top_themes(theme_scores: Dict) -> List[Dict]:
        """Get top 3 themes by absolute score."""
        all_scores = []
        for side in ["white", "black"]:
            scores = theme_scores.get(side, {})
            for key, value in scores.items():
                if key != "total":
                    all_scores.append({
                        "theme": key,
                        "side": side,
                        "score": value
                    })
        
        all_scores.sort(key=lambda x: abs(x["score"]), reverse=True)
        return all_scores[:3]
    
    @staticmethod
    def _organize_tags_by_category(tags: List[Dict]) -> Dict[str, List[Dict]]:
        """Organize tags by category (center, pawn, threat, etc.)."""
        organized = {}
        for tag in tags:
            tag_name = tag.get("tag_name", "")
            if "." in tag_name:
                parts = tag_name.split(".")
                if len(parts) >= 2:
                    category = parts[1]  # e.g., "center", "pawn", "threat"
                    if category not in organized:
                        organized[category] = []
                    organized[category].append(tag)
        return organized
    
    @staticmethod
    def _organize_tags_by_side(tags: List[Dict]) -> Dict[str, List[Dict]]:
        """Organize tags by side."""
        organized = {"white": [], "black": [], "both": []}
        for tag in tags:
            side = tag.get("side", "both")
            if side in organized:
                organized[side].append(tag)
            else:
                organized["both"].append(tag)
        return organized
    
    @staticmethod
    def _extract_center_control(raw_analysis: Dict) -> Dict:
        """Extract center control information."""
        center_space = raw_analysis.get("themes", {}).get("center_space", {})
        center_tags = [t for t in raw_analysis.get("tags", []) 
                      if "center" in t.get("tag_name", "")]
        return {
            "theme_data": center_space,
            "tags": center_tags
        }
    
    @staticmethod
    def _extract_space_advantage(raw_analysis: Dict) -> Dict:
        """Extract space advantage information."""
        center_space = raw_analysis.get("themes", {}).get("center_space", {})
        return {
            "white_space": center_space.get("white", {}).get("space_advantage", 0),
            "black_space": center_space.get("black", {}).get("space_advantage", 0)
        }
    
    @staticmethod
    def _extract_development(raw_analysis: Dict) -> Dict:
        """Extract development information."""
        development = raw_analysis.get("themes", {}).get("development", {})
        return development
    
    @staticmethod
    def _extract_tactical_tags(tags: List[Dict]) -> List[Dict]:
        """Extract tags related to tactics."""
        return [t for t in tags if "threat" in t.get("tag_name", "")]


















