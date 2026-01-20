"""
Graph Data Builder
Builds per-game derived features for fast frontend graphing.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict
import statistics
from datetime import datetime as dt


TIME_BUCKET_RANGES: List[Tuple[float, float, str]] = [
    (0, 5, "<5s"),
    (5, 15, "5-15s"),
    (15, 30, "15-30s"),
    (30, 60, "30s-1min"),
    (60, 150, "1min-2min30"),
    (150, 300, "2min30-5min"),
    (300, float("inf"), "5min+"),
]

ALL_PIECES = ["Pawn", "Knight", "Bishop", "Rook", "Queen", "King"]


def _safe_mean(vals: List[float]) -> Optional[float]:
    vals2 = [v for v in vals if isinstance(v, (int, float))]
    if not vals2:
        return None
    return float(statistics.mean(vals2))


def _to_date_str(game_date: Any) -> Optional[str]:
    if not game_date:
        return None
    if isinstance(game_date, dt):
        return game_date.strftime("%Y-%m-%d")
    if isinstance(game_date, str):
        # accept "YYYY-MM-DD", "YYYY-MM-DDTHH:MM:SS", etc.
        if "T" in game_date:
            return game_date.split("T")[0]
        if " " in game_date:
            return game_date.split(" ")[0]
        return game_date[:10]
    return None


def _piece_from_san(san: str) -> Optional[str]:
    if not san:
        return None
    c = san[0]
    if c == "K":
        return "King"
    if c == "Q":
        return "Queen"
    if c == "R":
        return "Rook"
    if c == "B":
        return "Bishop"
    if c == "N":
        return "Knight"
    if c in "abcdefgh" or c.islower():
        return "Pawn"
    return None


def _extract_tag_names(tags: Any) -> set:
    out = set()
    if not tags:
        return out
    for tag in tags:
        if isinstance(tag, str):
            out.add(tag)
        elif isinstance(tag, dict):
            name = tag.get("tag_name") or tag.get("name") or tag.get("tag", "")
            if name:
                out.add(name)
    return out


def build_graph_game_point(game: Dict[str, Any], index: int) -> Dict[str, Any]:
    """
    Build a compact per-game structure suitable for charting.
    Expects `game` to include full `game_review` JSON (include_full_review=True).
    """
    game_review = game.get("game_review") or {}
    metadata = game_review.get("metadata") or {}
    ply_records = game_review.get("ply_records") or []

    player_color = metadata.get("player_color", "white")
    result = game.get("result") or metadata.get("result") or "unknown"

    # Overall accuracy: prefer stats, fallback to ply_records mean (player moves only)
    overall_accuracy = None
    stats = game_review.get("stats") or {}
    if isinstance(stats, dict):
        overall_accuracy = stats.get("overall_accuracy")
    if overall_accuracy is None:
        accs = [
            r.get("accuracy_pct", 0)
            for r in ply_records
            if r.get("side_moved") == player_color and isinstance(r.get("accuracy_pct"), (int, float))
        ]
        overall_accuracy = _safe_mean(accs)

    # Piece accuracy per game
    piece_accs = defaultdict(list)
    piece_counts = defaultdict(int)
    for r in ply_records:
        if r.get("side_moved") != player_color:
            continue
        san = r.get("san", "")
        acc = r.get("accuracy_pct")
        if not isinstance(acc, (int, float)):
            continue
        piece = _piece_from_san(san)
        if piece in ALL_PIECES:
            piece_accs[piece].append(float(acc))
            piece_counts[piece] += 1

    piece_accuracy = {}
    for p in ALL_PIECES:
        m = _safe_mean(piece_accs[p])
        piece_accuracy[p] = {"accuracy": round(m, 1) if m is not None else None, "count": piece_counts[p]}

    # Time bucket accuracy per game
    bucket_accs = defaultdict(list)
    bucket_counts = defaultdict(int)
    for r in ply_records:
        if r.get("side_moved") != player_color:
            continue
        t = r.get("time_spent_s")
        acc = r.get("accuracy_pct")
        if not isinstance(t, (int, float)) or t <= 0:
            continue
        if not isinstance(acc, (int, float)):
            continue
        for lo, hi, name in TIME_BUCKET_RANGES:
            if lo <= float(t) < hi:
                bucket_accs[name].append(float(acc))
                bucket_counts[name] += 1
                break

    time_bucket_accuracy = {}
    for _, _, name in TIME_BUCKET_RANGES:
        m = _safe_mean(bucket_accs[name])
        time_bucket_accuracy[name] = {"accuracy": round(m, 1) if m is not None else None, "count": bucket_counts[name]}

    # Tag transitions per game (gained/lost between consecutive player moves)
    gained = defaultdict(list)  # tag -> accuracies
    lost = defaultdict(list)
    gained_count = defaultdict(int)
    lost_count = defaultdict(int)

    for i in range(1, len(ply_records)):
        prev = ply_records[i - 1]
        cur = ply_records[i]
        if cur.get("side_moved") != player_color:
            continue
        acc = cur.get("accuracy_pct")
        if not isinstance(acc, (int, float)):
            acc = None

        prev_tags = _extract_tag_names((prev.get("analyse") or {}).get("tags"))
        cur_tags = _extract_tag_names((cur.get("analyse") or {}).get("tags"))

        gained_tags = cur_tags - prev_tags
        lost_tags = prev_tags - cur_tags

        for t in gained_tags:
            gained_count[t] += 1
            if acc is not None:
                gained[t].append(float(acc))
        for t in lost_tags:
            lost_count[t] += 1
            if acc is not None:
                lost[t].append(float(acc))

    def _format_transitions(counts, acc_map):
        out = {}
        for tag, c in counts.items():
            m = _safe_mean(acc_map.get(tag, []))
            out[tag] = {"count": c, "avg_accuracy": round(m, 1) if m is not None else None}
        return out

    tag_transitions = {"gained": _format_transitions(gained_count, gained), "lost": _format_transitions(lost_count, lost)}

    opening_name = game.get("opening_name") or metadata.get("opening_name") or "Unknown"
    opening_eco = game.get("opening_eco") or metadata.get("opening_eco") or "Unknown"

    return {
        "index": index,
        "game_id": game.get("id") or game.get("external_id") or "",
        "game_date": _to_date_str(game.get("game_date") or metadata.get("game_date")),
        "result": result,
        "opening_name": opening_name,
        "opening_eco": opening_eco,
        "time_control": game.get("time_control") or metadata.get("time_control"),
        "overall_accuracy": round(float(overall_accuracy), 1) if isinstance(overall_accuracy, (int, float)) else None,
        "piece_accuracy": piece_accuracy,
        "time_bucket_accuracy": time_bucket_accuracy,
        "tag_transitions": tag_transitions,
    }


