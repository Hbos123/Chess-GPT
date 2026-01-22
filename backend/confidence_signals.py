from __future__ import annotations

from typing import Any, Dict, Optional

from facts_models import ConfidenceSignals


def compute_confidence_signals(*, facts_light: Dict[str, Any], facts_deep: Optional[Dict[str, Any]] = None) -> ConfidenceSignals:
    """
    Compute confidence signals strictly from engine artifacts (no LLM).
    Keep heuristics simple + bounded.
    """
    notes = []
    ev1 = facts_light.get("eval_cp") if isinstance(facts_light, dict) else None
    ev2 = facts_deep.get("eval_cp") if isinstance(facts_deep, dict) else None if isinstance(facts_deep, dict) else None

    # Eval stability: if deep eval close to light eval, it's more stable.
    eval_stability = None
    if isinstance(ev1, (int, float)) and isinstance(ev2, (int, float)):
        diff = abs(float(ev2) - float(ev1))
        # diff 0 => 1.0 stable, diff >= 120cp => 0.0 stable
        eval_stability = max(0.0, min(1.0, 1.0 - (diff / 120.0)))
        notes.append(f"eval_diff_cp={round(diff,1)}")

    # Volatility: heuristic from top-move spread and large swings.
    volatility = None
    try:
        tms = facts_light.get("top_moves") if isinstance(facts_light, dict) else None
        if isinstance(tms, list) and len(tms) >= 2:
            e0 = tms[0].get("eval_cp") if isinstance(tms[0], dict) else None
            e1 = tms[1].get("eval_cp") if isinstance(tms[1], dict) else None
            if isinstance(e0, (int, float)) and isinstance(e1, (int, float)):
                spread = abs(float(e0) - float(e1))
                # spread 0 => 0 volatility; spread >= 80 => 1 volatility
                volatility = max(0.0, min(1.0, spread / 80.0))
                notes.append(f"top2_spread_cp={round(spread,1)}")
    except Exception:
        pass

    # Horizon: if no deep eval provided and light depth is small, more horizon risk.
    horizon = None
    try:
        depth = facts_light.get("depth") if isinstance(facts_light, dict) else None
        if depth is None:
            horizon = 0.6
        else:
            d = int(depth)
            horizon = 1.0 if d <= 6 else 0.7 if d <= 10 else 0.4 if d <= 14 else 0.25
    except Exception:
        horizon = 0.6

    return ConfidenceSignals(
        eval_stability=eval_stability,
        volatility=volatility,
        horizon=horizon,
        notes=notes,
    )






