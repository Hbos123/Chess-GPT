# 🔍 Drill Criteria & Search System - Complete

## Overview

Enhanced the training system with transparent criteria display and intelligent position searching.

## How It Works

### Step 1: User Query
```
User types: "Fix my middlegame tactical mistakes with forks"
```

### Step 2: LLM Planning (GPT-4o-mini)
```
LLM analyzes:
- Game context (openings, results, game types)
- Common mistake tags
- Phase distribution of errors
- Critical positions identified

Generates blueprint:
{
  "focus_tags": ["tactic.fork", "tactic"],
  "context_filters": {"phases": ["middlegame"]},
  "drill_types": ["tactics", "defense"]
}
```

### Step 3: Search Criteria Display
```
📋 TRAINING SEARCH CRITERIA:
   User asked: 'Fix my middlegame tactical mistakes with forks'
   Looking for:
     • Positions with tags: tactic.fork, tactic
     • From game phases: middlegame
     • Drill types: tactics, defense
     • Mistakes and tactical opportunities
     • Target: 15 drills
```

### Step 4: Position Mining
```
🔍 SEARCHING FOR:
   Tags matching: tactic.fork, tactic
   Phase: middlegame
   Side: both
   Include critical choices: true
   Priority: Blunders > Mistakes > Critical > Threshold events

Searching game 1/3...
Searching game 2/3...
Searching game 3/3...

📊 SEARCH RESULTS:
   Moves checked: 164
   Candidates found: 12
   By category: {'blunder': 3, 'mistake': 5, 'critical_best': 4}
   
   Top 3 priorities:
     1. blunder (priority=17.0): Rxe8 - tags: fork, threat
     2. blunder (priority=15.0): Nxf7 - tags: fork, development
     3. mistake (priority=10.0): Qxd5 - tags: fork

✅ FINAL SELECTION: 12 positions
```

### Step 5: Results
```
If drills found:
  → Session created with 12-15 drills
  → Practice and improve

If NO drills found:
  → Empty session returned
  → Error message: "No relevant positions found. Try broader query."
  → Suggestions shown
```

## Search Criteria Explained

### What Gets Searched:

**1. Tags/Themes:**
```
Query: "fork patterns" 
→ Looking for: tactic.fork, tactic.discovered_attack
```

**2. Game Phases:**
```
Query: "middlegame mistakes"
→ Phase filter: middlegame only
→ Ignores opening and endgame positions
```

**3. Piece-Specific:**
```
Query: "knight tactics"
→ Tags: piece.knight, tactic.knight_fork
```

**4. Opening-Specific:**
```
Query: "mistakes in Italian Game"
→ Opening filter: "Italian Game"
→ Only positions from those games
```

**5. Error Types:**
```
Query: "my blunders"
→ Category filter: blunder (200+ cp loss)
```

**6. Critical Moments:**
```
Query: "important decisions I got right"
→ Include critical_best: true
→ Positions with 50+ cp gap to second move
```

**7. Endgame Types:**
```
Query: "rook endgame technique"
→ Phase: endgame
→ Endgame type: rook_endgame
→ Tags: endgame.rook, rook.activity
```

## Priority Scoring System

Positions are scored and ranked:

| Type | Base Points | Bonus | Total |
|------|-------------|-------|-------|
| Blunder + focus tag | 10 | +5 | 15 |
| Blunder | 10 | - | 10 |
| Mistake + focus tag | 7 | +3 | 10 |
| Mistake | 7 | - | 7 |
| Critical best move | 5 | - | 5 |
| Threshold crossing | 3 | - | 3 |
| Theory exit | 2 | - | 2 |

**Additional bonuses:**
- +2-4 for high CP loss (100+, 200+)
- +2 for time trouble (<5s and CP loss > 50)

## Example Search Outputs

### Query: "Fork mistakes in the middlegame"

**Console output:**
```
📋 TRAINING SEARCH CRITERIA:
   User asked: 'Fork mistakes in the middlegame'
   Looking for:
     • Positions with tags: tactic.fork
     • From game phases: middlegame
     • Drill types: tactics
     • Mistakes and tactical opportunities
     • Target: 15 drills

🔍 SEARCHING FOR:
   Tags matching: tactic.fork
   Phase: middlegame
   Side: both
   Include critical choices: false
   Priority: Blunders > Mistakes > Critical > Threshold events

   Searching game 1/3...
   Searching game 2/3...
   Searching game 3/3...

📊 SEARCH RESULTS:
   Moves checked: 82
   Candidates found: 4
   By category: {'blunder': 2, 'mistake': 2}
   
   Top 3 priorities:
     1. blunder (priority=17.0): Nxd5 - tags: fork, threat
     2. blunder (priority=15.0): Rxe8 - tags: fork
     3. mistake (priority=10.0): Qxd4 - tags: fork, development

✅ FINAL SELECTION: 4 positions
```

### Query: "Endgame rook technique"

**Console output:**
```
📋 TRAINING SEARCH CRITERIA:
   User asked: 'Endgame rook technique'
   Looking for:
     • Positions with tags: endgame.rook, rook.activity
     • From game phases: endgame
     • Drill types: conversion, tactics
     • Target: 15 drills

🔍 SEARCHING FOR:
   Tags matching: endgame.rook, rook.activity
   Phase: endgame
   
📊 SEARCH RESULTS:
   Moves checked: 28
   Candidates found: 3
   By category: {'mistake': 2, 'critical_best': 1}

✅ FINAL SELECTION: 3 positions
```

### Query: "Something overly specific"

**Console output:**
```
📋 TRAINING SEARCH CRITERIA:
   User asked: 'Queen sacrifices on h7 in the Najdorf'
   Looking for:
     • Positions with tags: sacrifice.queen
     • From game phases: middlegame
     • From openings: B90-B99
     
🔍 SEARCHING FOR:
   Tags matching: sacrifice.queen
   Phase: middlegame

📊 SEARCH RESULTS:
   Moves checked: 82
   Candidates found: 0
   
⚠️ NO RELEVANT POSITIONS FOUND
   Criteria may be too specific or games don't contain matching positions

✅ FINAL SELECTION: 0 positions
```

**Frontend receives:**
```json
{
  "empty": true,
  "total_cards": 0,
  "message": "No relevant positions found. Try a broader query or analyze more games.",
  "search_criteria": [
    "Positions with tags: sacrifice.queen",
    "From game phases: middlegame",
    "From openings: B90-B99"
  ]
}
```

**User sees:**
```
⚠️ No relevant drills found. Try a broader query or different focus.

Suggestions:
- Broaden your query (e.g., "tactical mistakes" instead of "queen sacrifices")
- Analyze more games (currently: 3 games)
- Try different openings or phases
```

## Frontend Display

### Training Manager - Hint Box:
```
┌────────────────────────────────────────────┐
│ 💡 The system will search through 3        │
│ analyzed games to find positions matching   │
│ your query. Be specific! Examples:         │
│   • Middlegame tactical mistakes with forks│
│   • Endgame technique errors               │
│   • Opening mistakes in my Sicilian        │
│   • Critical moments I got right           │
└────────────────────────────────────────────┘
```

### Browser Console (Developer Tools):
```
🔍 Training Search Criteria:
  • Positions with tags: tactic.fork
  • From game phases: middlegame
  • Drill types: tactics, defense
  • Mistakes and tactical opportunities
  • Target: 15 drills
```

## Backend Log Example (Complete Flow)

```
============================================================
🎓 CREATE TRAINING SESSION
============================================================
   User: HKB03
   Query: Fix my middlegame tactical mistakes
   Mode: focused
   Analyzed games: 3

📋 Step 1: Planning training...

📋 TRAINING SEARCH CRITERIA:
   User asked: 'Fix my middlegame tactical mistakes'
   Looking for:
     • Positions with tags: tactic.fork, tactic.pin, threat
     • From game phases: middlegame
     • Drill types: tactics, defense
     • Mistakes and tactical opportunities
     • Target: 15 drills

⛏️ Step 2: Mining positions...

🔍 POSITION MINER: Mining 15 positions from 3 games
   Focus tags: ['tactic.fork', 'tactic.pin', 'threat']
   Filters: phase=middlegame, side=both
   Game types: ['tactical_battle', 'dynamic', 'positional']
   Openings: ['Italian Game', 'Sicilian Defense', 'Queen's Gambit']

   🔍 SEARCHING FOR:
      Tags matching: tactic.fork, tactic.pin, threat
      Phase: middlegame
      Side: both
      Include critical choices: true
      Priority: Blunders > Mistakes > Critical > Threshold events

   Searching game 1/3...
   Searching game 2/3...
   Searching game 3/3...

   📊 SEARCH RESULTS:
      Moves checked: 82
      Candidates found: 12
      By category: {'blunder': 3, 'mistake': 5, 'critical_best': 4}
      
      Top 3 priorities:
        1. blunder (priority=17.0): Rxe8 - tags: fork, threat
        2. blunder (priority=15.0): Nxf7 - tags: fork
        3. mistake (priority=10.0): Qxd5 - tags: pin, threat

   ✅ FINAL SELECTION: 12 positions

🎯 Step 3: Generating drills...
   Drill 1: tactics, tags=['tactic.fork']
   ...

✅ TRAINING SESSION CREATED
   Session ID: 20251101_091234
   Total drills: 12
   Search criteria matched: 5 criteria
============================================================
```

## Empty Result Handling

### When No Positions Found:

**Backend logs:**
```
📊 SEARCH RESULTS:
   Moves checked: 82
   Candidates found: 0
   
⚠️ NO RELEVANT POSITIONS FOUND
   Criteria may be too specific or games don't contain matching positions

✅ FINAL SELECTION: 0 positions

⚠️ NO POSITIONS FOUND - Returning empty session
```

**Frontend receives:**
```json
{
  "session_id": null,
  "cards": [],
  "total_cards": 0,
  "empty": true,
  "message": "No relevant positions found. Try a broader query or analyze more games.",
  "search_criteria": [...]
}
```

**User sees:**
```
⚠️ No relevant drills found. Try a broader query or different focus.

What was searched:
• Positions with tags: sacrifice.queen
• From game phases: middlegame
• From openings: Najdorf

Suggestions:
- Try "tactical mistakes" instead
- Remove opening filter
- Analyze more games
```

## Benefits

### Transparency:
- ✅ User knows exactly what system is looking for
- ✅ Can refine query if too specific/broad
- ✅ Understands why no drills if empty

### Relevance:
- ✅ LLM interprets intent
- ✅ Searches systematically
- ✅ Prioritizes important positions
- ✅ Applies diversity (no repetition)

### Debugging:
- ✅ Full log trail
- ✅ Move count shown
- ✅ Candidate breakdown
- ✅ Top priorities listed
- ✅ Empty results explained

## Files Modified

1. **backend/training_planner.py**
   - Added `_generate_search_criteria()` method
   - Logs criteria after planning
   - Human-readable format

2. **backend/position_miner.py**
   - Enhanced logging (what we're searching for)
   - Move count tracking
   - Candidate breakdown by category
   - Top 3 priorities display
   - Empty result handling with explanation
   - Returns `[]` if nothing found

3. **backend/main.py**
   - Handle empty position results
   - Return empty session with message
   - Include search_criteria in response

4. **frontend/components/TrainingManager.tsx**
   - Check for empty sessions
   - Display error message
   - Log search criteria to console
   - Show hint box with examples

5. **frontend/app/styles.css**
   - Added `.training-hint` styles

## Current Status

```
✅ Backend running (localhost:8000, PID 73914)
✅ Both systems initialized
✅ Drill criteria system active
✅ Empty result handling ready
✅ Comprehensive logging enabled
```

## Test Examples

### Good Queries (Will Find Drills):
- ✅ "Tactical mistakes"
- ✅ "Middlegame errors"
- ✅ "Fork and pin practice"
- ✅ "Endgame technique"
- ✅ "Critical decisions"
- ✅ "Time pressure mistakes"

### Too Specific (Might Return Empty):
- ⚠️ "Queen sacrifices on h7 in the Najdorf"
- ⚠️ "Knight moves to f6 in move 12"
- ⚠️ "Zugzwang positions"

**Solution if empty:** Broaden query or analyze more games!

---

**Status:** ✅ READY TO TEST  
**Backend:** All criteria logging active  
**Frontend:** Empty state handled  
**Test:** Refresh browser and try specific queries! 🎯

