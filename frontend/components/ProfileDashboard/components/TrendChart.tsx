"use client";

import { useState } from "react";

interface TrendChartProps {
  dates: string[];
  series: Array<{
    name: string;
    data: (number | null)[];
    color: string;
  }>;
  baseline?: number;
  height?: number;
  showLegend?: boolean;
}

export default function TrendChart({ 
  dates, 
  series, 
  baseline,
  height = 200,
  showLegend = true 
}: TrendChartProps) {
  const [activeSeries, setActiveSeries] = useState<Set<string>>(
    new Set(series.slice(0, 3).map((s, i) => `series-${i}`))
  );
  
  if (!dates.length || !series.length) {
    return (
      <div style={{ 
        padding: '20px', 
        textAlign: 'center', 
        color: '#9ca3af',
        fontSize: '14px'
      }}>
        Not enough data for trend chart
      </div>
    );
  }
  
  const width = 600;
  const padding = { top: 20, right: 20, bottom: 40, left: 50 };
  
  // Calculate bounds from visible series
  const visibleSeries = series.filter((s, i) => activeSeries.has(`series-${i}`));
  const allValues: number[] = [];
  visibleSeries.forEach(s => {
    s.data.forEach(v => {
      if (v !== null) allValues.push(v);
    });
  });
  if (baseline !== undefined) {
    allValues.push(baseline);
  }
  
  const minVal = allValues.length > 0 ? Math.min(...allValues) - 5 : 0;
  const maxVal = allValues.length > 0 ? Math.max(...allValues) + 5 : 100;
  const valueRange = maxVal - minVal || 1;
  
  const toggleSeries = (index: number) => {
    setActiveSeries(prev => {
      const next = new Set(prev);
      const key = `series-${index}`;
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };
  
  // X scale
  const xScale = (i: number) => {
    if (dates.length <= 1) return padding.left;
    return padding.left + (i / (dates.length - 1)) * (width - padding.left - padding.right);
  };
  
  // Y scale
  const yScale = (v: number) => {
    return height - padding.bottom - ((v - minVal) / valueRange) * (height - padding.top - padding.bottom);
  };
  
  return (
    <div style={{ width: '100%' }}>
      {showLegend && series.length > 1 && (
        <div style={{ 
          display: 'flex', 
          flexWrap: 'wrap', 
          gap: '8px', 
          marginBottom: '12px',
          justifyContent: 'center'
        }}>
          {series.map((s, i) => {
            const isActive = activeSeries.has(`series-${i}`);
            return (
              <button
                key={`series-${i}`}
                onClick={() => toggleSeries(i)}
                style={{
                  padding: '4px 12px',
                  background: isActive ? 'rgba(59, 130, 246, 0.2)' : 'rgba(107, 114, 128, 0.1)',
                  border: `1px solid ${isActive ? s.color : 'transparent'}`,
                  borderRadius: '4px',
                  cursor: 'pointer',
                  fontSize: '12px',
                  color: '#e0e7ff',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  transition: 'all 0.2s'
                }}
              >
                <span style={{
                  width: '8px',
                  height: '8px',
                  borderRadius: '50%',
                  backgroundColor: s.color,
                  opacity: isActive ? 1 : 0.5
                }} />
                {s.name}
              </button>
            );
          })}
        </div>
      )}
      
      <svg width="100%" viewBox={`0 0 ${width} ${height}`} style={{ maxWidth: '100%', height: 'auto' }}>
        {/* Grid lines */}
        {[0, 25, 50, 75, 100].map(pct => {
          const val = minVal + (pct / 100) * valueRange;
          const y = yScale(val);
          return (
            <g key={pct}>
              <line 
                x1={padding.left} 
                y1={y} 
                x2={width - padding.right} 
                y2={y} 
                stroke="#374151" 
                strokeWidth="1"
                opacity="0.3"
              />
              <text 
                x={padding.left - 5} 
                y={y + 4} 
                textAnchor="end" 
                style={{
                  fontSize: '10px',
                  fill: '#9ca3af'
                }}
              >
                {val.toFixed(0)}%
              </text>
            </g>
          );
        })}
        
        {/* Baseline */}
        {baseline !== undefined && (
          <>
            <line
              x1={padding.left}
              y1={yScale(baseline)}
              x2={width - padding.right}
              y2={yScale(baseline)}
              stroke="#6b7280"
              strokeWidth="2"
              strokeDasharray="6,4"
              opacity="0.7"
            />
            <text 
              x={width - padding.right + 5} 
              y={yScale(baseline) + 4} 
              style={{
                fontSize: '10px',
                fill: '#6b7280'
              }}
            >
              baseline
            </text>
          </>
        )}
        
        {/* X axis labels (show every 3rd date or last date) */}
        {dates.map((date, i) => {
          if (i % 3 !== 0 && i !== dates.length - 1) return null;
          return (
            <text 
              key={`date-${i}`} 
              x={xScale(i)} 
              y={height - padding.bottom + 20} 
              textAnchor="middle" 
              style={{
                fontSize: '10px',
                fill: '#9ca3af'
              }}
            >
              {date.length > 10 ? date.slice(5, 10) : date.slice(5)} {/* MM-DD */}
            </text>
          );
        })}
        
        {/* Series lines */}
        {visibleSeries.map((s, seriesIndex) => {
          const originalIndex = series.indexOf(s);
          const points: string[] = [];
          const dots: Array<{ x: number; y: number }> = [];
          
          s.data.forEach((value, i) => {
            if (value !== null) {
              const x = xScale(i);
              const y = yScale(value);
              points.push(`${x},${y}`);
              dots.push({ x, y });
            }
          });
          
          if (points.length < 2) return null;
          
          return (
            <g key={`series-${originalIndex}`}>
              <polyline
                fill="none"
                stroke={s.color}
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                points={points.join(' ')}
                opacity="0.8"
              />
              {/* Data points */}
              {dots.map((dot, i) => (
                <circle
                  key={`dot-${i}`}
                  cx={dot.x}
                  cy={dot.y}
                  r="3"
                  fill={s.color}
                  opacity="0.9"
                />
              ))}
            </g>
          );
        })}
      </svg>
    </div>
  );
}

