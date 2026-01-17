#!/usr/bin/env python3
"""
Backfill script to recompute detailed analytics for all existing users and games.
This script should be run after deploying the detailed analytics system.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from supabase_client import SupabaseClient
from personal_stats_manager import PersonalStatsManager
from profile_analytics.detailed_analytics import DetailedAnalyticsAggregator


def backfill_user(user_id: str, supabase: SupabaseClient, stats_manager: PersonalStatsManager):
    """Backfill detailed analytics for a single user."""
    print(f"\n🔄 Processing user: {user_id}")
    
    try:
        # Get all active reviewed games
        games = supabase.get_active_reviewed_games(user_id, limit=100, include_full_review=True)
        
        if not games:
            print(f"   ⚠️ No games found for user {user_id}")
            return False
        
        print(f"   📚 Found {len(games)} games")
        
        # Recompute stats for each game
        for game in games:
            game_id = game.get("id")
            game_review = game.get("game_review", {})
            
            if not game_review:
                continue
            
            # Update stats incrementally
            stats_manager.update_stats_from_game(user_id, game_id, game_review)
        
        print(f"   ✅ Updated stats for {len(games)} games")
        return True
        
    except Exception as e:
        print(f"   ❌ Error processing user {user_id}: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main backfill function."""
    print("🚀 Starting detailed analytics backfill...")
    
    # Initialize clients
    supabase = SupabaseClient()
    stats_manager = PersonalStatsManager(supabase)
    
    # Get all users with games
    try:
        # Query for users who have analyzed games
        result = supabase.client.table("games")\
            .select("user_id")\
            .not_.is_("analyzed_at", "null")\
            .execute()
        
        user_ids = list(set([row["user_id"] for row in result.data]))
        print(f"📊 Found {len(user_ids)} users with analyzed games")
        
        # Process each user
        success_count = 0
        fail_count = 0
        
        for i, user_id in enumerate(user_ids, 1):
            print(f"\n[{i}/{len(user_ids)}] Processing user {user_id[:8]}...")
            if backfill_user(user_id, supabase, stats_manager):
                success_count += 1
            else:
                fail_count += 1
        
        print(f"\n✅ Backfill complete!")
        print(f"   Success: {success_count}")
        print(f"   Failed: {fail_count}")
        print(f"   Total: {len(user_ids)}")
        
    except Exception as e:
        print(f"❌ Error during backfill: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())

