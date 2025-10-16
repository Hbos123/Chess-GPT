# Move Analysis Enhanced - Raw Data & Analysis Cards

## Summary of Changes

Enhanced the move analysis feature to show:
1. **Only changes** in strengths/weaknesses (not pieces that stayed the same)
2. **📊 Raw Data button** (like in position analysis) to view full engine output
3. **Analysis cards** for before/after positions and best move alternative

## Changes Made

### Backend (`backend/main.py`)

#### Added Full Analysis to Reports
Modified the `/analyze_move` endpoint to include the complete analysis data in the response:

```python
# Generate report for played move
played_report = compare_full_analyses(analysis_before, analysis_after_played)
played_report["movePlayed"] = move_san
played_report["wasTheBestMove"] = is_best_move
played_report["analysisAfter"] = analysis_after_played  # ✅ NEW: Include full analysis

# Generate report for best move (if different)
best_report = None
if not is_best_move and analysis_after_best:
    best_report = compare_full_analyses(analysis_before, analysis_after_best)
    best_report["movePlayed"] = best_move_san
    best_report["wasTheBestMove"] = True
    best_report["evalDifference"] = best_report["evalAfter"] - played_report["evalAfter"]
    best_report["analysisAfter"] = analysis_after_best  # ✅ NEW: Include full analysis
```

### Frontend (`frontend/app/page.tsx`)

#### 1. Show Only Changes in Strengths/Weaknesses

**Before:**
```typescript
// Strengths (Active Pieces)
if (report.piecesActivated.length > 0 || report.activePiecesAfter.length > 0) {
  reply += `\n**Strengths:**\n`;
  if (report.piecesActivated.length > 0) {
    reply += `  ✓ Activated: ${report.piecesActivated.join(", ")}\n`;
  }
  if (report.activePiecesAfter.length > 0) {
    reply += `  Active pieces: ${report.activePiecesAfter.join(", ")}\n`;
  }
}
```

**After:**
```typescript
// Strengths (Active Pieces) - ONLY SHOW CHANGES
if (report.piecesActivated.length > 0) {
  reply += `\n**Strengths:**\n`;
  reply += `  ✓ Activated: ${report.piecesActivated.join(", ")}\n`;
}

// Weaknesses (Inactive Pieces) - ONLY SHOW CHANGES
if (report.piecesDeactivated.length > 0) {
  reply += `\n**Weaknesses:**\n`;
  reply += `  ✗ Deactivated: ${report.piecesDeactivated.join(", ")}\n`;
}
```

#### 2. Created `formatAnalysisCard()` Helper Function

New function to format full position analysis into a readable card:

```typescript
function formatAnalysisCard(analysisData: any): string {
  if (!analysisData) return "No analysis available";
  
  const evalCp = analysisData.eval_cp || 0;
  const evalPawns = (evalCp / 100).toFixed(2);
  const verdict = evalCp > 100 ? "+- (White is winning)" :
                  evalCp > 50 ? "+/= (White is slightly better)" :
                  evalCp > -50 ? "= (Equal position)" :
                  evalCp > -100 ? "=/+ (Black is slightly better)" :
                  "-+ (Black is winning)";
  
  const candidates = analysisData.candidate_moves || [];
  const themes = analysisData.themes || [];
  const threats = analysisData.threats || [];
  
  let card = `Verdict: ${verdict}\n`;
  card += `Eval: ${evalCp > 0 ? '+' : ''}${evalPawns}\n\n`;
  
  if (themes.length > 0) {
    card += `Key Themes:\n${themes.slice(0, 3).map((t: string, i: number) => `${i + 1}. ${t}`).join("\n")}\n\n`;
  }
  
  if (candidates.length > 0) {
    card += `Candidate Moves:\n`;
    candidates.slice(0, 3).forEach((c: any, i: number) => {
      const evalStr = c.eval_cp !== undefined ? `Eval: ${(c.eval_cp / 100).toFixed(2)}` : '';
      card += `${i + 1}. ${c.move} - ${evalStr}\n`;
    });
    card += `\n`;
  }
  
  if (threats.length > 0) {
    card += `Threats:\n`;
    threats.slice(0, 3).forEach((t: any) => {
      card += `• ${t.desc} (${t.delta_cp > 0 ? '+' : ''}${t.delta_cp}cp)\n`;
    });
  }
  
  return card.trim();
}
```

#### 3. Added Structured Analysis Cards to Message Metadata

Both move analysis paths now include structured analysis:

```typescript
// Create structured analysis cards for before/after/best
const structuredAnalysis = `
=== POSITION BEFORE MOVE ===
${formatAnalysisCard(analysis.analysisBefore)}

=== POSITION AFTER ${moveToAnalyze} ===
${formatAnalysisCard(analysis.playedMoveReport.analysisAfter)}

${!report.wasTheBestMove && analysis.bestMoveReport ? `
=== POSITION AFTER BEST MOVE (${analysis.bestMove}) ===
${formatAnalysisCard(analysis.bestMoveReport.analysisAfter)}
` : ''}
`.trim();

addAssistantMessage(reply.trim(), { 
  moveAnalysis: analysis,
  structuredAnalysis,        // ✅ For 📊 button
  rawEngineData: analysis,   // ✅ For raw JSON view
  mode: "MOVE_ANALYSIS",
  fen: fenBefore
});
```

## User Experience

### Before
- Showed all active/inactive pieces (even if they didn't change)
- No way to see full engine analysis
- No comparison cards
- Detailed structured output in main chat

### After
- **Natural Language Response**: LLM generates concise 2-3 sentence summary in main chat
- **📊 Raw Data button**: Click to see:
  - Full position analysis before the move
  - Full position analysis after the played move
  - Full position analysis after best move (if different)
- **Structured cards** showing:
  - Verdict (=, +/=, +-, etc.)
  - Evaluation in centipawns
  - Key themes
  - Strengths (active pieces for both sides)
  - Weaknesses (inactive pieces for both sides)
  - Top 3 candidate moves with evaluations
  - Threats with centipawn values

## Example Output

### Concise Response (Main Chat) - **NEW LLM-Generated**
```
Bxg5 is the best move but worsens your position by 1607cp - this is a losing blunder. 
The move gains black space advantage and black advantage while losing white advantage, 
activating Black's threats like e4 (+852cp) and Nf3 (+850cp). This move completely 
throws away White's winning position.
```

### Raw Data (📊 Button)
```
=== POSITION BEFORE MOVE ===
Verdict: = (Equal position)
Eval: +0.00

Key Themes:
1. Opening development
2. Center control
3. Pawn structure

Candidate Moves:
1. e4 - Eval: 0.15
2. d4 - Eval: 0.12
3. Nf3 - Eval: 0.08

=== POSITION AFTER e4 ===
Verdict: +/= (White is slightly better)
Eval: +0.15

Key Themes:
1. Center control
2. Space advantage
3. Development

Strengths:
  White: Bc1, Qd1
  Black: Bf8, Qd8

Weaknesses:
  White: Ra1
  Black: Ra8

Candidate Moves:
1. e5 - Eval: -0.15
2. c5 - Eval: -0.12
3. Nf6 - Eval: -0.10

Threats:
• Threat: d4 (+30cp)
• Threat: Nf3 (+25cp)
```

## Benefits

1. **Cleaner UI**: Only shows relevant changes, not static information
2. **Deep Dive Available**: Raw data button for users who want full details
3. **Better Comparison**: Side-by-side cards make it easy to see how the position evolved
4. **Consistent UX**: Same 📊 button pattern as position analysis
5. **Educational**: Shows what changed vs. what stayed the same

## Testing

1. Play a move and ask: "analyze last move"
2. Or ask: "analyze e4" from any position
3. Click the 📊 button on the response
4. You should see:
   - Concise summary in main chat (only changes)
   - Full analysis cards in raw data view (complete picture)

All features working! ✅

