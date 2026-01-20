"use client";

import { useMemo, useState } from "react";
import { GraphSeriesEntry, formatTagName } from "./graphSeries";

type DetailedAnalytics = {
  tag_transitions?: {
    gained?: Record<string, { significance_score?: number }>;
    lost?: Record<string, { significance_score?: number }>;
  };
};

const PIECES = ["Pawn", "Knight", "Bishop", "Rook", "Queen", "King"] as const;

const COLOR_POOL = [
  "#60a5fa",
  "#34d399",
  "#fbbf24",
  "#f87171",
  "#a78bfa",
  "#22d3ee",
  "#fb7185",
  "#4ade80",
  "#e879f9",
  "#f59e0b",
];

function entryId(kind: GraphSeriesEntry["kind"], params?: GraphSeriesEntry["params"]): string {
  const p = params || {};
  const parts = [
    `kind=${kind}`,
    p.openingName ? `opening=${p.openingName}` : "",
    p.piece ? `piece=${p.piece}` : "",
    p.bucket ? `bucket=${p.bucket}` : "",
    p.tag ? `tag=${p.tag}` : "",
    p.dir ? `dir=${p.dir}` : "",
  ].filter(Boolean);
  return parts.join("|");
}

function pickColor(index: number): string {
  return COLOR_POOL[index % COLOR_POOL.length];
}

export default function AddGraphEntryModal({
  isOpen,
  onClose,
  onAdd,
  existingIds,
  openings,
  detailed,
}: {
  isOpen: boolean;
  onClose: () => void;
  onAdd: (entry: GraphSeriesEntry) => void;
  existingIds: Set<string>;
  openings: string[];
  detailed: DetailedAnalytics | null;
}) {
  const [query, setQuery] = useState("");

  const suggested = useMemo(() => {
    const gained = detailed?.tag_transitions?.gained || {};
    const lost = detailed?.tag_transitions?.lost || {};
    const items: Array<{ dir: "gained" | "lost"; tag: string; score: number }> = [];
    for (const [tag, data] of Object.entries(gained)) {
      const s = typeof data?.significance_score === "number" ? data.significance_score : 0;
      if (s > 0) items.push({ dir: "gained", tag, score: s });
    }
    for (const [tag, data] of Object.entries(lost)) {
      const s = typeof data?.significance_score === "number" ? data.significance_score : 0;
      if (s > 0) items.push({ dir: "lost", tag, score: s });
    }
    return items.sort((a, b) => b.score - a.score).slice(0, 5);
  }, [detailed]);

  const gainedTags = useMemo(() => {
    const gained = detailed?.tag_transitions?.gained || {};
    return Object.entries(gained)
      .map(([tag, data]) => ({ tag, score: typeof data?.significance_score === "number" ? data.significance_score : 0 }))
      .sort((a, b) => b.score - a.score)
      .map((x) => x.tag);
  }, [detailed]);

  const lostTags = useMemo(() => {
    const lost = detailed?.tag_transitions?.lost || {};
    return Object.entries(lost)
      .map(([tag, data]) => ({ tag, score: typeof data?.significance_score === "number" ? data.significance_score : 0 }))
      .sort((a, b) => b.score - a.score)
      .map((x) => x.tag);
  }, [detailed]);

  const filter = (label: string) => {
    const q = query.trim().toLowerCase();
    if (!q) return true;
    return label.toLowerCase().includes(q);
  };

  const handleAdd = (entry: GraphSeriesEntry) => {
    if (existingIds.has(entry.id)) return;
    onAdd(entry);
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 50,
        background: "rgba(0,0,0,0.6)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 18,
      }}
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        style={{
          width: "min(980px, 100%)",
          maxHeight: "80vh",
          overflow: "auto",
          background: "rgba(15, 23, 42, 0.98)",
          border: "1px solid rgba(148, 163, 184, 0.2)",
          borderRadius: 14,
          boxShadow: "0 30px 80px rgba(0,0,0,0.55)",
        }}
      >
        <div
          style={{
            padding: "14px 16px",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            borderBottom: "1px solid rgba(148, 163, 184, 0.15)",
          }}
        >
          <div>
            <div style={{ color: "#e2e8f0", fontWeight: 800 }}>Add graph entry</div>
            <div style={{ color: "#94a3b8", fontSize: 12 }}>Suggested entries are driven by existing detailed-analytics significance scores.</div>
          </div>
          <button
            onClick={onClose}
            style={{
              width: 36,
              height: 34,
              borderRadius: 10,
              border: "1px solid rgba(148, 163, 184, 0.25)",
              background: "rgba(30, 58, 95, 0.35)",
              color: "#e2e8f0",
              cursor: "pointer",
              fontSize: 18,
            }}
            title="Close"
          >
            ×
          </button>
        </div>

        <div style={{ padding: "14px 16px", display: "grid", gap: 12 }}>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search openings, tags, pieces…"
            style={{
              width: "100%",
              padding: "10px 12px",
              borderRadius: 10,
              border: "1px solid rgba(148, 163, 184, 0.25)",
              background: "rgba(30, 58, 95, 0.20)",
              color: "#e2e8f0",
              outline: "none",
            }}
          />

          <div style={{ display: "grid", gap: 10 }}>
            <div style={{ color: "#e0e7ff", fontWeight: 800, fontSize: 12, letterSpacing: 0.4, textTransform: "uppercase" }}>
              Suggested
            </div>
            <div style={{ display: "grid", gap: 8 }}>
              {suggested.length === 0 ? (
                <div style={{ color: "#94a3b8", fontSize: 13 }}>No suggestions yet (need detailed analytics tag transitions).</div>
              ) : (
                suggested
                  .filter((x) => filter(formatTagName(x.tag)))
                  .map((sugg, i) => {
                    const label = `${sugg.dir === "gained" ? "Tag gained" : "Tag lost"}: ${formatTagName(sugg.tag)}`;
                    const entry: GraphSeriesEntry = {
                      id: entryId("tag_transition_count", { tag: sugg.tag, dir: sugg.dir }),
                      kind: "tag_transition_count",
                      label,
                      color: pickColor(i),
                      params: { tag: sugg.tag, dir: sugg.dir },
                    };
                    const disabled = existingIds.has(entry.id);
                    return (
                      <button
                        key={`${sugg.dir}:${sugg.tag}`}
                        disabled={disabled}
                        onClick={() => handleAdd(entry)}
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          gap: 12,
                          alignItems: "center",
                          padding: "10px 12px",
                          borderRadius: 12,
                          border: "1px solid rgba(148, 163, 184, 0.18)",
                          background: disabled ? "rgba(148, 163, 184, 0.06)" : "rgba(30, 58, 95, 0.25)",
                          cursor: disabled ? "not-allowed" : "pointer",
                          color: "#e2e8f0",
                          textAlign: "left",
                        }}
                      >
                        <div style={{ display: "flex", gap: 10, alignItems: "center", minWidth: 0 }}>
                          <span style={{ width: 10, height: 10, borderRadius: 999, background: entry.color, flex: "0 0 auto" }} />
                          <span style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{label}</span>
                        </div>
                        <div style={{ color: "#93c5fd", fontWeight: 700, fontVariantNumeric: "tabular-nums" }}>{sugg.score.toFixed(0)}</div>
                      </button>
                    );
                  })
              )}
            </div>
          </div>

          <div style={{ display: "grid", gap: 10, marginTop: 6 }}>
            <div style={{ color: "#e0e7ff", fontWeight: 800, fontSize: 12, letterSpacing: 0.4, textTransform: "uppercase" }}>
              Categories
            </div>

            <details open style={{ border: "1px solid rgba(148, 163, 184, 0.15)", borderRadius: 12, padding: 10 }}>
              <summary style={{ cursor: "pointer", color: "#e2e8f0", fontWeight: 700 }}>Openings</summary>
              <div style={{ display: "grid", gap: 8, marginTop: 10 }}>
                {openings.filter(filter).slice(0, 40).map((o, i) => {
                  const entry: GraphSeriesEntry = {
                    id: entryId("opening_frequency_pct", { openingName: o }),
                    kind: "opening_frequency_pct",
                    label: `Opening frequency: ${o}`,
                    color: pickColor(i),
                    params: { openingName: o },
                  };
                  const disabled = existingIds.has(entry.id);
                  return (
                    <button
                      key={o}
                      disabled={disabled}
                      onClick={() => handleAdd(entry)}
                      style={{
                        padding: "8px 10px",
                        borderRadius: 10,
                        border: "1px solid rgba(148, 163, 184, 0.18)",
                        background: disabled ? "rgba(148, 163, 184, 0.06)" : "rgba(30, 58, 95, 0.18)",
                        color: "#e2e8f0",
                        cursor: disabled ? "not-allowed" : "pointer",
                        textAlign: "left",
                      }}
                    >
                      {o}
                    </button>
                  );
                })}
              </div>
            </details>

            <details style={{ border: "1px solid rgba(148, 163, 184, 0.15)", borderRadius: 12, padding: 10 }}>
              <summary style={{ cursor: "pointer", color: "#e2e8f0", fontWeight: 700 }}>Piece accuracy</summary>
              <div style={{ display: "grid", gap: 8, marginTop: 10 }}>
                {PIECES.filter((p) => filter(p)).map((p, i) => {
                  const entry: GraphSeriesEntry = {
                    id: entryId("piece_accuracy", { piece: p }),
                    kind: "piece_accuracy",
                    label: `Piece accuracy: ${p}`,
                    color: pickColor(i),
                    params: { piece: p },
                  };
                  const disabled = existingIds.has(entry.id);
                  return (
                    <button
                      key={p}
                      disabled={disabled}
                      onClick={() => handleAdd(entry)}
                      style={{
                        padding: "8px 10px",
                        borderRadius: 10,
                        border: "1px solid rgba(148, 163, 184, 0.18)",
                        background: disabled ? "rgba(148, 163, 184, 0.06)" : "rgba(30, 58, 95, 0.18)",
                        color: "#e2e8f0",
                        cursor: disabled ? "not-allowed" : "pointer",
                        textAlign: "left",
                      }}
                    >
                      {p}
                    </button>
                  );
                })}
              </div>
            </details>

            <details style={{ border: "1px solid rgba(148, 163, 184, 0.15)", borderRadius: 12, padding: 10 }}>
              <summary style={{ cursor: "pointer", color: "#e2e8f0", fontWeight: 700 }}>Tags gained</summary>
              <div style={{ display: "grid", gap: 8, marginTop: 10 }}>
                {gainedTags
                  .map((t) => ({ t, label: formatTagName(t) }))
                  .filter((x) => filter(x.label))
                  .slice(0, 80)
                  .map((x, i) => {
                    const entry: GraphSeriesEntry = {
                      id: entryId("tag_transition_count", { tag: x.t, dir: "gained" }),
                      kind: "tag_transition_count",
                      label: `Tag gained: ${x.label}`,
                      color: pickColor(i),
                      params: { tag: x.t, dir: "gained" },
                    };
                    const disabled = existingIds.has(entry.id);
                    return (
                      <button
                        key={`gained:${x.t}`}
                        disabled={disabled}
                        onClick={() => handleAdd(entry)}
                        style={{
                          padding: "8px 10px",
                          borderRadius: 10,
                          border: "1px solid rgba(148, 163, 184, 0.18)",
                          background: disabled ? "rgba(148, 163, 184, 0.06)" : "rgba(30, 58, 95, 0.18)",
                          color: "#e2e8f0",
                          cursor: disabled ? "not-allowed" : "pointer",
                          textAlign: "left",
                        }}
                      >
                        {x.label}
                      </button>
                    );
                  })}
              </div>
            </details>

            <details style={{ border: "1px solid rgba(148, 163, 184, 0.15)", borderRadius: 12, padding: 10 }}>
              <summary style={{ cursor: "pointer", color: "#e2e8f0", fontWeight: 700 }}>Tags lost</summary>
              <div style={{ display: "grid", gap: 8, marginTop: 10 }}>
                {lostTags
                  .map((t) => ({ t, label: formatTagName(t) }))
                  .filter((x) => filter(x.label))
                  .slice(0, 80)
                  .map((x, i) => {
                    const entry: GraphSeriesEntry = {
                      id: entryId("tag_transition_count", { tag: x.t, dir: "lost" }),
                      kind: "tag_transition_count",
                      label: `Tag lost: ${x.label}`,
                      color: pickColor(i),
                      params: { tag: x.t, dir: "lost" },
                    };
                    const disabled = existingIds.has(entry.id);
                    return (
                      <button
                        key={`lost:${x.t}`}
                        disabled={disabled}
                        onClick={() => handleAdd(entry)}
                        style={{
                          padding: "8px 10px",
                          borderRadius: 10,
                          border: "1px solid rgba(148, 163, 184, 0.18)",
                          background: disabled ? "rgba(148, 163, 184, 0.06)" : "rgba(30, 58, 95, 0.18)",
                          color: "#e2e8f0",
                          cursor: disabled ? "not-allowed" : "pointer",
                          textAlign: "left",
                        }}
                      >
                        {x.label}
                      </button>
                    );
                  })}
              </div>
            </details>
          </div>
        </div>
      </div>
    </div>
  );
}


