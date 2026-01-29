"use client";

import type { ReactNode } from "react";
import { AuthProvider } from "@/contexts/AuthContext";
import { UsageProvider } from "@/contexts/UsageContext";

export default function Providers({ children }: { children: ReactNode }) {
  return (
    <AuthProvider>
      <UsageProvider>
        {children}
      </UsageProvider>
    </AuthProvider>
  );
}


