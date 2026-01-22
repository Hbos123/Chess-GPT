from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


Side = Literal["white", "black"]


class CandidateMove(BaseModel):
    rank: int = Field(..., ge=1)
    san: str
    uci: Optional[str] = None
    eval_cp: Optional[int] = None  # White POV centipawns
    pv_san: List[str] = Field(default_factory=list)


class ConfidenceSignals(BaseModel):
    """
    Confidence signals derived from engine artifacts only.
    Used to modulate language tone/verbosity, not to invent facts.
    """

    # 0..1 where higher means more stable.
    eval_stability: Optional[float] = None
    # 0..1 where higher means more tactical / volatile.
    volatility: Optional[float] = None
    # 0..1 where higher means horizon risk / unclear.
    horizon: Optional[float] = None
    notes: List[str] = Field(default_factory=list)


class FactsCard(BaseModel):
    """
    Canonical engine-first artifact.
    This is the only object the language layer should rely on for concrete claims.
    """

    fen: str
    side_to_move: Side
    eval_cp: int = 0  # White POV centipawns

    # Evaluation breakdown (expressed in words to user; derived internally)
    material_balance_cp: int = 0  # positive = white ahead
    material_summary: str = ""  # e.g. "White has a knight for two pawns."
    positional_cp: int = 0  # eval_cp - material_balance_cp
    positional_summary: str = ""  # e.g. "White also has the better position."
    positional_factors: List[str] = Field(default_factory=list)  # e.g. ["king safety", "piece activity"]

    top_moves: List[CandidateMove] = Field(default_factory=list)

    # Optional/phase-dependent attachments (keep small, may be omitted for speed):
    pv: List[str] = Field(default_factory=list)
    threats: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    roles: Dict[str, List[str]] = Field(default_factory=dict)

    deltas: Dict[str, Any] = Field(default_factory=dict)  # material/tag deltas etc.
    confidence_signals: ConfidenceSignals = Field(default_factory=ConfidenceSignals)

    # Provenance
    source: str = "stockfish"
    depth: Optional[int] = None
    multipv: Optional[int] = None


class UICommand(BaseModel):
    # UI command surface for LLM to control the user's board.
    # Keep this aligned with frontend/lib/commandHandler.ts.
    action: Literal[
        "load_position",
        "new_tab",
        "navigate",
        "annotate",
        "push_move",
        "set_fen",
        "set_pgn",
        "delete_move",
        "delete_variation",
        "promote_variation",
        "set_ai_game",
    ]
    params: Dict[str, Any] = Field(default_factory=dict)


class AnswerEnvelope(BaseModel):
    """
    v2 response envelope. Keep backward compatibility by also emitting `content` in SSE `complete`.
    """

    facts_card: FactsCard
    recommended_move: Optional[str] = None
    alternatives: List[str] = Field(default_factory=list)
    explanation: str = ""

    ui_commands: List[UICommand] = Field(default_factory=list)

    confidence: Optional[float] = None
    stop_reason: str = ""
    budgets: Dict[str, Any] = Field(default_factory=dict)
    artifacts_used: List[str] = Field(default_factory=list)


