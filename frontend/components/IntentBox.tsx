"use client";

import React, { useState, useMemo } from 'react';

interface StatusMessage {
  phase: string;
  message: string;
  tool?: string;
  timestamp: number;
}

interface IntentBoxProps {
  intent: string;
  toolsUsed: string[];
  statusHistory?: StatusMessage[];
  mode?: string;
}

export function IntentBox({ intent, toolsUsed, statusHistory, mode }: IntentBoxProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  
  // Deduplicate history so repeated early-phase messages (e.g. "Understanding your request...")
  // don't spam the expanded view (this matches StatusIndicator behavior).
  const uniqueHistory: StatusMessage[] = useMemo(() => {
    const src = Array.isArray(statusHistory) ? statusHistory : [];
    return src.reduce((acc: StatusMessage[], msg) => {
      if (acc.some(m => m.message === msg.message && m.phase === msg.phase)) return acc;
      return [...acc, msg];
    }, []);
  }, [statusHistory]);

  // Calculate thinking time from status history
  const thinkingTime: string | null = useMemo(() => {
    if (!uniqueHistory || uniqueHistory.length < 2) return null;
    const first = uniqueHistory[0]?.timestamp || 0;
    const last = uniqueHistory[uniqueHistory.length - 1]?.timestamp || 0;
    const seconds = (last - first);
    return seconds > 1000 ? (seconds / 1000).toFixed(1) : seconds.toFixed(1);
  }, [statusHistory]);
  
  if (!intent && toolsUsed.length === 0) {
    return null;
  }
  
  const hasHistory = uniqueHistory && uniqueHistory.length > 0;
  
  return (
    <div className="intent-whisper">
      {/* Main line - looks like system notification */}
      <div 
        className="intent-line"
        onClick={() => hasHistory && setIsExpanded(!isExpanded)}
        style={{ cursor: hasHistory ? 'pointer' : 'default' }}
      >
        Thought for {thinkingTime || '~'}s
        {toolsUsed.length > 0 && (
          <span className="tools-count"> · {toolsUsed.length} tool{toolsUsed.length > 1 ? 's' : ''}</span>
        )}
        {hasHistory && (
          <span className="expand-hint"> {isExpanded ? '▲' : '▼'}</span>
        )}
      </div>
      
      {/* Expanded chain of thought */}
      {isExpanded && hasHistory && (
        <div className="chain-expanded">
          {uniqueHistory.map((status, idx) => (
            <div key={idx} className="chain-line">
              <span className="chain-message">{status.message}</span>
              {status.tool && <span className="tool-name">({status.tool})</span>}
            </div>
          ))}
        </div>
      )}
      
      <style jsx>{`
        .intent-whisper {
          text-align: center;
          margin: 4px 0;
        }
        
        .intent-line {
          padding: 4px 0;
          font-size: 13px;
          color: rgba(255, 255, 255, 0.5);
          display: inline-flex;
          align-items: center;
          gap: 4px;
        }
        
        .intent-line:hover {
          color: rgba(255, 255, 255, 0.65);
        }
        
        .tools-count {
          opacity: 0.8;
        }
        
        .expand-hint {
          font-size: 9px;
          opacity: 0.5;
          margin-left: 4px;
        }
        
        .chain-expanded {
          margin: 8px auto 0;
          padding: 10px 20px;
          background: rgba(255, 255, 255, 0.03);
          border-radius: 8px;
          max-width: 500px;
        }
        
        .chain-line {
          font-size: 12px;
          color: rgba(255, 255, 255, 0.45);
          padding: 3px 0;
          text-align: center;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 6px;
        }
        
        .chain-message {
          /* message text */
        }
        
        .tool-name {
          opacity: 0.6;
          font-size: 11px;
        }
      `}</style>
    </div>
  );
}

export default IntentBox;
