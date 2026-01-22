"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import { supabase } from "@/lib/supabase";
import { getMyAdminRole } from "@/lib/admin";

export default function AdminInteractionDetailPage() {
  const params = useParams<{ interaction_id: string }>();
  const interactionId = params.interaction_id;

  const { user, loading: authLoading } = useAuth();
  const [adminRole, setAdminRole] = useState<string | null>(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [interaction, setInteraction] = useState<any | null>(null);
  const [engineTruth, setEngineTruth] = useState<any | null>(null);
  const [tagTrace, setTagTrace] = useState<any | null>(null);
  const [llmMeta, setLlmMeta] = useState<any | null>(null);
  const [behavior, setBehavior] = useState<any | null>(null);

  useEffect(() => {
    (async () => {
      const role = await getMyAdminRole();
      setAdminRole(role);
    })();
  }, [user?.id]);

  const canView = useMemo(() => !!user && !!adminRole, [user, adminRole]);

  useEffect(() => {
    if (!canView) return;
    if (!interactionId) return;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const [iRes, eRes, tRes, lRes, bRes] = await Promise.all([
          supabase.from("learning_interactions").select("*").eq("interaction_id", interactionId).maybeSingle(),
          supabase.from("learning_engine_truth").select("*").eq("interaction_id", interactionId).maybeSingle(),
          supabase.from("learning_tag_traces").select("*").eq("interaction_id", interactionId).maybeSingle(),
          supabase.from("learning_llm_response_meta").select("*").eq("interaction_id", interactionId).maybeSingle(),
          supabase.from("learning_user_behavior").select("*").eq("interaction_id", interactionId).maybeSingle(),
        ]);

        if (iRes.error) throw iRes.error;
        if (eRes.error) throw eRes.error;
        if (tRes.error) throw tRes.error;
        if (lRes.error) throw lRes.error;
        if (bRes.error) throw bRes.error;

        setInteraction(iRes.data ?? null);
        setEngineTruth(eRes.data ?? null);
        setTagTrace(tRes.data ?? null);
        setLlmMeta(lRes.data ?? null);
        setBehavior(bRes.data ?? null);
      } catch (e: any) {
        setError(e?.message ?? String(e));
      } finally {
        setLoading(false);
      }
    })();
  }, [canView, interactionId]);

  if (authLoading) return <div style={{ padding: 16 }}>Loading auth…</div>;
  if (!user) return <div style={{ padding: 16 }}>Please sign in.</div>;
  if (!adminRole) return <div style={{ padding: 16 }}>Access denied (not an admin).</div>;

  return (
    <div style={{ padding: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
        <div>
          <div style={{ fontSize: 18, fontWeight: 800 }}>Interaction Replay</div>
          <div style={{ opacity: 0.8, fontSize: 12 }}>
            <Link href="/admin/logging/interactions" style={{ textDecoration: "underline" }}>
              Back to list
            </Link>
            {" · "}
            {interactionId}
          </div>
        </div>
        <div style={{ opacity: 0.8, fontSize: 12 }}>Role: {adminRole}</div>
      </div>

      {error && (
        <div style={{ marginTop: 12, color: "#b91c1c" }}>
          Error loading interaction: {error}
          <div style={{ opacity: 0.8, fontSize: 12 }}>
            Check that migration 015 is applied and your admin membership is set.
          </div>
        </div>
      )}

      {loading && <div style={{ marginTop: 12 }}>Loading…</div>}

      {!loading && !interaction && !error && (
        <div style={{ marginTop: 12, opacity: 0.8 }}>No interaction found.</div>
      )}

      {!loading && interaction && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: 12, marginTop: 12 }}>
          <Section title="Context / System">
            <KV k="created_at" v={interaction.created_at} />
            <KV k="mode" v={interaction.mode} />
            <KV k="intent_label" v={interaction.intent_label} />
            <KV k="intent_confidence" v={interaction.intent_confidence} />
            <KV k="intent_source" v={interaction.intent_source} />
            <KV k="tools_used" v={fmt(interaction.tools_used)} />
            <KV k="engine_budget_class" v={interaction.engine_budget_class} />
            <KV k="multipv" v={interaction.multipv} />
            <KV k="fallback_flags" v={fmt(interaction.fallback_flags)} />
            <KV k="router_version" v={interaction.router_version} />
            <KV k="prompt_bundle_version" v={interaction.prompt_bundle_version} />
            <KV k="tagger_version" v={interaction.tagger_version} />
            <KV k="engine_version" v={interaction.engine_version} />
          </Section>

          <Section title="Chess">
            <KV k="position_id" v={interaction.position_id} />
            <KV k="phase" v={interaction.phase} />
            <KV k="side_to_move" v={interaction.side_to_move} />
            <KV k="ply" v={interaction.ply} />
            <KV k="material_signature" v={interaction.material_signature} />
            <KV k="fen" v={interaction.fen} mono />
          </Section>

          <Section title="Engine truth (if present)">
            {!engineTruth ? (
              <div style={{ opacity: 0.8 }}>No engine truth packet.</div>
            ) : (
              <>
                <KV k="eval_before_cp" v={engineTruth.eval_before_cp} />
                <KV k="eval_after_user_cp" v={engineTruth.eval_after_user_cp} />
                <KV k="eval_after_best_cp" v={engineTruth.eval_after_best_cp} />
                <KV k="delta_user_cp" v={engineTruth.delta_user_cp} />
                <KV k="gap_to_best_cp" v={engineTruth.gap_to_best_cp} />
                <KV k="pv_disagreement_cp" v={engineTruth.pv_disagreement_cp} />
                <KV k="engine_depth" v={engineTruth.engine_depth} />
                <KV k="engine_time_ms" v={engineTruth.engine_time_ms} />
                <KV k="tb_hit_bool" v={engineTruth.tb_hit_bool ? "true" : "false"} />
                <KV k="topn_moves" v={fmt(engineTruth.topn_moves)} mono />
              </>
            )}
          </Section>

          <Section title="Tag trace (if present)">
            {!tagTrace ? (
              <div style={{ opacity: 0.8 }}>No tag trace.</div>
            ) : (
              <>
                <KV k="dominant_tag" v={tagTrace.dominant_tag} />
                <KV k="runnerup_tag" v={tagTrace.runnerup_tag} />
                <KV k="competition_margin" v={tagTrace.competition_margin} />
                <KV k="resolution_rule_id" v={tagTrace.resolution_rule_id} />
                <KV k="tags_surface_plan" v={fmt(tagTrace.tags_surface_plan)} />
                <KV k="tags_fired" v={fmt(tagTrace.tags_fired)} mono />
                <KV k="tag_deltas" v={fmt(tagTrace.tag_deltas)} mono />
              </>
            )}
          </Section>

          <Section title="LLM meta (if present)">
            {!llmMeta ? (
              <div style={{ opacity: 0.8 }}>No LLM meta.</div>
            ) : (
              <>
                <KV k="model" v={llmMeta.model} />
                <KV k="latency_ms" v={llmMeta.latency_ms} />
                <KV k="token_in" v={llmMeta.token_in} />
                <KV k="token_out" v={llmMeta.token_out} />
                <KV k="schema_valid_bool" v={llmMeta.schema_valid_bool ? "true" : "false"} />
                <KV k="schema_errors" v={fmt(llmMeta.schema_errors)} />
                <KV k="confidence_declared_level" v={llmMeta.confidence_declared_level} />
                <KV k="confidence_allowed_level" v={llmMeta.confidence_allowed_level} />
                <KV k="verbosity_class" v={llmMeta.verbosity_class} />
                <KV k="sentence_count" v={llmMeta.sentence_count} />
                <KV k="bullet_count" v={llmMeta.bullet_count} />
                <KV k="tradeoff_present_bool" v={llmMeta.tradeoff_present_bool ? "true" : "false"} />
                <KV k="claims(eval/pv/tactic/plan)" v={`${llmMeta.num_eval_claims}/${llmMeta.num_pv_claims}/${llmMeta.num_tactical_claims}/${llmMeta.num_plan_claims}`} />
                <KV k="grounding(eval/pv)" v={`${llmMeta.claimed_eval_without_evidence_bool ? "Y" : "N"}/${llmMeta.claimed_pv_without_evidence_bool ? "Y" : "N"}`} />
                <KV k="tags_mentioned" v={fmt(llmMeta.tags_mentioned)} />
              </>
            )}
          </Section>

          <Section title="User behavior (if present)">
            {!behavior ? (
              <div style={{ opacity: 0.8 }}>No behavior signals.</div>
            ) : (
              <>
                <KV k="time_to_next_action_ms" v={behavior.time_to_next_action_ms} />
                <KV k="followup_within_60s_count" v={behavior.followup_within_60s_count} />
                <KV k="asked_followup_bool" v={behavior.asked_followup_bool ? "true" : "false"} />
                <KV k="requested_more_lines_bool" v={behavior.requested_more_lines_bool ? "true" : "false"} />
                <KV k="clicked_show_pv_bool" v={behavior.clicked_show_pv_bool ? "true" : "false"} />
                <KV k="expanded_sections" v={fmt(behavior.expanded_sections)} />
                <KV k="takeback_count" v={behavior.takeback_count} />
                <KV k="made_alternative_move_bool" v={behavior.made_alternative_move_bool ? "true" : "false"} />
                <KV k="replayed_same_position_bool" v={behavior.replayed_same_position_bool ? "true" : "false"} />
                <KV k="abandon_after_response_bool" v={behavior.abandon_after_response_bool ? "true" : "false"} />
              </>
            )}
          </Section>
        </div>
      )}
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div
      style={{
        border: "1px solid rgba(255,255,255,0.12)",
        borderRadius: 12,
        padding: 12,
      }}
    >
      <div style={{ fontWeight: 800, marginBottom: 10 }}>{title}</div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: 6 }}>{children}</div>
    </div>
  );
}

function KV({ k, v, mono }: { k: string; v: any; mono?: boolean }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "220px 1fr", gap: 10 }}>
      <div style={{ opacity: 0.75 }}>{k}</div>
      <div style={{ fontFamily: mono ? "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace" : undefined }}>
        {v === null || v === undefined || v === "" ? "—" : String(v)}
      </div>
    </div>
  );
}

function fmt(v: any) {
  if (v === null || v === undefined) return "—";
  try {
    return JSON.stringify(v, null, 2);
  } catch {
    return String(v);
  }
}


