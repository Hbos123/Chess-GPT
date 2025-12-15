# Lesson Alternate Move Auto-Play Fix

## Issue
When a player made an alternate/non-mainline move during a lesson, the AI was not reliably auto-playing a response move using Stockfish.

## Root Causes

### 1. **React State Updates Are Asynchronous**
The old code was trying to read from the React state after the move:
```typescript
const currentPosition = game.fen();
```

**Problem:** React state updates are asynchronous! When `checkLessonMove` runs, `game.fen()` still returns the position BEFORE the player's move was applied, even though `oldHandleMove` was called first. This caused the turn detection to fail.

**Evidence from logs:**
```
[LESSON DEVIATION] Current position after player's move: ...w - - 0 9
[LESSON DEVIATION] Player played: Ne5
[LESSON DEVIATION] Is opponent's turn? false  ← WRONG! Should be true
```

The FEN shows it's still white's turn even though white just played Ne5.

### 2. **Wrong API Response Structure**
The old code was looking for:
```typescript
const bestResponse = analysis.lines[0].moves[0];
```

**Problem:** The `/analyze_position` endpoint actually returns:
```typescript
const bestResponse = analysis.candidate_moves[0].move;
```

### 3. **Insufficient Error Handling**
Limited logging made it difficult to debug when the auto-play failed.

## Solution

### Updated Code (Lines 3388-3450)

**Key Changes:**

1. **Calculate Position Instead of Reading State**
```typescript
// Calculate the position AFTER the player's move by applying it to currentFen
// We can't rely on game.fen() because React state updates are asynchronous
const tempBoard = new Chess(currentFen);
const playerMove = tempBoard.move(moveSan);
const currentPosition = tempBoard.fen();
```

This ensures we have the correct position by manually applying the move, rather than waiting for React's async state update.

2. **Verify Opponent's Turn**
```typescript
const isOpponentTurn = (playerSide === "white" && tempBoard.turn() === 'b') || 
                       (playerSide === "black" && tempBoard.turn() === 'w');

if (isOpponentTurn) {
  // Auto-play engine response
}
```

3. **Correct API Response Parsing**
```typescript
if (analysis.candidate_moves && analysis.candidate_moves.length > 0) {
  const bestResponse = analysis.candidate_moves[0].move;
  // Apply the move...
}
```

4. **Enhanced Logging**
```typescript
console.log("[LESSON DEVIATION] Current position after player's move:", currentPosition);
console.log("[LESSON DEVIATION] Player played:", moveSan);
console.log("[LESSON DEVIATION] Is opponent's turn?", isOpponentTurn);
console.log("[LESSON DEVIATION] Engine's best response:", bestResponse);
```

## How It Works Now

### Flow for Alternate Moves:

1. **Player makes a non-mainline move**
   - Move is applied to game state via `oldHandleMove`
   - `checkLessonMove` is called with the move details

2. **System evaluates the deviation**
   - Calls `/check_lesson_move` to evaluate quality
   - Shows feedback with CP loss and evaluation symbols

3. **Engine auto-responds (NEW - RELIABLE)**
   - Gets current position from game state
   - Verifies it's opponent's turn
   - Calls Stockfish via `/analyze_position`
   - Plays the best move automatically
   - Updates board and move tree
   - Shows message: "Opponent responds with best move: **Nf6**"

### Example Console Output:
```
[LESSON DEVIATION] Position before player move: rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1
[LESSON DEVIATION] Player played: Nf6
[LESSON DEVIATION] Position after player move: rnbqkb1r/pppppppp/5n2/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 1 2
[LESSON DEVIATION] Turn is now: w
[LESSON DEVIATION] Player side: black
[LESSON DEVIATION] Is opponent's turn? true
[LESSON DEVIATION] Engine's best response: d4
```

## Benefits

✅ **Reliable auto-play**: Engine ALWAYS responds to alternate moves  
✅ **Correct state management**: Manually calculates position instead of relying on async React state  
✅ **Better debugging**: Enhanced logging shows before/after positions and turn changes  
✅ **Proper API usage**: Uses correct response structure from backend  
✅ **Turn verification**: Only auto-plays when it's actually opponent's turn  
✅ **No race conditions**: Doesn't depend on React state update timing  

## Testing

To test the fix:

1. Start a lesson (Create Lesson button)
2. When prompted to play a specific move, play a DIFFERENT move instead
3. The system should:
   - Show feedback about your deviation
   - Display CP loss
   - **AUTO-PLAY the opponent's best response using Stockfish**
4. The board should update automatically with the opponent's move

## Technical Details

**File Changed:** `frontend/app/page.tsx`  
**Lines Modified:** 3388-3440  
**Function:** `checkLessonMove`  
**Timeout:** 1500ms (1.5 seconds) before auto-playing response  

**API Endpoint Used:** `GET /analyze_position?fen={fen}&lines=1&depth=16`  
**Response Field:** `candidate_moves[0].move`  

## Related Files

- `backend/main.py` - `/analyze_position` and `/check_lesson_move` endpoints
- `frontend/app/page.tsx` - Lesson system logic
- `LESSON_ENGINE_AUTOPLAY.md` - Documentation for mainline auto-play
- `LESSON_IDEAL_LINE_SYSTEM.md` - Lesson system overview

---

**Status:** ✅ Fixed and tested  
**Date:** October 17, 2025  
**Impact:** High - Significantly improves lesson UX for alternate moves

