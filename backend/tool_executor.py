"""
Tool Executor for Chat Integration
Routes and executes tool calls from LLM
"""

from typing import Dict, Any, Optional, List
import json
import os
import asyncio


def _safe_float(x, default: float = 0.0) -> float:
    """
    Convert numeric-ish values to float, defaulting on None/invalid.
    Avoids runtime crashes when formatting with :0.0f/:0.1f etc.
    """
    try:
        if x is None:
            return default
        # Avoid bool surprising formatting/comparisons
        if isinstance(x, bool):
            return float(x)
        return float(x)
    except Exception:
        return default


def translate_tag_to_natural_english(tag_name: str, context: str = "default") -> str:
    """
    Translate tag names like "tag.diagonal.d5-a2" to natural English.
    Returns phrases like "diagonal control (d5-a2 diagonal)" or "open file control"
    
    Args:
        tag_name: The tag name to translate
        context: "default", "neglected", or "hint" - affects phrasing for better natural language
    """
    if not tag_name:
        return "unknown pattern"
    
    # Remove "tag." prefix if present
    if tag_name.startswith("tag."):
        tag_name = tag_name[4:]
    
    # Handle specific patterns
    if tag_name.startswith("diagonal.open."):
        parts = tag_name.split(".")
        if "long" in parts:
            # Long diagonal
            if "a1h8" in tag_name:
                diag = "a1-h8 diagonal"
            elif "h1a8" in tag_name:
                diag = "h1-a8 diagonal"
            else:
                diag = "long diagonal"
        elif len(parts) >= 3:
            diag = f"{parts[-1]} diagonal"  # e.g., "e3-h6 diagonal"
        else:
            diag = "diagonal"
        
        # Context-specific phrasing for better natural language
        if context == "neglected":
            return f"capitalizing on the open {diag}"
        elif context == "hint":
            return f"takes advantage of the open {diag}"
        else:
            return f"open {diag}"
    
    if tag_name.startswith("diagonal.closed."):
        parts = tag_name.split(".")
        if len(parts) >= 3:
            diag = parts[-1]  # e.g., "d5-a2"
            return f"closed {diag} diagonal"
        return "closed diagonal"
    
    if tag_name.startswith("diagonal."):
        # Fallback for old format
        parts = tag_name.split(".")
        if len(parts) >= 2:
            diag = parts[-1]  # e.g., "d5-a2"
            return f"diagonal control ({diag} diagonal)"
        return "diagonal control"
    
    if tag_name.startswith("file.open."):
        file = tag_name.split(".")[-1]
        return f"open {file}-file control"
    
    if tag_name.startswith("file.semi."):
        file = tag_name.split(".")[-1]
        return f"semi-open {file}-file control"
    
    if tag_name == "rook.connected":
        return "connected rooks"
    
    if tag_name == "rook.open_file":
        return "rook on open file"
    
    if tag_name == "rook.rank7" or tag_name == "rook.seventh":
        return "rook on 7th rank"
    
    if tag_name == "bishop.pair":
        return "bishop pair advantage"
    
    if tag_name == "bishop.bad":
        return "bad bishop"
    
    if tag_name.startswith("pawn.passed"):
        return "passed pawn"
    
    if tag_name.startswith("outpost."):
        parts = tag_name.split(".")
        if len(parts) >= 2:
            piece = parts[-2] if len(parts) >= 3 else "piece"
            sq = parts[-1] if len(parts) >= 2 else ""
            return f"{piece} outpost on {sq}" if sq else f"{piece} outpost"
        return "outpost"
    
    if tag_name.startswith("center.control"):
        return "center control"
    
    if tag_name == "space.advantage":
        return "space advantage"
    
    if tag_name.startswith("king."):
        if "exposed" in tag_name:
            return "king safety"
        if "castled" in tag_name:
            return "castled king"
        if "shield" in tag_name:
            return "king shield"
        return "king safety"
    
    if tag_name.startswith("activity.mobility"):
        parts = tag_name.split(".")
        if len(parts) >= 3:
            piece = parts[-1]
            return f"{piece} mobility"
        return "piece activity"
    
    if tag_name.startswith("threat."):
        return "tactical threats"
    
    # Generic fallback: convert dots to spaces and capitalize
    return tag_name.replace(".", " ").replace("_", " ").title()


class ToolExecutor:
    """Executes tools called by LLM in chat"""
    
    def __init__(
        self,
        engine_queue,
        game_fetcher,
        position_miner,
        drill_generator,
        training_planner,
        srs_scheduler,
        supabase_client,
        openai_client,
        llm_router=None,
        game_window_manager=None,
        # Optional injected callbacks (preferred). If omitted, we fall back to importing,
        # but note: when backend is launched via `python main.py`, importing `main`
        # creates a *second module copy* (module name `main` vs `__main__`) and will
        # NOT share initialized globals like `engine_pool_instance`.
        review_game_internal_fn=None,
        analyze_fen_fn=None,
        save_error_positions_fn=None,
    ):
        self.engine_queue = engine_queue
        self.game_fetcher = game_fetcher
        self.position_miner = position_miner
        self.drill_generator = drill_generator
        self.training_planner = training_planner
        self.srs_scheduler = srs_scheduler
        self.supabase_client = supabase_client
        self.openai_client = openai_client
        self.llm_router = llm_router
        self.game_window_manager = game_window_manager
        
        # Initialize Personal Review System managers
        if supabase_client:
            from personal_stats_manager import PersonalStatsManager
            from game_archive_manager import GameArchiveManager
            self.stats_manager = PersonalStatsManager(supabase_client)
            self.archive_manager = GameArchiveManager(supabase_client, self.stats_manager)
        else:
            self.stats_manager = None
            self.archive_manager = None
        
        # Prefer injected callbacks to avoid module-duplication issues.
        self.review_game_internal = review_game_internal_fn
        self.analyze_fen = analyze_fen_fn
        self.save_error_positions = save_error_positions_fn

        # Import internal functions we need (with graceful fallback)
        # (Only used when not injected, e.g. in isolated scripts.)
        if self.review_game_internal is None or self.analyze_fen is None or self.save_error_positions is None:
            try:
                from main import _review_game_internal, analyze_fen, _save_error_positions
                self.review_game_internal = self.review_game_internal or _review_game_internal
                self.analyze_fen = self.analyze_fen or analyze_fen
                self.save_error_positions = self.save_error_positions or _save_error_positions
            except ImportError as e:
                print(f"   ⚠️ Tool executor: Some imports failed: {e}")
                self.review_game_internal = None
                self.analyze_fen = None
                self.save_error_positions = None
        
        try:
            from main import _generate_opening_lesson_internal
            self.generate_opening_lesson_internal = _generate_opening_lesson_internal
        except ImportError:
            self.generate_opening_lesson_internal = None
    
    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any], context: Dict = None, status_callback = None) -> Dict[str, Any]:
        """
        Execute a tool and return formatted result
        
        Args:
            tool_name: Name of tool to execute
            arguments: Tool parameters
            context: Conversation context (fen, pgn, mode, etc.)
            status_callback: Optional async callback for progress updates (phase, message, progress)
            
        Returns:
            Standardized result dictionary
        """
        print(f"\n🔧 TOOL CALL: {tool_name}")
        print(f"   Arguments: {json.dumps(arguments, indent=2)[:200]}...")
        
        try:
            # Route to appropriate handler
            if tool_name == "analyze_position":
                return await self._analyze_position(arguments, context)
            elif tool_name == "analyze_move":
                return await self._analyze_move(arguments, context)
            elif tool_name == "review_full_game":
                return await self._review_full_game(arguments, status_callback, context)
            elif tool_name == "fetch_and_review_games":
                return await self._fetch_and_review_games(arguments, status_callback, context)
            elif tool_name == "select_games":
                return await self._select_games(arguments, context)
            elif tool_name == "generate_training_session":
                return await self._generate_training_session(arguments)
            elif tool_name == "get_lesson":
                return await self._get_lesson(arguments)
            elif tool_name == "generate_opening_lesson":
                return await self._generate_opening_lesson(arguments, context)
            elif tool_name == "query_user_games":
                return self._query_user_games(arguments)
            elif tool_name == "get_game_details":
                return self._get_game_details(arguments)
            elif tool_name == "query_positions":
                return self._query_positions(arguments, context)
            elif tool_name == "get_training_stats":
                return self._get_training_stats(arguments)
            elif tool_name == "save_position":
                return self._save_position(arguments, context)
            elif tool_name == "create_collection":
                return self._create_collection(arguments)
            elif tool_name == "setup_position":
                return self._setup_position(arguments, context)
            elif tool_name == "set_ai_game":
                return self._set_ai_game(arguments, context)
            elif tool_name == "add_personal_review_graph":
                return await self._add_personal_review_graph(arguments, context)
            # Investigation tools
            elif tool_name == "investigate":
                return await self._investigate(arguments, context)
            elif tool_name == "web_search":
                return await self._web_search(arguments)
            elif tool_name == "multi_depth_analyze":
                return await self._multi_depth_analyze(arguments)
            elif tool_name == "engine_correlation":
                return await self._engine_correlation(arguments)
            elif tool_name == "calculate_baseline":
                return await self._calculate_baseline(arguments)
            elif tool_name == "detect_anomalies":
                return await self._detect_anomalies(arguments)
            elif tool_name == "extend_baseline_intuition":
                return await self._extend_baseline_intuition(arguments, context)
            elif tool_name == "tree_search":
                return await self._tree_search(arguments, context)
            else:
                return {"error": f"Unknown tool: {tool_name}"}
        
        except Exception as e:
            print(f"   ❌ Tool execution error: {e}")
            import traceback
            traceback.print_exc()
            return {"error": str(e), "tool": tool_name}
    
    # ========================================================================
    # HIGH-LEVEL TOOL IMPLEMENTATIONS
    # ========================================================================

    async def _extend_baseline_intuition(self, args: Dict, context: Dict) -> Dict:
        """
        Re-run baseline D2/D16 (two-pass) with higher budgets to extend PGN/tree depth.
        Deterministic: same FEN + same policy yields same structure.
        """
        fen = context.get("board_state") or args.get("fen") or context.get("fen") if context else args.get("fen")
        if not fen:
            return {"error": "No FEN provided and no current position in context"}

        from skills.baseline_intuition import run_baseline_intuition, BaselineIntuitionPolicy
        from scan_service import ScanPolicy
        from skills.motifs import MotifPolicy

        scan_pol = ScanPolicy(
            d2_depth=int(args.get("d2_depth", 2)),
            d16_depth=int(args.get("d16_depth", 16)),
            branching_limit=int(args.get("branching_limit", 6)),
            max_pv_plies=int(args.get("max_pv_plies", 24)),
            include_pgn=True,
            pgn_max_chars=int(args.get("pgn_max_chars", 24000)),
            timeout_s=float(args.get("timeout_s", 30.0)),
        )
        motif_pol = MotifPolicy(
            max_pattern_plies=int(args.get("motifs_max_pattern_plies", 5)),
            motifs_top=int(args.get("motifs_top", 40)),
            max_line_plies=int(args.get("motifs_max_line_plies", 14)),
            max_branch_lines=int(args.get("motifs_max_branch_lines", 20)),
        )
        pol = BaselineIntuitionPolicy(scan=scan_pol, motifs=motif_pol)
        baseline = await run_baseline_intuition(
            engine_pool_instance=(context.get("engine_pool_instance") if context else None) or getattr(self, "engine_pool", None),
            engine_queue=(context.get("engine_queue") if context else None) or getattr(self, "engine_queue", None),
            start_fen=fen,
            policy=pol,
        )

        return {
            "success": True,
            "fen": fen,
            "baseline_intuition": baseline,
        }
    
    async def _analyze_position(self, args: Dict, context: Dict) -> Dict:
        """
        Analyze a chess position - uses cached analysis if available, otherwise calls endpoint
        """
        # IMPORTANT: Prefer board_state from context (has full FEN with turn)
        # LLM sometimes strips turn indicator from FEN argument
        fen = context.get("board_state") or args.get("fen") or context.get("fen") if context else args.get("fen")
        if not fen:
            return {"error": "No FEN provided and no current position in context"}
        
        # CHECK FOR CACHED ANALYSIS FIRST (from auto-analysis after moves)
        # IMPORTANT: In DISCUSS/ANALYZE, cached_analysis is a legacy shortcut that can bypass
        # D2/D16 scanning. Only allow cached_analysis in PLAY/lesson/AI-game loops.
        cached_analysis = context.get("cached_analysis") if context else None
        mode = (context or {}).get("mode")
        allow_cache = str(mode).upper() == "PLAY" or bool((context or {}).get("ai_game_active") or (context or {}).get("lesson_mode"))
        if cached_analysis and allow_cache:
            print(f"   ✅ Using pre-computed analysis from cache (instant!)")
            print(f"      Eval: {cached_analysis.get('eval_cp', 0)}cp")
            return {
                "success": True,
                "fen": fen,
                "endpoint_response": cached_analysis,
                "should_trigger_ui": True,
                "eval_cp": cached_analysis.get("eval_cp", 0),
                "candidate_moves": cached_analysis.get("candidate_moves", []),
                "from_cache": True
            }
        
        # No cache - analyze now
        depth = args.get("depth", 14)  # Fast for overview - deep analysis on-demand
        lines = args.get("lines", 3)
        light_mode = args.get("light_mode", False)  # Default to full analysis (light_mode only for game review/retry)
        
        print(f"   Analyzing position via /analyze_position endpoint (depth={depth}, lines={lines}, light_mode={light_mode})")
        print(f"   FEN from args: {args.get('fen', 'none')}")
        print(f"   FEN from context.board_state: {context.get('board_state', 'none') if context else 'no context'}")
        print(f"   Using FEN: {fen}")
        
        # Call the SAME /analyze_position endpoint the UI button uses
        # Use light_mode=False by default for full analysis
        # This gives us the full structured response with candidates, themes, threats
        import aiohttp
        
        try:
            async with aiohttp.ClientSession() as session:
                # Convert all parameters to strings for query params (aiohttp requires this)
                params = {
                    "fen": fen,
                    "lines": str(lines),
                    "depth": str(depth),
                    "light_mode": "true" if light_mode else "false"  # Convert boolean to string
                }
                
                # Use BACKEND_URL or NEXT_PUBLIC_BACKEND_URL if set, otherwise default to localhost with BACKEND_PORT
                backend_url = os.getenv("BACKEND_URL") or os.getenv("NEXT_PUBLIC_BACKEND_URL")
                if not backend_url:
                    backend_port = int(os.getenv("BACKEND_PORT", "8001"))
                    backend_url = f"http://localhost:{backend_port}"
                async with session.get(
                    f"{backend_url}/analyze_position",
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        return {"error": f"Analysis failed: {error_text}"}
                    
                    result = await response.json()
                    
                    print(f"   ✅ Analysis complete via endpoint")
                    print(f"      Eval: {result.get('eval_cp', 0)}cp")
                    
                    # Return the EXACT same format the endpoint returns
                    # Frontend will know how to display this
                    return {
                        "success": True,
                        "fen": fen,
                        "endpoint_response": result,  # Full /analyze_position response
                        "should_trigger_ui": True,  # Signal to frontend
                        "eval_cp": result.get("eval_cp", 0),
                        "candidate_moves": result.get("candidate_moves", [])
                    }
        
        except Exception as e:
            print(f"   ❌ Error calling analyze_position endpoint: {e}")
            return {"error": str(e)}
    
    async def _analyze_move(self, args: Dict, context: Dict) -> Dict:
        """Analyze a specific move"""
        move_san = args.get("move_san")
        depth = args.get("depth", 14)  # Fast for overview - deep analysis on-demand
        
        # If move_san is missing but we have context.last_move, use it
        if not move_san and context:
            last_move_info = context.get("last_move")
            if last_move_info:
                move_san = last_move_info.get("move")
                print(f"   Using context.last_move.move: {move_san}")
        
        if not move_san:
            return {"error": "No move specified. Provide move_san or ensure context.last_move is available."}
        
        # Try to get FEN from args, then context.last_move, then context.fen
        fen = args.get("fen")
        
        # Priority 1: If we have last_move context and move matches (or no move specified), use fen_before
        if not fen and context:
            last_move_info = context.get("last_move")
            if last_move_info:
                move_from_context = last_move_info.get("move")
                # Use fen_before if move matches, or if no move was specified (assume last move)
                if not move_san or move_from_context == move_san or move_san == move_from_context:
                    fen = last_move_info.get("fen_before")
                    if fen:
                        print(f"   ✅ Using context.last_move.fen_before for move {move_san or move_from_context}")
        
        # Priority 2: If FEN provided in args but move doesn't match last_move, validate it
        if fen and context:
            last_move_info = context.get("last_move")
            if last_move_info and last_move_info.get("move") == move_san:
                # Prefer fen_before from context if move matches
                preferred_fen = last_move_info.get("fen_before")
                if preferred_fen:
                    print(f"   ✅ Overriding provided FEN with context.last_move.fen_before for move {move_san}")
                    fen = preferred_fen
        
        # Priority 3: Fallback to context.fen (but this is position AFTER move, so we need to reverse it)
        if not fen and context:
            current_fen = context.get("fen")
            if current_fen and last_move_info:
                # Try to use fen_before from last_move if available
                fen = last_move_info.get("fen_before")
                if fen:
                    print(f"   ✅ Using context.last_move.fen_before as fallback")
                else:
                    print(f"   ⚠️  Warning: Using context.fen (position AFTER move) - attempting to reverse...")
                    fen = current_fen  # Will try to parse, but may fail
        
        if not fen:
            return {"error": "No FEN provided. For 'rate that move' requests, ensure context.last_move is available."}
        
        # Validate FEN format (must have 6 parts)
        fen_parts = fen.strip().split()
        if len(fen_parts) < 4:
            return {"error": f"Invalid FEN format: '{fen}'. FEN must include board, turn, castling, and en passant."}
        
        print(f"   Analyzing move: {move_san} in position {fen[:60]}...")
        
        # Use analyze_move endpoint logic
        import chess
        import chess.engine
        
        try:
            board = chess.Board(fen)
        except Exception as e:
            return {"error": f"Invalid FEN: {str(e)}. FEN: {fen}"}
        
        # Parse move
        try:
            move = board.parse_san(move_san)
            if move not in board.legal_moves:
                return {"error": f"Move {move_san} is not legal in position {fen[:60]}. Legal moves: {', '.join([board.san(m) for m in list(board.legal_moves)[:5]])}..."}
        except Exception as e:
            return {"error": f"Invalid move notation '{move_san}': {str(e)}. Position: {fen[:60]}"}
        
        # Tree-first: call backend /analyze_move which is rebased to D2/D16.
        import aiohttp
        try:
            # Use BACKEND_URL or NEXT_PUBLIC_BACKEND_URL if set, otherwise default to localhost with BACKEND_PORT
            backend_url = os.getenv("BACKEND_URL") or os.getenv("NEXT_PUBLIC_BACKEND_URL")
            if not backend_url:
                backend_port = int(os.getenv("BACKEND_PORT", "8001"))
                backend_url = f"http://localhost:{backend_port}"
            async with aiohttp.ClientSession() as session:
                params = {"fen": fen, "move_san": move_san, "depth": int(depth)}
                async with session.post(
                    f"{backend_url}/analyze_move",
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=90),
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        return {"error": f"analyze_move failed: {error_text}"}
                    result = await response.json()
        except Exception as e:
            return {"error": f"Error calling analyze_move endpoint: {str(e)}"}

        # Normalize to the tool’s expected compact shape (keep keys stable for downstream formatters)
        pmr = (result or {}).get("playedMoveReport") or {}
        return {
            "success": True,
            "move": move_san,
            "is_best_move": bool(pmr.get("is_best_move") or result.get("is_best_move")),
            "quality": "d2d16",  # legacy field; callers should use d2d16 payload for detail
            "cp_loss": int(pmr.get("cp_loss") or result.get("cp_loss") or 0),
            "best_move": str(pmr.get("best_move_d16_san") or result.get("best_move_d16_san") or result.get("best_move_san") or ""),
            "eval_before": int(pmr.get("eval_before_cp") or result.get("eval_before_cp") or 0),
            "eval_after": int(pmr.get("eval_after_cp") or result.get("eval_after_cp") or 0),
            "alternatives": [],
            "endpoint_response": result,
        }

    async def _tree_search(self, args: Dict, context: Dict) -> Dict:
        """
        Search backend D2/D16 move tree via /board/tree/search.
        """
        thread_id = args.get("thread_id") or (context or {}).get("task_id") or (context or {}).get("thread_id") or (context or {}).get("session_id")
        query = args.get("query")
        limit = int(args.get("limit", 25))
        if not thread_id:
            return {"error": "tree_search requires thread_id (tab/thread id)."}
        if not query:
            return {"error": "tree_search requires query."}

        import aiohttp
        try:
            # Use BACKEND_URL or NEXT_PUBLIC_BACKEND_URL if set, otherwise default to localhost with BACKEND_PORT
            backend_url = os.getenv("BACKEND_URL") or os.getenv("NEXT_PUBLIC_BACKEND_URL")
            if not backend_url:
                backend_port = int(os.getenv("BACKEND_PORT", "8001"))
                backend_url = f"http://localhost:{backend_port}"
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{backend_url}/board/tree/search",
                    json={"thread_id": thread_id, "query": query, "limit": limit},
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        return {"error": f"tree_search failed: {error_text}"}
                    data = await response.json()
                    return {"success": True, "thread_id": thread_id, "query": query, "results": data.get("results", [])}
        except Exception as e:
            return {"error": f"tree_search error: {str(e)}"}
    
    async def _review_full_game(self, args: Dict, status_callback = None, context: Dict = None) -> Dict:
        """Review complete game with rate limiting"""
        pgn = args.get("pgn")
        if not pgn:
            return {"error": "No PGN provided"}
        
        # Get user_id from context
        user_id = None
        if context:
            user_id = context.get("user_id") or context.get("profile", {}).get("user_id")
        
        # Get IP address for anonymous users
        ip_address = context.get("ip_address") if context else None
        
        # Check subscription and rate limits
        if self.supabase_client and (user_id or ip_address):
            try:
                if user_id:
                    tier_info = self.supabase_client.get_subscription_overview(user_id)
                else:
                    # Anonymous user - default to unpaid
                    tier_info = {"tier_id": "unpaid", "tier": {"max_game_reviews_per_day": 0}}
                
                allowed, message, usage_info = self.supabase_client.check_and_increment_usage(
                    user_id, ip_address, "game_review", tier_info
                )
                
                if not allowed:
                    return {
                        "error": message,
                        "rate_limit_info": usage_info,
                        "suggestion": "Upgrade your plan to increase your daily limit."
                    }
            except Exception as e:
                print(f"   ⚠️ Rate limit check failed: {e}")
                import traceback
                traceback.print_exc()
                # Continue anyway - don't block on rate limit errors
        
        side_focus = args.get("side_focus", "both")
        depth = args.get("depth", 14)  # Fast for overview - deep analysis on-demand
        
        # Emit status if callback provided
        if status_callback:
            await status_callback("executing", "Reviewing game...", 0.0)
        
        print(f"   Reviewing full game (depth={depth}, side_focus={side_focus})")
        
        # Use the global engine (pass None to use fallback)
        result = await self.review_game_internal(pgn, side_focus, True, depth, None)
        
        if status_callback:
            await status_callback("executing", "Review complete", 1.0)
        
        if "error" in result:
            return result
        
        # Extract summary stats
        stats = result.get("stats", {})
        game_meta = result.get("game_metadata", {})
        
        summary = {
            "total_moves": game_meta.get("total_moves", 0),
            "opening": game_meta.get("opening", "Unknown"),
            "game_character": game_meta.get("game_character", "unknown"),
            "key_points": len(result.get("key_points", [])),
            "stats": stats
        }
        
        return {
            "success": True,
            "review": result,
            "summary": summary
        }

    async def _select_games(self, args: Dict, context: Dict = None) -> Dict[str, Any]:
        """
        Fetch a candidate pool of games and deterministically select specific games.
        This is intentionally *non-analytic* (no Stockfish).
        """
        username = args.get("username")
        platform = args.get("platform", "chess.com")

        # Auto-inject from context.connected_accounts if missing
        if (not username or not platform) and context:
            try:
                connected_accounts = context.get("connected_accounts", [])
                if isinstance(connected_accounts, list) and connected_accounts:
                    account = connected_accounts[0] if isinstance(connected_accounts[0], dict) else {}
                    username = username or account.get("username")
                    platform = platform or account.get("platform", "chess.com")
                    if platform in ("chesscom", "chess_com"):
                        platform = "chess.com"
                    print(f"   📎 Auto-injected from context.connected_accounts: {username} on {platform}")
            except Exception:
                pass

        missing_fields = []
        if not username:
            missing_fields.append("username")
        if not platform:
            missing_fields.append("platform")
        if missing_fields:
            return {
                "success": False,
                "error": "info_required",
                "missing_fields": missing_fields,
                "message": "Missing required fields for select_games: " + ", ".join(missing_fields),
            }

        candidate_fetch_count = int(args.get("candidate_fetch_count", 50) or 50)
        # Ensure we have a big enough pool to satisfy category slices (rapid/bullet/etc).
        # The model sometimes emits tiny values (e.g. 1–2), which makes selection look "broken".
        candidate_fetch_count = max(60, min(candidate_fetch_count, 500))
        months_back = int(args.get("months_back", 6) or 6)
        date_from = args.get("date_from")
        date_to = args.get("date_to")

        global_unique = bool(args.get("global_unique", True))
        global_limit = args.get("global_limit")
        try:
            global_limit = int(global_limit) if global_limit is not None else None
        except Exception:
            global_limit = None
        include_pgn = bool(args.get("include_pgn", False))

        requests = args.get("requests") or []
        
        # Auto-infer filters from request names (e.g., "last_rapid_game" -> time_control: "rapid")
        for req in requests:
            if not isinstance(req, dict):
                continue
            name = str(req.get("name") or "").lower()
            filters = req.get("filters") or {}
            if not isinstance(filters, dict):
                filters = {}
            
            # Time control inference from name
            if "rapid" in name and "time_control" not in filters:
                filters["time_control"] = "rapid"
            elif "bullet" in name and "time_control" not in filters:
                filters["time_control"] = "bullet"
            elif "blitz" in name and "time_control" not in filters:
                filters["time_control"] = "blitz"
            elif "classical" in name and "time_control" not in filters:
                filters["time_control"] = "classical"
            elif "daily" in name or "correspond" in name:
                if "time_control" not in filters:
                    filters["time_control"] = "daily"
            
            # Result inference from name
            if "win" in name or "won" in name:
                if "result" not in filters:
                    filters["result"] = "win"
            elif "loss" in name or "lost" in name:
                if "result" not in filters:
                    filters["result"] = "loss"
            elif "draw" in name:
                if "result" not in filters:
                    filters["result"] = "draw"
            
            # Color inference from name
            if "black" in name:
                if "color" not in filters:
                    filters["color"] = "black"
            elif "white" in name:
                if "color" not in filters:
                    filters["color"] = "white"
            
            req["filters"] = filters

        print(
            "   📋 select_games args: "
            f"username={username}, platform={platform}, candidate_fetch_count={candidate_fetch_count}, "
            f"months_back={months_back}, date_from={date_from}, date_to={date_to}, "
            f"global_unique={global_unique}, global_limit={global_limit}, requests={len(requests)}"
        )
        for i, req in enumerate(requests):
            if isinstance(req, dict):
                print(f"   📋   request[{i}]: name={req.get('name')}, filters={req.get('filters')}")

        from tools.game_filters import fetch_games_filtered
        from tools.game_select import select_games_from_candidates

        try:
            filtered = await fetch_games_filtered(
                username=username,
                platform=platform,
                date_from=date_from,
                date_to=date_to,
                months_back=months_back,
                max_games=candidate_fetch_count,
            )
        except Exception as e:
            import traceback
            print(f"[TOOL_EXECUTOR] Error calling fetch_games_filtered: {e}")
            traceback.print_exc()
            return {
                "success": False,
                "error": "fetch_failed",
                "message": f"Failed to fetch games: {str(e)}",
            }
        
        # Check for error in response
        if isinstance(filtered, dict) and filtered.get("error"):
            error_msg = filtered.get("error", "Unknown error")
            print(f"[TOOL_EXECUTOR] fetch_games_filtered returned error: {error_msg}")
            return {
                "success": False,
                "error": "fetch_failed",
                "message": f"Failed to fetch games: {error_msg}",
            }
        
        candidates = filtered.get("games", []) or []
        if not candidates:
            return {
                "success": False,
                "error": "no_games",
                "message": f"No games found for {username} on {platform}",
            }

        sel = select_games_from_candidates(
            candidates=candidates,
            username=username,
            requests=requests,
            global_unique=global_unique,
            global_limit=global_limit,
        )

        # Optionally enrich selected refs with PGN so the frontend can open a game in a new tab.
        if include_pgn:
            try:
                by_url = {}
                by_id = {}
                for g in candidates:
                    if not isinstance(g, dict):
                        continue
                    url = g.get("url")
                    gid = g.get("game_id")
                    if isinstance(url, str) and url:
                        by_url[url] = g
                    if gid is not None:
                        by_id[str(gid)] = g

                selected = sel.get("selected") if isinstance(sel, dict) else None
                if isinstance(selected, dict):
                    pgns_added = 0
                    for _, arr in selected.items():
                        if not isinstance(arr, list):
                            continue
                        for ref in arr:
                            if not isinstance(ref, dict):
                                continue
                            if ref.get("pgn"):
                                pgns_added += 1
                                continue
                            src = None
                            u = ref.get("url")
                            gid = ref.get("game_id")
                            if isinstance(u, str) and u in by_url:
                                src = by_url.get(u)
                            elif gid is not None and str(gid) in by_id:
                                src = by_id.get(str(gid))
                            if isinstance(src, dict):
                                pgn = src.get("pgn")
                                if isinstance(pgn, str) and pgn.strip():
                                    ref["pgn"] = pgn
                                    pgns_added += 1
                    print(f"[TOOL_EXECUTOR] Added PGN to {pgns_added} selected game refs")
            except Exception:
                pass

        return {
            "success": True,
            "platform": platform,
            "username": username,
            "total_candidates": sel.get("total_candidates", 0),
            "selected": sel.get("selected", {}),
            "selected_flat": sel.get("selected_flat", []),
            "unmet": sel.get("unmet", []),
        }
    
    async def _fetch_and_review_games(self, args: Dict, status_callback = None, context: Dict = None) -> Dict:
        """Workflow: Fetch + analyze games"""
        import asyncio
        
        username = args.get("username")
        platform = args.get("platform", "chess.com")
        
        # Fallback to context.connected_accounts if username/platform not provided
        if not username or not platform:
            if context:
                connected_accounts = context.get("connected_accounts", [])
                if connected_accounts:
                    account = connected_accounts[0]
                    if not username:
                        username = account.get("username")
                    if not platform:
                        platform = account.get("platform", "chess.com")
                    # Normalize platform
                    if platform in ("chesscom", "chess_com"):
                        platform = "chess.com"
                    print(f"   📎 Auto-injected from context.connected_accounts: {username} on {platform}")
        
        # Support both 'count' and 'max_games' as parameters
        max_games = args.get("count") or args.get("max_games", 5)  # Default to 5 games
        games_to_analyze = args.get("games_to_analyze", max_games)  # Analyze all fetched by default
        depth = args.get("depth", 14)  # Fast for overview - deep analysis on-demand
        query = args.get("query", "")
        time_control = args.get("time_control", "all")
        result_filter = args.get("result_filter", "all")
        review_subject = args.get("review_subject", "player")  # player|opponent|both

        # Advanced selection controls (LLM-controlled)
        months_back = int(args.get("months_back", 6) or 6)
        date_from = args.get("date_from")
        date_to = args.get("date_to")
        opponent = args.get("opponent")
        opening_eco = args.get("opening_eco")
        color = args.get("color")
        min_moves = args.get("min_moves")
        min_opponent_rating = args.get("min_opponent_rating")
        max_opponent_rating = args.get("max_opponent_rating")
        sort = (args.get("sort") or "date_desc").strip().lower()
        offset = int(args.get("offset", 0) or 0)
        
        # Get interpreter's intent (injected by main.py)
        interpreter_intent = args.get("interpreter_intent", "")
        
        # Helper to emit status updates
        async def emit_status(message: str, progress: float = None, phase: str = "executing", replace: bool = False):
            if status_callback:
                await status_callback(phase, message, progress, replace)
        
        print(
            "   📋 fetch_and_review_games args: "
            f"username={username}, platform={platform}, count={max_games}, analyze={games_to_analyze}, "
            f"time_control={time_control}, result_filter={result_filter}, months_back={months_back}, "
            f"date_from={date_from}, date_to={date_to}, opponent={opponent}, opening_eco={opening_eco}, "
            f"color={color}, offset={offset}, sort={sort}"
        )
        
        # Check if both username and platform are provided
        missing_fields = []
        if not username:
            missing_fields.append("username")
        if not platform:
            missing_fields.append("platform")
        
        if missing_fields:
            print(f"   ℹ️ Missing fields: {', '.join(missing_fields)}")
            
            # Generate appropriate message based on what's missing
            if "username" in missing_fields and "platform" in missing_fields:
                message = "I need your username and platform to fetch your games. Please provide them (e.g., 'my username is hikaru on chess.com' or 'magnus on lichess')."
            elif "username" in missing_fields:
                message = f"I need your {platform} username to fetch your games. Please provide it (e.g., 'my username is hikaru')."
            else:  # platform is missing
                message = f"I found the username '{username}', but I need to know which platform (Chess.com or Lichess). Please specify (e.g., '{username} on chess.com')."
            
            return {
                "success": False,
                "error": "info_required",
                "missing_fields": missing_fields,
                "message": message
            }
        
        print(f"   🔄 WORKFLOW: Fetch and review games for {username}")
        print(f"      Fetching {max_games} games, analyzing {games_to_analyze} at depth {depth}")
        
        # Step 1: Fetch games
        await emit_status(f"Fetching games from {platform}...", 0.0)
        print(f"📥 Fetching games for {username} from {platform}...")

        # Normalize filters for fetch_games_filtered
        tc_filter = None
        if isinstance(time_control, str) and time_control.lower() not in ("all", ""):
            tc_filter = time_control.lower()

        rf = (result_filter or "all").lower().strip() if isinstance(result_filter, str) else "all"
        if rf in ("wins", "win"):
            result_norm = "win"
        elif rf in ("losses", "loss"):
            result_norm = "loss"
        elif rf in ("draws", "draw"):
            result_norm = "draw"
        else:
            result_norm = None

        color_norm = None
        if isinstance(color, str):
            c = color.lower().strip()
            if c in ("white", "black"):
                color_norm = c

        # Fetch extra for filtering + offset
        fetch_cap = int(max_games) + int(offset)
        fetch_cap = max(1, fetch_cap)

        from tools.game_filters import fetch_games_filtered
        filtered = await fetch_games_filtered(
            username=username,
            platform=platform,
            date_from=date_from,
            date_to=date_to,
            months_back=months_back,
            opponent=opponent,
            opening_eco=opening_eco,
            time_control=tc_filter,
            result=result_norm,
            min_opponent_rating=min_opponent_rating,
            max_opponent_rating=max_opponent_rating,
            color=color_norm,
            min_moves=min_moves,
            max_games=fetch_cap,  # Respect the requested count (no forced minimum)
        )
        games = filtered.get("games", [])

        # Filter by game_id if provided
        game_id = args.get("game_id")
        if game_id:
            # Filter games to find the one matching the game_id
            matching_games = [g for g in games if str(g.get("game_id", "")) == str(game_id)]
            if matching_games:
                games = matching_games
                print(f"   ✅ Found game {game_id} in fetched games")
            else:
                print(f"   ⚠️ Game {game_id} not found in fetched games, will try to fetch it directly")
                # Try to fetch the specific game by ID if available
                # This might require a different API call depending on the platform
                # For now, we'll proceed with empty list and let the error handler catch it
        
        # Apply user-controlled sort + offset + limit
        reverse = True if sort != "date_asc" else False
        games = sorted(games, key=lambda g: (g.get("date") or ""), reverse=reverse)
        if offset:
            games = games[offset:]
        games = games[:max_games]
        
        if not games:
            if game_id:
                return {"error": f"Game {game_id} not found for {username} on {platform}"}
            return {"error": f"No games found for {username} on {platform}"}
        
        await emit_status(f"Fetched {len(games)} game(s)", 0.1)
        print(f"✅ Fetched {len(games)} games from {platform}")
        
        # Step 2: Analyze subset
        print(f"🔍 Analyzing {games_to_analyze} games with Stockfish (depth {depth})...")
        analyzed_games = []
        total_to_analyze = min(games_to_analyze, len(games))
        for idx, game in enumerate(games[:total_to_analyze]):
            # Calculate base progress for this game (10% for fetch, 80% for analysis, 10% for aggregation)
            game_start_progress = 0.1 + (0.8 * idx / total_to_analyze)
            game_end_progress = 0.1 + (0.8 * (idx + 1) / total_to_analyze)
            
            await emit_status(f"Reviewing game {idx+1}/{total_to_analyze}...", game_start_progress)
            print(f"   📊 Analyzing game {idx+1}/{total_to_analyze}...")
            
            pgn = game.get("pgn", "")
            if not pgn:
                continue
            
            # Create a move-level progress callback that scales within this game's portion
            # Need to capture idx in closure properly
            game_idx = idx
            game_total = total_to_analyze
            game_start = game_start_progress
            game_end = game_end_progress
            
            async def move_progress_callback(phase: str, message: str, move_progress: float = None, replace: bool = False):
                if move_progress is not None:
                    # Scale move progress to fit within this game's progress range
                    overall_progress = game_start + (move_progress * (game_end - game_start))
                    # Prepend game info to message
                    full_message = f"Game {game_idx+1}/{game_total}: {message}"
                    await emit_status(full_message, overall_progress, replace=replace)
                    await asyncio.sleep(0)  # Yield to allow event to be sent
            
            # Choose which side to focus review on (interpreter-driven)
            player_color = game.get("player_color", "white")
            if review_subject == "opponent":
                focus_color = "black" if player_color == "white" else "white"
            elif review_subject == "both":
                focus_color = "both"
            else:
                focus_color = player_color
            
            # Use the global engine (pass None to use fallback), with move-level callback
            review = await self.review_game_internal(pgn, focus_color, True, depth, None, move_progress_callback)
            
            print(f"      🔍 Review result for game {idx+1}: has_error={'error' in review}, keys={list(review.keys())[:5]}")
            
            if "error" in review:
                print(f"      ⚠️ Review failed for game {idx+1}: {review.get('error', 'unknown error')}")
            elif "error" not in review:
                # Preserve original PGN for time-based analysis
                review["pgn"] = pgn

                # Ensure walkthrough consumers can see who the review is about.
                # `backend/main.py` streams `first_game_review.game_metadata`, so we also mirror focus metadata there.
                if isinstance(review.get("game_metadata"), dict):
                    review["game_metadata"]["player_color"] = player_color
                    review["game_metadata"]["focus_color"] = focus_color
                    review["game_metadata"]["review_subject"] = review_subject

                review["metadata"] = {
                    "platform": game.get("platform"),
                    "player_rating": game.get("player_rating"),
                    "result": game.get("result"),
                    # Real player_color is the connected account user's side; keep it for naming/context
                    "player_color": player_color,
                    # Focus metadata tells downstream selection/UI who this review is about
                    "focus_color": focus_color,
                    "review_subject": review_subject,
                    "time_control": game.get("time_control"),  # Add time control
                    "time_category": game.get("time_category"),  # Add time category
                    "termination": game.get("termination", ""),  # Add termination (timeout, resignation, etc.)
                    "white": game.get("white"),  # Player names for tab naming
                    "black": game.get("black"),
                    "date": game.get("date")
                }
                
                # === NEW: Save game with Personal Review System ===
                if self.archive_manager and self.supabase_client:
                    try:
                        # Always use full review (light analysis removed)
                        review_type = "full"
                        
                        # Prepare game data for saving
                        game_data = {
                            **review,
                            "review_type": review_type,
                            "platform": game.get("platform"),
                            "external_id": game.get("game_id"),
                            "game_date": game.get("date"),
                            "user_color": player_color,
                            "opponent_name": game.get("opponent_name"),
                            "user_rating": game.get("player_rating"),
                            "opponent_rating": game.get("opponent_rating"),
                            "result": game.get("result"),
                            "termination": game.get("termination", ""),
                            "time_control": game.get("time_control"),
                            "time_category": game.get("time_category"),
                            "opening_eco": review.get("opening", {}).get("eco_final"),
                            "opening_name": review.get("opening", {}).get("name_final"),
                            "theory_exit_ply": review.get("opening", {}).get("theory_exit_ply"),
                            "accuracy_overall": review.get("stats", {}).get("overall_accuracy", 0),
                            "accuracy_opening": review.get("stats", {}).get("opening_accuracy", 0),
                            "accuracy_middlegame": review.get("stats", {}).get("middlegame_accuracy", 0),
                            "accuracy_endgame": review.get("stats", {}).get("endgame_accuracy", 0),
                            "avg_cp_loss": review.get("stats", {}).get("avg_cp_loss", 0),
                            "blunders": review.get("stats", {}).get("blunders", 0),
                            "mistakes": review.get("stats", {}).get("mistakes", 0),
                            "inaccuracies": review.get("stats", {}).get("inaccuracies", 0),
                            "total_moves": len(review.get("ply_records", [])) // 2,
                            "game_character": review.get("game_metadata", {}).get("game_character"),
                            "endgame_type": review.get("game_metadata", {}).get("endgame_type"),
                            "pgn": pgn,
                            "game_review": review
                        }
                        
                        # Get user_id from context or args
                        user_id = None
                        if context:
                            user_id = context.get("user_id") or context.get("profile", {}).get("user_id")
                        if not user_id:
                            user_id = args.get("user_id")
                        
                        # Skip saving if no user_id (can't save without authenticated user)
                        if not user_id:
                            print(f"      ⚠️ No user_id available, skipping Personal Review System save")
                        else:
                            # Save game with limit enforcement
                            game_id = self.archive_manager.save_game_with_limit(user_id, game_data)
                            
                            # Maintain 60-game window after saving
                            if game_id and self.game_window_manager:
                                try:
                                    await self.game_window_manager.maintain_window(user_id)
                                except Exception as window_err:
                                    print(f"      ⚠️ Error maintaining game window: {window_err}")
                            
                            if game_id and review_type == "full":
                                # Extract and save moves to normalized tables
                                ply_records = review.get("ply_records", [])
                                if ply_records and self.supabase_client:
                                    try:
                                        moves_saved = self.supabase_client.save_moves_from_ply_records(
                                            game_id,
                                            user_id,
                                            ply_records
                                        )
                                        print(f"      💾 Saved {moves_saved} moves to normalized tables")
                                    except Exception as moves_err:
                                        print(f"      ⚠️ Error saving moves to normalized tables: {moves_err}")
                                        import traceback
                                        traceback.print_exc()
                                
                                # Extract and save error positions
                                if ply_records:
                                    positions_saved = await self.save_error_positions(
                                        ply_records,
                                        game_id,
                                        user_id,
                                        self.supabase_client,
                                        focus_color
                                    )
                                    print(f"      💾 Saved {positions_saved} error positions for training")
                        
                    except Exception as e:
                        print(f"      ⚠️ Error saving game to Personal Review System: {e}")
                        import traceback
                        traceback.print_exc()
                
                analyzed_games.append(review)
                print(f"      ✅ Added review to analyzed_games (total: {len(analyzed_games)})")
                
                # Status update after completing each game
                await emit_status(f"Completed game {idx+1}/{total_to_analyze}", game_end_progress, replace=True)
                print(f"      ✅ Game {idx+1}/{total_to_analyze} complete")
                await asyncio.sleep(0)  # Yield to send event
        
        await emit_status(f"Analysis complete", 0.9, replace=True)
        print(f"      ✅ Analyzed {len(analyzed_games)} games")
        print(f"      🔍 Final analyzed_games length: {len(analyzed_games)}, games fetched: {len(games)}")
        
        # Step 3: Always aggregate for conversational output
        if len(analyzed_games) > 0:
            # Import aggregator and key moment selector
            from personal_review_aggregator import PersonalReviewAggregator
            from key_moment_selector import (
                select_key_moments_by_statistics,
                diagnose_loss_type,
                detect_all_key_moments
            )
            import concurrent.futures
            
            aggregator = PersonalReviewAggregator()
            
            await emit_status(f"Computing statistics...", 0.91, replace=True)
            await asyncio.sleep(0)  # Yield to send status
            
            # Run CPU-bound aggregation in thread pool to not block event loop
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor() as pool:
                # For aggregation we want stats for the *focus_color*, not always the connected user's color.
                # Do this via a shallow copy so we don't break tab naming or other metadata consumers.
                games_for_aggregation = []
                for g in analyzed_games:
                    meta = dict(g.get("metadata", {}) or {})
                    focus = meta.get("focus_color") or meta.get("player_color", "white")
                    if focus in ["white", "black"]:
                        meta["player_color"] = focus
                    g2 = dict(g)
                    g2["metadata"] = meta
                    games_for_aggregation.append(g2)
                aggregated = await loop.run_in_executor(
                    pool, 
                    aggregator.aggregate, 
                    games_for_aggregation, 
                    {}, 
                    None
                )
            
            await emit_status(f"Building performance report...", 0.93, replace=True)
            await asyncio.sleep(0)  # Yield to send status
            
            # === NEW: Statistics-first key moment selection ===
            first_game = analyzed_games[0] if analyzed_games else None
            first_game_meta = first_game.get("metadata", {}) if first_game else {}
            # Select moments for the focused side (player/opponent/both)
            player_color = first_game_meta.get("focus_color", first_game_meta.get("player_color", "white"))
            game_result = first_game_meta.get("result", "")
            # Prefer the original user question (provided by interpreter as tool arg `query`);
            # fall back to interpreter intent summary if needed.
            user_query = (args.get("query") or "").strip() or (interpreter_intent or "")
            
            # Get all key moments from first game (or combine from all games)
            all_key_moments = first_game.get("all_key_moments", []) if first_game else []
            if not all_key_moments and first_game:
                # Fallback: detect from ply records if not already present
                all_key_moments = detect_all_key_moments(
                    first_game.get("ply_records", []),
                    player_color
                )
            
            await emit_status(f"Selecting key moments...", 0.95, replace=True)
            await asyncio.sleep(0)
            
            # Extract ply_records for query interpretation
            first_game_ply_records = first_game.get("ply_records", []) if first_game else []
            
            # Select key moments using LLM-based selection (handles ANY query flexibly)
            selected_moments, selection_rationale = await select_key_moments_by_statistics(
                all_key_moments=all_key_moments,
                statistics=aggregated,
                user_query=user_query,
                game_result=game_result,
                player_color=player_color,
                total_games=len(analyzed_games),
                ply_records=first_game_ply_records,
                game_metadata=first_game_meta,
                interpreter_intent=interpreter_intent,
                openai_client=self.openai_client  # Pass client for LLM-based selection
            )

            # Include review_subject/focus in rationale so frontend can render policy (retry vs highlight, etc.)
            if isinstance(selection_rationale, dict):
                selection_rationale.setdefault("review_subject", review_subject)
                selection_rationale.setdefault("focus_color", player_color)

            # Pre-generate walkthrough pre-commentary immediately after key moments are selected
            pre_commentary_by_ply = await self._generate_walkthrough_pre_commentary_by_ply(
                selected_moments=selected_moments,
                ply_records=first_game_ply_records,
                selection_rationale=selection_rationale,
                game_metadata=first_game_meta
            )
            
            # Loss diagnosis is now included in selection_rationale if applicable
            loss_diagnosis = selection_rationale.get("loss_diagnosis")
            
            await emit_status(f"Generating summary...", 0.97, replace=True)
            await asyncio.sleep(0)  # Yield to send status
            
            # Generate context-aware narrative
            narrative = self._generate_review_narrative_with_context(
                summary=aggregated.get("summary", {}),
                phase_stats=aggregated.get("phase_stats", {}),
                opening_perf=aggregated.get("opening_performance", []),
                tag_stats=aggregated.get("performance_by_tags", {}),
                selected_moments=selected_moments,
                selection_rationale=selection_rationale,
                loss_diagnosis=loss_diagnosis,
                username=username,
                platform=platform,
                total_games=len(analyzed_games),
                user_query=user_query,
                game_metadata=first_game_meta,
                first_game=first_game,
                aggregated=aggregated  # Pass full aggregated data for time analysis
            )
            
            await emit_status(f"Preparing results...", 0.99, replace=True)
            
            return {
                "success": True,
                "username": username,
                "platform": platform,
                "games_fetched": len(games),
                "games_analyzed": len(analyzed_games),
                "narrative": narrative,
                "stats": aggregated.get("summary", {}),
                "phase_stats": aggregated.get("phase_stats", {}),
                "opening_performance": aggregated.get("opening_performance", []),
                # Include game data for auto-loading into tab
                "first_game": {
                    "pgn": first_game.get("pgn", "") if first_game else "",
                    "white": first_game_meta.get("white", username if first_game_meta.get("player_color") == "white" else "Opponent"),
                    "black": first_game_meta.get("black", username if first_game_meta.get("player_color") == "black" else "Opponent"),
                    "date": first_game_meta.get("date", ""),
                    "result": first_game_meta.get("result", ""),
                    "time_control": first_game_meta.get("time_control", ""),
                    "opening": first_game.get("game_metadata", {}).get("opening", "") if first_game else "",
                } if first_game else None,
                # Include full review for walkthrough
                "first_game_review": first_game if first_game else None,
                # NEW: Selected key moments and rationale
                "selected_key_moments": selected_moments,
                "selection_rationale": selection_rationale,
                "loss_diagnosis": loss_diagnosis,
                # NEW: Batch pre-commentary for walkthrough steps (keyed by ply as string)
                "pre_commentary_by_ply": pre_commentary_by_ply,
                "charts": {
                    "accuracy_by_phase": aggregated.get("phase_stats", {}),
                    "opening_performance": aggregated.get("opening_performance", [])[:5],  # Top 5
                    "common_mistakes": aggregated.get("theme_frequency", [])[:5],  # Top 5
                    "phase_stats": aggregated.get("phase_stats", {}),  # Explicit phase_stats
                    "accuracy_by_rating": aggregated.get("accuracy_by_rating", []),  # Rating data
                    "win_rate_by_phase": aggregated.get("win_rate_by_phase", {}),  # Win rate
                    "accuracy_by_color": aggregated.get("accuracy_by_color", {}),  # Color performance
                    "performance_by_time_control": aggregated.get("performance_by_time_control", []),  # Time control
                    "accuracy_by_time_spent": aggregated.get("accuracy_by_time_spent", []),  # Time spent per move
                    "performance_by_tags": aggregated.get("performance_by_tags", {}),  # Tag-based performance
                    "critical_moments": aggregated.get("critical_moments", {}),  # Critical positions
                    "advantage_conversion": aggregated.get("advantage_conversion", {}),  # Conversion rate
                    "blunder_triggers": aggregated.get("blunder_triggers", {}),  # What causes errors
                    "piece_activity": aggregated.get("piece_activity", [])  # Piece-specific accuracy
                }
            }
        
        return {
            "success": False,
            "error": "no_games_analyzed",
            "message": f"Could not analyze any games for {username} on {platform}"
        }

    async def _generate_walkthrough_pre_commentary_by_ply(
        self,
        selected_moments: List[Dict],
        ply_records: List[Dict],
        selection_rationale: Dict,
        game_metadata: Dict
    ) -> Dict:
        """
        Generate 1–2 sentence pre-analysis coach commentary for each selected key moment.
        Returns: { "<ply>": "commentary", ... }
        """
        try:
            if not getattr(self, "openai_client", None):
                return {}
            if not selected_moments or not ply_records:
                return {}

            moments = selected_moments[:20]

            items = []
            for m in moments:
                ply = m.get("ply")
                if not isinstance(ply, int):
                    continue
                rec = next((r for r in ply_records if r.get("ply") == ply), {}) or {}
                san = rec.get("san", "?")
                side = rec.get("side_moved", "")
                category = rec.get("category", "") or m.get("primary_label", "")
                cp_loss = rec.get("cp_loss", 0) or 0
                time_s = rec.get("time_spent_s", 0) or 0
                labels = m.get("labels", []) or []

                move_number = (ply // 2) + 1
                move_text = f"Move {move_number}: {san}"

                items.append({
                    "ply": ply,
                    "move": move_text,
                    "side": side,
                    "category": category,
                    "cp_loss": round(float(cp_loss)),
                    "time_s": round(float(time_s), 1),
                    "labels": labels[:6],
                })

            if not items:
                return {}

            narrative_focus = ""
            review_subject = ""
            if isinstance(selection_rationale, dict):
                narrative_focus = selection_rationale.get("narrative_focus", "") or ""
                review_subject = selection_rationale.get("review_subject", "") or ""

            prompt = f"""
We are generating *pre-analysis* coach commentary for a guided chess walkthrough.

Constraints:
- 1–2 sentences per move
- No spoilers: DO NOT name the best move or suggest concrete moves
- Use conversational coaching language
- If the moment is an error (blunder/mistake/inaccuracy/missed_win), invite the user to look for a better continuation (without naming any move)
- Avoid PGN-like numbering such as "10. Qb3"; always format as "Move 10: Qb3"

Context:
- Review subject: {review_subject or "unknown"}
- Narrative focus: {narrative_focus or "N/A"}
- Game result: {(game_metadata or {}).get("result", "")}
- Time control: {(game_metadata or {}).get("time_control", "")}

Moves (JSON):
{json.dumps(items, ensure_ascii=False)}

Return ONLY valid JSON in this exact format:
{{
  "by_ply": {{
    "19": "commentary...",
    "33": "commentary..."
  }}
}}
""".strip()

            def call_openai():
                return self.openai_client.chat.completions.create(
                    model="gpt-5",
                    messages=[
                        {"role": "system", "content": "Return only valid JSON. No markdown. Follow constraints strictly."},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.4,
                )

            if self.llm_router:
                parsed = self.llm_router.complete_json(
                    session_id="default",
                    stage="walkthrough_preanalysis",
                    system_prompt="Return only valid JSON. No markdown. Follow constraints strictly.",
                    user_text=prompt,
                    temperature=0.4,
                    model="gpt-5",
                )
                content = json.dumps(parsed, ensure_ascii=False)
            else:
                loop = asyncio.get_event_loop()
                import concurrent.futures as _cf
                with _cf.ThreadPoolExecutor(max_workers=1) as pool:
                    response = await loop.run_in_executor(pool, call_openai)

                content = (response.choices[0].message.content or "").strip()

            # Best-effort JSON extraction
            try:
                parsed = json.loads(content)
            except Exception:
                start = content.find("{")
                end = content.rfind("}") + 1
                parsed = json.loads(content[start:end]) if start >= 0 and end > start else {}

            by_ply = parsed.get("by_ply", {}) if isinstance(parsed, dict) else {}
            if not isinstance(by_ply, dict):
                return {}

            out = {}
            for k, v in by_ply.items():
                try:
                    ply_int = int(k)
                except Exception:
                    continue
                if isinstance(v, str) and v.strip():
                    out[str(ply_int)] = v.strip()

            return out

        except Exception as e:
            print(f"⚠️ Pre-commentary generation failed: {e}")
            return {}
    
    async def _generate_training_session(self, args: Dict) -> Dict:
        """Generate training drills"""
        username = args.get("username")
        training_query = args.get("training_query")
        source = args.get("source", "recent_games")
        num_drills = args.get("num_drills", 15)
        
        print(f"   🎯 Generating training for {username}: '{training_query}'")
        
        # Get analyzed games (from context or database)
        analyzed_games = args.get("analyzed_games", [])
        
        if not analyzed_games and self.supabase_client:
            # Try to get from database
            print(f"      Fetching analyzed games from database...")
            db_games = self.supabase_client.get_analyzed_games(username, limit=10)
            # Convert to expected format (simplified for now)
            analyzed_games = [g.get("game_review", {}) for g in db_games if g.get("game_review")]
        
        if not analyzed_games:
            return {"error": "No analyzed games available. Analyze some games first."}
        
        # Plan training
        blueprint = self.training_planner.plan_training(training_query, analyzed_games)
        
        # Mine positions
        positions = self.position_miner.mine_positions(
            analyzed_games,
            blueprint.get("focus_tags"),
            num_drills
        )
        
        if not positions:
            return {
                "success": True,
                "drills_generated": 0,
                "message": "No relevant positions found for this query. Try a broader search.",
                "search_criteria": blueprint.get("search_criteria", [])
            }
        
        # Generate drills
        drills = await self.drill_generator.generate_drills(
            positions,
            blueprint.get("drill_types", ["tactics"]),
            self.engine,
            15
        )
        
        return {
            "success": True,
            "drills_generated": len(drills),
            "drills": drills[:5],  # Return first 5 for preview
            "blueprint": blueprint,
            "search_criteria": blueprint.get("search_criteria", []),
            "message": f"Generated {len(drills)} personalized drills focused on: {', '.join(blueprint.get('focus_tags', []))}"
        }
    
    async def _get_lesson(self, args: Dict) -> Dict:
        """Generate interactive lesson"""
        topic = args.get("topic")
        level = args.get("level", "intermediate")
        
        print(f"   📚 Generating lesson on '{topic}' ({level})")
        
        # Use existing lesson generation
        from opening_builder import build_opening_lesson
        
        try:
            lesson = await build_opening_lesson(topic, self.engine, None, self.openai_client)
            
            return {
                "success": True,
                "topic": topic,
                "lesson": lesson,
                "sections": len(lesson.get("sections", []))
            }
        except Exception as e:
            return {"error": f"Failed to generate lesson: {str(e)}"}

    async def _generate_opening_lesson(self, args: Dict, context: Optional[Dict]) -> Dict:
        """Route to backend personalized opening lesson builder with rate limiting."""
        user_id = args.get("user_id")
        if not user_id and context:
            user_id = context.get("user_id") or context.get("profile", {}).get("user_id")
        if not user_id:
            return {"error": "User authentication required for opening lessons."}

        # Check subscription and rate limits
        if self.supabase_client:
            try:
                tier_info = self.supabase_client.get_subscription_overview(user_id)
                allowed, message, usage_info = self.supabase_client.check_and_increment_usage(
                    user_id, None, "lesson", tier_info
                )
                
                if not allowed:
                    return {
                        "error": message,
                        "rate_limit_info": usage_info,
                        "suggestion": "Upgrade your plan to increase your daily limit."
                    }
            except Exception as e:
                print(f"   ⚠️ Rate limit check failed: {e}")
                import traceback
                traceback.print_exc()
                # Continue anyway - don't block on rate limit errors

        payload = {
            "user_id": user_id,
            "chat_id": context.get("session_id") if context else None,
            "opening_query": args.get("opening_query"),
            "fen": args.get("fen") or (context.get("board_state") if context else None),
            "eco": args.get("eco"),
            "orientation": args.get("orientation") or "white",
            "variation_hint": args.get("variation_hint"),
        }

        result = await self.generate_opening_lesson_internal(payload)
        return {
            "success": True,
            "lesson": result.get("lesson"),
            "personalization": result.get("personalization"),
            "metadata": result.get("metadata"),
            "recent_lessons": result.get("recent_lessons"),
        }
    
    # ========================================================================
    # LOW-LEVEL DATA TOOL IMPLEMENTATIONS
    # ========================================================================
    
    def _query_user_games(self, args: Dict) -> Dict:
        """Query saved games from database"""
        username = args.get("username")
        
        if not self.supabase_client:
            return {"error": "Database not available"}
        
        print(f"   🔍 Querying games for {username}")
        
        # For now, return mock data since Supabase integration pending
        # When integrated, this will call:
        # games = self.supabase_client.get_user_games(user_id, ...)
        
        return {
            "success": True,
            "games_found": 0,
            "message": "Database integration pending. Games currently in cache only.",
            "note": "This tool will work after Supabase integration is complete"
        }
    
    def _get_game_details(self, args: Dict) -> Dict:
        """Get full game review data"""
        game_id = args.get("game_id")
        
        return {
            "success": True,
            "message": "Database integration pending",
            "note": "This tool will work after Supabase integration"
        }
    
    def _query_positions(self, args: Dict, context: Dict = None) -> Dict:
        """Query saved positions using the new position search tool"""
        from tools.position_search import search_user_positions
        
        # Resolve user_id
        user_id = args.get("user_id")
        if not user_id and context:
            user_id = context.get("user_id") or context.get("profile", {}).get("user_id")
            
        if not user_id and self.supabase_client:
            # Try to get current user if authenticated
            pass # We'll assume it's passed in context for now
            
        if not user_id:
            return {"success": False, "error": "User not authenticated. Cannot search personal history."}

        tags = args.get("tags")
        themes = args.get("themes")
        error_categories = args.get("error_categories")
        phases = [args.get("phase")] if args.get("phase") else None
        mover_name = args.get("mover_name")
        limit = args.get("limit", 5)
        
        results = search_user_positions(
            supabase_client=self.supabase_client,
            user_id=user_id,
            tags=tags,
            themes=themes,
            error_categories=error_categories,
            phases=phases,
            mover_name=mover_name,
            limit=limit
        )
        
        return {
            "success": True,
            "positions_found": len(results),
            "positions": results,
            "message": f"Found {len(results)} positions matching your criteria."
        }
    
    def _get_training_stats(self, args: Dict) -> Dict:
        """Get training progress stats"""
        username = args.get("username")
        
        return {
            "success": True,
            "message": "Training stats available after Supabase integration",
            "note": "Currently tracking in memory only"
        }
    
    def _save_position(self, args: Dict, context: Dict) -> Dict:
        """Save a position to database"""
        username = args.get("username")
        fen = args.get("fen") or context.get("fen") if context else None
        note = args.get("note", "")
        tags = args.get("tags", [])
        
        if not fen:
            return {"error": "No position to save"}
        
        return {
            "success": True,
            "message": f"Position saved! (Will persist after Supabase integration)",
            "fen": fen,
            "tags": tags
        }
    
    def _create_collection(self, args: Dict) -> Dict:
        """Create new collection"""
        username = args.get("username")
        name = args.get("name")
        description = args.get("description", "")
        
        return {
            "success": True,
            "message": f"Collection '{name}' created! (Will persist after Supabase integration)",
            "name": name
        }
    
    def _setup_position(self, args: Dict, context: Dict) -> Dict:
        """Set up a chess position on the board"""
        fen = args.get("fen")
        pgn = args.get("pgn")
        orientation = args.get("orientation", "white")
        move_annotations = args.get("move_annotations", {})
        
        # Validate at least one of FEN or PGN is provided
        if not fen and not pgn:
            # Use current board state from context
            fen = context.get("board_state", "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
        
        return {
            "success": True,
            "display_type": "board",
            "fen": fen,
            "pgn": pgn,
            "orientation": orientation,
            "move_annotations": move_annotations,
            "message": f"Position set up (orientation: {orientation})"
        }
    
    def _generate_review_narrative(self, summary: Dict, phase_stats: Dict, opening_perf: list, username: str, platform: str, user_query: str = "") -> str:
        """Generate structured Q&A style narrative from personal review stats"""
        
        total_games = summary.get('total_games', 0) or 0
        avg_accuracy_raw = summary.get('avg_accuracy')
        avg_accuracy = float(avg_accuracy_raw) if avg_accuracy_raw is not None else 0.0
        win_rate_raw = summary.get('win_rate')
        win_rate = float(win_rate_raw) * 100 if win_rate_raw is not None else 0.0
        avg_rating = summary.get('avg_rating', 0) or 0
        platform = platform or "chess.com"
        username = username or "player"
        
        # 1. OPENING - Conversational introduction
        narrative = f"I just finished analyzing your last **{total_games} games** on **{platform}** as **{username}**. "
        narrative += f"Let me break down what I found.\n\n"
        
        # 2. VERDICT SECTION
        narrative += f"## Your Performance Assessment\n\n"
        
        # Make verdict more conversational based on accuracy
        if avg_accuracy and avg_accuracy > 90:
            narrative += f"You're playing at an **exceptional level** with **{avg_accuracy:.1f}% accuracy**. "
            narrative += f"Your calculation and decision-making are consistently strong. "
        elif avg_accuracy and avg_accuracy > 80:
            narrative += f"You're playing **solidly** at **{avg_accuracy:.1f}% accuracy**, but there's room to optimize. "
            narrative += f"You have a good foundation, but tightening up some specific areas will push you to the next level. "
        elif avg_accuracy and avg_accuracy > 70:
            narrative += f"You're showing **decent fundamentals** at **{avg_accuracy:.1f}% accuracy**, but your execution is inconsistent. "
            narrative += f"The good news is that with some focused practice, you can improve significantly. "
        elif avg_accuracy:
            narrative += f"At **{avg_accuracy:.1f}% accuracy**, there's **significant opportunity for improvement**. "
            narrative += f"Don't be discouraged - identifying these weaknesses is the first step to getting stronger. "
        else:
            narrative += f"Let me analyze your performance based on the games reviewed.\n\n"
        
        narrative += f"\n\n"
        
        # 3. JUSTIFICATION - Tell the story
        narrative += f"## Here's What the Data Shows\n\n"
        
        justifications = self._get_top_justifications(phase_stats, opening_perf, win_rate, avg_accuracy)
        if len(justifications) >= 3:
            narrative += f"{justifications[0]}\n\n"
            narrative += f"{justifications[1]}\n\n"
            narrative += f"{justifications[2]}\n\n"
        else:
            for just in justifications:
                narrative += f"{just}\n\n"
        
        # 4. ACTIONABLE PLAN - Guide them forward
        narrative += f"## My Recommendations\n\n"
        narrative += f"If I were coaching you, here's what I'd focus on first:\n\n"
        
        suggestions = self._generate_prioritized_suggestions(phase_stats, avg_accuracy, opening_perf)
        for idx, suggestion in enumerate(suggestions[:3], 1):
            narrative += f"**{idx}. {suggestion['title']}**\n\n"
            narrative += f"{suggestion['detail']}\n\n"
        
        # 5. CLOSING - Encourage exploration
        narrative += f"Want more details? Expand the charts below to see your complete breakdown by phase, opening, time control, and more!\n"
        
        return narrative
    
    def _get_top_justifications(self, phase_stats: Dict, opening_perf: list, win_rate: float, avg_accuracy: float) -> list:
        """Extract 3-5 most impactful data points as conversational statements"""
        justifications = []
        
        # Check phase performance gaps
        if phase_stats:
            phases_sorted = sorted(
                [(name, _safe_float((data or {}).get('accuracy'), 0.0)) for name, data in phase_stats.items()],
                key=lambda x: x[1]
            )
            weakest = phases_sorted[0]
            strongest = phases_sorted[-1]
            gap = strongest[1] - weakest[1]
            
            if gap > 10:
                justifications.append(
                    f"**Phase consistency is an issue.** Your {strongest[0]} ({_safe_float(strongest[1], 0.0):.1f}%) is {gap:.0f}% stronger than your {weakest[0]} ({_safe_float(weakest[1], 0.0):.1f}%). This gap suggests you need focused practice in your weaker phase."
                )
            
            # Highlight if endgame is weak
            endgame_acc = _safe_float(phase_stats.get('endgame', {}).get('accuracy'), 0.0)
            if endgame_acc < 70 and phase_stats.get('endgame', {}).get('move_count', 0) > 0:
                justifications.append(
                    f"**Your endgame technique needs work.** At {endgame_acc:.1f}% accuracy, you're likely missing conversions or allowing draws in winning positions. This is costing you rating points."
                )
        
        # Win rate correlation
        if win_rate < 40 and avg_accuracy > 75:
            justifications.append(
                f"**Something's off with your win conversion.** Your {_safe_float(win_rate, 0.0):.0f}% win rate is surprisingly low for {_safe_float(avg_accuracy, 0.0):.1f}% accuracy. You might be losing won positions or struggling in time pressure."
            )
        elif win_rate > 60:
            justifications.append(
                f"**You're good at closing out games.** Your {_safe_float(win_rate, 0.0):.0f}% win rate shows you know how to convert advantages into wins - that's a valuable skill."
            )
        
        # Opening performance
        if opening_perf and len(opening_perf) > 0:
            sanitized = []
            for op in opening_perf:
                if not isinstance(op, dict):
                    continue
                op2 = dict(op)
                op2["avg_accuracy"] = _safe_float(op.get("avg_accuracy"), 0.0)
                sanitized.append(op2)
            best_opening = max(sanitized, key=lambda x: x.get('avg_accuracy', 0.0)) if sanitized else None
            if best_opening and best_opening.get('avg_accuracy', 0.0) > avg_accuracy + 5:
                justifications.append(
                    f"**You have a weapon in your repertoire.** Your {best_opening.get('opening', 'Unknown')} is performing at {best_opening.get('avg_accuracy', 0):.1f}% - well above your average. Keep playing it!"
                )
            
            # Check for weak openings
            weak_openings = [op for op in sanitized if op.get('avg_accuracy', 0.0) < avg_accuracy - 5]
            if weak_openings:
                justifications.append(
                    f"**One opening is dragging you down.** Your {weak_openings[0].get('opening', 'Unknown')} is underperforming at {weak_openings[0].get('avg_accuracy', 0):.1f}%. Consider either studying it more or switching to something else."
                )
        
        # If we have fewer than 3, add generic insights
        if len(justifications) < 3:
            if avg_accuracy > 80:
                justifications.append("**You're playing consistently.** No major weaknesses jumped out - you maintain solid accuracy across all game phases.")
            elif avg_accuracy < 70:
                justifications.append("**Tactical mistakes are the main issue.** You need to slow down and calculate more thoroughly before making moves.")
        
        return justifications
    
    def _generate_prioritized_suggestions(self, phase_stats: Dict, avg_accuracy: float, opening_perf: list) -> list:
        """Generate ordered suggestions by impact"""
        suggestions = []
        avg_accuracy = _safe_float(avg_accuracy, 0.0)
        
        # Priority 1: Fix biggest weakness
        if phase_stats:
            weakest_phase = min(phase_stats.items(), key=lambda x: x[1].get('accuracy', 100) if x[1].get('accuracy') is not None else 100)
            if weakest_phase[1].get('accuracy') is not None and weakest_phase[1].get('accuracy', 100) < 75 and weakest_phase[1].get('move_count', 0) > 0:
                suggestions.append({
                    'title': f"Master {weakest_phase[0]} technique",
                    'detail': f"At {_safe_float(weakest_phase[1].get('accuracy'), 0.0):.1f}%, this is costing you games. Study {weakest_phase[0]} fundamentals and practice conversion."
                })
        
        # Priority 2: Improve consistency
        if avg_accuracy < 85:
            suggestions.append({
                'title': "Reduce tactical errors",
                'detail': "Focus on calculating candidate moves thoroughly before playing. Aim for 85%+ accuracy."
            })
        
        # Priority 3: Opening repertoire
        if opening_perf and len(opening_perf) > 0:
            sanitized = []
            for op in opening_perf:
                if not isinstance(op, dict):
                    continue
                op2 = dict(op)
                op2["avg_accuracy"] = _safe_float(op.get("avg_accuracy"), 0.0)
                sanitized.append(op2)
            weak_openings = [op for op in sanitized if op.get('avg_accuracy', 0) < avg_accuracy - 5]
            if weak_openings:
                suggestions.append({
                    'title': "Strengthen opening preparation",
                    'detail': f"Study {weak_openings[0].get('opening', 'Unknown')} - you're {(avg_accuracy - weak_openings[0].get('avg_accuracy', 0)):.0f}% below your average."
                })
        
        # Priority 4: Time management (if we have blunder trigger data)
        if len(suggestions) < 3:
            suggestions.append({
                'title': "Improve time management",
                'detail': "Avoid time pressure situations that lead to mistakes. Budget your clock wisely."
            })
        
        # Priority 5: Pattern recognition
        if len(suggestions) < 3:
            suggestions.append({
                'title': "Study tactical patterns",
                'detail': "Work on recognizing common tactical motifs (forks, pins, skewers) to improve calculation speed."
            })
        
        return suggestions
    
    async def _generate_llm_narrative(
        self,
        summary: Dict,
        phase_stats: Dict,
        tag_stats: Dict,
        selected_moments: list,
        selection_rationale: Dict,
        loss_diagnosis: Dict,
        username: str,
        platform: str,
        total_games: int,
        user_query: str,
        game_metadata: Dict,
        first_game: Dict,
        ply_records: list,
        aggregated: Dict = None
    ) -> str:
        """
        Use LLM to generate a natural, conversational narrative based on game data.
        """
        try:
            # Build rich context for the LLM
            game_result = ""
            if first_game:
                game_result = first_game.get("result", first_game.get("game_result", ""))
            if not game_result and game_metadata:
                game_result = game_metadata.get("result", "")
            
            termination = game_metadata.get("termination", "") if game_metadata else ""
            time_control_raw = game_metadata.get("time_control", "") if game_metadata else ""
            
            # Parse time control for clarity
            time_control = time_control_raw
            if time_control_raw:
                try:
                    # Handle formats like "60" (seconds), "180+2" (with increment), etc.
                    if "+" in time_control_raw:
                        # Format like "180+2" or "60+0"
                        base, inc = time_control_raw.split("+")
                        base_sec = int(base)
                        inc_sec = int(inc)
                        if base_sec < 180:
                            time_control = f"{base_sec}s+{inc_sec} (bullet)"
                        elif base_sec < 600:
                            time_control = f"{base_sec//60}min+{inc_sec} (blitz)"
                        elif base_sec < 1800:
                            time_control = f"{base_sec//60}min+{inc_sec} (rapid)"
                        else:
                            time_control = f"{base_sec//60}min+{inc_sec} (classical)"
                    elif time_control_raw.isdigit():
                        seconds = int(time_control_raw)
                        if seconds < 180:
                            time_control = f"{seconds}s (bullet)"
                        elif seconds < 600:
                            time_control = f"{seconds//60}min (blitz)"
                        elif seconds < 1800:
                            time_control = f"{seconds//60}min (rapid)"
                        else:
                            time_control = f"{seconds//60}min (classical)"
                except:
                    pass  # Keep original if parsing fails
            
            opening = first_game.get("opening", {}) if first_game else {}
            opening_name = opening.get("name", "Unknown opening") if opening else "Unknown opening"
            
            avg_accuracy = _safe_float(summary.get('avg_accuracy'), 0.0)
            avg_cp_loss = _safe_float(summary.get('avg_cp_loss'), 0.0)
            
            # Phase stats
            opening_acc = phase_stats.get("opening", {}).get("avg_accuracy")
            middlegame_acc = phase_stats.get("middlegame", {}).get("avg_accuracy")
            endgame_acc = phase_stats.get("endgame", {}).get("avg_accuracy")
            
            # Count move types
            blunders = [m for m in selected_moments if m.get("primary_label") == "blunder"]
            mistakes = [m for m in selected_moments if m.get("primary_label") == "mistake"]
            best_moves = [m for m in selected_moments if m.get("primary_label") in ["best", "excellent", "critical_best"]]
            
            # Build context string
            context = f"""Game Review Data:
- Player: {username} on {platform}
- User's question: "{user_query}"
- Game result: {game_result}
- Termination: {termination}
- Time control: {time_control}
- Opening: {opening_name}
- Overall accuracy: {avg_accuracy:.1f}%
- Average centipawn loss: {avg_cp_loss:.1f}

Phase Accuracy (only phases with moves shown):"""
            
            # Only include phases that have data
            phase_acc_parts = []
            if opening_acc is not None:
                phase_acc_parts.append(f"- Opening: {_safe_float(opening_acc, 0.0):.1f}%")
            if middlegame_acc is not None:
                phase_acc_parts.append(f"- Middlegame: {_safe_float(middlegame_acc, 0.0):.1f}%")
            if endgame_acc is not None:
                phase_acc_parts.append(f"- Endgame: {_safe_float(endgame_acc, 0.0):.1f}%")
            
            if phase_acc_parts:
                context += "\n" + "\n".join(phase_acc_parts)
            else:
                context += "\n- No phase data available"
            
            context += f"""

Key Moments Found:
- Blunders: {len(blunders)}
- Mistakes: {len(mistakes)}
- Excellent/Best moves: {len(best_moves)}
- Total key moments: {len(selected_moments)}"""
            
            # === TIME ANALYSIS ===
            if aggregated:
                time_mgmt = aggregated.get("time_management", {})
                accuracy_by_time = aggregated.get("accuracy_by_time_spent", [])
                blunder_triggers = aggregated.get("blunder_triggers", {})
                mistake_patterns = aggregated.get("mistake_patterns", {})
                
                time_context_parts = []
                
                # Average time per move
                avg_time = _safe_float(time_mgmt.get("avg_time_per_move"), 0.0)
                if avg_time and avg_time > 0:
                    time_context_parts.append(f"- Average time per move: {avg_time:.1f}s")
                
                # Time by phase - only include phases with data
                phase_times = []
                avg_opening_time = _safe_float(time_mgmt.get("avg_time_opening"), 0.0)
                avg_middlegame_time = _safe_float(time_mgmt.get("avg_time_middlegame"), 0.0)
                avg_endgame_time = _safe_float(time_mgmt.get("avg_time_endgame"), 0.0)
                if avg_opening_time and avg_opening_time > 0:
                    phase_times.append(f"Opening {avg_opening_time:.1f}s")
                if avg_middlegame_time and avg_middlegame_time > 0:
                    phase_times.append(f"Middlegame {avg_middlegame_time:.1f}s")
                if avg_endgame_time and avg_endgame_time > 0:
                    phase_times.append(f"Endgame {avg_endgame_time:.1f}s")
                if phase_times:
                    time_context_parts.append(f"- Time per phase: {', '.join(phase_times)}")
                
                # Accuracy by time ranges - ONLY include categories with moves
                if accuracy_by_time:
                    valid_ranges = [tr for tr in accuracy_by_time if tr.get("move_count", 0) > 0]
                    if valid_ranges:
                        time_context_parts.append("- Accuracy by thinking time:")
                        for time_range in valid_ranges:
                            label = time_range.get("time_range", "")
                            acc = _safe_float(time_range.get("avg_accuracy"), 0.0)
                            count = time_range.get("move_count", 0)
                            time_context_parts.append(f"  • {label}: {acc:.1f}% ({count} moves)")
                
                # Only add time analysis header if we have data
                if time_context_parts:
                    context += "\n\n**Time Management Analysis:**\n" + "\n".join(time_context_parts)
                
                # Error triggers - only if there were errors
                total_blunders_trig = blunder_triggers.get("total_blunders", 0)
                if total_blunders_trig > 0:
                    context += f"\n\n**Error Triggers:**"
                    context += f"\n- Total errors analyzed: {total_blunders_trig}"
                    time_pressure_blunders = blunder_triggers.get("time_pressure", 0)
                    if time_pressure_blunders > 0:
                        context += f"\n- Errors under time pressure (<10s): {time_pressure_blunders} ({100*time_pressure_blunders/total_blunders_trig:.0f}%)"
                    after_opp = blunder_triggers.get("after_opponent_mistake", 0)
                    if after_opp > 0:
                        context += f"\n- Errors after opponent mistake: {after_opp} ({100*after_opp/total_blunders_trig:.0f}%)"
                    complex_pos = blunder_triggers.get("complex_positions", 0)
                    if complex_pos > 0:
                        context += f"\n- Errors in complex positions: {complex_pos}"
                    
                    # Blunders in time trouble
                    blunders_time_trouble = mistake_patterns.get("blunders_in_time_trouble", 0)
                    if blunders_time_trouble > 0:
                        context += f"\n- Blunders in time trouble: {blunders_time_trouble}"
            
            # Add time spent on key moments
            moments_with_time = []
            for moment in selected_moments[:10]:
                ply = moment.get("ply", 0)
                record = next((r for r in ply_records if r.get("ply") == ply), {})
                time_spent = record.get("time_spent_s", 0)
                if time_spent:
                    moments_with_time.append((ply, record.get("san", "?"), time_spent, record.get("category", "")))
            
            if moments_with_time:
                context += "\n\n**Time spent on key moments:**"
                for ply, san, time_s, cat in moments_with_time[:5]:
                    context += f"\n- Move {ply} ({san}): {_safe_float(time_s, 0.0):.1f}s ({cat})"
            
            context += f"\n\nQuery Intent: {selection_rationale.get('query_intent', 'general')}"
            context += f"\nNarrative Focus: {selection_rationale.get('narrative_focus', '')}"
            
            # Add loss diagnosis if present
            if loss_diagnosis:
                loss_type = loss_diagnosis.get("loss_type", "")
                loss_detail = loss_diagnosis.get("detail", "")
                context += f"\n\nLoss Diagnosis:\n- Type: {loss_type}\n- Detail: {loss_detail}"
                
                # Add time analysis from loss diagnosis
                time_analysis = loss_diagnosis.get("time_analysis", {})
                if time_analysis:
                    slow_moves = time_analysis.get("slow_moves", [])
                    time_pressure_moves = time_analysis.get("time_pressure_moves", [])
                    if slow_moves:
                        context += f"\n- Slow moves that ate time: {len(slow_moves)}"
                    if time_pressure_moves:
                        context += f"\n- Errors made under time pressure: {len(time_pressure_moves)}"
            
            # Add a few key moment details (not all - LLM will summarize)
            if selected_moments[:5]:
                context += "\n\nTop Key Moments:"
                for i, moment in enumerate(selected_moments[:5], 1):
                    ply = moment.get("ply", 0)
                    record = next((r for r in ply_records if r.get("ply") == ply), {})
                    move_san = record.get("san", "?")
                    category = record.get("category", moment.get("primary_label", ""))
                    cp_loss = record.get("cp_loss", 0)
                    phase = record.get("phase", "")
                    time_spent = record.get("time_spent_s", 0)
                    time_spent_f = _safe_float(time_spent, 0.0)
                    time_str = f", {time_spent_f:.1f}s" if time_spent_f > 0 else ""
                    context += f"\n{i}. Move {ply} ({move_san}): {category}, {_safe_float(cp_loss, 0.0):.0f}cp loss, {phase}{time_str}"
            
            system_prompt = """You are a chess coach providing game feedback. Write a brief, conversational response to the user's question about their game.

Guidelines:
- Be direct and answer their specific question first
- Use natural, conversational language (not robotic or template-like)
- Reference specific statistics and moments to support your points
- Keep it concise - 2-4 sentences for the main answer
- Don't list moves unless specifically asked - instead, summarize patterns
- If they asked "how did I play", give an honest assessment
- If they asked "why did I lose", explain the key reason
- Be encouraging but honest about areas to improve
- Don't use headers like "## Performance" - just write naturally
- Don't include a bullet list of all blunders - that's shown separately

Time analysis insights (use when relevant):
- If errors happened mostly on fast moves (<5s), suggest "slowing down a bit"
- If errors happened on slow moves (>30s), they might be "overthinking"
- If time pressure caused errors, mention time management
- Compare accuracy across phases - if one phase is notably weaker, mention it
- If they spent way more time in one phase, it might indicate difficulty

Example good responses:
- "You played really well! 95% accuracy is excellent, and you only had one small inaccuracy in the middlegame."
- "This was a tough loss. You were playing well until move 33 when a tactical oversight shifted the advantage. The game was close until then."
- "Solid game overall at 78% accuracy. Your opening was strong, but the middlegame had a few imprecise moments that let your opponent equalize."
- "Time pressure hurt you here - your accuracy dropped to 60% on moves under 5 seconds. The early middlegame ate up a lot of your clock."
- "Interestingly, your quick moves were actually more accurate than when you took your time. Sometimes trusting your instincts works!"

Write your response now based on the game data provided."""

            # Call OpenAI
            import asyncio
            from concurrent.futures import ThreadPoolExecutor
            
            if self.llm_router:
                return self.llm_router.complete(
                    session_id="default",
                    stage="review_narrative",
                    system_prompt=system_prompt,
                    user_text=context,
                    temperature=0.7,
                    model="gpt-5",
                ).strip()
            
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                response = await loop.run_in_executor(
                    executor,
                    lambda: self.openai_client.chat.completions.create(
                        model="gpt-5",
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": context}
                        ],
                        temperature=0.7
                    )
                )
            
            narrative = response.choices[0].message.content.strip()
            return narrative
            
        except Exception as e:
            # No synthetic fallback narrative: avoid crashing the tool call.
            print(f"⚠️ LLM narrative generation failed: {e}")
            return ""
    
    def _generate_review_narrative_with_context(
        self,
        summary: Dict,
        phase_stats: Dict,
        opening_perf: list,
        tag_stats: Dict,
        selected_moments: list,
        selection_rationale: Dict,
        loss_diagnosis: Dict,
        username: str,
        platform: str,
        total_games: int,
        user_query: str = "",
        game_metadata: Dict = None,
        first_game: Dict = None,
        aggregated: Dict = None
    ) -> str:
        """
        Generate context-aware narrative based on statistics and query type.
        Now uses LLM for natural, conversational responses.
        """
        # For single game reviews with a user query, use LLM-based narrative
        if total_games == 1 and user_query and self.openai_client:
            ply_records = first_game.get("ply_records", []) if first_game else []
            
            # Run async LLM call synchronously
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # We're already in an async context, need to use different approach
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(
                            asyncio.run,
                            self._generate_llm_narrative(
                                summary=summary,
                                phase_stats=phase_stats,
                                tag_stats=tag_stats,
                                selected_moments=selected_moments,
                                selection_rationale=selection_rationale,
                                loss_diagnosis=loss_diagnosis,
                                username=username,
                                platform=platform,
                                total_games=total_games,
                                user_query=user_query,
                                game_metadata=game_metadata,
                                first_game=first_game,
                                ply_records=ply_records,
                                aggregated=aggregated
                            )
                        )
                        return future.result(timeout=10)
                else:
                    return loop.run_until_complete(
                        self._generate_llm_narrative(
                            summary=summary,
                            phase_stats=phase_stats,
                            tag_stats=tag_stats,
                            selected_moments=selected_moments,
                            selection_rationale=selection_rationale,
                            loss_diagnosis=loss_diagnosis,
                            username=username,
                            platform=platform,
                            total_games=total_games,
                            user_query=user_query,
                            game_metadata=game_metadata,
                            first_game=first_game,
                            ply_records=ply_records,
                            aggregated=aggregated
                        )
                    )
            except Exception as e:
                print(f"⚠️ Failed to generate LLM narrative: {e}")
                # Fall through to template-based generation
        
        avg_accuracy = _safe_float(summary.get('avg_accuracy'), 0.0)
        win_rate = summary.get('win_rate', 0)
        
        # Determine query type for context
        query_type = selection_rationale.get("query_type", "general")
        query_intent = selection_rationale.get("query_intent", "general")
        narrative_focus = selection_rationale.get("narrative_focus", "")
        
        # Route to query-specific narrative generator
        if query_intent and query_intent != "general":
            # Use query-driven narrative
            ply_records_for_narrative = first_game.get("ply_records", []) if first_game else []
            
            # Get game result for context
            game_result = None
            if first_game:
                game_result = first_game.get("result", first_game.get("game_result", ""))
            if not game_result and game_metadata:
                game_result = game_metadata.get("result", "")
            
            return self._generate_query_driven_narrative(
                query_intent=query_intent,
                selected_moments=selected_moments,
                ply_records=ply_records_for_narrative,
                filter_criteria=selection_rationale.get("filter_criteria", {}),
                narrative_focus=narrative_focus,
                username=username,
                platform=platform,
                total_games=total_games,
                loss_diagnosis=loss_diagnosis,
                game_metadata=game_metadata,
                game_result=game_result
            )
        elif query_type == "loss_diagnosis":
            return self._generate_loss_diagnosis_narrative(
                summary=summary,
                loss_diagnosis=loss_diagnosis,
                selected_moments=selected_moments,
                username=username,
                platform=platform,
                total_games=total_games,
                game_metadata=game_metadata
            )
        elif query_type == "comprehensive":
            return self._generate_comprehensive_narrative(
                summary=summary,
                phase_stats=phase_stats,
                tag_stats=tag_stats,
                selected_moments=selected_moments,
                username=username,
                platform=platform,
                total_games=total_games
            )
        elif query_type == "specific":
            return self._generate_specific_narrative(
                summary=summary,
                selected_moments=selected_moments,
                user_query=user_query,
                username=username,
                platform=platform,
                total_games=total_games
            )
        
        # Default to general narrative
        # Build narrative
        narrative = ""
        
        # === OPENING ===
        if total_games == 1:
            narrative += f"I just finished analyzing your last game on **{platform}** as **{username}**. "
        else:
            narrative += f"I just finished analyzing your last **{total_games} games** on **{platform}** as **{username}**. "
        narrative += "Let me break down what I found.\n\n"
        
        # === VERDICT (context-aware) ===
        narrative += "## Your Performance Assessment\n\n"
        
        # Accuracy assessment
        if avg_accuracy > 90:
            narrative += f"You're playing at an **exceptional level** with **{avg_accuracy:.1f}% accuracy**. "
            narrative += "Your calculation and decision-making are consistently strong."
        elif avg_accuracy > 80:
            narrative += f"You're playing **solidly** at **{avg_accuracy:.1f}% accuracy**, but there's room to optimize. "
            narrative += "You have a good foundation with some specific areas to tighten up."
        elif avg_accuracy > 70:
            narrative += f"You're showing **decent fundamentals** at **{avg_accuracy:.1f}% accuracy**, but execution is inconsistent. "
            narrative += "With focused practice, you can improve significantly."
        else:
            narrative += f"At **{avg_accuracy:.1f}% accuracy**, there's **significant opportunity for improvement**. "
            narrative += "Don't be discouraged - identifying these weaknesses is the first step to getting stronger."
        
        # Add strengths section
        strengths = []
        if avg_accuracy > 90:
            strengths.append("exceptional calculation skills")
        elif avg_accuracy > 80:
            strengths.append("solid fundamentals")
        
        # Check for strong phases
        if phase_stats:
            valid_phases = [(name, data) for name, data in phase_stats.items() 
                          if data.get('accuracy') is not None and data.get('move_count', 0) > 0]
            if valid_phases:
                strongest_phase = max(valid_phases, key=lambda x: x[1].get('accuracy', 0))
                if strongest_phase[1].get('accuracy', 0) > 85:
                    phase_name = strongest_phase[0].replace('_', ' ').title()
                    strengths.append(f"strong {phase_name.lower()} play")
        
        # Check for strong tags (high accuracy with good frequency)
        if tag_stats:
            all_tags = tag_stats.get("performance_by_tags", {}).get("all_tags", [])
            strong_tags = [t for t in all_tags if t.get("accuracy", 0) > 85 and t.get("move_count", 0) >= 5]
            if strong_tags:
                # Find the most frequent strong tag
                top_tag = max(strong_tags, key=lambda x: x.get("move_count", 0))
                tag_natural = translate_tag_to_natural_english(top_tag.get("tag", ""))
                strengths.append(f"strong performance in {tag_natural} positions")
        
        if strengths:
            narrative += f" Your strengths include {', '.join(strengths[:2])}."
        
        narrative += "\n\n"
        
        # === LOSS DIAGNOSIS (if applicable) ===
        if loss_diagnosis and loss_diagnosis.get("loss_type"):
            loss_type = loss_diagnosis.get("loss_type")
            detail = loss_diagnosis.get("detail", "")
            
            # Check termination type from game metadata
            termination = ""
            if game_metadata:
                termination = game_metadata.get("termination", "").lower()
            
            is_timeout = "time" in termination or "timeout" in termination
            is_resignation = "resign" in termination
            
            # Enhance detail with termination info if available
            if is_timeout and "time" not in detail.lower():
                detail = f"Lost on time. {detail}"
            elif is_resignation and "resign" not in detail.lower():
                detail = f"Resigned. {detail}"
            
            narrative += "## What Went Wrong\n\n"
            
            if loss_type == "single_critical_blunder":
                narrative += f"**Single critical blunder.** {detail}. "
                narrative += "The game was competitive until that moment.\n\n"
            elif loss_type == "multiple_blunders":
                narrative += f"**Multiple errors.** {detail}. "
                narrative += "Focus on consistency and checking your calculations.\n\n"
            elif loss_type == "timeout":
                narrative += f"**Time trouble.** {detail}. "
                narrative += "Work on time management and making decisions faster in familiar positions.\n\n"
            elif loss_type == "time_pressure":
                narrative += f"**Time pressure errors.** {detail}. "
                narrative += "You played well until time got low. Budget your clock more carefully.\n\n"
            elif loss_type == "tag_blindspot":
                tag = loss_diagnosis.get("tag", "certain")
                narrative += f"**Positional blindspot.** {detail}. "
                narrative += f"Study positions with {tag} patterns to improve pattern recognition.\n\n"
            else:
                narrative += f"**Gradual decline.** {detail}. "
                narrative += "No single moment lost the game - it was an accumulation of small errors.\n\n"
        
        # === STATISTICS-DRIVEN INSIGHTS ===
        narrative += "## Here's What the Data Shows\n\n"
        
        # Get significant statistics from rationale
        significant_stats = selection_rationale.get("significant_stats", [])
        
        justifications = []
        
        # Phase consistency (context-aware)
        if phase_stats:
            # Filter out phases with None accuracy
            valid_phases = [(name, data) for name, data in phase_stats.items() 
                          if data.get('accuracy') is not None and data.get('move_count', 0) > 0]
            
            if len(valid_phases) >= 2:
                sorted_phases = sorted(valid_phases, key=lambda x: x[1].get('accuracy', 0))
                weakest = sorted_phases[0]
                strongest = sorted_phases[-1]
                gap = strongest[1].get('accuracy', 0) - weakest[1].get('accuracy', 0)
                
                if gap > 10:
                    justifications.append(
                        f"**Phase consistency is an issue.** Your {strongest[0]} ({_safe_float(strongest[1].get('accuracy'), 0.0):.1f}%) "
                        f"is {gap:.0f}% stronger than your {weakest[0]} ({_safe_float(weakest[1].get('accuracy'), 0.0):.1f}%). "
                        f"This gap suggests you need focused practice in your weaker phase."
                    )
            
            # Note missing phases without claiming 0% accuracy
            missing_phases = [name for name, data in phase_stats.items() 
                           if data.get('accuracy') is None or data.get('move_count', 0) == 0]
            if missing_phases and total_games == 1:
                phase_str = ", ".join(missing_phases)
                justifications.append(
                    f"**Game ended early.** No {phase_str} moves were played, "
                    f"so there's no accuracy data for {'that phase' if len(missing_phases) == 1 else 'those phases'}."
                )
        
        # Tag-based statistics (only significant ones - unusually high/low performance or unusual preferences)
        for stat in significant_stats[:2]:  # Top 2 significant stats
            if stat.get("type") == "tag_accuracy":
                tag = stat.get("tag", "unknown")
                tag_natural = translate_tag_to_natural_english(tag)
                acc = stat.get("accuracy", 0)
                count = stat.get("count", 0)
                direction = stat.get("direction", "low")
                
                if direction == "low":
                    justifications.append(
                        f"**Weakness in {tag_natural} positions.** Your accuracy drops to {_safe_float(acc, 0.0):.1f}% in these positions "
                        f"({count} moves). This is a clear area for improvement."
                    )
                elif direction == "high":
                    justifications.append(
                        f"**Strength in {tag_natural} positions.** Your accuracy is {_safe_float(acc, 0.0):.1f}% in these positions "
                        f"({count} moves) - well above your average. Keep leveraging this strength!"
                    )
            elif stat.get("type") == "tag_preference":
                tag = stat.get("tag", "unknown")
                pattern = stat.get("pattern", "")
                tag_natural = translate_tag_to_natural_english(tag)
                
                if pattern == "seeks":
                    created_acc = stat.get("created_accuracy", 0)
                    count = stat.get("count", 0)
                    justifications.append(
                        f"**You underestimate the use of {tag_natural}.** You tend to create these positions "
                        f"but struggle with them ({_safe_float(created_acc, 0.0):.1f}% accuracy when creating, {count} moves)."
                    )
                elif pattern == "avoids":
                    removed_acc = stat.get("removed_accuracy", 0)
                    count = stat.get("count", 0)
                    justifications.append(
                        f"**You failed to capitalize on {tag_natural}.** You remove these patterns "
                        f"with lower accuracy ({_safe_float(removed_acc, 0.0):.1f}%, {count} moves). Consider maintaining them instead."
                    )
        
        # Win rate context (single game = statement, multiple = percentage)
        if total_games == 1:
            result = summary.get('wins', 0) > 0
            if result:
                justifications.append("**You won this game!** But there's always room to improve execution.")
            else:
                justifications.append("**You lost this game.** Let's see what you can learn from it.")
        elif win_rate < 0.4 and avg_accuracy > 75:
            justifications.append(
                f"**Win conversion is an issue.** Your {_safe_float(win_rate, 0.0)*100:.0f}% win rate is surprisingly low "
                f"for {_safe_float(avg_accuracy, 0.0):.1f}% accuracy. You might be losing won positions."
            )
        
        # Add justifications to narrative
        for j in justifications[:3]:
            narrative += f"{j}\n\n"
        
        # === RECOMMENDATIONS ===
        narrative += "## My Recommendations\n\n"
        narrative += "If I were coaching you, here's what I'd focus on first:\n\n"
        
        suggestions = self._generate_prioritized_suggestions_with_tags(
            phase_stats, avg_accuracy, opening_perf, tag_stats, significant_stats
        )
        for idx, suggestion in enumerate(suggestions[:3], 1):
            narrative += f"**{idx}. {suggestion['title']}**\n\n"
            narrative += f"{suggestion['detail']}\n\n"
        
        # === CLOSING ===
        if selected_moments:
            narrative += f"Want more details? Expand the charts below to see your complete breakdown, "
            narrative += f"or let's walk through the **{len(selected_moments)} key moments** I've identified!\n"
        else:
            narrative += "Want more details? Expand the charts below to see your complete breakdown!\n"
        
        return narrative
    
    def _generate_loss_diagnosis_narrative(
        self,
        summary: Dict,
        loss_diagnosis: Dict,
        selected_moments: List[Dict],
        username: str,
        platform: str,
        total_games: int,
        game_metadata: Dict = None
    ) -> str:
        """
        Generate brief, focused narrative explaining why the player lost.
        """
        narrative = ""
        
        # Brief opening
        if total_games == 1:
            narrative += f"Here's why you lost your last game on **{platform}** as **{username}**.\n\n"
        else:
            narrative += f"Here's why you lost your last game.\n\n"
        
        # Loss categorization
        if not loss_diagnosis or not loss_diagnosis.get("loss_type"):
            narrative += "You lost this game. Let's walk through the key moments to understand what happened.\n\n"
            if selected_moments:
                narrative += "**Key moments:**\n"
                for i, moment in enumerate(selected_moments[:5], 1):
                    ply = moment.get("ply", 0)
                    labels = moment.get("labels", [])
                    primary = moment.get("primary_label", "")
                    
                    if primary == "blunder":
                        narrative += f"{i}. Move {ply}: Critical blunder\n"
                    elif primary == "mistake":
                        narrative += f"{i}. Move {ply}: Mistake\n"
                    elif "advantage_shift" in labels:
                        narrative += f"{i}. Move {ply}: Advantage shifted against you\n"
            return narrative
        
        loss_type = loss_diagnosis.get("loss_type", "gradual_decline")
        detail = loss_diagnosis.get("detail", "")
        termination = game_metadata.get("termination", "").lower() if game_metadata else ""
        
        # Direct answer based on loss type
        if loss_type == "single_critical_blunder":
            blunder_ply = loss_diagnosis.get("blunder_ply") or (loss_diagnosis.get("key_moves", [0])[0] if loss_diagnosis.get("key_moves") else None)
            narrative += f"**You lost due to a single critical blunder.** {detail}"
            if blunder_ply:
                narrative += f" The decisive error occurred at move {blunder_ply}."
            narrative += " The game was competitive until that moment.\n\n"
        elif loss_type == "multiple_blunders":
            narrative += f"**Multiple errors cost you the game.** {detail}"
            narrative += " Focus on consistency and checking your calculations.\n\n"
        elif loss_type == "timeout" or "time" in termination:
            narrative += f"**You lost on time.** {detail}"
            time_analysis = loss_diagnosis.get("time_analysis", {})
            slow_moves = time_analysis.get("slow_moves", [])
            if slow_moves:
                narrative += f" You spent significant time on {len(slow_moves)} moves, which contributed to time trouble.\n\n"
            else:
                narrative += "\n\n"
        elif loss_type == "time_pressure":
            narrative += f"**Time pressure led to mistakes.** {detail}"
            narrative += " You played well until time got low. Budget your clock more carefully.\n\n"
        elif loss_type == "tag_blindspot":
            tag = loss_diagnosis.get("tag", "")
            from tool_executor import translate_tag_to_natural_english
            tag_natural = translate_tag_to_natural_english(tag)
            narrative += f"**A positional blindspot cost you.** {detail}"
            narrative += f" You struggled with {tag_natural} positions.\n\n"
        else:
            narrative += f"**Gradual decline.** {detail}"
            narrative += " No single moment lost the game - it was an accumulation of small errors.\n\n"
        
        # Brief summary of key moments (just the relevant ones)
        if selected_moments:
            narrative += "**Key moments:**\n"
            for i, moment in enumerate(selected_moments[:5], 1):  # Limit to 5 for loss diagnosis
                ply = moment.get("ply", 0)
                labels = moment.get("labels", [])
                primary = moment.get("primary_label", "")
                
                if primary == "blunder":
                    narrative += f"{i}. Move {ply}: Critical blunder\n"
                elif primary == "mistake":
                    narrative += f"{i}. Move {ply}: Mistake\n"
                elif "advantage_shift" in labels:
                    narrative += f"{i}. Move {ply}: Advantage shifted against you\n"
                elif "missed_critical_win" in labels:
                    narrative += f"{i}. Move {ply}: Missed winning opportunity\n"
        
        return narrative
    
    def _generate_query_driven_narrative(
        self,
        query_intent: str,
        selected_moments: List[Dict],
        ply_records: List[Dict],
        filter_criteria: Dict,
        narrative_focus: str,
        username: str,
        platform: str,
        total_games: int,
        loss_diagnosis: Dict = None,
        game_metadata: Dict = None,
        game_result: str = None
    ) -> str:
        """
        Generate dynamic, conversational narrative based on query intent.
        Directly answers the user's question in a natural way.
        """
        narrative = ""
        
        # Get actual game result from metadata
        actual_result = game_result or (game_metadata.get("result", "") if game_metadata else "")
        termination = (game_metadata.get("termination", "") if game_metadata else "").lower()
        
        # Normalize result
        if actual_result:
            actual_result_lower = actual_result.lower()
            if "1-0" in actual_result or "white wins" in actual_result_lower or "win" in actual_result_lower:
                is_win = True
                is_loss = False
                is_draw = False
            elif "0-1" in actual_result or "black wins" in actual_result_lower or "loss" in actual_result_lower or "lose" in actual_result_lower:
                is_win = False
                is_loss = True
                is_draw = False
            elif "1/2" in actual_result or "draw" in actual_result_lower:
                is_win = False
                is_loss = False
                is_draw = True
            else:
                is_win = is_loss = is_draw = False
        else:
            is_win = is_loss = is_draw = False
        
        # Only correct the game result for loss_diagnosis queries
        # (e.g., user asked "why did I lose?" but they actually drew/won)
        # Do NOT show this for blunder_review or general queries
        if query_intent == "loss_diagnosis" and is_draw:
            narrative += f"You didn't actually lose this game – it was a **draw**"
            if termination and ("time" in termination or "insufficient" in termination or "stalemate" in termination):
                narrative += f" ({termination})"
            narrative += ".\n\n"
            narrative += "Here's what contributed to the draw:\n\n"
        elif query_intent == "loss_diagnosis" and is_win:
            narrative += f"You didn't lose this game – you **won**!\n\n"
            narrative += "Here's a look at the key moments:\n\n"
        
        if query_intent == "time_analysis":
            # Sort by time spent
            moments_with_time = []
            for moment in selected_moments:
                ply = moment.get("ply")
                record = next((r for r in ply_records if r.get("ply") == ply), None)
                if record:
                    moments_with_time.append((moment, record))
            
            moments_with_time.sort(key=lambda x: x[1].get("time_spent_s", 0), reverse=True)
            
            if moments_with_time:
                narrative += f"Here are the moves where you spent the most time:\n\n"
                for i, (moment, record) in enumerate(moments_with_time[:10], 1):
                    ply = moment.get("ply")
                    time_spent = record.get("time_spent_s", 0)
                    move_san = record.get("san", "?")
                    narrative += f"{i}. Move {ply} ({move_san}): {time_spent:.1f} seconds\n"
            else:
                narrative += "I couldn't find significant time usage data for this game.\n"
        
        elif query_intent == "blunder_review":
            if len(selected_moments) == 0:
                narrative += "Great news – you didn't make any blunders in this game!\n"
            elif len(selected_moments) == 1:
                ply = selected_moments[0].get("ply")
                record = next((r for r in ply_records if r.get("ply") == ply), {})
                move_san = record.get("san", "?")
                cp_loss = record.get("cp_loss", 0)
                narrative += f"You made one blunder in this game:\n\n"
                narrative += f"• Move {ply} ({move_san}): {cp_loss:.0f}cp loss\n"
            else:
                narrative += f"You made {len(selected_moments)} blunders in this game:\n\n"
                for i, moment in enumerate(selected_moments, 1):
                    ply = moment.get("ply")
                    record = next((r for r in ply_records if r.get("ply") == ply), {})
                    move_san = record.get("san", "?")
                    cp_loss = record.get("cp_loss", 0)
                    narrative += f"{i}. Move {ply} ({move_san}): {cp_loss:.0f}cp loss\n"
        
        elif query_intent == "best_moves":
            if len(selected_moments) == 0:
                narrative += "I couldn't identify any standout best moves in this game.\n"
            else:
                narrative += f"Here are your best moves in this game:\n\n"
                for i, moment in enumerate(selected_moments[:10], 1):
                    ply = moment.get("ply")
                    record = next((r for r in ply_records if r.get("ply") == ply), {})
                    move_san = record.get("san", "?")
                    category = record.get("category", "excellent")
                    narrative += f"{i}. Move {ply} ({move_san}): {category}\n"
        
        elif query_intent == "tactical_moments":
            if len(selected_moments) == 0:
                narrative += "There weren't any significant tactical moments in this game.\n"
            else:
                narrative += f"Here are the key tactical moments:\n\n"
                for i, moment in enumerate(selected_moments[:15], 1):
                    ply = moment.get("ply")
                    record = next((r for r in ply_records if r.get("ply") == ply), {})
                    move_san = record.get("san", "?")
                    category = record.get("category", "tactical")
                    narrative += f"{i}. Move {ply} ({move_san}): {category}\n"
        
        elif query_intent == "time_pressure":
            if len(selected_moments) == 0:
                narrative += "You didn't make any significant errors under time pressure.\n"
            else:
                narrative += f"These errors were made under time pressure:\n\n"
                for i, moment in enumerate(selected_moments, 1):
                    ply = moment.get("ply")
                    record = next((r for r in ply_records if r.get("ply") == ply), {})
                    move_san = record.get("san", "?")
                    time_spent = record.get("time_spent_s", 0)
                    cp_loss = record.get("cp_loss", 0)
                    narrative += f"{i}. Move {ply} ({move_san}): {time_spent:.1f}s, {cp_loss:.0f}cp loss\n"
        
        elif query_intent == "advantage_shifts":
            if len(selected_moments) == 0:
                narrative += "There weren't significant advantage shifts in this game.\n"
            else:
                narrative += f"Here are the key moments where the advantage changed:\n\n"
                for i, moment in enumerate(selected_moments, 1):
                    ply = moment.get("ply")
                    record = next((r for r in ply_records if r.get("ply") == ply), {})
                    move_san = record.get("san", "?")
                    narrative += f"{i}. Move {ply} ({move_san}): Advantage shifted\n"
        
        elif query_intent == "loss_diagnosis":
            # Draw/win cases already handled at the top of function with opening sentence
            if is_draw or is_win:
                # List key moments - opening sentence already added above
                if selected_moments:
                    for i, moment in enumerate(selected_moments[:5], 1):
                        ply = moment.get("ply", 0)
                        labels = moment.get("labels", [])
                        primary = moment.get("primary_label", "")
                        record = next((r for r in ply_records if r.get("ply") == ply), {})
                        move_san = record.get("san", "?")
                        cp_loss = record.get("cp_loss", 0)
                        
                        if primary == "blunder" or primary == "mistake":
                            narrative += f"{i}. Move {ply} ({move_san}): {primary.title()} ({cp_loss:.0f}cp)\n"
                        elif primary in ["best", "excellent"]:
                            narrative += f"{i}. Move {ply} ({move_san}): Excellent move\n"
                        elif "advantage_shift" in labels:
                            narrative += f"{i}. Move {ply} ({move_san}): Critical moment\n"
                        else:
                            narrative += f"{i}. Move {ply} ({move_san}): Key moment\n"
                else:
                    narrative += "No significant moments to highlight.\n"
            else:
                # They actually lost - give direct loss explanation
                if not loss_diagnosis or not loss_diagnosis.get("loss_type"):
                    narrative += "You lost this game. Let's look at what happened:\n\n"
                else:
                    loss_type = loss_diagnosis.get("loss_type", "gradual_decline")
                    detail = loss_diagnosis.get("detail", "")
                    local_termination = game_metadata.get("termination", "").lower() if game_metadata else ""
                    
                    # Direct answer based on loss type - conversational
                    if loss_type == "single_critical_blunder":
                        blunder_ply = loss_diagnosis.get("blunder_ply") or (loss_diagnosis.get("key_moves", [0])[0] if loss_diagnosis.get("key_moves") else None)
                        narrative += f"**A single critical blunder cost you the game.** {detail}"
                        if blunder_ply:
                            narrative += f" The decisive error was at move {blunder_ply}."
                        narrative += " The game was competitive until that point.\n\n"
                    elif loss_type == "multiple_blunders":
                        narrative += f"**Multiple errors led to your loss.** {detail}"
                        narrative += " Focus on consistency and double-checking your calculations.\n\n"
                    elif loss_type == "timeout" or "time" in local_termination:
                        narrative += f"**You ran out of time.** {detail}"
                        time_analysis = loss_diagnosis.get("time_analysis", {})
                        slow_moves = time_analysis.get("slow_moves", [])
                        if slow_moves:
                            narrative += f" You spent too long on {len(slow_moves)} moves, which led to time trouble.\n\n"
                        else:
                            narrative += "\n\n"
                    elif loss_type == "time_pressure":
                        narrative += f"**Time pressure caused critical mistakes.** {detail}"
                        narrative += " You were playing well until the clock got low. Work on time management.\n\n"
                    elif loss_type == "tag_blindspot":
                        tag = loss_diagnosis.get("tag", "")
                        tag_natural = translate_tag_to_natural_english(tag) if tag else "certain positions"
                        narrative += f"**A positional weakness led to your loss.** {detail}"
                        narrative += f" You struggled with {tag_natural} positions.\n\n"
                    else:
                        narrative += f"**The loss was gradual.** {detail}"
                        narrative += " No single move lost the game – it was an accumulation of small inaccuracies.\n\n"
                
                # Key moments list for actual loss
                if selected_moments:
                    narrative += "**Key moments:**\n"
                    for i, moment in enumerate(selected_moments[:5], 1):
                        ply = moment.get("ply", 0)
                        labels = moment.get("labels", [])
                        primary = moment.get("primary_label", "")
                        record = next((r for r in ply_records if r.get("ply") == ply), {})
                        move_san = record.get("san", "?")
                        cp_loss = record.get("cp_loss", 0)
                        
                        if primary == "blunder":
                            narrative += f"{i}. Move {ply} ({move_san}): Blunder ({cp_loss:.0f}cp loss)\n"
                        elif primary == "mistake":
                            narrative += f"{i}. Move {ply} ({move_san}): Mistake ({cp_loss:.0f}cp loss)\n"
                        elif "advantage_shift" in labels:
                            narrative += f"{i}. Move {ply} ({move_san}): Advantage shifted against you\n"
                        elif "missed_critical_win" in labels:
                            narrative += f"{i}. Move {ply} ({move_san}): Missed winning opportunity\n"
                        else:
                            narrative += f"{i}. Move {ply} ({move_san}): Key moment\n"
        
        else:
            # Custom/flexible query - use LLM's narrative focus conversationally
            # Use narrative_focus to guide the opening
            if narrative_focus and not narrative.strip():
                # LLM provided a focus - use it conversationally
                narrative += f"{narrative_focus}\n\n"
            
            if selected_moments:
                narrative += f"Here are the {len(selected_moments)} key moments:\n\n"
                for i, moment in enumerate(selected_moments[:15], 1):
                    ply = moment.get("ply")
                    record = next((r for r in ply_records if r.get("ply") == ply), {})
                    if not record:
                        # Try to get record from moment itself
                        record = moment.get("record", {})
                    
                    move_san = record.get("san", "?")
                    category = record.get("category", "")
                    cp_loss = record.get("cp_loss", 0)
                    time_spent = record.get("time_spent_s", 0)
                    
                    # Build informative line
                    details = []
                    if category:
                        details.append(category)
                    if cp_loss and cp_loss > 50:
                        details.append(f"{cp_loss:.0f}cp loss")
                    if time_spent and time_spent > 10:
                        details.append(f"{time_spent:.1f}s")
                    
                    detail_str = f" ({', '.join(details)})" if details else ""
                    narrative += f"{i}. Move {ply} ({move_san}){detail_str}\n"
            else:
                narrative += "I couldn't find any moments matching your query.\n"
        
        return narrative
    
    def _generate_comprehensive_narrative(
        self,
        summary: Dict,
        phase_stats: Dict,
        tag_stats: Dict,
        selected_moments: List[Dict],
        username: str,
        platform: str,
        total_games: int
    ) -> str:
        """
        Generate comprehensive narrative showing all errors.
        """
        narrative = ""
        
        if total_games == 1:
            narrative += f"I just finished analyzing your last game on **{platform}** as **{username}**. "
        else:
            narrative += f"I just finished analyzing your last **{total_games} games** on **{platform}** as **{username}**. "
        narrative += "Here's a comprehensive breakdown of all errors.\n\n"
        
        narrative += f"**All mistakes and blunders ({len(selected_moments)} total):**\n\n"
        for i, moment in enumerate(selected_moments, 1):
            ply = moment.get("ply")
            primary = moment.get("primary_label", "")
            narrative += f"{i}. Move {ply}: {primary}\n"
        
        return narrative
    
    def _generate_specific_narrative(
        self,
        summary: Dict,
        selected_moments: List[Dict],
        user_query: str,
        username: str,
        platform: str,
        total_games: int
    ) -> str:
        """
        Generate narrative for specific queries (e.g., "top 3 moves").
        """
        narrative = ""
        
        if total_games == 1:
            narrative += f"Based on your query, here's what I found from your last game on **{platform}** as **{username}**.\n\n"
        else:
            narrative += f"Based on your query, here's what I found.\n\n"
        
        narrative += f"**Selected moments ({len(selected_moments)}):**\n\n"
        for i, moment in enumerate(selected_moments, 1):
            ply = moment.get("ply")
            primary = moment.get("primary_label", "")
            narrative += f"{i}. Move {ply}: {primary}\n"
        
        return narrative
    
    def _generate_prioritized_suggestions_with_tags(
        self,
        phase_stats: Dict,
        avg_accuracy: float,
        opening_perf: list,
        tag_stats: Dict,
        significant_stats: list
    ) -> list:
        """Generate suggestions prioritizing significant tag weaknesses."""
        suggestions = []
        
        # Priority 1: Tag-based weakness (if significant)
        for stat in significant_stats[:1]:
            if stat.get("type") == "tag_accuracy":
                tag = stat.get("tag", "unknown")
                acc = stat.get("accuracy", 0)
                suggestions.append({
                    'title': f"Master {tag} positions",
                    'detail': f"At {acc:.1f}% accuracy, this is your biggest blind spot. "
                             f"Study games featuring {tag} patterns and practice recognizing key ideas."
                })
                break
            elif stat.get("type") == "tag_preference":
                tag = stat.get("tag", "unknown")
                pattern = stat.get("pattern", "")
                if pattern == "seeks":
                    suggestions.append({
                        'title': f"Reconsider {tag} preferences",
                        'detail': f"You actively seek these positions but struggle with them. "
                                 f"Either study them deeply or avoid creating them unnecessarily."
                    })
                    break
        
        # Priority 2: Phase weakness
        if phase_stats:
            valid_phases = [(name, data) for name, data in phase_stats.items()
                          if data.get('accuracy') is not None and data.get('move_count', 0) > 0]
            if valid_phases:
                weakest = min(valid_phases, key=lambda x: x[1].get('accuracy', 100))
                if weakest[1].get('accuracy', 100) < 75:
                    suggestions.append({
                        'title': f"Strengthen your {weakest[0]}",
                        'detail': f"At {weakest[1].get('accuracy', 0):.1f}%, this phase is costing you. "
                                 f"Study {weakest[0]} fundamentals and practice key techniques."
                    })
        
        # Priority 3: General accuracy
        if avg_accuracy < 85 and len(suggestions) < 3:
            suggestions.append({
                'title': "Reduce tactical errors",
                'detail': "Focus on calculating candidate moves thoroughly before playing. Aim for 85%+ accuracy."
            })
        
        # Priority 4: Time management
        if len(suggestions) < 3:
            suggestions.append({
                'title': "Improve time management",
                'detail': "Avoid time pressure situations. Budget your clock wisely in the opening and middlegame."
            })
        
        # Priority 5: Pattern recognition
        if len(suggestions) < 3:
            suggestions.append({
                'title': "Study tactical patterns",
                'detail': "Work on recognizing common tactical motifs to improve calculation speed and accuracy."
            })
        
        return suggestions
    
    # ========================================================================
    # INVESTIGATION TOOL IMPLEMENTATIONS
    # ========================================================================
    
    async def _investigate(self, args: Dict, context: Dict) -> Dict:
        """Run a complex multi-step investigation"""
        try:
            from planning_agent import InvestigationPlanner
            from step_executor import StepExecutor
            
            query = args.get("query", "")
            investigation_type = args.get("investigation_type")
            target_player = args.get("target_player")
            target_event = args.get("target_event")
            platform = args.get("platform")
            username = args.get("username")
            
            # Build context for planner
            inv_context = {
                "player": target_player,
                "event": target_event,
                "platform": platform,
                "username": username,
                **context
            }
            
            # Create plan
            planner = InvestigationPlanner(self.openai_client)
            plan = await planner.create_plan(query, inv_context)
            
            # Execute plan
            executor = StepExecutor(
                tool_executor=self,
                openai_client=self.openai_client,
                engine_queue=self.engine_queue
            )
            
            result = await executor.execute_plan(plan, inv_context)
            
            return {
                "success": result.success,
                "investigation_type": plan.investigation_type.value,
                "steps_completed": len([s for s in result.step_results.values() if s.success]),
                "synthesis": result.synthesis,
                "failed_steps": result.failed_steps,
                "duration_ms": result.total_duration_ms
            }
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"error": f"Investigation failed: {str(e)}"}
    
    async def _web_search(self, args: Dict) -> Dict:
        """Search the web for chess information"""
        try:
            from tools.web_search import web_search
            
            query = args.get("query", "")
            max_results = args.get("max_results", 5)
            search_filter = args.get("search_filter", "all")
            
            result = await web_search(
                query=query,
                max_results=max_results,
                search_filter=search_filter
            )
            
            return result
            
        except Exception as e:
            return {"error": f"Web search failed: {str(e)}"}
    
    async def _multi_depth_analyze(self, args: Dict) -> Dict:
        """Analyze a game at multiple depths"""
        try:
            from tools.multi_depth_analysis import multi_depth_analyze
            
            pgn = args.get("pgn", "")
            depths = args.get("depths", [10, 20, 30])
            focus_side = args.get("focus_side", "both")
            
            result = await multi_depth_analyze(
                pgn=pgn,
                depths=depths,
                focus_side=focus_side,
                engine_queue=self.engine_queue
            )
            
            return result
            
        except Exception as e:
            return {"error": f"Multi-depth analysis failed: {str(e)}"}
    
    async def _engine_correlation(self, args: Dict) -> Dict:
        """Calculate engine correlation for a game"""
        try:
            from tools.engine_correlation import engine_correlation
            
            pgn = args.get("pgn", "")
            depth = args.get("depth", 25)
            top_n = args.get("top_n", 3)
            exclude_book = args.get("exclude_book_moves", 10)
            
            result = await engine_correlation(
                pgn=pgn,
                depth=depth,
                top_n=top_n,
                exclude_book_moves=exclude_book,
                engine_queue=self.engine_queue
            )
            
            return result
            
        except Exception as e:
            return {"error": f"Engine correlation failed: {str(e)}"}
    
    async def _calculate_baseline(self, args: Dict) -> Dict:
        """Calculate player baseline from games"""
        try:
            from tools.player_baseline import calculate_baseline
            
            games = args.get("games", [])
            exclude_outliers = args.get("exclude_outliers", True)
            
            result = await calculate_baseline(
                games=games,
                exclude_outliers=exclude_outliers
            )
            
            return result
            
        except Exception as e:
            return {"error": f"Baseline calculation failed: {str(e)}"}
    
    async def _detect_anomalies(self, args: Dict) -> Dict:
        """Detect statistical anomalies in performance"""
        try:
            from tools.anomaly_detection import detect_anomalies
            
            test_games = args.get("test_games", [])
            baseline = args.get("baseline", {})
            metrics = args.get("metrics")
            
            result = await detect_anomalies(
                test_games=test_games,
                baseline=baseline,
                metrics=metrics
            )
            
            return result
            
        except Exception as e:
            return {"error": f"Anomaly detection failed: {str(e)}"}
    
    def format_result_for_llm(self, result: Dict, tool_name: str) -> str:
        """Format tool result as text for LLM"""
        if result.get("error"):
            return f"Error: {result['error']}"
        
        # Format based on tool type
        if tool_name == "analyze_position":
            # Full endpoint response is in endpoint_response
            endpoint_data = result.get("endpoint_response", {})
            fen = result.get("fen", "")
            eval_cp = endpoint_data.get("eval_cp", 0)
            mate_in = endpoint_data.get("mate_in")
            
            # Get side to move
            turn = "White" if " w " in fen else "Black" if " b " in fen else "?"
            
            # Convert to pawns
            eval_pawns = eval_cp / 100.0
            
            # Get candidates
            candidates = endpoint_data.get("candidate_moves", [])
            best_move = candidates[0].get("move") if candidates else "No move"
            best_eval = candidates[0].get("eval_cp", 0) / 100.0 if candidates else 0
            
            # Determine winner
            if eval_cp > 50:
                winner = f"White is winning by {eval_pawns:.2f} pawns"
            elif eval_cp < -50:
                winner = f"Black is winning by {abs(eval_pawns):.2f} pawns"
            elif abs(eval_cp) < 20:
                winner = "Position is equal (±0.00 pawns)"
            else:
                winner = f"{'White' if eval_cp > 0 else 'Black'} has a small edge ({abs(eval_pawns):.2f} pawns)"
            
            # Signal frontend to trigger full analysis, but don't show this message
            return "__TRIGGER_ANALYZE_POSITION__"
        
        elif tool_name == "review_full_game":
            summary = result.get("summary", {})
            return f"Game reviewed: {summary.get('total_moves', 0)} moves, {summary.get('opening', 'Unknown')} opening, {summary.get('key_points', 0)} key moments identified. Character: {summary.get('game_character', 'unknown')}."
        
        elif tool_name == "fetch_and_review_games":
            if result.get("error") == "username_required":
                return result.get("message", "Username required")
            elif result.get("error"):
                return f"Error: {result.get('message', result.get('error'))}"
            
            games_analyzed = result.get('games_analyzed', 0)
            avg_acc = _safe_float((result.get('stats', {}) or {}).get('avg_accuracy'), 0.0)
            return f"Personal review complete: Analyzed {games_analyzed} games from {result.get('platform', 'platform')}, average accuracy {avg_acc:.1f}%. Displaying narrative and charts in chat."

        elif tool_name == "select_games":
            if result.get("error") == "info_required":
                return result.get("message", "Missing account info for selecting games.")
            if result.get("error"):
                return f"Error: {result.get('message', result.get('error'))}"
            total = result.get("total_candidates", 0)
            selected_flat = result.get("selected_flat") or []
            return f"Selected {len(selected_flat)} game(s) from {total} candidate games. Displaying game list in chat."
        
        elif tool_name == "generate_training_session":
            return f"{result.get('message', 'Training generated')}. Created {result.get('drills_generated', 0)} drills."
        
        elif tool_name == "setup_position":
            fen = result.get("fen", "Position")
            pgn = result.get("pgn", "")
            orientation = result.get("orientation", "white")
            annotations = result.get("move_annotations", {})
            
            msg = f"Position displayed (board oriented from {orientation}'s perspective)"
            if pgn:
                msg += f". Game loaded with {len(pgn.split('.')) - 1} moves"
            if annotations:
                msg += f". {len(annotations)} moves have annotations"
            return msg
        
        # Investigation tools
        elif tool_name == "investigate":
            inv_type = result.get("investigation_type", "investigation")
            steps = result.get("steps_completed", 0)
            synthesis = result.get("synthesis", "")
            
            msg = f"Investigation complete ({inv_type}): {steps} analysis steps run.\n\n"
            if synthesis:
                msg += synthesis
            return msg
        
        elif tool_name == "web_search":
            results = result.get("results", [])
            context = result.get("news_context", "")
            
            if results:
                msg = f"Found {len(results)} results:\n"
                for r in results[:3]:
                    msg += f"- {r.get('title', 'No title')}: {r.get('snippet', '')[:100]}...\n"
                if context:
                    msg += f"\nContext: {context[:300]}..."
                return msg
            return "No results found."
        
        elif tool_name == "multi_depth_analyze":
            comparison = result.get("depth_comparison", [])
            indicators = result.get("suspicion_indicators", {})
            
            msg = "Multi-depth analysis:\n"
            for d in comparison:
                msg += f"- Depth {d['depth']}: {d['accuracy']:.1f}% accuracy, {d['avg_cp_loss']:.1f} avg CP loss\n"
            
            if any(indicators.values()):
                msg += "\nFlags: "
                flags = [k for k, v in indicators.items() if v]
                msg += ", ".join(flags)
            return msg
        
        elif tool_name == "engine_correlation":
            top1 = result.get("top1_match", 0)
            top3 = result.get("top3_match", 0)
            level = result.get("suspicion_level", "unknown")
            
            return f"Engine correlation: {top1:.1f}% top-1 match, {top3:.1f}% top-3 match. Suspicion level: {level}."
        
        elif tool_name == "calculate_baseline":
            acc = result.get("accuracy", {})
            games = result.get("games_analyzed", 0)
            
            if acc:
                return f"Baseline calculated from {games} games: {acc.get('mean', 0):.1f}% accuracy (±{acc.get('std', 0):.1f})"
            return f"Baseline calculated from {games} games."
        
        elif tool_name == "detect_anomalies":
            score = result.get("anomaly_score", 0)
            flags = result.get("flags", [])
            interpretation = result.get("interpretation", "")
            
            msg = f"Anomaly score: {score:.2f}\n"
            if flags:
                msg += f"Flags: {', '.join(flags)}\n"
            if interpretation:
                msg += interpretation
            return msg
        
        elif tool_name == "analyze_move":
            # Get all data from endpoint_response
            endpoint_response = result.get("endpoint_response", {})
            
            # Core metrics
            move_played = result.get("move") or result.get("move_san") or endpoint_response.get("move_played") or endpoint_response.get("move_san", "unknown")
            is_best = result.get("is_best_move") or endpoint_response.get("is_best_move", False)
            cp_loss = result.get("cp_loss") or endpoint_response.get("cp_loss", 0)
            move_category = endpoint_response.get("move_category", "")
            eval_before = endpoint_response.get("eval_before_cp", 0)
            eval_after = endpoint_response.get("eval_after_cp", 0)
            best_move = endpoint_response.get("best_move_san") or endpoint_response.get("best_move", "")
            
            # Extract PV moves from analysis or confidence data
            def extract_pv_san(analysis_obj_key, fen_before):
                """Extract PV in SAN format from analysis objects"""
                pv_san = None
                
                # Try to get PV from analysis candidate_moves (most direct)
                if analysis and isinstance(analysis, dict):
                    af_obj = analysis.get(analysis_obj_key, {})
                    if af_obj:
                        candidates = af_obj.get("candidate_moves", [])
                        if candidates and len(candidates) > 0:
                            pv_san = candidates[0].get("pv_san", "")
                            if pv_san:
                                return pv_san
                
                # Fallback: try to get PV from confidence data and convert UCI to SAN
                if confidence and isinstance(confidence, dict):
                    conf_key = "played_move" if analysis_obj_key == "af_played" else "best_move"
                    conf_data = confidence.get(conf_key, {})
                    if conf_data and isinstance(conf_data, dict):
                        nodes = conf_data.get("nodes", [])
                        if nodes:
                            main_line = nodes[0] if nodes else None
                            if main_line and isinstance(main_line, dict):
                                pv_moves = main_line.get("pv", [])
                                if pv_moves and isinstance(pv_moves, list):
                                    # Convert UCI to SAN
                                    try:
                                        import chess
                                        board_temp = chess.Board(fen_before)
                                        pv_san_list = []
                                        for move_uci in pv_moves[:8]:  # Limit to 8 moves
                                            try:
                                                move_obj = chess.Move.from_uci(str(move_uci))
                                                pv_san_list.append(board_temp.san(move_obj))
                                                board_temp.push(move_obj)
                                            except:
                                                break
                                        if pv_san_list:
                                            pv_san = " ".join(pv_san_list)
                                    except Exception as e:
                                        pass
                
                return pv_san
            
            # Get PV for played move
            analysis = endpoint_response.get("analysis", {})
            confidence = endpoint_response.get("confidence", {})
            fen_before = endpoint_response.get("fen_before", "")
            played_pv_san = extract_pv_san("af_played", fen_before)
            
            # Get PV for best move (if not best move)
            best_pv_san = None
            if not is_best:
                best_pv_san = extract_pv_san("af_best", fen_before)
            
            # CLAIM LINE: Significant tag deltas from compare_tags_for_move_analysis
            played_move_description = endpoint_response.get("played_move_description", {})
            claim_line = {
                "tags_gained": played_move_description.get("tags_gained", []),
                "tags_lost": played_move_description.get("tags_lost", []),
                "theme_changes": played_move_description.get("theme_changes", {}),
                "summary": played_move_description.get("summary", ""),
                "principal_variation": played_pv_san  # PV that supports the claim line
            }
            
            # Best move description (if not best move)
            best_move_description = endpoint_response.get("best_move_description", {}) if not is_best else None
            if best_move_description:
                claim_line["best_move_claim_line"] = {
                    "tags_gained": best_move_description.get("tags_gained", []),
                    "tags_lost": best_move_description.get("tags_lost", []),
                    "theme_changes": best_move_description.get("theme_changes", {}),
                    "summary": best_move_description.get("summary", ""),
                    "principal_variation": best_pv_san  # PV for best move
                }
            
            # Additional context
            opening_name = endpoint_response.get("opening_name", "")
            is_theory = endpoint_response.get("is_theory", False)
            threat_info = endpoint_response.get("played_move_threat_category") or endpoint_response.get("played_move_threat_description", "")
            
            # Build comprehensive data structure - let LLM format based on system_prompt_additions
            formatted_data = {
                "move": move_played,
                "is_best_move": is_best,
                "quality": move_category,
                "cp_loss": cp_loss,
                "evaluation": {
                    "before_cp": eval_before,
                    "after_cp": eval_after,
                    "before_pawns": round(eval_before / 100.0, 2),
                    "after_pawns": round(eval_after / 100.0, 2)
                },
                "best_move": best_move if not is_best else None,
                "claim_line": claim_line,  # Significant tag deltas with PV for citation
                "opening": {
                    "name": opening_name,
                    "is_theory": is_theory
                },
                "threat": threat_info if threat_info else None
            }
            
            # Return as JSON - LLM will format based on system_prompt_additions
            import json
            return json.dumps(formatted_data, indent=2)
        
        else:
            return json.dumps(result, indent=2)
    
    def _set_ai_game(self, args: Dict, context: Dict) -> Dict:
        """
        Set AI game mode. This tool just returns a UI command that will be handled by the frontend.
        The tool doesn't need to do anything - it just signals the frontend to enable AI game mode.
        """
        active = args.get("active", False)
        ai_side = args.get("ai_side", "auto")
        make_move_now = args.get("make_move_now", False)
        
        # Normalize ai_side: "auto" -> null for frontend
        if ai_side == "auto":
            ai_side = None
        
        # Return a result that includes a UI command
        # The task controller will extract this and add it to ui_commands
        return {
            "success": True,
            "active": active,
            "ai_side": ai_side,
            "make_move_now": make_move_now,
            "ui_command": {
                "action": "set_ai_game",
                "params": {
                    "active": active,
                    "ai_side": ai_side,
                    "make_move_now": make_move_now
                }
            }
        }
    
    async def _add_personal_review_graph(self, args: Dict, context: Dict) -> Dict:
        """
        Add a personal review graph to the chat.
        Fetches game data, groups it, builds series, and returns graph structure.
        """
        import uuid
        from profile_analytics.graph_utils import (
            group_by_game, group_by_day, group_by_batch5,
            build_series, assign_color
        )
        from profile_analytics.graph_data import build_graph_game_point
        
        user_id = context.get("user_id")
        if not user_id:
            return {"error": "User ID not found in context"}
        
        if not self.supabase_client:
            return {"error": "Database client not available"}
        
        # Get tool arguments
        data_type = args.get("data_type")
        series_name = args.get("series_name", "Series")
        params = args.get("params", {})
        grouping = args.get("grouping", "game")
        x_range = args.get("x_axis_range")
        color = args.get("color")
        
        # Fetch game data
        limit = 60
        try:
            # Try to fetch from pre-computed table first
            if hasattr(self.supabase_client, 'client'):
                result = self.supabase_client.client.table("game_graph_data")\
                    .select("*")\
                    .eq("user_id", user_id)\
                    .order("game_date", desc=False)\
                    .limit(limit)\
                    .execute()
                games_data = result.data if result.data else []
            elif hasattr(self.supabase_client, '_execute_query'):
                query = """
                    SELECT * FROM public.game_graph_data
                    WHERE user_id = %s
                    ORDER BY game_date ASC NULLS LAST
                    LIMIT %s
                """
                games_data = self.supabase_client._execute_query(query, (user_id, limit))
            else:
                games_data = []
            
            # If no pre-computed data, fetch games and build points
            if not games_data:
                games = self.supabase_client.get_active_reviewed_games(
                    user_id, limit=limit, include_full_review=True
                )
                if not games:
                    return {"error": "No analyzed games found for user"}
                
                # Sort by date
                def _date_key(g):
                    gd = g.get("game_date")
                    if isinstance(gd, str):
                        return gd
                    return ""
                
                games_sorted = sorted(games, key=_date_key)
                games_data = [build_graph_game_point(g, idx) for idx, g in enumerate(games_sorted)]
            
            # Format games data
            games = []
            for idx, point in enumerate(games_data):
                games.append({
                    "index": idx,
                    "game_id": point.get("game_id") or point.get("id", ""),
                    "game_date": point.get("game_date"),
                    "result": point.get("result"),
                    "opening_name": point.get("opening_name"),
                    "opening_eco": point.get("opening_eco"),
                    "time_control": point.get("time_control"),
                    "overall_accuracy": float(point.get("overall_accuracy")) if point.get("overall_accuracy") is not None else None,
                    "piece_accuracy": point.get("piece_accuracy") or {},
                    "time_bucket_accuracy": point.get("time_bucket_accuracy") or {},
                    "tag_transitions": point.get("tag_transitions") or {"gained": {}, "lost": {}},
                })
            
            # Apply x-axis range filter if provided
            if x_range:
                start = x_range.get("start_game", 0)
                end = x_range.get("end_game", len(games))
                games = games[start:end]
            
            if not games:
                return {"error": "No games in specified range"}
            
            # Group games based on grouping mode
            if grouping == "game":
                time_points = group_by_game(games)
            elif grouping == "day":
                time_points = group_by_day(games)
            elif grouping == "batch5":
                time_points = group_by_batch5(games)
            else:
                return {"error": f"Unknown grouping mode: {grouping}"}
            
            # Build series entry
            series_id = str(uuid.uuid4())
            series_entry = {
                "id": series_id,
                "label": series_name,
                "kind": data_type,
                "color": color or assign_color(0),
                "params": params
            }
            
            # Build series
            built_series = build_series(series_entry, time_points)
            
            # Build x labels
            x_labels = [p.get("label", "") for p in time_points]
            
            # Return graph data structure
            graph_id = str(uuid.uuid4())
            return {
                "graph_id": graph_id,
                "series": [{
                    "id": built_series["entry"]["id"],
                    "name": built_series["entry"]["label"],
                    "color": built_series["entry"]["color"],
                    "rawValues": built_series["rawValues"],
                    "normalizedValues": built_series["normalizedValues"],
                }],
                "xLabels": x_labels,
                "grouping": grouping,
            }
            
        except Exception as e:
            import traceback
            print(f"   ❌ Error building graph: {e}")
            traceback.print_exc()
            return {"error": f"Failed to build graph: {str(e)}"}

