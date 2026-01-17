-- Detailed Analytics Migration
-- Adds new JSONB fields to personal_stats.stats structure for comprehensive analytics
-- This migration is additive and does not break existing functionality

-- Note: The personal_stats.stats JSONB column already exists and is flexible.
-- This migration documents the new structure but doesn't require schema changes.
-- The new fields will be populated by the backend as games are analyzed.

-- New fields added to personal_stats.stats JSONB:
-- {
--   "phase_analytics": {
--     "opening": {"accuracy": 75.2, "games_won": 12, "games_lost": 8, "games_drawn": 2},
--     "middlegame": {...},
--     "endgame": {...}
--   },
--   "opening_detailed": {
--     "Sicilian Defense": {
--       "frequency": 15,
--       "avg_accuracy": 78.5,
--       "win_rate": 0.6,
--       "wins": 9,
--       "losses": 5,
--       "draws": 1
--     }
--   },
--   "piece_accuracy_detailed": {
--     "per_game": [...],  -- Array of per-game piece breakdowns
--     "aggregate": {
--       "Pawn": {"accuracy": 82.1, "count": 450},
--       "Knight": {...}
--     }
--   },
--   "tag_transitions": {
--     "gained": {
--       "tag.center.control.core": {
--         "accuracy": 75.3,
--         "blunders": 2,
--         "mistakes": 5,
--         "inaccuracies": 8,
--         "count": 15
--       }
--     },
--     "lost": {...}
--   },
--   "time_buckets": {
--     "<5s": {"accuracy": 68.2, "blunder_rate": 0.15, "count": 120, "blunders": 18},
--     "5-15s": {...},
--     "15-30s": {...},
--     "30s-1min": {...},
--     "1min-2min30": {...},
--     "2min30-5min": {...},
--     "5min+": {...}
--   }
-- }

-- No schema changes needed - JSONB is flexible
-- Backend will populate these fields incrementally as games are analyzed

COMMENT ON COLUMN public.personal_stats.stats IS 
'JSONB stats payload. New fields: phase_analytics (phase win/loss tracking), 
opening_detailed (opening repertoire with accuracy), piece_accuracy_detailed 
(per-game and aggregate piece accuracy), tag_transitions (gained/lost tag analytics), 
time_buckets (7-bucket time performance with blunder rates).';

