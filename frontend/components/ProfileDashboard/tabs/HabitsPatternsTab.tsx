"use client";

import DetailedAnalyticsSection from "../components/DetailedAnalyticsSection";

interface HabitsPatternsTabProps {
  userId: string;
  backendBase: string;
  data?: any;
}

export default function HabitsPatternsTab({ userId, backendBase }: HabitsPatternsTabProps) {
  return (
    <div className="habits-patterns-tab">
      <DetailedAnalyticsSection userId={userId} backendBase={backendBase} title="Habits & Patterns" />
    </div>
  );
}

