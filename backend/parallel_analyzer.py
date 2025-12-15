"""
Parallel analyzer - standalone functions for ProcessPoolExecutor.

These functions are designed to be called from separate processes,
so they only use FEN strings (easily serializable) rather than chess.Board objects.
"""

import chess
from typing import Dict, List

# Import theme calculators
from theme_calculators import (
    calculate_center_space, calculate_pawn_structure, calculate_king_safety,
    calculate_piece_activity, calculate_color_complex, calculate_lanes,
    calculate_local_imbalances, calculate_development,
    calculate_promotion, calculate_breaks, calculate_prophylaxis
)

# Import tag detectors
from tag_detector import (
    detect_king_safety_tags, detect_pawn_tags,
    detect_center_space_tags, detect_file_tags,
    detect_diagonal_tags, detect_outpost_hole_tags,
    detect_activity_tags, detect_lever_tags
)

# Import material calculator
from material_calculator import calculate_material_balance


def compute_themes_and_tags(fen: str) -> Dict:
    """
    Compute all themes and tags for a position.
    
    This function is designed to run in a separate process via ProcessPoolExecutor.
    It takes a FEN string (easily serializable) and returns a dict with all results.
    
    Args:
        fen: FEN string of the position
        
    Returns:
        {
            "themes": {...},  # All 11 non-engine themes
            "tags": [...],    # All detected tags
            "material_balance_cp": int
        }
    """
    board = chess.Board(fen)
    
    # Calculate all themes (non-engine dependent)
    themes = {
        "center_space": calculate_center_space(board),
        "pawn_structure": calculate_pawn_structure(board),
        "king_safety": calculate_king_safety(board),
        "piece_activity": calculate_piece_activity(board),
        "color_complex": calculate_color_complex(board),
        "lanes": calculate_lanes(board),
        "local_imbalances": calculate_local_imbalances(board),
        "development": calculate_development(board),
        "promotion": calculate_promotion(board),
        "breaks": calculate_breaks(board),
        "prophylaxis": calculate_prophylaxis(board),
    }
    
    # Detect all tags
    all_tags = []
    all_tags.extend(detect_king_safety_tags(board))
    all_tags.extend(detect_pawn_tags(board))
    all_tags.extend(detect_center_space_tags(board))
    all_tags.extend(detect_file_tags(board))
    all_tags.extend(detect_diagonal_tags(board))
    all_tags.extend(detect_outpost_hole_tags(board))
    all_tags.extend(detect_activity_tags(board))
    all_tags.extend(detect_lever_tags(board))
    
    # Material balance
    material_balance = calculate_material_balance(board)
    
    return {
        "themes": themes,
        "tags": all_tags,
        "material_balance_cp": material_balance
    }


def compute_theme_scores(themes: Dict) -> Dict:
    """
    Compute total theme scores from themes dict.
    
    Args:
        themes: Dict of theme calculations
        
    Returns:
        {
            "white": {"S_CENTER_SPACE": float, ..., "total": float},
            "black": {"S_CENTER_SPACE": float, ..., "total": float}
        }
    """
    theme_weights = {
        "center_space": 1.0,
        "pawn_structure": 1.0,
        "king_safety": 1.2,
        "piece_activity": 1.0,
        "color_complex": 0.8,
        "lanes": 0.9,
        "local_imbalances": 0.7,
        "development": 1.0,
        "promotion": 1.5,
        "breaks": 0.8,
        "prophylaxis": 0.6,
    }
    
    white_scores = {}
    black_scores = {}
    white_total = 0.0
    black_total = 0.0
    
    for theme_name, theme_data in themes.items():
        if not isinstance(theme_data, dict):
            continue
            
        weight = theme_weights.get(theme_name, 1.0)
        score_key = f"S_{theme_name.upper()}"
        
        # Extract white score
        if "white" in theme_data:
            white_data = theme_data["white"]
            if isinstance(white_data, dict) and "total" in white_data:
                score = white_data["total"] * weight
                white_scores[score_key] = score
                white_total += score
        
        # Extract black score
        if "black" in theme_data:
            black_data = theme_data["black"]
            if isinstance(black_data, dict) and "total" in black_data:
                score = black_data["total"] * weight
                black_scores[score_key] = score
                black_total += score
    
    white_scores["total"] = white_total
    black_scores["total"] = black_total
    
    return {
        "white": white_scores,
        "black": black_scores
    }

