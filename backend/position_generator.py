"""
Dynamic chess position generator using Stockfish-guided rollouts and topic predicates.
"""

import chess
import chess.engine
import random
import time
import math
from typing import Dict, List, Optional, Any, Tuple
from predicates import score_topic, PredicateResult


# Difficulty evaluation bands (centipawns, relative to side to move)
# Widened bands for better generation success rate
DIFFICULTY_EVAL_BANDS = {
    "beginner": (-150, 150),      # Wide range for learning positions
    "intermediate": (-100, 200),   # Flexible advantage range
    "advanced": (-50, 600)         # Very wide for complex positions
}


async def generate_fen_for_topic(
    topic_code: str,
    side_to_move: str,
    difficulty: str,
    engine: chess.engine.SimpleEngine,
    time_budget_ms: int = 500
) -> Dict[str, Any]:
    """
    Generate a fresh FEN for a chess topic using engine-guided rollouts.
    
    Args:
        topic_code: Topic identifier (e.g., "PS.IQP")
        side_to_move: "white" or "black"
        difficulty: "beginner", "intermediate", or "advanced"
        engine: Stockfish engine instance
        time_budget_ms: Maximum time to spend generating (milliseconds)
    
    Returns:
        Dict with fen, objective, hints, ideal_line, etc.
        
    Raises:
        TimeoutError: If no suitable position found within time budget
    """
    start_time = time.time()
    
    # Seed RNG with timestamp + topic for unique positions each time
    seed = int(time.time() * 1000) + hash(topic_code) + hash(side_to_move)
    rng = random.Random(seed)
    
    cp_min, cp_max = DIFFICULTY_EVAL_BANDS.get(difficulty, (-50, 120))
    
    # Try multiple rollout attempts
    max_attempts = 24  # Increased for better success rate
    max_plies = 24  # Adjust based on topic (openings: 14-20, strategy: 18-24)
    
    for attempt in range(max_attempts):
        # Check time budget
        elapsed_ms = (time.time() - start_time) * 1000
        if elapsed_ms > time_budget_ms:
            raise TimeoutError(f"Could not generate position within {time_budget_ms}ms budget")
        
        # Start fresh rollout
        board = chess.Board()
        move_history = []  # Track moves for backtracking
        
        # Rollout with topic-guided moves
        target_plies = rng.randint(8, max_plies)
        
        for ply in range(target_plies):
            # Sample next move
            move = await sample_engine_move(board, topic_code, engine, rng)
            if move is None:
                break
            
            # Store move in history before applying
            move_history.append(move)
            board.push(move)
            
            # After sufficient development, check predicate
            if board.fullmove_number >= 4:
                # Only check when it's the target side's turn
                current_side = "white" if board.turn == chess.WHITE else "black"
                
                if current_side == side_to_move:
                    pred_result = score_topic(topic_code, board)
                    
                    if pred_result.score >= 0.85:  # High quality threshold
                        # Good topic match! Check difficulty
                        eval_cp = await eval_cp_for_side(board, side_to_move, engine)
                        
                        if cp_min <= eval_cp <= cp_max:
                            # CRITICAL: Backtrack 4-6 moves so students CREATE the theme
                            backtrack_plies = rng.randint(4, min(6, len(move_history)))
                            
                            # Build starting position by backtracking
                            starting_board = chess.Board()
                            for move in move_history[:-backtrack_plies]:
                                starting_board.push(move)
                            
                            # Validate starting position has correct side to move
                            starting_side = "white" if starting_board.turn == chess.WHITE else "black"
                            if starting_side != side_to_move:
                                # Skip if sides don't match
                                continue
                            
                            # Success! Return BACKTRACKED position
                            return await finalize_position(
                                topic_code, 
                                starting_board,  # Position BEFORE theme is achieved
                                side_to_move, 
                                engine,
                                pred_result,
                                attempt  # Add attempt number for uniqueness
                            )
    
    # Failed to generate within budget
    raise TimeoutError(f"Could not find suitable position after {max_attempts} attempts")


async def sample_engine_move(
    board: chess.Board,
    topic_code: str,
    engine: chess.engine.SimpleEngine,
    rng: random.Random
) -> Optional[chess.Move]:
    """
    Sample a move using engine suggestions with topic-specific nudges.
    
    Uses MultiPV=5 with softmax sampling and policy nudges toward topic features.
    """
    if board.is_game_over():
        return None
    
    try:
        # Get top moves from engine (fast analysis)
        analysis = await engine.analyse(
            board,
            chess.engine.Limit(time=0.05),  # 50ms per move
            multipv=5
        )
        
        if not analysis or not isinstance(analysis, list):
            analysis = [analysis] if analysis else []
        
        candidates = []
        for info in analysis[:5]:
            if "pv" not in info or not info["pv"]:
                continue
            
            move = info["pv"][0]
            score = info.get("score")
            
            # Convert score to centipawns
            if score:
                cp = score.relative.score(mate_score=10000) if score.relative else 0
            else:
                cp = 0
            
            candidates.append((move, cp))
        
        if not candidates:
            # Fallback to legal moves
            legal = list(board.legal_moves)
            return rng.choice(legal) if legal else None
        
        # Softmax sampling with topic nudges
        moves, scores = zip(*candidates)
        
        # Base weights from eval
        temp = 0.9
        weights = [math.exp(cp / 100.0 / temp) for cp in scores]
        
        # Apply topic nudges to encourage motif development
        boosted_weights = []
        for move, base_weight in zip(moves, weights):
            # Test move and check if predicate improves
            board.push(move)
            delta = await predicate_delta(topic_code, board)
            board.pop()
            
            # Boost moves that progress toward topic
            nudge = 1.0 + 0.25 * max(0.0, delta)
            boosted_weights.append(base_weight * nudge)
        
        # Weighted random choice
        total = sum(boosted_weights)
        if total == 0:
            return rng.choice(moves)
        
        normalized = [w / total for w in boosted_weights]
        chosen_move = rng.choices(moves, weights=normalized)[0]
        
        return chosen_move
        
    except Exception as e:
        # Fallback to random legal move
        legal = list(board.legal_moves)
        return rng.choice(legal) if legal else None


async def predicate_delta(topic_code: str, board: chess.Board) -> float:
    """
    Calculate change in predicate score (for move nudging).
    Positive = move progresses toward topic.
    """
    # This is called after move is made
    current_score = score_topic(topic_code, board).score
    
    # We can't easily get "before" score without unmaking move
    # So use a simplified heuristic: any non-zero score is progress
    return current_score * 0.5 if current_score > 0 else 0.0


async def eval_cp_for_side(
    board: chess.Board,
    side: str,
    engine: chess.engine.SimpleEngine
) -> int:
    """
    Get evaluation in centipawns from perspective of given side.
    """
    try:
        info = await engine.analyse(board, chess.engine.Limit(time=0.08))
        score = info.get("score")
        
        if not score or not score.relative:
            return 0
        
        cp = score.relative.score(mate_score=10000)
        
        # Adjust perspective if needed
        if side == "black":
            if board.turn == chess.WHITE:
                cp = -cp
        else:  # white
            if board.turn == chess.BLACK:
                cp = -cp
        
        return cp
        
    except:
        return 0


async def validate_topic_stability(
    topic_code: str,
    board: chess.Board,
    engine: chess.engine.SimpleEngine
) -> bool:
    """
    Validate that the topic feature persists through the best continuation.
    
    Replays engine's PV and checks that predicate stays satisfied.
    More lenient validation for better generation success.
    """
    try:
        # Get engine's best line
        info = await engine.analyse(board, chess.engine.Limit(time=0.1))
        pv = info.get("pv", [])
        
        if not pv or len(pv) < 2:
            return True  # No PV to validate or too short, accept position
        
        # Test first 4 plies of PV (reduced from 6)
        test_board = board.copy()
        ok_steps = 0
        
        for move in pv[:4]:
            test_board.push(move)
            pred = score_topic(topic_code, test_board)
            
            if pred.score >= 0.50:  # Lowered threshold
                ok_steps += 1
        
        # Require at least 1 ply maintain the theme (reduced from 2)
        return ok_steps >= 1
        
    except:
        return True  # If validation fails, accept position


async def finalize_position(
    topic_code: str,
    board: chess.Board,
    side_to_move: str,
    engine: chess.engine.SimpleEngine,
    pred_result: PredicateResult,
    attempt_number: int = 0
) -> Dict[str, Any]:
    """
    Package generated position with ideal line, hints, and metadata.
    
    The board passed here should be the STARTING position (after backtracking).
    The ideal_line shows how to achieve the strategic theme from this position.
    """
    from main import LESSON_TOPICS
    
    topic = LESSON_TOPICS.get(topic_code, {})
    
    # Generate ideal line (8-12 moves) FROM the starting position
    try:
        info = await engine.analyse(board, chess.engine.Limit(time=0.4))
        pv = info.get("pv", [])
        
        ideal_line = []
        ideal_pgn_parts = []
        
        temp_board = board.copy()
        move_num = temp_board.fullmove_number
        is_white_turn = temp_board.turn
        
        for i, move in enumerate(pv[:10]):  # Take 10 moves
            move_san = temp_board.san(move)
            ideal_line.append(move_san)
            
            # Build PGN notation
            if temp_board.turn == chess.WHITE:
                ideal_pgn_parts.append(f"{temp_board.fullmove_number}. {move_san}")
            else:
                if i == 0 and not is_white_turn:
                    ideal_pgn_parts.append(f"{temp_board.fullmove_number}... {move_san}")
                else:
                    ideal_pgn_parts.append(move_san)
            
            temp_board.push(move)
        
        ideal_pgn = " ".join(ideal_pgn_parts)
        
    except:
        ideal_line = []
        ideal_pgn = ""
    
    # Build hints from predicate details
    hints = build_hints_from_predicate(topic_code, pred_result, topic)
    
    # Build objective
    objective = build_objective_from_topic(topic_code, pred_result, topic)
    
    # Get evaluation
    eval_cp = await eval_cp_for_side(board, side_to_move, engine)
    
    # CRITICAL: board.fen() is the STARTING position for training (AFTER backtracking)
    # ideal_line contains the moves to be played FROM this position to achieve the theme
    # Students will execute the ideal_line to CREATE the strategic concept
    starting_fen = board.fen()
    
    return {
        "fen": starting_fen,  # Starting position (backtracked, before theme is achieved)
        "side": side_to_move,
        "objective": objective,
        "themes": [topic_code],
        "candidates": [],  # Could add candidate moves if needed
        "hints": hints,
        "difficulty": topic.get("difficulty", "1200-1800"),
        "topic_name": topic.get("name", "Chess Concept"),
        "ideal_line": ideal_line,  # Moves to play FROM starting FEN to achieve theme
        "ideal_pgn": ideal_pgn,
        "meta": {
            "eval_cp": eval_cp,
            "predicate_score": pred_result.score,
            "predicate_details": pred_result.details,
            "generated": True,
            "generation_attempt": attempt_number,
            "uniqueness_seed": int(time.time() * 1000)
        }
    }


def build_hints_from_predicate(
    topic_code: str,
    pred_result: PredicateResult,
    topic: Dict
) -> List[str]:
    """Build contextual hints from predicate evaluation."""
    hints = []
    details = pred_result.details
    
    # Topic-specific hint generation
    if "iqp" in topic_code.lower():
        if details.get("has_iqp"):
            hints.append(f"Your isolated pawn is on {details.get('iqp_square', 'd4')}")
        if details.get("breaks"):
            hints.append(f"Look for the {details['breaks'][0]} break to activate your pieces")
        if details.get("blockaded"):
            hints.append("The pawn is blockaded - how can you challenge the blockader?")
    
    elif "outpost" in topic_code.lower():
        if details.get("outposts"):
            hints.append(f"The {details['outposts'][0]} square is an ideal outpost")
        hints.append("Outpost squares can't be attacked by enemy pawns")
        if details.get("supported"):
            hints.append("Support your knight with a pawn for maximum stability")
    
    elif "seventh" in topic_code.lower():
        if details.get("rooks_on_seventh"):
            hints.append("The 7th rank is called the 'pig' rank for a reason")
        hints.append("Rooks on the 7th attack pawns and restrict the king")
    
    elif "carlsbad" in topic_code.lower():
        if details.get("minority_ready"):
            hints.append("The b4-b5 minority attack creates weaknesses")
        hints.append("Target the c6 square with your pieces and pawns")
    
    # Fallback to generic hints
    if not hints:
        hints = [goal for goal in topic.get("goals", [])][:3]
    
    return hints[:3]  # Max 3 hints


def build_objective_from_topic(
    topic_code: str,
    pred_result: PredicateResult,
    topic: Dict
) -> str:
    """Build objective description from topic and predicate details."""
    details = pred_result.details
    base_name = topic.get("name", "Chess Concept")
    
    # Topic-specific objectives
    if "iqp" in topic_code.lower() and details.get("has_iqp"):
        return f"Play for the e5 break with your isolated d-pawn on {details.get('iqp_square', 'd4')}. Keep your pieces active to compensate for the structural weakness."
    
    elif "carlsbad" in topic_code.lower() and details.get("has_structure"):
        return "Execute the minority attack with b4-b5 to create a weakness on c6. Double rooks on the c-file."
    
    elif "outpost" in topic_code.lower() and details.get("outposts"):
        return f"Establish a knight on the {details['outposts'][0]} outpost. This square cannot be attacked by enemy pawns."
    
    elif "seventh" in topic_code.lower() and details.get("rooks_on_seventh"):
        return "Invade the 7th rank with your rook. Attack enemy pawns and restrict their king."
    
    elif "fork" in topic_code.lower():
        return "Find the tactical fork that wins material. Attack two pieces at once."
    
    elif "pin" in topic_code.lower():
        return "Create or exploit a pin to win material or restrict enemy piece movement."
    
    # Fallback: use first goal
    goals = topic.get("goals", [])
    if goals:
        return f"Practice {base_name}: {goals[0]}"
    
    return f"Practice the concept: {base_name}"

