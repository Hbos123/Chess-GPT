/**
 * HabitsDashboard - Micro-habits visualization with sparklines and trend charts
 * Shows significant playing patterns with visual significance indicators
 */

import { useState, useEffect, useMemo } from 'react';
import { fetchProfileHabits, type Habit, type ProfileHabitsResponse } from '@/lib/api';
import { 
  formatTagName, 
  getTagGroup, 
  getTagGroupInfo, 
  getSameGroupHabits, 
  calculateGroupAverage,
  calculateGroupSparkline,
  calculateBaselineSparkline,
  TAG_GROUPS 
} from '@/lib/tagGroups';
import './HabitsDashboard.css';

interface HabitsDashboardProps {
  userId: string;
  onRefresh?: () => void;
}

const INITIAL_DISPLAY_COUNT = 6;

// Sparkline component - simple SVG line chart
function Sparkline({ data, color, baseline }: { data: number[]; color: string; baseline?: number }) {
  if (!data || data.length === 0) return null;
  
  const width = 80;
  const height = 24;
  const padding = 2;
  
  const min = Math.min(...data, baseline ?? Infinity) - 5;
  const max = Math.max(...data, baseline ?? -Infinity) + 5;
  const range = max - min || 1;
  
  const points = data.map((value, i) => {
    const x = padding + (i / (data.length - 1)) * (width - 2 * padding);
    const y = height - padding - ((value - min) / range) * (height - 2 * padding);
    return `${x},${y}`;
  }).join(' ');
  
  // Baseline line
  const baselineY = baseline !== undefined 
    ? height - padding - ((baseline - min) / range) * (height - 2 * padding)
    : null;
  
  return (
    <svg width={width} height={height} className="sparkline">
      {baselineY !== null && (
        <line 
          x1={padding} 
          y1={baselineY} 
          x2={width - padding} 
          y2={baselineY} 
          stroke="#6b7280" 
          strokeWidth="1" 
          strokeDasharray="2,2" 
          opacity="0.5"
        />
      )}
      <polyline
        fill="none"
        stroke={color}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        points={points}
      />
      {/* Last point dot */}
      {data.length > 0 && (
        <circle
          cx={width - padding}
          cy={height - padding - ((data[data.length - 1] - min) / range) * (height - 2 * padding)}
          r="3"
          fill={color}
        />
      )}
    </svg>
  );
}

// Trend indicator
function TrendBadge({ trend, value }: { trend: string; value: number }) {
  const icon = trend === 'improving' ? '↗' : trend === 'declining' ? '↘' : '→';
  const colorClass = trend === 'improving' ? 'trend-up' : trend === 'declining' ? 'trend-down' : 'trend-stable';
  
  return (
    <span className={`trend-badge ${colorClass}`}>
      {icon} {Math.abs(value) > 0 ? `${value > 0 ? '+' : ''}${value.toFixed(1)}` : ''}
    </span>
  );
}

// Individual habit card - now clickable
function HabitCard({ 
  habit, 
  isStrength, 
  onClick 
}: { 
  habit: Habit; 
  isStrength: boolean;
  onClick: () => void;
}) {
  const deviationSign = habit.deviation >= 0 ? '+' : '';
  const significanceBar = Math.min(100, habit.significance * 100);
  const displayName = formatTagName(habit.name);
  
  // Get additional metrics based on habit_type
  const getAdditionalMetrics = () => {
    const metrics: string[] = [];
    
    if (habit.habit_type === 'tag' && habit.win_rate !== undefined) {
      metrics.push(`Win rate: ${(habit.win_rate * 100).toFixed(1)}%`);
    }
    
    if (habit.habit_type === 'tag' && habit.avg_cp_loss !== undefined) {
      metrics.push(`Avg CP loss: ${habit.avg_cp_loss.toFixed(1)}`);
    }
    
    if (habit.habit_type === 'time' && habit.error_rate !== undefined) {
      metrics.push(`Error rate: ${habit.error_rate.toFixed(1)}%`);
    }
    
    if (habit.habit_type === 'time' && habit.avg_cp_loss !== undefined) {
      metrics.push(`Avg CP loss: ${habit.avg_cp_loss.toFixed(1)}`);
    }
    
    if (habit.habit_type === 'tag_pref' && habit.preference_strength !== undefined) {
      const signal = habit.preference_signal || 'neutral';
      const strength = Math.abs(habit.preference_strength);
      metrics.push(`${signal === 'created' ? 'Creates' : signal === 'removed' ? 'Removes' : 'Neutral'}: ${(strength * 100).toFixed(0)}%`);
    }
    
    return metrics;
  };
  
  const additionalMetrics = getAdditionalMetrics();
  
  return (
    <div 
      className={`habit-card ${isStrength ? 'strength' : 'weakness'}`}
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === 'Enter' && onClick()}
    >
      <div className="habit-header">
        <span className="habit-name">{displayName}</span>
        <TrendBadge trend={habit.trend} value={habit.trend_value} />
      </div>
      
      <div className="habit-metrics">
        <div className="habit-accuracy">
          <span className="accuracy-value">{habit.accuracy.toFixed(1)}%</span>
          <span className={`accuracy-deviation ${habit.deviation >= 0 ? 'positive' : 'negative'}`}>
            {deviationSign}{habit.deviation.toFixed(1)}
          </span>
        </div>
        <Sparkline 
          data={habit.sparkline} 
          color={habit.deviation >= 0 ? '#22c55e' : '#ef4444'} 
          baseline={habit.baseline}
        />
      </div>
      
      {additionalMetrics.length > 0 && (
        <div className="habit-additional-metrics">
          {additionalMetrics.map((metric, idx) => (
            <span key={idx} className="habit-metric-item">{metric}</span>
          ))}
        </div>
      )}
      
      <div className="habit-footer">
        <span className="habit-sample">{habit.sample_size} games • {habit.total_occurrences} moves</span>
        <div className="significance-bar">
          <div 
            className="significance-fill" 
            style={{ width: `${significanceBar}%` }}
          />
        </div>
      </div>
    </div>
  );
}

// Large sparkline for modal - with axes and overlay support
function LargeSparkline({ 
  data, 
  baseline, 
  baselineSparkline,
  overlayData,
  groupAverageSparkline 
}: { 
  data: number[]; 
  baseline: number;
  baselineSparkline?: number[] | null;  // Baseline as time series
  overlayData?: { name: string; data: number[]; color: string }[];
  groupAverageSparkline?: number[] | null;  // Group average as time series
}) {
  if (!data || data.length === 0) return null;
  
  const width = 400;
  const height = 150;
  const padding = { top: 15, right: 15, bottom: 25, left: 45 };
  
  // Calculate bounds including all data
  const allValues = [...data];
  if (overlayData) {
    overlayData.forEach(o => allValues.push(...o.data));
  }
  if (baselineSparkline) {
    allValues.push(...baselineSparkline);
  } else {
    allValues.push(baseline);
  }
  if (groupAverageSparkline) {
    allValues.push(...groupAverageSparkline);
  }
  
  const min = Math.min(...allValues) - 5;
  const max = Math.max(...allValues) + 5;
  const range = max - min || 1;
  
  const xScale = (i: number, len: number) => 
    padding.left + (i / Math.max(1, len - 1)) * (width - padding.left - padding.right);
  const yScale = (v: number) => 
    height - padding.bottom - ((v - min) / range) * (height - padding.top - padding.bottom);
  
  // Generate points for main data
  const points = data.map((value, i) => 
    `${xScale(i, data.length)},${yScale(value)}`
  ).join(' ');
  
  // Generate baseline points (time series)
  const baselinePoints = baselineSparkline?.map((value, i) => 
    `${xScale(i, baselineSparkline.length)},${yScale(value)}`
  ).join(' ');
  
  // Generate group average points (time series)
  const groupAvgPoints = groupAverageSparkline?.map((value, i) => 
    `${xScale(i, groupAverageSparkline.length)},${yScale(value)}`
  ).join(' ');
  
  // Calculate current averages for labels
  const currentBaseline = baselineSparkline && baselineSparkline.length > 0
    ? baselineSparkline[baselineSparkline.length - 1]
    : baseline;
  const currentGroupAvg = groupAverageSparkline && groupAverageSparkline.length > 0
    ? groupAverageSparkline[groupAverageSparkline.length - 1]
    : null;
  
  return (
    <svg width="100%" viewBox={`0 0 ${width} ${height}`} className="large-sparkline">
      {/* Grid lines */}
      {[min, min + range * 0.25, min + range * 0.5, min + range * 0.75, max].map((val, i) => (
        <g key={i}>
          <line 
            x1={padding.left} 
            y1={yScale(val)} 
            x2={width - padding.right} 
            y2={yScale(val)} 
            stroke="#374151" 
            strokeWidth="1"
            opacity="0.3"
          />
          <text 
            x={padding.left - 8} 
            y={yScale(val) + 4} 
            textAnchor="end" 
            className="axis-label"
            fontSize="10"
            fill="#6b7280"
          >
            {val.toFixed(0)}%
          </text>
        </g>
      ))}
      
      {/* Baseline - as time series if available, otherwise horizontal line */}
      {baselinePoints ? (
        <>
          <polyline
            fill="none"
            stroke="#6b7280"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeDasharray="6,4"
            points={baselinePoints}
            opacity="0.7"
          />
          <text 
            x={width - padding.right + 5} 
            y={yScale(currentBaseline) + 3} 
            fontSize="9"
            fill="#6b7280"
          >
            avg ({currentBaseline.toFixed(0)}%)
          </text>
        </>
      ) : (
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
            y={yScale(baseline) + 3} 
            fontSize="9"
            fill="#6b7280"
          >
            avg ({baseline.toFixed(0)}%)
          </text>
        </>
      )}
      
      {/* Group average line as time series */}
      {groupAvgPoints && (
        <>
          <polyline
            fill="none"
            stroke="#8b5cf6"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeDasharray="4,3"
            points={groupAvgPoints}
            opacity="0.6"
          />
          {currentGroupAvg !== null && (
            <text 
              x={padding.left + 5} 
              y={yScale(currentGroupAvg) - 5} 
              fontSize="9"
              fill="#8b5cf6"
            >
              group avg ({currentGroupAvg.toFixed(0)}%)
            </text>
          )}
        </>
      )}
      
      {/* Overlay data lines */}
      {overlayData?.map((overlay, idx) => {
        const overlayPoints = overlay.data.map((value, i) => 
          `${xScale(i, overlay.data.length)},${yScale(value)}`
        ).join(' ');
        return (
          <polyline
            key={idx}
            fill="none"
            stroke={overlay.color}
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            points={overlayPoints}
            opacity="0.5"
          />
        );
      })}
      
      {/* Main data line */}
      <polyline
        fill="none"
        stroke="#ef4444"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        points={points}
      />
      
      {/* Data points */}
      {data.map((value, i) => (
        <circle
          key={i}
          cx={xScale(i, data.length)}
          cy={yScale(value)}
          r={i === data.length - 1 ? 5 : 3}
          fill={i === data.length - 1 ? '#ef4444' : '#ef4444'}
          opacity={i === data.length - 1 ? 1 : 0.7}
        />
      ))}
    </svg>
  );
}

// Modal for habit details
function HabitDetailModal({ 
  habit, 
  onClose, 
  allHabits,
  baseline 
}: { 
  habit: Habit;
  onClose: () => void;
  allHabits: Habit[];
  baseline: number;
}) {
  const [overlayHabits, setOverlayHabits] = useState<string[]>([]);
  const [showGroupAvg, setShowGroupAvg] = useState(false);
  const [showBaseline, setShowBaseline] = useState(true);
  
  const displayName = formatTagName(habit.name);
  const tagGroup = getTagGroup(habit.name);
  const groupInfo = getTagGroupInfo(habit.name);
  const sameGroupHabits = getSameGroupHabits(habit, allHabits);
  
  // Calculate group average over time (from sparklines)
  const groupAverageSparkline = useMemo(() => {
    if (!sameGroupHabits.length) return null;
    return calculateGroupSparkline([habit, ...sameGroupHabits]);
  }, [habit, sameGroupHabits]);
  
  // Current group average (last value)
  const currentGroupAverage = useMemo(() => {
    if (!groupAverageSparkline || groupAverageSparkline.length === 0) return null;
    return groupAverageSparkline[groupAverageSparkline.length - 1];
  }, [groupAverageSparkline]);
  
  // Calculate baseline over time (average of all habits)
  const baselineSparkline = useMemo(() => {
    return calculateBaselineSparkline(allHabits);
  }, [allHabits]);
  
  // Current baseline (last value or static)
  const currentBaseline = useMemo(() => {
    if (baselineSparkline && baselineSparkline.length > 0) {
      return baselineSparkline[baselineSparkline.length - 1];
    }
    return baseline;
  }, [baselineSparkline, baseline]);
  
  const overlayData = useMemo(() => {
    return overlayHabits
      .map(name => {
        const h = allHabits.find(x => x.name === name);
        if (!h) return null;
        return {
          name: formatTagName(h.name),
          data: h.sparkline,
          color: '#60a5fa'
        };
      })
      .filter(Boolean) as { name: string; data: number[]; color: string }[];
  }, [overlayHabits, allHabits]);
  
  const toggleOverlay = (name: string) => {
    setOverlayHabits(prev => 
      prev.includes(name) 
        ? prev.filter(n => n !== name)
        : [...prev, name]
    );
  };
  
  // Close on escape
  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleEsc);
    return () => window.removeEventListener('keydown', handleEsc);
  }, [onClose]);
  
  // Calculate deviation from current baseline
  const deviation = habit.accuracy - currentBaseline;
  
  return (
    <div className="habit-modal-overlay" onClick={onClose}>
      <div className="habit-modal" onClick={e => e.stopPropagation()}>
        <header className="modal-header">
          <div>
            <h3>{displayName}</h3>
            {groupInfo && (
              <span 
                className="modal-group-badge"
                style={{ backgroundColor: groupInfo.color }}
              >
                {groupInfo.displayName}
              </span>
            )}
          </div>
          <button className="modal-close" onClick={onClose} aria-label="Close">×</button>
        </header>
        
        <div className="modal-metrics">
          <div className="modal-metric">
            <span className="metric-value">{habit.accuracy.toFixed(1)}%</span>
            <span className="metric-label">Your Accuracy</span>
          </div>
          <div className="modal-metric">
            <span className="metric-value">{currentBaseline.toFixed(1)}%</span>
            <span className="metric-label">Avg Accuracy</span>
          </div>
          <div className="modal-metric">
            <span className={`metric-value ${deviation >= 0 ? 'positive' : 'negative'}`}>
              {deviation >= 0 ? '+' : ''}{deviation.toFixed(1)}%
            </span>
            <span className="metric-label">Deviation</span>
          </div>
          <div className="modal-metric">
            <span className="metric-value">{habit.sample_size}</span>
            <span className="metric-label">Games</span>
          </div>
        </div>
        
        <div className="modal-chart">
          <LargeSparkline 
            data={habit.sparkline} 
            baseline={currentBaseline}
            baselineSparkline={showBaseline ? baselineSparkline : null}
            overlayData={overlayData}
            groupAverageSparkline={showGroupAvg ? groupAverageSparkline : null}
          />
        </div>
        
        <div className="modal-overlay-options">
          <h4>Compare over time:</h4>
          <label className="overlay-option">
            <input 
              type="checkbox" 
              checked={showBaseline}
              onChange={() => setShowBaseline(!showBaseline)}
            />
            <span className="overlay-label">
              Average Accuracy
              <span className="overlay-value">({currentBaseline.toFixed(1)}%)</span>
            </span>
          </label>
          {currentGroupAverage !== null && sameGroupHabits.length > 0 && (
            <label className="overlay-option">
              <input 
                type="checkbox" 
                checked={showGroupAvg}
                onChange={() => setShowGroupAvg(!showGroupAvg)}
              />
              <span className="overlay-label">
                {groupInfo?.displayName || 'Group'} Average
                <span className="overlay-value">({currentGroupAverage.toFixed(1)}%)</span>
              </span>
            </label>
          )}
          {sameGroupHabits.slice(0, 5).map(h => (
            <label key={h.name} className="overlay-option">
              <input 
                type="checkbox"
                checked={overlayHabits.includes(h.name)}
                onChange={() => toggleOverlay(h.name)}
              />
              <span className="overlay-label">
                {formatTagName(h.name)}
                <span className="overlay-value">({h.accuracy.toFixed(1)}%)</span>
              </span>
            </label>
          ))}
        </div>
        
        <div className="modal-footer">
          <span className="habit-sample">
            Based on {habit.sample_size} games • {habit.total_occurrences} moves analyzed
          </span>
        </div>
      </div>
    </div>
  );
}

// Main trend chart with multiple habits
function TrendChart({ 
  dates, 
  series, 
  baseline 
}: { 
  dates: string[]; 
  series: ProfileHabitsResponse['trend_chart']['series']; 
  baseline: number;
}) {
  const [activeHabits, setActiveHabits] = useState<Set<string>>(
    new Set(series.slice(0, 3).map(s => s.habit_key))
  );
  
  if (!dates.length || !series.length) {
    return <div className="trend-chart-empty">Not enough data for trend chart</div>;
  }
  
  const width = 400;
  const height = 200;
  const padding = { top: 20, right: 20, bottom: 40, left: 50 };
  
  // Calculate bounds from visible series
  const visibleSeries = series.filter(s => activeHabits.has(s.habit_key));
  const allValues = visibleSeries.flatMap(s => 
    s.series.filter(Boolean).map(e => e!.accuracy)
  );
  allValues.push(baseline);
  
  const minVal = Math.min(...allValues) - 5;
  const maxVal = Math.max(...allValues) + 5;
  const valueRange = maxVal - minVal || 1;
  
  const toggleHabit = (key: string) => {
    setActiveHabits(prev => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };
  
  // X scale
  const xScale = (i: number) => padding.left + (i / (dates.length - 1)) * (width - padding.left - padding.right);
  // Y scale
  const yScale = (v: number) => height - padding.bottom - ((v - minVal) / valueRange) * (height - padding.top - padding.bottom);
  
  return (
    <div className="trend-chart-container">
      <div className="trend-chart-legend">
        {series.map(s => (
          <button
            key={s.habit_key}
            className={`legend-item ${activeHabits.has(s.habit_key) ? 'active' : ''}`}
            onClick={() => toggleHabit(s.habit_key)}
            style={{ borderColor: activeHabits.has(s.habit_key) ? s.color : 'transparent' }}
          >
            <span className="legend-dot" style={{ backgroundColor: s.color }} />
            {s.name}
          </button>
        ))}
      </div>
      
      <svg width="100%" viewBox={`0 0 ${width} ${height}`} className="trend-chart-svg">
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
              <text x={padding.left - 5} y={y + 4} textAnchor="end" className="axis-label">
                {val.toFixed(0)}%
              </text>
            </g>
          );
        })}
        
        {/* Baseline */}
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
          className="baseline-label"
        >
          baseline
        </text>
        
        {/* X axis labels (show every 3rd date) */}
        {dates.map((date, i) => {
          if (i % 3 !== 0 && i !== dates.length - 1) return null;
          return (
            <text 
              key={date} 
              x={xScale(i)} 
              y={height - padding.bottom + 20} 
              textAnchor="middle" 
              className="axis-label"
            >
              {date.slice(5)} {/* MM-DD */}
            </text>
          );
        })}
        
        {/* Series lines */}
        {visibleSeries.map(s => {
          const points: string[] = [];
          const dots: { x: number; y: number; significant: boolean }[] = [];
          
          s.series.forEach((entry, i) => {
            if (entry) {
              const x = xScale(i);
              const y = yScale(entry.accuracy);
              points.push(`${x},${y}`);
              dots.push({ x, y, significant: entry.significant ?? false });
            }
          });
          
          if (points.length < 2) return null;
          
          return (
            <g key={s.habit_key}>
              <polyline
                fill="none"
                stroke={s.color}
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                points={points.join(' ')}
                opacity="0.8"
              />
              {/* Only show dots for significant data points */}
              {dots.map((dot, i) => (
                <circle
                  key={i}
                  cx={dot.x}
                  cy={dot.y}
                  r={dot.significant ? 4 : 2}
                  fill={s.color}
                  opacity={dot.significant ? 1 : 0.5}
                />
              ))}
            </g>
          );
        })}
      </svg>
    </div>
  );
}

// Main dashboard component
export default function HabitsDashboard({ userId, onRefresh }: HabitsDashboardProps) {
  const [habitsData, setHabitsData] = useState<ProfileHabitsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'cards' | 'chart'>('cards');
  const [selectedHabit, setSelectedHabit] = useState<Habit | null>(null);
  const [showAllWeaknesses, setShowAllWeaknesses] = useState(false);
  const [showAllStrengths, setShowAllStrengths] = useState(false);
  
  useEffect(() => {
    if (!userId) return;
    
    const loadHabits = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await fetchProfileHabits(userId);
        setHabitsData(data);
      } catch (err) {
        // Habits computation can take time - data is saved to Supabase so it will be available
        // on next fetch even if this request fails or is slow
        console.error('Failed to load habits:', err);
        // Show error but note that computation may still be happening in background
        const errorMsg = err instanceof Error ? err.message : 'Failed to load habits';
        setError(`${errorMsg}. Computation may still be in progress - data will be available on refresh once complete.`);
      } finally {
        setLoading(false);
      }
    };
    
    loadHabits();
  }, [userId]);
  
  // Memoize displayed habits based on showAll state
  const displayedWeaknesses = useMemo(() => {
    if (!habitsData) return [];
    return showAllWeaknesses 
      ? habitsData.weaknesses 
      : habitsData.weaknesses.slice(0, INITIAL_DISPLAY_COUNT);
  }, [habitsData, showAllWeaknesses]);
  
  const displayedStrengths = useMemo(() => {
    if (!habitsData) return [];
    return showAllStrengths 
      ? habitsData.strengths 
      : habitsData.strengths.slice(0, INITIAL_DISPLAY_COUNT);
  }, [habitsData, showAllStrengths]);
  
  if (loading) {
    return (
      <div className="habits-dashboard loading">
        <div className="loading-spinner">Analyzing your habits...</div>
      </div>
    );
  }
  
  if (error) {
    return (
      <div className="habits-dashboard error">
        <p>{error}</p>
        <button onClick={onRefresh}>Retry</button>
      </div>
    );
  }
  
  if (!habitsData || habitsData.habits.length === 0) {
    return (
      <div className="habits-dashboard empty">
        <p>Not enough games analyzed to detect habits.</p>
        <p className="empty-hint">Play and analyze more games to see your patterns!</p>
      </div>
    );
  }
  
  const { strengths, weaknesses, baseline_accuracy, total_games, trend_chart, habits } = habitsData;
  
  return (
    <div className="habits-dashboard">
      <header className="habits-header">
        <div className="habits-title">
          <h3>Your Chess Habits</h3>
          <span className="habits-subtitle">
            Based on {total_games} analyzed games • Baseline: {baseline_accuracy}%
          </span>
        </div>
        <div className="habits-view-toggle">
          <button 
            className={viewMode === 'cards' ? 'active' : ''} 
            onClick={() => setViewMode('cards')}
          >
            Cards
          </button>
          <button 
            className={viewMode === 'chart' ? 'active' : ''} 
            onClick={() => setViewMode('chart')}
          >
            Trends
          </button>
        </div>
      </header>
      
      {viewMode === 'cards' ? (
        <div className="habits-grid">
          {strengths.length > 0 && (
            <section className="habits-section strengths">
              <h4>💪 Strengths</h4>
              <div className="habits-cards">
                {displayedStrengths.map(habit => (
                  <HabitCard 
                    key={habit.name} 
                    habit={habit} 
                    isStrength={true}
                    onClick={() => setSelectedHabit(habit)}
                  />
                ))}
              </div>
              {strengths.length > INITIAL_DISPLAY_COUNT && (
                <div className="show-more-container">
                  <button 
                    className="show-more-btn"
                    onClick={() => setShowAllStrengths(!showAllStrengths)}
                  >
                    {showAllStrengths 
                      ? 'Show Less' 
                      : `Show ${strengths.length - INITIAL_DISPLAY_COUNT} More`}
                  </button>
                </div>
              )}
            </section>
          )}
          
          {weaknesses.length > 0 && (
            <section className="habits-section weaknesses">
              <h4>🎯 Focus Areas</h4>
              <div className="habits-cards">
                {displayedWeaknesses.map(habit => (
                  <HabitCard 
                    key={habit.name} 
                    habit={habit} 
                    isStrength={false}
                    onClick={() => setSelectedHabit(habit)}
                  />
                ))}
              </div>
              {weaknesses.length > INITIAL_DISPLAY_COUNT && (
                <div className="show-more-container">
                  <button 
                    className="show-more-btn"
                    onClick={() => setShowAllWeaknesses(!showAllWeaknesses)}
                  >
                    {showAllWeaknesses 
                      ? 'Show Less' 
                      : `Show ${weaknesses.length - INITIAL_DISPLAY_COUNT} More`}
                  </button>
                </div>
              )}
            </section>
          )}
        </div>
      ) : (
        <div className="habits-trend-view">
          <TrendChart 
            dates={trend_chart.dates}
            series={trend_chart.series}
            baseline={trend_chart.baseline}
          />
        </div>
      )}
      
      {/* Habit Detail Modal */}
      {selectedHabit && (
        <HabitDetailModal
          habit={selectedHabit}
          onClose={() => setSelectedHabit(null)}
          allHabits={habits}
          baseline={baseline_accuracy}
        />
      )}
    </div>
  );
}

