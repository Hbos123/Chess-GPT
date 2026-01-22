"""
Account Initialization Manager
Checks all accounts to ensure they have 60 games analyzed and window maintained.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import asyncio

class AccountInitializationManager:
    def __init__(self, supabase_client, profile_indexer, game_window_manager):
        self.supabase = supabase_client
        self.profile_indexer = profile_indexer
        self.game_window_manager = game_window_manager
    
    async def check_all_accounts(self) -> Dict[str, Any]:
        """
        Check all user accounts and ensure they have 60 games analyzed.
        Returns summary of accounts checked and actions taken.
        """
        # Get all user profiles
        print(f"🔍 [ACCOUNT_CHECK] Getting all profiles...")
        profiles = self.supabase.get_all_profiles()
        print(f"📊 [ACCOUNT_CHECK] Found {len(profiles)} profiles")
        
        results = {
            "checked_at": datetime.utcnow().isoformat(),
            "accounts_checked": 0,
            "accounts_needing_analysis": [],
            "accounts_maintained": [],
            "errors": []
        }
        
        for profile in profiles:
            # Handle both formats: profile might have "id" or "user_id"
            user_id = profile.get("id") or profile.get("user_id")
            if not user_id:
                print(f"⚠️ [ACCOUNT_CHECK] Profile missing user_id: {profile}")
                continue
            
            results["accounts_checked"] += 1
            
            try:
                # Check if account has 60 games analyzed
                active_count = self.game_window_manager.count_active_games(user_id)
                print(f"📊 [ACCOUNT_CHECK] User {user_id}: {active_count} active games")
                
                if active_count < 60:
                    # Check if there are unanalyzed games
                    unanalyzed = self.supabase.get_unanalyzed_games_count(user_id)
                    print(f"📊 [ACCOUNT_CHECK] User {user_id}: {unanalyzed} unanalyzed games")
                    
                    # Check if user has accounts linked (even if no games yet)
                    has_accounts = False
                    accounts_count = 0
                    accounts_list = []
                    if self.profile_indexer:
                        prefs = self.profile_indexer.load_preferences(user_id)
                        print(f"🔍 [ACCOUNT_CHECK] Preferences loaded: {prefs is not None}")
                        if prefs and prefs.get("accounts"):
                            accounts_list = prefs["accounts"]
                            accounts_count = len(accounts_list)
                            has_accounts = accounts_count > 0
                            accounts_display = [f"{a.get('platform')}/{a.get('username')}" for a in accounts_list]
                            print(f"📋 [ACCOUNT_CHECK] Found {accounts_count} accounts in preferences: {accounts_display}")
                    
                    # Also check Supabase profile if no preferences
                    if not has_accounts and self.supabase:
                        try:
                            profile = self.supabase.get_or_create_profile(user_id)
                            if profile:
                                linked_accounts = profile.get("linked_accounts") or []
                                chesscom_username = profile.get("chesscom_username")
                                lichess_username = profile.get("lichess_username")
                                
                                print(f"🔍 [ACCOUNT_CHECK] Profile linked_accounts: {linked_accounts}")
                                print(f"🔍 [ACCOUNT_CHECK] Profile chesscom_username: {chesscom_username}")
                                print(f"🔍 [ACCOUNT_CHECK] Profile lichess_username: {lichess_username}")
                                
                                if linked_accounts:
                                    accounts_list = linked_accounts if isinstance(linked_accounts, list) else []
                                elif chesscom_username or lichess_username:
                                    accounts_list = []
                                    if chesscom_username:
                                        accounts_list.append({"platform": "chess.com", "username": chesscom_username})
                                    if lichess_username:
                                        accounts_list.append({"platform": "lichess", "username": lichess_username})
                                
                                accounts_count = len(accounts_list)
                                has_accounts = accounts_count > 0
                                accounts_display = [f"{a.get('platform')}/{a.get('username')}" for a in accounts_list]
                                print(f"📋 [ACCOUNT_CHECK] Found {accounts_count} accounts in profile: {accounts_display}")
                        except Exception as e:
                            print(f"⚠️ [ACCOUNT_CHECK] Error checking profile: {e}")
                            import traceback
                            traceback.print_exc()
                    
                    # If we have accounts but not enough games, trigger analysis
                    # This includes the case where active_count == 0 (no games yet)
                    if has_accounts:
                        should_trigger = False
                        reason = ""
                        
                        if active_count == 0:
                            should_trigger = True
                            reason = "No games analyzed yet"
                        elif unanalyzed > 0:
                            should_trigger = True
                            reason = f"{unanalyzed} unanalyzed games found"
                        elif active_count < 60:
                            # Even if no unanalyzed games, if we're below 60, try to fetch more
                            should_trigger = True
                            reason = f"Only {active_count}/60 games analyzed"
                        
                        if should_trigger:
                            print(f"✅ [ACCOUNT_CHECK] User {user_id} needs analysis:")
                            print(f"   - Active games: {active_count}/60")
                            print(f"   - Unanalyzed: {unanalyzed}")
                            print(f"   - Accounts: {accounts_count} ({'chess.com' if any(acc.get('platform') == 'chess.com' for acc in (prefs.get('accounts', []) if prefs else [])) else 'none'})")
                            print(f"   - Reason: {reason}")
                            
                            results["accounts_needing_analysis"].append({
                                "user_id": user_id,
                                "active_games": active_count,
                                "unanalyzed_games": unanalyzed,
                                "needed": 60 - active_count,
                                "has_accounts": has_accounts,
                                "accounts_count": accounts_count,
                                "reason": reason
                            })
                            
                            # Trigger analysis if profile_indexer available
                            if self.profile_indexer:
                                print(f"🚀 [ACCOUNT_CHECK] Triggering analysis for user {user_id} - {reason}")
                                await self._trigger_analysis(user_id)
                            else:
                                print(f"⚠️ [ACCOUNT_CHECK] No profile_indexer available for user {user_id}")
                    else:
                        print(f"ℹ️ [ACCOUNT_CHECK] User {user_id} has no linked accounts (active: {active_count})")
                
                # Maintain window (compress if > 60)
                compressed = await self.game_window_manager.maintain_window(user_id)
                if compressed > 0:
                    results["accounts_maintained"].append({
                        "user_id": user_id,
                        "compressed": compressed
                    })
                    
            except Exception as e:
                results["errors"].append({
                    "user_id": user_id,
                    "error": str(e)
                })
        
        return results
    
    async def _trigger_analysis(self, user_id: str):
        """Trigger profile indexing for user"""
        if not self.profile_indexer:
            print(f"⚠️ [TRIGGER_ANALYSIS] No profile_indexer available for user {user_id}")
            return
        
        print(f"🔍 [TRIGGER_ANALYSIS] Loading preferences for user {user_id}")
        # Get user preferences first
        prefs = self.profile_indexer.load_preferences(user_id)
        accounts = prefs.get("accounts", []) if prefs else []
        time_controls = prefs.get("time_controls", []) if prefs else []
        
        print(f"📋 [TRIGGER_ANALYSIS] Preferences loaded: {len(accounts)} accounts, {len(time_controls)} time controls")
        if accounts:
            # NOTE: Avoid backslashes inside f-string expressions (Python syntax error).
            account_details = [f"{a.get('platform')}/{a.get('username')}" for a in accounts]
            print(f"📋 [TRIGGER_ANALYSIS] Account details: {account_details}")
        
        # If no preferences, check Supabase profile for linked accounts
        if not accounts and self.supabase:
            try:
                print(f"🔍 [TRIGGER_ANALYSIS] No preferences found, checking Supabase profile...")
                profile = self.supabase.get_or_create_profile(user_id)
                if profile:
                    # Check for chesscom_username/lichess_username columns
                    chesscom_username = profile.get("chesscom_username")
                    lichess_username = profile.get("lichess_username")
                    
                    if chesscom_username:
                        accounts.append({"platform": "chess.com", "username": chesscom_username})
                    if lichess_username:
                        accounts.append({"platform": "lichess", "username": lichess_username})
                    
                    # Also check linked_accounts if it exists
                    linked_accounts = profile.get("linked_accounts", [])
                    if linked_accounts and isinstance(linked_accounts, list):
                        for acc in linked_accounts:
                            if isinstance(acc, dict) and acc.get("platform") and acc.get("username"):
                                # Avoid duplicates
                                if not any(a.get("platform") == acc.get("platform") and a.get("username") == acc.get("username") for a in accounts):
                                    accounts.append({
                                        "platform": acc.get("platform"),
                                        "username": acc.get("username")
                                    })
                    
                    time_controls = profile.get("time_controls", [])
                    print(f"📋 [TRIGGER_ANALYSIS] Found {len(accounts)} accounts from profile")
            except Exception as e:
                print(f"⚠️ [TRIGGER_ANALYSIS] Error getting profile for user {user_id}: {e}")
                import traceback
                traceback.print_exc()
        
        # Start indexing if we have accounts
        if accounts:
            account_list = [f"{a.get('platform')}/{a.get('username')}" for a in accounts]
            print(f"🚀 [TRIGGER_ANALYSIS] Starting indexing for user {user_id} with {len(accounts)} account(s): {account_list}")
            print(f"🔍 [TRIGGER_ANALYSIS] Profile indexer type: {type(self.profile_indexer).__name__}")
            print(f"🔍 [TRIGGER_ANALYSIS] Time controls: {time_controls}")
            try:
                await self.profile_indexer.start_indexing(
                    user_id=user_id,
                    accounts=accounts,
                    time_controls=time_controls
                )
                print(f"✅ [TRIGGER_ANALYSIS] Successfully called start_indexing for user {user_id}")
                # Check status after a brief moment
                await asyncio.sleep(0.5)
                status = self.profile_indexer.get_status(user_id)
                print(f"📊 [TRIGGER_ANALYSIS] Status after start_indexing: {status.get('state')} - {status.get('message')}")
            except Exception as e:
                print(f"❌ [TRIGGER_ANALYSIS] Error starting indexing for user {user_id}: {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"⚠️ [TRIGGER_ANALYSIS] No accounts found for user {user_id} - cannot start indexing")
            print(f"🔍 [TRIGGER_ANALYSIS] Debug: prefs={prefs}, accounts={accounts}")

