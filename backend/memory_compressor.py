from __future__ import annotations

import os
from typing import Any, Dict, Optional

from command_protocol import render_command
from minimal_prompts import MIN_SYSTEM_PROMPT_V1


MEMORY_COMPRESS_CONTRACT_V1 = """CONTRACT (memory_compress):
- You compress task context into a small, stable memory object.
- Output valid JSON only.

Return JSON:
{
  "facts_card": {...},
  "decisions_so_far": ["..."],
  "open_questions": ["..."],
  "last_stop_reason": "..."
}
"""


async def compress_memory(
    *,
    llm_router,
    task_id: str,
    subsession: str,
    current_memory: Optional[Dict[str, Any]],
    evidence: Dict[str, Any],
    stop_reason: str,
    model: str,
) -> Dict[str, Any]:
    cmd = render_command(
        command="COMPRESS_MEMORY",
        input={
            "current_memory": current_memory or {},
            "evidence_keys": {
                "engine": sorted(list((evidence.get("engine") or {}).keys())),
                "chess": sorted(list((evidence.get("chess") or {}).keys())),
                "llm": sorted(list((evidence.get("llm") or {}).keys())),
            },
            "evidence_compact": {
                "engine": {k: evidence.get("engine", {}).get(k) for k in ["analysis", "analysis_deep", "move_compare"] if k in (evidence.get("engine") or {})},
                "chess": {k: evidence.get("chess", {}).get(k) for k in ["castling", "tags", "roles"] if k in (evidence.get("chess") or {})},
            },
            "stop_reason": stop_reason,
        },
        constraints={"json_only": True, "max_tokens": 350},
    )
    return llm_router.complete_json(
        session_id=task_id,
        stage="memory_compress",
        subsession=subsession,
        system_prompt=MIN_SYSTEM_PROMPT_V1,
        task_seed=MEMORY_COMPRESS_CONTRACT_V1,
        user_text=cmd,
        model=model,
        temperature=0.0 if not str(model).startswith("gpt-5") else None,
        max_tokens=int(os.getenv("MEMORY_COMPRESS_MAX_TOKENS", "350")),
    )





