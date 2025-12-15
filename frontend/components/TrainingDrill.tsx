"use client";

import { useState, useEffect } from "react";

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
  
  // Reset state when drill changes
  useEffect(() => {
    setShowHint(false);
    setHintsUsed(0);
    setUserMove("");
    setFeedback({type: "", message: ""});
    setShowSolution(false);
  }, [drill.card_id]);
  

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
      </div>

      <div className="drill-board">
        {/* Temporary: Board component causes infinite loop - using text display for now */}
        <div className="drill-board-placeholder">
          <div className="fen-display">FEN: {drill.fen}</div>
          <div className="position-info">
            {drill.side_to_move === "white" ? "White" : "Black"} to move
          </div>
          
          {!showSolution && !feedback.message && (
            <div className="move-prompt">
              Make your move by entering it below:
              <input
                type="text"
                placeholder="e.g., Nxd5"
                className="move-input"
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    const move = (e.target as HTMLInputElement).value;
                    setUserMove(move);
                    const timeSpent = (Date.now() - startTime) / 1000;
                    const isCorrect = move.toLowerCase() === drill.best_move_san.toLowerCase();
                    
                    if (isCorrect) {
                      setFeedback({
                        type: "correct",
                        message: `✅ Correct! ${drill.best_move_san} is the best move.`
                      });
                      setTimeout(() => onComplete(true, timeSpent, hintsUsed), 1500);
                    } else {
                      setFeedback({
                        type: "incorrect",
                        message: `❌ Not quite. Try again or show solution.`
                      });
                    }
                  }
                }}
              />
            </div>
          )}
          
          {showSolution && drill.best_move_san && (
            <div className="solution-overlay">
              ✅ Solution: {drill.best_move_san}
            </div>
          )}
        </div>
      </div>

      {feedback.message && (
        <div className={`drill-feedback ${feedback.type}`}>
          {feedback.message}
        </div>
      )}

      <div className="drill-actions">
        {!showSolution && !feedback.message && (
          <>
            <button onClick={handleShowHint} className="hint-btn" disabled={showHint}>
              {showHint ? `💡 ${drill.hint}` : "Show Hint"}
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
          {drill.hint}
        </div>
      )}
    </div>
  );
}

