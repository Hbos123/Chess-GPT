# Analyze Move Endpoint - Enhanced

## Overview
Enhanced `/analyze_move` endpoint that provides **detailed comparison** of themes, strengths, weaknesses, and threats between a played move and the best move.

## Endpoint Details

**URL:** `POST /analyze_move`

**Parameters:**
- `fen` (required): FEN string before the move
- `move_san` (required): Move in SAN notation (e.g., "Nf3", "e4")
- `depth` (optional): Analysis depth (10-20, default: 18)

## What It Does

1. **Analyzes position BEFORE the move**
   - Gets best move and top 3 candidates
   - Records evaluation

2. **Analyzes position AFTER played move**
   - Evaluates the new position
   - Gets top 3 candidate moves
   - Compares to position before

3. **Analyzes position AFTER best move** (if different from played)
   - Only runs if played move ≠ best move
   - Evaluates the alternative position
   - Compares to position before

## Response Structure

```json
{
  "fenBefore": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
  "movePlayed": "e4",
  "bestMove": "e4",
  "isPlayedMoveBest": true,
  
  "analysisBefore": {
    "eval": 20,
    "topMoves": ["e4", "d4", "Nf3"]
  },
  
  "playedMoveReport": {
    "movePlayed": "e4",
    "wasTheBestMove": true,
    "evalBefore": 20,
    "evalAfter": 25,
    "evalChange": 5,
    "evalChangeMagnitude": 5,
    "improvedPosition": true,
    "worsenedPosition": false,
    "topMovesBefore": ["e4", "d4", "Nf3"],
    "topMovesAfter": ["Nf6", "e5", "c5"],
    "bestMoveAfter": "Nf6",
    "bestEvalAfter": -25
  },
  
  "bestMoveReport": null  // Only present if played move ≠ best move
}
```

## When Best Move Report is Present

If the played move is NOT the best move:

```json
{
  "fenBefore": "...",
  "movePlayed": "a3",
  "bestMove": "e4",
  "isPlayedMoveBest": false,
  
  "playedMoveReport": {
    "movePlayed": "a3",
    "wasTheBestMove": false,
    "evalBefore": 20,
    "evalAfter": 15,
    "evalChange": -5,
    "evalChangeMagnitude": 5,
    "improvedPosition": false,
    "worsenedPosition": true,
    "topMovesBefore": ["e4", "d4", "Nf3"],
    "topMovesAfter": ["e5", "d5", "Nf6"],
    "bestMoveAfter": "e5",
    "bestEvalAfter": -15
  },
  
  "bestMoveReport": {
    "movePlayed": "e4",
    "wasTheBestMove": true,
    "evalBefore": 20,
    "evalAfter": 25,
    "evalChange": 5,
    "evalChangeMagnitude": 5,
    "improvedPosition": true,
    "worsenedPosition": false,
    "topMovesBefore": ["e4", "d4", "Nf3"],
    "topMovesAfter": ["e5", "c5", "Nf6"],
    "bestMoveAfter": "e5",
    "bestEvalAfter": -25,
    "evalDifference": 10  // How much better best move is (25 - 15)
  }
}
```

## Report Fields Explained

### Played Move Report
**Evaluation:**
- `evalBefore`: Evaluation before the move (in centipawns)
- `evalAfter`: Evaluation after the move
- `evalChange`: How much the eval changed
- `improvedPosition` / `worsenedPosition`: Boolean flags

**Themes (Key Positional Concepts):**
- `themesBefore`: Themes present before the move
- `themesAfter`: Themes present after the move
- `themesGained`: New themes that appeared (e.g., "open f-file")
- `themesLost`: Themes that disappeared
- `themesKept`: Themes that remained

**Threats:**
- `threatsCountBefore` / `threatsCountAfter`: Number of threats
- `threatsBefore` / `threatsAfter`: Detailed threat objects
- `threatsGained`: Net change in threat count

**Strengths (Active Pieces):**
- `activePiecesBefore`: Pieces with quality ≥ 0.6 before
- `activePiecesAfter`: Pieces with quality ≥ 0.6 after
- `piecesActivated`: Pieces that became active (e.g., "Bc1" → active)

**Weaknesses (Inactive Pieces):**
- `inactivePiecesBefore`: Pieces with quality ≤ 0.3 before
- `inactivePiecesAfter`: Pieces with quality ≤ 0.3 after
- `piecesDeactivated`: Pieces that became inactive

**Top Moves:**
- `topMovesBefore` / `topMovesAfter`: Top 3 candidate moves
- `bestMoveAfter`: Engine's top choice in resulting position

### Best Move Report (when different)
- All the same fields as played move report
- `evalDifference`: How much better the best move is

## What Changed - Example

```json
"playedMoveReport": {
  "movePlayed": "a3",
  "evalChange": -15,
  "worsenedPosition": true,
  
  "themesGained": [],
  "themesLost": ["center control"],
  "themesKept": ["opening development"],
  
  "threatsGained": -1,
  "threatsAfter": [],
  
  "piecesActivated": [],
  "piecesDeactivated": ["Bc1"],
  
  "activePiecesAfter": [],
  "inactivePiecesAfter": ["Ra1", "Bc1", "Bf1"]
}
```

This shows:
- ❌ Lost center control theme
- ❌ Lost a threat
- ❌ Bc1 became inactive
- ❌ Position worsened by 15cp

## Use Cases

1. **Move Comparison**: "Why was Nf3 better than d4?"
2. **Mistake Analysis**: "What did I lose by playing a3?"
3. **Learning Tool**: Compare what changed between played and best move
4. **Position Evaluation**: See how moves affect the position

## Example Usage

```bash
curl -X POST "http://localhost:8000/analyze_move?fen=rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR%20w%20KQkq%20-%200%201&move_san=a3&depth=18"
```

## Integration Notes

- Uses existing `analyze_with_depth` helper function
- Depth 18 provides strong analysis (same as game review)
- Handles both best moves and suboptimal moves
- Returns `null` for `bestMoveReport` when played move is best

