"use client";

import { useState, useEffect } from "react";
import PhasePerformanceCard from "../components/PhasePerformanceCard";
import PieceAccuracyCard from "../components/PieceAccuracyCard";
import TagTransitionsCard from "../components/TagTransitionsCard";
import TimeManagementCard from "../components/TimeManagementCard";

interface OverviewTabProps {
  data: any;
  profileStatus?: any;
  onOpenPersonalReview?: () => void;
  userId?: string;
  backendBase?: string;
}

export default function OverviewTab({ data, profileStatus, onOpenPersonalReview, userId, backendBase }: OverviewTabProps) {
  // Always render the UI structure, even with empty data
  const isComputing = data?.status === "computing";
  const hasError = data?.error;
  
  // Linked accounts state
  const [linkedAccounts, setLinkedAccounts] = useState<Array<{platform: string, username: string}>>([]);
  const [isEditing, setIsEditing] = useState(false);
  const [newAccountPlatform, setNewAccountPlatform] = useState<"chess.com" | "lichess">("chess.com");
  const [newAccountUsername, setNewAccountUsername] = useState("");
  const [isValidating, setIsValidating] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  
  // Detailed analytics state
  const [detailedAnalytics, setDetailedAnalytics] = useState<any>(null);
  const [loadingDetailed, setLoadingDetailed] = useState(false);
  
  // Diagnostic insights caching
  const [diagnosticInsights, setDiagnosticInsights] = useState<any[] | null>(null);
  
  // Load linked accounts from profile overview
  useEffect(() => {
    if (!userId || !backendBase) return;
    
    const loadAccounts = async () => {
      try {
        const response = await fetch(`${backendBase.replace(/\/$/, "")}/profile/overview?user_id=${userId}`);
        if (response.ok) {
          const data = await response.json();
          const accounts = data.preferences?.accounts || [];
          setLinkedAccounts(accounts);
        }
      } catch (e) {
        console.warn("[OverviewTab] Failed to load accounts:", e);
      }
    };
    
    loadAccounts();
  }, [userId, backendBase]);
  
  // Load detailed analytics (parallel with main analytics fetch)
  useEffect(() => {
    if (!userId || !backendBase) return;
    
    const loadDetailedAnalytics = async () => {
      setLoadingDetailed(true);
      try {
        const baseUrl = backendBase.replace(/\/$/, "");
        console.log(`[OverviewTab] Fetching detailed analytics from: ${baseUrl}/profile/analytics/${userId}/detailed`);
        const response = await fetch(`${baseUrl}/profile/analytics/${userId}/detailed`, { cache: 'no-store' });
        console.log(`[OverviewTab] Response status: ${response.status}`);
        if (response.ok) {
          const data = await response.json();
          console.log(`[OverviewTab] Received detailed analytics:`, data);
          setDetailedAnalytics(data);
        } else {
          const errorText = await response.text();
          console.error(`[OverviewTab] Failed to load detailed analytics: ${response.status} - ${errorText}`);
        }
      } catch (e) {
        console.error("[OverviewTab] Failed to load detailed analytics:", e);
      } finally {
        setLoadingDetailed(false);
      }
    };
    
    loadDetailedAnalytics();
  }, [userId, backendBase]);
  
  // Cache diagnostic insights
  useEffect(() => {
    if (data?.strength_profile?.diagnostic_insights && Array.isArray(data.strength_profile.diagnostic_insights)) {
      setDiagnosticInsights(data.strength_profile.diagnostic_insights);
    }
  }, [data?.strength_profile?.diagnostic_insights]);
  
  // Validate account before adding
  const validateAccount = async (username: string, platform: "chess.com" | "lichess"): Promise<boolean> => {
    if (!username.trim()) {
      setValidationError("Username cannot be empty");
      return false;
    }
    
    setIsValidating(true);
    setValidationError(null);
    
    try {
      const response = await fetch(
        `${backendBase?.replace(/\/$/, "")}/profile/validate-account?username=${encodeURIComponent(username)}&platform=${platform}`
      );
      const result = await response.json();
      
      if (result.valid) {
        setIsValidating(false);
        return true;
      } else {
        setValidationError(result.message || "Account not found");
        setIsValidating(false);
        return false;
      }
    } catch (e) {
      setValidationError("Error validating account. Please try again.");
      setIsValidating(false);
      return false;
    }
  };
  
  // Add account
  const handleAddAccount = async () => {
    if (!newAccountUsername.trim()) {
      setValidationError("Please enter a username");
      return;
    }
    
    const isValid = await validateAccount(newAccountUsername, newAccountPlatform);
    if (!isValid) {
      return;
    }
    
    // Check if account already exists
    const exists = linkedAccounts.some(
      acc => acc.platform === newAccountPlatform && acc.username.toLowerCase() === newAccountUsername.toLowerCase()
    );
    
    if (exists) {
      setValidationError("This account is already linked");
      return;
    }
    
    // Add to list
    setLinkedAccounts([...linkedAccounts, { platform: newAccountPlatform, username: newAccountUsername.trim() }]);
    setNewAccountUsername("");
    setValidationError(null);
  };
  
  // Remove account
  const handleRemoveAccount = (index: number) => {
    setLinkedAccounts(linkedAccounts.filter((_, i) => i !== index));
  };
  
  // Save accounts
  const handleSaveAccounts = async () => {
    if (!userId || !backendBase) return;
    
    setIsSaving(true);
    try {
      const response = await fetch(`${backendBase.replace(/\/$/, "")}/profile/preferences`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: userId,
          accounts: linkedAccounts.map(acc => ({
            platform: acc.platform === "chess.com" ? "chess.com" : "lichess",
            username: acc.username
          })),
          time_controls: []
        })
      });
      
      if (response.ok) {
        setIsEditing(false);
        // Reload page data
        window.location.reload();
      } else {
        const error = await response.text();
        setValidationError(`Failed to save: ${error}`);
      }
    } catch (e) {
      setValidationError("Error saving accounts. Please try again.");
    } finally {
      setIsSaving(false);
    }
  };
  
  // Use empty objects as defaults so UI always renders
  const lifetime_stats = data?.lifetime_stats || {};
  const patterns = data?.patterns || {};
  const strength_profile = data?.strength_profile || {};
  const rolling_window = data?.rolling_window || {};
  const deltas = data?.deltas || {};
  
  // Check if we have any actual data (not just empty objects)
  const hasLifetimeStats = lifetime_stats && Object.keys(lifetime_stats).length > 0;
  const hasPatterns = patterns && Object.keys(patterns).length > 0;
  const hasStrengthProfile = strength_profile && Object.keys(strength_profile).length > 0;
  const hasAnyData = hasLifetimeStats || hasPatterns || hasStrengthProfile;

  // Get active games count from rolling window or profile status
  const activeGames = rolling_window?.games || profileStatus?.deep_analyzed_games || 0;
  const targetGames = profileStatus?.target_games || 60;
  const progressPercent = Math.min((activeGames / targetGames) * 100, 100);
  
  // Get games being analyzed right now
  const gamesIndexed = profileStatus?.games_indexed || 0;
  const isAnalyzing = profileStatus?.state === "analyzing" || profileStatus?.state === "fetching";
  
  // Determine current activity status with real-time progress
  const getActivityStatus = () => {
    if (profileStatus?.state === "fetching") {
      const fetched = profileStatus?.games_indexed || 0;
      return `Fetching games... (${fetched} found so far)`;
    }
    if (profileStatus?.state === "analyzing") {
      const analyzed = profileStatus?.deep_analyzed_games || activeGames || 0;
      const total = profileStatus?.games_indexed || analyzed;
      if (total > 0 && analyzed < total) {
        return `Analyzing game ${analyzed + 1} of ${total}...`;
      }
      return `Analyzing ${total || 'new'} game${total !== 1 ? 's' : ''}...`;
    }
    if (activeGames > targetGames) {
      const excess = activeGames - targetGames;
      return `Dropping oldest ${excess} game${excess > 1 ? 's' : ''}...`;
    }
    if (activeGames < targetGames) {
      const needed = targetGames - activeGames;
      if (isAnalyzing && gamesIndexed > activeGames) {
        return `Analyzing... (${activeGames}/${targetGames} complete)`;
      }
      return `${needed} more game${needed > 1 ? 's' : ''} needed`;
    }
    if (activeGames === targetGames && activeGames > 0) {
      return "60-game window complete";
    }
    return "No games analyzed yet";
  };

  return (
    <div className="overview-tab">
      {/* Progress Bar - Always show at top */}
      <div style={{ 
        padding: '16px', 
        background: 'linear-gradient(135deg, #1e3a5f 0%, #2d4a6e 100%)', 
        borderRadius: '8px', 
        marginBottom: '24px',
        border: '1px solid rgba(147, 197, 253, 0.2)'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
          <span style={{ fontSize: '14px', fontWeight: 600, color: '#e0e7ff' }}>
            Profile Analysis Progress
          </span>
          <span style={{ fontSize: '14px', color: '#93c5fd' }}>
            {activeGames}/{targetGames} games analyzed
          </span>
        </div>
        <div style={{ 
          width: '100%', 
          height: '8px', 
          background: 'rgba(0, 0, 0, 0.3)', 
          borderRadius: '4px',
          overflow: 'hidden',
          marginBottom: '8px'
        }}>
          <div style={{ 
            width: `${progressPercent}%`, 
            height: '100%', 
            background: progressPercent === 100 
              ? 'linear-gradient(90deg, #10b981 0%, #059669 100%)'
              : 'linear-gradient(90deg, #3b82f6 0%, #2563eb 100%)',
            transition: 'width 0.3s ease',
            borderRadius: '4px'
          }} />
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {isAnalyzing ? (
            <div className="spinner" style={{ width: '12px', height: '12px', borderWidth: '2px', margin: 0 }}></div>
          ) : null}
          <span style={{ fontSize: '13px', color: '#cbd5e1', opacity: 0.9 }}>
            {getActivityStatus()}
          </span>
          {isAnalyzing && activeGames > 0 && (
            <span style={{ fontSize: '12px', color: '#93c5fd', marginLeft: 'auto' }}>
              {activeGames} analyzed so far
            </span>
          )}
        </div>
      </div>

      {/* Linked Accounts Section */}
      <div style={{ 
        padding: '16px', 
        background: '#1e3a5f', 
        borderRadius: '8px', 
        marginBottom: '24px',
        border: '1px solid rgba(147, 197, 253, 0.2)'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
          <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 600, color: '#e0e7ff' }}>
            Linked Accounts
          </h3>
          {!isEditing ? (
            <button
              onClick={() => setIsEditing(true)}
              style={{
                padding: '6px 12px',
                background: '#3b82f6',
                color: 'white',
                border: 'none',
                borderRadius: '6px',
                cursor: 'pointer',
                fontSize: '13px'
              }}
            >
              Edit
            </button>
          ) : (
            <div style={{ display: 'flex', gap: '8px' }}>
              <button
                onClick={() => {
                  setIsEditing(false);
                  setNewAccountUsername("");
                  setValidationError(null);
                  // Reload accounts
                  window.location.reload();
                }}
                style={{
                  padding: '6px 12px',
                  background: '#6b7280',
                  color: 'white',
                  border: 'none',
                  borderRadius: '6px',
                  cursor: 'pointer',
                  fontSize: '13px'
                }}
              >
                Cancel
              </button>
              <button
                onClick={handleSaveAccounts}
                disabled={isSaving}
                style={{
                  padding: '6px 12px',
                  background: '#10b981',
                  color: 'white',
                  border: 'none',
                  borderRadius: '6px',
                  cursor: isSaving ? 'not-allowed' : 'pointer',
                  fontSize: '13px',
                  opacity: isSaving ? 0.6 : 1
                }}
              >
                {isSaving ? 'Saving...' : 'Save'}
              </button>
            </div>
          )}
        </div>
        
        {/* Existing accounts */}
        {linkedAccounts.length > 0 ? (
          <div style={{ marginBottom: '12px' }}>
            {linkedAccounts.map((acc, index) => (
              <div
                key={index}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: '8px 12px',
                  background: 'rgba(0, 0, 0, 0.2)',
                  borderRadius: '6px',
                  marginBottom: '6px'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ 
                    fontSize: '12px', 
                    padding: '2px 6px', 
                    background: acc.platform === 'chess.com' ? '#7c3aed' : '#059669',
                    borderRadius: '4px',
                    color: 'white',
                    fontWeight: 600
                  }}>
                    {acc.platform === 'chess.com' ? 'Chess.com' : 'Lichess'}
                  </span>
                  <span style={{ color: '#e0e7ff', fontSize: '14px' }}>{acc.username}</span>
                </div>
                {isEditing && (
                  <button
                    onClick={() => handleRemoveAccount(index)}
                    style={{
                      padding: '4px 8px',
                      background: '#ef4444',
                      color: 'white',
                      border: 'none',
                      borderRadius: '4px',
                      cursor: 'pointer',
                      fontSize: '12px'
                    }}
                  >
                    Remove
                  </button>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div style={{ 
            padding: '12px', 
            background: 'rgba(0, 0, 0, 0.2)', 
            borderRadius: '6px',
            color: '#cbd5e1',
            fontSize: '13px',
            marginBottom: '12px'
          }}>
            No accounts linked. Add a chess.com or lichess account to start analyzing your games.
          </div>
        )}
        
        {/* Add new account form */}
        {isEditing && (
          <div style={{ 
            padding: '12px', 
            background: 'rgba(0, 0, 0, 0.2)', 
            borderRadius: '6px',
            border: '1px solid rgba(147, 197, 253, 0.3)'
          }}>
            <div style={{ display: 'flex', gap: '8px', marginBottom: '8px', flexWrap: 'wrap' }}>
              <select
                value={newAccountPlatform}
                onChange={(e) => setNewAccountPlatform(e.target.value as "chess.com" | "lichess")}
                style={{
                  padding: '6px 10px',
                  background: '#1e3a5f',
                  color: '#e0e7ff',
                  border: '1px solid rgba(147, 197, 253, 0.3)',
                  borderRadius: '6px',
                  fontSize: '13px',
                  cursor: 'pointer'
                }}
              >
                <option value="chess.com">Chess.com</option>
                <option value="lichess">Lichess</option>
              </select>
              <input
                type="text"
                value={newAccountUsername}
                onChange={(e) => {
                  setNewAccountUsername(e.target.value);
                  setValidationError(null);
                }}
                placeholder="Username"
                style={{
                  flex: 1,
                  minWidth: '150px',
                  padding: '6px 10px',
                  background: '#1e3a5f',
                  color: '#e0e7ff',
                  border: '1px solid rgba(147, 197, 253, 0.3)',
                  borderRadius: '6px',
                  fontSize: '13px'
                }}
                onKeyPress={(e) => {
                  if (e.key === 'Enter') {
                    handleAddAccount();
                  }
                }}
              />
              <button
                onClick={handleAddAccount}
                disabled={isValidating || !newAccountUsername.trim()}
                style={{
                  padding: '6px 12px',
                  background: isValidating || !newAccountUsername.trim() ? '#6b7280' : '#3b82f6',
                  color: 'white',
                  border: 'none',
                  borderRadius: '6px',
                  cursor: isValidating || !newAccountUsername.trim() ? 'not-allowed' : 'pointer',
                  fontSize: '13px',
                  opacity: isValidating || !newAccountUsername.trim() ? 0.6 : 1
                }}
              >
                {isValidating ? 'Validating...' : 'Add'}
              </button>
            </div>
            {validationError && (
              <div style={{ 
                padding: '8px', 
                background: '#7f1d1d', 
                borderRadius: '4px',
                color: '#fca5a5',
                fontSize: '12px',
                marginTop: '8px'
              }}>
                {validationError}
              </div>
            )}
            <div style={{ 
              fontSize: '11px', 
              color: '#9ca3af', 
              marginTop: '8px',
              fontStyle: 'italic'
            }}>
              Only chess.com and lichess accounts are supported. Accounts are validated before being added.
            </div>
          </div>
        )}
      </div>

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
            Computing analytics... This page will update automatically.
          </span>
        </div>
      )}
      
      {hasError && (
        <div className="error-message" style={{ marginBottom: '24px' }}>
          <p>Error loading analytics: {data.error}</p>
        </div>
      )}

      {/* Rolling window (last 60) snapshot - show even if computing or no data */}
      {(rolling_window?.status === "ok" || rolling_window?.status === "computing" || !rolling_window?.status) && (
        <div className="tab-section">
          <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center" }}>
            <div>
              <h2 style={{ marginBottom: 6 }}>Last {rolling_window.window || 60} Games</h2>
              <div style={{ opacity: 0.85 }}>
                Rolling snapshot (auto-updated): performance, patterns, and critical positions.
              </div>
            </div>
            {onOpenPersonalReview && (
              <button
                type="button"
                onClick={onOpenPersonalReview}
                className="generate-training-btn"
                style={{ whiteSpace: "nowrap" }}
              >
                Personal Review
              </button>
            )}
          </div>

          <div className="stats-grid" style={{ marginTop: 12 }}>
            <div className="stat-card">
              <span className="stat-label">Avg accuracy</span>
              <span className="stat-value">
                {typeof rolling_window?.avg_accuracy === "number" ? `${rolling_window.avg_accuracy}%` : "---"}
                {typeof deltas?.accuracy_delta === "number" ? (
                  <span style={{ marginLeft: 8, fontSize: 12, opacity: 0.8 }}>
                    ({deltas.accuracy_delta >= 0 ? "+" : ""}{deltas.accuracy_delta} vs lifetime)
                  </span>
                ) : null}
              </span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Win rate</span>
              <span className="stat-value">
                {typeof rolling_window?.win_rate === "number" ? `${rolling_window.win_rate}%` : "---"}
                {typeof deltas?.win_rate_delta === "number" ? (
                  <span style={{ marginLeft: 8, fontSize: 12, opacity: 0.8 }}>
                    ({deltas.win_rate_delta >= 0 ? "+" : ""}{deltas.win_rate_delta} vs lifetime)
                  </span>
                ) : null}
              </span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Time style</span>
              <span className="stat-value">
                {rolling_window?.patterns?.time_management?.time_usage_style
                  ? String(rolling_window.patterns.time_management.time_usage_style).toUpperCase()
                  : "---"}
              </span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Clutch (last 10 plies)</span>
              <span className="stat-value">
                {typeof rolling_window?.patterns?.clutch_performance === "number"
                  ? `${rolling_window.patterns.clutch_performance}%`
                  : "---"}
              </span>
            </div>
          </div>

          {Array.isArray(rolling_window?.critical_positions) && rolling_window.critical_positions.length > 0 && (
            <div style={{ marginTop: 16 }}>
              <h3 style={{ marginBottom: 8 }}>Critical Positions (Last {rolling_window.window || 60})</h3>
              <div style={{ display: "grid", gap: 8 }}>
                {rolling_window.critical_positions.slice(0, 6).map((p: any, idx: number) => (
                  <div
                    key={`${p.game_id || "g"}-${idx}`}
                    className="stat-card"
                    style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}
                  >
                    <div style={{ display: "grid", gap: 2 }}>
                      <div style={{ fontWeight: 600 }}>
                        {p.category?.toUpperCase?.() || "CRITICAL"} • {p.san}
                      </div>
                      <div style={{ opacity: 0.8, fontSize: 12 }}>
                        {typeof p.cp_loss === "number" ? `≈${p.cp_loss}cp` : ""}{p.game_date ? ` • ${String(p.game_date).slice(0, 10)}` : ""}
                      </div>
                    </div>
                    <div style={{ fontFamily: "monospace", fontSize: 10, opacity: 0.7, maxWidth: 280, textAlign: "right" }}>
                      {typeof p.fen_before === "string" ? p.fen_before.slice(0, 48) + "…" : ""}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {onOpenPersonalReview && (
        <div className="tab-section" style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center' }}>
          <div>
            <h2 style={{ marginBottom: 6 }}>Personal Review</h2>
            <div style={{ opacity: 0.85 }}>
              Link accounts, fetch games, and run the 60-game rolling analysis.
            </div>
          </div>
          <button
            type="button"
            onClick={onOpenPersonalReview}
            className="generate-training-btn"
            style={{ whiteSpace: 'nowrap' }}
          >
            Open Personal Review
          </button>
        </div>
      )}

      <div className="tab-section">
        <h2>At a Glance</h2>
        <div className="stats-grid">
          <div className="stat-card">
            <span className="stat-label">Peak Rating</span>
            <span className="stat-value">{lifetime_stats?.peak_rating || '---'}</span>
          </div>
          <div className="stat-card">
            <span className="stat-label">Win Rate</span>
            <span className="stat-value">
              {lifetime_stats?.win_rates?.blitz?.win_rate || 
               lifetime_stats?.win_rates?.rapid?.win_rate || '---'}%
            </span>
          </div>
          <div className="stat-card">
            <span className="stat-label">Best Win Streak</span>
            <span className="stat-value">{lifetime_stats?.best_win_streak || 0}</span>
          </div>
          <div className="stat-card">
            <span className="stat-label">Trend</span>
            <span className={`stat-value stat-trend ${lifetime_stats?.improvement_velocity?.trend || 'stable'}`}>
              {lifetime_stats?.improvement_velocity?.trend?.toUpperCase() || 'STABLE'}
            </span>
          </div>
        </div>
      </div>

      <div className="tab-section">
        <h2>Diagnostic Insights</h2>
        <div className="insights-grid">
          {diagnosticInsights && diagnosticInsights.length > 0 ? (
            diagnosticInsights.slice(0, 6).map((insight: any, idx: number) => (
              <div key={idx} className={`insight-card ${insight.relevance_score > 15 ? 'high-relevance' : ''}`}>
                <div className="insight-header">
                  <span className="insight-tag">{insight.tag.replace('tag.', '').replace('.', ' ')}</span>
                  <span className="insight-score">{Math.round(insight.relevance_score * 10) / 10} Relevance</span>
                </div>
                <div className="insight-body">
                  <span className={`insight-accuracy ${insight.tag_avg > 75 ? 'good' : 'poor'}`}>
                    {Math.round(insight.tag_avg)}% Accuracy
                  </span>
                  <span className="insight-count">{insight.tag_count} occurrences</span>
                </div>
                <div className="insight-label">
                  {insight.tag_avg > 80 ? '🌟 Significant Strength' : 
                   insight.tag_avg < 65 ? '⚠️ Critical Weakness' : '📈 Area for Improvement'}
                </div>
              </div>
            ))
          ) : (
            <div className="no-data-placeholder">Complete more games to unlock diagnostic insights.</div>
          )}
        </div>
      </div>

      <div className="tab-section">
        <h2>Strengths & Weaknesses</h2>
        <div className="stats-grid">
          <div className="stat-card highlight-card green">
            <span className="stat-label">Top Strength</span>
            <span className="stat-value">
              {strength_profile?.phase_proficiency?.opening > 80 ? 'Opening Mastery' : 
               strength_profile?.tactical_accuracy > 85 ? 'Tactical Sharpness' : 'Consistent Play'}
            </span>
          </div>
          <div className="stat-card highlight-card red">
            <span className="stat-label">Focus Area</span>
            <span className="stat-value">
              {strength_profile?.phase_proficiency?.endgame < 70 ? 'Endgame Technique' : 
               strength_profile?.positional_accuracy < 75 ? 'Positional Strategy' : 'Time Management'}
            </span>
          </div>
        </div>
      </div>

      <div className="tab-section">
        <h2>Recent Performance</h2>
        <div className="repertoire-list">
          {patterns?.opening_repertoire?.length > 0 ? (
            patterns.opening_repertoire.slice(0, 3).map((opening: any, idx: number) => (
              <div key={idx} className="repertoire-item">
                <div className="opening-main">
                  <span className="opening-name">{opening.name}</span>
                  <span className="opening-eco">{opening.eco}</span>
                </div>
                <div className="opening-stats">
                  <span className={`win-rate ${opening.win_rate >= 50 ? 'positive' : 'negative'}`}>
                    {opening.win_rate}% WR
                  </span>
                  <span className="frequency">{opening.frequency} games</span>
                </div>
              </div>
            ))
          ) : (
            <div className="no-data-placeholder">Analyze more games to see your repertoire performance.</div>
          )}
        </div>
      </div>

      {/* Detailed Analytics Section */}
      <div className="tab-section">
        <h2>Detailed Analytics</h2>
        {loadingDetailed ? (
          <div style={{ padding: '20px', textAlign: 'center', color: '#93c5fd' }}>
            Loading detailed analytics...
          </div>
        ) : detailedAnalytics ? (
            <>
              {detailedAnalytics.phase_analytics && (
                <PhasePerformanceCard phaseAnalytics={detailedAnalytics.phase_analytics} />
              )}
              
              {detailedAnalytics.opening_detailed && Object.keys(detailedAnalytics.opening_detailed).length > 0 && (
                <div style={{
                  padding: '20px',
                  background: '#1e3a5f',
                  borderRadius: '8px',
                  border: '1px solid rgba(147, 197, 253, 0.2)',
                  marginBottom: '20px'
                }}>
                  <h3 style={{ margin: '0 0 16px 0', fontSize: '18px', fontWeight: 600, color: '#e0e7ff' }}>
                    Opening Repertoire
                  </h3>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    {Object.entries(detailedAnalytics.opening_detailed)
                      .slice(0, 5)
                      .map(([opening, data]: [string, any]) => (
                        <div key={opening} style={{
                          padding: '12px',
                          background: 'rgba(59, 130, 246, 0.1)',
                          borderRadius: '6px',
                          border: '1px solid rgba(147, 197, 253, 0.2)'
                        }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                            <span style={{ fontSize: '14px', fontWeight: 600, color: '#93c5fd' }}>
                              {opening}
                            </span>
                            <span style={{ fontSize: '14px', fontWeight: 600, color: '#e0e7ff' }}>
                              {data.avg_accuracy.toFixed(1)}% accuracy
                            </span>
                          </div>
                          <div style={{ display: 'flex', gap: '16px', fontSize: '12px', color: '#cbd5e1' }}>
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
          <div style={{ padding: '20px', textAlign: 'center', color: '#9ca3af' }}>
            No detailed analytics data available yet. Analyze more games to see detailed metrics.
          </div>
        )}
      </div>
    </div>
  );
}

