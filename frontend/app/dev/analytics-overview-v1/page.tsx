"use client";

import { useState } from "react";
import Link from "next/link";
import { useAuth } from "@/contexts/AuthContext";
import OverviewTab from "@/components/ProfileDashboard/tabs/OverviewTab";
import PersonalReview from "@/components/PersonalReview";
import { useProfileAnalyticsData } from "@/components/analytics-overview-v2/useProfileAnalyticsData";

export default function AnalyticsOverviewV1Page() {
  const { user } = useAuth();
  const [showPersonalReview, setShowPersonalReview] = useState(false);
  const { backendBase, loading, error, analyticsData, profileStatus } =
    useProfileAnalyticsData(user?.id);

  if (!user) {
    return (
      <div style={{ padding: 32 }}>
        <h1>Analytics Overview V1</h1>
        <p>Please sign in to view your personal review analytics.</p>
        <Link href="/dev/analytics-overview-v2">Go to V2</Link>
      </div>
    );
  }

  return (
    <div style={{ padding: 24 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <h1 style={{ margin: 0 }}>Analytics Overview V1</h1>
        <Link href="/dev/analytics-overview-v2">Compare V2</Link>
      </div>
      {error && (
        <div style={{ marginTop: 12, color: "#f87171" }}>{error}</div>
      )}
      {loading && (
        <div style={{ marginTop: 12, color: "#94a3b8" }}>
          Loading analytics…
        </div>
      )}
      <OverviewTab
        data={analyticsData}
        profileStatus={profileStatus}
        onOpenPersonalReview={() => setShowPersonalReview(true)}
        userId={user?.id || ""}
        backendBase={backendBase}
      />
      {showPersonalReview && (
        <PersonalReview onClose={() => setShowPersonalReview(false)} />
      )}
    </div>
  );
}

