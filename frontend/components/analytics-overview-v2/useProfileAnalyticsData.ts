"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getBackendBase } from "@/lib/backendBase";

export interface ProfileAnalyticsState {
  backendBase: string;
  loading: boolean;
  error: string | null;
  analyticsData: any;
  profileStatus: any;
  profileOverview: any;
  refreshAnalytics: () => Promise<void>;
  refreshProfileOverview: () => Promise<void>;
}

export function useProfileAnalyticsData(userId?: string): ProfileAnalyticsState {
  const backendBase = getBackendBase();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [analyticsData, setAnalyticsData] = useState<any>(null);
  const [profileStatus, setProfileStatus] = useState<any>(null);
  const [profileOverview, setProfileOverview] = useState<any>(null);

  const analyticsAbortRef = useRef<AbortController | null>(null);
  const analyticsPollRef = useRef<NodeJS.Timeout | null>(null);
  const analyticsRefreshRef = useRef<NodeJS.Timeout | null>(null);
  const statusPollRef = useRef<NodeJS.Timeout | null>(null);
  const statusIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const loadTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const isMountedRef = useRef(true);

  const refreshProfileOverview = useCallback(async () => {
    if (!userId) return;
    try {
      const overviewUrl = `${backendBase.replace(/\/$/, "")}/profile/overview?user_id=${userId}`;
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 8000);
      const response = await fetch(overviewUrl, {
        cache: "no-store",
        signal: controller.signal,
      });
      clearTimeout(timeoutId);
      if (response.ok) {
        const data = await response.json();
        setProfileOverview(data);
        setProfileStatus(data.status || null);
      }
    } catch (e) {
      console.warn("[AnalyticsOverviewV2] Failed to load profile overview:", e);
    }
  }, [backendBase, userId]);

  const refreshAnalytics = useCallback(async () => {
    if (!userId) return;

    if (analyticsAbortRef.current) {
      analyticsAbortRef.current.abort();
    }

    if (!isMountedRef.current) return;

    setLoading(true);
    let pollInterval: NodeJS.Timeout | null = null;
    try {
      const url = `${backendBase.replace(/\/$/, "")}/profile/analytics/${userId}`;

      const controller = new AbortController();
      analyticsAbortRef.current = controller;

      const fetchWithRetry = async (attempts: number) => {
        let lastErr: any = null;
        for (let i = 0; i < attempts; i++) {
          if (controller.signal.aborted || !isMountedRef.current) {
            throw new Error("Request aborted");
          }
          try {
            const timeoutId = setTimeout(() => {
              if (!controller.signal.aborted) {
                controller.abort();
              }
            }, 30000);
            const res = await fetch(url, {
              signal: controller.signal,
              cache: "no-store",
            });
            clearTimeout(timeoutId);
            return res;
          } catch (e) {
            lastErr = e;
            if (controller.signal.aborted || !isMountedRef.current) {
              throw e;
            }
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

      if (data?.status === "computing") {
        setAnalyticsData(data);
        setError(null);
        setLoading(false);
        let pollCount = 0;
        const maxPolls = 24;
        pollInterval = setInterval(async () => {
          pollCount++;
          if (pollCount > maxPolls) {
            if (pollInterval) clearInterval(pollInterval);
            setError(
              "Analytics computation is taking longer than expected. Please refresh."
            );
            return;
          }
          try {
            if (!isMountedRef.current) {
              if (pollInterval) clearInterval(pollInterval);
              return;
            }
            const pollController = new AbortController();
            const timeoutId = setTimeout(() => pollController.abort(), 15000);
            const pollResponse = await fetch(url, {
              cache: "no-store",
              signal: pollController.signal,
            });
            clearTimeout(timeoutId);
            if (!isMountedRef.current) return;
            if (pollResponse.ok) {
              const pollData = await pollResponse.json();
              if (
                pollData?.status !== "computing" &&
                pollData?.status !== "error"
              ) {
                if (pollInterval) clearInterval(pollInterval);
                setAnalyticsData(pollData);
                setError(null);
              }
            }
          } catch (e) {
            if (
              !isMountedRef.current ||
              (e instanceof Error && e.name === "AbortError")
            ) {
              if (pollInterval) clearInterval(pollInterval);
              return;
            }
            console.warn("[AnalyticsOverviewV2] Poll error:", e);
          }
        }, 5000);
        return;
      }

      if (!data || typeof data !== "object") {
        setAnalyticsData({
          lifetime_stats: {},
          patterns: {},
          strength_profile: {},
          rolling_window: {},
          deltas: {},
        });
        return;
      }

      const safeData = {
        lifetime_stats: data.lifetime_stats || {},
        patterns: data.patterns || {},
        strength_profile: data.strength_profile || {},
        rolling_window: data.rolling_window || {},
        deltas: data.deltas || {},
        ...data,
      };

      setAnalyticsData(safeData);
    } catch (err: any) {
      if (!isMountedRef.current) return;
      if (err?.name === "AbortError" && analyticsAbortRef.current?.signal.aborted) {
        return;
      }
      const msg =
        err?.name === "AbortError"
          ? "Request timed out."
          : err?.message || String(err);
      setError(`Failed to load your profile analytics: ${msg}.`);
      setAnalyticsData({
        lifetime_stats: {},
        patterns: {},
        strength_profile: {},
      });
    } finally {
      if (isMountedRef.current) {
        setLoading(false);
      }
    }
  }, [backendBase, userId]);

  useEffect(() => {
    isMountedRef.current = true;
    if (!userId) {
      setProfileOverview(null);
      setProfileStatus(null);
      setAnalyticsData(null);
      setLoading(false);
      return;
    }

    refreshProfileOverview();

    const getPollInterval = () => {
      const state = profileStatus?.state;
      return state === "analyzing" || state === "fetching" ? 2000 : 6000;
    };

    statusPollRef.current = setInterval(refreshProfileOverview, getPollInterval());

    statusIntervalRef.current = setInterval(() => {
      if (statusPollRef.current) clearInterval(statusPollRef.current);
      statusPollRef.current = setInterval(
        refreshProfileOverview,
        getPollInterval()
      );
    }, 1000);

    return () => {
      isMountedRef.current = false;
      if (statusPollRef.current) clearInterval(statusPollRef.current);
      if (statusIntervalRef.current) clearInterval(statusIntervalRef.current);
    };
  }, [userId, backendBase, profileStatus?.state, refreshProfileOverview]);

  useEffect(() => {
    if (!userId) return;

    let isMounted = true;

    const debouncedLoadAnalytics = () => {
      if (loadTimeoutRef.current) clearTimeout(loadTimeoutRef.current);
      loadTimeoutRef.current = setTimeout(() => {
        if (isMounted) {
          refreshAnalytics();
        }
      }, 500);
    };

    refreshAnalytics();

    const getAnalyticsPollInterval = () => {
      const state = profileStatus?.state;
      return state === "analyzing" || state === "fetching" ? 3000 : 15000;
    };

    analyticsRefreshRef.current = setInterval(
      debouncedLoadAnalytics,
      getAnalyticsPollInterval()
    );

    const updateAnalyticsInterval = () => {
      if (!isMounted) return;
      if (analyticsRefreshRef.current) clearInterval(analyticsRefreshRef.current);
      analyticsRefreshRef.current = setInterval(
        debouncedLoadAnalytics,
        getAnalyticsPollInterval()
      );
    };

    analyticsPollRef.current = setInterval(updateAnalyticsInterval, 1000);

    return () => {
      isMounted = false;
      if (analyticsAbortRef.current) analyticsAbortRef.current.abort();
      if (loadTimeoutRef.current) clearTimeout(loadTimeoutRef.current);
      if (analyticsPollRef.current) clearInterval(analyticsPollRef.current);
      if (analyticsRefreshRef.current)
        clearInterval(analyticsRefreshRef.current);
    };
  }, [userId, backendBase, profileStatus?.state, refreshAnalytics]);

  return {
    backendBase,
    loading,
    error,
    analyticsData,
    profileStatus,
    profileOverview,
    refreshAnalytics,
    refreshProfileOverview,
  };
}

