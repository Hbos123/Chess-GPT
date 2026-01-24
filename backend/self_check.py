from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from command_protocol import render_command
from minimal_prompts import MIN_SYSTEM_PROMPT_V1, SELF_CHECK_CONTRACT_V1


def _artifact_flags(evidence: Dict[str, Any]) -> Dict[str, bool]:
    # Very lightweight presence checks.
    engine = (evidence or {}).get("engine") or {}
    chess = (evidence or {}).get("chess") or {}
    llm = (evidence or {}).get("llm") or {}
    return {
        "castling_check": "castling" in chess,
        "engine_eval": "analysis" in engine,
        "pv": "analysis" in engine,
        "candidates": "analysis" in engine,
        "threats": "threats" in engine,
        "tags": "tags" in chess,
        "roles": "roles" in chess,
        "material_delta": "material_delta" in chess,
        "opening_lookup": "opening" in chess,
        "move_compare": "move_compare" in engine,
        "intent": "intent_plan" in llm,
    }


async def self_check(
    *,
    llm_router,
    task_id: str,
    goal: Dict[str, Any],
    evidence: Dict[str, Any],
    model: str,
) -> Dict[str, Any]:
    """
    LLM-based self-check. vLLM-only.
    """
    cmd = render_command(
        command="SELF_CHECK",
        input={
            "goal": goal,
            "artifacts_present": _artifact_flags(evidence),
            "evidence_keys": {
                "engine": sorted(list((evidence.get("engine") or {}).keys())),
                "chess": sorted(list((evidence.get("chess") or {}).keys())),
                "llm": sorted(list((evidence.get("llm") or {}).keys())),
            },
        },
        constraints={"json_only": True},
    )
    return llm_router.complete_json(
        session_id=task_id,
        stage="self_check",
        subsession="self_check",
        system_prompt=MIN_SYSTEM_PROMPT_V1,
        task_seed=SELF_CHECK_CONTRACT_V1,
        user_text=cmd,
        model=model,
        temperature=0.0 if not str(model).startswith("gpt-5") else None,
    )






