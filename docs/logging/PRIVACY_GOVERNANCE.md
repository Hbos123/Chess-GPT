# Privacy & Governance for Learning Logs (v1)

This document defines the privacy stance, access model, and change-control process for the learning-first logging layer.

---

## Default stance (non-negotiable)

### No raw text by default
- Do not store raw user chat or raw LLM output for routine logging.
- Store **structured metadata** and **derived features** only.

### Debug text is opt-in + temporary
Raw text may be stored only when:
- The user (or internal operator in a test environment) explicitly enables “Debug Logging” for the session, and
- It is written to `learning_text_debug_artifacts` with an `expires_at` TTL, and
- Access is restricted by role (admin/analyst).

Implementation note:
- Session opt-in is represented by `learning_debug_sessions(user_id, app_session_id, enabled_bool, expires_at)`.
- `learning_text_debug_artifacts` inserts are allowed only when a non-expired enabled debug session exists for the interaction’s `app_session_id`.

---

## Access control (Supabase RLS)

### Admin membership
Create `public.admin_users(user_id, role, created_at)` and enforce:
- Admin UI requires the signed-in user to be present in this table.

### Read access
- **Admin/Analyst**: can read logging tables and admin views.
- **Normal users**: no access to learning logs (unless you explicitly open a “my diagnostics” feature later).

### Write access
Prefer server-side writes (backend service role) for:
- learning interactions
- engine truth packets
- tag traces
- LLM response meta

Client-side writes (anon key) are allowed only for:
- minimal UI telemetry signals that cannot be captured server-side (and must be tied to `auth.uid()`).

---

## Data minimization rules

### Allowed
- FEN / position hashes
- engine eval numbers and compact move lists
- tag scores, tag deltas, tag surfacing plan/mention lists
- response structural metadata (length, confidence level, claim counts)
- passive behavior summaries (counts/booleans)

### Disallowed by default
- full PV text dumps
- raw chat content
- any PII strings (email, names, usernames in free text)
- high-frequency UI cursor/hover streams

---

## Retention policy

### Standard logs
- Retain interaction logs for as long as needed for product improvement (recommend: 90–180 days initially).

### Debug text artifacts
- Must have `expires_at` (recommend: 7 days).
- Provide a cleanup mechanism (scheduled job or periodic maintenance function).

---

## Change control (adding or modifying logged fields)

Any new logging field must have:
- **Purpose**: what decision it enables
- **Privacy review**: does it increase risk or capture text?
- **Aggregation plan**: what view/metric will consume it
- **Size bounds**: max length / max array sizes / cardinality expectations
- **Backfill policy**: optional; usually “no backfill” for logs

If a field cannot be tied to a decision, it should not be logged.


