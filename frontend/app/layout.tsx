import type { Metadata } from "next";
import "./styles.css";

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
      <body>{children}</body>
    </html>
  );
}

