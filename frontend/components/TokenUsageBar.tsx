"use client";

import { useState } from 'react';

interface TokenUsageBarProps {
  messages?: { used: number; limit: number };
  tokens?: { used: number; limit: number };
}

export default function TokenUsageBar({ messages, tokens }: TokenUsageBarProps) {
  const [showTooltip, setShowTooltip] = useState(false);

  if (!messages && !tokens) {
    return null;
  }

  // Use messages if available, otherwise tokens
  const usage = messages || tokens;
  if (!usage) return null;

  const used = usage.used || 0;
  const limit = usage.limit || 1;
  const percentage = Math.min((used / limit) * 100, 100);
  
  // Color based on usage
  const getColor = () => {
    const ratio = used / limit;
    if (ratio >= 0.9) return '#ef4444'; // red
    if (ratio >= 0.7) return '#f59e0b'; // orange
    return '#10b981'; // green
  };

  return (
    <div
      style={{
        position: 'relative',
        width: '24px',
        height: '2px',
        backgroundColor: 'var(--bg-secondary)',
        borderRadius: '1px',
        cursor: 'help',
        flexShrink: 0,
      }}
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
    >
      {/* Progress bar */}
      <div
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          height: '100%',
          width: `${percentage}%`,
          backgroundColor: getColor(),
          borderRadius: '1px',
          transition: 'width 0.2s ease, background-color 0.2s ease',
        }}
      />
      
      {/* Tooltip */}
      {showTooltip && (
        <div
          style={{
            position: 'absolute',
            bottom: '8px',
            left: '50%',
            transform: 'translateX(-50%)',
            backgroundColor: 'var(--bg-primary)',
            border: '1px solid var(--border-color)',
            borderRadius: '6px',
            padding: '8px 12px',
            fontSize: '12px',
            color: 'var(--text-primary)',
            whiteSpace: 'nowrap',
            boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)',
            zIndex: 10001,
            pointerEvents: 'none',
          }}
        >
          <div style={{ marginBottom: '4px', fontWeight: 600 }}>
            Daily Usage
          </div>
          {messages && (
            <div style={{ marginBottom: '2px' }}>
              Messages: <strong>{messages.used}/{messages.limit}</strong>
            </div>
          )}
          {tokens && (
            <div>
              Tokens: <strong>{tokens.used.toLocaleString()}/{tokens.limit.toLocaleString()}</strong>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
