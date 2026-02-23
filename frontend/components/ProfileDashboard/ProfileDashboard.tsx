"use client";

import { useState, useEffect } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useUsage } from "@/contexts/UsageContext";
import { fetchProfileOverview, fetchProfileStats } from "@/lib/api";
import { getBackendBase } from "@/lib/backendBase";
import OverviewTab from "./tabs/OverviewTab";
import RecentGamesTab from "./tabs/RecentGamesTab";
import GraphsTab from "./tabs/GraphsTab";
import HabitsPatternsTab from "./tabs/HabitsPatternsTab";
import TrainingTab from "./tabs/TrainingTab";
import PersonalReview from "@/components/PersonalReview";
import "./ProfileDashboard.css";

interface ProfileDashboardProps {
  onClose: () => void;
  initialTab?: string;
  onCreateNewTab?: (params: any) => void;
}

export type TabType = 'overview' | 'recent' | 'graphs' | 'habits' | 'training';

export default function ProfileDashboard({ onClose, initialTab = 'overview', onCreateNewTab }: ProfileDashboardProps) {
  const { user } = useAuth();
  const { usage } = useUsage();
  const normalizedInitialTab = (initialTab === "lifetime" ? "graphs" : initialTab) as TabType;
  const [activeTab, setActiveTab] = useState<TabType>(normalizedInitialTab);
  
  const [loading, setLoading] = useState(true); // Start with loading true
  const [error, setError] = useState<string | null>(null);
  const [analyticsData, setAnalyticsData] = useState<any>(null); // Start with null instead of dummy data
  const [profileStatus, setProfileStatus] = useState<any>(null); // Start with null instead of dummy data
  const [profilePreferences, setProfilePreferences] = useState<any>(null); // from /profile/overview
  const [showPersonalReview, setShowPersonalReview] = useState(false);
  const [patternHistory, setPatternHistory] = useState<{current: any[], historical: any[]}>({ current: [], historical: [] }); // Start with empty arrays
  const backendBase = getBackendBase();

  const isSignedIn = !!user?.id;
  const tierId = usage?.tier_id;
  const isUnpaid = isSignedIn && tierId === "unpaid";

  // If user is unsigned in, don't spin forever — show a simple sign-in state.
  useEffect(() => {
    if (isSignedIn) return;
    setLoading(false);
    setError(null);
    setAnalyticsData(null);
    setPatternHistory({ current: [], historical: [] });
    setProfileStatus({
      tier_id: "unpaid",
      state: "idle",
      message: "Sign in to unlock your profile analytics.",
      target_games: 0,
      deep_analyzed_games: 0,
      games_indexed: 0,
      total_games_estimate: 0,
      progress_percent: 0,
    });
  }, [isSignedIn]);

  // For signed-in unpaid users, skip all profile/analytics fetches (no stored data) and show a locked state.
  useEffect(() => {
    if (!isUnpaid) return;
    setLoading(false);
    setError(null);
    setAnalyticsData(null);
    setPatternHistory({ current: [], historical: [] });
    setProfileStatus({
      tier_id: "unpaid",
      state: "idle",
      message: "Upgrade to analyze games and unlock your personal dashboard.",
      target_games: 0,
      deep_analyzed_games: 0,
      games_indexed: 0,
      total_games_estimate: 0,
      progress_percent: 0,
    });
  }, [isUnpaid]);

  // Load profile status to get analyzed games count - poll more frequently when analyzing
  useEffect(() => {
    if (!user?.id || isUnpaid) return;

    const loadProfileStatus = async () => {
      try {
        const overviewUrl = `${backendBase.replace(/\/$/, "")}/profile/overview?user_id=${user.id}`;
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 8000);
        const response = await fetch(overviewUrl, { cache: "no-store", signal: controller.signal });
        clearTimeout(timeoutId);
        if (response.ok) {
          const data = await response.json();
          const newStatus = data.status || null;
          if (data?.preferences) setProfilePreferences(data.preferences);
          
          // Reduced logging - only log when state changes significantly
          if (newStatus?.state !== profileStatus?.state || 
              newStatus?.deep_analyzed_games !== profileStatus?.deep_analyzed_games) {
            console.log('[ProfileDashboard] Status update:', {
              state: newStatus?.state,
              analyzed: newStatus?.deep_analyzed_games,
              target: newStatus?.target_games
            });
          }
          
          setProfileStatus(newStatus);
          
          // If actively analyzing, trigger analytics refresh too
          if (newStatus?.state === "analyzing" || newStatus?.state === "fetching" || newStatus?.state === "reviewing") {
            // Analytics will auto-refresh, but this ensures we see updates
          }
        }
      } catch (e) {
        // Non-fatal - just don't show progress
        console.warn("[ProfileDashboard] Failed to load profile status:", e);
      }
    };

    loadProfileStatus();
    
    // Poll more frequently when actively analyzing (every 2s), otherwise every 6s
    const getPollInterval = () => {
      const state = profileStatus?.state;
      return (state === "analyzing" || state === "fetching" || state === "reviewing") ? 2000 : 6000;
    };
    
    // Start with initial interval
    let pollInterval = setInterval(loadProfileStatus, getPollInterval());
    
    // Update interval when status changes
    const updateInterval = () => {
      clearInterval(pollInterval);
      pollInterval = setInterval(loadProfileStatus, getPollInterval());
    };
    
    // Watch for status changes to adjust polling frequency
    const statusCheckInterval = setInterval(updateInterval, 1000);

    return () => {
      clearInterval(pollInterval);
      clearInterval(statusCheckInterval);
    };
  }, [user?.id, backendBase, profileStatus?.state, isUnpaid]);

  // Fetch pattern history for graphing
  useEffect(() => {
    if (!user?.id || isUnpaid) return;

    const fetchPatternHistory = async () => {
      try {
        const response = await fetch(
          `${backendBase.replace(/\/$/, "")}/profile/analytics/${user.id}/patterns/history?days=30`,
          { cache: "no-store" } // Always fetch fresh
        );
        if (response.ok) {
          const data = await response.json();
          // Separate current vs historical patterns
          const current = data.patterns?.filter((p: any) => p.pattern_type === 'current') || [];
          const historical = data.patterns?.filter((p: any) => p.pattern_type === 'historical') || [];
          setPatternHistory({ current, historical });
        }
      } catch (e) {
        console.warn("[ProfileDashboard] Failed to load pattern history:", e);
      }
    };

    fetchPatternHistory();
    
    // Refresh pattern history more frequently when analyzing
    const isAnalyzing = profileStatus?.state === "analyzing" || profileStatus?.state === "fetching" || profileStatus?.state === "reviewing";
    const refreshInterval = isAnalyzing ? 5000 : 30000; // 5s when analyzing, 30s otherwise
    
    const interval = setInterval(fetchPatternHistory, refreshInterval);
    
    return () => clearInterval(interval);
  }, [user?.id, backendBase, profileStatus?.state, isUnpaid]);

  // Background warm-up for detailed analytics.
  // IMPORTANT: defer this work so opening the Profile modal isn't slowed down by
  // competing requests/compute. This does not change functionality (tabs still
  // fetch their own data); it only reduces redundant load.
  useEffect(() => {
    if (!user?.id || !backendBase || isUnpaid) return;
    // Only warm detailed analytics when the user is likely to need it.
    // (Graphs/Training tabs use it for suggestions and deeper breakdowns.)
    if (activeTab !== "graphs" && activeTab !== "training") return;
    let cancelled = false;
    let timeoutId: any = null;

    const warm = async () => {
      if (cancelled) return;
      try {
        const baseUrl = backendBase.replace(/\/$/, "");
        await fetch(`${baseUrl}/profile/analytics/${user.id}/detailed`, { cache: "no-store" });
      } catch {
        // non-fatal; this is best-effort warmup
      }
    };

    // Prefer idle time; fallback to a longer delay to avoid competing with the initial
    // /profile/overview + /profile/analytics calls.
    // @ts-ignore - requestIdleCallback not in TS lib by default.
    if (typeof window !== "undefined" && typeof (window as any).requestIdleCallback === "function") {
      // @ts-ignore
      (window as any).requestIdleCallback(() => warm(), { timeout: 15000 });
    } else {
      timeoutId = setTimeout(() => warm(), 12000);
    }

    return () => {
      cancelled = true;
      if (timeoutId) clearTimeout(timeoutId);
    };
  }, [user?.id, backendBase, isUnpaid, activeTab]);

  useEffect(() => {
    if (!user?.id || isUnpaid) return;

    let pollInterval: NodeJS.Timeout | null = null;
    let analyticsRefreshInterval: NodeJS.Timeout | null = null;
    let abortController: AbortController | null = null; // Track current request
    let loadTimeout: NodeJS.Timeout | null = null; // For debouncing
    let isMounted = true; // Track if component is still mounted

    const loadAnalytics = async () => {
      // Cancel any previous request
      if (abortController) {
        abortController.abort();
      }
      
      // Don't proceed if component unmounted
      if (!isMounted) return;
      
      setLoading(true);
      let isComputing = false;
      try {
        const url = `${backendBase.replace(/\/$/, "")}/profile/analytics/${user.id}`;
        console.log("[ProfileDashboard] Loading analytics:", { url });

        // Create new abort controller for this request
        abortController = new AbortController();
        const currentController = abortController; // Capture for timeout check

        const fetchWithRetry = async (attempts: number) => {
          let lastErr: any = null;
          for (let i = 0; i < attempts; i++) {
            // Check if request was aborted before retrying
            if (currentController.signal.aborted || !isMounted) {
              throw new Error("Request aborted");
            }
            
            try {
              // Increase timeout to 30 seconds to account for deduplication and computation time
              const timeoutId = setTimeout(() => {
                if (!currentController.signal.aborted) {
                  currentController.abort();
                }
              }, 30000);
              
              const res = await fetch(url, { 
                signal: currentController.signal, 
                cache: "no-store" 
              });
              
              clearTimeout(timeoutId);
              return res;
            } catch (e) {
              lastErr = e;
              
              // Don't retry if aborted (component unmounted or new request started)
              if (currentController.signal.aborted || !isMounted) {
                throw e;
              }
              
              // Only retry on network-ish failures
              const msg = e instanceof Error ? e.message : String(e);
              if (i < attempts - 1 && !msg.toLowerCase().includes("abort")) {
                await new Promise((r) => setTimeout(r, 400 * (i + 1)));
                continue;
              }
              throw e;
            }
          }
          throw lastErr;
        };

        const response = await fetchWithRetry(3);
        if (!response.ok) {
          const errorText = await response.text();
          throw new Error(`Failed to fetch analytics: ${errorText}`);
        }
        const data = await response.json();

        // Backend may respond quickly with a "computing" placeholder while analytics build in the background.
        if (data?.status === "computing") {
          // Set data immediately so UI can render with empty placeholders
          setAnalyticsData(data);
          setError(null);
          setLoading(false); // Don't show spinner - render tabs with empty data
          console.log("[ProfileDashboard] Analytics computing in background, will poll for updates");
          // Poll for completion every 5 seconds (max 2 minutes)
          let pollCount = 0;
          const maxPolls = 24; // 24 * 5s = 2 minutes max
          pollInterval = setInterval(async () => {
            pollCount++;
            if (pollCount > maxPolls) {
              if (pollInterval) clearInterval(pollInterval);
              setError("Analytics computation is taking longer than expected. Please refresh.");
              return;
            }
            try {
              // Don't poll if component unmounted
              if (!isMounted) {
                if (pollInterval) clearInterval(pollInterval);
                return;
              }
              
              const controller = new AbortController();
              const timeoutId = setTimeout(() => controller.abort(), 15000); // Increased from 8s to 15s
              const pollResponse = await fetch(url, { cache: "no-store", signal: controller.signal });
              clearTimeout(timeoutId);
              
              if (!isMounted) return; // Check again after fetch
              
              if (pollResponse.ok) {
                const pollData = await pollResponse.json();
                if (pollData?.status !== "computing" && pollData?.status !== "error") {
                  if (pollInterval) clearInterval(pollInterval);
                  setAnalyticsData(pollData);
                  setError(null);
                  console.log("[ProfileDashboard] Analytics computation completed");
                }
              }
            } catch (e) {
              // Ignore poll errors if component unmounted or aborted
              if (!isMounted || (e instanceof Error && e.name === "AbortError")) {
                if (pollInterval) clearInterval(pollInterval);
                return;
              }
              // Ignore other poll errors, keep polling
              console.warn("[ProfileDashboard] Poll error (non-fatal):", e);
            }
          }, 5000);
          return;
        }
        
        // Handle null/undefined data gracefully
        if (!data || typeof data !== 'object') {
          console.warn("No analytics data received - games may not be indexed yet");
          setAnalyticsData({
            lifetime_stats: {},
            patterns: {},
            strength_profile: {},
            rolling_window: {},
            deltas: {}
          });
          return;
        }
        
        // Ensure all expected fields exist with defaults
        const safeData = {
          lifetime_stats: data.lifetime_stats || {},
          patterns: data.patterns || {},
          strength_profile: data.strength_profile || {},
          rolling_window: data.rolling_window || {},
          deltas: data.deltas || {},
          ...data // Preserve any other fields
        };
        
        // Check if data is empty (no games indexed)
        const hasData = safeData.lifetime_stats && Object.keys(safeData.lifetime_stats).length > 0;
        if (!hasData) {
          console.warn("No analytics data - games may not be indexed yet");
        }
        
        setAnalyticsData(safeData);
      } catch (err: any) {
        // Don't set error state if component unmounted or request was intentionally aborted
        if (!isMounted) return;
        
        // Don't show error for intentional aborts (new request started or component unmounting)
        if (err?.name === "AbortError" && abortController?.signal.aborted) {
          console.log("[ProfileDashboard] Analytics request aborted (likely replaced by new request)");
          return;
        }
        
        console.error("Error loading analytics:", err);
        const msg = err?.name === "AbortError"
          ? "Request timed out."
          : (err?.message || String(err));
        setError(`Failed to load your profile analytics: ${msg}. (backend: ${backendBase})`);
        // Set empty data structure so UI can still render
        setAnalyticsData({
          lifetime_stats: {},
          patterns: {},
          strength_profile: {}
        });
      } finally {
        // Always end loading so tabs can render (even with empty data)
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    // Debounced load function to prevent rapid-fire requests
    const debouncedLoadAnalytics = () => {
      if (loadTimeout) clearTimeout(loadTimeout);
      loadTimeout = setTimeout(() => {
        if (isMounted) {
          loadAnalytics();
        }
      }, 500); // Wait 500ms before loading
    };

    // Initial load (no debounce for first load)
    loadAnalytics();
    
    // Poll analytics more frequently when actively analyzing (to catch pattern updates)
    const getAnalyticsPollInterval = () => {
      const state = profileStatus?.state;
      // Poll every 3 seconds when analyzing (to catch pattern updates), otherwise 15 seconds
      return (state === "analyzing" || state === "fetching" || state === "reviewing") ? 3000 : 15000;
    };
    
    // Start with initial interval (use debounced version to prevent rapid-fire)
    analyticsRefreshInterval = setInterval(debouncedLoadAnalytics, getAnalyticsPollInterval());
    
    // Update interval when status changes
    const updateAnalyticsInterval = () => {
      if (!isMounted) return;
      if (analyticsRefreshInterval) clearInterval(analyticsRefreshInterval);
      analyticsRefreshInterval = setInterval(debouncedLoadAnalytics, getAnalyticsPollInterval());
    };
    
    // Watch for status changes to adjust polling frequency
    const statusCheckInterval = setInterval(updateAnalyticsInterval, 1000);
    
    // Cleanup: clear polling interval on unmount or user change
    return () => {
      isMounted = false; // Mark as unmounted
      
      // Cancel any in-flight request
      if (abortController) {
        abortController.abort();
      }
      
      // Clear all timeouts and intervals
      if (loadTimeout) clearTimeout(loadTimeout);
      if (pollInterval) clearInterval(pollInterval);
      if (analyticsRefreshInterval) clearInterval(analyticsRefreshInterval);
      clearInterval(statusCheckInterval);
    };
  }, [user?.id, backendBase, profileStatus?.state, isUnpaid]);

  const tabs: { id: TabType; label: string }[] = [
    { id: 'overview', label: 'Overview' },
    { id: 'recent', label: 'Recent Games' },
    { id: 'graphs', label: 'Graphs' },
    { id: 'habits', label: 'Habits & Patterns' },
    { id: 'training', label: 'Training' },
  ];

  return (
    <div className="profile-dashboard-overlay" onClick={onClose}>
      <div className="profile-dashboard-container" onClick={(e) => e.stopPropagation()}>
        {/* Desktop Sidebar - hidden on mobile */}
        <div className="profile-dashboard-sidebar desktop-only">
          <div className="sidebar-header">
            <div className="user-avatar-large">
              {user?.email?.[0].toUpperCase() || 'P'}
            </div>
            <h3>Your Profile</h3>
          </div>
          <nav className="sidebar-nav">
            {tabs.map((tab) => {
              const locked = !isSignedIn || (isUnpaid && tab.id !== "overview");
              return (
                <button
                  key={tab.id}
                  className={`nav-item ${activeTab === tab.id ? 'active' : ''}`}
                  onClick={() => {
                    if (locked) {
                      if (!isSignedIn) window.location.href = "/auth";
                      return;
                    }
                    setActiveTab(tab.id);
                  }}
                  disabled={locked}
                  title={
                    !isSignedIn
                      ? "Sign in to unlock your profile"
                      : (isUnpaid && tab.id !== "overview")
                        ? "Upgrade to unlock this tab"
                        : undefined
                  }
                  style={locked ? { opacity: 0.55, cursor: "not-allowed" } : undefined}
                >
                  <span className="nav-label">{tab.label}</span>
                </button>
              );
            })}
          </nav>
          <div className="sidebar-footer">
            <button className="close-dashboard-btn" onClick={onClose}>
              Close Dashboard
            </button>
          </div>
        </div>

        {/* Main Content Area */}
        <div className="profile-dashboard-main">
          {/* Mobile Header - shown only on mobile */}
          <div className="mobile-header mobile-only">
            <div className="mobile-header-content">
              <div className="user-avatar-small">
                {user?.email?.[0].toUpperCase() || 'P'}
              </div>
              <h3>Your Profile</h3>
              <button className="close-dashboard-btn-mobile" onClick={onClose}>
                ×
              </button>
            </div>
          </div>

          {/* Content */}
          {!isSignedIn ? (
            <div className="dashboard-loading">
              <p style={{ margin: 0 }}>Sign in to unlock your profile analytics.</p>
              <div style={{ marginTop: 12 }}>
                <a href="/auth" className="close-dashboard-btn" style={{ textDecoration: "none" }}>
                  Sign In / Create Account
                </a>
              </div>
            </div>
          ) : loading ? (
            <div className="dashboard-loading">
              <div className="spinner"></div>
              <p>Analyzing your chess journey...</p>
            </div>
          ) : (
            <div className="dashboard-tab-content">
              {activeTab === 'overview' && (
                <OverviewTab
                  data={analyticsData}
                  profileStatus={profileStatus}
                  onOpenPersonalReview={() => {
                    if (isUnpaid) return;
                    setShowPersonalReview(true);
                  }}
                  userId={user?.id}
                  backendBase={backendBase}
                  preferences={profilePreferences}
                />
              )}
              {!isUnpaid && activeTab === 'recent' && <RecentGamesTab userId={user?.id || ''} onCreateNewTab={onCreateNewTab} />}
              {!isUnpaid && activeTab === 'graphs' && <GraphsTab userId={user?.id || ''} backendBase={backendBase} />}
              {!isUnpaid && activeTab === 'habits' && <HabitsPatternsTab userId={user?.id || ''} backendBase={backendBase} />}
              {!isUnpaid && activeTab === 'training' && (
                <TrainingTab
                  userId={user?.id || ''}
                  backendBase={backendBase}
                  onCreateNewTab={onCreateNewTab}
                  onCloseDashboard={onClose}
                />
              )}
            </div>
          )}
          {error && <div className="dashboard-error-banner">{error}</div>}
        </div>

        {/* Mobile bottom nav (PWA-friendly, safe-area aware) */}
        <div
          className="profile-dashboard-mobile-nav mobile-only"
          onClick={(e) => e.stopPropagation()}
        >
          {tabs.map((tab) => {
            const locked = !isSignedIn || (isUnpaid && tab.id !== "overview");
            return (
              <button
                key={tab.id}
                className={`profile-dashboard-mobile-nav-item ${activeTab === tab.id ? "active" : ""}`}
                onClick={() => {
                  if (locked) {
                    if (!isSignedIn) window.location.href = "/auth";
                    return;
                  }
                  setActiveTab(tab.id);
                }}
                type="button"
                disabled={locked}
                style={locked ? { opacity: 0.55, cursor: "not-allowed" } : undefined}
              >
                {tab.label}
              </button>
            );
          })}
        </div>
      </div>

      {showPersonalReview && isSignedIn && !isUnpaid && (
        <PersonalReview
          onClose={() => setShowPersonalReview(false)}
          onCreateNewTab={onCreateNewTab}
        />
      )}
    </div>
  );
}




