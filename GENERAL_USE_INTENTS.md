# General Use Intent Detection - Extended for All Modes

## Overview

The clarifying logic system has been extended to work in **all modes** (DISCUSS, ANALYZE, TACTICS, PLAY), not just during play sessions. It now handles general chess-related intents regardless of current context.

---

## New General Use Intents

### Mode Switching
- **switchToAnalyze**: `"switch to analyze mode"`, `"go to analyze"`, `"enter analyze"`
- **switchToDiscuss**: `"switch to discuss mode"`, `"go to discuss"`, `"chat mode"`
- **switchToTactics**: `"switch to tactics mode"`, `"go to tactics"`, `"puzzle mode"`

### Information Requests
- **help**: `"help"`, `"what can you do"`, `"how does this work"`, `"what are you"`
- **describePosition**: `"describe"`, `"explain"`, `"tell me about"`, `"what is"`, `"what's happening"`
- **showCandidates**: `"candidates"`, `"candidate moves"`, `"what moves"`, `"options"`, `"possible moves"`
- **showEvaluation**: `"evaluation"`, `"eval"`, `"what is the eval"`, `"score"`

### Game Management
- **reviewGame**: `"review"`, `"review game"`, `"analyze game"`, `"game review"`
- **startLesson**: `"lesson"`, `"opening lesson"`, `"start lesson"`, `"create lesson"`, `"build lesson"`

### General Actions
- **clear**: `"clear"`, `"close"`, `"cancel"`, `"dismiss"` (context-dependent)

---

## How It Works in All Modes

### In DISCUSS Mode
- All intents work
- Mode switching works
- Help requests work
- Position description works

### In ANALYZE Mode
- All intents work
- Can switch to other modes
- Can request candidates/evaluation
- Can review games

### In TACTICS Mode
- All intents work
- Can switch to other modes
- Can start new puzzles
- Can get help

### In PLAY Mode
- All intents work
- Can end game (with confirmation)
- Can switch modes mid-game
- Can analyze position during game

---

## Confidence Scoring (All Modes)

### High Confidence (>= 0.7)
- Execute immediately
- Examples: `"help"`, `"switch to analyze mode"`, `"play a game"`

### Medium-High (0.5 - 0.7)
- Check for ambiguity
- Execute if not ambiguous
- Examples: `"describe position"`, `"review game"`

### Medium (0.4 - 0.5)
- Always check for ambiguity
- Ask clarification if needed
- Examples: `"end"` (when multiple options)

### Low (< 0.4)
- Fallback message or normal flow
- Examples: `"ending"`, `"do something"`

---

## Context Boosts (All Modes)

Intent confidence is boosted based on context:

- **Mode Match**: +0.2 if intent matches current mode
- **Active Features**: +0.3-0.4 if relevant feature is active
- **Exact Match**: +0.1 for exact keyword match
- **Position Context**: +0.2 if position-related and position exists

---

## Example Scenarios (All Modes)

### Scenario 1: Mode Switching
```
User: "switch to analyze mode"
Context: Any mode
→ System: "Switched to Analyze mode."
→ Mode changes to ANALYZE
```

### Scenario 2: Help Request
```
User: "help"
Context: Any mode
→ System: [Normal LLM response with help information]
```

### Scenario 3: Describe Position
```
User: "describe this position"
Context: Position on board, any mode
→ System: [LLM describes position]
```

### Scenario 4: Ambiguous Mode Switch
```
User: "switch"
Context: Any mode
→ System: "I'm not sure what you'd like to do. Did you want to:
  1. Switch to analyze mode
  2. Switch to discuss mode
  3. Switch to tactics mode"
```

### Scenario 5: Review Game
```
User: "review this game"
Context: Game with moves, any mode
→ System: [LLM reviews game]
```

---

## Integration with Existing System

### Critical Intents (Always Checked First)
- endGame, resign, resetBoard, endWalkthrough
- Require confirmation if critical

### Non-Critical Intents (Works in All Modes)
- startGame, tactics, analyzePosition, switchToAnalyze, etc.
- Execute if confidence high enough
- Ask clarification if ambiguous

### Fallback
- Low confidence commands → Helpful message
- Non-commands → Normal LLM flow

---

## Benefits

1. **Works Everywhere**: System works in all modes, not just play
2. **Context Aware**: Understands current mode and adjusts
3. **Flexible**: Handles mode switching, help, analysis, etc.
4. **User Friendly**: Asks for clarification when uncertain
5. **Comprehensive**: Covers most common user intents

---

## Testing in All Modes

### Test in DISCUSS Mode
- `"switch to analyze mode"` → Should switch
- `"help"` → Should show help
- `"describe this position"` → Should describe

### Test in ANALYZE Mode
- `"switch to tactics mode"` → Should switch
- `"what are my candidates"` → Should show candidates
- `"review this game"` → Should review

### Test in TACTICS Mode
- `"switch to discuss mode"` → Should switch
- `"give me a puzzle"` → Should start puzzle
- `"help"` → Should show help

### Test in PLAY Mode
- `"end this game"` → Should ask confirmation
- `"switch to analyze mode"` → Should switch (game continues)
- `"describe position"` → Should describe

---

## Status: ✅ COMPLETE

The clarifying logic system now works in **all modes** for **general use**, not just play sessions!

