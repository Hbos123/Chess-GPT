from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SSEMilestone(BaseModel):
    name: str
    timestamp: float
    kind: Optional[str] = None


class SSEStatus(BaseModel):
    phase: str
    message: str
    timestamp: float
    progress: Optional[float] = None
    replace: Optional[bool] = None


class SSEFactsReady(BaseModel):
    """
    Small facts commit payload; keep it frontend-friendly.
    """

    eval_cp: Optional[int] = None
    recommended_move: Optional[str] = None
    recommended_reason: Optional[str] = None
    top_moves: List[Dict[str, Any]] = Field(default_factory=list)  # [{move, eval_cp}]


class SSEComplete(BaseModel):
    content: str
    stop_reason: str
    duration_s: Optional[float] = None
    budgets: Dict[str, Any] = Field(default_factory=dict)
    envelope: Optional[Dict[str, Any]] = None  # v2 AnswerEnvelope dumped as dict


class SSEError(BaseModel):
    message: str
    detail: Optional[str] = None





