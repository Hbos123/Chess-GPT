"""
Game Window Manager
Maintains a rolling window of 60 fully analyzed games per user.
Older games are "semi-forgotten" - full details removed but pattern data preserved.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.personal_review_utils import extract_tags


class GameWindowManager:
    """Manages rolling window of analyzed games with pattern retention"""
    
    MAX_ACTIVE_GAMES = 60
    
    def __init__(self, supabase_client):
        self.supabase = supabase_client
        print(f"✅ GameWindowManager initialized (max_active_games={self.MAX_ACTIVE_GAMES})")
    
    def count_active_games(self, user_id: str) -> int:
        """Count active (non-compressed) analyzed games for a user"""
        try:
            result = self.supabase.client.table("games")\
                .select("id", count="exact")\
                .eq("user_id", user_id)\
                .not_.is_("analyzed_at", "null")\
                .is_("compressed_at", "null")\
                .execute()
            
            return result.count if hasattr(result, 'count') else len(result.data) if result.data else 0
        except Exception as e:
            print(f"⚠️ Error counting active games: {e}")
            return 0
    
    def get_oldest_active_game(self, user_id: str) -> Optional[Dict]:
        """Get the oldest active (non-compressed) analyzed game"""
        try:
            result = self.supabase.client.table("games")\
                .select("*")\
                .eq("user_id", user_id)\
                .not_.is_("analyzed_at", "null")\
                .is_("compressed_at", "null")\
                .order("analyzed_at", desc=False)\
                .limit(1)\
                .execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0]
            return None
        except Exception as e:
            print(f"⚠️ Error getting oldest active game: {e}")
            return None
    
    def extract_pattern_summary(self, game: Dict) -> Dict[str, Any]:
        """Extract pattern-relevant data from full game_review"""
        review = game.get("game_review", {})
        
        # Handle both dict and string formats
        if isinstance(review, str):
            import json
            try:
                review = json.loads(review)
            except:
                review = {}
        
        ply_records = review.get("ply_records", []) if isinstance(review, dict) else []
        
        # Aggregate tags from all ply records
        all_tags = []
        tag_frequencies = {}
        for ply in ply_records:
            if not isinstance(ply, dict):
                continue
            tags = extract_tags(ply)
            all_tags.extend(tags)
            for tag in tags:
                tag_frequencies[tag] = tag_frequencies.get(tag, 0) + 1
        
        # Calculate phase accuracies
        phase_accuracies = {}
        for phase in ["opening", "middlegame", "endgame"]:
            phase_plys = [p for p in ply_records if isinstance(p, dict) and p.get("phase") == phase]
            if phase_plys:
                accuracies = [p.get("accuracy_pct", 0) for p in phase_plys if isinstance(p.get("accuracy_pct"), (int, float))]
                if accuracies:
                    phase_accuracies[phase] = sum(accuracies) / len(accuracies)
        
        # Extract metadata
        metadata = review.get("metadata", {}) if isinstance(review, dict) else {}
        
        return {
            "tags": list(set(all_tags)),  # Unique tags
            "tag_frequencies": tag_frequencies,
            "phase_accuracy": phase_accuracies,
            "opening_eco": game.get("opening_eco"),
            "opening_name": game.get("opening_name"),
            "time_control": game.get("time_control"),
            "time_category": game.get("time_category"),
            "result": game.get("result"),
            "accuracy_overall": game.get("accuracy_overall"),
            "accuracy_opening": game.get("accuracy_opening"),
            "accuracy_middlegame": game.get("accuracy_middlegame"),
            "accuracy_endgame": game.get("accuracy_endgame"),
            "blunders": game.get("blunders", 0),
            "mistakes": game.get("mistakes", 0),
            "inaccuracies": game.get("inaccuracies", 0),
            "avg_cp_loss": game.get("avg_cp_loss"),
            "game_character": game.get("game_character"),
            "endgame_type": game.get("endgame_type"),
            "user_rating": game.get("user_rating"),
            "opponent_rating": game.get("opponent_rating"),
            "opponent_name": game.get("opponent_name"),
            "game_date": game.get("game_date"),
            "user_color": game.get("user_color"),
            "platform": game.get("platform"),
            "external_id": game.get("external_id"),
            "total_moves": game.get("total_moves", 0),
            "theory_exit_ply": game.get("theory_exit_ply"),
            "termination": game.get("termination")
        }
    
    async def compress_oldest_game(self, user_id: str) -> Optional[str]:
        """Semi-forget oldest game: remove full details, keep pattern data"""
        oldest = self.get_oldest_active_game(user_id)
        if not oldest:
            print(f"   ⚠️ No oldest game found to compress for user {user_id}")
            return None
        
        game_id = oldest["id"]
        
        try:
            # Delete linked positions before compression
            # (CASCADE delete will handle this, but explicit for clarity and logging)
            try:
                delete_result = self.supabase.client.table("positions")\
                    .delete()\
                    .eq("from_game_id", game_id)\
                    .execute()
                deleted_count = len(delete_result.data) if delete_result.data else 0
                
                if deleted_count > 0:
                    print(f"   🗑️  Deleted {deleted_count} position(s) linked to game {game_id}")
            except Exception as e:
                print(f"   ⚠️  Error deleting positions: {e}")
            
            # Extract pattern data from game_review
            pattern_summary = self.extract_pattern_summary(oldest)
            
            # Update game: remove full details, keep pattern_summary
            from datetime import datetime as dt
            updates = {
                "game_review": None,  # Remove full review
                "pgn": None,  # Remove PGN
                "eval_trace": None,  # Remove eval trace
                "time_trace": None,  # Remove time trace
                "key_points": None,  # Remove key points
                "pattern_summary": pattern_summary if pattern_summary else None,  # Keep pattern data
                "compressed_at": dt.utcnow().isoformat() + "Z"
            }
            
            result = self.supabase.client.table("games")\
                .update(updates)\
                .eq("id", game_id)\
                .execute()
            
            if result.data:
                print(f"   ✅ Compressed game {game_id}")
                return game_id
            else:
                print(f"   ⚠️  Failed to compress game {game_id}")
                return None
        except Exception as e:
            print(f"   ❌ Error compressing game: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    async def maintain_window(self, user_id: str) -> int:
        """Ensure exactly MAX_ACTIVE_GAMES active games, compress oldest if needed"""
        active_count = self.count_active_games(user_id)
        
        if active_count > self.MAX_ACTIVE_GAMES:
            # Compress oldest games until we're at MAX_ACTIVE_GAMES
            compressed = 0
            while active_count > self.MAX_ACTIVE_GAMES:
                game_id = await self.compress_oldest_game(user_id)
                if game_id:
                    compressed += 1
                    active_count -= 1
                else:
                    break  # No more games to compress
            
            if compressed > 0:
                print(f"   🔄 Maintained window: compressed {compressed} game(s), {active_count} active remaining")
            
            return compressed
        
        return 0
    
    def get_compressed_games(self, user_id: str, limit: Optional[int] = None) -> List[Dict]:
        """Get compressed games (pattern_summary only) for pattern analysis"""
        try:
            query = self.supabase.client.table("games")\
                .select("id,pattern_summary,game_date,result,user_rating,opponent_rating,opening_eco,opening_name,time_control,time_category,user_color,platform,external_id")\
                .eq("user_id", user_id)\
                .not_.is_("pattern_summary", "null")\
                .order("game_date", desc=False)
            
            if limit:
                query = query.limit(limit)
            
            result = query.execute()
            return result.data if result.data else []
        except Exception as e:
            print(f"⚠️ Error getting compressed games: {e}")
            return []
    
    def expand_pattern_summary(self, compressed_game: Dict) -> Dict:
        """Expand compressed game pattern_summary into format compatible with pattern analysis"""
        pattern = compressed_game.get("pattern_summary", {})
        if isinstance(pattern, str):
            import json
            try:
                pattern = json.loads(pattern)
            except:
                pattern = {}
        
        # Create a game-like structure that pattern analyzers can use
        return {
            "id": compressed_game.get("id"),
            "game_date": compressed_game.get("game_date"),
            "result": compressed_game.get("result"),
            "user_rating": compressed_game.get("user_rating"),
            "opponent_rating": compressed_game.get("opponent_rating"),
            "opening_eco": compressed_game.get("opening_eco") or pattern.get("opening_eco"),
            "opening_name": compressed_game.get("opening_name") or pattern.get("opening_name"),
            "time_control": compressed_game.get("time_control") or pattern.get("time_control"),
            "time_category": compressed_game.get("time_category") or pattern.get("time_category"),
            "user_color": compressed_game.get("user_color") or pattern.get("user_color"),
            "platform": compressed_game.get("platform") or pattern.get("platform"),
            "external_id": compressed_game.get("external_id") or pattern.get("external_id"),
            "accuracy_overall": pattern.get("accuracy_overall"),
            "accuracy_opening": pattern.get("accuracy_opening"),
            "accuracy_middlegame": pattern.get("accuracy_middlegame"),
            "accuracy_endgame": pattern.get("accuracy_endgame"),
            "blunders": pattern.get("blunders", 0),
            "mistakes": pattern.get("mistakes", 0),
            "inaccuracies": pattern.get("inaccuracies", 0),
            "avg_cp_loss": pattern.get("avg_cp_loss"),
            "game_character": pattern.get("game_character"),
            "endgame_type": pattern.get("endgame_type"),
            "total_moves": pattern.get("total_moves", 0),
            "theory_exit_ply": pattern.get("theory_exit_ply"),
            "termination": pattern.get("termination"),
            "opponent_name": pattern.get("opponent_name"),
            # For pattern analysis, create a minimal game_review structure
            "game_review": {
                "metadata": {
                    "player_color": pattern.get("user_color"),
                    "player_rating": pattern.get("user_rating"),
                    "opponent_rating": pattern.get("opponent_rating"),
                    "result": pattern.get("result"),
                    "opening": {
                        "eco": pattern.get("opening_eco"),
                        "name": pattern.get("opening_name")
                    }
                },
                "stats": {
                    "overall_accuracy": pattern.get("accuracy_overall"),
                    "by_phase": {
                        "opening": {"accuracy": pattern.get("phase_accuracy", {}).get("opening")},
                        "middlegame": {"accuracy": pattern.get("phase_accuracy", {}).get("middlegame")},
                        "endgame": {"accuracy": pattern.get("phase_accuracy", {}).get("endgame")}
                    }
                },
                "tags": pattern.get("tags", []),
                "tag_frequencies": pattern.get("tag_frequencies", {})
            },
            "compressed": True  # Flag to indicate this is compressed
        }

