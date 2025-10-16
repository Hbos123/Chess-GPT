import os
import asyncio
import math
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager
from io import StringIO
import urllib.parse
import urllib.request

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import chess
import chess.engine
import chess.pgn
from dotenv import load_dotenv
import json
from openai import OpenAI

load_dotenv()

# Initialize OpenAI client
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Global engine instance
engine: Optional[chess.engine.SimpleEngine] = None

STOCKFISH_PATH = os.getenv("STOCKFISH_PATH", "./stockfish")

# System prompt for the LLM
SYSTEM_PROMPT = """You are Chess GPT. You must not invent concrete evaluations, tablebase facts, or long variations. For any concrete claims (evals, PVs, winning lines, best moves), you rely on tool outputs the client provides from backend endpoints:

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
    global engine
    try:
        # Close existing engine if any
        if engine:
            try:
                await engine.quit()
            except:
                pass
        
        if os.path.exists(STOCKFISH_PATH):
            transport, engine = await chess.engine.popen_uci(STOCKFISH_PATH)
            await engine.configure({"Threads": 2, "Hash": 128})
            print(f"✓ Stockfish engine initialized at {STOCKFISH_PATH}")
            return True
        else:
            print(f"⚠ Stockfish not found at {STOCKFISH_PATH}")
            engine = None
            return False
    except Exception as e:
        print(f"⚠ Failed to initialize Stockfish: {e}")
        engine = None
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup the Stockfish engine."""
    global engine
    await initialize_engine()
    
    yield
    
    if engine:
        try:
            await engine.quit()
        except:
            pass


app = FastAPI(title="Chess GPT Backend", version="1.0.0", lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Helper Functions
# ============================================================================

def win_prob_from_cp(cp: int) -> float:
    """Convert centipawn eval to win probability using logistic function."""
    return 1.0 / (1.0 + math.exp(-cp / 400.0))


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
        info = await engine.analyse(
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
        info = await engine.analyse(
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


# ============================================================================
# Endpoints
# ============================================================================

@app.get("/")
async def root():
    return {"message": "Chess GPT Backend API", "status": "running"}


@app.get("/meta")
async def get_meta():
    """Return metadata about the API."""
    return {
        "name": "Chess GPT",
        "version": "1.0.0",
        "modes": ["PLAY", "ANALYZE", "TACTICS", "DISCUSS"],
        "system_prompt": SYSTEM_PROMPT
    }


@app.get("/analyze_position")
async def analyze_position(
    fen: str = Query(..., description="FEN string of the position"),
    lines: int = Query(3, ge=1, le=5, description="Number of candidate lines"),
    depth: int = Query(16, ge=10, le=20, description="Search depth")
):
    """Analyze a chess position and return evaluation, candidates, threats, and themes."""
    if not engine:
        raise HTTPException(status_code=503, detail="Stockfish engine not available")
    
    try:
        board = chess.Board(fen)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid FEN: {str(e)}")
    
    try:
        # Get main evaluation
        try:
            main_info = await engine.analyse(board, chess.engine.Limit(depth=depth))
            score = main_info.get("score")
            
            if score and score.is_mate():
                mate_in = score.relative.mate()
                eval_cp = 10000 if mate_in > 0 else -10000
            elif score:
                eval_cp = score.relative.score(mate_score=10000)
            else:
                eval_cp = 0
        except chess.engine.EngineTerminatedError as e:
            # Engine crashed - try to reinitialize and retry once
            print(f"⚠ Engine crashed, reinitializing...")
            if await initialize_engine():
                print("✓ Engine reinitialized, retrying analysis...")
                main_info = await engine.analyse(board, chess.engine.Limit(depth=depth))
                score = main_info.get("score")
                
                if score and score.is_mate():
                    mate_in = score.relative.mate()
                    eval_cp = 10000 if mate_in > 0 else -10000
                elif score:
                    eval_cp = score.relative.score(mate_score=10000)
                else:
                    eval_cp = 0
            else:
                raise HTTPException(status_code=503, detail="Engine crashed and could not be reinitialized")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Engine analysis failed: {str(e)}")
        
        # Calculate win probability
        win_prob = win_prob_from_cp(eval_cp)
        
        # Get game phase
        phase = game_phase(board)
        
        # Get candidate moves
        candidates = await probe_candidates(board, multipv=lines, depth=depth)
        
        # Find threats
        threats = await find_threats(board)
        
        # Piece quality analysis
        piece_quality_map = {"W": {}, "B": {}}
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if piece:
                quality = piece_quality(board, square)
                side = "W" if piece.color == chess.WHITE else "B"
                square_name = chess.square_name(square)
                piece_name = piece.symbol().upper() + square_name
                piece_quality_map[side][piece_name] = quality
        
        # Extract themes
        themes = extract_themes(board, eval_cp)
        
        return {
            "eval_cp": eval_cp,
            "win_prob": round(win_prob, 2),
            "phase": phase,
            "candidate_moves": candidates,
            "threats": threats,
            "piece_quality": piece_quality_map,
            "themes": themes
        }
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Catch any other unexpected errors
        import traceback
        error_detail = f"Position analysis error: {str(e)}\n{traceback.format_exc()}"
        print(error_detail)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


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
    
    # Configure engine strength if requested
    if request.engine_elo:
        try:
            await engine.configure({
                "UCI_LimitStrength": True,
                "UCI_Elo": request.engine_elo
            })
        except:
            pass  # Some engines don't support strength limiting
    
    # Get engine move
    try:
        time_limit = chess.engine.Limit(time=request.time_ms / 1000.0) if request.time_ms else chess.engine.Limit(depth=12)
        result = await engine.play(board, time_limit)
        engine_move = result.move
        engine_move_san = board.san(engine_move)
        board.push(engine_move)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Engine move failed: {str(e)}")
    
    # Reset engine to full strength
    if request.engine_elo:
        try:
            await engine.configure({"UCI_LimitStrength": False})
        except:
            pass
    
    # Get eval after both moves
    try:
        eval_info = await engine.analyse(board, chess.engine.Limit(depth=12))
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
    Analyze a specific move by comparing:
    1. Position before the move (full analysis)
    2. Position after the played move (full analysis)
    3. Position after the best move (full analysis, if different)
    
    Returns detailed comparison of themes, strengths, weaknesses, threats.
    """
    if not engine:
        raise HTTPException(status_code=503, detail="Stockfish engine not available")
    
    try:
        board = chess.Board(fen)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid FEN: {str(e)}")
    
    try:
        # Get FULL analysis of position BEFORE the move
        analysis_before = await analyze_position(fen, lines=3, depth=depth)
        
        # Get the best move
        candidates = analysis_before.get("candidate_moves", [])
        if not candidates:
            raise HTTPException(status_code=500, detail="Could not find best move")
        
        best_move_san = candidates[0]["move"]
        
        # Parse and play the user's move
        try:
            played_move = board.parse_san(move_san)
            if played_move not in board.legal_moves:
                raise HTTPException(status_code=400, detail=f"Illegal move: {move_san}")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid move notation: {str(e)}")
        
        # Analyze position AFTER played move (FULL analysis)
        board_after_played = board.copy()
        board_after_played.push(played_move)
        fen_after_played = board_after_played.fen()
        analysis_after_played = await analyze_position(fen_after_played, lines=3, depth=depth)
        
        # Check if played move is the best move
        is_best_move = (move_san == best_move_san)
        
        # If not best move, analyze position after best move (FULL analysis)
        analysis_after_best = None
        if not is_best_move:
            board_after_best = board.copy()
            best_move_obj = board_after_best.parse_san(best_move_san)
            board_after_best.push(best_move_obj)
            fen_after_best = board_after_best.fen()
            analysis_after_best = await analyze_position(fen_after_best, lines=3, depth=depth)
        
        # Helper function to get active/inactive pieces
        def get_piece_activity(piece_quality: dict, side: str) -> dict:
            pieces = piece_quality.get(side, {})
            active = [p for p, q in pieces.items() if q >= 0.6]
            inactive = [p for p, q in pieces.items() if q <= 0.3]
            return {"active": active, "inactive": inactive}
        
        # Helper function to compare two full analyses
        def compare_full_analyses(before: dict, after: dict) -> dict:
            """Compare two full position analyses and track what changed."""
            eval_before = before.get("eval_cp", 0)
            eval_after = after.get("eval_cp", 0)
            eval_change = eval_after - eval_before
            
            # Themes comparison
            themes_before = set(before.get("themes", []))
            themes_after = set(after.get("themes", []))
            themes_gained = list(themes_after - themes_before)
            themes_lost = list(themes_before - themes_after)
            themes_kept = list(themes_before & themes_after)
            
            # Threats comparison
            threats_before = before.get("threats", [])
            threats_after = after.get("threats", [])
            
            # Piece activity (strengths/weaknesses)
            activity_before = get_piece_activity(before.get("piece_quality", {}), "W")
            activity_after = get_piece_activity(after.get("piece_quality", {}), "W")
            
            pieces_activated = [p for p in activity_after["active"] if p not in activity_before["active"]]
            pieces_deactivated = [p for p in activity_before["active"] if p not in activity_after["active"]]
            
            return {
                "evalBefore": eval_before,
                "evalAfter": eval_after,
                "evalChange": eval_change,
                "evalChangeMagnitude": abs(eval_change),
                "improvedPosition": eval_change > 0,
                "worsenedPosition": eval_change < 0,
                
                # Themes changes
                "themesBefore": list(themes_before),
                "themesAfter": list(themes_after),
                "themesGained": themes_gained,
                "themesLost": themes_lost,
                "themesKept": themes_kept,
                
                # Threats changes
                "threatsCountBefore": len(threats_before),
                "threatsCountAfter": len(threats_after),
                "threatsBefore": threats_before,
                "threatsAfter": threats_after,
                "threatsGained": len(threats_after) - len(threats_before),
                
                # Piece activity (strengths/weaknesses)
                "activePiecesBefore": activity_before["active"],
                "activePiecesAfter": activity_after["active"],
                "inactivePiecesBefore": activity_before["inactive"],
                "inactivePiecesAfter": activity_after["inactive"],
                "piecesActivated": pieces_activated,
                "piecesDeactivated": pieces_deactivated,
                
                # Top moves
                "topMovesBefore": [c["move"] for c in before.get("candidate_moves", [])[:3]],
                "topMovesAfter": [c["move"] for c in after.get("candidate_moves", [])[:3]],
                "bestMoveAfter": after.get("candidate_moves", [{}])[0].get("move"),
                "bestEvalAfter": after.get("candidate_moves", [{}])[0].get("eval_cp")
            }
        
        # Generate report for played move
        played_report = compare_full_analyses(analysis_before, analysis_after_played)
        played_report["movePlayed"] = move_san
        played_report["wasTheBestMove"] = is_best_move
        played_report["analysisAfter"] = analysis_after_played  # Include full analysis
        
        # Generate report for best move (if different)
        best_report = None
        if not is_best_move and analysis_after_best:
            best_report = compare_full_analyses(analysis_before, analysis_after_best)
            best_report["movePlayed"] = best_move_san
            best_report["wasTheBestMove"] = True
            best_report["evalDifference"] = best_report["evalAfter"] - played_report["evalAfter"]
            best_report["analysisAfter"] = analysis_after_best  # Include full analysis
    
        return {
            "fenBefore": fen,
            "movePlayed": move_san,
            "bestMove": best_move_san,
            "isPlayedMoveBest": is_best_move,
            "analysisBefore": analysis_before,
            "playedMoveReport": played_report,
            "bestMoveReport": best_report
        }
    except Exception as e:
        import traceback
        error_detail = f"Move analysis error: {str(e)}\n{traceback.format_exc()}"
        print(error_detail)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@app.post("/review_game")
async def review_game(pgn_string: str = Query(..., description="PGN string of the game")):
    """
    Comprehensive game review: analyze every move with Stockfish.
    Returns move-by-move analysis with quality, critical moves, missed wins, etc.
    """
    if not engine:
        raise HTTPException(status_code=503, detail="Stockfish engine not available")
    
    try:
        # Clean PGN: remove comments {like this} and extra whitespace
        import re
        cleaned_pgn = re.sub(r'\{[^}]*\}', '', pgn_string)  # Remove comments
        cleaned_pgn = ' '.join(cleaned_pgn.split())  # Normalize whitespace
        
        print(f"Original PGN: {pgn_string}")
        print(f"Cleaned PGN: {cleaned_pgn}")
        
        # Parse PGN
        pgn_io = chess.pgn.read_game(StringIO(cleaned_pgn))
        if not pgn_io:
            raise HTTPException(status_code=400, detail="Invalid PGN")
        
        board = chess.Board()
        move_analyses = []
        move_number = 1
        last_theory_move = -1
        last_phase = "opening"
        last_eval = 0
        
        # Iterate through all moves
        for move in pgn_io.mainline_moves():
            fen_before = board.fen()
            
            # Convert move to SAN BEFORE pushing (need current board state)
            move_san = board.san(move)
            
            # Analyze position BEFORE the move
            analysis_before = await analyze_with_depth(board, depth=18, multipv=3)
            eval_before = analysis_before["eval_cp"]
            
            # Make the move
            board.push(move)
            fen_after = board.fen()
            
            # Analyze position AFTER the move
            analysis_after = await analyze_with_depth(board, depth=18, multipv=3)
            eval_after = analysis_after["eval_cp"]
            
            # Check Lichess masters database for theory FIRST
            theory_check = check_lichess_masters(fen_before)
            is_theory = theory_check['isTheory']
            opening_name = theory_check['opening']
            
            # Calculate move quality
            eval_change = abs(eval_after - eval_before)
            cp_loss = eval_change
            
            # Determine quality - THEORY moves override all other classifications
            if is_theory:
                quality = "theory"
            elif cp_loss == 0:
                quality = "best"
            elif cp_loss < 30:
                quality = "excellent"
            elif cp_loss < 50:
                quality = "good"
            elif cp_loss < 80:
                quality = "inaccuracy"
            elif cp_loss < 200:
                quality = "mistake"
            else:
                quality = "blunder"
            
            # Get best move and alternatives
            candidates = analysis_before.get("candidate_moves", [])
            best_move = candidates[0]["move"] if candidates else move_san
            second_best = candidates[1]["move"] if len(candidates) > 1 else None
            
            # Check if the played move matches the best move
            played_best_move = (move_san == best_move)
            
            # Critical move detection (gap > 50cp to 2nd best)
            is_critical = False
            gap_to_second = 0
            if len(candidates) >= 2:
                best_eval = candidates[0]["eval_cp"]
                second_eval = candidates[1]["eval_cp"]
                gap_to_second = abs(best_eval - second_eval)
                # Only mark as critical if THIS move was played AND gap > 50cp
                is_critical = played_best_move and gap_to_second > 50
            
            # Missed win detection - only if did NOT play the best move
            is_missed_win = False
            if not played_best_move and not is_theory and eval_before > 50 and gap_to_second > 50:
                is_missed_win = True
            
            # Determine phase with sophisticated chess-specific rules
            piece_count = len(board.piece_map())
            queens = len([p for p in board.piece_map().values() if p.piece_type == chess.QUEEN])
            
            # OPENING → MIDDLEGAME: Count criteria (need 3+ to be in middlegame)
            opening_to_middle_criteria = 0
            
            # 1. Both kings have castled (or won't castle and king safety resolved)
            white_king_moved = board.has_kingside_castling_rights(chess.WHITE) == False and board.has_queenside_castling_rights(chess.WHITE) == False
            black_king_moved = board.has_kingside_castling_rights(chess.BLACK) == False and board.has_queenside_castling_rights(chess.BLACK) == False
            
            white_king_sq = board.king(chess.WHITE)
            black_king_sq = board.king(chess.BLACK)
            
            # Check if castled (king on g1/c1 for white, g8/c8 for black) or clearly won't
            white_castled = white_king_sq in [chess.G1, chess.C1] or (white_king_moved and move_number > 10)
            black_castled = black_king_sq in [chess.G8, chess.C8] or (black_king_moved and move_number > 10)
            
            if white_castled and black_castled:
                opening_to_middle_criteria += 1
            
            # 2. Development done: all minor pieces out, rooks connected
            def development_complete():
                # Count minor pieces (knights, bishops) on starting squares
                starting_minors = 0
                minor_starting_squares = [chess.B1, chess.C1, chess.F1, chess.G1,  # White
                                         chess.B8, chess.C8, chess.F8, chess.G8]  # Black
                for sq in minor_starting_squares:
                    piece = board.piece_at(sq)
                    if piece and piece.piece_type in [chess.KNIGHT, chess.BISHOP]:
                        starting_minors += 1
                
                # Check if rooks are connected (no pieces between them)
                def rooks_connected_for_color(color):
                    rooks = list(board.pieces(chess.ROOK, color))
                    if len(rooks) < 2:
                        return False
                    rank = 0 if color == chess.WHITE else 7
                    rook_files = [chess.square_file(r) for r in rooks if chess.square_rank(r) == rank]
                    if len(rook_files) < 2:
                        return False
                    min_file, max_file = min(rook_files), max(rook_files)
                    for file in range(min_file + 1, max_file):
                        if board.piece_at(chess.square(file, rank)) is not None:
                            return False
                    return True
                
                white_rooks_connected = rooks_connected_for_color(chess.WHITE)
                black_rooks_connected = rooks_connected_for_color(chess.BLACK)
                
                return starting_minors <= 2 and (white_rooks_connected or black_rooks_connected)
            
            if development_complete():
                opening_to_middle_criteria += 1
            
            # 3. Central pawn tension decided (d4/d5, e4/e5 played, exchanged, or blocked)
            def central_tension_resolved():
                # Check if central pawns have been played/exchanged
                d4_pawn = board.piece_at(chess.D4)
                d5_pawn = board.piece_at(chess.D5)
                e4_pawn = board.piece_at(chess.E4)
                e5_pawn = board.piece_at(chess.E5)
                
                # Count central pawn presence
                central_pawns = sum([
                    1 if d4_pawn and d4_pawn.piece_type == chess.PAWN else 0,
                    1 if d5_pawn and d5_pawn.piece_type == chess.PAWN else 0,
                    1 if e4_pawn and e4_pawn.piece_type == chess.PAWN else 0,
                    1 if e5_pawn and e5_pawn.piece_type == chess.PAWN else 0
                ])
                
                # Tension resolved if central pawns are fixed or exchanged
                return central_pawns >= 1 or move_number > 8
            
            if central_tension_resolved():
                opening_to_middle_criteria += 1
            
            # 4. Thematic pawn break played (structure is fixed)
            # Detected by: pawn captures, pawn advances past 4th/5th rank
            def pawn_break_played():
                advanced_pawns = 0
                for square in chess.SQUARES:
                    piece = board.piece_at(square)
                    if piece and piece.piece_type == chess.PAWN:
                        rank = chess.square_rank(square)
                        # White pawns on 5th+ rank, Black pawns on 4th- rank
                        if (piece.color == chess.WHITE and rank >= 4) or \
                           (piece.color == chess.BLACK and rank <= 3):
                            advanced_pawns += 1
                return advanced_pawns >= 2
            
            if pawn_break_played():
                opening_to_middle_criteria += 1
            
            # 5. Out of theory (already tracked)
            if not is_theory and move_number > 8:
                opening_to_middle_criteria += 1
            
            # MIDDLEGAME → ENDGAME: Count criteria (need 2-3 to be in endgame)
            middle_to_end_criteria = 0
            
            # 1. Queens off and material reduced
            if queens == 0:
                middle_to_end_criteria += 1
                # Additional check: few pieces remain
                if piece_count <= 14:
                    middle_to_end_criteria += 1
            
            # 2. Kings can safely centralize
            def kings_can_centralize():
                if queens > 0:  # Not safe with queens on board
                    return False
                # Check if kings are moving toward center (d/e files)
                white_king_file = chess.square_file(white_king_sq)
                black_king_file = chess.square_file(black_king_sq)
                # Kings on c-f files (approaching center)
                return white_king_file in [2, 3, 4, 5] or black_king_file in [2, 3, 4, 5]
            
            if kings_can_centralize():
                middle_to_end_criteria += 1
            
            # 3. Pawn structure/majorities are the main plan (few pieces, pawns matter)
            if piece_count <= 12:
                middle_to_end_criteria += 1
            
            # Determine phase based on criteria counts
            if last_phase == "opening":
                if opening_to_middle_criteria >= 3:
                    phase = "middlegame"
                else:
                    phase = "opening"
            elif last_phase == "middlegame":
                if middle_to_end_criteria >= 2:
                    phase = "endgame"
                else:
                    phase = "middlegame"
            else:
                # Already in endgame or starting position
                if middle_to_end_criteria >= 2:
                    phase = "endgame"
                elif opening_to_middle_criteria >= 3:
                    phase = "middlegame"
                else:
                    phase = "opening"
            
            # Track theory end
            left_theory = False
            if is_theory:
                last_theory_move = move_number
            elif last_theory_move >= 0 and not is_theory:
                left_theory = True  # First non-theory move
            
            # Track phase transitions
            entered_middlegame = False
            if last_phase == "opening" and phase == "middlegame":
                entered_middlegame = True
            last_phase = phase
            
            # Track advantage threshold crossings - only trigger HIGHEST threshold crossed
            crossed_100 = False
            crossed_200 = False
            crossed_300 = False
            
            # Only mark if we actually crossed from below to above
            if abs(last_eval) < 100 and abs(eval_after) >= 100:
                # Determine which threshold was actually crossed
                if abs(eval_after) >= 300:
                    crossed_300 = True
                elif abs(eval_after) >= 200:
                    crossed_200 = True
                else:
                    crossed_100 = True
            elif abs(last_eval) < 200 and abs(eval_after) >= 200:
                # Already above 100, now crossing 200
                if abs(eval_after) >= 300:
                    crossed_300 = True
                else:
                    crossed_200 = True
            elif abs(last_eval) < 300 and abs(eval_after) >= 300:
                # Already above 200, now crossing 300
                crossed_300 = True
            
            last_eval = eval_after
            
            # Advantage level
            adv = getAdvantageLevel(eval_after)
            
            # Calculate accuracy for non-theory and non-best moves using exponential formula
            accuracy = 100.0  # Default to 100% for theory and best moves
            if not is_theory and quality != "best":
                import math
                
                # Get best move eval (from candidates before the move)
                best_eval = candidates[0]["eval_cp"] if candidates else eval_before
                
                # CPL = centipawn loss
                CPL = cp_loss
                
                # E = best-move eval in pawns (clamp to ±24)
                E = best_eval / 100.0  # Convert centipawns to pawns
                E = max(-24, min(24, E))  # Clamp to ±24
                
                # Accuracy% = 100 * exp( - CPL / ( 89.6284023545 + 44.8142011772 * |E| ) )
                denominator = 89.6284023545 + 44.8142011772 * abs(E)
                
                if CPL == 0:
                    accuracy = 100.0
                else:
                    accuracy = 100.0 * math.exp(-CPL / denominator)
                    # Clamp between 0 and 100
                    accuracy = max(0, min(100, accuracy))
            
            move_analyses.append({
                "moveNumber": move_number,
                "move": move_san,
                "fen": fen_after,
                "fenBefore": fen_before,
                "color": "w" if board.turn == chess.BLACK else "b",
                "evalBefore": eval_before,
                "evalAfter": eval_after,
                "evalChange": eval_change,
                "cpLoss": cp_loss,
                "quality": quality,
                "accuracy": round(accuracy, 1),  # NEW: accuracy percentage
                "isCritical": is_critical,
                "isMissedWin": is_missed_win,
                "isTheoryMove": is_theory,
                "openingName": opening_name,
                "bestMove": best_move,
                "secondBestMove": second_best,
                "gapToSecondBest": gap_to_second,
                "phase": phase,
                "advantageLevel": adv["level"],
                "advantageFor": adv["for"],
                "leftTheory": left_theory,
                "enteredMiddlegame": entered_middlegame,
                "crossed100": crossed_100,
                "crossed200": crossed_200,
                "crossed300": crossed_300
            })
            
            if board.turn == chess.BLACK:
                move_number += 1
        
        # Calculate phase-based accuracy statistics
        opening_moves = [m for m in move_analyses if m["phase"] == "opening"]
        middlegame_moves = [m for m in move_analyses if m["phase"] == "middlegame"]
        endgame_moves = [m for m in move_analyses if m["phase"] == "endgame"]
        
        def calc_avg_accuracy(moves_list, color=None):
            """Calculate average accuracy for a list of moves, optionally filtered by color."""
            if color:
                moves_list = [m for m in moves_list if m["color"] == color]
            if not moves_list:
                return 100.0
            accuracies = [m["accuracy"] for m in moves_list]
            return round(sum(accuracies) / len(accuracies), 1)
        
        # Overall accuracy
        white_moves = [m for m in move_analyses if m["color"] == "w"]
        black_moves = [m for m in move_analyses if m["color"] == "b"]
        
        accuracy_stats = {
            "overall": {
                "white": calc_avg_accuracy(white_moves),
                "black": calc_avg_accuracy(black_moves)
            },
            "opening": {
                "white": calc_avg_accuracy(opening_moves, "w"),
                "black": calc_avg_accuracy(opening_moves, "b")
            },
            "middlegame": {
                "white": calc_avg_accuracy(middlegame_moves, "w"),
                "black": calc_avg_accuracy(middlegame_moves, "b")
            },
            "endgame": {
                "white": calc_avg_accuracy(endgame_moves, "w"),
                "black": calc_avg_accuracy(endgame_moves, "b")
            }
        }
        
        # Detect game tags based on evaluation trajectory
        game_tags = detect_game_tags(move_analyses)
        
        return {
            "moves": move_analyses,
            "accuracyStats": accuracy_stats,
            "gameTags": game_tags
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Review error: {str(e)}")


async def analyze_with_depth(board: chess.Board, depth: int = 18, multipv: int = 1):
    """Helper to analyze position at specific depth."""
    if not engine:
        return {"eval_cp": 0, "candidate_moves": []}
    
    try:
        info = await engine.analyse(
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


def getAdvantageLevel(cp: int):
    """Helper matching frontend logic."""
    absCp = abs(cp)
    if absCp < 50:
        return {"level": "equal", "for": "equal"}
    elif absCp < 100:
        level = "slight"
    elif absCp < 200:
        level = "clear"
    else:
        level = "strong"
    
    advantageFor = "white" if cp > 0 else "black"
    return {"level": level, "for": advantageFor}


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
    """Check if position exists in Lichess masters database."""
    try:
        url = f"https://explorer.lichess.ovh/masters?fen={urllib.parse.quote(fen)}"
        with urllib.request.urlopen(url, timeout=3) as response:
            data = json.loads(response.read())
            # If there are games in the database with this position, it's theory
            total_games = sum(move.get('white', 0) + move.get('draws', 0) + move.get('black', 0) 
                            for move in data.get('moves', []))
            return {
                'isTheory': total_games > 0,
                'totalGames': total_games,
                'opening': data.get('opening', {}).get('name', 'Unknown')
            }
    except:
        return {'isTheory': False, 'totalGames': 0, 'opening': None}


class LLMRequest(BaseModel):
    messages: List[Dict[str, str]]
    model: str = "gpt-4o-mini"
    temperature: float = 0.7


@app.post("/llm_chat")
async def llm_chat(request: LLMRequest):
    """
    Proxy endpoint for OpenAI chat completions to avoid CORS issues.
    """
    try:
        completion = openai_client.chat.completions.create(
            model=request.model,
            messages=request.messages,
            temperature=request.temperature
        )
        
        return {
            "content": completion.choices[0].message.content,
            "model": completion.model,
            "usage": {
                "prompt_tokens": completion.usage.prompt_tokens,
                "completion_tokens": completion.usage.completion_tokens,
                "total_tokens": completion.usage.total_tokens
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM error: {str(e)}")


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
            model="gpt-4o-mini",
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

async def generate_position_for_topic(topic_code: str, side: str = "white") -> Dict[str, Any]:
    """Generate a training position for a specific topic"""
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not available")
    
    topic = LESSON_TOPICS.get(topic_code)
    if not topic:
        raise HTTPException(status_code=404, detail=f"Topic {topic_code} not found")
    
    # For now, generate sample positions based on topic category
    # In production, this would use sophisticated FEN construction
    
    if topic_code == "PS.IQP":
        # IQP position template
        fen = "r1bq1rk1/pp1nbppp/2p1pn2/3p4/2PP4/2N1PN2/PP2BPPP/R1BQ1RK1 w - - 0 9"
        objective = "Play for the e5 break with your isolated d-pawn. Your pieces are active and White has dynamic compensation for the structural weakness."
        
    elif topic_code == "PS.CARLSBAD":
        # Carlsbad structure
        fen = "r1bq1rk1/pp2bppp/2n1pn2/2pp4/2PP4/2N1PN2/PP2BPPP/R1BQ1RK1 w - - 0 9"
        objective = "Execute the minority attack with b4-b5 to create weaknesses on Black's queenside. Double rooks on the c-file."
        
    elif topic_code == "ST.OUTPOST":
        # Knight outpost position
        fen = "r1bqr1k1/pp1nbppp/2p1pn2/3p4/2PP4/2N1PN2/PP2BPPP/R1BQR1K1 w - - 0 11"
        objective = "Establish a knight on the e5 outpost. This square is protected by your pawn and cannot be attacked by enemy pawns."
        
    elif topic_code == "ST.SEVENTH_RANK":
        # 7th rank invasion
        fen = "2kr3r/ppp2ppp/3b1n2/3p4/3P4/2PB1N2/PP3PPP/2KR3R w - - 0 15"
        objective = "Invade the 7th rank with your rook. The 7th rank is where you can attack pawns and restrict the enemy king."
        
    elif topic_code == "TM.FORK":
        # Fork tactics
        fen = "r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 5"
        objective = "Find the knight fork that wins material. Look for moves that attack two pieces at once."
        
    elif topic_code == "TM.PIN":
        # Pin tactics
        fen = "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4"
        objective = "Find the pin that restricts your opponent's pieces. A pinned piece cannot move without exposing a more valuable piece."
        
    else:
        # Default training position
        fen = "rnbqkb1r/ppp2ppp/4pn2/3p4/2PP4/2N2N2/PP2PPPP/R1BQKB1R b KQkq - 0 5"
        objective = f"Practice the concept: {topic['name']}"
    
    # Analyze the position
    try:
        board = chess.Board(fen)
        
        # Get candidate moves
        main_info = await engine.analyse(board, chess.engine.Limit(depth=16), multipv=3)
        
        candidates = []
        if hasattr(main_info, '__iter__'):
            for i, info in enumerate(main_info[:3]):
                pv = info.get("pv", [])
                if pv:
                    # Create a copy of the board to convert PV to SAN without modifying original
                    temp_board = board.copy()
                    move_san = temp_board.san(pv[0])
                    score = info.get("score")
                    eval_cp = score.relative.score(mate_score=10000) if score else 0
                    
                    # Convert entire PV line to SAN
                    pv_san = []
                    temp_board = board.copy()
                    for move in pv[:5]:
                        pv_san.append(temp_board.san(move))
                        temp_board.push(move)
                    
                    candidates.append({
                        "move": move_san,
                        "eval_cp": eval_cp,
                        "pv": " ".join(pv_san)
                    })
        
        # Generate hints based on topic
        hints = []
        if "outpost" in topic_code.lower():
            hints = ["Look for squares that are protected by your pawns", "Enemy pawns should not be able to attack this square"]
        elif "seventh" in topic_code.lower():
            hints = ["The 7th rank is often called the 'pig' rank", "Rooks on the 7th attack pawns and restrict the king"]
        elif "iqp" in topic_code.lower():
            hints = ["The e5 break is typical in IQP positions", "Keep your pieces active to compensate for the weak pawn"]
        elif "carlsbad" in topic_code.lower():
            hints = ["b4-b5 is the key minority attack move", "Create a weakness on c6 by forcing ...cxb5"]
        else:
            hints = [f"Focus on: {topic['goals'][0]}", f"Key theme: {topic['name']}"]
        
        # Generate the ideal solution line (best PV, 3-5 moves)
        ideal_line = []
        ideal_pgn = ""
        if main_info and hasattr(main_info, '__iter__') and len(list(main_info)) > 0:
            best_info = list(main_info)[0]
            pv = best_info.get("pv", [])
            if pv:
                temp_board = board.copy()
                move_num = temp_board.fullmove_number
                is_white = temp_board.turn
                pgn_parts = []
                
                for i, move in enumerate(pv[:5]):  # Take first 5 moves of best line
                    move_san = temp_board.san(move)
                    ideal_line.append(move_san)
                    
                    # Build PGN
                    if temp_board.turn:  # White's turn
                        pgn_parts.append(f"{temp_board.fullmove_number}. {move_san}")
                    else:  # Black's turn
                        if i == 0 and not is_white:  # First move is black
                            pgn_parts.append(f"{temp_board.fullmove_number}... {move_san}")
                        else:
                            pgn_parts.append(move_san)
                    
                    temp_board.push(move)
                
                ideal_pgn = " ".join(pgn_parts)
        
        return {
            "fen": fen,
            "side": side,
            "objective": objective,
            "themes": [topic_code],
            "candidates": candidates,
            "hints": hints,
            "difficulty": topic["difficulty"],
            "topic_name": topic["name"],
            "ideal_line": ideal_line,  # List of moves in SAN
            "ideal_pgn": ideal_pgn     # Human-readable PGN
        }
        
    except Exception as e:
        import traceback
        print(f"Position generation error: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to analyze position: {str(e)}")

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
        main_info = await engine.analyse(board, chess.engine.Limit(depth=16), multipv=3)
        
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
        after_info = await engine.analyse(board, chess.engine.Limit(depth=14))
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

