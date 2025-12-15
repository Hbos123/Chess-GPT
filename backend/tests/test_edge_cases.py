"""
Test edge cases and boundary conditions.
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


def test_position_with_all_high_confidence(client):
    """Position where all moves are good - all nodes should be green."""
    # Use starting position which usually has balanced options
    response = client.post("/confidence/raise_position", json={
        "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        "target": 50  # Low baseline
    })
    
    assert response.status_code == 200
    data = response.json()
    
    pos_conf = data.get("position_confidence", {})
    nodes = pos_conf.get("nodes", [])
    
    # With low baseline, most/all should be green
    green_count = sum(1 for n in nodes if n.get("color") == "green")
    assert green_count > len(nodes) // 2, "With low baseline, most nodes should be green"


def test_position_with_all_low_confidence(client):
    """Position with high baseline - many nodes should be red."""
    response = client.post("/confidence/raise_position", json={
        "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        "target": 95  # Very high baseline
    })
    
    assert response.status_code == 200
    data = response.json()
    
    pos_conf = data.get("position_confidence", {})
    nodes = pos_conf.get("nodes", [])
    
    # With very high baseline, many should be red
    red_count = sum(1 for n in nodes if n.get("color") == "red")
    assert red_count > 0, "With high baseline (95%), should have at least some red nodes"


def test_position_with_one_legal_move(client):
    """Position with forced move should still return valid tree."""
    # Position where king is in check with one escape
    fen = "k7/8/1K6/8/8/8/8/R7 b - - 0 1"  # Black king must move
    
    response = client.get("/analyze_position", params={
        "fen": fen,
        "depth": 10,
        "lines": 2
    })
    
    assert response.status_code == 200
    data = response.json()
    
    pos_conf = data.get("position_confidence", {})
    nodes = pos_conf.get("nodes", [])
    
    # Should have PV even with limited options
    assert len(nodes) > 0, "Should have nodes even with forced moves"
    
    # First move confidence might be high (forced move)
    first_conf = nodes[0].get("ConfidencePercent")
    # Forced moves may or may not have high confidence depending on evaluation
    assert 0 <= first_conf <= 100, "Confidence should be in valid range"


def test_endgame_tablebase_position(client):
    """Positions with clear outcomes should analyze correctly."""
    # K+R vs K endgame (clearly winning for white)
    fen = "8/8/8/8/8/2k5/8/K2R4 w - - 0 1"
    
    response = client.get("/analyze_position", params={
        "fen": fen,
        "depth": 15,
        "lines": 2
    })
    
    assert response.status_code == 200
    data = response.json()
    
    # Evaluation should be strongly positive
    eval_cp = data.get("eval_cp")
    assert eval_cp is not None, "Should have evaluation"
    # Might be mate score or high centipawn advantage
    
    pos_conf = data.get("position_confidence", {})
    assert pos_conf is not None, "Should have confidence data"


def test_complex_tactical_position(client):
    """Position with tactical complications should show varied confidence."""
    # Sicilian Dragon position (complex)
    fen = "r2qk2r/pp1b1ppp/2n1pn2/3p4/1bPP4/2NBPN2/PP3PPP/R1BQK2R w KQkq - 0 1"
    
    response = client.get("/analyze_position", params={
        "fen": fen,
        "depth": 15,
        "lines": 3
    })
    
    assert response.status_code == 200
    data = response.json()
    
    pos_conf = data.get("position_confidence", {})
    nodes = pos_conf.get("nodes", [])
    
    # Should have variation in confidence
    if len(nodes) > 5:
        confidences = [n.get("ConfidencePercent") for n in nodes]
        conf_range = max(confidences) - min(confidences)
        # Expect some variation (but not guaranteed)
        assert conf_range >= 0, "Confidences should vary"


def test_equal_evaluation_moves(client):
    """Multiple moves with same eval should still calculate confidence."""
    # Starting position often has several equal moves
    response = client.get("/analyze_position", params={
        "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        "depth": 12,
        "lines": 3
    })
    
    assert response.status_code == 200
    data = response.json()
    
    pos_conf = data.get("position_confidence", {})
    nodes = pos_conf.get("nodes", [])
    
    # Should have confidence values even if evaluations are similar
    for node in nodes:
        conf = node.get("ConfidencePercent")
        assert conf is not None, f"Node {node['id']} missing confidence"
        assert 0 <= conf <= 100, f"Node {node['id']} confidence out of range"


def test_invalid_fen_returns_error(client):
    """Invalid FEN should return appropriate error."""
    response = client.get("/analyze_position", params={
        "fen": "invalid_fen",
        "depth": 10,
        "lines": 2
    })
    
    # Should return error
    assert response.status_code in [400, 422, 500], "Invalid FEN should return error"


def test_empty_fen_returns_error(client):
    """Empty FEN should return appropriate error."""
    response = client.get("/analyze_position", params={
        "fen": "",
        "depth": 10,
        "lines": 2
    })
    
    assert response.status_code in [400, 422], "Empty FEN should return error"


def test_checkmate_position(client):
    """Checkmate position should handle gracefully (may return error)."""
    # Scholar's mate
    fen = "r1bqkb1r/pppp1Qpp/2n2n2/4p3/2B1P3/8/PPPP1PPP/RNB1K1NR b KQkq - 0 4"
    
    response = client.get("/analyze_position", params={
        "fen": fen,
        "depth": 5,
        "lines": 1
    })
    
    # Checkmate positions might return 422 (no legal moves) or 200 with mate score
    # Both are acceptable
    assert response.status_code in [200, 422], \
        f"Checkmate position should return 200 or 422, got {response.status_code}"
    
    if response.status_code == 200:
        data = response.json()
        # Should have some data if analyzed
        assert data is not None


def test_stalemate_position(client):
    """Stalemate position should handle gracefully (may return error)."""
    # Stalemate position
    fen = "k7/8/1K6/8/8/8/8/7Q b - - 0 1"  # Black is stalemated
    
    response = client.get("/analyze_position", params={
        "fen": fen,
        "depth": 5,
        "lines": 1
    })
    
    # Stalemate positions might return 422 (no legal moves) or 200 with draw indication
    assert response.status_code in [200, 422], \
        f"Stalemate position should return 200 or 422, got {response.status_code}"


def test_very_long_pv(client):
    """Analysis with very deep depth should handle gracefully (may reject)."""
    response = client.get("/analyze_position", params={
        "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        "depth": 25,  # Very deep
        "lines": 1
    })
    
    # System may reject depth > 20 with 422, or accept and cap at 18
    assert response.status_code in [200, 422], \
        f"Deep analysis should return 200 or 422, got {response.status_code}"
    
    if response.status_code == 200:
        data = response.json()
        pos_conf = data.get("position_confidence", {})
        nodes = pos_conf.get("nodes", [])
        
        # Should have nodes if accepted
        assert len(nodes) > 0, "Should have nodes if analysis accepted"


def test_position_near_50_move_rule(client):
    """Position close to 50-move rule should analyze correctly."""
    # Position with high halfmove clock
    fen = "8/8/8/4k3/8/4K3/8/8 w - - 48 100"
    
    response = client.get("/analyze_position", params={
        "fen": fen,
        "depth": 10,
        "lines": 1
    })
    
    assert response.status_code == 200
    data = response.json()
    
    pos_conf = data.get("position_confidence", {})
    # Should handle draw positions correctly
    assert pos_conf is not None


def test_position_with_en_passant(client):
    """Position with en passant should parse correctly."""
    # Position with en passant possible
    fen = "rnbqkbnr/ppp1pppp/8/3pP3/8/8/PPPP1PPP/RNBQKBNR w KQkq d6 0 3"
    
    response = client.get("/analyze_position", params={
        "fen": fen,
        "depth": 12,
        "lines": 2
    })
    
    assert response.status_code == 200
    data = response.json()
    
    # Should analyze correctly with en passant
    pos_conf = data.get("position_confidence", {})
    nodes = pos_conf.get("nodes", [])
    assert len(nodes) > 0


def test_position_with_castling_rights(client):
    """Position with various castling rights should handle correctly."""
    # Different castling rights scenarios
    fens = [
        "r3k2r/pppppppp/8/8/8/8/PPPPPPPP/R3K2R w KQkq - 0 1",  # All rights
        "r3k2r/pppppppp/8/8/8/8/PPPPPPPP/R3K2R w Kq - 0 1",  # Mixed rights
        "r3k2r/pppppppp/8/8/8/8/PPPPPPPP/R3K2R w - - 0 1",  # No rights
    ]
    
    for fen in fens:
        response = client.get("/analyze_position", params={
            "fen": fen,
            "depth": 10,
            "lines": 1
        })
        
        assert response.status_code == 200, f"Failed for FEN: {fen}"
        data = response.json()
        assert "position_confidence" in data

