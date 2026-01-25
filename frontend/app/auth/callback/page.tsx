"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { clearSupabaseAuthStorage, supabase } from "@/lib/supabase";
import type { AuthChangeEvent, Session } from "@supabase/supabase-js";

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL;
const SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

function AuthCallbackInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [status, setStatus] = useState<"pending" | "success" | "error">("pending");
  const [message, setMessage] = useState<string>("Completing sign in…");
  const [resetting, setResetting] = useState(false);

  useEffect(() => {
    console.log("[AuthCallback] useEffect triggered");
    let isMounted = true;
    let subscription: { unsubscribe: () => void } | null = null;

    console.log("[AuthCallback] Checking Supabase configuration...");
    console.log("[AuthCallback] SUPABASE_URL:", SUPABASE_URL ? "✓ Set" : "✗ Missing");
    console.log("[AuthCallback] SUPABASE_ANON_KEY:", SUPABASE_ANON_KEY ? "✓ Set" : "✗ Missing");
    console.log("[AuthCallback] supabase client:", supabase ? "✓ Available" : "✗ Missing");

    if (!SUPABASE_URL || !SUPABASE_ANON_KEY || !supabase) {
      console.error("[AuthCallback] Authentication not configured");
      setStatus("error");
      setMessage("Authentication is not configured.");
      return;
    }

    console.log("[AuthCallback] Checking URL parameters...");
    const errorDescription = searchParams.get("error_description");
    if (errorDescription) {
      console.error("[AuthCallback] Error description found:", errorDescription);
      setStatus("error");
      setMessage(errorDescription);
      return;
    }

    const code = searchParams.get("code");
    console.log("[AuthCallback] Code parameter:", code ? `✓ Found (${code.substring(0, 10)}...)` : "✗ Missing");
    
    // CHECK FOR CODE_VERIFIER IN LOCALSTORAGE (required for PKCE)
    console.log("[AuthCallback] Checking for code_verifier in localStorage...");
    const storageKeys = Object.keys(localStorage);
    const pkceKeys = storageKeys.filter(k => 
      k.toLowerCase().includes('pkce') || 
      k.toLowerCase().includes('code') || 
      k.toLowerCase().includes('verifier') ||
      k.includes('supabase')
    );
    console.log("[AuthCallback] PKCE-related localStorage keys found:", pkceKeys.length);
    pkceKeys.forEach(key => {
      const value = localStorage.getItem(key);
      console.log(`[AuthCallback] ${key}:`, value ? `${value.substring(0, 30)}...` : "null");
    });
    
    // Check Supabase's internal storage format
    if (SUPABASE_URL) {
      const supabaseHost = SUPABASE_URL.split('//')[1]?.split('.')[0];
      if (supabaseHost) {
        const supabaseStorageKey = `sb-${supabaseHost}-auth-token`;
        console.log("[AuthCallback] Checking Supabase storage key:", supabaseStorageKey);
        const supabaseStorage = localStorage.getItem(supabaseStorageKey);
        console.log("[AuthCallback] Supabase storage:", supabaseStorage ? "exists" : "missing");
        if (supabaseStorage) {
          try {
            const parsed = JSON.parse(supabaseStorage);
            console.log("[AuthCallback] Supabase storage contains:", Object.keys(parsed || {}));
          } catch (e) {
            console.log("[AuthCallback] Supabase storage is not JSON");
          }
        }
        
        // Check code_verifier format specifically
        const codeVerifierKey = `sb-${supabaseHost}-auth-token-code-verifier`;
        const codeVerifierRaw = localStorage.getItem(codeVerifierKey);
        console.log("[AuthCallback] Code verifier key:", codeVerifierKey);
        console.log("[AuthCallback] Code verifier raw value exists:", !!codeVerifierRaw);
        if (codeVerifierRaw) {
          console.log("[AuthCallback] Code verifier raw value length:", codeVerifierRaw.length);
          console.log("[AuthCallback] Code verifier raw value preview:", codeVerifierRaw.substring(0, 50) + "...");
          try {
            const parsed = JSON.parse(codeVerifierRaw);
            console.log("[AuthCallback] Code verifier is JSON-stringified, parsed length:", parsed?.length);
            console.log("[AuthCallback] Code verifier parsed preview:", parsed?.substring(0, 30) + "...");
          } catch (e) {
            console.log("[AuthCallback] Code verifier is not JSON (raw string)");
          }
        }
      }
    }
    
    if (!code) {
      console.error("[AuthCallback] No code parameter in URL");
      setStatus("error");
      setMessage("Missing authentication code. Please try signing in again.");
      return;
    }

    console.log("[AuthCallback] Setting up callback handler...");
    setStatus("pending");
    setMessage("Completing sign in…");

    const timeoutMs = 10000;
    const timeoutId = setTimeout(() => {
      if (!isMounted) return;
      console.error("[AuthCallback] Timeout reached after", timeoutMs, "ms");
      setStatus("error");
      setMessage("Sign-in timed out. Please try again.");
      if (subscription) {
        console.log("[AuthCallback] Unsubscribing due to timeout");
        subscription.unsubscribe();
      }
    }, timeoutMs);
    console.log("[AuthCallback] Timeout set for", timeoutMs, "ms");

    // Set up auth state listener FIRST to catch any events
    console.log("[AuthCallback] Setting up onAuthStateChange listener...");
    try {
      const { data } = supabase.auth.onAuthStateChange((event: AuthChangeEvent, session: Session | null) => {
        console.log("[AuthCallback] onAuthStateChange fired:", {
          event,
          hasSession: !!session,
          userId: session?.user?.id,
          email: session?.user?.email,
        });
        
        if (!isMounted) {
          console.log("[AuthCallback] Component unmounted, ignoring event");
          return;
        }
        
        if (event === 'SIGNED_IN' && session) {
          console.log("[AuthCallback] SIGNED_IN event received with session");
          clearTimeout(timeoutId);
          setStatus("success");
          setMessage("Signed in! Redirecting…");
          console.log("[AuthCallback] Scheduling redirect to /");
          setTimeout(() => {
            console.log("[AuthCallback] Executing redirect");
            window.location.replace("/");
          }, 500); // Increased from 200ms to 500ms to ensure session is fully established
        } else if (event === 'SIGNED_OUT') {
          console.warn("[AuthCallback] SIGNED_OUT event received");
          clearTimeout(timeoutId);
          setStatus("error");
          setMessage("Sign-in failed. Please try again.");
        } else {
          console.log("[AuthCallback] Other auth event:", event, "session:", !!session);
        }
      });
      subscription = data.subscription;
      console.log("[AuthCallback] onAuthStateChange listener registered, subscription:", !!subscription);
      
      // Supabase auth-js appears to deadlock/hang before network in this environment.
      // To "complete sign-in" reliably, perform the PKCE token exchange directly and write the session to storage.
      console.log("[AuthCallback] Completing PKCE exchange via direct fetch (bypassing auth-js)...");

      const supabaseUrl = SUPABASE_URL!;
      const anonKey = SUPABASE_ANON_KEY!;
      const supabaseHost = supabaseUrl.split("//")[1]?.split(".")[0];
      if (!supabaseHost) {
        throw new Error("Unable to derive Supabase project ref from URL");
      }

      const codeVerifierKey = `sb-${supabaseHost}-auth-token-code-verifier`;
      const codeVerifierRaw = window.localStorage.getItem(codeVerifierKey);
      if (!codeVerifierRaw) {
        throw new Error("Missing PKCE code_verifier in localStorage");
      }
      let codeVerifier = codeVerifierRaw;
      // Our logs show this value is JSON-stringified, so parse it if needed.
      try {
        const parsed = JSON.parse(codeVerifierRaw);
        if (typeof parsed === "string") codeVerifier = parsed;
      } catch {
        // raw string
      }

      const tokenUrl = `${supabaseUrl}/auth/v1/token?grant_type=pkce`;
      const bodyJson = {
        auth_code: code,
        code_verifier: codeVerifier,
      };

      console.log("[AuthCallback] POST /auth/v1/token (grant_type=pkce)", {
        tokenUrl,
        hasVerifier: !!codeVerifier,
        verifierLen: codeVerifier.length,
        codePreview: code.substring(0, 10) + "...",
      });

      (async () => {
        try {
          const res = await fetch(tokenUrl, {
            method: "POST",
            headers: {
              apikey: anonKey,
              Authorization: `Bearer ${anonKey}`,
              "Content-Type": "application/json",
            },
            body: JSON.stringify(bodyJson),
          });

          const text = await res.text();
          let json: any = null;
          try {
            json = text ? JSON.parse(text) : null;
          } catch {
            // leave as text
          }

          console.log("[AuthCallback] /token response:", {
            ok: res.ok,
            status: res.status,
            bodyType: typeof json === "object" && json ? "json" : "text",
          });

          if (!res.ok) {
            throw new Error(typeof json === "object" && json ? JSON.stringify(json) : String(text));
          }

          // Persist session in the format supabase-js expects in localStorage.
          const supabaseStorageKey = `sb-${supabaseHost}-auth-token`;
          window.localStorage.setItem(supabaseStorageKey, JSON.stringify(json));
          // Clean up verifier (optional but reduces future confusion)
          window.localStorage.removeItem(codeVerifierKey);

          // Best-effort: prime supabase-js in-memory session so AuthContext doesn't need to rely on storage hydration.
          // This MUST be time-bounded because auth-js has been observed to hang in this environment.
          try {
            if (json?.access_token && json?.refresh_token) {
              const setSessionTimeoutMs = 3000; // Increased from 2000ms to allow more time
              console.log("[AuthCallback] Attempting supabase.auth.setSession (best-effort, time-bounded)...");
              await Promise.race([
                supabase.auth.setSession({
                  access_token: json.access_token,
                  refresh_token: json.refresh_token,
                }),
                new Promise<never>((_, reject) =>
                  setTimeout(() => reject(new Error(`setSession timed out after ${setSessionTimeoutMs}ms`)), setSessionTimeoutMs)
                ),
              ]);
              console.log("[AuthCallback] supabase.auth.setSession completed");
            }
          } catch (e) {
            console.warn("[AuthCallback] supabase.auth.setSession failed/timed out (continuing):", e);
          }

          // Force a small delay to ensure localStorage is flushed and session is ready
          await new Promise(resolve => setTimeout(resolve, 300));

          if (!isMounted) return;
          clearTimeout(timeoutId);
          setStatus("success");
          setMessage("Signed in! Redirecting…");
          setTimeout(() => {
            window.location.replace("/");
          }, 500); // Increased from 200ms to 500ms to ensure session is fully established
        } catch (err: any) {
          console.error("[AuthCallback] Direct token exchange failed:", err);
          if (!isMounted) return;
          clearTimeout(timeoutId);
          setStatus("error");
          setMessage(err?.message || "Unable to complete sign in.");
        }
      })();
    } catch (e) {
      console.error("[AuthCallback] Error setting up auth state listener:", e);
      if (!isMounted) return;
      clearTimeout(timeoutId);
      setStatus("error");
      setMessage(e instanceof Error ? e.message : "Unable to complete sign in.");
    }

    return () => {
      console.log("[AuthCallback] Cleanup: unmounting component");
      isMounted = false;
      clearTimeout(timeoutId);
      if (subscription) {
        console.log("[AuthCallback] Cleanup: unsubscribing from auth state changes");
        subscription.unsubscribe();
      }
    };
  }, [router, searchParams]);

  return (
    <main className="auth-callback-screen">
      <div className={`auth-callback-card ${status}`}>
        <h1>Chess GPT</h1>
        <p>{message}</p>
        <button
          onClick={() => {
            try {
              setResetting(true);
              console.warn("[AuthCallback] Resetting Supabase auth storage and reloading...");
              clearSupabaseAuthStorage();
            } finally {
              // Hard reload to ensure a clean re-init of supabase-js and auth state.
              window.location.replace("/");
            }
          }}
          disabled={resetting}
          style={{ marginTop: "1rem" }}
        >
          {resetting ? "Resetting…" : "Reset auth + reload"}
        </button>
        {status === "error" && (
          <button onClick={() => router.replace("/")}>Return to app</button>
        )}
        {status === "pending" && (
          <button 
            onClick={() => router.replace("/")}
            style={{ marginTop: '1rem', opacity: 0.7 }}
          >
            Cancel and return to app
          </button>
        )}
      </div>
    </main>
  );
}

export default function AuthCallbackPage() {
  return (
    <Suspense fallback={<main className="auth-callback-screen"><div className="auth-callback-card pending"><p>Completing sign in…</p></div></main>}>
      <AuthCallbackInner />
    </Suspense>
  );
}
