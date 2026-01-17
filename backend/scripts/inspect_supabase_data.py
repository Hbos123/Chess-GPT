#!/usr/bin/env python3
"""
Quick script to inspect all Supabase data for debugging habits issue.
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from supabase import create_client

def main():
    # Load .env file from project root
    project_root = Path(__file__).parent.parent.parent
    env_path = project_root / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    else:
        load_dotenv()  # Try current directory
    
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if not supabase_url or not supabase_key:
        print("❌ Error: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
        sys.exit(1)
    
    client = create_client(supabase_url, supabase_key)
    
    print("=" * 80)
    print("📊 SUPABASE DATA INSPECTION")
    print("=" * 80)
    
    # Get all games
    print("\n🎮 GAMES TABLE:")
    print("-" * 80)
    try:
        games_result = client.table("games").select("*").limit(100).execute()
        games = games_result.data if games_result.data else []
        
        print(f"Total games found: {len(games)}")
        
        if games:
            # Count by review_type
            review_type_counts = {}
            archived_count = 0
            analyzed_count = 0
            has_review_count = 0
            has_ply_records_count = 0
            
            for game in games:
                review_type = game.get("review_type") or "NULL"
                review_type_counts[review_type] = review_type_counts.get(review_type, 0) + 1
                
                if game.get("archived_at"):
                    archived_count += 1
                if game.get("analyzed_at"):
                    analyzed_count += 1
                
                game_review = game.get("game_review")
                if game_review:
                    has_review_count += 1
                    if isinstance(game_review, dict) and game_review.get("ply_records"):
                        has_ply_records_count += 1
            
            print(f"\nBy review_type: {review_type_counts}")
            print(f"Archived: {archived_count}, Not archived: {len(games) - archived_count}")
            print(f"Analyzed: {analyzed_count}, Not analyzed: {len(games) - analyzed_count}")
            print(f"With game_review: {has_review_count}")
            print(f"With ply_records: {has_ply_records_count}")
            
            print(f"\n📋 Sample games (first 10):")
            for i, game in enumerate(games[:10], 1):
                game_id = game.get("id", "")[:8]
                user_id = game.get("user_id", "")[:8]
                review_type = game.get("review_type") or "NULL"
                analyzed = bool(game.get("analyzed_at"))
                archived = bool(game.get("archived_at"))
                has_review = bool(game.get("game_review"))
                game_review = game.get("game_review", {})
                has_ply = isinstance(game_review, dict) and bool(game_review.get("ply_records"))
                
                print(f"  {i}. ID: {game_id}..., user: {user_id}..., "
                      f"review_type: {review_type}, analyzed: {analyzed}, "
                      f"archived: {archived}, has_review: {has_review}, has_ply_records: {has_ply}")
        else:
            print("No games found!")
            
    except Exception as e:
        print(f"❌ Error fetching games: {e}")
        import traceback
        traceback.print_exc()
    
    # Get personal_stats
    print("\n📊 PERSONAL_STATS TABLE:")
    print("-" * 80)
    try:
        stats_result = client.table("personal_stats").select("*").execute()
        stats = stats_result.data if stats_result.data else []
        print(f"Total personal_stats rows: {len(stats)}")
        
        for stat in stats:
            user_id = stat.get("user_id", "")[:8]
            needs_recalc = stat.get("needs_recalc", False)
            has_stats = bool(stat.get("stats"))
            updated = stat.get("updated_at", "")
            print(f"  User: {user_id}..., needs_recalc: {needs_recalc}, "
                  f"has_stats: {has_stats}, updated: {str(updated)[:19] if updated else 'None'}")
    except Exception as e:
        print(f"❌ Error fetching personal_stats: {e}")
    
    # Get habit_trends
    print("\n📈 HABIT_TRENDS TABLE:")
    print("-" * 80)
    try:
        trends_result = client.table("habit_trends").select("*").limit(50).execute()
        trends = trends_result.data if trends_result.data else []
        print(f"Total habit_trends rows: {len(trends)}")
        
        if trends:
            # Group by habit_key
            by_habit = {}
            for trend in trends:
                key = trend.get("habit_key", "unknown")
                by_habit[key] = by_habit.get(key, 0) + 1
            
            print(f"By habit_key: {dict(list(by_habit.items())[:10])}")
    except Exception as e:
        print(f"❌ Error fetching habit_trends: {e}")
    
    # Test the query that habits uses
    print("\n🔍 TESTING get_active_reviewed_games QUERY:")
    print("-" * 80)
    try:
        # Get user_id from first game
        if games:
            user_id = games[0].get("user_id")
            if user_id:
                print(f"Testing with user_id: {user_id[:8]}...")
                
                # Try the OR query
                try:
                    result = client.table("games")\
                        .select("*")\
                        .eq("user_id", user_id)\
                        .is_("archived_at", "null")\
                        .or_("review_type.eq.full,review_type.is.null")\
                        .order("updated_at", desc=True)\
                        .limit(30)\
                        .execute()
                    
                    active_games = result.data if result.data else []
                    print(f"  ✅ OR query returned: {len(active_games)} games")
                except Exception as or_e:
                    print(f"  ❌ OR query failed: {or_e}")
                    
                    # Try fallback
                    result = client.table("games")\
                        .select("*")\
                        .eq("user_id", user_id)\
                        .is_("archived_at", "null")\
                        .order("updated_at", desc=True)\
                        .limit(30)\
                        .execute()
                    
                    all_games = result.data if result.data else []
                    filtered = [g for g in all_games if g.get("review_type") in ("full", None)]
                    print(f"  ✅ Fallback query returned: {len(filtered)} games (filtered from {len(all_games)})")
        else:
            print("No games to test with")
    except Exception as e:
        print(f"❌ Error testing query: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 80)
    print("✅ Inspection complete")
    print("=" * 80)

if __name__ == "__main__":
    main()

