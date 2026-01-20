"use client";

import { useMemo } from "react";
import InteractiveLineChart from "@/components/ProfileDashboard/components/graphs/InteractiveLineChart";
import type { ChatGraphData } from "@/types";

interface ChatGraphProps {
  graphData: ChatGraphData;
}

export default function ChatGraph({ graphData }: ChatGraphProps) {
  // Convert to format expected by InteractiveLineChart
  const chartSeries = useMemo(() => {
    return graphData.series.map(s => ({
      id: s.id,
      name: s.name,
      color: s.color,
      normalizedValues: s.normalizedValues,
      rawValues: s.rawValues,
    }));
  }, [graphData.series]);

  return (
    <div className="chat-graph-container" style={{ 
      marginBottom: "16px",
      padding: "12px",
      background: "rgba(30, 41, 59, 0.5)",
      borderRadius: "8px",
      border: "1px solid rgba(148, 163, 184, 0.2)"
    }}>
      <InteractiveLineChart 
        xLabels={graphData.xLabels}
        series={chartSeries}
        height={200}
      />
    </div>
  );
}

