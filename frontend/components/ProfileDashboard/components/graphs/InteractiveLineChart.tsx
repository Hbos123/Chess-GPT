"use client";

import { useMemo, useRef, useState } from "react";

type Series = {
  id: string;
  name: string;
  color: string;
  normalizedValues: Array<number | null>;
  rawValues: Array<number | null>;
};

export default function InteractiveLineChart({
  xLabels,
  series,
  height = 280,
}: {
  xLabels: string[];
  series: Series[];
  height?: number;
}) {
  const width = 900;
  const padding = { top: 18, right: 18, bottom: 42, left: 44 };
  const svgRef = useRef<SVGSVGElement | null>(null);

  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  const [hoverXY, setHoverXY] = useState<{ x: number; y: number } | null>(null);

  const n = xLabels.length;
  const xScale = (i: number) => {
    if (n <= 1) return padding.left;
    return padding.left + (i / (n - 1)) * (width - padding.left - padding.right);
  };
  const yScale = (v01: number) => {
    // v01 is 0..100
    const clamped = Math.max(0, Math.min(100, v01));
    return height - padding.bottom - (clamped / 100) * (height - padding.top - padding.bottom);
  };

  const anyData = useMemo(() => {
    for (const s of series) {
      if (s.normalizedValues.some((v) => typeof v === "number" && Number.isFinite(v))) return true;
    }
    return false;
  }, [series]);

  const lines = useMemo(() => {
    return series.map((s) => {
      const pts: Array<{ x: number; y: number; i: number }> = [];
      for (let i = 0; i < n; i++) {
        const v = s.normalizedValues[i];
        if (typeof v !== "number" || !Number.isFinite(v)) continue;
        pts.push({ x: xScale(i), y: yScale(v), i });
      }
      return { ...s, pts };
    });
  }, [series, n]);

  const onMove = (e: React.MouseEvent<SVGSVGElement>) => {
    if (!svgRef.current || n <= 0) return;
    const rect = svgRef.current.getBoundingClientRect();
    const mx = e.clientX - rect.left;

    const plotLeft = padding.left;
    const plotRight = width - padding.right;
    const t = (mx - plotLeft) / Math.max(1, plotRight - plotLeft);
    const idx = Math.round(t * (n - 1));
    const clamped = Math.max(0, Math.min(n - 1, idx));
    setHoverIndex(clamped);

    // Tooltip anchor point: use first series with a value at that x, else bottom axis
    let y = height - padding.bottom;
    for (const s of lines) {
      const v = s.normalizedValues[clamped];
      if (typeof v === "number" && Number.isFinite(v)) {
        y = yScale(v);
        break;
      }
    }
    const x = xScale(clamped);
    setHoverXY({ x, y });
  };

  const onLeave = () => {
    setHoverIndex(null);
    setHoverXY(null);
  };

  const tooltip = useMemo(() => {
    if (hoverIndex == null) return null;
    const label = xLabels[hoverIndex] ?? "";
    const rows = series.map((s) => {
      const raw = s.rawValues[hoverIndex];
      return {
        id: s.id,
        name: s.name,
        color: s.color,
        raw: raw == null || !Number.isFinite(raw) ? null : raw,
      };
    });
    return { label, rows };
  }, [hoverIndex, xLabels, series]);

  return (
    <div style={{ position: "relative", width: "100%" }}>
      <svg
        ref={svgRef}
        width="100%"
        viewBox={`0 0 ${width} ${height}`}
        style={{ maxWidth: "100%", height: "auto", display: "block" }}
        onMouseMove={onMove}
        onMouseLeave={onLeave}
      >
        {/* Grid lines (0/25/50/75/100) */}
        {[0, 25, 50, 75, 100].map((pct) => {
          const y = yScale(pct);
          return (
            <g key={pct}>
              <line
                x1={padding.left}
                y1={y}
                x2={width - padding.right}
                y2={y}
                stroke="#374151"
                strokeWidth="1"
                opacity="0.28"
              />
              <text
                x={padding.left - 6}
                y={y + 4}
                textAnchor="end"
                style={{ fontSize: "10px", fill: "#9ca3af" }}
              >
                {pct}
              </text>
            </g>
          );
        })}

        {/* X axis labels (every 3rd + last) */}
        {xLabels.map((lbl, i) => {
          if (n > 12 && i % 3 !== 0 && i !== n - 1) return null;
          const short = lbl?.length > 10 ? lbl.slice(5, 10) : lbl;
          return (
            <text
              key={`x-${i}`}
              x={xScale(i)}
              y={height - padding.bottom + 22}
              textAnchor="middle"
              style={{ fontSize: "10px", fill: "#9ca3af" }}
            >
              {short}
            </text>
          );
        })}

        {/* Series smooth curves + dots */}
        {lines.map((s) => {
          if (s.pts.length < 2) return null;
          
          // Generate smooth path using cubic Bezier curves
          const generateSmoothPath = (points: Array<{ x: number; y: number }>): string => {
            if (points.length === 0) return "";
            if (points.length === 1) return `M ${points[0].x} ${points[0].y}`;
            
            let path = `M ${points[0].x} ${points[0].y}`;
            
            for (let i = 0; i < points.length - 1; i++) {
              const p0 = points[Math.max(0, i - 1)];
              const p1 = points[i];
              const p2 = points[i + 1];
              const p3 = points[Math.min(points.length - 1, i + 2)];
              
              // Calculate control points for smooth curve
              const cp1x = p1.x + (p2.x - p0.x) / 6;
              const cp1y = p1.y + (p2.y - p0.y) / 6;
              const cp2x = p2.x - (p3.x - p1.x) / 6;
              const cp2y = p2.y - (p3.y - p1.y) / 6;
              
              path += ` C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${p2.x} ${p2.y}`;
            }
            
            return path;
          };
          
          const pathData = generateSmoothPath(s.pts);
          
          return (
            <g key={s.id}>
              <path
                d={pathData}
                fill="none"
                stroke={s.color}
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                opacity="0.9"
              />
              {s.pts.map((p) => (
                <circle key={`${s.id}-dot-${p.i}`} cx={p.x} cy={p.y} r="3" fill={s.color} opacity="0.9" />
              ))}
            </g>
          );
        })}

        {/* Hover cursor */}
        {hoverIndex != null && hoverXY && (
          <g>
            <line
              x1={hoverXY.x}
              y1={padding.top}
              x2={hoverXY.x}
              y2={height - padding.bottom}
              stroke="rgba(148, 163, 184, 0.55)"
              strokeWidth="1"
            />
            {lines.map((s) => {
              const v = s.normalizedValues[hoverIndex];
              if (typeof v !== "number" || !Number.isFinite(v)) return null;
              return (
                <circle
                  key={`${s.id}-hover`}
                  cx={xScale(hoverIndex)}
                  cy={yScale(v)}
                  r="5"
                  fill={s.color}
                  opacity="1"
                />
              );
            })}
          </g>
        )}

        {!anyData && (
          <text
            x={width / 2}
            y={height / 2}
            textAnchor="middle"
            style={{ fontSize: "13px", fill: "#9ca3af" }}
          >
            Not enough data to plot.
          </text>
        )}
      </svg>

      {/* Tooltip */}
      {tooltip && hoverXY && (
        <div
          style={{
            position: "absolute",
            left: `${(hoverXY.x / width) * 100}%`,
            top: `${Math.max(0, (hoverXY.y / height) * 100 - 6)}%`,
            transform: "translate(-50%, -100%)",
            pointerEvents: "none",
            background: "rgba(15, 23, 42, 0.95)",
            border: "1px solid rgba(148, 163, 184, 0.25)",
            borderRadius: 10,
            padding: "10px 12px",
            minWidth: 220,
            color: "#e2e8f0",
            boxShadow: "0 10px 30px rgba(0,0,0,0.35)",
          }}
        >
          <div style={{ fontWeight: 700, fontSize: 12, marginBottom: 6 }}>{tooltip.label}</div>
          <div style={{ display: "grid", gap: 6 }}>
            {tooltip.rows.map((r) => (
              <div key={r.id} style={{ display: "flex", justifyContent: "space-between", gap: 10 }}>
                <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  <span style={{ width: 10, height: 10, borderRadius: 999, background: r.color }} />
                  <span style={{ fontSize: 12, color: "#cbd5e1" }}>{r.name}</span>
                </div>
                <div style={{ fontSize: 12, color: "#e0e7ff", fontVariantNumeric: "tabular-nums" }}>
                  {r.raw == null ? "—" : r.raw.toFixed(2)}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}


