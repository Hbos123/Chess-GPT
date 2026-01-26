import os
import asyncio
import math
import uuid
from typing import Optional, List, Dict, Any, Literal
from contextlib import asynccontextmanager
from io import StringIO
import urllib.parse
import urllib.request
import urllib.error
import platform
import shutil
import stat
import tempfile
import tarfile
import zipfile
from datetime import datetime

from fastapi import FastAPI, HTTPException, Query, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
import chess
import chess.engine
import chess.pgn
from dotenv import load_dotenv
import json
from openai import OpenAI
from position_cache import PositionCache
from position_generator import generate_fen_for_topic
from opening_explorer import LichessExplorerClient
from opening_builder import build_opening_lesson
from opening_lesson_service import create_opening_lesson_payload
from material_calculator import calculate_material_balance
from fen_analyzer import analyze_fen
from delta_analyzer import calculate_delta, compare_tags_for_move_analysis
from game_fetcher import GameFetcher
from profile_indexer import ProfileIndexingManager
from supabase_client import SupabaseClient
from profile_analytics.engine import ProfileAnalyticsEngine
from personal_review_aggregator import PersonalReviewAggregator
from personal_stats_manager import PersonalStatsManager
from game_archive_manager import GameArchiveManager
from llm_planner import LLMPlanner
from llm_reporter import LLMReporter
from confidence_engine import compute_move_confidence, compute_position_confidence, neutral_confidence
from position_miner import PositionMiner
from piece_profiler import build_piece_profiles, get_profile_summary
from pv_profile_tracker import track_pv_profiles, detect_captures_in_pv, compute_pv_fens
from piece_interactions import compute_coordination_score
from square_control import compute_square_control, get_control_summary
from nnue_bridge import get_nnue_dump
from drill_generator import DrillGenerator
from training_planner import TrainingPlanner
from srs_scheduler import SRSScheduler
from drill_card import CardDatabase
from chat_tools import ALL_TOOLS, get_tools_for_context
from tool_executor import ToolExecutor
from enhanced_system_prompt import TOOL_AWARE_SYSTEM_PROMPT
from request_interpreter import RequestInterpreter, execute_analysis_requests
from prompt_builder import validate_interpreter_selections, build_interpreter_driven_prompt
from orchestration_plan import OrchestrationPlan, Mode, ResponseStyle
from engine_pool import EnginePool, get_engine_pool
from response_annotator import parse_response_for_annotations, generate_candidate_move_annotations
from engine_queue import StockfishQueue
from board_vision import analyze_board_image, BoardVisionError
from concurrent.futures import ProcessPoolExecutor
from parallel_analyzer import compute_themes_and_tags, compute_theme_scores
from llm_router import LLMRouter, LLMRouterConfig
from board_tree_store import BoardTreeStore, BoardTree, BoardTreeNode, new_node_id

load_dotenv()

# Initialize OpenAI client
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    print("⚠️  WARNING: OPENAI_API_KEY not set in environment variables")
    openai_client = None
else:
    try:
        openai_client = OpenAI(api_key=openai_api_key)
        print("✅ OpenAI client initialized")
    except Exception as e:
        print(f"⚠️  WARNING: Failed to initialize OpenAI client: {e}")
        openai_client = None

# Global engine instance
engine: Optional[chess.engine.SimpleEngine] = None
engine_queue: Optional[StockfishQueue] = None
queue_processor_task: Optional[asyncio.Task] = None

# Engine pool for parallel analysis (4 instances)
engine_pool_instance: Optional[EnginePool] = None

# Global position cache for dynamic generation
position_cache = PositionCache(ttl_seconds=3600)

# Global Lichess explorer client
explorer_client: Optional[LichessExplorerClient] = None

# Personal Review components
game_fetcher: Optional[GameFetcher] = None
review_aggregator: Optional[PersonalReviewAggregator] = None
stats_manager: Optional[PersonalStatsManager] = None
archive_manager: Optional[GameArchiveManager] = None
llm_planner: Optional[LLMPlanner] = None
llm_reporter: Optional[LLMReporter] = None

# Training & Drill components
position_miner: Optional[PositionMiner] = None
drill_generator: Optional[DrillGenerator] = None
training_planner: Optional[TrainingPlanner] = None
srs_scheduler: Optional[SRSScheduler] = None
card_databases: Dict[str, CardDatabase] = {}  # username -> CardDatabase

# Tool executor for chat
tool_executor: Optional[ToolExecutor] = None

# Request interpreter for chat preprocessing
request_interpreter: Optional[RequestInterpreter] = None

# Profile indexing manager
profile_indexer: Optional[ProfileIndexingManager] = None

# Profile analytics engine
profile_analytics_engine: Optional[ProfileAnalyticsEngine] = None
game_window_manager = None

# Board tree store for D2/D16 tree-first analysis
board_tree_store: Optional[BoardTreeStore] = None
account_init_manager = None

# Supabase client
supabase_client: Optional[SupabaseClient] = None

# Upload constraints
MAX_PHOTO_SIZE_BYTES = 8 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/heic",
    "image/heif",
    "image/webp",
}

# Pre-generated positions database (loaded at startup)
PRE_GENERATED_POSITIONS: Dict[str, List[Dict]] = {}

STOCKFISH_PATH = os.getenv("STOCKFISH_PATH", "./stockfish")

# Prevent concurrent runtime downloads (e.g. multiple startup paths)
_downloading_stockfish = False


def _ensure_stockfish_present() -> bool:
    """Best-effort: ensure a Stockfish binary exists at STOCKFISH_PATH.

    Primary path is build-time download (Render buildCommand). This is a runtime fallback.
    """
    global _downloading_stockfish

    if os.path.exists(STOCKFISH_PATH):
        return True

    # Avoid concurrent/recursive attempts
    if _downloading_stockfish:
        return False

    # Only auto-fetch for the default path; don't surprise users with downloads when
    # they configured a custom STOCKFISH_PATH.
    if os.getenv("STOCKFISH_PATH") and os.getenv("STOCKFISH_PATH") != "./stockfish":
        return False

    if platform.system().lower() != "linux":
        return False

    url = "https://github.com/official-stockfish/Stockfish/releases/download/sf_16/stockfish-ubuntu-x86-64-avx2.tar"

    try:
        _downloading_stockfish = True
        print(f"⬇️  Stockfish missing; downloading from {url}")

        target_path = os.path.abspath(STOCKFISH_PATH)
        target_dir = os.path.dirname(target_path) or "."
        os.makedirs(target_dir, exist_ok=True)

        with tempfile.TemporaryDirectory() as td:
            tar_path = os.path.join(td, "stockfish.tar")
            urllib.request.urlretrieve(url, tar_path)  # nosec - static URL

            extracted_path = os.path.join(td, "stockfish_extracted")
            with tarfile.open(tar_path, "r:*") as tf:
                candidate = None
                for m in tf.getmembers():
                    if m.isfile() and m.name.endswith("stockfish-ubuntu-x86-64-avx2"):
                        candidate = m
                        break
                if not candidate:
                    print("⚠️  Stockfish archive did not contain the expected binary")
                    return False

                src = tf.extractfile(candidate)
                if not src:
                    print("⚠️  Failed to extract Stockfish binary from tar")
                    return False

                with open(extracted_path, "wb") as dst:
                    dst.write(src.read())

            shutil.move(extracted_path, target_path)
            os.chmod(target_path, os.stat(target_path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

        print(f"✅ Stockfish downloaded to {target_path}")
        return True

    except urllib.error.HTTPError as e:
        print(f"⚠️  Failed to download Stockfish: HTTP {e.code} - {e.reason}")
        return False
    except urllib.error.URLError as e:
        print(f"⚠️  Failed to download Stockfish: URL error - {type(e).__name__}")
        return False
    except Exception as e:
        # Keep message safe
        print(f"⚠️  Failed to download Stockfish automatically: {type(e).__name__}: {str(e)[:200]}")
        return False
    finally:
        _downloading_stockfish = False

# System prompt
# System prompt for the LLM
SYSTEM_PROMPT = """You are Chesster. You must not invent concrete evaluations, tablebase facts, or long variations. For any concrete claims (evals, PVs, winning lines, best moves), you rely on tool outputs the client provides from backend endpoints:

- analyze_position(fen, lines, depth) for evaluations, candidates, threats, and themes.
- play_move(fen, user_move_san, engine_elo, time_ms) for engine replies during play.
- opening_lookup(fen) for ECO book context.
- tactics_next(...) for puzzle generation.

The user interface also provides current fen, pgn, and annotations (comments, NAGs, arrows, highlights). Use them as context.

When responding:
- Start with a verdict ("=", "+/=", "+-/-", etc.) and a single sentence why.
- List 2–3 key themes.
- Present 2–3 candidate moves with their purposes (numbers from tool outputs only).
- Show one critical line ≤ 8 ply based on PV from tools.
- Give a concise plan and one thing to avoid.

Keep it clear, rating-aware, and practical."""


async def initialize_engine():
    """Initialize or reinitialize the Stockfish engine."""
    global engine, engine_queue, queue_processor_task
    try:
        # Stop and cancel existing queue processor if any
        if queue_processor_task and not queue_processor_task.done():
            if engine_queue:
                engine_queue.stop()
                await engine_queue.cancel_all_pending()
            queue_processor_task.cancel()
            try:
                await queue_processor_task
            except asyncio.CancelledError:
                pass
        
        # Close existing engine if any
        if engine:
            try:
                await engine.quit()
            except:
                pass
        # Stockfish should be ensured during lifespan(); don't retry downloads here
        if os.path.exists(STOCKFISH_PATH):
            # Verify it's executable
            if not os.access(STOCKFISH_PATH, os.X_OK):
                os.chmod(STOCKFISH_PATH, os.stat(STOCKFISH_PATH).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            
            transport, engine = await chess.engine.popen_uci(STOCKFISH_PATH)
            await engine.configure({
                "Threads": 1,
                "Hash": 32})
            
            # Initialize queue system
            engine_queue = StockfishQueue(engine)
            queue_processor_task = asyncio.create_task(engine_queue.start_processing())
            
            print(f"✓ Stockfish engine initialized with request queue at {STOCKFISH_PATH}")
            return True
        else:
            print(f"⚠ Stockfish not found at {STOCKFISH_PATH} after download attempt")
            engine = None
            engine_queue = None
            queue_processor_task = None
            return False
    except Exception as e:
        print(f"⚠ Failed to initialize Stockfish: {e}")
        engine = None
        engine_queue = None
        queue_processor_task = None
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup the Stockfish engine and explorer client."""
    global engine, engine_queue, PRE_GENERATED_POSITIONS, explorer_client, game_fetcher, review_aggregator, stats_manager, archive_manager, llm_planner, llm_reporter, position_miner, drill_generator, training_planner, srs_scheduler, card_databases, tool_executor, profile_indexer, profile_analytics_engine, supabase_client, engine_pool_instance, board_tree_store
    
    _ensure_stockfish_present()
    await initialize_engine()
    # Initialize engine pool for parallel analysis (configurable; default 2 for Standard)
    pool_size = int(os.getenv("ENGINE_POOL_SIZE", "2"))
    if os.path.exists(STOCKFISH_PATH):
        try:
            engine_pool_instance = EnginePool(pool_size=pool_size, stockfish_path=STOCKFISH_PATH)
            await asyncio.wait_for(engine_pool_instance.initialize(), timeout=30.0)
        except Exception as e:
            print(f"⚠️  Failed to initialize engine pool: {e}")
            engine_pool_instance = None
    else:
        engine_pool_instance = None
    
    # Initialize Lichess explorer client
    explorer_client = LichessExplorerClient()
    
    # Initialize Supabase
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if supabase_url and supabase_service_role_key:
        try:
            supabase_client = SupabaseClient(supabase_url, supabase_service_role_key)
            print("✅ Supabase client initialized")
        except Exception as exc:
            print(f"⚠️  Failed to initialize Supabase client: {exc}")
            supabase_client = None
    else:
        print("⚠️  SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not set - database features will be unavailable")
        supabase_client = None

    # Initialize Personal Review components
    game_fetcher = GameFetcher()
    
    # Create profile_indexer first (without callback)
    profile_indexer = ProfileIndexingManager(
        game_fetcher,
        supabase_client=supabase_client,
        review_fn=_review_game_internal,
        engine_queue=engine_queue,
        engine_instance=engine,
    )
    
    # Define callback to save and analyze games after indexing
    # This must be defined after profile_indexer is created
    async def on_indexing_complete_callback(user_id: str) -> None:
        """Callback to review and save games after they're fetched"""
        if not profile_indexer or not supabase_client:
            print(f"⚠️ [INDEXING_CALLBACK] Cannot process games: profile_indexer={profile_indexer is not None}, supabase_client={supabase_client is not None}")
            return
        
        try:
            # Import _utc_now from profile_indexer
            from profile_indexer import _utc_now, ProfileIndexStatus
            
            # Get fetched games from profile_indexer
            games = profile_indexer._games.get(user_id, [])
            if not games:
                print(f"ℹ️ [INDEXING_CALLBACK] No games to process for user {user_id}")
                return
            
            # Update status to "analyzing" when starting
            if user_id in profile_indexer._status:
                status = profile_indexer._status[user_id]
                status.state = "analyzing"
                status.message = f"Starting analysis of {len(games)} games..."
                status.last_updated = _utc_now()
            else:
                status = ProfileIndexStatus(
                    state="analyzing",
                    message=f"Starting analysis of {len(games)} games...",
                    games_indexed=len(games),
                    last_updated=_utc_now()
                )
                profile_indexer._status[user_id] = status
            
            print(f"🔄 [INDEXING_CALLBACK] Starting to process {len(games)} games for user {user_id}")
            
            # Process up to 60 most recent games (rolling window)
            games_to_process = games[:60]
            total_games = len(games_to_process)
            print(f"📊 [INDEXING_CALLBACK] Processing {total_games} games (limited to 60 for rolling window)")
            
            saved_count = 0
            error_count = 0
            
            for idx, game in enumerate(games_to_process, 1):
                try:
                    # Update status with current progress before processing
                    if user_id in profile_indexer._status:
                        status = profile_indexer._status[user_id]
                        status.state = "analyzing"
                        status.message = f"Analyzing game {idx} of {total_games}..."
                        status.deep_analyzed_games = saved_count
                        status.last_updated = _utc_now()
                    
                    print(f"🎮 [INDEXING_CALLBACK] Processing game {idx}/{total_games}: {game.get('game_id', 'unknown')} from {game.get('platform', 'unknown')}")
                    
                    # Get PGN
                    pgn = game.get("pgn", "")
                    if not pgn:
                        print(f"⚠️ [INDEXING_CALLBACK] Game {idx} has no PGN, skipping")
                        error_count += 1
                        continue
                    
                    # Determine player color
                    player_color = game.get("player_color", "white")
                    
                    # Review the game
                    print(f"🔍 [INDEXING_CALLBACK] Reviewing game {idx} (side_focus={player_color})")
                    review_result = await _review_game_internal(
                        pgn_string=pgn,
                        side_focus=player_color,
                        include_timestamps=game.get("has_clock", False),
                        depth=14,
                        engine_instance=engine,
                    )
                    
                    if "error" in review_result:
                        print(f"❌ [INDEXING_CALLBACK] Review failed for game {idx}: {review_result.get('error')}")
                        error_count += 1
                        continue
                    
                    # Extract stats from review
                    stats = review_result.get("stats", {}).get(player_color, {})
                    counts = stats.get("counts", {})
                    phase_stats = stats.get("by_phase", {})
                    
                    # Normalize platform for database (chess.com -> chesscom)
                    platform = game.get("platform", "chess.com")
                    platform_db = "chesscom" if platform == "chess.com" else platform
                    
                    # Parse date
                    game_date = None
                    date_str = game.get("date", "")
                    if date_str:
                        try:
                            from datetime import datetime
                            game_date = datetime.strptime(date_str, "%Y-%m-%d").isoformat() + "Z"
                        except:
                            pass
                    
                    # Prepare game data for saving
                    game_data = {
                        "platform": platform_db,
                        "external_id": game.get("game_id", ""),
                        "game_date": game_date,
                        "user_color": player_color,
                        "opponent_name": game.get("opponent_name", "Unknown"),
                        "user_rating": game.get("player_rating", 0),
                        "opponent_rating": game.get("opponent_rating", 0),
                        "result": game.get("result", "unknown"),
                        "termination": game.get("termination", ""),
                        "time_control": game.get("time_control", ""),
                        "time_category": game.get("time_category", "unknown"),
                        "opening_eco": review_result.get("opening", {}).get("eco_final", "") or game.get("eco", ""),
                        "opening_name": review_result.get("opening", {}).get("name_final", "") or game.get("opening", ""),
                        "theory_exit_ply": review_result.get("opening", {}).get("theory_exit_ply"),
                        "accuracy_overall": stats.get("overall_accuracy", 0),
                        "accuracy_opening": phase_stats.get("opening", {}).get("accuracy", 0),
                        "accuracy_middlegame": phase_stats.get("middlegame", {}).get("accuracy", 0),
                        "accuracy_endgame": phase_stats.get("endgame", {}).get("accuracy", 0),
                        "avg_cp_loss": stats.get("avg_cp_loss", 0),
                        "blunders": counts.get("blunder", 0),
                        "mistakes": counts.get("mistake", 0),
                        "inaccuracies": counts.get("inaccuracy", 0),
                        "total_moves": len(review_result.get("ply_records", [])),
                        "game_character": review_result.get("game_character", "unknown"),
                        "endgame_type": review_result.get("endgame_type", "none"),
                        "pgn": pgn,
                        "game_review": review_result,
                        "review_type": "full",
                    }
                    
                    # Save to database
                    print(f"💾 [INDEXING_CALLBACK] Saving game {idx} to database")
                    game_id = supabase_client.save_game_review(user_id, game_data)
                    
                    if game_id:
                        saved_count += 1
                        # Update status with saved count after each successful save
                        if user_id in profile_indexer._status:
                            status = profile_indexer._status[user_id]
                            status.deep_analyzed_games = saved_count
                            status.message = f"Analyzed {saved_count} of {total_games} games..."
                            status.last_updated = _utc_now()
                        
                        # Extract and save critical positions from this game
                        ply_records = review_result.get("ply_records", [])
                        if ply_records:
                            try:
                                positions_saved = await _save_error_positions(
                                    ply_records,
                                    game_id,
                                    user_id,
                                    supabase_client,
                                    player_color
                                )
                                if positions_saved > 0:
                                    print(f"   💾 [INDEXING_CALLBACK] Saved {positions_saved} critical positions from game {idx}")
                            except Exception as pos_err:
                                print(f"   ⚠️ [INDEXING_CALLBACK] Error saving positions for game {idx}: {pos_err}")
                        
                        # Don't invalidate cache after every game - too aggressive
                        # We'll invalidate once at the end of indexing instead
                        # This prevents multiple concurrent recalculations during bulk indexing
                        
                        print(f"✅ [INDEXING_CALLBACK] Successfully saved game {idx} with ID: {game_id}")
                    else:
                        error_count += 1
                        print(f"❌ [INDEXING_CALLBACK] Failed to save game {idx} (save_game_review returned None)")
                    
                except Exception as e:
                    error_count += 1
                    print(f"❌ [INDEXING_CALLBACK] Error processing game {idx}: {e}")
                    import traceback
                    traceback.print_exc()
                    continue
            
            # Update final status when complete
            if user_id in profile_indexer._status:
                status = profile_indexer._status[user_id]
                status.state = "idle"
                status.message = f"Analysis complete: {saved_count} games saved, {error_count} errors"
                status.deep_analyzed_games = saved_count
                status.last_updated = _utc_now()
            
            # Invalidate analytics cache once at the end of indexing (not after every game)
            # This prevents multiple concurrent recalculations during bulk indexing
            if profile_analytics_engine and saved_count > 0:
                profile_analytics_engine.invalidate_cache(user_id)
                print(f"🔄 [INDEXING_CALLBACK] Invalidated analytics cache after completing {saved_count} game saves")
            
            # Pre-compute and save detailed analytics cache after batch completion (non-blocking, non-fatal)
            if supabase_client and saved_count > 0:
                try:
                    def compute_and_save_cache():
                        # Fetch 60 most recent games for detailed analytics
                        games = supabase_client.get_active_reviewed_games(user_id, limit=60, include_full_review=True)
                        if not games:
                            print(f"   ℹ️ [INDEXING_CALLBACK] No games found for detailed analytics cache")
                            return
                        
                        from profile_analytics.detailed_analytics import DetailedAnalyticsAggregator
                        aggregator = DetailedAnalyticsAggregator()
                        analytics_data = aggregator.aggregate(games)
                        
                        # Save to cache
                        supabase_client._save_detailed_analytics_cache(user_id, analytics_data, len(games))
                    
                    # Run in thread pool to avoid blocking
                    await asyncio.to_thread(compute_and_save_cache)
                except Exception as e:
                    print(f"   ⚠️ [INDEXING_CALLBACK] Failed to save detailed analytics cache: {e}")
                    # Non-fatal - games are still saved
            
            print(f"✅ [INDEXING_CALLBACK] Completed processing games for user {user_id}: {saved_count} saved, {error_count} errors")
            
        except Exception as e:
            print(f"❌ [INDEXING_CALLBACK] Fatal error in callback for user {user_id}: {e}")
            import traceback
            traceback.print_exc()
            # Update status to error state
            if user_id in profile_indexer._status:
                from profile_indexer import _utc_now
                status = profile_indexer._status[user_id]
                status.state = "error"
                status.message = f"Analysis failed: {str(e)}"
                status.last_updated = _utc_now()
    
    # Now set the callback on the profile_indexer
    if supabase_client:
        profile_indexer.on_indexing_complete = on_indexing_complete_callback
        print("✅ [INIT] on_indexing_complete callback set for ProfileIndexingManager")
    
    # Initialize Profile Analytics Engine (if Supabase available)
    if supabase_client:
        try:
            print("🔧 [PROFILE_ANALYTICS] Initializing Profile Analytics Engine...")
            profile_analytics_engine = ProfileAnalyticsEngine(
                supabase_client,
                profile_indexer=profile_indexer
            )
            print("✅ [PROFILE_ANALYTICS] Profile Analytics Engine initialized successfully")
        except Exception as e:
            import traceback
            print(f"❌ [PROFILE_ANALYTICS] Failed to initialize Profile Analytics Engine: {e}")
            print(f"   Traceback: {traceback.format_exc()}")
            profile_analytics_engine = None
    else:
        profile_analytics_engine = None
        print("⚠️ [PROFILE_ANALYTICS] Profile Analytics Engine not initialized (Supabase unavailable)")
    
    review_aggregator = PersonalReviewAggregator()
    
    # Initialize Personal Review System managers (if Supabase available)
    if supabase_client:
        stats_manager = PersonalStatsManager(supabase_client)
        archive_manager = GameArchiveManager(supabase_client, stats_manager)
        print("✅ Personal Review System managers initialized")
    else:
        stats_manager = None
        archive_manager = None
        print("⚠️ Personal Review System managers not initialized (Supabase unavailable)")
    
    # Initialize Game Window Manager and Account Initialization Manager
    game_window_manager = None
    account_init_manager = None
    if supabase_client:
        try:
            from services.game_window_manager import GameWindowManager
            from services.account_initialization_manager import AccountInitializationManager
            game_window_manager = GameWindowManager(supabase_client)
            account_init_manager = AccountInitializationManager(
                supabase_client,
                profile_indexer,
                game_window_manager
            )
            print("✅ Game Window Manager and Account Initialization Manager initialized")
        except Exception as e:
            print(f"⚠️ Failed to initialize window/account managers: {e}")
            game_window_manager = None
            account_init_manager = None

    # Initialize LLMRouter with OpenAI provider (GPT-5-mini) - "openai-vllm route"
    # This provides session management, prefix caching, and identical structure to vLLM calls
    llm_router = None
    if openai_client:
        try:
            # Configure router to use OpenAI provider with GPT-5-mini
            # Set LLM_PROVIDER=openai and VLLM_ONLY=false to enable OpenAI provider
            router_config = LLMRouterConfig(
                openai_api_key=openai_api_key,
                vllm_only=False,  # Allow OpenAI provider
            )
            # Set environment variables to force OpenAI provider for all stages
            # These are kept set for the duration of the application
            # Components will use OpenAI provider via _stage_provider() function
            os.environ["LLM_PROVIDER"] = "openai"
            os.environ["VLLM_ONLY"] = "false"
            
            llm_router = LLMRouter(config=router_config)
            
            print("✅ LLMRouter initialized (openai-vllm route) with GPT-5-mini")
            print("   📍 All LLM calls will use OpenAI provider via router")
        except Exception as e:
            print(f"⚠️  Failed to initialize LLMRouter: {e}")
            import traceback
            traceback.print_exc()
            llm_router = None
    
    llm_planner = LLMPlanner(openai_client, llm_router=llm_router)
    llm_reporter = LLMReporter(openai_client, llm_router=llm_router)
    print("✅ Personal Review system initialized")
    
    # Initialize Training & Drill components
    position_miner = PositionMiner(openai_client, llm_router=llm_router)
    drill_generator = DrillGenerator()
    training_planner = TrainingPlanner(openai_client, llm_router=llm_router)
    srs_scheduler = SRSScheduler()
    print("✅ Training & Drill system initialized")
    
    # Initialize Tool Executor for chat
    tool_executor = ToolExecutor(
        engine_queue=engine_queue,
        game_fetcher=game_fetcher,
        position_miner=position_miner,
        drill_generator=drill_generator,
        training_planner=training_planner,
        srs_scheduler=srs_scheduler,
        supabase_client=supabase_client,
        openai_client=openai_client,
        llm_router=llm_router
    )
    print("✅ Tool executor initialized for chat")
    
    # Initialize Request Interpreter for chat preprocessing
    # Multi-pass mode is available but disabled by default for performance
    # Set enable_multi_pass=True for complex requests requiring external data
    global request_interpreter
    if openai_client:
        request_interpreter = RequestInterpreter(
            openai_client, 
            use_compact_prompt=True,
            enable_multi_pass=False,  # Enable for multi-pass interpreter loop
            game_fetcher=game_fetcher,
            engine_queue=engine_queue,
            llm_router=llm_router  # Enable prefix caching and session management
        )
        print("✅ Request interpreter initialized")
    
    # Load pre-generated positions if available
    try:
        positions_file = "backend/generated_positions.json"
        if os.path.exists(positions_file):
            with open(positions_file, "r") as f:
                PRE_GENERATED_POSITIONS = json.load(f)
            print(f"✅ Loaded {sum(len(v) for v in PRE_GENERATED_POSITIONS.values())} pre-generated positions")
        else:
            print("⚠️  No pre-generated positions file found (run generate_lesson_positions.py)")
    except Exception as e:
        print(f"⚠️  Could not load pre-generated positions: {e}")
    
    # Background task for periodic account checks
    async def periodic_account_check():
        """Background task to check all accounts every hour"""
        while True:
            await asyncio.sleep(3600)  # 1 hour
            if account_init_manager:
                try:
                    results = await account_init_manager.check_all_accounts()
                    print(f"📊 Account check completed: {results['accounts_checked']} accounts checked")
                except Exception as e:
                    print(f"❌ Account check error: {e}")
    
    # Initialize board tree store
    board_tree_store = BoardTreeStore(ttl_s=1800.0)
    print("✅ Board tree store initialized")
    
    # Start background task
    if account_init_manager:
        asyncio.create_task(periodic_account_check())
        print("✅ Background account check task started")
    
    yield
    
    # Shutdown: Stop queue processor and cancel pending requests
    global queue_processor_task
    if engine_queue:
        engine_queue.stop()
        await engine_queue.cancel_all_pending()
    
    if queue_processor_task and not queue_processor_task.done():
        queue_processor_task.cancel()
        try:
            await queue_processor_task
        except asyncio.CancelledError:
            pass
    
    if engine:
        try:
            await engine.quit()
        except:
            pass
    
    # Shutdown engine pool
    if engine_pool_instance:
        try:
            await engine_pool_instance.shutdown()
        except:
            pass
    
    if explorer_client:
        try:
            await explorer_client.close()
        except:
            pass


app = FastAPI(title="Chesster Backend", version="1.0.0", lifespan=lifespan)

# Lightweight liveness probe for dev tooling / scripts.
@app.get("/health")
async def health():
    return {"status": "ok"}

# Warm-up endpoint for interpreter API (called when user starts typing)
@app.post("/warmup/interpreter")
async def warmup_interpreter():
    """Warm up the interpreter API connection and cache."""
    try:
        # Just ensure the interpreter is initialized and router is ready
        if request_interpreter and request_interpreter.llm_router:
            # Trigger a minimal warm-up call
            request_interpreter._warm_up_system_prompt()
        return {"status": "warmed_up"}
    except Exception as e:
        # Non-fatal - just return error
        return {"status": "error", "message": str(e)}

# CORS - Allow local development origins and production domains (Vercel, Render, etc.)
# Note: Cannot use allow_origins=["*"] with allow_credentials=True per CORS spec.
# We whitelist common local dev origins explicitly, and additionally allow common LAN origins and Vercel domains via regex.

# Get allowed origins from environment variable (comma-separated) or use defaults
allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "")
allowed_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
    "http://localhost",  # No port (defaults to 80, but some browsers might send this)
    "http://127.0.0.1",  # No port
]
if allowed_origins_env:
    # Add custom origins from environment variable
    allowed_origins.extend([origin.strip() for origin in allowed_origins_env.split(",") if origin.strip()])

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    # Allow LAN IPs (192.168.x.x, 10.x.x.x, 172.16-31.x.x), localhost on any port, and Vercel domains.
    # This regex matches: http://localhost, http://localhost:3000, http://192.168.1.1:3000, https://*.vercel.app, etc.
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+|172\.(1[6-9]|2[0-9]|3[0-1])\.\d+\.\d+|.*\.vercel\.app|.*\.onrender\.com)(:\d+)?/?$",
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
    expose_headers=["*"],  # Expose all headers
    max_age=3600,
)


# ============================================================================
# Helper Functions
# ============================================================================

def win_prob_from_cp(cp: int) -> float:
    """Convert centipawn eval to win probability using logistic function."""
    return 1.0 / (1.0 + math.exp(-cp / 400.0))


def format_eval(cp: int, mate_score: int = 10000) -> str:
    """
    Format evaluation for display.
    Converts mate scores (9999, 10000, -9999, -10000) to mate notation (M8, M-5, etc.)
    
    Args:
        cp: Centipawn evaluation
        mate_score: Threshold for mate detection (default 10000)
    
    Returns:
        Formatted string: either "M#" for mate or cp value
    """
    if abs(cp) >= mate_score - 100:  # Within 100cp of mate score
        # Calculate moves to mate
        if cp > 0:
            moves_to_mate = (mate_score - cp) // 100 + 1
            return f"M{moves_to_mate}"
        else:
            moves_to_mate = (mate_score + cp) // 100 + 1
            return f"M-{moves_to_mate}"
    return str(cp)


def game_phase(board: chess.Board) -> str:
    """Determine game phase based on piece count."""
    piece_count = len(board.piece_map())
    if piece_count >= 28:
        return "opening"
    elif piece_count >= 12:
        return "middlegame"
    else:
        return "endgame"


def piece_quality(board: chess.Board, square: chess.Square) -> float:
    """Simple piece quality metric based on mobility."""
    piece = board.piece_at(square)
    if not piece:
        return 0.0
    
    # Count safe mobility
    mobility = 0
    board_copy = board.copy()
    for move in board_copy.legal_moves:
        if move.from_square == square:
            mobility += 1
    
    # Bonus for rooks on open/semi-open files
    bonus = 0.0
    if piece.piece_type == chess.ROOK:
        file = chess.square_file(square)
        file_pawns = sum(1 for sq in chess.SQUARES 
                        if board.piece_at(sq) and 
                        board.piece_at(sq).piece_type == chess.PAWN and
                        chess.square_file(sq) == file)
        if file_pawns == 0:
            bonus = 0.2
        elif file_pawns == 1:
            bonus = 0.1
    
    quality = min(1.0, (mobility / 15.0) + bonus)
    return round(quality, 2)


async def probe_candidates(board: chess.Board, multipv: int = 3, depth: int = 16) -> List[Dict[str, Any]]:
    """Probe engine for top candidate moves."""
    if not engine:
        return []
    
    try:
        info = await engine_queue.enqueue(
            engine_queue.engine.analyse,
            board,
            chess.engine.Limit(depth=depth),
            multipv=multipv
        )
        
        candidates = []
        if isinstance(info, list):
            infos = info
        else:
            infos = [info]
        
        for item in infos:
            pv = item.get("pv", [])
            if not pv:
                continue
            
            move = pv[0]
            score = item.get("score")
            if not score:
                continue
            
            # Convert score to CP
            if score.is_mate():
                mate_in = score.relative.mate()
                eval_cp = 10000 if mate_in > 0 else -10000
            else:
                eval_cp = score.relative.score(mate_score=10000)
            
            # Build PV in SAN
            board_copy = board.copy()
            pv_san_list = []
            for m in pv[:6]:  # Limit to 6 moves
                try:
                    pv_san_list.append(board_copy.san(m))
                    board_copy.push(m)
                except:
                    break
            pv_san = " ".join(pv_san_list)
            
            candidates.append({
                "move": board.san(move),
                "uci": move.uci(),
                "eval_cp": eval_cp,
                "pv": pv,  # Include raw PV moves for internal use
                "pv_san": pv_san,
                "depth": depth
            })
        
        return candidates
    except Exception as e:
        print(f"Error probing candidates: {e}")
        return []


async def find_threats(board: chess.Board) -> List[Dict[str, Any]]:
    """Find tactical threats by analyzing opponent's best moves."""
    if not engine:
        return []
    
    # Switch perspective
    board.push(chess.Move.null())
    
    threats = []
    try:
        # Analyze opponent's candidates at shallow depth
        info = await engine_queue.enqueue(
            engine_queue.engine.analyse,
            board,
            chess.engine.Limit(depth=10),
            multipv=3
        )
        
        if isinstance(info, list):
            infos = info
        else:
            infos = [info]
        
        for item in infos:
            pv = item.get("pv", [])
            score = item.get("score")
            if not pv or not score:
                continue
            
            # Get eval change
            if score.is_mate():
                mate_in = score.relative.mate()
                eval_cp = 10000 if mate_in > 0 else -10000
            else:
                eval_cp = score.relative.score(mate_score=10000)
            
            # If opponent gains >= 120cp, it's a threat
            if eval_cp >= 120:
                board_copy = board.copy()
                pv_san_list = []
                for m in pv[:4]:
                    try:
                        pv_san_list.append(board_copy.san(m))
                        board_copy.push(m)
                    except:
                        break
                pv_san = " ".join(pv_san_list)
                
                threats.append({
                    "side": "B" if board.turn == chess.BLACK else "W",
                    "desc": f"Threat: {pv_san_list[0] if pv_san_list else ''}",
                    "delta_cp": eval_cp,
                    "pv_san": pv_san
                })
    except Exception as e:
        print(f"Error finding threats: {e}")
    finally:
        board.pop()  # Remove null move
    
    return threats


def extract_themes(board: chess.Board, eval_cp: int) -> List[str]:
    """Extract positional themes from the position."""
    themes = []
    
    # Check for open files
    for file in range(8):
        file_pawns = sum(1 for sq in chess.SQUARES 
                        if board.piece_at(sq) and 
                        board.piece_at(sq).piece_type == chess.PAWN and
                        chess.square_file(sq) == file)
        if file_pawns == 0:
            file_name = chess.FILE_NAMES[file]
            themes.append(f"open {file_name}-file")
    
    # Check for weak squares (simple heuristic)
    if eval_cp > 150:
        themes.append("white advantage")
    elif eval_cp < -150:
        themes.append("black advantage")
    
    # Check piece activity
    white_mobility = sum(1 for _ in board.legal_moves)
    board.push(chess.Move.null())
    try:
        black_mobility = sum(1 for _ in board.legal_moves)
    except:
        black_mobility = 0
    board.pop()
    
    if white_mobility > black_mobility * 1.5:
        themes.append("white space advantage")
    elif black_mobility > white_mobility * 1.5:
        themes.append("black space advantage")
    
    return themes[:3]  # Limit to 3 themes


# ============================================================================
# Pydantic Models
# ============================================================================

class PlayMoveRequest(BaseModel):
    fen: str
    user_move_san: str
    engine_elo: Optional[int] = None
    time_ms: Optional[int] = 1500


class AnnotateRequest(BaseModel):
    fen: str
    pgn: str
    comments: List[Dict[str, Any]] = Field(default_factory=list)
    nags: List[Dict[str, Any]] = Field(default_factory=list)
    arrows: List[Dict[str, str]] = Field(default_factory=list)
    highlights: List[Dict[str, str]] = Field(default_factory=list)


class RaiseMoveConfidenceRequest(BaseModel):
    fen: str
    move_san: str
    target: int = 80  # Legacy: kept for backward compatibility
    mode: str = "line"  # "line", "end", or "depth"
    target_line_conf: Optional[int] = None  # Target for line confidence (excludes last PV node)
    target_end_conf: Optional[int] = None  # Target for end confidence (last PV node only)
    max_depth: Optional[int] = None  # Maximum tree depth in ply
    existing_nodes: Optional[List[Dict[str, Any]]] = None  # For incremental updates


class RaisePositionConfidenceRequest(BaseModel):
    fen: str
    target: int = 80


class OpeningLessonRequest(BaseModel):
    user_id: str
    chat_id: Optional[str] = None
    opening_query: Optional[str] = None
    fen: Optional[str] = None
    eco: Optional[str] = None
    orientation: Optional[Literal["white", "black"]] = "white"
    variation_hint: Optional[str] = None


# ============================================================================
# Endpoints
# ============================================================================

@app.get("/")
async def root():
    return {"message": "Chesster Backend API", "status": "running"}


@app.get("/meta")
async def get_meta():
    """Return metadata about the API."""
    return {
        "name": "Chesster",
        "version": "1.0.0",
        "modes": ["PLAY", "ANALYZE", "TACTICS", "DISCUSS"],
        "system_prompt": SYSTEM_PROMPT
    }


# ============================================================================
# ENGINE POOL ENDPOINTS
# ============================================================================

@app.get("/engine_pool/status")
async def engine_pool_status():
    """Get the current status of the engine pool."""
    if engine_pool_instance is None:
        return {
            "available": False,
            "error": "Engine pool not initialized"
        }
    
    return {
        "available": True,
        **engine_pool_instance.get_status()
    }


@app.get("/engine_pool/health")
async def engine_pool_health():
    """Perform a quick health check on the engine pool."""
    if engine_pool_instance is None:
        return {
            "healthy": False,
            "error": "Engine pool not initialized"
        }
    
    return await engine_pool_instance.health_check()


# Sample PGN for testing
TEST_PGN = """[Event "Test Game"]
[Site "Test"]
[Date "2024.01.01"]
[White "Player1"]
[Black "Player2"]
[Result "1-0"]

1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6 5. O-O Be7 6. Re1 b5 7. Bb3 d6 
8. c3 O-O 9. h3 Nb8 10. d4 Nbd7 11. Nbd2 Bb7 12. Bc2 Re8 13. Nf1 Bf8 
14. Ng3 g6 15. Bg5 h6 16. Bd2 Bg7 17. a4 c5 18. d5 c4 19. b4 Nh5 20. Nxh5 gxh5 1-0"""


@app.post("/engine_pool/test")
async def engine_pool_test():
    """
    Run a full test game review using the engine pool.
    Returns timing and success information.
    """
    import time as _time
    
    if engine_pool_instance is None:
        return {
            "success": False,
            "error": "Engine pool not initialized"
        }
    
    # Parse test PGN
    pgn_io = chess.pgn.read_game(StringIO(TEST_PGN))
    if not pgn_io:
        return {
            "success": False,
            "error": "Failed to parse test PGN"
        }
    
    # Collect positions
    positions = []
    board = chess.Board()
    for move in pgn_io.mainline_moves():
        positions.append((board.fen(), move))
        board.push(move)
    
    n_positions = len(positions)
    print(f"🧪 Engine pool test: Analyzing {n_positions} positions...")
    
    start_time = _time.time()
    
    try:
        # Analyze in parallel
        results = await engine_pool_instance.analyze_game_parallel(
            positions,
            depth=10,  # Lower depth for test speed
            multipv=1
        )
        
        elapsed = _time.time() - start_time
        
        # Count successes
        successes = sum(1 for r in results if r.get("success", False))
        
        print(f"✅ Engine pool test complete: {successes}/{n_positions} in {elapsed:.2f}s")
        
        return {
            "success": True,
            "positions_analyzed": n_positions,
            "successful_analyses": successes,
            "failed_analyses": n_positions - successes,
            "elapsed_seconds": round(elapsed, 2),
            "positions_per_second": round(n_positions / elapsed, 2) if elapsed > 0 else 0,
            "pool_size": engine_pool_instance.pool_size,
            "message": f"Engine pool OK: {n_positions} moves analyzed in {elapsed:.1f}s ({engine_pool_instance.pool_size} engines)"
        }
        
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }


@app.post("/vision/board")
async def vision_board_endpoint(
    photo: UploadFile = File(...),
    preset: str = Form("digital"),
    orientation_hint: str = Form("white"),
):
    """Transcribe a chessboard photo into a FEN using the configured vision model."""
    if photo.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=415, detail="Unsupported image format")

    payload = await photo.read()
    if len(payload) > MAX_PHOTO_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="Image exceeds 8 MB limit")

    try:
        result = analyze_board_image(
            image_bytes=payload,
            preset=preset,
            orientation_hint=orientation_hint,
            openai_client=openai_client,
        )
    except BoardVisionError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return {
        "fen": result.fen,
        "confidence": result.confidence,
        "orientation": result.orientation,
        "uncertain_squares": [
            {"square": sq.square, "piece": sq.piece, "confidence": sq.confidence}
            for sq in result.uncertain_squares
        ],
        "notes": result.notes,
    }


def _extract_game_summary_from_pgn(pgn_text: str) -> Optional[Dict[str, Any]]:
    """Parse PGN and return headers + final FEN for quick summaries."""
    try:
        game = chess.pgn.read_game(StringIO(pgn_text))
        if not game:
            return None

        board = game.board()
        move_count = 0
        for move in game.mainline_moves():
            board.push(move)
            move_count += 1

        return {
            "headers": dict(game.headers),
            "final_fen": board.fen(),
            "move_count": move_count,
        }
    except Exception as exc:
        print(f"⚠️  Failed to parse PGN summary: {exc}")
        return None


@app.get("/game_lookup")
async def lookup_games(
    username: str = Query(..., min_length=2, description="Username to lookup"),
    opponent: Optional[str] = Query(None, description="Optional opponent substring filter"),
    platform: str = Query("lichess", description="Source platform: lichess, chess.com, combined"),
    max_games: int = Query(10, ge=1, le=50)
):
    """Lookup recent games for a player and return PGNs for the load panel."""
    if not game_fetcher:
        raise HTTPException(status_code=503, detail="Game fetcher not initialized")

    try:
        print(f"[game_lookup] Fetching games for {username} on {platform} (max {max_games})")
        fetched_games = await game_fetcher.fetch_games(
            username=username,
            platform=platform,
            max_games=max_games,
            months_back=6
        )
        print(f"[game_lookup] Raw games fetched: {len(fetched_games)}")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch games: {exc}") from exc

    opponent_lower = opponent.lower() if opponent else None
    results: List[Dict[str, Any]] = []

    for raw_game in fetched_games:
        pgn_text = raw_game.get("pgn")
        if not pgn_text:
            continue

        summary = _extract_game_summary_from_pgn(pgn_text)
        if not summary:
            continue

        headers = summary["headers"]
        white_name = headers.get("White", "White")
        black_name = headers.get("Black", "Black")
        result = headers.get("Result", "*")
        date_str = headers.get("UTCDate") or headers.get("Date") or raw_game.get("date") or ""

        if opponent_lower:
            if opponent_lower not in white_name.lower() and opponent_lower not in black_name.lower():
                continue

        results.append({
            "id": raw_game.get("game_id") or headers.get("Site") or f"{white_name}_vs_{black_name}_{len(results)}",
            "platform": raw_game.get("platform", platform),
            "white": white_name,
            "black": black_name,
            "result": result,
            "date": date_str,
            "fen": summary["final_fen"],
            "pgn": pgn_text,
            "move_count": summary["move_count"],
            "opponent_name": raw_game.get("opponent_name"),
        })

        if len(results) >= max_games:
            break

    return {"games": results}


@app.get("/engine/metrics")
async def engine_metrics():
    """Return Stockfish engine queue metrics."""
    if not engine_queue:
        raise HTTPException(status_code=503, detail="Engine not initialized")
    return engine_queue.get_metrics()


@app.get("/analyze_position")
async def analyze_position(
    fen: str = Query(..., description="FEN string of the position"),
    lines: int = Query(3, ge=1, le=5, description="Number of candidate lines"),
    depth: int = Query(18, ge=10, le=22, description="Search depth"),
    light_mode: bool = Query(False, description="Skip piece profiling (Step 7) for faster analysis")
):
    """
    Complete position analysis with theme-based evaluation.
    
    NEW PIPELINE:
    1. Stockfish analysis of starting position
    2. Material balance calculation
    3. Theme + tag analysis of starting position
    4. Build PV final position
    5. Stockfish analysis of final position
    6. Theme + tag analysis of final position
    7. Delta computation and plan classification
    """
    print(f"🔍 [ANALYZE_POSITION] Request received for FEN: {fen[:50]}... (depth={depth}, lines={lines})")
    if not engine:
        print("❌ [ANALYZE_POSITION] Engine not available")
        raise HTTPException(status_code=503, detail="Stockfish engine not available")
    
    try:
        board = chess.Board(fen)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid FEN: {str(e)}")
    
    try:
        # STEP 1: Extract candidate moves (single Stockfish call for eval + candidates)
        print("🎯 Step 1/6: Extracting candidate moves with Stockfish...")
        candidates = await probe_candidates(board, multipv=lines, depth=depth)
        print(f"   Found {len(candidates)} candidate lines")
        
        # Extract eval and PV from first candidate
        if candidates:
            eval_cp = candidates[0]["eval_cp"]
            pv = candidates[0].get("pv", [])
            print(f"   Eval: {eval_cp}cp, PV: {len(pv)} moves")
        else:
            eval_cp = 0
            pv = []
            print("   ⚠️ No candidates found, using default eval")
        
        # STEP 2: Calculate material balance and positional CP
        print("🧮 Step 2/6: Calculating material balance...")
        material_balance_start = calculate_material_balance(board)
        positional_cp_start = eval_cp - material_balance_start
        
        print(f"   Material: {material_balance_start}cp, Positional: {positional_cp_start}cp")
        
        # STEP 3: Build final FEN from PV (do this early so we can parallelize theme calculations)
        print("♟️  Step 3/6: Playing out principal variation...")
        final_board = board.copy()
        for move in pv:
            final_board.push(move)
        final_fen = final_board.fen()
        
        print(f"   PV final position: {final_fen[:50]}...")
        
        # STEP 4: Analyze both positions in parallel (themes + tags)
        print("🏷️  Step 4/6: Analyzing positions (parallel theme/tag calculations)...")
        loop = asyncio.get_event_loop()
        
        with ProcessPoolExecutor(max_workers=4) as pool:
            # Start both theme/tag calculations in parallel
            themes_start_future = loop.run_in_executor(pool, compute_themes_and_tags, fen)
            themes_final_future = loop.run_in_executor(pool, compute_themes_and_tags, final_fen)
            
            # While themes calculate, do Stockfish analysis of final position
            print("🔍 Step 5/6: Analyzing PV final position with Stockfish...")
            final_info = await engine_queue.enqueue(
                engine_queue.engine.analyse,
                final_board,
                chess.engine.Limit(depth=depth)
            )
            final_score = final_info.get("score")
            
            if final_score and final_score.is_mate():
                final_mate = final_score.relative.mate()
                eval_cp_final = 10000 if final_mate > 0 else -10000
            elif final_score:
                eval_cp_final = final_score.relative.score(mate_score=10000)
            else:
                eval_cp_final = 0
            
            material_balance_final = calculate_material_balance(final_board)
            positional_cp_final = eval_cp_final - material_balance_final
            
            print(f"   Final eval: {eval_cp_final}cp, Material: {material_balance_final}cp")
            
            # Wait for theme/tag results
            raw_start = await themes_start_future
            raw_final = await themes_final_future

            # Calculate theme scores
            raw_start["theme_scores"] = compute_theme_scores(raw_start["themes"])
            raw_final["theme_scores"] = compute_theme_scores(raw_final["themes"])

            # Add engine-based threats (for both start and final positions)
            print("🔍 Detecting threats...")
            from threat_analyzer import detect_engine_threats
            threats_start = await detect_engine_threats(fen, engine_queue, depth)
            threats_final = await detect_engine_threats(final_fen, engine_queue, depth)

            # Build analysis_start and analysis_final in the same format as analyze_fen
            analysis_start = {
                "fen": fen,
                "themes": raw_start["themes"],
                "tags": raw_start["tags"],
                "material_balance_cp": raw_start["material_balance_cp"],
                "theme_scores": raw_start["theme_scores"],
                "engine_threats": threats_start
            }
            analysis_final = {
                "fen": final_fen,
                "themes": raw_final["themes"],
                "tags": raw_final["tags"],
                "material_balance_cp": raw_final["material_balance_cp"],
                "theme_scores": raw_final["theme_scores"],
                "engine_threats": threats_final
            }
        
        print(f"   Detected {len(analysis_start['tags'])} tags in start, {len(analysis_final['tags'])} tags in final")
        
        # Calculate delta and classify plans
        print("📊 Computing delta and classifying plans...")
        delta = calculate_delta(
            analysis_start["themes"],
            analysis_final["themes"],
            material_balance_start,
            material_balance_final,
            positional_cp_start,
            positional_cp_final,
            analysis_start["tags"],
            analysis_final["tags"]
        )
        
        print(f"   Plan types - White: {delta['white']['plan_type']}, Black: {delta['black']['plan_type']}")
        
        # Get game phase
        phase = game_phase(board)
        
        # STEP 7: Build piece profiles (NNUE + tags + interactions) - SKIP IN LIGHT MODE
        piece_profiles_start = {}
        piece_profiles_final = {}
        piece_trajectories = {}
        captures_in_pv = []
        profile_summary = {}
        square_control_start = {}
        square_control_final = {}
        piece_interactions_start = []
        piece_interactions_final = []
        pv_fen_profiles = []
        
        if not light_mode:
            print("🧩 Step 7: Building piece profiles...")
        try:
            # Get NNUE dumps for start and final positions
            nnue_dump_start = get_nnue_dump(fen)
            nnue_dump_final = get_nnue_dump(final_fen) if final_fen != fen else nnue_dump_start
            
            # Build piece profiles
            piece_profiles_start = build_piece_profiles(
                fen=fen,
                nnue_dump=nnue_dump_start,
                tags=analysis_start.get("tags", []),
                themes=analysis_start.get("themes", {}),
                phase=phase
            )
            
            piece_profiles_final = build_piece_profiles(
                fen=final_fen,
                nnue_dump=nnue_dump_final,
                tags=analysis_final.get("tags", []),
                themes=analysis_final.get("themes", {}),
                phase=phase
            )
            
            # Compute square control
            square_control_start = compute_square_control(board)
            square_control_final = compute_square_control(final_board)
            
            # Get profile summary
            profile_summary = get_profile_summary(piece_profiles_start)
            
            # Add coordination scores
            profile_summary["white"]["coordination_score"] = round(
                compute_coordination_score(board, chess.WHITE), 2
            )
            profile_summary["black"]["coordination_score"] = round(
                compute_coordination_score(board, chess.BLACK), 2
            )
            
            # Track piece trajectories across PV
            if pv:
                pv_fens = compute_pv_fens(fen, pv)
                
                # Build profiles for each PV position (sample up to 5 positions)
                sample_indices = [0, len(pv_fens) - 1]  # Start and end
                if len(pv_fens) > 2:
                    mid = len(pv_fens) // 2
                    sample_indices.insert(1, mid)
                
                profiles_by_fen = {fen: piece_profiles_start, final_fen: piece_profiles_final}
                
                for idx in sample_indices:
                    if idx < len(pv_fens):
                        sample_fen = pv_fens[idx]
                        if sample_fen not in profiles_by_fen:
                            sample_board = chess.Board(sample_fen)
                            sample_dump = get_nnue_dump(sample_fen)
                            from tag_detector import aggregate_all_tags
                            sample_tags = await aggregate_all_tags(sample_board, engine_queue)
                            profiles_by_fen[sample_fen] = build_piece_profiles(
                                fen=sample_fen,
                                nnue_dump=sample_dump,
                                tags=sample_tags,
                                phase=phase
                            )
                
                # Track trajectories
                piece_trajectories = track_pv_profiles(pv_fens, profiles_by_fen)
                
                # Detect captures
                captures_in_pv = detect_captures_in_pv(fen, pv)
                
                # Build PV FEN profiles for response
                for idx, pv_fen in enumerate(pv_fens):
                    if pv_fen in profiles_by_fen:
                        pv_fen_profiles.append({
                            "fen_idx": idx,
                            "fen": pv_fen,
                            "profiles": profiles_by_fen[pv_fen]
                        })
            
            print(f"   Built profiles for {len(piece_profiles_start)} pieces")
            
        except Exception as pe:
            print(f"⚠️ Piece profiling error (non-fatal): {pe}")
            import traceback
            traceback.print_exc()
        else:
            print("⏭️  Step 7: Skipped (light mode enabled)")
        
        # Convert PV to SAN
        pv_san = []
        temp_board = board.copy()
        for move in pv:
            try:
                pv_san.append(temp_board.san(move))
                temp_board.push(move)
            except:
                break
        
        # Filter out null/zero themes and tags
        def filter_themes(theme_scores: Dict) -> Dict:
            """Remove themes with zero or near-zero scores."""
            return {k: v for k, v in theme_scores.items() if k == "total" or abs(v) > 0.01}
        
        def filter_tags(tags: List[Dict]) -> List[Dict]:
            """Return only non-empty tags."""
            return [t for t in tags if t.get("tag_name")]
        
        # Build response with two clear chunks per side
        white_mat_start = material_balance_start if board.turn == chess.WHITE else -material_balance_start
        white_pos_start = positional_cp_start if board.turn == chess.WHITE else -positional_cp_start
        black_mat_start = -material_balance_start if board.turn == chess.WHITE else material_balance_start
        black_pos_start = -positional_cp_start if board.turn == chess.WHITE else positional_cp_start
        
        response = {
            "fen": fen,
            "eval_cp": eval_cp,
            "pv": pv_san,
            "best_move": candidates[0]["move"] if candidates else (pv_san[0] if pv_san else ""),
            "candidate_moves": candidates,
            "phase": phase,
            "light_mode": light_mode,  # Flag to indicate if light mode was used
            "threats": {
                "white": threats_start["threats_by_side"]["white"] + threats_final["threats_by_side"]["white"],
                "black": threats_start["threats_by_side"]["black"] + threats_final["threats_by_side"]["black"]
            },
            
            "white_analysis": {
                "chunk_1_immediate": {
                    "description": "What the position IS right now for White",
                    "material_balance_cp": white_mat_start,
                    "positional_cp_significance": white_pos_start,
                    "theme_scores": filter_themes(analysis_start["theme_scores"]["white"]),
                    "tags": filter_tags([t for t in analysis_start["tags"] if t.get("side") == "white" or t.get("side") == "both"])
                },
                "chunk_2_plan_delta": {
                    "description": "How it SHOULD unfold for White (after PV)",
                    "plan_type": delta["white"]["plan_type"],
                    "plan_explanation": delta["white"]["plan_explanation"],
                    "material_delta_cp": delta["white"]["material_delta_cp"],
                    "positional_delta_cp": delta["white"]["positional_delta_cp"],
                    "theme_changes": {k: v for k, v in delta["white"]["theme_deltas"].items() if abs(v) > 0.5}
                }
            },
            
            "black_analysis": {
                "chunk_1_immediate": {
                    "description": "What the position IS right now for Black",
                    "material_balance_cp": black_mat_start,
                    "positional_cp_significance": black_pos_start,
                    "theme_scores": filter_themes(analysis_start["theme_scores"]["black"]),
                    "tags": filter_tags([t for t in analysis_start["tags"] if t.get("side") == "black" or t.get("side") == "both"])
                },
                "chunk_2_plan_delta": {
                    "description": "How it SHOULD unfold for Black (after PV)",
                    "plan_type": delta["black"]["plan_type"],
                    "plan_explanation": delta["black"]["plan_explanation"],
                    "material_delta_cp": delta["black"]["material_delta_cp"],
                    "positional_delta_cp": delta["black"]["positional_delta_cp"],
                    "theme_changes": {k: v for k, v in delta["black"]["theme_deltas"].items() if abs(v) > 0.5}
                }
            },
            
            # Piece profiling data
            "piece_profiles_start": piece_profiles_start,
            "piece_profiles_final": piece_profiles_final,
            "piece_trajectories": piece_trajectories,
            "captures_in_pv": captures_in_pv,
            "square_control_start": get_control_summary(square_control_start) if square_control_start else {},
            "square_control_final": get_control_summary(square_control_final) if square_control_final else {},
            "profile_summary": profile_summary,
            "pv_fen_profiles": pv_fen_profiles[:5],  # Limit to 5 positions
        }
        # Attach position-level confidence (best move from side-to-move)
        print("📊 [ANALYZE_POSITION] Computing position confidence...")
        try:
            position_conf = await compute_position_confidence(engine_queue, fen, target_conf=80)
            response["position_confidence"] = position_conf
            print("✅ [ANALYZE_POSITION] Position confidence computed successfully")
        except Exception as ce:
            print(f"⚠️ [ANALYZE_POSITION] Confidence computation failed (position): {ce}")
            import traceback
            traceback.print_exc()
            response["position_confidence"] = neutral_confidence()
        
        print("✅ [ANALYZE_POSITION] Analysis complete, returning response")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Analysis error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/play_move")
async def play_move(request: PlayMoveRequest):
    """Process a user move and return engine response."""
    if not engine:
        raise HTTPException(status_code=503, detail="Stockfish engine not available")
    
    try:
        board = chess.Board(request.fen)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid FEN: {str(e)}")
    
    # Parse and validate user move
    try:
        user_move = board.parse_san(request.user_move_san)
        if user_move not in board.legal_moves:
            return {
                "legal": False,
                "user_move_san": request.user_move_san,
                "error": "Illegal move"
            }
        board.push(user_move)
    except Exception as e:
        return {
            "legal": False,
            "user_move_san": request.user_move_san,
            "error": str(e)
        }
    
    # Configure engine strength if requested (through queue)
    if request.engine_elo:
        try:
            config_dict = {
                "UCI_LimitStrength": True,
                "UCI_Elo": request.engine_elo
            }
            await engine_queue.enqueue(engine.configure, config_dict)
        except:
            pass  # Some engines don't support strength limiting
    
    # Get engine move (through queue)
    try:
        time_limit = chess.engine.Limit(time=request.time_ms / 1000.0) if request.time_ms else chess.engine.Limit(depth=12)
        result = await engine_queue.enqueue(engine.play, board, time_limit)
        engine_move = result.move
        engine_move_san = board.san(engine_move)
        board.push(engine_move)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Engine move failed: {str(e)}")
    
    # Reset engine to full strength (through queue)
    if request.engine_elo:
        try:
            reset_dict = {"UCI_LimitStrength": False}
            await engine_queue.enqueue(engine.configure, reset_dict)
        except:
            pass
    
    # Get eval after both moves
    try:
        eval_info = await engine_queue.enqueue(engine_queue.engine.analyse, board, chess.engine.Limit(depth=12))
        score = eval_info.get("score")
        if score and score.is_mate():
            mate_in = score.relative.mate()
            eval_cp_after = 10000 if mate_in > 0 else -10000
        elif score:
            eval_cp_after = score.relative.score(mate_score=10000)
        else:
            eval_cp_after = 0
    except:
        eval_cp_after = 0
    
    return {
        "legal": True,
        "user_move_san": request.user_move_san,
        "engine_move_san": engine_move_san,
        "new_fen": board.fen(),
        "eval_cp_after": eval_cp_after,
        "commentary_points": []
    }


@app.get("/opening_lookup")
async def opening_lookup(fen: str = Query(..., description="FEN string")):
    """Look up opening information (stub for MVP)."""
    # MVP: Return empty/stub data
    # In production, this would query an opening book database
    return {
        "eco": "",
        "name": "",
        "book_moves": [],
        "novelty_ply": None
    }


@app.post("/confidence/raise_move")
async def confidence_raise_move(req: RaiseMoveConfidenceRequest):
    if not engine:
        raise HTTPException(status_code=503, detail="Stockfish engine not available")
    try:
        # Determine target based on mode
        target_conf = req.target
        if req.mode == "line" and req.target_line_conf is not None:
            target_conf = req.target_line_conf
        elif req.mode == "end" and req.target_end_conf is not None:
            target_conf = req.target_end_conf
        
        conf = await compute_move_confidence(
            engine_queue, 
            req.fen, 
            req.move_san, 
            target_conf=target_conf,
            branch=True,
            existing_nodes=req.existing_nodes,
            mode=req.mode,
            target_line_conf=req.target_line_conf,
            target_end_conf=req.target_end_conf,
            max_depth=req.max_depth
        )
        
        # DEBUG: Log what's being returned from the endpoint
        print("\n" + "="*80)
        print("🌐 API ENDPOINT: /confidence/raise_move RETURNING")
        print("="*80)
        print(f"Confidence data keys: {list(conf.keys())}")
        print(f"Nodes in response: {len(conf.get('nodes', []))}")
        print(f"Overall confidence: {conf.get('overall_confidence')}")
        print(f"Line confidence: {conf.get('line_confidence')}")
        print(f"End confidence: {conf.get('end_confidence')}")
        if conf.get('nodes'):
            print(f"First node ID: {conf['nodes'][0].get('id')}")
            print(f"First node confidence: {conf['nodes'][0].get('ConfidencePercent')}")
        print("="*80 + "\n")
        
        return {"confidence": conf}
    except Exception as e:
        print(f"⚠️ confidence/raise_move error: {e}")
        import traceback
        print(traceback.format_exc())
        return {"confidence": neutral_confidence()}


@app.post("/confidence/raise_position")
async def confidence_raise_position(req: RaisePositionConfidenceRequest):
    if not engine:
        raise HTTPException(status_code=503, detail="Stockfish engine not available")
    try:
        conf = await compute_position_confidence(engine_queue, req.fen, target_conf=req.target, branch=True)
        return {"position_confidence": conf}
    except Exception as e:
        print(f"⚠️ confidence/raise_position error: {e}")
        return {"position_confidence": neutral_confidence()}


@app.get("/tactics_next")
async def tactics_next(
    rating_min: Optional[int] = Query(None, description="Minimum rating"),
    rating_max: Optional[int] = Query(None, description="Maximum rating")
):
    """Get next tactics puzzle from tactics.json."""
    try:
        with open("tactics.json", "r") as f:
            tactics = json.load(f)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="tactics.json not found")
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"Invalid tactics.json: {str(e)}")
    
    # Filter by rating if specified
    filtered = tactics
    if rating_min is not None:
        filtered = [t for t in filtered if t.get("rating", 0) >= rating_min]
    if rating_max is not None:
        filtered = [t for t in filtered if t.get("rating", 9999) <= rating_max]
    
    if not filtered:
        raise HTTPException(status_code=404, detail="No tactics found matching criteria")
    
    # Return first matching tactic (in production, would track progress)
    return filtered[0]


@app.post("/annotate")
async def annotate(request: AnnotateRequest):
    """Validate and echo annotation data."""
    # MVP: Just validate schema and return the same data
    # In production, this would save to a database
    try:
        board = chess.Board(request.fen)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid FEN: {str(e)}")
    
    return {
        "fen": request.fen,
        "pgn": request.pgn,
        "comments": request.comments,
        "nags": request.nags,
        "arrows": request.arrows,
        "highlights": request.highlights
    }


@app.post("/analyze_move")
async def analyze_move(
    fen: str = Query(..., description="FEN before the move"),
    move_san: str = Query(..., description="Move in SAN notation"),
    depth: int = Query(18, ge=10, le=20, description="Analysis depth")
):
    """
    Theme-based move analysis using 3-5 analyze_fen calls.
    
    CASE 1 (Best Move): 3 AF calls
      - AF_starting, AF_best, AF_pv_best
    
    CASE 2 (Not Best): 5 AF calls  
      - AF_starting, AF_best, AF_pv_best, AF_played, AF_pv_played
    
    Compares tags/themes to show what the move accomplished.
    """
    if not engine:
        raise HTTPException(status_code=503, detail="Stockfish engine not available")
    
    try:
        board = chess.Board(fen)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid FEN: {str(e)}")
    
    try:
        # Determine which side is making the move (side to move in the FEN)
        side_to_move = "white" if board.turn == chess.WHITE else "black"
        print(f"🔍 Analyzing move: {move_san} (by {side_to_move})")
        
        # Check if position is in opening theory (Lichess masters DB)
        print("📚 Checking Lichess masters database for theory...")
        theory_check_before = check_lichess_masters(fen)
        is_theory_before = theory_check_before['isTheory']
        opening_name = theory_check_before.get('opening', '')
        print(f"   Theory before: {is_theory_before}, Opening: {opening_name or 'N/A'}")
        
        # Get best move from Stockfish
        info = await engine_queue.enqueue(engine_queue.engine.analyse, board, chess.engine.Limit(depth=depth), multipv=2)
        best_move_uci = str(info[0]["pv"][0])
        best_move_san = board.san(chess.Move.from_uci(best_move_uci))
        best_eval = info[0]["score"].relative.score(mate_score=10000)
        best_pv = info[0]["pv"]
        
        # Get second best for gap calculation
        second_best_eval = info[1]["score"].relative.score(mate_score=10000) if len(info) > 1 else best_eval
        second_best_gap_cp = abs(best_eval - second_best_eval)
        
        # Parse played move
        try:
            played_move = board.parse_san(move_san)
            if played_move not in board.legal_moves:
                raise HTTPException(status_code=400, detail=f"Illegal move: {move_san}")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid move notation: {str(e)}")
        
        # Calculate CP loss
        board_after_played = board.copy()
        board_after_played.push(played_move)
        played_info = await engine_queue.enqueue(engine_queue.engine.analyse, board_after_played, chess.engine.Limit(depth=depth))
        played_eval = -played_info["score"].relative.score(mate_score=10000)  # Flip for opponent
        cp_loss = best_eval - played_eval
        
        # Check if still in theory after the move
        fen_after = board_after_played.fen()
        theory_check_after = check_lichess_masters(fen_after)
        is_theory_after = theory_check_after['isTheory']
        opening_name_after = theory_check_after.get('opening', opening_name)  # Use more specific name if available
        print(f"   Theory after: {is_theory_after}, Opening: {opening_name_after or 'N/A'}")
        
        # Check if the specific move is a theory move (from position before)
        played_move_uci = played_move.uci()
        theory_moves_before = theory_check_before.get('theoryMoves', [])
        is_theory_move = played_move_uci in theory_moves_before
        print(f"   Theory moves available: {len(theory_moves_before)}, Played move {played_move_uci} is theory: {is_theory_move}")
        
        is_best_move = (move_san == best_move_san)
        
        # Categorize moves with threat categories (before determining move category)
        from threat_analyzer import categorize_threat
        
        # Categorize played move
        board_after_played = board.copy()
        board_after_played.push(played_move)
        played_move_category = categorize_threat(board, played_move, played_eval)
        played_move_threat_type = played_move_category["type"]
        played_move_threat_description = played_move_category["description"]
        
        # Categorize best move
        best_move_obj = chess.Move.from_uci(best_move_uci)
        best_move_category = categorize_threat(board, best_move_obj, best_eval)
        best_move_threat_type = best_move_category["type"]
        best_move_threat_description = best_move_category["description"]
        
        # Determine move category
        # PRIORITY 1: Check if the move itself is a theory move (from Lichess API)
        if is_theory_move:
            move_category = "📚 THEORY"
        elif cp_loss == 0 and second_best_gap_cp >= 50:
            move_category = "⚡ CRITICAL BEST"
        elif cp_loss == 0:
            move_category = "✓ BEST"
        elif cp_loss < 20:
            move_category = "✓ Excellent"
        elif cp_loss < 50:
            move_category = "✓ Good"
        elif cp_loss < 80:
            move_category = "!? Inaccuracy"
        elif cp_loss < 200:
            move_category = "? Mistake"
        else:
            move_category = "?? Blunder"
        
        # Add threat category context to move category
        if played_move_threat_type and played_move_threat_type != "attack":  # Don't add generic "attack"
            move_category += f" ({played_move_threat_type})"
        
        # AF_starting - before move
        print("📍 AF_starting: Analyzing position before move...")
        af_starting = await analyze_fen(fen, engine_queue, depth)
        
        if is_best_move:
            # CASE 1: Best move (3 analyze_fen calls)
            print(f"✓ Move {move_san} IS the best move (CP loss: 0)")
            
            # AF_best - after best move
            print("📍 AF_best: Analyzing position after best move...")
            board_best = board.copy()
            board_best.push(chess.Move.from_uci(best_move_uci))
            fen_best = board_best.fen()
            af_best = await analyze_fen(fen_best, engine_queue, depth)
            
            # AF_pv_best - final position after PV
            print("📍 AF_pv_best: Analyzing PV final position...")
            board_pv_best = board.copy()
            for move in best_pv:
                board_pv_best.push(move)
            fen_pv_best = board_pv_best.fen()
            af_pv_best = await analyze_fen(fen_pv_best, engine_queue, depth)
            
            # Get PV eval
            pv_info = await engine_queue.enqueue(engine_queue.engine.analyse, board_pv_best, chess.engine.Limit(depth=depth))
            pv_eval = pv_info["score"].relative.score(mate_score=10000)
            
            print(f"✅ Move analysis complete (best move case, 3 AF calls)")
            
            # Confidence (played == best)
            try:
                print(f"🔍 Computing confidence for best move: {best_move_san}")
                conf_best = await compute_move_confidence(engine_queue, fen, best_move_san, target_conf=80, branch=False)
                print(f"✅ Best move confidence: {len(conf_best.get('nodes', []))} nodes, line_conf={conf_best.get('line_confidence')}")
                print(f"🔍 Computing confidence for played move: {move_san}")
                conf_played = await compute_move_confidence(engine_queue, fen, move_san, target_conf=80, branch=False)
                print(f"✅ Played move confidence: {len(conf_played.get('nodes', []))} nodes, line_conf={conf_played.get('line_confidence')}")
            except Exception as ce:
                import traceback
                print(f"⚠️ Confidence computation failed (best case): {ce}")
                print(traceback.format_exc())
                conf_best = conf_played = neutral_confidence()

            return {
                "fen_before": fen,
                "move_played": move_san,
                "move_san": move_san,
                "side_to_move": side_to_move,
                "is_best_move": True,
                "is_theory": is_theory_after,
                "opening_name": opening_name_after,
                "move_category": move_category,
                "cp_loss": 0,
                "second_best_gap_cp": second_best_gap_cp,
                "eval_before_cp": best_eval,
                "eval_after_cp": played_eval,
                "eval_after_pv": pv_eval,
                "best_move_san": best_move_san,
                "played_move_threat_category": played_move_threat_type,
                "played_move_threat_description": played_move_threat_description,
                "best_move_threat_category": best_move_threat_type,
                "best_move_threat_description": best_move_threat_description,
                "case": "best_move",
                "analysis": {
                    "af_starting": af_starting,
                    "af_best": af_best,
                    "af_pv_best": af_pv_best
                },
                "confidence": {"played_move": conf_played, "best_move": conf_best}
            }
            
            # DEBUG: Log confidence data being returned
            print("\n" + "="*80)
            print("🌐 API ENDPOINT: /analyze_move RETURNING (best_move case)")
            print("="*80)
            print(f"Played move confidence nodes: {len(conf_played.get('nodes', []))}")
            print(f"Best move confidence nodes: {len(conf_best.get('nodes', []))}")
            if conf_played.get('nodes'):
                print(f"Played move first node: {conf_played['nodes'][0].get('id')}")
            if conf_best.get('nodes'):
                print(f"Best move first node: {conf_best['nodes'][0].get('id')}")
            print("="*80 + "\n")
        
        else:
            # CASE 2: Not best move (5 analyze_fen calls)
            print(f"⚠️  Move {move_san} is NOT best (best: {best_move_san}, CP loss: {cp_loss})")
            
            # AF_best
            print("📍 AF_best: Analyzing position after best move...")
            board_best = board.copy()
            board_best.push(chess.Move.from_uci(best_move_uci))
            fen_best = board_best.fen()
            af_best = await analyze_fen(fen_best, engine_queue, depth)
            
            # Get PV from best move
            best_pv_info = await engine_queue.enqueue(engine_queue.engine.analyse, board_best, chess.engine.Limit(depth=depth))
            best_pv_moves = best_pv_info["pv"]
            
            # AF_pv_best
            print("📍 AF_pv_best: Analyzing PV final from best move...")
            board_pv_best = board_best.copy()
            for move in best_pv_moves:
                board_pv_best.push(move)
            fen_pv_best = board_pv_best.fen()
            af_pv_best = await analyze_fen(fen_pv_best, engine_queue, depth)
            
            # AF_played
            print("📍 AF_played: Analyzing position after played move...")
            fen_played = board_after_played.fen()
            af_played = await analyze_fen(fen_played, engine_queue, depth)
            
            # Get PV from played position
            played_pv_info = await engine_queue.enqueue(engine_queue.engine.analyse, board_after_played, chess.engine.Limit(depth=depth))
            played_pv_moves = played_pv_info["pv"]
            
            # AF_pv_played
            print("📍 AF_pv_played: Analyzing PV final from played move...")
            board_pv_played = board_after_played.copy()
            for move in played_pv_moves:
                board_pv_played.push(move)
            fen_pv_played = board_pv_played.fen()
            af_pv_played = await analyze_fen(fen_pv_played, engine_queue, depth)
            
            # Get PV evals
            pv_best_eval = await engine_queue.enqueue(engine_queue.engine.analyse, board_pv_best, chess.engine.Limit(depth=depth))
            pv_best_eval_cp = pv_best_eval["score"].relative.score(mate_score=10000)
            pv_played_eval = await engine_queue.enqueue(engine_queue.engine.analyse, board_pv_played, chess.engine.Limit(depth=depth))
            pv_played_eval_cp = pv_played_eval["score"].relative.score(mate_score=10000)
            
            # Calculate eval after best move (from White's perspective if White to move)
            best_move_eval = -best_pv_info["score"].relative.score(mate_score=10000)
            
            # Calculate what the played move did and what the best move does uniquely
            from delta_analyzer import compare_tags_for_move_analysis
            played_move_description = compare_tags_for_move_analysis(af_starting, af_played, side_to_move)
            best_move_description = compare_tags_for_move_analysis(af_starting, af_best, side_to_move)
            
            # Find tags unique to best move (not in played move)
            played_tags = {t.get("tag_name") for t in af_played.get("tags", [])}
            best_tags = {t.get("tag_name") for t in af_best.get("tags", [])}
            starting_tags = {t.get("tag_name") for t in af_starting.get("tags", [])}
            
            # Find tags that best move created (appeared AFTER best move, not before)
            # These describe what the best move accomplished
            best_created_tags = [t for t in af_best.get("tags", []) 
                                if t.get("tag_name") not in starting_tags]
            
            # Find what the played move neglected:
            # 1. Tags available in starting position that best move used but played move didn't
            best_used_available_tags = [t for t in af_best.get("tags", []) 
                                        if t.get("tag_name") in starting_tags and t.get("tag_name") not in played_tags]
            
            # 2. Tags that best move created that played move didn't create
            best_created_neglected = [t for t in best_created_tags 
                                     if t.get("tag_name") not in played_tags]
            
            # Combine to get what the played move neglected
            neglected_tags = best_used_available_tags + best_created_neglected[:2]  # Limit to avoid too much info
            
            # Get natural descriptions
            from tool_executor import translate_tag_to_natural_english
            # Use tags that appeared AFTER best move to describe what it accomplished
            unique_best_tag_descriptions = [translate_tag_to_natural_english(t.get("tag_name", "")) 
                                           for t in best_created_tags[:3]]
            unique_best_tag_descriptions = [d for d in unique_best_tag_descriptions if d and d != "Unknown Pattern"]
            
            neglected_tag_descriptions = [translate_tag_to_natural_english(t.get("tag_name", "")) 
                                         for t in neglected_tags[:2]]
            neglected_tag_descriptions = [d for d in neglected_tag_descriptions if d and d != "Unknown Pattern"]
            
            print(f"✅ Move analysis complete (not best, 5 AF calls, CP loss: {cp_loss})")
    
        # Confidence (played vs best)
        try:
            print(f"🔍 Computing confidence for best move: {best_move_san}")
            conf_best = await compute_move_confidence(engine, fen, best_move_san, target_conf=80, branch=False)
            print(f"✅ Best move confidence: {len(conf_best.get('nodes', []))} nodes, line_conf={conf_best.get('line_confidence')}")
            print(f"🔍 Computing confidence for played move: {move_san}")
            conf_played = await compute_move_confidence(engine, fen, move_san, target_conf=80, branch=False)
            print(f"✅ Played move confidence: {len(conf_played.get('nodes', []))} nodes, line_conf={conf_played.get('line_confidence')}")
        except Exception as ce:
            import traceback
            print(f"⚠️ Confidence computation failed (not-best case): {ce}")
            print(traceback.format_exc())
            conf_best = conf_played = neutral_confidence()

        return {
                "fen_before": fen,
                "move_played": move_san,
                "move_san": move_san,
                "best_move": best_move_san,
                "best_move_san": best_move_san,
                "side_to_move": side_to_move,
                "is_best_move": False,
                "is_theory": is_theory_after,
                "opening_name": opening_name_after,
                "move_category": move_category,
                "cp_loss": cp_loss,
                "second_best_gap_cp": second_best_gap_cp,
                "eval_before_cp": best_eval,
                "eval_after_cp": played_eval,
                "eval_after_best": best_move_eval,
                "eval_pv_played": pv_played_eval_cp,
                "eval_pv_best": pv_best_eval_cp,
                "case": "not_best_move",
                "analysis": {
                    "af_starting": af_starting,
                    "af_best": af_best,
                    "af_pv_best": af_pv_best,
                    "af_played": af_played,
                    "af_pv_played": af_pv_played
                },
                "played_move_description": played_move_description,
                "unique_best_tag_descriptions": unique_best_tag_descriptions,
                "neglected_tag_descriptions": neglected_tag_descriptions,
                "played_move_threat_category": played_move_threat_type,
                "played_move_threat_description": played_move_threat_description,
                "best_move_threat_category": best_move_threat_type,
                "best_move_threat_description": best_move_threat_description,
                "confidence": {"played_move": conf_played, "best_move": conf_best}
        }
        
        # DEBUG: Log confidence data being returned
        print("\n" + "="*80)
        print("🌐 API ENDPOINT: /analyze_move RETURNING (not_best_move case)")
        print("="*80)
        print(f"Played move confidence nodes: {len(conf_played.get('nodes', []))}")
        print(f"Best move confidence nodes: {len(conf_best.get('nodes', []))}")
        if conf_played.get('nodes'):
            print(f"Played move first node: {conf_played['nodes'][0].get('id')}")
        if conf_best.get('nodes'):
            print(f"Best move first node: {conf_best['nodes'][0].get('id')}")
        print("="*80 + "\n")
        
    except Exception as e:
        import traceback
        error_detail = f"Move analysis error: {str(e)}\n{traceback.format_exc()}"
        print(error_detail)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


def calculate_phase(board: chess.Board, piece_count: int, queens: int, is_theory: bool, ply: int) -> str:
    """
    Determine game phase using criteria-based system.
    
    Opening → Middlegame: 3+ criteria
    Middlegame → Endgame: 2-3 criteria
    """
    # Opening→Middlegame criteria
    o_to_m = 0
    
    # 1. Both castled
    white_king = board.king(chess.WHITE)
    black_king = board.king(chess.BLACK)
    if white_king in [chess.G1, chess.C1] and black_king in [chess.G8, chess.C8]:
        o_to_m += 1
    
    # 2. Development (simplified check: few minors on start squares)
    start_squares = [chess.B1, chess.C1, chess.F1, chess.G1, chess.B8, chess.C8, chess.F8, chess.G8]
    minors_home = sum(1 for sq in start_squares if board.piece_at(sq) and board.piece_at(sq).piece_type in [chess.KNIGHT, chess.BISHOP])
    if minors_home <= 2:
        o_to_m += 1
    
    # 3. Out of theory and ply > 16
    if not is_theory and ply > 16:
        o_to_m += 1
    
    # Middlegame→Endgame criteria
    m_to_e = 0
    
    # 1. Queens off
    if queens == 0:
        m_to_e += 1
    
    # 2. Low material (≤12 pieces)
    if piece_count <= 12:
        m_to_e += 1
    
    # Determine phase
    if o_to_m >= 3:
        return "middlegame" if m_to_e < 2 else "endgame"
    else:
        return "opening"


async def _review_game_internal(
    pgn_string: str,
    side_focus: str = "both",
    include_timestamps: bool = True,
    depth: int = 14,  # Lowered for speed - deep analysis done on-demand via raw data
    engine_instance = None,
    status_callback = None  # Optional callback for progress updates
) -> Dict:
    """
    Internal function for game review logic (called by endpoint and aggregator).
    Comprehensive game review with theme-based analysis per move.
    Returns move-by-move analysis with full position themes, key points, and statistics.
    """
    # Use provided engine or fall back to global
    eng = engine_instance if engine_instance is not None else engine
    if not eng:
        print(f"⚠️  _review_game_internal: Stockfish engine not available")
        return {"error": "Stockfish engine not available", "ply_records": []}
    
    try:
        # Clean PGN
        import re
        
        print(f"🎮 Starting game review (side_focus={side_focus}, depth={depth})")
        print(f"   PGN length: {len(pgn_string)} chars")
        
        # PGN needs newlines preserved - don't join everything into one line!
        # Just use the PGN as-is
        cleaned_pgn = pgn_string
        
        # Parse PGN
        pgn_io = chess.pgn.read_game(StringIO(cleaned_pgn))
        if not pgn_io:
            print(f"   ⚠️ Failed to parse PGN")
            return {"error": "Invalid PGN", "ply_records": []}
        
        # Extract timestamps if present
        timestamps = {}
        if include_timestamps:
            node = pgn_io
            ply = 0
            while node.variations:
                node = node.variation(0)
                ply += 1
                if node.comment:
                    # Extract [%clk 0:05:23] or [%clk 0:05:23.5] format (handles decimals)
                    clk_match = re.search(r'\[%clk (\d+):(\d+):(\d+(?:\.\d+)?)\]', node.comment)
                    if clk_match:
                        h, m, s_str = clk_match.groups()
                        h, m = int(h), int(m)
                        s = float(s_str)  # Handle decimal seconds
                        timestamps[ply] = h * 3600 + m * 60 + s
        
        print(f"   Extracted {len(timestamps)} timestamps from PGN")
        if len(timestamps) > 0:
            first_few = list(timestamps.items())[:3]
            print(f"   First timestamps: {first_few}")
        else:
            print(f"   ⚠️ WARNING: No timestamps extracted (time management will be 0)")
        
        # Initialize game state
        board = chess.Board()
        ply_records = []
        last_phase = "opening"
        phase_hysteresis_counter = 0
        opening_name_final = ""
        eco_final = ""
        left_theory_ply = None
        advantage_history = []
        
        # Count moves first for debugging
        move_count = sum(1 for _ in pgn_io.mainline_moves())
        
        # Reset to start (mainline_moves() consumes the iterator)
        pgn_io = chess.pgn.read_game(StringIO(cleaned_pgn))
        
        # ====== PARALLEL ENGINE ANALYSIS (if pool available) ======
        engine_analysis_cache = {}  # fen_before -> {info_before, info_after}
        
        # Debug: check pool availability
        print(f"   🔍 Pool check: instance={engine_pool_instance is not None}, initialized={engine_pool_instance._initialized if engine_pool_instance else 'N/A'}")
        
        use_parallel = engine_pool_instance is not None and engine_pool_instance._initialized
        
        if use_parallel:
            print(f"⚡ Analyzing {move_count} moves with {engine_pool_instance.pool_size} engines...")
            
            # Collect all positions
            positions_for_pool = []
            temp_board = chess.Board()
            for move in pgn_io.mainline_moves():
                positions_for_pool.append((temp_board.fen(), move))
                temp_board.push(move)
            
            # Progress callback - unified "Analyzing moves n/N" format
            async def parallel_progress(move_done: int, move_total: int, message: str = "Analyzing moves..."):
                if status_callback:
                    # Calculate progress: 10% to 95% (theory check is 0-5%, analysis is 5-95%)
                    if "theory" in message.lower():
                        # Theory check phase: 0% to 5%
                        progress = 0.05 * (move_done / max(1, move_total))
                    else:
                        # Analysis phase: 5% to 95%
                        progress = 0.05 + (0.90 * (move_done / max(1, move_total)))
                    
                    # Format message
                    if move_done > 0 and move_total > 0:
                        status_msg = f"{message} {move_done}/{move_total}"
                    else:
                        status_msg = message
                    
                    await status_callback("executing", status_msg, progress, replace=True)
                    await asyncio.sleep(0)
            
            # Run parallel analysis - returns COMPLETE ply records
            try:
                pool_results = await engine_pool_instance.analyze_game_parallel(
                    positions_for_pool,
                    depth=depth,
                    multipv=2,
                    timestamps=timestamps,
                    progress_callback=parallel_progress
                )
                
                # Use complete ply records directly - just add phase detection
                for result in pool_results:
                    if result.get("success"):
                        ply = result["ply"]
                        fen_after = result["fen_after"]
                        theory_check = result.get("theory_check", {})
                        is_theory = theory_check.get("isTheory", False)
                        opening_name = theory_check.get("opening", "")
                        
                        # Track opening name
                        if is_theory and opening_name:
                            if opening_name == opening_name_final or not opening_name_final:
                                opening_name_final = opening_name
                            eco = theory_check.get('eco', '')
                            if eco:
                                eco_final = eco
                        
                        if not is_theory and left_theory_ply is None and ply > 1:
                            left_theory_ply = ply
                        
                        # Phase detection with hysteresis
                        board_after = chess.Board(fen_after)
                        piece_count = len(board_after.piece_map())
                        queens = len([p for p in board_after.piece_map().values() if p.piece_type == chess.QUEEN])
                        
                        new_phase = calculate_phase(board_after, piece_count, queens, is_theory, ply)
                        
                        if new_phase != last_phase:
                            phase_hysteresis_counter += 1
                            if phase_hysteresis_counter >= 2:
                                last_phase = new_phase
                                phase_hysteresis_counter = 0
                        else:
                            phase_hysteresis_counter = 0
                        
                        if ply >= 24 and last_phase == "opening":
                            last_phase = "middlegame"
                        if ply >= 72 and last_phase == "middlegame":
                            last_phase = "endgame"
                        
                        # Add phase to record
                        result["phase"] = last_phase
                        
                        # Track advantage history
                        played_eval = result["engine"]["played_eval_after_cp"]
                        advantage_history.append(played_eval)
                        
                        ply_records.append(result)
                
                print(f"   ✅ Analysis complete: {len(ply_records)}/{move_count} moves")
                
            except Exception as e:
                import traceback
                print(f"   ⚠️ Parallel analysis failed, falling back to sequential: {e}")
                traceback.print_exc()
                use_parallel = False
                ply_records = []
        
        # Sequential fallback - only if parallel failed or unavailable
        if not use_parallel:
            print(f"⏳ Analyzing {move_count} moves sequentially (depth={depth}, multipv=2)...")

            # Reset for sequential processing
            pgn_io = chess.pgn.read_game(StringIO(cleaned_pgn))
            ply_records = []
            advantage_history = []
            board = chess.Board()

            def _score_to_white_cp(score_obj) -> int:
                if not score_obj:
                    return 0
                try:
                    pov = score_obj.pov(chess.WHITE)
                    if pov.is_mate():
                        m = pov.mate()
                        return 10000 if (m is not None and m > 0) else -10000
                    return int(pov.score(mate_score=10000) or 0)
                except Exception:
                    return 0

            for move in pgn_io.mainline_moves():
                ply = len(ply_records) + 1

                if status_callback:
                    progress = ply / move_count if move_count > 0 else 0
                    await status_callback(
                        "executing",
                        f"Analyzing move {ply}/{move_count}...",
                        progress,
                        replace=True,
                    )

                fen_before = board.fen()
                side_moved = "white" if board.turn == chess.WHITE else "black"
                move_san = board.san(move)
                move_uci = move.uci()

                info_before = await engine_queue.enqueue(
                    engine_queue.engine.analyse,
                    board,
                    chess.engine.Limit(depth=depth),
                    multipv=2,
                )

                best_move_uci = ""
                best_move_san = ""
                best_eval_cp = 0
                second_best_gap_cp = 0
                try:
                    best_move_uci = str(info_before[0]["pv"][0]) if info_before and info_before[0].get("pv") else ""
                    best_move_san = board.san(chess.Move.from_uci(best_move_uci)) if best_move_uci else ""
                    best_eval_cp = _score_to_white_cp(info_before[0].get("score"))
                    if len(info_before) >= 2:
                        second_best_gap_cp = abs(best_eval_cp - _score_to_white_cp(info_before[1].get("score")))
                except Exception:
                    pass

                board.push(move)
                fen_after = board.fen()

                info_after = await engine_queue.enqueue(
                    engine_queue.engine.analyse,
                    board,
                    chess.engine.Limit(depth=depth),
                )
                played_eval_cp = _score_to_white_cp(info_after.get("score"))

                cp_loss = max(0, abs(best_eval_cp - played_eval_cp))
                accuracy_pct = 100 / (1 + (cp_loss / 50) ** 0.7)

                time_spent_s = None
                if isinstance(timestamps, dict) and ply in timestamps and (ply - 1) in timestamps:
                    try:
                        time_spent_s = float(timestamps[ply - 1]) - float(timestamps[ply])
                    except Exception:
                        time_spent_s = None

                # Opening DB check (best effort)
                is_theory = False
                opening_name = None
                is_theory_move = False
                try:
                    theory_check = check_lichess_masters(fen_before)
                    is_theory = bool(theory_check.get("isTheory", False))
                    opening_name = theory_check.get("opening") if is_theory else None
                    is_theory_move = is_theory and ply <= 20
                except Exception:
                    pass

                # Phase detection (best effort)
                try:
                    piece_count = len(board.piece_map())
                    queens = len([p for p in board.piece_map().values() if p.piece_type == chess.QUEEN])
                    new_phase = calculate_phase(board, piece_count, queens, is_theory, ply)
                    if isinstance(new_phase, str) and new_phase:
                        last_phase = new_phase
                except Exception:
                    pass

                # Category bucket
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

                ply_record = {
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
                        "second_best_gap_cp": second_best_gap_cp,
                    },
                    "cp_loss": cp_loss,
                    "accuracy_pct": accuracy_pct,
                    "category": category,
                    "time_spent_s": time_spent_s,
                    "raw_before": {},
                    "raw_after": {},
                    "analyse": {},
                    "phase": last_phase,
                    "is_theory": is_theory_move,
                    "opening_name": opening_name,
                    "key_point_labels": [],
                    "notes": "",
                }

                ply_records.append(ply_record)
                advantage_history.append(played_eval_cp)
        
            # Emit completion message
        if status_callback:
                await status_callback("executing", f"Analyzed {len(ply_records)} moves", 0.95, replace=True)
        
        print(f"✅ Analyzed {len(ply_records)} plies")
        
        # Detect key points and assign labels using enhanced detection
        if status_callback:
            await status_callback("executing", "Detecting key moments...", 0.96, replace=True)
            await asyncio.sleep(0)  # Yield to event loop
        print("🔍 Detecting key points (enhanced)...")
        
        # Use enhanced key moment detection for BOTH sides
        from key_moment_selector import detect_all_key_moments
        all_key_moments = detect_all_key_moments(ply_records, player_color=side_focus if side_focus != "both" else None)
        
        # Also update the legacy key_point_labels on each record for backwards compatibility
        key_moments_by_ply = {km["ply"]: km for km in all_key_moments}
        key_points = []
        
        for i, record in enumerate(ply_records):
            ply = record["ply"]
            
            # Check if this ply has a key moment
            km = key_moments_by_ply.get(ply)
            if km:
                record["key_point_labels"] = km.get("labels", [])
            else:
                record["key_point_labels"] = []
            
            # Apply side filtering for backwards compatibility
            if side_focus == "white":
                if record["side_moved"] == "black" and "blunder" not in record["key_point_labels"]:
                    record["key_point_labels"] = []
            elif side_focus == "black":
                if record["side_moved"] == "white" and "blunder" not in record["key_point_labels"]:
                    record["key_point_labels"] = []
            
            if record["key_point_labels"]:
                key_points.append(record)
            
            # Progress update every 10 moves or at the end
            if status_callback and (i % 10 == 0 or i == len(ply_records) - 1):
                progress = 0.96 + (i / len(ply_records) * 0.02)  # 96% to 98%
                await status_callback("executing", f"Scanning for key moments ({i+1}/{len(ply_records)})...", progress, replace=True)
                await asyncio.sleep(0)  # Yield to event loop
        
        # Calculate aggregated statistics
        if status_callback:
            await status_callback("executing", "Calculating statistics...", 0.98, replace=True)
            await asyncio.sleep(0)  # Yield to event loop
        print("📊 Calculating statistics...")
        def calculate_stats(records, side, total_moves=None):
            """
            Calculate statistics for one side with context-aware handling.
            
            Context-aware features:
            - Phases with 0 moves get accuracy=None, not 0%
            - Includes contextual notes for missing phases
            """
            side_records = [r for r in records if r["side_moved"] == side]
            
            if not side_records:
                return {
                    "overall_accuracy": None,
                    "avg_cp_loss": None,
                    "counts": {},
                    "by_phase": {},
                    "by_piece": {},
                    "total_moves": 0,
                    "note": f"No {side} moves in this game"
                }
            
            overall_acc = sum(r["accuracy_pct"] for r in side_records) / len(side_records)
            avg_cp = sum(r["cp_loss"] for r in side_records) / len(side_records)
            
            counts = {
                "critical_best": len([r for r in side_records if r["category"] == "critical_best"]),
                "excellent": len([r for r in side_records if r["category"] == "excellent"]),
                "good": len([r for r in side_records if r["category"] == "good"]),
                "inaccuracy": len([r for r in side_records if r["category"] == "inaccuracy"]),
                "mistake": len([r for r in side_records if r["category"] == "mistake"]),
                "blunder": len([r for r in side_records if r["category"] == "blunder"])
            }
            
            # By phase - CONTEXT-AWARE: Don't report 0% for phases with no moves
            by_phase = {}
            for phase in ["opening", "middlegame", "endgame"]:
                phase_records = [r for r in side_records if r["phase"] == phase]
                if phase_records:
                    by_phase[phase] = {
                        "accuracy": sum(r["accuracy_pct"] for r in phase_records) / len(phase_records),
                        "count": len(phase_records),
                        "avg_cp_loss": sum(r["cp_loss"] for r in phase_records) / len(phase_records)
                    }
                else:
                    # CONTEXT-AWARE: Use None instead of 0 for phases that didn't occur
                    by_phase[phase] = {
                        "accuracy": None,  # NOT 0! No moves = no accuracy to report
                        "count": 0,
                        "avg_cp_loss": None,
                        "note": f"No {phase} moves played"
                    }
            
            return {
                "overall_accuracy": overall_acc,
                "avg_cp_loss": avg_cp,
                "counts": counts,
                "by_phase": by_phase,
                "by_piece": {},
                "total_moves": len(side_records)
            }
        
        white_stats = calculate_stats(ply_records, "white")
        if status_callback:
            await status_callback("executing", "Computing performance metrics...", 0.99, replace=True)
            await asyncio.sleep(0)  # Yield to event loop
        
        black_stats = calculate_stats(ply_records, "black")
        
        # Phase boundaries
        if status_callback:
            await status_callback("executing", "Finalizing review...", 0.995, replace=True)
            await asyncio.sleep(0)  # Yield to event loop
        phase_transitions = []
        for i in range(1, len(ply_records)):
            if ply_records[i]["phase"] != ply_records[i-1]["phase"]:
                phase_transitions.append({
                    "ply": ply_records[i]["ply"],
                    "from_phase": ply_records[i-1]["phase"],
                    "to_phase": ply_records[i]["phase"]
                })
        
        print(f"✅ Review complete: {len(key_points)} key points, {len(phase_transitions)} phase transitions")
        
        # Add general game info for training system
        endgame_plies = [r for r in ply_records if r["phase"] == "endgame"]
        has_endgame = len(endgame_plies) > 0
        
        # Classify endgame type
        endgame_type = None
        if has_endgame and endgame_plies:
            last_endgame = endgame_plies[-1]
            fen = last_endgame.get("fen_after", "")
            if "Q" in fen or "q" in fen:
                endgame_type = "queen_endgame"
            elif "R" in fen or "r" in fen:
                endgame_type = "rook_endgame"
            elif "B" in fen or "b" in fen or "N" in fen or "n" in fen:
                endgame_type = "minor_piece_endgame"
            else:
                endgame_type = "pawn_endgame"
        
        # Classify game character
        evals = [r.get("engine", {}).get("played_eval_after_cp", 0) for r in ply_records]
        eval_changes = [abs(evals[i] - evals[i-1]) for i in range(1, len(evals))] if len(evals) > 1 else []
        avg_change = sum(eval_changes) / len(eval_changes) if eval_changes else 0
        
        if avg_change > 100:
            game_character = "tactical_battle"
        elif avg_change > 50:
            game_character = "dynamic"
        elif max(abs(e) for e in evals) < 100 if evals else False:
            game_character = "balanced"
        else:
            game_character = "positional"
        
        game_metadata = {
            "opening": opening_name_final,
            "eco": eco_final,
            "total_moves": len(ply_records) // 2,  # Full moves
            "game_length_plies": len(ply_records),
            "phases": {
                "opening_plies": len([r for r in ply_records if r["phase"] == "opening"]),
                "middlegame_plies": len([r for r in ply_records if r["phase"] == "middlegame"]),
                "endgame_plies": len(endgame_plies)
            },
            "has_endgame": has_endgame,
            "endgame_type": endgame_type,
            "game_character": game_character,
            "timestamps_available": len(timestamps) > 0
        }
        
        # Mark all critical moves with tags and notes
        for record in ply_records:
            category = record["category"]
            if category in ["inaccuracy", "mistake", "blunder"]:
                # Add error note
                symbol = "!?" if category == "inaccuracy" else "?" if category == "mistake" else "??"
                record["error_note"] = f"In this position you played {record['san']}{symbol} (cp_loss: {record['cp_loss']:.0f})"
                record["is_critical"] = True
            elif category == "critical_best":
                record["is_critical"] = True
                record["critical_note"] = f"Critical decision: {record['san']} was the only good move"
        
        return {
            "ply_records": ply_records,
            "opening": {
                "name_final": opening_name_final,
                "eco_final": eco_final,
                "left_theory_ply": left_theory_ply
            },
            "phases": phase_transitions,
            "side_focus": side_focus,
            "stats": {
                "white": white_stats,
                "black": black_stats
            },
            "key_points": key_points,
            "all_key_moments": all_key_moments,  # NEW: Enhanced key moments for both sides
            "game_metadata": game_metadata
        }
        
    except Exception as e:
        import traceback
        error_detail = f"Review error: {str(e)}\n{traceback.format_exc()}"
        print(error_detail)
        return {"error": f"Review error: {str(e)}", "ply_records": []}


async def _save_error_positions(
    ply_records: List[Dict],
    game_id: str,
    user_id: str,
    supabase_client,
    focus_color: str = "white"
) -> int:
    """
    Extract and save blunders/mistakes as training positions.
    Deduplicates by FEN + side_to_move.
    Returns count of positions saved.
    """
    if not supabase_client:
        return 0
    
    positions_to_save = []
    
    for record in ply_records:
        category = record.get("category", "")
        cp_loss = record.get("cp_loss", 0)
        side_moved = record.get("side_moved", "")
        
        # Only save blunders (200+) and mistakes (100+)
        if category not in ["blunder", "mistake"] or cp_loss < 100:
            continue
        
        # Determine error_side based on focus_color
        error_side = "player" if side_moved == focus_color else "opponent"
        
        # Extract tags
        raw_before = record.get("raw_before", {})
        raw_after = record.get("raw_after", {})
        tags_before = raw_before.get("tags", [])
        tags_after_played = raw_after.get("tags", [])
        
        # Convert tags to string list
        def extract_tag_names(tags):
            names = []
            for tag in tags:
                if isinstance(tag, str):
                    names.append(tag)
                elif isinstance(tag, dict):
                    name = tag.get("name", tag.get("tag", tag.get("tag_name", "")))
                    if name:
                        names.append(name)
            return names
        
        tags_before_list = extract_tag_names(tags_before)
        tags_after_played_list = extract_tag_names(tags_after_played)
        
        # Extract best move tags if available
        best_move_tags = record.get("best_move_tags", [])
        tags_after_best_list = extract_tag_names(best_move_tags)
        
        # Compute tag transitions
        tags_start_set = set(tags_before_list)
        tags_after_played_set = set(tags_after_played_list)
        tags_after_best_set = set(tags_after_best_list)
        
        tags_gained = list(tags_after_played_set - tags_start_set)
        tags_lost = list(tags_start_set - tags_after_played_set)
        
        # Extract piece information
        fen_before = record.get("fen_before")
        move_uci = record.get("uci")
        best_move_san = record.get("engine", {}).get("best_move_san")
        
        # Helper to extract piece name from move
        def piece_name_from_move(fen: str, uci: str) -> str:
            if not fen or not uci or len(uci) < 4:
                return None
            try:
                from chess import Board
                board = Board(fen)
                from_square = uci[:2]
                piece = board.piece_at(getattr(__import__('chess'), from_square.upper()))
                if piece:
                    return piece.symbol().upper() if piece.color else piece.symbol().lower()
            except:
                pass
            return None
        
        def piece_name_from_san(fen: str, san: str) -> str:
            if not fen or not san:
                return None
            try:
                from chess import Board
                board = Board(fen)
                move = board.parse_san(san)
                piece = board.piece_at(move.from_square)
                if piece:
                    return piece.symbol().upper() if piece.color else piece.symbol().lower()
            except:
                pass
            return None
        
        piece_blundered = piece_name_from_move(fen_before, move_uci) if fen_before and move_uci else None
        piece_best_move = piece_name_from_san(fen_before, best_move_san) if fen_before and best_move_san else None
        
        # Extract time data
        time_spent_s = record.get("time_spent_s")
        
        # Determine error category
        error_category = category  # "mistake" or "blunder"
        
        position_data = {
            "fen": fen_before,
            "side_to_move": side_moved,
            "from_game_id": game_id,  # Primary source game
            "source_ply": record.get("ply"),
            "move_san": record.get("san"),
            "move_uci": move_uci,
            "best_move_san": best_move_san,
            "best_move_uci": record.get("engine", {}).get("best_move_uci"),
            "eval_cp": record.get("engine", {}).get("eval_before_cp"),
            "cp_loss": cp_loss,
            "phase": record.get("phase"),
            "opening_name": record.get("opening_name"),  # Add opening_name if available
            "error_category": error_category,
            "is_critical": cp_loss >= 200,
            "error_note": f"{category.capitalize()}: {record.get('san')} (cp_loss: {cp_loss})",
            "source_game_ids": [game_id],  # Array for tracking multiple sources
            # Tag transition metadata
            "tags_start": tags_before_list,
            "tags_after_played": tags_after_played_list,
            "tags_after_best": tags_after_best_list,
            "tags_gained": tags_gained,
            "tags_lost": tags_lost,
            # Piece information
            "piece_blundered": piece_blundered,
            "piece_best_move": piece_best_move,
            # Time data
            "time_spent_s": time_spent_s,
        }
        positions_to_save.append(position_data)
    
    # Batch upsert with deduplication
    if positions_to_save:
        saved_count = supabase_client.batch_upsert_positions(user_id, positions_to_save, game_id)
        return saved_count
    
    return 0


@app.post("/review_game")
async def review_game(
    pgn_string: str = Query(..., description="PGN string of the game"),
    side_focus: str = Query("both", pattern="^(white|black|both)$", description="Which side to focus analysis on"),
    include_timestamps: bool = Query(True, description="Extract timestamps from PGN if available"),
    depth: int = Query(18, ge=10, le=25, description="Stockfish analysis depth")
):
    """
    Comprehensive game review with theme-based analysis per move.
    Returns move-by-move analysis with full position themes, key points, and statistics.
    """
    global engine
    result = await _review_game_internal(pgn_string, side_focus, include_timestamps, depth, engine)
    
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    
    return result


async def analyze_with_depth(board: chess.Board, depth: int = 18, multipv: int = 1):
    """Helper to analyze position at specific depth."""
    if not engine:
        return {"eval_cp": 0, "candidate_moves": []}
    
    try:
        info = await engine_queue.enqueue(
            engine_queue.engine.analyse,
            board,
            chess.engine.Limit(depth=depth),
            multipv=multipv
        )
        
        # Extract evaluation
        score = info[0]["score"].white()
        eval_cp = score.score(mate_score=10000) if score.is_mate() == False else (10000 if score.mate() > 0 else -10000)
        
        # Extract candidate moves
        candidates = []
        for i, pv_info in enumerate(info[:multipv]):
            if "pv" in pv_info and pv_info["pv"]:
                move = pv_info["pv"][0]
                pv_score = pv_info["score"].white()
                pv_cp = pv_score.score(mate_score=10000) if pv_score.is_mate() == False else (10000 if pv_score.mate() > 0 else -10000)
                
                candidates.append({
                    "move": board.san(move),
                    "uci": move.uci(),
                    "eval_cp": pv_cp
                })
        
        return {
            "eval_cp": eval_cp,
            "candidate_moves": candidates
        }
    except Exception as e:
        return {"eval_cp": 0, "candidate_moves": []}


def detect_game_tags(move_analyses: list) -> list:
    """
    Detect game characteristic tags based on evaluation trajectory.
    Returns a list of detected tags with descriptions.
    """
    import math
    
    tags = []
    
    if len(move_analyses) < 3:
        return tags
    
    # Extract evaluation series
    evals = [m["evalAfter"] for m in move_analyses]
    move_numbers = [m["moveNumber"] for m in move_analyses]
    total_moves = len(move_analyses)
                
def detect_game_tags(move_analyses: list) -> list:
    """
    Detect game characteristic tags based on evaluation trajectory.
    Returns a list of detected tags with descriptions.
    """
    import math
    
    tags = []
    
    if len(move_analyses) < 3:
        return tags
    
    # Extract evaluation series
    evals = [m["evalAfter"] for m in move_analyses]
    move_numbers = [m["moveNumber"] for m in move_analyses]
    total_moves = len(move_analyses)
    
    # Calculate eval deltas (change from previous move)
    deltas = [evals[i] - evals[i-1] for i in range(1, len(evals))]
    
    # Helper: 3-move median smoothing
    def median_smooth(series):
        smoothed = []
        for i in range(len(series)):
            window = series[max(0, i-1):min(len(series), i+2)]
            smoothed.append(sorted(window)[len(window)//2])
        return smoothed
    
    smoothed_evals = median_smooth(evals)
    
    # Helper: count lead flips
    def count_lead_flips(series):
        flips = 0
        for i in range(1, len(series)):
            if (series[i-1] > 0 and series[i] < 0) or (series[i-1] < 0 and series[i] > 0):
                flips += 1
        return flips
    
    # Helper: standard deviation
    def std_dev(series):
        if len(series) < 2:
            return 0
        mean = sum(series) / len(series)
        variance = sum((x - mean) ** 2 for x in series) / len(series)
        return math.sqrt(variance)
    
    # 1. Stable Equal — eval stays within ±50 cp for ≥70% of moves
    within_50 = sum(1 for e in evals if abs(e) <= 50)
    if within_50 / len(evals) >= 0.7:
        tags.append({
            "name": "Stable Equal",
            "description": f"{within_50}/{len(evals)} moves stayed within ±50cp"
        })
    
    # 2. Early Conversion — ≥+300 cp by move ≤15 and never drops below +200 cp thereafter
    early_winning = False
    conversion_move = None
    for i, m in enumerate(move_analyses):
        if m["moveNumber"] <= 15 and abs(m["evalAfter"]) >= 300:
            early_winning = True
            conversion_move = m["moveNumber"]
            # Check if it stays above 200cp
            subsequent_evals = [move_analyses[j]["evalAfter"] for j in range(i, len(move_analyses))]
            if m["evalAfter"] > 0:  # White winning
                if all(e >= 200 for e in subsequent_evals):
                    tags.append({
                        "name": "Early Conversion",
                        "description": f"≥+300cp by move {conversion_move}, maintained ≥+200cp"
                    })
            else:  # Black winning
                if all(e <= -200 for e in subsequent_evals):
                    tags.append({
                        "name": "Early Conversion",
                        "description": f"≤-300cp by move {conversion_move}, maintained ≤-200cp"
                    })
            break
    
    # 3. Gradual Accumulation — advantage grows with low volatility
    if len(deltas) > 0:
        delta_std = std_dev(deltas)
        max_single_swing = max(abs(d) for d in deltas) if deltas else 0
        
        # Check if advantage grows (final eval significantly different from start)
        eval_growth = abs(evals[-1] - evals[0])
        
        if eval_growth >= 150 and delta_std <= 80 and max_single_swing < 300:
            tags.append({
                "name": "Gradual Accumulation",
                "description": f"Advantage grew steadily (σ={delta_std:.0f}cp, max swing={max_single_swing:.0f}cp)"
            })
    
    # 4. Oscillating — lead flips ≥3 times (after smoothing)
    flips = count_lead_flips(smoothed_evals)
    if flips >= 3:
        tags.append({
            "name": "Oscillating",
            "description": f"Lead changed hands {flips} times"
        })
    
    # 5. High Volatility — ≥2 large swings (|Δeval| ≥300 cp) within any 6-move window
    for i in range(len(deltas) - 5):
        window = deltas[i:i+6]
        large_swings = sum(1 for d in window if abs(d) >= 300)
        if large_swings >= 2:
            tags.append({
                "name": "High Volatility",
                "description": f"≥2 swings of ≥300cp within 6 moves (around move {move_analyses[i+1]['moveNumber']})"
            })
            break
    
    # 6. Single-Point Reversal — one move changes eval by ≥500 cp and flips the lead
    for i, d in enumerate(deltas):
        if abs(d) >= 500:
            eval_before = evals[i]
            eval_after = evals[i+1]
            if (eval_before > 0 and eval_after < 0) or (eval_before < 0 and eval_after > 0):
                tags.append({
                    "name": "Single-Point Reversal",
                    "description": f"Move {move_analyses[i+1]['moveNumber']} ({move_analyses[i+1]['move']}) swung {abs(d):.0f}cp and flipped the game"
                })
                break
    
    # 7. Late Reversal — first decisive swing (|Δeval| ≥400 cp) occurs in final third
    final_third_start = int(len(deltas) * 2/3)
    early_decisive = any(abs(d) >= 400 for d in deltas[:final_third_start])
    late_decisive = any(abs(d) >= 400 for d in deltas[final_third_start:])
    
    if not early_decisive and late_decisive:
        for i in range(final_third_start, len(deltas)):
            if abs(deltas[i]) >= 400:
                tags.append({
                    "name": "Late Reversal",
                    "description": f"First decisive swing (≥400cp) at move {move_analyses[i+1]['moveNumber']}"
                })
                break
    
    # 8. Progressive Decline — cumulative small losses flip result without single swing ≥300 cp
    max_swing = max(abs(d) for d in deltas) if deltas else 0
    if max_swing < 300:
        # Check if result flipped (start vs end)
        if (evals[0] > 100 and evals[-1] < -100) or (evals[0] < -100 and evals[-1] > 100):
            # Count moves with 50-200cp losses
            medium_losses = sum(1 for d in deltas if 50 <= abs(d) <= 200)
            if medium_losses >= 3:
                tags.append({
                    "name": "Progressive Decline",
                    "description": f"{medium_losses} gradual losses (50-200cp each) flipped the result"
                })
    
    # 9. Tactical Instability — ≥25% of moves have |Δeval| ≥200 cp
    if len(deltas) > 0:
        large_jumps = sum(1 for d in deltas if abs(d) >= 200)
        if large_jumps / len(deltas) >= 0.25:
            tags.append({
                "name": "Tactical Instability",
                "description": f"{large_jumps}/{len(deltas)} moves had ≥200cp swings ({100*large_jumps/len(deltas):.0f}%)"
            })
    
    # 10. Controlled Clamp — once ahead (≥+150 cp), maintained
    for i, e in enumerate(evals):
        if abs(e) >= 150:
            # Found first time ahead by 150cp
            subsequent = evals[i:]
            if e > 0:  # White ahead
                if all(se >= 100 for se in subsequent):
                    post_std = std_dev(subsequent)
                    if post_std <= 120:
                        tags.append({
                            "name": "Controlled Clamp",
                            "description": f"After move {move_analyses[i]['moveNumber']}, maintained ≥+100cp (σ={post_std:.0f}cp)"
                        })
            else:  # Black ahead
                if all(se <= -100 for se in subsequent):
                    post_std = std_dev(subsequent)
                    if post_std <= 120:
                        tags.append({
                            "name": "Controlled Clamp",
                            "description": f"After move {move_analyses[i]['moveNumber']}, maintained ≤-100cp (σ={post_std:.0f}cp)"
                        })
            break
    
    # 11. Endgame Conversion — first time ≥+150 cp after move ≥40 and stays
    for i, m in enumerate(move_analyses):
        if m["moveNumber"] >= 40 and abs(m["evalAfter"]) >= 150:
            subsequent = [move_analyses[j]["evalAfter"] for j in range(i, len(move_analyses))]
            if m["evalAfter"] > 0:
                if all(e >= 150 for e in subsequent):
                    tags.append({
                        "name": "Endgame Conversion",
                        "description": f"Decisive advantage gained at move {m['moveNumber']} and held"
                    })
            else:
                if all(e <= -150 for e in subsequent):
                    tags.append({
                        "name": "Endgame Conversion",
                        "description": f"Decisive advantage gained at move {m['moveNumber']} and held"
                    })
            break
    
    # 12. Time-Pressure Degradation — accuracy drops near move 40/80
    # Check for CPL spikes near time controls
    for time_control in [40, 80]:
        cpl_spikes = 0
        for m in move_analyses:
            if abs(m["moveNumber"] - time_control) <= 3:
                if m["cpLoss"] >= 150:
                    cpl_spikes += 1
        
        if cpl_spikes >= 3:
            tags.append({
                "name": "Time-Pressure Degradation",
                "description": f"≥3 large mistakes (≥150cp loss) near move {time_control}"
            })
    
    # 13. Opening Collapse — ≤−300 cp before move 12
    for m in move_analyses:
        if m["moveNumber"] <= 12:
            if m["evalAfter"] <= -300 or m["evalAfter"] >= 300:
                # Check if never recovers
                subsequent = [move_analyses[j]["evalAfter"] for j in range(move_analyses.index(m), len(move_analyses))]
                if m["evalAfter"] <= -300:
                    if all(e <= -150 for e in subsequent):
                        tags.append({
                            "name": "Opening Collapse",
                            "description": f"≤-300cp by move {m['moveNumber']}, never recovered"
                        })
                else:
                    if all(e >= 150 for e in subsequent):
                        tags.append({
                            "name": "Opening Collapse",
                            "description": f"≥+300cp by move {m['moveNumber']}, opponent never recovered"
                        })
                break
    
    # 14. Queenless Middlegame — queens off by move ≤20
    # This requires board state, which we don't track in move_analyses
    # We can add this later if needed by checking the FEN for each move
    
    return tags


def check_lichess_masters(fen: str) -> dict:
    """Check if position exists in Lichess masters database.
    Returns theory status, opening name, and list of theory moves (in UCI format)."""
    try:
        url = f"https://explorer.lichess.ovh/masters?fen={urllib.parse.quote(fen)}"
        with urllib.request.urlopen(url, timeout=3) as response:
            data = json.loads(response.read())
            # If there are games in the database with this position, it's theory
            moves_list = data.get('moves', [])
            total_games = sum(move.get('white', 0) + move.get('draws', 0) + move.get('black', 0) 
                            for move in moves_list)
            # Extract move UCI strings from theory moves
            theory_moves_uci = [move.get('uci', '') for move in moves_list if move.get('uci')]
            return {
                'isTheory': total_games > 0,
                'totalGames': total_games,
                'opening': data.get('opening', {}).get('name', 'Unknown'),
                'theoryMoves': theory_moves_uci  # List of theory moves in UCI format
            }
    except:
        return {'isTheory': False, 'totalGames': 0, 'opening': None, 'theoryMoves': []}


class LLMRequest(BaseModel):
    messages: List[Dict[str, str]]
    model: str = "gpt-5-mini"
    temperature: float = 0.7
    use_tools: bool = True  # Enable function calling
    context: Optional[Dict[str, Any]] = None  # Board state, PGN, mode, etc.
    max_tool_iterations: int = 5  # Prevent infinite loops
    interpreter_model: Optional[str] = None  # Override interpreter model (for console command)


@app.post("/llm_chat")
async def llm_chat(request: LLMRequest):
    """
    Enhanced chat endpoint with OpenAI function calling support.
    LLM can call tools to analyze positions, review games, generate training, query database, etc.
    """
    if not openai_client:
        raise HTTPException(
            status_code=503,
            detail="OpenAI client not initialized. Please check OPENAI_API_KEY environment variable."
        )
    
    try:
        print(f"\n💬 LLM CHAT REQUEST (use_tools={request.use_tools})")
        
        # Build context for tool selection
        context = request.context or {}
        context["authenticated"] = False  # TODO: Get from auth when integrated
        
        # Log context details
        print(f"   📍 Context received:")
        print(f"      FEN: {context.get('fen', 'none')}")
        print(f"      Board state: {context.get('board_state', 'none')}")
        print(f"      Mode: {context.get('mode', 'none')}")
        print(f"      Has PGN: {context.get('has_pgn', False)}")
        print(f"      PGN length: {len(context.get('pgn', ''))}")
        print(f"      PGN preview: {context.get('pgn', '')[:100]}")
        
        # Log last user message
        user_messages = [m for m in request.messages if m.get('role') == 'user']
        last_user_message = ""
        if user_messages:
            last_user_message = user_messages[-1].get('content', '')
            print(f"      Last user message: {last_user_message[:100]}")
        
        # ============================================================
        # INTERPRETER: Analyze request and create orchestration plan
        # ============================================================
        orchestration_plan = None
        frontend_commands = []
        pre_computed_analysis = {}
        status_messages = []  # Track what the system is doing
        
        if request_interpreter and last_user_message:
            print(f"\n   🎯 Running request interpreter...")
            try:
                import time as _time
                
                # Status callback to collect status updates
                def status_callback(phase: str, message: str, **kwargs):
                    status_entry = {
                        "phase": phase,
                        "message": message,
                        "timestamp": kwargs.get("timestamp", _time.time())
                    }
                    if kwargs.get("tool"):
                        status_entry["tool"] = kwargs["tool"]
                    if kwargs.get("progress") is not None:
                        status_entry["progress"] = kwargs["progress"]
                    status_messages.append(status_entry)
                    print(f"         [{phase}] {message}")
                
                orchestration_plan = await request_interpreter.interpret(
                    message=last_user_message,
                    context=context,
                    conversation_history=request.messages,
                    status_callback=status_callback
                )
                print(f"      Mode: {orchestration_plan.mode.value} (confidence: {orchestration_plan.mode_confidence:.2f})")
                print(f"      Intent: {orchestration_plan.user_intent_summary}")
                print(f"      Tools planned: {[t.name for t in orchestration_plan.tool_sequence]}")
                print(f"      Skip tools: {orchestration_plan.skip_tools}")
                
                # Extract frontend commands for response
                frontend_commands = [cmd.to_dict() for cmd in orchestration_plan.frontend_commands]
                
                # EXTEND (not overwrite!) with status messages from plan
                status_messages.extend([s.to_dict() for s in orchestration_plan.status_messages])
                
                # Log status messages (handle both old 'action'/'description' and new 'phase'/'message' formats)
                if status_messages:
                    print(f"      Status updates: ({len(status_messages)} messages)")
                    try:
                        for s in status_messages:
                            phase = s.get('phase', s.get('action', 'unknown'))
                            msg = s.get('message', s.get('description', ''))
                            print(f"         [{phase}] {msg}")
                    except Exception as log_err:
                        print(f"      ⚠️ Error logging status messages: {log_err}")
                
                # Pre-execute analysis requests if any
                if orchestration_plan.analysis_requests and engine_queue:
                    print(f"      Pre-executing {len(orchestration_plan.analysis_requests)} analysis requests...")
                    
                    # Status callback to track progress
                    def status_cb(action: str, description: str):
                        status_messages.append({
                            "phase": action,  # Use 'phase' for consistency
                            "message": description,
                            "timestamp": _time.time()
                        })
                        print(f"         [{action}] {description}")
                    
                    pre_computed_analysis = await execute_analysis_requests(
                        orchestration_plan.analysis_requests,
                        engine_queue,
                        status_callback=status_cb
                    )
                    # Add to context for main LLM
                    context["pre_computed_analysis"] = pre_computed_analysis
                    
                    # Add completion status
                    status_messages.append({
                        "action": "complete",
                        "description": "Pre-analysis finished",
                        "phase": "complete"
                    })
                
                # Store extracted data in context
                if orchestration_plan.extracted_data:
                    for key, value in orchestration_plan.extracted_data.items():
                        if value and key not in context:
                            context[key] = value
                
            except Exception as e:
                print(f"      ⚠️ Interpreter failed: {e}")
                import traceback
                traceback.print_exc()
                orchestration_plan = None
        
        # Handle clarification requests - respond with question instead of processing
        if orchestration_plan and orchestration_plan.needs_clarification:
            print(f"   ❓ Interpreter needs clarification - responding with question")
            clarification_response = orchestration_plan.clarification_question
            
            return {
                "response": clarification_response,
                "tool_calls": [],
                "annotations": {},
                "mode": "chat",
                "status_messages": status_messages,
                "frontend_commands": frontend_commands,
                "detected_intent": orchestration_plan.user_intent_summary,
                "tools_used": [],
                "orchestration": {
                    "mode": orchestration_plan.mode.value,
                    "mode_confidence": orchestration_plan.mode_confidence,
                    "intent": orchestration_plan.user_intent_summary,
                    "needs_clarification": True
                }
            }
        
        # Get appropriate tools for this context
        # Skip tools if interpreter says so
        use_tools_for_call = request.use_tools
        if orchestration_plan and orchestration_plan.skip_tools:
            use_tools_for_call = False
            print(f"   📋 Skipping tools (interpreter decision)")
        
        tools = get_tools_for_context(context) if use_tools_for_call else []
        
        if tools:
            print(f"   📋 {len(tools)} tools available to LLM")
        
        # Prepare messages with enhanced system prompt if using tools
        messages = request.messages.copy()
        
        # Log interpreter decisions for debugging
        if orchestration_plan:
            print(f"   📋 Interpreter decisions:")
            print(f"      Include context: {list(orchestration_plan.include_context.keys())}")
            print(f"      Relevant analyses: {orchestration_plan.relevant_analyses}")
            if orchestration_plan.response_strategy:
                print(f"      Response strategy: {orchestration_plan.response_strategy[:100]}...")
            if orchestration_plan.exclude_from_response:
                print(f"      Exclude: {orchestration_plan.exclude_from_response}")
        
        # Build interpreter-driven prompt (always use new system)
        if orchestration_plan:
            # Filter data based on interpreter's selections (no pre-executed results in non-streaming path)
            filtered_context, filtered_analyses = validate_interpreter_selections(
                orchestration_plan,
                context,
                {}  # No pre-executed results in this path
            )
            
            # Build interpreter-driven prompt
            system_prompt = build_interpreter_driven_prompt(
                orchestration_plan,
                filtered_context,
                filtered_analyses,
                TOOL_AWARE_SYSTEM_PROMPT
            )
            print(f"   📋 Using interpreter-driven prompt (filtered context: {len(filtered_context)} keys)")
        else:
            # Fallback if no orchestration plan (shouldn't happen, but safety)
            system_prompt = TOOL_AWARE_SYSTEM_PROMPT
        
        if len(messages) > 0 and messages[0].get("role") == "system":
            # Check if structured output is forced
            force_structured = context.get('force_structured', False)
            structured_override = ""
            if force_structured:
                structured_override = "\n\n**CRITICAL OVERRIDE: The user has explicitly requested STRUCTURED ANALYSIS. You MUST use section headers (### Key Themes:, ### Candidate Moves:, ### Critical Line:, ### Plan:) for this response, regardless of how the question is phrased. Provide a complete technical breakdown with all sections.**"
            
            # Context is already included in interpreter-driven prompt
            messages[0] = {
                "role": "system",
                "content": system_prompt + structured_override
            }
        
        # ============================================================
        # DETAILED LOGGING: What's being sent to LLM
        # ============================================================
        print("\n" + "="*80)
        print("📤 DETAILED LLM REQUEST LOG")
        print("="*80)
        print(f"Model: {request.model}")
        print(f"Temperature: {request.temperature}")
        print(f"Use tools: {request.use_tools}")
        print(f"Max tool iterations: {request.max_tool_iterations}")
        
        # Log each message in detail
        print(f"\n📝 MESSAGES ({len(messages)} total):")
        total_message_chars = 0
        for idx, msg in enumerate(messages):
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            content_len = len(str(content))
            total_message_chars += content_len
            
            print(f"\n  [{idx+1}] {role.upper()}:")
            print(f"      Content length: {content_len:,} chars")
            
            # Show preview based on role
            if role == "system":
                # Show first 500 and last 200 chars
                if content_len > 700:
                    preview = content[:500] + "\n      ... [truncated] ...\n      " + content[-200:]
                else:
                    preview = content
                print(f"      Preview:\n      {preview}")
            elif role == "user":
                preview = content[:300] + "..." if content_len > 300 else content
                print(f"      Content: {preview}")
            elif role == "assistant":
                preview = content[:300] + "..." if content_len > 300 else content
                print(f"      Content: {preview}")
                if "tool_calls" in msg:
                    tool_calls = msg.get("tool_calls", [])
                    print(f"      Tool calls: {len(tool_calls)}")
                    for tc in tool_calls:
                        print(f"        - {tc.get('function', {}).get('name', 'unknown')}")
            elif role == "tool":
                print(f"      Tool: {msg.get('name', 'unknown')}")
                preview = content[:200] + "..." if content_len > 200 else content
                print(f"      Result preview: {preview}")
        
        # Log context breakdown
        print(f"\n🌐 CONTEXT BREAKDOWN:")
        context_str = json.dumps(context, indent=2)
        context_len = len(context_str)
        print(f"  Total context size: {context_len:,} chars")
        
        # Break down context by key
        for key, value in context.items():
            if value is None:
                size = 0
            elif isinstance(value, str):
                size = len(value)
            elif isinstance(value, (dict, list)):
                size = len(json.dumps(value))
            else:
                size = len(str(value))
            
            print(f"    {key}: {size:,} chars", end="")
            if key == "pgn" and isinstance(value, str):
                print(f" (PGN length: {len(value)})")
            elif key == "cached_analysis" and isinstance(value, dict):
                # Show what's in cached_analysis
                if "confidence" in value:
                    conf_data = value["confidence"]
                    if isinstance(conf_data, dict):
                        nodes_count = len(conf_data.get("nodes", []))
                        print(f" (has confidence data: {nodes_count} nodes)")
                    else:
                        print()
                else:
                    print(f" (keys: {list(value.keys())})")
            else:
                print()
        
        # Check if tool messages have JSON content that needs formatting
        # This allows frontend to send raw tool results and have them auto-formatted
        for msg in messages:
            if msg.get("role") == "tool" and isinstance(msg.get("content"), str):
                try:
                    # Try to parse as JSON - if it's a tool result dict, format it
                    content_json = json.loads(msg["content"])
                    if isinstance(content_json, dict):
                        tool_name = msg.get("name", "unknown")
                        # Check if this looks like a tool result (has common fields)
                        if any(key in content_json for key in ["move_played", "eval_cp", "tags", "themes", "ply_records"]):
                            # This is a tool result - format it
                            formatted = tool_executor.format_result_for_llm(content_json, tool_name)
                            msg["content"] = formatted
                            print(f"   🔧 Auto-formatted tool message for {tool_name}")
                except (json.JSONDecodeError, TypeError):
                    # Not JSON or not a dict, leave as is
                    pass
        
        # Log tools
        if tools:
            print(f"\n🔧 TOOLS ({len(tools)} available):")
            total_tool_chars = 0
            for tool in tools:
                tool_str = json.dumps(tool)
                tool_len = len(tool_str)
                total_tool_chars += tool_len
                print(f"    {tool.get('function', {}).get('name', 'unknown')}: {tool_len:,} chars")
            print(f"  Total tools size: {total_tool_chars:,} chars")
        else:
            total_tool_chars = 0
        
        # Calculate token estimates (rough: ~4 chars per token)
        total_chars = total_message_chars + context_len + total_tool_chars
        estimated_tokens = total_chars // 4
        
        print(f"\n📊 TOKEN ESTIMATES:")
        print(f"  Messages: ~{total_message_chars // 4:,} tokens ({total_message_chars:,} chars)")
        print(f"  Context: ~{context_len // 4:,} tokens ({context_len:,} chars)")
        print(f"  Tools: ~{total_tool_chars // 4:,} tokens ({total_tool_chars:,} chars)")
        print(f"  TOTAL ESTIMATE: ~{estimated_tokens:,} tokens ({total_chars:,} chars)")
        
        # Warn if approaching limits
        if estimated_tokens > 100000:
            print(f"\n⚠️  WARNING: Estimated tokens ({estimated_tokens:,}) exceeds 100k!")
            print(f"   Model limit: 128,000 tokens")
            print(f"   You may need to truncate context or messages")
        
        print("="*80 + "\n")
        
        # Determine if we should force tool calls
        force_tool_call = (
            orchestration_plan and 
            orchestration_plan.tool_sequence and 
            len(orchestration_plan.tool_sequence) > 0
        )
        
        # Initial LLM call
        # If interpreter planned specific tools, force the EXACT tool to be called
        if force_tool_call:
            first_tool = orchestration_plan.tool_sequence[0]
            tool_choice_value = {"type": "function", "function": {"name": first_tool.name}}
            print(f"   🔧 Forcing specific tool: {first_tool.name}")
        else:
            tool_choice_value = "auto"
        
        completion = openai_client.chat.completions.create(
            model=request.model,
            messages=messages,
            tools=tools if tools else None,
            tool_choice=tool_choice_value if tools else None,
            temperature=request.temperature,
            timeout=120.0
        )
        
        response_message = completion.choices[0].message
        tool_calls_made = []
        iterations = 0
        
        # Log LLM's initial response
        if response_message.tool_calls:
            print(f"   🔧 LLM requested {len(response_message.tool_calls)} tool calls:")
            for tc in response_message.tool_calls:
                print(f"      - {tc.function.name}")
        else:
            print(f"   💭 LLM responded with text (no tool calls)")
            print(f"      Content preview: {response_message.content[:150]}...")
        
        # Handle tool calls (with iteration limit)
        while response_message.tool_calls and iterations < request.max_tool_iterations:
            iterations += 1
            print(f"\n   🔧 Tool iteration {iterations}/{request.max_tool_iterations}")
            
            # Execute each tool call
            tool_results = []
            for tool_call in response_message.tool_calls:
                tool_name = tool_call.function.name
                try:
                    tool_args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    tool_args = {}
                
                # Merge with planned arguments from orchestration_plan
                final_tool_args = dict(tool_args)
                if orchestration_plan and orchestration_plan.tool_sequence:
                    for planned_tool in orchestration_plan.tool_sequence:
                        if planned_tool.name == tool_name and planned_tool.arguments:
                            for key, value in planned_tool.arguments.items():
                                if key not in final_tool_args or not final_tool_args.get(key):
                                    final_tool_args[key] = value
                                    print(f"      📎 Injected missing arg: {key}={value}")
                
                # Inject interpreter's intent for game review
                if tool_name == "fetch_and_review_games" and orchestration_plan and orchestration_plan.user_intent_summary:
                    final_tool_args["interpreter_intent"] = orchestration_plan.user_intent_summary
                    # Prefer sending the original user question to the tool (selector LLM uses it).
                    if not final_tool_args.get("query"):
                        last_user_msg = next(
                            (m.content for m in reversed(request.messages or []) if getattr(m, "role", None) == "user" and getattr(m, "content", None)),
                            ""
                        )
                        if last_user_msg:
                            final_tool_args["query"] = last_user_msg
                
                print(f"      Executing: {tool_name} with args: {final_tool_args}")
                
                # Execute tool with merged arguments
                result = await tool_executor.execute_tool(tool_name, final_tool_args, context)
                
                # Format for LLM
                result_text = tool_executor.format_result_for_llm(result, tool_name)
                
                print(f"      Tool result preview: {result_text[:200]}...")
                
                tool_results.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": tool_name,
                    "content": result_text
                })
                
                tool_calls_made.append({
                    "tool": tool_name,
                    "arguments": tool_args,
                    "result": result,
                    "result_text": result_text
                })
            
            # Add assistant message with tool calls + tool results to conversation
            messages.append({
                "role": "assistant",
                "content": response_message.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    } for tc in response_message.tool_calls
                ]
            })
            
            messages.extend(tool_results)
            
            # Continue conversation with tool results
            completion = openai_client.chat.completions.create(
                model=request.model,
                messages=messages,
                tools=tools if tools else None,
                temperature=request.temperature,
                timeout=120.0
            )
            
            response_message = completion.choices[0].message
        
        # Final response
        final_content = response_message.content or ""
        
        print(f"   ✅ Chat complete ({iterations} tool iterations, {len(tool_calls_made)} tools called)")
        print(f"   Final response preview: {final_content[:150]}...")
        
        # ============================================================
        # RESPONSE ANNOTATOR: Parse response for tag mentions
        # ============================================================
        response_annotations = {"arrows": [], "highlights": [], "tags_found": []}
        try:
            cached_analysis = context.get("cached_analysis", {})
            current_fen = context.get("board_state") or context.get("fen")
            
            response_annotations = parse_response_for_annotations(
                llm_response=final_content,
                cached_analysis=cached_analysis,
                fen=current_fen
            )
            
            # Log what we found
            print(f"\n   🎨 BACKEND ANNOTATION GENERATION:")
            if response_annotations.get("tags_found"):
                print(f"      Tags in LLM text: {response_annotations['tags_found']}")
            
            # Log cached analysis tags
            if cached_analysis:
                cached_tags = cached_analysis.get("tags", [])
                if not cached_tags and "white_analysis" in cached_analysis:
                    cached_tags = cached_analysis.get("white_analysis", {}).get("tags", [])
                if cached_tags:
                    tag_names = [t.get("name", str(t)) if isinstance(t, dict) else str(t) for t in cached_tags[:5]]
                    print(f"      Cached analysis tags: {tag_names}")
            
            if response_annotations.get("arrows"):
                print(f"      ➡️ Arrows: {len(response_annotations['arrows'])}")
                for a in response_annotations["arrows"][:3]:
                    print(f"         {a.get('from')} → {a.get('to')} ({a.get('type')})")
            
            if response_annotations.get("highlights"):
                print(f"      🔲 Highlights: {len(response_annotations['highlights'])}")
                for h in response_annotations["highlights"][:5]:
                    print(f"         {h.get('square')}: {h.get('type')}")
            
            if not response_annotations.get("arrows") and not response_annotations.get("highlights"):
                print(f"      ⚠️ No annotations generated")
                
        except Exception as e:
            print(f"   ⚠️ Response annotation failed: {e}")
            import traceback
            traceback.print_exc()
        
        # Build response with orchestration metadata
        response_data = {
            "content": final_content,
            "model": completion.model,
            "usage": {
                "prompt_tokens": completion.usage.prompt_tokens,
                "completion_tokens": completion.usage.completion_tokens,
                "total_tokens": completion.usage.total_tokens
            },
            "tool_calls": tool_calls_made,
            "iterations": iterations,
            # Orchestration additions
            "frontend_commands": frontend_commands,
            "status_messages": status_messages,
            # Response-based annotations
            "annotations": {
                "arrows": response_annotations.get("arrows", []),
                "highlights": response_annotations.get("highlights", []),
                "tags_referenced": response_annotations.get("tags_found", []),
            },
        }
        
        # Always add tools_used based on what was actually called
        called_tools = [tc.get("tool") for tc in tool_calls_made] if tool_calls_made else []
        
        # Add orchestration metadata if available
        if orchestration_plan:
            response_data["orchestration"] = {
                "mode": orchestration_plan.mode.value,
                "mode_confidence": orchestration_plan.mode_confidence,
                "intent": orchestration_plan.user_intent_summary,
                "extracted_data": orchestration_plan.extracted_data
            }
            
            # Add detected intent for frontend display
            response_data["detected_intent"] = orchestration_plan.user_intent_summary
            
            # Add tools used (both planned and actually called)
            planned_tools = [t.name for t in orchestration_plan.tool_sequence] if orchestration_plan.tool_sequence else []
            response_data["tools_used"] = list(set(planned_tools + called_tools))
            
            # Add pre-computed analysis summary if available
            if pre_computed_analysis:
                response_data["pre_computed_analysis"] = pre_computed_analysis
        else:
            # Fallback: even without orchestration plan, report called tools
            response_data["tools_used"] = called_tools
            response_data["detected_intent"] = None
        
        # Log final response payload for debugging
        print(f"\n   📦 FINAL RESPONSE:")
        print(f"      Content length: {len(final_content)}")
        print(f"      Status messages: {len(status_messages)}")
        print(f"      Detected intent: {response_data.get('detected_intent', 'none')}")
        print(f"      Tools used: {response_data.get('tools_used', [])}")
        
        return response_data
    
    except Exception as e:
        import traceback
        from openai import APIConnectionError, APIError
        
        error_detail = f"LLM error: {str(e)}\n{traceback.format_exc()}"
        print(error_detail)
        
        # Provide more helpful error messages for common issues
        if isinstance(e, APIConnectionError):
            error_msg = (
                "Failed to connect to OpenAI API. This could be due to:\n"
                "- Network connectivity issues\n"
                "- Invalid or missing OPENAI_API_KEY\n"
                "- DNS resolution problems\n"
                f"Original error: {str(e)}"
            )
        elif isinstance(e, APIError):
            error_msg = f"OpenAI API error: {str(e)}"
        else:
            error_msg = f"LLM error: {str(e)}"
        
        raise HTTPException(status_code=500, detail=error_msg)


# ============================================================================
# SSE STREAMING ENDPOINT FOR REAL-TIME STATUS UPDATES
# ============================================================================

@app.post("/llm_chat_stream")
async def llm_chat_stream(request: LLMRequest, http_request: Request):
    """
    SSE streaming version of /llm_chat.
    Sends status updates in real-time as the system processes the request.
    """
    import time as _time
    import asyncio
    
    async def event_generator():
        """Generate SSE events with status updates and final response."""
        try:
            context = request.context or {}
            context["authenticated"] = False
            
            user_messages = [m for m in request.messages if m.get('role') == 'user']
            last_user_message = user_messages[-1].get('content', '') if user_messages else ""
            
            # Get user info for rate limiting
            user_id = context.get("user_id") or context.get("profile", {}).get("user_id")
            ip_address = http_request.client.host if http_request else None
            
            # Helper to send SSE event
            def send_event(event_type: str, data: dict):
                try:
                    json_data = json.dumps(data, default=str)
                    return f"event: {event_type}\ndata: {json_data}\n\n"
                except Exception as e:
                    print(f"   ❌ JSON serialization error for event {event_type}: {e}")
                    return f"event: error\ndata: {{\"message\": \"JSON serialization failed for {event_type}\"}}\n\n"
            # Helper to send SSE event and ensure it's flushed immediately
            async def send_status_event_flushed(event_type: str, data: dict):
                """Send SSE event and ensure it's flushed immediately for progressive updates"""
                yield send_event(event_type, data)
                yield ": keepalive\n\n"
                await asyncio.sleep(0.01)  # Small delay to ensure FastAPI flushes the buffer
            
# Helper to strip massive raw analysis data from tool results
            def _strip_raw_analysis_from_tool_result(result: dict) -> dict:
                """Strip massive raw_before/raw_after from game reviews to reduce SSE event size"""
                if not isinstance(result, dict):
                    return result
                
                stripped = result.copy()
                
                # If this is a game review result, strip the massive data
                if "first_game_review" in stripped:
                    review = stripped["first_game_review"]
                    if review and isinstance(review, dict) and "ply_records" in review:
                        # Strip raw_before/raw_after from each ply record
                        for ply in review.get("ply_records", []):
                            if "raw_before" in ply:
                                ply["raw_before"] = {"_stripped": True, "note": "Use /analyze_position endpoint for full analysis"}
                            if "raw_after" in ply:
                                ply["raw_after"] = {"_stripped": True, "note": "Use /analyze_position endpoint for full analysis"}
                            if "analyse" in ply:
                                ply["analyse"] = {"_stripped": True, "note": "Use /analyze_position endpoint for full analysis"}
                
                return stripped
            
            # Collect all status messages for final response
            all_status_messages = []
            
            # Check message and token limits
            limit_exceeded = False
            limit_info = {}
            available_tools = {}
            
            if supabase_client:
                try:
                    # Get subscription info
                    if user_id:
                        tier_info = supabase_client.get_subscription_overview(user_id)
                    else:
                        # Anonymous user - default to unpaid (1 message/day)
                        tier_info = {"tier_id": "unpaid", "tier": {"daily_messages": 1, "daily_tokens": 15000, "max_game_reviews_per_day": 0, "max_lessons_per_day": 0}}
                    
                    # Check message limit
                    msg_allowed, msg_error, msg_info = supabase_client.check_message_limit(user_id, ip_address, tier_info)
                    if not msg_allowed:
                        limit_exceeded = True
                        limit_info = {
                            "type": "message_limit",
                            "message": msg_error,
                            "usage": msg_info,
                            "next_step": msg_info.get("next_step", "upgrade")
                        }
                    
                    # Check token limit (estimate ~5k tokens for a typical request)
                    if not limit_exceeded:
                        token_allowed, token_error, token_info = supabase_client.check_token_limit(
                            user_id, ip_address, tier_info, estimated_tokens=5000
                        )
                        if not token_allowed:
                            limit_exceeded = True
                            available_tools = token_info.get("available_tools", {})
                            limit_info = {
                                "type": "token_limit",
                                "message": token_error,
                                "usage": token_info,
                                "next_step": token_info.get("next_step", "upgrade"),
                                "available_tools": available_tools
                            }
                except Exception as e:
                    print(f"   ⚠️ Rate limit check failed: {e}")
                    import traceback
                    traceback.print_exc()
                    # Continue anyway - don't block on rate limit errors
            
            # Send limit exceeded event if needed (but continue conversation)
            if limit_exceeded:
                async for event in send_status_event_flushed("limit_exceeded", {
                    "type": limit_info.get("type"),
                    "message": limit_info.get("message"),
                    "usage": limit_info.get("usage"),
                    "next_step": limit_info.get("next_step"),
                    "available_tools": available_tools,
                    "timestamp": _time.time()
                }):
                    yield event
                # Continue with conversation - don't block, just notify
            
            # ============================================================
            # PHASE 1: INTERPRETATION
            # ============================================================
            async for event in send_status_event_flushed("status", {
                "phase": "interpreting",
                "message": "Understanding your request...",
                "timestamp": _time.time()
            }):

                yield event

            all_status_messages.append({"phase": "interpreting", "message": "Understanding your request...", "timestamp": _time.time()})  # Allow event to be sent
            
            orchestration_plan = None
            pre_computed_analysis = {}
            
            if request_interpreter and last_user_message:
                # Status callback that yields SSE events
                async def stream_status(phase: str, message: str, **kwargs):
                    nonlocal all_status_messages
                    status_entry = {
                        "phase": phase,
                        "message": message,
                        "timestamp": kwargs.get("timestamp", _time.time())
                    }
                    if kwargs.get("tool"):
                        status_entry["tool"] = kwargs["tool"]
                    if kwargs.get("progress") is not None:
                        status_entry["progress"] = kwargs["progress"]
                    all_status_messages.append(status_entry)
                    return status_entry
                
                # Run interpreter
                import time
                interpreter_start = time.time()
                orchestration_plan = await request_interpreter.interpret(
                    message=last_user_message,
                    context=context,
                    conversation_history=request.messages,
                    model_override=request.interpreter_model  # Allow console command to override model
                )
                interpreter_time = time.time() - interpreter_start
                print(f"🔍 [PERFORMANCE] Interpreter took {interpreter_time:.2f}s")
                
                # Log full orchestration plan
                print(f"🔍 [DOWNSTREAM_FLOW] Interpreter returned orchestration_plan")
                if orchestration_plan:
                    try:
                        plan_dict = {
                            "mode": orchestration_plan.mode.value if hasattr(orchestration_plan.mode, 'value') else str(orchestration_plan.mode),
                            "mode_confidence": orchestration_plan.mode_confidence,
                            "user_intent_summary": orchestration_plan.user_intent_summary,
                            "tool_sequence_count": len(orchestration_plan.tool_sequence) if orchestration_plan.tool_sequence else 0,
                            "tool_sequence": [{"name": t.name, "arguments": t.arguments} for t in (orchestration_plan.tool_sequence or [])],
                            "needs_clarification": orchestration_plan.needs_clarification,
                            "skip_tools": orchestration_plan.skip_tools,
                            "response_guidelines": orchestration_plan.response_guidelines.to_dict() if hasattr(orchestration_plan.response_guidelines, 'to_dict') else str(orchestration_plan.response_guidelines),
                            "frontend_commands": [cmd.to_dict() if hasattr(cmd, 'to_dict') else str(cmd) for cmd in (orchestration_plan.frontend_commands or [])],
                            "extracted_data": orchestration_plan.extracted_data.to_dict() if hasattr(orchestration_plan.extracted_data, 'to_dict') else orchestration_plan.extracted_data,
                        }
                        print(f"   orchestration_plan (full): {json.dumps(plan_dict, default=str, indent=2)}")
                    except Exception as e:
                        print(f"   ⚠️ Could not serialize orchestration_plan: {e}")
                        print(f"   orchestration_plan (str): {str(orchestration_plan)}")
                else:
                    print(f"   ⚠️ orchestration_plan is None!")
                
                # Send interpreter results
                async for event in send_status_event_flushed("status", {
                    "phase": "interpreting",
                    "message": f"Detected: {orchestration_plan.user_intent_summary}",
                    "timestamp": _time.time()
                }):

                    yield event

                all_status_messages.append({"phase": "interpreting", "message": "Understanding your request...", "timestamp": _time.time()})
                
                if orchestration_plan.tool_sequence:
                    tools_str = ', '.join([t.name for t in orchestration_plan.tool_sequence])
                    async for event in send_status_event_flushed("status", {
                        "phase": "planning",
                        "message": f"Planning to use: {tools_str}",
                        "timestamp": _time.time()
                    }):

                        yield event

                    all_status_messages.append({"phase": "interpreting", "message": "Understanding your request...", "timestamp": _time.time()})
            
            # ============================================================
            # HANDLE CLARIFICATION REQUESTS
            # ============================================================
            print(f"🔍 [DOWNSTREAM_FLOW] Checking if clarification needed")
            print(f"   orchestration_plan exists: {orchestration_plan is not None}")
            if orchestration_plan:
                print(f"   needs_clarification: {orchestration_plan.needs_clarification}")
                print(f"   clarification_question: {orchestration_plan.clarification_question if hasattr(orchestration_plan, 'clarification_question') else 'N/A'}")
            
            if orchestration_plan and orchestration_plan.needs_clarification:
                print(f"   ❓ Interpreter needs clarification - responding with question")
                clarification_response = orchestration_plan.clarification_question
                
                async for event in send_status_event_flushed("status", {
                    "phase": "clarifying",
                    "message": "Asking for clarification...",
                    "timestamp": _time.time()
                }):
                    yield event
                
                response_data = {
                    "response": clarification_response,
                    "tool_calls": [],
                    "annotations": {},
                    "mode": "chat",
                    "status_messages": all_status_messages,
                    "frontend_commands": [],
                    "detected_intent": orchestration_plan.user_intent_summary,
                    "tools_used": [],
                    "orchestration": {
                        "mode": orchestration_plan.mode.value,
                        "mode_confidence": orchestration_plan.mode_confidence,
                        "intent": orchestration_plan.user_intent_summary,
                        "needs_clarification": True
                    }
                }
                yield send_event("complete", response_data)
                return
            
            # ============================================================
            # PHASE 1.5: PRE-EXECUTE REQUIRED TOOLS
            # ============================================================
            pre_executed_results = {}
            pre_executed_tool_calls = []
            
            print(f"🔍 [DOWNSTREAM_FLOW] Pre-execution phase starting")
            if orchestration_plan:
                tool_seq = orchestration_plan.tool_sequence or []
                print(f"   tool_sequence count: {len(tool_seq)}")
                if tool_seq:
                    for idx, tool in enumerate(tool_seq):
                        print(f"   tool[{idx}]: name={tool.name}, args={json.dumps(tool.arguments, default=str)}")
            
            if orchestration_plan and orchestration_plan.tool_sequence and len(orchestration_plan.tool_sequence) > 0:
                print(f"   🔧 Pre-executing {len(orchestration_plan.tool_sequence)} required tools")
                
                for tool_call in orchestration_plan.tool_sequence:
                    tool_name = tool_call.name
                    tool_args = tool_call.arguments or {}
                    
                    print(f"🔍 [DOWNSTREAM_FLOW] Pre-executing tool: {tool_name}")
                    print(f"   tool_args (full): {json.dumps(tool_args, default=str, indent=2)}")
                    print(f"   context keys: {list(context.keys())}")
                    
                    # Inject interpreter's intent for game review
                    if tool_name == "fetch_and_review_games" and orchestration_plan.user_intent_summary:
                        tool_args["interpreter_intent"] = orchestration_plan.user_intent_summary
                        if not tool_args.get("query"):
                            last_user_msg = next(
                                (m.content for m in reversed(request.messages or []) if getattr(m, "role", None) == "user" and getattr(m, "content", None)),
                                ""
                            )
                            if last_user_msg:
                                tool_args["query"] = last_user_msg
                    
                    async for event in send_status_event_flushed("status", {
                        "phase": "executing",
                        "message": f"Running {tool_name}...",
                        "timestamp": _time.time()
                    }):

                    
                        yield event

                    
                    all_status_messages.append({"phase": "interpreting", "message": "Understanding your request...", "timestamp": _time.time()})
                    
                    # Use async queue for real-time status streaming during tool execution
                    status_queue = asyncio.Queue()
                    
                    async def pre_exec_status_callback(phase: str, message: str, progress: float = None, replace: bool = False):
                        status_msg = {
                            "phase": phase,
                            "message": message,
                            "tool": tool_name,
                            "progress": progress,
                            "timestamp": _time.time(),
                            "replace": replace
                        }
                        await status_queue.put(status_msg)
                        print(f"   📊 Pre-exec progress: {message} ({progress*100:.0f}%)" if progress is not None else f"   📊 Pre-exec status: {message}")
                    
                    # Run tool execution and status streaming concurrently
                    async def run_pre_exec_tool():
                        try:
                            res = await tool_executor.execute_tool(tool_name, tool_args, context, pre_exec_status_callback)
                            # Check if result contains an error (tools return {"error": "..."} on failure)
                            if isinstance(res, dict) and "error" in res:
                                return {"success": False, "error": res["error"], "result": res}
                            return {"success": True, "result": res}
                        except Exception as e:
                            import traceback
                            traceback.print_exc()
                            return {"success": False, "error": str(e)}
                    
                    # Start tool execution as a task
                    tool_task = asyncio.create_task(run_pre_exec_tool())
                    
                    # Stream status events while tool is running
                    while not tool_task.done():
                        try:
                            status_msg = await asyncio.wait_for(status_queue.get(), timeout=0.1)
                            all_status_messages.append(status_msg)
                            async for event in send_status_event_flushed("status", status_msg):

                                yield event
                        except asyncio.TimeoutError:
                            pass
                    
                    # Drain any remaining status messages
                    while not status_queue.empty():
                        try:
                            status_msg = status_queue.get_nowait()
                            all_status_messages.append(status_msg)
                            async for event in send_status_event_flushed("status", status_msg):

                                yield event
                        except asyncio.QueueEmpty:
                            break
                    
                    # Get tool result
                    tool_result = await tool_task
                    
                    print(f"🔍 [DOWNSTREAM_FLOW] Tool pre-execution result: {tool_name}")
                    print(f"   success: {tool_result['success']}")
                    if tool_result["success"]:
                        result_preview = json.dumps(tool_result["result"], default=str)
                        if len(result_preview) > 2000:
                            result_preview = result_preview[:2000] + f"... (truncated, total {len(result_preview)} chars)"
                        print(f"   result (full): {result_preview}")
                        pre_executed_results[tool_name] = tool_result["result"]
                        pre_executed_tool_calls.append({
                            "name": tool_name,
                            "arguments": tool_args,
                            "result": tool_result["result"]
                        })
                        print(f"   ✅ Pre-executed {tool_name} successfully")
                    else:
                        print(f"   error: {tool_result['error']}")
                        pre_executed_results[tool_name] = {"error": tool_result["error"]}
                        pre_executed_tool_calls.append({
                            "name": tool_name,
                            "arguments": tool_args,
                            "error": tool_result["error"]
                        })
                        print(f"   ❌ Pre-execution of {tool_name} failed: {tool_result['error']}")
                
                # Clear tool sequence so LLM doesn't try to call them again
                orchestration_plan.tool_sequence = []
            
            # ============================================================
            # PHASE 2: GET TOOLS AND BUILD MESSAGES
            # ============================================================
            use_tools_for_call = request.use_tools
            if orchestration_plan and orchestration_plan.skip_tools:
                use_tools_for_call = False
            
            # If we pre-executed tools, don't give LLM tool access (it just narrates)
            if pre_executed_results:
                use_tools_for_call = False
            
            tools = get_tools_for_context(context) if use_tools_for_call else []
            
            # Build messages
            messages = []
            
            # Log interpreter decisions for debugging
            if orchestration_plan:
                print(f"   📋 Interpreter decisions:")
                print(f"      Include context: {list(orchestration_plan.include_context.keys())}")
                print(f"      Relevant analyses: {orchestration_plan.relevant_analyses}")
                if orchestration_plan.response_strategy:
                    print(f"      Response strategy: {orchestration_plan.response_strategy[:100]}...")
                if orchestration_plan.exclude_from_response:
                    print(f"      Exclude: {orchestration_plan.exclude_from_response}")
            
            # Build interpreter-driven prompt (always use new system)
            if orchestration_plan:
                # Filter data based on interpreter's selections
                filtered_context, filtered_analyses = validate_interpreter_selections(
                    orchestration_plan,
                    context,
                    pre_executed_results
                )
                
                # Build interpreter-driven prompt
                system_prompt = build_interpreter_driven_prompt(
                    orchestration_plan,
                    filtered_context,
                    filtered_analyses,
                    TOOL_AWARE_SYSTEM_PROMPT  # Base capabilities for reference
                )
                print(f"   📋 Using interpreter-driven prompt (filtered context: {len(filtered_context)} keys, analyses: {len(filtered_analyses)} keys)")
            else:
                # Fallback if no orchestration plan (shouldn't happen, but safety)
                system_prompt = TOOL_AWARE_SYSTEM_PROMPT
            
            messages.append({"role": "system", "content": system_prompt})
            messages.extend(request.messages)
            
            # Check if tool messages have JSON content that needs formatting
            # This allows frontend to send raw tool results and have them auto-formatted
            for msg in messages:
                if msg.get("role") == "tool" and isinstance(msg.get("content"), str):
                    try:
                        # Try to parse as JSON - if it's a tool result dict, format it
                        content_json = json.loads(msg["content"])
                        if isinstance(content_json, dict):
                            tool_name = msg.get("name", "unknown")
                            # Check if this looks like a tool result (has common fields)
                            if any(key in content_json for key in ["move_played", "eval_cp", "tags", "themes", "ply_records"]):
                                # This is a tool result - format it
                                formatted = tool_executor.format_result_for_llm(content_json, tool_name)
                                msg["content"] = formatted
                                print(f"   🔧 Auto-formatted tool message for {tool_name}")
                    except (json.JSONDecodeError, TypeError):
                        # Not JSON or not a dict, leave as is
                        pass
            
            # Add pre-executed tool calls and results to messages so LLM knows what happened
            print(f"🔍 [DOWNSTREAM_FLOW] Building messages for LLM")
            print(f"   pre_executed_tool_calls count: {len(pre_executed_tool_calls)}")
            print(f"   messages count before adding tools: {len(messages)}")
            
            if pre_executed_tool_calls:
                # Add assistant message with tool calls
                messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": f"pre_exec_{idx}",
                            "type": "function",
                            "function": {
                                "name": tc["name"],
                                "arguments": json.dumps(tc["arguments"])
                            }
                        }
                        for idx, tc in enumerate(pre_executed_tool_calls)
                    ]
                })
                
                # Add tool results
                for idx, tc in enumerate(pre_executed_tool_calls):
                    tool_result = tc.get("result", {"error": tc.get("error", "Unknown error")})
                    tool_result_text = tool_executor.format_result_for_llm(tool_result, tc["name"])
                    messages.append({
                        "role": "tool",
                        "tool_call_id": f"pre_exec_{idx}",
                        "name": tc["name"],
                        "content": tool_result_text
                    })
                    print(f"   📝 Added pre-executed tool result for {tc['name']} to messages")
                    print(f"      tool_result_text length: {len(tool_result_text)} chars")
            
            print(f"🔍 [DOWNSTREAM_FLOW] Messages built for LLM call")
            print(f"   total messages: {len(messages)}")
            for idx, msg in enumerate(messages):
                role = msg.get("role", "unknown")
                content_preview = ""
                if "content" in msg and msg["content"]:
                    content_preview = str(msg["content"])[:300]
                elif "tool_calls" in msg and msg["tool_calls"]:
                    content_preview = f"tool_calls: {len(msg['tool_calls'])}"
                elif "name" in msg:
                    content_preview = f"tool result for {msg.get('name', 'unknown')}"
                print(f"   message[{idx}]: role={role}, preview={content_preview}...")
            
            # ============================================================
            # PHASE 3: LLM CALL (with tool execution)
            # ============================================================
            async for event in send_status_event_flushed("status", {
                "phase": "executing",
                "message": "Thinking...",
                "timestamp": _time.time()
            }):

                yield event

            all_status_messages.append({"phase": "interpreting", "message": "Understanding your request...", "timestamp": _time.time()})
            
            # Include pre-executed tool calls in the list (normalize structure)
            tool_calls_made = []
            for tc in pre_executed_tool_calls:
                tool_name = tc.get("name", "unknown")
                tool_args = tc.get("arguments", {})
                tool_result = tc.get("result", {"error": tc.get("error", "Unknown error")})
                
                # Strip massive raw analysis data before adding to tool_calls_made
                stripped_result = _strip_raw_analysis_from_tool_result(tool_result)
                
                # Format result text for consistency
                tool_result_text = tool_executor.format_result_for_llm(stripped_result, tool_name)
                tool_calls_made.append({
                    "tool": tool_name,
                    "arguments": tool_args,
                    "result": stripped_result,
                    "result_text": tool_result_text
                })
            iterations = 0
            max_iterations = 5
            final_content = ""
            
            # No need to force tool calls if we pre-executed them
            # (orchestration_plan.tool_sequence was cleared after pre-execution)
            force_tool_call = (
                orchestration_plan and 
                orchestration_plan.tool_sequence and 
                len(orchestration_plan.tool_sequence) > 0
            )
            
            # Diagnostic logging before LLM call
            print(f"🔍 [DOWNSTREAM_FLOW] About to call LLM")
            print(f"   model: {request.model}")
            print(f"   temperature: {request.temperature}")
            print(f"   tools available: {len(tools) if tools else 0}")
            print(f"   force_tool_call: {force_tool_call}")
            print(f"   pre_executed tools: {len(pre_executed_tool_calls)}")
            print(f"   messages count: {len(messages)}")
            # Log full messages (truncate very long content)
            messages_log = []
            for msg in messages:
                msg_copy = msg.copy()
                if "content" in msg_copy and msg_copy["content"] and len(str(msg_copy["content"])) > 1000:
                    msg_copy["content"] = str(msg_copy["content"])[:1000] + "... (truncated)"
                messages_log.append(msg_copy)
            print(f"   messages (full, truncated): {json.dumps(messages_log, default=str, indent=2)}")
            print(f"   🤖 About to call LLM (model={request.model}, tools={len(tools) if tools else 0}, pre_executed={len(pre_executed_tool_calls)})")
            
            while iterations < max_iterations:
                iterations += 1
                print(f"   🔄 LLM iteration {iterations}/{max_iterations}...")
                
                try:
                    if tools:
                        # Force the EXACT tool on first iteration if interpreter planned tools
                        if force_tool_call and iterations == 1 and orchestration_plan and orchestration_plan.tool_sequence:
                            first_tool = orchestration_plan.tool_sequence[0]
                            tool_choice_value = {"type": "function", "function": {"name": first_tool.name}}
                            print(f"   🔧 Forcing specific tool: {first_tool.name}")
                        else:
                            tool_choice_value = "auto"

                        print(f"   📡 Calling OpenAI API with tools...")
                        response = openai_client.chat.completions.create(
                            model=request.model,
                            messages=messages,
                            temperature=request.temperature,
                            tools=tools,
                            tool_choice=tool_choice_value,
                        )
                    else:
                        print(f"   📡 Calling OpenAI API without tools...")
                        response = openai_client.chat.completions.create(
                            model=request.model,
                            messages=messages,
                            temperature=request.temperature,
                        )

                    print(f"   ✅ LLM API call succeeded")
                    
                    # Log full LLM response
                    print(f"🔍 [DOWNSTREAM_FLOW] LLM response received")
                    response_summary = {
                        "id": response.id,
                        "model": response.model,
                        "choices_count": len(response.choices),
                        "usage": {
                            "prompt_tokens": response.usage.prompt_tokens if hasattr(response, 'usage') and response.usage else None,
                            "completion_tokens": response.usage.completion_tokens if hasattr(response, 'usage') and response.usage else None,
                            "total_tokens": response.usage.total_tokens if hasattr(response, 'usage') and response.usage else None,
                        } if hasattr(response, 'usage') and response.usage else None
                    }
                    if response.choices:
                        choice = response.choices[0]
                        response_summary["choice"] = {
                            "index": choice.index,
                            "finish_reason": choice.finish_reason,
                            "message": {
                                "role": choice.message.role,
                                "content_preview": (choice.message.content[:500] if choice.message.content else None),
                                "content_length": len(choice.message.content) if choice.message.content else 0,
                                "tool_calls_count": len(choice.message.tool_calls) if choice.message.tool_calls else 0,
                                "tool_calls": [{"id": tc.id, "type": tc.type, "function": {"name": tc.function.name, "arguments_preview": tc.function.arguments[:200]}} for tc in (choice.message.tool_calls or [])]
                            }
                        }
                    print(f"   response (summary): {json.dumps(response_summary, default=str, indent=2)}")
                    
                    response_message = response.choices[0].message

                    content_len = len(response_message.content) if response_message.content else 0
                    print(
                        f"   📨 LLM response: tool_calls={len(response_message.tool_calls) if response_message.tool_calls else 0}, "
                        f"content_length={content_len}"
                    )

                    if not response_message.tool_calls:
                        final_content = response_message.content or ""
                        print(f"🔍 [DOWNSTREAM_FLOW] Final content determined")
                        print(f"   final_content (full, {len(final_content)} chars): {final_content}")
                        print(f"   ✅ Got final content: {len(final_content)} chars")
                        if not final_content:
                            print(f"   ⚠️ WARNING: final_content is empty! Response was: {response_message}")
                        break
                    else:
                        print(f"   🔧 LLM requested {len(response_message.tool_calls)} tool calls, will execute...")

                except Exception as llm_err:
                    print(f"   ❌ LLM call failed at iteration {iterations}: {llm_err}")
                    import traceback
                    error_tb = traceback.format_exc()
                    print(f"   Traceback: {error_tb}")
                    # Re-raise to be caught by outer handler
                    raise
                
                # Execute tools
                tool_results = []
                for tool_call in response_message.tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = json.loads(tool_call.function.arguments)
                    
                    print(f"🔍 [DOWNSTREAM_FLOW] Executing tool from LLM: {tool_name}")
                    print(f"   tool_call_id: {tool_call.id}")
                    print(f"   tool_args from LLM: {json.dumps(tool_args, default=str)}")
                    
                    # Send initial "called" status (not loading - just info)
                    tool_start_status = {
                        "phase": "executing",
                        "message": f"Called {tool_name.replace('_', ' ')}",
                        "tool": tool_name,
                        "timestamp": _time.time()
                    }
                    all_status_messages.append(tool_start_status)
                    async for event in send_status_event_flushed("status", tool_start_status):

                        yield event
                    await asyncio.sleep(0)
                    
                    # Merge with planned arguments from orchestration_plan
                    final_tool_args = dict(tool_args)
                    if orchestration_plan and orchestration_plan.tool_sequence:
                        for planned_tool in orchestration_plan.tool_sequence:
                            if planned_tool.name == tool_name and planned_tool.arguments:
                                for key, value in planned_tool.arguments.items():
                                    if key not in final_tool_args or not final_tool_args.get(key):
                                        final_tool_args[key] = value
                                        print(f"   📎 Injected missing arg: {key}={value}")

                    # Ensure fetch_and_review_games receives interpreter intent + original question
                    if tool_name == "fetch_and_review_games" and orchestration_plan and orchestration_plan.user_intent_summary:
                        final_tool_args["interpreter_intent"] = orchestration_plan.user_intent_summary
                        if not final_tool_args.get("query"):
                            last_user_msg = next(
                                (m.content for m in reversed(request.messages or []) if getattr(m, "role", None) == "user" and getattr(m, "content", None)),
                                ""
                            )
                            if last_user_msg:
                                final_tool_args["query"] = last_user_msg
                    
                    print(f"   final_tool_args after merge: {json.dumps(final_tool_args, default=str)}")
                    print(f"   🔧 SSE: Executing {tool_name} with args: {final_tool_args}")
                    
                    # Use async queue for real-time status streaming during tool execution
                    status_queue = asyncio.Queue()
                    
                    async def tool_status_callback(phase: str, message: str, progress: float = None, replace: bool = False):
                        status_msg = {
                            "phase": phase,
                            "message": message,
                            "tool": tool_name,
                            "progress": progress,
                            "timestamp": _time.time(),
                            "replace": replace  # Frontend should replace last message instead of adding
                        }
                        await status_queue.put(status_msg)
                        print(f"   📊 Tool progress: {message} ({progress*100:.0f}%)" if progress is not None else f"   📊 Tool status: {message}")
                    
                    # Run tool execution and status streaming concurrently
                    async def run_tool():
                        try:
                            res = await tool_executor.execute_tool(tool_name, final_tool_args, context, tool_status_callback)
                            # Check if result contains an error (tools return {"error": "..."} on failure)
                            if isinstance(res, dict) and "error" in res:
                                return {"success": False, "error": res["error"], "result": res}
                            return {"success": True, "result": res}
                        except Exception as e:
                            return {"success": False, "error": str(e)}
                    
                    # Start tool execution as a task
                    tool_task = asyncio.create_task(run_tool())
                    
                    # Stream status events while tool is running
                    while not tool_task.done():
                        try:
                            # Wait for status with short timeout
                            status_msg = await asyncio.wait_for(status_queue.get(), timeout=0.1)
                            all_status_messages.append(status_msg)
                            async for event in send_status_event_flushed("status", status_msg):

                                yield event
                        except asyncio.TimeoutError:
                            # No status available, check if task is done
                            await asyncio.sleep(0)
                    
                    # Drain any remaining status messages
                    while not status_queue.empty():
                        status_msg = await status_queue.get()
                        all_status_messages.append(status_msg)
                        async for event in send_status_event_flushed("status", status_msg):

                            yield event
                    
                    # Get tool result
                    tool_result = await tool_task
                    
                    print(f"🔍 [DOWNSTREAM_FLOW] Tool execution completed: {tool_name}")
                    print(f"   success: {tool_result['success']}")
                    
                    if tool_result["success"]:
                        result = tool_result["result"]
                        result_full = json.dumps(result, default=str)
                        result_text = json.dumps(result, indent=2, default=str)[:4000]
                        if len(result_full) > 5000:
                            result_preview = result_full[:5000] + f"... (truncated, total {len(result_full)} chars)"
                        else:
                            result_preview = result_full
                        print(f"   result (full): {result_preview}")
                        print(f"   result_text (full, first 4000 chars): {result_text}")
                        print(f"   ✅ SSE: Tool {tool_name} completed, result preview: {result_text[:200]}...")
                        
                        # Yield completion status with summary
                        completion_msg = "Analysis complete"
                        if tool_name == "fetch_and_review_games" and result.get("success"):
                            completion_msg = f"Analyzed {result.get('games_analyzed', 0)} game(s)"
                        
                        tool_complete_status = {
                            "phase": "executing",
                            "message": completion_msg,
                            "tool": tool_name,
                            "progress": 1.0,
                            "timestamp": _time.time()
                        }
                        all_status_messages.append(tool_complete_status)
                        async for event in send_status_event_flushed("status", tool_complete_status):

                            yield event
                    else:
                        print(f"   ❌ SSE: Tool {tool_name} failed: {tool_result['error']}")
                        result = {"error": tool_result["error"]}
                        result_text = json.dumps(result)
                        
                        # Yield error status
                        error_status = {
                            "phase": "executing",
                            "message": f"Tool failed: {tool_result['error'][:50]}",
                            "tool": tool_name,
                            "timestamp": _time.time()
                        }
                        all_status_messages.append(error_status)
                        async for event in send_status_event_flushed("status", error_status):

                            yield event
                    
                    tool_results.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_name,
                        "content": result_text
                    })
                    
                    # Strip massive raw analysis data before adding
                    stripped_result = _strip_raw_analysis_from_tool_result(result) if isinstance(result, dict) else result
                    # Re-format result text with stripped data
                    stripped_result_text = json.dumps(stripped_result) if isinstance(stripped_result, dict) else str(stripped_result)
                    
                    tool_calls_made.append({
                        "tool": tool_name,
                        "arguments": tool_args,
                        "result": stripped_result,
                        "result_text": stripped_result_text
                    })
                
                # Add to messages and continue
                print(f"🔍 [DOWNSTREAM_FLOW] Adding assistant message and tool results to messages")
                print(f"   messages count before: {len(messages)}")
                assistant_msg = {
                    "role": "assistant",
                    "content": response_message.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        } for tc in response_message.tool_calls
                    ]
                }
                print(f"   assistant message: content_length={len(assistant_msg.get('content', '') or '')}, tool_calls={len(assistant_msg.get('tool_calls', []))}")
                messages.append(assistant_msg)
                print(f"   tool_results count: {len(tool_results)}")
                for tr in tool_results:
                    print(f"      tool_result: role={tr.get('role')}, name={tr.get('name')}, content_length={len(str(tr.get('content', '')))}")
                messages.extend(tool_results)
                print(f"   messages count after: {len(messages)}")
            
            # ============================================================
            # PHASE 4: GENERATE ANNOTATIONS
            # ============================================================
            annotations = {"arrows": [], "highlights": [], "tags_referenced": []}
            fen = context.get("fen", "")
            
            print(f"🔍 [DOWNSTREAM_FLOW] Generating annotations")
            print(f"   fen: {fen}")
            print(f"   final_content length: {len(final_content)}")
            print(f"   has_cached_analysis: {'cached_analysis' in context}")
            
            if fen and final_content:
                try:
                    cached_analysis = context.get("cached_analysis", {})
                    
                    # Extract tags from pre_executed tool results (especially analyze_move)
                    tool_tags = []
                    if pre_executed_tool_calls:
                        for tc in pre_executed_tool_calls:
                            if tc.get("name") == "analyze_move":
                                result = tc.get("result", {})
                                endpoint_response = result.get("endpoint_response", {})
                                analysis = endpoint_response.get("analysis", {})
                                
                                # Extract tags from all analysis objects
                                for af_key in ["af_starting", "af_played", "af_best", "af_pv_best", "af_pv_played"]:
                                    af_data = analysis.get(af_key, {})
                                    if af_data and isinstance(af_data, dict):
                                        af_tags = af_data.get("tags", [])
                                        if af_tags:
                                            tool_tags.extend(af_tags)
                    
                    # Merge tool tags into cached_analysis for annotation matching
                    if tool_tags:
                        if not isinstance(cached_analysis, dict):
                            cached_analysis = {}
                        else:
                            cached_analysis = cached_analysis.copy()
                        
                        if "tags" not in cached_analysis:
                            cached_analysis["tags"] = []
                        
                        # Add unique tags (avoid duplicates)
                        existing_tag_names = {t.get("name", "") if isinstance(t, dict) else str(t) for t in cached_analysis["tags"]}
                        for tag in tool_tags:
                            tag_name = tag.get("name", "") if isinstance(tag, dict) else str(tag)
                            if tag_name and tag_name not in existing_tag_names:
                                cached_analysis["tags"].append(tag)
                        print(f"🔍 [DOWNSTREAM_FLOW] Added {len(tool_tags)} tags from tool results to cached_analysis")
                        print(f"   Total tags in cached_analysis: {len(cached_analysis.get('tags', []))}")
                    
                    # Extract tags from brackets in final_content
                    from response_annotator import extract_tags_from_brackets
                    cleaned_content, extracted_tags = extract_tags_from_brackets(final_content)
                    
                    # Update final_content to remove tag brackets
                    if extracted_tags:
                        final_content = cleaned_content
                        print(f"🔍 [DOWNSTREAM_FLOW] Extracted tags from response: {extracted_tags}")
                    
                    # Generate annotations (will use extracted_tags if available)
                    annotations = parse_response_for_annotations(
                        cleaned_content, 
                        fen, 
                        cached_analysis,
                        explicit_tags=extracted_tags if extracted_tags else None
                    )
                    print(f"🔍 [DOWNSTREAM_FLOW] Annotations generated")
                    print(f"   annotations (full): {json.dumps(annotations, default=str, indent=2)}")
                    print(f"   highlights count: {len(annotations.get('highlights', []))}")
                    print(f"   arrows count: {len(annotations.get('arrows', []))}")
                except Exception as ann_err:
                    print(f"   Annotation error: {ann_err}")
                    import traceback
                    traceback.print_exc()
            
            # ============================================================
            # PHASE 5: SEND FINAL RESPONSE
            # ============================================================
            print(f"   📤 Preparing to send complete event...")
            print(f"      final_content length: {len(final_content)}")
            print(f"      tool_calls_made: {len(tool_calls_made)}")
            print(f"      iterations: {iterations}")
            print(f"      status_messages: {len(all_status_messages)}")
            
            if not final_content:
                print(f"   ⚠️ WARNING: final_content is empty! This may cause frontend issues.")
                # Set a fallback message if content is empty
                if pre_executed_tool_calls:
                    tool_names = [tc.get("name", "unknown") for tc in pre_executed_tool_calls]
                    final_content = f"I've completed the requested action: {', '.join(tool_names)}. The results are available in the tool output."
                    print(f"   📝 Using fallback content: {final_content[:100]}...")
            
            called_tools = [tc.get("tool", "unknown") for tc in tool_calls_made] if tool_calls_made else []
            
            # Get frontend commands from orchestration plan
            frontend_commands = []
            if orchestration_plan and orchestration_plan.frontend_commands:
                frontend_commands = [cmd.to_dict() for cmd in orchestration_plan.frontend_commands]
            
            print(f"🔍 [DOWNSTREAM_FLOW] Building response_data")
            print(f"   final_content length: {len(final_content)}")
            print(f"   tool_calls_made count: {len(tool_calls_made)}")
            print(f"   iterations: {iterations}")
            print(f"   frontend_commands: {json.dumps(frontend_commands, default=str)}")
            
            response_data = {
                "content": final_content,
                "model": request.model,
                "tool_calls": tool_calls_made,
                "iterations": iterations,
                "status_messages": all_status_messages,
                "annotations": annotations,
                "frontend_commands": frontend_commands
            }
            
            if orchestration_plan:
                response_data["orchestration"] = {
                    "mode": orchestration_plan.mode.value,
                    "mode_confidence": orchestration_plan.mode_confidence,
                    "intent": orchestration_plan.user_intent_summary,
                    "extracted_data": orchestration_plan.extracted_data
                }
                response_data["detected_intent"] = orchestration_plan.user_intent_summary
                planned_tools = [t.name for t in orchestration_plan.tool_sequence] if orchestration_plan.tool_sequence else []
                response_data["tools_used"] = list(set(planned_tools + called_tools))
            else:
                response_data["tools_used"] = called_tools
                response_data["detected_intent"] = None
            
            print(f"   📦 Response data prepared: content={len(final_content)} chars, tools_used={response_data.get('tools_used', [])}")
            
            print(f"🔍 [DOWNSTREAM_FLOW] response_data built")
            # Log response_data but truncate very large fields
            response_data_log = response_data.copy()
            if "tool_calls" in response_data_log:
                for tc in response_data_log["tool_calls"]:
                    if "result" in tc and isinstance(tc["result"], dict):
                        result_str = json.dumps(tc["result"], default=str)
                        if len(result_str) > 2000:
                            tc["result"] = {"_truncated": True, "_size": len(result_str)}
            if "status_messages" in response_data_log and len(response_data_log["status_messages"]) > 20:
                response_data_log["status_messages"] = response_data_log["status_messages"][:20] + [{"_truncated": True, "_total": len(response_data["status_messages"])}]
            print(f"   response_data (summary): {json.dumps(response_data_log, default=str, indent=2)}")
            
            # ============================================================
            # CHUNKED SSE: Send data in parts for large payloads
            # ============================================================
            
            # Check if we have game review data that needs chunking
            has_game_review = False
            game_review_data = None
            for tc in tool_calls_made:
                if isinstance(tc.get("result"), dict) and tc["result"].get("first_game_review"):
                    has_game_review = True
                    game_review_data = tc["result"]
                    break
            
            if has_game_review and game_review_data:
                print(f"   📦 Using chunked SSE for game review data...")
                
                # Part 1: Game data for loading into tab (~5KB)
                first_game = game_review_data.get("first_game", {})
                if first_game:
                    game_loaded_data = {
                        "first_game": first_game,
                        "username": game_review_data.get("username", ""),
                        "platform": game_review_data.get("platform", ""),
                        "games_analyzed": game_review_data.get("games_analyzed", 1)
                    }
                    print(f"   📤 Sending game_loaded event...")
                    yield send_event("game_loaded", game_loaded_data)
                    yield ": keepalive\n\n"
                    await asyncio.sleep(0.05)
                
                # Part 2: Statistics and charts (~30KB)
                stats_data = {
                    "stats": game_review_data.get("stats", {}),
                    "phase_stats": game_review_data.get("phase_stats", {}),
                    "opening_performance": game_review_data.get("opening_performance", []),
                    "charts": game_review_data.get("charts", {}),
                    "loss_diagnosis": game_review_data.get("loss_diagnosis")
                }
                print(f"   📤 Sending stats_ready event...")
                yield send_event("stats_ready", stats_data)
                yield ": keepalive\n\n"
                await asyncio.sleep(0.05)
                
                # Part 3: Narrative text (~3KB)
                narrative_data = {
                    "narrative": game_review_data.get("narrative", "")
                }
                print(f"   📤 Sending narrative event...")
                yield send_event("narrative", narrative_data)
                yield ": keepalive\n\n"
                await asyncio.sleep(0.05)
                
                # Part 4: Key moments for walkthrough - stripped down (~10KB)
                first_game_review = game_review_data.get("first_game_review", {})
                if first_game_review:
                    # Create minimal ply records for walkthrough (just what's needed)
                    minimal_ply_records = []
                    for ply in first_game_review.get("ply_records", []):
                        minimal_ply_records.append({
                            "ply": ply.get("ply"),
                            "san": ply.get("san"),
                            "uci": ply.get("uci"),
                            "side_moved": ply.get("side_moved"),
                            "category": ply.get("category"),
                            "cp_loss": ply.get("cp_loss"),
                            "accuracy_pct": ply.get("accuracy_pct"),
                            "key_point_labels": ply.get("key_point_labels", []),
                            "fen_before": ply.get("fen_before"),
                            "fen_after": ply.get("fen_after"),
                            "phase": ply.get("phase"),
                            "engine": {
                                "best_move_san": ply.get("engine", {}).get("best_move_san"),
                                "eval_before_str": ply.get("engine", {}).get("eval_before_str"),
                                "played_eval_after_str": ply.get("engine", {}).get("played_eval_after_str")
                            }
                        })
                    
                    walkthrough_data = {
                        "ply_records": minimal_ply_records,
                        "key_points": first_game_review.get("key_points", [])[:20],  # Limit to 20
                        "selected_key_moments": game_review_data.get("selected_key_moments", []),
                        "selection_rationale": game_review_data.get("selection_rationale", {}),
                        "pre_commentary_by_ply": game_review_data.get("pre_commentary_by_ply", {}),
                        "opening": first_game_review.get("opening", {}),
                        "game_metadata": first_game_review.get("game_metadata", {}),
                        "stats": first_game_review.get("stats", {})
                    }
                    # Calculate size for debugging
                    walkthrough_size = len(json.dumps(walkthrough_data, default=str))
                    print(f"   📤 Sending walkthrough_data event ({len(minimal_ply_records)} plies, {walkthrough_size/1024:.1f} KB)...")
                    yield send_event("walkthrough_data", walkthrough_data)
                    yield ": keepalive\n\n"
                    await asyncio.sleep(0.1)  # Longer delay for large event
                
                # Part 5: Final complete event - minimal data
                # Strip game review data from tool_calls_made since it was sent in chunks
                for tc in tool_calls_made:
                    if isinstance(tc.get("result"), dict):
                        # Remove heavy data that was already sent
                        tc["result"] = {
                            "success": tc["result"].get("success", True),
                            "username": tc["result"].get("username"),
                            "platform": tc["result"].get("platform"),
                            "games_analyzed": tc["result"].get("games_analyzed"),
                            "_chunked": True,
                            "_note": "Full data sent via chunked SSE events"
                        }
                
                response_data["tool_calls"] = tool_calls_made
                print(f"   📤 Sending final complete event (minimal)...")
                
            else:
                print(f"   📤 Using standard complete event (no game review)...")
            
            # Diagnostic: Calculate final size
            import sys
            def get_size_mb(obj):
                """Get approximate size of object in MB"""
                try:
                    return sys.getsizeof(json.dumps(obj, default=str)) / 1024 / 1024
                except:
                    return 0
            
            total_size = get_size_mb(response_data)
            print(f"   📊 Final complete event size: {total_size:.2f} MB")
            if total_size > 0.5:
                print(f"   ⚠️ WARNING: Complete event still large ({total_size:.2f}MB)")
            
            # Validate response_data is JSON-serializable before sending
            try:
                json.dumps(response_data, default=str)
                print(f"   ✅ Response data is JSON-serializable")
            except Exception as json_err:
                print(f"   ❌ Response data JSON serialization failed: {json_err}")
                import traceback
                traceback.print_exc()
                response_data = {
                    "content": final_content or "Error: Could not serialize response",
                    "error": "JSON serialization failed",
                    "tools_used": response_data.get('tools_used', [])
                }
            
            print(f"   🚀 Sending complete event...")
            
            print(f"🔍 [DOWNSTREAM_FLOW] Sending complete event")
            print(f"   event_type: complete")
            response_data_size = len(json.dumps(response_data, default=str))
            print(f"   response_data size: {response_data_size} bytes ({response_data_size/1024:.2f} KB)")
            print(f"   final_content: {final_content[:500]}..." if len(final_content) > 500 else f"   final_content: {final_content}")
            
            try:
                event_str = send_event("complete", response_data)
                print(f"   📤 Complete event string length: {len(event_str)}")
                yield event_str
                yield ": keepalive\n\n"
                await asyncio.sleep(0.2)
                print(f"   ✅ Complete event sent and flushed successfully")
            except Exception as send_err:
                print(f"   ❌ Failed to send complete event: {send_err}")
                import traceback
                error_tb = traceback.format_exc()
                traceback.print_exc()
                try:
                    yield send_event("error", {
                        "message": f"Failed to send complete event: {send_err}",
                        "traceback": error_tb
                    })
                    await asyncio.sleep(0.1)
                except:
                    pass
                raise
            
        except Exception as e:
            import traceback
            error_msg = str(e)
            error_tb = traceback.format_exc()
            print(f"   ❌ SSE stream error: {error_msg}")
            print(f"   Traceback: {error_tb}")
            
            try:
                yield send_event("error", {
                    "message": error_msg,
                    "traceback": error_tb
                })
            except (BrokenPipeError, ConnectionResetError) as pipe_err:
                # Client disconnected - log and exit gracefully
                print(f"   ⚠️ Client disconnected during error response: {pipe_err}")
    
    async def safe_event_generator():
        """Wrapper to handle broken pipe errors gracefully"""
        complete_sent = False
        
        # Helper function for error events (defined here since send_event is in event_generator scope)
        def send_error_event(msg: str, tb: str = ""):
            return f"event: error\ndata: {json.dumps({'message': msg, 'traceback': tb})}\n\n"
        
        try:
            async for event in event_generator():
                try:
                    yield event
                    # Check if this was a complete event
                    if isinstance(event, str) and "event: complete" in event:
                        complete_sent = True
                        print(f"   ✅ Complete event yielded in safe wrapper")
                except (BrokenPipeError, ConnectionResetError) as e:
                    print(f"   ⚠️ Client disconnected while sending event: {e}")
                    break
        except (BrokenPipeError, ConnectionResetError) as e:
            print(f"   ⚠️ Client disconnected during stream: {e}")
            if not complete_sent:
                print(f"   ⚠️ WARNING: Stream closed before complete event was sent")
        except Exception as e:
            print(f"   ❌ Unexpected error in SSE stream: {e}")
            import traceback
            error_tb = traceback.format_exc()
            traceback.print_exc()
            if not complete_sent:
                print(f"   ⚠️ WARNING: Exception occurred before complete event was sent")
                # Try to send error event
                try:
                    yield send_error_event(f"Stream error: {str(e)}", error_tb)
                    await asyncio.sleep(0.1)
                except:
                    pass
    
    return StreamingResponse(
        safe_event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


# ============================================================================
# LESSON SYSTEM - Universal Detectors & Topic Registry
# ============================================================================

# Pawn structure detectors
def locked_center(board: chess.Board) -> bool:
    """Detect locked center (e4/d5 or d4/e5)"""
    e4 = board.piece_at(chess.E4)
    d5 = board.piece_at(chess.D5)
    d4 = board.piece_at(chess.D4)
    e5 = board.piece_at(chess.E5)
    
    return (e4 and e4.piece_type == chess.PAWN and e4.color == chess.WHITE and
            d5 and d5.piece_type == chess.PAWN and d5.color == chess.BLACK) or \
           (d4 and d4.piece_type == chess.PAWN and d4.color == chess.WHITE and
            e5 and e5.piece_type == chess.PAWN and e5.color == chess.BLACK)

def open_center(board: chess.Board) -> bool:
    """Detect open center (no pawns on d4, d5, e4, e5)"""
    central_squares = [chess.D4, chess.D5, chess.E4, chess.E5]
    for sq in central_squares:
        piece = board.piece_at(sq)
        if piece and piece.piece_type == chess.PAWN:
            return False
    return True

def isolated_pawn(board: chess.Board, file_idx: int, color: chess.Color) -> bool:
    """Detect isolated pawn on given file"""
    # Check if any pawns exist on this file
    has_pawn_on_file = False
    for rank in range(8):
        sq = chess.square(file_idx, rank)
        piece = board.piece_at(sq)
        if piece and piece.piece_type == chess.PAWN and piece.color == color:
            has_pawn_on_file = True
            break
    
    if not has_pawn_on_file:
        return False
    
    # Check adjacent files
    for adj_file in [file_idx - 1, file_idx + 1]:
        if 0 <= adj_file < 8:
            for rank in range(8):
                sq = chess.square(adj_file, rank)
                piece = board.piece_at(sq)
                if piece and piece.piece_type == chess.PAWN and piece.color == color:
                    return False
    
    return True

def iqp(board: chess.Board, color: chess.Color) -> bool:
    """Detect isolated queen's pawn (d4 or d5)"""
    d_file = 3  # D file
    return isolated_pawn(board, d_file, color)

def hanging_pawns(board: chess.Board, color: chess.Color) -> bool:
    """Detect hanging pawns on c and d files"""
    c_file, d_file = 2, 3
    rank = 3 if color == chess.WHITE else 4  # 4th rank for white, 5th for black
    
    c_sq = chess.square(c_file, rank)
    d_sq = chess.square(d_file, rank)
    
    c_piece = board.piece_at(c_sq)
    d_piece = board.piece_at(d_sq)
    
    # Must have pawns on both c and d
    if not (c_piece and c_piece.piece_type == chess.PAWN and c_piece.color == color):
        return False
    if not (d_piece and d_piece.piece_type == chess.PAWN and d_piece.color == color):
        return False
    
    # Must NOT have pawns on b and e files (isolated pair)
    return isolated_pawn(board, 1, color) or isolated_pawn(board, 4, color)

def carlsbad(board: chess.Board, color: chess.Color) -> bool:
    """Detect Carlsbad structure (c4/d4 vs c6/d5 for white)"""
    if color == chess.WHITE:
        # White: c4, d4  Black: c6, d5
        c4 = board.piece_at(chess.C4)
        d4 = board.piece_at(chess.D4)
        c6 = board.piece_at(chess.C6)
        d5 = board.piece_at(chess.D5)
        
        return (c4 and c4.piece_type == chess.PAWN and c4.color == chess.WHITE and
                d4 and d4.piece_type == chess.PAWN and d4.color == chess.WHITE and
                c6 and c6.piece_type == chess.PAWN and c6.color == chess.BLACK and
                d5 and d5.piece_type == chess.PAWN and d5.color == chess.BLACK)
    return False

def maroczy(board: chess.Board, color: chess.Color) -> bool:
    """Detect Maróczy Bind (c4/e4 structure)"""
    if color == chess.WHITE:
        c4 = board.piece_at(chess.C4)
        e4 = board.piece_at(chess.E4)
        return (c4 and c4.piece_type == chess.PAWN and c4.color == chess.WHITE and
                e4 and e4.piece_type == chess.PAWN and e4.color == chess.WHITE)
    return False

# King safety detectors
def king_ring_pressure(board: chess.Board, color: chess.Color) -> int:
    """Count enemy pieces attacking king ring"""
    king_sq = board.king(color)
    if not king_sq:
        return 0
    
    king_rank = chess.square_rank(king_sq)
    king_file = chess.square_file(king_sq)
    
    pressure = 0
    enemy_color = not color
    
    # Check 3x3 ring around king
    for dr in [-1, 0, 1]:
        for df in [-1, 0, 1]:
            if dr == 0 and df == 0:
                continue
            r, f = king_rank + dr, king_file + df
            if 0 <= r < 8 and 0 <= f < 8:
                sq = chess.square(f, r)
                # Count enemy attackers to this square
                attackers = board.attackers(enemy_color, sq)
                pressure += len(attackers)
    
    return pressure

# Piece quality detectors
def outpost(board: chess.Board, sq: chess.Square, color: chess.Color) -> bool:
    """Detect if square is a good outpost for given color"""
    rank = chess.square_rank(sq)
    file_idx = chess.square_file(sq)
    
    # Outpost should be in opponent territory
    if color == chess.WHITE and rank < 4:
        return False
    if color == chess.BLACK and rank > 3:
        return False
    
    # Check if protected by friendly pawn
    protected_by_pawn = False
    pawn_rank = rank - 1 if color == chess.WHITE else rank + 1
    for pawn_file in [file_idx - 1, file_idx + 1]:
        if 0 <= pawn_file < 8:
            pawn_sq = chess.square(pawn_file, pawn_rank)
            piece = board.piece_at(pawn_sq)
            if piece and piece.piece_type == chess.PAWN and piece.color == color:
                protected_by_pawn = True
                break
    
    if not protected_by_pawn:
        return False
    
    # Check if enemy pawns can attack it
    enemy_color = not color
    enemy_pawn_rank = rank + 1 if color == chess.WHITE else rank - 1
    for enemy_file in [file_idx - 1, file_idx + 1]:
        if 0 <= enemy_file < 8 and 0 <= enemy_pawn_rank < 8:
            enemy_sq = chess.square(enemy_file, enemy_pawn_rank)
            piece = board.piece_at(enemy_sq)
            if piece and piece.piece_type == chess.PAWN and piece.color == enemy_color:
                return False
    
    return True

def rook_on_open_file(board: chess.Board, color: chess.Color) -> bool:
    """Detect if color has rook on open file"""
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece and piece.piece_type == chess.ROOK and piece.color == color:
            file_idx = chess.square_file(sq)
            # Check if file is open (no pawns)
            is_open = True
            for rank in range(8):
                check_sq = chess.square(file_idx, rank)
                check_piece = board.piece_at(check_sq)
                if check_piece and check_piece.piece_type == chess.PAWN:
                    is_open = False
                    break
            if is_open:
                return True
    return False

def seventh_rank_rook(board: chess.Board, color: chess.Color) -> bool:
    """Detect if color has rook on 7th rank"""
    rank = 6 if color == chess.WHITE else 1
    for file_idx in range(8):
        sq = chess.square(file_idx, rank)
        piece = board.piece_at(sq)
        if piece and piece.piece_type == chess.ROOK and piece.color == color:
            return True
    return False

# Lesson topic registry
LESSON_TOPICS = {
    # Pawn structures
    "PS.CARLSBAD": {
        "name": "Carlsbad: Minority Attack",
        "detector": "carlsbad",
        "goals": ["Create c6 weakness", "Double on c-file", "Execute b4-b5"],
        "difficulty": "1200-1800",
        "category": "pawn_structures"
    },
    "PS.IQP": {
        "name": "Isolated Queen's Pawn",
        "detector": "iqp",
        "goals": ["Play e5 break", "Active pieces", "Blockade d-pawn"],
        "difficulty": "1300-1900",
        "category": "pawn_structures"
    },
    "PS.HANGING": {
        "name": "Hanging Pawns",
        "detector": "hanging_pawns",
        "goals": ["Push for space", "Avoid exchanges", "Watch undermines"],
        "difficulty": "1400-2000",
        "category": "pawn_structures"
    },
    "PS.MARO": {
        "name": "Maróczy Bind",
        "detector": "maroczy",
        "goals": ["Restrict d5/b5", "Squeeze d-file", "Maintain bind"],
        "difficulty": "1500-2100",
        "category": "pawn_structures"
    },
    
    # Strategic themes
    "ST.OUTPOST": {
        "name": "Knight Outposts",
        "detector": "outpost",
        "goals": ["Establish outpost", "Support with pawns", "Dominate squares"],
        "difficulty": "1200-1800",
        "category": "strategy"
    },
    "ST.OPEN_FILE": {
        "name": "Open File Control",
        "detector": "rook_on_open_file",
        "goals": ["Double rooks", "Invade 7th rank", "Control file"],
        "difficulty": "1100-1700",
        "category": "strategy"
    },
    "ST.SEVENTH_RANK": {
        "name": "Seventh Rank",
        "detector": "seventh_rank_rook",
        "goals": ["Reach 7th rank", "Attack pawns", "Restrict king"],
        "difficulty": "1200-1800",
        "category": "strategy"
    },
    
    # King safety
    "KA.KING_RING": {
        "name": "King Ring Pressure",
        "detector": "king_ring_pressure",
        "goals": ["Attack king zone", "Create weaknesses", "Accumulate attackers"],
        "difficulty": "1300-2000",
        "category": "attack"
    },
    
    # Tactical motifs
    "TM.FORK": {
        "name": "Knight Fork",
        "detector": "fork",
        "goals": ["Attack two pieces", "Win material", "Force responses"],
        "difficulty": "900-1400",
        "category": "tactics"
    },
    "TM.PIN": {
        "name": "Pin Tactics",
        "detector": "pin",
        "goals": ["Immobilize piece", "Win material", "Create threats"],
        "difficulty": "900-1400",
        "category": "tactics"
    },
    "TM.SKEWER": {
        "name": "Skewer",
        "detector": "skewer",
        "goals": ["Force piece move", "Win material", "Reverse pin"],
        "difficulty": "1000-1500",
        "category": "tactics"
    },
}

class LessonRequest(BaseModel):
    description: str
    target_level: Optional[int] = 1500
    count: Optional[int] = 5

class LessonItem(BaseModel):
    fen: str
    side: str  # "white" or "black"
    objective: str
    themes: List[str]
    candidates: List[Dict[str, Any]]
    pv_san: str
    hints: List[str]
    difficulty: str

class LessonPlan(BaseModel):
    title: str
    description: str
    sections: List[Dict[str, Any]]
    total_positions: int

@app.post("/generate_lesson")
async def generate_lesson(request: LessonRequest):
    """Generate a custom lesson based on user description"""
    try:
        # Use LLM to parse user's lesson description and select topics
        prompt = f"""Given this lesson request: "{request.description}"
        
Target level: {request.target_level}

Available topics:
{json.dumps({k: v['name'] for k, v in LESSON_TOPICS.items()}, indent=2)}

Create a lesson plan with 3-5 sections. For each section:
1. Choose 1-2 relevant topic codes
2. Write a brief section title and goal
3. Suggest 2-3 positions to generate per topic

Return JSON:
{{
  "title": "lesson title",
  "description": "what they'll learn",
  "sections": [
    {{
      "title": "section name",
      "topics": ["PS.CARLSBAD"],
      "goal": "what to learn",
      "positions_per_topic": 2
    }}
  ]
}}"""

        # Call LLM
        response = openai_client.chat.completions.create(
            model="gpt-5-mini",
            messages=[
                {"role": "system", "content": "You are a chess lesson planner. Return valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        
        plan_text = response.choices[0].message.content.strip()
        
        # Remove markdown code blocks if present
        if plan_text.startswith("```"):
            plan_text = plan_text.split("```")[1]
            if plan_text.startswith("json"):
                plan_text = plan_text[4:]
            plan_text = plan_text.strip()
        
        plan_data = json.loads(plan_text)
        
        # For now, return the plan structure
        # Full position generation will be implemented in next phase
        total_positions = sum(
            section.get("positions_per_topic", 2) * len(section.get("topics", []))
            for section in plan_data.get("sections", [])
        )
        
        return {
            "title": plan_data.get("title", "Custom Lesson"),
            "description": plan_data.get("description", ""),
            "sections": plan_data.get("sections", []),
            "total_positions": total_positions,
            "status": "plan_ready"
        }
        
    except Exception as e:
        import traceback
        error_detail = f"Lesson generation error: {str(e)}\n{traceback.format_exc()}"
        print(error_detail)
        raise HTTPException(status_code=500, detail=f"Failed to generate lesson: {str(e)}")

@app.get("/topics")
async def get_topics(category: Optional[str] = None, level: Optional[int] = None):
    """Get available lesson topics"""
    topics = LESSON_TOPICS.copy()
    
    if category:
        topics = {k: v for k, v in topics.items() if v["category"] == category}
    
    if level:
        # Filter by difficulty range
        filtered = {}
        for k, v in topics.items():
            diff_range = v["difficulty"]
            low, high = map(int, diff_range.split("-"))
            if low <= level <= high + 200:  # Allow some overlap
                filtered[k] = v
        topics = filtered
    
    return {
        "topics": topics,
        "categories": list(set(v["category"] for v in LESSON_TOPICS.values()))
    }


def parse_difficulty_level(difficulty_range: str) -> str:
    """Parse difficulty range string to level category."""
    try:
        low, high = map(int, difficulty_range.split("-"))
        avg = (low + high) / 2
        
        if avg < 1200:
            return "beginner"
        elif avg < 1600:
            return "intermediate"
        else:
            return "advanced"
    except:
        return "intermediate"  # Default


async def generate_position_for_topic(topic_code: str, side: str = "white") -> Dict[str, Any]:
    """
    Generate a training position for a specific topic.
    
    Uses pre-generated positions if available, otherwise falls back to live generation.
    """
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not available")
    
    topic = LESSON_TOPICS.get(topic_code)
    if not topic:
        raise HTTPException(status_code=404, detail=f"Topic {topic_code} not found")
    
    # Try pre-generated positions first (instant)
    if topic_code in PRE_GENERATED_POSITIONS and PRE_GENERATED_POSITIONS[topic_code]:
        import random
        
        # Random selection from pre-generated pool
        position_data = random.choice(PRE_GENERATED_POSITIONS[topic_code])
        
        # Add metadata
        full_position = {
            "fen": position_data["fen"],
            "side": side,
            "objective": topic.get("goals", ["Practice this concept"])[0],
            "themes": [topic_code],
            "candidates": [],
            "hints": [f"Focus on: {goal}" for goal in topic.get('goals', [])[:2]],
            "difficulty": topic.get("difficulty", "1200-1800"),
            "topic_name": topic.get("name", "Chess Concept"),
            "ideal_line": position_data.get("ideal_line", []),
            "ideal_pgn": " ".join(position_data.get("ideal_line", [])),
            "meta": {"pre_generated": True, "source": "retrograde_backtracking"}
        }
        
        return full_position
    
    # Fall back to live generation (slower, less reliable)
    print(f"⚠️  No pre-generated positions for {topic_code}, attempting live generation...")
    
    # Parse difficulty from topic metadata
    difficulty_range = topic.get("difficulty", "1200-1800")
    difficulty_level = parse_difficulty_level(difficulty_range)
    
    # Try cache
    try:
        cached = await position_cache.get_position(topic_code, side, difficulty_level)
        if cached:
            return cached
    except Exception as e:
        print(f"Cache error: {e}")
    
    # Live generation (last resort)
    import time
    start = time.time()
    
    position_data = await generate_fen_for_topic(
        topic_code=topic_code,
        side_to_move=side,
        difficulty=difficulty_level,
        engine=engine,
        time_budget_ms=3000
    )
    
    generation_time = (time.time() - start) * 1000
    print(f"✅ Generated position for {topic_code} in {generation_time:.0f}ms")
    
    # Store in cache
    try:
        await position_cache.store_position(topic_code, side, difficulty_level, position_data)
    except Exception as e:
        print(f"Cache store error: {e}")
    
    return position_data

@app.post("/generate_positions")
async def generate_positions(topic_code: str = Query(...), count: int = Query(3, ge=1, le=10)):
    """Generate multiple training positions for a topic"""
    positions = []
    
    for i in range(count):
        try:
            pos = await generate_position_for_topic(topic_code, "white" if i % 2 == 0 else "black")
            positions.append(pos)
        except Exception as e:
            import traceback
            print(f"Failed to generate position {i+1}: {traceback.format_exc()}")
            # If we fail on the first position, raise error (don't return empty)
            if i == 0:
                raise HTTPException(status_code=500, detail=f"Failed to generate positions: {str(e)}")
            continue
    
    if len(positions) == 0:
        raise HTTPException(status_code=500, detail="No positions could be generated")
    
    return {
        "topic_code": topic_code,
        "positions": positions,
        "count": len(positions)
    }

@app.post("/check_lesson_move")
async def check_lesson_move(
    fen: str = Query(...),
    move_san: str = Query(...),
    expected_themes: List[str] = Query([])
):
    """Check if a move in a lesson is correct and provide feedback"""
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not available")
    
    try:
        board = chess.Board(fen)
        
        # Parse the move
        try:
            move = board.parse_san(move_san)
        except:
            return {
                "correct": False,
                "feedback": "Invalid move notation",
                "suggestion": None
            }
        
        if move not in board.legal_moves:
            return {
                "correct": False,
                "feedback": "This move is not legal in the current position",
                "suggestion": None
            }
        
        # Get best moves
        main_info = await engine_queue.enqueue(engine_queue.engine.analyse, board, chess.engine.Limit(depth=16), multipv=3)
        
        best_moves = []
        best_eval = None
        
        if hasattr(main_info, '__iter__'):
            for i, info in enumerate(main_info[:3]):
                pv = info.get("pv", [])
                if pv:
                    m = pv[0]
                    score = info.get("score")
                    eval_cp = score.relative.score(mate_score=10000) if score else 0
                    
                    if i == 0:
                        best_eval = eval_cp
                    
                    best_moves.append({
                        "move": board.san(m),
                        "uci": m.uci(),
                        "eval_cp": eval_cp
                    })
        
        # Check if player's move matches one of the top moves
        player_move_uci = move.uci()
        
        # Calculate eval after player's move
        board.push(move)
        after_info = await engine_queue.enqueue(engine_queue.engine.analyse, board, chess.engine.Limit(depth=14))
        after_score = after_info.get("score")
        player_eval = -after_score.relative.score(mate_score=10000) if after_score else 0
        board.pop()
        
        # Determine correctness
        is_best = any(m["uci"] == player_move_uci for m in best_moves[:1])
        is_good = any(m["uci"] == player_move_uci for m in best_moves[:2])
        
        cp_loss = best_eval - player_eval if best_eval is not None else 0
        
        if is_best:
            feedback = f"Excellent! This is the best move. {move_san} achieves the lesson objective perfectly."
            correct = True
        elif is_good and cp_loss < 30:
            feedback = f"Good move! {move_san} is one of the top choices, losing only {cp_loss}cp compared to the best move."
            correct = True
        elif cp_loss < 50:
            feedback = f"Reasonable move, but not optimal. You lose {cp_loss}cp. The best move was {best_moves[0]['move']}."
            correct = False
        elif cp_loss < 100:
            feedback = f"Inaccuracy! This loses {cp_loss}cp. Consider {best_moves[0]['move']} instead."
            correct = False
        else:
            feedback = f"This is a mistake, losing {cp_loss}cp. The best move was {best_moves[0]['move']}."
            correct = False
        
        return {
            "correct": correct,
            "feedback": feedback,
            "best_move": best_moves[0]["move"] if best_moves else None,
            "cp_loss": cp_loss,
            "alternatives": [m["move"] for m in best_moves[1:3]]
        }
        
    except Exception as e:
        import traceback
        error_detail = f"Move check error: {str(e)}\n{traceback.format_exc()}"
        print(error_detail)
        raise HTTPException(status_code=500, detail=f"Failed to check move: {str(e)}")


async def _generate_opening_lesson_internal(request_data: Dict[str, Any]) -> Dict[str, Any]:
    """Shared helper for tool calls and REST endpoint."""
    if not explorer_client:
        raise HTTPException(status_code=503, detail="Opening explorer not initialized")
    if not profile_indexer:
        raise HTTPException(status_code=503, detail="Profile indexer unavailable")

    payload = {
        "user_id": request_data.get("user_id"),
        "chat_id": request_data.get("chat_id"),
        "opening_query": request_data.get("opening_query"),
        "fen": request_data.get("fen"),
        "eco": request_data.get("eco"),
        "orientation": request_data.get("orientation"),
        "variation_hint": request_data.get("variation_hint"),
    }
    response = await create_opening_lesson_payload(
        payload,
        explorer_client=explorer_client,
        profile_indexer=profile_indexer,
        supabase_client=supabase_client,
        engine_queue=engine_queue,
    )
    
    # Persist canonical lesson snapshot so `/check_opening_move` can reference it
    lesson_plan = response.get("canonical_plan")
    if lesson_plan:
        # Ensure we have a lesson_id
        lesson_id = (
            lesson_plan.get("lesson_id")
            or response.get("metadata", {}).get("lesson_id")
            or uuid.uuid4().hex[:12]
        )
        lesson_plan["lesson_id"] = lesson_id
        response.setdefault("metadata", {})["lesson_id"] = lesson_id
        
        backend_dir = os.path.dirname(os.path.abspath(__file__))
        lessons_dir = os.path.join(backend_dir, "opening_lessons")
        os.makedirs(lessons_dir, exist_ok=True)
        snapshot_path = os.path.join(lessons_dir, f"{lesson_id}.json")
        try:
            with open(snapshot_path, "w") as f:
                json.dump(lesson_plan, f, indent=2)
        except Exception as exc:
            print(f"⚠️ Failed to persist opening lesson snapshot: {exc}")
    
    return response


@app.post("/generate_opening_lesson")
async def generate_opening_lesson(request: dict):
    """
    Generate an opening lesson from a query.
    
    Input: {"query": "Sicilian Najdorf", "db": "lichess"?, "rating_range": [1600, 2000]?}
    Output: LessonPlan JSON with sections/checkpoints/practice_fens
    """
    if not explorer_client:
        raise HTTPException(status_code=500, detail="Explorer client not initialized")
    
    try:
        query = request.get("query", "")
        if not query:
            raise HTTPException(status_code=400, detail="Query is required")
        
        db = request.get("db", "lichess")
        rating_range = tuple(request.get("rating_range", [1600, 2000]))
        
        # Build lesson plan
        lesson_plan = await build_opening_lesson(
            opening_query=query,
            explorer=explorer_client,
            db=db,
            rating_range=rating_range
        )
        
        # Store lesson snapshot
        lesson_id = lesson_plan["lesson_id"]
        backend_dir = os.path.dirname(os.path.abspath(__file__))
        lessons_dir = os.path.join(backend_dir, "opening_lessons")
        os.makedirs(lessons_dir, exist_ok=True)
        snapshot_path = os.path.join(lessons_dir, f"{lesson_id}.json")
        
        with open(snapshot_path, "w") as f:
            json.dump(lesson_plan, f, indent=2)
        
        print(f"✅ Generated opening lesson '{lesson_plan['title']}' with {lesson_plan['practice_count']} checkpoints")
        
        return lesson_plan
    
    except Exception as e:
        import traceback
        error_detail = f"Lesson generation error: {str(e)}\n{traceback.format_exc()}"
        print(error_detail)
        raise HTTPException(status_code=500, detail=f"Failed to generate opening lesson: {str(e)}")


@app.post("/lessons/opening")
async def create_personalized_opening_lesson(request: OpeningLessonRequest):
    """Generate a personalized opening lesson that blends explorer data with user history."""
    try:
        return await _generate_opening_lesson_internal(request.dict())
    except HTTPException:
        raise
    except Exception as exc:
        print(f"Opening lesson generation failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/generate_confidence_lesson")
async def generate_confidence_lesson(request: dict):
    """
    Generate a mini lesson from confidence tree data.
    
    Request body:
    {
        "nodes": [...],  # List of node dictionaries from confidence tree
        "baseline": 80,  # Optional, default 80
    }
    
    Returns lesson plan compatible with existing lesson system.
    """
    try:
        from lesson_generator import generate_confidence_lesson
        from tag_analyzer import track_tag_across_branches
        from confidence_engine import NodeState
        
        nodes_data = request.get("nodes", [])
        baseline = request.get("baseline", 80)
        
        if not nodes_data:
            raise HTTPException(status_code=400, detail="No nodes provided")
        
        # Convert node dictionaries to NodeState objects
        # We need to reconstruct NodeState from the payload
        nodes = []
        for node_data in nodes_data:
            # Create a minimal NodeState-like object
            # The lesson generator only needs basic attributes
            class NodeWrapper:
                def __init__(self, data):
                    self.id = data.get("id", "")
                    self.parent_id = data.get("parent_id")
                    self.role = data.get("role", "")
                    self.ply_index = data.get("ply_index", 0)
                    self.confidence = data.get("ConfidencePercent", 0)
                    self.frozen_confidence = data.get("frozen_confidence")
                    self.has_branches = data.get("has_branches", False)
                    self.fen = data.get("fen", "")
                    self.move = data.get("move")
                    self.metadata = data.get("metadata", {})
                    self.shape = data.get("shape", "circle")
                    self.color = data.get("color", "red")
            
            nodes.append(NodeWrapper(node_data))
        
        # Generate lesson
        lesson_plan = await generate_confidence_lesson(nodes, baseline=baseline)
        
        # Save lesson snapshot (optional, for consistency with other lesson types)
        lessons_dir = os.path.join(os.path.dirname(__file__), "confidence_lessons")
        os.makedirs(lessons_dir, exist_ok=True)
        import uuid
        lesson_id = str(uuid.uuid4())
        snapshot_path = os.path.join(lessons_dir, f"{lesson_id}.json")
        
        with open(snapshot_path, "w") as f:
            json.dump({**lesson_plan, "lesson_id": lesson_id}, f, indent=2)
        
        return {**lesson_plan, "lesson_id": lesson_id}
    
    except Exception as e:
        import traceback
        error_detail = f"Confidence lesson generation error: {str(e)}\n{traceback.format_exc()}"
        print(error_detail)
        raise HTTPException(status_code=500, detail=f"Failed to generate confidence lesson: {str(e)}")


@app.post("/check_opening_move")
async def check_opening_move(fen: str, move_san: str, lesson_id: str):
    """
    Check if a move is popular/valid in an opening lesson context.
    
    Input: FEN, move SAN, lesson ID
    Output: {"correct": bool, "is_popular": bool, "popularity": float, 
             "feedback": str, "popular_alternatives": List[Dict]}
    """
    if not explorer_client:
        raise HTTPException(status_code=500, detail="Explorer client not initialized")
    
    try:
        # Load lesson snapshot
        backend_dir = os.path.dirname(os.path.abspath(__file__))
        lessons_dir = os.path.join(backend_dir, "opening_lessons")
        snapshot_path = os.path.join(lessons_dir, f"{lesson_id}.json")
        
        if not os.path.exists(snapshot_path):
            raise HTTPException(status_code=404, detail="Lesson not found")
        
        with open(snapshot_path, "r") as f:
            lesson_plan = json.load(f)
        
        # Query explorer for current position
        meta = lesson_plan.get("meta", {})
        db = meta.get("db", "lichess")
        rating_range = meta.get("rating_range", [1600, 2000])
        
        explorer_data = await explorer_client.query_position(
            fen=fen,
            db=db,
            ratings=rating_range
        )
        
        total_games = explorer_data.get("white", 0) + explorer_data.get("draws", 0) + explorer_data.get("black", 0)
        
        if total_games == 0:
            return {
                "correct": True,
                "is_popular": True,
                "popularity": 0.0,
                "feedback": "Position not in database, allowing move",
                "popular_alternatives": []
            }
        
        # Find player's move in explorer data
        moves = explorer_data.get("moves", [])
        player_move = None
        player_games = 0
        
        for move in moves:
            if move.get("san") == move_san:
                player_move = move
                player_games = move.get("white", 0) + move.get("draws", 0) + move.get("black", 0)
                break
        
        if not player_move:
            # Move not in database at all
            popularity = 0.0
        else:
            popularity = player_games / total_games
        
        # Get top popular moves
        move_popularities = []
        for move in moves:
            games = move.get("white", 0) + move.get("draws", 0) + move.get("black", 0)
            pop = games / total_games
            move_popularities.append((move, pop, games))
        
        move_popularities.sort(key=lambda x: x[1], reverse=True)
        
        # Check if move is in top 2 (popular enough)
        is_popular = False
        top_moves = [m[0]["san"] for m in move_popularities[:2]]
        
        if move_san in top_moves:
            is_popular = True
        
        # Get alternatives
        popular_alternatives = []
        for move_data, pop, games in move_popularities[:4]:
            if move_data["san"] != move_san:
                popular_alternatives.append({
                    "san": move_data["san"],
                    "pop": pop,
                    "games": games
                })
        
        # Generate feedback
        if is_popular:
            feedback = f"Good! {move_san} is a popular choice ({popularity*100:.0f}% of games)"
        else:
            feedback = f"{move_san} is uncommon ({popularity*100:.1f}% of games)"
            if popular_alternatives:
                top_alt = popular_alternatives[0]
                feedback += f". Most popular: {top_alt['san']} ({top_alt['pop']*100:.0f}%)"
        
        return {
            "correct": is_popular,
            "is_popular": is_popular,
            "popularity": popularity,
            "feedback": feedback,
            "popular_alternatives": popular_alternatives
        }
    
    except Exception as e:
        import traceback
        error_detail = f"Opening move check error: {str(e)}\n{traceback.format_exc()}"
        print(error_detail)
        raise HTTPException(status_code=500, detail=f"Failed to check opening move: {str(e)}")


# ============================================================================
# PERSONAL REVIEW SYSTEM ENDPOINTS
# ============================================================================

class FetchGamesRequest(BaseModel):
    username: str
    platform: str = "chess.com"  # "chess.com", "lichess", or "combined"
    max_games: int = 100
    months_back: int = 6
    use_cache: bool = True


@app.post("/fetch_player_games")
async def fetch_player_games(request: FetchGamesRequest):
    """Fetch games for a player from Chess.com or Lichess"""
    if not game_fetcher:
        raise HTTPException(status_code=503, detail="Game fetcher not initialized")
    
    try:
        print(f"🎯 Fetching games for {request.username} from {request.platform}")
        
        # Try cache first
        if request.use_cache:
            cached_games = game_fetcher.load_cached_games(request.username, request.platform)
            if cached_games:
                return {
                    "games": cached_games,
                    "count": len(cached_games),
                    "cached": True
                }
        
        # Fetch fresh games
        games = await game_fetcher.fetch_games(
            username=request.username,
            platform=request.platform,
            max_games=request.max_games,
            months_back=request.months_back
        )
        
        # Cache the results
        game_fetcher.cache_games(request.username, request.platform, games)
        
        print(f"✅ Fetched {len(games)} games")
        
        return {
            "games": games,
            "count": len(games),
            "cached": False
        }
    
    except Exception as e:
        import traceback
        error_detail = f"Fetch games error: {str(e)}\n{traceback.format_exc()}"
        print(error_detail)
        raise HTTPException(status_code=500, detail=f"Failed to fetch games: {str(e)}")


class ProfileAccountPayload(BaseModel):
    platform: Literal["chess.com", "lichess", "chesscom"] = "chess.com"
    username: str = Field(..., min_length=1)


class ProfilePreferencesPayload(BaseModel):
    user_id: str = Field(..., min_length=1)
    accounts: List[ProfileAccountPayload]
    time_controls: List[str] = Field(default_factory=list)


def _default_profile_status() -> Dict[str, Any]:
    return {
        "state": "idle",
        "message": "Not started",
        "total_accounts": 0,
        "completed_accounts": 0,
        "total_games_estimate": 0,
        "games_indexed": 0,
        "progress_percent": 0,
        "started_at": None,
        "finished_at": None,
        "last_updated": None,
        "last_error": None,
        "accounts": [],
    }


def _profile_overview_payload(user_id: str, prefs_override: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if not profile_indexer:
        return {
            "preferences": prefs_override or {},
            "status": _default_profile_status(),
            "highlights": [],
            "games": [],
        }

    prefs = prefs_override or profile_indexer.load_preferences(user_id) or {}
    if (not prefs) and supabase_client:
        profile_row = supabase_client.get_or_create_profile(user_id)
        if profile_row:
            linked = profile_row.get("linked_accounts") or []
            time_controls = profile_row.get("time_controls") or []
            if linked or time_controls:
                prefs = {"accounts": linked, "time_controls": time_controls}
    
    status = profile_indexer.get_status(user_id)
    highlights = profile_indexer.get_highlights(user_id)
    games = profile_indexer.get_games(user_id, limit=25)
    return {
        "preferences": prefs,
        "status": status,
        "highlights": highlights,
        "games": games,
    }


@app.get("/profile/preferences")
async def get_profile_preferences(user_id: str):
    if not profile_indexer:
        raise HTTPException(status_code=503, detail="Profile indexer not initialized")
    prefs = profile_indexer.load_preferences(user_id) or {}
    return {"preferences": prefs}


@app.get("/profile/subscription")
async def profile_subscription(user_id: str):
    """
    Lightweight subscription overview for Settings UI.
    """
    if not supabase_client:
        raise HTTPException(status_code=503, detail="Supabase client not initialized")
    try:
        data = await asyncio.to_thread(supabase_client.get_subscription_overview, user_id)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch subscription: {str(e)}")


class BillingPortalPayload(BaseModel):
    user_id: str
    user_email: Optional[str] = None  # Email from frontend (fallback if backend can't get it)
    return_url: Optional[str] = None


class CheckoutPayload(BaseModel):
    user_id: str
    user_email: Optional[str] = None
    product_id: str  # Stripe Product ID (we'll get the default price)
    return_url: Optional[str] = None


@app.post("/billing/portal")
async def billing_portal(payload: BillingPortalPayload):
    """
    Create a Stripe Billing Portal session for the current user.
    
    If no Stripe customer is linked, attempts to find one by email or create a new customer.
    """
    if not supabase_client:
        raise HTTPException(status_code=503, detail="Supabase client not initialized")

    stripe_secret = os.getenv("STRIPE_SECRET_KEY")
    if not stripe_secret:
        raise HTTPException(status_code=500, detail="STRIPE_SECRET_KEY not set on backend")

    try:
        import stripe  # type: ignore
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stripe library not available: {str(e)}")

    stripe.api_key = stripe_secret

    # Get existing Stripe customer ID
    stripe_customer_id = await asyncio.to_thread(supabase_client.get_stripe_customer_id, payload.user_id)
    print(f"[BILLING_PORTAL] User {payload.user_id} - Existing customer ID: {stripe_customer_id}")
    
    # If no customer ID, try to find by email or create new customer
    if not stripe_customer_id:
        # Get user email - prefer passed email from frontend, fallback to API lookup
        user_email = payload.user_email
        print(f"[BILLING_PORTAL] Email from frontend: {user_email}")
        
        if not user_email:
            # Try to get from Supabase API (fallback)
            try:
                # Query auth.users via admin API to get email
                import requests
                supabase_url = os.getenv("SUPABASE_URL")
                service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
                
                if not supabase_url or not service_key:
                    print(f"[BILLING_PORTAL] Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
                else:
                    headers = {
                        "apikey": service_key,
                        "Authorization": f"Bearer {service_key}",
                    }
                    user_response = requests.get(
                        f"{supabase_url}/auth/v1/admin/users/{payload.user_id}",
                        headers=headers,
                        timeout=10,
                    )
                    
                    print(f"[BILLING_PORTAL] User lookup response status: {user_response.status_code}")
                    
                    if user_response.status_code == 200:
                        user_data = user_response.json()
                        user_email = user_data.get("email")
                        print(f"[BILLING_PORTAL] Found user email from API: {user_email}")
                    else:
                        print(f"[BILLING_PORTAL] Failed to get user: {user_response.status_code} - {user_response.text}")
            except Exception as e:
                print(f"[BILLING_PORTAL] Error getting user email from API: {e}")
                import traceback
                traceback.print_exc()
        
        if user_email:
            try:
                # Try to find existing Stripe customer by email
                print(f"[BILLING_PORTAL] Searching for Stripe customer with email: {user_email}")
                customers = stripe.Customer.list(email=user_email, limit=10)  # Get more to see all matches
                print(f"[BILLING_PORTAL] Found {len(customers.data)} Stripe customer(s) with email {user_email}")
                
                if customers.data and len(customers.data) > 0:
                    # Use the first one (most recent)
                    stripe_customer_id = customers.data[0].id
                    print(f"[BILLING_PORTAL] Using customer: {stripe_customer_id}")
                    
                    # Check if this customer has any subscriptions
                    subscriptions = stripe.Subscription.list(customer=stripe_customer_id, limit=10)
                    print(f"[BILLING_PORTAL] Customer has {len(subscriptions.data)} subscription(s)")
                    
                    # Link it to the user
                    await asyncio.to_thread(
                        supabase_client.upsert_user_subscription,
                        user_id=payload.user_id,
                        stripe_customer_id=stripe_customer_id,
                    )
                    print(f"[BILLING_PORTAL] ✅ Linked existing Stripe customer {stripe_customer_id} to user {payload.user_id}")
                else:
                    # No customer found - create a new Stripe customer so they can subscribe
                    print(f"[BILLING_PORTAL] No Stripe customer found with email {user_email}, creating new customer")
                    try:
                        customer = stripe.Customer.create(
                            email=user_email,
                            metadata={"user_id": payload.user_id},
                        )
                        stripe_customer_id = customer.id
                        # Link it to the user
                        await asyncio.to_thread(
                            supabase_client.upsert_user_subscription,
                            user_id=payload.user_id,
                            stripe_customer_id=stripe_customer_id,
                        )
                        print(f"[BILLING_PORTAL] ✅ Created new Stripe customer {stripe_customer_id} for user {payload.user_id}")
                    except Exception as e:
                        print(f"[BILLING_PORTAL] Error creating Stripe customer: {e}")
                        import traceback
                        traceback.print_exc()
            except Exception as e:
                print(f"[BILLING_PORTAL] Error searching/creating Stripe customer: {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"[BILLING_PORTAL] Could not get user email for {payload.user_id}")
    
    if not stripe_customer_id:
        # Provide more helpful error message
        error_detail = (
            "No Stripe customer found for this user. "
            "This usually means:\n"
            "1. You haven't subscribed yet - please use the pricing table to subscribe first\n"
            "2. The webhook hasn't synced your subscription yet - wait a few moments and try again\n"
            "3. Your Stripe email doesn't match your account email - contact support"
        )
        raise HTTPException(status_code=400, detail=error_detail)

    return_url = (
        payload.return_url
        or os.getenv("FRONTEND_URL")
        or os.getenv("NEXT_PUBLIC_FRONTEND_URL")
        or "https://chesster.ai"
    )

    try:
        session = stripe.billing_portal.Session.create(customer=stripe_customer_id, return_url=return_url)
        print(f"[BILLING_PORTAL] ✅ Created billing portal session for customer {stripe_customer_id}")
        return {"url": session.url}
    except Exception as e:
        print(f"[BILLING_PORTAL] ❌ Failed to create billing portal session: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to create billing portal session: {str(e)}")


@app.post("/stripe/create-checkout")
async def create_checkout(payload: CheckoutPayload):
    """
    Create a Stripe Checkout session for subscription.
    Uses product_id to find the default price.
    """
    if not supabase_client:
        raise HTTPException(status_code=503, detail="Supabase client not initialized")

    stripe_secret = os.getenv("STRIPE_SECRET_KEY")
    if not stripe_secret:
        raise HTTPException(status_code=500, detail="STRIPE_SECRET_KEY not set on backend")

    try:
        import stripe  # type: ignore
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stripe library not available: {str(e)}")

    stripe.api_key = stripe_secret

    # Get the default price for this product
    try:
        product = stripe.Product.retrieve(payload.product_id)
        # Get prices for this product
        prices = stripe.Price.list(product=payload.product_id, limit=1, active=True)
        if not prices.data:
            raise HTTPException(status_code=400, detail=f"No active price found for product {payload.product_id}")
        price_id = prices.data[0].id
        print(f"[CHECKOUT] Using price {price_id} for product {payload.product_id}")
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid product ID: {str(e)}")

    # Get or create Stripe customer
    stripe_customer_id = await asyncio.to_thread(supabase_client.get_stripe_customer_id, payload.user_id)
    
    # If no customer, create one
    if not stripe_customer_id:
        user_email = payload.user_email
        if not user_email:
            # Try to get from API
            try:
                import requests
                supabase_url = os.getenv("SUPABASE_URL")
                service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
                
                if supabase_url and service_key:
                    headers = {
                        "apikey": service_key,
                        "Authorization": f"Bearer {service_key}",
                    }
                    user_response = requests.get(
                        f"{supabase_url}/auth/v1/admin/users/{payload.user_id}",
                        headers=headers,
                        timeout=10,
                    )
                    if user_response.status_code == 200:
                        user_data = user_response.json()
                        user_email = user_data.get("email")
            except Exception as e:
                print(f"[CHECKOUT] Error getting user email: {e}")
        
        if user_email:
            try:
                customer = stripe.Customer.create(
                    email=user_email,
                    metadata={"user_id": payload.user_id},
                )
                stripe_customer_id = customer.id
                await asyncio.to_thread(
                    supabase_client.upsert_user_subscription,
                    user_id=payload.user_id,
                    stripe_customer_id=stripe_customer_id,
                )
                print(f"[CHECKOUT] Created Stripe customer {stripe_customer_id}")
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to create customer: {str(e)}")
        else:
            raise HTTPException(status_code=400, detail="Email required to create checkout session")

    return_url = (
        payload.return_url
        or os.getenv("FRONTEND_URL")
        or os.getenv("NEXT_PUBLIC_FRONTEND_URL")
        or "https://chesster.ai"
    )

    try:
        session = stripe.checkout.Session.create(
            customer=stripe_customer_id,
            line_items=[{"price": price_id, "quantity": 1}],
            mode="subscription",
            success_url=f"{return_url}/settings?success=true",
            cancel_url=f"{return_url}/settings?canceled=true",
            metadata={"user_id": payload.user_id},
        )
        print(f"[CHECKOUT] Created checkout session for customer {stripe_customer_id}")
        return {"url": session.url}
    except Exception as e:
        print(f"[CHECKOUT] Error creating checkout session: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to create checkout session: {str(e)}")


@app.get("/debug/stripe-customer")
async def debug_stripe_customer(user_id: str):
    """
    Debug endpoint to check Stripe customer status.
    Helps diagnose why billing portal might be failing.
    """
    if not supabase_client:
        return {"error": "Supabase not initialized"}
    
    try:
        import stripe  # type: ignore
    except Exception as e:
        return {"error": f"Stripe library not available: {str(e)}"}
    
    stripe_secret = os.getenv("STRIPE_SECRET_KEY")
    if not stripe_secret:
        return {"error": "STRIPE_SECRET_KEY not set"}
    
    stripe.api_key = stripe_secret
    
    # Get customer ID from Supabase
    customer_id = await asyncio.to_thread(supabase_client.get_stripe_customer_id, user_id)
    
    # Get user email with better error handling
    import requests
    supabase_url = os.getenv("SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    user_email = None
    email_lookup_error = None
    
    if not supabase_url:
        email_lookup_error = "SUPABASE_URL not set"
    elif not service_key:
        email_lookup_error = "SUPABASE_SERVICE_ROLE_KEY not set"
    else:
        headers = {
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
        }
        try:
            user_response = requests.get(
                f"{supabase_url}/auth/v1/admin/users/{user_id}",
                headers=headers,
                timeout=10,
            )
            if user_response.status_code == 200:
                user_data = user_response.json()
                user_email = user_data.get("email")
            else:
                email_lookup_error = f"HTTP {user_response.status_code}: {user_response.text[:200]}"
        except Exception as e:
            email_lookup_error = f"Request failed: {str(e)}"
    
    # Search Stripe for customers with this email
    stripe_customers_by_email = []
    if user_email:
        try:
            customers = stripe.Customer.list(email=user_email, limit=10)
            stripe_customers_by_email = [
                {
                    "id": c.id,
                    "email": c.email,
                    "created": datetime.fromtimestamp(c.created).isoformat() if c.created else None,
                    "metadata": c.metadata,
                }
                for c in customers.data
            ]
        except Exception as e:
            return {"error": f"Failed to search Stripe customers: {str(e)}"}
    
    # Get subscription info from Supabase
    subscription_info = None
    try:
        subscription_info = await asyncio.to_thread(supabase_client.get_subscription_overview, user_id)
    except Exception as e:
        pass
    
    return {
        "user_id": user_id,
        "user_email": user_email,
        "email_lookup_error": email_lookup_error,
        "supabase_customer_id": customer_id,
        "stripe_customers_by_email": stripe_customers_by_email,
        "subscription_info": subscription_info,
        "env_check": {
            "has_supabase_url": bool(supabase_url),
            "has_service_key": bool(service_key),
            "has_stripe_key": bool(stripe_secret),
        },
    }


@app.post("/webhooks/stripe")
async def stripe_webhook(request: Request):
    """
    Handle Stripe webhook events to sync subscription data to Supabase.
    
    Events handled:
    - checkout.session.completed: When a user completes checkout
    - customer.subscription.created: When a subscription is created
    - customer.subscription.updated: When a subscription changes
    - customer.subscription.deleted: When a subscription is canceled
    """
    if not supabase_client:
        raise HTTPException(status_code=503, detail="Supabase client not initialized")

    stripe_secret = os.getenv("STRIPE_SECRET_KEY")
    if not stripe_secret:
        raise HTTPException(status_code=500, detail="STRIPE_SECRET_KEY not set on backend")

    try:
        import stripe  # type: ignore
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stripe library not available: {str(e)}")

    stripe.api_key = stripe_secret
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    
    # Get the raw body and signature
    body = await request.body()
    sig_header = request.headers.get("stripe-signature")
    
    if not sig_header:
        raise HTTPException(status_code=400, detail="Missing stripe-signature header")
    
    try:
        if webhook_secret:
            event = stripe.Webhook.construct_event(body, sig_header, webhook_secret)
        else:
            # If no webhook secret, parse without verification (not recommended for production)
            import json
            event = json.loads(body)
            print("⚠️  WARNING: Processing Stripe webhook without signature verification")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid payload: {str(e)}")
    except stripe.error.SignatureVerificationError as e:
        raise HTTPException(status_code=400, detail=f"Invalid signature: {str(e)}")

    event_type = event.get("type")
    event_data = event.get("data", {}).get("object", {})
    
    print(f"[STRIPE_WEBHOOK] Received event: {event_type}")
    
    try:
        if event_type == "checkout.session.completed":
            # User completed checkout - create subscription record
            customer_id = event_data.get("customer")
            subscription_id = event_data.get("subscription")
            customer_email = event_data.get("customer_email") or event_data.get("customer_details", {}).get("email")
            
            if not customer_id:
                print(f"[STRIPE_WEBHOOK] No customer_id in checkout.session.completed")
                return {"status": "ok", "message": "No customer_id"}
            
            # Get customer details from Stripe
            customer = stripe.Customer.retrieve(customer_id)
            customer_email = customer_email or customer.get("email")
            
            if not customer_email:
                print(f"[STRIPE_WEBHOOK] No email found for customer {customer_id}")
                return {"status": "ok", "message": "No email found"}
            
            # Find user by email - try to get from auth.users via admin API
            # Since we can't directly query auth.users, we'll use the customer email
            # and store it in metadata or query via a function
            # For now, we'll try to find user via profiles or use customer metadata
            user_id = None
            
            # Check if customer has metadata with user_id
            if customer.get("metadata", {}).get("user_id"):
                user_id = customer.metadata.get("user_id")
            else:
                # Try to find user by email using Supabase admin API
                print(f"[STRIPE_WEBHOOK] No user_id in metadata, looking up user by email: {customer_email}")
                user_id = await asyncio.to_thread(supabase_client.get_user_by_email, customer_email)
                
                if not user_id:
                    print(f"[STRIPE_WEBHOOK] Could not find user with email {customer_email}")
                    # Store customer_id temporarily - we'll link it when user signs in
                    # For now, return success but log the issue
                    return {"status": "ok", "message": f"No user found for email {customer_email}, customer {customer_id} needs manual linking"}
            
            # Get subscription details if available
            subscription_data = {}
            if subscription_id:
                subscription = stripe.Subscription.retrieve(subscription_id)
                price_id = subscription.get("items", {}).get("data", [{}])[0].get("price", {}).get("id")
                
                # Map Stripe price_id to tier_id
                # You'll need to configure this mapping based on your Stripe price IDs
                tier_id = "unpaid"  # Default
                if price_id:
                    # Query subscription_tiers to find matching stripe_price_id
                    try:
                        tier_result = (
                            supabase_client.client.table("subscription_tiers")
                            .select("id")
                            .eq("stripe_price_id", price_id)
                            .limit(1)
                            .execute()
                        )
                        if tier_result.data and len(tier_result.data) > 0:
                            tier_id = tier_result.data[0].get("id")
                    except Exception as e:
                        print(f"[STRIPE_WEBHOOK] Error mapping price_id to tier: {e}")
                
                subscription_data = {
                    "stripe_subscription_id": subscription_id,
                    "tier_id": tier_id,
                    "status": subscription.get("status", "active"),
                    "current_period_start": datetime.fromtimestamp(subscription.get("current_period_start", 0)).isoformat() if subscription.get("current_period_start") else None,
                    "current_period_end": datetime.fromtimestamp(subscription.get("current_period_end", 0)).isoformat() if subscription.get("current_period_end") else None,
                }
            
            # Upsert subscription record
            await asyncio.to_thread(
                supabase_client.upsert_user_subscription,
                user_id=user_id,
                stripe_customer_id=customer_id,
                **subscription_data,
            )
            
            print(f"[STRIPE_WEBHOOK] Created subscription for user {user_id}, customer {customer_id}")
            
        elif event_type == "customer.subscription.created":
            # Subscription was created
            subscription = event_data
            customer_id = subscription.get("customer")
            subscription_id = subscription.get("id")
            price_id = subscription.get("items", {}).get("data", [{}])[0].get("price", {}).get("id")
            
            # Get customer to find user_id
            customer = stripe.Customer.retrieve(customer_id)
            user_id = customer.get("metadata", {}).get("user_id")
            
            if not user_id:
                # Try to find user by email
                customer_email = customer.get("email")
                if customer_email:
                    print(f"[STRIPE_WEBHOOK] No user_id in metadata, looking up user by email: {customer_email}")
                    user_id = await asyncio.to_thread(supabase_client.get_user_by_email, customer_email)
            
            if not user_id:
                print(f"[STRIPE_WEBHOOK] No user_id found for subscription {subscription_id}, customer {customer_id}")
                return {"status": "ok", "message": "No user_id found"}
            
            # Map price_id to tier_id
            tier_id = "unpaid"
            if price_id:
                try:
                    tier_result = (
                        supabase_client.client.table("subscription_tiers")
                        .select("id")
                        .eq("stripe_price_id", price_id)
                        .limit(1)
                        .execute()
                    )
                    if tier_result.data and len(tier_result.data) > 0:
                        tier_id = tier_result.data[0].get("id")
                except Exception as e:
                    print(f"[STRIPE_WEBHOOK] Error mapping price_id to tier: {e}")
            
            await asyncio.to_thread(
                supabase_client.upsert_user_subscription,
                user_id=user_id,
                stripe_customer_id=customer_id,
                stripe_subscription_id=subscription_id,
                tier_id=tier_id,
                status=subscription.get("status", "active"),
                current_period_start=datetime.fromtimestamp(subscription.get("current_period_start", 0)).isoformat() if subscription.get("current_period_start") else None,
                current_period_end=datetime.fromtimestamp(subscription.get("current_period_end", 0)).isoformat() if subscription.get("current_period_end") else None,
            )
            
            print(f"[STRIPE_WEBHOOK] Created subscription record for user {user_id}")
            
        elif event_type == "customer.subscription.updated":
            # Subscription was updated (e.g., plan change, status change)
            subscription = event_data
            customer_id = subscription.get("customer")
            subscription_id = subscription.get("id")
            
            customer = stripe.Customer.retrieve(customer_id)
            user_id = customer.get("metadata", {}).get("user_id")
            
            if not user_id:
                # Try to find user by email
                customer_email = customer.get("email")
                if customer_email:
                    print(f"[STRIPE_WEBHOOK] No user_id in metadata, looking up user by email: {customer_email}")
                    user_id = await asyncio.to_thread(supabase_client.get_user_by_email, customer_email)
            
            if not user_id:
                print(f"[STRIPE_WEBHOOK] No user_id found for subscription {subscription_id}, customer {customer_id}")
                return {"status": "ok", "message": "No user_id found"}
            
            price_id = subscription.get("items", {}).get("data", [{}])[0].get("price", {}).get("id")
            tier_id = None
            if price_id:
                try:
                    tier_result = (
                        supabase_client.client.table("subscription_tiers")
                        .select("id")
                        .eq("stripe_price_id", price_id)
                        .limit(1)
                        .execute()
                    )
                    if tier_result.data and len(tier_result.data) > 0:
                        tier_id = tier_result.data[0].get("id")
                except Exception as e:
                    print(f"[STRIPE_WEBHOOK] Error mapping price_id to tier: {e}")
            
            await asyncio.to_thread(
                supabase_client.upsert_user_subscription,
                user_id=user_id,
                stripe_customer_id=customer_id,
                stripe_subscription_id=subscription_id,
                tier_id=tier_id,
                status=subscription.get("status"),
                current_period_start=datetime.fromtimestamp(subscription.get("current_period_start", 0)).isoformat() if subscription.get("current_period_start") else None,
                current_period_end=datetime.fromtimestamp(subscription.get("current_period_end", 0)).isoformat() if subscription.get("current_period_end") else None,
            )
            
            print(f"[STRIPE_WEBHOOK] Updated subscription for user {user_id}")
            
        elif event_type == "customer.subscription.deleted":
            # Subscription was canceled
            subscription = event_data
            customer_id = subscription.get("customer")
            subscription_id = subscription.get("id")
            
            customer = stripe.Customer.retrieve(customer_id)
            user_id = customer.get("metadata", {}).get("user_id")
            
            if not user_id:
                # Try to find user by email
                customer_email = customer.get("email")
                if customer_email:
                    print(f"[STRIPE_WEBHOOK] No user_id in metadata, looking up user by email: {customer_email}")
                    user_id = await asyncio.to_thread(supabase_client.get_user_by_email, customer_email)
            
            if not user_id:
                print(f"[STRIPE_WEBHOOK] No user_id found for subscription {subscription_id}, customer {customer_id}")
                return {"status": "ok", "message": "No user_id found"}
            
            await asyncio.to_thread(
                supabase_client.upsert_user_subscription,
                user_id=user_id,
                stripe_customer_id=customer_id,
                stripe_subscription_id=subscription_id,
                status="canceled",
                current_period_end=datetime.fromtimestamp(subscription.get("current_period_end", 0)).isoformat() if subscription.get("current_period_end") else None,
            )
            
            print(f"[STRIPE_WEBHOOK] Marked subscription as canceled for user {user_id}")
        
        return {"status": "ok"}
        
    except Exception as e:
        print(f"[STRIPE_WEBHOOK] Error processing webhook: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Webhook processing error: {str(e)}")


@app.post("/subscription/webhook")
async def stripe_webhook_subscription(request: Request):
    """
    Alias for /webhooks/stripe to match existing Stripe webhook configuration.
    This endpoint is configured in Stripe Dashboard as: https://chesster-backend.onrender.com/subscription/webhook
    """
    # Reuse the same handler logic
    return await stripe_webhook(request)


@app.get("/profile/validate-account")
async def validate_account(
    username: str = Query(..., description="Username to validate"),
    platform: str = Query(..., pattern="^(chess.com|lichess)$", description="Platform: chess.com or lichess")
):
    """Validate that an account exists on chess.com or lichess"""
    try:
        import aiohttp
        import urllib.parse
        
        # Normalize platform name
        platform_normalized = "chess.com" if platform in ["chess.com", "chesscom"] else "lichess"
        
        # URL encode username to handle special characters
        encoded_username = urllib.parse.quote(username)
        
        async with aiohttp.ClientSession() as session:
            if platform_normalized == "chess.com":
                # Chess.com profile endpoint
                profile_url = f"https://api.chess.com/pub/player/{encoded_username}"
            else:  # lichess
                # Lichess user endpoint
                profile_url = f"https://lichess.org/api/user/{encoded_username}"
            
            print(f"🔍 Validating {platform_normalized} account: {username} (URL: {profile_url})")
            
            try:
                async with session.get(profile_url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    print(f"📡 Validation response status: {response.status} for {username} on {platform_normalized}")
                    
                    if response.status == 200:
                        # Account exists
                        print(f"✅ Account {username} on {platform_normalized} is valid")
                        return {
                            "valid": True,
                            "username": username,
                            "platform": platform_normalized,
                            "message": "Account found"
                        }
                    elif response.status == 404:
                        # Account doesn't exist
                        print(f"❌ Account {username} on {platform_normalized} not found (404)")
                        return {
                            "valid": False,
                            "username": username,
                            "platform": platform_normalized,
                            "message": "Account not found"
                        }
                    else:
                        # Other error - get response text for debugging
                        try:
                            error_text = await response.text()
                            print(f"⚠️ Validation error for {username}: status {response.status}, error: {error_text[:200]}")
                        except:
                            error_text = f"Status {response.status}"
                            print(f"⚠️ Validation error for {username}: status {response.status}")
                        
                        return {
                            "valid": False,
                            "username": username,
                            "platform": platform_normalized,
                            "message": f"API returned status {response.status}: {error_text[:100] if 'error_text' in locals() else ''}"
                        }
            except aiohttp.ClientError as e:
                return {
                    "valid": False,
                    "username": username,
                    "platform": platform_normalized,
                    "message": f"Network error: {str(e)}"
                }
            except asyncio.TimeoutError:
                return {
                    "valid": False,
                    "username": username,
                    "platform": platform_normalized,
                    "message": "Validation timeout - please try again"
                }
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"❌ Error validating account {username} on {platform}: {error_detail}")
        return {
            "valid": False,
            "username": username,
            "platform": platform,
            "message": f"Error validating account: {str(e)}"
        }


@app.post("/profile/preferences")
async def save_profile_preferences(payload: ProfilePreferencesPayload):
    if not profile_indexer:
        raise HTTPException(status_code=503, detail="Profile indexer not initialized")

    # Validate platform names and normalize
    normalized_accounts = []
    for acc in payload.accounts:
        if not acc.username.strip():
            continue
        
        # Only allow chess.com or lichess
        platform = acc.platform.lower()
        if platform not in ["chess.com", "lichess", "chesscom"]:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid platform: {platform}. Only 'chess.com' or 'lichess' are allowed."
            )
        
        # Normalize platform name
        platform_normalized = "chess.com" if platform in ["chess.com", "chesscom"] else "lichess"
        
        normalized_accounts.append({
            "platform": platform_normalized,
            "username": acc.username.strip()
        })
    
    prefs = {
        "accounts": normalized_accounts,
        "time_controls": [tc.lower() for tc in payload.time_controls],
    }

    profile_indexer.save_preferences(payload.user_id, prefs)
    await profile_indexer.start_indexing(
        user_id=payload.user_id,
        accounts=prefs["accounts"],
        time_controls=prefs["time_controls"],
    )
    return _profile_overview_payload(payload.user_id, prefs_override=prefs)


@app.get("/profile/overview")
async def profile_overview(user_id: str):
    """
    Must be fast and must not block on Supabase/network.
    Frontend polls this endpoint for progress (deep_analyzed_games).
    """
    if not profile_indexer:
        return JSONResponse(
            {
                "preferences": {},
                "status": {"state": "error", "message": "Profile indexer not initialized"},
                "highlights": [],
                "games": [],
            },
            status_code=503,
        )

    # In-memory only (never touch Supabase here).
    prefs = {}
    highlights = []
    games = []
    status = _default_profile_status()
    try:
        prefs = profile_indexer.load_preferences(user_id) or {}
    except Exception:
        prefs = {}
    try:
        full_status = profile_indexer.get_status(user_id) or {}
        
        # Get active games count from game window manager
        active_games_count = 0
        if supabase_client and game_window_manager:
            try:
                active_games_count = game_window_manager.count_active_games(user_id)
            except Exception:
                pass
        
        status = {
            "state": full_status.get("state", "idle"),
            "message": full_status.get("message", ""),
            "games_indexed": full_status.get("games_indexed", 0),
            "deep_analyzed_games": active_games_count or full_status.get("deep_analyzed_games", 0),
            "target_games": 60,  # Always 60 for rolling window
            "total_games_estimate": full_status.get("total_games_estimate", 0),
            "last_error": full_status.get("last_error"),
            "background_active": full_status.get("background_active", False),
            "next_poll_at": full_status.get("next_poll_at"),
        }
    except Exception:
        status = _default_profile_status()
    try:
        highlights = profile_indexer.get_highlights(user_id) or []
    except Exception:
        highlights = []
    try:
        cached_games = profile_indexer.get_games(user_id, limit=25) or []
        games = [
            {
                "game_id": g.get("game_id") or g.get("external_id"),
                "platform": g.get("platform"),
                "opponent_name": g.get("opponent_name"),
                "date": g.get("date") or g.get("game_date"),
                "result": g.get("result"),
                "opening": g.get("opening") or g.get("opening_name") or g.get("opening_eco"),
            }
            for g in cached_games
        ]
    except Exception:
        games = []

    # Kick background pipeline (never await)
    try:
        asyncio.create_task(profile_indexer.ensure_background_index(user_id))
    except Exception:
        pass
    
    # Trigger account initialization check (non-blocking)
    # Also ensure background indexing is active
    global account_init_manager
    if account_init_manager:
        try:
            # Check this specific account (non-blocking)
            print(f"🔍 Triggering account check for user {user_id}")
            asyncio.create_task(account_init_manager.check_all_accounts())
        except Exception as e:
            print(f"⚠️ Error triggering account check: {e}")
    
    # Also ensure profile indexer is active (this will start indexing if accounts are linked)
    if profile_indexer:
        try:
            # This will check for accounts and start indexing if needed
            asyncio.create_task(profile_indexer.ensure_background_index(user_id))
        except Exception as e:
            print(f"⚠️ Error ensuring background index: {e}")

    return {
        "preferences": prefs,
        "status": status,
        "highlights": highlights,
        "games": games,
    }


@app.get("/profile/overview/snapshot")
async def profile_overview_snapshot(user_id: str, limit: int = 60):
    """
    Lightweight Overview snapshot (last N games).
    Designed for fast UI rendering: record, accuracy, rating trend, time-style, openings snapshot, momentum.
    """
    if not supabase_client:
        raise HTTPException(status_code=503, detail="Supabase client not initialized")

    try:
        from profile_overview_snapshot import build_overview_snapshot

        def fetch_games():
            if hasattr(supabase_client, "get_recent_games_for_overview_snapshot"):
                return supabase_client.get_recent_games_for_overview_snapshot(user_id, limit=int(limit))
            # Fallback (should not happen): use active reviewed games without PGN clocks
            return supabase_client.get_active_reviewed_games(user_id, limit=int(limit), include_full_review=False)

        games = await asyncio.to_thread(fetch_games)
        return build_overview_snapshot(games or [], window=int(limit))
    except Exception as e:
        import traceback
        print(f"❌ [OVERVIEW_SNAPSHOT] Error: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to build overview snapshot: {str(e)}")


@app.get("/profile/stats")
async def profile_stats(user_id: str):
    if not profile_indexer:
        raise HTTPException(status_code=503, detail="Profile indexer not initialized")
    stats = profile_indexer.get_stats(user_id)
    return {"stats": stats}


@app.get("/profile/habits/{user_id}")
async def profile_habits(user_id: str):
    """
    Get profile habits data for a user.
    Returns computed habits, strengths, weaknesses, and trend chart data.
    """
    if not stats_manager:
        raise HTTPException(status_code=503, detail="Personal stats manager not initialized")
    
    try:
        print(f"📊 [PROFILE_HABITS_ENDPOINT] Request received for user_id: {user_id}")
        habits_data = stats_manager.get_habits_for_frontend(user_id)
        print(f"✅ [PROFILE_HABITS_ENDPOINT] Returning habits data for user_id: {user_id}")
        return habits_data
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"❌ [PROFILE_HABITS_ENDPOINT] Error fetching habits for user_id: {user_id}")
        print(f"   Error: {str(e)}")
        print(f"   Traceback: {error_trace}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch profile habits: {str(e)}")


@app.get("/profile/analyzed_games")
async def get_analyzed_games(user_id: str, limit: int = 5):
    """
    Get recently analyzed games for a user.
    Returns minimal game metadata for the RecentGamesTab.
    """
    if not supabase_client:
        raise HTTPException(status_code=503, detail="Supabase client not initialized")
    
    try:
        print(f"📊 [ANALYZED_GAMES_ENDPOINT] Request received for user_id: {user_id}, limit: {limit}")
        
        def fetch_games():
            # Fetch games without full review data (faster)
            games = supabase_client.get_active_reviewed_games(user_id, limit=limit, include_full_review=False)
            
            if not games:
                print(f"⚠️ [ANALYZED_GAMES_ENDPOINT] No games found for user_id: {user_id}")
                return []
            
            # Format games for frontend
            formatted_games = []
            for game in games:
                formatted_games.append({
                    "id": game.get("id"),
                    "game_id": game.get("external_id") or game.get("id"),
                    "platform": game.get("platform", "manual"),
                    "external_id": game.get("external_id"),
                    "game_date": game.get("game_date"),
                    "created_at": game.get("created_at"),
                    "analyzed_at": game.get("analyzed_at"),
                    "result": game.get("result", "unknown"),
                    "opponent_name": game.get("opponent_name", "Unknown"),
                    "user_rating": game.get("user_rating"),
                    "opponent_rating": game.get("opponent_rating"),
                    "opening_name": game.get("opening_name"),
                    "opening_eco": game.get("opening_eco"),
                    "time_control": game.get("time_control"),
                    "metadata": {
                        "result": game.get("result", "unknown"),
                        "player_rating": game.get("user_rating"),
                        "opponent_name": game.get("opponent_name", "Unknown"),
                        "opponent_rating": game.get("opponent_rating"),
                    }
                })
            
            return formatted_games
        
        games = await asyncio.to_thread(fetch_games)
        
        print(f"✅ [ANALYZED_GAMES_ENDPOINT] Returning {len(games)} games for user_id: {user_id}")
        return {"games": games}
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"❌ [ANALYZED_GAMES_ENDPOINT] Error fetching analyzed games for user_id: {user_id}")
        print(f"   Error: {str(e)}")
        print(f"   Traceback: {error_trace}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch analyzed games: {str(e)}")


# IMPORTANT: This route must come BEFORE /profile/analytics/{user_id} to avoid route conflicts
@app.get("/profile/analytics/{user_id}/detailed")
async def get_detailed_analytics(user_id: str):
    """
    Get comprehensive detailed analytics including:
    - Phase accuracies with win/loss tracking
    - Opening repertoire with accuracy
    - Piece accuracy breakdown
    - Tag transition analytics
    - Time bucket performance
    
    Fetches from pre-computed detailed_analytics_cache table for fast response.
    Falls back to on-demand computation if cache is missing.
    """
    if not supabase_client:
        raise HTTPException(status_code=503, detail="Supabase client not initialized")
    
    try:
        print(f"📊 [DETAILED_ANALYTICS_ENDPOINT] Request received for user_id: {user_id}")
        
        # Try to fetch from pre-computed cache first (much faster)
        def fetch_cache():
            try:
                result = supabase_client.client.table("detailed_analytics_cache")\
                    .select("*")\
                    .eq("user_id", user_id)\
                    .maybe_single()\
                    .execute()
                return result.data if result.data else None
            except Exception as e:
                # Table might not exist yet (migration not run)
                error_str = str(e).lower()
                if "does not exist" in error_str or "relation" in error_str:
                    print(f"   ℹ️ [DETAILED_ANALYTICS_ENDPOINT] detailed_analytics_cache table not found, falling back to computation")
                else:
                    print(f"   ⚠️ [DETAILED_ANALYTICS_ENDPOINT] Error fetching cache: {e}")
                return None
        
        cached = await asyncio.to_thread(fetch_cache)
        
        # If we have cached data, return it immediately
        if cached is not None:
            # Both Supabase and LocalPostgres return dict format
            analytics_data = cached.get("analytics_data")
            games_count = cached.get("games_count")
            computed_at = cached.get("computed_at")
            
            if analytics_data:
                print(f"✅ [DETAILED_ANALYTICS_ENDPOINT] Returning cached detailed analytics for user_id: {user_id} ({games_count} games, computed: {computed_at})")
                return analytics_data
        
        # Fallback: compute on-demand if cache not available
        print(f"   ℹ️ [DETAILED_ANALYTICS_ENDPOINT] No cached data found, computing on-demand for user_id: {user_id}")
        
        def fetch_and_aggregate():
            games = supabase_client.get_active_reviewed_games(user_id, limit=60, include_full_review=True)
            if not games:
                print(f"⚠️ [DETAILED_ANALYTICS_ENDPOINT] No games found for user_id: {user_id}")
                from profile_analytics.detailed_analytics import DetailedAnalyticsAggregator
                aggregator = DetailedAnalyticsAggregator()
                return aggregator._empty_analytics()
            
            print(f"📚 [DETAILED_ANALYTICS_ENDPOINT] Found {len(games)} games for user_id: {user_id}")
            
            from profile_analytics.detailed_analytics import DetailedAnalyticsAggregator
            aggregator = DetailedAnalyticsAggregator()
            return aggregator.aggregate(games)
        
        # Run in thread pool to avoid blocking
        detailed_analytics = await asyncio.to_thread(fetch_and_aggregate)
        
        print(f"✅ [DETAILED_ANALYTICS_ENDPOINT] Returning computed detailed analytics for user_id: {user_id}")
        return detailed_analytics
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"❌ [DETAILED_ANALYTICS_ENDPOINT] Error fetching detailed analytics for user_id: {user_id}")
        print(f"   Error: {str(e)}")
        print(f"   Traceback: {error_trace}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch detailed analytics: {str(e)}")


# IMPORTANT: This route must come BEFORE /profile/analytics/{user_id} to avoid route conflicts
@app.get("/profile/analytics/{user_id}/graph-data")
async def get_graph_data(
    user_id: str,
    limit: int = 60
):
    """
    Get compact per-game graphable data for the most recent reviewed games.
    Fetches from pre-computed game_graph_data table for fast response.
    Falls back to on-demand computation if pre-computed data is missing.
    """
    if not supabase_client:
        raise HTTPException(status_code=503, detail="Supabase client not initialized")

    try:
        from datetime import datetime
        
        # Try to fetch from pre-computed table first (much faster)
        def fetch_precomputed():
            try:
                result = supabase_client.client.table("game_graph_data")\
                    .select("*")\
                    .eq("user_id", user_id)\
                    .order("game_date", desc=False)\
                    .limit(int(limit))\
                    .execute()
                return result.data if result.data else []
            except Exception as e:
                # Table might not exist yet (migration not run)
                error_str = str(e).lower()
                if "does not exist" in error_str or "relation" in error_str:
                    print(f"   ℹ️ [GRAPH_DATA_ENDPOINT] game_graph_data table not found, falling back to computation")
                else:
                    print(f"   ⚠️ [GRAPH_DATA_ENDPOINT] Error fetching pre-computed data: {e}")
                return None

        precomputed = await asyncio.to_thread(fetch_precomputed)
        
        # If we have pre-computed data, format and return it
        if precomputed is not None and len(precomputed) > 0:
            formatted = []
            for idx, point in enumerate(precomputed):
                formatted.append({
                    "index": idx,
                    "game_id": point.get("game_id"),
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
            
            print(f"✅ [GRAPH_DATA_ENDPOINT] Returning {len(formatted)} pre-computed graph points for user_id: {user_id}")
            return {
                "user_id": user_id,
                "generated_at": datetime.now().isoformat(),
                "limit": limit,
                "games": formatted,
            }
        
        # Fallback: compute on-demand if pre-computed data not available
        print(f"   ℹ️ [GRAPH_DATA_ENDPOINT] No pre-computed data found, computing on-demand for user_id: {user_id}")
        from profile_analytics.graph_data import build_graph_game_point

        def fetch_games():
            return supabase_client.get_active_reviewed_games(
                user_id, limit=int(limit), include_full_review=True
            )

        games = await asyncio.to_thread(fetch_games)
        if not games:
            return {"user_id": user_id, "generated_at": datetime.now().isoformat(), "limit": limit, "games": []}

        # Sort by date if present, else preserve returned order (typically updated_at desc).
        def _date_key(g):
            gd = g.get("game_date")
            if isinstance(gd, str):
                return gd
            return ""

        games_sorted = sorted(games, key=_date_key)
        points = [build_graph_game_point(g, idx) for idx, g in enumerate(games_sorted)]

        return {
            "user_id": user_id,
            "generated_at": datetime.now().isoformat(),
            "limit": limit,
            "games": points,
        }
    except Exception as e:
        import traceback
        print(f"❌ [GRAPH_DATA_ENDPOINT] Error for user_id={user_id}: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to fetch graph data: {str(e)}")


@app.get("/profile/analytics/{user_id}")
async def profile_analytics(user_id: str):
    """
    Get comprehensive analytics for a user including lifetime stats, patterns, and strength analysis.
    Returns cached data if available (1-hour TTL), otherwise computes fresh analytics.
    """
    print(f"📊 [PROFILE_ANALYTICS_ENDPOINT] Request received for user_id: {user_id}")
    
    if not profile_analytics_engine:
        print(f"❌ [PROFILE_ANALYTICS_ENDPOINT] Engine not initialized for user_id: {user_id}")
        raise HTTPException(status_code=503, detail="Profile analytics engine not initialized")
    
    print(f"✅ [PROFILE_ANALYTICS_ENDPOINT] Engine initialized, calling get_full_analytics for user_id: {user_id}")
    
    try:
        analytics_data = await profile_analytics_engine.get_full_analytics(user_id)
        
        print(f"📦 [PROFILE_ANALYTICS_ENDPOINT] Analytics data received for user_id: {user_id}, keys: {list(analytics_data.keys())}")
        
        # If the engine returned an error dict, return empty structure instead of error
        if "error" in analytics_data:
            error_msg = analytics_data.get("error", "Analytics computation failed")
            print(f"⚠️ [PROFILE_ANALYTICS_ENDPOINT] Error in analytics data for user_id: {user_id}, error: {error_msg}")
            # Return empty structure instead of raising error - let frontend handle gracefully
            analytics_data = {
                "user_id": user_id,
                "generated_at": datetime.now().isoformat(),
                "lifetime_stats": {},
                "patterns": {},
                "strength_profile": {},
                "rolling_window": {"status": "no_data"},
                "deltas": {}
            }
        
        # Ensure all required fields exist with defaults
        if not analytics_data:
            analytics_data = {}
        
        # Always return a valid structure
        safe_analytics_data = {
            "user_id": user_id,
            "generated_at": analytics_data.get("generated_at", datetime.now().isoformat()),
            "lifetime_stats": analytics_data.get("lifetime_stats", {}),
            "patterns": analytics_data.get("patterns", {}),
            "strength_profile": analytics_data.get("strength_profile", {}),
            "rolling_window": analytics_data.get("rolling_window", {"status": "no_data"}),
            "deltas": analytics_data.get("deltas", {})
        }
        
        print(f"✅ [PROFILE_ANALYTICS_ENDPOINT] Successfully returning analytics for user_id: {user_id}")
        
        # Save daily pattern snapshot after computing analytics (non-blocking)
        try:
            pattern_recognizer = profile_analytics_engine.pattern_recognizer
            await pattern_recognizer.save_daily_pattern_snapshot(user_id, "current")
        except Exception as snapshot_err:
            print(f"⚠️ [PROFILE_ANALYTICS_ENDPOINT] Error saving pattern snapshot: {snapshot_err}")
        
        return safe_analytics_data
    except HTTPException:
        print(f"⚠️ [PROFILE_ANALYTICS_ENDPOINT] HTTPException raised for user_id: {user_id}")
        # Return empty structure instead of raising - let frontend handle gracefully
        return {
            "user_id": user_id,
            "generated_at": datetime.now().isoformat(),
            "lifetime_stats": {},
            "patterns": {},
            "strength_profile": {},
            "rolling_window": {"status": "no_data"},
            "deltas": {}
        }
    except Exception as e:
        import traceback
        error_detail = f"Failed to fetch analytics: {str(e)}\n{traceback.format_exc()}"
        print(f"❌ [PROFILE_ANALYTICS_ENDPOINT] Unexpected error for user_id: {user_id}, error: {error_detail}")
        # Return empty structure instead of raising - let frontend handle gracefully
        return {
            "user_id": user_id,
            "generated_at": datetime.now().isoformat(),
            "lifetime_stats": {},
            "patterns": {},
            "strength_profile": {},
            "rolling_window": {"status": "no_data"},
            "deltas": {}
        }


@app.get("/profile/analytics/{user_id}/patterns/history")
async def get_pattern_history(
    user_id: str,
    days: int = 30
):
    """Get pattern history for graphing (time-series data)"""
    if not supabase_client:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        from datetime import datetime, timedelta
        cutoff_date = (datetime.now() - timedelta(days=days)).date().isoformat()
        
        result = supabase_client.client.table("pattern_snapshots")\
            .select("*")\
            .eq("user_id", user_id)\
            .gte("snapshot_date", cutoff_date)\
            .order("snapshot_date", desc=False)\
            .execute()
        
        return {
            "patterns": result.data if result.data else [],
            "days": days
        }
    except Exception as e:
        # Handle case where table doesn't exist yet (migrations not run)
        error_msg = str(e)
        if "does not exist" in error_msg or "relation" in error_msg.lower():
            return {
                "patterns": [],
                "days": days,
                "note": "Pattern snapshots table not yet initialized"
            }
        raise HTTPException(status_code=500, detail=f"Error fetching pattern history: {str(e)}")


@app.post("/admin/check-all-accounts")
async def check_all_accounts():
    """Manually trigger account initialization check"""
    global account_init_manager
    if not account_init_manager:
        raise HTTPException(status_code=503, detail="Account initialization manager not available")
    
    results = await account_init_manager.check_all_accounts()
    return results


class PlanReviewRequest(BaseModel):
    query: str
    games: List[Dict]


@app.post("/plan_personal_review")
async def plan_personal_review(request: PlanReviewRequest):
    """Plan a personal review based on natural language query"""
    if not llm_planner:
        raise HTTPException(status_code=503, detail="LLM planner not initialized")
    
    try:
        print(f"🤔 Planning analysis for query: {request.query}")
        
        plan = llm_planner.plan_analysis(request.query, request.games)
        
        print(f"✅ Generated plan with intent: {plan.get('intent', 'unknown')}")
        
        return plan
    
    except Exception as e:
        import traceback
        error_detail = f"Plan review error: {str(e)}\n{traceback.format_exc()}"
        print(error_detail)
        raise HTTPException(status_code=500, detail=f"Failed to plan review: {str(e)}")


class AggregateReviewRequest(BaseModel):
    plan: Dict
    games: List[Dict]


@app.post("/aggregate_personal_review")
async def aggregate_personal_review(request: AggregateReviewRequest):
    """Aggregate statistics from analyzed games"""
    if not review_aggregator or not engine:
        raise HTTPException(status_code=503, detail="Aggregator or engine not initialized")
    
    try:
        print(f"\n{'='*60}")
        print(f"🎯 AGGREGATE_PERSONAL_REVIEW ENDPOINT CALLED")
        print(f"{'='*60}")
        
        # First, analyze the games using existing review_game logic
        # We'll analyze a subset based on the plan
        games_to_analyze = request.plan.get("games_to_analyze", min(len(request.games), 50))
        analysis_depth = request.plan.get("analysis_depth", 15)
        
        print(f"📊 Starting aggregation for {len(request.games)} games")
        print(f"   Settings: depth={analysis_depth}, games_to_analyze={games_to_analyze}")
        print(f"   Plan: {request.plan.get('intent', 'unknown')}")
        print(f"   Filters: {request.plan.get('filters', {})}")
        
        analyzed_games = []
        for idx, game in enumerate(request.games[:games_to_analyze]):
            print(f"\n  ===== Analyzing game {idx + 1}/{games_to_analyze} =====")
            print(f"  Game ID: {game.get('game_id', 'unknown')}")
            print(f"  Platform: {game.get('platform', 'unknown')}")
            print(f"  Player color: {game.get('player_color', 'unknown')}")
            
            try:
                # Use the existing review_game logic
                pgn_string = game.get("pgn", "")
                if not pgn_string:
                    print(f"  ⚠️ Skipping - no PGN data")
                    continue
                
                print(f"  PGN length: {len(pgn_string)} chars")
                
                # Get player color for focused analysis
                player_color = game.get("player_color", "white")
                
                # Call internal review function with player's side focus
                review_result = await _review_game_internal(
                    pgn_string=pgn_string,
                    side_focus=player_color,
                    include_timestamps=game.get("has_clock", False),
                    engine_instance=engine,
                    depth=analysis_depth
                )
                
                # Skip if review failed
                if "error" in review_result:
                    print(f"  ❌ Review failed: {review_result['error']}")
                    continue
                
                print(f"  ✅ Review complete: {len(review_result.get('ply_records', []))} moves analyzed")
                
                # Add metadata from the game
                review_result["metadata"] = {
                    "game_id": game.get("game_id"),
                    "platform": game.get("platform"),
                    "player_rating": game.get("player_rating"),
                    "opponent_rating": game.get("opponent_rating"),
                    "result": game.get("result"),
                    "player_color": game.get("player_color"),
                    "time_category": game.get("time_category"),
                    "date": game.get("date")
                }
                
                analyzed_games.append(review_result)
            
            except Exception as e:
                print(f"    Warning: Failed to analyze game {idx + 1}: {e}")
                continue
        
        print(f"\n{'='*60}")
        print(f"✅ Analyzed {len(analyzed_games)} games successfully")
        print(f"{'='*60}\n")
        
        if len(analyzed_games) == 0:
            print(f"⚠️ WARNING: No games were successfully analyzed!")
            return {
                "error": "No games could be analyzed",
                "summary": {"total_games": 0}
            }
        
        # Now aggregate the results
        print(f"🔄 Starting aggregation of {len(analyzed_games)} analyzed games...")
        filters = request.plan.get("filters", {})
        cohorts = request.plan.get("cohorts")
        
        print(f"   Calling review_aggregator.aggregate()...")
        aggregated_data = review_aggregator.aggregate(
            analyzed_games=analyzed_games,
            filters=filters,
            cohorts=cohorts
        )
        print(f"   ✅ Aggregation complete!")
        
        # Add action plan based on the data
        print(f"   Generating action plan...")
        aggregated_data["action_plan"] = _generate_action_plan(aggregated_data)
        print(f"   ✅ Action plan generated")
        
        # Add analyzed games for training system (feed-through mode)
        aggregated_data["analyzed_games"] = analyzed_games
        
        print(f"\n{'='*60}")
        print(f"✅ AGGREGATION PIPELINE COMPLETE")
        print(f"   Total games: {aggregated_data.get('total_games_analyzed', 0)}")
        print(f"   Summary accuracy: {aggregated_data.get('summary', {}).get('overall_accuracy', 0):.1f}%")
        print(f"   Analyzed games included: {len(analyzed_games)} (for training)")
        print(f"{'='*60}\n")
        
        return aggregated_data
    
    except Exception as e:
        import traceback
        error_detail = f"\n{'='*60}\n❌ AGGREGATE REVIEW ERROR\n{'='*60}\n{str(e)}\n\n{traceback.format_exc()}\n{'='*60}\n"
        print(error_detail)
        raise HTTPException(status_code=500, detail=f"Failed to aggregate review: {str(e)}")


@app.get("/personal_stats/{user_id}")
async def get_personal_stats_endpoint(user_id: str):
    """Get aggregated personal stats"""
    if not stats_manager:
        raise HTTPException(status_code=503, detail="Stats manager not initialized")
    
    try:
        stats = stats_manager.get_stats(user_id)
        return {"stats": stats}
    except Exception as e:
        import traceback
        print(f"Error getting personal stats: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to get personal stats: {str(e)}")


@app.post("/personal_stats/{user_id}/recalculate")
async def recalculate_personal_stats_endpoint(user_id: str):
    """Force full recalculation of personal stats"""
    if not stats_manager:
        raise HTTPException(status_code=503, detail="Stats manager not initialized")
    
    try:
        stats = stats_manager.full_recalculate(user_id)
        return {"stats": stats, "message": "Stats recalculated successfully"}
    except Exception as e:
        import traceback
        print(f"Error recalculating personal stats: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to recalculate stats: {str(e)}")


@app.post("/personal_stats/{user_id}/validate")
async def validate_personal_stats_endpoint(user_id: str):
    """Validate stats integrity"""
    if not stats_manager:
        raise HTTPException(status_code=503, detail="Stats manager not initialized")
    
    try:
        validation = stats_manager.validate_stats(user_id)
        return validation
    except Exception as e:
        import traceback
        print(f"Error validating personal stats: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to validate stats: {str(e)}")


def _generate_action_plan(data: Dict) -> List[str]:
    """Generate simple action plan from data"""
    actions = []
    summary = data.get("summary", {})
    phase_stats = data.get("phase_stats", {})
    
    # Check blunder rate
    if summary.get("blunder_rate", 0) > 5:
        actions.append("Focus on reducing blunders through tactical puzzles (3-5 puzzles daily)")
    
    # Check phase weaknesses
    if phase_stats:
        weakest_phase = min(phase_stats.items(), key=lambda x: x[1].get("accuracy", 100))
        if weakest_phase[1].get("accuracy", 100) < 80:
            actions.append(f"Study {weakest_phase[0]} principles - your accuracy is lower here")
    
    # Check opening performance
    opening_perf = data.get("opening_performance", [])
    if opening_perf:
        worst_opening = min(opening_perf[:5], key=lambda x: x["win_rate"])
        if worst_opening["win_rate"] < 40 and worst_opening["count"] >= 3:
            actions.append(f"Review or replace {worst_opening['name']} - poor win rate")
    
    # Time management
    time_mgmt = data.get("time_management", {})
    if time_mgmt.get("fast_move_accuracy", 100) < time_mgmt.get("slow_move_accuracy", 0):
        actions.append("Take more time on critical moves - fast moves show lower accuracy")
    
    # Default action if none triggered
    if not actions:
        actions.append("Continue your current training routine - maintain consistency")
        actions.append("Focus on converting winning positions to reduce draws")
    
    return actions


class GenerateReportRequest(BaseModel):
    query: str
    plan: Dict
    data: Dict


@app.post("/generate_personal_report")
async def generate_personal_report(request: GenerateReportRequest):
    """Generate natural language report from aggregated data"""
    if not llm_reporter:
        raise HTTPException(status_code=503, detail="LLM reporter not initialized")
    
    try:
        print(f"📝 Generating report...")
        
        report = llm_reporter.generate_report(
            query=request.query,
            plan=request.plan,
            data=request.data
        )
        
        print(f"✅ Report generated")
        
        return {"report": report}
    
    except Exception as e:
        import traceback
        error_detail = f"Generate report error: {str(e)}\n{traceback.format_exc()}"
        print(error_detail)
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {str(e)}")


@app.post("/compare_cohorts")
async def compare_cohorts(cohorts: List[Dict], games: List[Dict]):
    """Compare statistics between different cohorts"""
    if not review_aggregator:
        raise HTTPException(status_code=503, detail="Aggregator not initialized")
    
    try:
        comparison = review_aggregator._compare_cohorts(games, cohorts)
        return {"comparison": comparison}
    
    except Exception as e:
        import traceback
        error_detail = f"Compare cohorts error: {str(e)}\n{traceback.format_exc()}"
        print(error_detail)
        raise HTTPException(status_code=500, detail=f"Failed to compare cohorts: {str(e)}")


# ============================================================================
# TRAINING & DRILL SYSTEM ENDPOINTS
# ============================================================================

class MinePositionsRequest(BaseModel):
    analyzed_games: List[Dict]
    focus_tags: Optional[List[str]] = None
    max_positions: int = 20
    phase_filter: Optional[str] = None
    side_filter: Optional[str] = None
    include_critical_choices: bool = True


@app.post("/mine_positions")
async def mine_positions_endpoint(request: MinePositionsRequest):
    """Mine training positions from analyzed games"""
    if not position_miner:
        raise HTTPException(status_code=503, detail="Position miner not initialized")
    
    try:
        print(f"⛏️ Mining positions from {len(request.analyzed_games)} games")
        
        positions = position_miner.mine_positions(
            analyzed_games=request.analyzed_games,
            focus_tags=request.focus_tags,
            max_positions=request.max_positions,
            phase_filter=request.phase_filter,
            side_filter=request.side_filter,
            include_critical_choices=request.include_critical_choices
        )
        
        print(f"✅ Mined {len(positions)} positions")
        
        return {"positions": positions, "count": len(positions)}
    
    except Exception as e:
        import traceback
        error_detail = f"Mine positions error: {str(e)}\n{traceback.format_exc()}"
        print(error_detail)
        raise HTTPException(status_code=500, detail=f"Failed to mine positions: {str(e)}")


@app.get("/profile/positions/by-tag-transition")
async def get_positions_by_tag_transition(
    user_id: str,
    tag_name: str,
    transition_type: str = Query(..., pattern="^(gained|lost|missed)$"),
    limit: int = Query(20, ge=1, le=50),
    min_cp_loss: int = Query(100, ge=0)
):
    """
    Query critical positions filtered by tag transitions.
    
    Args:
        user_id: User ID to query positions for
        tag_name: Name of the tag to filter by
        transition_type: Type of transition to filter by
            - 'gained': Positions where tag_name was gained after played move
            - 'lost': Positions where tag_name was lost after played move  
            - 'missed': Positions where tag_name exists in best_move but not in played move
        limit: Maximum number of positions to return
        min_cp_loss: Minimum centipawn loss to filter by (default: 100)
    
    Returns:
        List of positions matching the tag transition filter
    """
    if not supabase_client:
        raise HTTPException(status_code=503, detail="Supabase client not initialized")
    
    try:
        print(f"🔍 [TAG_TRANSITION_QUERY] Querying positions for user {user_id}, tag: {tag_name}, type: {transition_type}")
        
        # Map transition_type to search parameters
        tags_gained_filter = None
        tags_lost_filter = None
        tags_missed_filter = None
        
        if transition_type == "gained":
            tags_gained_filter = tag_name
        elif transition_type == "lost":
            tags_lost_filter = tag_name
        elif transition_type == "missed":
            tags_missed_filter = tag_name
        
        # First, get total count of available positions (for display)
        total_count_result = await asyncio.to_thread(
            supabase_client.count_user_positions,
            user_id=user_id,
            tags_gained_filter=tags_gained_filter,
            tags_lost_filter=tags_lost_filter,
            tags_missed_filter=tags_missed_filter,
            min_cp_loss=min_cp_loss,
            error_categories=["blunder", "mistake"]
        )
        total_count = total_count_result.get("count", 0)
        
        # Query positions using enhanced search method (prioritizes unseen/oldest)
        positions = await asyncio.to_thread(
            supabase_client.search_user_positions,
            user_id=user_id,
            tags_gained_filter=tags_gained_filter,
            tags_lost_filter=tags_lost_filter,
            tags_missed_filter=tags_missed_filter,
            min_cp_loss=min_cp_loss,
            error_categories=["blunder", "mistake"],
            limit=limit,
            prioritize_fresh=True  # Prioritize unseen/oldest positions
        )
        
        # Calculate average accuracy from positions (if available)
        avg_accuracy = None
        if positions:
            accuracies = []
            for pos in positions:
                # Try to get accuracy from various sources
                acc = pos.get("accuracy_pct") or pos.get("accuracy")
                if acc is not None:
                    accuracies.append(float(acc))
            if accuracies:
                avg_accuracy = sum(accuracies) / len(accuracies)
        
        # Mark positions as used (update last_used_in_drill timestamp)
        if positions:
            position_ids = [pos.get("id") for pos in positions if pos.get("id")]
            if position_ids:
                await asyncio.to_thread(
                    supabase_client.mark_positions_used,
                    position_ids=position_ids
                )
        
        accuracy_str = f"{avg_accuracy:.1f}%" if avg_accuracy is not None else "N/A"
        print(f"✅ [TAG_TRANSITION_QUERY] Found {len(positions)}/{total_count} positions matching filter (avg accuracy: {accuracy_str})")
        
        return {
            "positions": positions,
            "count": len(positions),
            "total_available": total_count,
            "average_accuracy": round(avg_accuracy, 1) if avg_accuracy is not None else None,
            "tag_name": tag_name,
            "transition_type": transition_type
        }
    
    except Exception as e:
        import traceback
        error_detail = f"Tag transition query error: {str(e)}\n{traceback.format_exc()}"
        print(error_detail)
        raise HTTPException(status_code=500, detail=f"Failed to query positions by tag transition: {str(e)}")


@app.get("/profile/positions/by-filter")
async def get_positions_by_filter(
    user_id: str,
    filter_type: str = Query(..., pattern="^(phase|opening|piece|tag_transition|time_bucket)$"),
    filter_value: str = Query(...),
    transition_type: Optional[str] = Query(None, pattern="^(gained|lost|missed)$"),
    limit: int = Query(20, ge=1, le=50),
    min_cp_loss: int = Query(100, ge=0)
):
    """
    Unified endpoint to query critical positions by various filter types.
    
    Args:
        user_id: User ID to query positions for
        filter_type: Type of filter ("phase", "opening", "piece", "tag_transition", "time_bucket")
        filter_value: The specific value to filter by
            - For "phase": "opening", "middlegame", or "endgame"
            - For "opening": Opening name (e.g., "Italian Game")
            - For "piece": Piece type (e.g., "Bishop", "Knight")
            - For "tag_transition": Tag name (e.g., "pawn_structure")
            - For "time_bucket": Time bucket (e.g., "5-15s", "<5s", "5min+")
        transition_type: Only for tag_transition filter ("gained" | "lost" | "missed")
        limit: Maximum number of positions to return
        min_cp_loss: Minimum centipawn loss to filter by (default: 100)
    
    Returns:
        List of positions matching the filter, with total_available count and average_accuracy
    """
    if not supabase_client:
        raise HTTPException(status_code=503, detail="Supabase client not initialized")
    
    try:
        print(f"🔍 [FILTER_QUERY] Querying positions for user {user_id}, filter_type: {filter_type}, filter_value: {filter_value}")
        
        # Map filter_type to search parameters
        phase_filter = None
        opening_name_filter = None
        piece_type_filter = None
        time_bucket_filter = None
        tags_gained_filter = None
        tags_lost_filter = None
        tags_missed_filter = None
        
        if filter_type == "phase":
            phase_filter = filter_value
        elif filter_type == "opening":
            opening_name_filter = filter_value
        elif filter_type == "piece":
            piece_type_filter = filter_value
        elif filter_type == "time_bucket":
            time_bucket_filter = filter_value
        elif filter_type == "tag_transition":
            if not transition_type:
                raise HTTPException(status_code=400, detail="transition_type is required for tag_transition filter")
            if transition_type == "gained":
                tags_gained_filter = filter_value
            elif transition_type == "lost":
                tags_lost_filter = filter_value
            elif transition_type == "missed":
                tags_missed_filter = filter_value
        
        # Get total count of available positions
        total_count_result = await asyncio.to_thread(
            supabase_client.count_user_positions,
            user_id=user_id,
            tags_gained_filter=tags_gained_filter,
            tags_lost_filter=tags_lost_filter,
            tags_missed_filter=tags_missed_filter,
            min_cp_loss=min_cp_loss,
            error_categories=["blunder", "mistake"],
            phase_filter=phase_filter,
            opening_name_filter=opening_name_filter,
            piece_type_filter=piece_type_filter,
            time_bucket_filter=time_bucket_filter
        )
        total_count = total_count_result.get("count", 0)
        
        # Query positions using enhanced search method (prioritizes unseen/oldest)
        positions = await asyncio.to_thread(
            supabase_client.search_user_positions,
            user_id=user_id,
            tags_gained_filter=tags_gained_filter,
            tags_lost_filter=tags_lost_filter,
            tags_missed_filter=tags_missed_filter,
            min_cp_loss=min_cp_loss,
            error_categories=["blunder", "mistake"],
            limit=limit,
            prioritize_fresh=True,  # Prioritize unseen/oldest positions
            phase_filter=phase_filter,
            opening_name_filter=opening_name_filter,
            piece_type_filter=piece_type_filter,
            time_bucket_filter=time_bucket_filter
        )
        
        # Calculate average accuracy from positions (if available)
        avg_accuracy = None
        if positions:
            accuracies = []
            for pos in positions:
                # Try to get accuracy from various sources
                acc = pos.get("accuracy_pct") or pos.get("accuracy")
                if acc is not None:
                    accuracies.append(float(acc))
            if accuracies:
                avg_accuracy = sum(accuracies) / len(accuracies)
        
        # Mark positions as used (update last_used_in_drill timestamp)
        if positions:
            position_ids = [pos.get("id") for pos in positions if pos.get("id")]
            if position_ids:
                await asyncio.to_thread(
                    supabase_client.mark_positions_used,
                    position_ids=position_ids
                )
        
        accuracy_str = f"{avg_accuracy:.1f}%" if avg_accuracy is not None else "N/A"
        print(f"✅ [FILTER_QUERY] Found {len(positions)}/{total_count} positions matching filter (avg accuracy: {accuracy_str})")
        
        return {
            "positions": positions,
            "count": len(positions),
            "total_available": total_count,
            "average_accuracy": round(avg_accuracy, 1) if avg_accuracy is not None else None,
            "filter_type": filter_type,
            "filter_value": filter_value,
            "transition_type": transition_type
        }
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_detail = f"Filter query error: {str(e)}\n{traceback.format_exc()}"
        print(error_detail)
        raise HTTPException(status_code=500, detail=f"Failed to query positions by filter: {str(e)}")


class GenerateDrillsRequest(BaseModel):
    positions: List[Dict]
    drill_types: List[str] = ["tactics"]
    verify_ground_truth: bool = True
    verify_depth: int = 18


@app.post("/generate_drills")
async def generate_drills_endpoint(request: GenerateDrillsRequest):
    """Generate drills from mined positions"""
    if not drill_generator or not engine:
        raise HTTPException(status_code=503, detail="Drill generator or engine not initialized")
    
    try:
        print(f"🎯 Generating drills from {len(request.positions)} positions")
        
        drills = await drill_generator.generate_drills(
            positions=request.positions,
            drill_types=request.drill_types,
            engine=engine if request.verify_ground_truth else None,
            verify_depth=request.verify_depth
        )
        
        print(f"✅ Generated {len(drills)} drills")
        
        return {"drills": drills, "count": len(drills)}
    
    except Exception as e:
        import traceback
        error_detail = f"Generate drills error: {str(e)}\n{traceback.format_exc()}"
        print(error_detail)
        raise HTTPException(status_code=500, detail=f"Failed to generate drills: {str(e)}")


class PlanTrainingRequest(BaseModel):
    query: str
    analyzed_games: Optional[List[Dict]] = None
    user_stats: Optional[Dict] = None


@app.post("/plan_training")
async def plan_training_endpoint(request: PlanTrainingRequest):
    """Plan training based on query"""
    if not training_planner:
        raise HTTPException(status_code=503, detail="Training planner not initialized")
    
    try:
        print(f"📋 Planning training for query: {request.query}")
        
        blueprint = training_planner.plan_training(
            query=request.query,
            analyzed_games=request.analyzed_games,
            user_stats=request.user_stats
        )
        
        print(f"✅ Training blueprint created")
        
        return blueprint
    
    except Exception as e:
        import traceback
        error_detail = f"Plan training error: {str(e)}\n{traceback.format_exc()}"
        print(error_detail)
        raise HTTPException(status_code=500, detail=f"Failed to plan training: {str(e)}")


class CreateTrainingSessionRequest(BaseModel):
    username: str
    analyzed_games: List[Dict]
    training_query: str
    mode: str = "quick"


@app.post("/create_training_session")
async def create_training_session_endpoint(request: CreateTrainingSessionRequest):
    """Create complete training session from analyzed games"""
    if not training_planner or not position_miner or not drill_generator or not srs_scheduler:
        raise HTTPException(status_code=503, detail="Training system not fully initialized")
    
    try:
        print(f"\n{'='*60}")
        print(f"🎓 CREATE TRAINING SESSION")
        print(f"{'='*60}")
        print(f"   User: {request.username}")
        print(f"   Query: {request.training_query}")
        print(f"   Mode: {request.mode}")
        print(f"   Analyzed games: {len(request.analyzed_games)}")
        
        # Step 1: Plan training
        print(f"\n📋 Step 1: Planning training...")
        blueprint = training_planner.plan_training(
            query=request.training_query,
            analyzed_games=request.analyzed_games
        )
        
        # Step 2: Mine positions
        print(f"\n⛏️ Step 2: Mining positions...")
        positions = position_miner.mine_positions(
            analyzed_games=request.analyzed_games,
            focus_tags=blueprint.get("focus_tags"),
            max_positions=blueprint.get("session_config", {}).get("length", 20),
            phase_filter=blueprint.get("context_filters", {}).get("phases", [None])[0] if blueprint.get("context_filters", {}).get("phases") else None
        )
        
        # Check if no positions found
        if len(positions) == 0:
            print(f"\n⚠️ NO POSITIONS FOUND - Returning empty session")
            return {
                "session_id": None,
                "cards": [],
                "total_cards": 0,
                "blueprint": blueprint,
                "search_criteria": blueprint.get("search_criteria", []),
                "message": "No relevant positions found. Try a broader query or analyze more games.",
                "empty": True
            }
        
        # Step 3: Generate drills
        print(f"\n🎯 Step 3: Generating drills...")
        drills = await drill_generator.generate_drills(
            positions=positions,
            drill_types=blueprint.get("drill_types", ["tactics"]),
            engine=engine,
            verify_depth=15  # Faster verification
        )
        
        # Step 4: Load or create card database for user
        print(f"\n💾 Step 4: Loading card database...")
        if request.username not in card_databases:
            card_databases[request.username] = CardDatabase()
            card_databases[request.username].load(request.username)
        
        card_db = card_databases[request.username]
        
        # Step 5: Create session
        print(f"\n📚 Step 5: Building session...")
        # Add new drills to database
        from drill_card import DrillCard
        for drill in drills:
            if drill["card_id"] not in card_db.cards:
                card = DrillCard(
                    card_id=drill["card_id"],
                    fen=drill["fen"],
                    side_to_move=drill["side_to_move"],
                    best_move_san=drill["best_move_san"],
                    best_move_uci=drill["best_move_uci"],
                    tags=drill["tags"],
                    themes={},
                    difficulty=drill["difficulty"],
                    source=drill["source"]
                )
                card_db.add_card(card)
        
        # Build session from cards
        session = srs_scheduler.create_session(
            card_db=card_db,
            session_length=blueprint.get("session_config", {}).get("length", 20),
            mode=request.mode
        )
        
        # Add blueprint and metadata to session
        session["blueprint"] = blueprint
        session["lesson_goals"] = blueprint.get("lesson_goals", [])
        session["search_criteria"] = blueprint.get("search_criteria", [])
        session["empty"] = False
        
        # Save updated database
        card_db.save(request.username)
        
        print(f"\n{'='*60}")
        print(f"✅ TRAINING SESSION CREATED")
        print(f"   Session ID: {session['session_id']}")
        print(f"   Total drills: {session['total_cards']}")
        print(f"   Composition: {session['composition']}")
        print(f"   Search criteria matched: {len(session['search_criteria'])} criteria")
        print(f"{'='*60}\n")
        
        return session
    
    except Exception as e:
        import traceback
        error_detail = f"\n{'='*60}\n❌ CREATE TRAINING SESSION ERROR\n{'='*60}\n{str(e)}\n\n{traceback.format_exc()}\n{'='*60}\n"
        print(error_detail)
        raise HTTPException(status_code=500, detail=f"Failed to create training session: {str(e)}")


class UpdateDrillResultRequest(BaseModel):
    username: str
    card_id: str
    correct: bool
    time_s: float
    hints_used: int = 0


@app.post("/update_drill_result")
async def update_drill_result_endpoint(request: UpdateDrillResultRequest):
    """Update drill card after attempt"""
    try:
        if request.username not in card_databases:
            card_databases[request.username] = CardDatabase()
            card_databases[request.username].load(request.username)
        
        card_db = card_databases[request.username]
        
        if request.card_id not in card_db.cards:
            raise HTTPException(status_code=404, detail="Card not found")
        
        card = card_db.cards[request.card_id]
        card.update_srs(request.correct, request.time_s)
        card.stats["hints_used"] += request.hints_used
        
        # Save updated database
        card_db.save(request.username)
        
        return {
            "success": True,
            "new_due_date": card.srs_state["due_date"],
            "interval_days": card.srs_state["interval_days"],
            "stage": card.srs_state["stage"]
        }
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_detail = f"Update drill result error: {str(e)}\n{traceback.format_exc()}"
        print(error_detail)
        raise HTTPException(status_code=500, detail=f"Failed to update drill result: {str(e)}")


@app.get("/get_srs_queue")
async def get_srs_queue_endpoint(username: str, max_cards: int = 20):
    """Get due drills for user"""
    try:
        if username not in card_databases:
            card_databases[username] = CardDatabase()
            card_databases[username].load(username)
        
        card_db = card_databases[username]
        due_cards = card_db.get_due_cards(max_cards)
        
        return {
            "cards": [card.to_dict() for card in due_cards],
            "count": len(due_cards)
        }
    
    except Exception as e:
        import traceback
        error_detail = f"Get SRS queue error: {str(e)}\n{traceback.format_exc()}"
        print(error_detail)
        raise HTTPException(status_code=500, detail=f"Failed to get SRS queue: {str(e)}")


# ============================================================================
# BOARD TREE API ENDPOINTS
# ============================================================================

@app.get("/board/tree/get")
async def get_board_tree(
    thread_id: str = Query(..., description="Thread/tab ID"),
    include_scan: bool = Query(False, description="Include scan data")
):
    """Get the board tree for a thread"""
    if not board_tree_store:
        raise HTTPException(status_code=503, detail="Board tree store not initialized")
    
    tree = await board_tree_store.get_tree(thread_id=thread_id)
    if not tree:
        return {"success": False, "tree": None}
    
    # Convert tree to dict format
    tree_dict = {
        "root_id": tree.root_id,
        "current_id": tree.current_id,
        "nodes": {}
    }
    
    for node_id, node in tree.nodes.items():
        node_dict = {
            "id": node.id,
            "fen": node.fen,
            "parent_id": node.parent_id,
            "move_san": node.move_san,
            "is_mainline": node.is_mainline,
            "children": node.children,
        }
        if include_scan and node.scan:
            node_dict["scan"] = node.scan
        tree_dict["nodes"][node_id] = node_dict
    
    return {"success": True, "tree": tree_dict}


class InitBoardTreeRequest(BaseModel):
    thread_id: str
    start_fen: str = Field(default_factory=lambda: chess.Board().fen())


@app.post("/board/tree/init")
async def init_board_tree(request: InitBoardTreeRequest):
    """Initialize a new board tree for a thread"""
    if not board_tree_store:
        raise HTTPException(status_code=503, detail="Board tree store not initialized")
    
    # Create root node
    root_node = BoardTreeNode(
        id="root",
        fen=request.start_fen,
        parent_id=None,
        move_san="",
        is_mainline=True
    )
    
    tree = BoardTree(
        root_id="root",
        current_id="root",
        nodes={"root": root_node}
    )
    
    await board_tree_store.set_tree(thread_id=request.thread_id, tree=tree)
    return {"success": True, "tree_id": "root"}


class AddMoveToTreeRequest(BaseModel):
    thread_id: str
    from_fen: str
    move_san: str
    parent_id: str = "root"


@app.post("/board/tree/add_move")
async def add_move_to_tree(request: AddMoveToTreeRequest):
    """Add a move to the board tree"""
    if not board_tree_store:
        raise HTTPException(status_code=503, detail="Board tree store not initialized")
    
    tree = await board_tree_store.get_tree(thread_id=request.thread_id)
    if not tree:
        raise HTTPException(status_code=404, detail="Tree not found. Call /board/tree/init first")
    
    # Apply move to get new FEN
    board = chess.Board(request.from_fen)
    try:
        move = board.parse_san(request.move_san)
        board.push(move)
        new_fen = board.fen()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid move: {e}")
    
    # Create new node
    node_id = new_node_id()
    new_node = BoardTreeNode(
        id=node_id,
        fen=new_fen,
        parent_id=request.parent_id,
        move_san=request.move_san,
        is_mainline=False  # Could be determined by logic
    )
    
    # Add to parent's children list
    parent_node = tree.nodes.get(request.parent_id)
    if parent_node:
        if node_id not in parent_node.children:
            parent_node.children.append(node_id)
    
    tree.nodes[node_id] = new_node
    tree.current_id = node_id
    
    await board_tree_store.set_tree(thread_id=request.thread_id, tree=tree)
    return {"success": True, "node_id": node_id}


class BaselineIntuitionRequest(BaseModel):
    fen: Optional[str] = None
    thread_id: Optional[str] = None


@app.post("/board/baseline_intuition_start")
async def baseline_intuition_start(request: BaselineIntuitionRequest):
    """Start baseline intuition analysis (placeholder)"""
    # This endpoint might need actual implementation based on your needs
    return {"success": True, "message": "Baseline intuition started"}


class LogBehaviorRequest(BaseModel):
    behavior_type: str
    data: Dict[str, Any] = Field(default_factory=dict)


@app.post("/learning/log_behavior")
async def log_behavior(request: LogBehaviorRequest):
    """Log user behavior for learning (placeholder)"""
    # This endpoint might need actual implementation based on your needs
    return {"success": True, "message": "Behavior logged"}


if __name__ == "__main__":
    import uvicorn
    # Use PORT environment variable (set by Render/Heroku/etc.) or default to 8000
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)

