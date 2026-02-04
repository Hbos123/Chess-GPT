"use client";

import { useState, useEffect } from "react";
import DailyUsageDisplay from "@/components/DailyUsageDisplay";
import { mean, weightedMean } from "@/components/ProfileDashboard/components/graphs/graphSeries";

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

  const isSignedIn = !!userId;
  const isUnpaid = profileStatus?.tier_id === "unpaid" || profileStatus?.target_games === 0;
  const targetGames = typeof profileStatus?.target_games === "number" ? profileStatus.target_games : (isSignedIn ? 5 : 0);
  
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

  // Graph data (for trends + cp-loss chart)
  const [graphData, setGraphData] = useState<any[] | null>(null);
  const [graphDataLoading, setGraphDataLoading] = useState(false);
  
  // Analysis progress state (for move-by-move updates)
  const [analysisProgress, setAnalysisProgress] = useState<{
    currentGame: number;
    totalGames: number;
    currentMove: number;
    totalMoves: number;
    message: string;
  } | null>(null);
  
  // Listen for analysis progress updates from window events
  useEffect(() => {
    const handleProgress = (e: CustomEvent) => {
      const { status, message, progress } = e.detail;
      // Parse message to extract game/move info - be more flexible with patterns
      const gameMatch = message.match(/[Gg]ame (\d+)\/(\d+)/i) || message.match(/[Aa]nalyzing [Gg]ame (\d+)\/(\d+)/i);
      const moveMatch = message.match(/[Mm]ove (\d+)\/(\d+)/i) || message.match(/[Aa]nalyzing [Mm]ove (\d+)\/(\d+)/i);
      
      // Use target_games from profileStatus as the authoritative source for total games
      // This ensures we always show the subscription tier limit, not the backend response
      const targetGamesFromStatus = typeof profileStatus?.target_games === "number" ? profileStatus.target_games : (isSignedIn ? 5 : 0);
      
      if (gameMatch || moveMatch || (status === "analyzing" && message)) {
        setAnalysisProgress({
          currentGame: gameMatch ? parseInt(gameMatch[1]) : (analysisProgress?.currentGame || 0),
          // Always use target_games from subscription tier, not from the message
          totalGames: targetGamesFromStatus,
          currentMove: moveMatch ? parseInt(moveMatch[1]) : (analysisProgress?.currentMove || 0),
          totalMoves: moveMatch ? parseInt(moveMatch[2]) : (analysisProgress?.totalMoves || 0),
          message: message,
        });
      } else if (status === "complete" || status === "saving") {
        // Keep progress visible briefly after completion, then clear
        setTimeout(() => {
          setAnalysisProgress(null);
        }, 2000);
      }
    };
    
    window.addEventListener('analysis-progress' as any, handleProgress as EventListener);
    return () => {
      window.removeEventListener('analysis-progress' as any, handleProgress as EventListener);
    };
  }, [profileStatus?.target_games, isSignedIn]); // Only depend on target and sign-in state
  
  // Load linked accounts from profile overview
  useEffect(() => {
    if (!userId || !backendBase || isUnpaid) return;
    
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
  }, [userId, backendBase, isUnpaid]);
  
  // Cache diagnostic insights
  useEffect(() => {
    if (data?.strength_profile?.diagnostic_insights && Array.isArray(data.strength_profile.diagnostic_insights)) {
      setDiagnosticInsights(data.strength_profile.diagnostic_insights);
    }
  }, [data?.strength_profile?.diagnostic_insights]);

  // Fetch lightweight snapshot for the new Overview layout
  useEffect(() => {
    if (!userId || !backendBase || isUnpaid) return;
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
  }, [userId, backendBase, isUnpaid]);

  // Fetch per-game graph data (for trends + CP-loss-by-move chart)
  useEffect(() => {
    if (!userId || !backendBase || isUnpaid) return;
    let cancelled = false;

    const loadGraphData = async () => {
      setGraphDataLoading(true);
      try {
        const baseUrl = backendBase.replace(/\/$/, "");
        const url = `${baseUrl}/profile/analytics/${userId}/graph-data?limit=60`;
        const res = await fetch(url, { cache: "no-store" });
        if (!res.ok) throw new Error(`Failed to load graph data: ${res.status}`);
        const payload = await res.json();
        const games = Array.isArray(payload?.games) ? payload.games : [];
        if (!cancelled) setGraphData(games);
      } catch {
        if (!cancelled) setGraphData(null);
      } finally {
        if (!cancelled) setGraphDataLoading(false);
      }
    };

    loadGraphData();
    return () => {
      cancelled = true;
    };
  }, [userId, backendBase, isUnpaid]);
  
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
  // targetGames is already defined at the top of the component (line 21)
  const progressPercent = Math.min((activeGames / targetGames) * 100, 100);

  const computeLast3Trend = (values: Array<number | null | undefined>) => {
    const overall = mean(values as any);
    const last3 = mean(values.slice(-3) as any);
    if (overall == null || last3 == null) return null;
    return { overall, last3, delta: last3 - overall };
  };

  const TrendPill = ({ delta, fmt = (n: number) => n.toFixed(1) }: { delta: number; fmt?: (n: number) => string }) => {
    const abs = Math.abs(delta);
    const dir = abs < 0.05 ? "flat" : delta > 0 ? "up" : "down";
    const symbol = dir === "up" ? "▲" : dir === "down" ? "▼" : "—";
    const sign = dir === "flat" ? "" : delta > 0 ? "+" : "";
    return (
      <span className={`trend-pill ${dir}`} title="Last 3 games vs overall average">
        {symbol} {sign}{fmt(delta)}
      </span>
    );
  };

  const gamesForTrends = Array.isArray(graphData) ? graphData : [];
  const overallAccuracyTrend = computeLast3Trend(gamesForTrends.map((g: any) => g?.overall_accuracy));
  const avgCpLossTrend = computeLast3Trend(gamesForTrends.map((g: any) => g?.avg_cp_loss));
  const winRateTrend = (() => {
    const toScore = (r: any) => {
      const s = String(r || "").toLowerCase();
      if (s === "win") return 1;
      if (s === "draw") return 0.5;
      if (s === "loss") return 0;
      return null;
    };
    const overall = mean(gamesForTrends.map((g: any) => toScore(g?.result)).filter((v: any) => v != null) as any);
    const last3 = mean(gamesForTrends.slice(-3).map((g: any) => toScore(g?.result)).filter((v: any) => v != null) as any);
    if (overall == null || last3 == null) return null;
    return { overall: overall * 100, last3: last3 * 100, delta: (last3 - overall) * 100 };
  })();

  const cpLossByMoveSeries = (() => {
    // Aggregate per-game cp_loss_buckets into a weighted average series
    const buckets: Record<string, { start: number; end: number; items: Array<{ value: number | null; weight: number }> }> = {};
    for (const g of gamesForTrends) {
      const bs = g?.cp_loss_buckets;
      if (!Array.isArray(bs)) continue;
      for (const b of bs) {
        const start = Number(b?.start);
        const end = Number(b?.end);
        const val = typeof b?.avg_cp_loss === "number" ? b.avg_cp_loss : null;
        const weight = typeof b?.count === "number" ? b.count : 0;
        if (!Number.isFinite(start) || !Number.isFinite(end)) continue;
        const key = `${start}-${end}`;
        if (!buckets[key]) buckets[key] = { start, end, items: [] };
        buckets[key].items.push({ value: val, weight });
      }
    }
    const out = Object.values(buckets)
      .sort((a, b) => a.start - b.start)
      .map((b) => ({
        start: b.start,
        end: b.end,
        avg_cp_loss: weightedMean(b.items),
      }));
    return out.length ? out : null;
  })();

  const CpLossSparkline = ({ series }: { series: Array<{ start: number; end: number; avg_cp_loss: number | null }> }) => {
    const width = 520;
    const height = 140;
    const pad = 12;
    const ys = series.map((p) => p.avg_cp_loss).filter((v): v is number => typeof v === "number" && Number.isFinite(v));
    if (ys.length < 2) return null;
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys);
    const range = maxY - minY || 1;
    const pts = series.map((p, i) => {
      const x = pad + (i * (width - pad * 2)) / Math.max(1, series.length - 1);
      const yv = typeof p.avg_cp_loss === "number" ? p.avg_cp_loss : null;
      const y = yv == null ? null : pad + (1 - (yv - minY) / range) * (height - pad * 2);
      return { x, y, yv };
    });
    const d = pts
      .filter((p) => p.y != null)
      .map((p, idx) => `${idx === 0 ? "M" : "L"} ${p.x.toFixed(1)} ${(p.y as number).toFixed(1)}`)
      .join(" ");
    return (
      <svg width="100%" viewBox={`0 0 ${width} ${height}`} style={{ display: "block" }}>
        <path d={d} fill="none" stroke="rgba(125, 211, 252, 0.95)" strokeWidth="3" strokeLinecap="round" />
        <path d={`M ${pad} ${height - pad} L ${width - pad} ${height - pad}`} stroke="rgba(148, 163, 184, 0.25)" strokeWidth="1" />
        <text x={pad} y={pad + 10} fontSize="11" fill="rgba(203, 213, 225, 0.9)">
          {maxY.toFixed(0)}cp
        </text>
        <text x={pad} y={height - 2} fontSize="11" fill="rgba(203, 213, 225, 0.75)">
          {series[0].start}
        </text>
        <text x={width - pad} y={height - 2} fontSize="11" textAnchor="end" fill="rgba(203, 213, 225, 0.75)">
          {series[series.length - 1].end}
        </text>
      </svg>
    );
  };
  
  // Reduced logging - removed verbose target games logging
  
  // Get games being analyzed right now
  const gamesIndexed = profileStatus?.games_indexed || 0;
  const isAnalyzing = profileStatus?.state === "analyzing" || 
                      profileStatus?.state === "fetching" || 
                      profileStatus?.state === "reviewing" ||
                      (profileStatus?.state === "complete" && (profileStatus?.deep_analyzed_games || 0) < (profileStatus?.target_games || 0));
  
  // Check for newer games available
  const newerGamesAvailable = gamesIndexed > activeGames && activeGames >= targetGames;
  const newerGamesCount = newerGamesAvailable ? gamesIndexed - activeGames : 0;
  
  // Determine current activity status with real-time progress
  const getActivityStatus = () => {
    if (profileStatus?.state === "fetching") {
      const fetched = profileStatus?.games_indexed || 0;
      return `Fetching games... (${fetched} found so far)`;
    }
    if (profileStatus?.state === "analyzing" || profileStatus?.state === "reviewing") {
      const analyzed = profileStatus?.deep_analyzed_games || activeGames || 0;
      const total = targetGames; // Use target_games from subscription tier instead of games_indexed
      if (total > 0 && analyzed < total) {
        return `Analyzing game ${analyzed + 1} of ${total}...`;
      }
      return `Analyzing ${total || 'new'} game${total !== 1 ? 's' : ''}...`;
    }
    // Check for newer games when target is reached
    if (newerGamesAvailable) {
      return `${newerGamesCount} newer game${newerGamesCount > 1 ? 's' : ''} available - analyzing...`;
    }
    if (activeGames > targetGames) {
      const excess = activeGames - targetGames;
      return `Compressing oldest ${excess} game${excess > 1 ? 's' : ''}...`;
    }
    if (activeGames < targetGames) {
      const needed = targetGames - activeGames;
      if (isAnalyzing && gamesIndexed > activeGames) {
        return `Analyzing... (${activeGames}/${targetGames} complete)`;
      }
      return `${needed} more game${needed > 1 ? 's' : ''} needed`;
    }
    if (activeGames === targetGames && activeGames > 0) {
      return `${targetGames}-game window complete`;
    }
    return "No games analyzed yet";
  };

  return (
    <div className="overview-tab">
      {/* Summary Row */}
      {!isUnpaid && (
        <div className="tab-section overview-summary">
          <h2>Performance Summary</h2>
          <div className="stats-grid overview-summary-grid">
            <div className="stat-card">
              <span className="stat-label">Overall Accuracy</span>
              <span className="stat-value">
                {typeof snapshot?.avg_accuracy === "number" ? `${snapshot.avg_accuracy.toFixed(1)}%` : "—"}
              </span>
              {overallAccuracyTrend && <TrendPill delta={overallAccuracyTrend.delta} fmt={(n) => `${n.toFixed(1)}%`} />}
            </div>
            <div className="stat-card">
              <span className="stat-label">Avg CP Loss</span>
              <span className="stat-value">
                {typeof avgCpLossTrend?.overall === "number" ? `${avgCpLossTrend.overall.toFixed(1)}` : "—"}
              </span>
              {avgCpLossTrend && <TrendPill delta={avgCpLossTrend.delta} fmt={(n) => `${n.toFixed(1)}cp`} />}
            </div>
            <div className="stat-card">
              <span className="stat-label">Win Rate</span>
              <span className="stat-value">
                {snapshot?.rates?.win != null ? `${snapshot.rates.win.toFixed(1)}%` : "—"}
              </span>
              {winRateTrend && <TrendPill delta={winRateTrend.delta} fmt={(n) => `${n.toFixed(1)}%`} />}
            </div>
            <div className="stat-card">
              <span className="stat-label">CP Loss by Move #</span>
              {graphDataLoading ? (
                <div style={{ color: "#93c5fd", fontSize: 13, marginTop: 10 }}>Loading…</div>
              ) : cpLossByMoveSeries ? (
                <div style={{ marginTop: 10 }}>
                  <CpLossSparkline series={cpLossByMoveSeries} />
                </div>
              ) : (
                <div style={{ color: "#9ca3af", fontSize: 13, marginTop: 10 }}>
                  Not enough CP-loss data yet.
                </div>
              )}
            </div>
          </div>
        </div>
      )}

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
        {/* Newer games available indicator */}
        {newerGamesAvailable && !isAnalyzing && (
          <div style={{ 
            marginTop: '8px', 
            padding: '8px 12px', 
            background: 'rgba(251, 191, 36, 0.15)', 
            borderRadius: '6px',
            border: '1px solid rgba(251, 191, 36, 0.3)',
            fontSize: '12px',
            color: '#fbbf24'
          }}>
            🔄 {newerGamesCount} newer game{newerGamesCount > 1 ? 's' : ''} detected - will analyze and replace oldest
          </div>
        )}
        {/* Compression status indicator */}
        {activeGames > targetGames && (
          <div style={{ 
            marginTop: '8px', 
            padding: '8px 12px', 
            background: 'rgba(168, 85, 247, 0.15)', 
            borderRadius: '6px',
            border: '1px solid rgba(168, 85, 247, 0.3)',
            fontSize: '12px',
            color: '#a855f7'
          }}>
            📦 Compressing oldest games to maintain {targetGames}-game window
          </div>
        )}
        {/* Move-by-move progress display */}
        {isAnalyzing && analysisProgress && (
          <div style={{ 
            marginTop: '12px', 
            padding: '10px', 
            background: 'rgba(59, 130, 246, 0.15)', 
            borderRadius: '6px',
            border: '1px solid rgba(59, 130, 246, 0.3)'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
              <span style={{ fontSize: '12px', fontWeight: 600, color: '#93c5fd' }}>
                Game {analysisProgress.currentGame}/{analysisProgress.totalGames}
              </span>
              {analysisProgress.currentMove > 0 && (
                <span style={{ fontSize: '12px', color: '#cbd5e1' }}>
                  Move {analysisProgress.currentMove}/{analysisProgress.totalMoves}
                </span>
              )}
            </div>
            {analysisProgress.message && (
              <div style={{ fontSize: '11px', color: '#cbd5e1', opacity: 0.8 }}>
                {analysisProgress.message}
              </div>
            )}
          </div>
        )}
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
                : "Not enough opening data yet"}
            </span>
          </div>
          <div className="stat-card">
            <span className="stat-label">As Black (Faced)</span>
            <span className="stat-value">
              {snapshot?.openings?.as_black_faced?.name
                ? `${snapshot.openings.as_black_faced.name} (${snapshot.openings.as_black_faced.pct ?? 0}%)`
                : "Not enough opening data yet"}
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
          <button
            type="button"
            onClick={() => {
              if (!isSignedIn) {
                window.location.href = "/auth";
                return;
              }
              if (isUnpaid) {
                // Unpaid users don't have stored analytics; prompt upgrade via settings/profile.
                window.location.href = "/app?settings=open";
                return;
              }
              onOpenPersonalReview?.();
            }}
            className="generate-training-btn"
            style={{
              whiteSpace: "nowrap",
              opacity: (!isSignedIn || isUnpaid) ? 0.55 : 1,
              cursor: (!isSignedIn || isUnpaid) ? "pointer" : "pointer",
            }}
            title={
              !isSignedIn
                ? "Sign in to use Personal Review"
                : isUnpaid
                  ? "Upgrade to unlock Personal Review"
                  : undefined
            }
          >
            Personal Review
          </button>
        </div>
        {!isSignedIn && (
          <div style={{ fontSize: 12, color: "#93c5fd", marginTop: -6 }}>
            <a href="/auth" style={{ color: "#93c5fd", textDecoration: "underline" }}>
              Sign in
            </a>{" "}
            to unlock your Personal Review.
          </div>
        )}
        {isSignedIn && isUnpaid && (
          <div style={{ fontSize: 12, color: "#93c5fd", marginTop: -6 }}>
            Upgrade to analyze games and unlock Personal Review.
          </div>
        )}

        {snapshotError && (
          <div className="error-message" style={{ marginTop: 12 }}>
            <p>Failed to load snapshot: {snapshotError}</p>
          </div>
        )}

        {isUnpaid ? (
          <div style={{ padding: "12px", color: "#93c5fd" }}>
            Upgrade to generate a snapshot and track your progress.
          </div>
        ) : snapshotLoading && !snapshot ? (
          <div style={{ padding: "20px", textAlign: "center", color: "#93c5fd" }}>
            Loading snapshot...
          </div>
        ) : (
          <div className="stats-grid" style={{ marginTop: 12 }}>
            <div className="stat-card">
              <span className="stat-label">Games Analyzed</span>
              <span className="stat-value">{snapshot?.games_analyzed ?? 0}/{targetGames}</span>
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

