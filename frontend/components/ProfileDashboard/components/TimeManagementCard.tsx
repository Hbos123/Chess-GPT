"use client";

import ExpandableAnalyticsCard from "./ExpandableAnalyticsCard";

interface TimeManagementCardProps {
  timeBuckets: {
    [bucket: string]: { 
      accuracy: number; 
      count: number; 
      blunders: number; 
      mistakes: number;
      inaccuracies: number;
      blunder_rate: number;
      mistake_rate?: number;
      inaccuracy_rate?: number;
    };
  };
}

export default function TimeManagementCard({ timeBuckets }: TimeManagementCardProps) {
  // Define the 7 buckets in order
  const bucketOrder = [
    "<5s",
    "5-15s",
    "15-30s",
    "30s-1min",
    "1min-2min30",
    "2min30-5min",
    "5min+"
  ];

  const buckets = bucketOrder.map(bucket => ({
    name: bucket,
    data: timeBuckets[bucket] || { accuracy: 0, count: 0, blunders: 0, blunder_rate: 0 }
  })).filter(b => b.data.count > 0);

  if (buckets.length === 0) {
    return (
      <ExpandableAnalyticsCard title="Time Management Performance">
        <p style={{ color: '#cbd5e1', fontSize: '14px' }}>No time management data available yet.</p>
      </ExpandableAnalyticsCard>
    );
  }

  // Find best and worst buckets
  const bestBucket = buckets.reduce((best, curr) => 
    curr.data.accuracy > best.data.accuracy ? curr : best
  );
  const worstBucket = buckets.reduce((worst, curr) => 
    curr.data.accuracy < worst.data.accuracy ? curr : worst
  );
  
  // Calculate overall significance score (based on count and accuracy deviation)
  const avgAccuracy = buckets.length > 0
    ? buckets.reduce((sum, b) => sum + b.data.accuracy, 0) / buckets.length
    : 75;
  
  const calculateSignificance = (accuracy: number, count: number) => {
    const frequencyFactor = Math.min(1.0, Math.log(count + 1) / Math.log(50));
    const deviationFactor = Math.min(1.0, Math.abs(accuracy - avgAccuracy) / 25.0);
    return Math.round((frequencyFactor * 0.4 + deviationFactor * 0.6) * 100);
  };
  
  const overallSignificance = buckets.length > 0
    ? buckets.reduce((sum, b) => sum + calculateSignificance(b.data.accuracy, b.data.count), 0) / buckets.length
    : undefined;
  
  // Build trend data (placeholder - would need backend support for day intervals)
  const trendData = buckets.length > 0 ? {
    dates: [] as string[],
    series: buckets.slice(0, 5).map(b => ({
      name: b.name,
      data: [] as (number | null)[],
      color: b.data.accuracy >= 80 ? '#10b981' : b.data.accuracy >= 70 ? '#fbbf24' : '#ef4444'
    })),
    baseline: avgAccuracy
  } : undefined;

  return (
    <ExpandableAnalyticsCard 
      title="Time Management Performance"
      significanceScore={overallSignificance}
      trendData={trendData}
    >
      
      {/* Best/Worst Highlights */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '20px' }}>
        <div style={{
          padding: '12px',
          background: 'rgba(16, 185, 129, 0.1)',
          borderRadius: '6px',
          border: '1px solid rgba(16, 185, 129, 0.3)'
        }}>
          <div style={{ fontSize: '12px', color: '#6ee7b7', marginBottom: '4px' }}>Best Time Range</div>
          <div style={{ fontSize: '18px', fontWeight: 700, color: '#10b981', marginBottom: '4px' }}>
            {bestBucket.name}
          </div>
          <div style={{ fontSize: '16px', color: '#d1fae5', marginBottom: '4px' }}>
            {bestBucket.data.accuracy.toFixed(1)}% accuracy
          </div>
          <div style={{ fontSize: '11px', color: '#9ca3af' }}>
            {bestBucket.data.count} moves • Blunders: {bestBucket.data.blunders} ({bestBucket.data.blunder_rate ? (bestBucket.data.blunder_rate * 100).toFixed(1) : '0.0'}%)
          </div>
        </div>
        
        <div style={{
          padding: '12px',
          background: 'rgba(239, 68, 68, 0.1)',
          borderRadius: '6px',
          border: '1px solid rgba(239, 68, 68, 0.3)'
        }}>
          <div style={{ fontSize: '12px', color: '#fca5a5', marginBottom: '4px' }}>Needs Improvement</div>
          <div style={{ fontSize: '18px', fontWeight: 700, color: '#ef4444', marginBottom: '4px' }}>
            {worstBucket.name}
          </div>
          <div style={{ fontSize: '16px', color: '#fee2e2', marginBottom: '4px' }}>
            {worstBucket.data.accuracy.toFixed(1)}% accuracy
          </div>
          <div style={{ fontSize: '11px', color: '#9ca3af' }}>
            {worstBucket.data.count} moves • Blunders: {worstBucket.data.blunders} ({worstBucket.data.blunder_rate ? (worstBucket.data.blunder_rate * 100).toFixed(1) : '0.0'}%)
          </div>
        </div>
      </div>

      {/* All Buckets Visualization */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
        {bucketOrder.map((bucketName) => {
          const bucket = buckets.find(b => b.name === bucketName);
          if (!bucket) return null;
          
          const data = bucket.data;
          const accuracyColor = data.accuracy >= 80 ? '#10b981' : data.accuracy >= 70 ? '#fbbf24' : '#ef4444';
          const blunderColor = data.blunder_rate <= 5 ? '#10b981' : data.blunder_rate <= 10 ? '#fbbf24' : '#ef4444';
          
          return (
            <div key={bucketName} style={{
              padding: '12px',
              background: 'rgba(59, 130, 246, 0.1)',
              borderRadius: '6px',
              border: '1px solid rgba(147, 197, 253, 0.2)'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <span style={{ fontSize: '14px', fontWeight: 600, color: '#93c5fd' }}>
                  {bucketName}
                </span>
                <span style={{ fontSize: '16px', fontWeight: 700, color: accuracyColor }}>
                  {data.accuracy.toFixed(1)}%
                </span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', fontSize: '12px', color: '#cbd5e1' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span>{data.count} moves</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap' }}>
                  <span>
                    Blunders: <span style={{ color: data.blunders > 0 ? '#ef4444' : '#9ca3af', fontWeight: 600 }}>
                      {data.blunders} ({(data.blunder_rate * 100).toFixed(1)}%)
                    </span>
                  </span>
                  {data.mistakes !== undefined && (
                    <span>
                      Mistakes: <span style={{ color: data.mistakes > 0 ? '#fbbf24' : '#9ca3af', fontWeight: 600 }}>
                        {data.mistakes} ({data.mistake_rate ? (data.mistake_rate * 100).toFixed(1) : '0.0'}%)
                      </span>
                    </span>
                  )}
                  {data.inaccuracies !== undefined && (
                    <span>
                      Inaccuracies: <span style={{ color: data.inaccuracies > 0 ? '#fbbf24' : '#9ca3af', fontWeight: 600 }}>
                        {data.inaccuracies} ({data.inaccuracy_rate ? (data.inaccuracy_rate * 100).toFixed(1) : '0.0'}%)
                      </span>
                    </span>
                  )}
                </div>
              </div>
              {/* Accuracy bar */}
              <div style={{
                width: '100%',
                height: '4px',
                background: 'rgba(0, 0, 0, 0.3)',
                borderRadius: '2px',
                marginTop: '8px',
                overflow: 'hidden'
              }}>
                <div style={{
                  width: `${Math.min(data.accuracy, 100)}%`,
                  height: '100%',
                  background: accuracyColor,
                  transition: 'width 0.3s ease'
                }} />
              </div>
            </div>
          );
        })}
      </div>
    </ExpandableAnalyticsCard>
  );
}

