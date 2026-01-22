# Apply Supabase Migrations to Online Instance

This guide will help you apply all SQL migrations to your online Supabase database.

## Prerequisites

1. **Supabase Project Created**
   - Go to https://supabase.com and create a project
   - Wait for database to be provisioned (2-3 minutes)

2. **Get Your Credentials**
   - **SUPABASE_URL**: Found in Project Settings → API → Project URL
     - Example: `https://xxxxx.supabase.co`
   - **SUPABASE_DB_PASSWORD**: Found in Project Settings → Database → Database Password
     - This is the password you set when creating the project

3. **Set Environment Variables**
   
   Create or update `backend/.env`:
   ```bash
   SUPABASE_URL=https://your-project-ref.supabase.co
   SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
   SUPABASE_DB_PASSWORD=your-database-password
   ```

## Method 1: Automated Script (Recommended)

### Step 1: Install Dependencies

```bash
cd backend
pip install psycopg2-binary python-dotenv
```

### Step 2: Run Migration Script

```bash
python3 scripts/apply_all_migrations.py
```

The script will:
- ✅ Connect to your Supabase database
- ✅ Check which migrations have already been applied
- ✅ Run all migrations in order
- ✅ Track applied migrations in `schema_migrations` table
- ✅ Skip migrations that are already applied

### What the Script Does

1. **Connects** via Supabase Transaction Pooler (port 6543) or direct connection (port 5432)
2. **Creates** a `schema_migrations` table to track applied migrations
3. **Runs** all 33+ migration files in numerical order
4. **Tracks** which migrations have been applied
5. **Skips** migrations that are already applied (safe to re-run)

## Method 2: Manual via Supabase Dashboard

### Step 1: Open SQL Editor

1. Go to your Supabase Dashboard
2. Click **"SQL Editor"** in the left sidebar
3. Click **"New query"**

### Step 2: Run Migrations One by One

Run each migration file in order from `backend/supabase/migrations/`:

1. `000_complete_schema.sql` - Base schema
2. `001_auth_and_profiles.sql` - Auth and profiles
3. `002_collections.sql` - Collections
4. `003_games.sql` - Games table
5. `004_positions.sql` - Positions table
6. `005_chat.sql` - Chat tables
7. `006_training.sql` - Training cards
8. `007_rpcs.sql` - Stored procedures
9. `008_personal_review_updates.sql` - Personal review updates
10. `009_profile_linked_accounts.sql` - Linked accounts
11. `010_habit_trends.sql` - Habit trends
12. `011_positions_extended.sql` - Extended positions
13. `012_computed_habits.sql` - Computed habits
14. `013_advanced_analytics_rpcs.sql` - Advanced analytics
15. `014_diagnostic_analytics_v3.sql` - Diagnostic analytics
16. `015_learning_logging_v1.sql` - Learning logging
17. `016_prelaunch_hardening.sql` - Prelaunch hardening
18. `017_normalized_tags.sql` - Normalized tags
19. `018_moves_raw_table.sql` - Moves raw table
20. `019_move_metrics.sql` - Move metrics
21. `020_backfill_moves_raw.sql` - Backfill moves
22. `021_analytics_materialized_views.sql` - Materialized views
23. `022_refresh_analytics.sql` - Refresh analytics
24. `023_optimized_analytics_rpcs.sql` - Optimized analytics
25. `024_game_window_pattern_retention.sql` - Game window
26. `025a_fix_analytics_schema_part1.sql` - Analytics fix part 1
27. `025b_fix_analytics_schema_part2.sql` - Analytics fix part 2
28. `025c_fix_analytics_schema_part3.sql` - Analytics fix part 3
29. `026_pattern_snapshots.sql` - Pattern snapshots
30. `027_position_cascade_delete.sql` - Cascade delete
31. `028_detailed_analytics.sql` - Detailed analytics
32. `029_game_graph_data.sql` - Game graph data
33. `030_detailed_analytics_cache.sql` - Analytics cache
34. `031_positions_tag_transitions.sql` - Tag transitions
35. `032_positions_drill_indexes.sql` - Drill indexes

**For each file:**
1. Open the file in your editor
2. Copy the entire contents
3. Paste into SQL Editor
4. Click **"Run"** (or press Cmd/Ctrl + Enter)
5. Wait for success message
6. Move to next file

## Verification

After running migrations, verify they were applied:

### Check Migration Table

```sql
SELECT version, applied_at 
FROM schema_migrations 
ORDER BY applied_at;
```

### Check Key Tables Exist

```sql
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
ORDER BY table_name;
```

You should see tables like:
- `profiles`
- `games`
- `positions`
- `training_cards`
- `collections`
- `chat_sessions`
- etc.

### Check Functions Exist

```sql
SELECT routine_name 
FROM information_schema.routines 
WHERE routine_schema = 'public' 
AND routine_type = 'FUNCTION'
ORDER BY routine_name;
```

## Troubleshooting

### Connection Errors

**Error: "could not connect to server"**
- Check `SUPABASE_URL` is correct
- Verify database password is correct
- Check project is not paused in Supabase Dashboard
- Try different network (some networks block database ports)

**Error: "password authentication failed"**
- Verify `SUPABASE_DB_PASSWORD` matches the password in Supabase Dashboard
- Password is case-sensitive

### Migration Errors

**Error: "relation already exists"**
- Migration was partially applied before
- Safe to skip - the script will mark it as applied
- Or manually mark it: `INSERT INTO schema_migrations (version) VALUES ('filename.sql');`

**Error: "function already exists"**
- Function was created in a previous migration
- Safe to continue - the script handles this

**Error: "column already exists"**
- Column was added in a previous migration
- Safe to continue

### Timeout Errors

Some migrations might timeout if they process large amounts of data. If this happens:

1. **Check Supabase Dashboard** → Logs to see what's happening
2. **Run migrations individually** via SQL Editor
3. **For large migrations**, you may need to run them during off-peak hours

## Migration Order

Migrations are numbered and must be run in order:
- `000_*` runs first
- `001_*` runs second
- `025a_*`, `025b_*`, `025c_*` run in alphabetical order after `025_*`
- etc.

The automated script handles this automatically.

## Re-running Migrations

The script is **idempotent** - safe to run multiple times:
- Already-applied migrations are skipped
- New migrations are applied
- No duplicate data is created

## Next Steps

After migrations are applied:

1. **Set Environment Variables** in your backend:
   ```bash
   SUPABASE_URL=https://your-project.supabase.co
   SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
   ```

2. **Test Connection**:
   ```bash
   cd backend
   python3 -c "from supabase_client import SupabaseClient; import os; c = SupabaseClient(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_ROLE_KEY')); print('✅ Connected!')"
   ```

3. **Start Backend** and verify it connects to Supabase

## Support

If you encounter issues:
1. Check Supabase Dashboard → Logs for database errors
2. Verify all environment variables are set correctly
3. Check migration files exist in `backend/supabase/migrations/`
4. Try running migrations manually via SQL Editor
