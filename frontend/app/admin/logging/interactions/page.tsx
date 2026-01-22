"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/contexts/AuthContext";
import { supabase } from "@/lib/supabase";
import { getMyAdminRole } from "@/lib/admin";

type Mode = "PLAY" | "ANALYZE" | "TACTICS" | "DISCUSS";

type InteractionSummaryRow = {
  interaction_id: string;
  created_at: string;
  mode: Mode;
  intent_label: string | null;
  phase: string | null;
  dominant_tag: string | null;
  competition_margin: number | null;
  delta_user_cp: number | null;
  gap_to_best_cp: number | null;
  schema_valid_bool: boolean | null;
  confidence_declared_level: string | null;
  confidence_allowed_level: string | null;
  verbosity_class: string | null;
  followup_within_60s_count: number | null;
  abandon_after_response_bool: boolean | null;
  confusion_loop_bool: boolean | null;
  grounding_violation_bool: boolean | null;
  router_version: string | null;
  prompt_bundle_version: string | null;
  tagger_version: string | null;
};

export default function AdminLoggingInteractionsPage() {
  const { user, loading: authLoading } = useAuth();
  const [adminRole, setAdminRole] = useState<string | null>(null);

  const [modeFilter, setModeFilter] = useState<Mode | "ALL">("ALL");
  const [onlyConfusion, setOnlyConfusion] = useState(false);
  const [onlyGrounding, setOnlyGrounding] = useState(false);

  const [rows, setRows] = useState<InteractionSummaryRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      const role = await getMyAdminRole();
      setAdminRole(role);
    })();
  }, [user?.id]);

  const canView = useMemo(() => !!user && !!adminRole, [user, adminRole]);

  const load = useCallback(async () => {
    if (!canView) return;
    setLoading(true);
    setError(null);
    try {
      let q = supabase
        .from("v_admin_interaction_summary")
        .select(
          "interaction_id,created_at,mode,intent_label,phase,dominant_tag,competition_margin,delta_user_cp,gap_to_best_cp,schema_valid_bool,confidence_declared_level,confidence_allowed_level,verbosity_class,followup_within_60s_count,abandon_after_response_bool,confusion_loop_bool,grounding_violation_bool,router_version,prompt_bundle_version,tagger_version"
        )
        .order("created_at", { ascending: false })
        .limit(250);

      if (modeFilter !== "ALL") q = q.eq("mode", modeFilter);
      if (onlyConfusion) q = q.eq("confusion_loop_bool", true);
      if (onlyGrounding) q = q.eq("grounding_violation_bool", true);

      const { data, error } = await q;
      if (error) throw error;
      setRows((data ?? []) as InteractionSummaryRow[]);
    } catch (e: any) {
      setError(e?.message ?? String(e));
    } finally {
      setLoading(false);
    }
  }, [canView, modeFilter, onlyConfusion, onlyGrounding]);

  useEffect(() => {
    load();
  }, [load]);

  if (authLoading) return <div style={{ padding: 16 }}>Loading auth…</div>;
  if (!user) return <div style={{ padding: 16 }}>Please sign in.</div>;
  if (!adminRole) {
    return (
      <div style={{ padding: 16 }}>
        <div style={{ fontWeight: 700, marginBottom: 8 }}>Admin Logging</div>
        <div>Access denied (not an admin).</div>
      </div>
    );
  }

  return (
    <div style={{ padding: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center" }}>
        <div>
          <div style={{ fontSize: 18, fontWeight: 800 }}>Admin Logging — Interactions</div>
          <div style={{ opacity: 0.8, fontSize: 12 }}>Role: {adminRole}</div>
        </div>
        <button onClick={load} disabled={loading} style={{ padding: "8px 12px" }}>
          {loading ? "Refreshing…" : "Refresh"}
        </button>
      </div>

      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginTop: 12, alignItems: "center" }}>
        <label style={{ display: "flex", gap: 8, alignItems: "center" }}>
          Mode
          <select value={modeFilter} onChange={(e) => setModeFilter(e.target.value as any)}>
            <option value="ALL">ALL</option>
            <option value="PLAY">PLAY</option>
            <option value="ANALYZE">ANALYZE</option>
            <option value="TACTICS">TACTICS</option>
            <option value="DISCUSS">DISCUSS</option>
          </select>
        </label>

        <label style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <input type="checkbox" checked={onlyConfusion} onChange={(e) => setOnlyConfusion(e.target.checked)} />
          Only confusion loops
        </label>

        <label style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <input type="checkbox" checked={onlyGrounding} onChange={(e) => setOnlyGrounding(e.target.checked)} />
          Only grounding violations
        </label>
      </div>

      {error && (
        <div style={{ marginTop: 12, color: "#b91c1c" }}>
          Error loading logs: {error}
          <div style={{ opacity: 0.8, fontSize: 12 }}>
            Check that `015_learning_logging_v1.sql` has been applied and that your user is in `admin_users`.
          </div>
        </div>
      )}

      <div style={{ marginTop: 12, overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
          <thead>
            <tr style={{ textAlign: "left", borderBottom: "1px solid rgba(255,255,255,0.15)" }}>
              <th style={{ padding: 8 }}>Time</th>
              <th style={{ padding: 8 }}>Mode/Intent</th>
              <th style={{ padding: 8 }}>Eval Δ</th>
              <th style={{ padding: 8 }}>Tag</th>
              <th style={{ padding: 8 }}>LLM</th>
              <th style={{ padding: 8 }}>Behavior</th>
              <th style={{ padding: 8 }}>Flags</th>
              <th style={{ padding: 8 }}>Versions</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.interaction_id} style={{ borderBottom: "1px solid rgba(255,255,255,0.08)" }}>
                <td style={{ padding: 8, whiteSpace: "nowrap" }}>
                  <Link href={`/admin/logging/interactions/${r.interaction_id}`} style={{ textDecoration: "underline" }}>
                    {new Date(r.created_at).toLocaleString()}
                  </Link>
                </td>
                <td style={{ padding: 8 }}>
                  <div style={{ fontWeight: 700 }}>{r.mode}</div>
                  <div style={{ opacity: 0.8 }}>{r.intent_label ?? "—"}</div>
                </td>
                <td style={{ padding: 8 }}>
                  <div>Δuser: {r.delta_user_cp ?? "—"}</div>
                  <div style={{ opacity: 0.8 }}>gap: {r.gap_to_best_cp ?? "—"}</div>
                </td>
                <td style={{ padding: 8 }}>
                  <div>{r.dominant_tag ?? "—"}</div>
                  <div style={{ opacity: 0.8 }}>margin: {r.competition_margin ?? "—"}</div>
                </td>
                <td style={{ padding: 8 }}>
                  <div>schema: {r.schema_valid_bool === null ? "—" : r.schema_valid_bool ? "ok" : "fail"}</div>
                  <div style={{ opacity: 0.8 }}>
                    conf: {r.confidence_declared_level ?? "—"}/{r.confidence_allowed_level ?? "—"} · verb:{" "}
                    {r.verbosity_class ?? "—"}
                  </div>
                </td>
                <td style={{ padding: 8 }}>
                  <div>followups: {r.followup_within_60s_count ?? "—"}</div>
                  <div style={{ opacity: 0.8 }}>abandon: {r.abandon_after_response_bool ? "yes" : "no"}</div>
                </td>
                <td style={{ padding: 8 }}>
                  <div>confusion: {r.confusion_loop_bool ? "yes" : "no"}</div>
                  <div style={{ opacity: 0.8 }}>grounding: {r.grounding_violation_bool ? "yes" : "no"}</div>
                </td>
                <td style={{ padding: 8 }}>
                  <div style={{ opacity: 0.9 }}>router: {r.router_version ?? "—"}</div>
                  <div style={{ opacity: 0.8 }}>prompt: {r.prompt_bundle_version ?? "—"}</div>
                  <div style={{ opacity: 0.8 }}>tagger: {r.tagger_version ?? "—"}</div>
                </td>
              </tr>
            ))}
            {!loading && rows.length === 0 && (
              <tr>
                <td colSpan={8} style={{ padding: 12, opacity: 0.8 }}>
                  No rows found for the current filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}


