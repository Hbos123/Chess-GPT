/**
 * Resolve the backend base URL in a way that works for both:
 * - local desktop usage (http://localhost:8001)
 * - LAN / iPhone usage (http://<your-mac-ip>:8001)
 * - ngrok HTTPS access (https://<ngrok-domain> - same domain, no port)
 *
 * Priority:
 * 1) NEXT_PUBLIC_BACKEND_URL (explicit override)
 * 2) Auto-detect ngrok and use same domain with HTTPS (no port)
 * 3) window.location.hostname + default port (client-side, LAN-safe)
 * 4) localhost + default port (server-side fallback)
 */
// Backend runs on 8000 in this repo (start scripts + uvicorn port).
export const DEFAULT_BACKEND_PORT = "8000";

/**
 * Detect if we're accessing the app via ngrok
 */
function isNgrokDomain(hostname: string): boolean {
  return hostname.includes('.ngrok-free.dev') || 
         hostname.includes('.ngrok.io') ||
         hostname.includes('.ngrok.app');
}

export function getBackendBase(): string {
  const envUrl = process.env.NEXT_PUBLIC_BACKEND_URL;
  if (envUrl && String(envUrl).trim()) {
    const raw = String(envUrl).trim();
    // If an explicit env URL points at localhost but the user is visiting the site via LAN
    // (e.g. iPhone hitting http://192.168.x.x:3000), "localhost" will resolve to the phone.
    // In that case, rewrite the host to the current page hostname but keep protocol/port.
    if (typeof window !== "undefined") {
      try {
        const parsed = new URL(raw);
        const isLocalhost =
          parsed.hostname === "localhost" || parsed.hostname === "127.0.0.1";
        const pageHost = window.location.hostname;
        const pageIsLocalhost =
          pageHost === "localhost" || pageHost === "127.0.0.1";
        const pageIsNgrok = isNgrokDomain(pageHost);
        
        // If env URL is localhost but we're on ngrok, use Next.js API proxy
        if (isLocalhost && pageIsNgrok) {
          const proto = window.location.protocol || "https:";
          return `${proto}//${pageHost}/api/backend`;
        }
        
        if (isLocalhost && !pageIsLocalhost && !pageIsNgrok) {
          parsed.hostname = pageHost;
          // Keep port from envUrl; if missing, default.
          if (!parsed.port) parsed.port = DEFAULT_BACKEND_PORT;
          return parsed.toString().replace(/\/$/, "");
        }
      } catch {
        // If URL parsing fails, fall back to raw.
      }
    }
    return raw;
  }

  if (typeof window !== "undefined") {
    const proto = window.location.protocol || "http:";
    const host = window.location.hostname || "localhost";
    const isNgrok = isNgrokDomain(host);
    
    // If on ngrok domain, use Next.js API proxy route
    // This proxies requests to localhost backend through Next.js
    if (isNgrok) {
      // Force HTTPS for ngrok to avoid mixed content issues
      return `https://${host}/api/backend`;
    }
    
    // For localhost or LAN access, use the protocol and add port
    return `${proto}//${host}:${DEFAULT_BACKEND_PORT}`;
  }

  return `http://localhost:${DEFAULT_BACKEND_PORT}`;
}


