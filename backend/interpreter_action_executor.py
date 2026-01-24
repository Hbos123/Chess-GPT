"""
Interpreter Action Executor
Executes actions requested by the interpreter loop with caching and retry support
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
import asyncio
import time
import os
import hashlib
import json


@dataclass
class CachedResult:
    """A cached action result"""
    data: Any
    timestamp: float
    from_cache: bool = True


class ActionCache:
    """
    In-memory cache for action results.
    Prevents redundant API calls for identical requests.
    """
    
    def __init__(self, ttl_seconds: int = 300, max_entries: int = 100):
        self.ttl = ttl_seconds
        self.max_entries = max_entries
        self._cache: Dict[str, CachedResult] = {}
    
    def _make_key(self, action_type: str, params: Dict[str, Any]) -> str:
        """Generate cache key from action type and params"""
        content = f"{action_type}:{json.dumps(params, sort_keys=True, default=str)}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def get(self, action_type: str, params: Dict[str, Any]) -> Optional[CachedResult]:
        """Get cached result if exists and not expired"""
        key = self._make_key(action_type, params)
        
        if key in self._cache:
            result = self._cache[key]
            if time.time() - result.timestamp < self.ttl:
                return result
            else:
                del self._cache[key]
        
        return None
    
    def set(self, action_type: str, params: Dict[str, Any], data: Any):
        """Cache a result"""
        # Evict old entries if at capacity
        if len(self._cache) >= self.max_entries:
            self._evict_oldest()
        
        key = self._make_key(action_type, params)
        self._cache[key] = CachedResult(
            data=data,
            timestamp=time.time()
        )
    
    def _evict_oldest(self):
        """Remove oldest entries to make room"""
        if not self._cache:
            return
        
        # Sort by timestamp and remove oldest 10%
        sorted_keys = sorted(
            self._cache.keys(),
            key=lambda k: self._cache[k].timestamp
        )
        
        to_remove = max(1, len(sorted_keys) // 10)
        for key in sorted_keys[:to_remove]:
            del self._cache[key]
    
    def clear(self):
        """Clear all cached entries"""
        self._cache.clear()


class InterpreterActionExecutor:
    """
    Executes actions requested by the interpreter loop.
    Handles fetch, analyze, search, and compute actions.
    """
    
    def __init__(
        self,
        game_fetcher=None,
        engine_queue=None,
        openai_client=None,
        web_searcher=None,
        board_simulator=None,
        use_cache: bool = True,
        cache_ttl: int = 300
    ):
        self.game_fetcher = game_fetcher
        self.engine_queue = engine_queue
        self.openai_client = openai_client
        self.web_searcher = web_searcher
        
        # Initialize board simulator if not provided
        if board_simulator is None and engine_queue:
            from board_simulator import BoardSimulator
            board_simulator = BoardSimulator(engine_queue)
        self.board_simulator = board_simulator
        
        self.cache = ActionCache(ttl_seconds=cache_ttl) if use_cache else None
    
    async def execute(
        self, 
        action, 
        accumulated_data: Dict[str, Any] = None
    ) -> Any:
        """
        Execute an action and return the result.
        
        Args:
            action: InterpreterAction to execute
            accumulated_data: Previously accumulated data (for dependent actions)
        
        Returns:
            Action result data
        """
        from interpreter_loop import ActionType, InterpreterAction
        
        # Check cache first
        if self.cache:
            cached = self.cache.get(action.action_type.value, action.params)
            if cached:
                print(f"   📦 Cache hit for {action.action_type.value}")
                result = cached.data
                result["from_cache"] = True
                return result
        
        # Execute based on action type
        if action.action_type == ActionType.FETCH:
            result = await self._execute_fetch(action.params, accumulated_data)
        elif action.action_type == ActionType.ANALYZE:
            result = await self._execute_analyze(action.params, accumulated_data)
        elif action.action_type == ActionType.SEARCH:
            result = await self._execute_search(action.params)
        elif action.action_type == ActionType.COMPUTE:
            result = await self._execute_compute(action.params, accumulated_data)
        elif action.action_type == ActionType.TEST_MOVE:
            result = await self._execute_test_move(action.params, accumulated_data)
        elif action.action_type == ActionType.EXAMINE_PV:
            result = await self._execute_examine_pv(action.params, accumulated_data)
        elif action.action_type == ActionType.CHECK_CONSEQUENCE:
            result = await self._execute_check_consequence(action.params, accumulated_data)
        elif action.action_type == ActionType.SIMULATE_SEQUENCE:
            result = await self._execute_simulate_sequence(action.params, accumulated_data)
        else:
            raise ValueError(f"Unknown action type: {action.action_type}")
        
        # Cache the result
        if self.cache and result:
            self.cache.set(action.action_type.value, action.params, result)
        
        return result
    
    async def _execute_fetch(
        self, 
        params: Dict[str, Any],
        accumulated_data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Execute a fetch action (get games from platforms)"""
        if not self.game_fetcher:
            return {"error": "Game fetcher not available", "games": []}
        
        platforms = params.get("platforms", ["chess.com"])
        count = params.get("count", 10)
        username = params.get("username")
        time_controls = params.get("time_controls")
        result_filter = params.get("result_filter")
        
        all_games = []
        errors = []
        
        for platform in platforms:
            try:
                games = await self.game_fetcher.fetch_games(
                    username=username,
                    platform=platform,
                    max_games=count,
                    months_back=params.get("months_back", 6)
                )
                
                # Apply filters
                if time_controls:
                    games = [g for g in games if g.get("time_control") in time_controls]
                
                if result_filter and result_filter != "all":
                    games = self._filter_by_result(games, result_filter, username)
                
                all_games.extend(games)
                
            except Exception as e:
                errors.append(f"{platform}: {str(e)}")
        
        return {
            "games": all_games[:count],  # Limit total
            "total_fetched": len(all_games),
            "platforms": platforms,
            "errors": errors if errors else None
        }
    
    def _filter_by_result(
        self, 
        games: List[Dict], 
        result_filter: str,
        username: str = None
    ) -> List[Dict]:
        """Filter games by result"""
        filtered = []
        
        for game in games:
            result = game.get("result", "").lower()
            white = game.get("white", "").lower()
            black = game.get("black", "").lower()
            user_lower = (username or "").lower()
            
            is_white = user_lower and user_lower == white
            is_black = user_lower and user_lower == black
            
            if result_filter == "wins":
                if (is_white and "1-0" in result) or (is_black and "0-1" in result):
                    filtered.append(game)
            elif result_filter == "losses":
                if (is_white and "0-1" in result) or (is_black and "1-0" in result):
                    filtered.append(game)
            elif result_filter == "draws":
                if "1/2" in result or "draw" in result.lower():
                    filtered.append(game)
            else:
                filtered.append(game)
        
        return filtered
    
    async def _execute_analyze(
        self, 
        params: Dict[str, Any],
        accumulated_data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Execute an analysis action - uses /analyze_position endpoint for full candidate moves"""
        fen = params.get("fen")
        pgn = params.get("pgn")
        move = params.get("move")
        depth = params.get("depth", 18)
        lines = params.get("lines", 3)
        
        # If no FEN/PGN, try to get from accumulated data
        if not fen and not pgn and accumulated_data:
            for key, value in accumulated_data.items():
                if isinstance(value, dict):
                    if "fen" in value:
                        fen = value["fen"]
                        break
                    if "games" in value and value["games"]:
                        pgn = value["games"][0].get("pgn")
                        break
        
        if not fen and not pgn:
            return {"error": "No position to analyze"}
        
        # Use /analyze_position endpoint to get full structured response with candidate_moves
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                request_params = {
                    "fen": fen,
                    "depth": depth,
                    "lines": lines,
                    "light_mode": "false"  # String for query param
                }
                
                # Use BACKEND_URL or NEXT_PUBLIC_BACKEND_URL if set, otherwise default to localhost with BACKEND_PORT
                backend_url = os.getenv("BACKEND_URL") or os.getenv("NEXT_PUBLIC_BACKEND_URL")
                if not backend_url:
                    backend_port = int(os.getenv("BACKEND_PORT", "8001"))
                    backend_url = f"http://localhost:{backend_port}"
                async with session.get(
                    f"{backend_url}/analyze_position",
                    params=request_params,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        return {"error": f"Analysis failed: {error_text}"}
                    
                    result = await response.json()
                    
                    # Extract candidate moves for move testing
                    candidate_moves = []
                    if "candidate_moves" in result:
                        candidate_moves = result["candidate_moves"]
                    elif "white_analysis" in result and "candidate_moves" in result["white_analysis"]:
                        candidate_moves = result["white_analysis"]["candidate_moves"]
                    elif "black_analysis" in result and "candidate_moves" in result["black_analysis"]:
                        candidate_moves = result["black_analysis"]["candidate_moves"]
                    
                    return {
                        "fen": fen,
                        "eval_cp": result.get("eval_cp", 0),
                        "best_move": result.get("best_move"),
                        "candidate_moves": candidate_moves,  # CRITICAL for move testing
                        "pv": result.get("pv", []),
                        "depth": depth,
                        "endpoint_response": result  # Full response for reference
                    }
        except Exception as e:
            return {"error": str(e), "fen": fen}
    
    async def _analyze_with_engine(
        self,
        fen: str = None,
        pgn: str = None,
        move: str = None,
        depth: int = 18
    ) -> Dict[str, Any]:
        """Run analysis using the engine queue"""
        import chess
        
        # Set up position
        if pgn:
            import chess.pgn
            from io import StringIO
            game = chess.pgn.read_game(StringIO(pgn))
            if game:
                board = game.end().board()
                fen = board.fen()
        
        if not fen:
            fen = chess.STARTING_FEN
        
        board = chess.Board(fen)
        
        # Create analysis request
        request = {
            "type": "analyze",
            "fen": fen,
            "depth": depth,
            "lines": 3
        }
        
        # Submit to engine queue
        import asyncio
        future = asyncio.get_event_loop().create_future()
        
        await self.engine_queue.put((request, future))
        
        try:
            result = await asyncio.wait_for(future, timeout=30.0)
            
            # Format result
            return {
                "fen": fen,
                "eval": result.get("score", 0),
                "best_move": result.get("best_move"),
                "pv": result.get("pv", []),
                "depth": result.get("depth", depth),
                "mate": result.get("mate")
            }
        except asyncio.TimeoutError:
            return {"error": "Analysis timeout", "fen": fen}
    
    async def _execute_search(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a web search action"""
        query = params.get("query", "")
        
        if not query:
            return {"error": "No search query provided", "results": []}
        
        # Try to use web search tool if available
        if self.web_searcher:
            try:
                results = await self.web_searcher.search(query)
                return {"query": query, "results": results}
            except Exception as e:
                return {"error": str(e), "query": query, "results": []}
        
        # Try Tavily if configured
        try:
            from tools.web_search import web_search
            results = await web_search(query)
            return {"query": query, "results": results.get("results", [])}
        except Exception as e:
            return {"error": str(e), "query": query, "results": []}
    
    async def _execute_compute(
        self, 
        params: Dict[str, Any],
        accumulated_data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Execute a compute action"""
        compute_type = params.get("type", "")
        
        if compute_type == "baseline":
            return await self._compute_baseline(params, accumulated_data)
        elif compute_type == "correlation":
            return await self._compute_correlation(params, accumulated_data)
        elif compute_type == "anomaly":
            return await self._compute_anomalies(params, accumulated_data)
        elif compute_type == "complexity":
            return await self._compute_complexity(params, accumulated_data)
        elif compute_type == "critical_moments":
            return await self._compute_critical_moments(params, accumulated_data)
        else:
            return {"error": f"Unknown compute type: {compute_type}"}
    
    async def _compute_baseline(
        self, 
        params: Dict[str, Any],
        accumulated_data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Compute player baseline statistics"""
        # Get games from accumulated data
        games = self._extract_games(accumulated_data)
        
        if not games:
            return {"error": "No games available for baseline calculation"}
        
        try:
            from tools.player_baseline import calculate_baseline
            result = await calculate_baseline({"games": games})
            return result
        except Exception as e:
            # Fallback to basic stats
            total = len(games)
            wins = sum(1 for g in games if "1-0" in g.get("result", "") or "win" in g.get("result", "").lower())
            
            return {
                "games_analyzed": total,
                "win_rate": wins / total if total > 0 else 0,
                "average_accuracy": None,  # Would need engine analysis
                "strength_estimate": None
            }
    
    async def _compute_correlation(
        self, 
        params: Dict[str, Any],
        accumulated_data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Compute engine correlation"""
        games = self._extract_games(accumulated_data)
        
        if not games:
            return {"error": "No games available for correlation"}
        
        try:
            from tools.engine_correlation import engine_correlation
            result = await engine_correlation({
                "games": games,
                "depth": params.get("depth", 18)
            })
            return result
        except Exception as e:
            return {"error": str(e)}
    
    async def _compute_anomalies(
        self, 
        params: Dict[str, Any],
        accumulated_data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Detect anomalies in player performance"""
        games = self._extract_games(accumulated_data)
        
        if not games:
            return {"error": "No games available for anomaly detection"}
        
        try:
            from tools.anomaly_detection import detect_anomalies
            result = await detect_anomalies({
                "games": games,
                "baseline": accumulated_data.get("baseline")
            })
            return result
        except Exception as e:
            return {"error": str(e)}
    
    async def _compute_complexity(
        self, 
        params: Dict[str, Any],
        accumulated_data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Compute move complexity scores"""
        games = self._extract_games(accumulated_data)
        
        if not games:
            return {"error": "No games available for complexity scoring"}
        
        try:
            from tools.complexity_scorer import score_move_complexity
            result = await score_move_complexity({
                "games": games[:5]  # Limit for performance
            })
            return result
        except Exception as e:
            return {"error": str(e)}
    
    async def _compute_critical_moments(
        self, 
        params: Dict[str, Any],
        accumulated_data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Find critical moments in games"""
        games = self._extract_games(accumulated_data)
        
        if not games:
            return {"error": "No games available for critical moment detection"}
        
        try:
            from tools.critical_moments import find_critical_moments
            result = await find_critical_moments({
                "games": games[:3]  # Limit for performance
            })
            return result
        except Exception as e:
            return {"error": str(e)}
    
    def _extract_games(self, accumulated_data: Dict[str, Any]) -> List[Dict]:
        """Extract games from accumulated data"""
        if not accumulated_data:
            return []
        
        games = []
        for key, value in accumulated_data.items():
            if isinstance(value, dict) and "games" in value:
                games.extend(value["games"])
            elif isinstance(value, list):
                # Might be a list of games directly
                for item in value:
                    if isinstance(item, dict) and ("pgn" in item or "moves" in item):
                        games.append(item)
        
        return games
    
    async def _execute_test_move(
        self,
        params: Dict[str, Any],
        accumulated_data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Execute test_move action - test a move and follow PV"""
        if not self.board_simulator:
            return {"error": "Board simulator not available"}
        
        fen = params.get("fen")
        move_san = params.get("move_san")
        follow_pv = params.get("follow_pv", True)
        depth = params.get("depth", 12)
        
        if not fen or not move_san:
            return {"error": "Missing fen or move_san parameter"}
        
        try:
            result = await self.board_simulator.test_move(fen, move_san, follow_pv, depth)
            return result.to_dict()
        except Exception as e:
            return {"error": str(e)}
    
    async def _execute_examine_pv(
        self,
        params: Dict[str, Any],
        accumulated_data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Execute examine_pv action - analyze PV from position analysis"""
        # Get PV from accumulated data (from previous analyze action)
        pv_data = None
        if accumulated_data:
            for key, value in accumulated_data.items():
                if isinstance(value, dict) and ("pv" in value or "principal_variation" in value):
                    pv_data = value
                    break
        
        if not pv_data:
            return {"error": "No PV data found. Run analyze action first."}
        
        pv = pv_data.get("pv") or pv_data.get("principal_variation", [])
        
        # Extract insights about PV
        insights = []
        if isinstance(pv, list) and len(pv) > 0:
            # Check if knight moves in PV
            knight_moves = [m for m in pv if isinstance(m, str) and m.startswith("N")]
            if knight_moves:
                insights.append(f"Knight moves in PV: {knight_moves[0]}")
                # Find position of first knight move
                knight_index = pv.index(knight_moves[0])
                before_knight = pv[:knight_index]
                if before_knight:
                    insights.append(f"Moves before knight: {', '.join(before_knight)}")
            else:
                insights.append("Knight does not move in PV")
        
        return {
            "pv": pv,
            "insights": insights,
            "knight_moves": [m for m in pv if isinstance(m, str) and m.startswith("N")] if isinstance(pv, list) else []
        }
    
    async def _execute_check_consequence(
        self,
        params: Dict[str, Any],
        accumulated_data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Execute check_consequence action - check specific consequence of a move"""
        if not self.board_simulator:
            return {"error": "Board simulator not available"}
        
        fen = params.get("fen")
        move_san = params.get("move_san")
        consequence_type = params.get("consequence_type", "doubled_pawns")  # doubled_pawns, pins, captures
        
        if not fen or not move_san:
            return {"error": "Missing fen or move_san parameter"}
        
        try:
            # Test the move
            result = await self.board_simulator.test_move(fen, move_san, follow_pv=True, depth=12)
            
            # Check for specific consequence
            # Note: result is MoveTestResult from board_simulator, which has consequences field
            consequences = result.consequences
            found_consequence = None
            
            if consequence_type == "doubled_pawns":
                if "doubled_pawns" in consequences:
                    found_consequence = consequences["doubled_pawns"]
            elif consequence_type == "pins":
                if "pins" in consequences:
                    found_consequence = consequences["pins"]
            elif consequence_type == "captures":
                if "allows_captures" in consequences:
                    found_consequence = consequences["allows_captures"]
            
            return {
                "move_san": move_san,
                "consequence_type": consequence_type,
                "found": found_consequence is not None,
                "details": found_consequence,
                "all_consequences": consequences
            }
        except Exception as e:
            return {"error": str(e)}
    
    async def _execute_simulate_sequence(
        self,
        params: Dict[str, Any],
        accumulated_data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Execute simulate_sequence action - play out a sequence of moves"""
        if not self.board_simulator:
            return {"error": "Board simulator not available"}
        
        fen = params.get("fen")
        moves = params.get("moves", [])
        depth = params.get("depth", 12)
        
        if not fen or not moves:
            return {"error": "Missing fen or moves parameter"}
        
        try:
            result = await self.board_simulator.test_move_sequence(fen, moves, depth)
            return result
        except Exception as e:
            return {"error": str(e)}

