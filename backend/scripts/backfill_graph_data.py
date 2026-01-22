#!/usr/bin/env python3
"""
Backfill script to pre-compute graph data for all existing games.
This should be run once after deploying the game_graph_data table migration.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from supabase_client import SupabaseClient
from profile_analytics.graph_data import build_graph_game_point


def backfill_user(user_id: str, supabase: SupabaseClient, limit: int = 60):
    """Backfill graph data for a single user's most recent games."""
    print(f"\n🔄 Processing user: {user_id}")
    
    try:
        # Get all active reviewed games (up to limit)
        games = supabase.get_active_reviewed_games(user_id, limit=limit, include_full_review=True)
        
        if not games:
            print(f"   ⚠️ No games found for user {user_id}")
            return 0
        
        print(f"   📚 Found {len(games)} games")
        
        # Sort by date
        def _date_key(g):
            gd = g.get("game_date")
            if isinstance(gd, str):
                return gd
            return ""
        
        games_sorted = sorted(games, key=_date_key)
        
        # Compute and save graph data for each game
        saved_count = 0
        for idx, game in enumerate(games_sorted):
            game_id = game.get("id")
            if not game_id:
                continue
            
            try:
                # Build graph point
                graph_point = build_graph_game_point(game, idx)
                
                # Save to database
                if supabase._save_game_graph_data(user_id, game_id, graph_point):
                    saved_count += 1
                    if (idx + 1) % 10 == 0:
                        print(f"   ✅ Processed {idx + 1}/{len(games_sorted)} games...")
                else:
                    print(f"   ⚠️ Failed to save graph data for game {game_id}")
            except Exception as e:
                print(f"   ⚠️ Error processing game {game_id}: {e}")
                continue
        
        print(f"   ✅ Saved graph data for {saved_count}/{len(games_sorted)} games")
        return saved_count
        
    except Exception as e:
        print(f"   ❌ Error processing user {user_id}: {e}")
        import traceback
        traceback.print_exc()
        return 0


def main():
    """Backfill graph data for all users or a specific user."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Backfill graph data for existing games")
    parser.add_argument("--user-id", type=str, help="Specific user ID to backfill (optional)")
    parser.add_argument("--limit", type=int, default=60, help="Number of games per user to process (default: 60)")
    args = parser.parse_args()
    
    # Initialize Supabase client
    try:
        from dotenv import load_dotenv
        load_dotenv()
        
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        
        if not supabase_url or not supabase_key:
            print("❌ Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in environment")
            return
        
        supabase = SupabaseClient(supabase_url, supabase_key)
        print("✅ Connected to Supabase")
    except Exception as e:
        print(f"❌ Failed to initialize Supabase client: {e}")
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
            
            total_saved = 0
            for user_id in user_ids:
                saved = backfill_user(user_id, supabase, args.limit)
                total_saved += saved
            
            print(f"\n✅ Backfill complete: {total_saved} graph data points saved across {len(user_ids)} users")
        except Exception as e:
            print(f"❌ Error finding users: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()

