# Complete Four-Layer Pipeline Architecture Summary

## Overview

The Chess-GPT system uses a **4-layer pipeline** architecture to process user requests and generate chess analysis explanations. Each layer has a specific responsibility and strict boundaries to ensure clean separation of concerns.

---

## Architecture Flow

```
User Message
    ↓
[1] INTERPRETER → IntentPlan
    ↓
[2] PLANNER → ExecutionPlan
    ↓
[3] EXECUTOR → Calls Investigator → InvestigationResult
    ↓
[4] SUMMARISER → NarrativeDecision
    ↓
[5] EXPLAINER → Natural Language Response
```

---

## Layer 1: Interpreter (RequestInterpreter)

**Purpose:** Classify user intent and create an orchestration plan.

**Location:** `backend/request_interpreter.py`

### Responsibilities

1. **Intent Classification:** Uses LLM (GPT-4o) to understand what the user wants
2. **Mode Detection:** Determines if user wants to analyze, play, review, train, or chat
3. **Investigation Planning:** Creates `IntentPlan` with `investigation_requests`
4. **Message Decomposition:** Breaks complex requests into simpler components

### Input

```python
{
    "message": str,  # User's message
    "context": {
        "fen": str,  # Current board position
        "pgn": str,  # Game notation
        "mode": str,  # Current mode (DISCUSS, ANALYZE, etc.)
        "board_state": Dict,
        "has_fen": bool,
        "has_pgn": bool,
        ...
    }
}
```

### Output: `IntentPlan`

```python
@dataclass
class IntentPlan:
    intent: str  # "position_analysis", "move_analysis", "game_review", etc.
    scope: str  # "current_position", "specific_move", "entire_game"
    goal: str  # "find_best_move", "explain_mistake", etc.
    investigation_required: bool
    investigation_type: Optional[str]  # "position", "move", "game"
    investigation_requests: List[AnalysisRequest]  # What to investigate
    mode: Mode  # ANALYZE, DISCUSS, PLAY, etc.
    mode_confidence: float
    user_intent_summary: str
```

### Key Methods

- `interpret(message, context) -> IntentPlan`: Main entry point
- Uses LLM with `INTERPRETER_SYSTEM_PROMPT` to classify intent
- Validates that `investigation_required` matches `investigation_requests`

### Logging

- Logs complete input (message, context keys, FEN, mode)
- Logs complete output (intent, scope, goal, investigation_requests)

---

## Layer 2: Planner

**Purpose:** Convert abstract `IntentPlan` into a sequential `ExecutionPlan`.

**Location:** `backend/planner.py`

### Responsibilities

1. **Step Generation:** Creates ordered list of `ExecutionStep` objects
2. **Sequential Planning:** Steps are executed one-by-one in order
3. **Tool Mapping:** Maps investigation requests to specific investigator methods

### Input

```python
{
    "intent_plan": IntentPlan,
    "context": {
        "fen": str,
        "pgn": str,
        ...
    }
}
```

### Output: `ExecutionPlan`

```python
@dataclass
class ExecutionPlan:
    plan_id: str  # Unique identifier
    original_intent: IntentPlan
    steps: List[ExecutionStep]  # Ordered list

@dataclass
class ExecutionStep:
    step_number: int  # 1, 2, 3, ...
    action_type: str  # "investigate_position", "investigate_move", "synthesize", "answer"
    parameters: Dict[str, Any]  # {"fen": "...", "move_san": "Nf3", "focus": "knight"}
    purpose: str  # Human-readable purpose
    tool_to_call: Optional[str]  # "investigator.investigate_position"
    expected_output: str
    status: str  # "pending", "in_progress", "completed", "failed"
```

### Key Methods

- `create_execution_plan(intent_plan, context) -> ExecutionPlan`: Main entry point
- Uses LLM with `PLANNER_SYSTEM_PROMPT` to generate steps
- Ensures steps are sequential and actionable

### Logging

- Logs complete input (intent, investigation_requests, FEN)
- Logs complete output (plan_id, total_steps, each step's purpose and parameters)

---

## Layer 3: Executor

**Purpose:** Execute `ExecutionPlan` steps sequentially, calling `Investigator` methods.

**Location:** `backend/executor.py`

### Responsibilities

1. **Step Execution:** Processes each `ExecutionStep` in order
2. **Investigator Calls:** Calls appropriate `Investigator` methods based on `action_type`
3. **SSE Events:** Emits real-time updates via Server-Sent Events
4. **Result Aggregation:** Collects results from all steps

### Input

```python
{
    "plan": ExecutionPlan,
    "context": {
        "fen": str,
        "pgn": str,
        ...
    },
    "status_callback": Optional[Callable],
    "live_pgn_streams": Optional[Dict],
    "session_id": Optional[str]
}
```

### Output

```python
{
    "completed_steps": List[int],  # [1, 2, 3, ...]
    "results": {
        1: InvestigationResult,  # Step 1 result
        2: InvestigationResult,  # Step 2 result
        ...
    },
    "final_result": Dict,  # From last step
    "plan_id": str
}
```

### Key Methods

- `execute_plan(plan, context, ...) -> Dict`: Main entry point
- Handles different `action_type` values:
  - `"investigate_position"` → `investigator.investigate_position(...)`
  - `"investigate_move"` → `investigator.investigate_move(...)`
  - `"synthesize"` → Returns `{"synthesis_ready": True, "results": {...}}`
  - `"answer"` → Returns `{"answer_ready": True}`

### SSE Events Emitted

- `plan_created`: When plan starts
- `step_update`: When step status changes
- `thinking_started`: When investigation begins
- `pgn_update`: Real-time PGN exploration updates
- `plan_progress`: Overall progress percentage

### Logging

- Logs complete input (plan_id, total_steps, context FEN)
- Logs each step's input (FEN, move_san, depth, focus, scope)
- Logs each step's output (InvestigationResult summary)
- Logs complete output (completed_steps, results keys)

---

## Layer 4: Investigator

**Purpose:** Execute chess analysis and return structured `InvestigationResult` (facts only, NO prose).

**Location:** `backend/investigator.py`

### Responsibilities

1. **Chess Analysis:** Performs deep position and move analysis
2. **Dual-Depth Analysis:** Compares D16 (deep) vs D2 (shallow) evaluations
3. **Tactical Scanning:** Uses `TwoMoveWinEngine` to find tactics
4. **Tag Detection:** Uses `LightRawAnalyzer` to detect positional tags
5. **PGN Exploration:** Builds extensive PGN with all branches, themes, tactics, and tag deltas
6. **Structured Output:** Returns ONLY structured data, no natural language

### Input (for `investigate_position`)

```python
{
    "fen": str,
    "move_index": Optional[int],
    "depth": int,  # Default: 18
    "focus": Optional[str],  # "knight", "pawn_structure", etc.
    "scope": Optional[str],  # "general_position", "specific_piece"
    "pgn_callback": Optional[Callable]  # For real-time PGN updates
}
```

### Input (for `investigate_move`)

```python
{
    "fen": str,
    "move_san": str,  # "Nf3"
    "follow_pv": bool,  # Default: True
    "depth": int,  # Default: 12
    "focus": Optional[str]
}
```

### Output: `InvestigationResult`

```python
@dataclass
class InvestigationResult:
    # Position facts
    eval_before: Optional[float]  # In pawns
    eval_after: Optional[float]
    eval_drop: Optional[float]
    
    # Move facts
    player_move: Optional[str]  # SAN notation
    best_move: Optional[str]  # UCI notation
    missed_move: Optional[str]  # SAN notation
    
    # Classification (enums, not prose)
    primary_failure: Optional[str]  # "missed_opponent_critical_move", etc.
    mistake_type: Optional[str]  # "calculation_failure", "positional_mistake", etc.
    move_intent: Optional[str]  # "tactical", "positional_improvement", etc.
    game_phase: Optional[str]  # "opening", "middlegame", "endgame"
    
    # Tactical facts
    tactics_found: List[Dict[str, Any]]
    threats: List[Dict[str, Any]]
    
    # Delta facts
    material_change: Optional[float]
    positional_change: Optional[float]
    consequences: Dict[str, Any]  # Doubled pawns, pins, etc.
    
    # Two-move tactical scanner
    two_move_tactics: Optional[TwoMoveWinResult]
    
    # Light raw analysis (themes + tags)
    light_raw_analysis: Optional[LightRawAnalysis]
    
    # Dual-depth analysis
    eval_d16: Optional[float]  # Deep evaluation (ground truth)
    best_move_d16: Optional[str]  # UCI
    eval_d2: Optional[float]  # Shallow evaluation
    is_critical: Optional[bool]  # True if cp loss > 50
    is_winning: Optional[bool]  # True if best/second best have different signs
    overestimated_moves: List[str]  # Moves overestimated by D2
    
    # Multi-branched exploration
    exploration_tree: Dict[str, Any]  # Tree structure
    pgn_exploration: str  # Massive PGN with all branches, themes, tactics, tag deltas
    themes_identified: List[str]
    commentary: Dict[str, str]  # Move-by-move commentary
```

### Key Methods

#### `investigate_position(fen, depth, focus, scope, pgn_callback) -> InvestigationResult`

**Process:**
1. Runs `TwoMoveWinEngine.scan_two_move_tactics()` - Fast tactical scanner
2. Runs `compute_light_raw_analysis()` - Themes and tags detection
3. Runs D16 analysis (depth 16) with `get_top_2=True` - Deep evaluation
4. Runs D2 analysis (depth 2) - Shallow evaluation
5. Finds overestimated moves (moves where D2 > D16)
6. Recursively explores branches for overestimated moves
7. Builds exploration PGN with:
   - Starting position tags: `[Starting tags: tag1, tag2, ...]`
   - Per-move annotations: `[%eval +1.17] [%theme "center_space"] [%tactic "none"]`
   - Per-move tag deltas: `{[gained: tag1, tag2], [lost: tag3], [two_move: tactic1]}`
8. Generates commentary dictionary

**PGN Format:**
```
[Event "Investigation"]
[FEN "rn2kbnr/ppp1pppp/8/4q3/6b1/2N5/PPPPBPPP/R1BQK1NR w KQkq - 4 5"]

{ [Starting tags: tag.king.file.semi, tag.center.control.near, ...] }
5. d4
{ [%eval +1.17] [%theme "center_space,piece_activity"] [%tactic "none"] {[gained: tag.diagonal.open.c1-h6, tag.piece.overworked.d1], [lost: tag.center.control.near, tag.space.advantage], [two_move: closed_capture:g7xh6(+2)] }
5... Bxe2
{ [%eval +0.94] [%theme "center_space,piece_activity"] [%tactic "none"] {[gained: tag.center.control.near, tag.space.advantage], [lost: tag.diagonal.open.g4-c8], [two_move: closed_capture:d4xe5(+8)] }
...
```

#### `investigate_move(fen, move_san, follow_pv, depth, focus) -> InvestigationResult`

**Process:**
1. Sets board to FEN
2. Validates move is legal
3. Plays the move
4. Runs D16 analysis on position before move
5. Runs D16 analysis on position after move
6. Calculates eval drop
7. Classifies move (tactical, positional, etc.)
8. Detects consequences (allows_captures, creates_doubled_pawns, etc.)
9. Returns `InvestigationResult` with move-specific facts

### Two-Move Win Engine

**Location:** `backend/two_move_win_engine.py`

**Purpose:** Fast tactical scanner that validates tactics within 1-2 moves.

**Key Features:**
- **Tactic Validator:** Not a pattern enumerator - validates that tactics survive opponent's best reply
- **Validation Pipeline:**
  1. Simulates the tactic
  2. Enumerates opponent's best replies (captures, counter-checks, trades, interpositions)
  3. Resolves capture chains completely
  4. Evaluates outcome based on material balance and forced mate rules
- **Strict Rules:**
  - Rejects if: equal trades, loses attacking piece, depends on opponent error, unclear outcome
  - Accepts if: wins material, forces favorable exchange, forced mate, unavoidable promotion/check

**Returns:** `TwoMoveWinResult` with:
- `open_tactics`: Valid tactics available
- `blocked_tactics`: Tactics blocked by opponent
- `open_captures`: Valid captures available
- `closed_captures`: Captures that require setup
- `promotions`: Promotion opportunities
- `checkmates`: Mate in 1-2 moves
- `mate_patterns`: Mate patterns detected

### Light Raw Analyzer

**Location:** `backend/light_raw_analyzer.py`

**Purpose:** Fast positional analysis providing themes and tags without full piece profiling.

**Returns:** `LightRawAnalysis` with:
- `themes`: Dictionary of theme scores (center_space, piece_activity, etc.)
- `tags`: List of positional tags (tag.king.file.semi, tag.piece.overworked.d1, etc.)
- `roles`: Dict mapping piece_id -> list of role strings (NEW - see Roles section below)
- `top_themes`: Top 5 themes by score
- `material_balance_cp`: Material balance in centipawns
- `material_advantage`: "white" | "black" | "equal"
- `theme_scores`: Dict of theme scores per side

**Tag Categories:**
- **King Safety:** `tag.king.file.semi`, `tag.king.attackers.count`, `tag.king.defenders.count`, `tag.king.shield.intact`, `tag.king.shield.missing.f`
- **Tactical:** `tag.piece.overworked.d1`, `tag.pin`, `tag.fork`, `tag.skewer`
- **Structural:** `tag.pawn.doubled`, `tag.pawn.isolated`, `tag.pawn.passed`
- **Positional:** `tag.center.control.core`, `tag.center.control.near`, `tag.space.advantage`, `tag.key.d4`, `tag.key.e5`
- **Activity:** `tag.activity.mobility.knight`, `tag.activity.mobility.bishop`
- **Files/Diagonals:** `tag.file.semi.d`, `tag.diagonal.open.e2-a6`, `tag.diagonal.open.g4-c8`

### Piece Roles System

**Location:** `backend/role_detector.py`

**Purpose:** Assign deterministic, action-oriented roles to pieces to complement the tag system. Roles describe what pieces are actively doing, improving mechanism selection and causal explanations.

**Enhanced Features:**
- **Fork Quality Assessment:** Uses d2/d16 PGN exploration to determine if forks are refuted by intermediate saving moves
- **Attack/Defense Counting:** Counts simultaneous attacks and defenses with material values
- **Capture Chain Resolution:** Improved capture chain resolution with minimum-loss calculation
- **Overworked Piece Detection:** Detects pieces defending multiple targets that cannot be defended sequentially

**Role Categories (~40 roles):**

**Attacking Roles:**
- `role.attacking.piece` - Attacking enemy pieces
- `role.attacking.undefended_piece` - Attacking undefended pieces
- `role.attacking.overloaded_piece` - Attacking overloaded defenders
- `role.attacking.king` - Attacking king zone
- `role.attacking.through_pin` - Attacking through pin
- `role.attacking.through_xray` - Attacking through x-ray

**Defensive Roles:**
- `role.defending.piece` - Defending friendly pieces
- `role.defending.multiple` - Defending multiple pieces
- `role.defending.king` - Defending king zone
- `role.defending.pawn_chain` - Defending pawn chain
- `role.defending.overworked` - Overworked defender (NEW)
- `role.defending.over_defended` - Over-defended piece (NEW)

**Tactical Roles:**
- `role.tactical.good_fork` - Non-refuted fork (NEW)
- `role.tactical.refuted_fork` - Fork refuted by intermediate moves (NEW)
- `role.tactical.fork` - Fork opportunity
- `role.tactical.pinned` - Pinned piece
- `role.tactical.skewer` - Skewer pattern

**Status Roles:**
- `role.status.hanging` - Hanging piece (no defenders, under attack) (NEW)
- `role.status.over_defended` - Over-defended piece (NEW)
- `role.status.under_defended` - Under-defended piece (NEW)

**Other Roles:**
- `role.exchange.tension` - Mutual attacks
- `role.activating` - Piece mobility increased
- `role.developing` - Piece developing from starting square
- `role.control.outpost` - Piece on outpost square
- `role.structural.pawn_break_support` - Supporting pawn breaks
- And more...

**Fork Quality Assessment:**
- Leverages d2/d16 PGN exploration to find defensive resources
- Checks if fork is refuted by intermediate saving moves (e.g., one piece flees and defends another)
- Falls back to heuristic validation if PGN unavailable
- Returns `is_good_fork`, `refuted`, `refutation_moves`, `net_material_gain`, `quality_score`

**Attack/Defense Counting:**
- Counts simultaneous attacks and defenses with material values
- Identifies hanging, over-defended, and under-defended pieces
- Returns attackers/defenders with piece values, total attack/defense values, net attack value

**Capture Chain Resolution:**
- Enhanced version with minimum-loss calculation
- Each side chooses lowest-value piece to capture
- Allows choosing not to retake if beneficial
- Returns final material balance, plies played, and move sequence

**Overworked Piece Detection:**
- Detects pieces defending multiple targets that cannot be defended sequentially
- Checks if piece can move between targets to save them all
- Returns list of overworked pieces with vulnerable targets

**Integration:**
- Roles are computed in `compute_light_raw_analysis()` alongside themes and tags
- Roles are used in `Summariser` for mechanism selection and claim summaries
- Roles are used in `Explainer` for board-anchored explanations
- Roles complement tags by providing action-oriented descriptions

### Overworked Pieces Detection (Legacy)

**Location:** `backend/tag_detector.py`

**Purpose:** Detect pieces defending multiple attacked pieces where recapturing one leaves the other undefended.

**Note:** This is now enhanced by the roles system (`role.defending.overworked`) which provides more detailed analysis.

**Process:**
1. Iterates through all pieces
2. Finds what each piece defends
3. Simulates capture of one defended piece
4. Checks if other defended pieces become undefended
5. Returns tags like `tag.piece.overworked.d1`

### Logging

- Logs complete input (FEN, depth, focus, scope, move_san)
- Logs each analysis step (Two-Move Engine, Light Raw, D16, D2)
- Logs exploration progress (branches explored, recursion depth)
- Logs complete output (eval, best_move, overestimated_moves, PGN length, themes)

---

## Layer 5: Summariser

**Purpose:** Take `InvestigationResult` and create `NarrativeDecision` with evidence-locked Claims (editorial framing).

**Location:** `backend/summariser.py`

### Responsibilities

1. **Primary Narrative Selection:** Deterministically selects ONE dominant reason
2. **Tag Ranking & Suppression:** Ranks tags by importance (HIGH > MEDIUM > LOW) and suppresses all but top 2
3. **Claim Creation:** Creates evidence-locked `Claim` objects (structural enforcement of causality)
4. **Evidence Binding:** Deterministically binds move sequences to causal claims (generic, position-agnostic)
5. **Causal Spine Enforcement:** Enforces cause → consequence → lesson chain
6. **Psychological Framing:** Deterministically derives psychological frame (mandatory)
7. **PGN Tag Delta Extraction:** Extracts tag deltas from PGN exploration
8. **Refined PGN Generation:** Creates curated PGN with only relevant branches

### Input

```python
{
    "investigation_result": InvestigationResult,  # Single result
    # OR
    "multiple_results": List[InvestigationResult],  # Comparison mode
    "execution_plan": Optional[ExecutionPlan]
}
```

### Output: `NarrativeDecision`

```python
@dataclass
class Claim:
    """
    Evidence-locked claim abstraction (generic, position-agnostic).
    
    Rules:
    - causal_connector MUST be None unless evidence_moves exists
    - summary MUST make sense without causality
    - Claims are position-agnostic
    """
    summary: str  # Descriptive, non-causal sentence
    causal_connector: Optional[str]  # None | "because" | "allows" | "leads_to" | "causes" | etc.
    evidence_moves: Optional[List[str]]  # SAN moves proving causality (2-4 plies max)
    evidence_source: Optional[str]  # "pv" | "pgn" | "two_move" | "validated"

@dataclass
class NarrativeDecision:
    core_message: str  # One sentence summary
    mechanism: str  # MANDATORY: Concrete board-level mechanism
    mechanism_evidence: Optional[Dict[str, Any]]  # Evidence linking mechanism to source
    claims: List[Claim]  # Evidence-locked claims (replaces free-form causal text)
    emphasis: List[str]  # Max 2 facts to emphasize
    psychological_frame: str  # MANDATORY: "reasonable idea, wrong moment", etc.
    takeaway: Optional[Claim]  # Takeaway as Claim object (allows evidence binding)
    verbosity: str  # "brief" | "medium" | "detailed"
    suppress: List[str]  # Facts to NOT mention (code-enforced, includes all suppressed tags)
    refined_pgn: Optional[RefinedPGN]  # Curated PGN with only relevant branches
```

### Key Methods

#### `summarise(investigation_result, execution_plan) -> NarrativeDecision`

**Process:**

1. **Extract PGN Tag Deltas:**
   - Calls `_extract_tag_deltas_from_pgn(pgn_exploration)`
   - Parses format: `MOVE {[gained: tag1, tag2], [lost: tag3], [two_move: tactic1]}`
   - Uses fallback pattern if main pattern fails: `\{\[gained:\s*([^\]]+)\]\s*,\s*\[lost:\s*([^\]]+)\]\s*,\s*\[two_move:\s*([^\]]+)\]\s*\}`
   - Returns list of moves with their tag deltas

2. **Extract PGN Sequence:**
   - Calls `_extract_pgn_sequence_with_deltas(pgn_exploration)`
   - Extracts starting tags and main sequence of moves with deltas
   - Returns dict with `starting_tags` and `main_sequence`

3. **Extract D2 vs D16 Comparison:**
   - Calls `_extract_d2_vs_d16_comparison(investigation_result)`
   - Determines if D16 move is obvious (D2 matches D16) or not
   - Returns dict with comparison data

4. **Build Facts Dictionary:**
   - Combines all extracted data:
     - `eval_drop`, `mistake_type`, `move_intent`, `game_phase`, `urgency`
     - `tactics_found`, `threats`, `player_move`, `best_move`, `missed_move`
     - `consequences`: From `investigation_result.consequences`
     - `d2_vs_d16`: Comparison data
     - `all_tag_deltas`: All tag changes from PGN (no suppression - LLM decides)
     - `pgn_with_tag_deltas`: Full PGN with tag deltas for LLM reference

5. **Call LLM for Narrative Generation:**
   - Uses LLM with strict rules for generating:
     - `core_message`: ONE clear sentence with CRITICAL move reference rules:
       - If user mentions general goal (e.g., "developing the knight") but no specific move, identify which move they're thinking about
       - Structure options:
         * `'Developing your [piece] is thwarted by [next_move] which [tag_explanation]'`
         * `'Developing your [piece] doesn't work because after [full_PGN_sequence] [outcome_tag_explanation]'`
       - NEVER reference the LAST move in a sequence when explaining why something doesn't work
       - If referencing a single move, it must be the NEXT move the user would play (not the last move)
       - If referencing a sequence, use the full PGN sequence and explain the final outcome
       - Must follow INTENT → MECHANISM → OUTCOME structure
     - `psychological_frame`: How to frame psychologically (encouraging for suggestions, understanding for mistakes)
     - `mechanism`: ONE concrete board-level action from consequences/tags
     - `selected_tags`: 2-5 most relevant tags that support the narrative (LLM chooses contextually)
     - `suppressed_tags`: All tags NOT in selected_tags (for code enforcement)
     - `claims`: 1-3 claims with summary, claim_type, connector, evidence_moves, reason
     - `pgn_sequences_to_extract`: 2-3 sequences that PROVE the narrative
     - `emphasis`: Max 2 items (primary_narrative and one key consequence)
     - `takeaway`: One concrete, actionable lesson (non-causal)
     - `verbosity`: "brief" | "medium" | "detailed"
   - LLM returns JSON with all generated values

6. **Extract LLM-Generated Values:**
   - Parses LLM response to extract:
     - `llm_core_message`, `llm_psychological_frame`, `llm_mechanism`
     - `llm_selected_tags`, `llm_suppressed_tags`
     - `llm_claims` (list of claim dicts)
     - `pgn_sequences_to_extract` (list of sequence dicts)
   - Uses LLM values with deterministic fallbacks if missing

7. **Process Claims:**
   - For each LLM-generated claim:
     - Extracts summary, claim_type, connector, evidence_moves, reason
     - If `evidence_moves` provided by LLM, uses them
     - Otherwise, calls `_bind_evidence_to_claim()` to attempt evidence binding
     - Searches for evidence in priority order:
       1. Refined PGN (if available)
       2. Full PGN exploration
       3. Principal variation from engine analysis
       4. Two-move engine validated sequences
       5. Short validated legal line (2-4 plies max)
     - If evidence found: Creates Claim with `causal_connector` and `evidence_moves`
     - If no evidence: Creates Claim with `causal_connector=None` (mandatory downgrade)
   - Creates takeaway as Claim object (allows evidence binding)

8. **Validate Output:**
    - Ensures `emphasis` contains at most 2 items
    - Ensures `psychological_frame` is always set (uses LLM value with deterministic fallback)
    - Ensures `suppress` list includes all LLM-suppressed tags (code-enforced)
    - Ensures `mechanism` is always set (uses LLM value with deterministic fallback)
    - Ensures `core_message` follows move reference rules (next move, not last move)

9. **Build Refined PGN:**
    - Uses `pgn_sequences_to_extract` from LLM (if available) to select relevant sequences
    - If LLM sequences not available, falls back to deterministic scoring method
    - Calls `_build_refined_pgn(exploration_tree, selected_branches, investigation_result)`
    - Selects only relevant branches based on LLM-selected sequences or scoring
    - Creates curated PGN with annotations and commentary
    - Returns `RefinedPGN` object

### Tag Delta Extraction

**Method:** `_extract_tag_deltas_from_pgn(pgn_exploration) -> List[Dict[str, Any]]`

**Process:**
1. Tries main pattern: `r'(\d+\.\s*(?:\.\.\.\s*)?\S+)\s+(?:[^\{\n]*?\s+)?\{\[gained:\s*([^\]]+)\],\s*\[lost:\s*([^\]]+)\],\s*\[two_move:\s*([^\]]+)\]\}'`
2. If no matches, uses fallback pattern: `r'\{\[gained:\s*([^\]]+)\]\s*,\s*\[lost:\s*([^\]]+)\]\s*,\s*\[two_move:\s*([^\]]+)\]\s*\}'`
3. For each match:
   - Finds outer comment block (handles nested braces)
   - Looks backwards for move on previous line(s)
   - Extracts `gained`, `lost`, `two_move` values
   - Parses tags (handles "none" and "+X more" truncation)
4. Returns list of dicts: `[{"move": "5. d4", "tags_gained": [...], "tags_lost": [...], "two_move_output": [...]}, ...]`

### LLM-Based Generation (New)

**Method:** LLM generates core_message, mechanism, psychological_frame, selected_tags, suppressed_tags, claims, and PGN sequences

**Key Rules for Core Message:**
1. **General Goal Detection:** If user mentions a general goal (e.g., "developing the knight", "castling") but no specific move, the LLM must identify which move they're thinking about
2. **Move Reference Structure:**
   - Option A: `'Developing your [piece] is thwarted by [next_move] which [tag_explanation]'`
   - Option B: `'Developing your [piece] doesn't work because after [full_PGN_sequence] [outcome_tag_explanation]'`
3. **Never Reference Last Move:** When explaining why something doesn't work, NEVER reference the last move in a sequence (e.g., don't say "Qxe2" if the sequence is "Bxe2 Qxe2")
4. **Single Move Reference:** If referencing a single move, it must be the NEXT move the user would play (not the last move in the sequence)
5. **Full Sequence Reference:** If referencing a sequence, use the full PGN sequence and explain the final outcome with tag-based explanation

**Examples:**
- ✅ Correct: "Developing your knight is thwarted by Bxe2, which allows opponent to capture with advantage"
- ✅ Correct: "Developing your knight doesn't work because after Bxe2 Qxe2 Qa5 the king recaptures in the center, exposing it to attack"
- ❌ Wrong: "The move Qxe2 allows opponent captures" (Qxe2 is the last move, not the next move)

**Tag Selection:**
- LLM selects 2-5 most relevant tags based on narrative context
- Not based on HIGH/MEDIUM/LOW hierarchy - based on what supports the narrative
- All other tags are suppressed (code-enforced)
- Example from logs: Selected tags support "allows opponent captures" narrative (line 624)

**Claim Generation:**
- LLM generates claim summaries, claim_type, and connectors
- Evidence moves can be provided by LLM or bound deterministically
- If LLM provides evidence_moves, they are used (must be from PGN/PV)
- Example from logs: Claim with evidence_moves=["Bxe2", "Ngxe2"] (line 618 - full sequence, not just last move)
- Otherwise, `_bind_evidence_to_claim()` attempts to find evidence

**PGN Sequence Selection:**
- LLM selects 2-3 sequences that PROVE the narrative
- Each sequence has start_move, end_move, reason, and proves fields
- If LLM sequences are extracted successfully, they are used for PGN curation
- Otherwise, falls back to deterministic scoring method
- Example from logs: PGN sequence extraction attempted but failed, fell back to scoring (line 607)

### Evidence Binding

**Method:** `_bind_evidence_to_claim(summary, causal_connector, investigation_result) -> Claim`

**Purpose:** Deterministically bind evidence to a claim summary (generic, position-agnostic).

**Process:**
1. Searches for evidence in priority order:
   - **Priority 1:** PGN exploration (extracts first valid sequence of 2-4 plies)
   - **Priority 2:** PV sequences from `pv_after_move`
   - **Priority 3:** PV sequences from `exploration_tree` (recursive search)
   - **Priority 4:** Two-move tactics sequences (open_tactics or open_captures)
2. If evidence found and `causal_connector` provided:
   - Returns `Claim` with `causal_connector`, `evidence_moves`, and `evidence_source`
3. If no evidence found:
   - Returns `Claim` with `causal_connector=None` (mandatory downgrade to non-causal)

**Rules:**
- All logic is generic and position-agnostic (no hard-coded moves, squares, or pieces)
- Evidence must be 2-4 plies max
- Evidence must come from existing analysis output (no invention)

### Claim Creation

**Method:** `_create_claims_from_text(text, investigation_result, claim_type) -> List[Claim]`

**Purpose:** Create Claim objects from text that may contain causal language.

**Process:**
1. Detects causal connectors in text using regex patterns:
   - `because`, `allows`, `leads to`, `causes`, `resulting in`, `therefore`, `so that`, `which means`
2. For each causal connector found:
   - Extracts summary (full text)
   - Calls `_bind_evidence_to_claim()` to attempt evidence binding
   - Creates Claim object (with or without causality based on evidence availability)
3. Returns list of Claim objects

**Rules:**
- If evidence not found, Claim is automatically downgraded to non-causal
- All Claims are position-agnostic

### Logging

- Logs complete input (mode, multiple_results count, eval values, force_suggestion detection)
- Logs scoring function breakdown (for suggestion mode: base, boost, penalty, bonus, final score)
- Logs tag extraction results (matches found, moves extracted)
- Logs LLM-generated values (core_message, mechanism, selected_tags, suppressed_tags, claims)
- Logs PGN sequence extraction (LLM-selected sequences, extraction success/failure)
- Logs complete output (core_message, emphasis, psychological_frame, suppress list length, refined PGN length)

---

## Layer 5: Explainer

**Purpose:** Generate natural language explanation from `NarrativeDecision` and `InvestigationResult`, rendering Claims literally. Must expand skeleton into full explanation (not just repeat verbatim).

**Location:** `backend/explainer.py`

### Responsibilities

1. **Skeleton Expansion:** Expands narrative skeleton into full, fluent explanation (MANDATORY - not just verbatim repetition)
2. **Claim Rendering:** Renders Claim objects literally (NO rephrasing into causal sentences)
3. **Language Generation:** Converts narrative decisions to fluent prose with proper flow
4. **Strict Adherence:** Follows narrative exactly - NO new analysis, NO invented causality
5. **PGN Processing:** Extracts and references PGN comments
6. **Verbosity Control:** Adjusts length based on `verbosity` setting (should be ~1.5-2x skeleton length)
7. **Post-Render Validation:** Enforces evidence-locked causality (mandatory validator)
8. **Board Contact:** Ensures explanation includes concrete move sequences (SAN moves)

### Input

```python
{
    "narrative_decision": NarrativeDecision,
    "investigation_facts": InvestigationResult | Dict,  # Single result or comparison
    "user_message": str
}
```

### Output

```python
str  # Natural language explanation
```

### Key Methods

#### `explain(narrative_decision, investigation_facts, user_message) -> str`

**Process:**

1. **Extract PGN:**
   - Uses `refined_pgn` if available (from `NarrativeDecision`)
   - Otherwise uses `pgn_exploration` from `InvestigationResult`
   - Parses PGN to extract comments with move paths

2. **Build Facts Summary:**
   - For single result: Calls `_build_facts_summary(investigation_result)`
   - For comparison: Calls `_build_comparison_facts_summary(multiple_results)`
   - Formats structured facts for LLM

3. **Build Prompt:**
   - Uses `EXPLAINER_SYSTEM_PROMPT` with strict rules:
     - **FORBIDDEN:** Reanalysis, contradictions, new ideas, chess analysis
     - **REQUIRED:** Follow narrative exactly, use psychological frame
     - **INPUTS:** `NARRATIVE DECISION`, `INVESTIGATION FACTS`, `PGN COMMENTS`
     - **RULES:** Build explanation following narrative structure

4. **Build Claims Section:**
   - Formats Claims for prompt:
     - If Claim has `causal_connector` and `evidence_moves`: Shows summary + connector + evidence
     - If Claim has no `causal_connector`: Shows summary only (non-causal)
   - Formats takeaway Claim similarly

5. **Call LLM:**
   - Uses GPT-4o to generate explanation
   - **CRITICAL:** The skeleton is a TEMPLATE - must be expanded into a full, fluent explanation
   - **FORBIDDEN:** Repeating skeleton verbatim without expansion
   - **REQUIRED:** Generate at least 2-3 sentences connecting mechanism to user's goal
   - **REQUIRED:** Use investigation facts for details and concrete examples
   - Prompt includes strict CLAIM RENDERING RULES:
     - **FORBIDDEN:** Rephrasing claims into new causal sentences
     - **FORBIDDEN:** Introducing "because / leads to / results in" on its own
     - **FORBIDDEN:** Converting non-causal summaries into causal explanations
     - **REQUIRED:** Render each Claim exactly as provided
     - **REQUIRED:** Include evidence inline if causal_connector is present
   - Adjusts verbosity based on `verbosity` setting:
     - `"brief"`: 2-3 sentences (but must still expand skeleton)
     - `"medium"`: 4-6 sentences (should be ~1.5-2x skeleton length)
     - `"detailed"`: 7+ sentences (should be ~2-3x skeleton length)
   - Example from logs: Skeleton was 454 chars, response was 524 chars (line 692-695) - warning logged that response is shorter than expected (~1.15x, should be ~1.5-2x)

6. **Post-Render Validation (MANDATORY):**
   - Calls `_enforce_causal_claim_evidence(explanation, claims)`
   - Scans for causal connectors: `because`, `allows`, `leads to`, `causes`, `results in`, `therefore`, `so that`, `which means`, `affects`
   - For each occurrence:
     - Verifies that a SAN move sequence appears within next 200 characters
     - Checks for evidence patterns: "for example:", "(e.g.,", "for instance:", etc.
     - Checks for SAN move patterns
   - If any causal connector lacks nearby evidence:
     - Attempts to inject evidence from matching Claim
     - If no matching Claim found: Re-renders using only non-causal Claim summaries
     - If no Claim summaries available: Rewrites sentence to non-causal (generic replacements)
   - Returns validated explanation

7. **Return Explanation:**
   - Returns natural language string with evidence for all causal claims
   - All causal language is structurally enforced to have evidence

### PGN Comment Extraction

**Process:**
1. Parses PGN using `chess.pgn.read_game()`
2. Traverses main line and variations
3. Extracts comments with move paths
4. Formats as: `"- d4 -> Best move (D16). Themes: center_space, piece_activity."`
5. Includes in prompt for LLM reference

### Logging

- Logs complete input (user_message, narrative_decision, investigation_facts type)
- Logs skeleton analysis (length, preview, number of claims, core message, mechanism, psychological frame)
- Logs renderer statistics (claims with connectors, claims with evidence, skeleton contains inline SAN)
- Logs LLM response analysis (response length, preview, comparison to skeleton length)
- Logs warnings if response is shorter than expected (should be ~1.5-2x skeleton length)
- Logs complete output (explanation length, preview)

---

## Data Flow Example

### Example: User asks "I want to eventually castle but I'm not sure how, especially since it's awkward for me to develop my knight out"

**Step 1: Interpreter**
- **Input:** Message + context (FEN, PGN, mode)
- **Output:** `IntentPlan` with:
  - `intent: "position_analysis"`
  - `scope: "current_position"`
  - `goal: "find_best_move"`
  - `investigation_required: True`
  - `investigation_type: "position"`
  - `investigation_requests: [AnalysisRequest(type="position", focus=None)]`

**Step 2: Planner**
- **Input:** `IntentPlan` + context
- **Output:** `ExecutionPlan` with:
  - `steps: [ExecutionStep(action_type="investigate_position", ...), ExecutionStep(action_type="investigate_move", move_san="Nf3", ...), ExecutionStep(action_type="synthesize"), ExecutionStep(action_type="answer")]`

**Step 3: Executor**
- **Input:** `ExecutionPlan` + context
- **Process:**
  1. Executes step 1: Calls `investigator.investigate_position(fen, depth=18, focus=None)`
  2. Executes step 2: Calls `investigator.investigate_move(fen, move_san="Nf3", depth=12)`
  3. Executes step 3: Returns `{"synthesis_ready": True, "results": {...}}`
  4. Executes step 4: Returns `{"answer_ready": True}`
- **Output:** `{results: {1: InvestigationResult, 2: InvestigationResult, ...}}`

**Step 4: Investigator (called by Executor)**
- **For `investigate_position`:**
  - Runs Two-Move Win Engine → Finds 0 open tactics
  - Runs Light Raw Analysis → Finds 27 tags, 5 themes
  - Runs D16 analysis → Eval: +1.17, Best move: h2h3
  - Runs D2 analysis → Eval: +0.99
  - Finds 2 overestimated moves: ["d4", "Bxe2"]
  - Recursively explores branches
  - Builds PGN with tag deltas: `5. d4 {[gained: tag.diagonal.open.c1-h6, tag.piece.overworked.d1], [lost: tag.center.control.near, tag.space.advantage], [two_move: closed_capture:g7xh6(+2)]}`
  - Returns `InvestigationResult` with `pgn_exploration`, `themes_identified`, `light_raw_analysis`, etc.

- **For `investigate_move`:**
  - Sets board to FEN
  - Plays Nf3
  - Runs D16 before: Eval: +0.98
  - Runs D16 after: Eval: +0.51
  - Calculates eval_drop: -0.47
  - Classifies move_intent: "tactical"
  - Detects consequences: ["allows_captures"]
  - Returns `InvestigationResult` with move-specific facts

**Step 5: Summariser**
- **Input:** Multiple `InvestigationResult` objects (comparison mode)
- **Process:**
  1. Extracts tag deltas from PGN: Finds 25 matches
  2. Extracts PGN sequence: Gets starting tags and main sequence
  3. Extracts D2 vs D16: Determines if move is obvious
  4. Selects primary narrative: `"positional_concession_without_compensation"`
  5. Ranks tags: Finds 103 tags, selects 2 (tag.king.shield.intact, tag.king.file.semi), suppresses 101
  6. Selects psychological frame: `"reasonable idea, wrong moment"`
  7. Selects mechanism: `"allows opponent to damage your pawn structure"` with evidence from consequences
  8. Creates Claims:
     - Detects causal language in mechanism/core_message/takeaway
     - For each causal connector found:
       - Searches for evidence in PGN/PV/two_move data
       - If evidence found: Creates Claim with `causal_connector` and `evidence_moves`
       - If no evidence: Creates Claim with `causal_connector=None` (mandatory downgrade)
     - Example Claim: `Claim(summary="This move is problematic", causal_connector="allows", evidence_moves=["Bxf3", "gxf3"], evidence_source="pgn")`
  9. Calls LLM with facts and narrative structure
  10. Validates output
  11. Builds refined PGN
- **Output:** `NarrativeDecision` with:
  - `core_message: "The player intended to strengthen their position with 5. d4, but this move allowed for a significant positional concession without compensation..."`
  - `mechanism: "allows opponent to damage your pawn structure"`
  - `claims: [Claim(summary="...", causal_connector="allows", evidence_moves=["Bxf3", "gxf3"], ...), ...]`
  - `emphasis: ["positional_concession_without_compensation", "tag.king.file.semi"]`
  - `psychological_frame: "reasonable idea, wrong moment"`
  - `takeaway: Claim(summary="...", causal_connector=None, ...)` (non-causal if no evidence)
  - `suppress: ["lost:tag.diagonal.open.g4-c8@5. d4", ...]` (17+ tags)
  - `refined_pgn: RefinedPGN(...)`

**Step 6: Explainer**
- **Input:** `NarrativeDecision` + `InvestigationResult` + user_message
- **Process:**
  1. Extracts PGN comments
  2. Builds facts summary
  3. Formats Claims for prompt (shows evidence inline for causal Claims)
  4. Calls LLM with narrative decision, facts, and Claims
  5. LLM generates explanation, rendering Claims literally
  6. Post-render validation:
     - Scans for causal connectors in generated text
     - Verifies SAN move sequences appear within 200 characters
     - If evidence missing: Re-renders using non-causal Claim summaries or rewrites to non-causal
- **Output:** `"Hello! It's great that you're thinking about castling, as it's a key part of ensuring your king's safety... In the current position, playing 5. d4 might seem like a reasonable tactical idea, but it allows Bxf3 gxf3, which came at a cost to your positional strength, reducing your advantage and weakening your control of the semi-open king file..."` (all causal language has evidence)

---

## Key Design Principles

### 1. Separation of Concerns

- **Interpreter:** Intent classification only
- **Planner:** Step generation only
- **Executor:** Step execution only
- **Investigator:** Chess analysis only (NO prose)
- **Summariser:** Editorial decisions only (NO analysis)
- **Explainer:** Language generation only (NO analysis)

### 2. Structured Data Flow

- Each layer outputs structured data (dataclasses, dicts)
- NO prose until Explainer layer
- Clear contracts between layers

### 3. Deterministic Where Possible

- **Summariser:** Primary narrative selection is deterministic
- **Summariser:** Tag ranking is deterministic (HIGH > MEDIUM > LOW)
- **Summariser:** Psychological frame selection is deterministic
- **Investigator:** Analysis is deterministic (engine-based)

### 4. LLM Usage

- **Interpreter:** Uses LLM for intent classification
- **Planner:** Uses LLM for step generation
- **Summariser:** Uses LLM for narrative building (with strict constraints)
- **Explainer:** Uses LLM for language generation (with strict constraints)

### 5. Error Handling

- Each layer has defensive `None` checks
- Executor ensures `executor_result` is always a dict
- Investigator handles invalid moves gracefully
- Summariser validates LLM output

### 6. Logging

- Complete input/output logging for each layer
- Debug logging for tag extraction and suppression
- Reduced logging for profile-related endpoints
- `sys.stdout.flush()` to ensure immediate visibility

---

## Recent Improvements

### Planner Candidate Enforcement (Dec 2025)

- Planner now gates auto-added move investigations through engine-quality filters. When the user does **not** name specific moves, `_auto_add_candidate_moves` first tries to reuse cached Stockfish candidates that match the current FEN, dedupes them, then keeps only the lines that stay within **120 cp** of the top score (always normalized to White’s perspective).
- If no cached candidates survive, the planner probes Stockfish once (depth 16, multi-PV) and applies the same drop-threshold filter before inserting a single `investigate_move` step. Blunder candidates like `Bxf7+` or `Nxd4` are therefore skipped automatically unless the requester explicitly asked for them.
- Logged output makes the enforcement explicit: `✅ [PLANNER] Enforcing engine move policy: ['c3']` when cache hits, or a warning if no candidates are available.

### Evidence-Locked Causality System (Major Upgrade)

- **Problem:** System produced causal explanations ("because", "leads to", "causes") without demonstrating causality via concrete moves
- **Solution:** Introduced `Claim` dataclass with structural enforcement:
  - `Claim` objects require `evidence_moves` for any `causal_connector`
  - Summariser creates Claims with deterministic evidence binding
  - Explainer renders Claims literally (forbidden from inventing causality)
  - Post-render validator enforces evidence requirement (rejects or downgrades if missing)
- **Result:** System cannot output causal explanations without move evidence; every "because / leads to / causes" is immediately justified by SAN moves

### Claim-Based Architecture

- **Enhancement:** Replaced free-form causal text with `Claim` objects
- **Structure:**
  - `summary`: Non-causal descriptive sentence
  - `causal_connector`: Optional ("because", "allows", "leads_to", etc.)
  - `evidence_moves`: SAN moves proving causality (2-4 plies max)
  - `evidence_source`: "pv" | "pgn" | "two_move" | "validated"
- **Rules:**
  - `causal_connector` MUST be None unless `evidence_moves` exists
  - All logic is generic and position-agnostic (no hard-coded examples)
  - Mandatory downgrade to non-causal if evidence not found

### Evidence Binding (Deterministic)

- **Enhancement:** Generic, position-agnostic evidence extraction
- **Priority Order:**
  1. Refined PGN (if available)
  2. Full PGN exploration
  3. Principal variation from engine analysis
  4. Two-move engine validated sequences
  5. Short validated legal line (2-4 plies max)
- **Result:** Evidence binding works for all chess positions, not specific test cases

### Post-Render Validator (Strict)

- **Enhancement:** Mandatory validator that scans for causal connectors and verifies evidence
- **Process:**
  - Scans for causal connectors in generated text
  - Verifies SAN move sequences appear within 200 characters
  - If evidence missing: Re-renders using non-causal Claim summaries or rewrites to non-causal
- **Result:** System becomes provably resistant to hand-wavy explanations

### Tag Delta Extraction (Fixed)

- **Problem:** Regex pattern wasn't matching PGN format with nested braces
- **Solution:** Added flexible whitespace handling: `\s*` after each `\]`
- **Result:** Now extracts 25+ tag deltas successfully

### Tag Ranking & Suppression (Working)

- **Problem:** `suppress` list was empty
- **Solution:** Fixed tag extraction, now properly ranks and suppresses tags
- **Result:** Selects top 2 tags, suppresses 100+ less important tags

### PGN Format Enhancement

- **Enhancement:** PGN now includes tag deltas for every move
- **Format:** `MOVE {[gained: tag1, tag2], [lost: tag3], [two_move: tactic1]}`
- **Result:** Summariser can now track tag changes throughout the game

### Overworked Pieces Detection

- **Enhancement:** Added detection for pieces defending multiple attacked pieces
- **Tag:** `tag.piece.overworked.d1`
- **Result:** More granular tactical insights

---

## Explicit Causal Hammer Enforcement (Jan 2026)

### Problem

Although the system enforced evidence-locked causality, explanations could still feel vague because causal relationships were implicit. Users could see evaluations and intent, but not always a concrete "this allows that" board sequence.

### Solution

Introduced mandatory board-explicit causal anchoring, ensuring that every non-trivial explanation contains at least one concrete cause → sequence → consequence chain.

### Key Enhancements

#### Mandatory Hammer Claim (Summariser)

- **Requirement:** Every non-trivial `NarrativeDecision` must include at least one Claim that:
  - Uses a causal connector (`allows`, `leads_to`, `causes`, etc.)
  - Includes SAN evidence (2–4 plies)
  - Anchors to a concrete mechanism or consequence

- **Enforcement:**
  - After `_select_mechanism()`, the system scans existing claims for a qualifying hammer claim
  - If none exists, it attempts to synthesize one from:
    - `mechanism`
    - `consequences`
    - `selected_tag_deltas`
  - Uses `_bind_evidence_to_claim()` to attach SAN evidence
  - If evidence binding fails:
    - Explanation is forcibly downgraded to non-causal
    - Verbosity is reduced to "brief"
    - System logs a confidence warning

- **Result:** The system no longer produces causal explanations without board-verifiable proof.

#### Mechanism Anchoring

- **Requirement:** Any selected mechanism must be explicitly referenced by at least one Claim
- **Enforcement:**
  - After claim creation, the system checks if the mechanism appears in any claim's summary
  - If not, it creates a non-causal anchor claim that restates the mechanism
  - Prevents abstract or "floating" mechanisms without board contact

- **Result:** Mechanisms are always grounded in the explanation, never left as abstract labels.

#### Board Contact Requirement (Explainer)

- **Requirement:** Every explanation must contain at least one paragraph that:
  - References SAN moves (2–4 plies)
  - Names the concrete structural or tactical damage (mechanism or tag)

- **Enforcement:**
  - After LLM generation, the system scans output for:
    - SAN regex patterns
    - References to mechanism or selected tags
  - If missing:
    - Injects a paragraph rendered directly from the hammer Claim using `_render_hammer_claim()`
    - Re-runs post-render validation

- **Result:** Every explanation touches the board with concrete move sequences.

#### Canonical Hammer Sentence

- **Format:** `This move allows [SAN sequence], which causes [mechanism].`
- **Rules:**
  - No rephrasing
  - No added analysis
  - Exactly mirrors Claim content

- **Usage:**
  - Injected paragraphs when board contact is missing
  - Low-confidence fallback rendering
  - Ensures clarity, consistency, and zero rhetorical drift

### Result

The system no longer merely describes mistakes — it demonstrates them on the board.

Every causal explanation is now:
- **Verifiable:** Every causal claim has SAN evidence
- **Board-explicit:** Every explanation includes concrete move sequences
- **Impossible to produce without proof:** The system cannot speak causally without evidence

The system has progressed from "can justify its opinions" to "cannot speak causally without proof."

---

## Prompt Reference

For audits that need the literal instructions we give each LLM, see `FOUR_LAYER_PROMPTS.md`. That companion file captures:

- The full `INTERPRETER_SYSTEM_PROMPT`
- The full `PLANNER_SYSTEM_PROMPT`
- Both Summariser prompt templates (comparison mode and single investigation mode)
- The `EXPLAINER_SYSTEM_PROMPT`

All prompt text is copied verbatim from the backend modules, so you can ingest it directly without spelunking through the codebase.

---

## Summary

The 4-layer pipeline (actually 6 components) provides:

1. **Intent Understanding** (Interpreter)
2. **Execution Planning** (Planner)
3. **Step Execution** (Executor)
4. **Chess Analysis** (Investigator)
5. **Editorial Decisions** (Summariser) - Now with LLM-based generation and evidence-locked Claims
6. **Language Generation** (Explainer) - Now with skeleton expansion and strict causal validation

Each layer has clear responsibilities, structured inputs/outputs, and comprehensive logging. The system now:

- **LLM-Based Narrative Generation:** Core message, mechanism, psychological frame, tags, claims, and PGN sequences are generated by LLM (not deterministic)
- **Proper Move References:** When user mentions general goals (e.g., "developing the knight"), system identifies the move and references the NEXT move in sequence (not the last move)
- **Contextual Tag Selection:** LLM selects 2-5 most relevant tags based on narrative context (not just HIGH/MEDIUM/LOW hierarchy)
- **Extracts tag deltas** from PGN and provides all tags to LLM for contextual selection
- **Creates evidence-locked Claims** that structurally enforce causality requirements
- **Binds evidence deterministically** from PV/PGN/two_move data (generic, position-agnostic)
- **Renders Claims literally** without inventing causal language
- **Expands skeletons** into full explanations (not just verbatim repetition)
- **Validates explanations** to ensure all causal claims have supporting move sequences

The system has been upgraded from "sounds right" to "can prove what it says — or stays quiet", making it a serious analytical system rather than a demo. The move to LLM-based generation for narrative decisions allows for more contextually appropriate and user-intent-aware explanations.

