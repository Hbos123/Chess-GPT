"use client";

import { useState } from "react";
import TrainingSession from "./TrainingSession";
import { getBackendBase } from "@/lib/backendBase";

interface TrainingManagerProps {
  onClose: () => void;
  initialAnalyzedGames?: any[];  // From Personal Review
  initialUsername?: string;
  onCreateNewTab?: (params: any) => void;
  onCloseAll?: () => void;
}

export default function TrainingManager({
  onClose,
  initialAnalyzedGames,
  initialUsername,
  onCreateNewTab,
  onCloseAll,
}: TrainingManagerProps) {
  const BACKEND_BASE = getBackendBase();
  const [username, setUsername] = useState(initialUsername || "");
  const [mode, setMode] = useState<"feed-through" | "standalone">(
    initialAnalyzedGames ? "feed-through" : "standalone"
  );
  const [trainingQuery, setTrainingQuery] = useState("");
  const [analyzedGames, setAnalyzedGames] = useState(initialAnalyzedGames || []);
  const [session, setSession] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [searchCriteria, setSearchCriteria] = useState<string[]>([]);
  const [progressMessage, setProgressMessage] = useState("");

  const handleGenerateTraining = async () => {
    if (!username.trim()) {
      setError("Please enter a username");
      return;
    }

    if (!trainingQuery.trim()) {
      setError("Please enter what you want to practice");
      return;
    }

    if (analyzedGames.length === 0) {
      setError("No analyzed games available");
      return;
    }

    setIsLoading(true);
    setError("");
    setSearchCriteria([]);
    setProgressMessage("Analyzing your query...");

    try {
      // Create training session
      setProgressMessage("Creating personalized training session...");
      const response = await fetch(`${BACKEND_BASE}/create_training_session`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username,
          analyzed_games: analyzedGames,
          training_query: trainingQuery,
          mode: "focused"
        })
      });

      if (!response.ok) {
        throw new Error("Failed to create training session");
      }

      const sessionData = await response.json();
      
      // Store and display search criteria
      if (sessionData.search_criteria) {
        setSearchCriteria(sessionData.search_criteria);
      }
      
      // Check if empty session
      if (sessionData.empty || sessionData.total_cards === 0) {
        setError(sessionData.message || "No relevant drills found. Try a broader query or different focus.");
        setIsLoading(false);
        return;
      }
      
      setProgressMessage("");

      // Prefer launching into the main app tab system so this modal closes and the user gets the full UX.
      if (onCreateNewTab) {
        const firstFen =
          sessionData?.cards?.[0]?.fen ||
          sessionData?.cards?.[0]?.position?.fen ||
          "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

        onCreateNewTab({
          action: "new_tab",
          title: `Training: ${trainingQuery.trim().slice(0, 40)}`,
          type: "training",
          fen: firstFen,
          pgn: "",
          trainingSession: sessionData,
        });

        // Close both this modal and its parent (Personal Review) if provided.
        if (onCloseAll) onCloseAll();
        else onClose();
        return;
      }

      setSession(sessionData);
    } catch (err) {
      console.error("Training generation error:", err);
      setError("Failed to generate training. Check backend logs.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleSessionComplete = (results: any) => {
    console.log("Session complete:", results);
    setSession(null);
    setTrainingQuery("");
  };

  if (session) {
    return (
      <div className="training-manager-modal-overlay" onClick={onClose}>
        <div className="training-manager-modal" onClick={(e) => e.stopPropagation()}>
          <TrainingSession
            session={session}
            username={username}
            onComplete={handleSessionComplete}
            onClose={() => setSession(null)}
          />
        </div>
      </div>
    );
  }

  return (
    <div className="training-manager-modal-overlay" onClick={onClose}>
      <div className="training-manager-modal" onClick={(e) => e.stopPropagation()}>
        <div className="training-manager-header">
          <h2>🎯 Training & Drills</h2>
          <button className="close-button" onClick={onClose}>×</button>
        </div>

        <div className="training-manager-content">
          {mode === "feed-through" && (
            <div className="feed-through-info">
              ✓ Using {analyzedGames.length} analyzed games from Personal Review
            </div>
          )}

          <div className="training-section">
            <h3>Training Configuration</h3>
            
            {mode === "feed-through" && analyzedGames.length > 0 && (
              <div className="training-hint">
                💡 The system will search through {analyzedGames.length} analyzed games to find positions matching your query.
                Be specific! Examples:
                <ul>
                  <li>Middlegame tactical mistakes with forks</li>
                  <li>Endgame technique errors</li>
                  <li>Opening mistakes in my Sicilian</li>
                  <li>Critical moments I got right (to reinforce)</li>
                </ul>
              </div>
            )}
            
            <div className="input-group">
              <label>Username (for progress tracking):</label>
              <input
                type="text"
                placeholder="Enter your username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="username-input"
                disabled={!!initialUsername}
              />
              
              <label>What do you want to practice?</label>
              <textarea
                placeholder="Examples:&#10;• Middlegame tactical mistakes&#10;• Fork and pin patterns&#10;• Endgame rook technique&#10;• Critical decisions in Italian Game&#10;• Time pressure errors"
                value={trainingQuery}
                onChange={(e) => setTrainingQuery(e.target.value)}
                className="query-input"
                rows={4}
              />

              <button
                className="generate-training-btn"
                onClick={handleGenerateTraining}
                disabled={isLoading || !username.trim() || !trainingQuery.trim()}
              >
                {isLoading ? "Generating..." : "Generate Training Session"}
              </button>
            </div>

            {error && (
              <div className="error-message">
                ⚠️ {error}
              </div>
            )}
          </div>

          {isLoading && (
            <div className="progress-section">
              <div className="spinner"></div>
              <p className="progress-text">{progressMessage}</p>
              
              {searchCriteria.length > 0 && (
                <div className="search-criteria-display">
                  <h4>🔍 Searching For:</h4>
                  <ul>
                    {searchCriteria.map((criteria, idx) => (
                      <li key={idx}>{criteria}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
          
          {searchCriteria.length > 0 && !isLoading && !session && (
            <div className="criteria-info">
              <h4>🔍 Search Criteria Used:</h4>
              <ul>
                {searchCriteria.map((criteria, idx) => (
                  <li key={idx}>{criteria}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

