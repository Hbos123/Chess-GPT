# Lichess Opening Database

Build a comprehensive opening database from Lichess chess-openings repository (CC0 licensed).

## Overview

This module creates a FEN-based opening tree by:
1. Downloading Lichess chess-openings TSV (500 ECO codes with canonical lines)
2. Parsing opening sequences into a position tree (~30K nodes)
3. Enriching positions with Stockfish evaluations from Lichess eval DB
4. Flagging critical positions where the 2nd best move loses >50cp
5. Importing everything to Supabase

## Installation

```bash
cd backend/opening_database
pip install -r requirements.txt
```

## Configuration

Set environment variables:

```bash
export SUPABASE_URL="https://your-project.supabase.co"
export SUPABASE_SERVICE_KEY="your-service-role-key"
```

## Usage

### Full Pipeline

```bash
python -m backend.opening_database.main
```

This will:
- Download openings.tsv (~500KB)
- Download eval database (~10GB, one-time)
- Parse and enrich positions
- Import to Supabase

**Expected runtime:** 30-60 minutes (mostly eval DB scan)

### Step-by-Step

```python
from backend.opening_database import (
    LichessDownloader,
    OpeningsParser,
    EvalEnricher,
    CriticalDetector,
    SupabaseImporter
)

# Step 1: Download
downloader = LichessDownloader()
tsv_path = downloader.download_openings_data()
eval_path = downloader.download_eval_database()

# Step 2: Parse
parser = OpeningsParser()
parser.parse_tsv(tsv_path)

# Step 3: Enrich
enricher = EvalEnricher(eval_path)
enricher.load_eval_index(parser.position_nodes)
enricher.enrich_positions(parser.position_nodes)

# Step 4: Detect critical positions
detector = CriticalDetector()
critical_fens = detector.detect_critical_positions(parser.position_nodes)

# Step 5: Import
importer = SupabaseImporter()
importer.import_eco_codes(parser.eco_entries)
importer.import_position_nodes(parser.position_nodes)
importer.import_critical_notes(parser.position_nodes, critical_fens, detector)
```

## Output

### Supabase Tables

1. **openings** (~500 rows)
   - ECO codes (A00-E99)
   - Opening names
   - Canonical PGN lines
   - EPD positions

2. **opening_nodes** (~30,000 rows)
   - Every position in every opening line
   - Parent-child linkage for tree navigation
   - ECO codes and aliases

3. **opening_notes** (~1,000-3,000 rows)
   - Critical positions with auto-generated explanations
   - Flags for positions where accuracy is crucial

## Configuration

Edit `config.py` to customize:

```python
MAX_PLY_DEPTH = 30  # Track up to 15 moves per opening
MIN_EVAL_DEPTH = 20  # Only trust deep Stockfish evaluations
CRITICAL_CP_LOSS_THRESHOLD = 50  # CP loss to flag as critical
BATCH_SIZE = 1000  # Rows per database insert batch
```

## Data Sources

- **Chess Openings**: https://github.com/lichess-org/chess-openings (CC0)
- **Evaluations**: https://database.lichess.org/evals/ (CC0)

All derived data maintains CC0 license.

## Troubleshooting

### Eval DB Download Takes Forever

The eval database is ~10GB. Download once and cache:

```python
# Set custom path
from pathlib import Path
EVAL_DIR = Path("/path/to/large/storage/evals")
```

### Memory Issues

The eval DB scan uses streaming - memory usage stays <2GB. If issues persist, process in batches:

```python
# Process first 100 ECO codes
parser.eco_entries = parser.eco_entries[:100]
```

### Supabase Import Fails

Check RLS policies allow service role inserts:

```sql
-- In Supabase SQL Editor
ALTER TABLE openings ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Service role can insert" ON openings FOR INSERT 
  TO service_role USING (true);
```

## Future Enhancements

- Add game statistics from PGN dumps (popularity metrics)
- Add transposition detection (same position via different orders)
- Add player-specific statistics (Magnus's success in Najdorf, etc.)
- Incremental updates (monthly refresh from Lichess)

## License

Code: MIT  
Data: CC0 (Lichess)



