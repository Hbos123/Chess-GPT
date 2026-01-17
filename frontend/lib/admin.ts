"use client";

import { supabase } from "@/lib/supabase";

export type AdminRole = "admin" | "analyst";

export async function getMyAdminRole(): Promise<AdminRole | null> {
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) return null;

  // RLS on admin_users allows a user to read only their own membership row.
  const { data, error } = await supabase
    .from("admin_users")
    .select("role")
    .eq("user_id", user.id)
    .maybeSingle();

  if (error) return null;
  if (!data?.role) return null;
  return data.role as AdminRole;
}


