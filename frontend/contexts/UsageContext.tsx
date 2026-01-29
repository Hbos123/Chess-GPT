"use client";

import { createContext, useContext, useEffect, useState, useCallback, useRef } from 'react';
import { supabase } from '@/lib/supabase';
import { useAuth } from './AuthContext';
import { getBackendBase } from '@/lib/backendBase';

interface UsageInfo {
  // Message limits are display-only (token-based enforcement). Backend may return "unlimited".
  messages: { used: number; limit: number | string; remaining: number | string };
  tokens: { used: number; limit: number; remaining: number };
  gameReviews: { used: number; limit: number | string; remaining: number | string };
  lessons: { used: number; limit: number | string; remaining: number | string };
  tier_id: string;
}

interface UsageContextType {
  usage: UsageInfo | null;
  loading: boolean;
  checkCanSendMessage: (estimatedTokens: number) => boolean;
  deductTokens: (tokens: number, messageCount?: number) => Promise<boolean>; // Returns true if successful, false if limit exceeded
  refreshUsage: () => Promise<void>;
}

const UsageContext = createContext<UsageContextType>({
  usage: null,
  loading: true,
  checkCanSendMessage: () => false,
  deductTokens: async () => false,
  refreshUsage: async () => {}
});

export const useUsage = () => {
  const context = useContext(UsageContext);
  if (!context) {
    throw new Error('useUsage must be used within UsageProvider');
  }
  return context;
};

export function UsageProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const [usage, setUsage] = useState<UsageInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const channelRef = useRef<any>(null);

  // Fetch usage from backend
  const fetchUsage = useCallback(async () => {
    try {
      const response = await fetch(`${getBackendBase()}/check_limits`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: user?.id || null,
          estimated_tokens: 0,
          message_count: 0
        })
      });

      if (response.ok) {
        const data = await response.json();
        
        if (data.info) {
          const messages = data.info.messages || {};
          const tokens = data.info.tokens || {};
          const gameReviews = data.info.game_reviews || {};
          const lessons = data.info.lessons || {};
          
          setUsage({
            messages: {
              used: messages.used ?? 0,
              limit: messages.limit ?? 'unlimited',
              remaining: messages.remaining ?? 'unlimited'
            },
            tokens: {
              used: tokens.used ?? 0,
              limit: tokens.limit ?? 0,
              remaining: Math.max(0, (tokens.limit ?? 0) - (tokens.used ?? 0))
            },
            gameReviews: {
              used: gameReviews.used ?? 0,
              limit: gameReviews.limit ?? 0,
              remaining: typeof gameReviews.remaining === 'number' 
                ? gameReviews.remaining 
                : (gameReviews.limit === 'unlimited' ? 'unlimited' : Math.max(0, (gameReviews.limit ?? 0) - (gameReviews.used ?? 0)))
            },
            lessons: {
              used: lessons.used ?? 0,
              limit: lessons.limit ?? 0,
              remaining: typeof lessons.remaining === 'number'
                ? lessons.remaining
                : (lessons.limit === 'unlimited' ? 'unlimited' : Math.max(0, (lessons.limit ?? 0) - (lessons.used ?? 0)))
            },
            tier_id: data.info.tier_id || 'unpaid'
          });
        } else {
          console.warn('[UsageContext] No info in response:', data);
        }
      } else if (response.status === 429) {
        // Rate limit exceeded - parse error info to show usage
        try {
          const errorData = await response.json();
          
          if (errorData.info) {
            const messages = errorData.info.messages || {};
            const tokens = errorData.info.tokens || {};
            const gameReviews = errorData.info.game_reviews || {};
            const lessons = errorData.info.lessons || {};
            const tier_id = errorData.info.tier_id || 'unpaid';
            const tier = errorData.info.tier || {};
            
            setUsage({
              messages: {
                used: messages.used ?? 0,
                limit: messages.limit ?? 'unlimited',
                remaining: messages.remaining ?? 'unlimited'
              },
              tokens: {
                used: tokens.used ?? 0,
                limit: tokens.limit ?? tier.daily_tokens ?? 15000,
                remaining: tokens.remaining ?? Math.max(0, (tokens.limit ?? tier.daily_tokens ?? 15000) - (tokens.used ?? 0))
              },
              gameReviews: {
                used: gameReviews.used ?? 0,
                limit: gameReviews.limit ?? tier.max_game_reviews_per_day ?? 0,
                remaining: typeof gameReviews.remaining === 'number' 
                  ? gameReviews.remaining 
                  : (gameReviews.limit === 'unlimited' ? 'unlimited' : Math.max(0, (gameReviews.limit ?? tier.max_game_reviews_per_day ?? 0) - (gameReviews.used ?? 0)))
              },
              lessons: {
                used: lessons.used ?? 0,
                limit: lessons.limit ?? tier.max_lessons_per_day ?? 0,
                remaining: typeof lessons.remaining === 'number'
                  ? lessons.remaining
                  : (lessons.limit === 'unlimited' ? 'unlimited' : Math.max(0, (lessons.limit ?? tier.max_lessons_per_day ?? 0) - (lessons.used ?? 0)))
              },
              tier_id: tier_id
            });
          } else {
            // ignore
          }
        } catch (parseErr) {
          // ignore
        }
      }
    } catch (error) {
      console.error('Failed to fetch usage:', error);
    } finally {
      setLoading(false);
    }
  }, [user?.id]);

  // Subscribe to Supabase realtime for daily_usage changes
  useEffect(() => {
    // Always fetch usage (anon users are IP-based, signed-in users are user_id-based)
    fetchUsage();

    if (!user?.id || !supabase) {
      // Clean up subscription if user logs out
      if (channelRef.current) {
        supabase.removeChannel(channelRef.current);
        channelRef.current = null;
      }
      return;
    }

    // Subscribe to daily_usage table changes
    const channel = supabase
      .channel(`daily_usage:${user.id}`)
      .on(
        'postgres_changes',
        {
          event: '*', // INSERT, UPDATE, DELETE
          schema: 'public',
          table: 'daily_usage',
          filter: `user_id=eq.${user.id}`
        },
        (payload: any) => {
          // Refresh usage when database changes (syncs across tabs/devices)
          fetchUsage();
        }
      )
      .subscribe();

    channelRef.current = channel;

    return () => {
      if (channelRef.current) {
        supabase.removeChannel(channelRef.current);
        channelRef.current = null;
      }
    };
  }, [user?.id, fetchUsage]);

  // Check if user can send message (local check only - instant)
  const checkCanSendMessage = useCallback((estimatedTokens: number): boolean => {
    if (!usage) return false;

    // Enforce message limit only when backend returns a numeric remaining
    if (typeof usage.messages.remaining === 'number' && usage.messages.remaining <= 0) {
      return false;
    }

    // Check token limit
    if (usage.tokens.remaining < estimatedTokens) return false;
    
    return true;
  }, [usage]);

  // Deduct tokens (call backend, update local state)
  const deductTokens = useCallback(async (tokens: number, messageCount: number = 1): Promise<boolean> => {
    if (!usage) return false;
    
    // Local check first (instant feedback)
    if (usage.tokens.remaining < tokens) {
      return false;
    }

    try {
      // Backend will deduct and return updated usage
      const response = await fetch(`${getBackendBase()}/deduct_usage`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: user?.id || null,
          tokens: tokens,
          message_count: messageCount
        })
      });

      if (response.ok) {
        const data = await response.json();
        // Update local state with backend response
        if (data.usage) {
          setUsage(data.usage);
        }
        return true;
      } else if (response.status === 429) {
        // Limit exceeded - refresh usage to get latest
        await fetchUsage();
        return false;
      }
      return false;
    } catch (error) {
      console.error('Failed to deduct tokens:', error);
      return false;
    }
  }, [user?.id, usage, fetchUsage]);

  return (
    <UsageContext.Provider value={{
      usage,
      loading,
      checkCanSendMessage,
      deductTokens,
      refreshUsage: fetchUsage
    }}>
      {children}
    </UsageContext.Provider>
  );
}
