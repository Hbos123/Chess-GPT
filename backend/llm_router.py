"""
LLM Router

Single choke-point for all LLM calls.

Supports:
- vLLM (OpenAI-compatible) as primary provider
- Optional external OpenAI fallback provider (kept gated; may be disabled in vLLM-only mode)
- Session-aware, prefix-cache-friendly prompting via append-only SessionStore

Important KV-cache rules:
- Prefix must be bit-identical for cache reuse
- No dynamic content in the prefix (timestamps/UUIDs/counters)
- Append-only transcript; never rewrite prior tokens
"""

from __future__ import annotations

import hashlib
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Literal, Tuple, List

from openai import OpenAI

from session_store import InMemorySessionStore
from redis_session_store import build_session_store

Provider = Literal["vllm", "openai"]


def _stage_provider(stage: str) -> Provider:
    # Stage-specific overrides, e.g. EXPLAINER_PROVIDER=openai
    key = f"{stage.upper()}_PROVIDER"
    val = (os.getenv(key) or os.getenv("LLM_PROVIDER") or "vllm").lower().strip()
    return "openai" if val == "openai" else "vllm"


@dataclass
class LLMRouterConfig:
    # RunPod proxies usually expose the OpenAI-compatible API under /v1
    vllm_base_url: str = os.getenv("VLLM_BASE_URL", "https://ap1nybhfb76r0o-8000.proxy.runpod.net/v1")
    vllm_api_key: str = os.getenv("VLLM_API_KEY", "EMPTY")
    vllm_model: str = os.getenv("VLLM_MODEL", "/workspace/models/qwen2.5-32b-awq")

    openai_api_key: Optional[str] = os.getenv("OPENAI_API_KEY")

    # guardrails
    session_ttl_seconds: int = int(os.getenv("LLM_SESSION_TTL_SECONDS", str(60 * 60)))
    vllm_only: bool = (os.getenv("VLLM_ONLY", "true").lower().strip() == "true")
    # Health probe cache (avoid probing on every request)
    vllm_health_ttl_seconds: float = float(os.getenv("VLLM_HEALTH_TTL_SECONDS", "5"))
    # Router logging (high signal; intended for perf/caching audits)
    log_calls: bool = (os.getenv("LLM_ROUTER_LOG_CALLS", "true").lower().strip() == "true")
    # Streaming measurement enables TTFT capture, at the cost of slightly more plumbing.
    measure_ttft: bool = (os.getenv("LLM_ROUTER_MEASURE_TTFT", "true").lower().strip() == "true")
    # Simple circuit breaker (vLLM-only safety)
    cb_max_fails: int = int(os.getenv("VLLM_CB_MAX_FAILS", "3"))
    cb_window_seconds: float = float(os.getenv("VLLM_CB_WINDOW_S", "30"))
    cb_cooldown_seconds: float = float(os.getenv("VLLM_CB_COOLDOWN_S", "30"))


class LLMRouter:
    def __init__(self, config: Optional[LLMRouterConfig] = None):
        self.config = config or LLMRouterConfig()
        # Session store selection (memory by default, redis optional).
        # Redis is required for multi-user persistence across restarts.
        _redis_store = build_session_store(ttl_seconds=self.config.session_ttl_seconds)
        self.sessions = _redis_store or InMemorySessionStore(ttl_seconds=self.config.session_ttl_seconds)

        # vLLM is OpenAI-compatible, requires dummy api_key.
        self.vllm_client = OpenAI(
            base_url=self.config.vllm_base_url,
            api_key=self.config.vllm_api_key,
        )

        self.openai_client: Optional[OpenAI] = None
        if self.config.openai_api_key:
            try:
                self.openai_client = OpenAI(api_key=self.config.openai_api_key)
            except Exception:
                self.openai_client = None

        # Health probe memoization
        self._vllm_health_last_ok: Optional[bool] = None
        self._vllm_health_last_ts: float = 0.0
        self._vllm_health_last_url: Optional[str] = None  # Track URL changes to invalidate cache
        # Circuit breaker state
        self._cb_fail_ts: List[float] = []
        self._cb_open_until: float = 0.0

    def _client_for(self, provider: Provider) -> Tuple[OpenAI, str]:
        if provider == "openai":
            if self.config.vllm_only:
                raise RuntimeError("VLLM_ONLY is enabled; openai provider is not allowed.")
            if not self.openai_client:
                raise RuntimeError("OPENAI_API_KEY not configured for openai provider.")
            # Model selection for OpenAI is stage-specific in calling code.
            return self.openai_client, ""
        return self.vllm_client, self.config.vllm_model

    def _session_key(self, task_id: str, subsession: str) -> str:
        """
        Task-session primary keying.

        - task_id: stable per user task/thread (frontend tab is a good choice)
        - subsession: deterministic internal stream (e.g. main, planner_think, explainer_draft)
        """
        base = task_id or "default"
        sub = (subsession or "main").strip()
        return f"{base}:{sub}"

    def ensure_session(
        self,
        *,
        task_id: str,
        subsession: str,
        system_prompt: str,
        task_seed: Optional[str] = None,
    ) -> str:
        """Ensure a session exists and is seeded; returns the internal session key."""
        skey = self._session_key(task_id, subsession)
        self.sessions.get_or_create(skey, system_prompt or "")
        if task_seed:
            self.sessions.seed_once(skey, task_seed)
        return skey

    def append_user_visible(
        self,
        *,
        task_id: str,
        text: str,
        system_prompt: str,
        task_seed: Optional[str] = None,
        subsession: str = "main",
    ) -> None:
        """Append a user-visible message to the task's main transcript (no LLM call)."""
        skey = self.ensure_session(task_id=task_id, subsession=subsession, system_prompt=system_prompt, task_seed=task_seed)
        self.sessions.append_user(skey, text)

    def append_assistant_visible(
        self,
        *,
        task_id: str,
        text: str,
        system_prompt: str,
        task_seed: Optional[str] = None,
        subsession: str = "main",
    ) -> None:
        """Append an assistant-visible message to the task's main transcript (no LLM call)."""
        skey = self.ensure_session(task_id=task_id, subsession=subsession, system_prompt=system_prompt, task_seed=task_seed)
        self.sessions.append_assistant(skey, text)

    def complete_main(
        self,
        *,
        task_id: str,
        stage: str,
        system_prompt: str,
        task_seed: Optional[str],
        user_text: str,
        temperature: Optional[float] = None,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Convenience wrapper for Cursor-style discipline:
        - always use the task's 'main' subsession for user-visible chat
        - keep internal work in separate subsessions
        """
        return self.complete(
            session_id=task_id,
            stage=stage,
            subsession="main",
            system_prompt=system_prompt,
            task_seed=task_seed,
            user_text=user_text,
            temperature=temperature,
            model=model,
            max_tokens=max_tokens,
        )

    def get_task_memory(self, *, task_id: str, subsession: str = "main") -> Optional[Dict[str, Any]]:
        skey = self._session_key(task_id, subsession)
        try:
            md = self.sessions.get_metadata(skey)
            v = md.get("task_memory")
            return v if isinstance(v, dict) else None
        except Exception:
            return None

    def set_task_memory(self, *, task_id: str, memory: Dict[str, Any], subsession: str = "main") -> None:
        skey = self._session_key(task_id, subsession)
        self.sessions.set_metadata(skey, "task_memory", memory)

    def _hash_text(self, s: str) -> str:
        return hashlib.sha256((s or "").encode("utf-8")).hexdigest()[:16]

    def _log_call(
        self,
        *,
        session_id: str,
        stage: str,
        provider: Provider,
        model: str,
        system_prompt: str,
        prefix_chars: int,
        user_chunk_chars: int,
        response_chars: int,
        ttft_ms: Optional[float],
        total_ms: float,
        tokens_in: Optional[int],
        tokens_out: Optional[int],
        error: Optional[str] = None,
    ) -> None:
        if not self.config.log_calls:
            return
        sys_hash = self._hash_text(system_prompt or "")
        err_str = f" error={error!r}" if error else ""
        print(
            "   🔎 [LLM_ROUTER]"
            f" stage={stage}"
            f" provider={provider}"
            f" model={model}"
            f" session={session_id}"
            f" sys={sys_hash}"
            f" prefix_chars={prefix_chars}"
            f" user_chars={user_chunk_chars}"
            f" out_chars={response_chars}"
            f" ttft_ms={(round(ttft_ms, 1) if isinstance(ttft_ms, (int, float)) else None)}"
            f" total_ms={round(total_ms, 1)}"
            f" tokens_in={tokens_in}"
            f" tokens_out={tokens_out}"
            f"{err_str}"
        )

    def check_vllm_health(self, *, force: bool = False) -> None:
        """
        Fail-fast vLLM health probe.

        - Cached for a short TTL to avoid probing on every completion call.
        - Raises RuntimeError when unhealthy.
        - Automatically invalidates cache if vLLM URL changes.
        """
        now = time.monotonic()
        # Invalidate cache if URL changed
        if self._vllm_health_last_url != self.config.vllm_base_url:
            self._vllm_health_last_ok = None
            self._vllm_health_last_ts = 0.0
            self._vllm_health_last_url = self.config.vllm_base_url
        
        if self._cb_open_until and now < self._cb_open_until:
            raise RuntimeError(f"vLLM circuit breaker open for {round(self._cb_open_until - now, 2)}s")
        if not force and self.config.vllm_health_ttl_seconds > 0:
            age = now - self._vllm_health_last_ts
            if self._vllm_health_last_ok is not None and age < self.config.vllm_health_ttl_seconds:
                if self._vllm_health_last_ok is True:
                    return
                raise RuntimeError("vLLM health check failed (cached).")

        ok = False
        err: Optional[str] = None
        try:
            # OpenAI SDK call (OpenAI-compatible). Most servers support this.
            _ = self.vllm_client.models.list()
            ok = True
        except Exception as e:
            ok = False
            err = str(e)

        self._vllm_health_last_ok = ok
        self._vllm_health_last_ts = now

        if not ok:
            # Record failure and potentially open circuit breaker.
            try:
                self._cb_fail_ts.append(now)
                window = float(self.config.cb_window_seconds)
                if window > 0:
                    self._cb_fail_ts = [t for t in self._cb_fail_ts if (now - t) <= window]
                if self.config.cb_max_fails > 0 and len(self._cb_fail_ts) >= self.config.cb_max_fails:
                    self._cb_open_until = now + float(self.config.cb_cooldown_seconds)
            except Exception:
                pass
            raise RuntimeError(f"vLLM health check failed: {err}")
        else:
            # Healthy -> clear failure history.
            try:
                self._cb_fail_ts.clear()
                self._cb_open_until = 0.0
            except Exception:
                pass

    def _create_chat_completion(
        self,
        *,
        client: OpenAI,
        kwargs: Dict[str, Any],
    ):
        """
        Internal helper that optionally streams to measure TTFT.
        Returns: (resp, content, ttft_ms)
        """
        if not self.config.measure_ttft:
            t0 = time.monotonic()
            resp = client.chat.completions.create(**kwargs)
            dt_ms = (time.monotonic() - t0) * 1000.0
            content = (resp.choices[0].message.content or "").strip()
            # Non-streaming cannot observe TTFT; set None.
            return resp, content, None, dt_ms

        # Stream to capture first token time.
        t0 = time.monotonic()
        first_token_ts: Optional[float] = None
        chunks = []
        # OpenAI SDK: stream=True yields events with delta content.
        stream = client.chat.completions.create(**{**kwargs, "stream": True})
        resp_final = None
        try:
            for event in stream:
                # event is ChatCompletionChunk; may include choices[0].delta.content
                try:
                    delta = event.choices[0].delta
                    piece = getattr(delta, "content", None)
                except Exception:
                    piece = None
                if piece:
                    if first_token_ts is None:
                        first_token_ts = time.monotonic()
                    chunks.append(piece)
                resp_final = event  # keep last event (may include usage on some servers)
        finally:
            # Some SDK versions support close() on stream; ignore if missing.
            try:
                stream.close()  # type: ignore[attr-defined]
            except Exception:
                pass

        content = ("".join(chunks) or "").strip()
        ttft_ms = ((first_token_ts - t0) * 1000.0) if first_token_ts is not None else None
        total_ms = (time.monotonic() - t0) * 1000.0
        return resp_final, content, ttft_ms, total_ms

    def complete(
        self,
        *,
        session_id: str,
        stage: str,
        system_prompt: str,
        user_text: str,
        task_seed: Optional[str] = None,
        subsession: Optional[str] = None,
        response_format: Optional[Dict[str, Any]] = None,
        temperature: Optional[float] = None,
        model: Optional[str] = None,
        provider: Optional[Provider] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Session-aware completion.

        Prompt structure is intentionally a single user message containing the append-only transcript:
          <working_context>\n\nUSER: <new>\nASSISTANT:

        That makes the prefix caching behavior explicit and avoids relying on provider-specific
        chat templates across multiple message roles.
        """
        provider = provider or _stage_provider(stage)
        if self.config.vllm_only and provider != "vllm":
            raise RuntimeError("VLLM_ONLY is enabled; non-vLLM providers are disabled.")
        client, default_model = self._client_for(provider)
        # Guardrail: most of this codebase still passes OpenAI model names like "gpt-5".
        # If we're targeting vLLM, prefer the configured vLLM model id/path.
        if provider == "vllm" and isinstance(model, str) and model.lower().startswith("gpt-"):
            model = None
        chosen_model = model or default_model
        if not chosen_model:
            raise ValueError("Model must be provided for openai provider.")

        if provider == "vllm":
            # Fail fast if vLLM is unhealthy; prevents hidden fallbacks + confusing partial behavior.
            self.check_vllm_health()

        skey = self._session_key(session_id, subsession or stage)
        state = self.sessions.get_or_create(skey, system_prompt or "")
        if task_seed:
            # Seed a deterministic prefix once per session (contract/task seed).
            self.sessions.seed_once(skey, task_seed)

        # Build append-only prompt without rewriting prior tokens.
        prefix = state.working_context or ""
        user_chunk = (user_text or "").strip()
        prefix_chars = len(prefix or "")
        prompt_text = prefix
        if prompt_text:
            prompt_text += "\n\n"
        prompt_text += f"USER: {user_chunk}\nASSISTANT:"

        kwargs: Dict[str, Any] = {
            "model": chosen_model,
            "messages": [
                {"role": "system", "content": state.system_prompt},
                {"role": "user", "content": prompt_text},
            ],
        }
        if response_format is not None:
            kwargs["response_format"] = response_format
        if temperature is not None and "gpt-5" not in chosen_model.lower():
            kwargs["temperature"] = temperature
        if max_tokens is not None:
            # vLLM usually supports max_tokens; keep this as a compatibility knob.
            kwargs["max_tokens"] = int(max_tokens)

        # vLLM-only by default. Any fallback must be explicitly disabled by config.
        # (Your deployment choice: fail fast, no silent provider switching.)
        try:
            resp, content, ttft_ms, total_ms = self._create_chat_completion(client=client, kwargs=kwargs)
        except Exception as e:
            self._log_call(
                session_id=session_id,
                stage=stage,
                provider=provider,
                model=str(chosen_model),
                system_prompt=state.system_prompt,
                prefix_chars=prefix_chars,
                user_chunk_chars=len(user_chunk or ""),
                response_chars=0,
                ttft_ms=None,
                total_ms=0.0,
                tokens_in=None,
                tokens_out=None,
                error=str(e)[:200],
            )
            raise

        # Try to pull usage if the provider includes it (vLLM often does).
        tokens_in = None
        tokens_out = None
        try:
            usage = getattr(resp, "usage", None)
            if usage is not None:
                tokens_in = getattr(usage, "prompt_tokens", None)
                tokens_out = getattr(usage, "completion_tokens", None)
        except Exception:
            tokens_in = None
            tokens_out = None

        # Persist append-only transcript (KV-cache friendly).
        self.sessions.append_user(skey, user_chunk)
        self.sessions.append_assistant(skey, content)

        self._log_call(
            session_id=session_id,
            stage=stage,
            provider=provider,
            model=str(chosen_model),
            system_prompt=state.system_prompt,
            prefix_chars=prefix_chars,
            user_chunk_chars=len(user_chunk or ""),
            response_chars=len(content or ""),
            ttft_ms=ttft_ms,
            total_ms=total_ms,
            tokens_in=tokens_in if isinstance(tokens_in, int) else None,
            tokens_out=tokens_out if isinstance(tokens_out, int) else None,
        )
        return content

    def complete_json(
        self,
        *,
        session_id: str,
        stage: str,
        system_prompt: str,
        user_text: str,
        task_seed: Optional[str] = None,
        subsession: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        model: Optional[str] = None,
        provider: Optional[Provider] = None,
    ) -> Dict[str, Any]:
        txt = self.complete(
            session_id=session_id,
            stage=stage,
            system_prompt=system_prompt,
            user_text=user_text,
            task_seed=task_seed,
            subsession=subsession,
            response_format={"type": "json_object"},
            temperature=temperature,
            model=model,
            provider=provider,
            max_tokens=max_tokens,
        )
        import json
        try:
            return json.loads(txt)
        except Exception:
            # Best-effort JSON repair for models that emit stray prefixes/suffixes or code fences.
            # We keep this small and deterministic: extract the outermost {...} and try again.
            s = (txt or "").strip()
            # Strip common code fences
            if s.startswith("```"):
                s = s.strip("`")
            # Extract first JSON object
            i = s.find("{")
            j = s.rfind("}")
            if i != -1 and j != -1 and j > i:
                candidate = s[i : j + 1]
                try:
                    return json.loads(candidate)
                except Exception as e2:
                    # Log a compact snippet for debugging in backend.log (used by /debug/backend_log_tail).
                    try:
                        head = (s[:800] + ("…<truncated>" if len(s) > 800 else ""))
                        tail = (s[-400:] if len(s) > 400 else s)
                        print(
                            "❌ [LLM_JSON_PARSE] complete_json failed after repair"
                            f" stage={stage} session_id={session_id} subsession={subsession or 'main'}"
                            f" err1=nonjson err2={type(e2).__name__}: {str(e2)[:140]}"
                        )
                        print(f"❌ [LLM_JSON_PARSE] raw_head:\n{head}")
                        if tail and tail != head:
                            print(f"❌ [LLM_JSON_PARSE] raw_tail:\n{tail}")
                    except Exception:
                        pass
                    raise
            # No braces at all → log and raise.
            try:
                head = ((s[:800] + ("…<truncated>" if len(s) > 800 else "")) if isinstance(s, str) else "")
                print(
                    "❌ [LLM_JSON_PARSE] complete_json failed: no JSON object found"
                    f" stage={stage} session_id={session_id} subsession={subsession or 'main'}"
                )
                if head:
                    print(f"❌ [LLM_JSON_PARSE] raw_head:\n{head}")
            except Exception:
                pass
            raise


