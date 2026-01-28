"""
Supabase Client for Chesster
Handles all database operations with Supabase
"""

from typing import List, Dict, Any, Optional, Tuple
from supabase import create_client, Client
import os
from datetime import datetime
import json
from postgrest.exceptions import APIError
import traceback
import threading
import queue


class SupabaseClient:
    @staticmethod
    def _is_missing_column_error(exc: Exception, column_name: str) -> bool:
        """
        Supabase/PostgREST returns APIError with code 42703 for missing columns.
        We use this to gracefully degrade when optional columns (like compressed_at)
        aren't present in the user's schema/migrations yet.
        """
        if not isinstance(exc, APIError):
            return False
        try:
            payload = exc.args[0] if exc.args else {}
            return (
                isinstance(payload, dict)
                and payload.get("code") == "42703"
                and column_name in str(payload.get("message", ""))
            )
        except Exception:
            return False

    """Wrapper for Supabase operations"""
    
    def __init__(self, url: str, service_role_key: str):
        self.client: Client = create_client(url, service_role_key)
        print(f"✅ Supabase client initialized: {url}")

    def _apply_eq(self, query, column: str, value):
        """Apply an equality filter across PostgREST client versions.

        Some deployments expose .eq() on the request builder; others only expose .filter() or .match().
        """
        if hasattr(query, "eq"):
            return query.eq(column, value)
        if hasattr(query, "filter"):
            return query.filter(column, "eq", value)
        if hasattr(query, "match"):
            return query.match({column: value})
        raise AttributeError(f"Request builder has no eq/filter/match methods (type={type(query)})")

    def _apply_match(self, query, filters: dict):
        """Apply multiple equality filters across client versions."""
        if hasattr(query, "match"):
            return query.match(filters)
        # Fall back to chaining eq/filter
        for k, v in filters.items():
            query = self._apply_eq(query, k, v)
        return query
    
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
    # SUBSCRIPTIONS
    # ============================================================================

    def get_subscription_overview(self, user_id: str) -> Dict[str, Any]:
        """
        Fetch a user's subscription + tier details.

        Returns a JSON-serializable dict like:
          {
            "tier_id": "starter",
            "status": "active",
            "current_period_end": "2026-01-01T00:00:00Z",
            "stripe_customer_id": "cus_...",
            "tier": { ...subscription_tiers... }
          }
        """
        try:
            # PostgREST embedded relationship (FK: user_subscriptions.tier_id -> subscription_tiers.id)
            result = (
                self.client.table("user_subscriptions")
                .select(
                    "tier_id,status,current_period_start,current_period_end,stripe_customer_id,stripe_subscription_id,"
                    "subscription_tiers(id,name,daily_messages,daily_tokens,max_games_storage,max_lessons_per_day,max_game_reviews_per_day)"
                )
                .eq("user_id", user_id)
                .limit(1)
                .execute()
            )

            row = (result.data[0] if result.data else None) or None
            if not row:
                return {
                    "tier_id": "unpaid",
                    "status": "inactive",
                    "current_period_start": None,
                    "current_period_end": None,
                    "stripe_customer_id": None,
                    "stripe_subscription_id": None,
                    "tier": {"id": "unpaid", "name": "Unpaid"},
                }

            return {
                "tier_id": row.get("tier_id"),
                "status": row.get("status"),
                "current_period_start": row.get("current_period_start"),
                "current_period_end": row.get("current_period_end"),
                "stripe_customer_id": row.get("stripe_customer_id"),
                "stripe_subscription_id": row.get("stripe_subscription_id"),
                "tier": row.get("subscription_tiers"),
            }
        except Exception as e:
            print(f"[subscriptions] get_subscription_overview error: {e}")
            return {
                "tier_id": "unpaid",
                "status": "error",
                "current_period_start": None,
                "current_period_end": None,
                "stripe_customer_id": None,
                "stripe_subscription_id": None,
                "tier": {"id": "unpaid", "name": "Unpaid"},
            }

    def get_stripe_customer_id(self, user_id: str) -> Optional[str]:
        try:
            result = (
                self.client.table("user_subscriptions")
                .select("stripe_customer_id")
                .eq("user_id", user_id)
                .limit(1)
                .execute()
            )
            if not result.data:
                return None
            return (result.data[0] or {}).get("stripe_customer_id")
        except Exception as e:
            print(f"[subscriptions] get_stripe_customer_id error: {e}")
            return None

    def get_user_by_email(self, email: str) -> Optional[str]:
        """
        Get Supabase user ID by email address.
        Uses Supabase Admin API to query auth.users.
        """
        try:
            # Use Supabase Admin API to query auth.users
            # The service role key allows us to access auth.users
            import requests
            
            supabase_url = os.getenv("SUPABASE_URL") or self.client.supabase_url
            service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
            
            if not service_key:
                print("[subscriptions] SUPABASE_SERVICE_ROLE_KEY not set, cannot query auth.users")
                return None
            
            # Query auth.users via Admin API
            headers = {
                "apikey": service_key,
                "Authorization": f"Bearer {service_key}",
                "Content-Type": "application/json",
            }
            
            # List users and filter by email
            response = requests.get(
                f"{supabase_url}/auth/v1/admin/users",
                headers=headers,
                params={"email": email},
            )
            
            if response.status_code == 200:
                users = response.json().get("users", [])
                if users and len(users) > 0:
                    return users[0].get("id")
            
            return None
        except Exception as e:
            print(f"[subscriptions] get_user_by_email error: {e}")
            import traceback
            traceback.print_exc()
            return None

    def upsert_user_subscription(
        self,
        user_id: str,
        stripe_customer_id: str,
        stripe_subscription_id: Optional[str] = None,
        tier_id: Optional[str] = None,
        status: Optional[str] = None,
        current_period_start: Optional[str] = None,
        current_period_end: Optional[str] = None,
    ) -> bool:
        """
        Create or update user subscription record with Stripe data.
        
        Args:
            user_id: Supabase user ID
            stripe_customer_id: Stripe customer ID
            stripe_subscription_id: Stripe subscription ID (optional)
            tier_id: Subscription tier ID (optional, will try to infer from Stripe if not provided)
            status: Subscription status (optional)
            current_period_start: Period start timestamp (optional)
            current_period_end: Period end timestamp (optional)
        """
        try:
            # Build update data
            update_data: Dict[str, Any] = {
                "stripe_customer_id": stripe_customer_id,
                "updated_at": datetime.utcnow().isoformat(),
            }
            
            if stripe_subscription_id:
                update_data["stripe_subscription_id"] = stripe_subscription_id
            if tier_id:
                update_data["tier_id"] = tier_id
            if status:
                update_data["status"] = status
            if current_period_start:
                update_data["current_period_start"] = current_period_start
            if current_period_end:
                update_data["current_period_end"] = current_period_end

            # Upsert (insert or update)
            result = (
                self.client.table("user_subscriptions")
                .upsert(
                    {
                        "user_id": user_id,
                        **update_data,
                    },
                    on_conflict="user_id",
                )
                .execute()
            )
            
            print(f"[subscriptions] Upserted subscription for user {user_id}: {update_data}")
            return True
        except Exception as e:
            print(f"[subscriptions] upsert_user_subscription error: {e}")
            traceback.print_exc()
            return False

    def check_and_increment_usage(
        self, 
        user_id: Optional[str], 
        ip_address: Optional[str],
        resource_type: str,  # 'game_review' or 'lesson'
        tier_info: Dict[str, Any]
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Check if user can use a resource and increment counter if allowed.
        
        Args:
            user_id: User ID (optional, for authenticated users)
            ip_address: IP address (optional, for anonymous users)
            resource_type: 'game_review' or 'lesson'
            tier_info: Subscription tier info from get_subscription_overview()
        
        Returns:
            (allowed: bool, message: str, usage_info: dict)
        """
        if not user_id and not ip_address:
            return False, "Authentication required", {}
        
        # Get tier limits
        tier = tier_info.get("tier", {})
        max_per_day = None
        if resource_type == "game_review":
            max_per_day = tier.get("max_game_reviews_per_day")
        elif resource_type == "lesson":
            max_per_day = tier.get("max_lessons_per_day")
        
        # Check if feature is available for unpaid users
        tier_id = tier_info.get("tier_id", "unpaid")
        if tier_id == "unpaid" and max_per_day == 0:
            return False, "This feature is not available for unpaid users. Please upgrade to a paid plan.", {}
        
        # Unlimited for Full tier (max_per_day is None)
        if max_per_day is None:
            # Increment counter but allow
            self._increment_daily_usage(user_id, ip_address, resource_type)
            return True, "", {"used": 0, "limit": "unlimited"}
        
        # Get current usage
        today = datetime.now().date()
        usage = self._get_daily_usage(user_id, ip_address, today)
        
        count_field = "game_reviews_count" if resource_type == "game_review" else "lessons_count"
        current_count = usage.get(count_field, 0) if usage else 0
        
        if current_count >= max_per_day:
            return False, f"Daily limit exceeded. You've used {current_count}/{max_per_day} {resource_type}s today. Limit resets at midnight.", {
                "used": current_count,
                "limit": max_per_day
            }
        
        # Increment and allow
        self._increment_daily_usage(user_id, ip_address, resource_type)
        return True, "", {
            "used": current_count + 1,
            "limit": max_per_day
        }

    def _get_daily_usage(self, user_id: Optional[str], ip_address: Optional[str], date) -> Optional[Dict]:
        """Get today's usage record"""
        try:
            # Supabase Python v2: filters (eq, etc.) are available on the request builder
            # returned by .select()/.update()/.delete(), not on .table() directly.
            query = self.client.table("daily_usage").select("*")
            if user_id:
                query = self._apply_eq(query, "user_id", user_id)
            else:
                query = self._apply_eq(query, "ip_address", ip_address)
            query = self._apply_eq(query, "usage_date", date.isoformat())
            
            result = query.execute()
            return result.data[0] if result.data else None
        except Exception as e:
            print(f"[daily_usage] Error getting usage: {e}")
            return None

    def _increment_daily_usage(self, user_id: Optional[str], ip_address: Optional[str], resource_type: str):
        """Increment daily usage counter"""
        try:
            today = datetime.now().date()
            count_field = "game_reviews_count" if resource_type == "game_review" else "lessons_count"
            
            # Try to get existing record
            query = self.client.table("daily_usage").select("*")
            if user_id:
                query = self._apply_eq(query, "user_id", user_id)
            else:
                query = self._apply_eq(query, "ip_address", ip_address)
            query = self._apply_eq(query, "usage_date", today.isoformat())
            
            result = query.execute()
            
            if result.data:
                # Update existing
                current = result.data[0].get(count_field, 0)
                upd = self.client.table("daily_usage").update({count_field: current + 1})
                if user_id:
                    upd = self._apply_eq(upd, "user_id", user_id)
                else:
                    upd = self._apply_eq(upd, "ip_address", ip_address)
                upd = self._apply_eq(upd, "usage_date", today.isoformat())
                upd.execute()
            else:
                # Create new record
                data = {
                    "usage_date": today.isoformat(),
                    count_field: 1
                }
                if user_id:
                    data["user_id"] = user_id
                else:
                    data["ip_address"] = ip_address
                
                self.client.table("daily_usage").insert(data).execute()
        except Exception as e:
            print(f"[daily_usage] Error incrementing usage: {e}")
            traceback.print_exc()

    def check_message_limit(
        self,
        user_id: Optional[str],
        ip_address: Optional[str],
        tier_info: Dict[str, Any]
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Check if user can send a message today.
        
        Returns:
            (allowed: bool, message: str, usage_info: dict)
        """
        # Unsigned users: 1 message/day
        if not user_id:
            if not ip_address:
                return False, "IP address required for anonymous users", {}
            
            today = datetime.now().date()
            usage = self._get_daily_usage(None, ip_address, today)
            messages_count = usage.get("messages_count", 0) if usage else 0
            
            if messages_count >= 1:
                return False, "Daily message limit exceeded. Sign in to get 2 messages/day, or upgrade for more.", {
                    "used": messages_count,
                    "limit": 1,
                    "next_step": "sign_in"
                }
            
            # Increment and allow
            self._increment_message_count(None, ip_address)
            return True, "", {"used": messages_count + 1, "limit": 1}
        
        # Signed-in users: check tier limits
        tier = tier_info.get("tier", {})
        max_messages = tier.get("daily_messages", 2)  # Default to 2 for unpaid
        
        today = datetime.now().date()
        usage = self._get_daily_usage(user_id, None, today)
        messages_count = usage.get("messages_count", 0) if usage else 0
        
        if messages_count >= max_messages:
            tier_id = tier_info.get("tier_id", "unpaid")
            if tier_id == "unpaid":
                next_step = "upgrade_lite"
                message = f"Daily message limit exceeded ({messages_count}/{max_messages}). Upgrade to Lite for 15 messages/day."
            else:
                next_step = "upgrade"
                message = f"Daily message limit exceeded ({messages_count}/{max_messages}). Upgrade your plan for more messages."
            
            return False, message, {
                "used": messages_count,
                "limit": max_messages,
                "next_step": next_step,
                "tier_id": tier_id
            }
        
        # Increment and allow
        self._increment_message_count(user_id, None)
        return True, "", {"used": messages_count + 1, "limit": max_messages}

    def check_token_limit(
        self,
        user_id: Optional[str],
        ip_address: Optional[str],
        tier_info: Dict[str, Any],
        estimated_tokens: int = 0
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Check if user has enough tokens remaining for this request.
        
        Returns:
            (allowed: bool, message: str, usage_info: dict, available_tools: dict)
        """
        tier = tier_info.get("tier", {})
        max_tokens = tier.get("daily_tokens", 15000)  # Default to 15k for unpaid
        
        today = datetime.now().date()
        usage = self._get_daily_usage(user_id, ip_address, today)
        tokens_used = usage.get("tokens_used", 0) if usage else 0
        
        # Check available tools (game reviews/lessons)
        available_tools = {}
        tier_id = tier_info.get("tier_id", "unpaid")
        
        # Check game reviews
        max_reviews = tier.get("max_game_reviews_per_day", 0)
        if max_reviews is None:
            available_tools["game_reviews"] = {"available": True, "limit": "unlimited"}
        elif max_reviews > 0:
            reviews_used = usage.get("game_reviews_count", 0) if usage else 0
            available_tools["game_reviews"] = {
                "available": reviews_used < max_reviews,
                "used": reviews_used,
                "limit": max_reviews
            }
        else:
            available_tools["game_reviews"] = {"available": False, "limit": 0}
        
        # Check lessons
        max_lessons = tier.get("max_lessons_per_day", 0)
        if max_lessons is None:
            available_tools["lessons"] = {"available": True, "limit": "unlimited"}
        elif max_lessons > 0:
            lessons_used = usage.get("lessons_count", 0) if usage else 0
            available_tools["lessons"] = {
                "available": lessons_used < max_lessons,
                "used": lessons_used,
                "limit": max_lessons
            }
        else:
            available_tools["lessons"] = {"available": False, "limit": 0}
        
        if tokens_used + estimated_tokens > max_tokens:
            if tier_id == "unpaid":
                if not user_id:
                    next_step = "sign_in"
                    message = f"Token limit exceeded ({tokens_used}/{max_tokens}). Sign in to get 15k tokens/day, or upgrade for more."
                else:
                    next_step = "upgrade_lite"
                    message = f"Token limit exceeded ({tokens_used}/{max_tokens}). Upgrade to Lite for 43k tokens/day."
            else:
                next_step = "upgrade"
                message = f"Token limit exceeded ({tokens_used}/{max_tokens}). Upgrade your plan for more tokens."
            
            return False, message, {
                "used": tokens_used,
                "limit": max_tokens,
                "next_step": next_step,
                "tier_id": tier_id,
                "available_tools": available_tools
            }
        
        return True, "", {
            "used": tokens_used,
            "limit": max_tokens,
            "available_tools": available_tools
        }

    def _increment_message_count(self, user_id: Optional[str], ip_address: Optional[str]):
        """Increment daily message count (non-blocking, fire-and-forget)"""
        def _do_increment():
            try:
                today = datetime.now().date()
                
                query = self.client.table("daily_usage").select("*")
                if user_id:
                    query = self._apply_eq(query, "user_id", user_id)
                else:
                    query = self._apply_eq(query, "ip_address", ip_address)
                query = self._apply_eq(query, "usage_date", today.isoformat())
                
                result = query.execute()
                
                if result.data:
                    # Update existing
                    current = result.data[0].get("messages_count", 0)
                    upd = self.client.table("daily_usage").update({"messages_count": current + 1})
                    if user_id:
                        upd = self._apply_eq(upd, "user_id", user_id)
                    else:
                        upd = self._apply_eq(upd, "ip_address", ip_address)
                    upd = self._apply_eq(upd, "usage_date", today.isoformat())
                    upd.execute()
                else:
                    # Create new record
                    data = {
                        "usage_date": today.isoformat(),
                        "messages_count": 1
                    }
                    if user_id:
                        data["user_id"] = user_id
                    else:
                        data["ip_address"] = ip_address
                    
                    self.client.table("daily_usage").insert(data).execute()
            except Exception as e:
                # Silently fail - don't block the main request
                error_msg = str(e)
                if "timeout" not in error_msg.lower() and "ReadTimeout" not in error_msg:
                    print(f"[daily_usage] Error incrementing message count: {e}")
        
        # Run in background thread to avoid blocking
        thread = threading.Thread(target=_do_increment, daemon=True)
        thread.start()

    def increment_token_usage(self, user_id: Optional[str], ip_address: Optional[str], tokens: int):
        """Increment daily token usage (non-blocking, fire-and-forget)"""
        def _do_increment():
            try:
                today = datetime.now().date()
                
                query = self.client.table("daily_usage").select("*")
                if user_id:
                    query = self._apply_eq(query, "user_id", user_id)
                else:
                    query = self._apply_eq(query, "ip_address", ip_address)
                query = self._apply_eq(query, "usage_date", today.isoformat())
                
                result = query.execute()
                
                if result.data:
                    # Update existing
                    current = result.data[0].get("tokens_used", 0)
                    upd = self.client.table("daily_usage").update({"tokens_used": current + tokens})
                    if user_id:
                        upd = self._apply_eq(upd, "user_id", user_id)
                    else:
                        upd = self._apply_eq(upd, "ip_address", ip_address)
                    upd = self._apply_eq(upd, "usage_date", today.isoformat())
                    upd.execute()
                else:
                    # Create new record
                    data = {
                        "usage_date": today.isoformat(),
                        "tokens_used": tokens
                    }
                    if user_id:
                        data["user_id"] = user_id
                    else:
                        data["ip_address"] = ip_address
                    
                    self.client.table("daily_usage").insert(data).execute()
            except Exception as e:
                # Silently fail - don't block the main request
                error_msg = str(e)
                if "timeout" not in error_msg.lower() and "ReadTimeout" not in error_msg:
                    print(f"[daily_usage] Error incrementing token usage: {e}")
        
        # Run in background thread to avoid blocking
        thread = threading.Thread(target=_do_increment, daemon=True)
        thread.start()
    
    # ============================================================================
    # GAMES
    # ============================================================================
    
    def save_game_review(self, user_id: str, game_data: Dict) -> Optional[str]:
        """Save complete game review - direct insert instead of RPC for backend context"""
        try:
            def _normalize_platform(p: Any) -> Optional[str]:
                if p is None:
                    return None
                p2 = str(p).strip().lower()
                if p2 in ("chesscom", "chess_com", "chess.com", "chess-com"):
                    return "chess.com"
                if p2 in ("lichess", "lichess.org"):
                    return "lichess"
                return str(p).strip()

            # Extract fields for direct insert (RPC has auth issues in backend context)
            insert_data = {
                "user_id": user_id,
                "platform": _normalize_platform(game_data.get("platform")),
                "external_id": game_data.get("external_id"),
                "game_date": game_data.get("game_date"),
                "user_color": game_data.get("user_color"),
                "opponent_name": game_data.get("opponent_name"),
                "user_rating": game_data.get("user_rating"),
                "opponent_rating": game_data.get("opponent_rating"),
                "result": game_data.get("result"),
                "termination": game_data.get("termination"),
                "time_control": game_data.get("time_control"),
                "time_category": game_data.get("time_category"),
                "opening_eco": game_data.get("opening_eco"),
                "opening_name": game_data.get("opening_name"),
                "theory_exit_ply": game_data.get("theory_exit_ply"),
                "accuracy_overall": game_data.get("accuracy_overall", 0),
                "accuracy_opening": game_data.get("accuracy_opening", 0),
                "accuracy_middlegame": game_data.get("accuracy_middlegame", 0),
                "accuracy_endgame": game_data.get("accuracy_endgame", 0),
                "avg_cp_loss": game_data.get("avg_cp_loss", 0),
                "blunders": game_data.get("blunders", 0),
                "mistakes": game_data.get("mistakes", 0),
                "inaccuracies": game_data.get("inaccuracies", 0),
                "total_moves": game_data.get("total_moves", 0),
                "game_character": game_data.get("game_character"),
                "endgame_type": game_data.get("endgame_type"),
                "pgn": game_data.get("pgn"),
                # NOTE: Full game_review JSON can be very large and may trigger Postgres statement timeouts
                # during upsert. We conditionally store it below.
                "game_review": None,
                "review_type": game_data.get("review_type", "full"),
                "analyzed_at": datetime.utcnow().isoformat() + "Z"
            }
            # Decide whether to persist full review JSON in this row (can time out for large payloads).
            try:
                full_review = game_data.get("game_review") or game_data
                approx_bytes = len(json.dumps(full_review, default=str))
                # Keep under ~150KB to avoid statement timeouts on large rows.
                if approx_bytes <= 150_000:
                    insert_data["game_review"] = full_review
                else:
                    insert_data["game_review"] = {
                        "_stored": False,
                        "_reason": "payload_too_large",
                        "_approx_bytes": approx_bytes,
                    }
                    pgn = insert_data.get("pgn")
                    if isinstance(pgn, str) and len(pgn) > 200_000:
                        insert_data["pgn"] = pgn[:200_000] + "\n\n;[TRUNCATED]"
            except Exception:
                insert_data["game_review"] = {"_stored": False, "_reason": "size_check_failed"}

            
            # Debug: log platform value
            print(f"   💾 Saving game: platform={insert_data['platform']}, external_id={insert_data['external_id']}")
            
            # Upsert based on user_id + platform + external_id
            # Supabase Python client upsert updates all provided fields on conflict
            result = self.client.table("games").upsert(
                insert_data,
                on_conflict="user_id,platform,external_id"
            ).execute()
            
            if result.data and len(result.data) > 0:
                game_id = result.data[0].get("id")
                print(f"   ✅ Game saved with ID: {game_id}, analyzed_at: {insert_data.get('analyzed_at', 'not set')}")
                
                # Pre-compute and save graph data point (non-blocking, non-fatal)
                try:
                    from profile_analytics.graph_data import build_graph_game_point
                    # Build graph point from the game_data we just saved
                    graph_point = build_graph_game_point(
                        {**game_data, "id": game_id}, 
                        index=0  # Index will be recalculated when fetching
                    )
                    # Save to game_graph_data table
                    self._save_game_graph_data(user_id, game_id, graph_point)
                except Exception as e:
                    print(f"   ⚠️ Failed to save graph data for game {game_id}: {e}")
                    # Non-fatal - game is still saved
                
                return game_id
            
            return None
        
        except Exception as e:
            print(f"Error saving game review: {e}")
            import traceback
            traceback.print_exc()
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
            return self._handle_supabase_error(e, "fetching games", [])
    
    def get_analyzed_games(self, user_id: str, limit: int = 50, include_full_review: bool = False) -> List[Dict]:
        """Get games that have been analyzed (have game_review data)
        Only returns active (non-compressed) games.
        
        Args:
            user_id: User ID
            limit: Maximum number of games
            include_full_review: If False, only fetch metadata (reduces egress by ~90%)
        """
        try:
            # Optimize query - only fetch what's needed
            if include_full_review:
                select_fields = "*"
            else:
                # Minimal fields for listing - excludes massive game_review, pgn, eval_trace, etc.
                select_fields = "id,external_id,platform,game_date,user_color,opponent_name,user_rating,opponent_rating,result,termination,time_control,time_category,opening_eco,opening_name,accuracy_overall,analyzed_at,created_at,updated_at"
            
            # NOTE: Some deployments may not have compressed_at; don't let that break requests.
            query = self.client.table("games")\
                .select(select_fields)\
                .eq("user_id", user_id)\
                .not_.is_("analyzed_at", "null")
            try:
                query = query.is_("compressed_at", "null")
            except Exception:
                pass
            result = query.order("analyzed_at", desc=True).limit(limit).execute()
            
            return result.data if result.data else []
        
        except Exception as e:
            return self._handle_supabase_error(e, "fetching analyzed games", [])
    
    def get_games_metadata_only(self, user_id: str, limit: int = 25) -> List[Dict]:
        """Get games with only metadata fields (no game_review, pgn, etc.) - for profile overview.
        Reduces egress by ~95% compared to full query.
        """
        try:
            result = self.client.table("games")\
                .select("id,external_id,platform,game_date,opponent_name,result,opening_name,opening_eco,user_rating,opponent_rating,time_control,time_category")\
                .eq("user_id", user_id)\
                .is_("archived_at", "null")\
                .or_("review_type.eq.full,review_type.is.null")\
                .order("updated_at", desc=True)\
                .limit(limit)\
                .execute()
            
            return result.data if result.data else []
        
        except Exception as e:
            return self._handle_supabase_error(e, "fetching games metadata", [])

    def get_recent_games_for_overview_snapshot(self, user_id: str, limit: int = 60) -> List[Dict]:
        """
        Fetch a small set of fields needed for the Overview snapshot.
        Includes PGN clocks + user_color for true time-style classification.
        """
        try:
            select_fields = (
                "id,game_date,created_at,updated_at,"
                "pgn,user_color,user_rating,result,opening_name,accuracy_overall,time_control"
            )
            query = self.client.table("games")\
                .select(select_fields)\
                .eq("user_id", user_id)\
                .is_("archived_at", "null")\
                .or_("review_type.eq.full,review_type.is.null")

            # Filter out compressed games unless explicitly requested (best-effort)
            try:
                query = query.is_("compressed_at", "null")
                result = query.order("updated_at", desc=True).limit(int(limit)).execute()
            except Exception as e:
                if self._is_missing_column_error(e, "compressed_at"):
                    result = self.client.table("games")\
                        .select(select_fields)\
                        .eq("user_id", user_id)\
                        .is_("archived_at", "null")\
                        .or_("review_type.eq.full,review_type.is.null")\
                        .order("updated_at", desc=True)\
                        .limit(int(limit))\
                        .execute()
                else:
                    raise

            return result.data if result.data else []
        except Exception as e:
            error_msg = str(e)
            # On timeout, return empty list to avoid blocking the request
            if "timeout" in error_msg.lower() or "ReadTimeout" in error_msg:
                print(f"[supabase] Timeout fetching games for overview snapshot (user_id={user_id[:8]}...), returning empty list")
                return []
            return self._handle_supabase_error(e, "fetching overview snapshot games", [])
    
    def get_active_reviewed_games(self, user_id: str, limit: int = 30, include_full_review: bool = False, include_compressed: bool = False) -> List[Dict]:
        """Get active (non-archived) full-review games
        
        Args:
            user_id: User ID
            limit: Maximum number of games to fetch
            include_full_review: If False, only fetch minimal fields (id, game_review.ply_records) to reduce egress
        """
        try:
            # Optimize query based on what's needed
            if include_full_review:
                # Full query - only use when absolutely necessary
                select_fields = "*"
            else:
                # Minimal query - only fetch what's needed for habits computation
                # This reduces egress significantly while still providing key metadata
                select_fields = "id,game_date,created_at,updated_at,game_review,user_rating,opponent_rating,result,time_control,opening_eco,opening_name"
            
            # Get games with full review type OR NULL (for backward compatibility with older games)
            # By default, exclude compressed games (compressed_at IS NULL)
            # PostgREST syntax: use .or_() with comma-separated filters
            # Order by updated_at or created_at to get most recent
            query = self.client.table("games")\
                .select(select_fields)\
                .eq("user_id", user_id)\
                .is_("archived_at", "null")\
                .or_("review_type.eq.full,review_type.is.null")
            
            # Filter out compressed games unless explicitly requested
            # NOTE: Some deployments may not have the compressed_at column yet.
            try:
                if not include_compressed:
                    query = query.is_("compressed_at", "null")
                result = query\
                    .order("updated_at", desc=True)\
                    .limit(limit)\
                    .execute()
            except Exception as e:
                if self._is_missing_column_error(e, "compressed_at"):
                    # Retry without compressed filter
                    result = self.client.table("games")\
                        .select(select_fields)\
                        .eq("user_id", user_id)\
                        .is_("archived_at", "null")\
                        .or_("review_type.eq.full,review_type.is.null")\
                        .order("updated_at", desc=True)\
                        .limit(limit)\
                        .execute()
                else:
                    raise
            
            games = result.data if result.data else []
            
            # Fallback: if query returns empty but we know games exist, try without review_type filter
            if not games:
                print(f"   ⚠️ [SUPABASE] No games with review_type filter, trying without filter...")
                result_fallback = self.client.table("games")\
                    .select(select_fields)\
                    .eq("user_id", user_id)\
                    .is_("archived_at", "null")\
                    .order("updated_at", desc=True)\
                    .limit(limit)\
                    .execute()
                
                all_games = result_fallback.data if result_fallback.data else []
                # Filter in Python: include games with review_type='full' or NULL
                games = [
                    g for g in all_games 
                    if g.get("review_type") in ("full", None) or g.get("review_type") is None
                ]
                print(f"   ✅ [SUPABASE] Found {len(games)} games after fallback filter")
            
            return games
        
        except Exception as e:
            # Try fallback query without review_type filter
            try:
                select_fields = "*" if include_full_review else "id,game_date,created_at,updated_at,game_review"
                result = self.client.table("games")\
                    .select(select_fields)\
                    .eq("user_id", user_id)\
                    .is_("archived_at", "null")\
                    .order("updated_at", desc=True)\
                    .limit(limit)\
                    .execute()
                
                all_games = result.data if result.data else []
                # Filter in Python
                games = [
                    g for g in all_games 
                    if g.get("review_type") in ("full", None) or g.get("review_type") is None
                ]
                return games
            except Exception as fallback_e:
                # Use centralized error handler which will suppress tracebacks for transient errors
                return self._handle_supabase_error(fallback_e, "fetching active reviewed games", [])
    
    def get_active_reviewed_games_count(self, user_id: str, include_compressed: bool = False) -> int:
        """Count active full-review games (non-compressed by default)"""
        try:
            # Build base query
            query = self.client.table("games")\
                .select("id", count="exact")\
                .eq("user_id", user_id)\
                .eq("review_type", "full")\
                .is_("archived_at", "null")\
                .not_.is_("analyzed_at", "null")

            # Try to add compressed_at filter if needed
            if not include_compressed:
                query = query.is_("compressed_at", "null")
            
            result = query.execute()
            return result.count if hasattr(result, 'count') else 0
        
        except Exception as e:
            # If compressed_at column doesn't exist, retry without that filter
            if self._is_missing_column_error(e, "compressed_at") and not include_compressed:
                try:
                    query = self.client.table("games")\
                        .select("id", count="exact")\
                        .eq("user_id", user_id)\
                        .eq("review_type", "full")\
                        .is_("archived_at", "null")\
                        .not_.is_("analyzed_at", "null")
                    result = query.execute()
                    return result.count if hasattr(result, 'count') else 0
                except Exception as e2:
                    return self._handle_supabase_error(e2, "counting active reviewed games", 0)
            else:
                return self._handle_supabase_error(e, "counting active reviewed games", 0)
    
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
            return self._handle_supabase_error(e, "archiving oldest game", None)
    
    def clear_all_games(self, user_id: str) -> int:
        """Delete all games for a user (for fresh start). Returns count deleted."""
        try:
            # Get all game IDs first
            result = self.client.table("games")\
                .select("id")\
                .eq("user_id", user_id)\
                .execute()
            
            if not result.data:
                return 0
            
            count = len(result.data)
            
            # Delete all games
            self.client.table("games")\
                .delete()\
                .eq("user_id", user_id)\
                .execute()
            
            print(f"   🗑️  Deleted {count} games for user {user_id}")
            return count
        
        except Exception as e:
            return self._handle_supabase_error(e, "clearing games", 0)
    
    def get_games_needing_analysis(self, user_id: str, limit: int = 30) -> Dict:
        """
        Get stats about games needing analysis - stateless check against Supabase.
        Returns: {
            'analyzed_count': int,  # Games with analyzed_at set
            'analyzed_with_tags': int,  # Games with tags in ply_records
            'needs_analysis': int,  # Games needing analysis (no analyzed_at or no tags)
            'target': int,  # Target number (30)
            'external_ids_analyzed': set  # External IDs of already-analyzed games
        }
        """
        try:
            # Get all active games
            result = self.client.table("games")\
                .select("id, external_id, analyzed_at, game_review")\
                .eq("user_id", user_id)\
                .eq("review_type", "full")\
                .is_("archived_at", "null")\
                .limit(limit + 10)\
                .execute()
            
            if not result.data:
                return {
                    'analyzed_count': 0,
                    'analyzed_with_tags': 0,
                    'needs_analysis': limit,
                    'target': limit,
                    'external_ids_analyzed': set()
                }
            
            analyzed_count = 0
            analyzed_with_tags = 0
            external_ids_analyzed = set()
            
            for game in result.data:
                has_analyzed_at = game.get('analyzed_at') is not None
                
                # Check for tags
                game_review = game.get('game_review') or {}
                plys = game_review.get('ply_records', []) if isinstance(game_review, dict) else []
                has_tags = any(
                    len(p.get('analyse', {}).get('tags', [])) > 0
                    for p in plys if isinstance(p, dict)
                )
                
                if has_analyzed_at:
                    analyzed_count += 1
                    ext_id = game.get('external_id')
                    if ext_id:
                        external_ids_analyzed.add(str(ext_id))
                
                if has_analyzed_at and has_tags:
                    analyzed_with_tags += 1
            
            return {
                'analyzed_count': analyzed_count,
                'analyzed_with_tags': analyzed_with_tags,
                'needs_analysis': max(0, limit - analyzed_with_tags),
                'target': limit,
                'external_ids_analyzed': external_ids_analyzed
            }
        
        except Exception as e:
            print(f"Error checking games needing analysis: {e}")
            return {
                'analyzed_count': 0,
                'analyzed_with_tags': 0,
                'needs_analysis': limit,
                'target': limit,
                'external_ids_analyzed': set()
            }
    
    def mark_games_for_reanalysis(self, user_id: str, limit: int = 30) -> int:
        """Mark games for re-analysis by clearing analyzed_at timestamp.
        This allows games to be re-analyzed with new analysis features (e.g., tag computation).
        Returns count of games marked."""
        try:
            # Get games to mark
            result = self.client.table("games")\
                .select("id")\
                .eq("user_id", user_id)\
                .eq("review_type", "full")\
                .is_("archived_at", "null")\
                .not_.is_("analyzed_at", "null")\
                .limit(limit)\
                .execute()
            
            if not result.data:
                return 0
            
            game_ids = [g["id"] for g in result.data]
            
            # Update games to clear analyzed_at
            for game_id in game_ids:
                self.client.table("games")\
                    .update({"analyzed_at": None})\
                    .eq("id", game_id)\
                    .execute()
            
            print(f"   🔄 Marked {len(game_ids)} games for re-analysis")
            return len(game_ids)
        
        except Exception as e:
            print(f"Error marking games for re-analysis: {e}")
            return 0
    
    def save_moves_from_ply_records(
        self, 
        game_id: str, 
        user_id: str, 
        ply_records: List[Dict]
    ) -> int:
        """
        Extract and save moves from ply_records to moves_raw table.
        Also normalizes tags and populates move_metrics.
        Returns count of moves saved.
        """
        if not ply_records:
            return 0
        
        saved_count = 0
        try:
            # Use RPC to handle the complex logic server-side
            # This is more efficient than individual inserts
            result = self.client.rpc("backfill_moves_raw", {
                "p_user_id": user_id
            }).execute()
            
            # If RPC doesn't work, fall back to direct inserts
            # But first check if moves already exist for this game
            existing_check = self.client.table("moves_raw")\
                .select("id")\
                .eq("game_id", game_id)\
                .limit(1)\
                .execute()
            
            if existing_check.data:
                # Moves already exist, skip
                return len(existing_check.data)
            
            # Insert moves one by one (fallback if RPC unavailable)
            for record in ply_records:
                try:
                    # Extract data from ply record
                    engine = record.get("engine", {})
                    analyse = record.get("analyse", {})
                    
                    # Calculate deltas
                    eval_before = engine.get("eval_before_cp")
                    eval_after = engine.get("played_eval_after_cp")
                    best_eval_after = engine.get("best_eval_after_cp")
                    cp_loss = record.get("cp_loss", 0)
                    
                    eval_delta = (eval_after - eval_before) if (eval_before is not None and eval_after is not None) else None
                    best_delta = (best_eval_after - eval_before) if (eval_before is not None and best_eval_after is not None) else None
                    delta_vs_best = cp_loss if cp_loss else ((eval_after - best_eval_after) if (eval_after is not None and best_eval_after is not None) else None)
                    
                    # Determine category flags
                    category = record.get("category", "")
                    is_mistake = category == "mistake"
                    is_blunder = category == "blunder"
                    is_inaccuracy = category == "inaccuracy"
                    
                    # Insert move
                    move_data = {
                        "game_id": game_id,
                        "user_id": user_id,
                        "move_number": record.get("ply", 0),
                        "ply": record.get("ply", 0),
                        "side_moved": record.get("side_moved", "white" if record.get("ply", 0) % 2 == 1 else "black"),
                        "fen_before": record.get("fen_before", ""),
                        "fen_after": record.get("fen_after"),
                        "phase": record.get("phase"),
                        "move_san": record.get("san", ""),
                        "move_uci": record.get("uci"),
                        "eval_before_cp": eval_before,
                        "eval_after_cp": eval_after,
                        "best_eval_after_cp": best_eval_after,
                        "best_move_san": engine.get("best_move_san"),
                        "best_move_uci": engine.get("best_move_uci"),
                        "accuracy": record.get("accuracy_pct"),
                        "cp_loss": cp_loss,
                        "eval_delta_cp": eval_delta,
                        "best_delta_cp": best_delta,
                        "delta_vs_best_cp": delta_vs_best,
                        "is_mistake": is_mistake,
                        "is_blunder": is_blunder,
                        "is_inaccuracy": is_inaccuracy,
                        "category": category,
                        "time_spent_s": record.get("time_spent_s")
                    }
                    
                    move_result = self.client.table("moves_raw")\
                        .insert(move_data)\
                        .execute()
                    
                    if move_result.data:
                        move_id = move_result.data[0]["id"]
                        saved_count += 1
                        
                        # Extract and normalize tags
                        tags = analyse.get("tags", [])
                        if tags:
                            for tag_name in tags:
                                if isinstance(tag_name, dict):
                                    tag_name = tag_name.get("name") or tag_name.get("tag") or tag_name.get("tag_name", "")
                                
                                if tag_name and isinstance(tag_name, str) and len(tag_name.strip()) > 0:
                                    tag_name = tag_name.strip()
                                    
                                    # Get or create tag
                                    tag_result = self.client.table("tags")\
                                        .select("id")\
                                        .eq("name", tag_name)\
                                        .maybe_single()\
                                        .execute()
                                    
                                    tag_id = None
                                    if tag_result.data:
                                        tag_id = tag_result.data["id"]
                                    else:
                                        # Create tag
                                        tag_insert = self.client.table("tags")\
                                            .insert({"name": tag_name})\
                                            .execute()
                                        if tag_insert.data:
                                            tag_id = tag_insert.data[0]["id"]
                                    
                                    # Link move to tag
                                    if tag_id:
                                        try:
                                            self.client.table("move_tags")\
                                                .insert({
                                                    "move_id": move_id,
                                                    "tag_id": tag_id
                                                })\
                                                .execute()
                                        except Exception:
                                            # Ignore duplicate key errors
                                            pass
                        
                        # Populate move_metrics
                        is_non_mistake = not (is_mistake or is_blunder or is_inaccuracy)
                        metrics_data = {
                            "move_id": move_id,
                            "eval_delta_cp": eval_delta,
                            "best_delta_cp": best_delta,
                            "delta_vs_best_cp": delta_vs_best,
                            "accuracy": record.get("accuracy_pct"),
                            "phase": record.get("phase"),
                            "is_non_mistake": is_non_mistake
                        }
                        
                        try:
                            self.client.table("move_metrics")\
                                .upsert(metrics_data)\
                                .execute()
                        except Exception as metrics_err:
                            print(f"   ⚠️ Error saving move_metrics: {metrics_err}")
                
                except Exception as move_err:
                    print(f"   ⚠️ Error saving move {record.get('ply', 'unknown')}: {move_err}")
                    continue
            
            if saved_count > 0:
                print(f"   ✅ [MOVES] Saved {saved_count} moves to moves_raw for game {game_id}")
            
            return saved_count
        
        except Exception as e:
            print(f"   ⚠️ Error in save_moves_from_ply_records: {e}")
            import traceback
            traceback.print_exc()
            return saved_count
    
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
    
    def upsert_pattern_snapshot(self, snapshot_data: Dict) -> Optional[str]:
        """Upsert daily pattern snapshot to pattern_snapshots table"""
        try:
            result = self.client.table("pattern_snapshots")\
                .upsert(snapshot_data, on_conflict="user_id,snapshot_date,pattern_type")\
                .execute()
            return result.data[0]["id"] if result.data else None
        except Exception as e:
            print(f"Error saving pattern snapshot: {e}")
            return None
    
    def get_all_profiles(self) -> List[Dict]:
        """Get all user profiles"""
        try:
            result = self.client.table("profiles").select("*").execute()
            return result.data if result.data else []
        except Exception as e:
            print(f"Error getting profiles: {e}")
            return []
    
    def get_unanalyzed_games_count(self, user_id: str) -> int:
        """Count unanalyzed games for user"""
        try:
            result = self.client.table("games")\
                .select("id", count="exact")\
                .eq("user_id", user_id)\
                .is_("analyzed_at", "null")\
                .is_("archived_at", "null")\
                .execute()
            return result.count if hasattr(result, 'count') else 0
        except Exception as e:
            print(f"Error counting unanalyzed games: {e}")
            return 0
    
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
                
                # Ensure array fields default to empty lists if not provided
                array_fields = ["tags_start", "tags_after_played", "tags_after_best", 
                               "tags_gained", "tags_lost", "tags"]
                for field in array_fields:
                    if field not in position_data:
                        position_data[field] = []
                    elif position_data[field] is None:
                        position_data[field] = []
                
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
    
    def search_user_positions(
        self, 
        user_id: str, 
        tags: Optional[List[str]] = None, 
        error_categories: Optional[List[str]] = None,
        phases: Optional[List[str]] = None,
        themes: Optional[List[str]] = None,
        mover_name: Optional[str] = None,
        tags_gained_filter: Optional[str] = None,
        tags_lost_filter: Optional[str] = None,
        tags_missed_filter: Optional[str] = None,
        min_cp_loss: Optional[float] = None,
        prioritize_fresh: bool = False,
        limit: int = 10,
        phase_filter: Optional[str] = None,
        opening_name_filter: Optional[str] = None,
        piece_type_filter: Optional[str] = None,
        time_bucket_filter: Optional[str] = None
    ) -> List[Dict]:
        """
        Search user's saved positions with filters.
        
        Args:
            tags_gained_filter: Tag name that was gained after played move
            tags_lost_filter: Tag name that was lost after played move
            tags_missed_filter: Tag name that exists in best_move but not in played move
            min_cp_loss: Minimum centipawn loss to filter by
        """
        try:
            query = self.client.table("positions").select("*").eq("user_id", user_id)
            
            if tags:
                # Use tags_start which is the new column for v3
                query = query.overlaps("tags_start", tags)
            
            if error_categories:
                query = query.in_("error_category", error_categories)
                
            if phases:
                query = query.in_("phase", phases)

            if themes:
                # themes is jsonb, searching top-level keys if they are stored as such
                # or we might need a different approach if they are nested.
                # Assuming themes is a dict of {theme_name: score}
                # For simplicity, we'll skip complex jsonb filtering for now or use a basic contains
                pass
                
            if mover_name:
                query = query.eq("mover_name", mover_name)
            
            # Tag transition filters using array contains
            if tags_gained_filter:
                # Check if tag_name is in tags_gained array
                query = query.contains("tags_gained", [tags_gained_filter])
            
            if tags_lost_filter:
                # Check if tag_name is in tags_lost array
                query = query.contains("tags_lost", [tags_lost_filter])
            
            if tags_missed_filter:
                # Check if tag_name is in tags_after_best but not in tags_after_played
                # This requires a more complex query - we'll filter in Python after fetching
                # For now, we'll use contains on tags_after_best and filter client-side
                query = query.contains("tags_after_best", [tags_missed_filter])
            
            if min_cp_loss is not None:
                query = query.gte("cp_loss", min_cp_loss)
            
            # Order by freshness if requested (unseen/oldest first), otherwise by CP loss
            if prioritize_fresh:
                # Fetch more positions to sort properly (Supabase doesn't support NULLS FIRST)
                result = query.order("cp_loss", desc=True).limit(limit * 3).execute()
                positions_raw = result.data if result.data else []
                # Sort in Python to handle NULLS FIRST properly
                positions_raw.sort(key=lambda p: (
                    p.get("last_used_in_drill") is not None,  # False (None) comes first
                    p.get("last_used_in_drill") or datetime.min.replace(tzinfo=None),  # Then by date (oldest first)
                    -p.get("cp_loss", 0)  # Then by CP loss descending
                ))
                positions = positions_raw[:limit]
            else:
                result = query.order("cp_loss", desc=True).limit(limit).execute()
                positions = result.data if result.data else []
            
            # Post-process for tags_missed_filter (check that tag is NOT in tags_after_played)
            if tags_missed_filter and positions:
                filtered_positions = []
                for pos in positions:
                    tags_after_played = pos.get("tags_after_played", [])
                    if tags_missed_filter not in tags_after_played:
                        filtered_positions.append(pos)
                positions = filtered_positions
            
            return positions
            
        except Exception as e:
            print(f"Error searching positions: {e}")
            return []
    
    def count_user_positions(
        self,
        user_id: str,
        tags_gained_filter: Optional[str] = None,
        tags_lost_filter: Optional[str] = None,
        tags_missed_filter: Optional[str] = None,
        min_cp_loss: Optional[float] = None,
        error_categories: Optional[List[str]] = None,
        phase_filter: Optional[str] = None,
        opening_name_filter: Optional[str] = None,
        piece_type_filter: Optional[str] = None,
        time_bucket_filter: Optional[str] = None
    ) -> Dict[str, int]:
        """Count total available positions matching filters."""
        try:
            query = self.client.table("positions").select("id", count="exact").eq("user_id", user_id)
            
            if error_categories:
                query = query.in_("error_category", error_categories)
            
            if tags_gained_filter:
                query = query.contains("tags_gained", [tags_gained_filter])
            
            if tags_lost_filter:
                query = query.contains("tags_lost", [tags_lost_filter])
            
            if tags_missed_filter:
                query = query.contains("tags_after_best", [tags_missed_filter])
            
            if min_cp_loss is not None:
                query = query.gte("cp_loss", min_cp_loss)
            
            # Phase filter (single value)
            if phase_filter:
                query = query.eq("phase", phase_filter)
            
            # Opening name filter (case-insensitive)
            if opening_name_filter:
                query = query.ilike("opening_name", f"%{opening_name_filter}%")
            
            # Piece type filter (filter by piece_blundered)
            if piece_type_filter:
                query = query.eq("piece_blundered", piece_type_filter)
            
            # Time bucket filter
            if time_bucket_filter:
                TIME_BUCKET_RANGES = {
                    "<5s": (0, 5),
                    "5-15s": (5, 15),
                    "15-30s": (15, 30),
                    "30s-1min": (30, 60),
                    "1min-2min30": (60, 150),
                    "2min30-5min": (150, 300),
                    "5min+": (300, float('inf'))
                }
                if time_bucket_filter in TIME_BUCKET_RANGES:
                    min_time, max_time = TIME_BUCKET_RANGES[time_bucket_filter]
                    query = query.gte("time_spent_s", min_time)
                    if max_time != float('inf'):
                        query = query.lt("time_spent_s", max_time)
            
            result = query.execute()
            count = result.count if hasattr(result, 'count') else len(result.data) if result.data else 0
            
            # For tags_missed_filter, we need to filter out positions where tag is in tags_after_played
            if tags_missed_filter and result.data:
                filtered_count = sum(1 for pos in result.data 
                                   if tags_missed_filter not in (pos.get("tags_after_played") or []))
                count = filtered_count
            
            return {"count": count}
        except Exception as e:
            print(f"Error counting positions: {e}")
            return {"count": 0}
    
    def mark_positions_used(self, position_ids: List[str]) -> bool:
        """Mark positions as used by updating last_used_in_drill timestamp."""
        if not position_ids:
            return True
        try:
            from datetime import datetime
            now = datetime.utcnow().isoformat() + "Z"
            
            # Update in batches to avoid query size limits
            batch_size = 100
            for i in range(0, len(position_ids), batch_size):
                batch = position_ids[i:i + batch_size]
                self.client.table("positions")\
                    .update({"last_used_in_drill": now})\
                    .in_("id", batch)\
                    .execute()
            
            return True
        except Exception as e:
            print(f"Error marking positions as used: {e}")
            return False

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
    # LEARNING LOGGING (interaction-level, learning-first)
    # ============================================================================

    def upsert_learning_interaction(self, payload: Dict[str, Any]) -> bool:
        """Upsert a learning_interactions row by interaction_id (best-effort)."""
        try:
            self.client.table("learning_interactions").upsert(payload).execute()
            return True
        except Exception as e:
            print(f"⚠️  [LEARNING_LOG] Failed to upsert learning_interactions: {e}")
            return False

    def upsert_learning_engine_truth(self, payload: Dict[str, Any]) -> bool:
        """Upsert a learning_engine_truth row by interaction_id (best-effort)."""
        try:
            self.client.table("learning_engine_truth").upsert(payload).execute()
            return True
        except Exception as e:
            print(f"⚠️  [LEARNING_LOG] Failed to upsert learning_engine_truth: {e}")
            return False

    def upsert_learning_tag_trace(self, payload: Dict[str, Any]) -> bool:
        """Upsert a learning_tag_traces row by interaction_id (best-effort)."""
        try:
            self.client.table("learning_tag_traces").upsert(payload).execute()
            return True
        except Exception as e:
            print(f"⚠️  [LEARNING_LOG] Failed to upsert learning_tag_traces: {e}")
            return False

    def upsert_learning_llm_meta(self, payload: Dict[str, Any]) -> bool:
        """Upsert a learning_llm_response_meta row by interaction_id (best-effort)."""
        try:
            self.client.table("learning_llm_response_meta").upsert(payload).execute()
            return True
        except Exception as e:
            print(f"⚠️  [LEARNING_LOG] Failed to upsert learning_llm_response_meta: {e}")
            return False

    def upsert_learning_user_behavior(self, payload: Dict[str, Any]) -> bool:
        """Upsert a learning_user_behavior row by interaction_id (best-effort)."""
        try:
            self.client.table("learning_user_behavior").upsert(payload).execute()
            return True
        except Exception as e:
            print(f"⚠️  [LEARNING_LOG] Failed to upsert learning_user_behavior: {e}")
            return False

    def insert_learning_event(self, payload: Dict[str, Any]) -> bool:
        """Insert a learning_events row (append-only; best-effort)."""
        try:
            self.client.table("learning_events").insert(payload).execute()
            return True
        except Exception as e:
            print(f"⚠️  [LEARNING_LOG] Failed to insert learning_events: {e}")
            return False
    
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

    def get_lifetime_stats_v2(self, user_id: str) -> Dict:
        """Get lifetime stats computed via SQL RPC"""
        try:
            result = self.client.rpc("get_lifetime_stats_v2", {
                "p_user_id": user_id
            }).execute()
            return result.data if result.data else {}
        except Exception as e:
            print(f"Error calling get_lifetime_stats_v2: {e}")
            return {}

    def get_advanced_patterns_v2(self, user_id: str) -> Dict:
        """Get advanced patterns computed via SQL RPC"""
        try:
            result = self.client.rpc("get_advanced_patterns_v2", {
                "p_user_id": user_id
            }).execute()
            return result.data if result.data else {}
        except Exception as e:
            print(f"Error calling get_advanced_patterns_v2: {e}")
            return {}

    def get_strength_profile_v2(self, user_id: str) -> Dict:
        """Get strength profile computed via SQL RPC"""
        try:
            result = self.client.rpc("get_strength_profile_v2", {
                "p_user_id": user_id
            }).execute()
            return result.data if result.data else {}
        except Exception as e:
            print(f"Error calling get_strength_profile_v2: {e}")
            return {}

    def get_lifetime_stats_v3(self, user_id: str) -> Dict:
        """Get lifetime stats computed via SQL RPC v3 (includes scatter plot)"""
        try:
            result = self.client.rpc("get_lifetime_stats_v3", {
                "p_user_id": user_id
            }).execute()
            return result.data if result.data else {}
        except Exception as e:
            print(f"Error calling get_lifetime_stats_v3: {e}")
            return {}

    def get_advanced_patterns_v3(self, user_id: str) -> Dict:
        """Get advanced patterns computed via SQL RPC v3 (includes transitions)"""
        try:
            result = self.client.rpc("get_advanced_patterns_v3", {
                "p_user_id": user_id
            }).execute()
            return result.data if result.data else {}
        except Exception as e:
            print(f"Error calling get_advanced_patterns_v3: {e}")
            return {}

    def get_strength_profile_v3(self, user_id: str) -> Dict:
        """Get strength profile computed via SQL RPC v3 (includes relevance insights)"""
        try:
            result = self.client.rpc("get_strength_profile_v3", {
                "p_user_id": user_id
            }).execute()
            return result.data if result.data else {}
        except Exception as e:
            print(f"Error calling get_strength_profile_v3: {e}")
            return {}

    def get_lifetime_stats_v4(self, user_id: str) -> Dict:
        """Get lifetime stats computed via SQL RPC v4 (uses materialized views)"""
        try:
            result = self.client.rpc("get_lifetime_stats_v4", {
                "p_user_id": user_id
            }).execute()
            return result.data if result.data else {}
        except Exception as e:
            print(f"Error calling get_lifetime_stats_v4: {e}")
            # Fallback to v3 if v4 not available
            return self.get_lifetime_stats_v3(user_id)

    def get_advanced_patterns_v4(self, user_id: str) -> Dict:
        """Get advanced patterns computed via SQL RPC v4 (uses materialized views)"""
        try:
            result = self.client.rpc("get_advanced_patterns_v4", {
                "p_user_id": user_id
            }).execute()
            return result.data if result.data else {}
        except Exception as e:
            print(f"Error calling get_advanced_patterns_v4: {e}")
            # Fallback to v3 if v4 not available
            return self.get_advanced_patterns_v3(user_id)

    def get_strength_profile_v4(self, user_id: str) -> Dict:
        """Get strength profile computed via SQL RPC v4 (uses materialized views)"""
        try:
            result = self.client.rpc("get_strength_profile_v4", {
                "p_user_id": user_id
            }).execute()
            return result.data if result.data else {}
        except Exception as e:
            print(f"Error calling get_strength_profile_v4: {e}")
            # Fallback to v3 if v4 not available
            return self.get_strength_profile_v3(user_id)

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
        """Upsert aggregated profile statistics - uses personal_stats table"""
        try:
            # Use personal_stats table instead of profile_stats
            # Specify on_conflict to use the unique constraint on user_id
            self.client.table("personal_stats").upsert(
                {
                    "user_id": user_id,
                    "stats": stats,
                    "updated_at": datetime.utcnow().isoformat() + "Z"
                },
                on_conflict="user_id"
            ).execute()
            return True
        except Exception as e:
            print(f"Error saving profile stats: {e}")
            return False

    def get_profile_stats(self, user_id: str) -> Dict:
        """Fetch cached profile statistics"""
        try:
            # Try personal_stats first (new table)
            result = self.client.table("personal_stats")\
                .select("*")\
                .eq("user_id", user_id)\
                .maybe_single()\
                .execute()
            if result and result.data:
                return {"stats": result.data.get("stats", {})}
        except Exception as e:
            # Fallback to old profile_stats table if it exists
            try:
                result = self.client.table("profile_stats")\
                    .select("*")\
                    .eq("user_id", user_id)\
                    .maybe_single()\
                    .execute()
                if result and result.data:
                    return result.data
            except Exception:
                pass
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
                .maybe_single()\
                .execute()
            
            if result and result.data:
                return result.data
            return None
        
        except Exception as e:
            # No stats found is OK (will trigger lazy migration)
            print(f"Error fetching personal stats (non-fatal): {e}")
            return None
    
    def update_personal_stats(self, user_id: str, stats: Dict, game_ids: List[str]) -> bool:
        """Atomic update of personal stats"""
        try:
            # Upsert stats - specify on_conflict to use the unique constraint on user_id
            self.client.table("personal_stats").upsert(
                {
                    "user_id": user_id,
                    "stats": stats,
                    "game_ids": game_ids,
                    "needs_recalc": False,
                    "last_validated_at": datetime.now().isoformat() + "Z"
                },
                on_conflict="user_id"
            ).execute()
            
            return True
        
        except Exception as e:
            print(f"Error updating personal stats: {e}")
            return False
    
    def mark_stats_for_recalc(self, user_id: str, game_ids: List[str]) -> bool:
        """Mark stats as needing recalculation"""
        try:
            self.client.table("personal_stats").upsert(
                {
                    "user_id": user_id,
                    "game_ids": game_ids,
                    "needs_recalc": True
                },
                on_conflict="user_id"
            ).execute()
            
            return True
        
        except Exception as e:
            print(f"Error marking stats for recalc: {e}")
            return False
    
    # ============================================================================
    # HABIT TRENDS (Historical snapshots for trend persistence)
    # ============================================================================
    
    def save_habit_trend_snapshots(self, user_id: str, snapshots: List[Dict]) -> bool:
        """Batch insert habit trend snapshots for a user"""
        if not snapshots:
            return True
        
        try:
            # Prepare data for batch insert
            insert_data = []
            for snapshot in snapshots:
                insert_data.append({
                    "user_id": user_id,
                    "habit_key": snapshot.get("habit_key"),
                    "habit_type": snapshot.get("habit_type"),
                    "game_id": snapshot.get("game_id"),
                    "game_date": snapshot.get("game_date"),
                    "accuracy": snapshot.get("accuracy"),
                    "win_rate": snapshot.get("win_rate"),
                    "avg_cp_loss": snapshot.get("avg_cp_loss"),
                    "error_rate": snapshot.get("error_rate"),
                    "count": snapshot.get("count", 0),
                    "baseline_accuracy": snapshot.get("baseline_accuracy"),
                    "preference_signal": snapshot.get("preference_signal"),
                    "preference_strength": snapshot.get("preference_strength"),
                })
            
            # Batch insert with smaller batches to avoid timeout (Errno 35)
            # Use smaller batches and add retry logic
            batch_size = 50  # Reduced from 500 to avoid timeouts
            for i in range(0, len(insert_data), batch_size):
                batch = insert_data[i:i + batch_size]
                max_retries = 3
                retry_count = 0
                success = False
                
                while retry_count < max_retries and not success:
                    try:
                        self.client.table("habit_trends").insert(batch).execute()
                        success = True
                    except Exception as batch_error:
                        retry_count += 1
                        error_str = str(batch_error).lower()
                        # Check if it's a transient error (Errno 35, timeout, etc.)
                        is_transient = (
                            "errno 35" in error_str or
                            "resource temporarily unavailable" in error_str or
                            "timeout" in error_str or
                            "readerror" in error_str
                        )
                        
                        if is_transient and retry_count < max_retries:
                            # Wait a bit before retry
                            import time
                            time.sleep(0.5 * retry_count)  # Exponential backoff
                            continue
                        else:
                            # Non-transient error or max retries reached
                            print(f"Error saving habit trend snapshot batch {i//batch_size + 1} (non-fatal): {batch_error}")
                            break
                
                if not success:
                    # Log but continue with next batch
                    print(f"   ⚠️ Failed to save batch {i//batch_size + 1} after {max_retries} retries")
            
            return True
        
        except Exception as e:
            # Use centralized error handler
            return self._handle_supabase_error(e, "saving habit trend snapshots", False)
    
    def get_habit_trends(self, user_id: str, habit_key: Optional[str] = None, habit_type: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """Get historical habit trend data"""
        try:
            query = self.client.table("habit_trends")\
                .select("*")\
                .eq("user_id", user_id)\
                .order("game_date", desc=True)\
                .limit(limit)
            
            if habit_key:
                query = query.eq("habit_key", habit_key)
            if habit_type:
                query = query.eq("habit_type", habit_type)
            
            result = query.execute()
            return result.data if result.data else []
        
        except Exception as e:
            print(f"Error fetching habit trends: {e}")
            return []
    
    def cleanup_old_habit_trends(self, user_id: str, before_date: str) -> int:
        """Delete habit trends older than specified date. Returns count deleted."""
        try:
            result = self.client.table("habit_trends")\
                .delete()\
                .eq("user_id", user_id)\
                .lt("game_date", before_date)\
                .execute()
            
            # Count is not directly available, but we can estimate from response
            return len(result.data) if result.data else 0
        
        except Exception as e:
            print(f"Error cleaning up old habit trends: {e}")
            return 0
    
    def get_computed_habits(self, user_id: str) -> Optional[Dict]:
        """Get computed habits from computed_habits table."""
        try:
            result = self.client.table("computed_habits")\
                .select("*")\
                .eq("user_id", user_id)\
                .maybe_single()\
                .execute()
            
            # Handle case where result is None or result.data is None
            if result and result.data:
                habits_data = result.data.get("habits_data", {})
                needs_computation = habits_data.get("needs_computation", False)
                return {
                    "habits_data": habits_data,
                    "needs_computation": needs_computation,
                    "total_games_with_tags": result.data.get("total_games_with_tags", 0),
                    "computed_at": result.data.get("computed_at"),
                    "last_game_analyzed_at": result.data.get("last_game_analyzed_at")
                }
            return None
        
        except Exception as e:
            print(f"Error fetching computed habits: {e}")
            return self._handle_supabase_error(e, "fetching computed habits", None)
    
    def save_computed_habits(self, user_id: str, habits_data: Dict) -> bool:
        """Save computed habits to computed_habits table."""
        try:
            # Remove needs_computation flag if present
            clean_habits_data = {k: v for k, v in habits_data.items() if k != "needs_computation"}
            
            # Count games with tags from the data
            total_games = habits_data.get("total_games", 0)
            
            # Get last analyzed game timestamp
            last_game = self.client.table("games")\
                .select("analyzed_at")\
                .eq("user_id", user_id)\
                .not_.is_("analyzed_at", "null")\
                .order("analyzed_at", desc=True)\
                .limit(1)\
                .maybe_single()\
                .execute()
            
            last_game_analyzed_at = last_game.data.get("analyzed_at") if last_game.data else None
            
            # Upsert computed habits
            self.client.table("computed_habits")\
                .upsert({
                    "user_id": user_id,
                    "habits_data": clean_habits_data,
                    "total_games_with_tags": total_games,
                    "computed_at": "now()",
                    "last_game_analyzed_at": last_game_analyzed_at
                })\
                .execute()
            
            print(f"   ✅ [HABITS] Saved computed habits to Supabase (habits={len(habits_data.get('habits', []))}, games={total_games})")
            return True
        
        except Exception as e:
            return self._handle_supabase_error(e, "saving computed habits", False)

    def _save_game_graph_data(self, user_id: str, game_id: str, graph_point: Dict) -> bool:
        """Save pre-computed graph data point for a game."""
        try:
            from json import dumps
            # Convert game_date string to date if needed
            game_date = graph_point.get("game_date")
            if isinstance(game_date, str) and "T" in game_date:
                game_date = game_date.split("T")[0]
            
            self.client.table("game_graph_data").upsert({
                "user_id": user_id,
                "game_id": game_id,
                "game_date": game_date,
                "result": graph_point.get("result"),
                "opening_name": graph_point.get("opening_name"),
                "opening_eco": graph_point.get("opening_eco"),
                "time_control": graph_point.get("time_control"),
                "overall_accuracy": graph_point.get("overall_accuracy"),
                "piece_accuracy": graph_point.get("piece_accuracy") or {},
                "time_bucket_accuracy": graph_point.get("time_bucket_accuracy") or {},
                "tag_transitions": graph_point.get("tag_transitions") or {"gained": {}, "lost": {}},
            }, on_conflict="user_id,game_id").execute()
            
            print(f"   ✅ [GRAPH_DATA] Saved pre-computed graph data for game {game_id}")
            return True
        except Exception as e:
            # Check if table doesn't exist yet (migration not run)
            error_str = str(e).lower()
            if "does not exist" in error_str or "relation" in error_str:
                print(f"   ⚠️ [GRAPH_DATA] Table game_graph_data not found (migration may not be run yet): {e}")
            else:
                print(f"   ⚠️ [GRAPH_DATA] Error saving graph data for game {game_id}: {e}")
            return False

    def _save_detailed_analytics_cache(self, user_id: str, analytics_data: Dict, games_count: int) -> bool:
        """Save pre-computed detailed analytics cache for a user."""
        import time
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                from datetime import datetime
                self.client.table("detailed_analytics_cache").upsert({
                    "user_id": user_id,
                    "analytics_data": analytics_data,
                    "games_count": games_count,
                    "computed_at": datetime.utcnow().isoformat() + "Z",
                }, on_conflict="user_id").execute()
                
                print(f"   ✅ [DETAILED_ANALYTICS_CACHE] Saved pre-computed detailed analytics for user {user_id} ({games_count} games)")
                return True
            except Exception as e:
                error_str = str(e).lower()
                
                # Check if table doesn't exist yet (migration not run)
                if "does not exist" in error_str or "relation" in error_str or "pgrst205" in error_str:
                    print(f"   ⚠️ [DETAILED_ANALYTICS_CACHE] Table detailed_analytics_cache not found (migration may not be run yet): {e}")
                    return False
                
                # Retry on SSL/network errors
                if "ssl" in error_str or "eof" in error_str or "connection" in error_str or "timeout" in error_str:
                    if attempt < max_retries - 1:
                        print(f"   ⚠️ [DETAILED_ANALYTICS_CACHE] Network error (attempt {attempt + 1}/{max_retries}), retrying in {retry_delay}s...")
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                        continue
                    else:
                        print(f"   ❌ [DETAILED_ANALYTICS_CACHE] Failed after {max_retries} attempts: {e}")
                        return False
                
                # Other errors - don't retry
                print(f"   ⚠️ [DETAILED_ANALYTICS_CACHE] Error saving detailed analytics cache for user {user_id}: {e}")
                return False
        
        return False

    # ============================================================================
    # INTERNAL HELPERS
    # ============================================================================
    
    def _is_cloudflare_gateway_error(self, error: Exception) -> bool:
        """Detect Cloudflare gateway/proxy errors (e.g., HTML 520 pages)."""
        text = str(error).lower()
        return "cloudflare" in text and "520" in text
    
    def _handle_supabase_error(self, error: Exception, context: str, fallback):
        """Centralised error handler that gracefully degrades on Cloudflare issues and transient network errors."""
        # Check for transient network errors (Errno 35, ReadError, etc.)
        error_str = str(error).lower()
        # Check for common PostgREST API errors that we can safely treat as "non-fatal" in dev
        # (missing migrations, statement timeouts on free tier, etc.)
        api_code = None
        try:
            if isinstance(error, APIError) and error.args:
                payload = error.args[0]
                if isinstance(payload, dict):
                    api_code = payload.get("code") or payload.get("error_code")
        except Exception:
            api_code = None

        is_transient = (
            "errno 35" in error_str or
            "resource temporarily unavailable" in error_str or
            "readerror" in error_str or
            # httpx/httpcore can sometimes throw LocalProtocolError with HTTP/2 state machine issues.
            # Treat as transient to avoid crashing user flows.
            "localprotocolerror" in error_str or
            "streaminputs.send_headers" in error_str or
            "connectionstate.closed" in error_str or
            isinstance(error, (ConnectionError, TimeoutError)) or
            self._is_cloudflare_gateway_error(error) or
            # 57014: statement timeout (often happens on large tables / slow plans)
            api_code == "57014" or
            # 42703: missing column (schema not migrated)
            api_code == "42703" or
            # PGRST202: missing function in schema cache (RPC not deployed)
            api_code == "PGRST202"
        )
        
        if is_transient:
            # Suppress traceback for known transient errors
            print(f"⚠️  Supabase transient error while {context} (non-fatal): {error}")
            return fallback
        
        # For other errors, print full traceback for debugging
        print(f"Error {context}: {error}")
        traceback.print_exc()
        return fallback

