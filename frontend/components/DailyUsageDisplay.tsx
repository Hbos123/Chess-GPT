"use client";

import { useState, useEffect } from 'react';
import { getBackendBase } from '@/lib/backendBase';
import { useAuth } from '@/contexts/AuthContext';

interface DailyUsageDisplayProps {
  compact?: boolean;
}

export default function DailyUsageDisplay({ compact = false }: DailyUsageDisplayProps) {
  const { user } = useAuth();
  const [usage, setUsage] = useState<{
    messages?: { used: number; limit: number; remaining?: number };
    tokens?: { used: number; limit: number };
    gameReviews?: { used: number; limit: number | string; remaining?: number | string };
    lessons?: { used: number; limit: number | string; remaining?: number | string };
  } | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchUsage = async () => {
      try {
        const response = await fetch(`${getBackendBase()}/check_limits`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            user_id: user?.id || null,
            estimated_tokens: 0, // Just get current usage, don't check limits
            message_count: 0
          })
        });

        if (response.ok) {
          const data = await response.json();
          if (data.info) {
            const messages = data.info.messages;
            const messagesWithRemaining = messages ? {
              ...messages,
              remaining: messages.limit - messages.used
            } : undefined;
            
            setUsage({
              messages: messagesWithRemaining,
              tokens: data.info.tokens,
              gameReviews: data.info.game_reviews,
              lessons: data.info.lessons
            });
          }
        }
      } catch (err) {
        console.error('Failed to fetch usage:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchUsage();
    // Refresh every 30 seconds
    const interval = setInterval(fetchUsage, 30000);
    return () => clearInterval(interval);
  }, [user?.id]);

  if (loading) {
    return <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Loading...</div>;
  }

  if (!usage) {
    return null;
  }

  const getPercentage = (used: number, limit: number) => {
    if (limit === 0) return 0;
    return Math.min((used / limit) * 100, 100);
  };

  const getColor = (used: number, limit: number) => {
    const ratio = limit > 0 ? used / limit : 0;
    if (ratio >= 0.9) return '#ef4444'; // red
    if (ratio >= 0.7) return '#f59e0b'; // orange
    return '#10b981'; // green
  };

  if (compact) {
    return (
      <div style={{ 
        padding: '8px 12px',
        borderTop: '1px solid var(--border-color)',
        fontSize: '12px',
        color: 'var(--text-secondary)'
      }}>
        <div style={{ marginBottom: '6px', fontWeight: 600, color: 'var(--text-primary)' }}>
          Daily Usage
        </div>
        {usage.tokens && (
          <div style={{ marginBottom: '4px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '2px' }}>
              <span>Tokens:</span>
              <strong>{usage.tokens.used.toLocaleString()}/{usage.tokens.limit.toLocaleString()}</strong>
            </div>
            <div style={{
              width: '100%',
              height: '4px',
              backgroundColor: 'var(--bg-secondary)',
              borderRadius: '2px',
              overflow: 'hidden'
            }}>
              <div style={{
                height: '100%',
                width: `${getPercentage(usage.tokens.used, usage.tokens.limit)}%`,
                backgroundColor: getColor(usage.tokens.used, usage.tokens.limit),
                transition: 'width 0.2s ease'
              }} />
            </div>
          </div>
        )}
        {usage.gameReviews && (
          <div style={{ marginBottom: '4px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '2px' }}>
              <span>Game Reviews:</span>
              <strong>
                {usage.gameReviews.remaining === "unlimited" 
                  ? "Unlimited" 
                  : typeof usage.gameReviews.remaining === "number" 
                    ? `${usage.gameReviews.remaining} available`
                    : `${usage.gameReviews.used}/${usage.gameReviews.limit}`}
              </strong>
            </div>
            {usage.gameReviews.remaining !== "unlimited" && typeof usage.gameReviews.limit === "number" && (
              <div style={{
                width: '100%',
                height: '4px',
                backgroundColor: 'var(--bg-secondary)',
                borderRadius: '2px',
                overflow: 'hidden'
              }}>
                <div style={{
                  height: '100%',
                  width: `${getPercentage(usage.gameReviews.used, usage.gameReviews.limit)}%`,
                  backgroundColor: getColor(usage.gameReviews.used, usage.gameReviews.limit),
                  transition: 'width 0.2s ease'
                }} />
              </div>
            )}
          </div>
        )}
        {usage.lessons && (
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '2px' }}>
              <span>Lessons:</span>
              <strong>
                {usage.lessons.remaining === "unlimited" 
                  ? "Unlimited" 
                  : typeof usage.lessons.remaining === "number" 
                    ? `${usage.lessons.remaining} available`
                    : `${usage.lessons.used}/${usage.lessons.limit}`}
              </strong>
            </div>
            {usage.lessons.remaining !== "unlimited" && typeof usage.lessons.limit === "number" && (
              <div style={{
                width: '100%',
                height: '4px',
                backgroundColor: 'var(--bg-secondary)',
                borderRadius: '2px',
                overflow: 'hidden'
              }}>
                <div style={{
                  height: '100%',
                  width: `${getPercentage(usage.lessons.used, usage.lessons.limit)}%`,
                  backgroundColor: getColor(usage.lessons.used, usage.lessons.limit),
                  transition: 'width 0.2s ease'
                }} />
              </div>
            )}
          </div>
        )}
      </div>
    );
  }

  // Full version for ProfileDashboard
  return (
    <div style={{
      padding: '16px',
      backgroundColor: 'var(--bg-secondary)',
      borderRadius: '8px',
      marginBottom: '16px'
    }}>
      <h3 style={{ margin: '0 0 12px 0', fontSize: '16px', fontWeight: 600 }}>
        Daily Usage
      </h3>
      {usage.tokens && (
        <div style={{ marginBottom: '12px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px', fontSize: '14px' }}>
            <span>Tokens</span>
            <strong>{usage.tokens.used.toLocaleString()}/{usage.tokens.limit.toLocaleString()}</strong>
          </div>
          <div style={{
            width: '100%',
            height: '6px',
            backgroundColor: 'var(--bg-primary)',
            borderRadius: '3px',
            overflow: 'hidden'
          }}>
            <div style={{
              height: '100%',
              width: `${getPercentage(usage.tokens.used, usage.tokens.limit)}%`,
              backgroundColor: getColor(usage.tokens.used, usage.tokens.limit),
              transition: 'width 0.2s ease'
            }} />
          </div>
        </div>
      )}
      {usage.gameReviews && (
        <div style={{ marginBottom: '12px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px', fontSize: '14px' }}>
            <span>Game Reviews</span>
            <strong>
              {usage.gameReviews.remaining === "unlimited" 
                ? "Unlimited" 
                : typeof usage.gameReviews.remaining === "number" 
                  ? `${usage.gameReviews.remaining} available`
                  : `${usage.gameReviews.used}/${usage.gameReviews.limit}`}
            </strong>
          </div>
          {usage.gameReviews.remaining !== "unlimited" && typeof usage.gameReviews.limit === "number" && (
            <div style={{
              width: '100%',
              height: '6px',
              backgroundColor: 'var(--bg-primary)',
              borderRadius: '3px',
              overflow: 'hidden'
            }}>
              <div style={{
                height: '100%',
                width: `${getPercentage(usage.gameReviews.used, usage.gameReviews.limit)}%`,
                backgroundColor: getColor(usage.gameReviews.used, usage.gameReviews.limit),
                transition: 'width 0.2s ease'
              }} />
            </div>
          )}
        </div>
      )}
      {usage.lessons && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px', fontSize: '14px' }}>
            <span>Lessons</span>
            <strong>
              {usage.lessons.remaining === "unlimited" 
                ? "Unlimited" 
                : typeof usage.lessons.remaining === "number" 
                  ? `${usage.lessons.remaining} available`
                  : `${usage.lessons.used}/${usage.lessons.limit}`}
            </strong>
          </div>
          {usage.lessons.remaining !== "unlimited" && typeof usage.lessons.limit === "number" && (
            <div style={{
              width: '100%',
              height: '6px',
              backgroundColor: 'var(--bg-primary)',
              borderRadius: '3px',
              overflow: 'hidden'
            }}>
              <div style={{
                height: '100%',
                width: `${getPercentage(usage.lessons.used, usage.lessons.limit)}%`,
                backgroundColor: getColor(usage.lessons.used, usage.lessons.limit),
                transition: 'width 0.2s ease'
              }} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
