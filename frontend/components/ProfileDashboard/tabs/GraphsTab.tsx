"use client";

import { useEffect, useMemo, useState } from "react";

import AddGraphEntryModal from "../components/graphs/AddGraphEntryModal";
import GraphSeriesTable from "../components/graphs/GraphSeriesTable";
import InteractiveLineChart from "../components/graphs/InteractiveLineChart";
import { BuiltSeries, GraphGamePoint, GraphSeriesEntry, GroupingMode, TimePoint, buildSeries } from "../components/graphs/graphSeries";

type DetailedAnalytics = {
  tag_transitions?: {
    gained?: Record<string, { significance_score?: number }>;
    lost?: Record<string, { significance_score?: number }>;
  };
  static_tags?: Record<string, { significance_score?: number }>;
};

const COLOR_POOL = ["#60a5fa", "#34d399", "#fbbf24", "#f87171", "#a78bfa", "#22d3ee", "#fb7185", "#4ade80"];

function colorForIndex(i: number): string {
  return COLOR_POOL[i % COLOR_POOL.length];
}

function groupByDay(games: GraphGamePoint[]): TimePoint[] {
  const byDay = new Map<string, GraphGamePoint[]>();
  for (const g of games) {
    const d = g.game_date || "unknown";
    const arr = byDay.get(d) || [];
    arr.push(g);
    byDay.set(d, arr);
  }
  const days = Array.from(byDay.keys()).sort();
  return days.map((d) => ({
    key: `day:${d}`,
    label: d,
    games: (byDay.get(d) || []).sort((a, b) => (a.index ?? 0) - (b.index ?? 0)),
  }));
}

function groupByGame(games: GraphGamePoint[]): TimePoint[] {
  return games.map((game, i) => ({
    key: `game:${i}`,
    label: `Game ${i + 1}`,
    games: [game],
  }));
}

function groupByBatch5(games: GraphGamePoint[]): TimePoint[] {
  const out: TimePoint[] = [];
  for (let i = 0; i < games.length; i += 5) {
    const chunk = games.slice(i, i + 5);
    const label = `Games ${i + 1}-${i + chunk.length}`;
    out.push({
      key: `batch5:${i}`,
      label,
      games: chunk,
    });
  }
  return out;
}

interface GraphsTabProps {
  userId: string;
  backendBase: string;
}

export default function GraphsTab({ userId, backendBase }: GraphsTabProps) {
  const [loading, setLoading] = useState(true);
  const [games, setGames] = useState<GraphGamePoint[]>([]); // Start with empty array
  const [grouping, setGrouping] = useState<GroupingMode>("day");
  const [detailed, setDetailed] = useState<DetailedAnalytics | null>(null); // Start with null
  const [showAddModal, setShowAddModal] = useState(false);
  const [entries, setEntries] = useState<GraphSeriesEntry[]>(() => [
    { id: "kind=win_rate_pct", kind: "win_rate_pct", label: "Win rate (%)", color: colorForIndex(0) },
    { id: "kind=overall_accuracy", kind: "overall_accuracy", label: "Overall accuracy", color: colorForIndex(1) },
  ]);

  // Fetch real graph data
  useEffect(() => {
    if (!userId || !backendBase) return;
    const load = async () => {
      setLoading(true);
      try {
        const baseUrl = backendBase.replace(/\/$/, "");
        const url = `${baseUrl}/profile/analytics/${userId}/graph-data?limit=60`;
        const res = await fetch(url, { cache: "no-store" });
        if (!res.ok) {
          const txt = await res.text();
          throw new Error(txt);
        }
        const data = await res.json();
        const list: GraphGamePoint[] = Array.isArray(data?.games) ? data.games : [];
        // Sort by date (asc) then index to keep stable
        list.sort((a, b) => {
          const da = a.game_date || "";
          const db = b.game_date || "";
          if (da !== db) return da.localeCompare(db);
          return (a.index ?? 0) - (b.index ?? 0);
        });
        setGames(list);
      } catch (e) {
        console.error("[GraphsTab] Failed to load graph data:", e);
        setGames([]);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [userId, backendBase]);

  useEffect(() => {
    if (!userId || !backendBase) return;
    // Prefetch detailed analytics in background so modal suggestions are instant.
    const loadDetailed = async () => {
      try {
        const baseUrl = backendBase.replace(/\/$/, "");
        const url = `${baseUrl}/profile/analytics/${userId}/detailed`;
        const res = await fetch(url, { cache: "no-store" });
        if (!res.ok) return;
        const data = (await res.json()) as DetailedAnalytics;
        setDetailed(data);
      } catch {
        // non-fatal
      }
    };
    loadDetailed();
  }, [userId, backendBase]);

  const openings = useMemo(() => {
    const counts = new Map<string, number>();
    for (const g of games) {
      const o = g.opening_name || "Unknown";
      counts.set(o, (counts.get(o) || 0) + 1);
    }
    return Array.from(counts.entries())
      .sort((a, b) => b[1] - a[1])
      .map(([o]) => o)
      .slice(0, 15);
  }, [games]);

  const points = useMemo(() => {
    if (grouping === "game") return groupByGame(games);
    if (grouping === "batch5") return groupByBatch5(games);
    return groupByDay(games);
  }, [games, grouping]);

  const builtSeries: BuiltSeries[] = useMemo(() => entries.map((e) => buildSeries(e, points)), [entries, points]);
  const xLabels = useMemo(() => points.map((p) => p.label), [points]);
  const chartSeries = useMemo(
    () =>
      builtSeries.map((s) => ({
        id: s.entry.id,
        name: s.entry.label,
        color: s.entry.color,
        normalizedValues: s.normalizedValues,
        rawValues: s.rawValues,
      })),
    [builtSeries]
  );
  const existingIds = useMemo(() => new Set(entries.map((e) => e.id)), [entries]);

  const removeEntry = (id: string) => setEntries((prev) => prev.filter((e) => e.id !== id));
  const addEntry = (entry: GraphSeriesEntry) =>
    setEntries((prev) => {
      if (prev.some((e) => e.id === entry.id)) return prev;
      // Ensure a color is set; if not, assign next in pool.
      const c = entry.color || colorForIndex(prev.length);
      return [...prev, { ...entry, color: c }];
    });

  return (
    <div className="graphs-tab">
      <div className="tab-section">
        <h2>Graphs</h2>
        <div style={{ display: "grid", gap: 12 }}>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <span style={{ color: "#cbd5e1", fontSize: 12 }}>Time points</span>
              <select
                value={grouping}
                onChange={(e) => setGrouping(e.target.value as GroupingMode)}
                style={{
                  padding: "6px 10px",
                  background: "#1e3a5f",
                  color: "#e0e7ff",
                  border: "1px solid rgba(147, 197, 253, 0.25)",
                  borderRadius: "6px",
                  fontSize: 12,
                }}
              >
                <option value="game">By game</option>
                <option value="day">By day</option>
                <option value="batch5">By 5-game batches</option>
              </select>
            </div>
            <div style={{ color: "#9ca3af", fontSize: 12 }}>
              {grouping === "game" 
                ? `${points.length} game points` 
                : grouping === "day" 
                ? `${points.length} day points` 
                : `${points.length} batch points`} • last {games.length} games
            </div>
          </div>

          <div
            style={{
              padding: "14px",
              background: "#1e3a5f",
              borderRadius: 10,
              border: "1px solid rgba(147, 197, 253, 0.2)",
            }}
          >
            {loading ? (
              <div style={{ color: "#93c5fd" }}>Loading graph data...</div>
            ) : games.length === 0 ? (
              <div style={{ color: "#9ca3af" }}>No graph data available yet.</div>
            ) : (
              <InteractiveLineChart xLabels={xLabels} series={chartSeries} />
            )}
          </div>

          <GraphSeriesTable series={builtSeries} onRemove={removeEntry} onAddClick={() => setShowAddModal(true)} />

          <AddGraphEntryModal
            isOpen={showAddModal}
            onClose={() => setShowAddModal(false)}
            onAdd={addEntry}
            existingIds={existingIds}
            openings={openings}
            detailed={detailed}
          />
        </div>
      </div>
    </div>
  );
}


