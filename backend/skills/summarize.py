from __future__ import annotations

import os
from typing import Any, Dict

from command_protocol import render_command
from minimal_prompts import MIN_SYSTEM_PROMPT_V1


SUMMARIZE_CONTRACT_V1 = """CONTRACT (summarize_skill):
- You summarize the provided facts into 3-7 concrete claims and 1 recommended next step.
- Do not invent engine numbers. Use facts as given.
- Output valid JSON only.

Return JSON:
{
  "claims": ["..."],
  "recommended_next_step": "..."
}
"""


async def summarize_facts(
    *,
    llm_router,
    task_id: str,
    facts: Dict[str, Any],
    model: str,
) -> Dict[str, Any]:
    cmd = render_command(
        command="SUMMARIZE_FACTS",
        input={"facts": facts},
        constraints={"json_only": True, "max_claims": 7},
    )
    return llm_router.complete_json(
        session_id=task_id,
        stage="summarize_skill",
        subsession="summarize_skill",
        system_prompt=MIN_SYSTEM_PROMPT_V1,
        task_seed=SUMMARIZE_CONTRACT_V1,
        user_text=cmd,
        model=model,
        temperature=0.0 if not str(model).startswith("gpt-5") else None,
        max_tokens=int(os.getenv("SUMMARIZE_FACTS_MAX_TOKENS", "450")),
    )





