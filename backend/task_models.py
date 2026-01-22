from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional


ConfidenceRequired = Literal["low", "medium", "high"]

ArtifactType = Literal[
    "castling_check",
    "engine_eval",
    "pv",
    "candidates",
    "threats",
    "tags",
    "roles",
    "material_delta",
    "opening_lookup",
    "move_compare",
]


@dataclass
class StopPolicy:
    max_time_s: float = 18.0
    max_engine_calls: int = 6
    max_llm_calls: int = 6


@dataclass
class GoalObject:
    objective: str
    constraints: List[str] = field(default_factory=list)
    confidence_required: ConfidenceRequired = "medium"
    required_artifacts: List[ArtifactType] = field(default_factory=list)
    stop_policy: StopPolicy = field(default_factory=StopPolicy)


@dataclass
class EvidenceRegistry:
    # Generic buckets (kept small; heavy raw blobs should live elsewhere)
    engine: Dict[str, Any] = field(default_factory=dict)
    chess: Dict[str, Any] = field(default_factory=dict)
    llm: Dict[str, Any] = field(default_factory=dict)

    def has(self, artifact: ArtifactType) -> bool:
        if artifact == "castling_check":
            return "castling" in self.chess
        if artifact in {"engine_eval", "pv", "candidates"}:
            return "analysis" in self.engine
        if artifact == "threats":
            return "threats" in self.engine
        if artifact == "tags":
            return "tags" in self.chess
        if artifact == "roles":
            return "roles" in self.chess
        if artifact == "material_delta":
            return "material_delta" in self.chess
        if artifact == "opening_lookup":
            return "opening" in self.chess
        if artifact == "move_compare":
            return "move_compare" in self.engine
        return False


@dataclass
class CompressedTaskMemory:
    facts_card: Dict[str, Any] = field(default_factory=dict)
    decisions_so_far: List[str] = field(default_factory=list)
    open_questions: List[str] = field(default_factory=list)
    user_prefs: Dict[str, Any] = field(default_factory=dict)
    last_stop_reason: Optional[str] = None






