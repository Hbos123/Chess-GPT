export type GroupingMode = "game" | "day" | "batch5";

export type GraphGamePoint = {
  index: number;
  game_id: string;
  game_date: string | null;
  result: string;
  opening_name: string;
  opening_eco: string;
  time_control?: string | null;
  overall_accuracy: number | null;
  piece_accuracy?: Record<string, { accuracy: number | null; count: number }>;
  time_bucket_accuracy?: Record<string, { accuracy: number | null; count: number }>;
  tag_transitions?: {
    gained: Record<string, { count: number; avg_accuracy: number | null }>;
    lost: Record<string, { count: number; avg_accuracy: number | null }>;
  };
};

export type TimePoint = {
  key: string;
  label: string;
  games: GraphGamePoint[];
};

export type SeriesKind =
  | "win_rate_pct"
  | "overall_accuracy"
  | "opening_frequency_pct"
  | "opening_accuracy"
  | "piece_accuracy"
  | "time_bucket_accuracy"
  | "tag_transition_count"
  | "tag_transition_accuracy";

export type GraphSeriesEntry = {
  id: string;
  label: string;
  kind: SeriesKind;
  color: string;
  params?: {
    openingName?: string;
    piece?: string;
    bucket?: string;
    tag?: string;
    dir?: "gained" | "lost";
  };
};

export type BuiltSeries = {
  entry: GraphSeriesEntry;
  rawValues: Array<number | null>;
  normalizedValues: Array<number | null>;
  instancesByPoint: number[];
  instancesTotal: number;
  nPoints: number;
  trendDelta: number | null;
};

export function resultToScore(result: string): number {
  const r = String(result || "").toLowerCase();
  if (r === "win") return 1;
  if (r === "draw") return 0.5;
  if (r === "loss") return 0;
  return 0;
}

export function mean(values: Array<number | null | undefined>): number | null {
  const xs = values.filter((v): v is number => typeof v === "number" && Number.isFinite(v));
  if (xs.length === 0) return null;
  return xs.reduce((a, b) => a + b, 0) / xs.length;
}

export function weightedMean(items: Array<{ value: number | null; weight: number }>): number | null {
  let w = 0;
  let s = 0;
  for (const it of items) {
    if (typeof it.value !== "number" || !Number.isFinite(it.value)) continue;
    if (typeof it.weight !== "number" || !Number.isFinite(it.weight) || it.weight <= 0) continue;
    w += it.weight;
    s += it.value * it.weight;
  }
  if (w <= 0) return null;
  return s / w;
}

export function computeTrendDelta(rawValues: Array<number | null>): number | null {
  // delta of last point vs previous point, skipping nulls but preserving order
  const idxs: number[] = [];
  for (let i = 0; i < rawValues.length; i++) {
    const v = rawValues[i];
    if (typeof v === "number" && Number.isFinite(v)) idxs.push(i);
  }
  if (idxs.length < 2) return null;
  const last = rawValues[idxs[idxs.length - 1]] as number;
  const prev = rawValues[idxs[idxs.length - 2]] as number;
  return last - prev;
}

export function normalizeTo0_100(values: Array<number | null>): Array<number | null> {
  const xs = values.filter((v): v is number => typeof v === "number" && Number.isFinite(v));
  if (xs.length === 0) return values.map(() => null);
  const min = Math.min(...xs);
  const max = Math.max(...xs);
  const range = max - min || 1;
  return values.map((v) => {
    if (typeof v !== "number" || !Number.isFinite(v)) return null;
    return ((v - min) / range) * 100;
  });
}

export function buildSeries(entry: GraphSeriesEntry, points: TimePoint[]): BuiltSeries {
  const kind = entry.kind;
  const params = entry.params || {};

  const rawValues: Array<number | null> = [];
  const instancesByPoint: number[] = [];

  for (const p of points) {
    const games = p.games || [];

    if (kind === "win_rate_pct") {
      const total = games.length;
      const wins = games.filter((g) => String(g.result || "").toLowerCase() === "win").length;
      rawValues.push(total > 0 ? (wins / total) * 100 : null);
      instancesByPoint.push(total);
      continue;
    }

    if (kind === "overall_accuracy") {
      rawValues.push(mean(games.map((g) => g.overall_accuracy)));
      // instances: games contributing with a numeric value
      const n = games.filter((g) => typeof g.overall_accuracy === "number" && Number.isFinite(g.overall_accuracy)).length;
      instancesByPoint.push(n);
      continue;
    }

    if (kind === "opening_frequency_pct") {
      const o = params.openingName || "Unknown";
      const total = games.length;
      const n = games.filter((g) => (g.opening_name || "Unknown") === o).length;
      rawValues.push(total > 0 ? (n / total) * 100 : null);
      instancesByPoint.push(n);
      continue;
    }

    if (kind === "opening_accuracy") {
      const o = params.openingName || "Unknown";
      const matching = games.filter((g) => (g.opening_name || "Unknown") === o);
      rawValues.push(mean(matching.map((g) => g.overall_accuracy)));
      instancesByPoint.push(matching.length);
      continue;
    }

    if (kind === "piece_accuracy") {
      const piece = params.piece || "Pawn";
      const items = games.map((g) => {
        const it = g.piece_accuracy?.[piece];
        return { value: it?.accuracy ?? null, weight: it?.count ?? 0 };
      });
      rawValues.push(weightedMean(items));
      const inst = items.reduce((s, it) => s + (it.weight || 0), 0);
      instancesByPoint.push(inst);
      continue;
    }

    if (kind === "time_bucket_accuracy") {
      const bucket = params.bucket || "<5s";
      const items = games.map((g) => {
        const it = g.time_bucket_accuracy?.[bucket];
        return { value: it?.accuracy ?? null, weight: it?.count ?? 0 };
      });
      rawValues.push(weightedMean(items));
      const inst = items.reduce((s, it) => s + (it.weight || 0), 0);
      instancesByPoint.push(inst);
      continue;
    }

    if (kind === "tag_transition_count") {
      const tag = params.tag || "";
      const dir = params.dir || "gained";
      const counts = games.map((g) => g.tag_transitions?.[dir]?.[tag]?.count ?? 0);
      rawValues.push(counts.reduce((a, b) => a + b, 0));
      instancesByPoint.push(counts.reduce((a, b) => a + b, 0));
      continue;
    }

    if (kind === "tag_transition_accuracy") {
      const tag = params.tag || "";
      const dir = params.dir || "gained";
      const items = games.map((g) => {
        const it = g.tag_transitions?.[dir]?.[tag];
        return { value: it?.avg_accuracy ?? null, weight: it?.count ?? 0 };
      });
      rawValues.push(weightedMean(items));
      const inst = items.reduce((s, it) => s + (it.weight || 0), 0);
      instancesByPoint.push(inst);
      continue;
    }

    rawValues.push(null);
    instancesByPoint.push(0);
  }

  const normalizedValues = normalizeTo0_100(rawValues);
  const instancesTotal = instancesByPoint.reduce((a, b) => a + b, 0);
  const trendDelta = computeTrendDelta(rawValues);

  return {
    entry,
    rawValues,
    normalizedValues,
    instancesByPoint,
    instancesTotal,
    nPoints: points.length,
    trendDelta,
  };
}

export function formatDelta(delta: number | null, decimals = 1): string {
  if (delta == null || !Number.isFinite(delta)) return "—";
  const sign = delta > 0 ? "+" : "";
  return `${sign}${delta.toFixed(decimals)}`;
}

export function formatTagName(tag: string): string {
  return String(tag || "")
    .replace(/^tag\./, "")
    .replace(/\./g, " ")
    .replace(/\b\w/g, (l) => l.toUpperCase());
}


