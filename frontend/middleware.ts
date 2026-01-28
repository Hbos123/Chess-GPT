import { NextRequest, NextResponse } from "next/server";

// Minimal bot gating:
// - Redirect real users from "/" -> "/app"
// - Serve lightweight "/" to bots by letting them hit the landing page
// - Block the most expensive backend proxy routes for obvious crawler UAs

function isObviousBot(ua: string): boolean {
  const s = (ua || "").toLowerCase();
  return (
    s.includes("headlesschrome") ||
    s.includes("vercel-screenshot") ||
    s.includes("lighthouse") ||
    s.includes("pagespeed") ||
    s.includes("crawler") ||
    s.includes("spider")
  );
}

export function middleware(req: NextRequest) {
  const ua = req.headers.get("user-agent") || "";
  const bot = isObviousBot(ua);
  const { pathname } = req.nextUrl;

  // Block obvious bots from triggering expensive backend work through the proxy.
  // (They can still hit "/", but the landing is cheap.)
  if (bot && pathname.startsWith("/api/backend/board")) {
    return new NextResponse("Blocked", { status: 403 });
  }

  // Send real users into the app route. Bots stay on landing page.
  if (pathname === "/" && !bot) {
    const url = req.nextUrl.clone();
    url.pathname = "/app";
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/", "/api/backend/board/:path*"],
};

