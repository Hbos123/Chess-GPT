"""
Feature flags / kill switches for critical features.

Provides simple on/off toggles for:
- LLM responses (disable for engine-only mode)
- New model/LoRA variants (disable to revert to previous)

Uses Supabase table for persistence + in-memory cache for performance.
"""

from __future__ import annotations

from typing import Optional, Dict
import os
from supabase_client import SupabaseClient


class FeatureFlags:
    """Simple feature flag manager with Supabase persistence."""
    
    def __init__(self, supabase_client: Optional[SupabaseClient] = None):
        self.supabase_client = supabase_client
        self._cache: Dict[str, bool] = {}
        self._cache_ttl_seconds = 60  # Refresh cache every 60 seconds
        self._last_refresh: float = 0.0
        
    def _refresh_cache(self) -> None:
        """Refresh cache from Supabase (best-effort, non-blocking)."""
        if not self.supabase_client:
            # Fallback to env vars if no Supabase
            self._cache = {
                "llm_enabled": os.getenv("LLM_ENABLED", "true").lower() == "true",
                "new_model_enabled": os.getenv("NEW_MODEL_ENABLED", "true").lower() == "true",
            }
            return
        
        import time
        current_time = time.time()
        if current_time - self._last_refresh < self._cache_ttl_seconds:
            return  # Cache still valid
        
        try:
            result = self.supabase_client.client.table("feature_flags").select("flag_name, enabled_bool").execute()
            if result.data:
                self._cache = {row["flag_name"]: row["enabled_bool"] for row in result.data}
            else:
                # No flags in DB, use defaults
                self._cache = {"llm_enabled": True, "new_model_enabled": True}
            self._last_refresh = current_time
        except Exception as e:
            print(f"⚠️  [FEATURE_FLAGS] Failed to refresh cache (non-fatal): {e}")
            # Keep existing cache or use defaults
            if not self._cache:
                self._cache = {"llm_enabled": True, "new_model_enabled": True}
    
    def is_enabled(self, flag_name: str, default: bool = True) -> bool:
        """
        Check if a feature flag is enabled.
        
        Args:
            flag_name: Name of the flag (e.g., "llm_enabled")
            default: Default value if flag not found
            
        Returns:
            True if enabled, False otherwise
        """
        self._refresh_cache()
        return self._cache.get(flag_name, default)
    
    def set_flag(self, flag_name: str, enabled: bool, description: Optional[str] = None) -> bool:
        """
        Set a feature flag (admin-only, requires Supabase).
        
        Args:
            flag_name: Name of the flag
            enabled: Whether to enable it
            description: Optional description
            
        Returns:
            True if successful, False otherwise
        """
        if not self.supabase_client:
            print(f"⚠️  [FEATURE_FLAGS] Cannot set flag {flag_name}: no Supabase client")
            return False
        
        try:
            payload = {
                "flag_name": flag_name,
                "enabled_bool": enabled,
            }
            if description:
                payload["description"] = description
            
            self.supabase_client.client.table("feature_flags").upsert(payload).execute()
            
            # Update cache immediately
            self._cache[flag_name] = enabled
            print(f"✅ [FEATURE_FLAGS] Set {flag_name} = {enabled}")
            return True
        except Exception as e:
            print(f"⚠️  [FEATURE_FLAGS] Failed to set flag {flag_name}: {e}")
            return False


# Global instance (initialized in main.py)
_feature_flags_instance: Optional[FeatureFlags] = None


def get_feature_flags() -> FeatureFlags:
    """Get the global feature flags instance."""
    global _feature_flags_instance
    if _feature_flags_instance is None:
        _feature_flags_instance = FeatureFlags()
    return _feature_flags_instance


def init_feature_flags(supabase_client: SupabaseClient) -> None:
    """Initialize feature flags with Supabase client."""
    global _feature_flags_instance
    _feature_flags_instance = FeatureFlags(supabase_client)

