import type { Metadata } from "next";
import "./styles.css";
import Providers from "./providers";

export const metadata: Metadata = {
  title: "Chess GPT",
  description: "AI-powered chess analysis and training",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}

