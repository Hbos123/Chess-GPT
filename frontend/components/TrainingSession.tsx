"use client";

import { useState } from "react";
import TrainingDrill from "./TrainingDrill";
import { getBackendBase } from "@/lib/backendBase";

interface TrainingSessionProps {
  session: any;
  username: string;
  onComplete: (results: any) => void;
  onClose: () => void;
  onSwitchToChat?: () => void; // New prop to switch to chat
}

export default function TrainingSession({
  session,
  username,
  onComplete,
  onClose,
  onSwitchToChat
}: TrainingSessionProps) {
  const BACKEND_BASE = getBackendBase();
  const [currentDrillIndex, setCurrentDrillIndex] = useState(0);
  const [results, setResults] = useState<any[]>([]);
  const [isComplete, setIsComplete] = useState(false);
  const [activeTab, setActiveTab] = useState<'training' | 'chat'>('training');

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
      await fetch(`${BACKEND_BASE}/update_drill_result`, {
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
      <div className="session-header">
        <h3>Training Session: {session.mode}</h3>
        {session.intro && (
          <div className="session-intro">
            {session.intro}
          </div>
        )}
        <div className="session-composition">
          New: {session.composition.new} • Learning: {session.composition.learning} • Review: {session.composition.review}
        </div>
      </div>

      {/* Tab switcher */}
      <div className="training-tabs">
        <button
          className={`training-tab ${activeTab === 'training' ? 'active' : ''}`}
          onClick={() => setActiveTab('training')}
        >
          Training
        </button>
        <button
          className={`training-tab ${activeTab === 'chat' ? 'active' : ''}`}
          onClick={() => {
            setActiveTab('chat');
            if (onSwitchToChat) {
              onSwitchToChat();
            }
          }}
        >
          Chat
        </button>
      </div>

      {activeTab === 'training' && (
        <div className="training-content">
          <TrainingDrill
            drill={session.cards[currentDrillIndex]}
            onComplete={handleDrillComplete}
            onSkip={handleSkip}
            currentIndex={currentDrillIndex}
            totalDrills={session.cards.length}
          />
        </div>
      )}

      {activeTab === 'chat' && onSwitchToChat && (
        <div className="training-chat-placeholder">
          <p>Switch to chat tab to continue conversation</p>
        </div>
      )}

      <div className="session-footer">
        <button onClick={onClose} className="exit-session-btn">
          Exit Session
        </button>
      </div>
    </div>
  );
}

