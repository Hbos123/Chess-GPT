"""
Engine Correlation Tool
Measures how closely a player's moves match engine recommendations
"""

import chess
import chess.pgn
from io import StringIO
from typing import Dict, List, Optional, Literal
import asyncio


async def engine_correlation(
    pgn: str,
    depth: int = 25,
    top_n: int = 3,
    exclude_book_moves: int = 10,
    exclude_forced: bool = True,
    engine_queue = None
) -> Dict:
    """
    Calculate how closely player moves match engine's top choices.
    
    Args:
        pgn: PGN string of the game
        depth: Stockfish analysis depth
        top_n: Match against top N engine moves
        exclude_book_moves: Skip first N moves (opening theory)
        exclude_forced: Exclude positions with only 1-2 legal moves
        engine_queue: Stockfish engine queue
        
    Returns:
        {
            "top1_match": 0.67,       # % matching engine's #1 choice
            "top3_match": 0.89,       # % matching any of top 3
            "critical_match": 0.92,   # % in complex positions only
            "average_rank": 1.8,      # Average rank of played move in engine list
            "suspicion_level": "normal",  # normal/elevated/high/extreme
            "move_details": [
                {
                    "move_num": 15,
                    "played": "Nxe5",
                    "engine_top3": ["Nxe5", "Qd2", "Bf4"],
                    "rank": 1,
                    "matched_top1": True,
                    "matched_top3": True,
                    "complexity": "hard",
                    "cp_loss": 0
                }
            ],
            "complexity_breakdown": {
                "easy": {"total": 10, "matched": 9},
                "moderate": {"total": 15, "matched": 12},
                "hard": {"total": 8, "matched": 7},
                "very_hard": {"total": 3, "matched": 3}
            }
        }
    """
    # Parse PGN
    try:
        game = chess.pgn.read_game(StringIO(pgn))
        if not game:
            return {"error": "Could not parse PGN"}
    except Exception as e:
        return {"error": f"PGN parse error: {str(e)}"}
    
    # Determine which side we're analyzing from headers
    white = game.headers.get("White", "")
    black = game.headers.get("Black", "")
    
    # Get all positions and moves
    board = game.board()
    positions = []
    moves_played = []
    
    for move in game.mainline_moves():
        positions.append({
            "fen": board.fen(),
            "turn": board.turn,
            "legal_moves": len(list(board.legal_moves))
        })
        moves_played.append(move)
        board.push(move)
    
    # Results tracking
    move_details = []
    complexity_breakdown = {
        "trivial": {"total": 0, "matched": 0},
        "easy": {"total": 0, "matched": 0},
        "moderate": {"total": 0, "matched": 0},
        "hard": {"total": 0, "matched": 0},
        "very_hard": {"total": 0, "matched": 0}
    }
    
    total_top1 = 0
    total_top3 = 0
    total_analyzed = 0
    rank_sum = 0
    critical_matched = 0
    critical_total = 0
    
    for idx, (pos, move) in enumerate(zip(positions, moves_played)):
        move_num = idx + 1
        
        # Skip opening moves
        if idx < exclude_book_moves:
            continue
        
        # Skip forced moves
        if exclude_forced and pos["legal_moves"] <= 2:
            continue
        
        fen = pos["fen"]
        played_uci = move.uci()
        played_san = _move_to_san(fen, move)
        
        # Analyze position
        try:
            if engine_queue:
                analysis = await _analyze_for_correlation(
                    engine_queue, fen, depth, top_n + 2
                )
            else:
                # Placeholder analysis
                analysis = {
                    "top_moves": [],
                    "complexity": "moderate"
                }
            
            top_moves = analysis.get("top_moves", [])
            complexity = analysis.get("complexity", "moderate")
            
            # Find rank of played move
            rank = None
            cp_loss = 0
            for i, m in enumerate(top_moves):
                if m.get("move") == played_uci:
                    rank = i + 1
                    if i > 0:
                        cp_loss = abs(top_moves[0].get("eval", 0) - m.get("eval", 0))
                    break
            
            if rank is None:
                rank = len(top_moves) + 1  # Not in top moves
            
            matched_top1 = rank == 1
            matched_top3 = rank <= top_n
            
            # Update stats
            total_analyzed += 1
            if matched_top1:
                total_top1 += 1
            if matched_top3:
                total_top3 += 1
            rank_sum += rank
            
            # Complexity tracking
            complexity_breakdown[complexity]["total"] += 1
            if matched_top3:
                complexity_breakdown[complexity]["matched"] += 1
            
            # Critical moves (hard/very_hard)
            if complexity in ["hard", "very_hard"]:
                critical_total += 1
                if matched_top3:
                    critical_matched += 1
            
            # Build engine top 3 list
            engine_top3_san = []
            for m in top_moves[:top_n]:
                try:
                    san = _move_to_san(fen, chess.Move.from_uci(m.get("move", "")))
                    engine_top3_san.append(san)
                except:
                    engine_top3_san.append(m.get("move", "?"))
            
            move_details.append({
                "move_num": move_num,
                "played": played_san,
                "engine_top3": engine_top3_san,
                "rank": rank,
                "matched_top1": matched_top1,
                "matched_top3": matched_top3,
                "complexity": complexity,
                "cp_loss": cp_loss
            })
            
        except Exception as e:
            print(f"Correlation analysis error at move {move_num}: {e}")
            continue
    
    # Calculate final metrics
    if total_analyzed == 0:
        return {"error": "No moves analyzed"}
    
    top1_match = round(total_top1 / total_analyzed * 100, 1)
    top3_match = round(total_top3 / total_analyzed * 100, 1)
    critical_match = round(critical_matched / critical_total * 100, 1) if critical_total > 0 else 0
    average_rank = round(rank_sum / total_analyzed, 2)
    
    # Determine suspicion level
    suspicion_level = _calculate_suspicion_level(
        top1_match, top3_match, critical_match, average_rank, complexity_breakdown
    )
    
    return {
        "top1_match": top1_match,
        "top3_match": top3_match,
        "critical_match": critical_match,
        "average_rank": average_rank,
        "suspicion_level": suspicion_level,
        "move_details": move_details,
        "complexity_breakdown": complexity_breakdown,
        "total_moves_analyzed": total_analyzed,
        "analysis_depth": depth
    }


async def _analyze_for_correlation(
    engine_queue,
    fen: str,
    depth: int,
    num_lines: int
) -> Dict:
    """Analyze position for correlation metrics"""
    try:
        board = chess.Board(fen)
        legal_count = len(list(board.legal_moves))
        
        # Analyze
        result = await engine_queue.analyze(fen, depth=depth, num_lines=num_lines)
        
        top_moves = []
        if result and "lines" in result:
            for line in result["lines"]:
                pv = line.get("pv", [])
                top_moves.append({
                    "move": pv[0] if pv else "",
                    "eval": line.get("cp", 0)
                })
        
        # Determine complexity
        complexity = _assess_complexity(board, top_moves, legal_count)
        
        return {
            "top_moves": top_moves,
            "complexity": complexity
        }
    
    except Exception as e:
        return {"top_moves": [], "complexity": "moderate"}


def _assess_complexity(board: chess.Board, top_moves: List[Dict], legal_count: int) -> str:
    """
    Assess the complexity of a position.
    
    Factors:
    - Number of legal moves
    - Evaluation spread between top moves
    - Material on board
    - King safety considerations
    """
    # Trivial: very few legal moves
    if legal_count <= 3:
        return "trivial"
    
    # Easy: clear best move (big eval gap)
    if len(top_moves) >= 2:
        eval_gap = abs(top_moves[0].get("eval", 0) - top_moves[1].get("eval", 0))
        if eval_gap > 150:  # Clear best move
            return "easy"
    
    # Count material (more material = more complex generally)
    piece_count = len(board.piece_map())
    
    # Very hard: many pieces, many options, close evals
    if piece_count >= 20 and legal_count >= 30:
        if len(top_moves) >= 3:
            top_spread = abs(top_moves[0].get("eval", 0) - top_moves[2].get("eval", 0))
            if top_spread < 50:
                return "very_hard"
        return "hard"
    
    # Hard: complex with many options
    if legal_count >= 25 or piece_count >= 18:
        return "hard"
    
    # Moderate: typical middlegame
    if legal_count >= 15:
        return "moderate"
    
    return "easy"


def _calculate_suspicion_level(
    top1_match: float,
    top3_match: float,
    critical_match: float,
    average_rank: float,
    complexity_breakdown: Dict
) -> str:
    """
    Calculate suspicion level based on correlation metrics.
    
    Reference benchmarks (approximate):
    - GM level: ~65-75% top1, ~85-90% top3
    - IM level: ~55-65% top1, ~80-85% top3
    - Expert: ~45-55% top1, ~70-80% top3
    - Amateur: ~35-45% top1, ~60-70% top3
    
    Extreme values (>90% top1 or >98% top3) are suspicious.
    """
    score = 0
    
    # Top 1 match thresholds
    if top1_match > 85:
        score += 3
    elif top1_match > 75:
        score += 2
    elif top1_match > 65:
        score += 1
    
    # Top 3 match thresholds
    if top3_match > 95:
        score += 3
    elif top3_match > 90:
        score += 2
    elif top3_match > 85:
        score += 1
    
    # Critical move accuracy (most telling)
    if critical_match > 95:
        score += 4
    elif critical_match > 85:
        score += 2
    elif critical_match > 75:
        score += 1
    
    # Average rank (should be 1.5-2.5 for strong players)
    if average_rank < 1.3:
        score += 2
    elif average_rank < 1.5:
        score += 1
    
    # Hard move accuracy
    hard_total = complexity_breakdown.get("hard", {}).get("total", 0)
    hard_matched = complexity_breakdown.get("hard", {}).get("matched", 0)
    very_hard_total = complexity_breakdown.get("very_hard", {}).get("total", 0)
    very_hard_matched = complexity_breakdown.get("very_hard", {}).get("matched", 0)
    
    if hard_total + very_hard_total >= 5:
        hard_rate = (hard_matched + very_hard_matched) / (hard_total + very_hard_total)
        if hard_rate > 0.9:
            score += 3
        elif hard_rate > 0.8:
            score += 1
    
    # Determine level
    if score >= 10:
        return "extreme"
    elif score >= 7:
        return "high"
    elif score >= 4:
        return "elevated"
    else:
        return "normal"


def _move_to_san(fen: str, move: chess.Move) -> str:
    """Convert a move to SAN notation"""
    try:
        board = chess.Board(fen)
        return board.san(move)
    except:
        return move.uci()


# Tool schema for LLM
TOOL_ENGINE_CORRELATION = {
    "type": "function",
    "function": {
        "name": "engine_correlation",
        "description": "Calculate how closely a player's moves match Stockfish's top recommendations. Returns correlation percentages, complexity breakdown, and suspicion level assessment.",
        "parameters": {
            "type": "object",
            "properties": {
                "pgn": {
                    "type": "string",
                    "description": "PGN string of the game to analyze"
                },
                "depth": {
                    "type": "integer",
                    "description": "Stockfish analysis depth (default 25)",
                    "default": 25
                },
                "top_n": {
                    "type": "integer",
                    "description": "Match against top N moves (default 3)",
                    "default": 3
                },
                "exclude_book_moves": {
                    "type": "integer",
                    "description": "Skip first N opening moves (default 10)",
                    "default": 10
                }
            },
            "required": ["pgn"]
        }
    }
}

