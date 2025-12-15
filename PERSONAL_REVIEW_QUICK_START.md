# 🚀 Personal Review System - Quick Start Guide

## Prerequisites

1. **Backend running** with Stockfish initialized
2. **Frontend running** on localhost:3000
3. **OpenAI API key** configured in `.env`

## Testing the System

### Step 1: Start the Application

**Terminal 1 - Backend:**
```bash
cd backend
python main.py
```

Wait for:
```
✓ Stockfish engine initialized
✅ Personal Review system initialized
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev
```

### Step 2: Access Personal Review

1. Open browser to `http://localhost:3000`
2. Click the **"🎯 Personal Review"** button in the top-right header
3. Modal should open with username input

### Step 3: Fetch Games

**Test with real usernames:**

**For Chess.com:**
- Username: `hikaru` (GM Hikaru Nakamura)
- Username: `magnuscarlsen` (Magnus Carlsen)
- Username: `penguingm1` (GothamChess)

**For Lichess:**
- Username: `DrNykterstein` (Magnus Carlsen)
- Username: `penguingim1` (Penguin)
- Username: Any public Lichess username

**Steps:**
1. Enter username (e.g., `hikaru`)
2. Select platform (e.g., **Chess.com**)
3. Click **"Fetch Games"**
4. Wait for games to load (5-30 seconds)
5. Should see: "✓ 100 games loaded"

### Step 4: Ask a Question

**Example queries to test:**

1. **"Why am I stuck at my current rating?"**
   - Tests: Diagnostic intent, overall analysis

2. **"Which openings do I lose the most with?"**
   - Tests: Opening performance analysis

3. **"Am I better in the opening or endgame?"**
   - Tests: Phase comparison

4. **"Do I make more mistakes when I'm winning?"**
   - Tests: Advanced pattern detection

5. **"How has my play changed over the last 6 months?"**
   - Tests: Cohort comparison

**Steps:**
1. Type query in the text area
2. Click **"Analyze"**
3. Watch progress messages:
   - "Understanding your question..."
   - "Analyzing 50 games..." (this takes 15-20 minutes!)
   - "Generating insights..."

### Step 5: View Results

After analysis completes, you should see:

**1. Narrative Report**
- Overview section answering the question
- Quantitative insights with numbers
- Qualitative analysis
- Action plan with recommendations

**2. Visual Charts**
- Accuracy by Rating (bar chart)
- Opening Performance (table)
- Most Common Themes (bar chart)
- Performance by Phase (cards)

**3. Key Statistics**
- Total Games
- Overall Accuracy
- Win Rate
- Avg CP Loss
- Blunder Rate

## Expected Behavior

### ✅ Success Indicators

**Console (Backend):**
```
🎯 Fetching games for hikaru from chess.com
✅ Fetched 100 games
✓ Cached 100 games for hikaru (chess.com)
🤔 Planning analysis for query: Which openings do I lose with?
✅ Generated plan with intent: focus
📊 Starting aggregation for 100 games
  Analyzing game 1/50...
  Analyzing game 2/50...
  ...
✅ Analyzed 50 games
✅ Aggregation complete
📝 Generating report...
✅ Report generated
```

**Browser:**
- Modal opens smoothly
- Games load within 30 seconds
- Progress spinner shows during analysis
- Report renders with formatting
- Charts display correctly
- No console errors

### ⚠️ Common Issues

**1. "Failed to fetch games"**
- Check username spelling
- Try different platform
- Check API rate limits
- Verify internet connection

**2. "Analysis failed"**
- Check Stockfish is running
- Check OpenAI API key
- Reduce number of games to analyze
- Check backend logs for details

**3. "Report generation failed"**
- Check OpenAI API key
- Check API quota
- Will show fallback report

**4. Modal won't open**
- Check frontend console for errors
- Verify PersonalReview component imported
- Check CSS loaded

## Performance Notes

### Analysis Time Estimates

| Games | Time (depth 18) | Time (depth 15) |
|-------|-----------------|-----------------|
| 10    | 3-5 min         | 2-3 min         |
| 25    | 8-12 min        | 5-8 min         |
| 50    | 15-25 min       | 10-15 min       |
| 100   | 30-50 min       | 20-30 min       |

**Tips for faster testing:**
1. Start with 10-25 games
2. Reduce Stockfish depth in `main.py` (line ~1024: change `depth=18` to `depth=15`)
3. Use cached games (don't re-fetch)
4. Test with same username multiple times (uses cache)

## Test Cases

### Minimal Test (Quick)
```
1. Username: hikaru
2. Platform: chess.com
3. Fetch: Click (should cache)
4. Query: "What are my strengths?"
5. Wait: ~15 minutes
6. Verify: Report shows, charts display
```

### Full Feature Test
```
1. Test Chess.com fetch
2. Test Lichess fetch
3. Test Combined fetch
4. Test cache loading (re-fetch same user)
5. Test different query types:
   - Diagnostic: "Why am I stuck?"
   - Focus: "Which openings?"
   - Comparison: "How have I improved?"
6. Verify all charts render
7. Verify action plan generated
8. Test "New Query" button
9. Test modal close
10. Test error cases (invalid username)
```

## Debugging

### Backend Logs

**Check for:**
```bash
tail -f backend_logs.txt  # If logging to file
```

Or watch terminal output for:
- API errors
- Stockfish crashes
- OpenAI errors
- Analysis progress

### Frontend Console

**Check for:**
- Network errors (fetch failures)
- CORS issues
- Component errors
- State update issues

### Common Fixes

**Stockfish not responding:**
```bash
pkill -9 stockfish  # Kill stale processes
python main.py     # Restart backend
```

**Cache issues:**
```bash
rm -rf backend/cache/player_games/*
# Re-fetch games
```

**Frontend state stuck:**
- Refresh page (F5)
- Clear browser cache
- Restart frontend dev server

## API Testing (Optional)

Test endpoints directly with curl:

```bash
# 1. Fetch games
curl -X POST http://localhost:8000/fetch_player_games \
  -H "Content-Type: application/json" \
  -d '{"username":"hikaru","platform":"chess.com","max_games":10}'

# 2. Plan review (save games from step 1)
curl -X POST http://localhost:8000/plan_personal_review \
  -H "Content-Type: application/json" \
  -d '{"query":"Why am I stuck?","games":[...]}'

# 3. Check backend status
curl http://localhost:8000/
```

## Success Criteria

✅ **System is working if:**
1. Games fetch successfully from both platforms
2. Cache loads on second fetch (instant)
3. LLM planner generates valid JSON plan
4. Game analysis completes without crashes
5. Statistics aggregate correctly
6. LLM reporter generates readable text
7. All charts render with data
8. Action plan appears with recommendations
9. No errors in console
10. Modal interactions smooth

## Next Steps

Once basic functionality confirmed:
1. Test with your own account
2. Try different query variations
3. Experiment with filter parameters
4. Test error recovery
5. Check performance with larger datasets
6. Customize styling if needed
7. Add custom metrics (extend aggregator)

## Need Help?

**Check these files:**
- `PERSONAL_REVIEW_SYSTEM_COMPLETE.md` - Full documentation
- Backend logs - Error details
- Browser console - Frontend errors
- `backend/cache/player_games/` - Cached games

**Common questions:**
- **Q: How do I speed up analysis?**
  - A: Reduce depth to 15, analyze fewer games (10-25)

- **Q: Can I analyze my own games?**
  - A: Yes! Enter your username and platform

- **Q: Does it work offline?**
  - A: No, requires API access (Chess.com/Lichess/OpenAI)

- **Q: Can I export results?**
  - A: Not yet, but data is logged to console

---

Happy testing! 🎯♟️

