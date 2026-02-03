"use client";

import ExpandableAnalyticsCard from "./ExpandableAnalyticsCard";

interface StaticTagsCardProps {
  staticTags: {
    [tag: string]: {
      accuracy: number;
      count: number;
      blunders: number;
      mistakes: number;
      inaccuracies: number;
      trend?: string;
      trend_value?: number;
      significance_score?: number;
      day_intervals?: {
        dates: string[];
        accuracies: number[];
        counts: number[];
        errors: number[];
      };
    };
  };
}

export default function StaticTagsCard({ staticTags }: StaticTagsCardProps) {
  const entries = Object.entries(staticTags || {}).map(([tag, data]) => ({ tag, ...data }));

  const highest = [...entries]
    .sort((a, b) => {
      const sigA = a.significance_score || 0;
      const sigB = b.significance_score || 0;
      if (sigA !== sigB) return sigB - sigA;
      return b.accuracy - a.accuracy;
    })
    .slice(0, 5);

  const lowest = [...entries]
    .sort((a, b) => {
      const sigA = a.significance_score || 0;
      const sigB = b.significance_score || 0;
      if (sigA !== sigB) return sigB - sigA;
      return a.accuracy - b.accuracy;
    })
    .slice(0, 5);

  const allSignificanceScores = entries
    .map((e) => e.significance_score || 0)
    .filter((s) => s > 0);

  const overallSignificance =
    allSignificanceScores.length > 0
      ? allSignificanceScores.reduce((a, b) => a + b, 0) / allSignificanceScores.length
      : undefined;

  const formatTagName = (tag: string) => {
    return tag
      .replace(/^tag\./, "")
      .replace(/\./g, " ")
      .replace(/\b\w/g, (l) => l.toUpperCase());
  };

  const buildTrendData = () => {
    const allDates = new Set<string>();
    const seriesMap = new Map<string, { name: string; data: Map<string, number>; color: string }>();

    for (const { tag, day_intervals } of entries) {
      if (day_intervals && day_intervals.dates.length > 0) {
        day_intervals.dates.forEach((d) => allDates.add(d));
        seriesMap.set(tag, {
          name: formatTagName(tag),
          data: new Map(day_intervals.dates.map((date, i) => [date, day_intervals.accuracies[i]])),
          color: "#93c5fd",
        });
      }
    }

    if (allDates.size === 0) return undefined;

    const sortedDates = Array.from(allDates).sort();
    const series = Array.from(seriesMap.values()).slice(0, 5);

    return {
      dates: sortedDates,
      series: series.map((s) => ({
        name: s.name,
        data: sortedDates.map((date) => s.data.get(date) ?? null),
        color: s.color,
      })),
      baseline: undefined,
    };
  };

  const trendData = buildTrendData();

  if (highest.length === 0 && lowest.length === 0) {
    return (
      <ExpandableAnalyticsCard title="Static Tags" hideControls={true}>
        <p style={{ color: "#cbd5e1", fontSize: "14px" }}>No static tag data available yet.</p>
      </ExpandableAnalyticsCard>
    );
  }

  const renderCard = (tag: string, data: any, palette: "green" | "red") => {
    const errorRate =
      data.count > 0 ? ((data.blunders + data.mistakes + data.inaccuracies) / data.count) * 100 : 0;

    const bg =
      palette === "green" ? "rgba(16, 185, 129, 0.1)" : "rgba(239, 68, 68, 0.1)";
    const border =
      palette === "green" ? "1px solid rgba(16, 185, 129, 0.2)" : "1px solid rgba(239, 68, 68, 0.2)";
    const nameColor = palette === "green" ? "#6ee7b7" : "#fca5a5";

    return (
      <div
        key={tag}
        style={{
          padding: "12px",
          background: bg,
          borderRadius: "6px",
          border,
        }}
      >
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: "6px",
          }}
        >
          <div style={{ fontSize: "13px", fontWeight: 600, color: nameColor }}>{formatTagName(tag)}</div>
          {data.significance_score !== undefined && (
            <div
              style={{
                padding: "2px 6px",
                borderRadius: "3px",
                fontSize: "10px",
                fontWeight: 600,
                background:
                  data.significance_score >= 70
                    ? "rgba(16, 185, 129, 0.2)"
                    : data.significance_score >= 40
                      ? "rgba(251, 191, 36, 0.2)"
                      : "rgba(107, 114, 128, 0.2)",
                color:
                  data.significance_score >= 70 ? "#10b981" : data.significance_score >= 40 ? "#fbbf24" : "#9ca3af",
              }}
            >
              {data.significance_score.toFixed(0)}
            </div>
          )}
        </div>

        <div style={{ display: "flex", justifyContent: "space-between", fontSize: "12px", color: "#cbd5e1", marginBottom: "4px" }}>
          <span>Accuracy:</span>
          <span style={{ fontWeight: 600 }}>{data.accuracy.toFixed(1)}%</span>
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: "12px", color: "#cbd5e1", marginBottom: "4px" }}>
          <span>Occurrences:</span>
          <span>{data.count}</span>
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: "12px", color: "#cbd5e1" }}>
          <span>Error Rate:</span>
          <span style={{ color: errorRate > 20 ? "#ef4444" : errorRate > 10 ? "#fbbf24" : "#10b981" }}>
            {errorRate.toFixed(1)}%
          </span>
        </div>
        {data.trend && data.trend_value !== undefined && (
          <div
            style={{
              fontSize: "11px",
              color: data.trend === "improving" ? "#10b981" : data.trend === "declining" ? "#ef4444" : "#9ca3af",
              marginTop: "4px",
              display: "flex",
              alignItems: "center",
              gap: "4px",
            }}
          >
            {data.trend === "improving" ? "↑" : data.trend === "declining" ? "↓" : "→"}
            <span>
              {data.trend_value > 0 ? "+" : ""}
              {data.trend_value}% over last 10 games
            </span>
          </div>
        )}
      </div>
    );
  };

  return (
    <ExpandableAnalyticsCard
      title="Static Tags"
      significanceScore={overallSignificance}
      trendData={trendData}
      hideControls={true}
    >
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "20px" }}>
        <div>
          <h4 style={{ margin: "0 0 12px 0", fontSize: "14px", fontWeight: 600, color: "#10b981" }}>
            Static Tags - Highest Accuracy
          </h4>
          {highest.length > 0 ? (
            <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
              {highest.map(({ tag, ...data }) => renderCard(tag, data, "green"))}
            </div>
          ) : (
            <p style={{ color: "#9ca3af", fontSize: "12px" }}>No data</p>
          )}
        </div>

        <div>
          <h4 style={{ margin: "0 0 12px 0", fontSize: "14px", fontWeight: 600, color: "#ef4444" }}>
            Static Tags - Lowest Accuracy
          </h4>
          {lowest.length > 0 ? (
            <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
              {lowest.map(({ tag, ...data }) => renderCard(tag, data, "red"))}
            </div>
          ) : (
            <p style={{ color: "#9ca3af", fontSize: "12px" }}>No data</p>
          )}
        </div>
      </div>
    </ExpandableAnalyticsCard>
  );
}

