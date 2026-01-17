"""
Learning-first logging helpers.

This module is intentionally lightweight:
- No training logic
- No raw text logging by default
- Best-effort inserts (never break product flow)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, List, Tuple
import hashlib
import uuid
import time
import os
import json

import chess  # type: ignore


def _safe_uuid(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    try:
        return str(uuid.UUID(str(s)))
    except Exception:
        return None


def _now_iso() -> str:
    # Use UTC ISO-ish string without importing datetime everywhere.
    # Supabase will store as timestamptz; backend can pass ISO strings safely.
    import datetime as _dt

    return _dt.datetime.utcnow().replace(tzinfo=_dt.timezone.utc).isoformat()


def normalize_fen(fen: str) -> str:
    """Normalize FEN using python-chess to ensure stable hashing."""
    try:
        return chess.Board(fen).fen()
    except Exception:
        return fen.strip()


def position_id_from_fen(fen: str) -> str:
    nf = normalize_fen(fen)
    h = hashlib.sha256(nf.encode("utf-8")).hexdigest()
    return f"fen_{h[:32]}"


def pv_hash(moves_uci: List[str]) -> str:
    blob = " ".join(moves_uci).strip()
    h = hashlib.sha256(blob.encode("utf-8")).hexdigest()
    return f"pv_{h[:24]}"


@dataclass(frozen=True)
class LearningHeaders:
    user_id: Optional[str]
    app_session_id: Optional[str]
    interaction_id: Optional[str]
    frontend_version: Optional[str]


def extract_learning_headers(headers: Dict[str, str]) -> LearningHeaders:
    # Headers are case-insensitive; FastAPI lowercases in request.headers.
    user_id = _safe_uuid(headers.get("x-user-id"))
    app_session_id = _safe_uuid(headers.get("x-app-session-id"))
    interaction_id = _safe_uuid(headers.get("x-interaction-id"))
    frontend_version = headers.get("x-frontend-version")
    # Allow logging for anonymous (not logged-in) users by using a stable nil UUID.
    # This prevents FK / NOT NULL failures downstream and keeps learning logs usable.
    if not user_id and os.getenv("LEARNING_ALLOW_ANON", "true").lower().strip() == "true":
        user_id = "00000000-0000-0000-0000-000000000000"
    return LearningHeaders(
        user_id=user_id,
        app_session_id=app_session_id,
        interaction_id=interaction_id,
        frontend_version=frontend_version,
    )


def ensure_interaction_id(h: LearningHeaders) -> str:
    return h.interaction_id or str(uuid.uuid4())


def infer_mode_from_path(path: str, fallback: str = "DISCUSS") -> str:
    p = (path or "").lower()
    if p in ("/play_move",):
        return "PLAY"
    if p in ("/analyze_position", "/analyze_move"):
        return "ANALYZE"
    if p in ("/tactics_next", "/check_lesson_move", "/check_opening_move"):
        return "TACTICS"
    if p.startswith("/llm_chat"):
        return "DISCUSS"
    return fallback


def infer_intent_from_path(path: str) -> str:
    p = (path or "").lower().strip("/")
    return p or "unknown"


def compute_ply(board: chess.Board) -> int:
    # Ply = half-move count since start.
    return (board.fullmove_number - 1) * 2 + (0 if board.turn == chess.WHITE else 1)


def tag_name(t: Any) -> Optional[str]:
    if isinstance(t, dict):
        return t.get("tag_name") or t.get("tag") or t.get("name")
    if isinstance(t, str):
        return t
    return None


def tags_to_names(tags: Any) -> List[str]:
    out: List[str] = []
    if isinstance(tags, list):
        for t in tags:
            n = tag_name(t)
            if n:
                out.append(n)
    return out


def build_tag_trace_simple(
    tags_start: Any,
    tags_final: Any,
    *,
    surface_plan: Optional[List[str]] = None,
) -> Dict[str, Any]:
    start_names = tags_to_names(tags_start)
    final_names = tags_to_names(tags_final)
    start_set = set(start_names)
    final_set = set(final_names)

    gained = sorted(list(final_set - start_set))
    lost = sorted(list(start_set - final_set))

    # Minimal "fired" representation. If you later have numeric tag scores, replace score=1.0.
    tags_fired = [{"tag": n, "score": 1.0, "source": "tagger"} for n in start_names]

    dominant_tag = start_names[0] if start_names else None
    runnerup_tag = start_names[1] if len(start_names) > 1 else None

    tag_deltas = []
    for n in gained:
        tag_deltas.append({"tag": n, "delta_score": 1.0, "before_score": 0.0, "after_score": 1.0})
    for n in lost:
        tag_deltas.append({"tag": n, "delta_score": -1.0, "before_score": 1.0, "after_score": 0.0})

    return {
        "tags_fired": tags_fired,
        "tags_fired_count": len(tags_fired),
        "dominant_tag": dominant_tag,
        "runnerup_tag": runnerup_tag,
        "competition_margin": None,
        "tag_deltas": tag_deltas,
        "resolution_rule_id": None,
        "tags_surface_plan": surface_plan or [],
        "tags_surface_plan_count": len(surface_plan or []),
    }


def get_model_versions(llm_router_config: Optional[Any] = None, request_model: Optional[str] = None) -> Dict[str, str]:
    """
    Extract model versioning info for logging.
    
    Returns:
        Dict with base_model, lora_version, eval_schema
    """
    # Base model: from LLM router config or request model or env var
    base_model = None
    if llm_router_config and hasattr(llm_router_config, 'vllm_model'):
        base_model = llm_router_config.vllm_model
    elif request_model:
        base_model = request_model
    else:
        base_model = os.getenv("VLLM_MODEL", os.getenv("BASE_MODEL", "unknown"))
    
    # LoRA version: from env var (default "v0" for no LoRA)
    lora_version = os.getenv("LORA_VERSION", "v0")
    
    # Eval schema version: from env var (default "v1")
    eval_schema = os.getenv("EVAL_SCHEMA_VERSION", "v1")
    
    return {
        "base_model": base_model,
        "lora_version": lora_version,
        "eval_schema": eval_schema,
    }


def get_engine_options(engine: Optional[Any] = None) -> Dict[str, Any]:
    """
    Extract Stockfish UCI options for deterministic replay.
    
    Returns:
        Dict of engine options (e.g., {"Threads": 4, "Hash": 1024})
    """
    if not engine:
        return {}
    
    options = {}
    try:
        # Try to get UCI options from engine if available
        if hasattr(engine, 'get_option'):
            # Common Stockfish options we care about
            option_names = ["Threads", "Hash", "MultiPV", "Skill Level", "UCI_LimitStrength"]
            for opt_name in option_names:
                try:
                    value = engine.get_option(opt_name)
                    if value is not None:
                        options[opt_name] = value
                except Exception:
                    pass
    except Exception:
        pass
    
    # Fallback: read from env vars if available
    if not options:
        threads = os.getenv("STOCKFISH_THREADS")
        hash_mb = os.getenv("STOCKFISH_HASH")
        if threads:
            options["Threads"] = int(threads)
        if hash_mb:
            options["Hash"] = int(hash_mb)
    
    return options


def get_canary_variant() -> Optional[str]:
    """
    Determine if this request should be routed through a canary variant.
    
    Returns:
        Variant identifier (e.g., "prompt_v2", "lora_v1") or None
    """
    if os.getenv("CANARY_ENABLED", "false").lower() != "true":
        return None
    
    # Simple percentage-based routing (1-5% of requests)
    import random
    canary_percentage = float(os.getenv("CANARY_PERCENTAGE", "1.0"))
    if random.random() * 100 > canary_percentage:
        return None
    
    # Return variant identifier
    variant = os.getenv("CANARY_VARIANT", "prompt_v2")
    return variant


