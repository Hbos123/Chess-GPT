"""
Light Raw Analysis - Fast Theme/Tag Analysis
Purpose: Fast positional analysis with themes and tags only, without piece profiling overhead.
Performance target: ~50-150ms per position (vs ~300-800ms for full analysis).
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from parallel_analyzer import compute_themes_and_tags, compute_theme_scores


@dataclass
class LightRawAnalysis:
    """Light raw analysis - themes and tags only"""
    
    # Themes (11 theme calculations)
    themes: Dict[str, Any] = field(default_factory=dict)
    # {
    #   "center_space": {...},
    #   "pawn_structure": {...},
    #   "king_safety": {...},
    #   ...
    # }
    
    # Tags (100+ tags)
    tags: List[Dict[str, Any]] = field(default_factory=list)
    # [
    #   {"tag": "isolated_pawn", "square": "d4", "side": "white", "category": "pawn"},
    #   ...
    # ]
    
    # Material
    material_balance_cp: int = 0
    material_advantage: str = "equal"  # "white" | "black" | "equal"
    
    # Theme scores
    theme_scores: Dict[str, Dict[str, float]] = field(default_factory=dict)
    # {
    #   "white": {"S_CENTER_SPACE": 0.5, ..., "total": 3.2},
    #   "black": {"S_CENTER_SPACE": 0.3, ..., "total": 2.8}
    # }
    
    # Top themes (for quick reference)
    top_themes: List[str] = field(default_factory=list)
    # ["king_safety", "piece_activity", "center_space"]
    
    # Roles (deterministic piece roles)
    roles: Dict[str, List[str]] = field(default_factory=dict)
    # {
    #   "white_knight_f3": ["role.attacking.piece", "role.defending.king"],
    #   ...
    # }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "themes": self.themes,
            "tags": self.tags,
            "roles": self.roles,
            "material_balance_cp": self.material_balance_cp,
            "material_advantage": self.material_advantage,
            "theme_scores": self.theme_scores,
            "top_themes": self.top_themes
        }


def compute_light_raw_analysis(
    fen: str,
    previous_fen: Optional[str] = None,
    pgn_exploration: Optional[str] = None,
    investigation_result: Optional[Any] = None
) -> LightRawAnalysis:
    """
    Compute light raw analysis (themes and tags only, no piece profiling).
    
    This is a fast analysis that provides positional context without the overhead
    of piece-by-piece profiling. Used for recursive branching in dual-depth analysis.
    
    Args:
        fen: FEN string of position
        previous_fen: FEN string of previous position (for comparison roles)
        pgn_exploration: PGN exploration string from d2/d16 analysis
        investigation_result: InvestigationResult object with PGN data
        
    Returns:
        LightRawAnalysis with themes, tags, roles, material, and theme scores
    """
    # Compute themes and tags (uses existing parallel_analyzer functions)
    themes_and_tags = compute_themes_and_tags(fen)
    
    themes = themes_and_tags.get("themes", {})
    tags = themes_and_tags.get("tags", [])
    material_balance_cp = themes_and_tags.get("material_balance_cp", 0)
    
    # Compute theme scores
    theme_scores = compute_theme_scores(themes)
    
    # Determine material advantage
    if material_balance_cp > 0:
        material_advantage = "white"
    elif material_balance_cp < 0:
        material_advantage = "black"
    else:
        material_advantage = "equal"
    
    # Extract top themes (sort by total score)
    top_themes = _extract_top_themes(theme_scores)
    
    # NEW: Detect piece roles with enhanced context
    try:
        from role_detector import detect_all_piece_roles
        roles = detect_all_piece_roles(
            fen,
            previous_fen=previous_fen,
            pgn_exploration=pgn_exploration,
            investigation_result=investigation_result
        )
    except Exception as e:
        print(f"   ⚠️ [LIGHT_RAW] Error detecting roles: {e}")
        roles = {}
    
    return LightRawAnalysis(
        themes=themes,
        tags=tags,
        roles=roles,
        material_balance_cp=material_balance_cp,
        material_advantage=material_advantage,
        theme_scores=theme_scores,
        top_themes=top_themes
    )


def _extract_top_themes(theme_scores: Dict[str, Dict[str, float]]) -> List[str]:
    """
    Extract top 3-5 themes based on total scores.
    
    Args:
        theme_scores: Theme scores dict with "white" and "black" keys
        
    Returns:
        List of top theme names (e.g., ["king_safety", "piece_activity", "center_space"])
    """
    # Combine white and black scores to find most significant themes
    theme_totals = {}
    
    for side in ["white", "black"]:
        if side in theme_scores:
            side_scores = theme_scores[side]
            for key, value in side_scores.items():
                if key != "total" and key.startswith("S_"):
                    # Extract theme name from key (e.g., "S_CENTER_SPACE" -> "center_space")
                    theme_name = key[2:].lower()  # Remove "S_" prefix
                    if theme_name not in theme_totals:
                        theme_totals[theme_name] = 0
                    theme_totals[theme_name] += abs(value)
    
    # Sort by total and return top 5
    sorted_themes = sorted(theme_totals.items(), key=lambda x: x[1], reverse=True)
    return [theme[0] for theme in sorted_themes[:5]]




