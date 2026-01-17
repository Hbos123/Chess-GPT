"use client";

import ExpandableAnalyticsCard from "./ExpandableAnalyticsCard";

interface TagTransitionsCardProps {
  tagTransitions: {
    gained?: { 
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
      } 
    };
    lost?: { 
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
      } 
    };
  };
}

export default function TagTransitionsCard({ tagTransitions }: TagTransitionsCardProps) {
  const gained = tagTransitions?.gained || {};
  const lost = tagTransitions?.lost || {};
  
  // Sort by significance_score first, then accuracy - highest and lowest
  const gainedEntries = Object.entries(gained).map(([tag, data]) => ({ tag, ...data }));
  const highestGained = [...gainedEntries]
    .sort((a, b) => {
      const sigA = a.significance_score || 0;
      const sigB = b.significance_score || 0;
      if (sigA !== sigB) return sigB - sigA;
      return b.accuracy - a.accuracy;
    })
    .slice(0, 5);
  const lowestGained = [...gainedEntries]
    .sort((a, b) => {
      const sigA = a.significance_score || 0;
      const sigB = b.significance_score || 0;
      if (sigA !== sigB) return sigB - sigA;
      return a.accuracy - b.accuracy;
    })
    .slice(0, 5);
  
  const lostEntries = Object.entries(lost).map(([tag, data]) => ({ tag, ...data }));
  const highestLost = [...lostEntries]
    .sort((a, b) => {
      const sigA = a.significance_score || 0;
      const sigB = b.significance_score || 0;
      if (sigA !== sigB) return sigB - sigA;
      return b.accuracy - a.accuracy;
    })
    .slice(0, 5);
  const lowestLost = [...lostEntries]
    .sort((a, b) => {
      const sigA = a.significance_score || 0;
      const sigB = b.significance_score || 0;
      if (sigA !== sigB) return sigB - sigA;
      return a.accuracy - b.accuracy;
    })
    .slice(0, 5);
  
  // Calculate overall significance score (average of top tags)
  const allSignificanceScores = [
    ...gainedEntries.map(e => e.significance_score || 0),
    ...lostEntries.map(e => e.significance_score || 0)
  ].filter(s => s > 0);
  const overallSignificance = allSignificanceScores.length > 0
    ? allSignificanceScores.reduce((a, b) => a + b, 0) / allSignificanceScores.length
    : undefined;
  
  // Build trend data from day intervals
  const buildTrendData = () => {
    const allDates = new Set<string>();
    const seriesMap = new Map<string, { name: string; data: Map<string, number>; color: string }>();
    
    // Collect all dates and build series
    [...gainedEntries, ...lostEntries].forEach(({ tag, day_intervals }) => {
      if (day_intervals && day_intervals.dates.length > 0) {
        day_intervals.dates.forEach(date => allDates.add(date));
        const seriesName = formatTagName(tag);
        const color = gainedEntries.some(e => e.tag === tag) ? '#10b981' : '#ef4444';
        seriesMap.set(tag, {
          name: seriesName,
          data: new Map(day_intervals.dates.map((date, i) => [date, day_intervals.accuracies[i]])),
          color
        });
      }
    });
    
    if (allDates.size === 0) return undefined;
    
    const sortedDates = Array.from(allDates).sort();
    const series = Array.from(seriesMap.values()).slice(0, 5); // Limit to top 5 for readability
    
    return {
      dates: sortedDates,
      series: series.map(s => ({
        name: s.name,
        data: sortedDates.map(date => s.data.get(date) ?? null),
        color: s.color
      })),
      baseline: undefined
    };
  };
  
  const trendData = buildTrendData();

  const formatTagName = (tag: string) => {
    return tag
      .replace(/^tag\./, '')
      .replace(/\./g, ' ')
      .replace(/\b\w/g, l => l.toUpperCase());
  };

  if (highestGained.length === 0 && highestLost.length === 0) {
    return (
      <ExpandableAnalyticsCard title="Tag Transitions">
        <p style={{ color: '#cbd5e1', fontSize: '14px' }}>No tag transition data available yet.</p>
      </ExpandableAnalyticsCard>
    );
  }

  return (
    <ExpandableAnalyticsCard 
      title="Tag Transitions"
      significanceScore={overallSignificance}
      trendData={trendData}
    >
      
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
        {/* Gained Tags */}
        <div>
          <h4 style={{ margin: '0 0 12px 0', fontSize: '14px', fontWeight: 600, color: '#10b981' }}>
            Tags Gained - Highest Accuracy
          </h4>
          {highestGained.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '20px' }}>
              {highestGained.map(({ tag, ...data }) => {
                const errorRate = data.count > 0 
                  ? ((data.blunders + data.mistakes + data.inaccuracies) / data.count * 100)
                  : 0;
                
                return (
                  <div key={tag} style={{
                    padding: '12px',
                    background: 'rgba(16, 185, 129, 0.1)',
                    borderRadius: '6px',
                    border: '1px solid rgba(16, 185, 129, 0.2)'
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                      <div style={{ fontSize: '13px', fontWeight: 600, color: '#6ee7b7' }}>
                        {formatTagName(tag)}
                      </div>
                      {data.significance_score !== undefined && (
                        <div style={{
                          padding: '2px 6px',
                          borderRadius: '3px',
                          fontSize: '10px',
                          fontWeight: 600,
                          background: data.significance_score >= 70 ? 'rgba(16, 185, 129, 0.2)' : 
                                     data.significance_score >= 40 ? 'rgba(251, 191, 36, 0.2)' : 
                                     'rgba(107, 114, 128, 0.2)',
                          color: data.significance_score >= 70 ? '#10b981' : 
                                 data.significance_score >= 40 ? '#fbbf24' : '#9ca3af'
                        }}>
                          {data.significance_score.toFixed(0)}
                        </div>
                      )}
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', color: '#cbd5e1', marginBottom: '4px' }}>
                      <span>Accuracy:</span>
                      <span style={{ fontWeight: 600 }}>{data.accuracy.toFixed(1)}%</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', color: '#cbd5e1', marginBottom: '4px' }}>
                      <span>Occurrences:</span>
                      <span>{data.count}</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', color: '#cbd5e1' }}>
                      <span>Error Rate:</span>
                      <span style={{ color: errorRate > 20 ? '#ef4444' : errorRate > 10 ? '#fbbf24' : '#10b981' }}>
                        {errorRate.toFixed(1)}%
                      </span>
                    </div>
                    {data.trend && data.trend_value !== undefined && (
                      <div style={{ 
                        fontSize: '11px', 
                        color: data.trend === 'improving' ? '#10b981' : data.trend === 'declining' ? '#ef4444' : '#9ca3af',
                        marginTop: '4px',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '4px'
                      }}>
                        {data.trend === 'improving' ? '↑' : data.trend === 'declining' ? '↓' : '→'}
                        <span>
                          {data.trend_value > 0 ? '+' : ''}{data.trend_value}% over last 10 games
                        </span>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          ) : (
            <p style={{ color: '#9ca3af', fontSize: '12px' }}>No data</p>
          )}
          
          <h4 style={{ margin: '20px 0 12px 0', fontSize: '14px', fontWeight: 600, color: '#fbbf24' }}>
            Tags Gained - Lowest Accuracy
          </h4>
          {lowestGained.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {lowestGained.map(({ tag, ...data }) => {
                const errorRate = data.count > 0 
                  ? ((data.blunders + data.mistakes + data.inaccuracies) / data.count * 100)
                  : 0;
                
                return (
                  <div key={tag} style={{
                    padding: '12px',
                    background: 'rgba(251, 191, 36, 0.1)',
                    borderRadius: '6px',
                    border: '1px solid rgba(251, 191, 36, 0.2)'
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                      <div style={{ fontSize: '13px', fontWeight: 600, color: '#fbbf24' }}>
                        {formatTagName(tag)}
                      </div>
                      {data.significance_score !== undefined && (
                        <div style={{
                          padding: '2px 6px',
                          borderRadius: '3px',
                          fontSize: '10px',
                          fontWeight: 600,
                          background: data.significance_score >= 70 ? 'rgba(16, 185, 129, 0.2)' : 
                                     data.significance_score >= 40 ? 'rgba(251, 191, 36, 0.2)' : 
                                     'rgba(107, 114, 128, 0.2)',
                          color: data.significance_score >= 70 ? '#10b981' : 
                                 data.significance_score >= 40 ? '#fbbf24' : '#9ca3af'
                        }}>
                          {data.significance_score.toFixed(0)}
                        </div>
                      )}
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', color: '#cbd5e1', marginBottom: '4px' }}>
                      <span>Accuracy:</span>
                      <span style={{ fontWeight: 600 }}>{data.accuracy.toFixed(1)}%</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', color: '#cbd5e1', marginBottom: '4px' }}>
                      <span>Occurrences:</span>
                      <span>{data.count}</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', color: '#cbd5e1' }}>
                      <span>Error Rate:</span>
                      <span style={{ color: errorRate > 20 ? '#ef4444' : errorRate > 10 ? '#fbbf24' : '#10b981' }}>
                        {errorRate.toFixed(1)}%
                      </span>
                    </div>
                    {data.trend && data.trend_value !== undefined && (
                      <div style={{ 
                        fontSize: '11px', 
                        color: data.trend === 'improving' ? '#10b981' : data.trend === 'declining' ? '#ef4444' : '#9ca3af',
                        marginTop: '4px',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '4px'
                      }}>
                        {data.trend === 'improving' ? '↑' : data.trend === 'declining' ? '↓' : '→'}
                        <span>
                          {data.trend_value > 0 ? '+' : ''}{data.trend_value}% over last 10 games
                        </span>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          ) : (
            <p style={{ color: '#9ca3af', fontSize: '12px' }}>No data</p>
          )}
        </div>

        {/* Lost Tags */}
        <div>
          <h4 style={{ margin: '0 0 12px 0', fontSize: '14px', fontWeight: 600, color: '#ef4444' }}>
            Tags Lost - Highest Accuracy
          </h4>
          {highestLost.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '20px' }}>
              {highestLost.map(({ tag, ...data }) => {
                const errorRate = data.count > 0 
                  ? ((data.blunders + data.mistakes + data.inaccuracies) / data.count * 100)
                  : 0;
                
                return (
                  <div key={tag} style={{
                    padding: '12px',
                    background: 'rgba(239, 68, 68, 0.1)',
                    borderRadius: '6px',
                    border: '1px solid rgba(239, 68, 68, 0.2)'
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                      <div style={{ fontSize: '13px', fontWeight: 600, color: '#fca5a5' }}>
                        {formatTagName(tag)}
                      </div>
                      {data.significance_score !== undefined && (
                        <div style={{
                          padding: '2px 6px',
                          borderRadius: '3px',
                          fontSize: '10px',
                          fontWeight: 600,
                          background: data.significance_score >= 70 ? 'rgba(16, 185, 129, 0.2)' : 
                                     data.significance_score >= 40 ? 'rgba(251, 191, 36, 0.2)' : 
                                     'rgba(107, 114, 128, 0.2)',
                          color: data.significance_score >= 70 ? '#10b981' : 
                                 data.significance_score >= 40 ? '#fbbf24' : '#9ca3af'
                        }}>
                          {data.significance_score.toFixed(0)}
                        </div>
                      )}
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', color: '#cbd5e1', marginBottom: '4px' }}>
                      <span>Accuracy:</span>
                      <span style={{ fontWeight: 600 }}>{data.accuracy.toFixed(1)}%</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', color: '#cbd5e1', marginBottom: '4px' }}>
                      <span>Occurrences:</span>
                      <span>{data.count}</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', color: '#cbd5e1' }}>
                      <span>Error Rate:</span>
                      <span style={{ color: errorRate > 20 ? '#ef4444' : errorRate > 10 ? '#fbbf24' : '#10b981' }}>
                        {errorRate.toFixed(1)}%
                      </span>
                    </div>
                    {data.trend && data.trend_value !== undefined && (
                      <div style={{ 
                        fontSize: '11px', 
                        color: data.trend === 'improving' ? '#10b981' : data.trend === 'declining' ? '#ef4444' : '#9ca3af',
                        marginTop: '4px',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '4px'
                      }}>
                        {data.trend === 'improving' ? '↑' : data.trend === 'declining' ? '↓' : '→'}
                        <span>
                          {data.trend_value > 0 ? '+' : ''}{data.trend_value}% over last 10 games
                        </span>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          ) : (
            <p style={{ color: '#9ca3af', fontSize: '12px' }}>No data</p>
          )}
          
          <h4 style={{ margin: '20px 0 12px 0', fontSize: '14px', fontWeight: 600, color: '#fbbf24' }}>
            Tags Lost - Lowest Accuracy
          </h4>
          {lowestLost.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {lowestLost.map(({ tag, ...data }) => {
                const errorRate = data.count > 0 
                  ? ((data.blunders + data.mistakes + data.inaccuracies) / data.count * 100)
                  : 0;
                
                return (
                  <div key={tag} style={{
                    padding: '12px',
                    background: 'rgba(251, 191, 36, 0.1)',
                    borderRadius: '6px',
                    border: '1px solid rgba(251, 191, 36, 0.2)'
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                      <div style={{ fontSize: '13px', fontWeight: 600, color: '#fca5a5' }}>
                        {formatTagName(tag)}
                      </div>
                      {data.significance_score !== undefined && (
                        <div style={{
                          padding: '2px 6px',
                          borderRadius: '3px',
                          fontSize: '10px',
                          fontWeight: 600,
                          background: data.significance_score >= 70 ? 'rgba(16, 185, 129, 0.2)' : 
                                     data.significance_score >= 40 ? 'rgba(251, 191, 36, 0.2)' : 
                                     'rgba(107, 114, 128, 0.2)',
                          color: data.significance_score >= 70 ? '#10b981' : 
                                 data.significance_score >= 40 ? '#fbbf24' : '#9ca3af'
                        }}>
                          {data.significance_score.toFixed(0)}
                        </div>
                      )}
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', color: '#cbd5e1', marginBottom: '4px' }}>
                      <span>Accuracy:</span>
                      <span style={{ fontWeight: 600 }}>{data.accuracy.toFixed(1)}%</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', color: '#cbd5e1', marginBottom: '4px' }}>
                      <span>Occurrences:</span>
                      <span>{data.count}</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', color: '#cbd5e1' }}>
                      <span>Error Rate:</span>
                      <span style={{ color: errorRate > 20 ? '#ef4444' : errorRate > 10 ? '#fbbf24' : '#10b981' }}>
                        {errorRate.toFixed(1)}%
                      </span>
                    </div>
                    {data.trend && data.trend_value !== undefined && (
                      <div style={{ 
                        fontSize: '11px', 
                        color: data.trend === 'improving' ? '#10b981' : data.trend === 'declining' ? '#ef4444' : '#9ca3af',
                        marginTop: '4px',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '4px'
                      }}>
                        {data.trend === 'improving' ? '↑' : data.trend === 'declining' ? '↓' : '→'}
                        <span>
                          {data.trend_value > 0 ? '+' : ''}{data.trend_value}% over last 10 games
                        </span>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          ) : (
            <p style={{ color: '#9ca3af', fontSize: '12px' }}>No data</p>
          )}
        </div>
      </div>
    </ExpandableAnalyticsCard>
  );
}

