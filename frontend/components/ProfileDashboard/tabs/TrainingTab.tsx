"use client";

import { useState, useEffect } from "react";
import TrainingSession from "@/components/TrainingSession";
import { getBackendBase } from "@/lib/backendBase";

interface TrainingTabProps {
  userId: string;
  backendBase?: string;
}

interface TagTransition {
  tag_name: string;
  count: number;
  accuracy: number;
  blunders: number;
  mistakes: number;
  significance_score?: number;
}

interface DrillSuggestion {
  id: string;
  category: "phase" | "opening" | "piece" | "tag_transition" | "time_bucket";
  filter_type: string;
  filter_value: string;
  transition_type?: "gained" | "lost" | "missed";
  accuracy: number;
  position_count?: number;
  position_avg_accuracy?: number;
  metadata: {
    phase?: { games_won: number; games_lost: number; games_drawn: number; win_rate: number };
    opening?: { frequency: number; wins: number; losses: number; win_rate: number };
    piece?: { count: number; moves: number };
    tag?: { count: number; blunders: number; mistakes: number; significance_score: number };
    time?: { count: number; blunders: number; mistakes: number; blunder_rate: number };
  };
  description: string;
  difficulty: string;
}

export default function TrainingTab({ userId, backendBase }: TrainingTabProps) {
  const BACKEND_BASE = backendBase || getBackendBase();
  
  // TEMPORARY: Dummy data for formatting - REMOVE AFTER FORMATTING IS DONE
  const DUMMY_SUGGESTIONS: DrillSuggestion[] = [
    {
      id: "phase-opening",
      category: "phase",
      filter_type: "phase",
      filter_value: "opening",
      accuracy: 82.1,
      position_count: 45,
      position_avg_accuracy: 82.1,
      metadata: {
        phase: { games_won: 45, games_lost: 20, games_drawn: 8, win_rate: 61.6 }
      },
      description: "Opening performance: 82.1% accuracy, 73 games",
      difficulty: "Intermediate"
    },
    {
      id: "phase-endgame",
      category: "phase",
      filter_type: "phase",
      filter_value: "endgame",
      accuracy: 81.3,
      position_count: 38,
      position_avg_accuracy: 81.3,
      metadata: {
        phase: { games_won: 38, games_lost: 15, games_drawn: 5, win_rate: 65.5 }
      },
      description: "Endgame performance: 81.3% accuracy, 58 games",
      difficulty: "Intermediate"
    },
    {
      id: "opening-sicilian",
      category: "opening",
      filter_type: "opening",
      filter_value: "Sicilian Defense",
      accuracy: 79.1,
      position_count: 45,
      position_avg_accuracy: 79.1,
      metadata: {
        opening: { frequency: 45, wins: 28, losses: 12, win_rate: 62.2 }
      },
      description: "Sicilian Defense: 79.1% accuracy, played 45 times",
      difficulty: "Intermediate"
    },
    {
      id: "opening-queens-gambit",
      category: "opening",
      filter_type: "opening",
      filter_value: "Queen's Gambit",
      accuracy: 76.8,
      position_count: 38,
      position_avg_accuracy: 76.8,
      metadata: {
        opening: { frequency: 38, wins: 21, losses: 14, win_rate: 55.3 }
      },
      description: "Queen's Gambit: 76.8% accuracy, played 38 times",
      difficulty: "Advanced"
    },
    {
      id: "piece-knight",
      category: "piece",
      filter_type: "piece",
      filter_value: "Knight",
      accuracy: 75.8,
      position_count: 456,
      position_avg_accuracy: 75.8,
      metadata: {
        piece: { count: 456, moves: 456 }
      },
      description: "Knight accuracy: 75.8%, 456 moves",
      difficulty: "Advanced"
    },
    {
      id: "tag-time-pressure",
      category: "tag_transition",
      filter_type: "tag_transition",
      filter_value: "Time Pressure",
      transition_type: "lost",
      accuracy: 68.2,
      position_count: 32,
      position_avg_accuracy: 68.2,
      metadata: {
        tag: { count: 32, blunders: 8, mistakes: 12, significance_score: 0.72 }
      },
      description: "Time Pressure: 68.2% accuracy, 32 positions",
      difficulty: "Advanced"
    },
    {
      id: "time-opening",
      category: "time_bucket",
      filter_type: "time_bucket",
      filter_value: "opening",
      accuracy: 82.1,
      position_count: 247,
      position_avg_accuracy: 82.1,
      metadata: {
        time: { count: 247, blunders: 8, mistakes: 15, blunder_rate: 3.2 }
      },
      description: "Opening time control: 82.1% accuracy, 247 positions",
      difficulty: "Intermediate"
    }
  ];

  const [loading, setLoading] = useState(false); // Set to false for dummy data
  const [suggestions, setSuggestions] = useState<DrillSuggestion[]>(DUMMY_SUGGESTIONS);
  const [activeSession, setActiveSession] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  
  // Collapsible section states
  const [isPhaseExpanded, setIsPhaseExpanded] = useState(true);
  const [isOpeningExpanded, setIsOpeningExpanded] = useState(true);
  const [isPieceExpanded, setIsPieceExpanded] = useState(true);
  const [isTagExpanded, setIsTagExpanded] = useState(true);
  const [isTimeExpanded, setIsTimeExpanded] = useState(true);

  // TEMPORARY: Comment out fetch - UNCOMMENT AFTER FORMATTING IS DONE
  /*
  useEffect(() => {
    if (!userId) return;
    loadDrillSuggestions();
  }, [userId]);

  const loadDrillSuggestions = async () => {
    setLoading(true);
    setError(null);
    
    try {
      // Fetch detailed analytics to get all category stats
      const baseUrl = BACKEND_BASE.replace(/\/$/, "");
      const response = await fetch(
        `${baseUrl}/profile/analytics/${userId}/detailed`,
        { cache: "no-store" }
      );

      if (!response.ok) {
        throw new Error(`Failed to load analytics: ${response.status}`);
      }

      const analytics = await response.json();
      const allSuggestions: DrillSuggestion[] = [];

      // 1. Phase Performance Section
      const phaseAnalytics = analytics?.phase_analytics || {};
      const phases = [
        { key: "opening", label: "Opening", data: phaseAnalytics.opening },
        { key: "middlegame", label: "Middlegame", data: phaseAnalytics.middlegame },
        { key: "endgame", label: "Endgame", data: phaseAnalytics.endgame },
      ];

      phases.forEach((phase) => {
        if (phase.data) {
          const totalGames = (phase.data.games_won || 0) + (phase.data.games_lost || 0) + (phase.data.games_drawn || 0);
          if (totalGames > 0) {
            allSuggestions.push({
              id: `phase-${phase.key}`,
              category: "phase",
              filter_type: "phase",
              filter_value: phase.key,
              accuracy: phase.data.accuracy || 0,
              metadata: {
                phase: {
                  games_won: phase.data.games_won || 0,
                  games_lost: phase.data.games_lost || 0,
                  games_drawn: phase.data.games_drawn || 0,
                  win_rate: phase.data.win_rate || 0,
                },
              },
              description: `${phase.label} performance: ${phase.data.accuracy.toFixed(1)}% accuracy, ${totalGames} games`,
              difficulty: phase.data.accuracy >= 75 ? "Intermediate" : "Advanced",
            });
          }
        }
      });

      // 2. Opening Repertoire Section
      const openingDetailed = analytics?.opening_detailed || {};
      const openingEntries = Object.entries(openingDetailed)
        .map(([name, data]: [string, any]) => ({
          name,
          frequency: data.frequency || 0,
          accuracy: data.avg_accuracy || 0,
          wins: data.wins || 0,
          losses: data.losses || 0,
          win_rate: data.win_rate || 0,
        }))
        .filter((o) => o.frequency > 0)
        .sort((a, b) => b.frequency - a.frequency)
        .slice(0, 10);

      openingEntries.forEach((opening) => {
        allSuggestions.push({
          id: `opening-${opening.name}`,
          category: "opening",
          filter_type: "opening",
          filter_value: opening.name,
          accuracy: opening.accuracy,
          metadata: {
            opening: {
              frequency: opening.frequency,
              wins: opening.wins,
              losses: opening.losses,
              win_rate: opening.win_rate,
            },
          },
          description: `${opening.name}: ${opening.accuracy.toFixed(1)}% accuracy, played ${opening.frequency} times`,
          difficulty: opening.accuracy >= 70 ? "Intermediate" : "Advanced",
        });
      });

      // 3. Piece Accuracy Section
      const pieceAccuracy = analytics?.piece_accuracy_detailed || {};
      const pieceAggregate = pieceAccuracy?.aggregate || {};
      const pieces = ["Pawn", "Knight", "Bishop", "Rook", "Queen", "King"];

      pieces.forEach((pieceName) => {
        const pieceData = pieceAggregate[pieceName];
        if (pieceData && pieceData.count > 0) {
          allSuggestions.push({
            id: `piece-${pieceName}`,
            category: "piece",
            filter_type: "piece",
            filter_value: pieceName,
            accuracy: pieceData.accuracy || 0,
            metadata: {
              piece: {
                count: pieceData.count || 0,
                moves: pieceData.count || 0,
              },
            },
            description: `${pieceName} accuracy: ${pieceData.accuracy.toFixed(1)}% over ${pieceData.count} moves`,
            difficulty: pieceData.accuracy >= 70 ? "Intermediate" : "Advanced",
          });
        }
      });

      // 4. Tag Transitions Section (existing)
      const tagTransitions = analytics?.tag_transitions || {};
      const gainedTags: TagTransition[] = Object.entries(tagTransitions.gained || {}).map(
        ([tag_name, data]: [string, any]) => ({
          tag_name,
          count: data.count || 0,
          accuracy: data.accuracy || 0,
          blunders: data.blunders || 0,
          mistakes: data.mistakes || 0,
          significance_score: data.significance_score || 0,
        })
      );

      const lostTags: TagTransition[] = Object.entries(tagTransitions.lost || {}).map(
        ([tag_name, data]: [string, any]) => ({
          tag_name,
          count: data.count || 0,
          accuracy: data.accuracy || 0,
          blunders: data.blunders || 0,
          mistakes: data.mistakes || 0,
          significance_score: data.significance_score || 0,
        })
      );

      const sortBySignificance = (a: TagTransition, b: TagTransition) => {
        const scoreA = a.significance_score || a.count;
        const scoreB = b.significance_score || b.count;
        return scoreB - scoreA;
      };

      gainedTags.sort(sortBySignificance);
      lostTags.sort(sortBySignificance);

      lostTags.slice(0, 5).forEach((tag) => {
        allSuggestions.push({
          id: `tag-lost-${tag.tag_name}`,
          category: "tag_transition",
          filter_type: "tag_transition",
          filter_value: tag.tag_name,
          transition_type: "lost",
          accuracy: tag.accuracy,
          metadata: {
            tag: {
              count: tag.count,
              blunders: tag.blunders,
              mistakes: tag.mistakes,
              significance_score: tag.significance_score || 0,
            },
          },
          description: `Lost "${tag.tag_name.replace(/_/g, " ")}" advantage ${tag.count} times with ${tag.accuracy.toFixed(0)}% accuracy`,
          difficulty: tag.blunders > tag.mistakes ? "Intermediate" : "Advanced",
        });
      });

      gainedTags.slice(0, 3).forEach((tag) => {
        allSuggestions.push({
          id: `tag-gained-${tag.tag_name}`,
          category: "tag_transition",
          filter_type: "tag_transition",
          filter_value: tag.tag_name,
          transition_type: "gained",
          accuracy: tag.accuracy,
          metadata: {
            tag: {
              count: tag.count,
              blunders: tag.blunders,
              mistakes: tag.mistakes,
              significance_score: tag.significance_score || 0,
            },
          },
          description: `Gained "${tag.tag_name.replace(/_/g, " ")}" advantage ${tag.count} times`,
          difficulty: "Intermediate",
        });
      });

      // 5. Time Management Section
      const timeBuckets = analytics?.time_buckets || {};
      const bucketOrder = ["<5s", "5-15s", "15-30s", "30s-1min", "1min-2min30", "2min30-5min", "5min+"];

      bucketOrder.forEach((bucket) => {
        const bucketData = timeBuckets[bucket];
        if (bucketData && bucketData.count > 0) {
          allSuggestions.push({
            id: `time-${bucket}`,
            category: "time_bucket",
            filter_type: "time_bucket",
            filter_value: bucket,
            accuracy: bucketData.accuracy || 0,
            metadata: {
              time: {
                count: bucketData.count || 0,
                blunders: bucketData.blunders || 0,
                mistakes: bucketData.mistakes || 0,
                blunder_rate: bucketData.blunder_rate || 0,
              },
            },
            description: `${bucket} time control: ${bucketData.accuracy.toFixed(1)}% accuracy, ${bucketData.count} moves`,
            difficulty: bucketData.blunder_rate > 0.1 ? "Advanced" : "Intermediate",
          });
        }
      });

      setSuggestions(allSuggestions);

      // Pre-fetch position counts for all suggestions (non-blocking)
      allSuggestions.forEach(async (suggestion) => {
        try {
          const params = new URLSearchParams({
            user_id: userId,
            filter_type: suggestion.filter_type,
            filter_value: suggestion.filter_value,
            limit: "1",
            min_cp_loss: "100",
          });
          
          if (suggestion.transition_type) {
            params.append("transition_type", suggestion.transition_type);
          }

          const countResponse = await fetch(
            `${baseUrl}/profile/positions/by-filter?${params.toString()}`,
            { cache: "no-store" }
          );
          
          if (countResponse.ok) {
            const countData = await countResponse.json();
            setSuggestions((prev) =>
              prev.map((s) =>
                s.id === suggestion.id
                  ? {
                      ...s,
                      position_count: countData.total_available || 0,
                      position_avg_accuracy: countData.average_accuracy,
                    }
                  : s
              )
            );
          }
        } catch (err) {
          // Silently fail - position count is nice to have but not critical
          console.debug(`[TrainingTab] Failed to fetch position count for ${suggestion.id}:`, err);
        }
      });
    } catch (err: any) {
      console.error("[TrainingTab] Failed to load drill suggestions:", err);
      setError(err.message || "Failed to load training suggestions");
    } finally {
      setLoading(false);
    }
  };
  */ // END TEMPORARY COMMENT - UNCOMMENT ABOVE AFTER FORMATTING IS DONE

  const handleStartDrill = async (suggestion: DrillSuggestion) => {
    try {
      setLoading(true);
      setError(null);

      // Fetch positions using the unified filter endpoint
      const baseUrl = BACKEND_BASE.replace(/\/$/, "");
      const params = new URLSearchParams({
        user_id: userId,
        filter_type: suggestion.filter_type,
        filter_value: suggestion.filter_value,
        limit: "20",
        min_cp_loss: "100",
      });
      
      if (suggestion.transition_type) {
        params.append("transition_type", suggestion.transition_type);
      }

      const positionsResponse = await fetch(
        `${baseUrl}/profile/positions/by-filter?${params.toString()}`,
        { cache: "no-store" }
      );

      if (!positionsResponse.ok) {
        throw new Error(`Failed to fetch positions: ${positionsResponse.status}`);
      }

      const positionsData = await positionsResponse.json();
      const positions = positionsData.positions || [];
      const totalAvailable = positionsData.total_available || 0;
      const avgAccuracy = positionsData.average_accuracy;

      if (positions.length === 0) {
        setError(`No positions found for ${suggestion.filter_type} "${suggestion.filter_value}". Try a different filter.`);
        setLoading(false);
        return;
      }

      // Update suggestion with actual position data
      const updatedSuggestion = {
        ...suggestion,
        position_count: totalAvailable,
        position_avg_accuracy: avgAccuracy,
      };
      
      // Update the suggestion in the list
      setSuggestions((prev) =>
        prev.map((s) => (s.id === suggestion.id ? updatedSuggestion : s))
      );

      // Generate drills from positions
      const drillsResponse = await fetch(`${baseUrl}/generate_drills`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          positions: positions,
          drill_types: ["tactics"],
          verify_ground_truth: true,
          verify_depth: 18,
        }),
      });

      if (!drillsResponse.ok) {
        throw new Error(`Failed to generate drills: ${drillsResponse.status}`);
      }

      const drillsData = await drillsResponse.json();
      const drills = drillsData.drills || [];

      if (drills.length === 0) {
        setError("No drills could be generated from these positions.");
        setLoading(false);
        return;
      }

      // Create training session
      const session = {
        session_id: `drill-${suggestion.id}-${Date.now()}`,
        total_cards: drills.length,
        cards: drills.map((drill: any, idx: number) => ({
          card_id: drill.card_id || `drill-${idx}`,
          fen: drill.fen,
          side_to_move: drill.side_to_move || "white",
          best_move_san: drill.best_move_san,
          best_move_uci: drill.best_move_uci,
          type: drill.type || "tactics",
          question: drill.question || `Find the best move`,
          hint: drill.hint || "",
          phase: drill.phase,
          opening: drill.opening,
          tag_transitions: drill.tag_transitions,
          piece_context: drill.piece_context,
        })),
      };

      setActiveSession(session);
    } catch (err: any) {
      console.error("[TrainingTab] Failed to start drill:", err);
      setError(err.message || "Failed to start drill");
    } finally {
      setLoading(false);
    }
  };

  // TEMPORARY: Stub function - REMOVE AFTER FORMATTING IS DONE
  const loadDrillSuggestions = async () => {
    // Do nothing - using dummy data
  };

  const handleSessionComplete = (results: any) => {
    console.log("[TrainingTab] Session complete:", results);
    setActiveSession(null);
    // TEMPORARY: Commented out - reload suggestions to update stats
    // loadDrillSuggestions();
  };

  const handleSessionClose = () => {
    setActiveSession(null);
  };

  if (activeSession) {
    return (
      <TrainingSession
        session={activeSession}
        username={userId}
        onComplete={handleSessionComplete}
        onClose={handleSessionClose}
      />
    );
  }

  // Group suggestions by category
  const suggestionsByCategory = {
    phase: suggestions.filter((s) => s.category === "phase"),
    opening: suggestions.filter((s) => s.category === "opening"),
    piece: suggestions.filter((s) => s.category === "piece"),
    tag_transition: suggestions.filter((s) => s.category === "tag_transition"),
    time_bucket: suggestions.filter((s) => s.category === "time_bucket"),
  };

  const categoryLabels = {
    phase: "Phase Performance",
    opening: "Opening Repertoire",
    piece: "Piece Accuracy",
    tag_transition: "Tag Transitions",
    time_bucket: "Time Management",
  };

  return (
    <div className="training-tab">
      <div className="tab-section">
        <h2>Personalized Training Plan</h2>
        <p className="tab-subtitle">
          Practice drills based on your performance across all analytics categories. Focus on areas that need improvement.
        </p>

        {error && (
          <div className="error-banner" style={{ padding: "12px", marginBottom: "16px", background: "#fee", color: "#c33", borderRadius: "4px" }}>
            {error}
          </div>
        )}

        {loading ? (
          <div style={{ padding: "40px", textAlign: "center" }}>
            <p>Loading drill suggestions...</p>
          </div>
        ) : suggestions.length === 0 ? (
          <div style={{ padding: "40px", textAlign: "center" }}>
            <p>No drill suggestions available yet. Analyze more games to get personalized recommendations.</p>
          </div>
        ) : (
          <>
            {/* Phase Performance Section */}
            {suggestionsByCategory.phase.length > 0 && (
              <div style={{ marginBottom: "32px" }}>
                <div 
                  style={{ 
                    display: "flex", 
                    justifyContent: "space-between", 
                    alignItems: "center", 
                    marginBottom: "16px",
                    cursor: "pointer"
                  }}
                  onClick={() => setIsPhaseExpanded(!isPhaseExpanded)}
                >
                  <h3 style={{ margin: 0, fontSize: "20px", fontWeight: 600 }}>{categoryLabels.phase}</h3>
                  <span style={{ fontSize: "14px", color: "#93c5fd" }}>
                    {isPhaseExpanded ? "▼" : "▶"}
                  </span>
                </div>
                {isPhaseExpanded && (
                  <div className="training-grid">
                    {suggestionsByCategory.phase.map((suggestion) => (
                      <DrillCard key={suggestion.id} suggestion={suggestion} onStart={handleStartDrill} loading={loading} />
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Opening Repertoire Section */}
            {suggestionsByCategory.opening.length > 0 && (
              <div style={{ marginBottom: "32px" }}>
                <div 
                  style={{ 
                    display: "flex", 
                    justifyContent: "space-between", 
                    alignItems: "center", 
                    marginBottom: "16px",
                    cursor: "pointer"
                  }}
                  onClick={() => setIsOpeningExpanded(!isOpeningExpanded)}
                >
                  <h3 style={{ margin: 0, fontSize: "20px", fontWeight: 600 }}>{categoryLabels.opening}</h3>
                  <span style={{ fontSize: "14px", color: "#93c5fd" }}>
                    {isOpeningExpanded ? "▼" : "▶"}
                  </span>
                </div>
                {isOpeningExpanded && (
                  <div className="training-grid">
                    {suggestionsByCategory.opening.map((suggestion) => (
                      <DrillCard key={suggestion.id} suggestion={suggestion} onStart={handleStartDrill} loading={loading} />
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Piece Accuracy Section */}
            {suggestionsByCategory.piece.length > 0 && (
              <div style={{ marginBottom: "32px" }}>
                <div 
                  style={{ 
                    display: "flex", 
                    justifyContent: "space-between", 
                    alignItems: "center", 
                    marginBottom: "16px",
                    cursor: "pointer"
                  }}
                  onClick={() => setIsPieceExpanded(!isPieceExpanded)}
                >
                  <h3 style={{ margin: 0, fontSize: "20px", fontWeight: 600 }}>{categoryLabels.piece}</h3>
                  <span style={{ fontSize: "14px", color: "#93c5fd" }}>
                    {isPieceExpanded ? "▼" : "▶"}
                  </span>
                </div>
                {isPieceExpanded && (
                  <div className="training-grid">
                    {suggestionsByCategory.piece.map((suggestion) => (
                      <DrillCard key={suggestion.id} suggestion={suggestion} onStart={handleStartDrill} loading={loading} />
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Tag Transitions Section */}
            {suggestionsByCategory.tag_transition.length > 0 && (
              <div style={{ marginBottom: "32px" }}>
                <div 
                  style={{ 
                    display: "flex", 
                    justifyContent: "space-between", 
                    alignItems: "center", 
                    marginBottom: "16px",
                    cursor: "pointer"
                  }}
                  onClick={() => setIsTagExpanded(!isTagExpanded)}
                >
                  <h3 style={{ margin: 0, fontSize: "20px", fontWeight: 600 }}>{categoryLabels.tag_transition}</h3>
                  <span style={{ fontSize: "14px", color: "#93c5fd" }}>
                    {isTagExpanded ? "▼" : "▶"}
                  </span>
                </div>
                {isTagExpanded && (
                  <div className="training-grid">
                    {suggestionsByCategory.tag_transition.map((suggestion) => (
                      <DrillCard key={suggestion.id} suggestion={suggestion} onStart={handleStartDrill} loading={loading} />
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Time Management Section */}
            {suggestionsByCategory.time_bucket.length > 0 && (
              <div style={{ marginBottom: "32px" }}>
                <div 
                  style={{ 
                    display: "flex", 
                    justifyContent: "space-between", 
                    alignItems: "center", 
                    marginBottom: "16px",
                    cursor: "pointer"
                  }}
                  onClick={() => setIsTimeExpanded(!isTimeExpanded)}
                >
                  <h3 style={{ margin: 0, fontSize: "20px", fontWeight: 600 }}>{categoryLabels.time_bucket}</h3>
                  <span style={{ fontSize: "14px", color: "#93c5fd" }}>
                    {isTimeExpanded ? "▼" : "▶"}
                  </span>
                </div>
                {isTimeExpanded && (
                  <div className="training-grid">
                    {suggestionsByCategory.time_bucket.map((suggestion) => (
                      <DrillCard key={suggestion.id} suggestion={suggestion} onStart={handleStartDrill} loading={loading} />
                    ))}
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>

      <div className="tab-section">
        <h2>About Personalized Drills</h2>
        <p style={{ color: "#666", lineHeight: "1.6" }}>
          These drills are generated from positions in your analyzed games, filtered by phase, opening, piece type,
          tag transitions, and time management patterns. By practicing these positions, you'll improve your
          performance in specific areas of your game.
        </p>
      </div>
    </div>
  );
}

// Drill Card Component
function DrillCard({ suggestion, onStart, loading }: { suggestion: DrillSuggestion; onStart: (s: DrillSuggestion) => void; loading: boolean }) {
  const getTitle = () => {
    if (suggestion.category === "phase") {
      return suggestion.filter_value.charAt(0).toUpperCase() + suggestion.filter_value.slice(1);
    } else if (suggestion.category === "opening") {
      return suggestion.filter_value;
    } else if (suggestion.category === "piece") {
      return suggestion.filter_value;
    } else if (suggestion.category === "tag_transition") {
      return suggestion.filter_value.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase());
    } else if (suggestion.category === "time_bucket") {
      return suggestion.filter_value;
    }
    return suggestion.filter_value;
  };

  return (
    <div className="training-card">
      <div className="training-info">
        <h3>{getTitle()}</h3>
        <p>{suggestion.description}</p>
        <div style={{ display: "flex", gap: "12px", marginTop: "8px", flexWrap: "wrap" }}>
          <span className="difficulty-tag">{suggestion.difficulty}</span>
          {suggestion.position_count !== undefined ? (
            <span style={{ fontSize: "0.9em", color: "#666" }}>
              {suggestion.position_count} positions available
              {suggestion.position_avg_accuracy !== null && suggestion.position_avg_accuracy !== undefined && (
                <span> • {suggestion.position_avg_accuracy.toFixed(0)}% avg accuracy</span>
              )}
            </span>
          ) : (
            <span style={{ fontSize: "0.9em", color: "#666" }}>
              {suggestion.metadata.tag?.count || suggestion.metadata.piece?.count || 0} instances • {suggestion.accuracy.toFixed(0)}% accuracy
            </span>
          )}
        </div>
      </div>
      <button
        className="start-training-btn"
        onClick={() => onStart(suggestion)}
        disabled={loading}
      >
        {loading ? "Loading..." : "Start Drill"}
      </button>
    </div>
  );
}
