# NNUE Interpretability – Architecture (Option C)

## Overview
This pipeline patches Stockfish to emit raw NNUE internals and classical eval terms. Dumps are consumed by Python tooling to compute per-piece attributions and expose a CLI/HTTP API.

## Components
- **Patched Stockfish** (`backend/Stockfish-sf_16/src`): new UCI flags `DumpNNUE`, `DumpFeatures`, `DumpActivations`, `DumpClassical`, `DumpPath`; debug dumps land in `chess-interpretability/stockfish-modified/nnue-dumps/`.
- **Masking command**: `maskpiece <square>` removes the piece on the given square and re-evaluates, printing masked eval.
- **Python tools** (`chess-interpretability/python-tools`):
  - `nnue_loader.py` – load dumps (latest helper).
  - `classical_eval_parser.py` – parse classical terms.
  - `piece_attribution.py` – attribution scaffolding.
  - `end_to_end_analysis.py` – run engine, gather dump, compute JSON.
- **Interfaces** (`chess-interpretability/interfaces`):
  - `cli.py` – `python cli.py "<FEN>"`.
  - `api_server.py` – `/analyze` endpoint (FastAPI).

## Data flow
1. Engine invoked with dump options on and `go depth 1`.
2. Stockfish writes `eval_<timestamp>.json` with FEN, piece list, NNUE raw values, classical terms.
3. Python reads latest dump, parses NNUE/classical data, builds per-piece profile (NNUE deltas to be enriched with masked runs).
4. CLI/API return unified JSON for the given FEN.

## Notes
- Normal eval is unchanged when dump flags are off.
- Masking is approximate (piece removal) to allow quick Δ-eval experiments.
- Extend `piece_attribution.py` to consume masked/unmasked pairs for richer per-piece deltas.

