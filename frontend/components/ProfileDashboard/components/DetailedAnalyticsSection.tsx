"use client";

import { useEffect, useState } from "react";
import PhasePerformanceCard from "./PhasePerformanceCard";
import PieceAccuracyCard from "./PieceAccuracyCard";
import TagTransitionsCard from "./TagTransitionsCard";
import TimeManagementCard from "./TimeManagementCard";

interface DetailedAnalyticsSectionProps {
  userId: string;
  backendBase: string;
  title?: string;
}

export default function DetailedAnalyticsSection({
  userId,
  backendBase,
  title = "Detailed Analytics",
}: DetailedAnalyticsSectionProps) {
  // TEMPORARY: Dummy data for formatting - REMOVE AFTER FORMATTING IS DONE
  const DUMMY_DETAILED_ANALYTICS = {
    phase_analytics: {
      opening: { accuracy: 82.1, games_won: 45, games_lost: 20, games_drawn: 8, win_rate: 61.6 },
      middlegame: { accuracy: 76.5, games_won: 52, games_lost: 35, games_drawn: 12, win_rate: 52.5 },
      endgame: { accuracy: 81.3, games_won: 38, games_lost: 15, games_drawn: 5, win_rate: 65.5 }
    },
    opening_detailed: {
      "Sicilian Defense": { frequency: 45, avg_accuracy: 79.1, wins: 28, losses: 12, draws: 5, win_rate: 0.622 },
      "Queen's Gambit": { frequency: 38, avg_accuracy: 76.8, wins: 21, losses: 14, draws: 3, win_rate: 0.553 },
      "King's Indian Defense": { frequency: 32, avg_accuracy: 75.2, wins: 16, losses: 12, draws: 4, win_rate: 0.500 },
      "French Defense": { frequency: 28, avg_accuracy: 77.5, wins: 15, losses: 10, draws: 3, win_rate: 0.536 },
      "Caro-Kann": { frequency: 24, avg_accuracy: 78.3, wins: 14, losses: 8, draws: 2, win_rate: 0.583 },
      "Italian Game": { frequency: 22, avg_accuracy: 80.1, wins: 13, losses: 7, draws: 2, win_rate: 0.591 },
      "Ruy Lopez": { frequency: 18, avg_accuracy: 77.8, wins: 10, losses: 6, draws: 2, win_rate: 0.556 }
    },
    piece_accuracy_detailed: {
      aggregate: {
        Pawn: { accuracy: 79.2, count: 1245, moves: 1245 },
        Knight: { accuracy: 75.8, count: 456, moves: 456 },
        Bishop: { accuracy: 77.3, count: 432, moves: 432 },
        Rook: { accuracy: 78.9, count: 678, moves: 678 },
        Queen: { accuracy: 76.1, count: 234, moves: 234 },
        King: { accuracy: 81.5, count: 189, moves: 189 }
      }
    },
    tag_transitions: {
      gained: {
        "Positional Advantage": { accuracy: 82.1, count: 45, blunders: 2, mistakes: 5, inaccuracies: 8, significance_score: 0.85 },
        "Endgame Technique": { accuracy: 84.3, count: 38, blunders: 1, mistakes: 3, inaccuracies: 6, significance_score: 0.78 },
        "Pawn Structure": { accuracy: 80.5, count: 32, blunders: 3, mistakes: 4, inaccuracies: 7, significance_score: 0.72 }
      },
      lost: {
        "Time Pressure": { accuracy: 68.2, count: 32, blunders: 8, mistakes: 12, inaccuracies: 15, significance_score: 0.72 },
        "Tactical Awareness": { accuracy: 71.5, count: 28, blunders: 6, mistakes: 10, inaccuracies: 13, significance_score: 0.65 },
        "Opening Theory": { accuracy: 73.8, count: 24, blunders: 5, mistakes: 8, inaccuracies: 11, significance_score: 0.58 }
      }
    },
    time_bucket_analytics: {
      "opening": { accuracy: 82.1, count: 247, blunders: 8, mistakes: 15, blunder_rate: 3.2 },
      "middlegame": { accuracy: 76.5, count: 247, blunders: 18, mistakes: 28, blunder_rate: 7.3 },
      "endgame": { accuracy: 81.3, count: 195, blunders: 6, mistakes: 12, blunder_rate: 3.1 }
    },
    time_buckets: {
      "<5s": { accuracy: 65.2, count: 45, blunders: 12, mistakes: 18, blunder_rate: 26.7 },
      "5-15s": { accuracy: 72.8, count: 128, blunders: 15, mistakes: 25, blunder_rate: 11.7 },
      "15-30s": { accuracy: 78.5, count: 234, blunders: 18, mistakes: 32, blunder_rate: 7.7 },
      "30s-1min": { accuracy: 81.2, count: 312, blunders: 12, mistakes: 28, blunder_rate: 3.8 },
      "1min-2min30": { accuracy: 83.7, count: 456, blunders: 8, mistakes: 22, blunder_rate: 1.8 },
      "2min30-5min": { accuracy: 85.1, count: 289, blunders: 5, mistakes: 15, blunder_rate: 1.7 },
      "5min+": { accuracy: 86.3, count: 178, blunders: 3, mistakes: 8, blunder_rate: 1.7 }
    }
  };

  const [detailedAnalytics, setDetailedAnalytics] = useState<any>(DUMMY_DETAILED_ANALYTICS);
  const [loadingDetailed, setLoadingDetailed] = useState(false);

  // TEMPORARY: Comment out fetch - UNCOMMENT AFTER FORMATTING IS DONE
  /*
  useEffect(() => {
    if (!userId || !backendBase) return;

    const loadDetailedAnalytics = async () => {
      setLoadingDetailed(true);
      try {
        const baseUrl = backendBase.replace(/\/$/, "");
        const url = `${baseUrl}/profile/analytics/${userId}/detailed`;
        console.log(`[DetailedAnalyticsSection] Fetching detailed analytics from: ${url}`);
        const response = await fetch(url, { cache: "no-store" });
        if (response.ok) {
          const data = await response.json();
          setDetailedAnalytics(data);
        } else {
          const errorText = await response.text();
          console.error(
            `[DetailedAnalyticsSection] Failed to load detailed analytics: ${response.status} - ${errorText}`,
          );
          setDetailedAnalytics(null);
        }
      } catch (e) {
        console.error("[DetailedAnalyticsSection] Failed to load detailed analytics:", e);
        setDetailedAnalytics(null);
      } finally {
        setLoadingDetailed(false);
      }
    };

    loadDetailedAnalytics();
  }, [userId, backendBase]);
  */ // END TEMPORARY COMMENT

  return (
    <div className="tab-section">
      <h2>{title}</h2>
      {loadingDetailed ? (
        <div style={{ padding: "20px", textAlign: "center", color: "#93c5fd" }}>
          Loading detailed analytics...
        </div>
      ) : detailedAnalytics ? (
        <>
          {detailedAnalytics.phase_analytics && (
            <PhasePerformanceCard phaseAnalytics={detailedAnalytics.phase_analytics} />
          )}

          {detailedAnalytics.opening_detailed &&
            Object.keys(detailedAnalytics.opening_detailed).length > 0 && (
              <div
                style={{
                  padding: "20px",
                  background: "#1e3a5f",
                  borderRadius: "8px",
                  border: "1px solid rgba(147, 197, 253, 0.2)",
                  marginBottom: "20px",
                }}
              >
                <h3
                  style={{
                    margin: "0 0 16px 0",
                    fontSize: "18px",
                    fontWeight: 600,
                    color: "#e0e7ff",
                  }}
                >
                  Opening Repertoire
                </h3>
                <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                  {Object.entries(detailedAnalytics.opening_detailed)
                    .slice(0, 5)
                    .map(([opening, data]: [string, any]) => (
                      <div
                        key={opening}
                        style={{
                          padding: "12px",
                          background: "rgba(59, 130, 246, 0.1)",
                          borderRadius: "6px",
                          border: "1px solid rgba(147, 197, 253, 0.2)",
                        }}
                      >
                        <div
                          style={{
                            display: "flex",
                            justifyContent: "space-between",
                            alignItems: "center",
                            marginBottom: "8px",
                          }}
                        >
                          <span style={{ fontSize: "14px", fontWeight: 600, color: "#93c5fd" }}>
                            {opening}
                          </span>
                          <span style={{ fontSize: "14px", fontWeight: 600, color: "#e0e7ff" }}>
                            {data.avg_accuracy.toFixed(1)}% accuracy
                          </span>
                        </div>
                        <div style={{ display: "flex", gap: "16px", fontSize: "12px", color: "#cbd5e1" }}>
                          <span>Frequency: {data.frequency}</span>
                          <span>Win Rate: {(data.win_rate * 100).toFixed(1)}%</span>
                          <span>Wins: {data.wins}</span>
                          <span>Losses: {data.losses}</span>
                          {data.draws > 0 && <span>Draws: {data.draws}</span>}
                        </div>
                      </div>
                    ))}
                </div>
              </div>
            )}

          {detailedAnalytics.piece_accuracy_detailed && (
            <PieceAccuracyCard pieceData={detailedAnalytics.piece_accuracy_detailed} />
          )}

          {detailedAnalytics.tag_transitions && (
            <TagTransitionsCard tagTransitions={detailedAnalytics.tag_transitions} />
          )}

          {detailedAnalytics.time_buckets && Object.keys(detailedAnalytics.time_buckets).length > 0 && (
            <TimeManagementCard timeBuckets={detailedAnalytics.time_buckets} />
          )}
        </>
      ) : (
        <div style={{ padding: "20px", textAlign: "center", color: "#9ca3af" }}>
          No detailed analytics data available yet. Analyze more games to see detailed metrics.
        </div>
      )}
    </div>
  );
}


