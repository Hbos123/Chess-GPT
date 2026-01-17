"use client";

import { useMemo } from "react";

interface LifetimeStatsTabProps {
  data: any;
}

export default function LifetimeStatsTab({ data }: LifetimeStatsTabProps) {
  // Always render UI structure, even with empty data
  const isComputing = data?.status === "computing";
  const safeData = data || {};

  const winRates = useMemo(() => {
    if (!safeData.win_rates || Object.keys(safeData.win_rates).length === 0) {
      return [];
    }
    return Object.entries(safeData.win_rates || {}).map(([tc, stats]: [string, any]) => ({
      name: tc.charAt(0).toUpperCase() + tc.slice(1),
      ...stats
    }));
  }, [safeData.win_rates]);

  return (
    <div className="lifetime-stats-tab">
      {isComputing && (
        <div style={{ 
          padding: '12px 16px', 
          background: '#1e3a5f', 
          borderRadius: '8px', 
          marginBottom: '24px',
          display: 'flex',
          alignItems: 'center',
          gap: '12px'
        }}>
          <div className="spinner" style={{ width: '16px', height: '16px', borderWidth: '2px', margin: 0 }}></div>
          <span style={{ fontSize: '14px', color: '#93c5fd' }}>
            Computing lifetime statistics...
          </span>
        </div>
      )}

      <div className="tab-section">
        <h2>Rating Progression</h2>
        <div className="chart-placeholder">
          {/* In a real app, I'd use Recharts or Chart.js here */}
          {safeData.rating_history && safeData.rating_history.length > 0 ? (
            <>
              <div className="simple-rating-viz">
                {safeData.rating_history.map((point: any, idx: number) => (
                  <div 
                    key={idx} 
                    className="rating-bar" 
                    style={{ height: `${(point.rating / 3000) * 100}%` }}
                    title={`${point.date}: ${point.rating}`}
                  ></div>
                ))}
              </div>
              <div className="chart-info">Showing rating trend over last 100 analyzed games.</div>
            </>
          ) : (
            <div className="no-data-placeholder" style={{ padding: '40px', textAlign: 'center', color: '#666' }}>
              No rating history available yet. Analyze games to see your progression.
            </div>
          )}
        </div>
      </div>

      <div className="tab-section">
        <h2>Performance by Time Control</h2>
        <div className="tc-grid">
          {winRates.length > 0 ? winRates.map((tc) => (
            <div key={tc.name} className="tc-card">
              <h3>{tc.name}</h3>
              <div className="tc-pie-viz">
                <div className="pie-slice wins" style={{ width: `${tc.win_rate}%` }}></div>
                <div className="pie-slice draws" style={{ width: `${(tc.draws/tc.total)*100}%` }}></div>
                <div className="pie-slice losses" style={{ width: `${(tc.losses/tc.total)*100}%` }}></div>
              </div>
              <div className="tc-metrics">
                <span>{tc.win_rate}% Wins</span>
                <span>{tc.total} Games</span>
              </div>
            </div>
          )) : (
            <div className="no-data-placeholder" style={{ padding: '40px', textAlign: 'center', color: '#666', gridColumn: '1 / -1' }}>
              No time control data available yet.
            </div>
          )}
        </div>
      </div>

      <div className="tab-section">
        <h2>Tilt Analysis (Accuracy vs Time)</h2>
        <div className="chart-placeholder tilt-plot-container">
          {safeData.scatter_plot?.length > 0 ? (
            <div className="tilt-plot-wrapper">
              <svg viewBox="0 0 100 100" className="tilt-plot-svg">
                {/* Grid lines */}
                <line x1="0" y1="25" x2="100" y2="25" stroke="#333" strokeWidth="0.5" />
                <line x1="0" y1="50" x2="100" y2="50" stroke="#333" strokeWidth="0.5" />
                <line x1="0" y1="75" x2="100" y2="75" stroke="#333" strokeWidth="0.5" />
                
                {/* Data points */}
                {data.scatter_plot.map((point: any, idx: number) => {
                  // Normalize: time 0-60s -> 0-100, accuracy 0-100 -> 100-0 (SVG y is top-down)
                  const x = Math.min(100, (point.time / 60) * 100);
                  const y = 100 - point.accuracy;
                  return (
                    <circle 
                      key={idx} 
                      cx={x} 
                      cy={y} 
                      r="1" 
                      fill={point.accuracy > 80 ? "#4ade80" : point.accuracy > 50 ? "#facc15" : "#f87171"} 
                      opacity="0.6"
                    />
                  );
                })}
              </svg>
              <div className="plot-axes">
                <span className="y-axis-label">Accuracy %</span>
                <span className="x-axis-label">Time Spent (s)</span>
              </div>
            </div>
          ) : (
            <div className="no-data-placeholder">Not enough move-by-move data for tilt analysis.</div>
          )}
        </div>
      </div>

      <div className="tab-section">
        <h2>Improvement Metrics</h2>
        <div className="metrics-list">
          <div className="metric-row">
            <span className="label">Improvement Velocity</span>
            <span className="value">{safeData.improvement_velocity?.rating_delta || '---'} Elo points</span>
          </div>
          <div className="metric-row">
            <span className="label">Points Per Game</span>
            <span className="value">{safeData.improvement_velocity?.points_per_game || '---'} avg</span>
          </div>
          <div className="metric-row">
            <span className="label">Peak Performance</span>
            <span className="value">{safeData.peak_rating || '---'} Peak Rating</span>
          </div>
        </div>
      </div>
    </div>
  );
}

