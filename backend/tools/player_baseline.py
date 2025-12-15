"""
Player Baseline Tool
Calculates a player's historical performance baseline from their games
"""

from typing import Dict, List, Optional
import math


async def calculate_baseline(
    games: List[Dict],
    exclude_outliers: bool = True,
    min_games: int = 10
) -> Dict:
    """
    Calculate a player's historical performance baseline.
    
    Args:
        games: List of analyzed games with metrics
            Each should have: accuracy, cp_loss, blunder_count, move_count, etc.
        exclude_outliers: Remove statistical outliers (default True)
        min_games: Minimum games required for reliable baseline
        
    Returns:
        {
            "accuracy": {"mean": 72.3, "std": 8.5, "median": 73.1},
            "cp_loss": {"mean": 48, "std": 22, "median": 45},
            "blunder_rate": {"mean": 0.08, "std": 0.04, "median": 0.07},
            "critical_accuracy": {"mean": 68.5, "std": 12.1, "median": 70.0},
            "games_analyzed": 50,
            "reliable": True,
            "rating_range": {"min": 1850, "max": 2050}
        }
    """
    if len(games) < 3:
        return {
            "error": "Insufficient games for baseline",
            "games_provided": len(games),
            "min_required": 3,
            "reliable": False
        }
    
    # Collect raw values
    raw_data = {
        "accuracy": [],
        "cp_loss": [],
        "blunder_rate": [],
        "critical_accuracy": [],
        "move_count": [],
        "rating": []
    }
    
    for game in games:
        # Extract metrics from various possible structures
        if "accuracy" in game:
            raw_data["accuracy"].append(game["accuracy"])
        elif "analysis" in game and "accuracy" in game["analysis"]:
            raw_data["accuracy"].append(game["analysis"]["accuracy"])
        
        if "cp_loss" in game:
            raw_data["cp_loss"].append(game["cp_loss"])
        elif "avg_cp_loss" in game:
            raw_data["cp_loss"].append(game["avg_cp_loss"])
        elif "analysis" in game and "avg_cp_loss" in game["analysis"]:
            raw_data["cp_loss"].append(game["analysis"]["avg_cp_loss"])
        
        # Blunder rate
        if "blunder_rate" in game:
            raw_data["blunder_rate"].append(game["blunder_rate"])
        elif "blunder_count" in game and "move_count" in game:
            move_count = game["move_count"]
            if move_count > 0:
                raw_data["blunder_rate"].append(game["blunder_count"] / move_count)
        
        # Critical accuracy (if available)
        if "critical_accuracy" in game:
            raw_data["critical_accuracy"].append(game["critical_accuracy"])
        
        # Rating
        if "player_rating" in game:
            raw_data["rating"].append(game["player_rating"])
    
    # Remove outliers if requested
    if exclude_outliers:
        for key in raw_data:
            if len(raw_data[key]) >= 5:
                raw_data[key] = _remove_outliers(raw_data[key])
    
    # Calculate statistics
    results = {}
    
    for key, values in raw_data.items():
        if key == "rating":
            continue
        if len(values) >= 2:
            results[key] = {
                "mean": round(_mean(values), 2),
                "std": round(_std_dev(values), 2),
                "median": round(_median(values), 2),
                "min": round(min(values), 2),
                "max": round(max(values), 2),
                "n": len(values)
            }
    
    # Rating range
    if raw_data["rating"]:
        results["rating_range"] = {
            "min": min(raw_data["rating"]),
            "max": max(raw_data["rating"]),
            "avg": round(_mean(raw_data["rating"]))
        }
    
    # Reliability check
    reliable = len(games) >= min_games and len(raw_data["accuracy"]) >= min_games // 2
    
    results["games_analyzed"] = len(games)
    results["reliable"] = reliable
    
    if not reliable:
        results["warning"] = f"Baseline may be unreliable (need {min_games}+ games)"
    
    return results


def _mean(values: List[float]) -> float:
    """Calculate mean"""
    return sum(values) / len(values) if values else 0


def _std_dev(values: List[float]) -> float:
    """Calculate sample standard deviation"""
    if len(values) < 2:
        return 0
    mean = _mean(values)
    variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
    return math.sqrt(variance)


def _median(values: List[float]) -> float:
    """Calculate median"""
    if not values:
        return 0
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    mid = n // 2
    if n % 2 == 0:
        return (sorted_vals[mid - 1] + sorted_vals[mid]) / 2
    return sorted_vals[mid]


def _remove_outliers(values: List[float], k: float = 1.5) -> List[float]:
    """
    Remove outliers using IQR method.
    
    Args:
        values: List of values
        k: IQR multiplier (default 1.5, use 3 for extreme outliers only)
    """
    if len(values) < 4:
        return values
    
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    
    q1_idx = n // 4
    q3_idx = 3 * n // 4
    
    q1 = sorted_vals[q1_idx]
    q3 = sorted_vals[q3_idx]
    iqr = q3 - q1
    
    lower = q1 - k * iqr
    upper = q3 + k * iqr
    
    return [v for v in values if lower <= v <= upper]


async def calculate_baseline_from_pgns(
    pgns: List[str],
    engine_queue = None,
    depth: int = 15
) -> Dict:
    """
    Calculate baseline from raw PGN strings by analyzing each game.
    
    This is a convenience wrapper that analyzes games then calculates baseline.
    """
    # This would need the review_game function to analyze each PGN
    # For now, return a placeholder
    return {
        "error": "Use calculate_baseline() with pre-analyzed games",
        "hint": "Analyze games with review_full_game first, then pass results"
    }


# Tool schema for LLM
TOOL_PLAYER_BASELINE = {
    "type": "function",
    "function": {
        "name": "calculate_baseline",
        "description": "Calculate a player's historical performance baseline from their analyzed games. Returns mean, std, and median for accuracy, CP loss, and blunder rate.",
        "parameters": {
            "type": "object",
            "properties": {
                "games": {
                    "type": "array",
                    "description": "List of analyzed games with metrics (accuracy, cp_loss, etc.)",
                    "items": {"type": "object"}
                },
                "exclude_outliers": {
                    "type": "boolean",
                    "description": "Remove statistical outliers (default True)",
                    "default": True
                },
                "min_games": {
                    "type": "integer",
                    "description": "Minimum games for reliable baseline (default 10)",
                    "default": 10
                }
            },
            "required": ["games"]
        }
    }
}

