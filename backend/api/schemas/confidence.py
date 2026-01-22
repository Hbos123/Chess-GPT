from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict

NODE_SHAPES = {"circle", "triangle", "square"}
NODE_COLORS = {"red", "blue", "green"}


class ConfidenceNode(TypedDict, total=False):
    id: str
    parent_id: Optional[str]
    fen: str
    move_from_parent: Optional[str]
    ply_from_S0: int
    ConfidencePercent: int
    has_branches: bool
    frozen_confidence: Optional[int]
    initial_confidence: Optional[int]
    insufficient_confidence: bool
    shape: str
    color: str
    tags: List[str]
    extended_moves: Dict[str, int]
    metadata: Dict[str, Any]


class Snapshot(TypedDict):
    label: str
    iteration: int
    min_confidence: int
    stats: Dict[str, Any]
    nodes: List[ConfidenceNode]


class ConfidenceResponse(TypedDict):
    overall_confidence: int
    line_confidence: int
    lowest_confidence: int
    nodes: List[ConfidenceNode]
    caps: Dict[str, Any]
    snapshots: List[Snapshot]
    stats: Dict[str, Any]


def validate_node(node: ConfidenceNode) -> None:
    if node.get("shape") not in NODE_SHAPES:
        raise ValueError(f"Invalid shape: {node.get('shape')}")
    if node.get("color") not in NODE_COLORS:
        raise ValueError(f"Invalid color: {node.get('color')}")


def validate_response(payload: ConfidenceResponse) -> None:
    for node in payload["nodes"]:
        validate_node(node)
    for snapshot in payload["snapshots"]:
        for node in snapshot["nodes"]:
            validate_node(node)

