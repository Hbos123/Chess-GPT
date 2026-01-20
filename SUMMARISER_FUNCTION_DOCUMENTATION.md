# Summariser Function Documentation

## Overview

The `Summariser` class is the **Editorial Intelligence** layer of the 4-layer pipeline. It takes structured chess facts from the `Investigator` and decides **what narrative to tell** and **how to frame it**, without performing any chess analysis itself.

**Key Principle**: The Summariser chooses what to say, not why it's true. It acts as an editorial decision-maker that prioritizes and frames information.

---

## Function Signature

```python
async def summarise(
    self,
    investigation_result: Any,  # InvestigationResult or dict with multiple_results
    execution_plan: Optional[Any] = None,  # ExecutionPlan from Planner
    user_history: Optional[Dict[str, Any]] = None
) -> NarrativeDecision
```

---

## Input Types

### 1. **Single Result Mode**
- **Input**: `InvestigationResult` object
- **Use Case**: Analyzing a single position or move
- **Contains**: Eval changes, mistake types, tactics, PGN exploration, tag deltas

### 2. **Comparison Mode**
- **Input**: `dict` with `{"comparison_mode": True, "multiple_results": [...]}`
- **Use Case**: Comparing multiple investigation results (e.g., different moves)
- **Contains**: Array of investigation results with their respective facts

---

## Core Helper Methods

### 1. `_extract_tag_deltas_from_pgn(pgn_exploration: str)`

**Purpose**: Parses the PGN exploration string to extract tag deltas for each move.

**Input Format**:
```
[Starting tags: tag1, tag2, ...]
MOVE1 {[gained: tag1, tag2], [lost: tag3], [two_move: tactic1]}
MOVE2 {[gained: tag4], [lost: tag1], [two_move: none]}
```

**Output**:
```python
[
    {
        "move": "5. d4",
        "tags_gained": ["tag.center.control", "tag.space.advantage"],
        "tags_lost": ["tag.pawn.structure"],
        "two_move_output": ["fork", "winning_capture"]
    },
    ...
]
```

**How It Works**:
- Uses regex to match the pattern: `MOVE {[gained: ...], [lost: ...], [two_move: ...]}`
- Handles both white and black moves (with/without `...`)
- Parses comma-separated tags, filtering out "none" and "+X more" indicators
- Returns a list of dictionaries, one per move

---

### 2. `_extract_pgn_sequence_with_deltas(pgn_exploration: str)`

**Purpose**: Extracts the complete sequence information including starting tags and all move deltas.

**Output**:
```python
{
    "starting_tags": ["tag.king.file.semi", "tag.center.control", ...],
    "main_sequence": [
        {
            "move": "5. d4",
            "tags_gained": [...],
            "tags_lost": [...],
            "two_move_output": [...]
        },
        ...
    ]
}
```

**How It Works**:
- Extracts starting tags from `[Starting tags: ...]` comment
- Calls `_extract_tag_deltas_from_pgn` to get all move deltas
- Combines into a single structure

---

### 3. `_extract_d2_vs_d16_comparison(investigation_result: InvestigationResult)`

**Purpose**: Extracts comparison data between shallow (D2) and deep (D16) analysis to understand if the best move is "obvious."

**Output**:
```python
{
    "d16_best_move": "d4",
    "d16_eval": 0.91,
    "d2_eval": 0.85,
    "d2_top_moves": [
        {"move": "d4", "eval": 0.85},
        {"move": "Nf3", "eval": 0.80},
        ...
    ],
    "overestimated_moves": ["Nf3", "h3"],
    "is_critical": True,
    "is_winning": False,
    "second_best_d16": "Nf3",
    "second_best_d16_eval_cp": 85,
    "d2_suggests_different": False  # True if D16 best move not in D2 top 3
}
```

**Key Logic**:
- If `d2_suggests_different` is `True`, the D16 best move is **not completely obvious** (D2 suggests different moves)
- This indicates the position has multiple reasonable options
- The summariser uses this to explain why the best move isn't obvious and what alternatives don't address

---

## Main Flow: `summarise()` Method

### Step 1: Input Detection and Logging

The function first determines the mode:
- **Comparison Mode**: `isinstance(investigation_result, dict) and investigation_result.get("comparison_mode", False)`
- **Single Result Mode**: `isinstance(investigation_result, InvestigationResult)`

Logs input details for debugging.

---

### Step 2: Extract Tag Deltas and D2 vs D16 Data

For both modes, the function:

1. **Extracts PGN Tag Deltas**:
   ```python
   pgn_tag_deltas = None
   if investigation_result.pgn_exploration:
       pgn_tag_deltas = self._extract_pgn_sequence_with_deltas(investigation_result.pgn_exploration)
   ```

2. **Extracts D2 vs D16 Comparison**:
   ```python
   d2_vs_d16 = self._extract_d2_vs_d16_comparison(investigation_result)
   ```

---

### Step 3: Build Facts Dictionary

#### For Comparison Mode:
```python
facts_list = []
for item in multiple_results:
    facts = {
        "focus": inv_req.focus,
        "purpose": inv_req.purpose,
        "eval_before": result.eval_before,
        "eval_after": result.eval_after,
        "eval_drop": result.eval_drop,
        "mistake_type": result.mistake_type,
        "move_intent": result.move_intent,
        "game_phase": result.game_phase,
        "urgency": result.urgency,
        "tactics_found": len(result.tactics_found) > 0,
        "has_threats": len(result.threats) > 0,
        "player_move": result.player_move,
        "best_move": result.best_move,
        "material_change": result.material_change,
        "positional_change": result.positional_change,
        "has_consequences": bool(result.consequences),
        "pgn_tag_deltas": pgn_tag_deltas,  # NEW: Tag deltas per move
        "d2_vs_d16": d2_vs_d16  # NEW: D2 vs D16 comparison
    }
    facts_list.append(facts)
```

#### For Single Result Mode:
```python
# Determine investigation type (position vs move)
investigation_type = "position"
if execution_plan and hasattr(execution_plan, 'steps'):
    for step in execution_plan.steps:
        if step.action_type == "investigate_move":
            investigation_type = "move"
            break

facts = {
    "eval_drop": investigation_result.eval_drop,
    "mistake_type": investigation_result.mistake_type,
    "move_intent": investigation_result.move_intent,
    "intent_mismatch": investigation_result.intent_mismatch,
    "game_phase": investigation_result.game_phase,
    "urgency": investigation_result.urgency,
    "tactics_found": len(investigation_result.tactics_found) > 0,
    "has_threats": len(investigation_result.threats) > 0,
    "player_move": investigation_result.player_move,
    "best_move": investigation_result.best_move,
    "missed_move": investigation_result.missed_move,
    "primary_failure": investigation_result.primary_failure,
    "material_change": investigation_result.material_change,
    "positional_change": investigation_result.positional_change,
    "has_consequences": bool(investigation_result.consequences),
    "pgn_tag_deltas": pgn_tag_deltas,  # NEW: Tag deltas per move
    "d2_vs_d16": d2_vs_d16,  # NEW: D2 vs D16 comparison
    "investigation_type": investigation_type  # NEW: "position" or "move"
}
```

---

### Step 4: Build LLM Prompt

The prompt instructs the LLM to build a narrative based on:

1. **Tag Deltas**: What tags are gained/lost per move indicates positional consequences
2. **D2 vs D16**: Whether the best move is obvious or has alternatives
3. **Investigation Type**: Whether analyzing a move or a position

#### Comparison Mode Prompt Structure:
```
You are an editorial decision-maker. You receive multiple chess investigation results with tag deltas and decide what narrative to tell.

COMPARISON DATA (structured data only):
{json.dumps(facts_list, indent=2)}

PGN TAG DELTAS (what tags change in each move):
For each result, the PGN shows tag changes per move in format: MOVE {[gained: tag1, tag2], [lost: tag3], [two_move: tactic1]}
- Tags gained indicate what the move creates/enables
- Tags lost indicate what the move removes/prevents
- Two-move output shows tactical opportunities available
Use these tag deltas to understand what each move allows/prevents.

D2 vs D16 COMPARISON:
- d16_best_move: The deep analysis (D16) best move
- d2_top_moves: What shallow analysis (D2) suggests
- d2_suggests_different: If true, D16 best move is not completely obvious (D2 suggests different moves)
- overestimated_moves: Moves that D2 overestimated (looked good but aren't)
- If d2_suggests_different is true, the position has multiple reasonable options
- Mention what the move does/stops, but also note what doesn't stop in alternate variations

Your job: Build a narrative that explains:
1. What each move allows/prevents based on tag changes
2. How the game would progress (based on tag deltas in continuation)
3. If D2 suggests different moves, note that the best move isn't obvious and explain what alternatives don't address

Output JSON:
{
  "core_message": "narrative explaining move consequences based on tag deltas",
  "emphasis": ["key_tag_changes", "d2_vs_d16_insight"],
  "psychological_frame": "how to frame it psychologically (optional)",
  "takeaway": "one actionable lesson (optional)",
  "verbosity": "brief|medium|detailed",
  "suppress": ["fact3"]
}

RULES:
- Use tag deltas to explain what moves allow/prevent
- Tag changes indicate positional consequences (gained tags = new features, lost tags = removed features)
- If investigating a move, explain what continuation it allows and resulting tag changes
- If D2 suggests different moves, explain what the best move does that alternatives don't
- Note what doesn't stop in alternate variations (overestimated moves)
- Focus on tag changes as indicators of positional consequences
- Translate tag names to natural language (e.g., "tag.center.control" -> "center control")
```

#### Single Result Mode Prompt Structure:
```
You are an editorial decision-maker. You receive chess facts with tag deltas and decide what narrative to tell.

INVESTIGATION FACTS (structured data only):
{json.dumps(facts, indent=2)}

INVESTIGATION TYPE: {investigation_type}

PGN TAG DELTAS:
The PGN shows tag changes for each move in format: MOVE {[gained: tag1, tag2], [lost: tag3], [two_move: tactic1]}
- Tags gained indicate what the move creates/enables
- Tags lost indicate what the move removes/prevents
- Two-move output shows tactical opportunities available
- Use tag deltas to understand what moves allow/prevent and how the game progresses

D2 vs D16 COMPARISON:
- d16_best_move: The deep analysis (D16) best move
- d2_top_moves: What shallow analysis (D2) suggests
- d2_suggests_different: If true, D16 move isn't completely obvious (D2 suggests alternatives)
- overestimated_moves: Moves that D2 overestimated (looked good but aren't)
- If d2_suggests_different is true, explain what the best move does that alternatives don't address

Your job: Build a narrative that explains:
1. If investigating a MOVE: Explain what this move allows (continuation) and resulting tag changes
2. If investigating a POSITION: Explain how the game would progress based on tag deltas
3. Use tag changes to explain positional consequences (e.g., "gains center control" if tag.center.control gained)
4. If D2 suggests different moves, note the best move isn't obvious and explain what it does that alternatives don't
5. Note what doesn't stop in alternate variations (if overestimated_moves exist)

Output JSON:
{
  "core_message": "narrative explaining consequences based on tag deltas",
  "emphasis": ["key_tag_changes", "d2_vs_d16_insight", "continuation_consequences"],
  "psychological_frame": "how to frame it psychologically (optional)",
  "takeaway": "one actionable lesson (optional)",
  "verbosity": "brief|medium|detailed",
  "suppress": ["fact3"]
}

RULES:
- Use tag deltas to explain what moves allow/prevent
- Tag changes indicate positional consequences (gained tags = new features, lost tags = removed features)
- If investigating a move, explain: "This move allows [continuation] which causes [tag changes]"
- If D2 suggests different moves, explain what the best move does that alternatives don't
- Note what doesn't stop in alternate variations (overestimated moves)
- Focus on tag changes as indicators of narrative consequences
- Translate tag names to natural language (e.g., "tag.center.control" -> "center control")
- Build a story from tag changes: what the move enables, what it prevents, how the game progresses
```

---

### Step 5: Call LLM and Parse Response

```python
response = self.client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": prompt}],
    response_format={"type": "json_object"}
)

decision_dict = json.loads(response.choices[0].message.content)
```

---

### Step 6: Curate PGN (Optional)

If `investigation_result` has PGN exploration and an execution plan, the function curates a refined PGN:

```python
refined_pgn = None
if isinstance(investigation_result, InvestigationResult):
    if investigation_result.pgn_exploration and investigation_result.exploration_tree and execution_plan:
        try:
            refined_pgn = await self.curate_pgn(investigation_result, execution_plan)
        except Exception as e:
            print(f"   ⚠️ PGN curation error: {e}")
```

The `curate_pgn` method:
- Extracts moves of interest from the execution plan
- Scores branches by relevance (plan alignment, eval significance, tactical value, theme importance)
- Selects top 5 branches
- Builds a refined PGN with only selected branches

---

### Step 7: Create and Return NarrativeDecision

```python
narrative_decision = NarrativeDecision(
    core_message=decision_dict.get("core_message", "Analysis complete"),
    emphasis=decision_dict.get("emphasis", []),
    psychological_frame=decision_dict.get("psychological_frame"),
    takeaway=decision_dict.get("takeaway"),
    verbosity=decision_dict.get("verbosity", "medium"),
    suppress=decision_dict.get("suppress", []),
    refined_pgn=refined_pgn
)
```

---

## Output: NarrativeDecision

The `NarrativeDecision` dataclass contains:

```python
@dataclass
class NarrativeDecision:
    core_message: str  # One sentence summary
    emphasis: List[str]  # Facts to emphasize
    psychological_frame: Optional[str]  # How to frame it psychologically
    takeaway: Optional[str]  # One actionable lesson
    verbosity: str  # "brief" | "medium" | "detailed"
    suppress: List[str]  # Facts to NOT mention
    refined_pgn: Optional[RefinedPGN]  # Curated PGN with only relevant branches
```

---

## Key Narrative Building Principles

### 1. **Tag Deltas as Story Indicators**
- **Tags Gained**: Indicate what the move **creates/enables** (e.g., "gains center control", "creates doubled pawns")
- **Tags Lost**: Indicate what the move **removes/prevents** (e.g., "loses piece activity", "removes pin")
- **Two-Move Output**: Shows tactical opportunities available at that position

### 2. **D2 vs D16 Insight**
- If `d2_suggests_different` is `True`: The best move isn't obvious, explain what it does that alternatives don't
- **Overestimated Moves**: Moves that looked good at D2 but aren't - note what they don't stop

### 3. **Move Investigation Narrative**
- Format: "This move allows [continuation] which causes [tag changes]"
- Example: "Nf3 allows Bxe2 which causes doubled pawns (tag.pawn.doubled gained)"

### 4. **Position Investigation Narrative**
- Format: "The game would progress like so: [move sequence] with [tag changes]"
- Example: "After d4, the position gains center control but loses pawn structure flexibility"

---

## Example Flow

### Input (Single Result Mode):
```python
investigation_result = InvestigationResult(
    eval_before=0.50,
    eval_after=0.03,
    eval_drop=-0.47,
    player_move="Nf3",
    best_move="d4",
    pgn_exploration="[Starting tags: tag.center.control, tag.space.advantage] 5. Nf3 {[gained: none], [lost: tag.center.control], [two_move: none]} 5... Bxe2 {[gained: tag.pawn.doubled], [lost: tag.pawn.structure], [two_move: none]}",
    ...
)
```

### Processing:
1. Extract tag deltas: `Nf3` loses `tag.center.control`, `Bxe2` gains `tag.pawn.doubled`
2. Extract D2 vs D16: D2 suggests `d4` and `Nf3` are close, D16 clearly prefers `d4`
3. Build facts with tag deltas and D2 vs D16
4. LLM prompt includes tag delta narrative instructions
5. LLM generates narrative explaining: "Nf3 allows Bxe2 which creates doubled pawns, losing center control"

### Output:
```python
NarrativeDecision(
    core_message="Nf3 allows Bxe2 which creates doubled pawns and loses center control, while d4 maintains center control and prevents the bishop capture.",
    emphasis=["tag.pawn.doubled", "tag.center.control", "d2_vs_d16_insight"],
    takeaway="Avoid moves that allow opponent to create structural weaknesses",
    verbosity="medium"
)
```

---

## Error Handling

If any step fails, the function returns a fallback `NarrativeDecision`:

```python
except Exception as e:
    return NarrativeDecision(
        core_message="Analysis complete",
        emphasis=[],
        verbosity="medium",
        refined_pgn=None
    )
```

---

## Summary

The `summarise()` function:

1. **Extracts** tag deltas and D2 vs D16 comparison from investigation results
2. **Builds** a facts dictionary with structured data
3. **Prompts** an LLM to create a narrative based on tag changes and move comparisons
4. **Returns** a `NarrativeDecision` that tells the Explainer what to say and how to frame it

The key innovation is using **tag deltas as narrative indicators** - the function doesn't analyze chess, it interprets what the tag changes mean for the story being told.

















