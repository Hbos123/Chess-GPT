import type { Metadata, Viewport } from "next";
import "./styles.css";
import Providers from "./providers";

export const metadata: Metadata = {
  title: "Chesster",
  description: "AI-powered chess analysis and training",
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
      </body>
    </html>
  );
}

