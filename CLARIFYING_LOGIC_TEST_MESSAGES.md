# Clarifying Logic Test Messages

## Test Scenarios for Intent Detection & Clarification System

---

## Category 1: Clear High-Confidence Intents ✅

### Test 1.1: Explicit End Game
**Message:** `"end this game"`  
**Expected:** Confirmation prompt → "Are you sure you want to end the current game? Type 'yes' to confirm or 'no' to cancel."  
**Context:** Game active

### Test 1.2: Resignation
**Message:** `"I resign"`  
**Expected:** Immediate resignation → "You resigned. Game ended."  
**Context:** Game active

### Test 1.3: Start Game
**Message:** `"let's play a game"`  
**Expected:** Game starts → "AI Game Mode Activated! Make your moves on the board."  
**Context:** No game active

### Test 1.4: Reset Board
**Message:** `"reset board"`  
**Expected:** Confirmation prompt → "Are you sure you want to reset the board? Type 'yes' to confirm or 'no' to cancel."  
**Context:** Any

### Test 1.5: End Walkthrough
**Message:** `"end walkthrough"`  
**Expected:** Walkthrough ends → "Walkthrough ended. Feel free to ask any questions!"  
**Context:** Walkthrough active

---

## Category 2: Ambiguous Intents (Should Ask Clarification) ❓

### Test 2.1: Just "end"
**Message:** `"end"`  
**Context:** Game active + Walkthrough active  
**Expected:** Clarifying question:
```
"I'm not sure what you'd like to do. Did you want to:
1. End the current game
2. End the walkthrough
3. Analyze the current position

Please respond with the number or describe what you'd like."
```

### Test 2.2: "stop"
**Message:** `"stop"`  
**Context:** Game active + Walkthrough active  
**Expected:** Clarifying question (similar to Test 2.1)

### Test 2.3: "end this"
**Message:** `"end this"`  
**Context:** Game active + Walkthrough active  
**Expected:** Clarifying question

### Test 2.4: "quit"
**Message:** `"quit"`  
**Context:** Game active  
**Expected:** Could be end game or general quit → Clarifying question

---

## Category 3: Low Confidence / Fallback Cases 🔄

### Test 3.1: Unclear Command
**Message:** `"end something"`  
**Context:** No active features  
**Expected:** "I'm not sure what you'd like to do. Could you be more specific? For example: 'end game', 'start new game', 'reset board'."

### Test 3.2: Vague Command
**Message:** `"do something"`  
**Context:** Any  
**Expected:** Normal LLM flow (not a command, so no fallback message)

### Test 3.3: Partial Match
**Message:** `"ending"`  
**Context:** Game active  
**Expected:** Normal LLM flow (not command-like enough)

---

## Category 4: Confirmation Flows ✅

### Test 4.1: End Game - Yes
**Message 1:** `"end game"`  
**Expected:** "Are you sure you want to end the current game? Type 'yes' to confirm or 'no' to cancel."  
**Message 2:** `"yes"`  
**Expected:** "Game ended." + Game deactivated

### Test 4.2: End Game - No
**Message 1:** `"end game"`  
**Expected:** Confirmation prompt  
**Message 2:** `"no"`  
**Expected:** "Game continues." + Game still active

### Test 4.3: Reset Board - Yes
**Message 1:** `"reset board"`  
**Expected:** Confirmation prompt  
**Message 2:** `"y"`  
**Expected:** "Board reset to starting position" + Board reset

### Test 4.4: Reset Board - No
**Message 1:** `"reset board"`  
**Expected:** Confirmation prompt  
**Message 2:** `"n"`  
**Expected:** "Reset cancelled." + Board unchanged

---

## Category 5: Clarifying Question Responses 📝

### Test 5.1: Number Response
**Message 1:** `"end"`  
**Context:** Game + Walkthrough active  
**Expected:** Clarifying question with 3 options  
**Message 2:** `"1"`  
**Expected:** Confirmation prompt for ending game

### Test 5.2: Description Response
**Message 1:** `"end"`  
**Context:** Game + Walkthrough active  
**Expected:** Clarifying question  
**Message 2:** `"end the game"`  
**Expected:** Confirmation prompt for ending game

### Test 5.3: Keyword Response
**Message 1:** `"end"`  
**Context:** Game + Walkthrough active  
**Expected:** Clarifying question  
**Message 2:** `"game"`  
**Expected:** Confirmation prompt for ending game

---

## Category 6: Context-Aware Priority Tests 🎯

### Test 6.1: "end" with Only Game Active
**Message:** `"end"`  
**Context:** Game active, no walkthrough  
**Expected:** Direct to end game confirmation (not ambiguous)

### Test 6.2: "end" with Only Walkthrough Active
**Message:** `"end"`  
**Context:** Walkthrough active, no game  
**Expected:** Direct to end walkthrough (not ambiguous)

### Test 6.3: "end" with Nothing Active
**Message:** `"end"`  
**Context:** No active features  
**Expected:** Low confidence → Fallback message or normal flow

---

## Category 7: Edge Cases & Special Scenarios 🔍

### Test 7.1: Multiple Commands in One Message
**Message:** `"end game and reset board"`  
**Expected:** Should detect both, ask clarification or prioritize one

### Test 7.2: Typo in Command
**Message:** `"edn game"`  
**Expected:** Lower confidence, might fallback or normal flow

### Test 7.3: Command with Extra Words
**Message:** `"please end this game now"`  
**Expected:** Should still detect "end game" intent

### Test 7.4: Negative Command
**Message:** `"don't end the game"`  
**Expected:** Should NOT trigger end game intent

### Test 7.5: Question About Ending
**Message:** `"how do I end the game?"`  
**Expected:** Normal LLM response (not a command)

---

## Category 8: Non-Critical Intent Tests 🎮

### Test 8.1: Start Game - High Confidence
**Message:** `"play a game"`  
**Context:** No game active  
**Expected:** Game starts immediately (confidence >= 0.7)

### Test 8.2: Tactics - High Confidence
**Message:** `"give me a puzzle"`  
**Expected:** Tactics mode activated (confidence >= 0.7)

### Test 8.3: Analyze Position - Medium Confidence
**Message:** `"what should I do"`  
**Context:** Position on board  
**Expected:** Might ask clarification if confidence 0.4-0.6, or proceed if >= 0.7

### Test 8.4: Switch to Analyze Mode
**Message:** `"switch to analyze mode"`  
**Expected:** Mode switches to ANALYZE → "Switched to Analyze mode."

### Test 8.5: Switch to Discuss Mode
**Message:** `"go to discuss mode"`  
**Expected:** Mode switches to DISCUSS → "Switched to Discuss mode."

### Test 8.6: Switch to Tactics Mode
**Message:** `"enter tactics mode"`  
**Expected:** Mode switches to TACTICS → "Switched to Tactics mode."

### Test 8.7: Help Request
**Message:** `"help"` or `"what can you do"`  
**Expected:** Normal LLM flow handles help (intent detected but not executed, falls through)

### Test 8.8: Describe Position
**Message:** `"describe this position"`  
**Context:** Position on board  
**Expected:** Normal LLM flow handles description

### Test 8.9: Review Game
**Message:** `"review this game"`  
**Context:** Game with moves  
**Expected:** Normal LLM flow handles review

### Test 8.10: Show Candidates
**Message:** `"what are my candidate moves"`  
**Expected:** Normal LLM flow handles candidates request

### Test 8.11: Show Evaluation
**Message:** `"what's the evaluation"`  
**Expected:** Normal LLM flow handles evaluation request

---

## Category 9: Integration Tests 🔗

### Test 9.1: End Game During Play
**Message:** `"end this game"`  
**Context:** Mid-game, 5 moves played  
**Expected:** Confirmation → End game → Mode switches to DISCUSS

### Test 9.2: Reset During Analysis
**Message:** `"reset board"`  
**Context:** Analyzing position, no game active  
**Expected:** Confirmation → Reset → Position cleared

### Test 9.3: Multiple Quick Commands
**Message 1:** `"end game"`  
**Message 2:** `"yes"`  
**Message 3:** `"play a game"`  
**Expected:** Game ends → New game starts

---

## Category 10: Response Format Tests 📋

### Test 10.1: Yes Variations
**Messages:** `"yes"`, `"y"`, `"YES"`, `"Y"`  
**Expected:** All should work for confirmations

### Test 10.2: No Variations
**Messages:** `"no"`, `"n"`, `"NO"`, `"N"`  
**Expected:** All should work for cancellations

### Test 10.3: Number Variations
**Messages:** `"1"`, `" 1 "`, `"one"`  
**Expected:** "1" should work, "one" might not (could add support)

---

## Quick Test Checklist ✅

Run these in order to verify the system:

1. ✅ `"end this game"` → Confirmation
2. ✅ `"yes"` → Game ends
3. ✅ `"end"` (game + walkthrough active) → Clarifying question
4. ✅ `"1"` → Confirmation prompt
5. ✅ `"no"` → Cancelled
6. ✅ `"resign"` → Immediate resignation
7. ✅ `"reset board"` → Confirmation
8. ✅ `"y"` → Board reset
9. ✅ `"end"` (only game active) → Direct confirmation
10. ✅ `"do something unclear"` → Normal flow

---

## Expected Behavior Summary

### High Confidence (>= 0.6)
- Execute immediately (with confirmation if critical)

### Medium Confidence (0.4 - 0.6)
- Check for ambiguity
- Ask clarification if ambiguous
- Execute if not ambiguous

### Low Confidence (< 0.4)
- Fallback message for command-like input
- Normal flow for non-commands

### Ambiguous (gap < 0.2)
- Always ask clarifying question
- Show top 3 options
- Wait for user response

---

## Test Execution Order

1. **Setup:** Start a game or walkthrough
2. **Test clear intents:** Verify high-confidence detection
3. **Test ambiguous:** Create ambiguous context, verify questions
4. **Test confirmations:** Verify yes/no flow
5. **Test clarifying responses:** Verify number/description matching
6. **Test fallbacks:** Verify low-confidence handling
7. **Test edge cases:** Verify special scenarios

---

## Notes

- All tests assume LLM is enabled
- Some tests require specific context (game active, walkthrough active)
- Responses should be consistent and helpful
- System should never crash on ambiguous input
- All user messages should be added to chat history

