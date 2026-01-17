"use client";

import { useState, useEffect } from "react";
import PersonalReviewCharts from "./PersonalReviewCharts";
import PersonalReviewReport from "./PersonalReviewReport";
import TrainingManager from "./TrainingManager";
import { useAuth } from "@/contexts/AuthContext";
import { getBackendBase } from "@/lib/backendBase";

interface PersonalReviewProps {
  onClose: () => void;
}

export default function PersonalReview({ onClose }: PersonalReviewProps) {
  console.log("[PersonalReview] 🎬 Component rendering");
  
  const { user, loading: authLoading } = useAuth();
  console.log("[PersonalReview] 👤 Auth context", { 
    hasUser: !!user, 
    userId: user?.id, 
    userEmail: user?.email,
    authLoading: authLoading
  });
  
  const backendBase = getBackendBase();
  console.log("[PersonalReview] 🔗 Backend base URL:", backendBase);
  
  const [username, setUsername] = useState("");
  const [platform, setPlatform] = useState<"chess.com" | "lichess" | "combined">("chess.com");
  const [query, setQuery] = useState("");
  const [gamesToAnalyze, setGamesToAnalyze] = useState(3); // Default to 3 games
  const [analysisDepth, setAnalysisDepth] = useState(15); // Default to depth 15 (faster)
  const [isLoading, setIsLoading] = useState(false);
  const [progress, setProgress] = useState("");
  const [progressInfo, setProgressInfo] = useState<{
    current: number;
    total: number;
    message: string;
    status?: string;
  } | null>(null);
  const [games, setGames] = useState<any[]>([]);
  const [analysisData, setAnalysisData] = useState<any>(null);
  const [report, setReport] = useState<string>("");
  const [error, setError] = useState("");
  const [step, setStep] = useState<"input" | "fetching" | "analyzing" | "results">("input");
  const [showTraining, setShowTraining] = useState(false);
  const [analyzedGamesForTraining, setAnalyzedGamesForTraining] = useState<any[]>([]);
  const [gameSource, setGameSource] = useState<"fetched" | "analyzed" | null>(null); // Track game source

  const maxGamesSelectable = Math.min(games.length, 100);
  const showRolling60Option = games.length >= 60;
  
  console.log("[PersonalReview] 📊 Current state", {
    step,
    isLoading,
    gamesCount: games.length,
    gameSource,
    hasProgress: !!progress,
    hasError: !!error
  });

  // Reset step and loading state on mount to prevent stuck states
  useEffect(() => {
    console.log("[PersonalReview] 🚀 Component mounted - resetting state");
    setStep("input");
    setIsLoading(false);
    setProgressInfo(null);
    setError("");
    console.log("[PersonalReview] ✅ Initial state reset complete");
    
    return () => {
      console.log("[PersonalReview] 🛑 Component unmounting");
    };
  }, []); // Only run on mount

  // Load previously analyzed games from Supabase on mount (should be instant)
  useEffect(() => {
    console.log("[PersonalReview] 🔄 loadAnalyzedGames useEffect triggered", { 
      userId: user?.id, 
      backendBase,
      hasUser: !!user,
      authLoading: authLoading,
      userObject: user ? { id: user.id, email: user.email } : null
    });
    
    // Wait for auth to finish loading before trying to load games
    if (authLoading) {
      console.log("[PersonalReview] ⏳ Auth still loading - waiting...");
      setIsLoading(true);
      setProgress("Checking authentication...");
      return;
    }
    
    const loadAnalyzedGames = async () => {
      console.log("[PersonalReview] 📥 loadAnalyzedGames function called", { 
        userId: user?.id, 
        backendBase,
        authLoading: authLoading
      });
      
      if (!user?.id) {
        console.log("[PersonalReview] ⚠️ No user ID - user not authenticated", {
          user: user,
          userId: user?.id,
          userKeys: user ? Object.keys(user) : [],
          authLoading: authLoading
        });
        setProgress("Please sign in to view your analyzed games");
        setIsLoading(false);
        return;
      }
      
      // Add a loading state for initial load
      console.log("[PersonalReview] 🔄 Setting loading state to true");
      setIsLoading(true);
      setProgress("Loading your analyzed games...");
      
      try {
        const url = `${backendBase}/profile/analyzed_games?user_id=${user.id}&limit=50`;
        console.log("[PersonalReview] 🌐 Fetching from:", url);
        
        // Add timeout to prevent hanging (10 seconds)
        const controller = new AbortController();
        const timeoutId = setTimeout(() => {
          console.log("[PersonalReview] ⏱️ Timeout triggered (10s) - aborting fetch");
          controller.abort();
        }, 10000);
        
        const fetchStartTime = Date.now();
        const response = await fetch(url, {
          signal: controller.signal
        });
        const fetchDuration = Date.now() - fetchStartTime;
        
        clearTimeout(timeoutId);
        console.log("[PersonalReview] ✅ Fetch completed", { 
          status: response.status, 
          ok: response.ok, 
          duration: `${fetchDuration}ms` 
        });
        
        if (response.ok) {
          const parseStartTime = Date.now();
          const data = await response.json();
          const parseDuration = Date.now() - parseStartTime;
          console.log("[PersonalReview] 📦 Response parsed", { 
            gamesCount: data.games?.length || 0, 
            hasGames: !!(data.games && data.games.length > 0),
            parseDuration: `${parseDuration}ms`
          });
          
          if (data.games && data.games.length > 0) {
            // Only set if no games are currently loaded
            if (games.length === 0) {
              console.log("[PersonalReview] 💾 Setting games state", { 
                count: data.games.length,
                firstGameId: data.games[0]?.id || data.games[0]?.game_id || "unknown"
              });
              setGames(data.games);
              setGameSource("analyzed");
              setProgress(`Loaded ${data.games.length} previously analyzed games from your account`);
              // If we have enough history, default the selector to 60 (rolling window)
              if (data.games.length >= 60) {
                console.log("[PersonalReview] 🎯 Setting gamesToAnalyze to 60 (rolling window)");
                setGamesToAnalyze(60);
              }
              console.log("[PersonalReview] ✅ Games loaded successfully");
            } else {
              console.log("[PersonalReview] ⏭️ Skipping setGames - games already loaded", { currentCount: games.length });
            }
          } else {
            // No games in Supabase - show helpful message
            console.log("[PersonalReview] 📭 No games found in Supabase");
            setProgress("No analyzed games found. Fetch games from Chess.com or Lichess to get started.");
            setGames([]);
            setGameSource(null);
          }
        } else {
          const errorText = await response.text();
          console.error("[PersonalReview] ❌ Fetch failed", { 
            status: response.status, 
            statusText: response.statusText,
            errorText: errorText.substring(0, 200)
          });
          setProgress("Could not load games from your account. You can still fetch new games.");
          setGames([]);
          setGameSource(null);
        }
      } catch (err: any) {
        if (err.name === 'AbortError') {
          console.error("[PersonalReview] ⏱️ Timeout error loading analyzed games");
          setProgress("Loading timed out. You can still fetch new games.");
        } else {
          console.error("[PersonalReview] ❌ Error loading analyzed games:", err);
          setProgress("Could not load games. You can still fetch new games.");
        }
        setGames([]);
        setGameSource(null);
      } finally {
        console.log("[PersonalReview] 🏁 loadAnalyzedGames finally block - resetting loading state");
        setIsLoading(false);
        // Ensure step is always "input" after loading (not stuck in "analyzing")
        setStep("input");
        console.log("[PersonalReview] ✅ loadAnalyzedGames complete - step set to 'input'");
      }
    };
    
    console.log("[PersonalReview] 🎬 Starting loadAnalyzedGames");
    loadAnalyzedGames();
  }, [user?.id, backendBase, authLoading]); // Add authLoading to deps

  const handleFetchGames = async () => {
    console.log("[PersonalReview] 🎮 handleFetchGames called", { username, platform });
    
    if (!username.trim()) {
      console.log("[PersonalReview] ⚠️ No username provided");
      setError("Please enter a username");
      return;
    }

    console.log("[PersonalReview] 🔄 Setting state for fetch", { 
      isLoading: true, 
      step: "fetching" 
    });
    setIsLoading(true);
    setError("");
    setProgress("Fetching games...");
    setStep("fetching");

    try {
      const url = `${backendBase}/fetch_player_games`;
      console.log("[PersonalReview] 🌐 Fetching games from:", url, { username, platform });
      
      const fetchStartTime = Date.now();
      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, platform }),
      });
      const fetchDuration = Date.now() - fetchStartTime;
      
      console.log("[PersonalReview] 📡 Fetch response received", { 
        status: response.status, 
        ok: response.ok,
        duration: `${fetchDuration}ms`
      });

      if (!response.ok) {
        const errorText = await response.text();
        console.error("[PersonalReview] ❌ Fetch failed", { 
          status: response.status,
          errorText: errorText.substring(0, 200)
        });
        throw new Error("Failed to fetch games");
      }

      const parseStartTime = Date.now();
      const data = await response.json();
      const parseDuration = Date.now() - parseStartTime;
      console.log("[PersonalReview] 📦 Games data parsed", { 
        gamesCount: data.games?.length || 0,
        parseDuration: `${parseDuration}ms`
      });
      
      // Clear any previously analyzed games when fetching new ones
      console.log("[PersonalReview] 💾 Setting games state", { 
        count: data.games?.length || 0,
        source: "fetched"
      });
      setGames(data.games);
      setGameSource("fetched");
      setProgress(`Fetched ${data.games.length} games`);
      
      if (data.games.length === 0) {
        console.log("[PersonalReview] 📭 No games found for player");
        setError("No games found for this player");
        setIsLoading(false);
        setStep("input");
        return;
      }

      // Auto-proceed to query step
      console.log("[PersonalReview] ⏱️ Scheduling transition to input step (1s delay)");
      setTimeout(() => {
        console.log("[PersonalReview] ✅ Transitioning to input step");
        setStep("input");
        setIsLoading(false);
      }, 1000);
    } catch (err) {
      console.error("[PersonalReview] ❌ Fetch error:", err);
      setError("Failed to fetch games. Make sure backend is running and username is correct.");
      setIsLoading(false);
      setStep("input");
    }
  };

  const handleAnalyze = async () => {
    console.log("[PersonalReview] handleAnalyze called", { 
      query: query.trim(), 
      gamesCount: games.length,
      gamesToAnalyze,
      analysisDepth 
    });
    
    if (!query.trim()) {
      console.warn("[PersonalReview] No query provided");
      setError("Please enter a question or analysis request");
      return;
    }

    if (games.length === 0) {
      console.warn("[PersonalReview] No games loaded");
      setError("No games loaded. Please fetch games first.");
      return;
    }

    console.log("[PersonalReview] Starting analysis...");
    setIsLoading(true);
    setError("");
    setStep("analyzing");
    setProgress("Planning analysis...");
    setProgressInfo(null);
    
    let eventSource: EventSource | null = null;

    try {
      // Step 1: LLM Planner
      console.log("[PersonalReview] 📋 Step 1: Planning analysis...");
      setProgress("Understanding your question...");
      
      const planUrl = `${backendBase}/plan_personal_review`;
      console.log("[PersonalReview] 🌐 Fetching plan from:", planUrl);
      
      const planStartTime = Date.now();
      const planResponse = await fetch(planUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, games }),
      });
      const planDuration = Date.now() - planStartTime;
      
      console.log("[PersonalReview] 📡 Plan response received", {
        status: planResponse.status,
        ok: planResponse.ok,
        duration: `${planDuration}ms`
      });

      if (!planResponse.ok) {
        const errorText = await planResponse.text();
        console.error("[PersonalReview] ❌ Plan request failed", {
          status: planResponse.status,
          statusText: planResponse.statusText,
          errorText: errorText.substring(0, 200)
        });
        throw new Error("Failed to plan analysis");
      }

      const planParseStart = Date.now();
      const plan = await planResponse.json();
      const planParseDuration = Date.now() - planParseStart;
      console.log("[PersonalReview] 📦 Plan received", {
        planKeys: Object.keys(plan),
        intent: plan.intent,
        parseDuration: `${planParseDuration}ms`
      });
      
      // Override with user's selection BEFORE sending to backend
      const finalPlan = {
        ...plan,
        games_to_analyze: gamesToAnalyze,
        analysis_depth: analysisDepth
      };
      
      console.log("[PersonalReview] 📝 Final plan prepared", {
        games_to_analyze: finalPlan.games_to_analyze,
        analysis_depth: finalPlan.analysis_depth,
        intent: finalPlan.intent
      });
      
      setProgress(`Analyzing ${gamesToAnalyze} games (depth ${analysisDepth})...`);

      // Step 2: Aggregate analysis with SSE progress updates
      const backendUrl = backendBase;
      const sessionId =
        (typeof crypto !== "undefined" && "randomUUID" in crypto)
          ? crypto.randomUUID()
          : `sess-${Date.now()}-${Math.random().toString(16).slice(2)}`;

      console.log("[PersonalReview] 🆔 Generated session ID:", sessionId);
      console.log("[PersonalReview] 📡 SSE URL:", `${backendUrl}/personal_review/progress/${sessionId}`);

      // Subscribe to progress BEFORE starting the long-running request.
      console.log("[PersonalReview] 📊 Setting initial progress info", {
        current: 0,
        total: gamesToAnalyze
      });
      setProgress("Starting analysis...");
      setProgressInfo({
        current: 0,
        total: gamesToAnalyze,
        message: "Starting analysis..."
      });

      try {
        const sseUrl = `${backendUrl}/personal_review/progress/${sessionId}`;
        console.log("[PersonalReview] 🔌 Creating EventSource", { sseUrl });
        eventSource = new EventSource(sseUrl);
        console.log(`[PersonalReview] ✅ EventSource created for session: ${sessionId}`);
        
        eventSource.onmessage = (event) => {
          try {
            console.log(`[PersonalReview] 📨 Raw SSE message received:`, event.data);
            const parseStart = Date.now();
            const data = JSON.parse(event.data);
            const parseDuration = Date.now() - parseStart;
            console.log(`[PersonalReview] 📦 Progress update parsed (${parseDuration}ms):`, data);
            
            const msg = String(data?.message || "");
            if (msg) {
              console.log(`[PersonalReview] 📝 Updating progress message:`, msg);
              setProgress(msg);
            }
            
            if (typeof data?.current === "number" && typeof data?.total === "number") {
              console.log(`[PersonalReview] 📊 Updating progressInfo: ${data.current}/${data.total}`);
              setProgressInfo({
                current: Math.max(0, data.current),
                total: Math.max(0, data.total),
                message: msg || progress,
                status: data?.status
              });
            } else if (msg) {
              console.log(`[PersonalReview] 📝 Updating progressInfo message only:`, msg);
              setProgressInfo((prev) => prev ? { ...prev, message: msg, status: data?.status } : prev);
            }
          } catch (e) {
            console.error("[PersonalReview] ❌ Error parsing progress update:", e, event.data);
          }
        };
        
        eventSource.onopen = () => {
          console.log(`[PersonalReview] ✅ SSE connection opened for session: ${sessionId}`);
        };
        
        eventSource.onerror = (e) => {
          console.error(`[PersonalReview] ❌ SSE error for session ${sessionId}:`, e);
          console.error(`[PersonalReview] EventSource readyState:`, eventSource?.readyState);
          // Don't hard-fail the flow if SSE hiccups; just keep going.
        };
      } catch (sseError) {
        console.error("[PersonalReview] ❌ Failed to create EventSource:", sseError);
        // Continue anyway - progress updates might not work but analysis can continue
      }

      console.log("[PersonalReview] 🔬 Step 2: Starting aggregate analysis...");
      setProgress("Running deep analysis...");
      
      const aggregateUrl = `${backendUrl}/aggregate_personal_review`;
      console.log("[PersonalReview] 🌐 Fetching aggregate analysis from:", aggregateUrl);
      
      const aggregateStartTime = Date.now();
      const aggregateResponse = await fetch(aggregateUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ plan: finalPlan, games, session_id: sessionId }),
      });
      const aggregateDuration = Date.now() - aggregateStartTime;
      
      console.log("[PersonalReview] 📡 Aggregate response received", {
        status: aggregateResponse.status,
        ok: aggregateResponse.ok,
        duration: `${aggregateDuration}ms`
      });

      if (!aggregateResponse.ok) {
        const errorText = await aggregateResponse.text();
        console.error("[PersonalReview] Aggregate request failed:", aggregateResponse.status, errorText);
        throw new Error("Failed to aggregate data");
      }

      const responseData = await aggregateResponse.json();
      console.log("[PersonalReview] Aggregate response received:", {
        hasSessionId: !!responseData.session_id,
        totalGamesAnalyzed: responseData.total_games_analyzed,
        hasError: !!responseData.error
      });
      
      const { session_id, ...aggregatedData } = responseData;
      
      // Check for errors
      if (aggregatedData.error) {
        console.error("[PersonalReview] Aggregate error:", aggregatedData.error);
        setError(aggregatedData.error);
        setStep("input");
        setIsLoading(false);
        return;
      }
      
      if (aggregatedData.total_games_analyzed === 0) {
        console.warn("[PersonalReview] No games were analyzed");
        setError("No games could be analyzed. Please try different games or check your query.");
        setStep("input");
        setIsLoading(false);
        return;
      }
      
      console.log("[PersonalReview] Analysis complete, updating UI...");
      // Ensure UI reflects completion even if SSE lagged.
      setProgressInfo((prev) => {
        const total = prev?.total ?? aggregatedData?.total_games_analyzed ?? gamesToAnalyze;
        console.log("[PersonalReview] Setting progressInfo to completion:", { current: total, total });
        return {
          current: total,
          total,
          message: "Analysis complete!",
          status: "completed"
        };
      });
      
      setAnalysisData(aggregatedData);
      
      // Store analyzed game IDs for training (frontend can fetch full data from Supabase if needed)
      // For now, we'll pass empty array - training system can fetch by IDs if needed
      setAnalyzedGamesForTraining([]);
      
      console.log("[PersonalReview] Step 3: Generating report...");
      setProgress("Generating insights...");

      // Step 3: LLM Reporter
      const reportResponse = await fetch(`${backendBase}/generate_personal_report`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, plan: finalPlan, data: aggregatedData }),
      });

      if (!reportResponse.ok) {
        console.error("[PersonalReview] Report generation failed:", reportResponse.status);
        throw new Error("Failed to generate report");
      }

      const reportData = await reportResponse.json();
      console.log("[PersonalReview] Report generated, length:", reportData.report?.length || 0);
      setReport(reportData.report);
      setProgress("Analysis complete!");
      
      // Ensure progressInfo is set to completion state before showing results
      setProgressInfo((prev) => {
        if (!prev) {
          // If progressInfo was lost, recreate it from aggregatedData
          const total = aggregatedData?.total_games_analyzed ?? gamesToAnalyze;
          console.log("[PersonalReview] Recreating progressInfo from aggregatedData:", { current: total, total });
          return {
            current: total,
            total,
            message: "Analysis complete!",
            status: "completed"
          };
        }
        // Update existing progressInfo to completion
        console.log("[PersonalReview] Updating existing progressInfo to completion");
        return {
          ...prev,
          current: prev.total,
          message: "Analysis complete!",
          status: "completed"
        };
      });
      
      console.log("[PersonalReview] Transitioning to results step");
      setStep("results");
    } catch (err) {
      console.error("[PersonalReview] ❌ Analysis error:", err);
      console.error("[PersonalReview] Error details:", {
        name: (err as any)?.name,
        message: (err as any)?.message,
        stack: (err as any)?.stack?.substring(0, 500)
      });
      setError("Analysis failed. Please try again or rephrase your question.");
      setStep("input");
    } finally {
      // Close SSE connection
      if (eventSource) {
        console.log("[PersonalReview] 🔌 Closing SSE connection");
        eventSource.close();
        console.log("[PersonalReview] ✅ SSE connection closed");
      }
      console.log("[PersonalReview] 🔄 Resetting loading state");
      setIsLoading(false);
      console.log("[PersonalReview] 🏁 Analysis flow complete");
    }
  };

  const resetAnalysis = () => {
    setStep("input");
    setQuery("");
    setAnalysisData(null);
    setReport("");
    setError("");
    setProgressInfo(null);
    setProgress("");
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
                  {/* Show loading state during auth check or initial Supabase fetch */}
                  {(authLoading || (isLoading && games.length === 0 && !gameSource)) && (
                    <div className="loading-message" style={{ marginBottom: '12px', color: '#888', fontSize: '14px' }}>
                      {authLoading ? "Checking authentication..." : (progress || "Loading your analyzed games...")}
                    </div>
                  )}
                  
                  {/* Show status message when games are loaded or when there are no games (and auth is done) */}
                  {!authLoading && !isLoading && (
                    <div className="status-message" style={{ marginBottom: '12px', fontSize: '14px', color: games.length > 0 ? '#4caf50' : '#888' }}>
                      {games.length > 0 ? (
                        <span>✓ {games.length} games loaded{gameSource ? ` (${gameSource === "analyzed" ? "from your account" : "fetched"})` : ""}</span>
                      ) : (
                        <span>{progress || "No games loaded. Fetch games from Chess.com or Lichess to get started."}</span>
                      )}
                    </div>
                  )}
                  
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
                      <button
                        className="reset-btn"
                        onClick={() => {
                          setGames([]);
                          setUsername("");
                          setGameSource(null);
                          setProgress("");
                          setGamesToAnalyze(3);
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
                  
                  {/* Query Suggestions */}
                  <div className="query-suggestions">
                    <div className="suggestion-label">Quick questions:</div>
                    <div className="suggestion-buttons">
                      {[
                        "Why am I stuck at my current rating?",
                        "How has my middlegame improved?",
                        "Which openings should I avoid?",
                        "Do I play worse in endgames?",
                        "What are my biggest weaknesses?",
                        "How is my time management?"
                      ].map((suggestion) => (
                        <button
                          key={suggestion}
                          className="suggestion-btn"
                          onClick={() => setQuery(suggestion)}
                          disabled={isLoading}
                        >
                          {suggestion}
                        </button>
                      ))}
                    </div>
                  </div>
                  
                  <textarea
                    placeholder="Or type your own question..."
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
                      {showRolling60Option && <option value={60}>60 games (rolling window)</option>}
                      <option value={50}>50 games</option>
                      <option value={maxGamesSelectable}>
                        All {maxGamesSelectable} games
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
                    {isLoading ? "Analyzing..." : `Analyze ${gamesToAnalyze}${gamesToAnalyze === 60 ? " (Rolling)" : ""} Games`}
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
              {progressInfo && progressInfo.total > 0 && (
                <div className="personal-review-progress" aria-label="Analysis progress">
                  <div className="personal-review-progress-meta">
                    <span>{progressInfo.message || "Analyzing games..."}</span>
                    <span>{Math.min(progressInfo.current, progressInfo.total)}/{progressInfo.total} ({Math.round((Math.min(progressInfo.current, progressInfo.total) / progressInfo.total) * 100)}%)</span>
                  </div>
                  <div className="personal-review-progress-bar">
                    <div
                      className="personal-review-progress-fill"
                      style={{
                        width: `${Math.round((Math.min(progressInfo.current, progressInfo.total) / progressInfo.total) * 100)}%`,
                      }}
                    />
                  </div>
                </div>
              )}
              {(!progressInfo || progressInfo.total === 0) && (
                <p className="progress-text">{progress}</p>
              )}
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
                  disabled={analyzedGamesForTraining.length === 0}
                  title={analyzedGamesForTraining.length === 0 ? "Training generation requires analyzed game payloads (coming next)." : "Generate training from results"}
                >
                  🎯 Generate Training from Results
                </button>
              </div>

              {/* Player Information at top of overview */}
              <div className="review-section" style={{ marginTop: "1rem", marginBottom: "1.5rem" }}>
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
                      ✓ {games.length} games loaded{gameSource ? ` (${gameSource === "analyzed" ? "from your account" : "fetched"})` : ""}
                      <button
                        className="reset-btn"
                        onClick={() => {
                          setGames([]);
                          setUsername("");
                          setGameSource(null);
                          setProgress("");
                          setGamesToAnalyze(3);
                        }}
                      >
                        Reset
                      </button>
                    </div>
                  )}
                </div>
                
                {/* Quick Analyze Section - Show if games are loaded */}
                {games.length > 0 && (
                  <div className="quick-analyze-section" style={{ marginTop: "1rem", paddingTop: "1rem", borderTop: "1px solid var(--border-color)" }}>
                    <h4>Quick Analysis</h4>
                    <textarea
                      placeholder="Enter your analysis question..."
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                      className="query-input"
                      rows={3}
                      style={{ marginBottom: "0.75rem" }}
                    />
                    <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", flexWrap: "wrap" }}>
                      <select
                        value={gamesToAnalyze}
                        onChange={(e) => setGamesToAnalyze(Number(e.target.value))}
                        className="games-count-select"
                        style={{ minWidth: "120px" }}
                      >
                        <option value={3}>3 games</option>
                        <option value={5}>5 games</option>
                        <option value={10}>10 games</option>
                        <option value={25}>25 games</option>
                        {showRolling60Option && <option value={60}>60 games (rolling)</option>}
                        <option value={50}>50 games</option>
                        <option value={maxGamesSelectable}>All {maxGamesSelectable} games</option>
                      </select>
                      <button
                        className="analyze-btn"
                        onClick={handleAnalyze}
                        disabled={isLoading || !query.trim()}
                        style={{ flex: "1", minWidth: "200px" }}
                      >
                        {isLoading ? "Analyzing..." : `Analyze ${gamesToAnalyze}${gamesToAnalyze === 60 ? " (Rolling)" : ""} Games`}
                      </button>
                    </div>
                  </div>
                )}
              </div>

              {/* Progress bar at top of overview section - always show if we have analysis data */}
              {(progressInfo && progressInfo.total > 0) || (analysisData && analysisData.total_games_analyzed) ? (
                <div className="personal-review-progress-overview">
                  <div className="personal-review-progress-meta">
                    <span>{progressInfo?.message || "Analysis complete"}</span>
                    <span>
                      {progressInfo 
                        ? `${Math.min(progressInfo.current, progressInfo.total)}/${progressInfo.total} (${Math.round((Math.min(progressInfo.current, progressInfo.total) / progressInfo.total) * 100)}%)`
                        : analysisData?.total_games_analyzed 
                          ? `${analysisData.total_games_analyzed}/${analysisData.total_games_analyzed} (100%)`
                          : "100%"
                      }
                    </span>
                  </div>
                  <div className="personal-review-progress-bar">
                    <div
                      className="personal-review-progress-fill"
                      style={{
                        width: progressInfo && progressInfo.total > 0
                          ? `${Math.round((Math.min(progressInfo.current, progressInfo.total) / progressInfo.total) * 100)}%`
                          : "100%"
                      }}
                    />
                  </div>
                </div>
              ) : null}

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

