# Contextual Analysis Responses

## Overview

The AI now **adapts its response format** based on how you ask your question! Different questions get different levels of detail.

---

## Response Types

### 1️⃣ **"What should I do?" → CONCISE ADVICE**

**User Asks:**
- `"what should I do?"`
- `"what should white do?"`
- `"how should I proceed?"`
- `"help me find a move"`

**AI Response Format (2 sentences, ~40-50 words):**
```
Sentence 1: "You [have/don't have] an advantage here ([brief 6-word position summary])."
Sentence 2: "Play [candidate moves] to [plan]."
```

**Example:**
```
You: "what should I do here?"

AI: "You have an advantage here (active pieces, center control, better king safety). 
Play Nf3, e4, or d4 to develop pieces and control the center."

Board: Shows arrows on Nf3, e4, d4
```

---

### 2️⃣ **"Best move?" → SUPER CONCISE**

**User Asks:**
- `"best move?"`
- `"what's best?"`
- `"best moves"`

**AI Response Format (1-2 sentences, ~20-30 words):**
```
"Play [move] to [reason]. Alternative: [move2]."
```

**Example:**
```
You: "best move?"

AI: "Play e4 to control the center and open lines for your bishops. 
Alternative: d4."

Board: Green arrow on e4, blue arrow on d4
```

---

### 3️⃣ **"Show candidates" → OPTIONS LIST**

**User Asks:**
- `"what are my options?"`
- `"show me candidates"`
- `"show me moves"`
- `"candidates"`

**AI Response Format (1 sentence, ~30-40 words):**
```
"Your top options: [move1] ([reason]), [move2] ([reason]), or [move3] ([reason])."
```

**Example:**
```
You: "what are my options?"

AI: "Your top options: Nf3 (develops knight and prepares castling), 
e4 (controls center), or d4 (claims space)."

Board: Shows 3 arrows on all candidate moves
```

---

### 4️⃣ **"Analyze" → FULL ANALYSIS**

**User Asks:**
- `"analyze"`
- `"analyze position"`
- `"evaluate"`
- `"assess"`

**AI Response Format (3 sentences, ~60-80 words):**
```
Sentence 1: "This is [a/an] [opening/middlegame/endgame] position with [who's winning] (eval: [+/-]X.XX)."
Sentence 2: "[Side] [has the advantage/is equal/is behind] due to [evidence]."
Sentence 3: "It's [Side]'s turn to move, and they could [candidate moves] to [plan]."
```

**Example:**
```
You: "analyze"

AI: "This is an opening position with equal (eval: +0.32). White is equal 
due to balanced material and standard opening development. It's White's 
turn to move, and they could play e4 or d4 to control the center and 
develop pieces."

Board: Shows all visual annotations + analysis
```

---

## Complete Examples

### Example 1: Playing a game, quick advice

```
You: e4
AI: "Engine plays: e5. Eval: +0.28"

You: "what should I do?"
AI: "You have an advantage here (center control, active pieces, better development). 
Play Nf3, Bc4, or Nc3 to develop and prepare castling."

[Arrows show on Nf3, Bc4, Nc3]
[Click 📊 to see full ANALYSIS 1]
```

**Why this is better:**
- ✅ Direct answer to "what should I do?"
- ✅ Doesn't overwhelm with 3-sentence analysis
- ✅ Gives clear plan with candidates
- ✅ Still has full analysis in 📊 button

---

### Example 2: Want the best move quickly

```
You: "best move?"

AI: "Play Rf1 to activate your rook and pressure the f-file. 
Alternative: Nc3."

[Green arrow on Rf1, blue arrow on Nc3]
```

**Why this is better:**
- ✅ Super concise (~25 words)
- ✅ Tells you exactly what to play
- ✅ Gives why + alternative
- ✅ No fluff

---

### Example 3: Exploring options

```
You: "what are my options?"

AI: "Your top options: Qd3 (centralizes queen and controls diagonals), 
Rf1 (activates rook), or Nc3 (develops knight and supports center)."

[3 arrows showing all options]
```

**Why this is better:**
- ✅ Answers the question directly
- ✅ Lists all top moves with reasons
- ✅ Easy to compare options
- ✅ Actionable

---

### Example 4: Deep dive analysis

```
You: "analyze"

AI: "This is a middlegame position with White has a slight advantage 
(eval: +0.75). White has the advantage due to superior piece activity, 
active Qd3, and better king safety. It's White's turn to move, and they 
could play Rf1 or Nc3 to press the advantage."

[Full visual annotations: arrows, highlights, threats]
[Click 📊 for complete ANALYSIS 1]
```

**Why this is better:**
- ✅ Complete 3-sentence analysis
- ✅ Includes evaluation, evidence, plan
- ✅ Professional format
- ✅ Detailed

---

## Behind the Scenes

### Question Detection System

```typescript
function shouldTriggerAnalysis(msg: string): { 
  shouldAnalyze: boolean; 
  questionType: string 
}

Question Types Detected:
├─ "what_should_i_do"  → Concise 2-sentence advice
├─ "best_move"         → Super concise best move
├─ "show_candidates"   → Options list
├─ "show_options"      → Options list
├─ "how_to_proceed"    → Concise advice
├─ "help_with_move"    → Concise advice
├─ "evaluation"        → Full analysis
├─ "assessment"        → Full analysis
└─ "full_analysis"     → Full 3-sentence analysis
```

### Analysis Pipeline

```
User asks question
    ↓
Detect question type
    ↓
Run Stockfish analysis (same for all)
    ↓
Generate ANALYSIS 1 (Chess GPT structured - logged to console)
    ↓
Generate visual annotations (arrows + highlights)
    ↓
Apply to board
    ↓
Select prompt template based on question type
    ↓
LLM generates contextual response
    ↓
User sees tailored answer
    ↓
Full ANALYSIS 1 stored in 📊 button
```

---

## All Question Formats

### ✅ Concise Advice (2 sentences, ~40-50 words)

| Triggers |
|----------|
| "what should I do?" |
| "what should white do?" |
| "what should black do?" |
| "how should I proceed?" |
| "how do I proceed?" |
| "help me find a move" |
| "help with move" |

**Format:**
```
"You [have/don't have] an advantage here ([6-word summary]). 
Play [moves] to [plan]."
```

---

### ✅ Super Concise (1-2 sentences, ~20-30 words)

| Triggers |
|----------|
| "best move?" |
| "best moves" |
| "what's best?" |
| "what is best?" |

**Format:**
```
"Play [move] to [reason]. Alternative: [move2]."
```

---

### ✅ Options List (1 sentence, ~30-40 words)

| Triggers |
|----------|
| "what are my options?" |
| "show me candidates" |
| "show me moves" |
| "candidate moves" |
| "candidates" |

**Format:**
```
"Your top options: [move1] ([reason]), [move2] ([reason]), [move3] ([reason])."
```

---

### ✅ Full Analysis (3 sentences, ~60-80 words)

| Triggers |
|----------|
| "analyze" |
| "analyze position" |
| "analyze this" |
| "evaluate" |
| "evaluation" |
| "assess" |
| "assessment" |

**Format:**
```
Sentence 1: Phase + who's winning + eval
Sentence 2: Evidence for assessment
Sentence 3: Side to move + candidates + plan
```

---

## Comparison Table

| Question Type | Words | Sentences | Detail Level | Use Case |
|--------------|-------|-----------|--------------|----------|
| **What should I do?** | 40-50 | 2 | Medium | Quick game advice |
| **Best move?** | 20-30 | 1-2 | Low | Fast decision |
| **Show options** | 30-40 | 1 | Medium | Compare moves |
| **Analyze** | 60-80 | 3 | High | Deep understanding |

---

## Benefits

### ✅ **Context-Aware**
```
Before:
  User: "best move?"
  AI: [3-sentence detailed analysis]
  User: "Too much text, I just wanted the move..."

After:
  User: "best move?"
  AI: "Play e4 to control center. Alternative: d4."
  User: "Perfect!" ✅
```

### ✅ **Efficient**
```
Quick question → Quick answer (20-30 words)
Detailed request → Detailed analysis (60-80 words)
```

### ✅ **Flexible**
```
Same position, different questions:
- "best move?" → 1 sentence
- "what should I do?" → 2 sentences  
- "analyze" → 3 sentences
- All backed by same Stockfish analysis!
```

### ✅ **Always Have Full Data**
```
Every response stores full ANALYSIS 1 in 📊 button
- Click 📊 to see complete Chess GPT analysis
- See all raw engine data
- No information lost
```

---

## Real Conversation Examples

### Conversation 1: Quick Game

```
You: "e4"
AI: "Engine plays: e5"

You: "best move?"
AI: "Play Nf3 to develop and attack e5. Alternative: Bc4."

You: "Nf3"
AI: "Engine plays: Nc6"

You: "what should I do?"
AI: "You have an advantage here (center control, developed pieces). 
Play Bb5 or Bc4 to develop and prepare castling."
```

**Perfect!** Quick answers for quick questions.

---

### Conversation 2: Deep Analysis

```
You: "analyze"

AI: "This is an opening position with equal (eval: +0.32). White is 
equal due to balanced material and standard development. It's White's 
turn to move, and they could play e4 or d4 to control the center."

[Click 📊]
[Modal shows full ANALYSIS 1 with all data]
```

**Perfect!** Detailed analysis when requested.

---

### Conversation 3: Exploring Options

```
You: "what are my options?"

AI: "Your top options: e4 (controls center and opens lines), 
d4 (claims space), or Nf3 (develops and prepares castling)."

[3 arrows on board]

You: "e4"
AI: "Engine plays: e5"
```

**Perfect!** Options list when exploring.

---

## Technical Implementation

### LLM Prompt Templates

#### 1. Concise Advice Template
```typescript
`You are answering "What should I do?" in a chess position. Be VERY concise.

REQUIRED FORMAT (2 sentences max):
Sentence 1: "You [have/don't have] an advantage here ([brief 6-word summary])."
Sentence 2: "Play [candidate moves] to [plan]."

Max tokens: 100
Temperature: 0.5
```

#### 2. Best Move Template
```typescript
`You are answering "What's the best move?" Be EXTREMELY concise.

REQUIRED FORMAT (1-2 sentences):
"Play [move] to [reason]. Alternative: [move2]."

Max tokens: 80
Temperature: 0.5
```

#### 3. Options Template
```typescript
`You are showing candidate moves. Be concise.

REQUIRED FORMAT:
"Your top options: [move1] ([reason]), [move2] ([reason]), [move3] ([reason])."

Max tokens: 100
Temperature: 0.5
```

#### 4. Full Analysis Template
```typescript
`You are analyzing a chess position. Generate concise 2-3 sentence response.

REQUIRED FORMAT:
Sentence 1: Phase + evaluation + who's winning
Sentence 2: Evidence for assessment
Sentence 3: Candidates + plan

Max tokens: 200
Temperature: 0.5
```

---

## Testing Examples

### Test 1: Concise Advice
```
Input: "what should I do here?"
Expected: 2 sentences, ~40-50 words
Format: "You have/don't have advantage (summary). Play moves to plan."
Result: ✅
```

### Test 2: Best Move
```
Input: "best move?"
Expected: 1-2 sentences, ~20-30 words
Format: "Play move to reason. Alternative: move2."
Result: ✅
```

### Test 3: Show Options
```
Input: "what are my options?"
Expected: 1 sentence, ~30-40 words
Format: "Your top options: move1 (reason), move2 (reason), move3 (reason)."
Result: ✅
```

### Test 4: Full Analysis
```
Input: "analyze"
Expected: 3 sentences, ~60-80 words
Format: Standard analysis format
Result: ✅
```

---

## Summary

✅ **4 Response Types** - Tailored to your question
✅ **Smart Detection** - Automatically determines format
✅ **Always Efficient** - No wasted words
✅ **Full Data Available** - 📊 button has everything
✅ **Natural Conversation** - Ask how you naturally would
✅ **Same Analysis Quality** - Stockfish + Chess GPT always run
✅ **Visual Annotations** - Always applied to board

**The AI now speaks your language!** 🎯♟️

---

## Usage Tips

### Quick Decision?
❓ Ask: `"best move?"`
✅ Get: 1 sentence with the move

### Want Advice?
❓ Ask: `"what should I do?"`
✅ Get: 2 sentences with plan

### Exploring?
❓ Ask: `"what are my options?"`
✅ Get: List of 3 moves with reasons

### Deep Dive?
❓ Ask: `"analyze"`
✅ Get: Full 3-sentence analysis

### Want More Detail?
❓ Click: 📊 button
✅ Get: Complete ANALYSIS 1 + raw data

---

**Status:** ✅ Fully implemented and context-aware!

Test it now at http://localhost:3000! 🚀
