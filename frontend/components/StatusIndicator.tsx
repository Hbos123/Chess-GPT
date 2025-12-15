"use client";

import React from 'react';

interface StatusMessage {
  phase: string;
  message: string;
  tool?: string;
  progress?: number;
  timestamp: number;
  pass_number?: number;  // For multi-pass interpreter
  instant?: boolean;  // Skip animation for rapid updates (prevents flashing)
}

interface StatusIndicatorProps {
  messages: StatusMessage[];
  isComplete: boolean;
  isVisible: boolean;
  onCancel?: () => void;  // Optional cancel callback
}

// Phase icons (text-based to avoid emoji issues)
const getPhaseIndicator = (phase: string): string => {
  switch (phase) {
    case 'interpreting': return 'i';
    case 'thinking': return 't';
    case 'planning': return 'p';
    case 'executing': return 'x';
    case 'ready': return 'r';
    case 'complete': return 'c';
    default: return '*';
  }
};

export function StatusIndicator({ messages, isComplete, isVisible, onCancel }: StatusIndicatorProps) {
  if (!isVisible || messages.length === 0) {
    return null;
  }
  
  // Show cancel button for operations that take > 3 seconds
  const firstTimestamp = messages[0]?.timestamp || Date.now() / 1000;
  const elapsedSeconds = (Date.now() / 1000) - firstTimestamp;
  const showCancel = !isComplete && onCancel && elapsedSeconds > 3;
  
  // Deduplicate and show only meaningful messages
  const uniqueMessages = messages.reduce((acc: StatusMessage[], msg) => {
    // Skip duplicate messages
    if (acc.some(m => m.message === msg.message && m.phase === msg.phase)) {
      return acc;
    }
    return [...acc, msg];
  }, []);
  
  // Extract pass info from messages
  const passMatch = uniqueMessages.find(m => m.message.includes('Pass '));
  const currentPass = passMatch 
    ? parseInt(passMatch.message.match(/Pass (\d+)/)?.[1] || '0') 
    : null;
  const maxPasses = passMatch 
    ? parseInt(passMatch.message.match(/\/(\d+)/)?.[1] || '5') 
    : null;
  
  return (
    <div className="status-notifications">
      {/* Multi-pass progress bar if applicable */}
      {currentPass && maxPasses && (
        <div className="pass-progress">
          <div className="pass-label">Pass {currentPass}/{maxPasses}</div>
          <div className="pass-bar">
            <div 
              className="pass-fill" 
              style={{ width: `${(currentPass / maxPasses) * 100}%` }}
            />
          </div>
        </div>
      )}
      
      {/* Status messages */}
      {uniqueMessages.map((msg, idx) => {
        const isLatest = idx === uniqueMessages.length - 1;
        const phaseClass = `phase-${msg.phase}`;
        
        // Format message - clean up pass info if it's redundant with progress bar
        let displayMessage = msg.message;
        if (currentPass && displayMessage.includes('Pass ')) {
          displayMessage = displayMessage.replace(/Pass \d+\/\d+\.\.\.?/, '').trim() || displayMessage;
        }
        
        // Don't show empty messages
        if (!displayMessage) return null;
        
        return (
          <div 
            key={`${msg.timestamp}-${idx}`} 
            className={`status-line ${isLatest ? 'latest' : ''} ${phaseClass} ${msg.instant ? 'no-animate' : ''}`}
          >
            {isLatest && !isComplete && <span className="status-spinner" />}
            <span className="status-text">
              {displayMessage}
              {msg.tool && <span className="status-tool"> [{msg.tool}]</span>}
            </span>
            {/* Tool progress bar */}
            {msg.progress !== undefined && msg.progress !== null && msg.progress < 1 && (
              <div className="tool-progress">
                <div 
                  className={`tool-progress-fill ${msg.instant ? 'no-animate' : ''}`}
                  style={{ width: `${Math.round(msg.progress * 100)}%` }}
                />
                <span className="tool-progress-text">{Math.round(msg.progress * 100)}%</span>
              </div>
            )}
          </div>
        );
      })}
      
      {/* Cancel button for long operations */}
      {showCancel && (
        <button className="cancel-button" onClick={onCancel}>
          Cancel
        </button>
      )}
      
      <style jsx>{`
        .status-notifications {
          display: flex;
          flex-direction: column;
          gap: 3px;
          margin: 4px 0;
          padding: 0 8px;
        }
        
        .pass-progress {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 4px 0;
          margin-bottom: 2px;
        }
        
        .pass-label {
          font-size: 11px;
          color: rgba(255, 255, 255, 0.5);
          min-width: 60px;
        }
        
        .pass-bar {
          flex: 1;
          max-width: 100px;
          height: 3px;
          background: rgba(255, 255, 255, 0.1);
          border-radius: 2px;
          overflow: hidden;
        }
        
        .pass-fill {
          height: 100%;
          background: rgba(76, 175, 80, 0.6);
          transition: width 0.3s ease-out;
          border-radius: 2px;
        }
        
        .status-line {
          text-align: center;
          padding: 3px 0;
          font-size: 13px;
          color: rgba(255, 255, 255, 0.45);
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 6px;
          animation: fadeIn 0.15s ease-out;
        }
        
        /* Skip animation for rapid updates to prevent epileptic flashing */
        .status-line.no-animate {
          animation: none;
        }
        
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(-2px); }
          to { opacity: 1; transform: translateY(0); }
        }
        
        .status-line.latest {
          color: rgba(255, 255, 255, 0.65);
        }
        
        /* Phase-specific colors */
        .status-line.phase-thinking {
          color: rgba(150, 180, 255, 0.65);
        }
        
        .status-line.phase-executing {
          color: rgba(180, 255, 180, 0.65);
        }
        
        .status-line.phase-ready {
          color: rgba(76, 175, 80, 0.8);
        }
        
        .status-spinner {
          width: 10px;
          height: 10px;
          border: 1.5px solid rgba(255, 255, 255, 0.15);
          border-top-color: rgba(255, 255, 255, 0.5);
          border-radius: 50%;
          animation: spin 0.6s linear infinite;
          flex-shrink: 0;
        }
        
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
        
        .status-text {
          opacity: 0.9;
        }
        
        .status-tool {
          opacity: 0.5;
          font-size: 11px;
          font-family: monospace;
        }
        
        .tool-progress {
          display: flex;
          align-items: center;
          gap: 6px;
          margin-left: 8px;
          min-width: 80px;
        }
        
        .tool-progress-fill {
          height: 4px;
          background: linear-gradient(90deg, rgba(76, 175, 80, 0.6), rgba(76, 175, 80, 0.9));
          border-radius: 2px;
          transition: width 0.3s ease-out;
          min-width: 0;
        }
        
        /* Skip transition for rapid updates */
        .tool-progress-fill.no-animate {
          transition: none;
        }
        
        .tool-progress-text {
          font-size: 10px;
          color: rgba(255, 255, 255, 0.5);
          min-width: 28px;
          text-align: right;
        }
        
        .cancel-button {
          align-self: center;
          margin-top: 6px;
          padding: 4px 12px;
          font-size: 11px;
          color: rgba(255, 255, 255, 0.6);
          background: rgba(244, 67, 54, 0.15);
          border: 1px solid rgba(244, 67, 54, 0.3);
          border-radius: 4px;
          cursor: pointer;
          transition: all 0.15s ease;
        }
        
        .cancel-button:hover {
          color: #f44336;
          background: rgba(244, 67, 54, 0.25);
          border-color: rgba(244, 67, 54, 0.5);
        }
      `}</style>
    </div>
  );
}

export default StatusIndicator;
