import { NextRequest, NextResponse } from "next/server";

function isObviousBot(ua: string): boolean {
  const s = (ua || "").toLowerCase();
  return (
    s.includes("headlesschrome") ||
    s.includes("vercel-screenshot") ||
    s.includes("lighthouse") ||
    s.includes("pagespeed") ||
    s.includes("crawler") ||
    s.includes("spider") ||
    // Common bot tokens that may not include "crawler"/"spider"
    s.includes("bot") ||
    s.includes("googlebot") ||
    s.includes("bingbot")
  );
}

export function middleware(req: NextRequest) {
  const ua = req.headers.get("user-agent") || "";
  const bot = isObviousBot(ua);
  const { pathname } = req.nextUrl;

  // Block obvious bots from triggering expensive backend work through the proxy.
  // (They can still hit public pages like "/", but the landing is cheap.)
  if (bot && pathname.startsWith("/api/backend/board")) {
    return new NextResponse("Blocked", { status: 403 });
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/api/backend/board/:path*"],
};

