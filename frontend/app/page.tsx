"use client";

import Link from "next/link";
import { useEffect } from "react";

export default function LandingPage() {
  // For real users, immediately send them into the app.
  // Bot/crawler traffic is handled in middleware (rewritten here or blocked).
  useEffect(() => {
    try {
      if (typeof window !== "undefined") window.location.replace("/app");
    } catch {
      // ignore
    }
  }, []);

  return (
    <main style={{ maxWidth: 880, margin: "0 auto", padding: "48px 20px", fontFamily: "system-ui" }}>
      <h1 style={{ fontSize: 36, marginBottom: 8 }}>Chesster</h1>
      <p style={{ fontSize: 16, opacity: 0.8, marginBottom: 24 }}>
        Chess analysis + training. If you’re not redirected automatically, click below.
      </p>
      <Link
        href="/app"
        style={{
          display: "inline-block",
          padding: "12px 16px",
          borderRadius: 10,
          background: "#111827",
          color: "white",
          textDecoration: "none",
          fontWeight: 600,
        }}
      >
        Open App
      </Link>
    </main>
  );
}

