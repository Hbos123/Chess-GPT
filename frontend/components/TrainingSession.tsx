"use client";

import { useState } from "react";
import TrainingDrill from "./TrainingDrill";

interface TrainingSessionProps {
  session: any;
  username: string;
  onComplete: (results: any) => void;
  onClose: () => void;
}

export default function TrainingSession({
  session,
  username,
  onComplete,
  onClose
}: TrainingSessionProps) {
  const [currentDrillIndex, setCurrentDrillIndex] = useState(0);
  const [results, setResults] = useState<any[]>([]);
  const [isComplete, setIsComplete] = useState(false);

  const handleDrillComplete = async (correct: boolean, timeS: number, hintsUsed: number) => {
    const drill = session.cards[currentDrillIndex];
    
    // Record result
    const result = {
      card_id: drill.card_id,
      correct,
      time_s: timeS,
      hints_used: hintsUsed
    };
    
    setResults([...results, result]);
    
    // Update backend SRS
    try {
      await fetch("http://localhost:8000/update_drill_result", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username,
          card_id: drill.card_id,
          correct,
          time_s: timeS,
          hints_used: hintsUsed
        })
      });
    } catch (err) {
      console.error("Failed to update drill result:", err);
    }
    
    // Move to next drill or finish
    if (currentDrillIndex + 1 < session.cards.length) {
      setTimeout(() => {
        setCurrentDrillIndex(currentDrillIndex + 1);
      }, 500);
    } else {
      setTimeout(() => {
        setIsComplete(true);
        onComplete([...results, result]);
      }, 500);
    }
  };

  const handleSkip = () => {
    // Mark as incorrect skip
    handleDrillComplete(false, 0, 0);
  };

  if (isComplete) {
    const correctCount = results.filter(r => r.correct).length;
    const accuracy = (correctCount / results.length) * 100;
    const avgTime = results.reduce((sum, r) => sum + r.time_s, 0) / results.length;

    return (
      <div className="training-session-complete">
        <h2>🎯 Session Complete!</h2>
        
        <div className="session-summary">
          <div className="summary-stat">
            <div className="stat-label">Accuracy</div>
            <div className="stat-value">{accuracy.toFixed(0)}%</div>
          </div>
          <div className="summary-stat">
            <div className="stat-label">Drills Completed</div>
            <div className="stat-value">{correctCount}/{results.length}</div>
          </div>
          <div className="summary-stat">
            <div className="stat-label">Avg Time</div>
            <div className="stat-value">{avgTime.toFixed(1)}s</div>
          </div>
        </div>

        <div className="session-feedback">
          {accuracy >= 80 && <p>🌟 Excellent work! Your pattern recognition is strong.</p>}
          {accuracy >= 60 && accuracy < 80 && <p>👍 Good session! Keep practicing these patterns.</p>}
          {accuracy < 60 && <p>💪 Keep training! Review the missed drills and try again.</p>}
        </div>

        <div className="session-actions">
          <button className="review-mistakes-btn" onClick={() => setCurrentDrillIndex(0)}>
            Review Mistakes
          </button>
          <button className="close-session-btn" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="training-session-container">
      <div className="session-info">
        <h3>Training Session: {session.mode}</h3>
        <div className="session-composition">
          New: {session.composition.new} • Learning: {session.composition.learning} • Review: {session.composition.review}
        </div>
      </div>

      <TrainingDrill
        drill={session.cards[currentDrillIndex]}
        onComplete={handleDrillComplete}
        onSkip={handleSkip}
        currentIndex={currentDrillIndex}
        totalDrills={session.cards.length}
      />

      <div className="session-footer">
        <button onClick={onClose} className="exit-session-btn">
          Exit Session
        </button>
      </div>
    </div>
  );
}

