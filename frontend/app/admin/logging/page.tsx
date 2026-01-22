"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function AdminLoggingIndexPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/admin/logging/interactions");
  }, [router]);

  return null;
}


