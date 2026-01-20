#!/usr/bin/env python3
"""
Backfill script to pre-compute detailed analytics cache for all existing users.
This should be run once after deploying the detailed_analytics_cache table migration.
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# Try to load from .env if available
try:
    from dotenv import load_dotenv
    env_file = backend_dir / ".env"
    if env_file.exists():
        load_dotenv(env_file)
except ImportError:
    pass

from supabase_client import SupabaseClient
from profile_analytics.detailed_analytics import DetailedAnalyticsAggregator


def backfill_user(user_id: str, supabase: SupabaseClient, limit: int = 60):
    """Backfill detailed analytics cache for a single user."""
    print(f"\n🔄 Processing user: {user_id}")
    
    try:
        # Get active reviewed games (up to limit)
        games = supabase.get_active_reviewed_games(user_id, limit=limit, include_full_review=True)
        
        if not games:
            print(f"   ⚠️ No games found for user {user_id}")
            return False
        
        print(f"   📚 Found {len(games)} games")
        
        # Compute detailed analytics
        aggregator = DetailedAnalyticsAggregator()
        analytics_data = aggregator.aggregate(games)
        
        # Save to cache
        if supabase._save_detailed_analytics_cache(user_id, analytics_data, len(games)):
            print(f"   ✅ Saved detailed analytics cache for {len(games)} games")
            return True
        else:
            print(f"   ⚠️ Failed to save detailed analytics cache")
            return False
        
    except Exception as e:
        print(f"   ❌ Error processing user {user_id}: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Backfill detailed analytics cache for all users or a specific user."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Backfill detailed analytics cache for existing users")
    parser.add_argument("--user-id", type=str, help="Specific user ID to backfill (optional)")
    parser.add_argument("--limit", type=int, default=60, help="Number of games per user to process (default: 60)")
    args = parser.parse_args()
    
    # Initialize Supabase client
    try:
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        
        if not supabase_url or not supabase_key:
            print("❌ Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in environment")
            print("   Make sure you're running from the backend directory with .env file")
            return
        
        supabase = SupabaseClient(supabase_url, supabase_key)
        print("✅ Connected to Supabase")
    except Exception as e:
        print(f"❌ Failed to initialize Supabase client: {e}")
        import traceback
        traceback.print_exc()
        return
    
    if args.user_id:
        # Backfill specific user
        backfill_user(args.user_id, supabase, args.limit)
    else:
        # Backfill all users
        print("🔍 Finding all users with analyzed games...")
        try:
            # Get all users who have games
            result = supabase.client.table("games")\
                .select("user_id")\
                .not_.is_("analyzed_at", "null")\
                .execute()
            
            user_ids = list(set([g.get("user_id") for g in (result.data or []) if g.get("user_id")]))
            print(f"📊 Found {len(user_ids)} users with analyzed games")
            
            success_count = 0
            fail_count = 0
            for i, user_id in enumerate(user_ids, 1):
                print(f"\n[{i}/{len(user_ids)}] Processing user {user_id[:8]}...")
                if backfill_user(user_id, supabase, args.limit):
                    success_count += 1
                else:
                    fail_count += 1
            
            print(f"\n✅ Backfill complete: {success_count} succeeded, {fail_count} failed across {len(user_ids)} users")
        except Exception as e:
            print(f"❌ Error finding users: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()

