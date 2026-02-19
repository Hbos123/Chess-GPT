import type { Metadata, Viewport } from "next";
import "./styles.css";
import Providers from "./providers";
import { Analytics } from "@vercel/analytics/next";

// Get canonical URL (the one that doesn't redirect)
const getCanonicalUrl = (): string => {
  // Prefer configuring via NEXT_PUBLIC_BASE_URL. Fallback should match the
  // production canonical host to avoid cross-domain canonical/sitemap issues.
  const raw = (process.env.NEXT_PUBLIC_BASE_URL || 'https://www.chessterai.com').replace(/\/$/, '');
  // If the apex redirects to www (current production behavior), ensure canonicals
  // don't point at a different host.
  return raw === 'https://chessterai.com' ? 'https://www.chessterai.com' : raw;
};

export const metadata: Metadata = {
  title: "Chesster",
  description: "AI-powered chess analysis and training",
  metadataBase: new URL(getCanonicalUrl()),
  alternates: {
    canonical: '/',
  },
  icons: {
    icon: [
      // Use PNG for the tab/favicon to avoid browser SVG favicon rendering quirks.
      { url: "/icons/icon-192.png", type: "image/png", sizes: "192x192" },
    ],
    apple: [
      { url: "/icons/icon-192.png", type: "image/png", sizes: "180x180" },
    ],
  },
  manifest: "/manifest.json",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "Chesster",
  },
  formatDetection: {
    telephone: false,
  },
  openGraph: {
    type: "website",
    siteName: "Chesster",
    title: "Chesster",
    description: "AI-powered chess analysis and training",
    url: getCanonicalUrl(),
  },
  twitter: {
    card: "summary",
    title: "Chesster",
    description: "AI-powered chess analysis and training",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
  viewportFit: "cover",
  themeColor: "#1e3a8a",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <div className="app-root">
          <Providers>{children}</Providers>
        </div>
        <Analytics />
      </body>
    </html>
  );
}

