import { useState } from 'react';
import Board from './Board';
import { Chess } from 'chess.js';
import PGNViewer from './PGNViewer';
import type { MoveNode } from '@/lib/moveTree';

interface BoardDockProps {
  fen: string;
  pgn?: string;
  arrows: any[];
  highlights: any[];
  onMove: (from: string, to: string, promotion?: string) => void;
  orientation?: 'white' | 'black';
  onLoadGame?: () => void;
  onHideBoard?: () => void;
  onFlipBoard?: () => void;
  // Optional PGN viewer props
  rootNode?: MoveNode;
  currentNode?: MoveNode;
  onMoveClick?: (node: MoveNode) => void;
  onDeleteMove?: (node: MoveNode) => void;
  onDeleteVariation?: (node: MoveNode) => void;
  onPromoteVariation?: (node: MoveNode) => void;
  onAddComment?: (node: MoveNode, comment: string) => void;
}

export default function BoardDock({ 
  fen, 
  pgn,
  arrows, 
  highlights, 
  onMove,
  orientation = 'white',
  onLoadGame,
  onHideBoard,
  onFlipBoard,
  rootNode,
  currentNode,
  onMoveClick,
  onDeleteMove,
  onDeleteVariation,
  onPromoteVariation,
  onAddComment
}: BoardDockProps) {
  const [showFen, setShowFen] = useState(false);

  return (
    <div className="board-dock">
      {onHideBoard && (
        <button className="hide-board-button" onClick={onHideBoard}>
          Hide
        </button>
      )}
      <div className="board-dock-inner">
        <div className="board-container">
          <Board
            fen={fen}
            onMove={onMove}
            arrows={arrows}
            highlights={highlights}
            orientation={orientation}
          />
          {/* PGN viewer placed in the same width container as the board */}
          {pgn && rootNode && currentNode && (
            <div className="pgn-under-board">
              <PGNViewer
                rootNode={rootNode}
                currentNode={currentNode}
                onMoveClick={onMoveClick || (() => {})}
                onDeleteMove={onDeleteMove || (() => {})}
                onDeleteVariation={onDeleteVariation || (() => {})}
                onPromoteVariation={onPromoteVariation || (() => {})}
                onAddComment={onAddComment || (() => {})}
              />
            </div>
          )}
        </div>
        
        <div className="board-info">
          {onFlipBoard && (
            <button className="flip-board-button" onClick={onFlipBoard}>
              Flip Board
            </button>
          )}
          {/* FEN Display (toggleable only) */}
          <div className="fen-toggle-section">
            <button 
              className="fen-toggle-button"
              onClick={() => setShowFen(!showFen)}
            >
              {showFen ? 'Hide' : 'Show'} FEN
            </button>
            {showFen && (
              <div className="fen-display">
                <code>{fen}</code>
              </div>
            )}
          </div>
        </div>
        
        {onLoadGame && (
          <button className="load-game-sidebar" onClick={onLoadGame}>
            Load game
          </button>
        )}
      </div>
    </div>
  );
}

