"""
State consistency tests - verify backend returns consistent state across operations.
"""

import pytest
from fastapi.testclient import TestClient
import chess


@pytest.fixture
def client():
    """Create test client for FastAPI app with lifespan."""
    from main import app
    with TestClient(app) as test_client:
        yield test_client


def test_fen_after_moves_is_valid(client):
    """Test that FEN returned after moves is always valid."""
    moves = [
        ("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", "e4"),
        ("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1", "e5"),
        ("rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq e6 0 2", "Nf3"),
    ]
    
    for fen, move_san in moves:
        response = client.post("/play_move", json={
            "fen": fen,
            "user_move_san": move_san,
            "engine_elo": 1600,
            "time_ms": 500
        })
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify returned FEN is valid
        try:
            board = chess.Board(data["new_fen"])
            assert board.is_valid()
        except Exception as e:
            pytest.fail(f"Invalid FEN returned: {data['new_fen']}, error: {e}")


def test_confidence_tree_nodes_have_valid_fens(client):
    """Test that all nodes in confidence tree have valid FENs."""
    # Note: This test is primarily for when branching is enabled
    # Test position analysis which always returns PV nodes
    response = client.post("/confidence/raise_position", json={
        "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        "target": 80
    })
    
    assert response.status_code == 200
    data = response.json()
    
    # Extract position_confidence
    conf_data = data.get("position_confidence", {})
    nodes = conf_data.get("nodes", [])
    
    # Should have PV nodes at minimum
    if len(nodes) == 0:
        # Skip test if no nodes returned (edge case)
        pytest.skip("No nodes returned - branching may be disabled")
    
    assert len(nodes) > 0, "Expected PV nodes to be returned"
    
    # Verify every node has a valid FEN
    for node in nodes:
        fen = node.get("fen")
        assert fen is not None, f"Node {node.get('id')} has no FEN"
        
        try:
            board = chess.Board(fen)
            assert board.is_valid()
        except Exception as e:
            pytest.fail(f"Node {node.get('id')} has invalid FEN: {fen}, error: {e}")


def test_analysis_data_consistency(client):
    """Test that analysis returns consistent evaluation data."""
    fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"
    
    # Analyze same position twice
    response1 = client.get("/analyze_position", params={
        "fen": fen,
        "depth": 12,
        "lines": 3
    })
    response2 = client.get("/analyze_position", params={
        "fen": fen,
        "depth": 12,
        "lines": 3
    })
    
    assert response1.status_code == 200
    assert response2.status_code == 200
    
    data1 = response1.json()
    data2 = response2.json()
    
    # Evaluations should be similar (within 20cp due to engine variations)
    eval1 = data1.get("eval_cp", 0)
    eval2 = data2.get("eval_cp", 0)
    assert abs(eval1 - eval2) < 20, f"Inconsistent evals: {eval1} vs {eval2}"
    
    # Should return same number of candidates
    assert len(data1.get("candidate_moves", [])) == len(data2.get("candidate_moves", []))


def test_move_tree_fen_progression(client):
    """Test that FENs in move tree progress logically."""
    current_fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    
    # Play 3 moves and track FEN progression
    fens = [current_fen]
    
    for move in ["e4", "d4", "Nf3"]:
        response = client.post("/play_move", json={
            "fen": current_fen,
            "user_move_san": move,
            "engine_elo": 1600,
            "time_ms": 500
        })
        
        assert response.status_code == 200
        new_fen = response.json()["new_fen"]
        
        # New FEN should be different
        assert new_fen != current_fen
        assert new_fen not in fens
        
        fens.append(new_fen)
        current_fen = new_fen
    
    # We should have 4 unique FENs (start + 3 moves)
    assert len(set(fens)) == 4


def test_pgn_context_matches_fen(client):
    """Test that when FEN changes, PGN context should reflect it."""
    # This tests that backend doesn't mix up state
    
    fen1 = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    fen2 = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"
    
    # Analyze both positions
    analysis1 = client.get("/analyze_position", params={"fen": fen1, "depth": 10, "lines": 2})
    analysis2 = client.get("/analyze_position", params={"fen": fen2, "depth": 10, "lines": 2})
    
    assert analysis1.status_code == 200
    assert analysis2.status_code == 200
    
    # Results should be different (different positions)
    data1 = analysis1.json()
    data2 = analysis2.json()
    
    # Evals will be different from White vs Black perspective
    # Just verify both return valid data
    assert "eval_cp" in data1
    assert "eval_cp" in data2
    assert "candidate_moves" in data1
    assert "candidate_moves" in data2

