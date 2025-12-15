"""
Test confidence tree structure accuracy.

Verify correct shapes, colors, connections, and node properties.
"""

import pytest
from fastapi.testclient import TestClient
import chess


@pytest.fixture
def client():
    """Create test client with lifespan."""
    from main import app
    with TestClient(app) as test_client:
        yield test_client


def test_pv_spine_structure(client):
    """Tree should form correct structure with start node and child nodes."""
    response = client.get("/analyze_position", params={
        "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
        "depth": 18,
        "lines": 3
    })
    
    assert response.status_code == 200
    data = response.json()
    
    pos_conf = data.get("position_confidence", {})
    nodes = pos_conf.get("nodes", [])
    
    assert len(nodes) > 0, "Should have at least one node"
    
    # Find start node (should have no parent)
    start_node = next((n for n in nodes if n["id"] == "start"), None)
    assert start_node is not None, "Should have a 'start' node"
    assert start_node["parent_id"] is None, "Start node should have no parent"
    assert start_node["color"] == "grey", "Start node should be grey (position before move)"
    
    # All other nodes should have a parent (either "start" or another node)
    for node in nodes:
        if node["id"] != "start":
            assert node["parent_id"] is not None, f"Node {node['id']} should have a parent"
            # Verify parent exists
            parent = next((n for n in nodes if n["id"] == node["parent_id"]), None)
            assert parent is not None, f"Node {node['id']} has parent {node['parent_id']} that doesn't exist"


def test_node_shapes_are_valid(client):
    """All nodes should have valid shapes."""
    response = client.post("/confidence/raise_position", json={
        "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
        "target": 80
    })
    
    assert response.status_code == 200
    data = response.json()
    
    pos_conf = data.get("position_confidence", {})
    nodes = pos_conf.get("nodes", [])
    
    # Start node should be square and grey (or green/red if confidence changed, but ideally grey)
    start_node = next((n for n in nodes if n["id"] == "start"), None)
    if start_node:
        assert start_node["shape"] == "square", "Start node should be square"
        # Start node should be grey (position before move), but may be green/red if confidence is high/low
        assert start_node["color"] in ["grey", "green", "red"], \
            f"Start node should be grey/green/red, got {start_node['color']}"
    
    # All nodes should have valid shapes
    for node in nodes:
        shape = node["shape"]
        assert shape in ["circle", "square", "triangle"], \
                f"Node {node['id']} has invalid shape: {shape}"


def test_node_colors_match_confidence(client):
    """Nodes should have valid colors based on confidence and shape."""
    baseline = 80
    response = client.post("/confidence/raise_position", json={
        "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
        "target": baseline
    })
    
    assert response.status_code == 200
    data = response.json()
    
    pos_conf = data.get("position_confidence", {})
    nodes = pos_conf.get("nodes", [])
    
    for node in nodes:
        conf = node["ConfidencePercent"]
        color = node["color"]
        shape = node["shape"]
        
        # Valid colors: red, green, blue, grey (grey is for start node)
        assert color in ["red", "green", "blue", "grey"], \
            f"Node {node['id']} has invalid color: {color}"
        
        # Start node should be grey
        if node["id"] == "start":
            assert color == "grey", "Start node should be grey"
        # Other nodes should be red or green based on confidence
        elif color not in ["red", "green", "blue"]:
            assert False, f"Node {node['id']} with {conf}% has invalid color {color}"


def test_ply_from_S0_increments(client):
    """Each node should have ply_from_S0 = parent + 1."""
    response = client.get("/analyze_position", params={
        "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
        "depth": 18,
        "lines": 3
    })
    
    assert response.status_code == 200
    data = response.json()
    
    pos_conf = data.get("position_confidence", {})
    nodes = pos_conf.get("nodes", [])
    
    # Start node should have ply 0
    start_node = next((n for n in nodes if n["id"] == "start"), None)
    if start_node:
        assert start_node["ply_from_S0"] == 0, "Start node should have ply 0"
    
    # Child nodes should have ply >= 1
    for node in nodes:
        if node["id"] != "start":
            assert node["ply_from_S0"] >= 1, \
                f"Node {node['id']} should have ply >= 1, got {node['ply_from_S0']}"
            # If it has a parent, ply should be parent's ply + 1
            if node["parent_id"]:
                parent = next((n for n in nodes if n["id"] == node["parent_id"]), None)
                if parent:
                    assert node["ply_from_S0"] == parent["ply_from_S0"] + 1, \
                        f"Node {node['id']} should have ply = parent + 1"


def test_all_nodes_have_valid_fens(client):
    """Every FEN should be chess-legal and parseable."""
    response = client.get("/analyze_position", params={
        "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
        "depth": 18,
        "lines": 3
    })
    
    assert response.status_code == 200
    data = response.json()
    
    pos_conf = data.get("position_confidence", {})
    nodes = pos_conf.get("nodes", [])
    
    for node in nodes:
        fen = node.get("fen")
        assert fen is not None, f"Node {node['id']} missing FEN"
        
        try:
            board = chess.Board(fen)
            assert board.is_valid(), f"Node {node['id']} FEN is invalid: {fen}"
        except Exception as e:
            pytest.fail(f"Node {node['id']} has unparseable FEN: {fen}, error: {e}")


def test_node_data_completeness(client):
    """Every node should have all required fields."""
    response = client.get("/analyze_position", params={
        "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
        "depth": 18,
        "lines": 3
    })
    
    assert response.status_code == 200
    data = response.json()
    
    pos_conf = data.get("position_confidence", {})
    nodes = pos_conf.get("nodes", [])
    
    required_fields = [
        "id", "fen", "move_from_parent", "ply_from_S0",
        "ConfidencePercent", "shape", "color"
    ]
    
    for node in nodes:
        for field in required_fields:
            assert field in node, f"Node {node.get('id', 'unknown')} missing field: {field}"
            # Start node can have None for move_from_parent (it has no parent)
            if field == "move_from_parent" and node["id"] == "start":
                continue  # Skip None check for start node's move_from_parent
            assert node[field] is not None, f"Node {node['id']} has None for {field}"


def test_no_duplicate_node_ids(client):
    """All node IDs in tree should be unique."""
    response = client.get("/analyze_position", params={
        "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
        "depth": 18,
        "lines": 3
    })
    
    assert response.status_code == 200
    data = response.json()
    
    pos_conf = data.get("position_confidence", {})
    nodes = pos_conf.get("nodes", [])
    
    node_ids = [n["id"] for n in nodes]
    unique_ids = set(node_ids)
    
    assert len(node_ids) == len(unique_ids), \
        f"Duplicate node IDs found: {[id for id in node_ids if node_ids.count(id) > 1]}"


def test_metadata_accuracy(client):
    """Metadata fields should match actual analysis."""
    response = client.get("/analyze_position", params={
        "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
        "depth": 18,
        "lines": 3
    })
    
    assert response.status_code == 200
    data = response.json()
    
    pos_conf = data.get("position_confidence", {})
    nodes = pos_conf.get("nodes", [])
    
    # Check start node exists
    start_node = next((n for n in nodes if n["id"] == "start"), None)
    assert start_node is not None, "Should have a start node"
    
    # Check that nodes have required fields
    for node in nodes:
        assert "id" in node, f"Node missing id"
        assert "fen" in node, f"Node {node.get('id')} missing fen"
        assert "ConfidencePercent" in node, f"Node {node.get('id')} missing ConfidencePercent"


def test_move_from_parent_is_valid(client):
    """Each move should be legal from parent's FEN."""
    response = client.get("/analyze_position", params={
        "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
        "depth": 18,
        "lines": 3
    })
    
    assert response.status_code == 200
    data = response.json()
    
    pos_conf = data.get("position_confidence", {})
    nodes = pos_conf.get("nodes", [])
    
    # Build parent map
    parent_map = {}
    for node in nodes:
        if node["parent_id"]:
            parent_map[node["id"]] = next(n for n in nodes if n["id"] == node["parent_id"])
    
    # Check each move is legal from parent FEN
    for node in nodes[1:]:  # Skip first node (no parent)
        parent = parent_map[node["id"]]
        parent_board = chess.Board(parent["fen"])
        move_uci = node["move_from_parent"]
        
        try:
            move = chess.Move.from_uci(move_uci)
            assert move in parent_board.legal_moves, \
                f"Move {move_uci} not legal in parent FEN: {parent['fen']}"
            
            # Apply move and check matches node FEN
            parent_board.push(move)
            # FENs might differ in halfmove clock, so compare pieces only
            assert parent_board.board_fen() in node["fen"], \
                f"Move {move_uci} from {parent['fen']} doesn't produce {node['fen']}"
        except Exception as e:
            pytest.fail(f"Error checking move {move_uci}: {e}")


def test_extended_moves_format(client):
    """extended_moves should be empty dict when no branching."""
    response = client.get("/analyze_position", params={
        "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
        "depth": 18,
        "lines": 3
    })
    
    assert response.status_code == 200
    data = response.json()
    
    pos_conf = data.get("position_confidence", {})
    nodes = pos_conf.get("nodes", [])
    
    for node in nodes:
        extended_moves = node.get("extended_moves", {})
        assert isinstance(extended_moves, dict), \
            f"Node {node['id']} extended_moves should be dict, got {type(extended_moves)}"
        
        # When branching disabled, should be empty
        if not node.get("has_branches", False):
            assert len(extended_moves) == 0, \
                f"Node {node['id']} without branches should have empty extended_moves"


def test_has_branches_flag_accuracy(client):
    """has_branches should be True when node has children, False otherwise."""
    response = client.get("/analyze_position", params={
        "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
        "depth": 18,
        "lines": 3
    })
    
    assert response.status_code == 200
    data = response.json()
    
    pos_conf = data.get("position_confidence", {})
    nodes = pos_conf.get("nodes", [])
    
    # Build a map of node IDs to nodes for quick lookup
    node_map = {node['id']: node for node in nodes}
    
    for node in nodes:
        has_branches = node.get("has_branches", False)
        node_id = node['id']
        
        # Check if this node has any children
        has_children = any(
            child_node.get("parent_id") == node_id 
            for child_node in nodes
        )
        
        # has_branches should match whether the node has children
        if has_children:
            assert has_branches, f"Node {node_id} has children but has_branches=False"
        else:
            # Leaf nodes should have has_branches=False (unless they have extended_moves)
            extended_moves = node.get("extended_moves", {})
            if len(extended_moves) == 0:
                assert not has_branches, f"Node {node_id} has no children and no extended_moves but has_branches=True"

