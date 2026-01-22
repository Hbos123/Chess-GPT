"use client";

import React, { Suspense, useState, useEffect, useRef } from 'react';
import { useSearchParams } from 'next/navigation';
import Board from '@/components/Board';
import { Chess } from 'chess.js';
import { getBackendBase } from '@/lib/backendBase';

function LiveBoardInner() {
  const searchParams = useSearchParams();
  const planId = searchParams.get('plan_id') || '';
  const sessionId = searchParams.get('session_id') || '';
  
  const [currentFEN, setCurrentFEN] = useState('rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1');
  const [currentPGN, setCurrentPGN] = useState('');
  const [moveCount, setMoveCount] = useState(0);
  const [branches, setBranches] = useState(0);
  const [currentMove, setCurrentMove] = useState<string | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const gameRef = useRef(new Chess());
  const eventSourceRef = useRef<EventSource | null>(null);
  
  useEffect(() => {
    if (!planId || !sessionId) {
      setError('Missing plan_id or session_id');
      return;
    }
    
    // Connect to SSE stream - use backend URL directly
    const BACKEND_BASE = getBackendBase();
    const eventSource = new EventSource(
      `${BACKEND_BASE}/live_board_stream?plan_id=${encodeURIComponent(planId)}&session_id=${encodeURIComponent(sessionId)}`
    );
    
    eventSourceRef.current = eventSource;
    
    eventSource.addEventListener('connected', (e) => {
      const data = JSON.parse(e.data);
      console.log('Connected to live board stream:', data);
      setIsConnected(true);
      setError(null);
    });
    
    eventSource.addEventListener('pgn_update', (e) => {
      const data = JSON.parse(e.data);
      console.log('PGN update:', data);
      
      if (data.pgn) {
        setCurrentPGN(data.pgn);
        setMoveCount(data.move_count || 0);
        setBranches(data.branches || 0);
        setCurrentMove(data.current_move || null);
        
        // Update board from PGN
        try {
          const newGame = new Chess();
          newGame.loadPgn(data.pgn);
          setCurrentFEN(newGame.fen());
          gameRef.current = newGame;
        } catch (err) {
          console.error('Error loading PGN:', err);
        }
      }
    });
    
    eventSource.addEventListener('board_state', (e) => {
      const data = JSON.parse(e.data);
      console.log('Board state update:', data);
      
      if (data.fen) {
        setCurrentFEN(data.fen);
        try {
          gameRef.current.load(data.fen);
        } catch (err) {
          console.error('Error loading FEN:', err);
        }
      }
      
      if (data.move_san) {
        setCurrentMove(data.move_san);
      }
    });
    
    eventSource.addEventListener('branch_added', (e) => {
      const data = JSON.parse(e.data);
      console.log('Branch added:', data);
      setBranches(prev => prev + 1);
    });
    
    eventSource.addEventListener('error', (e: MessageEvent) => {
      const data = JSON.parse(e.data);
      console.error('SSE error:', data);
      setError(data.message || 'Connection error');
      setIsConnected(false);
    });
    
    eventSource.onerror = (err) => {
      console.error('EventSource error:', err);
      setError('Connection lost');
      setIsConnected(false);
    };
    
    // Cleanup
    return () => {
      eventSource.close();
    };
  }, [planId, sessionId]);
  
  return (
    <div className="live-board-page">
      <div className="live-board-header">
        <h1>Live Board View</h1>
        <div className="live-board-status">
          <span className={`status-indicator ${isConnected ? 'connected' : 'disconnected'}`}>
            {isConnected ? '●' : '○'}
          </span>
          <span>{isConnected ? 'Connected' : 'Disconnected'}</span>
          {planId && <span className="plan-id">Plan: {planId.substring(0, 8)}...</span>}
        </div>
      </div>
      
      {error && (
        <div className="live-board-error">
          Error: {error}
        </div>
      )}
      
      <div className="live-board-content">
        <div className="live-board-left">
          <div className="live-board-stats">
            <div className="stat">
              <span className="stat-label">Moves:</span>
              <span className="stat-value">{moveCount}</span>
            </div>
            <div className="stat">
              <span className="stat-label">Branches:</span>
              <span className="stat-value">{branches}</span>
            </div>
            {currentMove && (
              <div className="stat">
                <span className="stat-label">Current:</span>
                <span className="stat-value">{currentMove}</span>
              </div>
            )}
          </div>
          
          <div className="live-board-container">
            <Board
              fen={currentFEN}
              onMove={() => {}} // Read-only
              disabled={true}
              orientation="white"
            />
          </div>
        </div>
        
        <div className="live-board-right">
          <div className="live-board-pgn-header">
            <h3>PGN (Live Updates)</h3>
          </div>
          <div className="live-board-pgn-viewer">
            {currentPGN ? (
              <pre>{currentPGN}</pre>
            ) : (
              <div className="live-board-pgn-empty">
                Waiting for PGN updates...
              </div>
            )}
          </div>
        </div>
      </div>
      
      <style jsx>{`
        .live-board-page {
          min-height: 100vh;
          background: #1a1a1a;
          color: rgba(255, 255, 255, 0.9);
          padding: 20px;
        }
        
        .live-board-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 20px;
          padding-bottom: 16px;
          border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .live-board-header h1 {
          margin: 0;
          font-size: 24px;
          color: rgba(255, 255, 255, 0.9);
        }
        
        .live-board-status {
          display: flex;
          align-items: center;
          gap: 12px;
          font-size: 14px;
        }
        
        .status-indicator {
          font-size: 12px;
        }
        
        .status-indicator.connected {
          color: rgba(76, 175, 80, 0.9);
        }
        
        .status-indicator.disconnected {
          color: rgba(244, 67, 54, 0.9);
        }
        
        .plan-id {
          font-size: 12px;
          color: rgba(255, 255, 255, 0.5);
          font-family: monospace;
        }
        
        .live-board-error {
          background: rgba(244, 67, 54, 0.2);
          border: 1px solid rgba(244, 67, 54, 0.4);
          border-radius: 4px;
          padding: 12px;
          margin-bottom: 20px;
          color: rgba(244, 67, 54, 0.9);
        }
        
        .live-board-content {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 20px;
        }
        
        .live-board-left {
          display: flex;
          flex-direction: column;
          gap: 16px;
        }
        
        .live-board-stats {
          display: flex;
          gap: 16px;
          padding: 12px;
          background: rgba(30, 30, 30, 0.6);
          border-radius: 8px;
        }
        
        .stat {
          display: flex;
          flex-direction: column;
          gap: 4px;
        }
        
        .stat-label {
          font-size: 11px;
          color: rgba(255, 255, 255, 0.5);
        }
        
        .stat-value {
          font-size: 16px;
          font-weight: 600;
          color: rgba(255, 255, 255, 0.9);
        }
        
        .live-board-container {
          background: rgba(30, 30, 30, 0.6);
          border-radius: 8px;
          padding: 16px;
        }
        
        .live-board-right {
          display: flex;
          flex-direction: column;
        }
        
        .live-board-pgn-header {
          margin-bottom: 12px;
        }
        
        .live-board-pgn-header h3 {
          margin: 0;
          font-size: 16px;
          color: rgba(255, 255, 255, 0.9);
        }
        
        .live-board-pgn-viewer {
          flex: 1;
          background: rgba(30, 30, 30, 0.6);
          border-radius: 8px;
          padding: 16px;
          overflow-y: auto;
          max-height: 600px;
        }
        
        .live-board-pgn-viewer pre {
          margin: 0;
          font-family: 'Courier New', monospace;
          font-size: 12px;
          color: rgba(255, 255, 255, 0.8);
          white-space: pre-wrap;
          word-wrap: break-word;
        }
        
        .live-board-pgn-empty {
          color: rgba(255, 255, 255, 0.4);
          font-style: italic;
          text-align: center;
          padding: 40px;
        }
        
        @media (max-width: 768px) {
          .live-board-content {
            grid-template-columns: 1fr;
          }
        }
      `}</style>
    </div>
  );
}

export default function LiveBoardPage() {
  // Next.js requires a Suspense boundary when using useSearchParams() in app router pages.
  return (
    <Suspense fallback={<div className="live-board-page">Loading…</div>}>
      <LiveBoardInner />
    </Suspense>
  );
}

