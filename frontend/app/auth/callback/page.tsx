"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { supabase } from "@/lib/supabase";

export default function AuthCallbackPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [status, setStatus] = useState<"pending" | "success" | "error">("pending");
  const [message, setMessage] = useState<string>("Completing sign in…");

  useEffect(() => {
    const errorDescription = searchParams.get("error_description");
    if (errorDescription) {
      setStatus("error");
      setMessage(errorDescription);
      return;
    }

    async function exchangeSession() {
      try {
        const { error } = await supabase.auth.exchangeCodeForSession(
          window.location.href
        );
        if (error) {
          throw error;
        }
        setStatus("success");
        setMessage("Signed in! Redirecting…");
        setTimeout(() => router.replace("/"), 800);
      } catch (err) {
        const friendly =
          err instanceof Error ? err.message : "Unable to complete sign in.";
        setStatus("error");
        setMessage(friendly);
      }
    }

    exchangeSession();
  }, [router, searchParams]);

  return (
    <main className="auth-callback-screen">
      <div className={`auth-callback-card ${status}`}>
        <h1>Chess GPT</h1>
        <p>{message}</p>
        {status === "error" && (
          <button onClick={() => router.replace("/")}>Return to app</button>
        )}
      </div>
    </main>
  );
}


