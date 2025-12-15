"use client";

import React, { useState, useRef, useEffect, useCallback } from 'react';

export interface BoardTab {
  id: string;
  name: string;
  fen: string;
  pgn: string;
  isAnalyzing: boolean;
  hasUnread: boolean;
  isModified: boolean;
  metadata?: {
    white?: string;
    black?: string;
    date?: string;
    result?: string;
    timeControl?: string;
    opening?: string;
  };
  createdAt: number;
}

interface TabBarProps {
  tabs: BoardTab[];
  activeTabId: string;
  onTabSelect: (tabId: string) => void;
  onTabClose: (tabId: string) => void;
  onTabRename: (tabId: string, newName: string) => void;
  onTabDuplicate: (tabId: string) => void;
  onNewTab: () => void;
  maxTabs?: number;
}

export default function TabBar({
  tabs,
  activeTabId,
  onTabSelect,
  onTabClose,
  onTabRename,
  onTabDuplicate,
  onNewTab,
  maxTabs = 5,
}: TabBarProps) {
  const [editingTabId, setEditingTabId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');
  const [contextMenu, setContextMenu] = useState<{ x: number; y: number; tabId: string } | null>(null);
  const editInputRef = useRef<HTMLInputElement>(null);
  const contextMenuRef = useRef<HTMLDivElement>(null);

  // Focus input when editing starts
  useEffect(() => {
    if (editingTabId && editInputRef.current) {
      editInputRef.current.focus();
      editInputRef.current.select();
    }
  }, [editingTabId]);

  // Close context menu on click outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (contextMenuRef.current && !contextMenuRef.current.contains(e.target as Node)) {
        setContextMenu(null);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Handle keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const isMod = e.metaKey || e.ctrlKey;
      
      // Cmd/Ctrl + 1-5: Switch tabs
      if (isMod && e.key >= '1' && e.key <= '5') {
        e.preventDefault();
        const tabIndex = parseInt(e.key) - 1;
        if (tabs[tabIndex]) {
          onTabSelect(tabs[tabIndex].id);
        }
      }
      
      // Cmd/Ctrl + T: New tab
      if (isMod && e.key === 't' && !e.shiftKey) {
        e.preventDefault();
        if (tabs.length < maxTabs) {
          onNewTab();
        }
      }
      
      // Cmd/Ctrl + W: Close tab
      if (isMod && e.key === 'w' && !e.shiftKey) {
        e.preventDefault();
        if (tabs.length > 1) {
          onTabClose(activeTabId);
        }
      }
      
      // Cmd/Ctrl + Shift + D: Duplicate tab
      if (isMod && e.shiftKey && e.key === 'd') {
        e.preventDefault();
        if (tabs.length < maxTabs) {
          onTabDuplicate(activeTabId);
        }
      }
    };
    
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [tabs, activeTabId, maxTabs, onTabSelect, onNewTab, onTabClose, onTabDuplicate]);

  const startEditing = (tabId: string, currentName: string) => {
    setEditingTabId(tabId);
    setEditValue(currentName);
  };

  const finishEditing = () => {
    if (editingTabId && editValue.trim()) {
      onTabRename(editingTabId, editValue.trim());
    }
    setEditingTabId(null);
    setEditValue('');
  };

  const handleContextMenu = (e: React.MouseEvent, tabId: string) => {
    e.preventDefault();
    setContextMenu({ x: e.clientX, y: e.clientY, tabId });
  };

  const buildTooltip = (tab: BoardTab): string => {
    const parts: string[] = [];
    if (tab.metadata?.white && tab.metadata?.black) {
      parts.push(`${tab.metadata.white} vs ${tab.metadata.black}`);
    }
    if (tab.metadata?.timeControl) {
      parts.push(tab.metadata.timeControl);
    }
    if (tab.metadata?.date) {
      parts.push(tab.metadata.date);
    }
    if (tab.metadata?.result) {
      parts.push(tab.metadata.result);
    }
    if (tab.metadata?.opening) {
      parts.push(tab.metadata.opening);
    }
    return parts.length > 0 ? parts.join(' · ') : tab.name;
  };

  return (
    <div className="tab-bar">
      <div className="tab-bar-tabs">
        {tabs.map((tab, index) => (
          <div
            key={tab.id}
            className={`tab-item ${tab.id === activeTabId ? 'active' : ''}`}
            onClick={() => onTabSelect(tab.id)}
            onContextMenu={(e) => handleContextMenu(e, tab.id)}
            title={buildTooltip(tab)}
          >
            {/* State indicators */}
            <div className="tab-indicators">
              {tab.isAnalyzing && (
                <span className="tab-indicator analyzing" title="Analyzing...">
                  <svg className="spinner" width="12" height="12" viewBox="0 0 24 24">
                    <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" fill="none" strokeDasharray="30 70" />
                  </svg>
                </span>
              )}
              {tab.hasUnread && !tab.isAnalyzing && (
                <span className="tab-indicator unread" title="New messages" />
              )}
              {tab.isModified && !tab.isAnalyzing && !tab.hasUnread && (
                <span className="tab-indicator modified" title="Modified" />
              )}
            </div>

            {/* Tab name */}
            {editingTabId === tab.id ? (
              <input
                ref={editInputRef}
                className="tab-name-input"
                value={editValue}
                onChange={(e) => setEditValue(e.target.value)}
                onBlur={finishEditing}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') finishEditing();
                  if (e.key === 'Escape') {
                    setEditingTabId(null);
                    setEditValue('');
                  }
                }}
                onClick={(e) => e.stopPropagation()}
              />
            ) : (
              <span
                className="tab-name"
                onDoubleClick={() => startEditing(tab.id, tab.name)}
              >
                {tab.name}
              </span>
            )}

            {/* Keyboard hint */}
            {index < 5 && (
              <span className="tab-shortcut">{index + 1}</span>
            )}

            {/* Close button */}
            {tabs.length > 1 && (
              <button
                className="tab-close"
                onClick={(e) => {
                  e.stopPropagation();
                  onTabClose(tab.id);
                }}
                title="Close tab (Cmd+W)"
              >
                ×
              </button>
            )}
          </div>
        ))}

        {/* New tab button */}
        {tabs.length < maxTabs && (
          <button
            className="tab-new"
            onClick={onNewTab}
            title="New tab (Cmd+T)"
          >
            +
          </button>
        )}
      </div>

      {/* Context menu */}
      {contextMenu && (
        <div
          ref={contextMenuRef}
          className="tab-context-menu"
          style={{ left: contextMenu.x, top: contextMenu.y }}
        >
          <button
            onClick={() => {
              startEditing(contextMenu.tabId, tabs.find(t => t.id === contextMenu.tabId)?.name || '');
              setContextMenu(null);
            }}
          >
            Rename
          </button>
          {tabs.length < maxTabs && (
            <button
              onClick={() => {
                onTabDuplicate(contextMenu.tabId);
                setContextMenu(null);
              }}
            >
              Duplicate
            </button>
          )}
          {tabs.length > 1 && (
            <button
              onClick={() => {
                onTabClose(contextMenu.tabId);
                setContextMenu(null);
              }}
            >
              Close
            </button>
          )}
        </div>
      )}

      <style jsx>{`
        .tab-bar {
          display: flex;
          align-items: center;
          background: rgba(30, 30, 35, 0.95);
          border-bottom: 1px solid rgba(255, 255, 255, 0.1);
          padding: 0 8px;
          height: 36px;
          position: relative;
          z-index: 100;
        }

        .tab-bar-tabs {
          display: flex;
          align-items: center;
          gap: 2px;
          overflow-x: auto;
          scrollbar-width: none;
        }

        .tab-bar-tabs::-webkit-scrollbar {
          display: none;
        }

        .tab-item {
          display: flex;
          align-items: center;
          gap: 6px;
          padding: 6px 12px;
          background: rgba(255, 255, 255, 0.05);
          border-radius: 6px 6px 0 0;
          cursor: pointer;
          min-width: 100px;
          max-width: 180px;
          transition: background 0.15s ease;
          position: relative;
        }

        .tab-item:hover {
          background: rgba(255, 255, 255, 0.1);
        }

        .tab-item.active {
          background: rgba(76, 175, 80, 0.2);
          border-bottom: 2px solid #4caf50;
        }

        .tab-indicators {
          display: flex;
          align-items: center;
          width: 14px;
          flex-shrink: 0;
        }

        .tab-indicator {
          display: block;
        }

        .tab-indicator.analyzing .spinner {
          animation: spin 1s linear infinite;
          color: #4caf50;
        }

        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }

        .tab-indicator.unread {
          width: 8px;
          height: 8px;
          background: #2196f3;
          border-radius: 50%;
        }

        .tab-indicator.modified {
          width: 8px;
          height: 8px;
          background: #ff9800;
          border-radius: 50%;
        }

        .tab-name {
          flex: 1;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
          font-size: 13px;
          color: rgba(255, 255, 255, 0.9);
        }

        .tab-name-input {
          flex: 1;
          background: rgba(0, 0, 0, 0.3);
          border: 1px solid rgba(76, 175, 80, 0.5);
          border-radius: 3px;
          padding: 2px 4px;
          font-size: 13px;
          color: white;
          outline: none;
          min-width: 60px;
        }

        .tab-shortcut {
          font-size: 10px;
          color: rgba(255, 255, 255, 0.3);
          padding: 1px 4px;
          background: rgba(255, 255, 255, 0.05);
          border-radius: 3px;
          flex-shrink: 0;
        }

        .tab-close {
          background: none;
          border: none;
          color: rgba(255, 255, 255, 0.4);
          cursor: pointer;
          padding: 0 2px;
          font-size: 16px;
          line-height: 1;
          border-radius: 3px;
          flex-shrink: 0;
          transition: all 0.15s ease;
        }

        .tab-close:hover {
          color: #f44336;
          background: rgba(244, 67, 54, 0.1);
        }

        .tab-new {
          background: none;
          border: 1px dashed rgba(255, 255, 255, 0.2);
          color: rgba(255, 255, 255, 0.5);
          cursor: pointer;
          padding: 4px 12px;
          font-size: 16px;
          border-radius: 6px 6px 0 0;
          transition: all 0.15s ease;
        }

        .tab-new:hover {
          color: #4caf50;
          border-color: rgba(76, 175, 80, 0.5);
          background: rgba(76, 175, 80, 0.1);
        }

        .tab-context-menu {
          position: fixed;
          background: rgba(40, 40, 45, 0.98);
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 6px;
          padding: 4px 0;
          min-width: 120px;
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
          z-index: 1000;
        }

        .tab-context-menu button {
          display: block;
          width: 100%;
          text-align: left;
          background: none;
          border: none;
          color: rgba(255, 255, 255, 0.9);
          padding: 8px 12px;
          font-size: 13px;
          cursor: pointer;
          transition: background 0.15s ease;
        }

        .tab-context-menu button:hover {
          background: rgba(76, 175, 80, 0.2);
        }
      `}</style>
    </div>
  );
}

// Helper function to generate auto tab names
export function generateTabName(tab: Partial<BoardTab>): string {
  if (tab.metadata?.white && tab.metadata?.black) {
    return `${tab.metadata.white} vs ${tab.metadata.black}`;
  }
  if (tab.metadata?.opening) {
    return `Analysis: ${tab.metadata.opening}`;
  }
  if (tab.pgn && tab.pgn.length > 0) {
    // Extract first few moves from PGN
    const moves = tab.pgn.split(/\d+\./).filter(m => m.trim()).slice(0, 2);
    if (moves.length > 0) {
      return `Game: ${moves.join(' ').trim().substring(0, 20)}...`;
    }
  }
  return 'Board';
}

// Helper to create a default tab
export function createDefaultTab(index: number = 1): BoardTab {
  return {
    id: `tab-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
    name: `Board ${index}`,
    fen: 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
    pgn: '',
    isAnalyzing: false,
    hasUnread: false,
    isModified: false,
    createdAt: Date.now(),
  };
}

// Helper to create a tab from game data
export function createTabFromGame(gameData: {
  pgn: string;
  white?: string;
  black?: string;
  date?: string;
  result?: string;
  timeControl?: string;
  opening?: string;
}): BoardTab {
  const tab: BoardTab = {
    id: `tab-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
    name: '',
    fen: 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
    pgn: gameData.pgn,
    isAnalyzing: false,
    hasUnread: false,
    isModified: false,
    metadata: {
      white: gameData.white,
      black: gameData.black,
      date: gameData.date,
      result: gameData.result,
      timeControl: gameData.timeControl,
      opening: gameData.opening,
    },
    createdAt: Date.now(),
  };
  tab.name = generateTabName(tab);
  return tab;
}

