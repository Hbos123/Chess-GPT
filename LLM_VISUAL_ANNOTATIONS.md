# 🎨 LLM Visual Annotations System

## Overview

After the LLM responds in chat, the board automatically displays what it's talking about through **intelligent annotation parsing**.

## Architecture

```
LLM Response
    ↓
Parse Text → Extract moves + themes + tags
    ↓
Generate Annotations
    ├─ Move Arrows (suggested moves)
    └─ Theme/Tag Highlights (what LLM referenced)
    ↓
Apply to Board (500ms delay)
```

## Components

### 1. **`llmAnnotations.ts`** - Response Parser
Extracts from LLM text:
- **Moves**: "Best is Nf3", "Play d4", "Consider Nc3"
- **Themes**: "central space", "S_CENTER_SPACE: -1.2", "king safety"
- **Tags**: "knight attacking queen", "semi-open e-file", "bishop pair"

### 2. **`themeAnnotations.ts`** - Visual Dictionary
Maps themes/tags → board annotations:

**Themes:**
- `S_CENTER_SPACE` → Highlight d4/e4/d5/e5
- `S_KING` → Highlight king + pawn shield
- `S_THREATS` → Red arrows showing attacks
- `S_PAWN` → Highlight weak pawns (isolated, backward)
- `S_ACTIVITY` → Highlight active pieces
- `S_DEV` → Highlight undeveloped pieces

**Tags:**
- `threat.capture.more_value` → Red arrow + highlight target
- `outpost.knight.d5` → Green highlight on outpost square
- `file.semi.e` → Blue highlight on file entry squares
- `diagonal.long.a1h8` → Teal arrow along diagonal
- `tactic.fork` → Gold highlight on forking piece + arrows to targets
- `tactic.pin` → Red arrow through pinned piece
- `bishop.pair` → Teal highlights on both bishops
- `pawn.passed.d5` → Gold highlight + arrow to promotion

### 3. **Universal Integration** - `page.tsx`
```typescript
// AUTOMATIC: After every addAssistantMessage():
addAssistantMessage(content, meta)
  → Auto-triggers (500ms delay)
  → Checks for analysis data (meta, tool_raw_data, or cache)
  → If found: applyLLMAnnotations(llmText, engineData)
    → Parse response
    → Generate move arrows (green/blue/amber for 1st/2nd/3rd moves)
    → Generate theme/tag annotations
    → Apply to board
    → Show system message with count
```

**Works for ALL chat contexts:**
- ✅ Position analysis ("who's winning?")
- ✅ General chat with cached analysis
- ✅ Move commentary
- ✅ Game review
- ✅ Tool-based responses
- ✅ Walkthrough annotations

## Example Flow

**User:** "who's winning here"

**LLM:** "White is slightly better at +0.38 pawns. The knight on c3 is attacking the queen on d5, forcing Black to move it. Best is Qd6 to save the queen."

**Annotations Applied:**
1. ✅ **Move arrow**: Green arrow Qd5→Qd6 (suggested move)
2. ✅ **Threat arrow**: Red arrow Nc3→Qd5 (knight attacking queen)
3. ✅ **Threat highlight**: Red highlight on d5 (queen under attack)
4. ✅ **Center highlights**: Green on controlled central squares

**System message:**
> 📍 Visual annotations applied: 3 arrows, 5 highlights

## Clutter Control

- **Max 10 arrows** per response
- **Max 15 highlights** per response
- **500ms delay** to let message render first
- **Smart deduplication** of overlapping annotations
- **Priority order**: Threats → Tactics → Passed pawns → Files → Center

## Color Scheme

- 🟢 **Green**: Good (suggestions, your control, safety)
- 🔴 **Red**: Danger (threats, attacks, weak squares)
- 🟡 **Amber**: Warning (weak pieces, isolated pawns)
- 🔵 **Blue**: Neutral (files, diagonals, plans)
- 🟡 **Gold**: Special (passed pawns, forks, sacrifices)
- 🔷 **Teal**: Info (bishop pair, coordination)

## Full Theme Dictionary Support

The system implements ~80% of your comprehensive rulebook including:
- **Center & Space** (S_CENTER, S_SPACE)
- **Pawn Structure** (isolated, doubled, backward, passed)
- **King Safety** (shield, open files, attackers/defenders)
- **Piece Activity** (mobility, outposts, trapped pieces)
- **Tactics** (fork, pin, skewer, discovered, backrank)
- **Development** (undeveloped pieces)
- **Threats** (all threat tags)
- **Files & Diagonals** (open/semi-open, batteries)

## Future Enhancements

To complete the full rulebook:
- **Labels** on squares (text annotations)
- **Rays** for long-range attacks (dashed lines)
- **Brackets** for files/ranks
- **Areas** for shaded regions (space advantage)
- **Icons** for tactical motifs
- **Hover expansion** (show details on hover)
- **Animation** for move sequences

## Usage

The system works **universally and automatically** - no user action required!

### Scenario 1: Position Question
1. Make a move (auto-analyzes in background)
2. Ask "who's winning?"
3. LLM responds with data
4. Board auto-annotates → ✅

### Scenario 2: General Chat
1. Playing a game
2. Say "hi" or "what should I focus on"
3. LLM responds naturally
4. If analysis is cached → board annotates → ✅

### Scenario 3: Move Commentary
1. Play in PLAY mode
2. LLM comments on your move
3. Board shows what it's talking about → ✅

### Scenario 4: Game Review
1. Reviewing a game
2. LLM explains a critical moment
3. Board highlights the tactical point → ✅

**Every time the LLM talks about the position, the board shows it!** 🎯

The magic: Annotations pull from 3 sources (in priority order):
1. `meta.rawEngineData` (explicit analysis)
2. `meta.tool_raw_data.endpoint_response` (tool calls)
3. `analysisCache[fen]` (auto-cached from moves)

