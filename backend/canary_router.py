"""
Canary routing infrastructure.

Routes a small percentage of requests (1-5%) to variant prompts/models
for A/B testing before full rollout.

Usage:
    variant = canary_router.get_variant()
    if variant == "prompt_v2":
        # Use new prompt
    else:
        # Use default prompt
"""

from __future__ import annotations

from typing import Optional
import os
import random


class CanaryRouter:
    """Simple percentage-based canary routing."""
    
    def __init__(self):
        self.enabled = os.getenv("CANARY_ENABLED", "false").lower() == "true"
        self.percentage = float(os.getenv("CANARY_PERCENTAGE", "1.0"))
        self.variant = os.getenv("CANARY_VARIANT", "prompt_v2")
        self.random_seed = os.getenv("CANARY_RANDOM_SEED")
        
        # Use seed for deterministic testing if provided
        if self.random_seed:
            try:
                random.seed(int(self.random_seed))
            except ValueError:
                pass
    
    def get_variant(self) -> Optional[str]:
        """
        Determine if this request should be routed to a canary variant.
        
        Returns:
            Variant identifier (e.g., "prompt_v2", "lora_v1") or None
        """
        if not self.enabled:
            return None
        
        # Simple percentage-based routing
        if random.random() * 100 > self.percentage:
            return None
        
        return self.variant
    
    def should_route(self) -> bool:
        """Check if current request should be routed to canary."""
        return self.get_variant() is not None


# Global instance
_canary_router_instance: Optional[CanaryRouter] = None


def get_canary_router() -> CanaryRouter:
    """Get the global canary router instance."""
    global _canary_router_instance
    if _canary_router_instance is None:
        _canary_router_instance = CanaryRouter()
    return _canary_router_instance

