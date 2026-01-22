"use client";

import { useState } from "react";
import TrendChart from "./TrendChart";

interface ExpandableAnalyticsCardProps {
  title: string;
  children: React.ReactNode;
  significanceScore?: number;
  trendData?: {
    dates: string[];
    series: Array<{
      name: string;
      data: (number | null)[];
      color: string;
    }>;
    baseline?: number;
  };
  expandedContent?: React.ReactNode;
  hideControls?: boolean;
}

export default function ExpandableAnalyticsCard({ 
  title, 
  children, 
  significanceScore,
  trendData,
  expandedContent,
  hideControls = false
}: ExpandableAnalyticsCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  
  const getSignificanceBadgeStyle = (score: number) => {
    if (score >= 70) {
      return {
        background: 'rgba(16, 185, 129, 0.2)',
        color: '#10b981',
        borderColor: 'rgba(16, 185, 129, 0.3)'
      };
    } else if (score >= 40) {
      return {
        background: 'rgba(251, 191, 36, 0.2)',
        color: '#fbbf24',
        borderColor: 'rgba(251, 191, 36, 0.3)'
      };
    } else {
      return {
        background: 'rgba(107, 114, 128, 0.2)',
        color: '#9ca3af',
        borderColor: 'rgba(107, 114, 128, 0.3)'
      };
    }
  };
  
  return (
    <div style={{
      padding: '20px',
      background: '#1e3a5f',
      borderRadius: '8px',
      border: '1px solid rgba(147, 197, 253, 0.2)',
      marginBottom: '20px'
    }}>
      <div style={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'center', 
        marginBottom: '16px' 
      }}>
        <h3 style={{ 
          margin: 0, 
          fontSize: '18px', 
          fontWeight: 600, 
          color: '#e0e7ff' 
        }}>
          {title}
        </h3>
        {!hideControls && (
          <div style={{ 
            display: 'flex', 
            gap: '12px', 
            alignItems: 'center' 
          }}>
            {significanceScore !== undefined && (
              <div style={{
                padding: '4px 8px',
                borderRadius: '4px',
                fontSize: '12px',
                fontWeight: 600,
                border: '1px solid',
                ...getSignificanceBadgeStyle(significanceScore)
              }}>
                Significance: {significanceScore.toFixed(0)}
              </div>
            )}
            {(trendData || expandedContent) && (
              <button
                onClick={() => setIsExpanded(!isExpanded)}
                style={{
                  padding: '6px 12px',
                  background: isExpanded ? '#3b82f6' : 'rgba(59, 130, 246, 0.2)',
                  color: '#e0e7ff',
                  border: '1px solid rgba(147, 197, 253, 0.3)',
                  borderRadius: '6px',
                  cursor: 'pointer',
                  fontSize: '13px',
                  fontWeight: 600,
                  transition: 'all 0.2s'
                }}
              >
                {isExpanded ? '▼ Collapse' : '▶ Expand'}
              </button>
            )}
          </div>
        )}
      </div>
      
      {children}
      
      {isExpanded && (
        <div style={{
          marginTop: '20px',
          padding: '16px',
          background: 'rgba(0, 0, 0, 0.2)',
          borderRadius: '6px',
          border: '1px solid rgba(147, 197, 253, 0.1)'
        }}>
          {expandedContent || (
            <div>
              <h4 style={{ 
                margin: '0 0 12px 0', 
                fontSize: '14px', 
                fontWeight: 600, 
                color: '#93c5fd' 
              }}>
                Detailed Trends & Patterns
              </h4>
              {trendData && (
                <TrendChart 
                  dates={trendData.dates}
                  series={trendData.series}
                  baseline={trendData.baseline}
                  height={200}
                  showLegend={trendData.series.length > 1}
                />
              )}
              {!trendData && (
                <p style={{ color: '#9ca3af', fontSize: '12px' }}>
                  No trend data available for this metric.
                </p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

