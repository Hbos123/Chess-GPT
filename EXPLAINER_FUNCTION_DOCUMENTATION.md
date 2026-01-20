# Explainer Function Documentation

## Overview

The `Explainer` class is the **Language Engine** layer of the 4-layer pipeline. It takes the `NarrativeDecision` from the `Summariser` and converts it into fluent, natural language explanations without performing any chess analysis.

**Key Principle**: The Explainer is a language engine only - it is NOT allowed to think, reanalyze, or introduce new ideas. It strictly converts the narrative decision into prose.

---

## Function Signature

```python
async def explain(
    self,
    narrative_decision: NarrativeDecision,
    investigation_facts: Any,  # InvestigationResult, dict with multiple_results, or None
    user_message: str
) -> str
```

---

## Input Types

### 1. **NarrativeDecision**
- **Source**: From the `Summariser` layer
- **Contains**:
  - `core_message`: One sentence summary of the dominant reason
  - `emphasis`: List of facts to emphasize (max 2 items)
  - `psychological_frame`: Mandatory framing (e.g., "missed a concrete reply")
  - `takeaway`: One actionable lesson
  - `verbosity`: "brief" | "medium" | "detailed"
  - `suppress`: List of facts to NOT mention
  - `refined_pgn`: Optional curated PGN with only relevant branches

### 2. **InvestigationFacts**
- **Single Result Mode**: `InvestigationResult` object
- **Comparison Mode**: `dict` with `{"comparison_mode": True, "multiple_results": [...]}`
- **None**: Fallback when no investigation facts are available

### 3. **UserMessage**
- Original user question/request
- Used for context and tone

---

## Core Methods

### 1. `explain(narrative_decision, investigation_facts, user_message)`

**Purpose**: Main method that generates fluent explanation from narrative decision.

**Process**:

#### Step 1: Input Logging
Logs all inputs for debugging:
- User message
- Narrative decision components
- Investigation facts type and key fields

#### Step 2: PGN Selection
Selects which PGN to use:
```python
if narrative_decision.refined_pgn:
    pgn_to_use = narrative_decision.refined_pgn.pgn
    pgn_metadata = {
        "key_branches": ...,
        "themes": ...,
        "tactical_highlights": ...,
        "moves_of_interest": ...
    }
elif isinstance(investigation_facts, InvestigationResult):
    pgn_to_use = investigation_facts.pgn_exploration
```

**Priority**: Refined PGN (curated) > Full PGN exploration > None

#### Step 3: Mode Detection
```python
is_comparison = isinstance(investigation_facts, dict) and investigation_facts.get("comparison_mode", False)
```

#### Step 4: Facts Summary Building
- **Single Result**: Calls `_build_facts_summary(investigation_facts)`
- **Comparison**: Calls `_build_comparison_facts_summary(multiple_results)`
- **None**: Returns "No investigation facts available."

#### Step 5: PGN Processing
- Limits PGN to first 2000 characters to avoid token bloat
- Extracts PGN comments using `chess.pgn` parser
- Includes metadata (themes, tactical highlights, key branches)

#### Step 6: Prompt Construction
Builds a comprehensive prompt with:
- User question
- Narrative decision (what to say)
- Investigation facts (what is true)
- PGN analysis (if available)
- Comparison instructions (if comparison mode)
- Critical rules and context usage guidelines

#### Step 7: LLM Call
```python
response = self.client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": prompt}],
    temperature=0.7
)
```

#### Step 8: Output Logging and Return
- Logs explanation length and preview
- Returns the generated explanation
- Falls back to simple message if error occurs

---

### 2. `_build_facts_summary(facts: InvestigationResult) -> str`

**Purpose**: Builds a structured summary of investigation facts for single result mode.

**Extracts and Formats**:
- Evaluation before/after/drop
- Player move, best move, missed move
- Mistake type, move intent, intent mismatch
- Game phase, urgency
- Tactics found (with details)
- Consequences (formatted as key-value pairs)
- Material and positional changes
- Two-move tactical analysis (if available)
- Light raw analysis themes and tags
- Critical/winning move information
- Commentary from exploration
- Overestimated moves

**Example Output**:
```
- Position evaluation before: +0.50 pawns
- Position evaluation after: +0.03 pawns
- Evaluation change: -0.47 pawns
- Move played: Nf3
- Best move: d4
- Missed move: d4
- Mistake type: mistake
- Move intent: develop knight
- Intent mismatch: True
- Game phase: opening
- Urgency: medium
- Tactics found: 1
  * fork: {...}
- Consequences: doubled_pawns: True, allows_captures: True
- Material change: 0.00 pawns
- Positional change: -47.00 centipawns
- Two-move tactical scan: 2 open tactics, 1 capture opportunity
- Positional themes: center_space, piece_activity
- Positional tags: tag.center.control, tag.space.advantage
- Critical decision: d4 vs Nf3 (centipawn difference: 47)
- Move commentary available for 3 moves
  * d4: Best move (D16). Themes: center_space, piece_activity.
  * Nf3: Continuation: Nf3. Themes: piece_activity.
  * Bxe2: Continuation: Bxe2. Creates doubled pawns.
- Moves overestimated by shallow analysis: Nf3, h3
```

---

### 3. `_build_comparison_facts_summary(multiple_results: list) -> str`

**Purpose**: Builds a structured summary for comparison mode (multiple investigation results).

**Process**:
- Iterates through each result in `multiple_results`
- For each result:
  - Extracts focus from investigation request
  - Builds summary similar to single result
  - Groups by focus (e.g., "KNIGHT", "BISHOP")

**Example Output**:
```
--- KNIGHT ---
- Evaluation before: +0.50 pawns
- Evaluation after: +0.03 pawns
- Evaluation change: -0.47 pawns
- Move: Nf3
- Best move: d4
- Mistake type: mistake
- Move intent: develop knight
- Game phase: opening
- Urgency: medium
- Tactics found: 1
- Material change: 0.00 pawns
- Positional change: -47.00 centipawns

--- BISHOP ---
- Evaluation before: +0.50 pawns
- Evaluation after: +0.45 pawns
- Evaluation change: -0.05 pawns
- Move: Bc4
- Best move: d4
- Mistake type: inaccuracy
- Move intent: develop bishop
- Game phase: opening
- Urgency: medium
- Tactics found: 0
- Material change: 0.00 pawns
- Positional change: -5.00 centipawns
```

---

### 4. `explain_simple(user_message, context)`

**Purpose**: Simple explanation for non-investigation requests (general chat).

**Use Case**: When the request doesn't go through the full pipeline (e.g., general chess questions, rules explanations).

**Process**:
- Formats context using `_format_context()`
- Builds simple prompt
- Calls LLM with `gpt-4o`
- Returns conversational response

---

### 5. `_format_context(context: Dict[str, Any]) -> str`

**Purpose**: Formats context dictionary for simple explanations.

**Extracts**:
- FEN (current position)
- Mode (game mode)
- PGN (if available)

---

## Prompt Structure

### Main Prompt Template

```
You are a chess coach explaining conclusions that have already been reached.

USER QUESTION: {user_message}

NARRATIVE DECISION (what to say):
- Core message: {core_message}
- Emphasis: {emphasis}
- Frame: {psychological_frame}
- Takeaway: {takeaway}
- Verbosity: {verbosity}

INVESTIGATION FACTS (what is true):
{facts_summary}

{pgn_section}

{comparison_instruction}

YOUR TASK:
Turn this narrative decision into a fluent, human explanation.

CRITICAL RULES:
1. You are NOT allowed to introduce new analysis
2. You are NOT allowed to speculate
3. Only explain what is provided
4. Use natural language and coaching tone
5. Reference the facts provided
6. Follow the narrative decision exactly
7. If verbosity is "brief", keep it short (2-3 sentences)
8. If verbosity is "detailed", provide more context
9. Do NOT mention moves not in the investigation facts
10. Do NOT contradict the narrative decision
11. If comparing, structure as a clear comparison with contrasts

CONTEXT USAGE GUIDELINES:
- If consequences are listed, explain what they mean and why they matter
- If tactics are found, describe the tactical opportunities or threats
- If themes are identified, explain how they relate to the position
- If commentary exists in PGN, use it to provide move-by-move insights
- If eval_drop is significant, explain the evaluation change in terms of the consequences and tactics found
- If critical/winning move information is present, explain why the move choice is critical
- Always connect evaluation changes to concrete factors (tactics, consequences, themes)

Generate the explanation:
```

---

## Critical Rules

### 1. **No New Analysis**
- The Explainer must NOT introduce new chess ideas
- It must NOT reanalyze the position
- It must NOT contradict the narrative decision

### 2. **Strict Adherence to Narrative Decision**
- Must follow `core_message` exactly
- Must emphasize items in `emphasis` list
- Must use `psychological_frame` for framing
- Must respect `verbosity` level
- Must NOT mention items in `suppress` list

### 3. **Facts-Based Explanation**
- Only explain what is provided in `investigation_facts`
- Reference specific facts (evaluations, moves, tactics)
- Connect evaluation changes to concrete factors
- Use PGN commentary when available

### 4. **Natural Language**
- Use coaching tone
- Be conversational and educational
- Avoid technical jargon when possible
- Make explanations accessible

### 5. **Comparison Mode**
- Structure as clear comparison
- Use phrases like "compared to", "whereas", "on the other hand"
- Make it clear which result refers to which focus

---

## PGN Processing

### PGN Selection Priority

1. **Refined PGN** (from `NarrativeDecision.refined_pgn`):
   - Curated by Summariser
   - Contains only relevant branches
   - Includes metadata (themes, tactical highlights, key branches)

2. **Full PGN Exploration** (from `InvestigationResult.pgn_exploration`):
   - Complete exploration tree
   - All branches and variations
   - More comprehensive but potentially verbose

3. **None**: No PGN available

### PGN Comment Extraction

The Explainer parses PGN to extract comments:

```python
import chess.pgn
import io

game = chess.pgn.read_game(io.StringIO(pgn_to_use))
# Traverse main line and variations
# Extract comments with move paths
```

**Example Extracted Comments**:
```
- d4 -> Best move (D16). Themes: center_space, piece_activity.
- d4 -> Nf3 -> Continuation: Nf3. Themes: piece_activity.
- d4 -> Nf3 -> Bxe2 -> Continuation: Bxe2. Creates doubled pawns.
```

### PGN Size Limiting

- PGN preview limited to first 2000 characters
- Prevents token bloat in LLM prompt
- Full PGN available in investigation facts if needed

---

## Verbosity Levels

### Brief (2-3 sentences)
- Core message only
- Minimal context
- Direct and concise

**Example**:
> "Nf3 allows Bxe2 which creates doubled pawns and loses center control. The best move was d4, which maintains center control and prevents the bishop capture. Avoid moves that allow opponent to create structural weaknesses."

### Medium (default)
- Core message with context
- Key facts explained
- Balanced detail

**Example**:
> "You played Nf3 with the intent to develop your knight, but this move allows Bxe2 which creates doubled pawns and loses center control. The evaluation dropped by -0.47 pawns, indicating this was a mistake. The best move was d4, which maintains center control and prevents the bishop capture. This highlights the importance of considering structural consequences when developing pieces."

### Detailed
- Full context
- Multiple facts explained
- Comprehensive explanation

**Example**:
> "You played Nf3 with the intent to develop your knight and eventually castle, but this move allows Bxe2 which creates doubled pawns and loses center control. The evaluation dropped by -0.47 pawns, indicating this was a mistake. The best move was d4, which maintains center control and prevents the bishop capture. The position shows center_space and piece_activity themes, and the two-move tactical scan reveals 2 open tactics and 1 capture opportunity. This highlights the importance of considering structural consequences when developing pieces, especially when the opponent can create weaknesses."

---

## Error Handling

### LLM Call Failure
```python
except Exception as e:
    fallback = f"{narrative_decision.core_message}. {narrative_decision.takeaway or ''}"
    return fallback
```

**Fallback Strategy**:
- Uses `core_message` from narrative decision
- Appends `takeaway` if available
- Logs error for debugging

### PGN Parsing Failure
```python
except Exception as e:
    print(f"   ⚠️ Error parsing PGN comments: {e}")
    # Continue without PGN comments
```

**Graceful Degradation**:
- Continues without PGN comments
- Logs warning
- Uses other available facts

---

## Example Flow

### Input
```python
narrative_decision = NarrativeDecision(
    core_message="Nf3 allows Bxe2 which creates doubled pawns and loses center control",
    emphasis=["allowed_structural_damage", "tag.pawn.doubled"],
    psychological_frame="reasonable idea, wrong moment",
    takeaway="Avoid moves that allow opponent to create structural weaknesses",
    verbosity="medium",
    suppress=["tag.space.advantage", "tag.center.control"]
)

investigation_facts = InvestigationResult(
    eval_before=0.50,
    eval_after=0.03,
    eval_drop=-0.47,
    player_move="Nf3",
    best_move="d4",
    mistake_type="mistake",
    move_intent="develop knight",
    consequences={"doubled_pawns": True, "allows_captures": True},
    ...
)

user_message = "I want to eventually castle but I'm not sure how I'm going to do it especially since it's awkward for me to develop my knight out"
```

### Processing
1. **Logs inputs**: User message, narrative decision, investigation facts
2. **Selects PGN**: Uses refined PGN if available, otherwise full exploration
3. **Builds facts summary**: Extracts all relevant facts from InvestigationResult
4. **Constructs prompt**: Combines narrative decision, facts, PGN, and rules
5. **Calls LLM**: Uses `gpt-4o` with temperature 0.7
6. **Logs output**: Explanation length and preview

### Output
```
You played Nf3 with the intent to develop your knight and eventually castle, but this move allows Bxe2 which creates doubled pawns and loses center control. The evaluation dropped by -0.47 pawns, indicating this was a mistake. The best move was d4, which maintains center control and prevents the bishop capture. This highlights the importance of considering structural consequences when developing pieces, especially when the opponent can create weaknesses.
```

---

## Integration with Pipeline

### Upstream: Summariser
- Receives `NarrativeDecision` with:
  - Selected primary narrative
  - Top 2 tag deltas
  - Mandatory psychological frame
  - Suppressed facts list
  - Curated PGN (optional)

### Downstream: Frontend/User
- Returns natural language explanation
- Ready for display to user
- No further processing needed

### Data Flow
```
Summariser (NarrativeDecision)
    ↓
Explainer (explain())
    ↓
Natural Language Explanation
    ↓
Frontend/User
```

---

## Key Design Principles

### 1. **Language Engine Only**
- No chess analysis
- No reanalysis
- No speculation
- Only language generation

### 2. **Strict Adherence**
- Follows narrative decision exactly
- Respects emphasis and suppression
- Uses provided psychological frame
- Honors verbosity level

### 3. **Facts-Based**
- References specific facts
- Connects evaluation to concrete factors
- Uses PGN commentary when available
- Explains consequences and tactics

### 4. **Natural and Accessible**
- Coaching tone
- Conversational style
- Educational approach
- Avoids unnecessary jargon

### 5. **Error Resilience**
- Graceful degradation
- Fallback explanations
- Continues without optional data
- Logs errors for debugging

---

## Summary

The `Explainer` class:

1. **Receives** `NarrativeDecision` and `InvestigationResult` from upstream layers
2. **Selects** appropriate PGN (refined > full > none)
3. **Builds** structured facts summary
4. **Constructs** comprehensive prompt with strict rules
5. **Generates** fluent explanation using `gpt-4o`
6. **Returns** natural language ready for user display

The key innovation is that the Explainer is **purely a language engine** - it doesn't think, analyze, or introduce new ideas. It strictly converts the narrative decision into prose, ensuring consistency and accuracy with the upstream analysis.

















