"""
Move Complexity Scorer Tool
Assesses the difficulty of finding correct moves in a position
"""

import chess
from typing import Dict, List, Optional, Literal


async def score_move_complexity(
    fen: str,
    move: str = None,
    engine_queue = None,
    depth: int = 25
) -> Dict:
    """
    Score the complexity of a position or specific move.
    
    Args:
        fen: Position in FEN notation
        move: Optional move to assess (in SAN or UCI)
        engine_queue: Stockfish engine queue
        depth: Analysis depth
        
    Returns:
        {
            "complexity": "hard",  # trivial/easy/moderate/hard/very_hard
            "complexity_score": 0.72,  # 0-1 numeric
            "num_legal_moves": 34,
            "num_reasonable_moves": 8,  # Within 50cp of best
            "eval_spread": 125,  # CP difference between best and 5th best
            "is_only_move": False,
            "tactical_elements": ["pin", "fork_threat"],
            "piece_tension": 0.65,  # How many pieces are attacked/defended
            "move_assessment": {  # Only if move provided
                "played": "Nxe5",
                "rank": 2,
                "cp_loss": 15,
                "difficulty_to_find": "moderate"
            },
            "time_expected": 45.0  # Estimated human think time (seconds)
        }
    """
    try:
        board = chess.Board(fen)
    except:
        return {"error": f"Invalid FEN: {fen}"}
    
    # Basic position info
    legal_moves = list(board.legal_moves)
    num_legal = len(legal_moves)
    
    if num_legal == 0:
        return {
            "complexity": "trivial",
            "complexity_score": 0,
            "reason": "No legal moves - game over"
        }
    
    # Analyze position
    analysis_result = None
    if engine_queue:
        try:
            analysis_result = await engine_queue.analyze(fen, depth=depth, num_lines=min(10, num_legal))
        except Exception as e:
            print(f"Engine analysis error: {e}")
    
    # Extract move evaluations
    move_evals = []
    if analysis_result and "lines" in analysis_result:
        for line in analysis_result["lines"]:
            pv = line.get("pv", [])
            if pv:
                move_evals.append({
                    "move": pv[0],
                    "eval": line.get("cp", 0)
                })
    
    # Calculate metrics
    best_eval = move_evals[0]["eval"] if move_evals else 0
    
    # Count reasonable moves (within 50cp of best)
    reasonable_moves = sum(
        1 for m in move_evals 
        if abs(m["eval"] - best_eval) <= 50
    )
    
    # Eval spread (difference between best and 5th best)
    if len(move_evals) >= 5:
        eval_spread = abs(best_eval - move_evals[4]["eval"])
    elif len(move_evals) >= 2:
        eval_spread = abs(best_eval - move_evals[-1]["eval"])
    else:
        eval_spread = 0
    
    # Is only move?
    is_only_move = num_legal == 1 or (len(move_evals) >= 2 and abs(move_evals[0]["eval"] - move_evals[1]["eval"]) > 200)
    
    # Tactical elements
    tactical_elements = _detect_tactical_elements(board)
    
    # Piece tension
    piece_tension = _calculate_piece_tension(board)
    
    # Calculate complexity score
    complexity_score = _calculate_complexity_score(
        num_legal, reasonable_moves, eval_spread, 
        is_only_move, len(tactical_elements), piece_tension
    )
    
    # Map to category
    complexity = _score_to_category(complexity_score)
    
    # Estimate human think time
    time_expected = _estimate_think_time(complexity_score, len(tactical_elements))
    
    result = {
        "complexity": complexity,
        "complexity_score": round(complexity_score, 2),
        "num_legal_moves": num_legal,
        "num_reasonable_moves": reasonable_moves,
        "eval_spread": eval_spread,
        "is_only_move": is_only_move,
        "tactical_elements": tactical_elements,
        "piece_tension": round(piece_tension, 2),
        "time_expected": round(time_expected, 1)
    }
    
    # Assess specific move if provided
    if move:
        move_assessment = _assess_specific_move(board, move, move_evals, complexity_score)
        result["move_assessment"] = move_assessment
    
    return result


def _detect_tactical_elements(board: chess.Board) -> List[str]:
    """Detect tactical patterns in the position"""
    elements = []
    
    # Check for checks
    if board.is_check():
        elements.append("in_check")
    
    # Count potential checks
    check_moves = sum(1 for m in board.legal_moves if board.gives_check(m))
    if check_moves >= 2:
        elements.append("multiple_check_threats")
    
    # Detect pins (simplified)
    king_sq = board.king(board.turn)
    if king_sq is not None:
        for sq, piece in board.piece_map().items():
            if piece.color == board.turn and piece.piece_type != chess.KING:
                # Check if piece is between attacker and king
                attackers = board.attackers(not board.turn, sq)
                if attackers:
                    for attacker_sq in attackers:
                        attacker = board.piece_at(attacker_sq)
                        if attacker and attacker.piece_type in [chess.BISHOP, chess.ROOK, chess.QUEEN]:
                            # Simplified pin detection
                            if _squares_aligned(attacker_sq, sq, king_sq):
                                elements.append("pin")
                                break
    
    # Detect hanging pieces
    for sq, piece in board.piece_map().items():
        if piece.color == board.turn:
            attackers = board.attackers(not board.turn, sq)
            defenders = board.attackers(board.turn, sq)
            if attackers and not defenders:
                elements.append("hanging_piece")
                break
    
    # Fork potential
    for move in board.legal_moves:
        board.push(move)
        attacked = []
        moved_piece_sq = move.to_square
        moved_piece = board.piece_at(moved_piece_sq)
        if moved_piece:
            for sq, piece in board.piece_map().items():
                if piece.color != moved_piece.color:
                    if board.is_attacked_by(moved_piece.color, sq):
                        if piece.piece_type in [chess.QUEEN, chess.ROOK, chess.KING]:
                            attacked.append(sq)
            if len(attacked) >= 2:
                elements.append("fork_threat")
                board.pop()
                break
        board.pop()
    
    # Remove duplicates
    return list(set(elements))


def _squares_aligned(sq1: int, sq2: int, sq3: int) -> bool:
    """Check if three squares are aligned (diagonal or straight line)"""
    r1, f1 = sq1 // 8, sq1 % 8
    r2, f2 = sq2 // 8, sq2 % 8
    r3, f3 = sq3 // 8, sq3 % 8
    
    # Same rank
    if r1 == r2 == r3:
        return True
    # Same file
    if f1 == f2 == f3:
        return True
    # Same diagonal
    if (r1 - r2) * (f2 - f3) == (r2 - r3) * (f1 - f2):
        return True
    
    return False


def _calculate_piece_tension(board: chess.Board) -> float:
    """
    Calculate piece tension (0-1).
    High tension = many pieces attacking/defending each other.
    """
    total_pieces = len(board.piece_map())
    if total_pieces == 0:
        return 0
    
    tension_count = 0
    for sq in board.piece_map():
        # Count attackers from both sides
        white_attackers = len(board.attackers(chess.WHITE, sq))
        black_attackers = len(board.attackers(chess.BLACK, sq))
        if white_attackers > 0 or black_attackers > 0:
            tension_count += 1
    
    return tension_count / total_pieces


def _calculate_complexity_score(
    num_legal: int,
    reasonable_moves: int,
    eval_spread: int,
    is_only_move: bool,
    num_tactics: int,
    piece_tension: float
) -> float:
    """Calculate 0-1 complexity score"""
    if is_only_move:
        return 0.1
    
    score = 0
    
    # More legal moves = more complex
    if num_legal >= 40:
        score += 0.3
    elif num_legal >= 30:
        score += 0.2
    elif num_legal >= 20:
        score += 0.1
    
    # More reasonable options = harder to choose
    if reasonable_moves >= 5:
        score += 0.25
    elif reasonable_moves >= 3:
        score += 0.15
    elif reasonable_moves >= 2:
        score += 0.05
    
    # Small eval spread = harder (close moves)
    if eval_spread < 30:
        score += 0.25
    elif eval_spread < 60:
        score += 0.15
    elif eval_spread < 100:
        score += 0.05
    
    # Tactical elements add complexity
    score += min(0.2, num_tactics * 0.05)
    
    # Piece tension adds complexity
    score += piece_tension * 0.15
    
    return min(1, score)


def _score_to_category(score: float) -> str:
    """Convert numeric score to category"""
    if score < 0.2:
        return "trivial"
    elif score < 0.35:
        return "easy"
    elif score < 0.55:
        return "moderate"
    elif score < 0.75:
        return "hard"
    else:
        return "very_hard"


def _estimate_think_time(complexity_score: float, num_tactics: int) -> float:
    """Estimate human thinking time in seconds"""
    base_time = 5  # Minimum time
    
    # Scale with complexity
    time = base_time + complexity_score * 60  # Up to 65 seconds
    
    # Tactics add time
    time += num_tactics * 10
    
    return min(120, time)  # Cap at 2 minutes


def _assess_specific_move(
    board: chess.Board,
    move_str: str,
    move_evals: List[Dict],
    position_complexity: float
) -> Dict:
    """Assess a specific move"""
    try:
        # Try SAN first, then UCI
        try:
            move = board.parse_san(move_str)
        except:
            move = chess.Move.from_uci(move_str)
        
        move_uci = move.uci()
        move_san = board.san(move)
    except:
        return {"error": f"Could not parse move: {move_str}"}
    
    # Find rank in engine list
    rank = None
    cp_loss = 0
    for i, m in enumerate(move_evals):
        if m["move"] == move_uci:
            rank = i + 1
            if i > 0:
                cp_loss = abs(move_evals[0]["eval"] - m["eval"])
            break
    
    if rank is None:
        rank = len(move_evals) + 1
        if move_evals:
            # Estimate CP loss for non-top moves
            cp_loss = 100  # Default
    
    # Difficulty to find based on rank and position complexity
    if rank == 1:
        difficulty = "obvious" if position_complexity < 0.3 else "moderate"
    elif rank <= 3:
        difficulty = "moderate" if position_complexity < 0.5 else "hard"
    else:
        difficulty = "hard" if position_complexity < 0.6 else "very_hard"
    
    return {
        "played": move_san,
        "rank": rank,
        "cp_loss": cp_loss,
        "difficulty_to_find": difficulty
    }


# Tool schema for LLM
TOOL_COMPLEXITY_SCORER = {
    "type": "function",
    "function": {
        "name": "score_move_complexity",
        "description": "Assess the difficulty of finding the correct move in a chess position. Returns complexity category, tactical elements, and estimated think time.",
        "parameters": {
            "type": "object",
            "properties": {
                "fen": {
                    "type": "string",
                    "description": "Position in FEN notation"
                },
                "move": {
                    "type": "string",
                    "description": "Optional specific move to assess (SAN or UCI)"
                },
                "depth": {
                    "type": "integer",
                    "description": "Analysis depth (default 25)",
                    "default": 25
                }
            },
            "required": ["fen"]
        }
    }
}

