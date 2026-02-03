"use client";

import { useEffect, useState } from "react";
import PhasePerformanceCard from "./PhasePerformanceCard";
import PieceAccuracyCard from "./PieceAccuracyCard";
import TagTransitionsCard from "./TagTransitionsCard";
import StaticTagsCard from "./StaticTagsCard";
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
  const [detailedAnalytics, setDetailedAnalytics] = useState<any>(null); // Start with null instead of dummy data
  const [loadingDetailed, setLoadingDetailed] = useState(true); // Start with loading true

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
          try {
            const DEBUG_TAG_TRANSITIONS =
              typeof window !== "undefined" && (window.localStorage?.getItem("chessterDebugTags") === "1");
            if (DEBUG_TAG_TRANSITIONS) {
              const gained = data?.tag_transitions?.gained || {};
              const lost = data?.tag_transitions?.lost || {};
              const gainedKeys = Object.keys(gained);
              const lostKeys = Object.keys(lost);
              console.log(
                `[DetailedAnalyticsSection] tag_transitions summary: gained=${gainedKeys.length}, lost=${lostKeys.length}, sampleGained=${gainedKeys.slice(0, 5).join(", ") || "—"}, sampleLost=${lostKeys.slice(0, 5).join(", ") || "—"}`,
              );
            }
          } catch {
            // ignore debug failures
          }
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

  return (
    <div className="tab-section">
      <h2>{title}</h2>
      {loadingDetailed ? (
        <div className="dashboard-loading">
          <div className="spinner"></div>
          <p>Loading detailed analytics...</p>
        </div>
      ) : detailedAnalytics ? (
        <>
          {/* Show warning if most games are missing move data (old stub format) */}
          {detailedAnalytics._meta && (
            (() => {
              const meta = detailedAnalytics._meta;
              const total = meta.games_total || 0;
              const withPly = meta.games_with_ply_records || 0;
              const stubOld = meta.games_stub_old_format || 0;
              const missing = meta.games_missing_game_review || 0;
              const usableGames = withPly;
              const unusableGames = stubOld + missing;
              
              // Show warning if less than 50% of games have usable data
              if (total > 0 && usableGames < total * 0.5) {
                return (
                  <div style={{
                    padding: "16px",
                    marginBottom: "20px",
                    background: "rgba(251, 191, 36, 0.1)",
                    border: "1px solid rgba(251, 191, 36, 0.3)",
                    borderRadius: "8px",
                    color: "#fbbf24"
                  }}>
                    <div style={{ fontSize: "14px", fontWeight: 600, marginBottom: "4px" }}>
                      ⚠️ Limited Analytics Data
                    </div>
                    <div style={{ fontSize: "12px", color: "#cbd5e1" }}>
                      {usableGames} of {total} games have full move data. {unusableGames > 0 && `${unusableGames} games are missing move records (older format).`} 
                      {" "}New games will include complete analytics.
                    </div>
                  </div>
                );
              }
              return null;
            })()
          )}

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

          <StaticTagsCard staticTags={detailedAnalytics.static_tags || {}} />

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


