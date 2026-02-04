#!/usr/bin/env python3
"""
Generate sample detailed analytics data for testing/development.
This populates the detailed_analytics_cache table with realistic sample data
so you don't have to wait for real games to be analyzed.
"""

import sys
import os
from pathlib import Path
import random
from datetime import datetime

# Add parent directory to path
backend_dir = Path(__file__).parent.parent
project_root = backend_dir.parent
sys.path.insert(0, str(backend_dir))

# Try to load from .env if available
try:
    from dotenv import load_dotenv
    env_file = backend_dir / ".env"
    if env_file.exists():
        load_dotenv(env_file)
    else:
        root_env = project_root / ".env"
        if root_env.exists():
            load_dotenv(root_env)
        else:
            load_dotenv()
except ImportError:
    pass

from supabase_client import SupabaseClient


def generate_sample_analytics(user_id: str, games_count: int = 40) -> dict:
    """Generate realistic sample detailed analytics data."""
    
    # Phase Analytics
    phase_analytics = {
        "opening": {
            "accuracy": round(random.uniform(75, 90), 1),
            "games_won": random.randint(8, 15),
            "games_lost": random.randint(3, 8),
            "games_drawn": random.randint(1, 4)
        },
        "middlegame": {
            "accuracy": round(random.uniform(70, 85), 1),
            "games_won": random.randint(10, 18),
            "games_lost": random.randint(5, 12),
            "games_drawn": random.randint(1, 5)
        },
        "endgame": {
            "accuracy": round(random.uniform(75, 88), 1),
            "games_won": random.randint(12, 20),
            "games_lost": random.randint(4, 10),
            "games_drawn": random.randint(1, 3)
        }
    }
    
    # Opening Detailed
    opening_names = [
        "Sicilian Defense",
        "Queen's Gambit",
        "King's Indian Defense",
        "French Defense",
        "Caro-Kann Defense",
        "Italian Game",
        "Ruy Lopez",
        "Nimzo-Indian Defense",
        "English Opening",
        "Pirc Defense"
    ]
    
    opening_detailed = {}
    selected_openings = random.sample(opening_names, random.randint(4, 7))
    total_freq = 0
    for opening in selected_openings:
        freq = random.randint(2, 8)
        wins = random.randint(1, freq - 1)
        losses = random.randint(0, freq - wins)
        draws = freq - wins - losses
        opening_detailed[opening] = {
            "frequency": freq,
            "avg_accuracy": round(random.uniform(72, 88), 1),
            "win_rate": round(wins / freq, 3) if freq > 0 else 0,
            "wins": wins,
            "losses": losses,
            "draws": draws
        }
        total_freq += freq
    
    # Piece Accuracy
    pieces = ["Pawn", "Knight", "Bishop", "Rook", "Queen", "King"]
    piece_aggregate = {}
    for piece in pieces:
        piece_aggregate[piece] = {
            "accuracy": round(random.uniform(75, 90), 1),
            "count": random.randint(20, 150)
        }
    
    # Make sure best/worst pieces are distinct
    sorted_pieces = sorted(piece_aggregate.items(), key=lambda x: x[1]["accuracy"])
    piece_aggregate[sorted_pieces[0][0]]["accuracy"] = round(random.uniform(82, 92), 1)  # Best
    piece_aggregate[sorted_pieces[-1][0]]["accuracy"] = round(random.uniform(70, 78), 1)  # Worst
    
    piece_accuracy_detailed = {
        "aggregate": piece_aggregate,
        "per_game": []  # Can be empty for sample data
    }
    
    # Tag Transitions
    tag_names = [
        "tag.center.control.near",
        "tag.center.control.core",
        "tag.key.e4",
        "tag.key.e5",
        "tag.space.advantage",
        "tag.piece.trapped",
        "tag.piece.overworked",
        "tag.diagonal.open.d1-a4",
        "tag.diagonal.open.d5-b7",
        "tag.undeveloped.queen",
        "tag.bishop.bad",
        "tag.knight.outpost"
    ]
    
    tag_transitions = {
        "gained": {},
        "lost": {}
    }
    
    # Generate gained tags
    gained_tags = random.sample(tag_names, random.randint(5, 8))
    for tag in gained_tags:
        count = random.randint(8, 25)
        tag_transitions["gained"][tag] = {
            "count": count,
            "accuracy": round(random.uniform(85, 98), 1),
            "blunders": random.randint(0, max(1, count // 10)),
            "mistakes": random.randint(0, max(1, count // 8)),
            "inaccuracies": random.randint(0, max(1, count // 6)),
            "error_rate": round(random.uniform(0, 0.15), 3)
        }
    
    # Generate lost tags
    lost_tags = random.sample([t for t in tag_names if t not in gained_tags], random.randint(4, 7))
    for tag in lost_tags:
        count = random.randint(6, 20)
        tag_transitions["lost"][tag] = {
            "count": count,
            "accuracy": round(random.uniform(80, 95), 1),
            "blunders": random.randint(0, max(1, count // 8)),
            "mistakes": random.randint(0, max(1, count // 6)),
            "inaccuracies": random.randint(0, max(1, count // 5)),
            "error_rate": round(random.uniform(0, 0.20), 3)
        }
    
    # Static Tags
    static_tags = {}
    static_tag_names = random.sample(tag_names, random.randint(6, 10))
    for tag in static_tag_names:
        count = random.randint(10, 35)
        static_tags[tag] = {
            "count": count,
            "accuracy": round(random.uniform(82, 96), 1),
            "blunders": random.randint(0, max(1, count // 12)),
            "mistakes": random.randint(0, max(1, count // 10)),
            "inaccuracies": random.randint(0, max(1, count // 8)),
            "error_rate": round(random.uniform(0, 0.12), 3)
        }
    
    # Time Buckets
    time_buckets = {
        "<5s": {
            "accuracy": round(random.uniform(65, 75), 1),
            "count": random.randint(15, 40),
            "blunders": random.randint(2, 8),
            "mistakes": random.randint(3, 10),
            "inaccuracies": random.randint(4, 12),
            "blunder_rate": round(random.uniform(0.10, 0.25), 3),
            "mistake_rate": round(random.uniform(0.15, 0.30), 3),
            "inaccuracy_rate": round(random.uniform(0.20, 0.35), 3)
        },
        "5-15s": {
            "accuracy": round(random.uniform(72, 82), 1),
            "count": random.randint(30, 60),
            "blunders": random.randint(2, 6),
            "mistakes": random.randint(4, 10),
            "inaccuracies": random.randint(5, 15),
            "blunder_rate": round(random.uniform(0.05, 0.15), 3),
            "mistake_rate": round(random.uniform(0.10, 0.20), 3),
            "inaccuracy_rate": round(random.uniform(0.15, 0.25), 3)
        },
        "15-30s": {
            "accuracy": round(random.uniform(78, 88), 1),
            "count": random.randint(40, 80),
            "blunders": random.randint(1, 5),
            "mistakes": random.randint(3, 8),
            "inaccuracies": random.randint(4, 12),
            "blunder_rate": round(random.uniform(0.03, 0.10), 3),
            "mistake_rate": round(random.uniform(0.05, 0.15), 3),
            "inaccuracy_rate": round(random.uniform(0.08, 0.18), 3)
        },
        "30s-1min": {
            "accuracy": round(random.uniform(80, 90), 1),
            "count": random.randint(35, 70),
            "blunders": random.randint(1, 4),
            "mistakes": random.randint(2, 6),
            "inaccuracies": random.randint(3, 10),
            "blunder_rate": round(random.uniform(0.02, 0.08), 3),
            "mistake_rate": round(random.uniform(0.04, 0.12), 3),
            "inaccuracy_rate": round(random.uniform(0.06, 0.15), 3)
        },
        "1min-2min30": {
            "accuracy": round(random.uniform(82, 92), 1),
            "count": random.randint(25, 55),
            "blunders": random.randint(0, 3),
            "mistakes": random.randint(1, 5),
            "inaccuracies": random.randint(2, 8),
            "blunder_rate": round(random.uniform(0.01, 0.06), 3),
            "mistake_rate": round(random.uniform(0.03, 0.10), 3),
            "inaccuracy_rate": round(random.uniform(0.05, 0.12), 3)
        },
        "2min30-5min": {
            "accuracy": round(random.uniform(84, 94), 1),
            "count": random.randint(15, 40),
            "blunders": random.randint(0, 2),
            "mistakes": random.randint(0, 4),
            "inaccuracies": random.randint(1, 6),
            "blunder_rate": round(random.uniform(0.00, 0.05), 3),
            "mistake_rate": round(random.uniform(0.02, 0.08), 3),
            "inaccuracy_rate": round(random.uniform(0.03, 0.10), 3)
        },
        "5min+": {
            "accuracy": round(random.uniform(86, 96), 1),
            "count": random.randint(10, 30),
            "blunders": random.randint(0, 1),
            "mistakes": random.randint(0, 2),
            "inaccuracies": random.randint(0, 4),
            "blunder_rate": round(random.uniform(0.00, 0.03), 3),
            "mistake_rate": round(random.uniform(0.00, 0.05), 3),
            "inaccuracy_rate": round(random.uniform(0.02, 0.08), 3)
        }
    }
    
    # Build final analytics structure
    analytics_data = {
        "phase_analytics": phase_analytics,
        "opening_detailed": opening_detailed,
        "piece_accuracy_detailed": piece_accuracy_detailed,
        "tag_transitions": tag_transitions,
        "static_tags": static_tags,
        "time_buckets": time_buckets
    }
    
    return analytics_data


def main():
    """Generate and save sample analytics data."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Generate sample detailed analytics data for testing"
    )
    parser.add_argument(
        "--user-id",
        type=str,
        required=True,
        help="User ID to generate sample data for"
    )
    parser.add_argument(
        "--games-count",
        type=int,
        default=40,
        help="Number of games to simulate (default: 40)"
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing cache if it exists"
    )
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
        print(f"✅ Connected to Supabase: {supabase_url}")
    except Exception as e:
        print(f"❌ Failed to initialize Supabase client: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Check if cache already exists
    if not args.overwrite:
        try:
            existing = supabase.client.table("detailed_analytics_cache")\
                .select("id")\
                .eq("user_id", args.user_id)\
                .maybe_single()\
                .execute()
            
            if existing.data:
                print(f"⚠️  Cache already exists for user {args.user_id}")
                print("   Use --overwrite to replace it")
                return
        except Exception as e:
            # Table might not exist, continue anyway
            pass
    
    # Generate sample data
    print(f"\n🎲 Generating sample analytics data for user: {args.user_id}")
    print(f"   Simulating {args.games_count} games...")
    
    analytics_data = generate_sample_analytics(args.user_id, args.games_count)
    
    # Save to cache
    print(f"\n💾 Saving sample analytics to cache...")
    if supabase._save_detailed_analytics_cache(args.user_id, analytics_data, args.games_count):
        print(f"✅ Successfully saved sample analytics cache!")
        print(f"\n📊 Sample data includes:")
        print(f"   - Phase analytics: {len(analytics_data['phase_analytics'])} phases")
        print(f"   - Opening detailed: {len(analytics_data['opening_detailed'])} openings")
        print(f"   - Piece accuracy: {len(analytics_data['piece_accuracy_detailed']['aggregate'])} pieces")
        print(f"   - Tag transitions gained: {len(analytics_data['tag_transitions']['gained'])} tags")
        print(f"   - Tag transitions lost: {len(analytics_data['tag_transitions']['lost'])} tags")
        print(f"   - Static tags: {len(analytics_data['static_tags'])} tags")
        print(f"   - Time buckets: {len(analytics_data['time_buckets'])} buckets")
        print(f"\n🎉 You can now view the analytics in the Profile Dashboard!")
    else:
        print(f"❌ Failed to save sample analytics cache")


if __name__ == "__main__":
    main()
