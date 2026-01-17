# Evidence Semantic Story Pipeline (Design Doc)

### Goal
Reduce “double-negative” interpretation errors (e.g., *tag LOST* incorrectly framed as bad) by adding a **deterministic** intermediate layer that turns per-move deltas (tags/roles/eval) into a **semantic, human-readable story** *without* introducing new analysis.

This is an additive change: we still provide the full PGN + per-move structured evidence. The new layer supplies a “semantic story” that removes parsing and polarity-inversion burden from the summariser.

---

### Current pain point
Today the summariser receives evidence that is:
- **Algebraic**: SAN/PGN sequences + delta lists
- **Polarity-heavy**: `tags_lost_net` requires semantic inversion (“lost” may mean improvement)
- **Single-pass expectation**: the LLM must parse, interpret, and write claims in one go

This increases the chance of:
- Treating **tag losses as inherently negative**
- Producing incorrect causal language (“traps your rook”) when the evidence implies “no longer trapped”
- Overweighting low-signal tags or misreading net changes

---

### Proposed pipeline (additive)
We add a deterministic module that produces a **Semantic Story** alongside the existing evidence payload.

### Data Flow
- **Investigator / Executor**
  - Produces:
    - Evidence line (SAN list / PGN)
    - Per-move deltas: tags gained/lost, roles gained/lost
    - Eval breakdown start/end (material/positional/total), optional per-move eval if available later
    - Themes (optional)
- **Semantic Story Builder (NEW, deterministic)**
  - Consumes structured evidence only
  - Emits:
    - A per-move list of “events” with explicit semantics for each gained/lost tag and role
    - A final “net semantic summary” (positive/negative/neutral changes)
  - **No engine calls, no LLM calls**
- **Summariser (LLM)**
  - Receives:
    - Full structured PGN evidence (source of truth)
    - Semantic Story (interpretation aid)
  - Must:
    - Ground claims in the structured PGN and semantic story
    - Avoid inventing moves/tags/roles
- **Explainer (LLM)**
  - Receives narrative decisions + evidence snippets (unchanged)
  - Benefits because claims are cleaner and semantically consistent

---

### What “Semantic Story” is (and is not)
### Definition
Semantic Story is a **deterministic paraphrase** of *what the evidence already says*.

It is:
- A structured list of “what changed” per move in plain language
- Explicit about semantic inversion: **what tag/role gained/lost means**
- Safe and bounded (no new chess analysis)

It is not:
- A new evaluation layer
- A replacement for the PGN
- A speculative explanation (“maybe Black intended…”)
- A second engine run or deeper search

---

### Output schema (recommended)
The story is structured so the summariser can use it as scaffolding without re-parsing algebra.

```json
{
  "starting": {
    "fen": "...",
    "side_to_move": "white|black",
    "castling_rights": "KQkq|-",
    "eval": { "total": 0.0, "material": 0.0, "positional": 0.0 }
  },
  "moves": [
    {
      "ply": 1,
      "move_san": "Nf3",
      "events": [
        { "type": "tag", "change": "lost", "name": "tag.undeveloped.knight", "meaning": "a knight became developed", "polarity": "positive" },
        { "type": "role", "change": "gained", "name": "role.developing.piece", "meaning": "development improved", "polarity": "positive" }
      ],
      "eval_note": { "delta_total": +0.10, "delta_positional": +0.10, "delta_material": 0.0 }
    }
  ],
  "net": {
    "positive": [ "development improved", "piece freed", "castling became legal (kingside)" ],
    "negative": [ "bishop pair removed", "king safety worsened" ],
    "neutral": [ "diagonal opened/closed" ],
    "net_eval_delta_total": -0.67
  },
  "guards": {
    "no_new_analysis": true,
    "grounding": "All meanings are derived from tag/role names + evidence deltas only"
  }
}
```

---

### Deterministic semantics rules
We need consistent rules for interpreting **gain/loss** of tags/roles.

### Tag semantics
Tags are properties of the position. A tag being:
- **Gained** means that property now exists
- **Lost** means that property no longer exists

But the *polarity* (good/bad) depends on the tag’s semantics.

### Tag polarity classification (deterministic)
Each tag is mapped to a polarity category using:
- Prefix-based / substring-based heuristics (fast, maintainable)
- Optional curated lists for high-signal tags

#### Category A — “Problem tags” (negative semantics)
If a tag name includes or matches concepts like:
- `trapped`, `undeveloped`, `hanging`, `overloaded`, `pinned` (if used as weakness), `exposed`, `weak`, `isolated`, `backward`, `bad` (as in bad bishop), `king.center.exposed`, `shield.missing`

Then:
- **GAIN** → a problem appeared (negative)
- **LOSS** → a problem was resolved (positive)

#### Category B — “Benefit tags” (positive semantics)
If a tag name includes or matches concepts like:
- `bishop.pair`, `shield.intact`, `outpost` (as benefit), `passed_pawn`, `space` (if used positively), `initiative` (if present), `castling.available.*`

Then:
- **GAIN** → a benefit appeared (positive)
- **LOSS** → a benefit was removed (negative)

#### Category C — “Context-dependent / structural tags”
Examples:
- `diagonal.open.*`, `file.open`, `center.control.*`, `key.*`, `activity.*`, `lever.*`, many geometry tags

Then:
- **GAIN/LOSS** → “property changed” (neutral by default)
- The semantic story should not force a polarity unless:
  - There is a paired, higher-signal tag that makes it obvious, or
  - The eval delta is large and we’re summarising net direction

### Role semantics
Roles are “functional descriptors” of pieces/squares. We treat them similarly:
- **Role gained**: the role is now present
- **Role lost**: the role is no longer present

But polarity depends on whether the role describes:

#### “Improvement roles”
Examples:
- `role.developing.*`, `role.activity.*`, `role.control.*` (when used as advantage), `role.attacking.*` (for the side), `role.defending.*` (for the side)

Then:
- **GAIN** → likely positive for that side
- **LOSS** → likely negative for that side

#### “Weakness roles”
Examples:
- `role.status.trapped`, `role.status.hanging`, `role.attacking.overloaded_piece` (if it indicates “your piece is overloaded”), `role.status.over_defended` (depends: over-defended might be “wasteful defenders”)

Then:
- **GAIN** → likely negative for that side
- **LOSS** → likely positive for that side

#### “Neutral roles”
If role semantics are unclear:
- Mark as neutral and do not force a narrative; let eval delta decide importance

---

### Castling-specific handling (tags)
Castling is a special case because it is both:
- A **right** (K/Q) and
- An **available legal move** (O-O / O-O-O)

We will use tags like:
- `tag.castling.available.kingside` / `tag.castling.available.queenside`
  - Meaning: castling is currently legal for that side
  - Polarity: benefit tag (gain = positive, loss = negative)
- `tag.castling.rights.kingside` / `tag.castling.rights.queenside`
  - Meaning: rights exist, but move not currently legal (blocked/check/etc.)
  - Polarity: informational/neutral; a *loss* indicates rights were lost (negative)
- `tag.castling.rights.lost.*`
  - Meaning: rights are gone
  - Polarity: negative for that side

Semantic Story should render these as explicit sentences, e.g.:
- “Kingside castling became legal.”
- “Queenside castling is no longer available (rights lost).”

---

### How the summariser should use the Semantic Story
### Prompt contract
The summariser receives:
- **Structured PGN evidence** (source of truth)
- **Semantic Story** (interpretation helper)

Rules:
- Claims must be grounded in the structured PGN evidence.
- Semantic Story can be paraphrased, but summariser must not introduce:
  - Moves not in PGN
  - Tags/roles not in deltas
  - Eval numbers not present
- When describing tag/role losses, prefer the story meaning (“problem resolved”) rather than literal “lost X”.

### Why this helps
It breaks the “three hard tasks in one pass” problem:
- Parsing is reduced (story already explains)
- Polarity inversion is explicit
- Narrative can focus on what matters (backed by eval delta)

---

### Implementation plan (files + responsibilities)
### 1) Add Semantic Story Builder (deterministic)
Recommended location:
- `backend/summariser.py` (best locality: it already has `pgn_tag_deltas_raw` and the prompt assembly)

Add:
- `def _build_semantic_story(self, pgn_tag_deltas_raw, evidence_eval, extra_context) -> Dict`

### 2) Extend the “organized PGN structure”
You already have an “organized PGN structure” concept; extend it with:
- `semantic_story`
- `net_semantic_summary`

### 3) Prompt update
Add a dedicated prompt section:
- “SEMANTIC STORY (deterministic, derived from tags/roles; use as interpretation aid)”
- Clear constraints: “No new analysis; do not contradict PGN”

### 4) Tests (recommended)
Add tests that assert:
- If a “problem tag” is **lost**, the story marks it as **positive**
- Castling tags render as “became legal” vs “rights lost”

---

### Example outputs (generic, not tied to any one position)
These are deliberately abstract; they illustrate format and polarity handling, not a specific test case.

### Example A — Development resolves an “undeveloped” tag
**Input deltas**
- Move: `Nf3`
  - Tags lost: `tag.undeveloped.knight`
  - Roles gained: `role.developing.piece`
  - Eval delta total: +0.12

**Semantic Story**
- “Nf3: a previously-undeveloped knight became developed (positive). Development improved (positive).”
- Net: positive changes dominate; small eval improvement.

### Example B — Benefit tag lost (bishop pair removed)
**Input deltas**
- Move: `Bxe2`
  - Tags lost: `tag.bishop.pair`
  - Eval delta total: -0.45

**Semantic Story**
- “Bxe2: bishop pair advantage was removed (negative).”
- Net: negative change; modest eval decrease.

### Example C — Castling becomes legal
**Input deltas**
- Move: `Be2`
  - Tags gained: `tag.castling.available.kingside`

**Semantic Story**
- “Be2: kingside castling became legal (positive).”

### Example D — Castling rights lost
**Input deltas**
- Move: `Kf1`
  - Tags gained: `tag.castling.rights.lost`

**Semantic Story**
- “Kf1: castling rights are now lost (negative).”

---

### Guardrails to prevent “overfitting” and false positives
We avoid hard-coding position-specific examples by:
- Using **semantic categories** (problem vs benefit vs neutral) rather than bespoke tag-by-tag scripts
- Keeping the story builder deterministic and reversible:
  - It only rephrases what the tag/role names already encode
- Maintaining the structured PGN as the ultimate ground truth

---

### Success criteria
We consider this system “working” when:
- Summaries correctly treat problem-tag losses as improvements (“no longer trapped” rather than “trapped”)
- Claims align with evidence sequences (no invented captures/actors)
- Castling availability is explicitly surfaced (became legal / rights lost)
- Tag spam doesn’t leak into claims (semantic story marks neutral tags as neutral unless eval supports)







