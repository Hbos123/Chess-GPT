# Raw Analysis System - Complete Documentation

## Overview

The Raw Analysis System is a comprehensive chess position analysis pipeline that combines Stockfish engine evaluation with theme-based positional analysis and tag detection. It provides deep insights into chess positions by analyzing multiple dimensions: material balance, positional factors, tactical themes, and strategic patterns.

## Table of Contents

1. [System Architecture](#system-architecture)
2. [Input Specifications](#input-specifications)
3. [Processing Pipeline](#processing-pipeline)
4. [Output Structure](#output-structure)
5. [Components Breakdown](#components-breakdown)
6. [Usage Examples](#usage-examples)
7. [Performance Characteristics](#performance-characteristics)

---

## System Architecture

The raw analysis system operates in two main contexts:

1. **Single Position Analysis** (`/analyze_position` endpoint)
   - Analyzes one position with full depth
   - Returns chunked analysis (immediate + delta)
   - Includes piece profiling (optional)

2. **Game Analysis** (`EnginePool.analyze_game_parallel`)
   - Analyzes all positions in a game in parallel
   - Optimizes by analyzing unique positions only
   - Returns raw analysis for each move (`raw_before` and `raw_after`)

---

## Input Specifications

### Endpoint: `GET /analyze_position`

**Query Parameters:**
- `fen` (required): FEN string of the position to analyze
  - Example: `rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1`
- `lines` (optional, default=3): Number of candidate moves to analyze (1-5)
- `depth` (optional, default=18): Engine search depth (10-22)
- `light_mode` (optional, default=false): Skip piece profiling for faster analysis

**Example Request:**
```
GET /analyze_position?fen=rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR%20b%20KQkq%20e3%200%201&depth=18&lines=3&light_mode=false
```

### Game Analysis Input

**Function:** `EnginePool.analyze_game_parallel()`

**Parameters:**
- `positions`: List of `(fen_before, move)` tuples for each move in the game
- `depth`: Engine analysis depth (default: 14)
- `multipv`: Number of principal variations (default: 2)
- `timestamps`: Optional dict mapping ply → clock time (for time spent calculation)
- `progress_callback`: Optional async callback for progress updates

**Example:**
```python
positions = [
    ("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", chess.Move.from_uci("e2e4")),
    ("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1", chess.Move.from_uci("e7e5")),
    # ... more moves
]
results = await engine_pool.analyze_game_parallel(positions, depth=14)
```

---

## Processing Pipeline

### Single Position Analysis Pipeline

#### Step 1: Extract Candidate Moves
- **Process:** Single Stockfish call with `multipv=lines`
- **Output:** List of candidate moves with evaluations and principal variations
- **Duration:** ~100-500ms depending on depth

#### Step 2: Calculate Material Balance
- **Process:** Count material using standard piece values
- **Output:** Material balance in centipawns
- **Duration:** <1ms

#### Step 3: Build PV Final Position
- **Process:** Play out principal variation moves on board
- **Output:** FEN string of final position after PV
- **Duration:** <1ms

#### Step 4: Parallel Theme/Tag Analysis
- **Process:** 
  - Start theme/tag calculation for starting position (ProcessPoolExecutor)
  - Start theme/tag calculation for final position (ProcessPoolExecutor)
  - While themes calculate, run Stockfish analysis of final position
- **Components:**
  - 11 non-engine themes (center_space, pawn_structure, king_safety, etc.)
  - 100+ tag detectors (king safety, pawn structure, center control, etc.)
  - Material balance calculation
- **Duration:** ~50-200ms per position (parallel execution)

#### Step 5: Stockfish Analysis of Final Position
- **Process:** Engine analysis of PV final position
- **Output:** Evaluation, material balance, positional CP
- **Duration:** ~100-500ms

#### Step 6: Compute Delta and Classify Plans
- **Process:** 
  - Calculate differences between start and final positions
  - Classify plan types (balanced, material_gain, positional_improvement, etc.)
  - Compute theme deltas
- **Output:** Delta analysis with plan classification
- **Duration:** <10ms

#### Step 7: Build Piece Profiles (Optional, skipped in light_mode)
- **Process:**
  - Extract NNUE evaluation for each piece
  - Combine with tags and themes
  - Compute square control
  - Track piece trajectories across PV
  - Detect captures in PV
- **Output:** Piece profiles, trajectories, square control maps
- **Duration:** ~200-500ms

### Game Analysis Pipeline

#### Phase 1: Collect Unique Positions
- **Process:** Identify unique FENs (fen_after of move N == fen_before of move N+1)
- **Optimization:** Reduces analysis by ~50% for typical games
- **Output:** Set of unique FENs to analyze

#### Phase 2: Batch Theory Checks (First 30 moves)
- **Process:** Parallel checks against Lichess Masters database
- **Output:** Theory cache mapping FEN → theory information
- **Duration:** ~10-50ms per position (parallel)

#### Phase 3: Analyze Unique Positions (Parallel)
- **Process:** For each unique FEN:
  - **Parallel execution:**
    - Theme/tag calculation (ProcessPoolExecutor)
    - Engine analysis (multipv=2) (EnginePool)
  - Cache results
- **Workers:** Multiple engine pool workers + process pool workers
- **Output:** Cached analysis for each unique FEN

#### Phase 4: Build Ply Records
- **Process:** For each move:
  - Look up `fen_before` and `fen_after` from cache
  - Extract engine evaluations
  - Calculate CP loss and accuracy
  - Check theory status
  - Build complete ply record with `raw_before` and `raw_after`
- **Output:** List of complete ply records

---

## Output Structure

### Single Position Analysis Response

```json
{
  "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
  "eval_cp": -26,
  "pv": ["e5", "Nf3", "Nf6", "Nc3", "Nc6", "Bb5"],
  "best_move": "e5",
  "phase": "opening",
  "light_mode": false,
  
  "candidate_moves": [
    {
      "move": "e5",
      "eval_cp": -26,
      "pv": ["e5", "Nf3", "Nf6"],
      "depth": 18
    },
    // ... more candidates
  ],
  
  "threats": {
    "white": [...],
    "black": [...]
  },
  
  "white_analysis": {
    "chunk_1_immediate": {
      "description": "What the position IS right now for White",
      "material_balance_cp": 0,
      "positional_cp_significance": 26,
      "theme_scores": {
        "S_CENTER_SPACE": 9.0,
        "S_PAWN": -1.0,
        "S_ACTIVITY": 0.95,
        "total": 8.95
      },
      "tags": [
        {
          "tag_name": "tag.center.control.core",
          "side": "white",
          "squares": ["e4", "d4"],
          "strength": 0.8
        },
        // ... more tags
      ]
    },
    "chunk_2_plan_delta": {
      "description": "How it SHOULD unfold for White (after PV)",
      "plan_type": "leveraging_advantage",
      "plan_explanation": "Improve position (+52cp) through center_space, piece_activity",
      "material_delta_cp": 0,
      "positional_delta_cp": 52,
      "theme_changes": {
        "center_space": 2.5,
        "piece_activity": 1.2
      }
    }
  },
  
  "black_analysis": {
    "chunk_1_immediate": {...},
    "chunk_2_plan_delta": {...}
  },
  
  "piece_profiles_start": {
    "Pe4": {
      "piece": "Pe4",
      "nnue_contribution": 12.5,
      "tags": ["tag.center.control.core"],
      "square": "e4",
      "role": "center_pawn"
    },
    // ... more pieces
  },
  
  "piece_profiles_final": {...},
  "piece_trajectories": {...},
  "captures_in_pv": [...],
  "square_control_start": {...},
  "square_control_final": {...},
  "profile_summary": {...},
  "pv_fen_profiles": [...],
  
  "position_confidence": {
    "confidence": 85,
    "factors": {...}
  }
}
```

### Raw Analysis Data Structure (raw_before/raw_after)

The `raw_before` and `raw_after` fields in game reviews contain the complete analysis result:

```json
{
  "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
  
  "themes": {
    "center_space": {
      "white": {
        "center_control": 0.6,
        "space_advantage": 0.4,
        "total": 1.0
      },
      "black": {
        "center_control": 0.3,
        "space_advantage": 0.2,
        "total": 0.5
      }
    },
    "pawn_structure": {...},
    "king_safety": {...},
    "piece_activity": {...},
    "color_complex": {...},
    "lanes": {...},
    "local_imbalances": {...},
    "development": {...},
    "promotion": {...},
    "breaks": {...},
    "prophylaxis": {...}
  },
  
  "tags": [
    {
      "tag_name": "tag.center.control.core",
      "side": "white",
      "squares": ["e4", "d4"],
      "pieces": [],
      "strength": 0.8,
      "description": "Control of central squares"
    },
    {
      "tag_name": "tag.rook.connected",
      "side": "white",
      "pieces": ["Ra1", "Rh1"],
      "strength": 0.6
    },
    // ... 100+ more tags
  ],
  
  "material_balance_cp": 0,
  
  "theme_scores": {
    "white": {
      "S_CENTER_SPACE": 9.0,
      "S_PAWN": -1.0,
      "S_KING": 0.0,
      "S_ACTIVITY": 0.95,
      "S_COMPLEX": 0,
      "S_LANES": 0,
      "S_LOCAL": 0,
      "S_TACTICS": 0,
      "S_DEV": 0,
      "S_PROMO": 0,
      "S_BREAKS": 0,
      "S_THREATS": 0,
      "S_PROPH": 0,
      "S_TRADES": 0,
      "total": 8.95
    },
    "black": {
      "S_CENTER_SPACE": 4.5,
      // ... similar structure
      "total": 4.25
    }
  },
  
  "engine_info": [
    {
      "eval_cp": -26,
      "mate_in": null,
      "pv": ["e5", "Nf3", "Nf6"],
      "depth": 18
    },
    {
      "eval_cp": -28,
      "mate_in": null,
      "pv": ["d5", "e4", "d4"],
      "depth": 18
    }
  ],
  
  "eval_cp": -26,
  "best_move_uci": "e7e5"
}
```

### Game Analysis Ply Record

Each ply record in game analysis includes:

```json
{
  "success": true,
  "ply": 1,
  "side_moved": "white",
  "san": "e4",
  "uci": "e2e4",
  "fen_before": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
  "fen_after": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
  
  "engine": {
    "eval_before_cp": 26,
    "eval_before_str": "26",
    "best_move_uci": "e2e4",
    "best_move_san": "e4",
    "played_eval_after_cp": -26,
    "played_eval_after_str": "-26",
    "mate_in": null,
    "second_best_gap_cp": 15
  },
  
  "cp_loss": 0,
  "accuracy_pct": 100.0,
  "category": "excellent",
  "threat_category": "development",
  "threat_description": "Develops central pawn",
  "time_spent_s": 2.3,
  
  "raw_before": {
    // Full raw analysis structure (see above)
    "themes": {...},
    "tags": [...],
    "material_balance_cp": 0,
    "theme_scores": {...},
    "engine_info": [...],
    "eval_cp": 26,
    "best_move_uci": "e2e4"
  },
  
  "raw_after": {
    // Full raw analysis structure for position after move
    // Same structure as raw_before
  },
  
  "analyse": {
    // Alias for raw_after (for backward compatibility)
  },
  
  "best_move_tags": [
    // Tags that would be created by best move (if different from played)
  ],
  
  "is_theory": true,
  "theory_check": {
    "isTheory": true,
    "theoryMoves": ["e2e4", "e7e5", "g1f3"],
    "opening": "King's Pawn Game",
    "eco": "C20",
    "totalGames": 125000
  },
  "opening_name": "King's Pawn Game",
  
  "key_point_labels": [],
  "notes": ""
}
```

---

## Components Breakdown

### 1. Theme Calculators (11 Non-Engine Themes)

Located in `backend/theme_calculators.py`:

1. **center_space**: Central control and space advantage
2. **pawn_structure**: Pawn weaknesses, strengths, structure quality
3. **king_safety**: King exposure, castling rights, safety factors
4. **piece_activity**: Piece mobility, coordination, activity scores
5. **color_complex**: Color complex control and imbalances
6. **lanes**: File and rank control, open files, ranks
7. **local_imbalances**: Local tactical and strategic imbalances
8. **development**: Piece development, centralization
9. **promotion**: Promotion threats and opportunities
10. **breaks**: Pawn breaks and structural changes
11. **prophylaxis**: Defensive moves and prevention

**Function:** `compute_themes_and_tags(fen: str) -> Dict`
- Runs in ProcessPoolExecutor (separate process)
- Returns themes dict and tags list

### 2. Tag Detectors (100+ Tags)

Located in `backend/tag_detector.py`:

**Tag Categories:**
- King safety tags (castled, exposed, etc.)
- Pawn tags (isolated, doubled, passed, etc.)
- Center space tags (control.core, control.extended, etc.)
- File tags (open file, semi-open file, etc.)
- Diagonal tags (bishop diagonal, etc.)
- Outpost/hole tags (knight outpost, weak square, etc.)
- Activity tags (piece activity, coordination, etc.)
- Lever tags (pawn lever, etc.)

**Function:** Multiple detector functions aggregated by `aggregate_all_tags()`

### 3. Material Calculator

**Function:** `calculate_material_balance(board) -> int`
- Returns material balance in centipawns
- Standard piece values: Q=900, R=500, B=300, N=300, P=100

### 4. Theme Score Aggregator

**Function:** `compute_theme_scores(themes: Dict) -> Dict`
- Aggregates theme scores per side
- Applies weights to each theme
- Returns `{"white": {...}, "black": {...}}`

**Theme Weights:**
- `king_safety`: 1.2
- `promotion`: 1.5
- `color_complex`: 0.8
- `lanes`: 0.9
- `local_imbalances`: 0.7
- `breaks`: 0.8
- `prophylaxis`: 0.6
- Others: 1.0

### 5. Delta Analyzer

**Function:** `calculate_delta(...) -> Dict`
- Computes differences between start and final positions
- Classifies plan types:
  - `balanced`: Equal material and positional factors
  - `material_gain`: Material advantage gained
  - `positional_improvement`: Positional factors improved
  - `leveraging_advantage`: Using existing advantage
  - `defensive`: Defensive consolidation
  - `tactical`: Tactical sequence
- Returns plan type, explanation, deltas

### 6. Threat Analyzer

**Function:** `detect_engine_threats(fen, engine_queue, depth) -> Dict`
- Uses engine to detect tactical threats
- Returns threats by side

### 7. Piece Profiler (Optional)

**Functions:**
- `get_nnue_dump(fen)`: Extract NNUE evaluation per piece
- `build_piece_profiles(...)`: Combine NNUE + tags + themes
- `compute_square_control(board)`: Calculate square control
- `track_pv_profiles(...)`: Track piece trajectories
- `detect_captures_in_pv(...)`: Detect captures in PV

---

## Usage Examples

### Example 1: Analyze Single Position

```python
import requests

response = requests.get(
    "http://localhost:8000/analyze_position",
    params={
        "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
        "depth": 18,
        "lines": 3,
        "light_mode": False
    }
)

data = response.json()
print(f"Eval: {data['eval_cp']}cp")
print(f"Best move: {data['best_move']}")
print(f"White theme scores: {data['white_analysis']['chunk_1_immediate']['theme_scores']}")
print(f"Tags found: {len(data['white_analysis']['chunk_1_immediate']['tags'])}")
```

### Example 2: Analyze Full Game

```python
from backend.engine_pool import EnginePool
import chess

# Initialize pool
pool = EnginePool(pool_size=4)
await pool.initialize()

# Parse game
pgn = "..."
game = chess.pgn.read_game(StringIO(pgn))
board = game.board()

# Build positions list
positions = []
for move in game.mainline_moves():
    fen_before = board.fen()
    board.push(move)
    positions.append((fen_before, move))

# Analyze
results = await pool.analyze_game_parallel(
    positions=positions,
    depth=14,
    multipv=2
)

# Access raw analysis
for ply_record in results:
    raw_before = ply_record["raw_before"]
    raw_after = ply_record["raw_after"]
    
    print(f"Ply {ply_record['ply']}: {ply_record['san']}")
    print(f"  Eval before: {raw_before['eval_cp']}cp")
    print(f"  Tags before: {len(raw_before['tags'])}")
    print(f"  Theme scores: {raw_before['theme_scores']['white']['total']}")
```

### Example 3: Access Raw Analysis from Game Review

```python
# Game review stored in database includes raw_before/raw_after
review = get_game_review(game_id)

for ply_record in review["ply_records"]:
    raw_before = ply_record.get("raw_before", {})
    
    # Access themes
    center_space = raw_before["themes"]["center_space"]
    
    # Access tags
    center_tags = [t for t in raw_before["tags"] 
                   if "center" in t.get("tag_name", "")]
    
    # Access engine info
    best_eval = raw_before["engine_info"][0]["eval_cp"]
    second_eval = raw_before["engine_info"][1]["eval_cp"]
    gap = abs(best_eval - second_eval)
    
    # Access theme scores
    white_total = raw_before["theme_scores"]["white"]["total"]
    black_total = raw_before["theme_scores"]["black"]["total"]
```

---

## Performance Characteristics

### Single Position Analysis

**Timing (depth=18, light_mode=false):**
- Step 1 (Candidates): ~200-500ms
- Step 2 (Material): <1ms
- Step 3 (PV Build): <1ms
- Step 4 (Themes/Tags): ~100-200ms (parallel)
- Step 5 (Final Eval): ~200-500ms
- Step 6 (Delta): <10ms
- Step 7 (Piece Profiles): ~200-500ms
- **Total: ~700-1700ms**

**Timing (depth=18, light_mode=true):**
- **Total: ~500-1200ms** (saves ~200-500ms)

### Game Analysis

**Optimizations:**
- Unique position deduplication: ~50% reduction
- Parallel engine analysis: 4x speedup (with 4 engines)
- Parallel theme calculation: 4x speedup (with 4 workers)
- Theory batch checking: Parallel for first 30 moves

**Timing (60-move game, depth=14):**
- Unique positions: ~90 (from 120 total)
- Theory checks: ~30 positions, ~300-500ms (parallel)
- Position analysis: ~90 positions, ~2-4 seconds (parallel)
- Ply record building: ~100-200ms
- **Total: ~3-5 seconds**

### Memory Usage

- **Per position cache:** ~50-100KB (themes + tags + engine info)
- **60-move game:** ~5-10MB total cache
- **Engine pool:** ~50MB per engine instance

---

## Data Flow Diagram

```
Input (FEN)
    │
    ├─→ [Stockfish Engine] ──→ Engine Eval + PV
    │
    ├─→ [Material Calculator] ──→ Material Balance
    │
    ├─→ [ProcessPoolExecutor] ──→ compute_themes_and_tags()
    │   │
    │   ├─→ [11 Theme Calculators] ──→ Themes Dict
    │   │
    │   ├─→ [8 Tag Detectors] ──→ Tags List (100+)
    │   │
    │   └─→ [Material Calculator] ──→ Material Balance
    │
    └─→ [Theme Score Aggregator] ──→ Theme Scores
    
Combine:
    ├─→ Raw Analysis Structure
    │   ├─→ themes
    │   ├─→ tags
    │   ├─→ material_balance_cp
    │   ├─→ theme_scores
    │   ├─→ engine_info
    │   └─→ eval_cp
    │
    └─→ (For /analyze_position) ──→ Chunked Response
        ├─→ chunk_1_immediate
        └─→ chunk_2_plan_delta
```

---

## Notes

1. **Raw analysis is stripped in SSE responses** to reduce payload size. Full data is available in database and via `/analyze_position` endpoint.

2. **Theme calculations are CPU-bound** and run in separate processes to avoid blocking the event loop.

3. **Engine analysis is I/O-bound** (waiting for Stockfish) and runs in async engine pool.

4. **Unique position deduplication** significantly reduces analysis time for games (fen_after of move N == fen_before of move N+1).

5. **Light mode** skips piece profiling (Step 7) for ~30% faster analysis when piece-level detail isn't needed.

6. **Raw analysis data is cached** during game analysis to avoid re-computing the same positions.

---

## Related Files

- `backend/main.py`: `/analyze_position` endpoint
- `backend/engine_pool.py`: `analyze_game_parallel()` method
- `backend/parallel_analyzer.py`: `compute_themes_and_tags()` function
- `backend/theme_calculators.py`: All 11 theme calculators
- `backend/tag_detector.py`: All tag detectors
- `backend/delta_analyzer.py`: Delta computation and plan classification
- `backend/material_calculator.py`: Material balance calculation
- `backend/threat_analyzer.py`: Engine-based threat detection


















