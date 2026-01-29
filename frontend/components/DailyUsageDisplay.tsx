"use client";

import { useState, useEffect, useRef } from 'react';
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
  
  // Client-side cache to avoid redundant state updates
  const lastFetchedRef = useRef<string | null>(null);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  const isVisibleRef = useRef(true);

  useEffect(() => {
    const fetchUsage = async () => {
      // Skip if tab is hidden (Page Visibility API)
      if (!isVisibleRef.current) {
        return;
      }

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
            
            const newUsage = {
              messages: messagesWithRemaining,
              tokens: data.info.tokens,
              gameReviews: data.info.game_reviews,
              lessons: data.info.lessons
            };
            
            // Client-side cache: only update if data changed
            const usageKey = JSON.stringify(newUsage);
            if (usageKey !== lastFetchedRef.current) {
              lastFetchedRef.current = usageKey;
              setUsage(newUsage);
            }
          }
        } else if (response.status === 429) {
          // Rate limit exceeded - parse error info to show usage
          try {
            const errorData = await response.json();
            if (errorData.info) {
              const messages = errorData.info.messages;
              const messagesWithRemaining = messages ? {
                ...messages,
                remaining: 0 // No remaining when limit exceeded
              } : undefined;
              
              const newUsage = {
                messages: messagesWithRemaining,
                tokens: errorData.info.tokens,
                gameReviews: errorData.info.game_reviews,
                lessons: errorData.info.lessons
              };
              
              // Client-side cache: only update if data changed
              const usageKey = JSON.stringify(newUsage);
              if (usageKey !== lastFetchedRef.current) {
                lastFetchedRef.current = usageKey;
                setUsage(newUsage);
              }
            }
          } catch (parseErr) {
            console.warn('Failed to parse 429 error response:', parseErr);
          }
        }
      } catch (err) {
        console.error('Failed to fetch usage:', err);
        // Don't set loading to false on network errors - keep showing last known state
        // setLoading(false);
      } finally {
        setLoading(false);
      }
    };

    // Initial fetch
    fetchUsage();
    
    // Page Visibility API: pause polling when tab is hidden
    const handleVisibilityChange = () => {
      isVisibleRef.current = !document.hidden;
      if (!document.hidden) {
        // Tab became visible - fetch immediately
        fetchUsage();
      }
    };
    
    document.addEventListener('visibilitychange', handleVisibilityChange);
    
    // Refresh every 60 seconds (reduced from 30s to minimize queries)
    intervalRef.current = setInterval(fetchUsage, 60000);
    
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
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
