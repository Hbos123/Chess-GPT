# Hypothetical Moves & Context-Aware Analysis

## New Features Added

### 1. **Context-Aware Move Analysis** 📍
The LLM now receives full context about the current position when analyzing moves:
- **Current FEN**: Position at time of analysis
- **Current PGN**: Full game history
- **Position before move**: For last move analysis

This ensures the AI understands WHICH position you're asking about, not just the move itself.

### 2. **Hypothetical Move Exploration** 🔮
You can now ask "what if" questions and the move will be:
- Analyzed by Stockfish
- Added to the move tree as a variation
- Displayed on the board
- Evaluated with natural language response

## Trigger Patterns

### Hypothetical Moves
- "**what if I play** e4?"
- "**what about** Nf3?"
- "**how about** playing Qxe5?"
- "**should I play** d4?"
- "**would** Bc4 be good?"
- "**could I play** O-O here?"
- "**if I play** Rxf7..."

### Regular Analysis
- "**analyze** the last move"
- "**rate** Bxg5"
- "**what do you think of** my last move?"
- "**evaluate** Nf3"

## Implementation Details

### Frontend Changes

#### 1. Enhanced Move Detection
**File:** `frontend/app/page.tsx`

```typescript
function detectMoveAnalysisRequest(msg: string): { 
  isMoveAnalysis: boolean; 
  move: string | null; 
  isHypothetical: boolean // NEW FLAG
} {
  const hypotheticalPatterns = [
    "what if i play", "what if i played", "what about playing", "what about",
    "how about", "should i play", "would", "could i play", "can i play",
    "if i play", "if i played"
  ];
  
  const isHypothetical = hypotheticalPatterns.some(pattern => lower.includes(pattern));
  
  // ... rest of detection logic
  
  return { isMoveAnalysis: true, move: extractedMove, isHypothetical };
}
```

#### 2. Hypothetical Move Tree Integration
When a hypothetical move is detected:

```typescript
if (isHypothetical) {
  try {
    const testGame = new Chess(fenToAnalyze);
    const moveObj = testGame.move(moveToAnalyze);
    
    if (moveObj) {
      const newFen = testGame.fen();
      const newTree = moveTree.clone();
      newTree.addMove(moveObj.san, newFen, `hypothetical eval ${report.evalAfter}cp`);
      setMoveTree(newTree);
      setFen(newFen);
      setPgn(newTree.toPGN());
      setGame(testGame);
      setTreeVersion(v => v + 1);
    }
  } catch (err) {
    console.error("Failed to add hypothetical move to tree:", err);
  }
}
```

#### 3. Context-Aware LLM Prompts
Now includes position context:

```typescript
const llmPrompt = `You are analyzing a chess move${isHypothetical ? ' (hypothetical)' : ''}. 

CURRENT POSITION FEN: ${fenToAnalyze}
CURRENT PGN: ${pgn || 'Starting position'}
MOVE ANALYZED: ${moveToAnalyze}
...

INSTRUCTIONS:
${isHypothetical ? 'Frame as "if you play this" or "this would...".' : 'Frame as analysis of the position.'}
...`;
```

## User Experience

### Before
```
User: "what about e4?"
AI: "e4 would improve by 15cp..." 
(analyzing from starting position regardless of board state)
```

### After
```
User: "what about e4?"
AI: "If you play e4 here, it would improve your position by 15cp..."
(analyzing from CURRENT board position)
(move added to board as variation)
```

## Example Usage

### Scenario 1: Exploring Alternatives
```
[After playing d4]
User: "what if I had played e4 instead?"

AI: "If you play e4 here, it would be slightly better (+12cp) than d4. 
     The move gains center control and activates your light-squared bishop. 
     It creates threats like Nc3 and Nf3, putting immediate pressure on Black."

[e4 appears on board as alternate branch from starting position]
```

### Scenario 2: Asking About Current Position
```
[Mid-game position]
User: "should I play Bxf7+?"

AI: "Exploring hypothetical move Bxf7+..."

AI: "If you play Bxf7+, it would worsen your position by 280cp - this is a mistake. 
     The bishop sacrifice fails because after Kxf7, you don't have sufficient compensation. 
     Better is Nf3, maintaining pressure with a +40cp advantage."

[Bxf7+ added to tree, board shows resulting position]
```

### Scenario 3: Analyzing Last Move
```
[After playing Qxe5]
User: "analyze last move"

AI: "Qxe5 was an excellent move, improving by 85cp. 
     It gained material advantage and king safety while activating your queen. 
     The move creates threats like Qe7+ and Qxh8, winning more material."

[Uses context of actual played position, not current board state]
```

## Benefits

1. **Accurate Context**: AI knows WHICH position you're asking about
2. **Visual Exploration**: Hypothetical moves appear on the board
3. **Branch Management**: Create variations without committing
4. **Natural Language**: "What if" questions feel natural
5. **Learning Tool**: Explore alternatives safely
6. **Decision Making**: Compare multiple candidate moves

## Technical Notes

- **FEN Tracking**: Uses `fenToAnalyze` variable to track correct position
- **PGN Context**: Full game history provided to LLM for context
- **Tree Integration**: Hypothetical moves added as variations
- **State Management**: Board updates to show hypothetical position
- **Reversible**: Can navigate back through move tree

## Future Enhancements

Potential additions:
- "Compare e4 vs d4" - analyze multiple moves
- "Show me the best 3 moves here" - batch analysis
- "Undo hypothetical" - quick branch deletion
- Visual indicators for hypothetical vs played moves

All features working! Test with phrases like "what if I play Nf3?" or "should I play Qh5?" 🎉

