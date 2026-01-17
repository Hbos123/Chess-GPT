"""
In-memory BoardTree store (TTL) for D2/D16 tree-first analysis.

Scope:
- Persists per (thread_id, optional app_session_id) while backend is running.
- Designed to be deterministic + lightweight; heavy artifacts (pgn_exploration/tree)
  are stored per node but can be omitted in responses if needed later.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import time
import uuid
import asyncio


@dataclass
class BoardTreeNode:
    id: str
    fen: str
    parent_id: Optional[str] = None
    move_san: str = ""  # SAN that led to this node ("" for root)
    children: List[str] = field(default_factory=list)  # ordered; children[0] is mainline
    is_mainline: bool = True  # relative to parent: True if this edge is parent's mainline
    created_ts: float = field(default_factory=lambda: time.time())
    # D2/D16 artifacts
    scan: Optional[Dict[str, Any]] = None


@dataclass
class BoardTree:
    root_id: str
    current_id: str
    nodes: Dict[str, BoardTreeNode] = field(default_factory=dict)

    def get(self, node_id: str) -> Optional[BoardTreeNode]:
        return self.nodes.get(node_id)

    def variation_depth(self, node_id: str) -> int:
        """
        Deviation depth from mainline:
        - root: 0
        - child on mainline: 0
        - child on side branch: 1
        - branch-of-branch: 2, etc.
        """
        depth = 0
        n = self.nodes.get(node_id)
        while n and n.parent_id:
            if not n.is_mainline:
                depth += 1
            n = self.nodes.get(n.parent_id)
        return depth


class BoardTreeStore:
    def __init__(self, ttl_s: float = 1800.0):
        self.ttl_s = float(ttl_s)
        self._store: Dict[str, Tuple[float, BoardTree]] = {}
        self._lock = asyncio.Lock()

    def _now(self) -> float:
        return time.time()

    def _make_key(self, thread_id: str, app_session_id: Optional[str] = None) -> str:
        sid = app_session_id or "none"
        return f"{sid}:{thread_id}"

    async def get_tree(self, *, thread_id: str, app_session_id: Optional[str] = None) -> Optional[BoardTree]:
        key = self._make_key(thread_id, app_session_id)
        async with self._lock:
            self._evict_expired_locked()
            item = self._store.get(key)
            if not item:
                return None
            ts, tree = item
            # touch
            self._store[key] = (self._now(), tree)
            return tree

    async def set_tree(self, *, thread_id: str, tree: BoardTree, app_session_id: Optional[str] = None) -> None:
        key = self._make_key(thread_id, app_session_id)
        async with self._lock:
            self._evict_expired_locked()
            self._store[key] = (self._now(), tree)

    async def delete_tree(self, *, thread_id: str, app_session_id: Optional[str] = None) -> None:
        key = self._make_key(thread_id, app_session_id)
        async with self._lock:
            self._store.pop(key, None)

    def _evict_expired_locked(self) -> None:
        now = self._now()
        keys = list(self._store.keys())
        for k in keys:
            last_ts, _tree = self._store.get(k, (0.0, None))  # type: ignore
            if now - float(last_ts) > self.ttl_s:
                self._store.pop(k, None)


def new_node_id(prefix: str = "n") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


