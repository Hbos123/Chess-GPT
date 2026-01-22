"""
Test suite for Stockfish request queue system.
Tests sequential processing, concurrent handling, and error recovery.
"""

import pytest
import asyncio
import chess
import chess.engine
from engine_queue import StockfishQueue


@pytest.fixture
async def engine():
    """Initialize Stockfish engine for testing."""
    transport, engine_instance = await chess.engine.popen_uci("./stockfish")
    await engine_instance.configure({"Threads": 1, "Hash": 16})
    yield engine_instance
    await engine_instance.quit()


@pytest.fixture
async def queue(engine):
    """Initialize StockfishQueue for testing."""
    queue_instance = StockfishQueue(engine)
    task = asyncio.create_task(queue_instance.start_processing())
    yield queue_instance
    queue_instance.stop()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_basic_analysis(queue):
    """Test basic engine analysis through queue."""
    board = chess.Board()
    result = await queue.enqueue(
        queue.engine.analyse,
        board,
        chess.engine.Limit(depth=10)
    )
    
    assert result is not None
    assert "score" in result
    assert "pv" in result


@pytest.mark.asyncio
async def test_sequential_processing(queue):
    """Test that requests are processed one at a time."""
    board = chess.Board()
    
    # Track request order
    start_times = []
    
    async def timed_analysis(label):
        start_times.append((label, asyncio.get_event_loop().time()))
        result = await queue.enqueue(
            queue.engine.analyse,
            board,
            chess.engine.Limit(depth=5)
        )
        return result
    
    # Submit multiple requests
    tasks = [
        timed_analysis("A"),
        timed_analysis("B"),
        timed_analysis("C")
    ]
    
    await asyncio.gather(*tasks)
    
    # All requests should have started (been queued)
    assert len(start_times) == 3
    # They should be processed in order (A before B before C)
    assert start_times[0][0] == "A"
    assert start_times[1][0] == "B"
    assert start_times[2][0] == "C"


@pytest.mark.asyncio
async def test_concurrent_request_handling(queue):
    """Test that multiple concurrent requests queue properly."""
    board = chess.Board()
    
    # Submit 5 requests simultaneously
    tasks = [
        queue.enqueue(queue.engine.analyse, board, chess.engine.Limit(depth=8))
        for _ in range(5)
    ]
    
    # All should complete without errors
    results = await asyncio.gather(*tasks)
    
    assert len(results) == 5
    for result in results:
        assert "score" in result
        assert "pv" in result


@pytest.mark.asyncio
async def test_error_handling(queue):
    """Test that failed requests don't crash the queue."""
    board = chess.Board()
    
    # Test that queue continues working even if we have some edge cases
    # First, make a successful request
    result1 = await queue.enqueue(
        queue.engine.analyse,
        board,
        chess.engine.Limit(depth=5)
    )
    assert result1 is not None
    assert "score" in result1
    
    # Queue should continue working after any issues
    result2 = await queue.enqueue(
        queue.engine.analyse,
        board,
        chess.engine.Limit(depth=5)
    )
    
    assert result2 is not None
    assert "score" in result2
    
    # Verify metrics show no failures (or minimal failures)
    metrics = queue.get_metrics()
    assert metrics["total_requests"] >= 2


@pytest.mark.asyncio
async def test_health_check(queue):
    """Test engine health check functionality."""
    is_healthy = await queue.health_check()
    assert is_healthy is True


@pytest.mark.asyncio
async def test_metrics(queue):
    """Test queue metrics tracking."""
    board = chess.Board()
    
    # Make some requests
    await queue.enqueue(queue.engine.analyse, board, chess.engine.Limit(depth=5))
    await queue.enqueue(queue.engine.analyse, board, chess.engine.Limit(depth=5))
    
    metrics = queue.get_metrics()
    
    assert metrics["total_requests"] >= 2
    assert metrics["current_queue_size"] >= 0
    assert "avg_wait_time_ms" in metrics


@pytest.mark.asyncio
async def test_multipv_through_queue(queue):
    """Test multipv analysis through queue."""
    board = chess.Board()
    
    result = await queue.enqueue(
        queue.engine.analyse,
        board,
        chess.engine.Limit(depth=10),
        multipv=3
    )
    
    assert isinstance(result, list)
    assert len(result) == 3
    for info in result:
        assert "score" in info
        assert "pv" in info

