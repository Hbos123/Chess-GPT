"use client";

import React, { useState } from 'react';
import LiveBoardView from './LiveBoardView';

interface ThinkingStageProps {
  phase: string;
  message: string;
  plan_id?: string;
  step_number?: number;
  onOpenLiveBoard?: () => void;
  isComplete?: boolean;
  thinkingTimeSeconds?: number;
}

export default function ThinkingStage({
  phase,
  message,
  plan_id,
  step_number,
  onOpenLiveBoard,
  isComplete = false,
  thinkingTimeSeconds
}: ThinkingStageProps) {
  const [showLiveBoard, setShowLiveBoard] = useState(false);
  const [isCollapsed, setIsCollapsed] = useState(isComplete); // Auto-collapse when complete
  
  const handleToggleLiveBoard = () => {
    if (onOpenLiveBoard) {
      onOpenLiveBoard();
    } else {
      setShowLiveBoard(!showLiveBoard);
    }
  };
  
  return (
    <>
      <div className="thinking-stage">
        <div className="thinking-stage-header">
          <button 
            className="thinking-stage-toggle"
            onClick={() => setIsCollapsed(!isCollapsed)}
            style={{ 
              background: 'transparent', 
              border: 'none', 
              color: 'rgba(255, 255, 255, 0.7)',
              cursor: 'pointer',
              fontSize: '12px',
              padding: '0 4px'
            }}
          >
            {isCollapsed ? '▶' : '▼'}
          </button>
          <span className="thinking-stage-title">
            {isComplete && thinkingTimeSeconds 
              ? `Thought for ${thinkingTimeSeconds}s` 
              : 'Thinking...'}
          </span>
        </div>
        
        {!isCollapsed && (
          <>
            <div className="thinking-stage-content">
              {!isComplete && <div className="thinking-stage-spinner" />}
              <span className="thinking-stage-message">{message}</span>
            </div>
            
            {plan_id && (
              <button 
                className="thinking-stage-button"
                onClick={handleToggleLiveBoard}
              >
                {showLiveBoard ? 'Hide' : 'Show'} Live Board View
              </button>
            )}
          </>
        )}
      
      <style jsx>{`
        .thinking-stage {
          display: flex;
          flex-direction: column;
          gap: 12px;
          padding: 12px;
          background: rgba(30, 30, 30, 0.6);
          border: 1px solid rgba(33, 150, 243, 0.3);
          border-radius: 8px;
          margin: 8px 0;
        }
        
        .thinking-stage-header {
          display: flex;
          align-items: center;
          gap: 8px;
        }
        
        .thinking-stage-title {
          font-size: 12px;
          color: rgba(255, 255, 255, 0.7);
          font-weight: 500;
        }
        
        .thinking-stage-content {
          display: flex;
          align-items: center;
          gap: 12px;
        }
        
        .thinking-stage-spinner {
          width: 16px;
          height: 16px;
          border: 2px solid rgba(33, 150, 243, 0.3);
          border-top-color: rgba(33, 150, 243, 0.9);
          border-radius: 50%;
          animation: spin 0.8s linear infinite;
        }
        
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
        
        .thinking-stage-message {
          color: rgba(150, 180, 255, 0.9);
          font-size: 14px;
        }
        
        .thinking-stage-button {
          padding: 6px 16px;
          font-size: 12px;
          color: rgba(255, 255, 255, 0.9);
          background: rgba(33, 150, 243, 0.2);
          border: 1px solid rgba(33, 150, 243, 0.4);
          border-radius: 4px;
          cursor: pointer;
          transition: all 0.15s ease;
        }
        
        .thinking-stage-button:hover {
          background: rgba(33, 150, 243, 0.3);
          border-color: rgba(33, 150, 243, 0.6);
        }
        
        .thinking-stage-button:active {
          transform: scale(0.98);
        }
      `}</style>
      </div>
      
      {showLiveBoard && plan_id && (
        <LiveBoardView
          planId={plan_id}
          sessionId={plan_id}
          onClose={() => setShowLiveBoard(false)}
        />
      )}
    </>
  );
}

