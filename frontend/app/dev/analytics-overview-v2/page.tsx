"use client";

import { useAuth } from "@/contexts/AuthContext";
import MobileShell from "@/components/analytics-overview-v2/MobileShell";

export default function AnalyticsOverviewV2Page() {
  const { user } = useAuth();

  if (!user) {
    return (
      <div style={{ padding: 32 }}>
        <h1>Analytics Overview V2</h1>
        <p>Please sign in to view your personal review analytics.</p>
      </div>
    );
  }

  return (
    <MobileShell>
      {() => null}
    </MobileShell>
  );
}

