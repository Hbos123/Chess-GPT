# Derived Signals & Deterministic Detectors (v1)

This document defines the **derived signals** and **detectors** computed from logging tables to identify failure modes *without* explicit labels and *without* ML.

All detectors should be computed via SQL views (or backend batch jobs later) and always segmented by:
- `mode`
- `phase`
- `engine_budget_class`
- `router_version` / `prompt_bundle_version` / `tagger_version`

---

## 1) Engine certainty & volatility features (from `learning_engine_truth`)

### Engine certainty proxies
- **`tb_certainty`**: `tb_hit_bool = true` ⇒ effectively certain
- **`mate_certainty`**: any `mate_* is not null` at sufficient depth
- **`depth_reached`**: `engine_depth`
- **`multipv_disagreement`**: `pv_disagreement_cp`

### Volatility / ambiguity proxies
- **`abs(delta_best_cp)`**: big swings imply tactical/forcing positions
- **`gap_to_best_cp`**: large gap implies a clear tactical punishment or blunder
- **`pv_disagreement_cp` high**: implies multiple near-equal options or shallow certainty

Recommended buckets (tunable):
- `volatility_bucket`:
  - `low` if `abs(delta_best_cp) <= 50`
  - `medium` if `50 < abs(delta_best_cp) <= 150`
  - `high` if `abs(delta_best_cp) > 150`
- `ambiguity_bucket`:
  - `low` if `pv_disagreement_cp <= 30`
  - `medium` if `30 < pv_disagreement_cp <= 80`
  - `high` if `pv_disagreement_cp > 80`

---

## 2) Interaction outcome signals (from `learning_user_behavior` + `learning_interactions`)

### Acceptance proxies
- **`fast_next_action`**: `time_to_next_action_ms <= 8000` AND next action is not “asked_followup”
- **`move_committed`** (PLAY/TACTICS): `made_alternative_move_bool=false` AND `takeback_count=0` shortly after response
- **`low_followup`**: `followup_within_60s_count = 0`

### Confusion proxies
- **`confusion_loop`**: `followup_within_60s_count >= 2`
- **`mode_flip`**: `mode_switch_within_60s_bool = true`
- **`line_demand`**: `requested_more_lines_bool=true` OR `clicked_show_pv_bool=true` repeatedly across interactions

### Disagreement proxies
- **`reject_move_advice`** (PLAY): after “best move” recommendation, user plays a different move AND does not request more explanation
- **`try_multiple_alternatives`**: `made_alternative_move_bool=true` and `replayed_same_position_bool=true`

### Abandonment
- **`abandon_after_response`**: `abandon_after_response_bool=true`

Why these beat ratings:
- High coverage (no user effort)
- Less selection bias (ratings are from extremes)
- Tied to real behavior (move choice, followups, abandonment)

---

## 3) LLM calibration & structure signals (from `learning_llm_response_meta`)

### Verbosity mismatch detector
Compute per user and per cohort:
- `verbosity_class` vs `followup_within_60s_count`, `abandon_after_response_bool`

Detectors:
- **`too_verbose_risk`**:
  - `verbosity_class='long'` AND `abandon_after_response_bool=true`
  - OR `verbosity_class='long'` AND `time_to_next_action_ms` very high (e.g. > 45s)
- **`too_short_risk`**:
  - `verbosity_class='short'` AND `confusion_loop=true`

### Overconfidence detector
Trigger when declared confidence exceeds allowed confidence or when engine ambiguity is high:
- **`overconfident`** if:
  - `confidence_declared_level='high'` AND `confidence_allowed_level in ('low','medium')`
  - OR `confidence_declared_level='high'` AND `pv_disagreement_cp > 80`
  - OR grounding violations: `claimed_eval_without_evidence_bool=true` OR `claimed_pv_without_evidence_bool=true`

### Underconfidence detector
- **`underconfident`** if:
  - `tb_hit_bool=true` AND `confidence_declared_level in ('low','medium')`
  - OR mate found AND confidence not high

### Poor trade-off resolution detector (tag competition not surfaced)

This targets “the system saw a close contest between tags, but the explanation pretended it was one-dimensional.”

Prerequisites:
- `learning_tag_traces.competition_margin` exists
- `learning_llm_response_meta.tradeoff_present_bool` logged
- `learning_llm_response_meta.tags_mentioned` logged (from structured output)

Detectors:
- **`tradeoff_expected`** if `competition_margin` is small:
  - e.g. `competition_margin <= 0.10` (tune to your tag score scale)
- **`tradeoff_missing`** if:
  - `tradeoff_expected=true` AND `tradeoff_present_bool=false`

Tag surfacing mismatch:
- **`dominant_tag_not_mentioned`** if:
  - `dominant_tag is not null` AND `tags_mentioned` does not include it

### Eval-shift valence mismatch detector
When a move objectively worsened the position, but the response is praising (or vice versa).

Inputs:
- `delta_user_cp` (perspective-correct)
- `dominant_shift_direction` (derived from `delta_user_cp`)
- `response_valence`

Mapping rule (first pass):
- `delta_user_cp <= -80` ⇒ `dominant_shift_direction='worsening'`
- `delta_user_cp >= +80` ⇒ `dominant_shift_direction='improving'`
- else `flat`

Detector:
- **`valence_mismatch`** if:
  - `dominant_shift_direction='worsening'` AND `response_valence='praise'`
  - OR `dominant_shift_direction='improving'` AND `response_valence='critical'`

### Grounding violations (hard failures)
- `claimed_eval_without_evidence_bool=true`
- `claimed_pv_without_evidence_bool=true`
- `schema_valid_bool=false` (if your UI relies on schema)

These should be elevated above all other cohorts because they are brand-damaging.

---

## 4) Chess-specific cohort slices (high leverage)

Define standard slices so dashboards are comparable over time:
- **Phase**: opening/middlegame/endgame
- **Volatility bucket**: low/medium/high
- **Ambiguity bucket**: low/medium/high
- **Game character proxy** (optional): use `abs(delta_best_cp)` and forcing-move rate if you log it later
- **Tag family**: `tactic.*` vs `king_safety.*` vs `endgame.*` vs `strategy.*`

---

## 5) Concrete examples (how patterns imply system problems)

### Example A: Overconfidence in ambiguous positions (policy/calibration issue)
Pattern:
- `pv_disagreement_cp` high (ambiguity high)
- `confidence_declared_level='high'`
- `confusion_loop=true`
Implication:
- Confidence governor too permissive in ambiguity; tighten `confidence_allowed_level` cap.

### Example B: Explanation ignores dominant changing tag (reasoning selection issue)
Pattern:
- `tag_deltas` show `king_safety` jumped strongly
- `dominant_tag='king_safety'`
- `tags_mentioned` excludes `king_safety`
- user clicks “show PV” repeatedly
Implication:
- Tag-to-surface mapping is broken (or explainer prompt ignores `tags_surface_plan`).

### Example C: Verbosity mismatch in PLAY (UX contract issue)
Pattern:
- `mode='PLAY'`, `verbosity_class='long'`
- `abandon_after_response_bool=true` spikes after a prompt_bundle change
Implication:
- PLAY mode verbosity governor regressed; enforce shorter schema with stronger limits.

### Example D: Missing trade-offs in near-equal positions (taste issue)
Pattern:
- `competition_margin` small (two tags tied)
- `tradeoff_present_bool=false`
- followups ask “but what about…”
Implication:
- Add a rule: when tag competition is tight, explanation must include one explicit trade-off.


