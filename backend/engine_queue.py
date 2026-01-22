"""
Stockfish Request Queue Manager

Serializes all Stockfish engine requests to prevent concurrent access crashes.
Provides health monitoring and auto-recovery capabilities.
"""

import asyncio
import time
from typing import Optional, Callable, Any, Dict
import chess.engine


class StockfishQueue:
    """
    Queue manager for Stockfish engine requests.
    Ensures all engine operations are executed sequentially to prevent crashes.
    """
    
    def __init__(self, engine: chess.engine.SimpleEngine):
        self.engine = engine
        self.queue: asyncio.Queue = asyncio.Queue()
        self.processing = False
        self.metrics = {
            'total_requests': 0,
            'failed_requests': 0,
            'total_wait_time': 0.0,
            'max_queue_depth': 0
        }
        
    async def start_processing(self):
        """
        Process queued requests one at a time.
        Runs continuously in background task.
        """
        self.processing = True
        print("🔄 Stockfish queue processor started")
        
        while self.processing:
            try:
                # Use get_nowait with timeout to allow checking self.processing
                try:
                    request = await asyncio.wait_for(self.queue.get(), timeout=0.1)
                except asyncio.TimeoutError:
                    # No request available, check if we should continue
                    continue
                
                # Update metrics
                self.metrics['total_requests'] += 1
                wait_time = time.time() - request['enqueue_time']
                self.metrics['total_wait_time'] += wait_time
                
                # Execute the request
                try:
                    result = await request['fn'](*request['args'], **request['kwargs'])
                    # Only set result if future is not already done (cancelled or completed)
                    if not request['future'].done():
                        request['future'].set_result(result)
                except asyncio.CancelledError:
                    # Request was cancelled, cancel the future if not done
                    if not request['future'].done():
                        request['future'].cancel()
                    # Don't break here, continue processing other requests
                except Exception as e:
                    self.metrics['failed_requests'] += 1
                    # Only set exception if future is not already done
                    if not request['future'].done():
                        request['future'].set_exception(e)
                    print(f"❌ Engine request failed: {e}")
                finally:
                    self.queue.task_done()
                    
            except asyncio.CancelledError:
                print("🛑 Queue processor cancelled")
                # Cancel any pending request's future
                try:
                    request = self.queue.get_nowait()
                    if not request['future'].done():
                        request['future'].cancel()
                    self.queue.task_done()
                except:
                    pass
                break
            except Exception as e:
                print(f"❌ Queue processor error: {e}")
                # Continue processing despite errors
    
    async def enqueue(self, fn: Callable, *args, **kwargs) -> Any:
        """
        Add a request to the queue and wait for its result.
        
        Args:
            fn: The engine method to call
            *args: Positional arguments for the method
            **kwargs: Keyword arguments for the method. Can include 'timeout' to set max wait time.
            
        Returns:
            The result of the engine call
            
        Raises:
            asyncio.TimeoutError: If the request times out
        """
        # Extract timeout from kwargs (if provided) before passing to engine function
        timeout = kwargs.pop('timeout', 120.0)  # Default 120 seconds
        
        future = asyncio.Future()
        current_depth = self.queue.qsize()
        
        # Track max queue depth
        if current_depth > self.metrics['max_queue_depth']:
            self.metrics['max_queue_depth'] = current_depth
        
        await self.queue.put({
            'fn': fn,
            'args': args,
            'kwargs': kwargs,  # kwargs no longer contains 'timeout'
            'future': future,
            'enqueue_time': time.time()
        })
        
        # Wait for result with timeout
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            # Cancel the future if it's still pending
            if not future.done():
                future.cancel()
            print(f"   ⚠️ [ENGINE_QUEUE] Request timed out after {timeout}s")
            raise
    
    async def health_check(self) -> bool:
        """
        Check if the engine is responsive.
        
        Returns:
            True if engine responds within timeout, False otherwise
        """
        try:
            board = chess.Board()
            await asyncio.wait_for(
                self.enqueue(self.engine.analyse, board, chess.engine.Limit(depth=1)),
                timeout=5.0
            )
            return True
        except asyncio.TimeoutError:
            print("⚠️  Engine health check timeout")
            return False
        except Exception as e:
            print(f"⚠️  Engine health check failed: {e}")
            return False
    
    async def auto_restart_engine(self):
        """
        Attempt to restart the engine after a crash.
        """
        print("⚠️  Engine unhealthy, attempting restart...")
        # This will be called by main.py's initialize_engine
        from main import initialize_engine
        success = await initialize_engine()
        if success:
            print("✅ Engine successfully restarted")
        else:
            print("❌ Engine restart failed")
        return success
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get queue performance metrics.
        
        Returns:
            Dictionary of metrics
        """
        avg_wait = 0.0
        if self.metrics['total_requests'] > 0:
            avg_wait = self.metrics['total_wait_time'] / self.metrics['total_requests']
        
        return {
            'total_requests': self.metrics['total_requests'],
            'failed_requests': self.metrics['failed_requests'],
            'avg_wait_time_ms': round(avg_wait * 1000, 2),
            'max_queue_depth': self.metrics['max_queue_depth'],
            'current_queue_size': self.queue.qsize(),
            'processing': self.processing
        }
    
    def stop(self):
        """Stop processing the queue."""
        self.processing = False
    
    async def cancel_all_pending(self):
        """Cancel all pending requests in the queue."""
        cancelled_count = 0
        while not self.queue.empty():
            try:
                request = self.queue.get_nowait()
                if not request['future'].done():
                    request['future'].cancel()
                    cancelled_count += 1
                self.queue.task_done()
            except asyncio.QueueEmpty:
                break
        if cancelled_count > 0:
            print(f"🛑 Cancelled {cancelled_count} pending engine requests")

