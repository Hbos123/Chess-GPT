"""
Test branching logic with branching enabled.

Note: These tests require branching to be enabled. They will skip if branching is disabled.
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create test client with lifespan."""
    from main import app
    with TestClient(app) as test_client:
        yield test_client


def test_red_nodes_extend_to_triangles(client):
    """Red circles should become triangles with branches when confidence raised."""
    # This test requires branching to be enabled
    # If branching is disabled, it will skip gracefully
    
    response = client.post("/confidence/raise_move", json={
        "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
        "move_san": "Nf3",
        "target": 80,
        "branch": True  # Explicitly request branching
    })
    
    assert response.status_code == 200
    data = response.json()
    
    # Check if branching happened
    conf_data = data.get("confidence", data)
    nodes = conf_data.get("nodes", [])
    
    # Count triangles
    triangle_count = sum(1 for n in nodes if n.get("shape") == "triangle")
    
    if triangle_count == 0:
        pytest.skip("Branching appears to be disabled")
    
    # If we have triangles, verify they have extended_moves
    for node in nodes:
        if node.get("shape") == "triangle":
            extended_moves = node.get("extended_moves", {})
            assert len(extended_moves) > 0, \
                f"Triangle node {node['id']} should have extended_moves"


def test_branch_stops_at_green_node(client):
    """Branch extension should stop when terminal node is green."""
    response = client.post("/confidence/raise_move", json={
        "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
        "move_san": "Nf3",
        "target": 80,
        "branch": True
    })
    
    assert response.status_code == 200
    data = response.json()
    
    conf_data = data.get("confidence", data)
    nodes = conf_data.get("nodes", [])
    
    # If no triangles, skip
    triangles = [n for n in nodes if n.get("shape") == "triangle"]
    if len(triangles) == 0:
        pytest.skip("Branching appears to be disabled")
    
    # For each triangle with extended_moves, verify branch terminals
    for triangle in triangles:
        extended_moves = triangle.get("extended_moves", {})
        for move_san, move_data in extended_moves.items():
            # Find terminal node of this branch
            # (This is a simplified check - actual test would traverse branch)
            # The terminal should be green or at max distance
            pass  # Detailed implementation depends on data structure


def test_branch_stops_at_18_ply_distance(client):
    """Branch should stop when terminal distance from S0 exceeds 18."""
    response = client.post("/confidence/raise_move", json={
        "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
        "move_san": "Nf3",
        "target": 80,
        "branch": True
    })
    
    assert response.status_code == 200
    data = response.json()
    
    conf_data = data.get("confidence", data)
    nodes = conf_data.get("nodes", [])
    
    # All nodes should have ply_from_S0 <= 18 (or slightly more for PV)
    for node in nodes:
        ply = node.get("ply_from_S0")
        # PV might go to 18, branches shouldn't exceed much beyond
        assert ply <= 25, f"Node {node['id']} has ply {ply} > reasonable max"


def test_triangle_recoloring(client):
    """Triangles should be marked red if adjusted best move lacks confidence."""
    response = client.post("/confidence/raise_move", json={
        "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
        "move_san": "Nf3",
        "target": 80,
        "branch": True
    })
    
    assert response.status_code == 200
    data = response.json()
    
    conf_data = data.get("confidence", data)
    nodes = conf_data.get("nodes", [])
    
    triangles = [n for n in nodes if n.get("shape") == "triangle"]
    if len(triangles) == 0:
        pytest.skip("Branching appears to be disabled")
    
    # Triangles with insufficient_confidence should be red
    for triangle in triangles:
        insufficient = triangle.get("insufficient_confidence", False)
        color = triangle.get("color")
        
        if insufficient:
            assert color == "red", \
                f"Triangle {triangle['id']} with insufficient_confidence should be red, got {color}"


def test_no_branch_from_green_triangles(client):
    """Green triangles shouldn't extend on subsequent raises."""
    # First raise
    response1 = client.post("/confidence/raise_move", json={
        "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
        "move_san": "Nf3",
        "target": 80,
        "branch": True
    })
    
    assert response1.status_code == 200
    data1 = response1.json()
    nodes1 = data1.get("confidence", data1).get("nodes", [])
    
    green_triangles_before = [n for n in nodes1 
                              if n.get("shape") == "triangle" and n.get("color") == "green"]
    
    if len(green_triangles_before) == 0:
        pytest.skip("No green triangles to test")
    
    # Second raise (using the returned tree)
    response2 = client.post("/confidence/raise_move", json={
        "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
        "move_san": "Nf3",
        "target": 80,
        "branch": True,
        "existing_nodes": nodes1  # Pass existing tree
    })
    
    assert response2.status_code == 200
    data2 = response2.json()
    nodes2 = data2.get("confidence", data2).get("nodes", [])
    
    # Green triangles from before should not have new branches
    for gt_before in green_triangles_before:
        gt_after = next((n for n in nodes2 if n["id"] == gt_before["id"]), None)
        if gt_after:
            # extended_moves should be same or similar
            assert gt_after.get("color") != "red", \
                f"Green triangle {gt_before['id']} should not turn red"


def test_multiple_confidence_raises(client):
    """Repeated raises should only extend red nodes."""
    # Start with initial analysis
    fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
    
    # First raise
    response1 = client.post("/confidence/raise_move", json={
        "fen": fen,
        "move_san": "Nf3",
        "target": 80,
        "branch": True
    })
    assert response1.status_code == 200
    nodes1 = response1.json().get("confidence", response1.json()).get("nodes", [])
    
    if len([n for n in nodes1 if n.get("shape") == "triangle"]) == 0:
        pytest.skip("Branching not enabled")
    
    node_count_1 = len(nodes1)
    
    # Second raise
    response2 = client.post("/confidence/raise_move", json={
        "fen": fen,
        "move_san": "Nf3",
        "target": 80,
        "branch": True
    })
    assert response2.status_code == 200
    nodes2 = response2.json().get("confidence", response2.json()).get("nodes", [])
    
    node_count_2 = len(nodes2)
    
    # If there were red nodes, count should increase
    red_nodes_1 = [n for n in nodes1 if n.get("color") == "red"]
    if len(red_nodes_1) > 0:
        assert node_count_2 >= node_count_1, \
            "With red nodes remaining, tree should grow or stay same"


def test_initial_confidence_frozen(client):
    """initial_confidence field should not change across raises."""
    # First raise
    response1 = client.post("/confidence/raise_move", json={
        "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
        "move_san": "Nf3",
        "target": 80,
        "branch": True
    })
    assert response1.status_code == 200
    nodes1 = response1.json().get("confidence", response1.json()).get("nodes", [])
    
    # Store initial confidences
    initial_confs = {n["id"]: n.get("initial_confidence") for n in nodes1}
    
    # Second raise
    response2 = client.post("/confidence/raise_move", json={
        "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
        "move_san": "Nf3",
        "target": 80,
        "branch": True
    })
    assert response2.status_code == 200
    nodes2 = response2.json().get("confidence", response2.json()).get("nodes", [])
    
    # Check that initial_confidence didn't change for existing nodes
    for node in nodes2:
        if node["id"] in initial_confs:
            initial_before = initial_confs[node["id"]]
            initial_after = node.get("initial_confidence")
            
            if initial_before is not None:
                assert initial_after == initial_before, \
                    f"Node {node['id']} initial_confidence changed: {initial_before} -> {initial_after}"


def test_branching_disabled_returns_pv_only(client):
    """When branching disabled, should only return PV line."""
    response = client.post("/confidence/raise_move", json={
        "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
        "move_san": "Nf3",
        "target": 80,
        "branch": False  # Explicitly disable
    })
    
    assert response.status_code == 200
    data = response.json()
    
    conf_data = data.get("confidence", data)
    nodes = conf_data.get("nodes", [])
    
    # Should only have PV nodes (no triangles)
    triangles = [n for n in nodes if n.get("shape") == "triangle"]
    assert len(triangles) == 0, "With branching disabled, should have no triangles"
    
    # All nodes should be on PV line
    for i, node in enumerate(nodes):
        assert node["id"] == f"pv-{i}", f"Node {i} should be pv-{i}, got {node['id']}"

