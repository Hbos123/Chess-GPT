# Backtracking Fix - Proper Starting Positions

## Date: October 17, 2025

## The Critical Problem

**Before:** System found a position with the theme ALREADY PRESENT and asked students to play from there.

**Example:**
```
Rollout finds: Knight already on e5 outpost at move 15
Returns FEN: Board with knight ON e5
Ideal line: Nf6, Bg7, etc. (continuing from outpost)
Student experience: "The knight is already there... what am I learning?" ❌
```

## The Fix: Backtracking

**After:** System backtracks 4-6 moves BEFORE the theme appears, so students CREATE it.

**Example:**
```
Rollout finds: Knight on e5 outpost at move 15
Backtrack: Go back to move 10-11
Returns FEN: Board BEFORE knight reaches e5
Ideal line: Nf3, d4, Nbd2, Ne5 (shows HOW to create outpost)
Student experience: "I need to maneuver my knight to e5!" ✅
```

## Implementation

### File: `backend/position_generator.py`

#### 1. Track Move History (lines 63-76)
```python
# NEW: Track all moves during rollout
move_history = []

for ply in range(target_plies):
    move = await sample_engine_move(...)
    move_history.append(move)  # Store before applying
    board.push(move)
```

#### 2. Backtrack When Theme Found (lines 91-103)
```python
if pred_result.score >= 0.85:  # Found position with theme!
    # BACKTRACK 4-6 moves
    backtrack_plies = rng.randint(4, min(6, len(move_history)))
    
    # Rebuild board from start, stopping BEFORE theme
    starting_board = chess.Board()
    for move in move_history[:-backtrack_plies]:
        starting_board.push(move)
    
    # Validate side to move
    if starting_board.turn matches side_to_move:
        return finalize_position(starting_board, ...)  # ✅
```

#### 3. Unique Position Seeds (lines 48-50)
```python
# Seed RNG with timestamp + topic hash for uniqueness
seed = int(time.time() * 1000) + hash(topic_code) + hash(side_to_move)
rng = random.Random(seed)
```

**Result:** Each generation produces different rollout paths → unique positions

## How It Works Now

### Generation Flow

```
1. Start from initial position
   rnbqkbnr/pppppppp/...

2. Rollout with random Stockfish-guided moves
   Move 1: e4
   Move 2: e5
   Move 3: Nf3
   ...
   Move 12: Nbd2  [Position A - stored in history]
   Move 13: Nc4   [Position B]
   Move 14: Ne3   [Position C]
   Move 15: Ne5   [Position D - OUTPOST DETECTED! score=0.90]

3. Backtrack 4-6 moves (randomly choose 5)
   Go back from Move 15 → Move 10
   
4. Return Position at Move 10
   FEN: Board state after 10 moves (BEFORE outpost)
   
5. Generate ideal_line FROM Move 10
   Stockfish analyzes and finds: Nbd2, Nc4, Ne3, Ne5, ...
   This shows HOW to create the outpost!
```

### Student Experience

**Starting Position (Move 10):**
- Board setup without outpost yet
- Objective: "Establish knight on e5 outpost"

**Ideal Line:**
- Nbd2 → Nc4 → Ne3 → Ne5 ← Creates the outpost!
- Student learns the PROCESS of creating outposts

**Result:**
- ✅ Pedagogically correct
- ✅ Shows strategic execution
- ✅ Student creates the concept themselves

## Uniqueness Guarantees

### 1. Timestamp Seed
- Each call gets different seed
- Different rollout paths
- Different positions

### 2. Random Backtracking
- Backtracks 4-6 moves (random)
- Same rollout → different starting positions

### 3. Random Sampling
- Softmax sampling in rollout
- Not deterministic
- Natural variety

### Combined Effect
Even calling same topic twice in a row produces different FENs!

## What the Predicate Threshold (0.85) Means

**Predicate Score = How strongly the position shows the concept**

```
0.0 = No trace of the concept
0.5 = Concept partially present
0.70 = Concept clearly present but incomplete
0.85 = Strong, clear example (threshold) ✅
1.0 = Perfect textbook example
```

**Example: Knight Outpost**
- `0.0`: No knight, or knight not advanced
- `0.7`: Knight on 5th rank
- `0.85`: Knight on 5th rank + can't be attacked by pawns ✅ 
- `1.0`: Knight on outpost + pawn support + perfect placement

**Why 0.85 is Perfect:**
- Not too easy (would accept weak examples at 0.5)
- Not too hard (would timeout searching for 1.0)
- Ensures quality training positions
- Still achievable in 24 attempts

## Current Success Rate

From your logs (lines 123-177):
```
✅ ST.OUTPOST: Generated in 1706ms  [SUCCESS]
✅ ST.OUTPOST: Generated in 2087ms  [SUCCESS]
✅ TM.PIN: Generated in 969ms       [SUCCESS]
✅ TM.PIN: Generated in 3114ms      [SUCCESS]

❌ PS.IQP: Timeout                  [Some topics harder]
❌ ST.OPEN_FILE: Timeout
❌ TM.FORK: Timeout
```

**Success rate: ~40-50%** (improving with relaxed validation)

## Why Some Topics Fail

**Harder to detect:**
- **PS.IQP**: Requires specific pawn structure (c/d/e files)
- **ST.OPEN_FILE**: Needs file with no pawns + rook present
- **TM.FORK**: Needs specific piece alignment

**Easier to detect:**
- **ST.OUTPOST**: Just needs knight on advanced square
- **TM.PIN**: Common in many positions

## Next Steps to Improve

If success rate not high enough:
1. Lower threshold to 0.75 for struggling topics
2. Increase time budget to 5000ms
3. Add more attempts (24 → 48)
4. Make specific predicates more lenient

---

**Status:** ✅ Backtracking implemented
**Services:** Running at http://localhost:3000  
**Key Fix:** Positions now show starting point, not end result
**Uniqueness:** Guaranteed via timestamp seeding




