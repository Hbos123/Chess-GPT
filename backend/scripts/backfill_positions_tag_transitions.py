#!/usr/bin/env python3
"""
Backfill script to extract tag transitions from existing game_review.ply_records
for positions already in the database.

This script:
1. Fetches all positions from the database
2. For each position, finds the corresponding game and ply_record
3. Extracts tag transitions, piece info, and time data
4. Updates the position with the new metadata
"""

import sys
import os
import subprocess
from pathlib import Path
import chess

# Add parent directory to path
script_dir = Path(__file__).parent
backend_dir = script_dir.parent
project_root = backend_dir.parent
sys.path.insert(0, str(backend_dir))

from supabase_client import SupabaseClient
from dotenv import load_dotenv

# Piece labels mapping
PIECE_LABELS = {
    chess.PAWN: "pawn",
    chess.KNIGHT: "knight",
    chess.BISHOP: "bishop",
    chess.ROOK: "rook",
    chess.QUEEN: "queen",
    chess.KING: "king",
}

def extract_tag_names(tags):
    """Extract tag names from tag objects or strings."""
    names = []
    if not tags:
        return names
    for tag in tags:
        if isinstance(tag, str):
            names.append(tag)
        elif isinstance(tag, dict):
            name = tag.get("name", tag.get("tag", tag.get("tag_name", "")))
            if name:
                names.append(name)
    return names

def piece_name_from_move(fen_before, move_uci):
    """Extract piece name from move UCI notation."""
    if not fen_before or not move_uci:
        return None
    try:
        board = chess.Board(fen_before)
        move = chess.Move.from_uci(move_uci)
        piece = board.piece_at(move.from_square)
        if not piece:
            return None
        return PIECE_LABELS.get(piece.piece_type)
    except Exception:
        return None

def piece_name_from_san(fen_before, move_san):
    """Extract piece name from move SAN notation."""
    if not fen_before or not move_san:
        return None
    try:
        board = chess.Board(fen_before)
        move = board.parse_san(move_san)
        piece = board.piece_at(move.from_square)
        if not piece:
            return None
        return PIECE_LABELS.get(piece.piece_type)
    except Exception:
        return None

def backfill_position(supabase: SupabaseClient, position: dict):
    """Backfill a single position with tag transition data."""
    position_id = position.get("id")
    user_id = position.get("user_id")
    from_game_id = position.get("from_game_id")
    source_ply = position.get("source_ply")
    fen = position.get("fen")
    
    if not from_game_id or source_ply is None:
        print(f"   ⚠️ Position {position_id}: Missing from_game_id or source_ply")
        return False
    
    try:
        # Fetch the game
        game_result = supabase.client.table("games")\
            .select("id, game_review, user_id")\
            .eq("id", from_game_id)\
            .eq("user_id", user_id)\
            .maybe_single()\
            .execute()
        
        if not game_result.data:
            print(f"   ⚠️ Position {position_id}: Game {from_game_id} not found")
            return False
        
        game = game_result.data
        game_review = game.get("game_review", {})
        
        if not isinstance(game_review, dict):
            print(f"   ⚠️ Position {position_id}: Invalid game_review format")
            return False
        
        ply_records = game_review.get("ply_records", [])
        if not isinstance(ply_records, list):
            print(f"   ⚠️ Position {position_id}: Invalid ply_records format")
            return False
        
        # Find the matching ply_record
        matching_ply = None
        for ply in ply_records:
            if isinstance(ply, dict) and ply.get("ply") == source_ply:
                matching_ply = ply
                break
        
        if not matching_ply:
            print(f"   ⚠️ Position {position_id}: Ply {source_ply} not found in game")
            return False
        
        # Extract tag transition data
        raw_before = matching_ply.get("raw_before", {})
        raw_after = matching_ply.get("raw_after", {})
        analyse = matching_ply.get("analyse", {})
        best_move_tags = matching_ply.get("best_move_tags", [])
        
        tags_start = extract_tag_names(
            raw_before.get("tags", []) if isinstance(raw_before, dict) else []
        )
        tags_after_played = extract_tag_names(
            raw_after.get("tags", []) if isinstance(raw_after, dict) else analyse.get("tags", [])
        )
        tags_after_best = extract_tag_names(best_move_tags)
        
        # Compute tag transitions
        tags_start_set = set(tags_start)
        tags_after_played_set = set(tags_after_played)
        
        tags_gained = list(tags_after_played_set - tags_start_set)
        tags_lost = list(tags_start_set - tags_after_played_set)
        
        # Extract piece information
        move_uci = matching_ply.get("uci")
        best_move_san = matching_ply.get("engine", {}).get("best_move_san") if isinstance(matching_ply.get("engine"), dict) else None
        
        piece_blundered = piece_name_from_move(fen, move_uci)
        piece_best_move = piece_name_from_san(fen, best_move_san) if best_move_san else None
        
        # Extract time data
        time_spent_s = matching_ply.get("time_spent_s")
        
        # Update position
        update_data = {
            "tags_start": tags_start,
            "tags_after_played": tags_after_played,
            "tags_after_best": tags_after_best,
            "tags_gained": tags_gained,
            "tags_lost": tags_lost,
        }
        
        if piece_blundered:
            update_data["piece_blundered"] = piece_blundered
        if piece_best_move:
            update_data["piece_best_move"] = piece_best_move
        if time_spent_s is not None:
            update_data["time_spent_s"] = time_spent_s
        
        supabase.client.table("positions")\
            .update(update_data)\
            .eq("id", position_id)\
            .execute()
        
        return True
        
    except Exception as e:
        print(f"   ❌ Position {position_id}: Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def backfill_user(supabase: SupabaseClient, user_id: str):
    """Backfill all positions for a user."""
    print(f"\n🔄 Processing user: {user_id}")
    
    try:
        # Fetch all positions for this user that need backfilling
        # (positions with from_game_id but missing tag transition data)
        result = supabase.client.table("positions")\
            .select("id, user_id, from_game_id, source_ply, fen, move_uci, best_move_san")\
            .eq("user_id", user_id)\
            .not_.is_("from_game_id", "null")\
            .not_.is_("source_ply", "null")\
            .execute()
        
        positions = result.data or []
        
        if not positions:
            print(f"   ℹ️ No positions found for user {user_id}")
            return 0, 0
        
        print(f"   📚 Found {len(positions)} positions to backfill")
        
        success_count = 0
        fail_count = 0
        
        for i, position in enumerate(positions, 1):
            if i % 10 == 0:
                print(f"   Progress: {i}/{len(positions)}")
            
            if backfill_position(supabase, position):
                success_count += 1
            else:
                fail_count += 1
        
        print(f"   ✅ Backfill complete: {success_count} succeeded, {fail_count} failed")
        return success_count, fail_count
        
    except Exception as e:
        print(f"   ❌ Error processing user {user_id}: {e}")
        import traceback
        traceback.print_exc()
        return 0, 0

def main():
    """Backfill tag transitions for all users or a specific user."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Backfill tag transitions for existing positions")
    parser.add_argument("--user-id", type=str, help="Specific user ID to backfill (optional)")
    args = parser.parse_args()
    
    # Load environment variables
    # Try backend/.env first, then project root .env
    env_file = backend_dir / ".env"
    if not env_file.exists():
        env_file = project_root / ".env"
    
    if env_file.exists():
        load_dotenv(env_file)
        print(f"📄 Loaded environment from: {env_file}")
    else:
        print(f"⚠️ No .env file found at {backend_dir / '.env'} or {project_root / '.env'}")
    
    # Initialize Supabase client
    try:
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
        backfill_user(supabase, args.user_id)
    else:
        # Backfill all users
        print("🔍 Finding all users with positions...")
        try:
            # Get all users who have positions
            result = supabase.client.table("positions")\
                .select("user_id")\
                .not_.is_("from_game_id", "null")\
                .execute()
            
            user_ids = list(set([p.get("user_id") for p in (result.data or []) if p.get("user_id")]))
            print(f"📊 Found {len(user_ids)} users with positions")
            
            total_success = 0
            total_fail = 0
            
            for i, user_id in enumerate(user_ids, 1):
                print(f"\n[{i}/{len(user_ids)}] Processing user {user_id[:8]}...")
                success, fail = backfill_user(supabase, user_id)
                total_success += success
                total_fail += fail
            
            print(f"\n✅ Backfill complete: {total_success} succeeded, {total_fail} failed across {len(user_ids)} users")
        except Exception as e:
            print(f"❌ Error finding users: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    main()

