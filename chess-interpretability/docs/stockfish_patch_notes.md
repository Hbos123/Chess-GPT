# Stockfish patch notes

## Added UCI options
- `DumpNNUE` (check): enable NNUE debug dumps
- `DumpFeatures` (check): include transformed features
- `DumpActivations` (check): include layer outputs
- `DumpClassical` (check): include classical trace terms
- `DumpPath` (string): directory for dumps (default `chess-interpretability/nnue-dumps`)

## Dump output format

When any dump flag is on, `Eval::evaluate` writes `eval_<timestamp>.json` with:

### Core evaluation data
- `fen`: Position FEN string
- `used_nnue`: Whether NNUE was used (boolean)
- `final_eval_cp`: Final blended evaluation in centipawns
- `nnue_eval_cp`: Raw NNUE evaluation in centipawns
- `classical_eval_cp`: Classical evaluation in centipawns

### Piece information
- `pieces`: Dictionary mapping piece IDs (e.g., `white_knight_b1`) to their squares

### NNUE internals
- `nnue_raw.bucket`: The NNUE bucket used (based on piece count)
- `nnue_raw.psqt_raw`: Raw PSQT score from NNUE
- `nnue_raw.positional_raw`: Positional score from network layers
- `nnue_raw.layer_outputs`: Network layer output values
- `nnue_raw.transformed_features`: Feature transformer output buffer

### Classical terms
- `classical_terms`: Breakdown by category (MATERIAL, IMBALANCE, MOBILITY, THREAT, PASSED, SPACE, WINNABLE, TOTAL)

### Per-piece masked evaluations
- `masked_total`: Dictionary mapping piece IDs to the NNUE evaluation when that piece is removed
- `masked_classical`: Dictionary mapping piece IDs to the classical evaluation when that piece is removed

**Masking semantics:**
- For each non-king piece, a modified FEN is created with the piece removed
- A fresh position is set up and evaluated (both NNUE and classical)
- The masked eval represents "what would the position evaluate to without this piece?"
- Kings are skipped (returns 0) since removing them creates invalid positions
- Pieces whose removal puts the king in check are also skipped (returns 0)

To compute a piece's **contribution**, subtract the masked eval from the base eval:
```
contribution = base_eval - masked_eval
```
Positive contribution means the piece helps the side to move.

## Files touched
- `src/evaluate.h/cpp` — debug flags, dumping helper, FEN manipulation, per-piece masking
- `src/nnue/evaluate_nnue.h/cpp` — debug struct, optional capture
- `src/nnue/nnue_feature_transformer.h` — mask_transformed_buffer helper
- `src/ucioption.cpp` — UCI options for dumping

## Build
From `backend/Stockfish-sf_16/src`:
```bash
make build ARCH=apple-silicon  # For Apple Silicon Macs
# or
make build ARCH=x86-64-modern  # For modern x86-64 CPUs
```

The resulting binary is at `backend/Stockfish-sf_16/src/stockfish`.

## Usage example

```bash
./stockfish <<EOF
uci
setoption name DumpNNUE value true
setoption name DumpClassical value true
setoption name DumpPath value /tmp/nnue-dumps
position fen rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1
eval
quit
EOF
```

This creates a JSON dump file in `/tmp/nnue-dumps/` with full NNUE internals and per-piece masked evaluations.
