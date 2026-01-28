"use client";

import { useState, useEffect } from "react";
import DailyUsageDisplay from "@/components/DailyUsageDisplay";

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
  
  // Diagnostic insights caching
  const [diagnosticInsights, setDiagnosticInsights] = useState<any[] | null>(null);

  // Lightweight overview snapshot (new Overview UI)
  const [snapshot, setSnapshot] = useState<any | null>(null);
  const [snapshotLoading, setSnapshotLoading] = useState(false);
  const [snapshotError, setSnapshotError] = useState<string | null>(null);
  
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
  
  // Cache diagnostic insights
  useEffect(() => {
    if (data?.strength_profile?.diagnostic_insights && Array.isArray(data.strength_profile.diagnostic_insights)) {
      setDiagnosticInsights(data.strength_profile.diagnostic_insights);
    }
  }, [data?.strength_profile?.diagnostic_insights]);

  // Fetch lightweight snapshot for the new Overview layout
  useEffect(() => {
    if (!userId || !backendBase) return;
    let cancelled = false;

    const loadSnapshot = async () => {
      setSnapshotLoading(true);
      setSnapshotError(null);
      try {
        const baseUrl = backendBase.replace(/\/$/, "");
        const url = `${baseUrl}/profile/overview/snapshot?user_id=${userId}&limit=60`;
        const res = await fetch(url, { cache: "no-store" });
        if (!res.ok) {
          const t = await res.text();
          throw new Error(`${res.status} ${t}`);
        }
        const payload = await res.json();
        if (!cancelled) setSnapshot(payload);
      } catch (e: any) {
        if (!cancelled) {
          setSnapshot(null);
          setSnapshotError(e?.message || "Failed to load snapshot");
        }
      } finally {
        if (!cancelled) setSnapshotLoading(false);
      }
    };

    loadSnapshot();
    return () => {
      cancelled = true;
    };
  }, [userId, backendBase]);
  
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

      {/* Daily Usage Section */}
      <DailyUsageDisplay />

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

      <div className="tab-section">
        <h2>Rating Context</h2>
        <div className="stats-grid">
          <div className="stat-card">
            <span className="stat-label">Current Rating</span>
            <span className="stat-value">{snapshot?.rating?.current ?? "---"}</span>
          </div>
          <div className="stat-card">
            <span className="stat-label">Trend</span>
            <span className="stat-value">
              {snapshot?.rating?.trend === "up"
                ? "↑ Improving"
                : snapshot?.rating?.trend === "down"
                ? "↓ Declining"
                : snapshot?.rating?.trend === "stable"
                ? "→ Stable"
                : "—"}
            </span>
          </div>
        </div>
      </div>

      <div className="tab-section">
        <h2>Player Snapshot</h2>
        <div className="stats-grid">
          <div className="stat-card">
            <span className="stat-label">Time Style</span>
            <span className="stat-value">{snapshot?.time_style?.label ?? "---"}</span>
          </div>
          <div className="stat-card highlight-card green">
            <span className="stat-label">Top Strength</span>
            <span className="stat-value">
              {snapshot?.identity?.note ? `Emerging Pattern: ${snapshot?.identity?.top_strength}` : snapshot?.identity?.top_strength ?? "---"}
            </span>
          </div>
          <div className="stat-card highlight-card red">
            <span className="stat-label">Focus Area</span>
            <span className="stat-value">
              {snapshot?.identity?.note ? `Emerging Pattern: ${snapshot?.identity?.focus_area}` : snapshot?.identity?.focus_area ?? "---"}
            </span>
          </div>
        </div>
      </div>

      <div className="tab-section">
        <h2>Openings Snapshot</h2>
        <div className="stats-grid">
          <div className="stat-card">
            <span className="stat-label">As White</span>
            <span className="stat-value">
              {snapshot?.openings?.as_white?.name
                ? `${snapshot.openings.as_white.name} (${snapshot.openings.as_white.pct ?? 0}%)`
                : "---"}
            </span>
          </div>
          <div className="stat-card">
            <span className="stat-label">As Black (Faced)</span>
            <span className="stat-value">
              {snapshot?.openings?.as_black_faced?.name
                ? `${snapshot.openings.as_black_faced.name} (${snapshot.openings.as_black_faced.pct ?? 0}%)`
                : "---"}
            </span>
          </div>
        </div>
      </div>

      <div className="tab-section">
        <h2>Streak & Momentum</h2>
        <div className="stats-grid">
          <div className="stat-card">
            <span className="stat-label">Best Win Streak</span>
            <span className="stat-value">{snapshot?.momentum?.best_win_streak ?? 0}</span>
          </div>
          <div className="stat-card">
            <span className="stat-label">Current Form</span>
            <span className="stat-value">
              {typeof snapshot?.momentum?.wins_last_5 === "number" ? `${snapshot.momentum.wins_last_5} wins in last 5` : "---"}
            </span>
          </div>
        </div>

        {Array.isArray(snapshot?.momentum?.results_last_10) && snapshot.momentum.results_last_10.length > 0 && (
          <div style={{ marginTop: 12, display: "flex", gap: 6, flexWrap: "wrap" }}>
            {snapshot.momentum.results_last_10.map((r: string, idx: number) => (
              <span
                key={idx}
                style={{
                  padding: "4px 8px",
                  borderRadius: 999,
                  fontSize: 12,
                  background:
                    r === "win" ? "rgba(16, 185, 129, 0.2)" : r === "loss" ? "rgba(239, 68, 68, 0.2)" : "rgba(148, 163, 184, 0.2)",
                  color: r === "win" ? "#10b981" : r === "loss" ? "#ef4444" : "#cbd5e1",
                  border: "1px solid rgba(147, 197, 253, 0.15)",
                }}
              >
                {r === "win" ? "W" : r === "loss" ? "L" : r === "draw" ? "D" : "?"}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Personal Review Section - Moved to bottom */}
      <div className="tab-section">
        <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center", marginBottom: 12 }}>
          <div>
            <h2 style={{ margin: 0, fontSize: "18px" }}>Personal Review</h2>
            <div style={{ fontSize: "13px", color: "#cbd5e1", marginTop: 4 }}>
              Ask for a tailored personal review based on any number of recent games
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

        {snapshotError && (
          <div className="error-message" style={{ marginTop: 12 }}>
            <p>Failed to load snapshot: {snapshotError}</p>
          </div>
        )}

        {snapshotLoading && !snapshot ? (
          <div style={{ padding: "20px", textAlign: "center", color: "#93c5fd" }}>
            Loading snapshot...
          </div>
        ) : (
          <div className="stats-grid" style={{ marginTop: 12 }}>
            <div className="stat-card">
              <span className="stat-label">Games Analyzed</span>
              <span className="stat-value">{snapshot?.games_analyzed ?? 0}/{snapshot?.window ?? 60}</span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Record</span>
              <span className="stat-value">
                {snapshot?.record
                  ? `${snapshot.record.wins}W – ${snapshot.record.draws}D – ${snapshot.record.losses}L`
                  : "---"}
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

