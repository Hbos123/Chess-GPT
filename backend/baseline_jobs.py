from __future__ import annotations

import asyncio
import json
import os
import time
import hashlib
from dataclasses import dataclass
from typing import Any, Dict, Optional

import chess  # type: ignore


def _normalize_fen(fen: str) -> str:
    try:
        return chess.Board(fen).fen()
    except Exception:
        return (fen or "").strip()


def _safe_key_part(x: Optional[str]) -> str:
    s = (x or "").strip()
    return s if s else "anon"


@dataclass
class BaselineJob:
    key: str
    fen: str
    created_at_s: float
    task: asyncio.Task
    meta: Dict[str, Any]


class BaselineJobs:
    """
    In-memory job cache for baseline intuition.
    Goal: allow board to prefetch baseline while user composes message; chat awaits completion.
    """

    def __init__(self, *, max_jobs: int = 64) -> None:
        self._lock = asyncio.Lock()
        self._jobs: Dict[str, BaselineJob] = {}
        self._max_jobs = int(max_jobs)

        # Default: keep caches under backend/cache/... (not backend/backend/cache/...).
        # If BASELINE_CACHE_DIR is provided, respect it and disable legacy fallback.
        env_cache_dir = os.getenv("BASELINE_CACHE_DIR")
        if env_cache_dir:
            self._cache_dir = env_cache_dir
            self._legacy_cache_dir = None
        else:
            self._cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache", "baseline_intuition")
            # Legacy path from earlier iterations (kept for fallback/migration).
            self._legacy_cache_dir = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "backend",
                "cache",
                "baseline_intuition",
            )
        os.makedirs(self._cache_dir, exist_ok=True)
        self._cache_ttl_s = float(os.getenv("BASELINE_CACHE_TTL_S", "86400"))  # 24h default

    def make_key(self, *, app_session_id: Optional[str], thread_id: Optional[str], fen: str) -> str:
        nfen = _normalize_fen(fen)
        # Use a stable short digest segment (avoid Python hash seed variance).
        digest8 = hashlib.sha256(nfen.encode("utf-8")).hexdigest()[:10]
        # Include a schema/version segment so we can evolve baseline artifacts without serving stale caches.
        # Bump BASELINE_CACHE_VERSION to invalidate old disk caches.
        ver = (os.getenv("BASELINE_CACHE_VERSION", "v1") or "v1").strip()
        return f"bi:{ver}:{_safe_key_part(app_session_id)}:{_safe_key_part(thread_id)}:{digest8}"

    def _cache_path(self, *, fen: str, include_second_pass: bool) -> str:
        nfen = _normalize_fen(fen)
        ver = (os.getenv("BASELINE_CACHE_VERSION", "v1") or "v1").strip()
        key = f"{ver}|{nfen}|second_pass={1 if include_second_pass else 0}"
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return os.path.join(self._cache_dir, f"bi_{digest}.json")

    def _legacy_cache_path(self, *, fen: str, include_second_pass: bool) -> Optional[str]:
        if not self._legacy_cache_dir:
            return None
        nfen = _normalize_fen(fen)
        key = f"{nfen}|second_pass={1 if include_second_pass else 0}"
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return os.path.join(self._legacy_cache_dir, f"bi_{digest}.json")

    def _cache_load(self, *, fen: str, include_second_pass: bool) -> Optional[Dict[str, Any]]:
        try:
            p = self._cache_path(fen=fen, include_second_pass=include_second_pass)
            if not os.path.exists(p):
                # Legacy fallback: if the old path has the cache, load it and migrate into new dir.
                lp = self._legacy_cache_path(fen=fen, include_second_pass=include_second_pass)
                if lp and os.path.exists(lp):
                    p = lp
                else:
                    return None
            st = os.stat(p)
            if self._cache_ttl_s > 0 and (time.time() - st.st_mtime) > self._cache_ttl_s:
                return None
            with open(p, "r", encoding="utf-8") as f:
                payload = json.load(f)
            if isinstance(payload, dict) and payload.get("start_fen"):
                # If loaded from legacy path, best-effort migrate to new dir.
                try:
                    expected = self._cache_path(fen=fen, include_second_pass=include_second_pass)
                    if os.path.abspath(p) != os.path.abspath(expected):
                        self._cache_save(fen=fen, include_second_pass=include_second_pass, payload=payload)
                except Exception:
                    pass
                return payload
        except Exception:
            return None
        return None

    def _cache_save(self, *, fen: str, include_second_pass: bool, payload: Dict[str, Any]) -> None:
        try:
            p = self._cache_path(fen=fen, include_second_pass=include_second_pass)
            tmp = p + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(payload, f)
            os.replace(tmp, p)
        except Exception:
            pass

    async def _evict_if_needed(self) -> None:
        # Drop oldest completed jobs first, otherwise oldest jobs.
        if len(self._jobs) <= self._max_jobs:
            return
        items = list(self._jobs.items())
        completed = [(k, j) for (k, j) in items if j.task.done()]
        pool = completed if completed else [j for j in items]
        pool.sort(key=lambda kv: float(kv[1].created_at_s))
        for k, _ in pool[: max(1, len(self._jobs) - self._max_jobs)]:
            self._jobs.pop(k, None)

    async def ensure_task(
        self,
        *,
        key: str,
        fen: str,
        engine_pool_instance=None,
        engine_queue=None,
        policy=None,
    ) -> asyncio.Task:
        """
        Ensure a baseline job exists for key. If key exists but fen differs, replace it.
        """
        nfen = _normalize_fen(fen)
        include_second_pass = str(os.getenv("BASELINE_INCLUDE_SECOND_PASS", "false")).lower().strip() == "true"

        async with self._lock:
            existing = self._jobs.get(key)
            if existing and existing.fen == nfen:
                return existing.task
            if existing and existing.fen != nfen:
                try:
                    existing.task.cancel()
                except Exception:
                    pass
                self._jobs.pop(key, None)

            job_meta: Dict[str, Any] = {
                "source": "unknown",  # disk_cache | compute
                "started_at_s": time.time(),
                "done_at_s": None,
                "duration_ms": None,
                "stage": "starting",
                "stage_detail": None,
                "last_update_s": time.time(),
            }

            def _progress(stage: str, detail: Dict[str, Any]) -> None:
                # Best-effort: keep it tiny + safe (no exceptions, no awaits).
                try:
                    job_meta["stage"] = str(stage or "running")
                    job_meta["stage_detail"] = detail if isinstance(detail, dict) else None
                    job_meta["last_update_s"] = time.time()
                except Exception:
                    pass

            async def _run() -> Dict[str, Any]:
                from skills.baseline_intuition import run_baseline_intuition, BaselineIntuitionPolicy
                from scan_service import ScanPolicy
                from skills.motifs import MotifPolicy
                import os

                cached = self._cache_load(fen=nfen, include_second_pass=include_second_pass)
                if cached is not None:
                    job_meta["source"] = "disk_cache"
                    job_meta["stage"] = "disk_cache_hit"
                    job_meta["last_update_s"] = time.time()
                    job_meta["done_at_s"] = time.time()
                    job_meta["duration_ms"] = int((job_meta["done_at_s"] - job_meta["started_at_s"]) * 1000)
                    return cached

                job_meta["source"] = "compute"
                _progress("policy", {"include_second_pass": include_second_pass})
                scan_pol = ScanPolicy(
                    d2_depth=int(os.getenv("SCAN_D2_DEPTH", "2")),
                    d16_depth=int(os.getenv("SCAN_D16_DEPTH", "16")),
                    branching_limit=int(os.getenv("SCAN_BRANCHING_LIMIT", "4")),
                    max_pv_plies=int(os.getenv("SCAN_MAX_PV_PLIES", "16")),
                    include_pgn=(str(os.getenv("SCAN_INCLUDE_PGN", "true")).lower().strip() == "true"),
                    pgn_max_chars=int(os.getenv("SCAN_PGN_MAX_CHARS", "12000")),
                    timeout_s=float(os.getenv("SCAN_TIMEOUT_S", "18")),
                )
                motif_pol = MotifPolicy(
                    max_pattern_plies=int(os.getenv("MOTIFS_MAX_PATTERN_PLIES", "4")),
                    motifs_top=int(os.getenv("MOTIFS_TOP", "25")),
                    max_line_plies=int(os.getenv("MOTIFS_MAX_LINE_PLIES", "10")),
                    max_branch_lines=int(os.getenv("MOTIFS_MAX_BRANCH_LINES", "12")),
                )
                baseline_pol = (
                    BaselineIntuitionPolicy(scan=scan_pol, motifs=motif_pol, include_second_pass=include_second_pass)
                    if policy is None
                    else policy
                )
                _progress("baseline_start", {"d2_depth": int(scan_pol.d2_depth), "d16_depth": int(scan_pol.d16_depth), "branching_limit": int(scan_pol.branching_limit)})
                out = await run_baseline_intuition(
                    engine_pool_instance=engine_pool_instance,
                    engine_queue=engine_queue,
                    start_fen=nfen,
                    policy=baseline_pol,
                    progress_cb=_progress,
                )
                if isinstance(out, dict) and out.get("scan_root"):
                    self._cache_save(fen=nfen, include_second_pass=include_second_pass, payload=out)
                    _progress("saved_to_disk_cache", {})
                job_meta["done_at_s"] = time.time()
                job_meta["duration_ms"] = int((job_meta["done_at_s"] - job_meta["started_at_s"]) * 1000)
                _progress("done", {"duration_ms": job_meta["duration_ms"]})
                return out

            t = asyncio.create_task(_run())
            self._jobs[key] = BaselineJob(key=key, fen=nfen, created_at_s=time.time(), task=t, meta=job_meta)
            await self._evict_if_needed()
            return t

    async def get_status(self, key: str) -> Dict[str, Any]:
        async with self._lock:
            j = self._jobs.get(key)
        if not j:
            return {"exists": False}
        if j.task.done():
            err = None
            try:
                _ = j.task.result()
            except Exception as e:
                err = f"{type(e).__name__}:{str(e)[:120]}"
            return {"exists": True, "done": True, "fen": j.fen, "error": err, "meta": j.meta}
        return {"exists": True, "done": False, "fen": j.fen, "meta": j.meta}


baseline_jobs = BaselineJobs()


