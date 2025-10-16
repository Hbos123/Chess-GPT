"use client";

import { useState } from "react";

interface LessonBuilderProps {
  onStartLesson: (description: string, level: number) => void;
  onClose: () => void;
}

export default function LessonBuilder({ onStartLesson, onClose }: LessonBuilderProps) {
  const [description, setDescription] = useState("");
  const [level, setLevel] = useState(1500);
  const [showLevelInfo, setShowLevelInfo] = useState(false);

  const handleSubmit = () => {
    if (description.trim()) {
      onStartLesson(description, level);
    }
  };

  const levelRanges = [
    { range: "900-1200", label: "Beginner", desc: "Basic tactics and rules" },
    { range: "1200-1700", label: "Club Player", desc: "Combinations and plans" },
    { range: "1700-2000", label: "Advanced", desc: "Strategic tradeoffs" },
    { range: "2000+", label: "Expert", desc: "Deep calculation and nuance" }
  ];

  return (
    <div className="lesson-builder-overlay" onClick={onClose}>
      <div className="lesson-builder-modal" onClick={(e) => e.stopPropagation()}>
        <div className="lesson-builder-header">
          <h2>📚 Create Custom Lesson</h2>
          <button onClick={onClose} className="close-button">×</button>
        </div>

        <div className="lesson-builder-body">
          <div className="form-group">
            <label>What would you like to learn?</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Example: 'I want to learn about isolated queen pawns and how to use them' or 'Teach me rook endgames' or 'Help me understand minority attacks'"
              rows={4}
              className="lesson-description-input"
            />
          </div>

          <div className="form-group">
            <label>
              Your Rating Level
              <button 
                className="info-button"
                onClick={() => setShowLevelInfo(!showLevelInfo)}
              >
                ℹ️
              </button>
            </label>
            <input
              type="range"
              min="900"
              max="2400"
              step="100"
              value={level}
              onChange={(e) => setLevel(parseInt(e.target.value))}
              className="level-slider"
            />
            <div className="level-display">{level}</div>
            
            {showLevelInfo && (
              <div className="level-info">
                {levelRanges.map((item, idx) => (
                  <div key={idx} className="level-info-item">
                    <strong>{item.range}</strong> - {item.label}: {item.desc}
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="lesson-examples">
            <h4>Example lesson requests:</h4>
            <ul>
              <li onClick={() => setDescription("Teach me about isolated queen pawns and how to play with them")}>
                📌 Isolated Queen Pawns
              </li>
              <li onClick={() => setDescription("I want to learn the Carlsbad structure and minority attack")}>
                📌 Minority Attack
              </li>
              <li onClick={() => setDescription("Help me understand knight outposts and how to establish them")}>
                📌 Knight Outposts
              </li>
              <li onClick={() => setDescription("Teach me basic tactical motifs like forks, pins, and skewers")}>
                📌 Basic Tactics
              </li>
              <li onClick={() => setDescription("Show me rook endgame techniques")}>
                📌 Rook Endgames
              </li>
            </ul>
          </div>
        </div>

        <div className="lesson-builder-footer">
          <button onClick={onClose} className="cancel-button">
            Cancel
          </button>
          <button 
            onClick={handleSubmit} 
            className="generate-button"
            disabled={!description.trim()}
          >
            🎓 Generate Lesson
          </button>
        </div>
      </div>
    </div>
  );
}

