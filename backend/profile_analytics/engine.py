"""
Profile Analytics Engine - Main Orchestrator
Orchestrates advanced analytics for user profiles including lifetime stats,
pattern recognition, and strength analysis.
"""

from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import asyncio
import statistics

from profile_analytics.pattern_recognizer import PatternRecognizer
from profile_analytics.strength_analyzer import StrengthAnalyzer

class ProfileAnalyticsEngine:
    def __init__(self, supabase_client, profile_indexer=None):
        self.supabase = supabase_client
        self.indexer = profile_indexer
        self._cache = {} # Simple in-memory cache {user_id: (timestamp, data)}
        self._in_flight = {}  # Track in-flight computations {user_id: asyncio.Task}
        
        # Configurable limits to prevent database overload
        self.db_limits = {
            'max_recent_games': 50,
            'lifetime_sample_size': 200,
            'pattern_min_samples': 5,
            'cache_ttl_hours': 1 # Cache for 1 hour
        }

    def invalidate_cache(self, user_id: str) -> None:
        """Invalidate cached analytics for a user (called when new game is added)"""
        if user_id in self._cache:
            del self._cache[user_id]
            print(f"🗑️ [PROFILE_ANALYTICS_ENGINE] Cache invalidated for user_id: {user_id}")

    async def get_full_analytics(self, user_id: str) -> Dict[str, Any]:
        """
        Get comprehensive analytics for a user.
        Combines lifetime stats, patterns, and strength analysis.
        All computation is handled by Supabase SQL RPCs for maximum efficiency.
        
        Implements request deduplication: if multiple requests come in for the same
        user_id simultaneously, they will share the same computation task.
        """
        print(f"🔍 [PROFILE_ANALYTICS_ENGINE] get_full_analytics called for user_id: {user_id}")
        
        # Check cache first (1-hour TTL)
        now = datetime.now()
        if user_id in self._cache:
            timestamp, cached_data = self._cache[user_id]
            cache_age = now - timestamp
            if cache_age < timedelta(hours=self.db_limits['cache_ttl_hours']):
                print(f"💾 [PROFILE_ANALYTICS_ENGINE] Cache hit for user_id: {user_id}, age: {cache_age}")
                return cached_data
            else:
                print(f"⏰ [PROFILE_ANALYTICS_ENGINE] Cache expired for user_id: {user_id}, age: {cache_age}")
        else:
            print(f"🆕 [PROFILE_ANALYTICS_ENGINE] No cache entry for user_id: {user_id}")

        # Check if computation is already in flight - deduplicate concurrent requests
        if user_id in self._in_flight:
            print(f"⏳ [PROFILE_ANALYTICS_ENGINE] Computation already in flight for user_id: {user_id}, waiting for existing task...")
            try:
                # Wait for the in-flight computation to complete
                result = await self._in_flight[user_id]
                print(f"✅ [PROFILE_ANALYTICS_ENGINE] Got result from in-flight computation for user_id: {user_id}")
                return result
            except Exception as e:
                # If the in-flight computation failed, remove it and continue to start a new one
                print(f"⚠️ [PROFILE_ANALYTICS_ENGINE] In-flight computation failed: {e}, starting new computation")
                if user_id in self._in_flight:
                    del self._in_flight[user_id]

        # Start new computation task
        print(f"🚀 [PROFILE_ANALYTICS_ENGINE] Starting new computation task for user_id: {user_id}")
        task = asyncio.create_task(self._compute_analytics(user_id))
        self._in_flight[user_id] = task
        
        try:
            result = await task
            return result
        finally:
            # Clean up in-flight tracking (only if this is still the current task)
            if user_id in self._in_flight and self._in_flight[user_id] == task:
                del self._in_flight[user_id]
                print(f"🧹 [PROFILE_ANALYTICS_ENGINE] Cleaned up in-flight task for user_id: {user_id}")

    async def _compute_analytics(self, user_id: str) -> Dict[str, Any]:
        """
        Internal method to actually compute analytics.
        This is separated so multiple requests can share the same computation task.
        """
        print(f"🚀 [PROFILE_ANALYTICS_ENGINE] _compute_analytics starting for user_id: {user_id}")
        
        # Run RPCs in parallel with timeout to prevent hanging
        try:
            print(f"📡 [PROFILE_ANALYTICS_ENGINE] Gathering RPC results for user_id: {user_id}")
            try:
                results = await asyncio.wait_for(
                    asyncio.gather(
                        asyncio.to_thread(self.supabase.get_lifetime_stats_v4, user_id),
                        asyncio.to_thread(self.supabase.get_advanced_patterns_v4, user_id),
                        asyncio.to_thread(self.supabase.get_strength_profile_v4, user_id),
                        self._compute_rolling_window(user_id, 60),  # Now async, no need for to_thread
                        return_exceptions=True
                    ),
                    timeout=30.0
                )
            except asyncio.TimeoutError:
                print(f"⏱️ [PROFILE_ANALYTICS_ENGINE] Timeout after 30s for user_id: {user_id}")
                # Return partial results or empty structure
                return {
                    "user_id": user_id,
                    "error": "Analytics computation timed out",
                    "generated_at": datetime.now().isoformat(),
                    "lifetime_stats": {},
                    "patterns": {},
                    "strength_profile": {},
                    "rolling_window": {"status": "timeout"},
                    "deltas": {}
                }
            
            print(f"✅ [PROFILE_ANALYTICS_ENGINE] RPC calls completed for user_id: {user_id}")
            print(f"📊 [PROFILE_ANALYTICS_ENGINE] Results summary for user_id: {user_id}:")
            print(f"   - lifetime_stats: {'OK' if not isinstance(results[0], Exception) else f'ERROR: {results[0]}'}")
            print(f"   - patterns: {'OK' if not isinstance(results[1], Exception) else f'ERROR: {results[1]}'}")
            print(f"   - strength_profile: {'OK' if not isinstance(results[2], Exception) else f'ERROR: {results[2]}'}")
            print(f"   - rolling_window: {'OK' if not isinstance(results[3], Exception) else f'ERROR: {results[3]}'}")
            
            # Handle empty results - return empty dicts instead of errors if no data
            lifetime_stats = results[0] if not isinstance(results[0], Exception) else {}
            patterns = results[1] if not isinstance(results[1], Exception) else {}
            strength_profile = results[2] if not isinstance(results[2], Exception) else {}
            rolling_window = results[3] if not isinstance(results[3], Exception) else {"status": "error", "error": str(results[3])}
            
            # Log data presence
            has_lifetime = bool(lifetime_stats and isinstance(lifetime_stats, dict) and len(lifetime_stats) > 0)
            has_patterns = bool(patterns and isinstance(patterns, dict) and len(patterns) > 0)
            has_strength = bool(strength_profile and isinstance(strength_profile, dict) and len(strength_profile) > 0)
            has_rolling = bool(rolling_window and isinstance(rolling_window, dict) and rolling_window.get("status") != "error")
            
            print(f"📈 [PROFILE_ANALYTICS_ENGINE] Data presence for user_id: {user_id}:")
            print(f"   - lifetime_stats: {has_lifetime} ({len(lifetime_stats) if isinstance(lifetime_stats, dict) else 0} keys)")
            print(f"   - patterns: {has_patterns} ({len(patterns) if isinstance(patterns, dict) else 0} keys)")
            print(f"   - strength_profile: {has_strength} ({len(strength_profile) if isinstance(strength_profile, dict) else 0} keys)")
            print(f"   - rolling_window: {has_rolling} (status: {rolling_window.get('status') if isinstance(rolling_window, dict) else 'N/A'})")
            
            # If all are empty, likely no games indexed
            if not lifetime_stats and not patterns and not strength_profile:
                print(f"⚠️ [PROFILE_ANALYTICS_ENGINE] No data found for user {user_id} - games may not be indexed yet")
            
            print(f"🔨 [PROFILE_ANALYTICS_ENGINE] Computing deltas for user_id: {user_id}")
            deltas = self._compute_deltas(lifetime_stats, rolling_window)
            
            final_data = {
                "user_id": user_id,
                "generated_at": datetime.now().isoformat(),
                "lifetime_stats": lifetime_stats,
                "patterns": patterns,
                "strength_profile": strength_profile,
                "rolling_window": rolling_window,
                "deltas": deltas,
            }
            
            # Store in cache
            self._cache[user_id] = (datetime.now(), final_data)
            print(f"💾 [PROFILE_ANALYTICS_ENGINE] Cached analytics for user_id: {user_id}")
            
            print(f"✅ [PROFILE_ANALYTICS_ENGINE] Successfully generated analytics for user_id: {user_id}")
            return final_data
            
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            print(f"❌ [PROFILE_ANALYTICS_ENGINE] Error fetching analytics from Supabase for user_id: {user_id}")
            print(f"   Error: {str(e)}")
            print(f"   Traceback: {error_trace}")
            return {
                "user_id": user_id,
                "error": str(e),
                "generated_at": datetime.now().isoformat()
            }

    # ---------------------------------------------------------------------
    # Rolling window (last 60) snapshot + critical positions
    # ---------------------------------------------------------------------
    async def _compute_rolling_window(self, user_id: str, limit: int = 60) -> Dict[str, Any]:
        """
        Compute a rolling-window snapshot from the most recent reviewed games.
        This is used to show "last 60 games" behavior vs lifetime.
        """
        print(f"🪟 [PROFILE_ANALYTICS_ENGINE] Computing rolling window for user_id: {user_id}, limit: {limit}")
        try:
            # Run database query in thread pool to avoid blocking
            games = await asyncio.to_thread(
                self.supabase.get_active_reviewed_games, 
                user_id, 
                limit=limit, 
                include_full_review=False, 
                include_compressed=False
            )
            print(f"📚 [PROFILE_ANALYTICS_ENGINE] Retrieved {len(games) if games else 0} games for rolling window, user_id: {user_id}")
            if not games:
                print(f"⚠️ [PROFILE_ANALYTICS_ENGINE] No games found for rolling window, user_id: {user_id}")
                return {"status": "no_data", "games": 0}

            # Patterns (openings/time/opponents/clutch) from rolling games only
            print(f"🔍 [PROFILE_ANALYTICS_ENGINE] Computing patterns for rolling window, user_id: {user_id}")
            pattern_recognizer = PatternRecognizer(self.supabase)
            patterns = await pattern_recognizer.get_patterns(user_id, games=games)
            print(f"✅ [PROFILE_ANALYTICS_ENGINE] Patterns computed, user_id: {user_id}, keys: {list(patterns.keys()) if isinstance(patterns, dict) else 'N/A'}")

            # Strength snapshot (phase + tactical/positional + piece metrics)
            print(f"💪 [PROFILE_ANALYTICS_ENGINE] Computing strength profile for rolling window, user_id: {user_id}")
            strength_analyzer = StrengthAnalyzer(self.supabase)
            strength = await strength_analyzer.get_profile(user_id, games=games)
            print(f"✅ [PROFILE_ANALYTICS_ENGINE] Strength profile computed, user_id: {user_id}, keys: {list(strength.keys()) if isinstance(strength, dict) else 'N/A'}")

            print(f"📊 [PROFILE_ANALYTICS_ENGINE] Computing metrics for rolling window, user_id: {user_id}")
            avg_accuracy = self._avg_game_accuracy(games)
            win_rate = self._win_rate(games)
            critical = self._extract_critical_positions(games, limit=10, save_to_db=True)
            print(f"📈 [PROFILE_ANALYTICS_ENGINE] Metrics computed - accuracy: {avg_accuracy}, win_rate: {win_rate}, critical_positions: {len(critical)}, user_id: {user_id}")

            result = {
                "status": "ok",
                "window": limit,
                "games": len(games),
                "avg_accuracy": avg_accuracy,
                "win_rate": win_rate,
                "patterns": patterns if isinstance(patterns, dict) else {},
                "strength": strength if isinstance(strength, dict) else {},
                "critical_positions": critical,
            }
            print(f"✅ [PROFILE_ANALYTICS_ENGINE] Rolling window computation complete for user_id: {user_id}")
            return result
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            print(f"❌ [PROFILE_ANALYTICS_ENGINE] Error in rolling window computation for user_id: {user_id}")
            print(f"   Error: {str(e)}")
            print(f"   Traceback: {error_trace}")
            return {"status": "error", "error": str(e)}

    @staticmethod
    def _avg_game_accuracy(games: List[Dict[str, Any]]) -> Optional[float]:
        vals: List[float] = []
        for g in games:
            # Prefer DB field if present, fallback to game_review stats
            if g.get("accuracy_overall") is not None:
                try:
                    vals.append(float(g.get("accuracy_overall")))
                    continue
                except Exception:
                    pass
            review = g.get("game_review") or {}
            stats = review.get("stats") if isinstance(review, dict) else {}
            # try common locations
            for key in ("overall_accuracy",):
                if isinstance(stats, dict) and key in stats:
                    try:
                        vals.append(float(stats[key]))
                        break
                    except Exception:
                        pass
        if not vals:
            return None
        return round(statistics.mean(vals), 1)

    @staticmethod
    def _win_rate(games: List[Dict[str, Any]]) -> Optional[float]:
        wins = 0
        total = 0
        for g in games:
            result = g.get("result") or (g.get("metadata") or {}).get("result")
            if not result:
                continue
            total += 1
            if result == "win":
                wins += 1
        if total == 0:
            return None
        return round((wins / total) * 100.0, 1)

    def _extract_critical_positions(
        self, 
        games: List[Dict[str, Any]], 
        limit: int = 10,
        save_to_db: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Extract critical positions (mistake/blunder) from ply_records where available.
        Optionally saves positions to database.
        Returns a compact list for UI/training entry points.
        """
        positions: List[Tuple[float, Dict[str, Any]]] = []
        positions_to_save = []
        
        for g in games:
            review = g.get("game_review") or {}
            if not isinstance(review, dict):
                continue
            plys = review.get("ply_records", [])
            if not isinstance(plys, list):
                continue
            for ply in plys:
                if not isinstance(ply, dict):
                    continue
                category = ply.get("category") or ""
                if category not in {"mistake", "blunder"}:
                    continue
                fen = ply.get("fen_before")
                san = ply.get("san")
                if not fen or not san:
                    continue
                cp_loss = float(ply.get("cp_loss", 0) or 0)
                
                position_data = {
                    "fen_before": fen,
                    "san": san,
                    "category": category,
                    "cp_loss": round(cp_loss, 1),
                    "game_id": g.get("id"),
                    "game_date": g.get("game_date") or g.get("created_at") or g.get("updated_at"),
                }
                
                positions.append((cp_loss, position_data))
                
                # Prepare for database save
                if save_to_db:
                    # Determine side_to_move from FEN
                    fen_parts = fen.split()
                    side_to_move = "white" if len(fen_parts) > 1 and fen_parts[1] == "w" else "black"
                    
                    positions_to_save.append({
                        "fen": fen,
                        "side_to_move": side_to_move,
                        "from_game_id": g.get("id"),
                        "source_ply": ply.get("ply"),
                        "move_san": san,
                        "move_uci": ply.get("uci"),
                        "eval_cp": ply.get("engine", {}).get("eval_before_cp") if isinstance(ply.get("engine"), dict) else None,
                        "cp_loss": cp_loss,
                        "phase": ply.get("phase"),
                        "is_critical": cp_loss >= 200,
                        "error_note": f"{category.capitalize()}: {san} (cp_loss: {round(cp_loss, 1)})",
                    })
        
        # Sort by CP loss
        positions.sort(key=lambda x: x[0], reverse=True)
        top_positions = [p for _score, p in positions[:limit]]
        
        # Save to database if requested
        if save_to_db and positions_to_save and self.supabase:
            user_id = games[0].get("user_id") if games else None
            if user_id:
                # Sort positions_to_save by cp_loss and take top N
                positions_to_save.sort(key=lambda x: x.get("cp_loss", 0), reverse=True)
                for pos in positions_to_save[:limit]:
                    game_id = pos.pop("from_game_id")
                    try:
                        self.supabase.batch_upsert_positions(
                            user_id, [pos], game_id
                        )
                    except Exception as e:
                        print(f"⚠️ Error saving position to database: {e}")
        
        return top_positions

    @staticmethod
    def _compute_deltas(lifetime_stats: Dict[str, Any], rolling_window: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compute simple deltas between rolling window and lifetime values where available.
        We keep this conservative because lifetime schema comes from RPCs and may vary.
        """
        deltas: Dict[str, Any] = {}
        if not isinstance(rolling_window, dict) or rolling_window.get("status") != "ok":
            return deltas

        # Win rate delta vs any lifetime aggregate win_rate we can find
        rolling_win = rolling_window.get("win_rate")
        lifetime_win = None
        try:
            # Prefer a generic lifetime win_rate if present
            if isinstance(lifetime_stats, dict):
                lifetime_win = lifetime_stats.get("win_rate")
        except Exception:
            lifetime_win = None

        if isinstance(rolling_win, (int, float)) and isinstance(lifetime_win, (int, float)):
            deltas["win_rate_delta"] = round(float(rolling_win) - float(lifetime_win), 1)

        # Accuracy delta if lifetime has an average_accuracy field
        rolling_acc = rolling_window.get("avg_accuracy")
        lifetime_acc = lifetime_stats.get("average_accuracy") if isinstance(lifetime_stats, dict) else None
        if isinstance(rolling_acc, (int, float)) and isinstance(lifetime_acc, (int, float)):
            deltas["accuracy_delta"] = round(float(rolling_acc) - float(lifetime_acc), 1)

        return deltas

    async def get_lifetime_stats(self, user_id: str, games: List[Dict] = None) -> Dict[str, Any]:
        """Fetch lifetime stats via Supabase RPC v4 (uses materialized views)."""
        return await asyncio.to_thread(self.supabase.get_lifetime_stats_v4, user_id)

    async def get_advanced_patterns(self, user_id: str, games: List[Dict] = None) -> Dict[str, Any]:
        """Fetch advanced patterns via Supabase RPC v4 (uses materialized views)."""
        return await asyncio.to_thread(self.supabase.get_advanced_patterns_v4, user_id)

    async def get_strength_profile(self, user_id: str, games: List[Dict] = None) -> Dict[str, Any]:
        """Fetch strength profile via Supabase RPC v4 (uses materialized views)."""
        return await asyncio.to_thread(self.supabase.get_strength_profile_v4, user_id)
    
    @property
    def pattern_recognizer(self):
        """Get pattern recognizer instance"""
        from profile_analytics.pattern_recognizer import PatternRecognizer
        from services.game_window_manager import GameWindowManager
        game_window_manager = GameWindowManager(self.supabase)
        return PatternRecognizer(self.supabase, game_window_manager)

