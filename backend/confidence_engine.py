from __future__ import annotations

import heapq
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple, TYPE_CHECKING

import chess
import chess.engine

from confidence_helpers import analyse_multipv, analyse_pv

if TYPE_CHECKING:
    from engine_queue import StockfishQueue

# Import tag detection (lazy import to avoid circular dependencies)
try:
    from tag_detector import aggregate_all_tags
except ImportError:
    aggregate_all_tags = None

__all__ = [
    "neutral_confidence",
    "compute_move_confidence",
    "compute_position_confidence",
    "_print_full_node_dump",
]

DEFAULT_BASELINE = 80
DEFAULT_MAX_NODES = 120
DEFAULT_MAX_ITERATIONS = 50
DEFAULT_MAX_PLY = 18
DEFAULT_DELTA2 = 30
DEFAULT_TOPK = 1
ALT_SCORE_MARGIN = 5  # centipawn margin to consider a move "better"
ALT_INITIAL_MAX = 4
WIDTH_ADD_LIMIT = 2


def _compute_confidence(s18: int, s2: int, pv18: int, pv2: int) -> int:
    def _conf_scalar(a: int, b: int, sigma: int = 30) -> float:
        return max(0.0, 1.0 - (abs(a - b) / float(sigma)))

    def _sign_factor(a: int, b: int) -> float:
        if abs(a) < 15 or abs(b) < 15:
            return 1.0
        return 1.0 if (a >= 0 and b >= 0) or (a < 0 and b < 0) else 0.5

    ia = _conf_scalar(s2, s18)
    pa = _conf_scalar(pv2, pv18)
    eu = _conf_scalar(pv2, s18)
    sign = _sign_factor(s2, s18)
    conf_raw = 0.3 * ia + 0.4 * pa + 0.3 * eu
    result = int(round(100.0 * conf_raw * sign))
    
    # Always log when result is 0 (critical issue)
    if result == 0:
        print(json.dumps({
            "event": "confidence_calc_zero",
            "inputs": {"s18": s18, "s2": s2, "pv18": pv18, "pv2": pv2},
            "intermediates": {
                "ia": round(ia, 3),
                "pa": round(pa, 3),
                "eu": round(eu, 3),
                "sign": round(sign, 3),
                "conf_raw": round(conf_raw, 3),
                "conf_raw_x_100": round(conf_raw * 100, 3),
                "final_before_round": round(100.0 * conf_raw * sign, 3)
            },
            "result": result,
            "note": "CRITICAL: Confidence calculation returned 0 - investigating"
        }, ensure_ascii=False))
    
    # DEBUG: Log when result is exactly 70 (common issue)
    if result == 70:
        print(json.dumps({
            "event": "confidence_is_70",
            "inputs": {"s18": s18, "s2": s2, "pv18": pv18, "pv2": pv2},
            "intermediates": {
                "ia": round(ia, 3),
                "pa": round(pa, 3),
                "eu": round(eu, 3),
                "sign": round(sign, 3),
                "conf_raw": round(conf_raw, 3)
            },
            "result": result,
            "note": "Confidence is exactly 70 - investigating pattern"
        }, ensure_ascii=False))
    
    # DEBUG: Log confidence calculation details if result is zero or unusual
    if result == 0 or result < 0 or result > 100 or abs(s18 - s2) > 100 or abs(pv18 - pv2) > 100:
        print(json.dumps({
            "event": "confidence_calc_unusual",
            "inputs": {"s18": s18, "s2": s2, "pv18": pv18, "pv2": pv2},
            "intermediates": {
                "ia": round(ia, 3),
                "pa": round(pa, 3),
                "eu": round(eu, 3),
                "sign": round(sign, 3),
                "conf_raw": round(conf_raw, 3)
            },
            "result": result
        }, ensure_ascii=False))
    
    return result


def _print_full_node_dump(nodes: List[Dict[str, Any]], title: str = "NODE DUMP") -> None:
    """Print every node and its properties in JSON form for debugging."""
    def _safe(obj: Any) -> Any:
        if obj is None or isinstance(obj, (int, float, str, bool)):
            return obj
        if isinstance(obj, dict):
            return {str(k): _safe(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_safe(v) for v in obj]
        return str(obj)

    payload = {
        "title": str(title),
        "total_nodes": len(nodes),
        "nodes": [_safe(node) for node in nodes],
    }
    try:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    except TypeError:
        fallback = {
            "title": str(title),
            "total_nodes": len(nodes),
            "nodes": [{str(k): str(v) for k, v in node.items()} for node in nodes],
        }
        print(json.dumps(fallback, indent=2, ensure_ascii=False))


@dataclass
class NodeState:
    id: str
    parent_id: Optional[str]
    fen: str
    move: Optional[str]
    ply_index: int
    confidence: int
    role: str
    shape: str = "circle"
    color: str = "red"
    has_branches: bool = False
    initial_confidence: Optional[int] = None  # Initial confidence (locked when first set)
    transferred_confidence: Optional[int] = None  # Confidence transferred from children (when propagated)
    preference_number: Optional[int] = None  # Depth 2 engine preference ranking (1 = best, 2 = second best, etc.)
    tags: List[str] = field(default_factory=list)
    extended_moves: Dict[str, int] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def set_confidence(self, value: int, baseline: int) -> None:
        """Set confidence and immediately refresh color."""
        old_conf = self.confidence
        self.confidence = value
        if old_conf != value:
            self.refresh_color(baseline)
    
    def set_initial_confidence(self, value: int) -> None:
        """Set immutable initial confidence if not already set."""
        if self.initial_confidence is None:
            self.initial_confidence = value

    def refresh_color(self, baseline: int) -> None:
        """Refresh color based on confidence and baseline."""
        # CRITICAL: Start node should always stay grey - never change its color
        if self.id == "start" and self.color == "grey":
            return  # Don't refresh start node color - keep it grey
        
        old_color = self.color
        conf = self.confidence if self.confidence is not None else 0
        # Simple threshold check: green if >= baseline, red otherwise
        self.color = "green" if conf >= baseline else "red"
        
        # Log color changes for debugging
        if old_color != self.color:
            print(json.dumps({
                "event": "color_changed_in_refresh",
                "node_id": self.id,
                "old_color": old_color,
                "new_color": self.color,
                "baseline": baseline,
                "confidence": conf,
            }, ensure_ascii=False))

    def mark_branch(self, baseline: int) -> None:
        """Mark node as having branches."""
        self.has_branches = True
        # Shape is determined by role/context, not by branching
        self.refresh_color(baseline)

    def to_payload(self) -> Dict[str, Any]:
        # CRITICAL: Final confidence logic:
        # 1. Use transferred_confidence if available (confidence from children)
        # 2. Otherwise use initial_confidence (immutable confidence from direct analysis)
        # 3. Fallback to confidence field (shouldn't happen if system is working correctly)
        if self.transferred_confidence is not None:
            reported_confidence = self.transferred_confidence
        elif self.initial_confidence is not None:
            reported_confidence = self.initial_confidence
        else:
            reported_confidence = self.confidence
        
        return {
            "id": self.id,
            "parent_id": self.parent_id,
            "fen": self.fen,
            "move_from_parent": self.move,
            "ply_from_S0": self.ply_index,
            "ConfidencePercent": reported_confidence,
            "has_branches": self.has_branches,
            "initial_confidence": self.initial_confidence,
            "transferred_confidence": self.transferred_confidence,
            "preference_number": self.preference_number,
            "insufficient_confidence": self.color == "red",
            "shape": self.shape,
            "color": self.color,
            "tags": list(self.tags),
            "extended_moves": dict(self.extended_moves),
            "metadata": dict(self.metadata),
        }


class ConfidenceEngine:
    def __init__(
        self,
        engine_queue: "StockfishQueue",
        start_board: chess.Board,
        move: chess.Move,
        *,
        baseline: int = DEFAULT_BASELINE,
        delta2: int = DEFAULT_DELTA2,
        topk: int = DEFAULT_TOPK,
        max_nodes: int = DEFAULT_MAX_NODES,
        max_iterations: int = DEFAULT_MAX_ITERATIONS,
        max_ply: int = DEFAULT_MAX_PLY,
        existing_nodes: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        self.engine_queue = engine_queue
        self.start_board = start_board
        self.move = move
        self.baseline = baseline
        self.delta2 = delta2
        self.topk = max(1, topk)
        self.max_nodes = max_nodes
        # NOTE: max_iterations is kept for API compatibility but not used in 3-phase system
        # The 3-phase system processes all red nodes in one pass (Phase 1/2/3)
        self.max_iterations = max_iterations
        self.max_ply = max_ply

        self.nodes: Dict[str, NodeState] = {}
        self.order: List[str] = []
        self.snapshots: List[Dict[str, Any]] = []
        self.iteration = 0  # Used for snapshot tracking
        # DEPRECATED: round_robin_counter - only used in old _eligible_candidates method
        self.round_robin_counter = 0
        self.branch_counter = 0
        self.min_pv_confidence = 100
        self.end_confidence = 100  # Confidence of last PV node
        self.start_confidence = 100
        self.played_move_d2_score: Optional[int] = None
        self.stats: Dict[str, Any] = {}
        # Store PV endpoint evaluations for branch confidence calculations
        self.pv_endpoint_deep: Optional[int] = None
        self.pv_endpoint_shallow: Optional[int] = None
        self.start_perspective_is_white: Optional[bool] = None
        # Phase tracking for frontend logging
        self.phase_info: Dict[str, Any] = {
            "phase1_nodes_converted": 0,
            "phase2_nodes_added": 0,
            "phase3_nodes_frozen": 0,
            "phases_executed": []
        }
        
        # Tree identifier to prevent mixing nodes from different calculations
        after_board = start_board.copy()
        after_board.push(move)
        self.tree_id = f"{start_board.fen()}:{move.uci()}:{after_board.fen()}"
        
        # Load existing nodes if provided (for incremental updates)
        if existing_nodes:
            self._load_existing_nodes(existing_nodes)

    def _load_existing_nodes(self, existing_nodes: List[Dict[str, Any]]) -> None:
        """Load existing nodes from a previous confidence calculation.
        This allows incremental updates instead of rebuilding from scratch.
        
        CRITICAL: Validates that nodes belong to the same tree and preserves
        initial_confidence values to prevent them from being overwritten.
        """
        # Try to detect previous baseline from node metadata
        previous_baseline = None
        if existing_nodes:
            # Check first node's metadata for baseline hint
            first_node_meta = existing_nodes[0].get("metadata", {})
            if "baseline" in first_node_meta:
                previous_baseline = first_node_meta.get("baseline")
        
        print(json.dumps({
            "event": "loading_existing_nodes",
            "count": len(existing_nodes),
            "current_baseline": self.baseline,
            "previous_baseline": previous_baseline,
            "baseline_changed": previous_baseline is not None and previous_baseline != self.baseline,
            "note": "If baseline changed, colors will be refreshed with new baseline"
        }, ensure_ascii=False))
        
        # Validate tree consistency - check that start node matches our starting position
        # CRITICAL: Use "start" node instead of "pv-0" (which doesn't exist in new structure)
        start_nodes = [n for n in existing_nodes if n.get("id") == "start"]
        tree_mismatch = False
        if start_nodes:
            start_fen = start_nodes[0].get("fen", "")
            expected_start_fen = self.start_board.fen()
            if start_fen != expected_start_fen:
                tree_mismatch = True
                print(json.dumps({
                    "event": "tree_mismatch_warning",
                    "expected_start_fen": expected_start_fen,
                    "received_start_fen": start_fen,
                    "tree_id": self.tree_id,
                    "note": "CRITICAL: Start node FEN mismatch - nodes may be from a different tree"
                }, ensure_ascii=False))
        elif existing_nodes:
            # No start node found but we have nodes - this is suspicious
            # Check if any node has a FEN that matches our start position
            expected_start_fen = self.start_board.fen()
            has_matching_fen = any(n.get("fen") == expected_start_fen for n in existing_nodes)
            if not has_matching_fen:
                tree_mismatch = True
                print(json.dumps({
                    "event": "tree_mismatch_no_start_node",
                    "expected_start_fen": expected_start_fen,
                    "existing_node_ids": [n.get("id") for n in existing_nodes[:5]],
                    "tree_id": self.tree_id,
                    "note": "CRITICAL: No start node found and no node matches start FEN - rejecting nodes"
                }, ensure_ascii=False))
        
        if tree_mismatch:
            # Don't load nodes from a different tree - this prevents confusion
            print(json.dumps({
                "event": "rejecting_different_tree_nodes",
                "tree_id": self.tree_id,
                "existing_nodes_count": len(existing_nodes),
                "note": "CRITICAL: Rejecting existing nodes - they belong to a different tree. This will cause tree to be rebuilt from scratch."
            }, ensure_ascii=False))
            return  # Don't load nodes from different tree - this causes tree to be rebuilt
        
        initial_conf_preserved = 0
        initial_conf_set = 0
        nodes_loaded = 0
        nodes_skipped = 0
        
        print(json.dumps({
            "event": "starting_node_load_loop",
            "existing_nodes_to_load": len(existing_nodes),
            "current_nodes_count": len(self.nodes),
            "note": "Starting to load existing nodes into empty tree"
        }, ensure_ascii=False))
        
        for node_data in existing_nodes:
            node_id = node_data.get("id", "")
            # CRITICAL: Preserve initial_confidence from existing node data
            # This is a one-time variable - once set, it should never change
            existing_initial_conf = node_data.get("initial_confidence")
            
            # Reconstruct NodeState from payload
            # NOTE: Don't trust the color from payload - we'll refresh it with current baseline
            # EXCEPT for start node which should be grey
            node_color = "red"  # Temporary - will be refreshed with correct color based on current baseline
            if node_id == "start":
                node_color = "grey"  # Start node is always grey
            
            node = NodeState(
                id=node_id,
                parent_id=node_data.get("parent_id"),
                fen=node_data.get("fen", ""),
                move=node_data.get("move_from_parent"),
                ply_index=node_data.get("ply_from_S0", 0),
                confidence=node_data.get("ConfidencePercent", 0),
                role=node_data.get("role", "pv"),
                shape=node_data.get("shape", "circle"),
                color=node_color,
                has_branches=node_data.get("has_branches", False),
                preference_number=node_data.get("preference_number"),
                tags=node_data.get("tags", []),
                extended_moves=dict(node_data.get("extended_moves", {})),  # Make a copy
                metadata=dict(node_data.get("metadata", {})),  # Make a copy
            )
            
            # CRITICAL: Set initial_confidence if it exists in the payload (lock it)
            if existing_initial_conf is not None:
                node.set_initial_confidence(existing_initial_conf)
            
            # CRITICAL: Refresh color immediately with current baseline (ignores old color from payload)
            # EXCEPT for start node which should stay grey
            color_before_refresh = node.color
            if node.id != "start":
                node.refresh_color(self.baseline)
            # Start node stays grey
            
            # Log if color changed during load
            if color_before_refresh != node.color:
                print(json.dumps({
                    "event": "color_changed_during_load",
                    "node_id": node.id,
                    "color_before": color_before_refresh,
                    "color_after": node.color,
                    "baseline": self.baseline,
                    "confidence": node.confidence,
                    "note": "Color changed when loading existing node"
                }, ensure_ascii=False))
            
            # Track initial_confidence preservation
            if existing_initial_conf is not None:
                initial_conf_preserved += 1
                if node.has_branches:
                    initial_conf_set += 1
                # Log initial_confidence preservation
                print(json.dumps({
                    "event": "initial_confidence_preserved_in_load",
                    "node_id": node.id,
                    "initial_confidence": node.initial_confidence,
                    "confidence": node.confidence,
                    "note": "Preserved initial_confidence from existing node"
                }, ensure_ascii=False))
            
            # CRITICAL: If node already exists, DO NOT overwrite it - keep the existing one
            # This prevents any modifications to nodes that are already loaded
            if node_id in self.nodes:
                existing_node = self.nodes[node_id]
                # Log state before refresh
                color_before = existing_node.color
                initial_conf_before = existing_node.initial_confidence
                
                # Force refresh color with current baseline (ensures new logic is applied)
                existing_node.refresh_color(self.baseline)
                
                # Log if anything changed
                if color_before != existing_node.color:
                    print(json.dumps({
                        "event": "existing_node_modified_during_load",
                        "node_id": node_id,
                        "color_before": color_before,
                        "color_after": existing_node.color,
                        "baseline": self.baseline,
                        "confidence": existing_node.confidence,
                        "note": "Existing node color was refreshed during load"
                    }, ensure_ascii=False))
                
                print(json.dumps({
                    "event": "skipping_node_reload",
                    "node_id": node_id,
                    "existing_initial_confidence": existing_node.initial_confidence,
                    "incoming_initial_confidence": existing_initial_conf,
                    "refreshed_color": existing_node.color,
                    "note": "Node already exists - keeping existing node, color refreshed with current baseline"
                }, ensure_ascii=False))
                nodes_skipped += 1
                continue  # Skip adding this node - keep the existing one
            
            self._add_node(node)
            nodes_loaded += 1
            
            # Update counters to avoid ID conflicts
            if node.id.startswith("branch-"):
                # Extract counter from branch IDs
                try:
                    parts = node.id.split("-")
                    if len(parts) >= 3:
                        counter_val = int(parts[-1]) if parts[-1].isdigit() else 0
                        self.branch_counter = max(self.branch_counter, counter_val + 1)
                except:
                    pass
        
            # Update confidence calculations from existing nodes
            all_nodes = list(self.nodes.values())
            if all_nodes:
                # Get start_confidence from starting position node
                start_node = next((n for n in all_nodes if n.id == "start"), None)
                if start_node:
                    self.start_confidence = start_node.confidence
                
                # Calculate min confidence from all nodes
                all_confidences = [n.confidence for n in all_nodes]
                if all_confidences:
                    self.min_pv_confidence = min(all_confidences)
                    self.end_confidence = max(all_confidences)  # End confidence is max (best)
                else:
                    self.min_pv_confidence = 100
                    self.end_confidence = 100
        
        # Refresh all nodes with the current baseline (important when baseline changes)
        for node in self.nodes.values():
            node.refresh_color(self.baseline)
        
        pv_nodes = [n for n in self.nodes.values() if n.id.startswith("pv-")]
        print(json.dumps({
            "event": "existing_nodes_loaded",
            "total_nodes": len(self.nodes),
            "nodes_loaded": nodes_loaded,
            "nodes_skipped": nodes_skipped,
            "nodes_in_existing_list": len(existing_nodes),
            "pv_nodes": len(pv_nodes),
            "min_pv_confidence": self.min_pv_confidence,
            "branch_counter": self.branch_counter,
            "baseline": self.baseline,
            "initial_confidence_stats": {
                "preserved": initial_conf_preserved,
                "with_branches": initial_conf_set,
                "note": "initial_confidence values preserved from existing nodes"
            },
            "node_ids_loaded": [n.id for n in self.nodes.values()][:10],  # First 10 for debugging
            "note": "CRITICAL: If nodes_loaded + nodes_skipped != nodes_in_existing_list, some nodes were lost!"
        }, ensure_ascii=False))
        
        # CRITICAL: Validate that we loaded all nodes
        if nodes_loaded + nodes_skipped != len(existing_nodes):
            print(json.dumps({
                "event": "CRITICAL_NODE_LOAD_MISMATCH",
                "nodes_loaded": nodes_loaded,
                "nodes_skipped": nodes_skipped,
                "total_expected": len(existing_nodes),
                "actual_sum": nodes_loaded + nodes_skipped,
                "nodes_in_tree": len(self.nodes),
                "note": "CRITICAL: Some nodes were not loaded! This will cause tree to be rebuilt."
            }, ensure_ascii=False))

    def _find_node_by_fen(self, fen: str, exclude_id: Optional[str] = None) -> Optional[NodeState]:
        """Find a node with the same FEN (excluding a specific node ID)."""
        for node in self.nodes.values():
            if node.id != exclude_id and node.fen == fen:
                return node
        return None
    
    def _add_node(self, node: NodeState) -> None:
        # CRITICAL: If node with same ID already exists, preserve it and don't overwrite
        if node.id in self.nodes:
            existing_node = self.nodes[node.id]
            # Node already exists - preserve it, don't delete or overwrite
            print(json.dumps({
                "event": "node_already_exists_preserving",
                "node_id": node.id,
                "existing_initial_confidence": existing_node.initial_confidence,
                "new_initial_confidence": node.initial_confidence,
                "note": "Node with this ID already exists - preserving existing node, NOT deleting or overwriting"
            }, ensure_ascii=False))
            return  # Don't add the duplicate - preserve existing node
        
        # CRITICAL: Only merge nodes with same FEN AND same move AND same parent
        # If they have different moves or preference numbers, keep both as separate nodes
        existing_fen_node = self._find_node_by_fen(node.fen, exclude_id=node.id)
        if existing_fen_node:
            # Check if they represent the same move from the same parent
            same_move = (node.move == existing_fen_node.move)
            same_parent = (node.parent_id == existing_fen_node.parent_id)
            
            if same_move and same_parent:
                # Same FEN, same move, same parent - merge the nodes
                print(json.dumps({
                    "event": "merging_duplicate_fen_nodes",
                    "new_node_id": node.id,
                    "existing_node_id": existing_fen_node.id,
                    "fen": node.fen,
                    "move": node.move,
                    "note": "Two nodes represent the same position and move - merging into existing node, NOT adding new one"
                }, ensure_ascii=False))
                
                # Update all children to point to the existing node
                for child in self.nodes.values():
                    if child.parent_id == node.id:
                        child.parent_id = existing_fen_node.id
                
                # Merge roles if different
                if node.role != existing_fen_node.role:
                    if "played" in node.role or "best" in node.role:
                        if "played" in existing_fen_node.role or "best" in existing_fen_node.role:
                            # Combine roles
                            roles = set([existing_fen_node.role, node.role])
                            if "played" in roles and "best" in roles:
                                existing_fen_node.role = "played-best"
                            elif "played" in roles:
                                existing_fen_node.role = "played"
                            elif "best" in roles:
                                existing_fen_node.role = "best"
                
                # Use the better confidence (preserve existing initial_confidence if locked)
                if node.initial_confidence is not None and existing_fen_node.initial_confidence is not None:
                    # Both have initial_confidence - keep the existing one (it's locked)
                    # Don't overwrite locked initial_confidence
                    pass
                elif node.initial_confidence is not None:
                    existing_fen_node.initial_confidence = node.initial_confidence
                
                # Use the better preference number (lower is better)
                if node.preference_number is not None and existing_fen_node.preference_number is not None:
                    existing_fen_node.preference_number = min(existing_fen_node.preference_number, node.preference_number)
                elif node.preference_number is not None:
                    existing_fen_node.preference_number = node.preference_number
                
                # Use square shape if either is square (best moves are squares)
                if node.shape == "square" or existing_fen_node.shape == "square":
                    existing_fen_node.shape = "square"
                
                # Update confidence to max
                existing_fen_node.confidence = max(existing_fen_node.confidence, node.confidence)
                existing_fen_node.refresh_color(self.baseline)
                
                # CRITICAL: Don't delete anything - just don't add the new node
                # The new node was never added, so we just return without adding it
                return  # Don't add the duplicate node
            else:
                # Same FEN but different move or parent - keep both as separate nodes
                print(json.dumps({
                    "event": "keeping_separate_nodes_same_fen",
                    "new_node_id": node.id,
                    "existing_node_id": existing_fen_node.id,
                    "fen": node.fen,
                    "new_move": node.move,
                    "existing_move": existing_fen_node.move,
                    "new_parent": node.parent_id,
                    "existing_parent": existing_fen_node.parent_id,
                    "note": "Same FEN but different move/parent - keeping both nodes"
                }, ensure_ascii=False))
        
        # CRITICAL: If node already exists with locked initial_confidence, DO NOT overwrite it
        if node.id in self.nodes:
            existing_node = self.nodes[node.id]
            # Preserve locked initial_confidence - NEVER overwrite it
            if existing_node.initial_confidence is not None:
                print(json.dumps({
                    "event": "preserving_existing_node",
                    "node_id": node.id,
                    "existing_initial_confidence": existing_node.initial_confidence,
                    "new_initial_confidence": node.initial_confidence,
                    "note": "Node exists with locked initial_confidence - preserving it, NOT overwriting"
                }, ensure_ascii=False))
                # Use existing node's locked values
                node.initial_confidence = existing_node.initial_confidence
                # Only update confidence if it comes from transferred_confidence (children changed)
                # Otherwise keep the existing confidence
                if node.transferred_confidence is None and existing_node.transferred_confidence is not None:
                    # New node doesn't have transferred, but existing does - keep existing
                    node.transferred_confidence = existing_node.transferred_confidence
                    node.confidence = existing_node.confidence
        
        self.nodes[node.id] = node
        if node.id not in self.order:
            self.order.append(node.id)

    def _get_node(self, node_id: str) -> NodeState:
        return self.nodes[node_id]

    def _record_snapshot(self, label: str) -> None:
        snapshot = {
            "label": label,
            "iteration": self.iteration,
            "min_confidence": self.min_pv_confidence,
            "stats": self._compute_stats(),
            "nodes": [self.nodes[nid].to_payload() for nid in self.order],
        }
        self.snapshots.append(snapshot)
    
    def _print_tree_summary(self, title: str) -> None:
        """Print a concise tree summary showing node states."""
        pv_nodes = [self.nodes[nid] for nid in self.order if self.nodes[nid].role == "pv"]
        branch_nodes = [self.nodes[nid] for nid in self.order if self.nodes[nid].role in ("branch-mid", "branch-leaf")]
        
        print(f"\n{'='*80}")
        print(f"📊 {title}")
        print(f"{'='*80}")
        print(f"Total nodes: {len(self.nodes)} | PV: {len(pv_nodes)} | Branches: {len(branch_nodes)}")
        print(f"Min PV confidence: {self.min_pv_confidence} | Baseline: {self.baseline}")
        print(f"\nPV Line:")
        for node in pv_nodes:
            conf_str = f"{node.confidence}%"
            color_emoji = {"red": "🔴", "green": "🟢"}.get(node.color, "⚪")
            shape_char = {"square": "■", "circle": "●", "triangle": "▲"}.get(node.shape, "?")
            print(f"  {shape_char} {color_emoji} {node.id:12s} conf={conf_str:15s} branches={len(node.extended_moves)}")
        
        if branch_nodes:
            print(f"\nBranches ({len(branch_nodes)}):")
            for node in branch_nodes[:10]:  # Show first 10 branches
                color_emoji = {"red": "🔴", "blue": "🔵", "green": "🟢"}.get(node.color, "⚪")
                print(f"  {color_emoji} {node.id:20s} conf={node.confidence}% parent={node.parent_id}")
            if len(branch_nodes) > 10:
                print(f"  ... and {len(branch_nodes) - 10} more branches")
        
        print(f"{'='*80}\n")

    def _compute_stats(self) -> Dict[str, Any]:
        pv_nodes = [node for node in self.nodes.values() if node.role == "pv"]
        triangle_nodes = [node for node in pv_nodes if node.has_branches]
        red_nodes = [node for node in pv_nodes if node.color == "red"]
        branch_midpoints = [node for node in self.nodes.values() if node.role == "branch-mid"]
        branch_leaves = [node for node in self.nodes.values() if node.role == "branch-leaf"]
        return {
            "pv_length": len(pv_nodes),
            "triangles": len(triangle_nodes),
            "red_pv_nodes": len(red_nodes),
            "branch_midpoints": len(branch_midpoints),
            "branch_leaves": len(branch_leaves),
            "total_nodes": len(self.nodes),
            "iteration": self.iteration,
        }

    async def _build_pv(self) -> None:
        """Build the new confidence tree structure starting from position BEFORE the move."""
        # CRITICAL: If we have existing nodes with initial_confidence, DO NOT recalculate anything
        # Just update confidence from children and return
        has_existing_nodes = any(
            n.initial_confidence is not None 
            for n in self.nodes.values()
        )
        
        if has_existing_nodes:
            print(json.dumps({
                "event": "_build_pv_early_exit_with_existing_nodes",
                "existing_nodes_count": len(self.nodes),
                "note": "CRITICAL: _build_pv called but existing nodes present - exiting early to prevent recalculation"
            }, ensure_ascii=False))
            # Just update confidence from children if we have a start node
            start_node = self.nodes.get("start")
            if start_node:
                self._update_confidence_from_children(start_node)
            return
        
        # Starting position is BEFORE the move
        starting_fen = self.start_board.fen()
        starting_perspective_is_white = self.start_board.turn == chess.WHITE
        
        # Check if start node already exists with locked initial_confidence
        existing_start = self.nodes.get("start")
        start_node = None
        start_analysis_d18 = None
        
        if existing_start and existing_start.initial_confidence is not None:
            # CRITICAL: Node exists with locked initial_confidence - use it, do NOT recalculate
            print(json.dumps({
                "event": "preserving_existing_initial_confidence",
                "node_id": "start",
                "initial_confidence": existing_start.initial_confidence,
                "current_confidence": existing_start.confidence,
                "note": "Using existing locked initial_confidence - will NOT recalculate"
            }, ensure_ascii=False))
            start_node = existing_start
            self.start_confidence = existing_start.initial_confidence
            self.start_perspective_is_white = starting_perspective_is_white
            # Only do minimal analysis to get best move (for navigation), NOT for confidence
            start_analysis_d18 = await analyse_pv(self.engine_queue, self.start_board, depth=18)
        else:
            # Node doesn't exist or doesn't have initial_confidence - calculate it
            start_analysis_d18 = await analyse_pv(self.engine_queue, self.start_board, depth=18)
            start_analysis_d2 = await analyse_pv(self.engine_queue, self.start_board, depth=2)
            
            # Get PV endpoint for confidence calculation
            pv_board = self.start_board.copy()
            if start_analysis_d18.moves:
                pv_board.push(start_analysis_d18.moves[0])
                for move in start_analysis_d18.moves[1:18]:
                    if pv_board.is_game_over():
                        break
                    pv_board.push(move)
            
            endpoint_d18 = await analyse_pv(self.engine_queue, pv_board, depth=18)
            endpoint_d2 = await analyse_pv(self.engine_queue, pv_board, depth=2)
            
            # Normalize evaluations
            s18 = start_analysis_d18.score_cp if start_analysis_d18.score_cp is not None else 0
            s2 = start_analysis_d2.score_cp if start_analysis_d2.score_cp is not None else 0
            pv18 = endpoint_d18.score_cp if endpoint_d18.score_cp is not None else 0
            pv2 = endpoint_d2.score_cp if endpoint_d2.score_cp is not None else 0
            
            # Normalize endpoint to starting perspective
            endpoint_perspective_is_white = pv_board.turn == chess.WHITE
            if endpoint_perspective_is_white != starting_perspective_is_white:
                pv18 = -pv18
                pv2 = -pv2
            
            start_conf = _compute_confidence(s18, s2, pv18, pv2)
            if start_conf is None:
                start_conf = 0
            
            self.start_confidence = start_conf
            self.start_perspective_is_white = starting_perspective_is_white
            
            # Create starting position node - GREY to represent position BEFORE move
            start_node = NodeState(
                id="start",
                parent_id=None,
                fen=starting_fen,
                move=None,
                ply_index=0,
                confidence=start_conf,
                role="start",
                shape="square",
                color="grey",  # Grey represents position before move was pushed
            )
            start_node.set_initial_confidence(start_conf)  # LOCK IT - never changes
            # Don't refresh color - keep it grey
            self._add_node(start_node)
        
        # 2. Get depth 18 best move (needed for creating child nodes)
        best_move_d18 = start_analysis_d18.moves[0] if start_analysis_d18.moves else None
        if not best_move_d18:
            # Update confidence from children if we have existing nodes
            if start_node:
                self._update_confidence_from_children(start_node)
            return
        
        # 3. Evaluate depth 18 best move at depth 2 (for reference only) - only if needed
        best_move_board = self.start_board.copy()
        best_move_board.push(best_move_d18)
        best_move_d2_eval = await analyse_pv(self.engine_queue, best_move_board, depth=2)
        best_move_d2_score = best_move_d2_eval.score_cp if best_move_d2_eval.score_cp is not None else 0
        if best_move_board.turn != starting_perspective_is_white:
            best_move_d2_score = -best_move_d2_score

        # Evaluate the played move - ONLY if played-move node doesn't exist with initial_confidence
        existing_played_move = self.nodes.get("played-move")
        if existing_played_move and existing_played_move.initial_confidence is not None:
            # Use existing - skip all calculations
            played_move_conf = existing_played_move.initial_confidence
            # played_move_d2_score is stored separately, not in terminal_confidence
            # If we need it, we'll need to get it from metadata or recalculate
            print(json.dumps({
                "event": "preserving_existing_initial_confidence",
                "node_id": "played-move",
                "initial_confidence": existing_played_move.initial_confidence,
                "note": "Using existing initial_confidence - skipping all calculations"
            }, ensure_ascii=False))
        else:
            # Analyze using FEN BEFORE the move (start_board), not after
            played_move_d18_before = await analyse_pv(self.engine_queue, self.start_board, depth=18)
            played_move_d2_before = await analyse_pv(self.engine_queue, self.start_board, depth=2)
            
            # Get PV from the position before the move
            played_pv_board = self.start_board.copy()
            if played_move_d18_before.moves:
                for move in played_move_d18_before.moves[:18]:
                    if played_pv_board.is_game_over():
                        break
                    played_pv_board.push(move)
            played_endpoint_d18 = await analyse_pv(self.engine_queue, played_pv_board, depth=18)
            played_endpoint_d2 = await analyse_pv(self.engine_queue, played_pv_board, depth=2)
            
            played_s18 = played_move_d18_before.score_cp if played_move_d18_before.score_cp is not None else 0
            played_s2 = played_move_d2_before.score_cp if played_move_d2_before.score_cp is not None else 0
            played_pv18 = played_endpoint_d18.score_cp if played_endpoint_d18 and played_endpoint_d18.score_cp is not None else 0
            played_pv2 = played_endpoint_d2.score_cp if played_endpoint_d2 and played_endpoint_d2.score_cp is not None else 0
            
            # Perspective is from starting position (before move)
            played_before_perspective = self.start_board.turn == chess.WHITE
            played_endpoint_perspective = played_pv_board.turn == chess.WHITE
            
            if played_before_perspective != starting_perspective_is_white:
                played_s18 = -played_s18
                played_s2 = -played_s2
            if played_endpoint_perspective != starting_perspective_is_white:
                played_pv18 = -played_pv18
                played_pv2 = -played_pv2
            
            self.played_move_d2_score = played_s2
            played_move_conf = _compute_confidence(played_s18, played_s2, played_pv18, played_pv2)
            if played_move_conf is None:
                played_move_conf = 0

        # 4. Get all legal moves and evaluate at depth 2 (for preference ranking)
        # CRITICAL: Skip preference ranking calculation if we already have nodes with preference numbers
        # This prevents Stockfish recalculation when increasing confidence
        preference_map: Dict[str, int] = {}
        has_existing_preferences = any(
            n.preference_number is not None 
            for n in self.nodes.values() 
            if n.id != "start"
        )
        
        if has_existing_preferences:
            # Extract existing preference numbers from nodes to preserve them
            print(json.dumps({
                "event": "skipping_preference_ranking_recalculation",
                "note": "Existing nodes have preference numbers - using them instead of recalculating"
            }, ensure_ascii=False))
            for node in self.nodes.values():
                if node.preference_number is not None and node.move:
                    preference_map[node.move] = node.preference_number
        else:
            # Calculate preference ranking only if we don't have existing nodes
            all_moves = list(self.start_board.legal_moves)
            move_evaluations: List[Tuple[chess.Move, int]] = []
            
            for move in all_moves:
                test_board = self.start_board.copy()
                test_board.push(move)
                move_d2_eval = await analyse_pv(self.engine_queue, test_board, depth=2)
                move_d2_score = move_d2_eval.score_cp if move_d2_eval.score_cp is not None else 0
                if test_board.turn != starting_perspective_is_white:
                    move_d2_score = -move_d2_score
                move_evaluations.append((move, move_d2_score))
            
            # Sort by depth 2 score (best first) to assign preference numbers
            # CRITICAL: Moves with the same score should share the same rank
            sorted_by_d2 = sorted(move_evaluations, key=lambda x: x[1], reverse=True)
            current_rank = 1
            prev_score = None
            for move, score in sorted_by_d2:
                # If score is different from previous, increment rank
                if prev_score is not None and score != prev_score:
                    current_rank += 1
                preference_map[move.uci()] = current_rank
                prev_score = score
        
        # 5. Get FEN after the played move and best move to check for duplicates
        played_move_after_board = self.start_board.copy()
        played_move_after_board.push(self.move)
        played_move_fen = played_move_after_board.fen()
        
        best_move_after_board = self.start_board.copy()
        best_move_after_board.push(best_move_d18)
        best_move_fen = best_move_after_board.fen()
        
        # Check if played move and best move lead to the same FEN
        played_equals_best = (played_move_fen == best_move_fen)
        
        # 6. Create played move node (triangle) - FIRST after start node
        played_move_pref = preference_map.get(self.move.uci())
        existing_played_move = self.nodes.get("played-move")
        if existing_played_move and existing_played_move.initial_confidence is not None:
            # Use existing - preserve preference number if not set
            if existing_played_move.preference_number is None and played_move_pref is not None:
                existing_played_move.preference_number = played_move_pref
            played_move_node = existing_played_move
        else:
            played_move_node = NodeState(
                id="played-move",
                parent_id="start",
                fen=played_move_fen,
                move=self.move.uci(),
                ply_index=1,
                confidence=played_move_conf,
                role="played",
                shape="triangle",
                color="green" if played_move_conf >= self.baseline else "red",
                preference_number=played_move_pref,
            )
            played_move_node.set_initial_confidence(played_move_conf)  # LOCK IT
            played_move_node.refresh_color(self.baseline)
            self._add_node(played_move_node)
            # Start node now has children
            start_node.has_branches = True
        
        # 7. Create best move node (square) - SECOND after start node
        # If played move == best move, reuse the same node instead of creating duplicate
        best_move_pref = preference_map.get(best_move_d18.uci())
        existing_best_move = self.nodes.get("best-move")
        
        if played_equals_best:
            # Played move and best move are the same - connect them as one node
            print(json.dumps({
                "event": "played_move_equals_best_move",
                "move": self.move.uci(),
                "fen": played_move_fen,
                "note": "Played move and best move are the same - using played-move node as best-move"
            }, ensure_ascii=False))
            # Use played-move node as best-move node (same FEN, same move)
            # Update played-move node to also be the best move
            played_move_node.role = "played-best"  # Mark as both
            # Update shape to square (best moves are squares)
            played_move_node.shape = "square"
            # Use the better confidence (max of both)
            if existing_best_move and existing_best_move.initial_confidence is not None:
                # If best-move already exists, preserve existing initial_confidence - DO NOT overwrite
                best_move_conf = existing_best_move.initial_confidence
                # CRITICAL: Never overwrite existing initial_confidence - preserve the existing one
                if played_move_node.initial_confidence is None:
                    # Only set if not already set
                    played_move_node.set_initial_confidence(max(played_move_conf, best_move_conf))
                # Update confidence to max, but preserve initial_confidence
                played_move_node.confidence = max(played_move_node.confidence, best_move_conf)
            else:
                # Calculate best move confidence
                best_move_d18_after = await analyse_pv(self.engine_queue, best_move_after_board, depth=18)
                best_move_d2_after = await analyse_pv(self.engine_queue, best_move_after_board, depth=2)
                
                # Get endpoint for best move
                best_pv_board = best_move_after_board.copy()
                if best_move_d18_after.moves:
                    for move in best_move_d18_after.moves[:18]:
                        if best_pv_board.is_game_over():
                            break
                        best_pv_board.push(move)
                
                best_endpoint_d18 = await analyse_pv(self.engine_queue, best_pv_board, depth=18)
                best_endpoint_d2 = await analyse_pv(self.engine_queue, best_pv_board, depth=2)
                
                best_s18 = best_move_d18_after.score_cp if best_move_d18_after.score_cp is not None else 0
                best_s2 = best_move_d2_after.score_cp if best_move_d2_after.score_cp is not None else 0
                best_pv18 = best_endpoint_d18.score_cp if best_endpoint_d18.score_cp is not None else 0
                best_pv2 = best_endpoint_d2.score_cp if best_endpoint_d2.score_cp is not None else 0
                
                best_after_perspective = best_move_after_board.turn == chess.WHITE
                best_endpoint_perspective = best_pv_board.turn == chess.WHITE
                
                if best_after_perspective != starting_perspective_is_white:
                    best_s18 = -best_s18
                    best_s2 = -best_s2
                if best_endpoint_perspective != starting_perspective_is_white:
                    best_pv18 = -best_pv18
                    best_pv2 = -best_pv2
                
                best_move_conf = _compute_confidence(best_s18, best_s2, best_pv18, best_pv2)
                if best_move_conf is None:
                    best_move_conf = 0
                
                # Use the better confidence
                # CRITICAL: Only set initial_confidence if not already set (preserve existing)
                if played_move_node.initial_confidence is None:
                    played_move_node.set_initial_confidence(max(played_move_conf, best_move_conf))
                # Update confidence to max, but preserve existing initial_confidence
                played_move_node.confidence = max(played_move_node.confidence, best_move_conf)
            
            # Also add as best-move for reference (but it points to same node)
            # Actually, let's not create a duplicate - just use played-move
            best_move_node = played_move_node
        else:
            # Played move != best move - create separate best-move node
            if existing_best_move and existing_best_move.initial_confidence is not None:
                print(json.dumps({
                    "event": "preserving_existing_initial_confidence",
                    "node_id": "best-move",
                    "initial_confidence": existing_best_move.initial_confidence,
                    "note": "Using existing initial_confidence - will NOT recalculate"
                }, ensure_ascii=False))
                # Preserve preference number if not set
                if existing_best_move.preference_number is None and best_move_pref is not None:
                    existing_best_move.preference_number = best_move_pref
                best_move_node = existing_best_move
            else:
                best_move_d18_after = await analyse_pv(self.engine_queue, best_move_after_board, depth=18)
                best_move_d2_after = await analyse_pv(self.engine_queue, best_move_after_board, depth=2)
                
                # Get endpoint for best move
                best_pv_board = best_move_after_board.copy()
                if best_move_d18_after.moves:
                    for move in best_move_d18_after.moves[:18]:
                        if best_pv_board.is_game_over():
                            break
                        best_pv_board.push(move)
                
                best_endpoint_d18 = await analyse_pv(self.engine_queue, best_pv_board, depth=18)
                best_endpoint_d2 = await analyse_pv(self.engine_queue, best_pv_board, depth=2)
                
                best_s18 = best_move_d18_after.score_cp if best_move_d18_after.score_cp is not None else 0
                best_s2 = best_move_d2_after.score_cp if best_move_d2_after.score_cp is not None else 0
                best_pv18 = best_endpoint_d18.score_cp if best_endpoint_d18.score_cp is not None else 0
                best_pv2 = best_endpoint_d2.score_cp if best_endpoint_d2.score_cp is not None else 0
                
                best_after_perspective = best_move_after_board.turn == chess.WHITE
                best_endpoint_perspective = best_pv_board.turn == chess.WHITE
                
                if best_after_perspective != starting_perspective_is_white:
                    best_s18 = -best_s18
                    best_s2 = -best_s2
                if best_endpoint_perspective != starting_perspective_is_white:
                    best_pv18 = -best_pv18
                    best_pv2 = -best_pv2
                
                best_move_conf = _compute_confidence(best_s18, best_s2, best_pv18, best_pv2)
                if best_move_conf is None:
                    best_move_conf = 0
                
                best_move_node = NodeState(
                    id="best-move",
                    parent_id="start",
                    fen=best_move_fen,
                    move=best_move_d18.uci(),
                    ply_index=1,
                    confidence=best_move_conf,
                    role="best",
                    shape="square",
                    color="green" if best_move_conf >= self.baseline else "red",
                    preference_number=best_move_pref,
                )
                best_move_node.set_initial_confidence(best_move_conf)  # LOCK IT
                best_move_node.refresh_color(self.baseline)
                self._add_node(best_move_node)
                # Start node now has children
                start_node.has_branches = True
        
        # 8. Create alternative move nodes (circles) - moves Depth-2 prefers over BOTH played and best
        # Get depth 2 scores for played and best moves
        # CRITICAL: move_evaluations may not exist if we skipped preference ranking
        played_d2_score = None
        best_d2_score = None
        
        if not has_existing_preferences and 'move_evaluations' in locals():
            for m, score in move_evaluations:
                if m == self.move:
                    played_d2_score = score
                    break
            
            for m, score in move_evaluations:
                if m == best_move_d18:
                    best_d2_score = score
                    break
        
        # Only show alternatives that depth 2 prefers over BOTH played and best
        min_d2_threshold = None
        if played_d2_score is not None and best_d2_score is not None:
            min_d2_threshold = max(played_d2_score, best_d2_score) + ALT_SCORE_MARGIN
        elif played_d2_score is not None:
            min_d2_threshold = played_d2_score + ALT_SCORE_MARGIN
        elif best_d2_score is not None:
            min_d2_threshold = best_d2_score + ALT_SCORE_MARGIN
        
        alt_counter = 0
        start_node = self.nodes.get("start")
        
        # CRITICAL: Only process alternatives if we calculated move_evaluations
        # If we skipped preference ranking (has_existing_preferences), skip alternative nodes too
        if has_existing_preferences:
            print(json.dumps({
                "event": "skipping_alternative_nodes_with_existing_preferences",
                "note": "Skipping alternative node creation - existing nodes have preference numbers"
            }, ensure_ascii=False))
        else:
            sorted_evals = sorted(move_evaluations, key=lambda item: item[1], reverse=True)
            for move, move_d2_score in sorted_evals:
                if move == best_move_d18 or move == self.move:
                    continue
                # Only include if depth 2 prefers it over BOTH played and best
                if min_d2_threshold is not None and move_d2_score <= min_d2_threshold:
                    continue
                
                alt_node_id = f"alt-{alt_counter}"
                existing_alt = self.nodes.get(alt_node_id)
                
                # CRITICAL: Check if node exists with locked initial_confidence BEFORE doing any analysis
                if existing_alt and existing_alt.initial_confidence is not None:
                    print(json.dumps({
                        "event": "preserving_existing_initial_confidence",
                        "node_id": alt_node_id,
                        "initial_confidence": existing_alt.initial_confidence,
                        "note": "Using existing initial_confidence - skipping ALL calculations"
                    }, ensure_ascii=False))
                    # Use existing - skip ALL analysis and calculations
                    # Preserve preference number if not set
                    alt_pref = preference_map.get(move.uci())
                    if existing_alt.preference_number is None and alt_pref is not None:
                        existing_alt.preference_number = alt_pref
                    alt_node = existing_alt
                else:
                    # Node doesn't exist - calculate confidence
                    # Analyze using FEN BEFORE the move (start_board), not after
                    alt_d18_before = await analyse_pv(self.engine_queue, self.start_board, depth=18)
                    alt_d2_before = await analyse_pv(self.engine_queue, self.start_board, depth=2)
                    
                    # Get endpoint from PV starting from position before the move
                    alt_pv_board = self.start_board.copy()
                    if alt_d18_before.moves:
                        for mv in alt_d18_before.moves[:18]:
                            if alt_pv_board.is_game_over():
                                break
                            alt_pv_board.push(mv)
                    
                    alt_endpoint_d18 = await analyse_pv(self.engine_queue, alt_pv_board, depth=18)
                    alt_endpoint_d2 = await analyse_pv(self.engine_queue, alt_pv_board, depth=2)
                    
                    alt_s18 = alt_d18_before.score_cp if alt_d18_before.score_cp is not None else 0
                    alt_s2 = alt_d2_before.score_cp if alt_d2_before.score_cp is not None else 0
                    
                    # Store the FEN after the move for the node
                    alt_board = self.start_board.copy()
                    alt_board.push(move)
                    alt_pv18 = alt_endpoint_d18.score_cp if alt_endpoint_d18 and alt_endpoint_d18.score_cp is not None else 0
                    alt_pv2 = alt_endpoint_d2.score_cp if alt_endpoint_d2 and alt_endpoint_d2.score_cp is not None else 0
                    
                    # Perspective is from starting position (before move)
                    alt_before_perspective = self.start_board.turn == chess.WHITE
                    alt_endpoint_perspective = alt_pv_board.turn == chess.WHITE
                    
                    if alt_before_perspective != starting_perspective_is_white:
                        alt_s18 = -alt_s18
                        alt_s2 = -alt_s2
                    if alt_endpoint_perspective != starting_perspective_is_white:
                        alt_pv18 = -alt_pv18
                        alt_pv2 = -alt_pv2
                    
                    alt_conf = _compute_confidence(alt_s18, alt_s2, alt_pv18, alt_pv2)
                    if alt_conf is None:
                        alt_conf = 0
                    
                    alt_pref = preference_map.get(move.uci())
                    alt_node = NodeState(
                        id=alt_node_id,
                        parent_id="start",
                        fen=alt_board.fen(),
                        move=move.uci(),
                        ply_index=1,
                        confidence=alt_conf,
                        role="alternative",
                        shape="circle",
                        color="green" if alt_conf >= self.baseline else "red",
                        preference_number=alt_pref,
                    )
                    alt_node.set_initial_confidence(alt_conf)  # LOCK IT
                    alt_node.refresh_color(self.baseline)
                    self._add_node(alt_node)
                alt_counter += 1
                if start_node:
                    start_node.has_branches = True
                if alt_counter >= ALT_INITIAL_MAX:
                    break
        
        # 8. Update starting position confidence based on children (min of all sub-branches)
        self._update_confidence_from_children(start_node)
        
        # Update min_pv_confidence
        all_confidences = [node.confidence for node in self.nodes.values()]
        if all_confidences:
            self.min_pv_confidence = min(all_confidences)
    
    def _update_confidence_from_children(self, node: NodeState) -> None:
        """Update node confidence as minimum of all children's confidences.
        
        CRITICAL: This is the ONLY way confidence changes after initial_confidence is set.
        Existing nodes are NEVER re-analyzed - only extended with new children.
        """
        # CRITICAL: Never recalculate initial_confidence for existing nodes
        if node.initial_confidence is None:
            print(json.dumps({
                "event": "error_node_missing_initial_confidence",
                "node_id": node.id,
                "note": "CRITICAL: Node should have initial_confidence before updating from children"
            }, ensure_ascii=False))
            return
        
        children = [n for n in self.nodes.values() if n.parent_id == node.id]
        if children:
            # Get effective confidence from each child (prioritize transferred_confidence, then initial_confidence, then confidence)
            def get_effective_confidence(child: NodeState) -> int:
                if child.transferred_confidence is not None:
                    return child.transferred_confidence
                elif child.initial_confidence is not None:
                    return child.initial_confidence
                else:
                    return child.confidence
            
            # Confidence = min of all children's effective confidences (transferred from children)
            # This is the ONLY way confidence changes after initial calculation
            min_child_conf = min(get_effective_confidence(child) for child in children)
            node.transferred_confidence = min_child_conf
            old_conf = node.confidence
            node.set_confidence(min_child_conf, self.baseline)
            
            if old_conf != min_child_conf:
                print(json.dumps({
                    "event": "confidence_updated_via_transferred",
                    "node_id": node.id,
                    "old_confidence": old_conf,
                    "new_confidence": min_child_conf,
                    "transferred_confidence": min_child_conf,
                    "initial_confidence": node.initial_confidence,
                    "children_count": len(children),
                    "note": "Confidence updated ONLY via transferred_confidence from children - initial_confidence preserved"
                }, ensure_ascii=False))
        else:
            # No children - use initial confidence (not transferred)
            # Leaf nodes don't have transferred_confidence, so they use initial_confidence
            if node.initial_confidence is not None:
                node.transferred_confidence = None  # Not transferred, use initial
                node.set_confidence(node.initial_confidence, self.baseline)
    
    def _propagate_confidences(self) -> None:
        """Propagate confidences from leaves up to root.
        
        Only updates nodes that have children - leaf nodes keep their terminal/initial confidence.
        """
        # Process nodes in reverse order (leaves first, then parents)
        sorted_nodes = sorted(self.nodes.values(), key=lambda n: n.ply_index, reverse=True)
        for node in sorted_nodes:
            # Only update nodes that have children - leaf nodes don't need updating
            children = [n for n in self.nodes.values() if n.parent_id == node.id]
            if children:
                self._update_confidence_from_children(node)
    
    def _sync_confidences_with_transferred(self) -> None:
        """Sync all nodes' confidence fields with their transferred_confidence.
        
        This ensures that after all propagation is complete, every node's confidence
        field reflects its transferred_confidence if it has one.
        """
        for node in self.nodes.values():
            if node.transferred_confidence is not None:
                # Update confidence to match transferred_confidence
                old_conf = node.confidence
                if old_conf != node.transferred_confidence:
                    node.set_confidence(node.transferred_confidence, self.baseline)
                    print(json.dumps({
                        "event": "confidence_synced_with_transferred",
                        "node_id": node.id,
                        "old_confidence": old_conf,
                        "new_confidence": node.transferred_confidence,
                        "transferred_confidence": node.transferred_confidence,
                        "initial_confidence": node.initial_confidence,
                        "note": "Synced confidence field with transferred_confidence at end of confidence increase"
                    }, ensure_ascii=False))
    
    async def _intelligent_expand(self) -> None:
        """Intelligently expand tree to boost confidence by 5-10% per iteration.
        
        Algorithm:
        1. Find the node with lowest confidence (starting position or its children)
        2. Evaluate ROI of:
           - Depth expansion: Extend lowest confidence branch deeper
           - Width expansion: Add more alternative moves from starting position
        3. Choose option with best (confidence_gain / time) ratio
        4. Target: 5-10% confidence increase
        """
        start_node = self.nodes.get("start")
        if not start_node:
            return
        
        current_conf = start_node.confidence
        target_conf = min(100, current_conf + 7)  # Target ~7% boost (middle of 5-10%)
        
        print(json.dumps({
            "event": "intelligent_expand_start",
            "current_confidence": current_conf,
            "target_confidence": target_conf,
            "baseline": self.baseline
        }, ensure_ascii=False))
        
        # Get all children of start node
        children = [n for n in self.nodes.values() if n.parent_id == "start"]
        if not children:
            return
        
        # Find lowest confidence child
        lowest_child = min(children, key=lambda n: n.confidence)
        
        # Strategy 1: Depth expansion - extend lowest confidence branch
        depth_gain_estimate = await self._estimate_depth_expansion_gain(lowest_child)
        
        # Strategy 2: Width expansion - add more alternatives from start
        width_gain_estimate = await self._estimate_width_expansion_gain(start_node, children)
        
        # Choose best strategy based on ROI (gain / time)
        if depth_gain_estimate["roi"] > width_gain_estimate["roi"] and depth_gain_estimate["gain"] > 0:
            print(json.dumps({
                "event": "choosing_depth_expansion",
                "gain": depth_gain_estimate["gain"],
                "time_estimate": depth_gain_estimate["time_estimate"],
                "roi": depth_gain_estimate["roi"]
            }, ensure_ascii=False))
            await self._expand_depth(lowest_child)
        elif width_gain_estimate["gain"] > 0:
            print(json.dumps({
                "event": "choosing_width_expansion",
                "gain": width_gain_estimate["gain"],
                "time_estimate": width_gain_estimate["time_estimate"],
                "roi": width_gain_estimate["roi"]
            }, ensure_ascii=False))
            await self._expand_width(start_node, children)
        else:
            print(json.dumps({
                "event": "no_expansion_beneficial",
                "note": "Both strategies estimated low gain, checking for below-baseline leaf nodes"
            }, ensure_ascii=False))
        
        # CRITICAL: Extend any below-baseline leaf nodes (up to 5 nodes per extension)
        # This is the ONLY way to increase confidence - by extending nodes with new children
        # Note: force_extend_all is controlled by the caller (enable_branching logic)
        await self._extend_below_baseline_leaves(force_extend_all=False)
    
    async def _extend_below_baseline_leaves(self, force_extend_all: bool = False) -> None:
        """Extend leaf nodes to increase confidence.
        
        By default, only extends nodes below baseline. If force_extend_all is True,
        extends ALL leaf nodes regardless of confidence (used when actively increasing confidence).
        
        Creates up to 5 nodes per extension to maximize confidence increase.
        
        This is the ONLY way to increase confidence - by extending nodes with new children.
        """
        max_iterations = 10  # Prevent infinite loops
        iteration = 0
        
        while iteration < max_iterations:
            # Find all leaf nodes (nodes with no children)
            leaf_nodes = []
            
            for node in self.nodes.values():
                # Skip start node
                if node.id == "start":
                    continue
                
                # CRITICAL: Only extend nodes that have initial_confidence (never re-analyze)
                if node.initial_confidence is None:
                    continue
                
                # Check if it's a leaf (no children)
                has_children = any(n.parent_id == node.id for n in self.nodes.values())
                if not has_children:
                    # Check max_ply limit
                    if node.ply_index >= self.max_ply:
                        continue
                    
                    if force_extend_all:
                        # When forcing extension, extend ALL leaf nodes
                        leaf_nodes.append(node)
                    else:
                        # Only extend nodes below baseline
                        node_conf = node.transferred_confidence if node.transferred_confidence is not None else (node.initial_confidence if node.initial_confidence is not None else node.confidence)
                        if node_conf < self.baseline:
                            leaf_nodes.append(node)
            
            if not leaf_nodes:
                break  # No more nodes to extend
            
            print(json.dumps({
                "event": "extending_below_baseline_leaves",
                "iteration": iteration + 1,
                "count": len(leaf_nodes),
                "force_extend_all": force_extend_all,
                "node_ids": [n.id for n in leaf_nodes]
            }, ensure_ascii=False))
            
            # Extend all leaf nodes (creates up to 5 nodes per extension)
            for node in leaf_nodes:
                await self._extend_leaf_with_two_nodes(node)
            
            iteration += 1
        
        if iteration >= max_iterations:
            print(json.dumps({
                "event": "extend_below_baseline_max_iterations",
                "note": "Reached max iterations for extending below-baseline leaves"
            }, ensure_ascii=False))
    
    async def _extend_leaf_with_two_nodes(self, node: NodeState) -> None:
        """Extend a leaf node by creating up to 5 sequential nodes along a branch path.
        
        Creates a chain: node -> child1 -> child2 -> child3 -> child4 -> child5
        Each node uses the best move from depth 18 engine analysis.
        
        These new nodes get NEW initial confidences, and the parent node's confidence
        is updated ONLY via transferred_confidence from these children.
        
        CRITICAL: This is the ONLY way to increase confidence - by extending nodes.
        """
        # CRITICAL: Never re-analyze existing nodes - only extend with new children
        if node.initial_confidence is None:
            print(json.dumps({
                "event": "warning_node_missing_initial_confidence",
                "node_id": node.id,
                "note": "Node should have initial_confidence before extension"
            }, ensure_ascii=False))
            return
        
        # Get the board position for this node
        board = chess.Board(node.fen)
        
        if board.is_game_over():
            return  # Can't extend if game is over
        
        # Check max_ply limit
        if node.ply_index >= self.max_ply:
            print(json.dumps({
                "event": "cannot_extend_max_ply_reached",
                "node_id": node.id,
                "ply_index": node.ply_index,
                "max_ply": self.max_ply
            }, ensure_ascii=False))
            return
        
        # Create up to 5 sequential nodes along a single branch path
        created_nodes = []
        current_node = node
        current_board = board.copy()
        max_nodes_to_create = 5
        
        for node_num in range(1, max_nodes_to_create + 1):
            # Check max_ply limit
            if current_node.ply_index >= self.max_ply:
                break
            
            if current_board.is_game_over():
                break
            
            # Get best move from depth 18 engine
            analysis_d18 = await analyse_pv(self.engine_queue, current_board, depth=18, max_length=1)
            if not analysis_d18.moves:
                break
            
            best_move = analysis_d18.moves[0]
            next_board = current_board.copy()
            next_board.push(best_move)
            
            if next_board.is_game_over():
                break
            
            # Calculate NEW initial confidence for this node
            # Analyze from position BEFORE move (current_board), not after (next_board)
            node_d18 = await analyse_pv(self.engine_queue, current_board, depth=18)
            node_d2 = await analyse_pv(self.engine_queue, current_board, depth=2)
            
            # Get endpoint for this node
            endpoint_board = next_board.copy()
            if node_d18.moves:
                for mv in node_d18.moves[:18]:
                    if endpoint_board.is_game_over():
                        break
                    if mv in endpoint_board.legal_moves:
                        endpoint_board.push(mv)
                    else:
                        break
            
            endpoint_d18 = await analyse_pv(self.engine_queue, endpoint_board, depth=18)
            endpoint_d2 = await analyse_pv(self.engine_queue, endpoint_board, depth=2)
            
            s18 = node_d18.score_cp if node_d18.score_cp is not None else 0
            s2 = node_d2.score_cp if node_d2.score_cp is not None else 0
            pv18 = endpoint_d18.score_cp if endpoint_d18.score_cp is not None else 0
            pv2 = endpoint_d2.score_cp if endpoint_d2.score_cp is not None else 0
            
            # Normalize to starting perspective
            # CRITICAL: s18 and s2 are from analyzing 'current_board' (BEFORE move), so check current_board.turn
            node_before_perspective = current_board.turn == chess.WHITE
            endpoint_perspective = endpoint_board.turn == chess.WHITE
            if node_before_perspective != self.start_perspective_is_white:
                s18 = -s18
                s2 = -s2
            if endpoint_perspective != self.start_perspective_is_white:
                pv18 = -pv18
                pv2 = -pv2
            
            conf = _compute_confidence(s18, s2, pv18, pv2)
            if conf is None:
                conf = 0
            
            # Create node with NEW initial confidence
            node_id = f"{current_node.id}-d18-{current_node.ply_index + 1}"
            new_node = NodeState(
                id=node_id,
                parent_id=current_node.id,
                fen=next_board.fen(),
                move=best_move.uci(),
                ply_index=current_node.ply_index + 1,
                confidence=conf,
                role="extension",
                shape="circle",
                color="green" if conf >= self.baseline else "red",
            )
            new_node.set_initial_confidence(conf)  # NEW initial confidence - locked
            new_node.refresh_color(self.baseline)
            self._add_node(new_node)
            created_nodes.append((node_id, conf))
            current_node.has_branches = True
            
            # Move to next node in the chain
            current_node = new_node
            current_board = next_board.copy()
        
        if not created_nodes:
            print(json.dumps({
                "event": "no_nodes_created_extension",
                "leaf_node_id": node.id,
                "note": "No nodes could be created (game over or max_ply reached)"
            }, ensure_ascii=False))
            return
        
        # CRITICAL: Update parent node confidence ONLY via transferred_confidence from children
        # This is the ONLY way confidence changes after initial calculation
        # Update from the first child (which will propagate up through the chain)
        self._update_confidence_from_children(node)
        
        print(json.dumps({
            "event": "below_baseline_leaf_extended",
            "leaf_node_id": node.id,
            "nodes_created": len(created_nodes),
            "max_nodes": 5,
            "branch_length": len(created_nodes),
            "node_details": [{"id": nid, "confidence": conf} for nid, conf in created_nodes],
            "parent_updated_via_transferred": node.transferred_confidence,
            "note": f"Created {len(created_nodes)} sequential nodes along branch - parent confidence updated ONLY via transferred_confidence from new children"
        }, ensure_ascii=False))
        
    async def _estimate_depth_expansion_gain(self, node: NodeState) -> Dict[str, float]:
        """Estimate confidence gain from extending a branch deeper."""
        # Estimate: extending by 2-3 plies might improve confidence by 3-8%
        # Time: ~2-3 seconds per ply extension
        estimated_gain = min(8, max(3, (self.baseline - node.confidence) * 0.3))
        time_estimate = 3.0  # seconds
        roi = estimated_gain / time_estimate if time_estimate > 0 else 0
        
        return {
            "gain": estimated_gain,
            "time_estimate": time_estimate,
            "roi": roi
        }
    
    async def _estimate_width_expansion_gain(self, start_node: NodeState, existing_children: List[NodeState]) -> Dict[str, float]:
        """Estimate confidence gain from adding more alternative moves."""
        # Check how many alternatives we could add
        board = chess.Board(start_node.fen)
        all_moves = list(board.legal_moves)
        
        # Get moves we haven't analyzed yet
        analyzed_moves = {chess.Move.from_uci(child.move) for child in existing_children if child.move}
        unanalyzed_moves = [m for m in all_moves if m not in analyzed_moves]
        
        if not unanalyzed_moves:
            return {"gain": 0, "time_estimate": 0, "roi": 0}
        
        # Estimate: adding 1-2 alternatives might improve confidence by 2-5%
        # (if they have better confidence than current worst)
        # Time: ~1-2 seconds per alternative
        estimated_gain = min(5, max(2, len(unanalyzed_moves) * 1.5))
        time_estimate = len(unanalyzed_moves[:2]) * 1.5  # Analyze up to 2 new alternatives
        roi = estimated_gain / time_estimate if time_estimate > 0 else 0
        
        return {
            "gain": estimated_gain,
            "time_estimate": time_estimate,
            "roi": roi
        }
    
    async def _expand_depth(self, node: NodeState) -> None:
        """Expand a branch deeper by analyzing further moves."""
        # Analyze using the FEN BEFORE the move (parent's FEN if available, otherwise node's FEN)
        parent_node = self.nodes.get(node.parent_id) if node.parent_id else None
        analysis_fen = parent_node.fen if parent_node else node.fen
        board = chess.Board(analysis_fen)
        
        # If we have a parent, we need to push the move to get to the node's position
        if parent_node and node.move:
            try:
                move = chess.Move.from_uci(node.move)
                if move in board.legal_moves:
                    board.push(move)
            except:
                pass  # If move parsing fails, use the board as-is
        
        # Get best move from this position (after the move if we pushed one)
        analysis = await analyse_pv(self.engine_queue, board, depth=18, max_length=3)
        if not analysis.moves:
            return
        
        next_move = analysis.moves[0]
        next_board = board.copy()
        next_board.push(next_move)
        
        # Analyze the new position using the position BEFORE next_move
        # So we analyze from 'board' (before next_move), not 'next_board' (after next_move)
        next_d18 = await analyse_pv(self.engine_queue, board, depth=18)
        next_d2 = await analyse_pv(self.engine_queue, board, depth=2)
        
        # Get endpoint
        endpoint_board = next_board.copy()
        if next_d18.moves:
            for move in next_d18.moves[:18]:
                if endpoint_board.is_game_over():
                    break
                # Check if move is legal before pushing
                if move in endpoint_board.legal_moves:
                    endpoint_board.push(move)
                else:
                    break  # Stop if we hit an illegal move
        
        endpoint_d18 = await analyse_pv(self.engine_queue, endpoint_board, depth=18)
        endpoint_d2 = await analyse_pv(self.engine_queue, endpoint_board, depth=2)
        
        # Calculate confidence
        s18 = next_d18.score_cp if next_d18.score_cp is not None else 0
        s2 = next_d2.score_cp if next_d2.score_cp is not None else 0
        pv18 = endpoint_d18.score_cp if endpoint_d18.score_cp is not None else 0
        pv2 = endpoint_d2.score_cp if endpoint_d2.score_cp is not None else 0
        
        # Normalize to starting perspective
        # CRITICAL: s18 and s2 are from analyzing 'board' (BEFORE move), so check board.turn
        next_before_perspective = board.turn == chess.WHITE
        endpoint_perspective = endpoint_board.turn == chess.WHITE
        if next_before_perspective != self.start_perspective_is_white:
            s18 = -s18
            s2 = -s2
        if endpoint_perspective != self.start_perspective_is_white:
            pv18 = -pv18
            pv2 = -pv2
        
        conf = _compute_confidence(s18, s2, pv18, pv2)
        if conf is None:
            conf = 0
        
        # Create new node
        new_node_id = f"{node.id}-ext-{node.ply_index + 1}"
        new_node = NodeState(
            id=new_node_id,
            parent_id=node.id,
            fen=next_board.fen(),
            move=next_move.uci(),
            ply_index=node.ply_index + 1,
            confidence=conf,
            role="extension",
            shape="circle",
            color="green" if conf >= self.baseline else "red",
        )
        new_node.set_initial_confidence(conf)
        new_node.refresh_color(self.baseline)
        self._add_node(new_node)
        node.has_branches = True
        
        print(json.dumps({
            "event": "depth_expansion_complete",
            "new_node_id": new_node_id,
            "confidence": conf,
            "ply_index": new_node.ply_index
        }, ensure_ascii=False))
            
    async def _expand_width(self, start_node: NodeState, existing_children: List[NodeState]) -> None:
        """Add more alternative moves from starting position."""
        board = chess.Board(start_node.fen)
        all_moves = list(board.legal_moves)
        
        # CRITICAL: When confidence is raised, create nodes for moves with better preference numbers
        # Get all moves with their depth 2 scores to calculate preference numbers
        all_move_evaluations: List[Tuple[chess.Move, int]] = []
        for move in all_moves:
            test_board = board.copy()
            test_board.push(move)
            move_d2_eval = await analyse_pv(self.engine_queue, test_board, depth=2)
            move_d2_score = move_d2_eval.score_cp if move_d2_eval.score_cp is not None else 0
            if test_board.turn != self.start_perspective_is_white:
                move_d2_score = -move_d2_score
            all_move_evaluations.append((move, move_d2_score))
        
        # Sort by depth 2 score (best first) to assign preference numbers
        sorted_by_d2 = sorted(all_move_evaluations, key=lambda x: x[1], reverse=True)
        preference_map: Dict[str, int] = {}
        for pref_num, (move, score) in enumerate(sorted_by_d2, start=1):
            preference_map[move.uci()] = pref_num
        
        # Get existing moves (by move UCI, not by node)
        existing_move_ucis = {child.move for child in existing_children if child.move}
        
        # Find moves with better preference numbers that don't exist yet
        # Priority: create nodes for preference 1, 2, 3, etc. that are missing
        missing_preference_moves: List[Tuple[chess.Move, int, int]] = []
        for move, move_d2_score in sorted_by_d2:
            move_uci = move.uci()
            pref_num = preference_map.get(move_uci)
            if pref_num is None:
                continue
            
            # Check if this move already exists as a child of start
            if move_uci not in existing_move_ucis:
                missing_preference_moves.append((move, move_d2_score, pref_num))
        
        # Sort by preference number (lower is better - rank 1, 2, 3, etc.)
        missing_preference_moves.sort(key=lambda x: x[2])
        
        if not missing_preference_moves:
            print(json.dumps({
                "event": "width_expansion_no_missing_moves",
                "existing_moves": list(existing_move_ucis),
                "note": "All preference moves already exist as children"
            }, ensure_ascii=False))
            print(json.dumps({
                "event": "width_expansion_complete",
                "alternatives_added": 0
            }, ensure_ascii=False))
            return
        
        alt_counter = len([n for n in existing_children if n.id and str(n.id).startswith("alt-")])
        added = 0
        
        # CRITICAL: When increasing confidence, create nodes for ALL missing preference moves (not just WIDTH_ADD_LIMIT)
        # This ensures we maximize confidence increase by exploring all alternatives
        max_moves_to_add = max(WIDTH_ADD_LIMIT, len(missing_preference_moves))  # Add all missing moves
        for move, move_d2_score, pref_num in missing_preference_moves[:max_moves_to_add]:
            # Skip if this move is the played move (it's already created as "played-move")
            # Note: best move might be the same as played move, so we check by move UCI
            if move == self.move:
                continue
            
            # Check if this move is already the best move (by checking existing best-move node)
            existing_best_move = self.nodes.get("best-move")
            if existing_best_move and existing_best_move.move == move.uci():
                continue
            
            # Get FEN after the move
            move_fen_board = board.copy()
            move_fen_board.push(move)
            move_fen = move_fen_board.fen()
            # CRITICAL: When increasing confidence, don't filter by ALT_SCORE_MARGIN
            # We want to create nodes for all missing preference moves to increase confidence
            # Only skip if the move is significantly worse (not just slightly worse)
            if self.played_move_d2_score is not None and move_d2_score < self.played_move_d2_score - ALT_SCORE_MARGIN:
                # Skip moves that are significantly worse than played move
                continue
            # Analyze using FEN BEFORE the move (start_board), not after
            start_node = self.nodes.get("start")
            if start_node:
                before_board = chess.Board(start_node.fen)
            else:
                before_board = self.start_board.copy()
            
            move_d18_before = await analyse_pv(self.engine_queue, before_board, depth=18)
            move_d2_before = await analyse_pv(self.engine_queue, before_board, depth=2)
            
            move_pv_board = before_board.copy()
            if move_d18_before.moves:
                for mv in move_d18_before.moves[:18]:
                    if move_pv_board.is_game_over():
                        break
                    if mv in move_pv_board.legal_moves:
                        move_pv_board.push(mv)
                    else:
                        break
            
            move_endpoint_d18 = await analyse_pv(self.engine_queue, move_pv_board, depth=18)
            move_endpoint_d2 = await analyse_pv(self.engine_queue, move_pv_board, depth=2)
            
            move_s18 = move_d18_before.score_cp if move_d18_before.score_cp is not None else 0
            move_s2 = move_d2_before.score_cp if move_d2_before.score_cp is not None else 0
            
            # Store the FEN after the move for the node
            test_board = chess.Board(move_fen)
            move_pv18 = move_endpoint_d18.score_cp if move_endpoint_d18 and move_endpoint_d18.score_cp is not None else 0
            move_pv2 = move_endpoint_d2.score_cp if move_endpoint_d2 and move_endpoint_d2.score_cp is not None else 0
            
            # Perspective is from starting position (before move)
            move_before_perspective = before_board.turn == chess.WHITE
            move_endpoint_perspective = move_pv_board.turn == chess.WHITE
            
            if move_before_perspective != self.start_perspective_is_white:
                move_s18 = -move_s18
                move_s2 = -move_s2
            if move_endpoint_perspective != self.start_perspective_is_white:
                move_pv18 = -move_pv18
                move_pv2 = -move_pv2
            
            move_conf = _compute_confidence(move_s18, move_s2, move_pv18, move_pv2)
            if move_conf is None:
                move_conf = 0
            
            # Create node with preference number (already calculated above)
            alt_node = NodeState(
                id=f"alt-{alt_counter}",
                parent_id="start",
                fen=move_fen,
                move=move.uci(),
                ply_index=1,
                confidence=move_conf,
                role="alternative",
                shape="circle",
                color="green" if move_conf >= self.baseline else "red",
                preference_number=pref_num,  # Use calculated preference number
            )
            alt_node.set_initial_confidence(move_conf)  # NEW initial confidence - locked
            alt_node.refresh_color(self.baseline)
            self._add_node(alt_node)
            alt_counter += 1
            added += 1
            start_node.has_branches = True
            
            print(json.dumps({
                "event": "width_expansion_added_alternative",
                "node_id": alt_node.id,
                "move": move.uci(),
                "preference_number": pref_num,
                "initial_confidence": move_conf,
                "note": "Created node for missing preference number"
            }, ensure_ascii=False))
        
        print(json.dumps({
            "event": "width_expansion_complete",
            "alternatives_added": added
        }, ensure_ascii=False))

    # DEPRECATED: This method is from the old iterative expansion system
    # It is NOT used in the new 3-phase system (Phase 1/2/3).
    # Kept for reference but should not be called.
    # The 3-phase system directly processes red nodes without using this candidate selection.
    def _eligible_candidates(self) -> List[Tuple[int, int, str, Dict[str, Any]]]:
        print(json.dumps({
            "event": "deprecated_method_called",
            "method": "_eligible_candidates",
            "warning": "This method is deprecated. The 3-phase system does not use candidate selection.",
            "note": "If you see this, there may be old code still calling this method"
        }, ensure_ascii=False))
        # Return empty heap to prevent old code from executing
        return []

    async def _extend_branch_from_blue_triangle(self, blue_node: NodeState) -> None:
        """Phase 2: Extend branch from blue triangle until green circle or 18 ply from origin.
        
        Args:
            blue_node: The blue triangle node to extend from
        """
        print(f"    🔍 Analyzing position at ply {blue_node.ply_index}...")
        
        print(json.dumps({
            "event": "phase2_extend_branch_start",
            "node_id": blue_node.id,
            "ply_index": blue_node.ply_index,
            "max_ply": self.max_ply
        }, ensure_ascii=False))
        
        board_at = chess.Board(blue_node.fen)
        
        # Get alternate moves (depth-2 multipv)
        candidates = await analyse_multipv(
            self.engine_queue,
            board_at,
            depth=2,
            multipv=max(2, self.topk + 1),
        )
        
        if not candidates or len(candidates) < 2:
            print(f"    ⚠️  No alternate moves found (only {len(candidates) if candidates else 0} candidate(s))")
            print(json.dumps({
                "event": "phase2_no_alternates",
                "node_id": blue_node.id,
                "reason": "no_candidates_or_only_one"
            }, ensure_ascii=False))
            return
        
        best_score = candidates[0].score_cp
        alternates: List[Tuple[int, chess.Move]] = []
        for candidate in candidates[1:]:
            if candidate.score_cp >= best_score - self.delta2:
                alternates.append((candidate.score_cp, candidate.move))
        
        # Force at least one alternate if confidence is below baseline
        if not alternates and blue_node.confidence < self.baseline and len(candidates) > 1:
            fallback = candidates[1]
            alternates.append((fallback.score_cp, fallback.move))
        
        if not alternates:
            print(f"    ⚠️  No alternates within delta2 ({self.delta2} cp)")
            print(json.dumps({
                "event": "phase2_no_alternates",
                "node_id": blue_node.id,
                "reason": "no_alternates_within_delta2"
            }, ensure_ascii=False))
            return
        
        print(f"    ✅ Found {len(alternates)} alternate move(s) to extend")
        
        # Extend branch for each alternate move (only first one for now, can extend later)
        for score_cp, move in alternates[:1]:  # Start with first alternate
            if move.uci() in blue_node.extended_moves:
                print(f"    ⏭️  Move {move.uci()} already extended, skipping")
                continue  # Already extended
            
            print(f"    🌿 Extending branch with move {move.uci()} (score: {score_cp} cp)")
            
            print(json.dumps({
                "event": "phase2_extending_move",
                "node_id": blue_node.id,
                "move": move.uci(),
                "score_cp": score_cp
            }, ensure_ascii=False))
            
            # Analyze using FEN BEFORE the move (board_at), not after
            # Analyze the position before the move is applied
            alt_deep = await analyse_pv(self.engine_queue, board_at, depth=self.max_ply, max_length=self.max_ply)
            alt_shallow = await analyse_pv(self.engine_queue, board_at, depth=2, max_length=self.max_ply)
            
            alt_s18 = alt_deep.score_cp if alt_deep and alt_deep.score_cp is not None else 0
            alt_s2 = alt_shallow.score_cp if alt_shallow and alt_shallow.score_cp is not None else 0
            
            # Normalize to starting perspective (from board_at, before move)
            alt_perspective_is_white = board_at.turn == chess.WHITE
            if alt_perspective_is_white != self.start_perspective_is_white:
                alt_s18 = -alt_s18
                alt_s2 = -alt_s2
            
            # Store the FEN after the move for the node
            alt_board = board_at.copy()
            alt_board.push(move)
            
            pv18 = self.pv_endpoint_deep if self.pv_endpoint_deep is not None else 0
            pv2 = self.pv_endpoint_shallow if self.pv_endpoint_shallow is not None else 0
            
            alt_conf = _compute_confidence(alt_s18, alt_s2, pv18, pv2)
            if alt_conf is None:
                alt_conf = 0
            
            # Create first branch node (circle)
            branch_mid_id = f"branch-{blue_node.id}-{self.branch_counter}"
            self.branch_counter += 1
            
            mid_node = NodeState(
                id=branch_mid_id,
                parent_id=blue_node.id,
                fen=alt_board.fen(),
                move=move.uci(),
                ply_index=blue_node.ply_index + 1,
                confidence=alt_conf,
                role="branch-mid",
                shape="circle",
                tags=["branch"],
                metadata={"score_cp": score_cp},
            )
            # Set initial_confidence immediately when branch node is created
            mid_node.set_initial_confidence(alt_conf)
            
            # Detect tags for branch node
            if aggregate_all_tags:
                try:
                    tags = await aggregate_all_tags(alt_board, self.engine_queue)
                    mid_node.tags.extend([tag.get("tag_name", "") for tag in tags if tag.get("tag_name")])
                    mid_node.metadata["tags"] = tags
                    mid_node.metadata["tag_count"] = len(tags)
                except Exception as e:
                    print(json.dumps({
                        "event": "tag_detection_failed",
                        "node_id": mid_node.id,
                        "error": str(e),
                        "note": "Tag detection failed for branch node"
                    }, ensure_ascii=False))
            
            mid_node.refresh_color(self.baseline)
            self._add_node(mid_node)
            
            print(f"      📍 Created branch node {mid_node.id} at ply {mid_node.ply_index} (confidence: {alt_conf}%)")
            
            # Recursively extend until green or 18 ply from origin
            terminal_conf = await self._expand_branch_recursive(mid_node, alt_board, alt_deep)
            
            # Store terminal confidence for this move
            blue_node.extended_moves[move.uci()] = terminal_conf
            
            print(f"      ✅ Branch extended to terminal confidence: {terminal_conf}%")
            
            print(json.dumps({
                "event": "phase2_branch_extended",
                "node_id": blue_node.id,
                "move": move.uci(),
                "initial_confidence": terminal_conf,
                "terminal_ply": mid_node.ply_index + (self.max_ply - blue_node.ply_index - 1)
            }, ensure_ascii=False))
    
    async def _freeze_and_recolor_blue_triangle(self, blue_node: NodeState) -> None:
        """Phase 3: Freeze blue triangle with terminal confidence, recolor based on frozen confidence.
        
        Args:
            blue_node: The blue triangle to freeze and recolor
        """
        print(f"    🔍 Processing {blue_node.id}...")
        
        print(json.dumps({
            "event": "phase3_freeze_start",
            "node_id": blue_node.id,
            "extended_moves": dict(blue_node.extended_moves)
        }, ensure_ascii=False))
        
        # Get minimum terminal confidence from all extended moves
        if blue_node.extended_moves:
            frozen_conf = min(blue_node.extended_moves.values())
            branch_confs = list(blue_node.extended_moves.values())
            print(f"      📊 Terminal confidences: {branch_confs} → min: {frozen_conf}%")
        else:
            # No branches extended, use current confidence
            frozen_conf = blue_node.confidence
            print(f"      ⚠️  No branches extended, using current confidence: {frozen_conf}%")
        
        # Set frozen confidence and refresh color immediately
        blue_node.set_frozen_confidence(frozen_conf, self.baseline)
        
        # Determine final shape: preserve square if original was square (PV endpoint)
        original_shape = blue_node.metadata.get("original_shape", blue_node.shape)
        pv_endpoint = blue_node.metadata.get("pv_endpoint", False)
        
        if pv_endpoint or original_shape == "square":
            blue_node.shape = "square"
            print(f"      🔲 Preserved square shape (original: {original_shape}, PV endpoint: {pv_endpoint})")
        else:
            blue_node.shape = "triangle"
            print(f"      🔺 Set to triangle shape (original: {original_shape})")
        
        # Recolor based on frozen confidence using refresh_color to ensure consistency
        # This ensures that future refresh_color calls will work correctly
        old_color = blue_node.color
        blue_node.refresh_color(self.baseline)
        
        print(f"      🎨 Recolored: {old_color} → {blue_node.color} (frozen: {frozen_conf}% vs baseline: {self.baseline}%)")
        
        # Verify the color is correct (debug check)
        if frozen_conf >= self.baseline and blue_node.color != "green":
            print(json.dumps({
                "event": "phase3_color_mismatch",
                "node_id": blue_node.id,
                "expected_color": "green",
                "actual_color": blue_node.color,
                "frozen_confidence": frozen_conf,
                "baseline": self.baseline,
                "has_branches": blue_node.has_branches,
                "note": "CRITICAL: Color should be green but isn't - investigating"
            }, ensure_ascii=False))
        elif frozen_conf < self.baseline and blue_node.color != "red":
            print(json.dumps({
                "event": "phase3_color_mismatch",
                "node_id": blue_node.id,
                "expected_color": "red",
                "actual_color": blue_node.color,
                "frozen_confidence": frozen_conf,
                "baseline": self.baseline,
                "has_branches": blue_node.has_branches,
                "note": "CRITICAL: Color should be red but isn't - investigating"
            }, ensure_ascii=False))
        
        # Update branch summary
        all_branch_confs = list(blue_node.extended_moves.values())
        blue_node.metadata["branch_summary"] = {
            "count": len(all_branch_confs),
            "min": min(all_branch_confs) if all_branch_confs else frozen_conf,
            "max": max(all_branch_confs) if all_branch_confs else frozen_conf,
        }
        
        print(f"      ✅ Final: {blue_node.shape} {blue_node.color}, frozen: {frozen_conf}%")
        
        print(json.dumps({
            "event": "phase3_freeze_complete",
            "node_id": blue_node.id,
            "frozen_confidence": frozen_conf,
            "final_shape": blue_node.shape,
            "final_color": blue_node.color,
            "baseline": self.baseline,
            "original_shape": original_shape
        }, ensure_ascii=False))
    
    async def _expand_branch_recursive(self, branch_node: NodeState, board: chess.Board, pv_analysis: Any) -> int:
        """Recursively expand a branch until it hits green or 18 ply limit from origin.
        Returns the terminal confidence of the branch.
        
        Args:
            branch_node: The current node in the branch
            board: The board state at branch_node
            pv_analysis: PVAnalysis object containing the PV moves to follow
        """
        current_node = branch_node
        current_board = board.copy()
        current_pv = pv_analysis.moves if pv_analysis and hasattr(pv_analysis, 'moves') else []
        
        # Continue expanding until green or 18 ply from origin (S0)
        while current_node.ply_index < self.max_ply:
            # Get the next move from PV
            if not current_pv:
                # No more moves in PV, this is the terminal node
                print(f"        ⚠️  Terminal node {current_node.id} - no more PV moves (ply {current_node.ply_index})")
                print(json.dumps({
                    "event": "phase2_branch_terminal_no_pv",
                    "node_id": current_node.id,
                    "ply_index": current_node.ply_index,
                    "confidence": current_node.confidence
                }, ensure_ascii=False))
                return current_node.confidence
            
            next_move = current_pv[0]
            current_pv = current_pv[1:]
            
            # Check ply limit from origin (S0)
            if current_node.ply_index + 1 > self.max_ply:
                print(f"        ⚠️  Terminal node at ply {current_node.ply_index + 1} - reached max ply limit ({self.max_ply})")
                print(json.dumps({
                    "event": "phase2_branch_terminal_ply_limit",
                    "node_id": current_node.id,
                    "ply_index": current_node.ply_index + 1,
                    "max_ply": self.max_ply,
                    "confidence": current_node.confidence
                }, ensure_ascii=False))
                return current_node.confidence
            
            print(f"        ➡️  Extending to ply {current_node.ply_index + 1} with move {next_move.uci()}")
            
            # Analyze using FEN BEFORE the move (current_board before push), not after
            # Analyze the position before the move is applied
            next_deep = await analyse_pv(self.engine_queue, current_board, depth=self.max_ply, max_length=self.max_ply)
            next_shallow = await analyse_pv(self.engine_queue, current_board, depth=2, max_length=self.max_ply)
            
            # Calculate confidence
            next_s18 = next_deep.score_cp if next_deep and next_deep.score_cp is not None else 0
            next_s2 = next_shallow.score_cp if next_shallow and next_shallow.score_cp is not None else 0
            
            # Normalize to starting perspective (from current_board, before move)
            next_perspective_is_white = current_board.turn == chess.WHITE
            if next_perspective_is_white != self.start_perspective_is_white:
                next_s18 = -next_s18
                next_s2 = -next_s2
            
            # Push the move to get the FEN after the move for the node
            current_board.push(next_move)
            
            pv18 = self.pv_endpoint_deep if self.pv_endpoint_deep is not None else 0
            pv2 = self.pv_endpoint_shallow if self.pv_endpoint_shallow is not None else 0
            
            next_conf = _compute_confidence(next_s18, next_s2, pv18, pv2)
            if next_conf is None:
                next_conf = 0
            
            # Create next node in the branch (always a circle)
            next_node_id = f"branch-leaf-{self.branch_counter}"
            self.branch_counter += 1
            
            next_node = NodeState(
                id=next_node_id,
                parent_id=current_node.id,
                fen=current_board.fen(),
                move=next_move.uci(),
                ply_index=current_node.ply_index + 1,
                confidence=next_conf,
                role="branch-leaf",
                shape="circle",  # Always a circle
                color="green" if next_conf >= self.baseline else "red",
                tags=["branch-leaf"],
                metadata={"score_cp": next_conf},
            )
            next_node.set_initial_confidence(next_conf)
            
            # Detect tags for branch leaf node
            if aggregate_all_tags:
                try:
                    tags = await aggregate_all_tags(current_board, self.engine_queue)
                    next_node.tags.extend([tag.get("tag_name", "") for tag in tags if tag.get("tag_name")])
                    next_node.metadata["tags"] = tags
                    next_node.metadata["tag_count"] = len(tags)
                except Exception as e:
                    print(json.dumps({
                        "event": "tag_detection_failed",
                        "node_id": next_node.id,
                        "error": str(e),
                        "note": "Tag detection failed for branch leaf node"
                    }, ensure_ascii=False))
            
            next_node.refresh_color(self.baseline)
            self._add_node(next_node)
            
            # Check if this node is green (stop if so)
            if next_node.color == "green":
                print(f"        ✅ Terminal node {next_node.id} is GREEN (confidence: {next_node.confidence}%) - stopping branch")
                print(json.dumps({
                    "event": "phase2_branch_terminal_green",
                    "node_id": next_node.id,
                    "ply_index": next_node.ply_index,
                    "confidence": next_node.confidence
                }, ensure_ascii=False))
                return next_node.confidence
            
            # Update current for next iteration
            current_node = next_node
            current_pv = next_deep.moves if next_deep else []
        
        # Reached 18 ply limit
        print(f"        ⚠️  Terminal node {current_node.id} - reached max ply limit ({self.max_ply})")
        print(json.dumps({
            "event": "phase2_branch_terminal_max_ply",
            "node_id": current_node.id,
            "ply_index": current_node.ply_index,
            "confidence": current_node.confidence
        }, ensure_ascii=False))
        return current_node.confidence

    # DEPRECATED: Old _expand_node method - no longer used in 3-phase system
    # This method is kept for reference but should not be called.
    # The new 3-phase system uses:
    # - Phase 1: _extend_branch_from_blue_triangle (converts red to blue)
    # - Phase 2: _extend_branch_from_blue_triangle (extends branches)
    # - Phase 3: _freeze_and_recolor_blue_triangle (freezes and recolors)
    async def _expand_node(self, node_id: str) -> bool:
        print(json.dumps({
            "event": "deprecated_method_called",
            "method": "_expand_node",
            "node_id": node_id,
            "warning": "This method is deprecated. The 3-phase system should be used instead.",
            "note": "If you see this, there may be old code still calling this method"
        }, ensure_ascii=False))
        # Return False to prevent execution of old logic
        return False

    async def run(
        self, 
        *, 
        enable_branching: bool,
        mode: str = "line",
        target_line_conf: Optional[int] = None,
        target_end_conf: Optional[int] = None,
        max_depth: Optional[int] = None
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        # CRITICAL: Only build PV if we don't have existing nodes
        # When increasing confidence, we should NOT recalculate anything - only generate new nodes
        # Check if we have ANY nodes loaded (not just ones with initial_confidence)
        # This is more robust - if nodes were passed in, we should have loaded them
        has_existing_nodes = len(self.nodes) > 0
        
        # Also check if we have nodes with initial_confidence (more strict check)
        has_nodes_with_initial_conf = any(
            n.initial_confidence is not None 
            for n in self.nodes.values()
        )
        
        print(json.dumps({
            "event": "run_method_node_check",
            "total_nodes": len(self.nodes),
            "has_existing_nodes": has_existing_nodes,
            "has_nodes_with_initial_conf": has_nodes_with_initial_conf,
            "node_ids": [n.id for n in list(self.nodes.values())[:5]],
            "note": "Checking if we should skip _build_pv"
        }, ensure_ascii=False))
        
        if not has_existing_nodes:
            # First time building the tree - calculate everything
            await self._build_pv()
        else:
            # Existing nodes present - skip _build_pv to avoid any recalculation
            # CRITICAL: Validate that we actually have nodes loaded
            if len(self.nodes) == 0:
                print(json.dumps({
                    "event": "CRITICAL_NO_NODES_LOADED",
                    "note": "CRITICAL: has_existing_nodes was True but self.nodes is empty! This should never happen. Rebuilding tree."
                }, ensure_ascii=False))
                # Fallback: rebuild tree if somehow nodes weren't loaded
                await self._build_pv()
                await self._extend_below_baseline_leaves(force_extend_all=False)
                self._propagate_confidences()
                self._print_tree_summary("INITIAL CONFIDENCE TREE (REBUILT)")
                self._record_snapshot("initial")
                # Continue with rest of run() logic
            else:
                # Extract necessary state from existing nodes instead of recalculating
                start_node = self.nodes.get("start")
                if start_node:
                    if start_node.initial_confidence is not None:
                        self.start_confidence = start_node.initial_confidence
                    elif start_node.transferred_confidence is not None:
                        self.start_confidence = start_node.transferred_confidence
                    else:
                        self.start_confidence = start_node.confidence
                    self.start_perspective_is_white = self.start_board.turn == chess.WHITE
                else:
                    # This shouldn't happen, but create minimal start node if needed
                    start_node = NodeState(
                        id="start",
                        parent_id=None,
                        fen=self.start_board.fen(),
                        move=None,
                        ply_index=0,
                        confidence=0,
                        role="start",
                        shape="square",
                        color="grey",
                    )
                    self._add_node(start_node)
                    self.start_confidence = 0
                    self.start_perspective_is_white = self.start_board.turn == chess.WHITE
            
            # Extract played_move_d2_score from existing played-move node if available
            played_move_node = self.nodes.get("played-move")
            # played_move_d2_score is stored separately, not in terminal_confidence
            # If we need it, we'll need to get it from metadata or recalculate
            
            print(json.dumps({
                "event": "skipping_build_pv_with_existing_nodes",
                "existing_nodes_count": len(self.nodes),
                "start_confidence": self.start_confidence,
                "node_ids": [n.id for n in list(self.nodes.values())[:10]],
                "note": "Skipping _build_pv to prevent Stockfish recalculation - only generating new nodes"
            }, ensure_ascii=False))
        
        # Extend any below-baseline leaf nodes after initial tree is built
        # CRITICAL: This is the ONLY way to increase confidence - by extending nodes with new children
        if len(self.nodes) > 0:
            await self._extend_below_baseline_leaves(force_extend_all=False)
        self._propagate_confidences()  # Update confidences after extension
        self._print_tree_summary("INITIAL CONFIDENCE TREE")
        self._record_snapshot("initial")

        if mode == "line" and target_line_conf is not None:
            self.baseline = target_line_conf
        elif mode == "end" and target_end_conf is not None:
            self.baseline = target_end_conf
        if max_depth is not None and mode == "depth":
            self.max_ply = max_depth

        for node in self.nodes.values():
            node.refresh_color(self.baseline)

        if enable_branching:
            await self._intelligent_expand()
            # After intelligent expansion, extend any newly created below-baseline leaves
            # CRITICAL: When enable_branching=True, ALWAYS extend ALL leaf nodes (not just below-baseline)
            # This is the ONLY way to increase confidence - by extending nodes with new children
            # Even if confidence is already high, we need to extend to potentially increase it further
            await self._extend_below_baseline_leaves(force_extend_all=True)
            self._propagate_confidences()
            self._record_snapshot("after_expand")

        start_node = self.nodes.get("start")
        if start_node:
            # Use transferred_confidence if available, otherwise initial_confidence
            if start_node.transferred_confidence is not None:
                self.start_confidence = start_node.transferred_confidence
            elif start_node.initial_confidence is not None:
                self.start_confidence = start_node.initial_confidence
            else:
                self.start_confidence = start_node.confidence

        # Calculate confidences using transferred_confidence if available, otherwise initial_confidence
        all_confidences = []
        for node in self.nodes.values():
            if node.transferred_confidence is not None:
                all_confidences.append(node.transferred_confidence)
            elif node.initial_confidence is not None:
                all_confidences.append(node.initial_confidence)
            else:
                all_confidences.append(node.confidence)
        
        if all_confidences:
            self.min_pv_confidence = min(all_confidences)
            self.end_confidence = max(all_confidences)
        else:
            self.min_pv_confidence = self.end_confidence = self.start_confidence

        # CRITICAL: Sync all nodes' confidence fields with their transferred_confidence
        # This ensures that after all propagation is complete, every node's confidence
        # field reflects its transferred_confidence if it has one
        self._sync_confidences_with_transferred()

        self.stats = self._compute_stats()
        final_payload = self._final_payload()
        self._print_tree_summary("FINAL CONFIDENCE TREE")
        return final_payload, self.stats

        # Legacy multi-phase implementation retained below (unreachable)
        
        # Print concise BEFORE summary
        self._print_tree_summary("BEFORE CONFIDENCE RAISE")
        
        self._record_snapshot("initial")
        
        # Handle different expansion modes FIRST (before refreshing colors)
        if mode == "depth" and max_depth is not None:
            # Update max_ply and continue with normal expansion
            old_max_ply = self.max_ply
            self.max_ply = max_depth
            print(json.dumps({
                "event": "depth_expansion_mode",
                "old_max_ply": old_max_ply,
                "new_max_ply": self.max_ply,
                "note": "Expanding tree to new maximum depth"
            }, ensure_ascii=False))
        
        # Determine target baseline based on mode BEFORE refreshing colors
        old_baseline = self.baseline
        if mode == "line" and target_line_conf is not None:
            self.baseline = target_line_conf
            print(json.dumps({
                "event": "line_confidence_mode",
                "old_baseline": old_baseline,
                "new_baseline": self.baseline,
                "target_line_conf": target_line_conf,
                "note": "Targeting line confidence (excluding last PV node)"
            }, ensure_ascii=False))
        elif mode == "end" and target_end_conf is not None:
            self.baseline = target_end_conf
            print(json.dumps({
                "event": "end_confidence_mode",
                "old_baseline": old_baseline,
                "new_baseline": self.baseline,
                "target_end_conf": target_end_conf,
                "note": "Targeting end confidence (last PV node only)"
            }, ensure_ascii=False))
        
        # NOW refresh all nodes with the CORRECT baseline
        print(json.dumps({
            "event": "pre_phase1_refresh_start",
            "baseline": self.baseline,
            "old_baseline": old_baseline,
            "total_nodes": len(self.nodes),
            "note": "Refreshing all node colors with NEW baseline before Phase 1"
        }, ensure_ascii=False))
        
        def is_node_below_baseline(node: NodeState) -> bool:
            """Check if node is below baseline based on its confidence values."""
            return node.confidence < self.baseline
        
        def summarize_node_states(label: str) -> Dict[str, Any]:
            total_nodes = len(self.nodes)
            pv_nodes = [n for n in self.nodes.values() if n.role == "pv"]
            triangles = [n.id for n in self.nodes.values() if n.has_branches]
            red_nodes_list = [n.id for n in self.nodes.values() if is_node_below_baseline(n)]
            summary = {
                "label": label,
                "total_nodes": total_nodes,
                "pv_nodes": len(pv_nodes),
                "triangles": len(triangles),
                "red_nodes": len(red_nodes_list),
                "red_node_samples": red_nodes_list[:10]
            }
            return summary
        
        print(json.dumps({
            "event": "pre_phase1_node_states",
            "summary": summarize_node_states("before_refresh"),
            "note": "Node state summary BEFORE refresh_color"
        }, ensure_ascii=False))
        
        # CRITICAL: Identify red nodes BEFORE refreshing colors
        # Use actual confidence/frozen_confidence values, not color (which might be stale)
        
        # Identify red nodes based on actual confidence values
        red_nodes_before_refresh = [n for n in self.nodes.values() if is_node_below_baseline(n)]
        
        print(json.dumps({
            "event": "red_nodes_identified_before_refresh",
            "red_nodes_count": len(red_nodes_before_refresh),
            "red_node_ids": [n.id for n in red_nodes_before_refresh],
            "baseline": self.baseline,
            "note": "Red nodes identified based on confidence values BEFORE refresh_color"
        }, ensure_ascii=False))
        
        # NOW refresh colors with the NEW baseline
        for node in self.nodes.values():
            node.refresh_color(self.baseline)
        
        print(json.dumps({
            "event": "post_refresh_node_states",
            "summary": summarize_node_states("after_refresh"),
            "baseline": self.baseline,
            "note": "Node state summary AFTER refresh_color"
        }, ensure_ascii=False))
        
        # Use the red nodes identified BEFORE refresh (they're the ones that need branching)
        red_nodes = red_nodes_before_refresh
        
        print(json.dumps({
            "event": "red_nodes_before_mode_filtering",
            "red_nodes_count": len(red_nodes),
            "red_node_ids": [n.id for n in red_nodes],
            "red_node_details": [
                {
                    "id": n.id,
                    "role": n.role,
                    "confidence": n.confidence,
                    "frozen_confidence": n.frozen_confidence,
                    "has_branches": n.has_branches,
                    "ply_index": n.ply_index
                }
                for n in red_nodes
            ],
            "mode": mode,
            "note": "Red nodes BEFORE mode filtering"
        }, ensure_ascii=False))
        
        # Filter red nodes based on mode
        if mode == "end":
            # Only process last PV node for end confidence
            pv_nodes = [n for n in self.nodes.values() if n.role == "pv"]
            if pv_nodes:
                pv_nodes_sorted = sorted(pv_nodes, key=lambda n: n.ply_index)
                last_pv = pv_nodes_sorted[-1]
                excluded_count = len(red_nodes)
                red_nodes = [n for n in red_nodes if n.id == last_pv.id]
                excluded_count -= len(red_nodes)
                print(json.dumps({
                    "event": "end_mode_filtering",
                    "last_pv_node_id": last_pv.id,
                    "last_pv_confidence": last_pv.confidence,
                    "last_pv_frozen": last_pv.frozen_confidence,
                    "last_pv_is_red": last_pv.id in [n.id for n in red_nodes_before_refresh],
                    "filtered_red_nodes": [n.id for n in red_nodes],
                    "excluded_count": excluded_count,
                    "note": f"End mode: only processing last PV node (excluded {excluded_count} other red nodes)"
                }, ensure_ascii=False))
        elif mode == "line":
            # Exclude last PV node for line confidence
            pv_nodes = [n for n in self.nodes.values() if n.role == "pv"]
            if pv_nodes:
                pv_nodes_sorted = sorted(pv_nodes, key=lambda n: n.ply_index)
                last_pv_id = pv_nodes_sorted[-1].id
                last_pv_node = pv_nodes_sorted[-1]
                excluded_count = sum(1 for n in red_nodes if n.id == last_pv_id)
                red_nodes = [n for n in red_nodes if n.id != last_pv_id]
                print(json.dumps({
                    "event": "line_mode_filtering",
                    "last_pv_node_id": last_pv_id,
                    "last_pv_confidence": last_pv_node.confidence,
                    "last_pv_frozen": last_pv_node.frozen_confidence,
                    "last_pv_was_red": last_pv_id in [n.id for n in red_nodes_before_refresh],
                    "filtered_red_nodes": [n.id for n in red_nodes],
                    "excluded_count": excluded_count,
                    "note": f"Line mode: excluding last PV node (excluded {excluded_count} red node(s))"
                }, ensure_ascii=False))
        
        print(json.dumps({
            "event": "red_nodes_identified_after_filtering",
            "red_nodes_count": len(red_nodes),
            "red_node_ids": [n.id for n in red_nodes],
            "mode": mode,
            "filtered_from": len(red_nodes_before_refresh),
            "note": f"Red nodes identified for Phase 1 processing (filtered from {len(red_nodes_before_refresh)} to {len(red_nodes)} by mode '{mode}')"
        }, ensure_ascii=False))
        
        # For now, if branching is disabled or no red nodes, just return the tree
        if not enable_branching or not red_nodes:
            self.stats = self._compute_stats()
            final_payload = self._final_payload()
            self._print_tree_summary("FINAL TREE")
            return final_payload, self.stats
        
        # Intelligent expansion: boost confidence by 5-10% per iteration
        await self._intelligent_expand()
        
        # Update all parent confidences from children
        self._propagate_confidences()
        
        self.stats = self._compute_stats()
        final_payload = self._final_payload()
        self._print_tree_summary("FINAL TREE")
        return final_payload, self.stats
        
        # ============================================================
        # PHASE 1: Convert all red circles/triangles/squares to blue triangles
        # ============================================================
        print("\n" + "="*80)
        print("🌳 PHASE 1: CONVERTING RED NODES TO BLUE TRIANGLES")
        print("="*80)
        print(f"📊 Found {len(red_nodes)} red node(s) to convert")
        print(f"🎯 Baseline confidence: {self.baseline}%")
        
        print(json.dumps({
            "event": "phase1_start",
            "red_nodes_count": len(red_nodes),
            "baseline": self.baseline
        }, ensure_ascii=False))
        
        blue_triangles: List[NodeState] = []
        # Reset phase info for this run
        self.phase_info["phase1_nodes_converted"] = 0
        self.phase_info["phase2_nodes_added"] = 0
        self.phase_info["phase3_nodes_frozen"] = 0
        for idx, node in enumerate(red_nodes, 1):
            # Store original shape and confidence before conversion
            if "original_shape" not in node.metadata:
                node.metadata["original_shape"] = node.shape
            
            # CRITICAL: initial_confidence should already be set when node was created
            # Only set it here if it's somehow None (shouldn't happen for new nodes)
            # For nodes loaded from existing_nodes, initial_confidence should be preserved
            if node.initial_confidence is None:
                # This is a fallback - node should have had initial_confidence set at creation
                # Set it to current confidence, but log a warning
                was_set = node.set_initial_confidence(node.confidence)
                print(json.dumps({
                    "event": "initial_confidence_set_in_phase1_fallback",
                    "node_id": node.id,
                    "initial_confidence": node.initial_confidence,
                    "confidence": node.confidence,
                    "note": "WARNING: initial_confidence was None in Phase 1 - this should not happen. Setting as fallback."
                }, ensure_ascii=False))
            else:
                # initial_confidence already set - verify it hasn't changed
                if node.initial_confidence != node.confidence:
                    # Log if confidence has changed from initial (this is expected after refresh_color)
                    print(json.dumps({
                        "event": "initial_confidence_preserved_in_phase1",
                        "node_id": node.id,
                        "existing_initial_confidence": node.initial_confidence,
                        "current_confidence": node.confidence,
                        "confidence_difference": node.confidence - node.initial_confidence,
                        "note": "Initial confidence preserved (immutable) - current confidence may differ after refresh_color"
                    }, ensure_ascii=False))
                else:
                    print(json.dumps({
                        "event": "initial_confidence_unchanged_in_phase1",
                        "node_id": node.id,
                        "initial_confidence": node.initial_confidence,
                        "current_confidence": node.confidence,
                        "note": "Initial confidence matches current confidence"
                    }, ensure_ascii=False))
            
            original_shape = node.metadata.get("original_shape")
            original_color = node.color
            
            # Convert to blue triangle (preserve square if PV endpoint)
            pv_endpoint = node.metadata.get("pv_endpoint")
            if not pv_endpoint:
                node.shape = "triangle"
            node.has_branches = True
            node.color = "blue"
            blue_triangles.append(node)
            self.phase_info["phase1_nodes_converted"] += 1
            
            print(f"  [{idx}/{len(red_nodes)}] {node.id}: {original_shape} {original_color} → {node.shape} {node.color}")
            print(f"      Confidence: {node.confidence}% (initial: {node.initial_confidence}%)")
            if pv_endpoint:
                print(f"      ⚠️  Preserved square shape (PV endpoint)")
            
            print(json.dumps({
                "event": "phase1_convert_to_blue_triangle",
                "node_id": node.id,
                "original_shape": original_shape,
                "new_shape": node.shape,
                "confidence": node.confidence,
                "initial_confidence": node.initial_confidence
            }, ensure_ascii=False))
        
        self._record_snapshot("phase1_complete")
        print(f"\n✅ PHASE 1 COMPLETE: {len(blue_triangles)} node(s) converted to blue triangles")
        print("="*80)
        
        print(json.dumps({
            "event": "phase1_complete",
            "blue_triangles_count": len(blue_triangles)
        }, ensure_ascii=False))
        
        # ============================================================
        # PHASE 2: Extend branches from blue triangles until green or 18 ply
        # ============================================================
        print("\n" + "="*80)
        print("🌳 PHASE 2: EXTENDING BRANCHES FROM BLUE TRIANGLES")
        print("="*80)
        print(f"📊 Extending branches from {len(blue_triangles)} blue triangle(s)")
        print(f"🎯 Max distance from origin: {self.max_ply} ply")
        
        print(json.dumps({
            "event": "phase2_start",
            "blue_triangles_to_extend": len(blue_triangles)
        }, ensure_ascii=False))
        
        nodes_before = len(self.nodes)
        for idx, blue_node in enumerate(blue_triangles, 1):
            print(f"\n  [{idx}/{len(blue_triangles)}] Extending branch from {blue_node.id} (ply {blue_node.ply_index})")
            await self._extend_branch_from_blue_triangle(blue_node)
        
        nodes_after = len(self.nodes)
        nodes_added = nodes_after - nodes_before
        self.phase_info["phase2_nodes_added"] = nodes_added
        
        self._record_snapshot("phase2_complete")
        print(f"\n✅ PHASE 2 COMPLETE: Added {nodes_added} new node(s) (total: {nodes_after})")
        print("="*80)
        
        print(json.dumps({
            "event": "phase2_complete",
            "total_nodes_after_extension": nodes_after,
            "nodes_added": nodes_added
        }, ensure_ascii=False))
        
        # ============================================================
        # PHASE 3: Freeze blue shapes with terminal confidence, recolor
        # ============================================================
        print("\n" + "="*80)
        print("🌳 PHASE 3: FREEZING AND RECOLORING BLUE TRIANGLES")
        print("="*80)
        print(f"📊 Freezing {len(blue_triangles)} blue triangle(s) with terminal confidence")
        print(f"🎯 Baseline confidence: {self.baseline}%")
        
        print(json.dumps({
            "event": "phase3_start"
        }, ensure_ascii=False))
        
        for idx, blue_node in enumerate(blue_triangles, 1):
            print(f"\n  [{idx}/{len(blue_triangles)}] Freezing {blue_node.id}")
            await self._freeze_and_recolor_blue_triangle(blue_node)
            self.phase_info["phase3_nodes_frozen"] += 1
        
        self._record_snapshot("phase3_complete")
        print(f"\n✅ PHASE 3 COMPLETE: All nodes frozen and recolored")
        print("="*80)
        
        print(json.dumps({
            "event": "phase3_complete"
        }, ensure_ascii=False))
        
        # Update confidence calculations after all phases
        pv_nodes = [self.nodes[nid] for nid in self.order if self.nodes[nid].role == "pv"]
        if pv_nodes:
            # Sort PV nodes by ply_index to ensure correct order
            pv_nodes_sorted = sorted(pv_nodes, key=lambda n: n.ply_index)
            
            # End confidence: confidence of last PV node (the square)
            # NOTE: The last PV node is the endpoint, so its confidence is calculated using
            # the same endpoint values for all four inputs (s18, s2, pv18, pv2), which
            # mathematically results in 100% confidence. This is correct behavior.
            # However, if the node has branches, use frozen_confidence instead.
            last_pv_node = pv_nodes_sorted[-1]
            
            # If the last node has branches, use frozen_confidence
            if last_pv_node.has_branches and last_pv_node.frozen_confidence is not None:
                self.end_confidence = last_pv_node.frozen_confidence
            else:
                # For the endpoint node, confidence is always 100% because all eval values are the same
                # Instead, use the confidence of the move that led to this endpoint
                # (i.e., the confidence of the second-to-last node, or the last node if only one exists)
                if len(pv_nodes_sorted) > 1:
                    # Use the confidence of the second-to-last node (the move before the endpoint)
                    second_to_last = pv_nodes_sorted[-2]
                    self.end_confidence = (
                        second_to_last.frozen_confidence 
                        if second_to_last.has_branches and second_to_last.frozen_confidence is not None 
                        else second_to_last.confidence
                    )
                else:
                    # Only one PV node, use its confidence (though it will be 100%)
                    self.end_confidence = last_pv_node.confidence
            
            # Line confidence: minimum of all PV nodes EXCEPT the last one
            if len(pv_nodes_sorted) > 1:
                line_pv_nodes = pv_nodes_sorted[:-1]  # All except last
                self.min_pv_confidence = min(
                    node.frozen_confidence if node.has_branches and node.frozen_confidence is not None else node.confidence
                    for node in line_pv_nodes
                )
            else:
                # Only one PV node, line confidence equals end confidence
                self.min_pv_confidence = self.end_confidence
            
            print(json.dumps({
                "event": "confidence_calculations_complete",
                "line_confidence": self.min_pv_confidence,
                "end_confidence": self.end_confidence,
                "pv_length": len(pv_nodes_sorted),
                "last_pv_node_id": last_pv_node.id,
                "last_pv_confidence": last_pv_node.confidence,
                "last_pv_frozen": last_pv_node.frozen_confidence
            }, ensure_ascii=False))
        
        self.stats = self._compute_stats()
        final_payload = self._final_payload()
        
        # Print concise AFTER summary
        self._print_tree_summary("AFTER CONFIDENCE RAISE")
        
        print("\n" + "="*80)
        print("✅ CONFIDENCE RAISE COMPLETE")
        print("="*80)
        print(f"📊 Total nodes: {len(self.nodes)}")
        print(f"🎯 Line confidence: {self.min_pv_confidence}%")
        print(f"🎯 End confidence: {self.end_confidence}%")
        print(f"📸 Snapshots recorded: {len(final_payload['snapshots'])}")
        
        # Count nodes by color
        color_counts = {"red": 0, "green": 0, "blue": 0}
        shape_counts = {"circle": 0, "triangle": 0, "square": 0}
        for node in self.nodes.values():
            color_counts[node.color] = color_counts.get(node.color, 0) + 1
            shape_counts[node.shape] = shape_counts.get(node.shape, 0) + 1
        
        print(f"🎨 Colors: {color_counts['red']} red, {color_counts['green']} green, {color_counts['blue']} blue")
        print(f"🔷 Shapes: {shape_counts['circle']} circles, {shape_counts['triangle']} triangles, {shape_counts['square']} squares")
        print("="*80 + "\n")
        
        # Add phase information to stats for frontend logging
        self.phase_info["phases_executed"] = ["phase1", "phase2", "phase3"]
        self.stats["phase_info"] = self.phase_info
        
        print(json.dumps({
            "event": "confidence_raise_complete",
            "total_nodes": len(self.nodes),
            "snapshots_recorded": len(final_payload['snapshots']),
            "line_confidence": self.min_pv_confidence,
            "end_confidence": self.end_confidence,
            "color_counts": color_counts,
            "shape_counts": shape_counts,
            "phase_info": self.phase_info
        }, ensure_ascii=False))
        
        return final_payload, self.stats

    def _final_payload(self) -> Dict[str, Any]:
        return {
            "nodes": [self.nodes[nid].to_payload() for nid in self.order],
            "snapshots": list(self.snapshots),
            "line_confidence": self.min_pv_confidence,
            "end_confidence": self.end_confidence,
        }


def neutral_confidence() -> Dict[str, Any]:
    return {
        "overall_confidence": 100,
        "line_confidence": 100,
        "end_confidence": 100,
        "lowest_confidence": 100,
        "nodes": [],
        "caps": {"global_nodes_used": 0, "max_nodes_global": DEFAULT_MAX_NODES},
        "snapshots": [],
        "stats": {},
    }


async def compute_move_confidence(
    engine_queue: "StockfishQueue",
    start_fen: str,
    move_san: str,
    *,
    target_conf: int = DEFAULT_BASELINE,
    delta2: int = DEFAULT_DELTA2,
    topk: int = DEFAULT_TOPK,
    max_nodes_global: int = DEFAULT_MAX_NODES,
    max_ply_from_S0: int = DEFAULT_MAX_PLY,
    branch: bool = False,
    existing_nodes: Optional[List[Dict[str, Any]]] = None,
    mode: str = "line",
    target_line_conf: Optional[int] = None,
    target_end_conf: Optional[int] = None,
    max_depth: Optional[int] = None,
) -> Dict[str, Any]:
    try:
        board = chess.Board(start_fen)
        move = board.parse_san(move_san)
    except Exception as err:
        raise ValueError(f"Invalid SAN '{move_san}': {err}")

    engine_runner = ConfidenceEngine(
        engine_queue,
        start_board=board,
        move=move,
        baseline=target_conf,
        delta2=delta2,
        topk=topk,
        max_nodes=max_nodes_global,
        max_iterations=DEFAULT_MAX_ITERATIONS,
        max_ply=max_ply_from_S0,
        existing_nodes=existing_nodes,
    )

    try:
        payload, stats = await engine_runner.run(
            enable_branching=branch,
            mode=mode,
            target_line_conf=target_line_conf,
            target_end_conf=target_end_conf,
            max_depth=max_depth
        )
        nodes_payload = payload["nodes"]
        overall_conf = engine_runner.start_confidence
        min_conf = engine_runner.min_pv_confidence
        lowest_conf = min((node["ConfidencePercent"] for node in nodes_payload), default=overall_conf)
        snapshots = payload["snapshots"]

        # Extract end_confidence from payload if available
        end_conf = payload.get("end_confidence", overall_conf)
        
        result = {
            "overall_confidence": overall_conf,
            "line_confidence": min_conf,
            "end_confidence": end_conf,
            "lowest_confidence": lowest_conf,
            "nodes": nodes_payload,
            "caps": {
                "global_nodes_used": len(nodes_payload),
                "max_nodes_global": max_nodes_global,
            },
            "snapshots": snapshots,
            "stats": stats,
        }
        
        # DEBUG: Print what's being returned from compute_move_confidence
        print("\n" + "="*80)
        print("📤 RETURNING FROM compute_move_confidence")
        print("="*80)
        print(f"Overall confidence: {overall_conf}")
        print(f"Line confidence: {min_conf}")
        print(f"End confidence: {end_conf}")
        print(f"Lowest confidence: {lowest_conf}")
        print(f"Nodes count: {len(nodes_payload)}")
        print(f"Snapshots count: {len(snapshots)}")
        if nodes_payload:
            print(f"First node: {json.dumps(nodes_payload[0], indent=2)}")
            print(f"Last node: {json.dumps(nodes_payload[-1], indent=2)}")
        else:
            print("⚠️  WARNING: nodes_payload is EMPTY!")
        print("="*80 + "\n")
        
        return result
    except Exception as exc:
        import traceback

        print(json.dumps({"event": "confidence_exception", "error": str(exc)}, ensure_ascii=False))
        print(traceback.format_exc())
        return neutral_confidence()


async def compute_position_confidence(
    engine_queue: "StockfishQueue",
    start_fen: str,
    *,
    target_conf: int = DEFAULT_BASELINE,
    branch: bool = False,
) -> Dict[str, Any]:
    board = chess.Board(start_fen)
    pv_analysis = await analyse_pv(engine_queue, board, depth=DEFAULT_MAX_PLY, max_length=DEFAULT_MAX_PLY)
    if not pv_analysis.moves:
        return neutral_confidence()
    move_san = board.san(pv_analysis.moves[0])
    return await compute_move_confidence(
        engine_queue,
        start_fen,
        move_san,
        target_conf=target_conf,
        branch=branch,
    )


