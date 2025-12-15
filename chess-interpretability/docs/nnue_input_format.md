# NNUE input/dump format (patched Stockfish)

## Dump location
`chess-interpretability/nnue-dumps/eval_<timestamp>.json`

## Full JSON schema

```json
{
  "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
  "used_nnue": true,
  "final_eval_cp": -5,
  "nnue_eval_cp": -4,
  "classical_eval_cp": -63,
  
  "pieces": {
    "white_rook_a1": {"square": "a1"},
    "white_knight_b1": {"square": "b1"},
    "...": {}
  },
  
  "nnue_raw": {
    "bucket": 7,
    "psqt_raw": 253,
    "positional_raw": -479,
    "layer_outputs": [-479],
    "transformed_features": [0, 0, 1, 0, 19, ...]
  },
  
  "classical_terms": {
    "MATERIAL": {"white_mg": 23, "black_mg": 0},
    "IMBALANCE": {"white_mg": 0, "black_mg": 0},
    "MOBILITY": {"white_mg": -46, "black_mg": -182},
    "THREAT": {"white_mg": 0, "black_mg": 6},
    "PASSED": {"white_mg": 0, "black_mg": 0},
    "SPACE": {"white_mg": 105, "black_mg": 63},
    "WINNABLE": {"white_mg": 0, "black_mg": 0},
    "TOTAL": {"white_mg": 213, "black_mg": 0}
  },
  
  "masked_total": {
    "white_rook_a1": 560,
    "white_knight_b1": 497,
    "white_bishop_c1": 567,
    "white_queen_d1": 738,
    "white_king_e1": 0,
    "...": 0
  },
  
  "masked_classical": {
    "white_rook_a1": 278,
    "white_knight_b1": 177,
    "white_bishop_c1": 218,
    "white_queen_d1": 738,
    "white_king_e1": 0,
    "...": 0
  }
}
```

## Field descriptions

### Core evaluation
| Field | Type | Description |
|-------|------|-------------|
| `fen` | string | Position in FEN notation |
| `used_nnue` | bool | Whether NNUE was used for this evaluation |
| `final_eval_cp` | int | Final blended evaluation in centipawns |
| `nnue_eval_cp` | int | Raw NNUE evaluation before blending |
| `classical_eval_cp` | int | Classical evaluation |

### NNUE internals
| Field | Type | Description |
|-------|------|-------------|
| `bucket` | int | NNUE bucket (0-7, based on piece count) |
| `psqt_raw` | int | Raw PSQT (piece-square table) component |
| `positional_raw` | int | Positional component from network layers |
| `layer_outputs` | int[] | Output values from each network layer |
| `transformed_features` | int[] | Feature transformer output (post-clipped accumulator) |

### Per-piece masked evaluations
| Field | Type | Description |
|-------|------|-------------|
| `masked_total` | dict | Eval (cp) with each piece removed, NNUE enabled |
| `masked_classical` | dict | Eval (cp) with each piece removed, classical only |

**Note:** Kings return 0 (removing them creates invalid positions). Pieces whose removal puts the king in check also return 0.

## Piece contribution calculation

To compute a piece's contribution to the evaluation:

```python
# From the dump
base_eval = dump["final_eval_cp"]  # e.g., -5
masked_eval = dump["masked_total"]["white_queen_d1"]  # e.g., 738

# Contribution = base - masked
# If positive, piece helps the side to move
contribution = base_eval - masked_eval  # -5 - 738 = -743

# White queen contributes -743 cp from black's perspective
# (Removing it swings eval by 743 cp in white's favor)
```

## UCI options to enable dumping

```
setoption name DumpNNUE value true        # Enable NNUE dump
setoption name DumpFeatures value true    # Include transformed features
setoption name DumpActivations value true # Include layer outputs  
setoption name DumpClassical value true   # Include classical terms
setoption name DumpPath value /path/to/dumps
```

## Example session

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

# Check output
cat /tmp/nnue-dumps/eval_*.json | python3 -m json.tool
```
