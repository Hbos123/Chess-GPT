#!/usr/bin/env python3
"""
Reset account - clear all games, stats, positions, and habit_trends for a user.
Usage: python reset_account.py [--force] [user_id]
"""

import os
import sys
import argparse
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from supabase import create_client

def main():
    parser = argparse.ArgumentParser(description="Reset account - clear all data for a user")
    parser.add_argument("user_id", nargs="?", help="User ID to reset (optional, will auto-detect if not provided)")
    parser.add_argument("--force", action="store_true", help="Skip confirmation prompt")
    args = parser.parse_args()
    
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
    print("🔄 ACCOUNT RESET")
    print("=" * 80)
    
    # Get user_id
    user_id = args.user_id
    if not user_id:
        # Get all user_ids from games table
        print("\n🔍 Finding users...")
        try:
            games_result = client.table("games").select("user_id").execute()
            user_ids = set()
            if games_result.data:
                for game in games_result.data:
                    user_ids.add(game.get("user_id"))
            
            if not user_ids:
                print("❌ No users found in games table")
                sys.exit(1)
            
            print(f"Found {len(user_ids)} unique user(s):")
            for i, uid in enumerate(user_ids, 1):
                print(f"  {i}. {uid}")
            
            # If only one user, use it; otherwise ask
            if len(user_ids) == 1:
                user_id = list(user_ids)[0]
                print(f"\n✅ Using single user: {user_id}")
            else:
                print("\n⚠️  Multiple users found. Please specify user_id as argument:")
                print(f"   python reset_account.py <user_id>")
                sys.exit(1)
            
        except Exception as e:
            print(f"❌ Error finding users: {e}")
            sys.exit(1)
    
    # Confirm deletion (unless --force)
    print(f"\n⚠️  WARNING: This will DELETE ALL data for user {user_id}:")
    print("   - All games")
    print("   - All personal stats")
    print("   - All positions")
    print("   - All habit_trends")
    
    if not args.force:
        response = input("\nType 'RESET' to confirm: ")
        if response != "RESET":
            print("❌ Cancelled")
            sys.exit(0)
    else:
        print("\n✅ --force flag set, proceeding without confirmation...")
    
    # Clear all data
    print(f"\n🗑️  Clearing all data for user {user_id}...")
    
    counts = {
        "games": 0,
        "personal_stats": 0,
        "positions": 0,
        "habit_trends": 0
    }
    
    # Clear games
    try:
        games_result = client.table("games").select("id").eq("user_id", user_id).execute()
        if games_result.data:
            counts["games"] = len(games_result.data)
            client.table("games").delete().eq("user_id", user_id).execute()
            print(f"   ✅ Deleted {counts['games']} games")
    except Exception as e:
        print(f"   ⚠️  Error deleting games: {e}")
    
    # Clear personal_stats
    try:
        stats_result = client.table("personal_stats").select("id").eq("user_id", user_id).execute()
        if stats_result.data:
            counts["personal_stats"] = len(stats_result.data)
            client.table("personal_stats").delete().eq("user_id", user_id).execute()
            print(f"   ✅ Deleted {counts['personal_stats']} personal_stats records")
    except Exception as e:
        print(f"   ⚠️  Error deleting personal_stats: {e}")
    
    # Clear positions
    try:
        positions_result = client.table("positions").select("id").eq("user_id", user_id).execute()
        if positions_result.data:
            counts["positions"] = len(positions_result.data)
            client.table("positions").delete().eq("user_id", user_id).execute()
            print(f"   ✅ Deleted {counts['positions']} positions")
    except Exception as e:
        print(f"   ⚠️  Error deleting positions: {e}")
    
    # Clear habit_trends
    try:
        trends_result = client.table("habit_trends").select("id").eq("user_id", user_id).execute()
        if trends_result.data:
            counts["habit_trends"] = len(trends_result.data)
            client.table("habit_trends").delete().eq("user_id", user_id).execute()
            print(f"   ✅ Deleted {counts['habit_trends']} habit_trends records")
    except Exception as e:
        print(f"   ⚠️  Error deleting habit_trends: {e}")
    
    print("\n" + "=" * 80)
    print("✅ ACCOUNT RESET COMPLETE")
    print("=" * 80)
    print(f"\nSummary:")
    print(f"  Games deleted: {counts['games']}")
    print(f"  Personal stats deleted: {counts['personal_stats']}")
    print(f"  Positions deleted: {counts['positions']}")
    print(f"  Habit trends deleted: {counts['habit_trends']}")
    print(f"\n🎮 Your account is now reset. Games will be re-analyzed when you fetch them again.")

if __name__ == "__main__":
    main()

