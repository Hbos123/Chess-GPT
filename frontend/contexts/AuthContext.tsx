"use client";

import { createContext, useContext, useEffect, useState } from 'react';
import { clearSupabaseAuthStorage, supabase, getSession, getUser } from '@/lib/supabase';
import type { User, Session } from '@supabase/supabase-js';

interface AuthContextType {
  user: User | null;
  session: Session | null;
  loading: boolean;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  session: null,
  loading: true,
  signOut: async () => {}
});

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;
    let timeoutId: NodeJS.Timeout;

    const getProjectRef = (): string | null => {
      const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
      if (!url) return null;
      try {
        const host = new URL(url).host; // "<ref>.supabase.co"
        return host.split(".")[0] || null;
      } catch {
        return null;
      }
    };

    const readSessionFromLocalStorage = (): Session | null => {
      try {
        const ref = getProjectRef();
        if (!ref) return null;
        const key = `sb-${ref}-auth-token`;
        const raw = window.localStorage.getItem(key);
        if (!raw) return null;
        const parsed = JSON.parse(raw);
        if (!parsed || typeof parsed !== "object") return null;
        // supabase-js storage format is essentially a Session-like object
        if (!parsed.access_token || !parsed.user) return null;
        return parsed as Session;
      } catch {
        return null;
      }
    };

    // Set a timeout to ensure loading always resolves
    timeoutId = setTimeout(() => {
      if (isMounted) {
        console.warn('[AuthContext] Loading timeout - forcing loading to false');
        setLoading(false);
      }
    }, 5000); // 5 second timeout

    // Check if Supabase is configured first
    const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
    const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
    
    if (!supabaseUrl || !supabaseAnonKey || !supabase) {
      console.warn('[AuthContext] Supabase not configured - skipping auth check');
      if (isMounted) {
        clearTimeout(timeoutId);
        setLoading(false);
      }
      return;
    }

    // Failsafe: if supabase-js hangs during getSession(), still hydrate UI from localStorage.
    try {
      const local = readSessionFromLocalStorage();
      if (local && isMounted) {
        console.log("[AuthContext] Hydrated session from localStorage failsafe");
        setSession(local);
        setUser((local as any).user ?? null);
        // Don't end loading yet; we'll still try canonical getSession below.
      }
    } catch {
      // ignore
    }

    // Canonical session hydration
    const getSessionWithTimeout = async () => {
      const timeoutMs = 2500;
      return await Promise.race([
        supabase.auth.getSession(),
        new Promise<never>((_, reject) => setTimeout(() => reject(new Error(`getSession timed out after ${timeoutMs}ms`)), timeoutMs)),
      ]);
    };

    getSessionWithTimeout()
      .then(({ data: { session } }: any) => {
        if (!isMounted) return;
        clearTimeout(timeoutId);
        setSession(session);
        setUser(session?.user ?? null);
        setLoading(false);
      })
      .catch((error) => {
        if (!isMounted) return;
        clearTimeout(timeoutId);
        // If we already hydrated from localStorage, don't spam an "error" for a known SDK hang.
        const local = readSessionFromLocalStorage();
        if (local) {
          console.warn('[AuthContext] getSession failed/timed out; keeping localStorage session (SDK issue):', error);
          setSession((prev) => prev ?? local);
          setUser((prev) => prev ?? (local?.user ?? null));
        } else {
          console.error('[AuthContext] Error getting session (or timeout):', error);
          setSession(null);
          setUser(null);
        }
        setLoading(false);
      });

    // Listen for auth changes (only if supabase is configured)
    let subscription: { unsubscribe: () => void } | null = null;
    try {
      if (supabase) {
        const { data } = supabase.auth.onAuthStateChange((_event, session) => {
          if (isMounted) {
            clearTimeout(timeoutId);
            setSession(session);
            setUser(session?.user ?? null);
            setLoading(false);
          }
        });
        subscription = data.subscription;
      }
    } catch (error) {
      if (isMounted) {
        clearTimeout(timeoutId);
        console.error('[AuthContext] Error setting up auth state listener:', error);
        setLoading(false);
      }
    }

    return () => {
      isMounted = false;
      clearTimeout(timeoutId);
      if (subscription) {
        subscription.unsubscribe();
      }
    };
  }, []);

  const handleSignOut = async () => {
    // Supabase auth-js has been observed to hang in this repo's dev environment.
    // We therefore treat sign-out as "best effort" and always clear local storage.
    if (supabase) {
      try {
        const timeoutMs = 1500;
        await Promise.race([
          supabase.auth.signOut(),
          new Promise<never>((_, reject) =>
            setTimeout(() => reject(new Error(`supabase.auth.signOut timed out after ${timeoutMs}ms`)), timeoutMs)
          ),
        ]);
      } catch (error) {
        console.warn('Error signing out (continuing with local clear):', error);
      }
    }
    // Clear any persisted auth tokens/verifiers so our localStorage failsafe doesn't keep you "logged in".
    try {
      clearSupabaseAuthStorage();
    } catch (e) {
      console.warn("Failed to clear Supabase auth storage during sign out:", e);
    }
    setUser(null);
    setSession(null);
  };

  return (
    <AuthContext.Provider value={{ user, session, loading, signOut: handleSignOut }}>
      {children}
    </AuthContext.Provider>
  );
}

