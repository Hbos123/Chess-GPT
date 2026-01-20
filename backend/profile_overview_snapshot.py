"""
Lightweight profile snapshot builder for the Overview tab.

Design goals:
- Fast to compute (last ~60 games only)
- No deep/engine-heavy metrics
- Friendly, non-technical labels (time style + identity)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from io import StringIO
from typing import Any, Dict, List, Optional, Tuple

import chess.pgn


def _safe_date_key(g: Dict[str, Any]) -> str:
    # Prefer game_date, fall back to created_at/updated_at
    for k in ("game_date", "created_at", "updated_at"):
        v = g.get(k)
        if isinstance(v, str) and v:
            return v
    return ""


def _pct(n: int, d: int) -> float:
    if d <= 0:
        return 0.0
    return round((n / d) * 100.0, 1)


def _result_list(games_desc: List[Dict[str, Any]]) -> List[str]:
    out: List[str] = []
    for g in games_desc:
        r = g.get("result") or (g.get("metadata") or {}).get("result")
        if r in ("win", "loss", "draw"):
            out.append(r)
        else:
            out.append("unknown")
    return out


def _best_win_streak(results_chrono: List[str]) -> int:
    best = 0
    cur = 0
    for r in results_chrono:
        if r == "win":
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best


def _mean(values: List[float]) -> Optional[float]:
    if not values:
        return None
    return sum(values) / len(values)


def _std(values: List[float]) -> Optional[float]:
    if len(values) < 2:
        return None
    m = _mean(values)
    if m is None:
        return None
    var = sum((x - m) ** 2 for x in values) / len(values)
    return var ** 0.5


def _parse_user_clocks_from_pgn(pgn: str, user_color: str) -> List[float]:
    """
    Returns list of clock remaining (seconds) AFTER each of the user's moves.
    Uses [%clk H:MM:SS(.d)] comments if present.
    """
    if not isinstance(pgn, str) or "[%clk" not in pgn:
        return []

    game = chess.pgn.read_game(StringIO(pgn))
    if not game:
        return []

    clocks_by_ply: Dict[int, float] = {}
    ply = 0
    node = game

    import re

    while node.variations:
        node = node.variation(0)
        ply += 1
        comment = node.comment or ""
        # Matches [%clk 0:05:23] or [%clk 0:05:23.5]
        m = re.search(r"\[%clk (\d+):(\d+):(\d+(?:\.\d+)?)\]", comment)
        if not m:
            continue
        h, mm, ss = m.groups()
        try:
            clocks_by_ply[ply] = int(h) * 3600 + int(mm) * 60 + float(ss)
        except Exception:
            continue

    if not clocks_by_ply:
        return []

    want_white = user_color == "white"
    user_clocks: List[float] = []
    for p in sorted(clocks_by_ply.keys()):
        is_white_ply = (p % 2) == 1
        if (want_white and is_white_ply) or ((not want_white) and (not is_white_ply)):
            user_clocks.append(float(clocks_by_ply[p]))
    return user_clocks


def _time_style_from_games(games_desc: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Compute a single label using true clock remaining from PGN comments.
    """
    early_burn_vals: List[float] = []
    late_pressure_vals: List[float] = []
    games_with_clock = 0
    pressure_games = 0
    pressure_non_loss = 0
    overall_non_loss = 0
    overall_count = 0

    for g in games_desc:
        r = g.get("result")
        if r in ("win", "draw", "loss"):
            overall_count += 1
            if r != "loss":
                overall_non_loss += 1

        pgn = g.get("pgn")
        user_color = g.get("user_color")
        if not isinstance(pgn, str) or user_color not in ("white", "black"):
            continue

        clocks = _parse_user_clocks_from_pgn(pgn, user_color)
        if len(clocks) < 6:
            continue

        games_with_clock += 1
        # Estimate initial clock from early maximum (robust vs increments)
        initial = max(clocks[: min(8, len(clocks))])
        if initial <= 0:
            continue

        last = clocks[-1]
        denom = max(1e-9, initial - last)

        idx30 = max(0, int((len(clocks) * 0.30) - 1))
        c30 = clocks[idx30]
        early_burn = (initial - c30) / denom
        early_burn_vals.append(max(0.0, min(1.0, float(early_burn))))

        late_moves = [c for c in clocks if (c / initial) < 0.10]
        late_pressure = len(late_moves) / len(clocks)
        late_pressure_vals.append(float(late_pressure))

        if late_moves:
            pressure_games += 1
            if r in ("win", "draw"):
                pressure_non_loss += 1

    if games_with_clock < 20:
        return {"label": "Insufficient data", "confidence": round(min(1.0, games_with_clock / 20.0), 2)}

    avg_early = _mean(early_burn_vals) or 0.0
    avg_late = _mean(late_pressure_vals) or 0.0
    overall_non_loss_rate = (overall_non_loss / overall_count) if overall_count else 0.0
    pressure_non_loss_rate = (pressure_non_loss / pressure_games) if pressure_games else 0.0
    clutch_lift = pressure_non_loss_rate - overall_non_loss_rate

    # Label rules (tunable, designed for stability)
    label = "Balanced"
    if avg_early < 0.38 and avg_late <= 0.20:
        label = "Fast & Decisive"
    elif avg_early > 0.62 and avg_late > 0.30:
        label = "Time-Troubled"
    elif 0.38 <= avg_early <= 0.62 and avg_late <= 0.15 and clutch_lift >= 0.08:
        label = "Clutch"
    elif avg_early > 0.58 and avg_late > 0.22:
        label = "Inconsistent"

    confidence = min(1.0, games_with_clock / 30.0)
    return {"label": label, "confidence": round(confidence, 2)}


def _openings_snapshot(games_desc: List[Dict[str, Any]]) -> Dict[str, Any]:
    def top_opening(subset: List[Dict[str, Any]]) -> Tuple[Optional[str], Optional[float]]:
        from collections import Counter

        names: List[str] = []
        for g in subset:
            name = g.get("opening_name")
            if isinstance(name, str) and name and name.lower() not in ("unknown", "undefined"):
                names.append(name)
        if not names:
            return None, None
        counts = Counter(names)
        name, cnt = counts.most_common(1)[0]
        return name, _pct(cnt, len(names))

    as_white = [g for g in games_desc if g.get("user_color") == "white"]
    as_black = [g for g in games_desc if g.get("user_color") == "black"]
    # “Most Faced as Black” is approximated as the most common opening_name in games where you played Black.
    # (True “opponent-chosen opening” would require deeper opening attribution later.)
    w_name, w_pct = top_opening(as_white)
    b_name, b_pct = top_opening(as_black)
    return {"as_white": {"name": w_name, "pct": w_pct}, "as_black_faced": {"name": b_name, "pct": b_pct}}


def _rating_trend(games_desc: List[Dict[str, Any]]) -> Dict[str, Any]:
    # Order chronologically
    games_chrono = list(reversed(games_desc))
    ratings: List[float] = []
    for g in games_chrono:
        r = g.get("user_rating")
        if isinstance(r, (int, float)):
            ratings.append(float(r))
    current = None
    for g in games_desc:
        r = g.get("user_rating")
        if isinstance(r, (int, float)):
            current = int(r)
            break

    if len(ratings) < 40:
        return {"current": current, "trend": "insufficient"}

    prev20 = ratings[-40:-20]
    last20 = ratings[-20:]
    a_prev = _mean(prev20) or 0.0
    a_last = _mean(last20) or 0.0
    delta = a_last - a_prev
    trend = "stable"
    if delta > 10:
        trend = "up"
    elif delta < -10:
        trend = "down"
    return {"current": current, "trend": trend}


def _identity_labels(
    games_desc: List[Dict[str, Any]],
    avg_accuracy: Optional[float],
    win_rate: Optional[float],
    draw_rate: Optional[float],
    time_style: Dict[str, Any],
) -> Dict[str, Any]:
    # Compute per-game accuracy for consistency
    accs: List[float] = []
    for g in games_desc:
        a = g.get("accuracy_overall")
        if isinstance(a, (int, float)):
            accs.append(float(a))
    acc_std = _std(accs)

    results = _result_list(games_desc)
    overall_non_loss = sum(1 for r in results if r in ("win", "draw")) / max(1, sum(1 for r in results if r != "unknown"))

    openings = _openings_snapshot(games_desc)
    # Approx top opening share across all games with an opening name
    from collections import Counter

    opening_names = [
        g.get("opening_name")
        for g in games_desc
        if isinstance(g.get("opening_name"), str) and g.get("opening_name") and str(g.get("opening_name")).lower() not in ("unknown", "undefined")
    ]
    top_open_share = 0.0
    if opening_names:
        c = Counter(opening_names)
        top_open_share = c.most_common(1)[0][1] / len(opening_names)

    # Strength scoring (simple, stable)
    strength_scores: List[Tuple[str, float]] = []
    if acc_std is not None and acc_std <= 6.0:
        strength_scores.append(("Consistent Play", 0.8))
    if time_style.get("label") == "Clutch":
        strength_scores.append(("Clutch Performance", 0.75))
    if openings.get("as_white", {}).get("name") and top_open_share >= 0.35:
        strength_scores.append(("Opening Comfort", 0.7))
    # Endgame resilience proxy: long games non-loss rate
    long_non_loss = None
    long_total = 0
    long_non_loss_cnt = 0
    for g in games_desc:
        pgn = g.get("pgn")
        r = g.get("result")
        if not isinstance(pgn, str) or r not in ("win", "draw", "loss"):
            continue
        game = chess.pgn.read_game(StringIO(pgn))
        if not game:
            continue
        plies = sum(1 for _ in game.mainline_moves())
        if plies >= 100:  # 50 moves
            long_total += 1
            if r != "loss":
                long_non_loss_cnt += 1
    if long_total >= 8:
        long_non_loss = long_non_loss_cnt / long_total
        if long_non_loss >= overall_non_loss + 0.05:
            strength_scores.append(("Endgame Resilience", 0.65))

    if not strength_scores:
        strength_scores.append(("Consistent Play", 0.4))
    strength_scores.sort(key=lambda x: x[1], reverse=True)
    top_strength = strength_scores[0][0]

    # Focus scoring
    focus_scores: List[Tuple[str, float]] = []
    if time_style.get("label") in ("Time-Troubled", "Inconsistent"):
        focus_scores.append(("Time Management", 0.9))
    if top_open_share >= 0.60:
        focus_scores.append(("Opening Variety", 0.7))
    if isinstance(avg_accuracy, (int, float)) and isinstance(win_rate, (int, float)) and isinstance(draw_rate, (int, float)):
        if avg_accuracy >= 75.0 and win_rate <= 50.0 and draw_rate >= 25.0:
            focus_scores.append(("Conversion", 0.65))
    if acc_std is not None and acc_std >= 12.0:
        focus_scores.append(("Risk Control", 0.6))
    if not focus_scores:
        focus_scores.append(("Time Management", 0.35))
    focus_scores.sort(key=lambda x: x[1], reverse=True)
    focus_area = focus_scores[0][0]

    confidence = 0.0
    # Confidence is a soft aggregate
    if time_style.get("confidence") is not None:
        confidence += float(time_style["confidence"]) * 0.5
    if acc_std is not None and len(accs) >= 20:
        confidence += 0.3
    if opening_names:
        confidence += 0.2
    confidence = min(1.0, confidence)

    note = None
    if confidence < 0.6:
        note = "Emerging Pattern"

    return {"top_strength": top_strength, "focus_area": focus_area, "confidence": round(confidence, 2), "note": note}


def build_overview_snapshot(games: List[Dict[str, Any]], window: int = 60) -> Dict[str, Any]:
    # Sort most-recent-first
    games_desc = sorted(games, key=_safe_date_key, reverse=True)[: int(window)]

    results = _result_list(games_desc)
    total_known = sum(1 for r in results if r in ("win", "draw", "loss"))
    wins = sum(1 for r in results if r == "win")
    draws = sum(1 for r in results if r == "draw")
    losses = sum(1 for r in results if r == "loss")

    win_rate = _pct(wins, total_known) if total_known else None
    draw_rate = _pct(draws, total_known) if total_known else None
    loss_rate = _pct(losses, total_known) if total_known else None

    acc_vals: List[float] = []
    for g in games_desc:
        a = g.get("accuracy_overall")
        if isinstance(a, (int, float)):
            acc_vals.append(float(a))
    avg_accuracy = round(_mean(acc_vals), 1) if acc_vals else None

    rating = _rating_trend(games_desc)
    time_style = _time_style_from_games(games_desc)
    openings = _openings_snapshot(games_desc)

    # Momentum
    results_chrono = list(reversed(results))
    best_streak = _best_win_streak(results_chrono)
    last5 = results[:5]
    wins_last_5 = sum(1 for r in last5 if r == "win")
    results_last_10 = results[:10]

    identity = _identity_labels(games_desc, avg_accuracy, win_rate, draw_rate, time_style)

    return {
        "window": int(window),
        "games_analyzed": len(games_desc),
        "record": {"wins": wins, "draws": draws, "losses": losses},
        "rates": {"win": win_rate, "draw": draw_rate, "loss": loss_rate},
        "avg_accuracy": avg_accuracy,
        "rating": rating,
        "time_style": time_style,
        "openings": openings,
        "identity": identity,
        "momentum": {
            "best_win_streak": best_streak,
            "wins_last_5": wins_last_5,
            "results_last_10": results_last_10,
        },
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }


