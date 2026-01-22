"""
FEN analyzer - orchestrates all theme calculators and tag detectors.
Main entry point for analyzing a chess position.
"""

import chess
import chess.engine
from typing import Dict, TYPE_CHECKING
from material_calculator import calculate_material_balance

if TYPE_CHECKING:
    from engine_queue import StockfishQueue
from theme_calculators import (
    calculate_center_space, calculate_pawn_structure, calculate_king_safety,
    calculate_piece_activity, calculate_color_complex, calculate_lanes,
    calculate_local_imbalances, calculate_tactics, calculate_development,
    calculate_promotion, calculate_breaks, calculate_threats,
    calculate_prophylaxis, calculate_trades
)
from tag_detector import aggregate_all_tags


async def analyze_fen(
    fen: str,
    engine_queue: "StockfishQueue",
    depth: int = 18
) -> Dict:
    """
    Analyzes a FEN using all 14 themes and 100+ tags.
    
    Args:
        fen: FEN string of position to analyze
        engine_queue: Stockfish engine queue instance
        depth: Analysis depth for engine
        
    Returns:
        {
          "fen": str,
          "material_balance_cp": int,
          "themes": {
            "center_space": {"white": {...}, "black": {...}},
            "pawn_structure": {...},
            "king_safety": {...},
            "piece_activity": {...},
            "color_complex": {...},
            "lanes": {...},
            "local_imbalances": {...},
            "tactics": {...},
            "development": {...},
            "promotion": {...},
            "breaks": {...},
            "threats": {...},
            "prophylaxis": {...},
            "trades": {...}
          },
          "tags": [...],  # All 100+ tags
          "theme_scores": {
            "white": {
              "S_CENTER_SPACE": float,
              "S_PAWN": float,
              ...
              "total": float
            },
            "black": {...}
          }
        }
    """
    board = chess.Board(fen)
    
    print(f"   → Calculating material balance...")
    # Calculate material balance
    material_balance = calculate_material_balance(board)
    
    print(f"   → Computing 14 themes...")
    # Calculate all 14 themes
    themes = {
        "center_space": calculate_center_space(board),
        "pawn_structure": calculate_pawn_structure(board),
        "king_safety": calculate_king_safety(board),
        "piece_activity": calculate_piece_activity(board),
        "color_complex": calculate_color_complex(board),
        "lanes": calculate_lanes(board),
        "local_imbalances": calculate_local_imbalances(board),
        "tactics": await calculate_tactics(board, engine_queue, depth),
        "development": calculate_development(board),
        "promotion": calculate_promotion(board),
        "breaks": calculate_breaks(board),
        "threats": await calculate_threats(board, engine_queue),
        "prophylaxis": calculate_prophylaxis(board),
        "trades": await calculate_trades(board, engine_queue)
    }
    
    print(f"   → Detecting tags...")
    # Detect all tags
    tags = await aggregate_all_tags(board, engine_queue)
    
    print(f"   → Aggregating theme scores...")
    # Sum theme scores per side
    theme_scores = compute_theme_score_totals(themes)
    
    return {
        "fen": fen,
        "material_balance_cp": material_balance,
        "themes": themes,
        "tags": tags,
        "theme_scores": theme_scores
    }


def compute_theme_score_totals(themes: Dict) -> Dict:
    """
    Aggregate individual theme scores into totals per side.
    
    Args:
        themes: Dict of all theme results
        
    Returns:
        {
            "white": {"S_CENTER_SPACE": float, "S_PAWN": float, ..., "total": float},
            "black": {...}
        }
    """
    theme_names_map = {
        "center_space": "S_CENTER_SPACE",
        "pawn_structure": "S_PAWN",
        "king_safety": "S_KING",
        "piece_activity": "S_ACTIVITY",
        "color_complex": "S_COMPLEX",
        "lanes": "S_LANES",
        "local_imbalances": "S_LOCAL",
        "tactics": "S_TACTICS",
        "development": "S_DEV",
        "promotion": "S_PROMO",
        "breaks": "S_BREAKS",
        "threats": "S_THREATS",
        "prophylaxis": "S_PROPH",
        "trades": "S_TRADES"
    }
    
    white_scores = {}
    black_scores = {}
    
    for theme_key, score_name in theme_names_map.items():
        theme_data = themes.get(theme_key, {})
        white_scores[score_name] = theme_data.get("white", {}).get("total", 0)
        black_scores[score_name] = theme_data.get("black", {}).get("total", 0)
    
    # Calculate grand totals
    white_scores["total"] = sum(white_scores.values())
    black_scores["total"] = sum(black_scores.values())
    
    return {
        "white": white_scores,
        "black": black_scores
    }




