from __future__ import annotations

import json
import os
import time
from dataclasses import asdict
from typing import Any, Dict, Optional


def _now() -> float:
    return time.time()


class RedisSessionStore:
    """
    Redis-backed session store implementing the same API surface as InMemorySessionStore.

    Properties:
    - system_prompt is immutable per session key (bit-identical)
    - working_context is append-only
    - seed_prefix is set-once and must remain bit-identical
    - metadata is a small JSON blob (task_memory, etc.)

    Storage layout:
    - Redis HASH at key: session_key
      fields: system_prompt, seed_prefix, working_context, metadata_json, created_at, updated_at
    - key is EXPIRE'd on write to enforce TTL
    """

    def __init__(
        self,
        *,
        redis_url: Optional[str] = None,
        ttl_seconds: int = 60 * 60,
        max_context_chars: int = 250_000,
    ):
        self.redis_url = redis_url or os.getenv("REDIS_URL") or "redis://localhost:6379/0"
        self.ttl_seconds = int(ttl_seconds)
        self.max_context_chars = int(max_context_chars)

        try:
            import redis  # type: ignore
        except Exception as e:
            raise RuntimeError("redis package is required for RedisSessionStore") from e

        # Sync client is OK here: session ops are small, and the existing LLMRouter is sync.
        self._r = redis.Redis.from_url(self.redis_url, decode_responses=True)

    def _expire(self, session_key: str) -> None:
        if self.ttl_seconds > 0:
            try:
                self._r.expire(session_key, self.ttl_seconds)
            except Exception:
                pass

    def _hgetall(self, session_key: str) -> Optional[Dict[str, str]]:
        try:
            d = self._r.hgetall(session_key)
            return d if isinstance(d, dict) and d else None
        except Exception:
            return None

    def get_or_create(self, session_key: str, system_prompt: str):
        existing = self._hgetall(session_key)
        if existing:
            if (existing.get("system_prompt") or "") != (system_prompt or ""):
                raise ValueError(f"Session {session_key} system_prompt mismatch (prefix must be bit-identical).")
            return existing

        created = {
            "system_prompt": system_prompt or "",
            "seed_prefix": "",
            "working_context": "",
            "metadata_json": "{}",
            "created_at": str(_now()),
            "updated_at": str(_now()),
        }
        try:
            self._r.hset(session_key, mapping=created)
            self._expire(session_key)
        except Exception as e:
            raise RuntimeError(f"Failed to create session in Redis: {str(e)[:120]}") from e
        return created

    def seed_once(self, session_key: str, seed_prefix: str) -> None:
        seed = (seed_prefix or "").strip()
        if not seed:
            return
        d = self._hgetall(session_key)
        if not d:
            raise KeyError(f"Session not found: {session_key}")

        existing_seed = (d.get("seed_prefix") or "").strip()
        if existing_seed and existing_seed != seed:
            allow_reset = os.getenv("ALLOW_SEED_PREFIX_RESET", "true").lower() == "true"
            if not allow_reset:
                raise ValueError(f"Session {session_key} seed_prefix mismatch (prefix must be bit-identical).")
            # Reset instead of crashing the whole session.
            try:
                self._r.hset(
                    session_key,
                    mapping={"seed_prefix": seed, "working_context": seed, "updated_at": str(_now())},
                )
                self._expire(session_key)
            except Exception as e:
                raise RuntimeError(f"Failed to reset seed_prefix: {str(e)[:120]}") from e
            return
        if existing_seed:
            return

        wc = (d.get("working_context") or "").strip()
        if not wc:
            wc = seed
        try:
            self._r.hset(
                session_key,
                mapping={"seed_prefix": seed, "working_context": wc, "updated_at": str(_now())},
            )
            self._expire(session_key)
        except Exception as e:
            raise RuntimeError(f"Failed to seed session: {str(e)[:120]}") from e

    def _append(self, session_key: str, chunk: str, *, role: str) -> None:
        c = (chunk or "").strip()
        if not c:
            return
        d = self._hgetall(session_key)
        if not d:
            raise KeyError(f"Session not found: {session_key}")

        wc = d.get("working_context") or ""
        if role == "USER":
            if wc:
                wc += "\n\n"
            wc += f"USER: {c}"
        else:
            if wc:
                wc += "\n"
            wc += f"ASSISTANT: {c}"

        if self.max_context_chars > 0 and len(wc) > self.max_context_chars:
            # Fail safe: do not allow unbounded growth (bad for caching + memory).
            wc = wc[-self.max_context_chars :]

        try:
            self._r.hset(session_key, mapping={"working_context": wc, "updated_at": str(_now())})
            self._expire(session_key)
        except Exception as e:
            raise RuntimeError(f"Failed to append {role}: {str(e)[:120]}") from e

    def append_user(self, session_key: str, text: str) -> None:
        self._append(session_key, text, role="USER")

    def append_assistant(self, session_key: str, text: str) -> None:
        self._append(session_key, text, role="ASSISTANT")

    def get_metadata(self, session_key: str) -> Dict[str, Any]:
        d = self._hgetall(session_key)
        if not d:
            raise KeyError(f"Session not found: {session_key}")
        raw = d.get("metadata_json") or "{}"
        try:
            obj = json.loads(raw)
            return obj if isinstance(obj, dict) else {}
        except Exception:
            return {}

    def set_metadata(self, session_key: str, key: str, value: Any) -> None:
        md = self.get_metadata(session_key)
        md[str(key)] = value
        try:
            self._r.hset(session_key, mapping={"metadata_json": json.dumps(md, ensure_ascii=False), "updated_at": str(_now())})
            self._expire(session_key)
        except Exception as e:
            raise RuntimeError(f"Failed to set metadata: {str(e)[:120]}") from e


def build_session_store(*, ttl_seconds: int):
    """
    Factory: SESSION_STORE=redis|memory (default memory if redis not configured/importable).
    """
    mode = (os.getenv("SESSION_STORE") or "memory").lower().strip()
    if mode == "redis":
        try:
            return RedisSessionStore(
                redis_url=os.getenv("REDIS_URL"),
                ttl_seconds=int(os.getenv("SESSION_TTL_SECONDS", str(ttl_seconds))),
                max_context_chars=int(os.getenv("SESSION_MAX_CONTEXT_CHARS", "250000")),
            )
        except Exception as e:
            print(f"⚠️ Redis session store unavailable; falling back to in-memory: {type(e).__name__}: {e}")
            return None
    return None



