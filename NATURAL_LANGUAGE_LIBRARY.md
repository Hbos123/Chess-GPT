# Natural Language Library - Complete Reference

## Comprehensive Natural Language Support for Move Analysis

The Chess GPT system now supports an extensive natural language library for analyzing moves in various contexts. The AI understands hundreds of different ways to ask about moves.

---

## 🎯 **1. HYPOTHETICAL MOVES** (Future/Conditional)

Ask "what if" questions about moves you're considering playing.

### What If Patterns
```
✓ "what if I play e4?"
✓ "what if I played Nf3?"
✓ "what if I had played Qxe5?"
✓ "what if we play d4?"
✓ "what if I go with Bc4?"
✓ "what if I went O-O?"
```

### Question Patterns
```
✓ "what about e4?"
✓ "how about Nf3 here?"
✓ "what do you think about playing d4?"
✓ "should I play Qh5?"
✓ "should I have played Nc6?"
✓ "should I go with Bxf7?"
✓ "is it good to play e5?"
✓ "is it worth playing Rxf7?"
```

### Would/Could Patterns
```
✓ "would it be good to play e4?"
✓ "would it work if I played Bxh7?"
✓ "would playing Nf6 be better?"
✓ "could I play Qh4 here?"
✓ "can I play O-O?"
✓ "could I have played d5?"
```

### Conditional Patterns
```
✓ "if I play e4"
✓ "if I played Nf3"
✓ "if I had played d4"
✓ "if I go with Bc4"
✓ "if I went Qxe5"
✓ "if I move my knight"
```

### Consider/Explore Patterns
```
✓ "considering e4"
✓ "thinking about Nf3"
✓ "exploring d4"
✓ "looking at Bc4"
✓ "trying Qh5"
✓ "contemplating O-O"
```

---

## 📍 **2. CURRENT POSITION ANALYSIS**

Ask about moves in the context of the current board position.

### Position Reference Patterns
```
✓ "what's best here?"
✓ "in this position, should I play e4?"
✓ "from here, what about Nf3?"
✓ "from this position, how is d4?"
✓ "now what should I do?"
✓ "currently, is e5 good?"
✓ "at this point, what about Bc4?"
✓ "right now, should I castle?"
✓ "in this position, analyze Qh5"
✓ "from the current position, rate d5"
```

---

## 📜 **3. PREVIOUS MOVE ANALYSIS**

Analyze moves that have already been played.

### Last Move Patterns
```
✓ "analyze the last move"
✓ "rate my last move"
✓ "what do you think of that move?"
✓ "how was my previous move?"
✓ "was this move good?"
✓ "thoughts on the move I just played?"
✓ "evaluate my recent move"
✓ "how is the move?"
✓ "was that move a mistake?"
```

### Specific Move Analysis
```
✓ "analyze e4" (after you played e4)
✓ "rate Nf3"
✓ "what do you think of my Bxf7?"
✓ "evaluate Qh5"
✓ "assess d4"
✓ "was Nc6 good?"
```

---

## 🔄 **4. COMPARISON ANALYSIS** (Instead of / Better than)

Compare hypothetical moves to what was actually played.

### Instead Of Patterns
```
✓ "what if I played e4 instead of d4?"
✓ "e4 instead of d4"
✓ "Nf3 rather than Nc3"
✓ "Bxf7 vs Nf3"
✓ "Qh5 versus d4"
✓ "e5 compared to d5"
✓ "Nc6 over Nf6"
```

### Better/Alternative Patterns
```
✓ "would e4 be better than d4?"
✓ "is Nf3 stronger than Nc3?"
✓ "Bxf7 or Nf3?"
✓ "prefer e5 or d5?"
✓ "alternative to d4?"
✓ "better move than Qh5?"
```

**What happens:**
- Both moves are analyzed
- The AI compares their evaluations
- Explains why one is better/worse than the other
- Shows the evaluation difference

---

## 🔍 **5. GENERAL ANALYSIS REQUESTS**

Various ways to ask for move evaluation.

### Analyze Keywords
```
✓ "analyze e4"
✓ "analyse Nf3"
✓ "break down d4"
✓ "look at Bc4"
✓ "analysis of Qh5"
```

### Rate/Evaluate
```
✓ "rate e4"
✓ "rating of Nf3"
✓ "evaluate d4"
✓ "evaluation of Bc4"
✓ "assess Qh5"
✓ "assessment of O-O"
✓ "judge my move"
✓ "review e5"
✓ "check d5"
✓ "examine Nf6"
```

### Opinion Patterns
```
✓ "what do you think of e4?"
✓ "what do you think about Nf3?"
✓ "what do you make of d4?"
✓ "your thoughts on Bc4?"
✓ "thoughts on Qh5"
✓ "opinion on O-O"
✓ "your view on e5"
✓ "your take on d5"
```

### Quality Questions
```
✓ "how is e4?"
✓ "how was Nf3?"
✓ "how's d4?"
✓ "how good is Bc4?"
✓ "is this good?"
✓ "was this good?"
✓ "is that good?"
✓ "was that good?"
✓ "is it good?"
✓ "was it good?"
✓ "good move?"
```

### Comparison
```
✓ "compare e4 and d4"
✓ "which is better: Nf3 or Nc3?"
✓ "is e4 stronger than d4?"
✓ "is Nf3 weaker than Nc3?"
```

---

## 💡 **EXAMPLE CONVERSATIONS**

### Example 1: Hypothetical Move
```
User: "what if I play Bxf7+ here?"

System: Exploring hypothetical move Bxf7+...

AI: "If you play Bxf7+, it would worsen your position by 280cp - this is a 
     mistake. The sacrifice fails because after Kxf7, you don't have sufficient 
     compensation. Better is Nf3, maintaining +40cp advantage."

[Move added to tree as variation, board shows result]
```

### Example 2: Current Position
```
User: "in this position, is e5 good?"

System: Analyzing move e5 from current position...

AI: "e5 is an excellent move, improving by 65cp. It gains central space and 
     opens lines for your pieces while restricting Black's knight. The move 
     creates tactical threats on d6 and f6."

[Move analyzed from current board state]
```

### Example 3: Previous Move
```
User: "analyze my last move"

AI: "Qxe5 was an excellent move, improving by 85cp. It gained material advantage 
     and king safety while activating your queen. The move creates threats like 
     Qe7+ and Qxh8, winning more material."

[Uses actual game history for context]
```

### Example 4: Comparison
```
User: "what if I had played e4 instead of d4?"

System: Exploring hypothetical move e4...

AI: "If you play e4, it would improve by 35cp compared to d4 which gave +20cp. 
     e4 is slightly superior because it opens more lines for your light-squared 
     bishop. However, both moves are good, and d4 is still solid."

[Compares evaluation of e4 vs the played d4]
```

### Example 5: Multi-Context
```
[After playing several moves]
User: "should I play Nc6 now?"

System: Exploring hypothetical move Nc6...

AI: "If you play Nc6 here, it would improve by 15cp and is a good move. The 
     knight develops to an active square and supports the d4 pawn. It also 
     prepares castling, though Nf6 is slightly more accurate (+25cp)."

[Board shows Nc6 as new variation]
```

---

## 🎨 **BEHAVIOR BASED ON CONTEXT**

### Hypothetical Moves
- ✅ Move is analyzed from current position
- ✅ Move is added to the move tree as a variation
- ✅ Board updates to show the result
- ✅ Response framed as "if you play..." or "this would..."
- ✅ Can navigate back through the tree

### Current Position Analysis
- ✅ Uses the current FEN from the board
- ✅ Provides analysis specific to the displayed position
- ✅ References the current game state
- ✅ Optionally adds move if hypothetical

### Previous Move Analysis
- ✅ Retrieves the move from game history
- ✅ Analyzes from the position before that move
- ✅ Shows what actually happened
- ✅ Response framed in past tense

### Comparison Analysis
- ✅ Analyzes both moves
- ✅ Compares evaluations
- ✅ Explains the difference
- ✅ Recommends which is better

---

## 🔧 **TECHNICAL IMPLEMENTATION**

### Detection Algorithm
1. **Pattern Matching**: Scans message for trigger phrases
2. **Move Extraction**: Extracts chess notation (e4, Nf3, O-O, etc.)
3. **Context Detection**: Identifies hypothetical vs actual
4. **Reference Detection**: Finds "instead of" comparisons
5. **Position Mapping**: Determines which FEN to use

### Response Generation
1. **Backend Analysis**: Stockfish evaluates position
2. **Context Assembly**: FEN + PGN + move data
3. **LLM Synthesis**: Natural language response generated
4. **Board Update**: Visual state updated if hypothetical
5. **Tree Integration**: Move added as variation if needed

---

## 📊 **SUPPORTED FORMATS**

### Chess Notation
```
✓ Pawn moves: e4, d5, a3, h6
✓ Piece moves: Nf3, Bc4, Qh5, Rd1, Ke2
✓ Captures: exd5, Nxe5, Bxf7, Qxe4
✓ Castling: O-O, O-O-O
✓ Promotion: e8=Q, a1=N
✓ Check/Mate: Qh5+, Nf7#
```

---

## 🚀 **KEY FEATURES**

1. **Context-Aware**: Always knows which position you're asking about
2. **Natural Language**: Hundreds of trigger phrases supported
3. **Flexible**: Works with typos and variations
4. **Visual**: Shows results on the board
5. **Reversible**: Can navigate back through variations
6. **Intelligent**: LLM understands intent and nuance
7. **Comprehensive**: Handles past, present, and hypothetical scenarios

---

## 📝 **TIPS FOR BEST RESULTS**

1. **Be Specific**: Include the move notation (e.g., "e4", "Nf3")
2. **Use Context**: Say "here", "now", or "in this position" for clarity
3. **Compare Freely**: Ask "X instead of Y" to understand differences
4. **Explore Safely**: Hypothetical moves don't affect your main game line
5. **Ask Follow-ups**: "Why is that better?" or "What happens after?"

---

All features are live! Try asking in any of these ways and the AI will understand! 🎉

