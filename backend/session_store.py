"""
Session store for prefix-cache-friendly LLM usage.

Key property: the prompt prefix for a given session must remain bit-identical across calls
to maximize vLLM KV-cache reuse.

Therefore:
- `system_prompt` is immutable per session
- `working_context` is append-only
- we avoid inserting timestamps/UUIDs/counters into the prefix (those break caching)
"""

from __future__ import annotations

import time
import os
from dataclasses import dataclass, field
from typing import Dict, Optional, Any


@dataclass
class SessionState:
    system_prompt: str
    working_context: str = ""  # append-only transcript
    metadata: Dict[str, Any] = field(default_factory=dict)
    # Optional deterministic seed prefix for the session (must be stable once set).
    # This is intended for a short “contract” or task seed that should sit at the
    # front of `working_context` and never change, improving prefix cache reuse.
    seed_prefix: str = ""
    created_at: float = field(default_factory=lambda: time.time())
    updated_at: float = field(default_factory=lambda: time.time())

    def touch(self) -> None:
        self.updated_at = time.time()


class InMemorySessionStore:
    """
    Minimal in-memory session store.
    Designed so it can be swapped for Redis later (same API surface).
    """

    def __init__(self, ttl_seconds: int = 60 * 60, max_context_chars: Optional[int] = None):
        self._ttl_seconds = int(ttl_seconds)
        # Safety cap: prevent prompt prefix bloat causing vLLM context-length failures.
        # RedisSessionStore already enforces this; InMemory should too.
        if max_context_chars is None:
            try:
                max_context_chars = int(os.getenv("INMEMORY_MAX_CONTEXT_CHARS", "8000"))
            except Exception:
                max_context_chars = 8000
        self._max_context_chars = int(max_context_chars) if max_context_chars is not None else 8000
        self._sessions: Dict[str, SessionState] = {}

    def _cap_context(self, s: SessionState) -> None:
        mc = int(self._max_context_chars or 0)
        if mc <= 0:
            return
        wc = s.working_context or ""
        if len(wc) <= mc:
            return
        seed = (s.seed_prefix or "").strip()
        if seed:
            # Preserve the seed prefix and keep the tail of the transcript.
            tail_budget = max(0, mc - (len(seed) + 2))
            tail = wc[-tail_budget:] if tail_budget > 0 else ""
            s.working_context = seed + ("\n\n" + tail if tail else "")
        else:
            s.working_context = wc[-mc:]

    def _is_expired(self, s: SessionState) -> bool:
        if self._ttl_seconds <= 0:
            return False
        return (time.time() - s.updated_at) > self._ttl_seconds

    def cleanup(self) -> None:
        """Opportunistic cleanup; safe to call frequently."""
        dead = [k for k, v in self._sessions.items() if self._is_expired(v)]
        for k in dead:
            self._sessions.pop(k, None)

    def get(self, session_key: str) -> Optional[SessionState]:
        s = self._sessions.get(session_key)
        if not s:
            return None
        if self._is_expired(s):
            self._sessions.pop(session_key, None)
            return None
        return s

    def get_or_create(self, session_key: str, system_prompt: str) -> SessionState:
        self.cleanup()
        existing = self.get(session_key)
        if existing:
            # Enforce immutability of the prefix system prompt.
            if (existing.system_prompt or "") != (system_prompt or ""):
                raise ValueError(
                    f"Session {session_key} system_prompt mismatch (prefix must be bit-identical)."
                )
            return existing

        s = SessionState(system_prompt=system_prompt or "")
        self._sessions[session_key] = s
        return s

    def seed_once(self, session_key: str, seed_prefix: str) -> None:
        """
        Seed a session with a deterministic prefix exactly once.

        Rules:
        - Seed must be bit-identical once set for a given session key.
        - If seed is provided and session has no seed yet, it becomes the initial working_context.
        - Seed is NOT wrapped in USER/ASSISTANT markers; callers should pass a plain block.
        """
        s = self._sessions.get(session_key)
        if not s:
            raise KeyError(f"Session not found: {session_key}")
        seed = (seed_prefix or "").strip()
        if not seed:
            return
        if (s.seed_prefix or "") and (s.seed_prefix or "") != seed:
            # Avoid hard-crashing a user session if different stages accidentally share a subsession.
            # KV-cache reuse is nice-to-have; correctness/availability is mandatory.
            allow_reset = os.getenv("ALLOW_SEED_PREFIX_RESET", "true").lower() == "true"
            if not allow_reset:
                raise ValueError(f"Session {session_key} seed_prefix mismatch (prefix must be bit-identical).")
            print(f"⚠️ [SESSION_STORE] seed_prefix mismatch; resetting session_key={session_key}")
            s.seed_prefix = seed
            s.working_context = seed
            s.touch()
            return
        if not (s.seed_prefix or ""):
            s.seed_prefix = seed
            if not (s.working_context or ""):
                s.working_context = seed
            s.touch()

    def append_user(self, session_key: str, text: str) -> None:
        s = self._sessions.get(session_key)
        if not s:
            raise KeyError(f"Session not found: {session_key}")
        chunk = (text or "").strip()
        if not chunk:
            return
        if s.working_context:
            s.working_context += "\n\n"
        s.working_context += f"USER: {chunk}"
        self._cap_context(s)
        s.touch()

    def append_assistant(self, session_key: str, text: str) -> None:
        s = self._sessions.get(session_key)
        if not s:
            raise KeyError(f"Session not found: {session_key}")
        chunk = (text or "").strip()
        if not chunk:
            return
        if s.working_context:
            s.working_context += "\n"
        s.working_context += f"ASSISTANT: {chunk}"
        self._cap_context(s)
        s.touch()

    def get_metadata(self, session_key: str) -> Dict[str, Any]:
        s = self._sessions.get(session_key)
        if not s:
            raise KeyError(f"Session not found: {session_key}")
        return s.metadata

    def set_metadata(self, session_key: str, key: str, value: Any) -> None:
        s = self._sessions.get(session_key)
        if not s:
            raise KeyError(f"Session not found: {session_key}")
        s.metadata[str(key)] = value
        s.touch()


