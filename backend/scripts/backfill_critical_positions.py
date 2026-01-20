#!/usr/bin/env python3
"""
Backfill script to extract and save critical positions from existing analyzed games.
This script processes all games with game_review data and extracts blunders/mistakes as positions.
"""

import sys
import os
from pathlib import Path
from typing import List, Dict, Any

# Add parent directory to path
script_dir = Path(__file__).parent
backend_dir = script_dir.parent
project_root = backend_dir.parent
sys.path.insert(0, str(backend_dir))

from dotenv import load_dotenv
load_dotenv(backend_dir / ".env")

# Import after path setup
from profile_analytics.engine import ProfileAnalyticsEngine

def get_supabase_client():
    """Initialize the appropriate database client."""
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if not supabase_url or not supabase_key:
        print("❌ Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in environment")
        return None
    
    # Use Supabase client
    from supabase_client import SupabaseClient
    print(f"📦 Using Supabase: {supabase_url}")
    return SupabaseClient(supabase_url, supabase_key)


def backfill_user_positions(user_id: str, supabase_client, limit: int = None):
    """Backfill critical positions for a single user."""
    print(f"\n🔄 Processing user: {user_id}")
    
    try:
        # Get all games with full reviews (need ply_records)
        if limit:
            games = supabase_client.get_active_reviewed_games(user_id, limit=limit, include_full_review=True)
        else:
            # Get all games
            games = supabase_client.get_active_reviewed_games(user_id, limit=1000, include_full_review=True)
        
        if not games:
            print(f"   ⚠️ No games found for user {user_id}")
            return 0
        
        print(f"   📚 Found {len(games)} games with reviews")
        
        # Use ProfileAnalyticsEngine to extract positions
        engine = ProfileAnalyticsEngine(supabase_client)
        
        total_saved = 0
        games_with_positions = 0
        
        for idx, game in enumerate(games, 1):
            try:
                review = game.get("game_review") or {}
                if not isinstance(review, dict):
                    continue
                
                plys = review.get("ply_records", [])
                if not isinstance(plys, list) or len(plys) == 0:
                    continue
                
                # Extract positions from this game
                # We'll use the _extract_critical_positions method
                # But we need to pass it as a list of games
                positions = engine._extract_critical_positions(
                    [game], 
                    limit=100,  # Extract all positions from this game
                    save_to_db=True
                )
                
                if positions:
                    games_with_positions += 1
                    # The method already saves to DB, so we just count
                    # But we need to check how many were actually saved
                    # The method returns top_positions (limited list), but saves all
                    # So we count the ply_records that match criteria
                    mistake_blunder_count = sum(
                        1 for ply in plys 
                        if isinstance(ply, dict) 
                        and ply.get("category") in ("mistake", "blunder")
                        and float(ply.get("cp_loss", 0) or 0) >= 100
                    )
                    total_saved += mistake_blunder_count
                    
                    if idx % 10 == 0:
                        print(f"   📊 Processed {idx}/{len(games)} games, {games_with_positions} with positions, ~{total_saved} positions saved")
                
            except Exception as e:
                print(f"   ⚠️ Error processing game {idx}: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        print(f"   ✅ Processed {len(games)} games")
        print(f"   ✅ {games_with_positions} games had critical positions")
        print(f"   ✅ ~{total_saved} positions extracted and saved")
        
        return total_saved
        
    except Exception as e:
        print(f"   ❌ Error processing user {user_id}: {e}")
        import traceback
        traceback.print_exc()
        return 0


def main():
    """Backfill critical positions for all users or a specific user."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Backfill critical positions from existing analyzed games")
    parser.add_argument("--user-id", type=str, help="Specific user ID to backfill (optional)")
    parser.add_argument("--limit", type=int, help="Limit number of games per user (optional)")
    args = parser.parse_args()
    
    # Initialize client
    supabase_client = get_supabase_client()
    if not supabase_client:
        print("❌ Failed to initialize database client")
        return
    
    print("✅ Connected to database")
    
    if args.user_id:
        # Backfill specific user
        backfill_user_positions(args.user_id, supabase_client, args.limit)
    else:
        # Backfill all users
        print("🔍 Finding all users with analyzed games...")
        try:
            # Get all users who have games with reviews
            if hasattr(supabase_client, 'client'):  # Supabase
                result = supabase_client.client.table("games")\
                    .select("user_id")\
                    .not_.is_("game_review", "null")\
                    .execute()
                user_ids = list(set([g.get("user_id") for g in (result.data or []) if g.get("user_id")]))
            else:  # LocalPostgres
                result = supabase_client._execute_query(
                    "SELECT DISTINCT user_id FROM public.games WHERE game_review IS NOT NULL",
                    ()
                )
                user_ids = [row["user_id"] for row in result if row.get("user_id")]
            
            print(f"📊 Found {len(user_ids)} users with analyzed games")
            
            total_saved = 0
            for i, user_id in enumerate(user_ids, 1):
                print(f"\n[{i}/{len(user_ids)}] Processing user {user_id[:8]}...")
                saved = backfill_user_positions(user_id, supabase_client, args.limit)
                total_saved += saved
            
            print(f"\n✅ Backfill complete: ~{total_saved} positions saved across {len(user_ids)} users")
        except Exception as e:
            print(f"❌ Error finding users: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()

