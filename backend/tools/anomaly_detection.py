"""
Anomaly Detection Tool
Detects statistical anomalies in player performance vs historical baseline
"""

from typing import Dict, List, Optional
import math


async def detect_anomalies(
    test_games: List[Dict],
    baseline: Dict,
    metrics: List[str] = None
) -> Dict:
    """
    Detect statistical anomalies in player performance.
    
    Args:
        test_games: List of analyzed games with metrics
            Each game should have: accuracy, cp_loss, blunder_count, etc.
        baseline: Historical baseline from calculate_baseline()
        metrics: List of metrics to check (default: all)
        
    Returns:
        {
            "test_metrics": {
                "accuracy": {"mean": 92.5, "std": 3.2, "n": 5},
                "cp_loss": {"mean": 15.2, "std": 8.1, "n": 5},
                ...
            },
            "z_scores": {
                "accuracy": 3.8,
                "cp_loss": -2.9,
                ...
            },
            "anomaly_score": 0.85,  # 0-1, higher = more anomalous
            "flags": [
                "accuracy_spike",
                "near_perfect_critical_moves"
            ],
            "confidence": "high",
            "interpretation": "Performance significantly exceeds historical baseline"
        }
    """
    if metrics is None:
        metrics = ["accuracy", "cp_loss", "blunder_rate", "critical_accuracy"]
    
    # Calculate test metrics
    test_metrics = _calculate_test_metrics(test_games, metrics)
    
    if not test_metrics or not baseline:
        return {
            "error": "Insufficient data for anomaly detection",
            "test_metrics": test_metrics,
            "baseline": baseline
        }
    
    # Calculate z-scores
    z_scores = {}
    for metric in metrics:
        if metric in test_metrics and metric in baseline:
            test_val = test_metrics[metric].get("mean", 0)
            base_mean = baseline.get(metric, {}).get("mean", 0)
            base_std = baseline.get(metric, {}).get("std", 1)
            
            if base_std > 0:
                z = (test_val - base_mean) / base_std
                z_scores[metric] = round(z, 2)
            else:
                z_scores[metric] = 0
    
    # Calculate overall anomaly score
    anomaly_score = _calculate_anomaly_score(z_scores, metrics)
    
    # Generate flags
    flags = _generate_flags(z_scores, test_metrics, baseline)
    
    # Determine confidence based on sample size
    test_n = min(test_metrics.get(m, {}).get("n", 0) for m in metrics if m in test_metrics)
    baseline_n = baseline.get("games_analyzed", 0)
    
    if test_n >= 5 and baseline_n >= 20:
        confidence = "high"
    elif test_n >= 3 and baseline_n >= 10:
        confidence = "medium"
    else:
        confidence = "low"
    
    # Generate interpretation
    interpretation = _generate_interpretation(z_scores, flags, anomaly_score)
    
    return {
        "test_metrics": test_metrics,
        "baseline_metrics": {k: v for k, v in baseline.items() if k in metrics},
        "z_scores": z_scores,
        "anomaly_score": round(anomaly_score, 3),
        "flags": flags,
        "confidence": confidence,
        "interpretation": interpretation,
        "test_games_count": test_n,
        "baseline_games_count": baseline_n
    }


def _calculate_test_metrics(games: List[Dict], metrics: List[str]) -> Dict:
    """Calculate metrics from test games"""
    if not games:
        return {}
    
    results = {}
    
    # Collect values for each metric
    metric_values = {m: [] for m in metrics}
    
    for game in games:
        for metric in metrics:
            if metric in game:
                metric_values[metric].append(game[metric])
            # Handle nested metrics
            elif "analysis" in game and metric in game["analysis"]:
                metric_values[metric].append(game["analysis"][metric])
    
    # Calculate statistics
    for metric, values in metric_values.items():
        if values:
            results[metric] = {
                "mean": sum(values) / len(values),
                "std": _std_dev(values),
                "min": min(values),
                "max": max(values),
                "n": len(values)
            }
    
    return results


def _std_dev(values: List[float]) -> float:
    """Calculate standard deviation"""
    if len(values) < 2:
        return 0
    
    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
    return math.sqrt(variance)


def _calculate_anomaly_score(z_scores: Dict, metrics: List[str]) -> float:
    """
    Calculate overall anomaly score (0-1).
    
    Uses a combination of:
    - Absolute z-scores (higher = more anomalous)
    - Direction-weighted scores (e.g., high accuracy more suspicious than low)
    """
    if not z_scores:
        return 0
    
    weighted_scores = []
    
    for metric, z in z_scores.items():
        abs_z = abs(z)
        
        # Metrics where HIGH is suspicious
        positive_suspicious = ["accuracy", "critical_accuracy", "top1_match", "top3_match"]
        # Metrics where LOW is suspicious
        negative_suspicious = ["cp_loss", "blunder_rate", "avg_time"]
        
        if metric in positive_suspicious and z > 0:
            # Positive z for accuracy = more suspicious
            weight = 1.5
        elif metric in negative_suspicious and z < 0:
            # Negative z for cp_loss = more suspicious (better than baseline)
            weight = 1.5
        else:
            weight = 1.0
        
        # Convert z-score to 0-1 probability of being anomalous
        # Using sigmoid-like function
        prob = 1 / (1 + math.exp(-0.5 * (abs_z - 2)))
        weighted_scores.append(prob * weight)
    
    if not weighted_scores:
        return 0
    
    # Return weighted average, capped at 1
    return min(1, sum(weighted_scores) / len(weighted_scores))


def _generate_flags(z_scores: Dict, test_metrics: Dict, baseline: Dict) -> List[str]:
    """Generate specific flags for anomalous patterns"""
    flags = []
    
    # Accuracy spike
    if z_scores.get("accuracy", 0) > 2.5:
        flags.append("accuracy_spike")
    
    # Near-perfect play
    test_acc = test_metrics.get("accuracy", {}).get("mean", 0)
    if test_acc > 95:
        flags.append("near_perfect_accuracy")
    
    # Critical move accuracy
    if z_scores.get("critical_accuracy", 0) > 2.5:
        flags.append("exceptional_critical_moves")
    
    # Low CP loss
    if z_scores.get("cp_loss", 0) < -2.5:
        flags.append("unusually_low_centipawn_loss")
    
    # Zero blunders
    test_blunders = test_metrics.get("blunder_rate", {}).get("mean", 0)
    base_blunders = baseline.get("blunder_rate", {}).get("mean", 0.05)
    if test_blunders < 0.01 and base_blunders > 0.03:
        flags.append("no_blunders")
    
    # Consistency anomaly (very low std in test)
    test_std = test_metrics.get("accuracy", {}).get("std", 0)
    if test_std < 2 and test_metrics.get("accuracy", {}).get("n", 0) >= 3:
        flags.append("suspiciously_consistent")
    
    return flags


def _generate_interpretation(z_scores: Dict, flags: List[str], anomaly_score: float) -> str:
    """Generate human-readable interpretation"""
    if anomaly_score < 0.3:
        severity = "within normal range"
    elif anomaly_score < 0.5:
        severity = "slightly above baseline"
    elif anomaly_score < 0.7:
        severity = "notably above baseline"
    elif anomaly_score < 0.85:
        severity = "significantly above baseline"
    else:
        severity = "extremely above baseline"
    
    # Build interpretation
    interpretation = f"Performance is {severity}."
    
    if flags:
        flag_descriptions = {
            "accuracy_spike": "accuracy spiked significantly",
            "near_perfect_accuracy": "near-perfect accuracy achieved",
            "exceptional_critical_moves": "critical moves found at exceptional rate",
            "unusually_low_centipawn_loss": "centipawn loss unusually low",
            "no_blunders": "zero blunders (unusual for this player)",
            "suspiciously_consistent": "performance suspiciously consistent across games"
        }
        
        flag_text = ", ".join(flag_descriptions.get(f, f) for f in flags[:3])
        interpretation += f" Notable: {flag_text}."
    
    # Add context about z-scores
    high_z = [(m, z) for m, z in z_scores.items() if abs(z) > 2]
    if high_z:
        high_z.sort(key=lambda x: abs(x[1]), reverse=True)
        top_metric, top_z = high_z[0]
        direction = "above" if top_z > 0 else "below"
        interpretation += f" {top_metric.replace('_', ' ').title()} is {abs(top_z):.1f} standard deviations {direction} baseline."
    
    return interpretation


# Tool schema for LLM
TOOL_ANOMALY_DETECT = {
    "type": "function",
    "function": {
        "name": "detect_anomalies",
        "description": "Detect statistical anomalies in player performance compared to their historical baseline. Returns z-scores, anomaly flags, and interpretation.",
        "parameters": {
            "type": "object",
            "properties": {
                "test_games": {
                    "type": "array",
                    "description": "List of analyzed games with metrics to test",
                    "items": {
                        "type": "object"
                    }
                },
                "baseline": {
                    "type": "object",
                    "description": "Historical baseline from calculate_baseline()"
                },
                "metrics": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Metrics to analyze (default: accuracy, cp_loss, blunder_rate)",
                    "default": ["accuracy", "cp_loss", "blunder_rate"]
                }
            },
            "required": ["test_games", "baseline"]
        }
    }
}

