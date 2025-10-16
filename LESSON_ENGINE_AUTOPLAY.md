# Lesson Engine Auto-Play System

## Overview
The lesson system now features **automatic opponent move playback**. When the player makes a correct move, the engine automatically plays the opponent's response from the ideal line, creating a smooth, interactive training experience.

## Key Changes

### 1. Hidden Ideal Line ✅
**Problem:** Players could see the target moves, making it too easy.
**Solution:** Removed all displays of `ideal_pgn` from UI messages.

**Before:**
```
📚 Lesson Position 1/3
[LLM intro]
*Goal: Play the line 9. b3 b6 10. Bb2 Bb7 11. Bd3*

💡 Objective: ...
Target line: 9. b3 b6 10. Bb2 Bb7 11. Bd3
```

**After:**
```
📚 Lesson Position 1/3
[LLM intro]

💡 Objective: ...
Hints:
• The e5 break is typical in IQP positions
• Keep your pieces active
```

### 2. Engine Auto-Play ✅
**Problem:** Player had to manually play both sides.
**Solution:** Engine automatically plays opponent moves from the ideal line.

## Technical Implementation

### `checkLessonMove` Function

**Key Logic:**

1. **Determine Player's Side:**
```typescript
const playerSide = currentLessonPosition.side; // "white" or "black"
const currentBoard = new Chess(currentFen);
const isPlayerTurn = (playerSide === "white" && currentBoard.turn() === 'w') || 
                    (playerSide === "black" && currentBoard.turn() === 'b');
```

2. **Check Move Correctness:**
```typescript
const expectedMove = idealLine[lessonMoveIndex];
const isOnMainLine = moveSan === expectedMove;
```

3. **If Correct, Check for Opponent Response:**
```typescript
if (isOnMainLine) {
  setLessonMoveIndex(newIndex);
  
  // Only give feedback for player moves
  if (isPlayerTurn) {
    addAssistantMessage(`✅ **Correct!** ${llmFeedback}`);
  }
  
  // Check if next move is opponent's
  if (newIndex < idealLine.length) {
    const nextMove = idealLine[newIndex];
    const nextBoard = new Chess(fen);
    
    const isNextMoveOpponent = (playerSide === "white" && nextBoard.turn() === 'b') || 
                               (playerSide === "black" && nextBoard.turn() === 'w');
    
    if (isNextMoveOpponent) {
      // Auto-play after 1.5 second delay
      setTimeout(() => {
        const move = nextBoard.move(nextMove);
        if (move) {
          setFen(nextBoard.fen());
          setGame(nextBoard);
          moveTree.addMove(move.san, nextBoard.fen());
          setLessonMoveIndex(newIndex + 1);
          
          addSystemMessage(`Opponent plays: **${move.san}**`);
        }
      }, 1500);
    }
  }
}
```

## User Experience Flow

### Example: IQP Position (Player is White)

**Ideal Line:** `["b3", "b6", "Qc2", "Bb7", "Bb2"]`

#### Step 1: Player Plays b3
```
Player: [plays b3]
System: Checking your move...
✅ Correct! This prepares the fianchetto and controls key squares.

[1.5 second delay]

System: Opponent plays: **b6**
[Board updates to show b6]
```

#### Step 2: Player Plays Qc2
```
Player: [plays Qc2]
System: Checking your move...
✅ Correct! The queen supports the center and prepares development.

[1.5 second delay]

System: Opponent plays: **Bb7**
[Board updates to show Bb7]
```

#### Step 3: Player Plays Bb2
```
Player: [plays Bb2]
System: Checking your move...
✅ Correct! Completing the fianchetto setup!

🎉 Perfect! You've completed the ideal line for this position!

[2 second delay - auto-advance to next position]
```

## Key Features

### 1. Player-Only Feedback
- Only player moves receive LLM-generated feedback
- Opponent moves are simply announced: `Opponent plays: **Bb7**`
- Keeps the flow fast and focused

### 2. Smooth Timing
- **1.5 seconds** between player move and opponent response
- **2 seconds** before advancing to next position
- Natural pacing for learning

### 3. Turn-Based Logic
- System tracks whose turn it is
- Only validates moves when it's the player's turn
- Auto-plays when it's opponent's turn

### 4. Move Tree Integration
- Both player and engine moves are added to the move tree
- PGN is correctly built with both sides' moves
- Can navigate back through the full sequence

## Edge Cases Handled

### 1. Line Ends on Player Move
```typescript
if (newIndex >= idealLine.length) {
  // No opponent response needed
  addAssistantMessage("🎉 Perfect! You've completed the ideal line!");
  // Auto-advance
}
```

### 2. Line Ends on Opponent Move
```typescript
if (newIndex + 1 >= idealLine.length) {
  // Line complete after engine move
  addAssistantMessage("🎉 Perfect! You've completed the ideal line!");
  // Auto-advance
}
```

### 3. Player Deviates from Main Line
```typescript
else {
  // Evaluate the move
  // Mark as off main line
  // Show "Return to Main Line" button
  // Allow exploration
}
```

## Benefits

### For Students:
1. **Realistic Training:** Opponent actually responds, like in a real game
2. **Focus on Your Moves:** Don't have to play opponent's moves manually
3. **Hidden Solution:** Must find the moves yourself, not just read them
4. **Natural Flow:** Smooth back-and-forth like a real game

### For Coaches/Developers:
1. **Automatic Sequencing:** No manual scripting of both sides
2. **Consistent Responses:** Engine always plays the ideal line
3. **Flexible Duration:** Lessons can be 2, 3, 5+ moves long
4. **Easy Variations:** Can add branching logic later

## Configuration

### Backend: Position Generation
```python
# Each position can be generated for either side
pos = await generate_position_for_topic(topic_code, "white")  # Player is white
pos = await generate_position_for_topic(topic_code, "black")  # Player is black

# Position includes:
{
  "side": "white",           # Which side the player plays
  "ideal_line": ["b3", "b6", "Qc2", "Bb7", "Bb2"],
  "ideal_pgn": "9. b3 b6 10. Qc2 Bb7 11. Bb2"  # For internal use only
}
```

### Frontend: Auto-Play Delay
```typescript
setTimeout(() => {
  // Auto-play opponent move
}, 1500);  // 1.5 seconds - adjustable
```

## Future Enhancements

Potential additions:
- **Variable Delays:** Slower for beginners, faster for advanced
- **Move Annotations:** Show arrows/highlights for engine moves
- **Multi-Line Support:** Engine chooses from multiple good responses
- **Conditional Responses:** Engine adapts if player deviates then returns
- **Commentary Mode:** Engine "explains" its moves (optional)
- **Undo Feature:** Player can undo their move without resetting
- **Move Hints:** Progressive hints if player is stuck (shows engine move after 30s)

## Testing Scenarios

### Test 1: Full Line Completion
1. Generate IQP position (player: white)
2. Play all correct moves: b3, Qc2, Bb2
3. Verify engine plays: b6, Bb7
4. Confirm auto-advance to next position

### Test 2: Mid-Line Deviation
1. Start same position
2. Play b3 (correct) → engine plays b6
3. Play Bd3 (wrong) → should trigger deviation
4. Verify "Return to Main Line" button appears
5. Click return → board resets to position after b6

### Test 3: Player as Black
1. Generate position with player: black
2. Verify engine plays first (white's move)
3. Player responds
4. Verify alternating pattern continues

### Test 4: Odd-Length Lines
1. Generate position with 3-move line (player, opponent, player)
2. Verify engine plays middle move
3. Verify line completes after final player move

## Code Changes Summary

**Modified Files:**
- `frontend/app/page.tsx`
  - `loadLessonPosition()`: Removed ideal_pgn from displays
  - `checkLessonMove()`: Complete rewrite with turn-based logic and auto-play
  
**Behavior Changes:**
- ✅ Ideal line no longer shown to player
- ✅ Opponent moves auto-played from ideal line
- ✅ Only player moves receive detailed feedback
- ✅ 1.5 second delay between moves for natural pacing

**Backward Compatibility:**
- ✅ Still works with existing position generation
- ✅ Deviation system unchanged
- ✅ Return to main line still functional
- ✅ Progress tracking accurate

