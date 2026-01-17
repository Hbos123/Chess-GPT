"use client";

import ExpandableAnalyticsCard from "./ExpandableAnalyticsCard";

interface PieceAccuracyCardProps {
  pieceData: {
    aggregate?: {
      [piece: string]: { accuracy: number; count: number };
    };
    per_game?: Array<{
      game_id: string;
      pieces: { [piece: string]: { accuracy: number; count: number } };
    }>;
  };
}

export default function PieceAccuracyCard({ pieceData }: PieceAccuracyCardProps) {
  const aggregate = pieceData?.aggregate || {};
  const pieces = ["Pawn", "Knight", "Bishop", "Rook", "Queen", "King"];
  
  // Sort pieces by accuracy (highest first)
  const sortedPieces = pieces
    .map(piece => ({
      name: piece,
      data: aggregate[piece] || { accuracy: 0, count: 0 }
    }))
    .filter(p => p.data.count > 0)
    .sort((a, b) => b.data.accuracy - a.data.accuracy);

  if (sortedPieces.length === 0) {
    return (
      <ExpandableAnalyticsCard title="Piece Accuracy">
        <p style={{ color: '#cbd5e1', fontSize: '14px' }}>No piece accuracy data available yet.</p>
      </ExpandableAnalyticsCard>
    );
  }

  const bestPiece = sortedPieces[0];
  const worstPiece = sortedPieces[sortedPieces.length - 1];
  
  // Calculate overall significance score
  const avgAccuracy = sortedPieces.length > 0
    ? sortedPieces.reduce((sum, p) => sum + p.data.accuracy, 0) / sortedPieces.length
    : 75;
  
  const calculateSignificance = (accuracy: number, count: number) => {
    const frequencyFactor = Math.min(1.0, Math.log(count + 1) / Math.log(200));
    const deviationFactor = Math.min(1.0, Math.abs(accuracy - avgAccuracy) / 25.0);
    return Math.round((frequencyFactor * 0.4 + deviationFactor * 0.6) * 100);
  };
  
  const overallSignificance = sortedPieces.length > 0
    ? sortedPieces.reduce((sum, p) => sum + calculateSignificance(p.data.accuracy, p.data.count), 0) / sortedPieces.length
    : undefined;
  
  // Build trend data from per_game data if available
  const buildTrendData = () => {
    if (!pieceData.per_game || pieceData.per_game.length === 0) return undefined;
    
    const piecesToTrack = sortedPieces.slice(0, 5).map(p => p.name);
    const seriesMap = new Map<string, { name: string; data: number[]; color: string }>();
    
    piecesToTrack.forEach(pieceName => {
      const piece = sortedPieces.find(p => p.name === pieceName);
      if (piece) {
        const color = piece.data.accuracy >= 80 ? '#10b981' : piece.data.accuracy >= 70 ? '#fbbf24' : '#ef4444';
        seriesMap.set(pieceName, {
          name: pieceName,
          data: [],
          color
        });
      }
    });
    
    pieceData.per_game.forEach(game => {
      piecesToTrack.forEach(pieceName => {
        const series = seriesMap.get(pieceName);
        if (series && game.pieces[pieceName]) {
          series.data.push(game.pieces[pieceName].accuracy);
        } else if (series) {
          series.data.push(null);
        }
      });
    });
    
    return {
      dates: pieceData.per_game.map((_, i) => `Game ${i + 1}`),
      series: Array.from(seriesMap.values()),
      baseline: avgAccuracy
    };
  };
  
  const trendData = buildTrendData();

  return (
    <ExpandableAnalyticsCard 
      title="Piece Accuracy"
      significanceScore={overallSignificance}
      trendData={trendData}
    >
      
      {/* Best and Worst Highlights */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '20px' }}>
        <div style={{
          padding: '12px',
          background: 'rgba(16, 185, 129, 0.1)',
          borderRadius: '6px',
          border: '1px solid rgba(16, 185, 129, 0.3)'
        }}>
          <div style={{ fontSize: '12px', color: '#6ee7b7', marginBottom: '4px' }}>Best</div>
          <div style={{ fontSize: '20px', fontWeight: 700, color: '#10b981' }}>
            {bestPiece.name}
          </div>
          <div style={{ fontSize: '16px', color: '#d1fae5' }}>
            {bestPiece.data.accuracy.toFixed(1)}%
          </div>
          <div style={{ fontSize: '11px', color: '#9ca3af', marginTop: '4px' }}>
            {bestPiece.data.count} moves
          </div>
        </div>
        
        <div style={{
          padding: '12px',
          background: 'rgba(239, 68, 68, 0.1)',
          borderRadius: '6px',
          border: '1px solid rgba(239, 68, 68, 0.3)'
        }}>
          <div style={{ fontSize: '12px', color: '#fca5a5', marginBottom: '4px' }}>Needs Work</div>
          <div style={{ fontSize: '20px', fontWeight: 700, color: '#ef4444' }}>
            {worstPiece.name}
          </div>
          <div style={{ fontSize: '16px', color: '#fee2e2' }}>
            {worstPiece.data.accuracy.toFixed(1)}%
          </div>
          <div style={{ fontSize: '11px', color: '#9ca3af', marginTop: '4px' }}>
            {worstPiece.data.count} moves
          </div>
        </div>
      </div>

      {/* All Pieces Breakdown */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: '12px' }}>
        {sortedPieces.map((piece) => {
          const percentage = piece.data.accuracy;
          const color = percentage >= 80 ? '#10b981' : percentage >= 70 ? '#fbbf24' : '#ef4444';
          
          return (
            <div key={piece.name} style={{
              padding: '12px',
              background: 'rgba(59, 130, 246, 0.1)',
              borderRadius: '6px',
              border: `1px solid ${color}40`,
              textAlign: 'center'
            }}>
              <div style={{ fontSize: '14px', fontWeight: 600, color: '#93c5fd', marginBottom: '8px' }}>
                {piece.name}
              </div>
              <div style={{ fontSize: '20px', fontWeight: 700, color, marginBottom: '4px' }}>
                {piece.data.accuracy.toFixed(1)}%
              </div>
              <div style={{ fontSize: '11px', color: '#9ca3af' }}>
                {piece.data.count} moves
              </div>
            </div>
          );
        })}
      </div>
    </ExpandableAnalyticsCard>
  );
}

