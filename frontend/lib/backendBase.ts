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
  if (typeof window !== "undefined") {
    const proto = window.location.protocol || "http:";
    const host = window.location.hostname || "localhost";
    const isNgrok = isNgrokDomain(host);
    const isLocalhost = host === "localhost" || host === "127.0.0.1";
    
    // For production domains (vercel.app, custom domains, etc.), always use API proxy
    // This avoids CORS issues and keeps requests server-side
    if (!isLocalhost && !isNgrok) {
      return `${proto}//${host}/api/backend`;
    }
    
    const envUrl = process.env.NEXT_PUBLIC_BACKEND_URL;
    
    // If env URL is set and we're on localhost/ngrok, handle special cases
    if (envUrl && String(envUrl).trim()) {
      const raw = String(envUrl).trim();
      try {
        const parsed = new URL(raw);
        const isLocalhostUrl = parsed.hostname === "localhost" || parsed.hostname === "127.0.0.1";
        
        // If env URL is localhost but we're on ngrok, use API proxy
        if (isLocalhostUrl && isNgrok) {
          return `https://${host}/api/backend`;
        }
        
        // If env URL is localhost but we're on LAN, rewrite hostname
        if (isLocalhostUrl && !isLocalhost && !isNgrok) {
          parsed.hostname = host;
          if (!parsed.port) parsed.port = DEFAULT_BACKEND_PORT;
          return parsed.toString().replace(/\/$/, "");
        }
        
        // For localhost with localhost URL, use direct connection
        if (isLocalhost && isLocalhostUrl) {
          return raw;
        }
      } catch {
        // If URL parsing fails, fall back to API proxy for production
        if (!isLocalhost && !isNgrok) {
          return `${proto}//${host}/api/backend`;
        }
      }
    }
    
    // For ngrok, use API proxy
    if (isNgrok) {
      return `https://${host}/api/backend`;
    }
    
    // For localhost without env URL, use direct connection with port
    if (isLocalhost) {
      return `${proto}//${host}:${DEFAULT_BACKEND_PORT}`;
    }
  }

  return `http://localhost:${DEFAULT_BACKEND_PORT}`;
}
