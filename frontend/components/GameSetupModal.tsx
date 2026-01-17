"use client";

import { useState } from "react";

interface GameSetupModalProps {
  open: boolean;
  onClose: () => void;
  currentFen: string;
  onStartGame: (config: {
    userSide: "white" | "black";
    aiElo: number;
    startFromCurrent: boolean;
    newTab: boolean;
  }) => void;
}

export default function GameSetupModal({
  open,
  onClose,
  currentFen,
  onStartGame,
}: GameSetupModalProps) {
  const [userSide, setUserSide] = useState<"white" | "black">("white");
  const [aiElo, setAiElo] = useState(1500);
  const [startFromCurrent, setStartFromCurrent] = useState(true);

  if (!open) return null;

  const handleStart = () => {
    onStartGame({
      userSide,
      aiElo,
      startFromCurrent,
      newTab: !startFromCurrent,
    });
    onClose();
  };

  return (
    <div className="game-setup-overlay">
      <div className="game-setup-modal">
        <div className="game-setup-header">
          <h2>Play Against Chesster</h2>
          <button className="game-setup-close" onClick={onClose}>×</button>
        </div>

        <div className="game-setup-content">
          {/* Side Selection */}
          <div className="game-setup-section">
            <h3>Choose Your Side</h3>
            <div className="side-selection">
              <button
                className={`side-button ${userSide === "white" ? "active" : ""}`}
                onClick={() => setUserSide("white")}
              >
                White
              </button>
              <button
                className={`side-button ${userSide === "black" ? "active" : ""}`}
                onClick={() => setUserSide("black")}
              >
                Black
              </button>
            </div>
          </div>

          {/* ELO Slider */}
          <div className="game-setup-section">
            <h3>AI Difficulty (ELO)</h3>
            <div className="elo-slider-container">
              <input
                type="range"
                min="800"
                max="3200"
                step="100"
                value={aiElo}
                onChange={(e) => setAiElo(Number(e.target.value))}
                className="elo-slider"
              />
              <div className="elo-display">
                <span className="elo-value">{aiElo}</span>
                <span className="elo-label">ELO</span>
              </div>
            </div>
            <div className="elo-presets">
              <button
                className="elo-preset"
                onClick={() => setAiElo(800)}
              >
                Beginner
              </button>
              <button
                className="elo-preset"
                onClick={() => setAiElo(1500)}
              >
                Intermediate
              </button>
              <button
                className="elo-preset"
                onClick={() => setAiElo(2200)}
              >
                Advanced
              </button>
              <button
                className="elo-preset"
                onClick={() => setAiElo(3200)}
              >
                Master
              </button>
            </div>
          </div>

          {/* Start Options */}
          <div className="game-setup-section">
            <h3>Start From</h3>
            <div className="start-options">
              <button
                className={`start-option-button ${startFromCurrent ? "active" : ""}`}
                onClick={() => setStartFromCurrent(true)}
              >
                Current Position
              </button>
              <button
                className={`start-option-button ${!startFromCurrent ? "active" : ""}`}
                onClick={() => setStartFromCurrent(false)}
              >
                New Tab
              </button>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="game-setup-actions">
            <button className="game-setup-cancel" onClick={onClose}>
              Cancel
            </button>
            <button className="game-setup-start" onClick={handleStart}>
              Start Game
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

