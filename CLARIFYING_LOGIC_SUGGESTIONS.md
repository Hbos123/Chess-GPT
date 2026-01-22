# Clarifying Logic Suggestions for Ambiguous User Input

## Problem
When the system isn't sure what the user wants, it currently gives a generic description. We need better handling for ambiguous cases.

---

## Suggested Approaches

### 1. **Confidence Scoring System** ⭐ (Recommended)

**How it works:**
- Each intent detection (play mode, analyze, tactics, etc.) gets a confidence score (0-1)
- If multiple intents have similar scores (within 0.2), ask for clarification
- If one intent is clearly highest (>0.7), proceed with it

**Example:**
```typescript
const intentScores = {
  play: 0.65,      // "end this game" could be play-related
  analyze: 0.30,   // Low confidence
  endGame: 0.60    // Also possible
};

// Gap between top 2 is only 0.05 - too close!
if (topScore - secondScore < 0.2) {
  askClarification(intentScores);
}
```

**Implementation:**
- Add confidence scores to all intent detection functions
- Track top 2 scores
- If gap < threshold, ask clarifying question

---

### 2. **Clarifying Questions** ⭐⭐ (Highly Recommended)

**When to ask:**
- Multiple intents detected with similar confidence
- Ambiguous phrases detected ("end", "stop", "analyze this")
- Context doesn't clearly indicate intent

**Question format:**
```
System: "I'm not sure what you'd like to do. Did you want to:
1. End the current game?
2. Analyze the position?
3. Something else?"
```

**Smart questions based on context:**
- If in play mode + ambiguous: "Did you want to end the game or analyze the position?"
- If analyzing + ambiguous: "Did you want to continue analysis or start a new game?"
- If no clear context: "What would you like to do?"

**Implementation:**
```typescript
function askClarification(possibleIntents: string[], context: any) {
  const questions = generateContextualQuestions(possibleIntents, context);
  addSystemMessage(questions);
  // Wait for user response, then route based on answer
}
```

---

### 3. **"Did You Mean..." Suggestions** ⭐

**How it works:**
- When intent is unclear, suggest the most likely interpretations
- User can click or type the number/option

**Example:**
```
User: "end this"
System: "Did you mean:
  1. End this game? (resign/stop playing)
  2. End this analysis? (finish current analysis)
  3. End this walkthrough? (if walkthrough active)"
```

**Implementation:**
- Generate suggestions based on:
  - Current mode (PLAY, ANALYZE, etc.)
  - Active features (walkthrough, game, etc.)
  - Message keywords
- Present as clickable buttons or numbered options

---

### 4. **Context-Aware Disambiguation** ⭐⭐

**How it works:**
- Use current state to narrow down possibilities
- If in play mode + "end" → prioritize "end game"
- If analyzing + "end" → prioritize "end analysis"
- If walkthrough active + "end" → prioritize "end walkthrough"

**Priority order:**
1. **Active features** (game active > walkthrough > analysis)
2. **Current mode** (PLAY > ANALYZE > DISCUSS)
3. **Recent actions** (last 3 messages)
4. **Keyword strength** (exact match > partial match)

**Example:**
```typescript
function disambiguate(message: string, context: Context) {
  const intents = detectIntents(message);
  
  // Boost confidence for intents matching active features
  if (context.aiGameActive && intents.includes('endGame')) {
    intents['endGame'].confidence += 0.3;
  }
  
  if (context.walkthroughActive && intents.includes('endWalkthrough')) {
    intents['endWalkthrough'].confidence += 0.3;
  }
  
  return selectBestIntent(intents);
}
```

---

### 5. **Fallback Handling with Learning** ⭐

**How it works:**
- When uncertain, make best guess but acknowledge uncertainty
- Learn from user corrections
- Improve over time

**Example:**
```
User: "end this"
System: "I think you want to end the game. Ending now... (If not, just say 'no' and tell me what you meant)"
```

**Learning mechanism:**
- Track corrections: "no, I meant X"
- Store patterns: "end this" + context → actual intent
- Use for future disambiguation

---

### 6. **Multi-Step Confirmation** (For Critical Actions)

**For important actions that can't be undone:**
- Resignation
- Ending game
- Resetting board
- Deleting data

**Example:**
```
User: "end game"
System: "Are you sure you want to end the current game? Type 'yes' to confirm or 'no' to cancel."
```

---

## Recommended Implementation Plan

### Phase 1: Quick Fix (Now)
1. ✅ Fix "end this game" detection (DONE)
2. Add clarifying questions for ambiguous end/resign commands
3. Add context-aware priority for active features

### Phase 2: Confidence System (Next)
1. Add confidence scores to all intent detection
2. Implement gap threshold (0.2)
3. Generate clarifying questions when gap is too small

### Phase 3: Smart Suggestions (Later)
1. "Did you mean..." suggestions with buttons
2. Context-aware disambiguation
3. Learning from corrections

---

## Code Structure Suggestion

```typescript
interface IntentDetection {
  intent: string;
  confidence: number;
  keywords: string[];
  contextRequirements?: string[];
}

function detectIntentWithConfidence(
  message: string, 
  context: Context
): IntentDetection[] {
  // Return all possible intents with confidence scores
}

function handleAmbiguousIntent(
  intents: IntentDetection[],
  context: Context
): void {
  const sorted = intents.sort((a, b) => b.confidence - a.confidence);
  const gap = sorted[0].confidence - sorted[1].confidence;
  
  if (gap < 0.2) {
    // Ask clarifying question
    askClarification(sorted.slice(0, 3), context);
  } else {
    // Proceed with highest confidence
    executeIntent(sorted[0].intent, context);
  }
}
```

---

## Example Scenarios

### Scenario 1: "end this"
- **Context:** Game active, no walkthrough
- **Detected:** endGame (0.7), endAnalysis (0.3)
- **Action:** Proceed with endGame (gap > 0.2)

### Scenario 2: "end"
- **Context:** Game active + walkthrough active
- **Detected:** endGame (0.5), endWalkthrough (0.5)
- **Action:** Ask "End the game or end the walkthrough?"

### Scenario 3: "analyze this"
- **Context:** In play mode, position on board
- **Detected:** analyzePosition (0.8), analyzeMove (0.4)
- **Action:** Proceed with analyzePosition (gap > 0.2)

---

## Benefits

1. **Better UX:** Users get help when system is uncertain
2. **Fewer errors:** Reduces wrong actions from ambiguous input
3. **Learning:** System improves over time
4. **Transparency:** Users know when system is uncertain
5. **Flexibility:** Handles edge cases gracefully

---

## Next Steps

1. **Decide on approach:** Which combination of the above?
2. **Prioritize:** Quick fixes first, then confidence system
3. **Implement:** Start with Phase 1, iterate based on feedback
4. **Test:** Try ambiguous inputs, measure success rate
5. **Refine:** Adjust thresholds and questions based on results

