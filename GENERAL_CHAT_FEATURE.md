# General Chat Feature - Contextual AI Responses

## Overview

The system now includes **intelligent general chat detection** that skips unnecessary analysis and provides contextual suggestions based on the current board state.

## How It Works

### Message Flow with General Chat Detection:

```
User sends message
    ↓
Is it general chat? (hi, hello, thanks, etc.)
    ↓ YES
Skip analysis logic ✅
    ↓
Detect board context:
  • Starting position (empty)
  • Game in progress (N moves)
  • Custom position set
    ↓
Generate context-aware response with suggestions
    ↓
User sees natural reply + relevant options
```

### Old Behavior (Before):
```
User: "hi"
System: "Not a valid move. Use board or standard notation."
❌ Not helpful!
```

### New Behavior (After):
```
User: "hi"
System: "Hello! 👋 I see you're at the starting position. Would you like to:
        • Start a game (try typing 'e4')
        • Analyze an opening
        • Solve a chess puzzle?"
✅ Helpful and contextual!
```

## Board Context Detection

### Function: `getBoardContext()`

```typescript
function getBoardContext(): string {
  const isStartPosition = fen === INITIAL_FEN;
  const hasMoves = pgn.length > 0 && game.history().length > 0;
  const moveCount = game.history().length;
  
  if (isStartPosition && !hasMoves) {
    return "starting_position_empty";
  } else if (hasMoves) {
    return `game_in_progress_${moveCount}_moves`;
  } else if (!isStartPosition) {
    return "custom_position_set";
  }
  return "unknown";
}
```

### Board States Detected:

1. **`starting_position_empty`**
   - FEN matches initial position
   - No moves have been played
   - PGN is empty

2. **`game_in_progress_N_moves`**
   - Moves have been played
   - PGN contains game data
   - N = number of moves

3. **`custom_position_set`**
   - FEN differs from starting position
   - No game history
   - Custom setup

## General Chat Detection

### Function: `isGeneralChat()`

```typescript
function isGeneralChat(msg: string): boolean {
  const lower = msg.toLowerCase().trim();
  
  // Greetings
  const greetings = ["hi", "hello", "hey", "yo", "sup", "howdy", "greetings"];
  if (greetings.includes(lower)) return true;
  
  // Questions about the app
  if (lower.includes("what can you do") || 
      lower.includes("what are you") ||
      lower.includes("who are you") ||
      lower.includes("help me") ||
      lower.includes("how does this work")) return true;
  
  // Pleasantries
  if (lower.includes("how are you") || 
      lower.includes("what's up") ||
      lower.includes("thanks") ||
      lower.includes("thank you")) return true;
  
  return false;
}
```

### Triggers:
- ✅ "hi", "hello", "hey", "yo", "sup", "howdy", "greetings"
- ✅ "what can you do?", "who are you?", "what are you?"
- ✅ "help me", "how does this work?"
- ✅ "how are you?", "what's up?"
- ✅ "thanks", "thank you"

### Does NOT Trigger:
- ❌ "e4" (chess move)
- ❌ "analyze" (specific request)
- ❌ "what should I do?" (chess question)

## Contextual Responses

### Scenario 1: Starting Position (Empty Board)

**User:** "hi"

**LLM Context Provided:**
```
User sent: "hi"

Board State:
- FEN: rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1
- Is starting position: true
- Has moves played: false
- Move count: 0

Context: The board is at the starting position with no moves played yet.

Instructions:
1. Respond warmly to their greeting
2. Suggest: starting a game, analyzing openings, or solving tactics
3. Keep it concise (2-3 sentences)
4. Don't analyze the position unless explicitly asked
```

**Example Response:**
```
Hello! 👋 Welcome to Chess GPT! I see you're at the starting position. 

Would you like to:
• Start a game by typing a move like 'e4'
• Click "Analyze Position" to explore opening strategies
• Try "Next Tactic" to sharpen your skills with puzzles

What sounds fun?
```

### Scenario 2: Game in Progress

**User:** "hey"

**Board State:**
- Move count: 5
- FEN: Custom (after 5 moves)
- PGN: "1. e4 e5 2. Nf3 Nc6 3. Bb5"

**LLM Context Provided:**
```
Context: There's a game in progress with 5 moves played.

Instructions:
- Offer to analyze the position
- Suggest next moves
- Offer to review the game
```

**Example Response:**
```
Hey there! I see you've got a Ruy Lopez going with 5 moves played. 

You can:
• Continue playing (make your next move)
• Ask "What should I do?" for move suggestions
• Click "Analyze Position" to evaluate your position
• Copy your PGN to save the game

Need help deciding your next move?
```

### Scenario 3: Custom Position Setup

**User:** "hello"

**Board State:**
- FEN: Custom (not starting position)
- No moves played
- Empty PGN

**Example Response:**
```
Hello! I notice you have a custom position set up on the board.

Would you like to:
• Analyze this position to understand the evaluation
• Start playing from here
• Ask questions about the position

Just let me know what you'd like to explore!
```

## Without LLM (Fallback Mode)

When LLM is disabled, the system provides structured suggestions:

### Starting Position:
```
Hello! I'm Chess GPT. Here's what you can do:

• Type a move like 'e4' to start playing
• Click 'Analyze Position' to get insights
• Click 'Next Tactic' to solve puzzles
• Ask me anything about chess!
```

### Game in Progress:
```
Hello! I'm Chess GPT. I see you've played 5 moves. You can:

• Continue playing (make your next move)
• Click 'Analyze Position' to evaluate the current position
• Ask 'What should I do?' for advice
• Click 'Copy PGN' to save your game
```

### Custom Position:
```
Hello! I'm Chess GPT. I see you have a custom position set up. You can:

• Click 'Analyze Position' to evaluate it
• Start playing from this position
• Ask questions about the position
```

## Implementation Details

### Priority Order in `handleSendMessage()`:

```typescript
async function handleSendMessage(message: string) {
  addUserMessage(message);

  // 1. Check general chat FIRST (highest priority)
  if (isGeneralChat(message)) {
    await handleGeneralChat(message);
    return;  // Skip all other logic
  }

  // 2. Then check for mode inference
  const inferredMode = inferModeFromMessage(message);
  
  // 3. Then try move parsing if in PLAY mode
  if (effectiveMode === "PLAY") {
    // Try to parse as move...
  }
  
  // 4. Finally route to specific handlers
  switch (effectiveMode) {
    case "ANALYZE": ...
    case "TACTICS": ...
    case "DISCUSS": ...
  }
}
```

### Key Design Decisions:

1. **General chat checked FIRST** - Avoids treating "hi" as invalid move
2. **Skips analysis** - No Stockfish call for greetings
3. **Context-aware** - Different suggestions based on board state
4. **Fast response** - Minimal processing for simple greetings
5. **Helpful** - Always provides actionable next steps

## Meta Information Stored

For general chat responses:

```typescript
const meta = {
  type: "general_chat",
  boardContext: "starting_position_empty",  // or game_in_progress_5_moves, etc.
  fen: "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
  moveCount: 0
};
```

This appears in the 📊 button modal as:
```
Type: general_chat
Board Context: starting_position_empty
Position (FEN): rnbqkbnr/...
Move Count: 0
```

## Testing Examples

### Test 1: Simple Greeting
```
Input: "hi"
Expected: Warm greeting + context-based suggestions
Board: Starting position
Result: ✅ Suggests starting game, analyzing, or tactics
```

### Test 2: Greeting Mid-Game
```
Input: "hello"
Expected: Greeting + game-specific suggestions
Board: 8 moves played
Result: ✅ Suggests continuing game, analyzing position, reviewing
```

### Test 3: Custom Position
```
Input: "hey"
Expected: Greeting + position-specific options
Board: Custom FEN, no moves
Result: ✅ Suggests analyzing position or playing from here
```

### Test 4: Thanks After Analysis
```
Input: "thanks"
Board: Any state
Result: ✅ Warm response + ask if need anything else
```

### Test 5: App Questions
```
Input: "what can you do?"
Expected: Feature overview + contextual suggestions
Result: ✅ Explains capabilities based on current state
```

## Benefits

### For Users:
✅ **Natural Interaction** - Can greet the AI naturally
✅ **Contextual Help** - Gets relevant suggestions
✅ **No Confusion** - Greetings don't trigger move errors
✅ **Friendly Experience** - Feels conversational

### For System:
✅ **Efficient** - Skips unnecessary analysis
✅ **Smart Routing** - Detects intent early
✅ **Flexible** - Works with or without LLM
✅ **Extensible** - Easy to add more greeting patterns

## Future Enhancements

Potential improvements:
- [ ] Detect follow-up questions in conversation
- [ ] Remember user preferences from chat
- [ ] Multi-turn conversation context
- [ ] Detect frustration and offer help
- [ ] Language detection for international users

## Summary

The general chat feature makes Chess GPT feel more **natural** and **helpful** by:

1. **Detecting** when users are just chatting vs analyzing
2. **Understanding** the current board context
3. **Providing** relevant, actionable suggestions
4. **Skipping** unnecessary engine analysis
5. **Responding** warmly and naturally

**Status:** ✅ Fully implemented and context-aware!
