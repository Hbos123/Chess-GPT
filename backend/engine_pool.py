"""
Engine Pool - Manages multiple Stockfish instances for parallel analysis.

This module provides a pool of chess engines that can analyze positions
concurrently, significantly speeding up game reviews.
"""

import asyncio
import chess
import chess.engine
import json
import urllib.request
import urllib.parse
from concurrent.futures import ProcessPoolExecutor
from typing import List, Dict, Any, Optional, Tuple, Callable
from dataclasses import dataclass
import time

# Import parallel computation function (for ProcessPoolExecutor)
from parallel_analyzer import compute_themes_and_tags, compute_theme_scores


def check_lichess_masters(fen: str) -> dict:
    """Check if position exists in Lichess masters database."""
    try:
        url = f"https://explorer.lichess.ovh/masters?fen={urllib.parse.quote(fen)}"
        with urllib.request.urlopen(url, timeout=2) as response:
            data = json.loads(response.read())
            moves_list = data.get('moves', [])
            total_games = sum(move.get('white', 0) + move.get('draws', 0) + move.get('black', 0) 
                            for move in moves_list)
            theory_moves_uci = [move.get('uci', '') for move in moves_list if move.get('uci')]
            return {
                'isTheory': total_games > 0,
                'totalGames': total_games,
                'opening': data.get('opening', {}).get('name', ''),
                'eco': data.get('opening', {}).get('eco', ''),
                'theoryMoves': theory_moves_uci
            }
    except:
        return {'isTheory': False, 'totalGames': 0, 'opening': '', 'eco': '', 'theoryMoves': []}


@dataclass
class EngineStatus:
    """Status of a single engine in the pool"""
    id: int
    is_available: bool
    analyses_completed: int = 0
    last_used: Optional[float] = None


class EnginePool:
    """
    Pool of Stockfish engine instances for parallel analysis.
    
    Usage:
        pool = EnginePool(pool_size=4)
        await pool.initialize()
        
        # Analyze positions in parallel
        results = await pool.analyze_positions_parallel(
            positions=[("fen1", move1), ("fen2", move2), ...],
            depth=14
        )
        
        await pool.shutdown()
    """
    
    def __init__(self, pool_size: int = 4, stockfish_path: str = "./stockfish"):
        self.pool_size = pool_size
        self.stockfish_path = stockfish_path
        self.engines: List[chess.engine.UciProtocol] = []
        self.available: asyncio.Queue = asyncio.Queue()
        self.engine_status: Dict[int, EngineStatus] = {}
        self._initialized = False
        self._lock = asyncio.Lock()
        
        # ProcessPoolExecutor for CPU-bound theme/tag calculations
        self.process_pool: Optional[ProcessPoolExecutor] = None
        
    async def initialize(self) -> bool:
        """
        Initialize the engine pool by spawning multiple Stockfish instances.
        Returns True if successful, False otherwise.
        """
        if self._initialized:
            return True
            
        async with self._lock:
            if self._initialized:  # Double-check after acquiring lock
                return True
                
            print(f"🔧 Initializing engine pool with {self.pool_size} instances...")
            
            try:
                for i in range(self.pool_size):
                    transport, engine = await chess.engine.popen_uci(self.stockfish_path)
                    # Optimized configuration for multi-user scaling:
                    # Threads=1: Better CPU utilization, less contention
                    # Hash=32: Reduced memory footprint (27% savings per engine)
                    # MultiPV=2: Consistent behavior, slight performance boost
                    # Ponder=False: Explicitly disable (already default)
                    await engine.configure({
                        "Threads": 1,
                        "Hash": 32,
                                                "Ponder": False
                    })
                    self.engines.append(engine)
                    await self.available.put((i, engine))
                    self.engine_status[i] = EngineStatus(
                        id=i,
                        is_available=True,
                        analyses_completed=0,
                        last_used=None
                    )
                    print(f"   ✓ Engine {i+1}/{self.pool_size} initialized")
                
                # Initialize ProcessPoolExecutor for CPU-bound theme/tag calculations
                self.process_pool = ProcessPoolExecutor(max_workers=self.pool_size)
                print(f"   ✓ ProcessPool initialized with {self.pool_size} workers")
                
                self._initialized = True
                print(f"✅ Engine pool ready: {self.pool_size} engines + {self.pool_size} CPU workers")
                return True
                
            except Exception as e:
                print(f"❌ Failed to initialize engine pool: {e}")
                # Clean up any engines that were created
                await self.shutdown()
                return False
    
    async def acquire(self, timeout: float = 60.0) -> Tuple[int, chess.engine.UciProtocol]:
        """
        Acquire an available engine from the pool.
        Blocks until an engine is available, with optional timeout.
        
        Args:
            timeout: Maximum time to wait for an engine (seconds). Default 60s.
                    If None, waits indefinitely.
        
        Returns: (engine_id, engine) tuple
        
        Raises:
            asyncio.TimeoutError: If timeout is exceeded
        """
        if not self._initialized:
            raise RuntimeError("Engine pool not initialized. Call initialize() first.")
        
        if timeout is None:
            engine_id, engine = await self.available.get()
        else:
            try:
                engine_id, engine = await asyncio.wait_for(self.available.get(), timeout=timeout)
            except asyncio.TimeoutError:
                print(f"   ⚠️ [ENGINE_POOL] Timeout waiting for available engine after {timeout}s")
                raise
        
        self.engine_status[engine_id].is_available = False
        self.engine_status[engine_id].last_used = time.time()
        return engine_id, engine
    
    async def release(self, engine_id: int, engine: chess.engine.UciProtocol):
        """Return an engine to the pool."""
        self.engine_status[engine_id].is_available = True
        self.engine_status[engine_id].analyses_completed += 1
        await self.available.put((engine_id, engine))
    
    async def analyze_single(
        self,
        fen: str,
        depth: int = 14,
        multipv: int = 2,
        acquire_timeout: float = 60.0,
        analysis_timeout: float = 120.0
    ) -> Dict[str, Any]:
        """
        Analyze a single position using an engine from the pool.
        
        Args:
            fen: Position FEN string
            depth: Analysis depth
            multipv: Number of principal variations
            acquire_timeout: Max time to wait for available engine (seconds)
            analysis_timeout: Max time for engine analysis (seconds)
        
        Returns:
            Dict with success, engine_id, result/error
        """
        engine_id = None
        engine = None
        try:
            # Acquire engine with timeout
            engine_id, engine = await self.acquire(timeout=acquire_timeout)
            
            board = chess.Board(fen)
            print(f"      🔍 [ENGINE_POOL] analyze_single:", flush=True)
            print(f"         - Input FEN: {fen}", flush=True)
            print(f"         - Board FEN: {board.fen()}", flush=True)
            print(f"         - Side to move: {'WHITE' if board.turn == chess.WHITE else 'BLACK'}", flush=True)
            
            # Run analysis with timeout
            result = await asyncio.wait_for(
                engine.analyse(board, chess.engine.Limit(depth=depth), multipv=multipv),
                timeout=analysis_timeout
            )
            
            return {
                "success": True,
                "engine_id": engine_id,
                "result": result
            }
        except asyncio.TimeoutError as e:
            error_msg = f"Analysis timeout after {analysis_timeout}s" if engine_id is not None else f"Engine acquisition timeout after {acquire_timeout}s"
            print(f"   ⚠️ [ENGINE_POOL] {error_msg}")
            return {
                "success": False,
                "engine_id": engine_id,
                "error": error_msg
            }
        except Exception as e:
            return {
                "success": False,
                "engine_id": engine_id,
                "error": str(e)
            }
        finally:
            if engine_id is not None and engine is not None:
                await self.release(engine_id, engine)
    
    async def analyze_position_pair(
        self,
        fen_before: str,
        move: chess.Move,
        depth: int = 14,
        multipv: int = 2
    ) -> Dict[str, Any]:
        """
        Analyze a position before and after a move (for game review).
        Uses a single engine for both analyses to maintain consistency.
        """
        engine_id, engine = await self.acquire()
        try:
            # Analyze BEFORE move
            board_before = chess.Board(fen_before)
            info_before = await engine.analyse(
                board_before, 
                chess.engine.Limit(depth=depth), 
                multipv=multipv
            )
            
            # Make move and analyze AFTER
            board_after = chess.Board(fen_before)
            board_after.push(move)
            info_after = await engine.analyse(
                board_after,
                chess.engine.Limit(depth=depth)
            )
            
            return {
                "success": True,
                "engine_id": engine_id,
                "fen_before": fen_before,
                "fen_after": board_after.fen(),
                "move": move.uci(),
                "info_before": info_before,
                "info_after": info_after
            }
        except Exception as e:
            return {
                "success": False,
                "engine_id": engine_id,
                "error": str(e)
            }
        finally:
            await self.release(engine_id, engine)
    
    async def analyze_chunk(
        self,
        positions: List[Tuple[str, chess.Move]],
        depth: int = 14,
        multipv: int = 2,
        chunk_id: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Analyze a chunk of positions sequentially using one engine.
        This is called in parallel across multiple engines.
        
        Args:
            positions: List of (fen_before, move) tuples
            depth: Engine analysis depth
            multipv: Number of principal variations
            chunk_id: Identifier for this chunk (for logging)
        
        Returns:
            List of analysis results in order
        """
        engine_id, engine = await self.acquire()
        results = []
        
        try:
            for idx, (fen_before, move) in enumerate(positions):
                try:
                    # Analyze BEFORE move
                    board_before = chess.Board(fen_before)
                    info_before = await engine.analyse(
                        board_before,
                        chess.engine.Limit(depth=depth),
                        multipv=multipv
                    )
                    
                    # Make move and analyze AFTER
                    board_after = chess.Board(fen_before)
                    board_after.push(move)
                    info_after = await engine.analyse(
                        board_after,
                        chess.engine.Limit(depth=depth)
                    )
                    
                    results.append({
                        "success": True,
                        "chunk_id": chunk_id,
                        "position_idx": idx,
                        "fen_before": fen_before,
                        "fen_after": board_after.fen(),
                        "move": move.uci(),
                        "info_before": info_before,
                        "info_after": info_after
                    })
                except Exception as e:
                    results.append({
                        "success": False,
                        "chunk_id": chunk_id,
                        "position_idx": idx,
                        "fen_before": fen_before,
                        "error": str(e)
                    })
            
            return results
            
        finally:
            await self.release(engine_id, engine)
    
    async def analyze_game_parallel(
        self,
        positions: List[Tuple[str, chess.Move]],
        depth: int = 14,
        multipv: int = 2,
        timestamps: Dict[int, float] = None,
        progress_callback=None
    ) -> List[Dict[str, Any]]:
        """
        Analyze a full game's positions in parallel, building complete ply records.
        
        Uses a work-queue approach where all engines pull from a shared queue.
        Returns complete ply records ready for use (no second pass needed).
        
        Args:
            positions: List of (fen_before, move) tuples for the entire game
            depth: Engine analysis depth
            multipv: Number of principal variations
            timestamps: Optional dict mapping ply -> clock time (for time spent calc)
            progress_callback: Optional async callback(positions_done, total) for progress
        
        Returns:
            List of complete ply records in move order
        """
        if not positions:
            return []
        
        n_positions = len(positions)
        timestamps = timestamps or {}
        
        # === OPTIMIZATION: Collect unique FENs to avoid duplicate analysis ===
        # fen_after of move N == fen_before of move N+1, so we only need to analyze each once!
        unique_fens = set()
        fen_after_list = []  # Store fen_after for each move
        
        for fen_before, move in positions:
            unique_fens.add(fen_before)
            board = chess.Board(fen_before)
            board.push(move)
            fen_after = board.fen()
            fen_after_list.append(fen_after)
            unique_fens.add(fen_after)
        
        unique_fens = list(unique_fens)
        n_unique = len(unique_fens)
        print(f"   📊 Analyzing {n_unique} unique positions (saved {n_positions * 2 - n_unique} duplicates)")
        
        # Results storage
        results: List[Optional[Dict[str, Any]]] = [None] * n_positions
        fen_analysis_cache: Dict[str, Dict] = {}  # Cache for theme/tag results
        fen_engine_cache: Dict[str, Any] = {}  # Cache for engine results
        
        # Progress tracking
        progress_counter = {"done": 0}
        progress_lock = asyncio.Lock()
        
        def format_eval(cp: int) -> str:
            """Format centipawn eval as string."""
            if abs(cp) >= 10000:
                return f"M{abs(cp) - 10000}" if cp > 0 else f"-M{abs(cp) - 10000}"
            return str(cp)
        
        # Get event loop for process pool submissions
        loop = asyncio.get_event_loop()
        
        # === THEORY CHECK PHASE: Batch check opening theory for early moves ===
        theory_cache: Dict[str, Dict] = {}
        theory_fens = []
        theory_indices = []  # Track which moves need theory checks
        
        for idx, (fen_before, move) in enumerate(positions):
            ply = idx + 1
            if ply <= 30:  # Only check theory for first 30 moves
                if fen_before not in theory_cache:
                    theory_fens.append(fen_before)
                    theory_indices.append((idx, fen_before))
        
        # Batch theory checks in parallel
        if theory_fens:
            print(f"   📚 Checking opening theory for {len(theory_fens)} positions...")
            
            if progress_callback:
                try:
                    await progress_callback(0, len(theory_fens), "Checking opening theory...")
                    await asyncio.sleep(0)
                except Exception:
                    pass
            
            async def check_theory_async(fen: str) -> Tuple[str, Dict]:
                """Check theory for a single FEN."""
                try:
                    result = await loop.run_in_executor(None, check_lichess_masters, fen)
                    return (fen, result)
                except Exception as e:
                    print(f"   ⚠️ Theory check error for FEN: {e}")
                    return (fen, {'isTheory': False, 'theoryMoves': [], 'opening': '', 'eco': '', 'totalGames': 0})
            
            # Run all theory checks in parallel
            theory_results = await asyncio.gather(*[check_theory_async(fen) for fen in theory_fens])
            
            # Update progress when complete
            if progress_callback:
                try:
                    await progress_callback(len(theory_fens), len(theory_fens), "Checking opening theory...")
                    await asyncio.sleep(0)
                except Exception:
                    pass
            
            # Cache results
            for fen, result in theory_results:
                theory_cache[fen] = result
        
        # === PHASE 1: Analyze all unique positions ===
        fen_queue: asyncio.Queue = asyncio.Queue()
        for fen in unique_fens:
            await fen_queue.put(fen)
        
        async def analyze_fen_worker(worker_id: int):
            """Worker that analyzes unique FENs."""
            engine_id, engine = await self.acquire()
            
            try:
                while True:
                    try:
                        fen = fen_queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break
                    
                    try:
                        board = chess.Board(fen)
                        
                        # Theme/tag calculation in process pool (with recovery)
                        themes_future = None
                        try:
                            themes_future = loop.run_in_executor(
                                self.process_pool, compute_themes_and_tags, fen
                            )
                        except RuntimeError as e:
                            if "process pool is not usable" in str(e):
                                print(f"   ⚠️ Process pool died, recreating...")
                                await self._recreate_process_pool()
                                themes_future = loop.run_in_executor(
                                    self.process_pool, compute_themes_and_tags, fen
                                )
                            else:
                                raise
                        
                        # Engine analysis (multipv=2 for all positions) with crash recovery
                        info = None
                        max_retries = 2
                        for retry in range(max_retries):
                            try:
                                info = await engine.analyse(
                                    board,
                                    chess.engine.Limit(depth=depth),
                                    multipv=multipv
                                )
                                break  # Success, exit retry loop
                            except chess.engine.EngineTerminatedError:
                                if retry < max_retries - 1:
                                    print(f"   ⚠️ Engine {engine_id} crashed, recreating...")
                                    await self._recreate_engine(engine_id)
                                    # Get the recreated engine
                                    engine = self.engines[engine_id]
                                    print(f"   ✓ Engine {engine_id} recreated, retrying...")
                                else:
                                    raise  # Last retry failed, propagate error
                        
                        # Get theme/tag results (with recovery)
                        try:
                            raw = await themes_future
                        except RuntimeError as e:
                            if "process pool is not usable" in str(e):
                                print(f"   ⚠️ Process pool died during execution, recreating...")
                                await self._recreate_process_pool()
                                themes_future = loop.run_in_executor(
                                    self.process_pool, compute_themes_and_tags, fen
                                )
                                raw = await themes_future
                            else:
                                raise
                        
                        raw["theme_scores"] = compute_theme_scores(raw["themes"])
                        
                        # Extract engine eval
                        score = info[0]["score"].relative
                        if score.is_mate():
                            eval_cp = 10000 if score.mate() > 0 else -10000
                        else:
                            eval_cp = score.score(mate_score=10000)
                        
                        best_move_obj = info[0]["pv"][0] if info[0].get("pv") else None
                        best_move_uci = best_move_obj.uci() if best_move_obj else None
                        
                        # Serialize engine_info (convert PovScore to plain values)
                        serialized_info = []
                        for pv_info in info:
                            pv_score = pv_info["score"].relative
                            if pv_score.is_mate():
                                pv_eval = 10000 if pv_score.mate() > 0 else -10000
                                pv_mate = pv_score.mate()
                            else:
                                pv_eval = pv_score.score(mate_score=10000)
                                pv_mate = None
                            serialized_info.append({
                                "eval_cp": pv_eval,
                                "mate_in": pv_mate,
                                "pv": [m.uci() for m in pv_info.get("pv", [])],
                                "depth": pv_info.get("depth", depth)
                            })
                        
                        # Add scoring and compartmentalization
                        from significance_scorer import SignificanceScorer
                        from raw_data_compartmentalizer import RawDataCompartmentalizer
                        
                        # Score all metrics
                        scored_insights = SignificanceScorer.score_all_metrics_in_raw_analysis(raw)
                        
                        # Compartmentalize for LLM access
                        compartments = RawDataCompartmentalizer.compartmentalize({
                            **raw,
                            "scored_insights": scored_insights
                        })
                        
                        # Cache results
                        fen_analysis_cache[fen] = {
                            "fen": fen,
                            "engine_info": serialized_info,
                            "eval_cp": eval_cp,
                            "best_move_uci": best_move_uci,
                            "scored_insights": scored_insights,
                            "compartments": compartments,
                            **raw
                        }
                        
                    except Exception as e:
                        error_msg = str(e)
                        print(f"   ⚠️ Analysis error for FEN: {error_msg}")
                        
                        # Check if process pool died
                        if "process pool is not usable" in error_msg or "child process terminated" in error_msg.lower():
                            try:
                                await self._recreate_process_pool()
                            except Exception as pool_err:
                                print(f"   ❌ Failed to recreate process pool: {pool_err}")
                        
                        fen_analysis_cache[fen] = {"error": error_msg}
                    
                    # Update progress - report as move analysis progress
                    async with progress_lock:
                        progress_counter["done"] += 1
                        done = progress_counter["done"]
                    
                    if progress_callback:
                        try:
                            # Estimate move progress: we analyze ~1.5 unique positions per move
                            # So when we've done n_unique positions, we're roughly done with all moves
                            estimated_moves_done = min(n_positions, int((done / n_unique) * n_positions))
                            await progress_callback(estimated_moves_done, n_positions, "Analyzing moves...")
                        except Exception:
                            pass
                    
                    fen_queue.task_done()
            finally:
                await self.release(engine_id, engine)
        
        # Run FEN analysis workers
        n_workers = min(self.pool_size, n_unique)
        workers = [asyncio.create_task(analyze_fen_worker(i)) for i in range(n_workers)]
        await asyncio.gather(*workers)
        
        # === PHASE 2: Build ply records from cached results ===
        print(f"   📝 Building move records from cached results...")
        
        # Track if progress callback is failing (stream might be closed)
        callback_failures = 0
        max_callback_failures = 3  # Stop calling if it fails 3 times in a row
        
        for idx, (fen_before, move) in enumerate(positions):
            ply = idx + 1
            fen_after = fen_after_list[idx]
            
            # Progress update every move (but skip if callback is failing)
            if progress_callback and callback_failures < max_callback_failures and n_positions > 0:
                try:
                    # Report as "Analyzing moves n/N"
                    await progress_callback(idx + 1, n_positions, "Analyzing moves...")
                    await asyncio.sleep(0)
                    callback_failures = 0  # Reset on success
                except Exception as e:
                    callback_failures += 1
                    if callback_failures == 1:  # Only log first failure with traceback
                        print(f"   ⚠️ Progress callback error (stream may be closed): {e}")
                        import traceback
                        traceback.print_exc()
                    # Continue processing even if callback fails
            
            # Look up cached results
            analysis_before = fen_analysis_cache.get(fen_before, {})
            analysis_after = fen_analysis_cache.get(fen_after, {})
            
            if analysis_before.get("error") or analysis_after.get("error"):
                results[idx] = {
                    "success": False,
                    "ply": ply,
                    "fen_before": fen_before,
                    "error": analysis_before.get("error") or analysis_after.get("error")
                }
                continue
            
            try:
                board_before = chess.Board(fen_before)
                side_moved = "white" if board_before.turn == chess.WHITE else "black"
                move_san = board_before.san(move)
                move_uci = move.uci()
                
                # Extract from cached analysis
                best_eval_cp = analysis_before.get("eval_cp", 0)
                best_move_uci = analysis_before.get("best_move_uci")
                # Convert UCI to SAN for display
                if best_move_uci:
                    best_move_obj = chess.Move.from_uci(best_move_uci)
                    best_move_san = board_before.san(best_move_obj)
                else:
                    best_move_san = None
                info_before = analysis_before.get("engine_info", [{}])
                
                # Get eval after from cached analysis
                eval_after_cp = analysis_after.get("eval_cp", 0)
                
                # Second-best gap for critical move detection (info is now serialized)
                second_best_gap_cp = 0
                if len(info_before) >= 2:
                    second_eval = info_before[1].get("eval_cp", 0)
                    second_best_gap_cp = abs(best_eval_cp - second_eval)
                
                # Played eval (from perspective of side that moved)
                played_eval_cp = -eval_after_cp  # Flip for mover's perspective
                
                # CP loss & accuracy
                if side_moved == "white":
                    cp_loss = best_eval_cp - played_eval_cp
                else:
                    cp_loss = played_eval_cp - best_eval_cp
                cp_loss = max(0, cp_loss)
                
                accuracy_pct = 100 / (1 + (cp_loss / 50) ** 0.7)
                
                # Opening theory check (use cached result from batched phase)
                if ply <= 30 and fen_before in theory_cache:
                    theory_check = theory_cache[fen_before]
                    is_theory_move = move_uci in theory_check.get('theoryMoves', [])
                else:
                    theory_check = {'isTheory': False, 'theoryMoves': [], 'opening': '', 'eco': '', 'totalGames': 0}
                    is_theory_move = False
                
                # Yield to event loop periodically to keep it responsive
                if idx % 10 == 0:
                    await asyncio.sleep(0)
                
                # Move category
                if is_theory_move:
                    category = "theory"
                elif cp_loss == 0 and second_best_gap_cp >= 50:
                    category = "critical_best"
                elif cp_loss < 20:
                    category = "excellent"
                elif cp_loss < 50:
                    category = "good"
                elif cp_loss < 80:
                    category = "inaccuracy"
                elif cp_loss < 200:
                    category = "mistake"
                else:
                    category = "blunder"
                
                # Time spent
                time_spent_s = None
                if ply in timestamps and (ply - 1) in timestamps:
                    time_spent_s = timestamps[ply - 1] - timestamps[ply]
                
                # === Best Move Tag Analysis ===
                # When best move != played move, analyze what tags best move would create
                best_move_tags = []
                if best_move_uci and best_move_uci != move_uci:
                    try:
                        # Make best move on board to get resulting position
                        board_best = chess.Board(fen_before)
                        board_best.push(chess.Move.from_uci(best_move_uci))
                        fen_after_best = board_best.fen()
                        
                        # Check cache first
                        best_move_analysis = fen_analysis_cache.get(fen_after_best)
                        if not best_move_analysis:
                            # Compute themes/tags for best move position (with recovery)
                            try:
                                raw_best = await loop.run_in_executor(
                                    self.process_pool, compute_themes_and_tags, fen_after_best
                                )
                                best_move_tags = raw_best.get("tags", [])
                            except RuntimeError as e:
                                if "process pool is not usable" in str(e) or "child process terminated" in str(e).lower():
                                    print(f"   ⚠️ Process pool died during best move analysis, recreating...")
                                    await self._recreate_process_pool()
                                    raw_best = await loop.run_in_executor(
                                        self.process_pool, compute_themes_and_tags, fen_after_best
                                    )
                                    best_move_tags = raw_best.get("tags", [])
                                else:
                                    raise
                        else:
                            best_move_tags = best_move_analysis.get("tags", [])
                    except Exception as e:
                        print(f"   ⚠️ Error computing best move tags for ply {ply}: {e}")
                        best_move_tags = []
                
                # === Threat Category Classification ===
                threat_category = None
                threat_description = None
                try:
                    from threat_analyzer import categorize_threat
                    board_temp = chess.Board(fen_before)
                    move_obj = chess.Move.from_uci(move_uci)
                    threat_cat_result = categorize_threat(board_temp, move_obj, played_eval_cp)
                    threat_category = threat_cat_result["type"]
                    threat_description = threat_cat_result["description"]
                except Exception as e:
                    print(f"   ⚠️ Error categorizing threat for ply {ply}: {e}")
                    threat_category = None
                    threat_description = None
                
                # Add scoring for raw_after (with delta from raw_before)
                from significance_scorer import SignificanceScorer
                from raw_data_compartmentalizer import RawDataCompartmentalizer
                
                # Score raw_after with deltas from raw_before
                scored_insights_after = SignificanceScorer.score_all_metrics_in_raw_analysis(
                    analysis_after,
                    raw_before=analysis_before
                )
                
                # Score CP loss
                cp_loss_score = SignificanceScorer.score_cp_loss(cp_loss)
                scored_insights_after["cp_loss"] = cp_loss_score
                
                # Score second-best gap
                if second_best_gap_cp > 0:
                    gap_score = SignificanceScorer.score_second_best_gap(second_best_gap_cp)
                    scored_insights_after["second_best_gap"] = gap_score
                
                # Add scored insights to analysis_after
                analysis_after["scored_insights"] = scored_insights_after
                analysis_after["compartments"] = RawDataCompartmentalizer.compartmentalize(analysis_after)
                
                # Also add compartments to analysis_before if not present
                if "compartments" not in analysis_before:
                    analysis_before["compartments"] = RawDataCompartmentalizer.compartmentalize(analysis_before)
                
                # Build ply record
                ply_record = {
                    "success": True,
                    "ply": ply,
                    "side_moved": side_moved,
                    "san": move_san,
                    "uci": move_uci,
                    "fen_before": fen_before,
                    "fen_after": fen_after,
                    "engine": {
                        "eval_before_cp": best_eval_cp,
                        "eval_before_str": format_eval(best_eval_cp),
                        "best_move_uci": best_move_uci,
                        "best_move_san": best_move_san,
                        "played_eval_after_cp": played_eval_cp,
                        "played_eval_after_str": format_eval(played_eval_cp),
                        "mate_in": None,
                        "second_best_gap_cp": second_best_gap_cp
                    },
                    "cp_loss": cp_loss,
                    "accuracy_pct": accuracy_pct,
                    "category": category,
                    "threat_category": threat_category,
                    "threat_description": threat_description,
                    "time_spent_s": time_spent_s,
                    "raw_before": analysis_before,
                    "raw_after": analysis_after,
                    "analyse": analysis_after,
                    "best_move_tags": best_move_tags,  # NEW: Tags that best move would create
                    "is_theory": is_theory_move,
                    "theory_check": theory_check,
                    "opening_name": theory_check.get('opening', '') if is_theory_move else None,
                    "key_point_labels": [],
                    "notes": ""
                }
                
                # Generate structured explanation (if not a theory move or excellent move)
                if not is_theory_move and cp_loss > 20:
                    try:
                        from explanation_generator import generate_move_explanation
                        
                        # Determine game phase (simple piece-count based)
                        try:
                            board_for_phase = chess.Board(fen_before)
                            piece_count = len(board_for_phase.piece_map())
                            if piece_count >= 28:
                                phase = "opening"
                            elif piece_count >= 12:
                                phase = "middlegame"
                            else:
                                phase = "endgame"
                        except:
                            # Fallback to ply-based phase detection
                            phase = "opening" if ply <= 20 else ("endgame" if ply > 60 else "middlegame")
                        
                        # Generate structured analysis
                        structured_analysis = generate_move_explanation(
                            ply_record=ply_record,
                            raw_before=analysis_before,
                            raw_after=analysis_after,
                            best_move_tags=best_move_tags,
                            engine_info=info_before,
                            ply_records=results[:idx] if idx > 0 else None,  # Previous records for context
                            phase=phase
                        )
                        ply_record["structured_analysis"] = structured_analysis
                    except Exception as e:
                        print(f"   ⚠️ Error generating explanation for ply {ply}: {e}")
                        import traceback
                        traceback.print_exc()
                        # Continue without structured analysis
                
                results[idx] = ply_record
                
            except Exception as e:
                print(f"   ⚠️ Error building ply record {ply}: {e}")
                results[idx] = {
                    "success": False,
                    "ply": ply,
                    "fen_before": fen_before,
                    "error": str(e)
                }
        
        # Filter out any None results
        return [r for r in results if r is not None]
    
    def get_status(self) -> Dict[str, Any]:
        """Get the current status of the engine pool."""
        return {
            "initialized": self._initialized,
            "pool_size": self.pool_size,
            "engines_available": self.available.qsize() if self._initialized else 0,
            "engine_details": [
                {
                    "id": status.id,
                    "available": status.is_available,
                    "analyses_completed": status.analyses_completed,
                    "last_used": status.last_used
                }
                for status in self.engine_status.values()
            ]
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform a quick health check by analyzing a simple position.
        """
        if not self._initialized:
            return {
                "healthy": False,
                "error": "Pool not initialized"
            }
        
        start_time = time.time()
        try:
            # Analyze starting position
            result = await self.analyze_single(
                "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
                depth=5,  # Low depth for speed
                multipv=1
            )
            
            elapsed = time.time() - start_time
            
            if result["success"]:
                return {
                    "healthy": True,
                    "response_time_ms": round(elapsed * 1000),
                    "pool_status": self.get_status()
                }
            else:
                return {
                    "healthy": False,
                    "error": result.get("error", "Unknown error"),
                    "pool_status": self.get_status()
                }
                
        except Exception as e:
            return {
                "healthy": False,
                "error": str(e),
                "pool_status": self.get_status()
            }
    
    async def shutdown(self):
        """Gracefully shutdown all engines in the pool."""
        print("🔧 Shutting down engine pool...")
        
        for i, engine in enumerate(self.engines):
            try:
                await engine.quit()
                print(f"   ✓ Engine {i+1} stopped")
            except Exception as e:
                print(f"   ⚠️ Error stopping engine {i+1}: {e}")
        
        # Shutdown ProcessPoolExecutor
        if self.process_pool:
            self.process_pool.shutdown(wait=True)
            self.process_pool = None
            print(f"   ✓ ProcessPool stopped")
        
        self.engines = []
        self.engine_status = {}
        self._initialized = False
        
        # Clear the queue
        while not self.available.empty():
            try:
                self.available.get_nowait()
            except asyncio.QueueEmpty:
                break
        
        print("✅ Engine pool shutdown complete")
    
    async def _recreate_process_pool(self):
        """Recreate ProcessPoolExecutor after it becomes unusable."""
        async with self._lock:
            if self.process_pool:
                try:
                    self.process_pool.shutdown(wait=False)
                except:
                    pass
                self.process_pool = None
            
            try:
                self.process_pool = ProcessPoolExecutor(max_workers=self.pool_size)
                print(f"   ✓ ProcessPool recreated with {self.pool_size} workers")
            except Exception as e:
                print(f"   ❌ Failed to recreate ProcessPool: {e}")
                raise
    
    async def _recreate_engine(self, engine_id: int):
        """Recreate a crashed engine."""
        async with self._lock:
            try:
                # Remove old engine
                if engine_id < len(self.engines):
                    old_engine = self.engines[engine_id]
                    try:
                        await old_engine.quit()
                    except:
                        pass
                
                # Create new engine
                transport, new_engine = await chess.engine.popen_uci(self.stockfish_path)
                # Apply same optimized configuration
                await new_engine.configure({
                    "Threads": 1,
                    "Hash": 32,
                                        "Ponder": False
                })
                if engine_id < len(self.engines):
                    self.engines[engine_id] = new_engine
                else:
                    self.engines.append(new_engine)
                
                # Update status
                self.engine_status[engine_id] = EngineStatus(
                    id=engine_id,
                    is_available=True,
                    analyses_completed=0,
                    last_used=None
                )
                
                print(f"   ✓ Engine {engine_id} recreated")
            except Exception as e:
                print(f"   ❌ Failed to recreate engine {engine_id}: {e}")
                raise


# Global instance
engine_pool: Optional[EnginePool] = None


async def get_engine_pool(pool_size: int = 4, stockfish_path: str = "./stockfish") -> EnginePool:
    """Get or create the global engine pool instance."""
    global engine_pool
    
    if engine_pool is None:
        engine_pool = EnginePool(pool_size=pool_size, stockfish_path=stockfish_path)
        await engine_pool.initialize()
    
    return engine_pool

