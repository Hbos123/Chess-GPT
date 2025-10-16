# Lesson Ideal Line System

## Overview
The lesson system now includes **predefined solution paths** (ideal lines) that students must follow. Each lesson position has a 3-5 move ideal line that represents the best continuation. Students can explore variations but have the option to return to the main line.

## Backend Changes

### Position Generation (`generate_position_for_topic`)
**File:** `backend/main.py`

Added ideal line generation:
```python
# Generate the ideal solution line (best PV, 3-5 moves)
ideal_line = []  # List of moves in SAN
ideal_pgn = ""   # Human-readable PGN

if main_info and hasattr(main_info, '__iter__') and len(list(main_info)) > 0:
    best_info = list(main_info)[0]
    pv = best_info.get("pv", [])
    if pv:
        temp_board = board.copy()
        for i, move in enumerate(pv[:5]):  # Take first 5 moves
            move_san = temp_board.san(move)
            ideal_line.append(move_san)
            # Build PGN with move numbers
            temp_board.push(move)
        ideal_pgn = " ".join(pgn_parts)
```

**Returns:**
- `ideal_line`: `["b3", "b6", "Qc2", "Bb7", "Bb2"]` - List of moves to match
- `ideal_pgn`: `"9. b3 b6 10. Bb2 Bb7 11. Bd3"` - Display format

## Frontend Changes

### New State Variables
**File:** `frontend/app/page.tsx`

```typescript
const [lessonMoveIndex, setLessonMoveIndex] = useState(0);
const [isOffMainLine, setIsOffMainLine] = useState(false);
const [mainLineFen, setMainLineFen] = useState<string>("");
```

### `loadLessonPosition` Updates
- Displays the ideal PGN as a goal: `*Goal: Play the line 9. b3 b6 10. Bb2*`
- Resets `lessonMoveIndex` to 0
- Saves starting FEN for returning to main line

### `checkLessonMove` Rewrite
**Core Logic:**
1. **Check if move matches ideal line:**
   ```typescript
   const expectedMove = idealLine[lessonMoveIndex];
   const isOnMainLine = moveSan === expectedMove;
   ```

2. **If on main line:**
   - Increment `lessonMoveIndex`
   - Give encouraging feedback via LLM
   - If line completed, auto-advance to next position

3. **If deviation:**
   - Call backend to evaluate the move quality
   - Mark `isOffMainLine = true`
   - Save FEN to allow return
   - Provide feedback about the deviation

### `returnToMainLine` Function
```typescript
function returnToMainLine() {
  setFen(mainLineFen);              // Reset to saved FEN
  setGame(new Chess(mainLineFen));  // Reset game state
  setMoveTree(new MoveTree());      // Clear move history
  setIsOffMainLine(false);          // Clear deviation flag
  addSystemMessage("♻️ Returned to main line. Try again!");
}
```

### UI Components

#### "Return to Main Line" Button
- **Appears when:** `isOffMainLine === true`
- **Position:** Below lesson mode indicator
- **Style:** Orange gradient button with hover effects
- **Action:** Calls `returnToMainLine()`

```tsx
{lessonMode && isOffMainLine && (
  <button 
    className="return-to-main-line-button"
    onClick={returnToMainLine}
  >
    ♻️ Return to Main Line
  </button>
)}
```

#### Lesson Mode Indicator Enhancement
Shows "(Off Main Line)" warning when player deviates:
```tsx
<div className="lesson-mode-indicator">
  📚 Lesson Mode {isOffMainLine && <span style={{color: '#f59e0b'}}>(Off Main Line)</span>}
</div>
```

## CSS Styling
**File:** `frontend/app/styles.css`

```css
.return-to-main-line-button {
  position: absolute;
  top: 45px;
  right: 10px;
  background: linear-gradient(135deg, #f59e0b, #d97706);
  border: none;
  padding: 8px 16px;
  border-radius: 20px;
  font-size: 13px;
  font-weight: 600;
  color: white;
  cursor: pointer;
  box-shadow: 0 4px 12px rgba(245, 158, 11, 0.3);
  transition: all 0.2s ease;
  z-index: 10;
}

.return-to-main-line-button:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(245, 158, 11, 0.4);
  background: linear-gradient(135deg, #fbbf24, #f59e0b);
}
```

## User Experience Flow

### 1. Position Loaded
```
📚 Lesson Position 1/3

Welcome to this IQP position! [LLM intro]

*Goal: Play the line 9. b3 b6 10. Bb2 Bb7 11. Bd3*

💡 Objective: Play for the e5 break...
Hints:
• The e5 break is typical in IQP positions
• Keep your pieces active
Target line: 9. b3 b6 10. Bb2 Bb7 11. Bd3
```

### 2. Player Makes Correct Move (b3)
```
System: Checking your move...

✅ Correct! This move prepares to develop your light-squared bishop 
and supports the center. Well done!
```
➡️ Continues to next move in sequence

### 3. Player Deviates (plays Qc2 instead of b3)
```
System: Checking your move...

📝 You deviated from the ideal line by playing Qc2 instead of b3. 
While this is a reasonable developing move with only a small loss 
in evaluation, the main line with b3 prepares the fianchetto more 
accurately. You can continue exploring this variation or return to 
the main line to practice the ideal sequence.
```
➡️ "Return to Main Line" button appears
➡️ Player can continue or reset

### 4. Line Completed
```
🎉 Perfect! You've completed the ideal line for this position!

[2 second delay]

📚 Lesson Position 2/3
[Next position loads]
```

### 5. All Positions Complete
```
🏆 Lesson Complete! You've successfully completed all positions. 
Excellent work!

[Lesson mode ends]
```

## Benefits

1. **Clear Goals:** Students know exactly what moves to aim for
2. **Flexible Learning:** Can explore variations but return to practice the ideal line
3. **Progressive Difficulty:** Each position has a multi-move sequence to master
4. **Immediate Feedback:** Students know instantly if they're on track
5. **Exploration Mode:** Deviations are evaluated and explained, not penalized

## Technical Details

### Move Matching
- Uses **exact SAN match**: `moveSan === expectedMove`
- Case-sensitive: "Nf3" ≠ "nf3"
- Includes captures, checks: "Qxe5+", "O-O", etc.

### FEN Tracking
- `mainLineFen` stores the position where deviation occurred
- Allows precise return to that exact moment
- Move tree is reset to prevent confusion

### Auto-Advancement
- 2-second delay after completing ideal line
- Smooth transition between positions
- Progress bar updates automatically

### Variation Exploration
- All moves are legal (chess rules enforced)
- Engine evaluates alternative moves
- LLM provides context-aware feedback
- Can continue playing in variation mode

## Example Lesson Flow

**Position:** IQP Structure
**Ideal Line:** `["b3", "b6", "Qc2", "Bb7", "Bb2"]`
**Goal:** Develop pieces harmoniously while maintaining pressure

**Student moves:**
1. `b3` ✅ Correct (1/5)
2. `b6` ✅ Correct (2/5)
3. `Bd3` ❌ Deviation (expected Qc2)
   - Feedback: "Reasonable but premature..."
   - **[Return button appears]**
4. Student clicks "♻️ Return to Main Line"
   - Board resets to position after `b6`
5. `Qc2` ✅ Correct (3/5)
6. `Bb7` ✅ Correct (4/5)
7. `Bb2` ✅ Correct (5/5)
   - 🎉 Position complete!
   - Auto-advance to Position 2

## Future Enhancements

Potential additions:
- **Multiple solution paths:** Accept alternate moves if equally good
- **Hints system:** Progressive hints if student is stuck
- **Time tracking:** Record how long each position takes
- **Retry counter:** Track attempts before completing
- **Difficulty adjustment:** Shorter lines for beginners, longer for advanced
- **Interactive variations:** AI plays opponent moves in the ideal line
- **Branch visualization:** Show the ideal line as a tree diagram

