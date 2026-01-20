# Investigation PGN - Extracted Documentation

*This document will be populated when you run the extraction script with a real investigation result.*

## How to Generate This Document

Run the extraction script after performing an investigation:

```bash
python3 backend/scripts/extract_recent_pgn.py
```

Or provide a specific FEN:

```bash
python3 backend/scripts/extract_recent_pgn.py "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
```

## Expected PGN Structure

The PGN will contain:

### Main Line (Principal Variation)
The root PV from D16 analysis, showing the engine's best continuation with:
- **Eval annotations**: `[%eval +X.XX]` for each move
- **Theme annotations**: `[%theme "theme1,theme2"]` showing positional themes
- **Tactic annotations**: `[%tactic "tactic_type"]` showing tactical patterns
- **Tag changes**: `{[gained: tags], [lost: tags], [threats: threats]}` showing what changed

### Alternate Branches
Variations showing:
- **Overestimated moves**: Moves D2 thought were good but D16 proves inferior
- **Stopped branches**: Branches that stopped early with reasons:
  - `d2_eval_below_original`: Position became worse
  - `no_overestimated_moves`: D16 and D2 agree
  - `depth_limit`: Maximum recursion reached

## Example Structure

```
[Event "Investigation"]
[FEN "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"]
[Starting tags: tag.king.shield.intact, tag.center.control.core, ...]

1. e4 [%eval +0.28] [%theme "center_space,development"] [%tactic "center_control"] 
   {[gained: center control core, key e4], [lost: none], [threats: center control]}
    (1. e4 [%eval +0.25] [%theme "stopped_branch,d2_worse_than_original"] 
     Branch stopped: d2_eval_below_original. D2 eval (+0.25) below original (+0.28), diff: -0.03.)
1... e5 [%eval +0.30] [%theme "center_space,king_safety"] [%tactic "none"] 
     {[gained: key e5], [lost: none], [threats: none]}
2. Nf3 [%eval +0.32] [%theme "development,piece_activity"] [%tactic "knight_development"] 
   {[gained: knight development, piece activity], [lost: none], [threats: knight activity]}
    (2. d4 [%eval +0.24] [%theme "overestimated"] D2 overestimates. Threat: center_control.)
2... Nf6 [%eval +0.28] [%theme "development,king_safety"] [%tactic "knight_development"] 
     {[gained: knight development], [lost: none], [threats: none]}
...
```

## Next Steps

1. Run an investigation through the backend API or directly via the Investigator class
2. Extract the `pgn_exploration` field from the `InvestigationResult`
3. Run the extraction script to generate this document with full details

---

*Run `python3 backend/scripts/extract_recent_pgn.py` to populate this document with actual investigation data.*
















