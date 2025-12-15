"""
Game Archive Manager
Manages 30-game limit with soft-delete archiving
"""

from typing import Dict, List, Optional
from datetime import datetime


class GameArchiveManager:
    """Manages 30-game limit with soft-delete archiving."""
    
    MAX_ACTIVE_GAMES = 30
    
    def __init__(self, supabase_client, stats_manager):
        self.supabase = supabase_client
        self.stats_manager = stats_manager
    
    def save_game_with_limit(self, user_id: str, game_data: Dict) -> Optional[str]:
        """
        Save game, archive oldest if at limit.
        Only counts review_type='full' toward limit.
        Returns game_id if successful.
        """
        try:
            review_type = game_data.get("review_type", "full")
            
            # Only full reviews count toward limit
            if review_type == "full":
                # Count active full-review games
                active_count = self.supabase.get_active_reviewed_games_count(user_id)
                
                if active_count >= self.MAX_ACTIVE_GAMES:
                    # Archive oldest game
                    oldest_game_id = self.supabase.archive_oldest_game(user_id)
                    if oldest_game_id:
                        print(f"   📦 Archived oldest game {oldest_game_id} (limit reached)")
                        # Remove from stats
                        self.stats_manager.remove_game_from_stats(user_id, oldest_game_id)
            
            # Save new game
            game_id = self.supabase.save_game_review(user_id, game_data)
            
            if game_id and review_type == "full":
                # Update stats with new game
                self.stats_manager.update_stats_from_game(user_id, game_id, game_data)
            
            return game_id
        
        except Exception as e:
            print(f"   ❌ Error saving game with limit: {e}")
            return None
    
    def archive_game(self, user_id: str, game_id: str) -> bool:
        """Soft-delete: set archived_at, update stats."""
        try:
            result = self.supabase.client.table("games")\
                .update({"archived_at": datetime.now().isoformat()})\
                .eq("user_id", user_id)\
                .eq("id", game_id)\
                .execute()
            
            if result.data:
                # Remove from stats
                self.stats_manager.remove_game_from_stats(user_id, game_id)
                return True
            
            return False
        
        except Exception as e:
            print(f"   ❌ Error archiving game: {e}")
            return False
    
    def unarchive_game(self, user_id: str, game_id: str) -> bool:
        """
        Restore archived game, may archive another if limit exceeded.
        Returns True if successful.
        """
        try:
            # Unarchive the game
            result = self.supabase.client.table("games")\
                .update({"archived_at": None})\
                .eq("user_id", user_id)\
                .eq("id", game_id)\
                .execute()
            
            if not result.data:
                return False
            
            # Check if we're over limit now
            active_count = self.supabase.get_active_reviewed_games_count(user_id)
            
            if active_count > self.MAX_ACTIVE_GAMES:
                # Archive oldest to maintain limit
                oldest_game_id = self.supabase.archive_oldest_game(user_id)
                if oldest_game_id and oldest_game_id != game_id:
                    print(f"   📦 Archived oldest game {oldest_game_id} (limit exceeded after unarchive)")
                    self.stats_manager.remove_game_from_stats(user_id, oldest_game_id)
            
            # Re-add to stats
            game = self.supabase.client.table("games")\
                .select("*")\
                .eq("id", game_id)\
                .single()\
                .execute()
            
            if game.data:
                game_review = game.data.get("game_review", {})
                if game_review:
                    self.stats_manager.update_stats_from_game(user_id, game_id, game_review)
            
            return True
        
        except Exception as e:
            print(f"   ❌ Error unarchiving game: {e}")
            return False
    
    def get_active_games(self, user_id: str, limit: int = 30) -> List[Dict]:
        """Get active (non-archived) games."""
        try:
            result = self.supabase.client.table("games")\
                .select("*")\
                .eq("user_id", user_id)\
                .is_("archived_at", "null")\
                .order("analyzed_at", desc=True)\
                .limit(limit)\
                .execute()
            
            return result.data if result.data else []
        
        except Exception as e:
            print(f"   ❌ Error getting active games: {e}")
            return []
    
    def get_archived_games(self, user_id: str, limit: int = 100) -> List[Dict]:
        """Get archived games."""
        try:
            result = self.supabase.client.table("games")\
                .select("*")\
                .eq("user_id", user_id)\
                .not_.is_("archived_at", "null")\
                .order("archived_at", desc=True)\
                .limit(limit)\
                .execute()
            
            return result.data if result.data else []
        
        except Exception as e:
            print(f"   ❌ Error getting archived games: {e}")
            return []

