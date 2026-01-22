import { createClient } from '@supabase/supabase-js';

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

// Validate environment variables
if (!supabaseUrl || !supabaseAnonKey) {
  console.warn('Missing Supabase environment variables. Authentication will not work.');
}

// Only create client if we have valid environment variables
// This prevents 404 errors from malformed requests
export const supabase = supabaseUrl && supabaseAnonKey
  ? createClient(supabaseUrl, supabaseAnonKey, {
      global: {
        fetch: async (input: RequestInfo | URL, init?: RequestInit) => {
          const url = typeof input === "string" ? input : (input instanceof URL ? input.toString() : (input as any)?.url);
          const method = init?.method ?? "GET";
          const startedAt = (typeof performance !== "undefined" && performance.now) ? performance.now() : Date.now();

          const isAuthTokenCall = typeof url === "string" && url.includes("/auth/v1/token");
          const isAuthCall = typeof url === "string" && url.includes("/auth/v1/");

          // Redact headers to avoid leaking tokens in logs.
          const safeHeaders: Record<string, string> = {};
          try {
            const h = init?.headers;
            if (h) {
              const entries: [string, string][] =
                h instanceof Headers
                  ? Array.from(h.entries())
                  : Array.isArray(h)
                    ? (h as any)
                    : Object.entries(h as Record<string, string>);
              for (const [k, v] of entries) {
                const key = String(k).toLowerCase();
                if (key === "authorization" || key.includes("apikey")) {
                  safeHeaders[k] = "<redacted>";
                } else {
                  safeHeaders[k] = String(v);
                }
              }
            }
          } catch {
            // ignore
          }

          if (isAuthCall) {
            console.log("[supabase.fetch] →", {
              method,
              url,
              isAuthTokenCall,
              headers: safeHeaders,
              hasBody: !!init?.body,
            });
          }

          try {
            const res = await fetch(input as any, init as any);
            const endedAt = (typeof performance !== "undefined" && performance.now) ? performance.now() : Date.now();
            if (isAuthCall) {
              console.log("[supabase.fetch] ←", {
                method,
                url,
                isAuthTokenCall,
                status: res.status,
                ok: res.ok,
                durationMs: Math.round(endedAt - startedAt),
              });
            }
            return res;
          } catch (e) {
            const endedAt = (typeof performance !== "undefined" && performance.now) ? performance.now() : Date.now();
            if (isAuthCall) {
              console.error("[supabase.fetch] ✕", {
                method,
                url,
                isAuthTokenCall,
                durationMs: Math.round(endedAt - startedAt),
                error: e,
              });
            }
            throw e;
          }
        },
      },
      auth: {
        persistSession: true,
        // In local dev we've repeatedly seen browser-level "Load failed" on the refresh_token call,
        // which then cascades into noisy errors and stuck UI. Prefer stability over background refresh.
        // (Tokens are still persisted; user can re-auth if needed.)
        autoRefreshToken:
          typeof window !== "undefined"
            ? (window.location.hostname !== "localhost" && window.location.hostname !== "127.0.0.1")
            : true,
        // IMPORTANT: disable auto URL processing to avoid double-processing / lock contention.
        // Our callback page calls exchangeCodeForSession explicitly.
        detectSessionInUrl: false,
        // Force PKCE so OAuth redirects back with ?code=... and the callback can use exchangeCodeForSession().
        flowType: "pkce",
      },
    })
  : null as any; // Type assertion for development - will fail gracefully

const oauthRedirect = () => `${window.location.origin}/auth/callback`;

function getSupabaseProjectRefFromUrl(url: string | undefined): string | null {
  if (!url) return null;
  // Typical: https://<ref>.supabase.co
  try {
    const host = new URL(url).host; // "<ref>.supabase.co"
    const first = host.split(".")[0];
    return first || null;
  } catch {
    return null;
  }
}

export function clearSupabaseAuthStorage() {
  // This is an in-app escape hatch for "auth storage corruption"/stuck locks.
  // It clears all Supabase auth keys for the current project ref.
  if (typeof window === "undefined") return;

  const ref = getSupabaseProjectRefFromUrl(process.env.NEXT_PUBLIC_SUPABASE_URL);
  const prefix = ref ? `sb-${ref}-` : "sb-";

  try {
    const keys = Object.keys(window.localStorage);
    for (const k of keys) {
      if (k.startsWith(prefix) || k === "supabase.auth.token") {
        window.localStorage.removeItem(k);
      }
    }
    // Also clear any Supabase cookies (best-effort; not all are readable from JS).
    // We at least force a hard reload to rebuild client state from a clean slate.
  } catch (e) {
    console.warn("[clearSupabaseAuthStorage] Failed to clear localStorage", e);
  }
}

// Helper to check if Supabase is configured
const isSupabaseConfigured = () => {
  if (!supabaseUrl || !supabaseAnonKey || !supabase) {
    console.warn('Supabase not configured. Authentication functions will not work.');
    return false;
  }
  return true;
};

// Auth helpers
export const signInWithGoogle = async () => {
  if (!isSupabaseConfigured()) {
    return { data: null, error: { message: 'Supabase not configured' } as any };
  }
  
  console.log("[signInWithGoogle] Starting OAuth flow...");
  console.log("[signInWithGoogle] Redirect URL:", oauthRedirect());
  
  const { data, error } = await supabase.auth.signInWithOAuth({
    provider: 'google',
    options: {
      redirectTo: oauthRedirect(),
    },
  });
  
  if (error) {
    console.error("[signInWithGoogle] signInWithOAuth error:", error);
    return { data: null, error };
  }
  
  if (data?.url) {
    console.log("[signInWithGoogle] Redirecting to:", data.url);
    window.location.href = data.url;
  } else {
    console.error("[signInWithGoogle] No redirect URL returned from signInWithOAuth");
    return { data: null, error: { message: 'No redirect URL received' } as any };
  }
  
  return { data, error };
};

export const signInWithApple = async () => {
  if (!isSupabaseConfigured()) {
    return { data: null, error: { message: 'Supabase not configured' } as any };
  }
  
  console.log("[signInWithApple] Starting OAuth flow...");
  console.log("[signInWithApple] Redirect URL:", oauthRedirect());
  
  const { data, error } = await supabase.auth.signInWithOAuth({
    provider: 'apple',
    options: {
      redirectTo: oauthRedirect(),
      queryParams: {
        response_mode: 'form_post',
      },
    },
  });
  
  if (error) {
    console.error("[signInWithApple] signInWithOAuth error:", error);
    return { data: null, error };
  }
  
  if (data?.url) {
    console.log("[signInWithApple] Redirecting to:", data.url);
    window.location.href = data.url;
  } else {
    console.error("[signInWithApple] No redirect URL returned from signInWithOAuth");
    return { data: null, error: { message: 'No redirect URL received' } as any };
  }
  
  return { data, error };
};

export const signInWithMagicLink = async (email: string) => {
  if (!isSupabaseConfigured()) {
    return { data: null, error: { message: 'Supabase not configured' } as any };
  }
  const { data, error } = await supabase.auth.signInWithOtp({
    email,
    options: {
      emailRedirectTo: oauthRedirect(),
    },
  });
  return { data, error };
};

export const signInWithPassword = async (email: string, password: string) => {
  if (!isSupabaseConfigured()) {
    return { data: null, error: { message: 'Supabase not configured' } as any };
  }
  const { data, error } = await supabase.auth.signInWithPassword({
    email,
    password,
  });
  return { data, error };
};

export const signUpWithPassword = async (email: string, password: string, username: string) => {
  if (!isSupabaseConfigured()) {
    return { data: null, error: { message: 'Supabase not configured' } as any };
  }
  const { data, error } = await supabase.auth.signUp({
    email,
    password,
    options: {
      data: {
        username,
        display_name: username,
      },
    },
  });
  return { data, error };
};

export const signOut = async () => {
  if (!isSupabaseConfigured()) {
    return { error: { message: 'Supabase not configured' } as any };
  }
  const { error } = await supabase.auth.signOut();
  return { error };
};

export const getSession = async () => {
  // If Supabase is not configured, return null immediately
  if (!supabaseUrl || !supabaseAnonKey || !supabase) {
    console.warn('Supabase not configured. Cannot get session.');
    return null;
  }

  try {
    const {
      data: { session },
      error,
    } = await supabase.auth.getSession();
    if (error) {
      console.error('Error getting session:', error);
      return null;
    }
    return session;
  } catch (error) {
    console.error('Exception getting session:', error);
    return null;
  }
};

export const getUser = async () => {
  // If Supabase is not configured, return null immediately
  if (!supabaseUrl || !supabaseAnonKey || !supabase) {
    console.warn('Supabase not configured. Cannot get user.');
    return null;
  }

  try {
    const {
      data: { user },
      error,
    } = await supabase.auth.getUser();
    if (error) {
      console.error('Error getting user:', error);
      return null;
    }
    return user;
  } catch (error) {
    console.error('Exception getting user:', error);
    return null;
  }
};
