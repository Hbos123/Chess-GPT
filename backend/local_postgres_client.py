"""
Local PostgreSQL Client - Drop-in replacement for SupabaseClient
Uses direct PostgreSQL connection instead of Supabase REST API
"""

from typing import List, Dict, Any, Optional
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import os
from datetime import datetime
import json


class LocalPostgresClient:
    """
    Local PostgreSQL client that mimics SupabaseClient interface.
    Use this when SUPABASE_URL points to localhost.
    """
    
    def __init__(self, connection_string: str):
        """Initialize with PostgreSQL connection string"""
        self.conn = psycopg2.connect(connection_string)
        self.conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        print(f"✅ Local PostgreSQL client initialized: {connection_string}")
    
    def _execute_query(self, query: str, params: tuple = None) -> List[Dict]:
        """Execute SELECT query and return results as list of dicts"""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            return [dict(row) for row in cur.fetchall()]
    
    def _execute_one(self, query: str, params: tuple = None) -> Optional[Dict]:
        """Execute SELECT query and return single result"""
        results = self._execute_query(query, params)
        return results[0] if results else None
    
    def _execute_update(self, table: str, updates: Dict, where_clause: str, where_params: tuple = None) -> int:
        """Execute UPDATE query and return number of rows affected"""
        # Handle JSONB values properly (Json objects from psycopg2)
        processed_updates = {}
        for k, v in updates.items():
            # If already a Json object, use it; otherwise convert dict/list to Json
            if isinstance(v, Json):
                processed_updates[k] = v
            elif isinstance(v, (dict, list)):
                processed_updates[k] = Json(v)
            else:
                processed_updates[k] = v
        
        set_clause = ', '.join([f"{k} = %s" for k in processed_updates.keys()])
        values = list(processed_updates.values())
        if where_params:
            values.extend(where_params)
        
        query = f"UPDATE {table} SET {set_clause} WHERE {where_clause}"
        with self.conn.cursor() as cur:
            cur.execute(query, values)
            return cur.rowcount
    
    def _execute_delete(self, table: str, where_clause: str, where_params: tuple = None) -> int:
        """Execute DELETE query and return number of rows affected"""
        query = f"DELETE FROM {table} WHERE {where_clause}"
        with self.conn.cursor() as cur:
            cur.execute(query, where_params)
            return cur.rowcount
    
    def _execute_insert(self, table: str, data: Dict) -> Optional[Dict]:
        """Insert row and return inserted data"""
        columns = list(data.keys())
        values = list(data.values())
        placeholders = ', '.join(['%s'] * len(values))
        columns_str = ', '.join(columns)
        
        query = f"""
            INSERT INTO {table} ({columns_str})
            VALUES ({placeholders})
            RETURNING *
        """
        
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, values)
            result = cur.fetchone()
            return dict(result) if result else None
    
    def _execute_upsert(self, table: str, data: Dict, conflict_cols: List[str]) -> Optional[Dict]:
        """Upsert row based on conflict columns"""
        columns = list(data.keys())
        values = list(data.values())
        placeholders = ', '.join(['%s'] * len(values))
        columns_str = ', '.join(columns)
        conflict_str = ', '.join(conflict_cols)
        
        # Build UPDATE clause
        update_clause = ', '.join([f"{col} = EXCLUDED.{col}" for col in columns if col not in conflict_cols])
        
        query = f"""
            INSERT INTO {table} ({columns_str})
            VALUES ({placeholders})
            ON CONFLICT ({conflict_str}) DO UPDATE SET {update_clause}
            RETURNING *
        """
        
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, values)
            result = cur.fetchone()
            return dict(result) if result else None
    
    # ============================================================================
    # PROFILES (mimics SupabaseClient interface)
    # ============================================================================
    
    def get_or_create_profile(self, user_id: str, username: str = None) -> Dict:
        """Get or create user profile"""
        try:
            # Try to get existing profile
            query = "SELECT * FROM profiles WHERE user_id = %s"
            profile = self._execute_one(query, (user_id,))
            
            if profile:
                return profile
            
            # Create new profile - handle foreign key constraint by checking if user exists in auth.users
            # For local dev, we'll try to create the profile and handle the FK error gracefully
            try:
                profile_data = {
                    "user_id": user_id,
                    "username": username or f"user_{user_id[:8]}"
                }
                return self._execute_insert("profiles", profile_data) or {}
            except Exception as fk_error:
                # If foreign key constraint fails, try to create user in auth.users first (for local dev)
                if 'foreign key' in str(fk_error).lower() or 'user_id_fkey' in str(fk_error).lower():
                    try:
                        # Try to insert user into auth.users if it doesn't exist
                        # Local auth.users table only has: id, email, created_at
                        with self.conn.cursor() as cur:
                            cur.execute("""
                                INSERT INTO auth.users (id, email, created_at)
                                VALUES (%s, %s, now())
                                ON CONFLICT (id) DO NOTHING
                            """, (user_id, f"{user_id}@local.dev"))
                        # Retry profile creation
                        profile_data = {
                            "user_id": user_id,
                            "username": username or f"user_{user_id[:8]}"
                        }
                        return self._execute_insert("profiles", profile_data) or {}
                    except Exception as e2:
                        print(f"⚠️  Could not create user in auth.users: {e2}")
                        # Return minimal profile structure - the app should still work
                        return {"user_id": user_id, "username": username or f"user_{user_id[:8]}"}
                else:
                    raise
        except Exception as e:
            print(f"Error getting/creating profile: {e}")
            # Return minimal profile structure so app doesn't crash
            return {"user_id": user_id, "username": username or f"user_{user_id[:8]}"}
    
    def update_profile(self, user_id: str, updates: Dict) -> bool:
        """Update user profile - only updates columns that exist in the table"""
        try:
            # Get list of actual columns in profiles table
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_schema = 'public' 
                    AND table_name = 'profiles'
                """)
                existing_columns = {row[0] for row in cur.fetchall()}
            
            # Filter updates to only include existing columns
            # Also map linked_accounts to chesscom_username/lichess_username if needed
            processed_updates = {}
            for k, v in updates.items():
                # Skip columns that don't exist
                if k not in existing_columns:
                    # Handle special mappings
                    if k == "linked_accounts" and isinstance(v, list):
                        # Extract chess.com and lichess usernames from linked_accounts
                        for account in v:
                            if isinstance(account, dict):
                                platform = account.get("platform", "").lower()
                                username = account.get("username", "")
                                if platform == "chess.com" and username:
                                    if "chesscom_username" in existing_columns:
                                        processed_updates["chesscom_username"] = username
                                elif platform == "lichess" and username:
                                    if "lichess_username" in existing_columns:
                                        processed_updates["lichess_username"] = username
                    # Skip other non-existent columns (like profile_setup_complete, time_controls)
                    continue
                
                # Convert dict/list values to JSON for PostgreSQL
                if isinstance(v, (dict, list)):
                    processed_updates[k] = Json(v)
                else:
                    processed_updates[k] = v
            
            # Only update if we have valid columns
            if not processed_updates:
                print(f"⚠️  No valid columns to update for profile {user_id}")
                return False
            
            set_clause = ', '.join([f"{k} = %s" for k in processed_updates.keys()])
            values = list(processed_updates.values()) + [user_id]
            
            query = f"UPDATE profiles SET {set_clause} WHERE user_id = %s"
            with self.conn.cursor() as cur:
                cur.execute(query, values)
                return cur.rowcount > 0
        except Exception as e:
            print(f"Error updating profile: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    # ============================================================================
    # GAMES (mimics SupabaseClient interface)
    # ============================================================================
    
    def save_game_review(self, user_id: str, game_data: Dict) -> Optional[str]:
        """Save complete game review"""
        try:
            insert_data = {
                "user_id": user_id,
                "platform": game_data.get("platform"),
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
                "game_review": Json(game_data.get("game_review") or game_data),
                "review_type": game_data.get("review_type", "full"),
                "analyzed_at": datetime.utcnow().isoformat() + "Z"
            }
            
            result = self._execute_upsert(
                "games",
                insert_data,
                ["user_id", "platform", "external_id"]
            )
            
            if result:
                print(f"   ✅ Game saved with ID: {result.get('id')}")
                return str(result.get('id'))
            return None
        except Exception as e:
            print(f"Error saving game review: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def get_active_reviewed_games(self, user_id: str, limit: int = 50, include_full_review: bool = False, include_compressed: bool = False) -> List[Dict]:
        """Get active reviewed games"""
        try:
            if include_full_review:
                select_fields = "*"
            else:
                select_fields = "id,external_id,platform,game_date,user_color,opponent_name,user_rating,opponent_rating,result,termination,time_control,time_category,opening_eco,opening_name,accuracy_overall,analyzed_at,created_at,updated_at"
            
            # Check if archived_at column exists, if not, don't filter by it
            try:
                # Try query with archived_at first
                query = f"""
                    SELECT {select_fields}
                    FROM games
                    WHERE user_id = %s
                      AND analyzed_at IS NOT NULL
                      AND archived_at IS NULL
                    ORDER BY game_date DESC
                    LIMIT %s
                """
                return self._execute_query(query, (user_id, limit))
            except Exception as e:
                # If archived_at doesn't exist, query without it
                if 'archived_at' in str(e).lower():
                    query = f"""
                        SELECT {select_fields}
                        FROM games
                        WHERE user_id = %s
                          AND analyzed_at IS NOT NULL
                        ORDER BY game_date DESC
                        LIMIT %s
                    """
                    return self._execute_query(query, (user_id, limit))
                else:
                    raise
        except Exception as e:
            print(f"Error fetching games: {e}")
            return []
    
    def get_active_reviewed_games_count(self, user_id: str, include_compressed: bool = False) -> int:
        """Get count of active reviewed games"""
        try:
            # Check if archived_at column exists
            try:
                query = """
                    SELECT COUNT(*) as count
                    FROM games
                    WHERE user_id = %s
                      AND analyzed_at IS NOT NULL
                      AND archived_at IS NULL
                """
                result = self._execute_one(query, (user_id,))
                return result.get('count', 0) if result else 0
            except Exception as e:
                # If archived_at doesn't exist, query without it
                if 'archived_at' in str(e).lower():
                    query = """
                        SELECT COUNT(*) as count
                        FROM games
                        WHERE user_id = %s
                          AND analyzed_at IS NOT NULL
                    """
                    result = self._execute_one(query, (user_id,))
                    return result.get('count', 0) if result else 0
                else:
                    raise
        except Exception as e:
            print(f"Error counting games: {e}")
            return 0
    
    # Add more methods as needed - this is a minimal implementation
    # For methods not implemented, they'll return empty/default values
    
    def get_lifetime_stats_v4(self, user_id: str):
        """Call RPC function"""
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM get_lifetime_stats_v4(%s)", (user_id,))
                result = cur.fetchone()
                return dict(result) if result else {}
        except Exception as e:
            print(f"Error calling get_lifetime_stats_v4: {e}")
            return {}
    
    def get_advanced_patterns_v4(self, user_id: str):
        """Call RPC function"""
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM get_advanced_patterns_v4(%s)", (user_id,))
                result = cur.fetchone()
                return dict(result) if result else {}
        except Exception as e:
            print(f"Error calling get_advanced_patterns_v4: {e}")
            return {}
    
    def get_strength_profile_v4(self, user_id: str):
        """Call RPC function"""
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM get_strength_profile_v4(%s)", (user_id,))
                result = cur.fetchone()
                return dict(result) if result else {}
        except Exception as e:
            print(f"Error calling get_strength_profile_v4: {e}")
            return {}
    
    # ============================================================================
    # PROFILE STATS (mimics SupabaseClient interface)
    # ============================================================================
    
    def save_profile_stats(self, user_id: str, stats: Dict) -> bool:
        """Save profile statistics to personal_stats table"""
        try:
            # Check if personal_stats table exists
            try:
                stats_json = Json(stats)  # Use psycopg2's Json adapter
                result = self._execute_upsert(
                    "personal_stats",
                    {
                        "user_id": user_id,
                        "stats": stats_json,
                        "updated_at": datetime.utcnow()
                    },
                    ["user_id"]
                )
                return result is not None
            except Exception as e:
                # If table doesn't exist, create it
                if 'personal_stats' in str(e).lower() or 'does not exist' in str(e).lower():
                    print(f"⚠️  personal_stats table doesn't exist, creating it...")
                    self._create_personal_stats_table()
                    # Retry after creating table
                    stats_json = Json(stats)
                    result = self._execute_upsert(
                        "personal_stats",
                        {
                            "user_id": user_id,
                            "stats": stats_json,
                            "updated_at": datetime.utcnow()
                        },
                        ["user_id"]
                    )
                    return result is not None
                else:
                    raise
        except Exception as e:
            print(f"Error saving profile stats: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def get_profile_stats(self, user_id: str) -> Dict:
        """Get profile statistics from personal_stats table"""
        try:
            result = self._execute_one(
                "SELECT * FROM personal_stats WHERE user_id = %s",
                (user_id,)
            )
            if result:
                # Parse JSONB stats back to dict (psycopg2 handles this automatically)
                if result.get("stats"):
                    if isinstance(result["stats"], str):
                        result["stats"] = json.loads(result["stats"])
                    return result
            return {}
        except Exception as e:
            # If table doesn't exist, return empty dict
            if 'personal_stats' in str(e).lower() or 'does not exist' in str(e).lower():
                return {}
            print(f"Error getting profile stats: {e}")
            return {}
    
    def _create_personal_stats_table(self):
        """Create personal_stats table if it doesn't exist"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS public.personal_stats (
                        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                        user_id uuid NOT NULL,
                        stats jsonb NOT NULL DEFAULT '{}',
                        updated_at timestamptz DEFAULT now(),
                        created_at timestamptz DEFAULT now(),
                        CONSTRAINT unique_user_personal_stats UNIQUE (user_id)
                    );
                    
                    CREATE INDEX IF NOT EXISTS personal_stats_user_idx ON personal_stats (user_id);
                """)
                print("✅ Created personal_stats table")
        except Exception as e:
            print(f"⚠️  Error creating personal_stats table: {e}")
    
    # ============================================================================
    # Placeholder methods for other SupabaseClient methods
    # ============================================================================
    
    def get_all_profiles(self) -> List[Dict]:
        """Get all user profiles"""
        try:
            return self._execute_query("SELECT * FROM profiles")
        except Exception as e:
            print(f"Error getting profiles: {e}")
            return []
    
    def upsert_pattern_snapshot(self, snapshot_data: Dict) -> Optional[str]:
        """Upsert daily pattern snapshot to pattern_snapshots table"""
        try:
            from psycopg2.extras import Json
            # Create table if it doesn't exist
            with self.conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS public.pattern_snapshots (
                        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                        user_id uuid NOT NULL,
                        snapshot_date DATE NOT NULL,
                        pattern_type TEXT NOT NULL,
                        opening_repertoire JSONB,
                        time_management JSONB,
                        opponent_analysis JSONB,
                        clutch_performance JSONB,
                        games_count INTEGER,
                        active_games_count INTEGER,
                        compressed_games_count INTEGER,
                        created_at TIMESTAMPTZ DEFAULT NOW(),
                        updated_at TIMESTAMPTZ DEFAULT NOW(),
                        UNIQUE(user_id, snapshot_date, pattern_type)
                    );
                """)
            
            # Insert or update
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO public.pattern_snapshots (
                        user_id, snapshot_date, pattern_type,
                        opening_repertoire, time_management, opponent_analysis, clutch_performance,
                        games_count, active_games_count, compressed_games_count
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (user_id, snapshot_date, pattern_type)
                    DO UPDATE SET
                        opening_repertoire = EXCLUDED.opening_repertoire,
                        time_management = EXCLUDED.time_management,
                        opponent_analysis = EXCLUDED.opponent_analysis,
                        clutch_performance = EXCLUDED.clutch_performance,
                        games_count = EXCLUDED.games_count,
                        active_games_count = EXCLUDED.active_games_count,
                        compressed_games_count = EXCLUDED.compressed_games_count,
                        updated_at = NOW()
                    RETURNING id
                """, (
                    snapshot_data.get("user_id"),
                    snapshot_data.get("snapshot_date"),
                    snapshot_data.get("pattern_type"),
                    Json(snapshot_data.get("opening_repertoire", {})),
                    Json(snapshot_data.get("time_management", {})),
                    Json(snapshot_data.get("opponent_analysis", {})),
                    Json(snapshot_data.get("clutch_performance", {})),
                    snapshot_data.get("games_count"),
                    snapshot_data.get("active_games_count"),
                    snapshot_data.get("compressed_games_count")
                ))
                result = cur.fetchone()
                return str(result[0]) if result else None
        except Exception as e:
            print(f"Error saving pattern snapshot: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def get_compressed_games(self, user_id: str, limit: Optional[int] = None) -> List[Dict]:
        """Get compressed games (pattern_summary only) for pattern analysis"""
        try:
            # Check if pattern_summary column exists
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_schema = 'public' 
                    AND table_name = 'games' 
                    AND column_name = 'pattern_summary'
                """)
                if not cur.fetchone():
                    # Column doesn't exist yet, return empty list gracefully
                    return []
            
            query = """
                SELECT id, pattern_summary, game_date, result, user_rating, opponent_rating,
                       opening_eco, opening_name, time_control, time_category, user_color, platform, external_id
                FROM public.games
                WHERE user_id = %s AND pattern_summary IS NOT NULL
                ORDER BY game_date ASC
            """
            params = (user_id,)
            if limit:
                query += f" LIMIT {limit}"
            
            return self._execute_query(query, params)
        except Exception as e:
            print(f"⚠️ Error getting compressed games: {e}")
            return []
    
    def get_computed_habits(self, user_id: str):
        return {}
    
    def save_computed_habits(self, user_id: str, habits_data: Dict) -> bool:
        return True

