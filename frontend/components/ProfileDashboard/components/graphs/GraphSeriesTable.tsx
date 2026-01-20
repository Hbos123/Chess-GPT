"use client";

import { BuiltSeries, formatDelta } from "./graphSeries";

function formatInt(n: number): string {
  if (!Number.isFinite(n)) return "0";
  return Math.round(n).toLocaleString();
}

export default function GraphSeriesTable({
  series,
  onRemove,
  onAddClick,
}: {
  series: BuiltSeries[];
  onRemove: (id: string) => void;
  onAddClick: () => void;
}) {
  return (
    <div
      style={{
        border: "1px solid rgba(147, 197, 253, 0.18)",
        borderRadius: 10,
        overflow: "hidden",
        background: "rgba(30, 58, 95, 0.55)",
      }}
    >
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 140px 90px 150px 56px",
          padding: "10px 12px",
          borderBottom: "1px solid rgba(147, 197, 253, 0.12)",
          color: "#cbd5e1",
          fontSize: 12,
          fontWeight: 600,
          gap: 8,
        }}
      >
        <div>Name</div>
        <div>Instances</div>
        <div>n</div>
        <div>Trend Δ</div>
        <div />
      </div>

      {series.map((s) => {
        const d = s.trendDelta;
        const dir = d == null ? "flat" : d > 0 ? "up" : d < 0 ? "down" : "flat";
        const deltaColor = dir === "up" ? "#10b981" : dir === "down" ? "#f87171" : "#9ca3af";
        return (
          <div
            key={s.entry.id}
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 140px 90px 150px 56px",
              padding: "10px 12px",
              borderBottom: "1px solid rgba(147, 197, 253, 0.10)",
              alignItems: "center",
              gap: 8,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}>
              <span style={{ width: 10, height: 10, borderRadius: 999, background: s.entry.color, flex: "0 0 auto" }} />
              <span style={{ color: "#e0e7ff", fontSize: 13, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                {s.entry.label}
              </span>
            </div>
            <div style={{ color: "#e0e7ff", fontSize: 13, fontVariantNumeric: "tabular-nums" }}>
              {formatInt(s.instancesTotal)}
            </div>
            <div style={{ color: "#e0e7ff", fontSize: 13, fontVariantNumeric: "tabular-nums" }}>{s.nPoints}</div>
            <div style={{ color: deltaColor, fontSize: 13, fontVariantNumeric: "tabular-nums" }}>
              {formatDelta(d, 2)}
            </div>
            <div style={{ display: "flex", justifyContent: "flex-end" }}>
              <button
                onClick={() => onRemove(s.entry.id)}
                title="Remove"
                style={{
                  width: 34,
                  height: 30,
                  borderRadius: 8,
                  border: "1px solid rgba(148, 163, 184, 0.25)",
                  background: "rgba(15, 23, 42, 0.35)",
                  color: "#e2e8f0",
                  cursor: "pointer",
                }}
              >
                ×
              </button>
            </div>
          </div>
        );
      })}

      {/* Add row */}
      <button
        onClick={onAddClick}
        style={{
          width: "100%",
          display: "flex",
          justifyContent: "center",
          gap: 10,
          padding: "12px",
          background: "rgba(15, 23, 42, 0.20)",
          border: "none",
          cursor: "pointer",
          color: "#93c5fd",
          fontWeight: 700,
        }}
      >
        <span style={{ fontSize: 16, lineHeight: "16px" }}>+</span>
        Add entry
      </button>
    </div>
  );
}


