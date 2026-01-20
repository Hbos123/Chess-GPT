"""
Graph utilities for building series from game data
Replicates frontend graphSeries.ts logic in Python
"""

from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict
import statistics
import uuid


def group_by_game(games: List[Dict]) -> List[Dict]:
    """Group each game as its own point"""
    return [
        {
            "key": f"game:{i}",
            "label": f"Game {i+1}",
            "games": [game]
        }
        for i, game in enumerate(games)
    ]


def group_by_day(games: List[Dict]) -> List[Dict]:
    """Group games by date"""
    by_day = defaultdict(list)
    for game in games:
        date = game.get("game_date") or "unknown"
        by_day[date].append(game)
    
    days = sorted(by_day.keys())
    return [
        {
            "key": f"day:{d}",
            "label": d,
            "games": sorted(by_day[d], key=lambda g: g.get("index", 0))
        }
        for d in days
    ]


def group_by_batch5(games: List[Dict]) -> List[Dict]:
    """Group games into batches of 5"""
    out = []
    for i in range(0, len(games), 5):
        chunk = games[i:i+5]
        label = f"Games {i+1}-{i+len(chunk)}"
        out.append({
            "key": f"batch5:{i}",
            "label": label,
            "games": chunk
        })
    return out


def mean(values: List[Optional[float]]) -> Optional[float]:
    """Calculate mean, ignoring None values"""
    xs = [v for v in values if v is not None and isinstance(v, (int, float))]
    if not xs:
        return None
    return sum(xs) / len(xs)


def weighted_mean(items: List[Dict[str, Any]]) -> Optional[float]:
    """Calculate weighted mean"""
    total_weight = 0
    total_value = 0
    for item in items:
        value = item.get("value")
        weight = item.get("weight", 0)
        if value is not None and isinstance(value, (int, float)) and weight > 0:
            total_weight += weight
            total_value += value * weight
    if total_weight == 0:
        return None
    return total_value / total_weight


def normalize_to_0_100(values: List[Optional[float]]) -> List[Optional[float]]:
    """Normalize values to 0-100 range"""
    xs = [v for v in values if v is not None and isinstance(v, (int, float))]
    if not xs:
        return [None] * len(values)
    min_val = min(xs)
    max_val = max(xs)
    range_val = max_val - min_val if max_val != min_val else 1
    return [
        ((v - min_val) / range_val * 100) if v is not None else None
        for v in values
    ]


def compute_trend_delta(raw_values: List[Optional[float]]) -> Optional[float]:
    """Compute trend delta (last point vs previous point)"""
    valid_indices = [i for i, v in enumerate(raw_values) if v is not None]
    if len(valid_indices) < 2:
        return None
    last_idx = valid_indices[-1]
    prev_idx = valid_indices[-2]
    last_val = raw_values[last_idx]
    prev_val = raw_values[prev_idx]
    if last_val is not None and prev_val is not None:
        return last_val - prev_val
    return None


def build_series(
    entry: Dict[str, Any],
    time_points: List[Dict]
) -> Dict[str, Any]:
    """
    Build a series from entry and time points.
    
    Args:
        entry: Series entry with kind, params, label, color
        time_points: List of time points, each with 'games' list
    
    Returns:
        Built series with rawValues, normalizedValues, etc.
    """
    kind = entry.get("kind")
    params = entry.get("params", {})
    
    raw_values: List[Optional[float]] = []
    instances_by_point: List[int] = []
    
    for point in time_points:
        games = point.get("games", [])
        
        if kind == "win_rate_pct":
            total = len(games)
            wins = sum(1 for g in games if str(g.get("result", "")).lower() == "win")
            raw_values.append((wins / total * 100) if total > 0 else None)
            instances_by_point.append(total)
            continue
        
        if kind == "overall_accuracy":
            accs = [g.get("overall_accuracy") for g in games]
            raw_values.append(mean(accs))
            instances_by_point.append(
                sum(1 for g in games if g.get("overall_accuracy") is not None)
            )
            continue
        
        if kind == "opening_frequency_pct":
            opening_name = params.get("openingName") or "Unknown"
            total = len(games)
            matching = sum(1 for g in games if (g.get("opening_name") or "Unknown") == opening_name)
            raw_values.append((matching / total * 100) if total > 0 else None)
            instances_by_point.append(matching)
            continue
        
        if kind == "opening_accuracy":
            opening_name = params.get("openingName") or "Unknown"
            matching = [g for g in games if (g.get("opening_name") or "Unknown") == opening_name]
            accs = [g.get("overall_accuracy") for g in matching]
            raw_values.append(mean(accs))
            instances_by_point.append(len(matching))
            continue
        
        if kind == "piece_accuracy":
            piece = params.get("piece") or "Pawn"
            items = []
            for g in games:
                piece_data = (g.get("piece_accuracy") or {}).get(piece, {})
                acc = piece_data.get("accuracy")
                count = piece_data.get("count", 0)
                items.append({"value": acc, "weight": count})
            raw_values.append(weighted_mean(items))
            instances_by_point.append(sum(item.get("weight", 0) for item in items))
            continue
        
        if kind == "time_bucket_accuracy":
            bucket = params.get("bucket") or "<5s"
            items = []
            for g in games:
                bucket_data = (g.get("time_bucket_accuracy") or {}).get(bucket, {})
                acc = bucket_data.get("accuracy")
                count = bucket_data.get("count", 0)
                items.append({"value": acc, "weight": count})
            raw_values.append(weighted_mean(items))
            instances_by_point.append(sum(item.get("weight", 0) for item in items))
            continue
        
        if kind == "tag_transition_count":
            tag = params.get("tag") or ""
            direction = params.get("dir") or "gained"
            total_count = 0
            for g in games:
                transitions = g.get("tag_transitions", {})
                tag_data = transitions.get(direction, {}).get(tag, {})
                total_count += tag_data.get("count", 0)
            raw_values.append(float(total_count) if total_count > 0 else None)
            instances_by_point.append(total_count)
            continue
        
        if kind == "tag_transition_accuracy":
            tag = params.get("tag") or ""
            direction = params.get("dir") or "gained"
            items = []
            for g in games:
                transitions = g.get("tag_transitions", {})
                tag_data = transitions.get(direction, {}).get(tag, {})
                acc = tag_data.get("avg_accuracy")
                count = tag_data.get("count", 0)
                items.append({"value": acc, "weight": count})
            raw_values.append(weighted_mean(items))
            instances_by_point.append(sum(item.get("weight", 0) for item in items))
            continue
        
        # Unknown kind
        raw_values.append(None)
        instances_by_point.append(0)
    
    normalized_values = normalize_to_0_100(raw_values)
    instances_total = sum(instances_by_point)
    trend_delta = compute_trend_delta(raw_values)
    
    return {
        "entry": entry,
        "rawValues": raw_values,
        "normalizedValues": normalized_values,
        "instancesByPoint": instances_by_point,
        "instancesTotal": instances_total,
        "nPoints": len(time_points),
        "trendDelta": trend_delta,
    }


def assign_color(index: int) -> str:
    """Assign a color from a palette"""
    colors = [
        "#3b82f6",  # blue
        "#10b981",  # green
        "#f59e0b",  # amber
        "#ef4444",  # red
        "#8b5cf6",  # purple
        "#06b6d4",  # cyan
        "#f97316",  # orange
        "#ec4899",  # pink
    ]
    return colors[index % len(colors)]

