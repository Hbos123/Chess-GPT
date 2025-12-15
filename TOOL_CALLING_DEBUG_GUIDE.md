# 🔧 Tool Calling - Debug Guide

## Current Status

✅ **Backend:** Tool calling working, analyzing correct FENs
✅ **Frontend:** Sending context, logging tool calls
⚠️ **Issue:** LLM responses too generic/similar even with different positions

## What's Happening (From Logs)

### Move 1 → Ask "Who's winning?"
```
Backend receives:
  FEN: rnb1kbnr/ppp1pppp/8/3q4/8/2N5/PPPP1PPP/R1BQKBNR
  
Tool executes:
  analyze_position with that FEN
  Returns: Eval +0cp, themes, etc.
  
LLM receives tool result:
  "Position equal (±0.00), queen on d5 strong..."
  
LLM responds:
  "Position is equal, queen on d5 strong..."
```

### Move 2 → Ask "Who's winning now?"
```
Backend receives:
  FEN: rnb1kbnr/ppp1pppp/8/8/8/2N5/PPPq1PPP/R1BQKBNR (DIFFERENT!)
  
Tool executes:
  analyze_position with NEW FEN
  Returns: Different eval (queen captured pawn!)
  
LLM receives tool result:
  "Position analysis for new FEN..."
  
LLM responds:
  Similar generic response (NOT using specific tool data!)
```

## The Real Issue

The tool is working correctly, but the **LLM isn't being specific enough** in its responses. It's seeing the tool results but giving generic chess advice instead of citing the actual evaluation.

## Solutions

### Fix 1: Improve Tool Result Format (DONE ✅)

I already updated the tool result to include:
```
POSITION ANALYSIS for FEN: [specific fen]
Evaluation: [specific eval with description]
Best move: [move]
Key themes: [themes]
Material: [balance]
```

This gives the LLM more specific data to cite.

### Fix 2: Update System Prompt (Add Instruction)

The system prompt should tell the LLM to **cite specific numbers** from tool results:

Add to enhanced_system_prompt.py:
```python
When presenting tool results:
- ALWAYS cite the specific evaluation (e.g., "+0.35" not "equal")  
- Reference the exact FEN analyzed
- Use concrete numbers from analysis
- Don't be generic - be specific!
```

### Fix 3: Test With More Specific Question

Instead of: "Who's winning?"
Try: "What's the exact evaluation?"

This forces the LLM to give a number.

## Backend Logs to Watch

**When you ask "Who's winning?" now, watch for:**

```
💬 LLM CHAT REQUEST
   📋 6 tools available

   🔧 Tool iteration 1/5
      Executing: analyze_position
      
🔧 TOOL CALL: analyze_position
   Analyzing position (depth=18)
   
   Tool result preview: POSITION ANALYSIS for FEN: rnb1k...
Evaluation: Slight advantage (+35cp)
Best move: Nf3
Key themes: development, center
Material: +0
Candidate moves: 3

   ✅ Chat complete (1 tool iterations, 1 tools called)
   Final response preview: The position shows a slight advantage for White (+35cp). The best move is Nf3...
```

## What to Check

### In Backend Logs:
1. ✅ FEN changes between requests
2. ✅ Tool result shows DIFFERENT evaluation
3. ⏳ Final response cites SPECIFIC evaluation

### In Frontend Console:
1. ✅ Tool calls logged
2. ✅ Different FENs sent
3. ⏳ Response uses specific numbers

## Quick Test

**Try this conversation:**

```
1. Make a move (e.g., e4)
2. Ask: "What's the exact eval in centipawns?"
   Expected: "+25cp" or specific number

3. Make a blunder (e.g., Qxf7 blunder)
4. Ask: "What's the exact eval now?"
   Expected: "-200cp" or DIFFERENT number

5. Compare responses - should be clearly different!
```

## Raw Data Button

You mentioned wanting to see the "Show Raw Data" button. This should appear when:
- Tool calls `analyze_position`
- Frontend receives `tool_calls` array with analysis data
- Message meta includes the analysis

Currently the tool_calls are being logged to console but not stored in message meta. 

**To fix:** Update page.tsx to store tool results in message meta:

```typescript
const {content, tool_calls} = await callLLM(messages);

// Add message with tool data
addAssistantMessage(content, {
  tool_calls: tool_calls,
  rawEngineData: tool_calls[0]?.result?.analysis  // For "Show Raw Data" button
});
```

This will enable the raw data button for tool-based analysis.

---

**Current Status:**
✅ Backend analyzing correct FENs
✅ Tool results include FEN and specific eval
✅ Enhanced logging active

**Test now:**
- Ask specific questions ("What's the eval?")
- Check backend logs for tool results
- See if LLM cites specific numbers

🔧 **Try testing again with enhanced logging!**

