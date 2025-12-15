# Profile Indexing & Insight Pipeline

## Overview

The profile indexing manager (`backend/profile_indexer.py`) fetches recent games from Chess.com/Lichess,
persists preferences, computes aggregate insights, and surfaces them via the `/profile/overview`
and `/profile/stats` endpoints. Indexed data powers the Personal dashboard inside the History Curtain.

## Lifecycle

1. **Preferences save** (`POST /profile/preferences`)
   - Preferences are stored locally (`backend/cache/profile_prefs`) and mirrored into Supabase
     (`profiles` table).
   - The manager launches a foreground indexing task that fetches batches (default 40 games/account)
     until the cache reaches the configured target.
   - When indexing completes, the cache is deduplicated, sorted, capped, and summary stats are recomputed.

2. **Background trickle indexing**
   - After at least 50 games are cached, each `/profile/overview` request calls
     `ProfileIndexingManager.ensure_background_index(user_id)`.
   - A lightweight scheduler throttles requests (`background_interval_seconds`, default 20 min) and,
     when idle, enqueues a background refresh with a smaller batch size (default 1/3 of foreground).
   - Status fields `background_active` and `next_poll_at` are exposed so the UI can show “Quietly indexing…”.

3. **Aggregated statistics**
   - `_compute_stats` aggregates the cached games into:
     - Overall record, win rate, average accuracy, blunder/mistake rates.
     - Opening performance (top/bottom, with accuracy + error rates).
  - **Opening profile snapshots** – per-opening+color breakdowns capturing games played, win rate, phase accuracy, common tags, recent examples, and divergence moves. The manager also surfaces a `priority` list so the UI/lesson planner can immediately highlight “high volume, low performance” openings.
     - Tag insights (best/worst tags by win rate and average CP loss, if provided by upstream analysis).
     - Phase accuracy (opening/middlegame/endgame), using any available `phase_accuracy` data.
     - Personality/tendency blurbs derived from the strongest signals.
   - The stats blob is cached in memory and persisted to Supabase (`profile_stats` table) so
     historical data survives restarts.
   - `GET /profile/stats` returns the cached structure for the frontend.

## Advanced Insight Buckets

Phase 4/5 adds an interpretation layer that surfaces the richer move-level metadata already captured by the light analysis pass:

- **Accuracy by piece & phase × piece heatmap** – per-piece CP loss/error rates, plus a phase overlay.
- **Position / advantage contexts** – open vs closed/IQP/opposite-side castling buckets and advantage regimes (losing → winning).
- **Tactical profile** – motif-level found/missed counts, average miss cost, and tactical phase concentration.
- **Structural & weakness tags** – cp_loss + win rates for tags like `tag.file.open.c`, plus separate trajectories for exploiting opponent weaknesses vs defending your own.
- **Time & pressure** – accuracy buckets for time usage and opponent rating gaps.
- **Playstyle sliders** – aggression vs positional, material vs initiative, simplification tendency, king-safety risk.
- **Conversion & resilience** – winning-position conversion rate, defensive save rate, and max advantage/deficit summaries.
- **Opening families & endgame snapshot** – aggregates per opening family plus quick phase accuracy recap.
- **Narrative insights** – generated bullet lists grouped by accuracy/tactics/structure/playstyle/conversion so the UI can show “who am I as a player?” sentences without reprocessing raw data.
- **Opening lesson personalization** – `summarize_opening_history` exposes the user’s most played lines, recurring mistakes, and variation hashes so the opening lesson generator can prioritize real experience and seed spaced repetition.

All of the above live under `stats.advanced` and `stats.insights` in `/profile/stats`, and the History Curtain now renders dedicated tables/cards for each section.

## Key Files

| File | Purpose |
| --- | --- |
| `backend/profile_indexer.py` | Core scheduler, caching, aggregation, Supabase sync |
| `backend/main.py` | Exposes `/profile/overview` (with background ping) and `/profile/stats` |
| `backend/supabase/migrations/000_complete_schema.sql` | Adds `profile_stats` table + policies |
| `frontend/app/page.tsx` | Loads overview/stats, triggers background activity |
| `frontend/components/HistoryCurtain.tsx` | Renders progress, stats tables, and personality section |

## Configuration

`ProfileIndexingManager` exposes several tunables:

| Setting | Default | Description |
| --- | --- | --- |
| `max_cached_games` | 200 | Total cached per user |
| `max_games_per_account` | 40 | Foreground fetch batch |
| `background_target_games` | 50 | Minimum before trickle mode |
| `background_interval_seconds` | 1200 | Delay between background batches |
| `background_batch_size` | `max(5, max_games_per_account / 3)` | Games per background pass |

Adjust these if API quotas or UX expectations change.

## Light vs Deep Analysis

- Light analysis uses the existing `_review_game_internal` pipeline (depth 12) to annotate every move, compute accuracy/blunder counts, and surface critical positions. Results are cached per game and reflected in `/profile/stats`.
- Deep analysis replays every critical FEN at a higher depth (20) through the shared Stockfish queue. Once the critical set for a game is finished, the `deep_analyzed_games` counter increments.
- `/profile/overview` now returns `games_indexed`, `light_analyzed_games`, and `deep_analyzed_games`, enabling the nested progress bar in the Personal dashboard (fetched ➝ light ➝ deep).
- Background refreshes automatically extend both analyses after new games arrive; the UI shows “Quietly indexing…” whenever the scheduler runs.

## Testing

Unit tests cover stat aggregation and scheduler gating (`tests/test_profile_indexer_stats.py`).
Use `pytest` to ensure background scheduling only fires when enough games exist and that aggregates
are stable given synthetic datasets.

