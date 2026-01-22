"""
Progress Manager for Personal Review System
Manages progress tracking and SSE streaming
"""

from typing import Dict, Any, Optional, AsyncGenerator
import asyncio
import time
from collections import defaultdict


class ProgressManager:
    """Manages progress tracking for long-running operations"""
    
    def __init__(self):
        """Initialize progress manager"""
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._subscribers: Dict[str, list] = defaultdict(list)  # session_id -> list of queues
    
    def create_session(self, session_id: str, total: int = 0, initial_message: str = "Starting...") -> None:
        """
        Create a new progress session.
        
        Args:
            session_id: Unique session identifier
            total: Total number of items to process
            initial_message: Initial progress message
        """
        self._sessions[session_id] = {
            "current": 0,
            "total": total,
            "message": initial_message,
            "percentage": 0.0,
            "created_at": time.time(),
            "updated_at": time.time()
        }
        print(f"   📊 Created progress session: {session_id} (total={total})")
        
        # Notify any existing subscribers about the new session
        self._notify_subscribers(session_id, self._sessions[session_id])
    
    def update_progress(
        self,
        session_id: str,
        current: int,
        total: Optional[int] = None,
        message: Optional[str] = None
    ) -> None:
        """
        Update progress for a session.
        
        Args:
            session_id: Session identifier
            current: Current progress count
            total: Optional total (updates if provided)
            message: Optional progress message
        """
        if session_id not in self._sessions:
            self.create_session(session_id, total or current * 2)
        
        session = self._sessions[session_id]
        session["current"] = current
        
        if total is not None:
            session["total"] = total
        
        if message is not None:
            session["message"] = message
        
        # Calculate percentage
        if session["total"] > 0:
            session["percentage"] = min(100.0, (current / session["total"]) * 100.0)
        else:
            session["percentage"] = 0.0
        
        session["updated_at"] = time.time()
        
        # Notify subscribers
        self._notify_subscribers(session_id, session)
    
    def get_progress(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get current progress for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Progress dictionary or None if session doesn't exist
        """
        return self._sessions.get(session_id)
    
    async def get_progress_stream(self, session_id: str) -> AsyncGenerator[str, None]:
        """
        Get SSE stream for progress updates.
        
        Args:
            session_id: Session identifier
            
        Yields:
            SSE-formatted progress update strings
        """
        queue = asyncio.Queue()
        self._subscribers[session_id].append(queue)
        print(f"   📡 SSE stream connected for session: {session_id} (subscribers: {len(self._subscribers[session_id])})")
        
        try:
            # Send initial progress if available
            if session_id in self._sessions:
                progress = self._sessions[session_id]
                print(f"   📤 Sending initial progress for session {session_id}: {progress['current']}/{progress['total']}")
                yield self._format_sse_event(progress)
            else:
                # Session doesn't exist yet, but we're subscribed
                # Send a waiting message
                print(f"   ⏳ Session {session_id} doesn't exist yet, sending waiting message")
                yield self._format_sse_event({
                    "current": 0,
                    "total": 0,
                    "message": "Waiting for analysis to start...",
                    "percentage": 0.0
                })
            
            # Stream updates
            while True:
                try:
                    # Wait for update with timeout
                    progress = await asyncio.wait_for(queue.get(), timeout=1.0)
                    
                    if progress is None:  # Sentinel value to stop
                        print(f"   🛑 Received stop signal for session {session_id}")
                        break
                    
                    print(f"   📤 Sending progress update for session {session_id}: {progress.get('current', 0)}/{progress.get('total', 0)}")
                    yield self._format_sse_event(progress)
                    
                except asyncio.TimeoutError:
                    # Send heartbeat to keep connection alive
                    yield ": heartbeat\n\n"
                    
                    # Check if session is complete
                    if session_id in self._sessions:
                        session = self._sessions[session_id]
                        if session["current"] >= session["total"] and session["total"] > 0:
                            # Session complete, wait a bit then close
                            print(f"   ✅ Session {session_id} complete, closing stream")
                            await asyncio.sleep(0.5)
                            break
                    # If session doesn't exist yet, keep waiting (don't break)
                    # This allows the stream to wait for the session to be created
        
        finally:
            # Clean up subscriber
            if session_id in self._subscribers:
                self._subscribers[session_id].remove(queue)
                if not self._subscribers[session_id]:
                    del self._subscribers[session_id]
            print(f"   🔌 SSE stream closed for session: {session_id}")
    
    def _notify_subscribers(self, session_id: str, progress: Dict[str, Any]) -> None:
        """Notify all subscribers of progress update"""
        if session_id in self._subscribers:
            subscriber_count = len(self._subscribers[session_id])
            print(f"   📤 Notifying {subscriber_count} subscriber(s) for session {session_id}: {progress.get('current', 0)}/{progress.get('total', 0)}")
            for queue in self._subscribers[session_id]:
                try:
                    queue.put_nowait(progress)
                except Exception as e:
                    print(f"   ⚠️ Error notifying subscriber: {e}")
        else:
            print(f"   ⚠️ No subscribers found for session {session_id} (this is normal if SSE hasn't connected yet)")
    
    def _format_sse_event(self, progress: Dict[str, Any]) -> str:
        """
        Format progress as SSE event.
        
        Args:
            progress: Progress dictionary
            
        Returns:
            SSE-formatted string
        """
        import json
        data = {
            "current": progress["current"],
            "total": progress["total"],
            "message": progress["message"],
            "percentage": progress["percentage"]
        }
        return f"data: {json.dumps(data)}\n\n"
    
    def complete_session(self, session_id: str, final_message: str = "Complete") -> None:
        """
        Mark session as complete.
        
        Args:
            session_id: Session identifier
            final_message: Final progress message
        """
        if session_id in self._sessions:
            session = self._sessions[session_id]
            session["current"] = session["total"]
            session["message"] = final_message
            session["percentage"] = 100.0
            session["updated_at"] = time.time()
            
            self._notify_subscribers(session_id, session)
            
            # Send sentinel to close streams
            if session_id in self._subscribers:
                for queue in self._subscribers[session_id]:
                    try:
                        queue.put_nowait(None)
                    except Exception:
                        pass
    
    def cleanup_old_sessions(self, max_age_seconds: int = 3600) -> int:
        """
        Clean up old sessions.
        
        Args:
            max_age_seconds: Maximum age in seconds
            
        Returns:
            Number of sessions removed
        """
        now = time.time()
        sessions_to_remove = []
        
        for session_id, session in self._sessions.items():
            age = now - session.get("updated_at", session.get("created_at", 0))
            if age > max_age_seconds:
                sessions_to_remove.append(session_id)
        
        for session_id in sessions_to_remove:
            del self._sessions[session_id]
            if session_id in self._subscribers:
                del self._subscribers[session_id]
        
        if sessions_to_remove:
            print(f"   🧹 Cleaned up {len(sessions_to_remove)} old progress sessions")
        
        return len(sessions_to_remove)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get progress manager statistics"""
        return {
            "active_sessions": len(self._sessions),
            "total_subscribers": sum(len(queues) for queues in self._subscribers.values())
        }

