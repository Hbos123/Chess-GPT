"""
Action / schema validation helpers for command-based prompts.

These validators are intentionally lightweight and defensive; they gate the most
common failure modes (wrong shape / wrong action types) and enable a single
repair retry via LLM if needed.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple


PLANNER_ACTION_TYPES = {
    "ask_clarification",
    "investigate_move",
    "investigate_position",
    "investigate_target",
    "select_line",
    "apply_line",
    "save_state",
    "score_state",
    "select_state",
    "investigate_game",
    "synthesize",
    "answer",
}


def validate_planner_plan(obj: Any) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    if not isinstance(obj, dict):
        return False, ["plan is not an object"]
    steps = obj.get("steps")
    if not isinstance(steps, list) or len(steps) < 1:
        errors.append("steps must be a non-empty list")
    else:
        for i, s in enumerate(steps[:50]):
            if not isinstance(s, dict):
                errors.append(f"steps[{i}] must be an object")
                continue
            at = s.get("action_type")
            if at not in PLANNER_ACTION_TYPES:
                errors.append(f"steps[{i}].action_type invalid: {at!r}")
            sn = s.get("step_number")
            if not isinstance(sn, int):
                errors.append(f"steps[{i}].step_number must be int")
    return (len(errors) == 0), errors


def validate_interpreter_intent(obj: Any) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    if not isinstance(obj, dict):
        return False, ["intent plan is not an object"]
    for k in ["intent", "investigation_required", "mode", "mode_confidence", "user_intent_summary"]:
        if k not in obj:
            errors.append(f"missing key: {k}")
    if "mode_confidence" in obj and not isinstance(obj.get("mode_confidence"), (int, float)):
        errors.append("mode_confidence must be a number")
    if "investigation_required" in obj and not isinstance(obj.get("investigation_required"), bool):
        errors.append("investigation_required must be boolean")
    return (len(errors) == 0), errors





