# Chess GPT API Pipeline Upgrade

## Overview

The API pipeline has been upgraded to include a **two-stage LLM response system**:

1. **Stage 1:** Generate structured Chess GPT analysis (format-driven)
2. **Stage 2:** Use structured analysis to inform a natural LLM conversation

This ensures users get natural, conversational responses while maintaining the ability to view the underlying structured analysis.

## New Pipeline Flow

### Before (Old System):
```
User Question
    ↓
Backend Analysis (Stockfish)
    ↓
Raw Engine Data → Directly to User ❌
```

### After (New System):
```
User Question
    ↓
Backend Analysis (Stockfish)
    ↓
Generate Chess GPT Structured Response
    ↓
Structured Response + Context → Final LLM Call
    ↓
Natural Conversational Response → User ✅
    ↓
[📊 Button] → View Chess GPT Structured Analysis
```

## Stage 1: Chess GPT Structured Response

### Format:
```
Verdict: = (Equal position)

Key Themes:
1. Opening development
2. Center control
3. Pawn structure

Candidate Moves:
1. e4 - Establishes central control and opens lines for development.
2. d4 - Also claims the center and prepares to develop the pieces.
3. Nf3 - Develops a knight and prepares for castling.

Critical Line (e4):
1. e4 e5
2. Nf3 Nc6
3. Bb5

Plan: Develop pieces towards the center while controlling key squares.

One Thing to Avoid: Avoid moving the same piece multiple times in the opening unless necessary.
```

### How It's Generated:

```typescript
function generateChessGPTStructuredResponse(analysisData: any): string {
  // 1. Determine verdict based on evaluation
  const evalCp = analysisData.eval_cp || 0;
  const verdict = evalCp > 150 ? "+/- (White is better)" :
                  evalCp > 50 ? "+/= (White is slightly better)" :
                  evalCp < -150 ? "-/+ (Black is better)" :
                  evalCp < -50 ? "=/+ (Black is slightly better)" :
                  "= (Equal position)";

  // 2. Extract themes from engine data
  const themes = analysisData.themes || ["Opening development", "Center control", "Pawn structure"];

  // 3. Format candidate moves with descriptions
  const candidates = analysisData.candidate_moves.map((c, i) => 
    `${i + 1}. ${c.move} - ${getCandidateDescription(c)}`
  );

  // 4. Format critical line (PV of best move)
  const criticalLine = formatPVLine(analysisData.candidate_moves[0].pv_san);

  // 5. Generate plan and advice
  // ...

  return structuredResponse;
}
```

## Stage 2: Final LLM Response

### Context Provided to LLM:

```typescript
const contextMessage = `
Current Position (FEN): ${fen}
Current PGN: ${pgn}
Mode: ${inferredMode} (${modeContext})
Chat History: ${messages.slice(-3).map(m => `${m.role}: ${m.content}`).join("\n")}

Chess GPT Analysis:
${structuredAnalysis}

Raw Engine Data:
${JSON.stringify(toolOutput, null, 2)}

User Message: ${userMessage}

Instructions: Respond naturally and conversationally based on the Chess GPT analysis above. 
Keep your response concise (2-3 paragraphs max). Focus on being helpful and engaging.
`;
```

### Example Final Response:

**User:** "What should I do here?"

**Stage 1 (Chess GPT Structured - Hidden):**
```
Verdict: = (Equal position)
Key Themes: 1. Opening development 2. Center control...
[Full structured response]
```

**Stage 2 (Final LLM Response - Shown to User):**
```
This is the starting position, so we have an equal game ahead! The key here is to 
establish control of the center quickly. The three main opening moves—e4, d4, and 
Nf3—all accomplish this in different ways.

I'd recommend starting with 1.e4, which opens up lines for your bishop and queen 
while immediately claiming the center. After 1.e4 e5 2.Nf3 Nc6 3.Bb5, you'll be 
in the Ruy Lopez, one of the most solid openings for White.

The main thing to avoid is moving the same piece twice in the opening. Each move 
should develop a new piece or improve your position—tempo is valuable!
```

## Mode Detection & Context

The system now includes **intelligent mode detection** from user messages:

```typescript
function inferModeFromMessage(msg: string): Mode | undefined {
  const lower = msg.toLowerCase();
  
  // Check for move patterns
  if (/^[KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](=[QRBN])?[+#]?$/.test(msg.trim())) {
    return "PLAY";
  }
  
  // Check for analysis keywords
  if (lower.includes("analyze") || lower.includes("assess")) return "ANALYZE";
  
  // Check for discussion keywords
  if (lower.includes("explain") || lower.includes("why")) return "DISCUSS";
  
  return undefined;
}
```

This context is included in the final LLM call:
- **PLAY** → "playing a game"
- **ANALYZE** → "analyzing positions"
- **TACTICS** → "solving tactics"
- **DISCUSS** → "discussing chess"

## Accessing Raw Data

### The 📊 Button

Every response with meta information includes a **📊 button**:

```typescript
{msg.meta && (
  <button 
    onClick={() => handleShowMeta(msg.meta)}
    className="meta-button"
    title="View raw analysis data"
  >
    📊
  </button>
)}
```

### Modal Contents

Clicking the 📊 button shows:

1. **Mode:** Current mode (PLAY/ANALYZE/TACTICS/DISCUSS)
2. **Position (FEN):** Current board position
3. **Chess GPT Structured Analysis:** The formatted analysis
4. **Raw Engine Output:** JSON from Stockfish

```typescript
const meta = {
  structuredAnalysis: "Verdict: = (Equal position)...",
  rawEngineData: { eval_cp: 32, candidate_moves: [...], ... },
  mode: "ANALYZE",
  fen: "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
};
```

## Implementation Details

### Key Functions

1. **`generateChessGPTStructuredResponse(analysisData)`**
   - Takes raw Stockfish output
   - Returns formatted Chess GPT analysis string
   - Includes verdict, themes, candidates, critical line, plan

2. **`generateLLMResponse(userMessage, toolOutput, structuredAnalysis)`**
   - Takes user message, raw data, and structured analysis
   - Calls OpenAI API with full context
   - Returns natural conversational response
   - Stores meta information with response

3. **`getCandidateDescription(candidate)`**
   - Generates natural language descriptions for moves
   - Uses heuristics based on move notation
   - Examples: "Establishes central control", "Develops knight"

4. **`formatPVLine(pv)`**
   - Formats principal variation into readable moves
   - Example: "1. e4 e5 2. Nf3 Nc6 3. Bb5"

### Updated Flow Functions

**`handleAnalyzePosition()`** now:
```typescript
async function handleAnalyzePosition() {
  const result = await analyzePosition(fen, 3, 16);
  
  // Generate Chess GPT structured response
  const structuredAnalysis = generateChessGPTStructuredResponse(result);
  
  // Use it to inform final LLM response
  if (llmEnabled) {
    await generateLLMResponse(
      "Analyze this chess position...",
      result,              // Raw engine data
      structuredAnalysis   // Formatted Chess GPT response
    );
  } else {
    // Show structured response if LLM disabled
    addAssistantMessage(structuredAnalysis, result);
  }
}
```

## Benefits

### For End Users:
✅ **Natural Conversation:** Responses feel human and engaging
✅ **Context-Aware:** LLM considers chat history and mode
✅ **Structured Fallback:** Chess GPT format when LLM is disabled
✅ **Transparency:** Can view underlying analysis anytime

### For Power Users:
✅ **Full Data Access:** 📊 button shows all details
✅ **Engine Output:** Raw Stockfish evaluation visible
✅ **Structured Analysis:** Chess GPT formatted response
✅ **Mode Tracking:** See what mode was inferred

### For Development:
✅ **Modular Design:** Easy to modify Chess GPT format
✅ **Flexible Pipeline:** Can adjust LLM prompts independently
✅ **Debug-Friendly:** All intermediate data preserved
✅ **Extensible:** Easy to add new analysis features

## Testing the New Pipeline

### 1. Basic Analysis:
```
User: "Analyze position"
Result: 
  - Natural conversational response ✅
  - 📊 button appears ✅
  - Click → Modal shows Chess GPT + Engine data ✅
```

### 2. Contextual Questions:
```
User: "What should I do?"
System:
  - Detects mode (DISCUSS/ANALYZE)
  - Generates Chess GPT analysis
  - LLM uses it for natural response
  - Includes chat history
Result: Context-aware answer ✅
```

### 3. Move Suggestions:
```
User: "Best move?"
Chess GPT generates:
  - Verdict: = (Equal)
  - Candidates: e4, d4, Nf3
  - Critical line with e4
LLM converts to:
  "The position is equal. I recommend e4 because..."
```

## Configuration

### Environment Variables:
```bash
# Frontend .env.local
NEXT_PUBLIC_OPENAI_API_KEY=sk-proj-...
```

### Model Selection:
```typescript
model: "gpt-4o-mini",  // Fast and cost-effective
temperature: 0.7,       // Balanced creativity
max_tokens: 500,        // Concise responses
```

## Future Enhancements

Potential improvements:
- [ ] Customize Chess GPT format per user preference
- [ ] Add explanation depth slider
- [ ] Support multiple Chess GPT formats (beginner/advanced)
- [ ] Cache structured responses for faster repeated queries
- [ ] Add "regenerate" button for different LLM interpretations

## Summary

The upgraded pipeline provides:
1. **Better UX** - Natural, engaging responses
2. **Transparency** - Full access to underlying analysis
3. **Flexibility** - Works with or without LLM
4. **Intelligence** - Context and mode-aware responses

**Status:** ✅ Fully implemented and tested
