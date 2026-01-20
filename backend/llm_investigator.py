"""
Generic LLM investigator loop (domain-agnostic).

This module is intentionally minimal: it provides an iterative refinement scaffold that can
later be extended with heuristic checks, tool calls, or model escalation.

It uses LLMRouter + SessionStore so vLLM prefix caching can reuse KV across iterations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Dict, Any, List

from llm_router import LLMRouter


@dataclass
class InvestigatorResult:
    goal: str
    final_answer: str
    iterations: int
    notes: List[str]


def run_investigator(
    *,
    router: LLMRouter,
    session_id: str,
    goal: str,
    system_prompt: str = "You are an investigator. Be concise, grounded, and stop when the goal is satisfied.",
    max_iters: int = 3,
    stop_when: Optional[Callable[[str], bool]] = None,
    stage: str = "investigator",
) -> InvestigatorResult:
    """
    Iteratively query the LLM, appending to a session, until a stop condition is met.

    - goal: free-form goal string (domain agnostic)
    - stop_when: function that receives the latest answer and returns True to stop
    """
    notes: List[str] = []
    answer = ""

    for i in range(1, max_iters + 1):
        prompt = f"""GOAL:
{goal}

ITERATION: {i}/{max_iters}

Respond with:
- One direct answer (if possible)
- If not enough info, list exactly what is missing (bullets)
"""
        answer = router.complete(
            session_id=session_id,
            stage=stage,
            system_prompt=system_prompt,
            user_text=prompt,
            model="gpt-5",
            temperature=0.2,
        )
        notes.append(f"iter_{i}: {len(answer or '')} chars")

        if stop_when and stop_when(answer):
            break
        # Basic heuristic: if model explicitly signals completion, stop.
        if isinstance(answer, str) and "DONE" in answer[:200]:
            break

    return InvestigatorResult(
        goal=goal,
        final_answer=answer or "",
        iterations=len(notes),
        notes=notes,
    )






