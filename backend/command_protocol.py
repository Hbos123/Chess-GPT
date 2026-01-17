"""
Command protocol: deterministic, compact prompt envelopes.

Instead of free-form prompts, we send a single typed command with structured input.
This improves reliability, reduces prompt entropy, and strengthens cache reuse.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional


def render_command(
    *,
    command: str,
    input: Dict[str, Any],
    constraints: Optional[Dict[str, Any]] = None,
    output_schema: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Render a deterministic command envelope.

    Notes:
    - JSON is compact and key-sorted to keep prompts stable.
    - The model is expected to follow the stage contract + response_format.
    """
    payload: Dict[str, Any] = {
        "command": str(command or "").strip(),
        "input": input or {},
    }
    if constraints:
        payload["constraints"] = constraints
    if output_schema:
        payload["output_schema"] = output_schema
    return "COMMAND\n" + json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))





