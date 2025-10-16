"use client";

import { useState, useRef, useEffect } from "react";
import type { MoveNode } from "@/lib/moveTree";

interface PGNViewerProps {
  rootNode: MoveNode;
  currentNode: MoveNode;
  onMoveClick: (node: MoveNode) => void;
  onDeleteMove: (node: MoveNode) => void;
  onDeleteVariation: (node: MoveNode) => void;
  onPromoteVariation: (node: MoveNode) => void;
  onAddComment: (node: MoveNode, comment: string) => void;
}

interface ContextMenu {
  node: MoveNode;
  x: number;
  y: number;
}

export default function PGNViewer({
  rootNode,
  currentNode,
  onMoveClick,
  onDeleteMove,
  onDeleteVariation,
  onPromoteVariation,
  onAddComment,
}: PGNViewerProps) {
  const [contextMenu, setContextMenu] = useState<ContextMenu | null>(null);
  const [editingComment, setEditingComment] = useState<MoveNode | null>(null);
  const [commentText, setCommentText] = useState("");
  const contextMenuRef = useRef<HTMLDivElement>(null);

  // Close context menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (contextMenuRef.current && !contextMenuRef.current.contains(e.target as Node)) {
        setContextMenu(null);
      }
    };

    if (contextMenu) {
      document.addEventListener("mousedown", handleClickOutside);
      return () => document.removeEventListener("mousedown", handleClickOutside);
    }
  }, [contextMenu]);

  const handleRightClick = (e: React.MouseEvent, node: MoveNode) => {
    e.preventDefault();
    setContextMenu({
      node,
      x: e.clientX,
      y: e.clientY,
    });
  };

  const handleDeleteMove = () => {
    if (contextMenu) {
      onDeleteMove(contextMenu.node);
      setContextMenu(null);
    }
  };

  const handleDeleteVariation = () => {
    if (contextMenu) {
      onDeleteVariation(contextMenu.node);
      setContextMenu(null);
    }
  };

  const handlePromoteVariation = () => {
    if (contextMenu) {
      onPromoteVariation(contextMenu.node);
      setContextMenu(null);
    }
  };

  const handleAddComment = () => {
    if (contextMenu) {
      setEditingComment(contextMenu.node);
      setCommentText(contextMenu.node.comment || "");
      setContextMenu(null);
    }
  };

  const handleSaveComment = () => {
    if (editingComment) {
      onAddComment(editingComment, commentText);
      setEditingComment(null);
      setCommentText("");
    }
  };

  const getNagDescription = (nag: string) => {
    const descriptions: { [key: string]: string } = {
      '!': 'Good move',
      '!!': 'Brilliant move',
      '?': 'Bad move',
      '??': 'Blunder',
      '!?': 'Interesting move',
      '?!': 'Dubious move',
    };
    return descriptions[nag] || nag;
  };

  const getMoveQualityClass = (node: any) => {
    if (!node.quality) return '';
    
    // Return CSS class based on move quality
    const qualityClasses: { [key: string]: string } = {
      'theory': 'move-theory',
      'best': 'move-best',
      'excellent': 'move-excellent',
      'good': 'move-good',
      'inaccuracy': 'move-inaccuracy',
      'mistake': 'move-mistake',
      'blunder': 'move-blunder'
    };
    
    let classes = qualityClasses[node.quality] || '';
    
    // Add special classes for critical/missed wins
    if (node.isCritical) classes += ' move-critical';
    if (node.isMissedWin) classes += ' move-missed-win';
    
    return classes;
  };

  const renderMove = (node: MoveNode, depth: number = 0): JSX.Element[] => {
    const elements: JSX.Element[] = [];

    if (node.move) {
      const isCurrent = node.id === currentNode.id;
      const isWhiteMove = node.fen.split(' ')[1] === 'b';
      const isVariationStart = node.parent && node.parent.children[0] !== node;

      // Add move number for white moves or start of variation
      const needsMoveNumber = isWhiteMove || isVariationStart;

      elements.push(
        <span key={`move-${node.id}`} className="inline-flex items-center">
          {needsMoveNumber && (
            <span className="move-number">{node.moveNumber}.</span>
          )}
          {!isWhiteMove && isVariationStart && (
            <span className="move-number">{node.moveNumber}...</span>
          )}
          <span
            className={`move ${isCurrent ? 'current-move' : ''} ${!node.isMainLine ? 'variation-move' : ''} ${getMoveQualityClass(node)}`}
            onClick={() => onMoveClick(node)}
            onContextMenu={(e) => handleRightClick(e, node)}
          >
            {node.move}
          </span>
          {node.comment && (
            <span className="comment-text" title="Click move to edit">
              {`{${node.comment}}`}
            </span>
          )}
        </span>
      );
    }

    // Render variations FIRST (immediately after this move)
    if (node.children.length > 1) {
      for (let i = 1; i < node.children.length; i++) {
        elements.push(
          <span key={`variation-${node.children[i].id}`} className="variation">
            <span className="variation-bracket">(</span>
            {renderMove(node.children[i], depth + 1)}
            <span className="variation-bracket">)</span>
          </span>
        );
      }
    }

    // Then render main line continuation
    if (node.children.length > 0) {
      elements.push(...renderMove(node.children[0], depth));
    }

    return elements;
  };

  return (
    <div className="pgn-viewer">
      <div className="moves-container">
        {renderMove(rootNode)}
      </div>

      {/* Context Menu */}
      {contextMenu && (
        <div
          ref={contextMenuRef}
          className="context-menu"
          style={{
            position: 'fixed',
            left: contextMenu.x,
            top: contextMenu.y,
            zIndex: 1000,
          }}
        >
          <div className="context-menu-item" onClick={handleDeleteMove}>
            🗑️ Delete move from here
          </div>
          {contextMenu.node.parent && contextMenu.node.parent.children.indexOf(contextMenu.node) > 0 && (
            <div className="context-menu-item" onClick={handleDeleteVariation}>
              ❌ Delete variation
            </div>
          )}
          {contextMenu.node.parent && contextMenu.node.parent.children.indexOf(contextMenu.node) > 0 && (
            <div className="context-menu-item" onClick={handlePromoteVariation}>
              ⬆️ Promote to main line
            </div>
          )}
          <div className="context-menu-item" onClick={handleAddComment}>
            💬 Add/Edit comment
          </div>
        </div>
      )}

      {/* Comment Editor */}
      {editingComment && (
        <div className="comment-editor-overlay">
          <div className="comment-editor">
            <h3>Edit Comment for {editingComment.move}</h3>
            <textarea
              value={commentText}
              onChange={(e) => setCommentText(e.target.value)}
              placeholder="Enter comment..."
              rows={4}
            />
            <div className="comment-editor-buttons">
              <button onClick={handleSaveComment}>Save</button>
              <button onClick={() => setEditingComment(null)}>Cancel</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

