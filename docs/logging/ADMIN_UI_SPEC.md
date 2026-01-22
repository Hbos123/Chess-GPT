# Internal Logging Window (Admin UI) — Spec v1

This is the internal “logging window” used to **enforce adaptation/policy changes** by inspecting cohorts, replays, and failure modes. It is **not** user-facing.

Constraints:
- Works with Supabase RLS (admin-only read access).
- Queries **views** when possible (stable contracts).
- Must support “compare by version” (router/prompt/tagger).

---

## Access control

### Who can access
- Only users in `public.admin_users` (role: `admin` or `analyst`).

### What non-admin users can see
- Nothing (default). We avoid exposing internal diagnostics in the client.

---

## Routes

### `/admin/logging`
Landing dashboard for the last 24h/7d:
- **Headline metrics**:
  - interactions total
  - confusion_loop rate
  - abandon_after_response rate
  - grounding violation rate
  - schema failure rate
- **Top cohorts** (ranked):
  - by `mode`
  - by `dominant_tag`
  - by `phase`
  - by `volatility_bucket`
- **Recent regressions**:
  - compare last 24h vs prior 24h by `prompt_bundle_version` and `router_version`

Primary data sources:
- `public.v_admin_logging_kpis_daily`
- `public.v_admin_failure_modes_ranked`

### `/admin/logging/interactions`
List view (filterable), backed by `public.v_admin_interaction_summary`.

Filters (must be first-class):
- time range
- mode
- phase
- volatility/ambiguity bucket
- dominant_tag
- router_version / prompt_bundle_version / tagger_version
- “only with engine truth”
- “only with grounding violations”
- “only confusion loops”

Columns:
- timestamp
- mode + intent_label
- position preview (fen short hash + optional mini FEN string)
- eval delta (delta_user_cp, gap_to_best_cp)
- dominant_tag + competition_margin
- response meta (confidence, verbosity, schema ok)
- behavior outcome (followup_count, abandoned)
- version bundle (router/prompt/tagger)

### `/admin/logging/interactions/[interaction_id]`
“Replay card” that shows the full structured evidence:

Sections:
- **Context**: mode, intent, versions, tool chain, budgets, fallbacks
- **Chess**: FEN (full), phase, material signature
- **Engine truth packet** (if present):
  - eval before/after, delta_user, gap_to_best
  - top-N moves (compact)
  - certainty: depth, time, multipv spread, tablebase hit
- **Tag trace**:
  - tags_fired sorted by score
  - dominant/runner-up + margin
  - tag deltas (big movers)
  - tags_surface_plan vs tags_mentioned
- **LLM meta**:
  - schema pass/fail
  - confidence declared vs allowed
  - verbosity + claim counts + tradeoff flag
  - grounding alarms
  - valence mismatch (if any)
- **User behavior**:
  - followup count/time to next action
  - PV expansion / request-line indicators
  - takebacks / alternative move attempts
  - abandonment

Primary data source:
- joins on `learning_interactions` + `learning_engine_truth` + `learning_tag_traces` + `learning_llm_response_meta` + `learning_user_behavior`

### `/admin/logging/cohorts`
Purpose: human-driven aggregation without ML. This is where you answer “where does it break?”

UI:
- a cohort builder (AND filters) + saved cohort presets
- output table: metrics by cohort + links to example interactions (5–20)

Metrics:
- confusion_loop rate
- abandon rate
- grounding violation rate
- schema failure rate
- median latency

Primary data sources:
- `public.v_admin_cohort_metrics`
- `public.v_admin_interaction_summary` (for sampling interactions)

### `/admin/logging/change-impact`
Purpose: compare performance across versions and catch regressions.

Compare slices:
- by `prompt_bundle_version` (primary)
- by `router_version`
- by `tagger_version`

Must support:
- same time window
- same cohort filter
- diff view (delta in confusion/abandon/grounding rates)

Primary data source:
- `public.v_admin_change_impact`

---

## Minimum viable build (what we implement first)
Phase 1 (ship fast):
- `/admin/logging/interactions` list + filter
- `/admin/logging/interactions/[interaction_id]` detail replay

Phase 2:
- cohorts page and change-impact comparisons


