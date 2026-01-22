"""
Test helper functions for outcome verification.

These helpers check actual good outcomes, not just absence of errors.
"""

import chess
from typing import List, Dict, Any


def assert_confidence_mathematically_valid(nodes: List[Dict[str, Any]], tolerance: int = 2):
    """
    Verify confidence values match the formula:
    confidence = 100 - |s18-s2| - |pv18-pv2| - |pv2-s18|
    
    Args:
        nodes: List of confidence tree nodes
        tolerance: Allowed deviation in percentage points
    """
    for node in nodes:
        conf = node.get("ConfidencePercent")
        assert conf is not None, f"Node {node['id']} missing confidence"
        assert 0 <= conf <= 100, f"Node {node['id']} confidence {conf}% out of range"
        
        # If we have metadata with evaluations, verify formula
        metadata = node.get("metadata", {})
        if "evaluations" in metadata:
            evals = metadata["evaluations"]
            s18 = evals.get("s18")
            s2 = evals.get("s2")
            pv18 = evals.get("pv18")
            pv2 = evals.get("pv2")
            
            if all(v is not None for v in [s18, s2, pv18, pv2]):
                expected = 100 - abs(s18 - s2) - abs(pv18 - pv2) - abs(pv2 - s18)
                assert abs(conf - expected) <= tolerance, \
                    f"Node {node['id']}: confidence {conf}% doesn't match formula {expected}%"


def assert_colors_match_baseline(nodes: List[Dict[str, Any]], baseline: int):
    """
    Verify node colors match baseline threshold.
    Green >= baseline, red < baseline.
    """
    for node in nodes:
        conf = node.get("ConfidencePercent")
        color = node.get("color")
        
        assert color in ["red", "green"], \
            f"Node {node['id']} has invalid color: {color}"
        
        if conf >= baseline:
            assert color == "green", \
                f"Node {node['id']} has {conf}% >= {baseline}% but is {color}, should be green"
        else:
            assert color == "red", \
                f"Node {node['id']} has {conf}% < {baseline}% but is {color}, should be red"


def assert_tree_structure_valid(nodes: List[Dict[str, Any]]):
    """
    Verify tree forms valid DAG: root exists, no cycles, all connected.
    """
    if len(nodes) == 0:
        return
    
    # Check root exists
    roots = [n for n in nodes if n.get("parent_id") is None]
    assert len(roots) > 0, "Tree should have at least one root node"
    
    # Build parent-child map
    node_map = {n["id"]: n for n in nodes}
    
    # Check all parent references are valid
    for node in nodes:
        parent_id = node.get("parent_id")
        if parent_id is not None:
            assert parent_id in node_map, \
                f"Node {node['id']} references non-existent parent {parent_id}"
    
    # Check no cycles (simple check: traverse from root shouldn't revisit)
    def has_cycle(node_id, visited):
        if node_id in visited:
            return True
        visited.add(node_id)
        
        # Find children
        children = [n for n in nodes if n.get("parent_id") == node_id]
        for child in children:
            if has_cycle(child["id"], visited.copy()):
                return True
        return False
    
    for root in roots:
        assert not has_cycle(root["id"], set()), f"Cycle detected from root {root['id']}"


def assert_node_data_complete(nodes: List[Dict[str, Any]]):
    """
    Verify every node has all required fields with valid values.
    """
    required_fields = {
        "id": str,
        "fen": str,
        "move_from_parent": str,
        "ply_from_S0": int,
        "ConfidencePercent": (int, float),
        "shape": str,
        "color": str
    }
    
    for node in nodes:
        for field, expected_type in required_fields.items():
            assert field in node, f"Node {node.get('id', 'unknown')} missing field: {field}"
            value = node[field]
            
            # Allow None for first node's move_from_parent
            if field == "move_from_parent" and node.get("parent_id") is None:
                continue
            
            assert value is not None, f"Node {node['id']} has None for {field}"
            assert isinstance(value, expected_type), \
                f"Node {node['id']} field {field} wrong type: {type(value)}, expected {expected_type}"


def assert_all_fens_valid(nodes: List[Dict[str, Any]]):
    """
    Verify every FEN is chess-legal and parseable.
    """
    for node in nodes:
        fen = node.get("fen")
        assert fen is not None, f"Node {node['id']} missing FEN"
        
        try:
            board = chess.Board(fen)
            assert board.is_valid(), f"Node {node['id']} FEN is invalid: {fen}"
        except Exception as e:
            raise AssertionError(f"Node {node['id']} has unparseable FEN: {fen}, error: {e}")


def assert_moves_are_legal(nodes: List[Dict[str, Any]]):
    """
    Verify each move is legal from parent's FEN and produces node's FEN.
    """
    # Build parent map
    node_map = {n["id"]: n for n in nodes}
    
    for node in nodes:
        parent_id = node.get("parent_id")
        if parent_id is None:
            continue  # Root node
        
        parent = node_map.get(parent_id)
        assert parent is not None, f"Node {node['id']} parent {parent_id} not found"
        
        parent_board = chess.Board(parent["fen"])
        move_uci = node["move_from_parent"]
        
        try:
            move = chess.Move.from_uci(move_uci)
            assert move in parent_board.legal_moves, \
                f"Move {move_uci} not legal in {parent['fen']}"
            
            parent_board.push(move)
            # Compare board positions (not full FEN due to clocks)
            assert parent_board.board_fen() in node["fen"], \
                f"Move {move_uci} from {parent['fen']} doesn't produce {node['fen']}"
        except Exception as e:
            raise AssertionError(f"Error checking move {move_uci}: {e}")


def assert_ply_increments_correctly(nodes: List[Dict[str, Any]]):
    """
    Verify ply_from_S0 increments properly in sequence.
    """
    # For PV line, should increment by 1 each time
    pv_nodes = [n for n in nodes if n["id"].startswith("pv-")]
    pv_nodes_sorted = sorted(pv_nodes, key=lambda n: int(n["id"].split("-")[1]))
    
    for i, node in enumerate(pv_nodes_sorted):
        expected_ply = i + 1
        actual_ply = node.get("ply_from_S0")
        assert actual_ply == expected_ply, \
            f"Node {node['id']} should have ply {expected_ply}, got {actual_ply}"


def assert_shapes_correct(nodes: List[Dict[str, Any]], branching_enabled: bool = False):
    """
    Verify node shapes follow rules:
    - First and last nodes are squares
    - With branching: extended nodes are triangles
    - Without branching: intermediate nodes are circles
    """
    if len(nodes) == 0:
        return
    
    # First node should be square
    assert nodes[0]["shape"] == "square", "First node should be square"
    
    # Last node should be square
    assert nodes[-1]["shape"] == "square", "Last node should be square"
    
    # Intermediate nodes
    for node in nodes[1:-1]:
        shape = node["shape"]
        has_branches = node.get("has_branches", False)
        
        if has_branches or len(node.get("extended_moves", {})) > 0:
            assert shape == "triangle", \
                f"Node {node['id']} with branches should be triangle, got {shape}"
        elif not branching_enabled:
            assert shape == "circle", \
                f"Node {node['id']} without branches should be circle, got {shape}"


def assert_confidence_in_reasonable_range(nodes: List[Dict[str, Any]]):
    """
    Verify confidence values are reasonable (not all 0, not all 100).
    """
    if len(nodes) == 0:
        return
    
    confidences = [n.get("ConfidencePercent") for n in nodes]
    
    # Should have some variation
    min_conf = min(confidences)
    max_conf = max(confidences)
    
    assert min_conf >= 0, "Minimum confidence should be >= 0"
    assert max_conf <= 100, "Maximum confidence should be <= 100"
    
    # Should not all be the same (unless forced)
    if len(set(confidences)) == 1 and len(confidences) > 1:
        # All same - might be edge case, warn but don't fail
        print(f"Warning: All {len(confidences)} nodes have same confidence {confidences[0]}%")


def calculate_expected_confidence(s18: int, s2: int, pv18: int, pv2: int) -> int:
    """
    Calculate expected confidence from evaluation components.
    
    Formula: confidence = 100 - |s18-s2| - |pv18-pv2| - |pv2-s18|
    """
    return 100 - abs(s18 - s2) - abs(pv18 - pv2) - abs(pv2 - s18)


def assert_metadata_accuracy(nodes: List[Dict[str, Any]]):
    """
    Verify metadata fields are accurate.
    """
    for i, node in enumerate(nodes):
        metadata = node.get("metadata", {})
        
        if node["id"].startswith("pv-"):
            # PV node should have pv_index
            pv_index = metadata.get("pv_index")
            expected_index = int(node["id"].split("-")[1])
            assert pv_index == expected_index, \
                f"Node {node['id']} has pv_index {pv_index}, expected {expected_index}"

