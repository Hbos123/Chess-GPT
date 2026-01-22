"""
Peer Comparison Tool
Compare player metrics against similar-rated players
"""

from typing import Dict, List, Optional
import math


# Reference data for different rating bands
# These are approximate values based on engine analysis studies
PEER_DATA = {
    "2700+": {
        "accuracy": {"mean": 85.5, "std": 5.2},
        "cp_loss": {"mean": 18.5, "std": 8.2},
        "top1_match": {"mean": 68.0, "std": 7.5},
        "top3_match": {"mean": 88.5, "std": 4.8},
        "blunder_rate": {"mean": 0.025, "std": 0.015},
        "sample_size": 500
    },
    "2600-2700": {
        "accuracy": {"mean": 82.0, "std": 6.5},
        "cp_loss": {"mean": 25.0, "std": 12.0},
        "top1_match": {"mean": 62.0, "std": 8.5},
        "top3_match": {"mean": 84.0, "std": 6.2},
        "blunder_rate": {"mean": 0.038, "std": 0.020},
        "sample_size": 800
    },
    "2500-2600": {
        "accuracy": {"mean": 78.5, "std": 7.8},
        "cp_loss": {"mean": 32.0, "std": 15.0},
        "top1_match": {"mean": 56.0, "std": 9.5},
        "top3_match": {"mean": 79.5, "std": 7.5},
        "blunder_rate": {"mean": 0.052, "std": 0.025},
        "sample_size": 1000
    },
    "2400-2500": {
        "accuracy": {"mean": 75.0, "std": 8.5},
        "cp_loss": {"mean": 40.0, "std": 18.0},
        "top1_match": {"mean": 50.0, "std": 10.0},
        "top3_match": {"mean": 75.0, "std": 8.5},
        "blunder_rate": {"mean": 0.068, "std": 0.030},
        "sample_size": 1200
    },
    "2200-2400": {
        "accuracy": {"mean": 71.5, "std": 9.2},
        "cp_loss": {"mean": 50.0, "std": 22.0},
        "top1_match": {"mean": 44.0, "std": 11.0},
        "top3_match": {"mean": 70.0, "std": 10.0},
        "blunder_rate": {"mean": 0.085, "std": 0.038},
        "sample_size": 1500
    },
    "2000-2200": {
        "accuracy": {"mean": 67.5, "std": 10.5},
        "cp_loss": {"mean": 62.0, "std": 28.0},
        "top1_match": {"mean": 38.0, "std": 12.0},
        "top3_match": {"mean": 64.0, "std": 11.5},
        "blunder_rate": {"mean": 0.105, "std": 0.045},
        "sample_size": 2000
    },
    "1800-2000": {
        "accuracy": {"mean": 63.0, "std": 12.0},
        "cp_loss": {"mean": 78.0, "std": 35.0},
        "top1_match": {"mean": 32.0, "std": 13.0},
        "top3_match": {"mean": 58.0, "std": 13.0},
        "blunder_rate": {"mean": 0.130, "std": 0.055},
        "sample_size": 2500
    },
    "1600-1800": {
        "accuracy": {"mean": 58.0, "std": 13.5},
        "cp_loss": {"mean": 95.0, "std": 42.0},
        "top1_match": {"mean": 27.0, "std": 14.0},
        "top3_match": {"mean": 52.0, "std": 14.5},
        "blunder_rate": {"mean": 0.165, "std": 0.068},
        "sample_size": 3000
    },
    "<1600": {
        "accuracy": {"mean": 52.0, "std": 15.0},
        "cp_loss": {"mean": 115.0, "std": 50.0},
        "top1_match": {"mean": 22.0, "std": 15.0},
        "top3_match": {"mean": 45.0, "std": 16.0},
        "blunder_rate": {"mean": 0.200, "std": 0.080},
        "sample_size": 4000
    }
}


async def compare_to_peers(
    player_metrics: Dict,
    rating_range: str = None,
    player_rating: int = None,
    metrics_to_compare: List[str] = None
) -> Dict:
    """
    Compare player metrics against similar-rated players.
    
    Args:
        player_metrics: Player's performance metrics
            {"accuracy": 85.5, "cp_loss": 22.0, "top1_match": 70.0, ...}
        rating_range: Rating band (e.g., "2500-2600") or auto-detect from player_rating
        player_rating: Player's rating (used if rating_range not specified)
        metrics_to_compare: Specific metrics to compare (default: all available)
        
    Returns:
        {
            "rating_range": "2500-2600",
            "percentiles": {
                "accuracy": 92.5,  # Player is at 92.5th percentile
                "cp_loss": 88.2,
                ...
            },
            "peer_comparison": {
                "accuracy": {"player": 85.5, "peer_mean": 78.5, "peer_std": 7.8},
                ...
            },
            "z_scores": {
                "accuracy": 0.89,
                "cp_loss": -0.67,  # Negative = better than average
                ...
            },
            "notable_deviations": [
                "accuracy significantly above peers (+0.89σ)",
                "top1_match in top 5% for rating band"
            ],
            "overall_assessment": "Performance above typical for rating band"
        }
    """
    # Determine rating range
    if not rating_range and player_rating:
        rating_range = _get_rating_band(player_rating)
    elif not rating_range:
        rating_range = "2000-2200"  # Default
    
    # Get peer data
    peer_data = _get_peer_data(rating_range)
    
    if not peer_data:
        return {
            "error": f"No peer data for rating range: {rating_range}",
            "available_ranges": list(PEER_DATA.keys())
        }
    
    # Determine which metrics to compare
    if not metrics_to_compare:
        metrics_to_compare = list(peer_data.keys())
        metrics_to_compare = [m for m in metrics_to_compare if m != "sample_size"]
    
    # Calculate comparisons
    percentiles = {}
    peer_comparison = {}
    z_scores = {}
    notable_deviations = []
    
    for metric in metrics_to_compare:
        if metric not in player_metrics or metric not in peer_data:
            continue
        
        player_value = player_metrics[metric]
        peer_mean = peer_data[metric]["mean"]
        peer_std = peer_data[metric]["std"]
        
        # Calculate z-score
        if peer_std > 0:
            z = (player_value - peer_mean) / peer_std
        else:
            z = 0
        
        z_scores[metric] = round(z, 2)
        
        # Calculate percentile (using normal distribution approximation)
        percentile = _z_to_percentile(z, metric)
        percentiles[metric] = round(percentile, 1)
        
        # Store comparison
        peer_comparison[metric] = {
            "player": round(player_value, 2),
            "peer_mean": peer_mean,
            "peer_std": peer_std
        }
        
        # Note significant deviations
        deviation = _describe_deviation(metric, z, percentile)
        if deviation:
            notable_deviations.append(deviation)
    
    # Overall assessment
    overall = _generate_overall_assessment(z_scores, percentiles)
    
    return {
        "rating_range": rating_range,
        "peer_sample_size": peer_data.get("sample_size", "unknown"),
        "percentiles": percentiles,
        "peer_comparison": peer_comparison,
        "z_scores": z_scores,
        "notable_deviations": notable_deviations,
        "overall_assessment": overall
    }


def _get_rating_band(rating: int) -> str:
    """Get rating band string from numeric rating"""
    if rating >= 2700:
        return "2700+"
    elif rating >= 2600:
        return "2600-2700"
    elif rating >= 2500:
        return "2500-2600"
    elif rating >= 2400:
        return "2400-2500"
    elif rating >= 2200:
        return "2200-2400"
    elif rating >= 2000:
        return "2000-2200"
    elif rating >= 1800:
        return "1800-2000"
    elif rating >= 1600:
        return "1600-1800"
    else:
        return "<1600"


def _get_peer_data(rating_range: str) -> Dict:
    """Get peer data for rating range"""
    # Direct match
    if rating_range in PEER_DATA:
        return PEER_DATA[rating_range]
    
    # Try to parse and find closest
    if "-" in rating_range:
        try:
            low, high = map(int, rating_range.split("-"))
            mid = (low + high) // 2
            return PEER_DATA.get(_get_rating_band(mid))
        except:
            pass
    
    return None


def _z_to_percentile(z: float, metric: str) -> float:
    """Convert z-score to percentile, accounting for metric direction"""
    # For "good" metrics (accuracy, match rates), higher is better
    # For "bad" metrics (cp_loss, blunder_rate), lower is better
    
    # Use error function approximation for normal CDF
    cdf = 0.5 * (1 + math.erf(z / math.sqrt(2)))
    
    # Invert for metrics where lower is better
    if metric in ["cp_loss", "blunder_rate", "avg_cp_loss"]:
        return (1 - cdf) * 100
    
    return cdf * 100


def _describe_deviation(metric: str, z: float, percentile: float) -> Optional[str]:
    """Generate description of significant deviation"""
    if abs(z) < 1.0:
        return None  # Not significant
    
    metric_name = metric.replace("_", " ")
    
    if z > 2:
        if metric in ["cp_loss", "blunder_rate"]:
            return f"{metric_name} significantly worse than peers (+{z:.1f}σ)"
        else:
            return f"{metric_name} exceptionally high (top {100-percentile:.0f}%)"
    elif z > 1:
        if metric in ["cp_loss", "blunder_rate"]:
            return f"{metric_name} above peer average (+{z:.1f}σ)"
        else:
            return f"{metric_name} above peers (+{z:.1f}σ)"
    elif z < -2:
        if metric in ["cp_loss", "blunder_rate"]:
            return f"{metric_name} exceptionally low (top {percentile:.0f}%)"
        else:
            return f"{metric_name} significantly below peers ({z:.1f}σ)"
    elif z < -1:
        if metric in ["cp_loss", "blunder_rate"]:
            return f"{metric_name} better than peer average ({z:.1f}σ)"
        else:
            return f"{metric_name} below peer average ({z:.1f}σ)"
    
    return None


def _generate_overall_assessment(z_scores: Dict, percentiles: Dict) -> str:
    """Generate overall assessment of performance vs peers"""
    # Count positive and negative significant deviations
    positive_good = 0
    negative_bad = 0
    
    good_metrics = ["accuracy", "top1_match", "top3_match", "critical_match"]
    bad_metrics = ["cp_loss", "blunder_rate", "avg_cp_loss"]
    
    for metric, z in z_scores.items():
        if metric in good_metrics and z > 1:
            positive_good += 1
        elif metric in good_metrics and z < -1:
            negative_bad += 1
        elif metric in bad_metrics and z < -1:
            positive_good += 1  # Lower is better
        elif metric in bad_metrics and z > 1:
            negative_bad += 1
    
    # Average percentile for good metrics
    good_percentiles = [p for m, p in percentiles.items() if m in good_metrics]
    avg_good = sum(good_percentiles) / len(good_percentiles) if good_percentiles else 50
    
    if positive_good >= 3 and avg_good > 85:
        return "Performance significantly exceeds typical for rating band"
    elif positive_good >= 2 and avg_good > 70:
        return "Performance above typical for rating band"
    elif negative_bad >= 2 and avg_good < 30:
        return "Performance below typical for rating band"
    elif 40 <= avg_good <= 60:
        return "Performance typical for rating band"
    elif avg_good > 60:
        return "Performance slightly above typical for rating band"
    else:
        return "Performance slightly below typical for rating band"


# Tool schema for LLM
TOOL_PEER_COMPARISON = {
    "type": "function",
    "function": {
        "name": "compare_to_peers",
        "description": "Compare a player's performance metrics against similar-rated players. Returns percentiles, z-scores, and notable deviations from peer norms.",
        "parameters": {
            "type": "object",
            "properties": {
                "player_metrics": {
                    "type": "object",
                    "description": "Player's metrics (accuracy, cp_loss, top1_match, top3_match, blunder_rate)"
                },
                "rating_range": {
                    "type": "string",
                    "description": "Rating band (e.g., '2500-2600', '2700+')"
                },
                "player_rating": {
                    "type": "integer",
                    "description": "Player's rating (auto-determines range if not specified)"
                }
            },
            "required": ["player_metrics"]
        }
    }
}

