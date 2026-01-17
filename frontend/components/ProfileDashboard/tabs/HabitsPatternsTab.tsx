"use client";

import { useState, useEffect } from "react";
import HabitsDashboard from "@/components/HabitsDashboard";

interface HabitsPatternsTabProps {
  userId: string;
  data: any;
}

export default function HabitsPatternsTab({ userId, data }: HabitsPatternsTabProps) {
  const [showAdvanced, setShowAllAdvanced] = useState(false);
  const isComputing = data?.status === "computing";
  const safeData = data || {};

  return (
    <div className="habits-patterns-tab">
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
            Computing patterns and habits...
          </span>
        </div>
      )}

      <div className="tab-section">
        <h2>Your Playing Habits</h2>
        <HabitsDashboard userId={userId} />
      </div>

      <div className="tab-section">
        <h2>Advanced Patterns</h2>
        <div className="pattern-grid">
          <div className="pattern-card">
            <h3>Opening Repertoire</h3>
            <div className="opening-stats-list">
              {safeData?.opening_repertoire && safeData.opening_repertoire.length > 0 ? safeData.opening_repertoire.map((opening: any, idx: number) => (
                <div key={idx} className="opening-stat-row">
                  <div className="opening-info">
                    <span className="name">{opening.name}</span>
                    <span className="eco">{opening.eco}</span>
                  </div>
                  <div className="opening-bar-container">
                    <div className="opening-bar" style={{ width: `${opening.win_rate}%` }}></div>
                    <span className="win-rate">{opening.win_rate}%</span>
                  </div>
                </div>
              )) : (
                <p className="no-data" style={{ padding: '20px', textAlign: 'center', color: '#666' }}>
                  No opening repertoire data available yet.
                </p>
              )}
            </div>
          </div>

          <div className="pattern-card">
            <h3>Time Management</h3>
            {data?.time_management?.status === 'insufficient_data' ? (
              <p className="no-data">More analyzed moves needed for time patterns.</p>
            ) : (
              <div className="time-patterns">
                <div className="style-badge">{data?.time_management?.time_usage_style?.toUpperCase()}</div>
                <div className="time-buckets">
                  {Object.entries(data?.time_management?.accuracy_by_time || {}).map(([bucket, acc]: [string, any]) => (
                    <div key={bucket} className="time-bucket">
                      <span className="label">{bucket}</span>
                      <span className="value">{acc}% accuracy</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="tab-section">
        <h2>Tag Transitions</h2>
        <div className="pattern-grid">
          <div className="pattern-card">
            <h3>Top Gained Tags (Error Impact)</h3>
            <div className="transition-list">
              {data?.transitions?.gained?.length > 0 ? (
                data.transitions.gained.slice(0, 5).map((t: any, idx: number) => (
                  <div key={idx} className="transition-item">
                    <span className="name">{t.tag.replace('tag.', '').replace('.', ' ')}</span>
                    <div className="stats">
                      <span className="acc">{t.accuracy}% Acc</span>
                      <span className="count">{t.frequency} errors</span>
                    </div>
                  </div>
                ))
              ) : (
                <p className="no-data">Insufficient transition data.</p>
              )}
            </div>
          </div>
          <div className="pattern-card">
            <h3>Top Lost Tags (Error Impact)</h3>
            <div className="transition-list">
              {data?.transitions?.lost?.length > 0 ? (
                data.transitions.lost.slice(0, 5).map((t: any, idx: number) => (
                  <div key={idx} className="transition-item">
                    <span className="name">{t.tag.replace('tag.', '').replace('.', ' ')}</span>
                    <div className="stats">
                      <span className="acc">{t.accuracy}% Acc</span>
                      <span className="count">{t.frequency} errors</span>
                    </div>
                  </div>
                ))
              ) : (
                <p className="no-data">Insufficient transition data.</p>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="tab-section">
        <h2>Opponent Adaptation</h2>
        <div className="opponent-stats">
          <div className="stat-box">
            <span className="label">Win Rate vs Stronger</span>
            <span className="value">{data?.opponent_analysis?.win_rate_vs_higher || 0}%</span>
          </div>
          <div className="stat-box">
            <span className="label">Win Rate vs Weaker</span>
            <span className="value">{data?.opponent_analysis?.win_rate_vs_lower || 0}%</span>
          </div>
          <div className="stat-box">
            <span className="label">Clutch Factor (Endgame Acc)</span>
            <span className="value">{data?.clutch_performance || 0}%</span>
          </div>
        </div>
      </div>
    </div>
  );
}

