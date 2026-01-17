"use client";

import { useState, useEffect, useRef, useMemo } from "react";
import { Chess } from "chess.js";
import Board from "./Board";

interface TrainingDrillProps {
  drill: any;
  onComplete: (correct: boolean, timeS: number, hintsUsed: number) => void;
  onSkip: () => void;
  currentIndex: number;
  totalDrills: number;
}

export default function TrainingDrill({
  drill,
  onComplete,
  onSkip,
  currentIndex,
  totalDrills
}: TrainingDrillProps) {
  const [showHint, setShowHint] = useState(false);
  const [hintsUsed, setHintsUsed] = useState(0);
  const [startTime] = useState(Date.now());
  const [userMove, setUserMove] = useState("");
  const [feedback, setFeedback] = useState<{type: "correct" | "incorrect" | ""; message: string}>({type: "", message: ""});
  const [showSolution, setShowSolution] = useState(false);
  
  // INFINITE LOOP PREVENTION:
  // - Use refs to track previous values and only update when they actually change
  // - Memoize derived values to prevent new object/array references on every render
  // - Use function initializers in useState to prevent recreation on every render
  // - Check for actual value changes before calling setState in useEffect
  
  const prevDrillIdRef = useRef<string | undefined>(undefined);
  const prevFenRef = useRef<string | undefined>(undefined);
  
  // Memoize the initial FEN to prevent recreation on every render
  const initialFen = useMemo(() => {
    return drill.fen || "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";
  }, [drill.fen]);
  
  // Initialize game state - use function initializer to prevent recreation
  const [drillGame, setDrillGame] = useState<Chess>(() => {
    try {
      return new Chess(initialFen);
    } catch (e) {
      console.error("Failed to initialize drill game:", e);
      return new Chess("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1");
    }
  });
  
  // Reset state when drill changes - only when card_id actually changes
  // This prevents infinite loops by checking refs before updating state
  useEffect(() => {
    const currentDrillId = drill.card_id;
    const currentFen = drill.fen;
    
    // Only reset if drill ID or FEN actually changed (not just a new reference)
    if (prevDrillIdRef.current !== currentDrillId || prevFenRef.current !== currentFen) {
      prevDrillIdRef.current = currentDrillId;
      prevFenRef.current = currentFen;
      
      setShowHint(false);
      setHintsUsed(0);
      setUserMove("");
      setFeedback({type: "", message: ""});
      setShowSolution(false);
      
      // Only create new game if FEN actually changed
      try {
        const newGame = new Chess(currentFen || initialFen);
        setDrillGame(newGame);
      } catch (e) {
        console.error("Invalid FEN in drill:", currentFen, e);
        setDrillGame(new Chess(initialFen));
      }
    }
  }, [drill.card_id, drill.fen, initialFen]);

  const handleBoardMove = (from: string, to: string, promotion?: string) => {
    if (showSolution || feedback.message) return;
    
    try {
      const tempGame = new Chess(drill.fen);
      const move = tempGame.move({ from, to, promotion });
      
      if (!move) {
        setFeedback({
          type: "incorrect",
          message: "❌ Invalid move. Try again."
        });
        return;
      }
      
      const moveSan = move.san;
      const timeSpent = (Date.now() - startTime) / 1000;
      const isCorrect = moveSan.toLowerCase() === drill.best_move_san.toLowerCase();
      
      setUserMove(moveSan);
      setDrillGame(tempGame);
      
      if (isCorrect) {
        setFeedback({
          type: "correct",
          message: `✅ Correct! ${drill.best_move_san} is the best move.`
        });
        setTimeout(() => onComplete(true, timeSpent, hintsUsed), 1500);
      } else {
        setFeedback({
          type: "incorrect",
          message: `❌ Not quite. The best move is ${drill.best_move_san}. Try again or show solution.`
        });
        // Reset board after showing incorrect feedback
        setTimeout(() => {
          setDrillGame(new Chess(drill.fen));
        }, 2000);
      }
    } catch (e) {
      setFeedback({
        type: "incorrect",
        message: "❌ Invalid move. Try again."
      });
    }
  };

  const handleTextMove = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      const move = (e.target as HTMLInputElement).value.trim();
      if (!move) return;
      
      try {
        const tempGame = new Chess(drill.fen);
        const moveObj = tempGame.move(move);
        
        if (!moveObj) {
          setFeedback({
            type: "incorrect",
            message: "❌ Invalid move notation. Try again."
          });
          return;
        }
        
        const timeSpent = (Date.now() - startTime) / 1000;
        const isCorrect = moveObj.san.toLowerCase() === drill.best_move_san.toLowerCase();
        
        setUserMove(move);
        setDrillGame(tempGame);
        
        if (isCorrect) {
          setFeedback({
            type: "correct",
            message: `✅ Correct! ${drill.best_move_san} is the best move.`
          });
          setTimeout(() => onComplete(true, timeSpent, hintsUsed), 1500);
        } else {
          setFeedback({
            type: "incorrect",
            message: `❌ Not quite. The best move is ${drill.best_move_san}. Try again or show solution.`
          });
          setTimeout(() => {
            setDrillGame(new Chess(drill.fen));
          }, 2000);
        }
      } catch (e) {
        setFeedback({
          type: "incorrect",
          message: "❌ Invalid move notation. Try again."
        });
      }
    }
  };

  const handleShowHint = () => {
    setShowHint(true);
    setHintsUsed(hintsUsed + 1);
  };

  const handleShowSolution = () => {
    setShowSolution(true);
    setFeedback({
      type: "correct",
      message: `💡 Solution: ${drill.best_move_san}. ${drill.hint || ""}`
    });
    
    const timeSpent = (Date.now() - startTime) / 1000;
    
    setTimeout(() => {
      onComplete(false, timeSpent, hintsUsed + 1);
    }, 3000);
  };

  const boardOrientation = drill.side_to_move === "white" ? "white" : "black";

  return (
    <div className="training-drill-container">
      <div className="drill-header">
        <div className="drill-progress">
          Drill {currentIndex + 1} of {totalDrills}
        </div>
        <div className="drill-type-badge">{drill.type}</div>
      </div>

      <div className="drill-question">
        <h3>{drill.question}</h3>
        {drill.phase && (
          <div className="drill-meta">
            Phase: {drill.phase} {drill.opening && `• Opening: ${drill.opening}`}
          </div>
        )}
        {drill.origin && (
          <div className="drill-origin">
            📍 {drill.origin}
            {drill.game_date && (
              <span className="drill-date">
                ({new Date(drill.game_date).toLocaleDateString()})
              </span>
            )}
          </div>
        )}
      </div>

      <div className="drill-board-section">
        <div className="drill-board-wrapper">
          <Board
            fen={drillGame.fen()}
            onMove={handleBoardMove}
            orientation={boardOrientation}
            disabled={showSolution || !!feedback.message}
          />
        </div>
        <div className="drill-board-info">
          <div className="position-info">
            {drill.side_to_move === "white" ? "White" : "Black"} to move
          </div>
          {!showSolution && !feedback.message && (
            <div className="move-input-section">
              <label>Or enter move notation:</label>
              <input
                type="text"
                placeholder="e.g., Nxd5"
                className="move-input"
                onKeyDown={handleTextMove}
                disabled={showSolution || !!feedback.message}
              />
            </div>
          )}
        </div>
      </div>

      {feedback.message && (
        <div className={`drill-feedback ${feedback.type}`}>
          {feedback.message}
        </div>
      )}

      {showSolution && drill.best_move_san && (
        <div className="solution-display">
          ✅ Solution: {drill.best_move_san}
        </div>
      )}

      <div className="drill-actions">
        {!showSolution && !feedback.message && (
          <>
            <button onClick={handleShowHint} className="hint-btn" disabled={showHint}>
              {showHint ? `💡 ${drill.hint || "No hint available"}` : "Show Hint"}
            </button>
            <button onClick={handleShowSolution} className="solution-btn">
              Show Solution
            </button>
            <button onClick={onSkip} className="skip-btn">
              Skip
            </button>
          </>
        )}
      </div>

      {showHint && !showSolution && (
        <div className="drill-hint">
          {drill.hint || "No hint available for this position."}
        </div>
      )}
    </div>
  );
}

