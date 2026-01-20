"use client";

import React from "react";

interface SafeAreaViewProps {
  className?: string;
  children: React.ReactNode;
}

export default function SafeAreaView({ className, children }: SafeAreaViewProps) {
  return <div className={`v2-safe-area ${className || ""}`}>{children}</div>;
}

