"use client";

import ExpandableAnalyticsCard from "./ExpandableAnalyticsCard";

interface PhasePerformanceCardProps {
  phaseAnalytics: {
    opening?: { accuracy: number; games_won: number; games_lost: number; games_drawn: number };
    middlegame?: { accuracy: number; games_won: number; games_lost: number; games_drawn: number };
    endgame?: { accuracy: number; games_won: number; games_lost: number; games_drawn: number };
  };
}

export default function PhasePerformanceCard({ phaseAnalytics }: PhasePerformanceCardProps) {
  const phases = [
    { key: "opening", label: "Opening", data: phaseAnalytics.opening },
    { key: "middlegame", label: "Middlegame", data: phaseAnalytics.middlegame },
    { key: "endgame", label: "Endgame", data: phaseAnalytics.endgame },
  ];
  
  const phasesWithData = phases.filter(p => p.data);
  
  // Calculate overall significance score
  const avgAccuracy = phasesWithData.length > 0
    ? phasesWithData.reduce((sum, p) => sum + (p.data?.accuracy || 0), 0) / phasesWithData.length
    : 75;
  
  const calculateSignificance = (accuracy: number, totalGames: number) => {
    const frequencyFactor = Math.min(1.0, Math.log(totalGames + 1) / Math.log(30));
    const deviationFactor = Math.min(1.0, Math.abs(accuracy - avgAccuracy) / 25.0);
    return Math.round((frequencyFactor * 0.4 + deviationFactor * 0.6) * 100);
  };
  
  const overallSignificance = phasesWithData.length > 0
    ? phasesWithData.reduce((sum, p) => {
        const totalGames = (p.data?.games_won || 0) + (p.data?.games_lost || 0) + (p.data?.games_drawn || 0);
        return sum + calculateSignificance(p.data?.accuracy || 0, totalGames);
      }, 0) / phasesWithData.length
    : undefined;
  
  // Build trend data
  const trendData = phasesWithData.length > 0 ? {
    dates: [] as string[],
    series: phasesWithData.map(p => ({
      name: p.label,
      data: [] as (number | null)[],
      color: (p.data?.accuracy || 0) >= 80 ? '#10b981' : (p.data?.accuracy || 0) >= 70 ? '#fbbf24' : '#ef4444'
    })),
    baseline: avgAccuracy
  } : undefined;

  return (
    <ExpandableAnalyticsCard 
      title="Phase Performance"
      significanceScore={overallSignificance}
      trendData={trendData}
    >
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
        {phases.map((phase) => {
          const data = phase.data;
          if (!data) return null;
          
          const totalGames = data.games_won + data.games_lost + data.games_drawn;
          const winRate = totalGames > 0 ? (data.games_won / totalGames) * 100 : 0;
          
          return (
            <div key={phase.key} style={{
              padding: '16px',
              background: 'rgba(59, 130, 246, 0.1)',
              borderRadius: '6px',
              border: '1px solid rgba(147, 197, 253, 0.1)'
            }}>
              <div style={{ fontSize: '14px', fontWeight: 600, color: '#93c5fd', marginBottom: '8px' }}>
                {phase.label}
              </div>
              <div style={{ fontSize: '24px', fontWeight: 700, color: '#e0e7ff', marginBottom: '4px' }}>
                {data.accuracy.toFixed(1)}%
              </div>
              <div style={{ fontSize: '12px', color: '#cbd5e1', marginBottom: '12px' }}>
                Accuracy
              </div>
              {totalGames > 0 && (
                <div style={{ fontSize: '12px', color: '#cbd5e1' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                    <span>Wins:</span>
                    <span style={{ color: '#10b981' }}>{data.games_won}</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                    <span>Losses:</span>
                    <span style={{ color: '#ef4444' }}>{data.games_lost}</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                    <span>Draws:</span>
                    <span style={{ color: '#fbbf24' }}>{data.games_drawn}</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '8px', paddingTop: '8px', borderTop: '1px solid rgba(147, 197, 253, 0.1)' }}>
                    <span>Win Rate:</span>
                    <span style={{ fontWeight: 600 }}>{winRate.toFixed(1)}%</span>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </ExpandableAnalyticsCard>
  );
}

