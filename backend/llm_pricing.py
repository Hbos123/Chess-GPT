"""
LLM Pricing Table (token-based)

This module provides a small pricing table + helpers to estimate $ cost from
token usage. It is intentionally lightweight and safe to import from anywhere.

IMPORTANT:
- Pricing changes over time. Update PRICING_PER_1M when you change models or when
  OpenAI publishes updated pricing.
- If a model is unknown, cost estimation returns None (not 0).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple


@dataclass(frozen=True)
class ModelPricing:
    input_per_1m_usd: float
    output_per_1m_usd: float


# ---------------------------------------------------------------------------
# Pricing table (USD per 1M tokens)
# ---------------------------------------------------------------------------
# NOTE: Web pricing retrieval is not reliably available inside this environment,
# so these are best-effort defaults. Please verify against OpenAI's pricing page
# and update as needed.
#
# If you want to override, update this file or add additional keys.
PRICING_PER_1M: Dict[str, ModelPricing] = {
    # Common "mini" model (historically very cheap)
    "gpt-4o-mini": ModelPricing(input_per_1m_usd=0.15, output_per_1m_usd=0.60),
    # Reasonable placeholder for "gpt-5" if used; set to None by omission if unknown.
    # Add exact pricing once confirmed.
    # "gpt-5": ModelPricing(input_per_1m_usd=???, output_per_1m_usd=???),
}


def _match_pricing(model: Optional[str]) -> Optional[Tuple[str, ModelPricing]]:
    """
    Return (matched_key, pricing) by longest-prefix match.
    E.g. "gpt-4o-mini-2025-xx-yy" matches "gpt-4o-mini".
    """
    if not model:
        return None
    m = str(model).strip()
    if not m:
        return None

    best_key = None
    best = None
    for key, pricing in PRICING_PER_1M.items():
        if m == key or m.startswith(key):
            if best_key is None or len(key) > len(best_key):
                best_key = key
                best = pricing
    if best_key and best:
        return best_key, best
    return None


def estimate_cost_usd(model: Optional[str], tokens_in: int, tokens_out: int) -> Optional[float]:
    """
    Estimate cost in USD for a single request or an aggregate.
    Returns None if model pricing is unknown.
    """
    match = _match_pricing(model)
    if not match:
        return None
    _, p = match
    ti = max(0, int(tokens_in or 0))
    to = max(0, int(tokens_out or 0))
    return (ti / 1_000_000.0) * p.input_per_1m_usd + (to / 1_000_000.0) * p.output_per_1m_usd





