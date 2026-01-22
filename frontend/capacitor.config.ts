// Avoid depending on @capacitor/cli at build time on Vercel.
// This file is only relevant for Capacitor builds; for web deploys we just need TS to type-check.
type CapacitorConfig = {
  appId: string;
  appName: string;
  webDir: string;
  bundledWebRuntime?: boolean;
  server?: {
    url?: string;
    cleartext?: boolean;
  };
};

/**
 * Capacitor config for the Next.js frontend.
 *
 * Build flow (static):
 * 1) CAPACITOR_EXPORT=1 npm run build
 *    -> outputs static site into `out/`
 * 2) npx cap sync
 *
 * Note: This app expects a backend API (FastAPI) to be reachable from the device.
 * For iOS Simulator, that is usually your Mac's LAN IP (not `localhost`).
 */
const config: CapacitorConfig = {
  appId: "com.hugo.chessgpt",
  appName: "Chess GPT",
  webDir: "out",
  bundledWebRuntime: false,
};

export default config;

