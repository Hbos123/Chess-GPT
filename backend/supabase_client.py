"""
Supabase Client for Chess GPT
Handles all database operations with Supabase
"""

from typing import List, Dict, Any, Optional
from supabase import create_client, Client
import os
from datetime import datetime
import json


class SupabaseClient:
    """Wrapper for Supabase operations"""
    
    def __init__(self, url: str, service_role_key: str):
        self.client: Client = create_client(url, service_role_key)
        print(f"✅ Supabase client initialized: {url}")
    
    # ============================================================================
    # PROFILES
    # ============================================================================
    
    def get_or_create_profile(self, user_id: str, username: str = None) -> Dict:
        """Get or create user profile"""
        try:
            result = self.client.table("profiles").select("*").eq("user_id", user_id).execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0]
            
            # Create profile
            profile_data = {
                "user_id": user_id,
                "username": username or f"user_{user_id[:8]}"
            }
            result = self.client.table("profiles").insert(profile_data).execute()
            return result.data[0] if result.data else {}
        
        except Exception as e:
            print(f"Error getting/creating profile: {e}")
            return {}
    
    def update_profile(self, user_id: str, updates: Dict) -> bool:
        """Update user profile"""
        try:
            self.client.table("profiles").update(updates).eq("user_id", user_id).execute()
            return True
        except Exception as e:
            print(f"Error updating profile: {e}")
            return False
    
    # ============================================================================
    # GAMES
    # ============================================================================
    
    def save_game_review(self, user_id: str, game_data: Dict) -> Optional[str]:
        """Save complete game review using RPC"""
        try:
            result = self.client.rpc("save_game_review", {
                "p_user_id": user_id,
                "p_game": json.dumps(game_data)
            }).execute()
            
            return result.data if result.data else None
        
        except Exception as e:
            print(f"Error saving game review: {e}")
            return None
    
    def get_user_games(
        self,
        user_id: str,
        limit: int = 100,
        platform: Optional[str] = None,
        opening_eco: Optional[str] = None
    ) -> List[Dict]:
        """Fetch user's games with optional filters"""
        try:
            query = self.client.table("games").select("*").eq("user_id", user_id)
            
            if platform:
                query = query.eq("platform", platform)
            
            if opening_eco:
                query = query.eq("opening_eco", opening_eco)
            
            result = query.order("game_date", desc=True).limit(limit).execute()
            
            return result.data if result.data else []
        
        except Exception as e:
            print(f"Error fetching games: {e}")
            return []
    
    def get_analyzed_games(self, user_id: str, limit: int = 50) -> List[Dict]:
        """Get games that have been analyzed (have game_review data)"""
        try:
            result = self.client.table("games")\
                .select("*")\
                .eq("user_id", user_id)\
                .not_.is_("analyzed_at", "null")\
                .order("analyzed_at", desc=True)\
                .limit(limit)\
                .execute()
            
            return result.data if result.data else []
        
        except Exception as e:
            print(f"Error fetching analyzed games: {e}")
            return []
    
    def get_active_reviewed_games(self, user_id: str, limit: int = 30) -> List[Dict]:
        """Get active (non-archived) full-review games"""
        try:
            result = self.client.table("games")\
                .select("*")\
                .eq("user_id", user_id)\
                .eq("review_type", "full")\
                .is_("archived_at", "null")\
                .not_.is_("analyzed_at", "null")\
                .order("analyzed_at", desc=True)\
                .limit(limit)\
                .execute()
            
            return result.data if result.data else []
        
        except Exception as e:
            print(f"Error fetching active reviewed games: {e}")
            return []
    
    def get_active_reviewed_games_count(self, user_id: str) -> int:
        """Count active full-review games"""
        try:
            result = self.client.table("games")\
                .select("id", count="exact")\
                .eq("user_id", user_id)\
                .eq("review_type", "full")\
                .is_("archived_at", "null")\
                .not_.is_("analyzed_at", "null")\
                .execute()
            
            return result.count if hasattr(result, 'count') else 0
        
        except Exception as e:
            print(f"Error counting active reviewed games: {e}")
            return 0
    
    def archive_oldest_game(self, user_id: str) -> Optional[str]:
        """Archive oldest active full-review game, return its ID"""
        try:
            # Get oldest game
            result = self.client.table("games")\
                .select("id")\
                .eq("user_id", user_id)\
                .eq("review_type", "full")\
                .is_("archived_at", "null")\
                .not_.is_("analyzed_at", "null")\
                .order("analyzed_at", desc=False)\
                .limit(1)\
                .execute()
            
            if not result.data or len(result.data) == 0:
                return None
            
            game_id = result.data[0]["id"]
            
            # Archive it
            self.client.table("games")\
                .update({"archived_at": datetime.now().isoformat()})\
                .eq("id", game_id)\
                .execute()
            
            return game_id
        
        except Exception as e:
            print(f"Error archiving oldest game: {e}")
            return None
    
    #============================================================================
    # POSITIONS
    # ============================================================================
    
    def save_position(self, user_id: str, position_data: Dict) -> Optional[str]:
        """Save a position using RPC"""
        try:
            result = self.client.rpc("save_position", {
                "p_user_id": user_id,
                "p_position": json.dumps(position_data)
            }).execute()
            
            return result.data if result.data else None
        
        except Exception as e:
            print(f"Error saving position: {e}")
            return None
    
    def get_positions_by_tags(self, user_id: str, tags: List[str], limit: int = 50) -> List[Dict]:
        """Get positions matching any of the tags"""
        try:
            result = self.client.table("positions")\
                .select("*")\
                .eq("user_id", user_id)\
                .contains("tags", tags)\
                .limit(limit)\
                .execute()
            
            return result.data if result.data else []
        
        except Exception as e:
            print(f"Error fetching positions by tags: {e}")
            return []
    
    def batch_upsert_positions(self, user_id: str, positions: List[Dict], game_id: str) -> int:
        """
        Upsert positions with deduplication.
        Uses ON CONFLICT (user_id, fen, side_to_move) DO UPDATE.
        Appends game_id to source_game_ids array.
        Returns count of positions saved.
        """
        saved_count = 0
        try:
            for position_data in positions:
                position_data["user_id"] = user_id
                
                # Ensure source_game_ids is a list
                if "source_game_ids" not in position_data:
                    position_data["source_game_ids"] = []
                
                # Append game_id if not already present
                if game_id not in position_data["source_game_ids"]:
                    position_data["source_game_ids"].append(game_id)
                
                # Try to find existing position
                existing = self.client.table("positions")\
                    .select("id, source_game_ids")\
                    .eq("user_id", user_id)\
                    .eq("fen", position_data["fen"])\
                    .eq("side_to_move", position_data["side_to_move"])\
                    .execute()
                
                if existing.data and len(existing.data) > 0:
                    # Update existing - append game_id to source_game_ids
                    existing_id = existing.data[0]["id"]
                    existing_sources = existing.data[0].get("source_game_ids", [])
                    if game_id not in existing_sources:
                        existing_sources.append(game_id)
                    
                    self.client.table("positions")\
                        .update({
                            **position_data,
                            "source_game_ids": existing_sources
                        })\
                        .eq("id", existing_id)\
                        .execute()
                else:
                    # Insert new
                    self.client.table("positions").insert(position_data).execute()
                
                saved_count += 1
        
        except Exception as e:
            print(f"Error batch upserting positions: {e}")
        
        return saved_count
    
    # ============================================================================
    # COLLECTIONS
    # ============================================================================
    
    def create_collection(self, user_id: str, name: str, description: str = "") -> Optional[str]:
        """Create a new collection"""
        try:
            result = self.client.table("collections").insert({
                "user_id": user_id,
                "name": name,
                "description": description
            }).execute()
            
            return result.data[0]["id"] if result.data else None
        
        except Exception as e:
            print(f"Error creating collection: {e}")
            return None
    
    def get_user_collections(self, user_id: str) -> List[Dict]:
        """Get all collections for user"""
        try:
            result = self.client.table("collections")\
                .select("*")\
                .eq("user_id", user_id)\
                .order("created_at", desc=True)\
                .execute()
            
            return result.data if result.data else []
        
        except Exception as e:
            print(f"Error fetching collections: {e}")
            return []
    
    def add_game_to_collection(self, collection_id: str, game_id: str) -> bool:
        """Add game to collection"""
        try:
            self.client.table("collection_games").insert({
                "collection_id": collection_id,
                "game_id": game_id
            }).execute()
            return True
        
        except Exception as e:
            print(f"Error adding game to collection: {e}")
            return False
    
    # ============================================================================
    # TRAINING CARDS
    # ============================================================================
    
    def save_training_card(self, user_id: str, card_data: Dict) -> Optional[str]:
        """Save or update a training card"""
        try:
            # Check if card exists
            existing = self.client.table("training_cards")\
                .select("id")\
                .eq("user_id", user_id)\
                .eq("card_id", card_data["card_id"])\
                .execute()
            
            if existing.data and len(existing.data) > 0:
                # Update existing
                card_uuid = existing.data[0]["id"]
                self.client.table("training_cards").update(card_data).eq("id", card_uuid).execute()
                return card_uuid
            else:
                # Insert new
                card_data["user_id"] = user_id
                result = self.client.table("training_cards").insert(card_data).execute()
                return result.data[0]["id"] if result.data else None
        
        except Exception as e:
            print(f"Error saving training card: {e}")
            return None
    
    def get_due_cards(self, user_id: str, max_cards: int = 20) -> List[Dict]:
        """Get due training cards using RPC"""
        try:
            result = self.client.rpc("get_srs_due_cards", {
                "p_user_id": user_id,
                "p_max_cards": max_cards
            }).execute()
            
            return result.data if result.data else []
        
        except Exception as e:
            print(f"Error fetching due cards: {e}")
            return []
    
    def update_card_attempt(
        self,
        card_id: str,
        correct: bool,
        time_s: float,
        hints_used: int
    ) -> Dict:
        """Update card SRS state after attempt"""
        try:
            result = self.client.rpc("update_card_srs", {
                "p_card_id": card_id,
                "p_correct": correct,
                "p_time_s": time_s,
                "p_hints_used": hints_used
            }).execute()
            
            return result.data if result.data else {}
        
        except Exception as e:
            print(f"Error updating card: {e}")
            return {}
    
    def get_cards_by_stage(self, user_id: str, stage: str) -> List[Dict]:
        """Get cards in specific SRS stage"""
        try:
            result = self.client.table("training_cards")\
                .select("*")\
                .eq("user_id", user_id)\
                .eq("srs_stage", stage)\
                .execute()
            
            return result.data if result.data else []
        
        except Exception as e:
            print(f"Error fetching cards by stage: {e}")
            return []
    
    # ============================================================================
    # CHAT
    # ============================================================================
    
    def create_chat_session(
        self,
        user_id: str,
        title: str = "New Chat",
        mode: str = "DISCUSS",
        linked_game_id: Optional[str] = None
    ) -> Optional[str]:
        """Create a new chat session"""
        try:
            result = self.client.table("chat_sessions").insert({
                "user_id": user_id,
                "title": title,
                "mode": mode,
                "linked_game_id": linked_game_id
            }).execute()
            
            return result.data[0]["id"] if result.data else None
        
        except Exception as e:
            print(f"Error creating chat session: {e}")
            return None
    
    def save_chat_message(
        self,
        session_id: str,
        user_id: str,
        role: str,
        content: str,
        tool_name: Optional[str] = None
    ) -> bool:
        """Save a chat message"""
        try:
            self.client.table("chat_messages").insert({
                "session_id": session_id,
                "user_id": user_id,
                "role": role,
                "content": content,
                "tool_name": tool_name
            }).execute()
            return True
        
        except Exception as e:
            print(f"Error saving chat message: {e}")
            return False
    
    def get_chat_history(self, session_id: str, limit: int = 100) -> List[Dict]:
        """Get messages for a chat session"""
        try:
            result = self.client.table("chat_messages")\
                .select("*")\
                .eq("session_id", session_id)\
                .order("created_at")\
                .limit(limit)\
                .execute()
            
            return result.data if result.data else []
        
        except Exception as e:
            print(f"Error fetching chat history: {e}")
            return []
    
    def get_user_chat_sessions(self, user_id: str, limit: int = 20) -> List[Dict]:
        """Get user's recent chat sessions"""
        try:
            result = self.client.table("chat_sessions")\
                .select("*")\
                .eq("user_id", user_id)\
                .order("last_message_at", desc=True)\
                .limit(limit)\
                .execute()
            
            return result.data if result.data else []
        
        except Exception as e:
            print(f"Error fetching chat sessions: {e}")
            return []
    
    # ============================================================================
    # STATS & ANALYTICS
    # ============================================================================
    
    def get_user_stats(self, user_id: str) -> Dict:
        """Get user statistics using RPC"""
        try:
            result = self.client.rpc("get_user_stats", {
                "p_user_id": user_id
            }).execute()
            
            return result.data if result.data else {}
        
        except Exception as e:
            print(f"Error fetching user stats: {e}")
            return {}

    # ============================================================================
    # LESSONS
    # ============================================================================

    def save_opening_lesson(self, user_id: str, lesson_data: Dict) -> Optional[str]:
        """Persist generated opening lesson metadata for spaced repetition."""
        try:
            payload = {
                "user_id": user_id,
                "lesson_id": lesson_data.get("lesson_id"),
                "opening_name": lesson_data.get("opening_name"),
                "eco": lesson_data.get("eco"),
                "variation_hash": lesson_data.get("variation_hash"),
                "orientation": lesson_data.get("orientation"),
                "seed_query": lesson_data.get("seed_query"),
                "chat_id": lesson_data.get("chat_id"),
                "difficulty": lesson_data.get("difficulty"),
                "metadata": lesson_data.get("metadata"),
            }
            result = self.client.table("opening_lessons").insert(payload).execute()
            if result.data:
                return result.data[0].get("id")
            return None
        except Exception as e:
            print(f"Error saving opening lesson: {e}")
            return None

    def get_recent_opening_lessons(self, user_id: str, opening_key: Optional[str], limit: int = 5) -> List[Dict]:
        """Fetch recent lessons for an opening to manage variation rotation."""
        try:
            query = self.client.table("opening_lessons")\
                .select("*")\
                .eq("user_id", user_id)\
                .order("created_at", desc=True)\
                .limit(limit)
            if opening_key:
                query = query.or_(f"eco.eq.{opening_key},opening_name.ilike.%{opening_key}%")
            result = query.execute()
            return result.data if result.data else []
        except Exception as e:
            print(f"Error fetching opening lessons: {e}")
            return []

    # ============================================================================
    # PROFILE STATS
    # ============================================================================

    def save_profile_stats(self, user_id: str, stats: Dict) -> bool:
        """Upsert aggregated profile statistics"""
        try:
            self.client.table("profile_stats").upsert({
                "user_id": user_id,
                "stats": stats,
                "updated_at": datetime.utcnow().isoformat() + "Z"
            }).execute()
            return True
        except Exception as e:
            print(f"Error saving profile stats: {e}")
            return False

    def get_profile_stats(self, user_id: str) -> Dict:
        """Fetch cached profile statistics"""
        try:
            result = self.client.table("profile_stats")\
                .select("*")\
                .eq("user_id", user_id)\
                .single()\
                .execute()
            return result.data if result.data else {}
        except Exception as e:
            print(f"Error fetching profile stats: {e}")
            return {}
    
    # ============================================================================
    # PERSONAL STATS (for Personal Review System)
    # ============================================================================
    
    def get_personal_stats(self, user_id: str) -> Optional[Dict]:
        """Get personal stats row"""
        try:
            result = self.client.table("personal_stats")\
                .select("*")\
                .eq("user_id", user_id)\
                .single()\
                .execute()
            
            return result.data if result.data else None
        
        except Exception as e:
            # No stats found is OK (will trigger lazy migration)
            return None
    
    def update_personal_stats(self, user_id: str, stats: Dict, game_ids: List[str]) -> bool:
        """Atomic update of personal stats"""
        try:
            # Upsert stats
            self.client.table("personal_stats").upsert({
                "user_id": user_id,
                "stats": stats,
                "game_ids": game_ids,
                "needs_recalc": False,
                "last_validated_at": datetime.now().isoformat() + "Z"
            }).execute()
            
            return True
        
        except Exception as e:
            print(f"Error updating personal stats: {e}")
            return False
    
    def mark_stats_for_recalc(self, user_id: str, game_ids: List[str]) -> bool:
        """Mark stats as needing recalculation"""
        try:
            self.client.table("personal_stats").upsert({
                "user_id": user_id,
                "game_ids": game_ids,
                "needs_recalc": True
            }).execute()
            
            return True
        
        except Exception as e:
            print(f"Error marking stats for recalc: {e}")
            return False

