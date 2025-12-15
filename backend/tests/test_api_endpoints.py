"""
Test suite for Chess GPT API endpoints.
Tests critical API functionality and error handling.
"""

import pytest
import httpx
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create test client for FastAPI app with lifespan."""
    from main import app
    # Use context manager to properly initialize lifespan
    with TestClient(app) as test_client:
        yield test_client


def test_meta_endpoint(client):
    """Test /meta endpoint returns correct metadata."""
    response = client.get("/meta")
    assert response.status_code == 200
    
    data = response.json()
    assert data["name"] == "Chess GPT"
    assert "version" in data
    assert "modes" in data


def test_engine_metrics(client):
    """Test /engine/metrics endpoint."""
    response = client.get("/engine/metrics")
    assert response.status_code == 200
    
    metrics = response.json()
    assert "total_requests" in metrics
    assert "failed_requests" in metrics
    assert "avg_wait_time_ms" in metrics
    assert "current_queue_size" in metrics
    assert metrics["processing"] is True


def test_analyze_position_valid(client):
    """Test /analyze_position with valid FEN."""
    params = {
        "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
        "depth": 12,
        "lines": 3
    }
    
    response = client.get("/analyze_position", params=params)
    assert response.status_code == 200
    
    data = response.json()
    assert "eval_cp" in data
    assert "candidate_moves" in data
    assert isinstance(data["candidate_moves"], list)


def test_analyze_position_invalid_fen(client):
    """Test /analyze_position with invalid FEN."""
    params = {
        "fen": "invalid_fen_string",
        "depth": 12,
        "lines": 3
    }
    
    response = client.get("/analyze_position", params=params)
    # Should handle gracefully, either 400 or return empty/neutral response
    assert response.status_code in [200, 400]


def test_play_move_valid(client):
    """Test /play_move with valid move."""
    payload = {
        "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        "user_move_san": "e4",
        "engine_elo": 1600,
        "time_ms": 1000
    }
    
    response = client.post("/play_move", json=payload)
    assert response.status_code == 200
    
    data = response.json()
    assert "engine_move_san" in data
    assert "commentary_points" in data
    assert "new_fen" in data


def test_play_move_invalid(client):
    """Test /play_move with illegal move."""
    payload = {
        "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        "user_move_san": "e5",  # Illegal for white (pawn can't move two squares from e2 to e5)
        "engine_elo": 1600,
        "time_ms": 1000
    }
    
    response = client.post("/play_move", json=payload)
    # Server may return 200 with legal:false or 400/422
    data = response.json()
    if response.status_code == 200:
        assert data.get("legal") == False
    else:
        assert response.status_code in [400, 422]


def test_confidence_raise_move(client):
    """Test /confidence/raise_move endpoint."""
    payload = {
        "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        "move_san": "Nf3",
        "target": 80
    }
    
    response = client.post("/confidence/raise_move", json=payload)
    assert response.status_code == 200
    
    data = response.json()
    # Response structure has confidence nested
    conf = data.get("confidence", data)
    assert "overall_confidence" in conf
    assert "line_confidence" in conf
    assert "nodes" in conf
    assert isinstance(conf["nodes"], list)


def test_confidence_raise_position(client):
    """Test /confidence/raise_position endpoint."""
    payload = {
        "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
        "target": 80
    }
    
    response = client.post("/confidence/raise_position", json=payload)
    assert response.status_code == 200
    
    data = response.json()
    assert "position_confidence" in data


def test_llm_chat_basic(client):
    """Test /llm_chat with basic message."""
    payload = {
        "messages": [{"role": "user", "content": "What is chess?"}],
        "context": {
            "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        },
        "use_tools": False
    }
    
    response = client.post("/llm_chat", json=payload)
    assert response.status_code == 200
    
    data = response.json()
    assert "content" in data
    assert isinstance(data["content"], str)
    assert len(data["content"]) > 0


def test_concurrent_requests(client):
    """Test that multiple simultaneous requests don't crash."""
    import concurrent.futures
    
    def make_request():
        params = {
            "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
            "depth": 10,
            "lines": 2
        }
        return client.get("/analyze_position", params=params)
    
    # Submit 5 concurrent requests
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(make_request) for _ in range(5)]
        results = [f.result() for f in futures]
    
    # All should succeed
    for response in results:
        assert response.status_code == 200


def test_vision_board_endpoint(client, monkeypatch):
    """Ensure /vision/board returns a placeholder FEN when vision model is unavailable."""
    monkeypatch.setenv("CG_FAKE_VISION", "1")
    from PIL import Image
    from io import BytesIO

    image = Image.new("RGB", (80, 80), (255, 255, 255))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)

    response = client.post(
        "/vision/board",
        files={"photo": ("board.png", buffer.read(), "image/png")},
        data={"preset": "digital", "orientation_hint": "white"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert "fen" in payload
    assert payload["fen"].count("/") == 7

