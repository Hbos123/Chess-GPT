"use client";

import { useState } from "react";
import PersonalReviewCharts from "./PersonalReviewCharts";
import PersonalReviewReport from "./PersonalReviewReport";
import TrainingManager from "./TrainingManager";

interface PersonalReviewProps {
  onClose: () => void;
}

export default function PersonalReview({ onClose }: PersonalReviewProps) {
  const [username, setUsername] = useState("");
  const [platform, setPlatform] = useState<"chess.com" | "lichess" | "combined">("chess.com");
  const [query, setQuery] = useState("");
  const [gamesToAnalyze, setGamesToAnalyze] = useState(3); // Default to 3 games
  const [analysisDepth, setAnalysisDepth] = useState(15); // Default to depth 15 (faster)
  const [isLoading, setIsLoading] = useState(false);
  const [progress, setProgress] = useState("");
  const [games, setGames] = useState<any[]>([]);
  const [analysisData, setAnalysisData] = useState<any>(null);
  const [report, setReport] = useState<string>("");
  const [error, setError] = useState("");
  const [step, setStep] = useState<"input" | "fetching" | "analyzing" | "results">("input");
  const [showTraining, setShowTraining] = useState(false);
  const [analyzedGamesForTraining, setAnalyzedGamesForTraining] = useState<any[]>([]);

  const handleFetchGames = async () => {
    if (!username.trim()) {
      setError("Please enter a username");
      return;
    }

    setIsLoading(true);
    setError("");
    setProgress("Fetching games...");
    setStep("fetching");

    try {
      const response = await fetch("http://localhost:8000/fetch_player_games", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, platform }),
      });

      if (!response.ok) {
        throw new Error("Failed to fetch games");
      }

      const data = await response.json();
      setGames(data.games);
      setProgress(`Fetched ${data.games.length} games`);
      
      if (data.games.length === 0) {
        setError("No games found for this player");
        setIsLoading(false);
        setStep("input");
        return;
      }

      // Auto-proceed to query step
      setTimeout(() => {
        setStep("input");
        setIsLoading(false);
      }, 1000);
    } catch (err) {
      console.error("Fetch error:", err);
      setError("Failed to fetch games. Make sure backend is running and username is correct.");
      setIsLoading(false);
      setStep("input");
    }
  };

  const handleAnalyze = async () => {
    if (!query.trim()) {
      setError("Please enter a question or analysis request");
      return;
    }

    if (games.length === 0) {
      setError("No games loaded. Please fetch games first.");
      return;
    }

    setIsLoading(true);
    setError("");
    setStep("analyzing");
    setProgress("Planning analysis...");

    try {
      // Step 1: LLM Planner
      setProgress("Understanding your question...");
      const planResponse = await fetch("http://localhost:8000/plan_personal_review", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, games }),
      });

      if (!planResponse.ok) {
        throw new Error("Failed to plan analysis");
      }

      const plan = await planResponse.json();
      
      // Override with user's selection
      plan.games_to_analyze = gamesToAnalyze;
      plan.analysis_depth = analysisDepth;
      
      setProgress(`Analyzing ${gamesToAnalyze} games (depth ${analysisDepth})...`);

      // Step 2: Aggregate analysis
      setProgress("Running deep analysis...");
      const aggregateResponse = await fetch("http://localhost:8000/aggregate_personal_review", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ plan, games }),
      });

      if (!aggregateResponse.ok) {
        throw new Error("Failed to aggregate data");
      }

      const aggregatedData = await aggregateResponse.json();
      setAnalysisData(aggregatedData);
      
      // Store analyzed games for training (they're embedded in the aggregation response)
      // We need to pass them through the plan response
      setAnalyzedGamesForTraining(aggregatedData.analyzed_games || []);
      
      setProgress("Generating insights...");

      // Step 3: LLM Reporter
      const reportResponse = await fetch("http://localhost:8000/generate_personal_report", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, plan, data: aggregatedData }),
      });

      if (!reportResponse.ok) {
        throw new Error("Failed to generate report");
      }

      const reportData = await reportResponse.json();
      setReport(reportData.report);
      setProgress("Analysis complete!");
      setStep("results");
    } catch (err) {
      console.error("Analysis error:", err);
      setError("Analysis failed. Please try again or rephrase your question.");
      setStep("input");
    } finally {
      setIsLoading(false);
    }
  };

  const resetAnalysis = () => {
    setStep("input");
    setQuery("");
    setAnalysisData(null);
    setReport("");
    setError("");
  };

  return (
    <div className="personal-review-modal-overlay" onClick={onClose}>
      <div className="personal-review-modal" onClick={(e) => e.stopPropagation()}>
        <div className="personal-review-header">
          <h2>🎯 Personal Chess Review</h2>
          <button className="close-button" onClick={onClose}>×</button>
        </div>

        <div className="personal-review-content">
          {step === "input" && (
            <>
              {/* Step 1: Username & Platform */}
              <div className="review-section">
                <h3>Player Information</h3>
                <div className="input-group">
                  <input
                    type="text"
                    placeholder="Enter username"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    className="username-input"
                    disabled={games.length > 0}
                  />
                  <div className="platform-buttons">
                    <button
                      className={`platform-btn ${platform === "chess.com" ? "active" : ""}`}
                      onClick={() => setPlatform("chess.com")}
                      disabled={games.length > 0}
                    >
                      Chess.com
                    </button>
                    <button
                      className={`platform-btn ${platform === "lichess" ? "active" : ""}`}
                      onClick={() => setPlatform("lichess")}
                      disabled={games.length > 0}
                    >
                      Lichess
                    </button>
                    <button
                      className={`platform-btn ${platform === "combined" ? "active" : ""}`}
                      onClick={() => setPlatform("combined")}
                      disabled={games.length > 0}
                    >
                      Combined
                    </button>
                  </div>
                  {games.length === 0 ? (
                    <button
                      className="fetch-games-btn"
                      onClick={handleFetchGames}
                      disabled={isLoading || !username.trim()}
                    >
                      {isLoading ? "Fetching..." : "Fetch Games"}
                    </button>
                  ) : (
                    <div className="games-fetched">
                      ✓ {games.length} games loaded
                      <button
                        className="reset-btn"
                        onClick={() => {
                          setGames([]);
                          setUsername("");
                        }}
                      >
                        Reset
                      </button>
                    </div>
                  )}
                </div>
              </div>

              {/* Step 2: Natural Language Query */}
              {games.length > 0 && (
                <div className="review-section">
                  <h3>What would you like to know?</h3>
                  <textarea
                    placeholder="Examples:&#10;• Why am I stuck at my current rating?&#10;• How has my middlegame improved?&#10;• Which openings should I avoid?&#10;• Do I play worse in endgames?"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    className="query-input"
                    rows={5}
                  />
                  
                  <div className="games-to-analyze-section">
                    <label htmlFor="games-count">Number of games to analyze:</label>
                    <select
                      id="games-count"
                      value={gamesToAnalyze}
                      onChange={(e) => setGamesToAnalyze(Number(e.target.value))}
                      className="games-count-select"
                    >
                      <option value={3}>3 games</option>
                      <option value={5}>5 games</option>
                      <option value={10}>10 games</option>
                      <option value={25}>25 games</option>
                      <option value={50}>50 games</option>
                      <option value={Math.min(games.length, 100)}>
                        All {Math.min(games.length, 100)} games
                      </option>
                    </select>
                    
                    <label htmlFor="depth-input">Stockfish depth (10-25):</label>
                    <input
                      id="depth-input"
                      type="number"
                      min="10"
                      max="25"
                      value={analysisDepth}
                      onChange={(e) => {
                        const val = Number(e.target.value);
                        // Clamp between 10 and 25
                        if (val >= 10 && val <= 25) {
                          setAnalysisDepth(val);
                        } else if (val < 10) {
                          setAnalysisDepth(10);
                        } else if (val > 25) {
                          setAnalysisDepth(25);
                        }
                      }}
                      className="depth-input"
                      placeholder="15"
                    />
                    
                    <div className="games-count-note">
                      ⏱️ Estimated time: ~{Math.ceil(gamesToAnalyze * (analysisDepth <= 12 ? 2 : analysisDepth <= 15 ? 3 : analysisDepth <= 18 ? 5 : analysisDepth <= 20 ? 8 : 10))} minutes
                      <br />
                      💡 Depth 15 recommended for balance of speed and accuracy
                    </div>
                  </div>
                  
                  <button
                    className="analyze-btn"
                    onClick={handleAnalyze}
                    disabled={isLoading || !query.trim()}
                  >
                    {isLoading ? "Analyzing..." : `Analyze ${gamesToAnalyze} Games`}
                  </button>
                </div>
              )}

              {error && (
                <div className="error-message">
                  ⚠️ {error}
                </div>
              )}
            </>
          )}

          {(step === "fetching" || step === "analyzing") && (
            <div className="progress-section">
              <div className="spinner"></div>
              <p className="progress-text">{progress}</p>
            </div>
          )}

          {step === "results" && analysisData && report && (
            <div className="results-section">
              <div className="results-header-actions">
                <button className="new-query-btn" onClick={resetAnalysis}>
                  ← New Query
                </button>
                <button
                  className="generate-training-btn-header"
                  onClick={() => setShowTraining(true)}
                >
                  🎯 Generate Training from Results
                </button>
              </div>

              <PersonalReviewReport
                report={report}
                data={analysisData}
                query={query}
              />

              <PersonalReviewCharts data={analysisData} />
            </div>
          )}
          
          {showTraining && analyzedGamesForTraining.length > 0 && (
            <TrainingManager
              onClose={() => setShowTraining(false)}
              initialAnalyzedGames={analyzedGamesForTraining}
              initialUsername={username}
            />
          )}
        </div>
      </div>
    </div>
  );
}

