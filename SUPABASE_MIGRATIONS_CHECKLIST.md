# Supabase Migrations Checklist

## Quick Summary

Your project has **33+ SQL migration files** that need to be applied to your online Supabase database. These migrations create all tables, functions, and indexes needed for the application.

## Migration Files Location

All migrations are in: `backend/supabase/migrations/`

## How to Apply Migrations

### Option 1: Use Supabase SQL Editor (Easiest)

1. **Go to Supabase Dashboard** → SQL Editor → New Query

2. **Run migrations in order** (copy-paste each file):

   ```
   000_complete_schema.sql
   001_auth_and_profiles.sql
   002_collections.sql
   003_games.sql
   004_positions.sql
   005_chat.sql
   006_training.sql
   007_rpcs.sql
   008_personal_review_updates.sql
   009_profile_linked_accounts.sql
   010_habit_trends.sql
   011_positions_extended.sql
   012_computed_habits.sql
   013_advanced_analytics_rpcs.sql
   014_diagnostic_analytics_v3.sql
   015_learning_logging_v1.sql
   016_prelaunch_hardening.sql
   017_normalized_tags.sql
   018_moves_raw_table.sql
   019_move_metrics.sql
   020_backfill_moves_raw.sql
   021_analytics_materialized_views.sql
   022_refresh_analytics.sql
   023_optimized_analytics_rpcs.sql
   024_game_window_pattern_retention.sql
   025a_fix_analytics_schema_part1.sql
   025b_fix_analytics_schema_part2.sql
   025c_fix_analytics_schema_part3.sql
   026_pattern_snapshots.sql
   027_position_cascade_delete.sql
   028_detailed_analytics.sql
   029_game_graph_data.sql
   030_detailed_analytics_cache.sql
   031_positions_tag_transitions.sql
   032_positions_drill_indexes.sql
   ```

3. **For each file:**
   - Open the file in your editor
   - Copy entire contents
   - Paste into SQL Editor
   - Click "Run"
   - Wait for success ✅
   - Move to next file

### Option 2: Use Python Script

A script `backend/scripts/apply_all_migrations.py` can automate this:

```bash
cd backend
pip install psycopg2-binary python-dotenv
python3 scripts/apply_all_migrations.py
```

**Note:** You'll need `SUPABASE_DB_PASSWORD` in your `.env` file.

## Verification

After running migrations, verify in Supabase SQL Editor:

```sql
-- Check migration tracking table exists
SELECT * FROM schema_migrations ORDER BY applied_at;

-- Check key tables exist
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
ORDER BY table_name;

-- Should see: profiles, games, positions, training_cards, etc.
```

## Important Notes

1. **Run migrations in order** - They're numbered for a reason
2. **Don't skip migrations** - Each builds on the previous
3. **Safe to re-run** - Most migrations use `IF NOT EXISTS`
4. **Check for errors** - Some migrations might timeout on large datasets

## Troubleshooting

**"relation already exists"** → Migration was partially applied, safe to continue

**"function already exists"** → Already applied, safe to continue  

**Timeout errors** → Run migrations individually via SQL Editor

**Connection errors** → Check SUPABASE_URL and SUPABASE_DB_PASSWORD

## Next Steps

After migrations are applied:
1. ✅ Set `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` in Render
2. ✅ Deploy backend to Render
3. ✅ Test backend connects to Supabase
4. ✅ Verify tables are accessible
