"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import SafeAreaView from "./SafeAreaView";
import { useProfileAnalyticsData } from "./useProfileAnalyticsData";
import "./AnalyticsOverviewV2.css";

interface AnalyticsOverviewV2Props {
  userId: string;
  onOpenPersonalReview: () => void;
  embedded?: boolean;
}

const MIN_GAMES_FOR_INSIGHTS = 10;

const normalizePlatform = (platform?: string) => {
  if (!platform) return "chess.com";
  if (platform === "chesscom" || platform === "chess.com") return "chess.com";
  if (platform === "lichess") return "lichess";
  return platform;
};

const formatPercent = (value?: number | null) =>
  typeof value === "number" ? `${value}%` : "—";

const formatValue = (value?: string | number | null) =>
  value === 0 || value ? String(value) : "—";

const getTrendLabel = (trend?: string) => {
  if (trend === "up") return "Up";
  if (trend === "down") return "Down";
  if (trend === "stable") return "Stable";
  return "—";
};

export default function AnalyticsOverviewV2({
  userId,
  onOpenPersonalReview,
  embedded = false,
}: AnalyticsOverviewV2Props) {
  const {
    backendBase,
    loading,
    error,
    analyticsData,
    profileStatus,
    profileOverview,
    refreshAnalytics,
    refreshProfileOverview,
  } = useProfileAnalyticsData(userId);

  const [snapshot, setSnapshot] = useState<any | null>(null);
  const [snapshotLoading, setSnapshotLoading] = useState(false);
  const [snapshotError, setSnapshotError] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const [linkedAccounts, setLinkedAccounts] = useState<
    Array<{ platform: string; username: string }>
  >([]);
  const [isEditing, setIsEditing] = useState(false);
  const [newAccountPlatform, setNewAccountPlatform] = useState<
    "chess.com" | "lichess"
  >("chess.com");
  const [newAccountUsername, setNewAccountUsername] = useState("");
  const [isValidating, setIsValidating] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const accountsRef = useRef<HTMLDivElement | null>(null);

  const loadSnapshot = useCallback(async () => {
    if (!userId || !backendBase) return;
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
      setSnapshot(payload);
    } catch (e: any) {
      setSnapshot(null);
      setSnapshotError(e?.message || "Failed to load snapshot");
    } finally {
      setSnapshotLoading(false);
    }
  }, [backendBase, userId]);

  useEffect(() => {
    loadSnapshot();
  }, [loadSnapshot]);

  useEffect(() => {
    const rawAccounts = profileOverview?.preferences?.accounts;
    if (!Array.isArray(rawAccounts)) {
      if (!rawAccounts) return;
      setLinkedAccounts([]);
      return;
    }
    const normalized = rawAccounts.map((acc: any) => ({
      platform: normalizePlatform(acc?.platform),
      username: acc?.username || "",
    }));
    setLinkedAccounts(normalized);
  }, [profileOverview?.preferences?.accounts]);

  const hasLinkedAccounts = linkedAccounts.length > 0;
  const activeGames =
    snapshot?.games_analyzed ??
    profileStatus?.deep_analyzed_games ??
    profileStatus?.games_indexed ??
    0;
  const targetGames = snapshot?.window ?? profileStatus?.target_games ?? 60;
  const hasEnoughGames = activeGames >= MIN_GAMES_FOR_INSIGHTS;

  const winRate =
    snapshot?.rates?.win ??
    (typeof analyticsData?.rolling_window?.win_rate === "number"
      ? analyticsData.rolling_window.win_rate
      : null);
  const avgAccuracy =
    snapshot?.avg_accuracy ??
    (typeof analyticsData?.rolling_window?.avg_accuracy === "number"
      ? analyticsData.rolling_window.avg_accuracy
      : null);

  const gamesAnalyzedLabel =
    activeGames || activeGames === 0 ? `${activeGames}/${targetGames}` : "—";

  const trendLabel = getTrendLabel(snapshot?.rating?.trend);

  const activityStatus = useMemo(() => {
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
      return `Analyzing ${total || "new"} game${total !== 1 ? "s" : ""}...`;
    }
    if (activeGames > targetGames) {
      const excess = activeGames - targetGames;
      return `Dropping oldest ${excess} game${excess > 1 ? "s" : ""}...`;
    }
    if (activeGames < targetGames) {
      const needed = targetGames - activeGames;
      return `${needed} more game${needed > 1 ? "s" : ""} needed`;
    }
    if (activeGames === targetGames && activeGames > 0) {
      return "60-game window complete";
    }
    return "No games analyzed yet";
  }, [activeGames, profileStatus, targetGames]);

  const validateAccount = async (
    username: string,
    platform: "chess.com" | "lichess"
  ): Promise<boolean> => {
    if (!username.trim()) {
      setValidationError("Username cannot be empty");
      return false;
    }

    setIsValidating(true);
    setValidationError(null);

    try {
      const response = await fetch(
        `${backendBase?.replace(
          /\/$/,
          ""
        )}/profile/validate-account?username=${encodeURIComponent(
          username
        )}&platform=${platform}`
      );
      const result = await response.json();

      if (result.valid) {
        setIsValidating(false);
        return true;
      }
      setValidationError(result.message || "Account not found");
      setIsValidating(false);
      return false;
    } catch (e) {
      setValidationError("Error validating account. Please try again.");
      setIsValidating(false);
      return false;
    }
  };

  const handleAddAccount = async () => {
    if (!newAccountUsername.trim()) {
      setValidationError("Please enter a username");
      return;
    }

    const isValid = await validateAccount(
      newAccountUsername,
      newAccountPlatform
    );
    if (!isValid) {
      return;
    }

    const exists = linkedAccounts.some(
      (acc) =>
        acc.platform === newAccountPlatform &&
        acc.username.toLowerCase() === newAccountUsername.toLowerCase()
    );

    if (exists) {
      setValidationError("This account is already linked");
      return;
    }

    setLinkedAccounts([
      ...linkedAccounts,
      { platform: newAccountPlatform, username: newAccountUsername.trim() },
    ]);
    setNewAccountUsername("");
    setValidationError(null);
  };

  const handleRemoveAccount = (index: number) => {
    setLinkedAccounts(linkedAccounts.filter((_, i) => i !== index));
  };

  const handleSaveAccounts = async () => {
    if (!userId || !backendBase) return;

    setIsSaving(true);
    try {
      const response = await fetch(
        `${backendBase.replace(/\/$/, "")}/profile/preferences`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            user_id: userId,
            accounts: linkedAccounts.map((acc) => ({
              platform: acc.platform === "chess.com" ? "chess.com" : "lichess",
              username: acc.username,
            })),
            time_controls: [],
          }),
        }
      );

      if (response.ok) {
        setIsEditing(false);
        await refreshProfileOverview();
      } else {
        const errorText = await response.text();
        setValidationError(`Failed to save: ${errorText}`);
      }
    } catch (e) {
      setValidationError("Error saving accounts. Please try again.");
    } finally {
      setIsSaving(false);
    }
  };

  const handleScrollToAccounts = () => {
    setIsEditing(true);
    const prefersReduced = window.matchMedia?.(
      "(prefers-reduced-motion: reduce)"
    )?.matches;
    accountsRef.current?.scrollIntoView({
      behavior: prefersReduced ? "auto" : "smooth",
      block: "start",
    });
  };

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await Promise.allSettled([
      refreshProfileOverview(),
      refreshAnalytics(),
      loadSnapshot(),
    ]);
    setIsRefreshing(false);
  };

  const snapshotEmpty =
    !snapshotLoading &&
    !snapshotError &&
    (!snapshot || !snapshot?.games_analyzed);
  const openingsEmpty =
    !snapshot?.openings?.as_white?.name ||
    !snapshot?.openings?.as_black_faced?.name;

  const content = (
    <div className={`analytics-v2 ${embedded ? "analytics-v2-embedded" : ""}`}>
      {!embedded && (
        <div className="v2-appbar">
          <div className="v2-container v2-appbar-inner">
            <div>
              <div className="v2-title">Personal Review</div>
              <div className="v2-subtitle">
                Last 60 games · Rolling snapshot
              </div>
            </div>
            <div className="v2-appbar-actions">
              <Link className="v2-link" href="/dev/analytics-overview-v1">
                View V1
              </Link>
              <button
                type="button"
                className="v2-button v2-button-ghost"
                onClick={handleRefresh}
                disabled={isRefreshing}
              >
                {isRefreshing ? "Refreshing..." : "Refresh"}
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="v2-container v2-stack">
        {embedded && (
          <div className="v2-embedded-header">
            <div>
              <div className="v2-title">Personal Review</div>
              <div className="v2-subtitle">
                Last 60 games · Rolling snapshot
              </div>
            </div>
            <button
              type="button"
              className="v2-button v2-button-ghost"
              onClick={handleRefresh}
              disabled={isRefreshing}
            >
              {isRefreshing ? "Refreshing..." : "Refresh"}
            </button>
          </div>
        )}

        {error && <div className="v2-inline-error">{error}</div>}
        {snapshotError && (
          <div className="v2-inline-error">
            Failed to load snapshot: {snapshotError}
          </div>
        )}

        <section className="v2-card v2-progress-card">
          <div className="v2-progress-head">
            <span>Profile Analysis Progress</span>
            <span>{gamesAnalyzedLabel} games analyzed</span>
          </div>
          <div className="v2-progress-bar">
            <div
              className="v2-progress-fill"
              style={{
                width: `${Math.min(
                  100,
                  (activeGames / Math.max(targetGames, 1)) * 100
                )}%`,
              }}
            />
          </div>
          <div className="v2-progress-sub">{activityStatus}</div>
        </section>

        <section className="v2-card">
          <div className="v2-section-header">
            <div>
              <div className="v2-section-title">At a glance</div>
              <div className="v2-section-subtitle">
                How your last 60 games are trending.
              </div>
            </div>
          </div>

          {snapshotLoading && !snapshot ? (
            <div className="v2-metrics-grid">
              {[...Array(4)].map((_, idx) => (
                <div className="v2-metric-tile" key={`skeleton-${idx}`}>
                  <div className="v2-skeleton v2-skeleton-line short" />
                  <div className="v2-skeleton v2-skeleton-line" />
                </div>
              ))}
            </div>
          ) : (
            <div className="v2-metrics-grid">
              <div className="v2-metric-tile">
                <div className="v2-metric-value">{formatPercent(winRate)}</div>
                <div className="v2-metric-label">Win rate</div>
              </div>
              <div className="v2-metric-tile">
                <div className="v2-metric-value">
                  {formatPercent(avgAccuracy)}
                </div>
                <div className="v2-metric-label">Avg accuracy</div>
              </div>
              <div className="v2-metric-tile">
                <div className="v2-metric-value">{gamesAnalyzedLabel}</div>
                <div className="v2-metric-label">Games analyzed</div>
              </div>
              <div className="v2-metric-tile">
                <div className="v2-metric-value">{trendLabel}</div>
                <div className="v2-metric-label">Trend</div>
              </div>
            </div>
          )}
          {snapshotEmpty && (
            <div className="v2-helper-text">
              Complete more games to unlock insights.
            </div>
          )}
        </section>

        <section className="v2-card">
          <div className="v2-section-header">
            <div>
              <div className="v2-section-title">Player snapshot</div>
              <div className="v2-section-subtitle">
                A quick read on your current profile.
              </div>
            </div>
            <button
              type="button"
              className="v2-button v2-button-text"
              disabled
            >
              Learn more
            </button>
          </div>

          <div className="v2-list">
            <div className="v2-list-item">
              <span className="v2-list-label">Time style</span>
              <span className="v2-list-value">
                {formatValue(snapshot?.time_style?.label)}
              </span>
            </div>
            <div className="v2-list-item">
              <span className="v2-list-label">Top strength</span>
              <span className="v2-list-value">
                {formatValue(snapshot?.identity?.top_strength)}
              </span>
            </div>
            <div className="v2-list-item">
              <span className="v2-list-label">Focus area</span>
              <span className="v2-list-value">
                {formatValue(snapshot?.identity?.focus_area)}
              </span>
            </div>
          </div>
          {!hasEnoughGames && (
            <div className="v2-helper-text">
              Complete more games to unlock insights.
            </div>
          )}
        </section>

        <section className="v2-card">
          <div className="v2-section-header">
            <div>
              <div className="v2-section-title">Openings</div>
              <div className="v2-section-subtitle">
                Most common starts in your last 60 games.
              </div>
            </div>
          </div>
          <div className="v2-list">
            <div className="v2-list-item">
              <span className="v2-list-label">As White</span>
              <span className="v2-list-value">
                {snapshot?.openings?.as_white?.name
                  ? `${snapshot.openings.as_white.name} (${
                      snapshot.openings.as_white.pct ?? 0
                    }%)`
                  : "—"}
              </span>
            </div>
            <div className="v2-list-item">
              <span className="v2-list-label">As Black</span>
              <span className="v2-list-value">
                {snapshot?.openings?.as_black_faced?.name
                  ? `${snapshot.openings.as_black_faced.name} (${
                      snapshot.openings.as_black_faced.pct ?? 0
                    }%)`
                  : "—"}
              </span>
            </div>
          </div>
          {openingsEmpty && (
            <div className="v2-helper-text">
              Not enough games yet. Keep playing to surface your top openings.
            </div>
          )}
        </section>

        <section className="v2-card" ref={accountsRef}>
          <div className="v2-section-header">
            <div>
              <div className="v2-section-title">Linked accounts</div>
              <div className="v2-section-subtitle">
                Keep your chess.com and lichess data in sync.
              </div>
            </div>
            {!isEditing ? (
              <button
                type="button"
                className="v2-button v2-button-text"
                onClick={() => setIsEditing(true)}
              >
                Edit
              </button>
            ) : (
              <div className="v2-button-row">
                <button
                  type="button"
                  className="v2-button v2-button-ghost"
                  onClick={() => {
                    setIsEditing(false);
                    setNewAccountUsername("");
                    setValidationError(null);
                    refreshProfileOverview();
                  }}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  className="v2-button v2-button-primary"
                  onClick={handleSaveAccounts}
                  disabled={isSaving}
                >
                  {isSaving ? "Saving..." : "Save"}
                </button>
              </div>
            )}
          </div>

          {linkedAccounts.length > 0 ? (
            <div className="v2-account-list">
              {linkedAccounts.map((acc, index) => (
                <div key={`${acc.platform}-${acc.username}-${index}`} className="v2-account-row">
                  <div>
                    <div className="v2-account-platform">
                      {acc.platform === "chess.com" ? "Chess.com" : "Lichess"}
                    </div>
                    <div className="v2-account-username">{acc.username}</div>
                  </div>
                  {isEditing && (
                    <button
                      type="button"
                      className="v2-button v2-button-ghost"
                      onClick={() => handleRemoveAccount(index)}
                    >
                      Remove
                    </button>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="v2-empty-state">
              No accounts linked yet. Add your chess.com or lichess handle to
              start syncing games.
            </div>
          )}

          {isEditing && (
            <div className="v2-account-editor">
              <div className="v2-field-row">
                <select
                  value={newAccountPlatform}
                  onChange={(e) =>
                    setNewAccountPlatform(e.target.value as "chess.com" | "lichess")
                  }
                  className="v2-select"
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
                  className="v2-input"
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      handleAddAccount();
                    }
                  }}
                />
                <button
                  type="button"
                  className="v2-button v2-button-primary"
                  onClick={handleAddAccount}
                  disabled={isValidating || !newAccountUsername.trim()}
                >
                  {isValidating ? "Validating..." : "Add"}
                </button>
              </div>
              {validationError && (
                <div className="v2-inline-error">{validationError}</div>
              )}
              <div className="v2-helper-text">
                Only chess.com and lichess accounts are supported. Accounts are
                validated before being added.
              </div>
            </div>
          )}
        </section>

        <section className="v2-actions">
          <div className="v2-card v2-actions-card">
            <div className="v2-section-title">Actions</div>
            <div className="v2-action-buttons">
              {!hasLinkedAccounts ? (
                <button
                  type="button"
                  className="v2-button v2-button-primary"
                  onClick={handleScrollToAccounts}
                >
                  Link accounts
                </button>
              ) : (
                <button
                  type="button"
                  className="v2-button v2-button-primary"
                  onClick={handleRefresh}
                  disabled={isRefreshing}
                >
                  {isRefreshing ? "Refreshing..." : "Refresh games"}
                </button>
              )}
              <button
                type="button"
                className="v2-button v2-button-secondary"
                onClick={onOpenPersonalReview}
              >
                Open Personal Review
              </button>
            </div>
            {!hasLinkedAccounts && (
              <div className="v2-helper-text">
                Link accounts to enable automatic game syncing and rolling
                analytics.
              </div>
            )}
          </div>
        </section>

        {loading && (
          <div className="v2-loading-state">Loading analytics…</div>
        )}
      </div>
    </div>
  );

  if (embedded) {
    return content;
  }

  return <SafeAreaView className="analytics-v2">{content}</SafeAreaView>;
}

