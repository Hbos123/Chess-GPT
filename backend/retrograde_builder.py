"""
Retrograde puzzle builder - walks backwards from completed positions to starting positions.
"""

import chess
import chess.engine
from typing import List, Dict, Tuple, Optional, Any
import time


CP_GAP = 150  # Centipawn gap for move uniqueness


def boards_equal_strict(a: chess.Board, b: chess.Board) -> bool:
    """Check if two boards are exactly equal."""
    return (
        a.board_fen() == b.board_fen() and
        a.turn == b.turn and
        a.castling_rights == b.castling_rights and
        a.ep_square == b.ep_square
    )


def plausible_from_squares(piece: chess.Piece, to_sq: int, child: chess.Board) -> List[int]:
    """
    Generate plausible squares a piece could have moved from to reach to_sq.
    
    Uses geometric rules without full history reconstruction.
    """
    res = []
    
    if piece.piece_type == chess.KNIGHT:
        # Knight moves: all 8 L-shapes
        for delta in [17, 15, 10, 6, -17, -15, -10, -6]:
            from_sq = to_sq + delta
            if 0 <= from_sq < 64:
                res.append(from_sq)
    
    elif piece.piece_type == chess.BISHOP:
        # Diagonal rays
        for delta in [9, 7, -9, -7]:
            from_sq = to_sq
            while True:
                from_sq += delta
                if not (0 <= from_sq < 64):
                    break
                # Check if this could be origin (empty or opposite color piece)
                piece_at = child.piece_at(from_sq)
                if piece_at is None:
                    res.append(from_sq)
                else:
                    # Could be capture origin
                    if piece_at.color != piece.color:
                        res.append(from_sq)
                    break
    
    elif piece.piece_type == chess.ROOK:
        # Straight rays
        for delta in [8, -8, 1, -1]:
            from_sq = to_sq
            while True:
                from_sq += delta
                if not (0 <= from_sq < 64):
                    break
                piece_at = child.piece_at(from_sq)
                if piece_at is None:
                    res.append(from_sq)
                else:
                    if piece_at.color != piece.color:
                        res.append(from_sq)
                    break
    
    elif piece.piece_type == chess.QUEEN:
        # All 8 directions
        for delta in [9, 7, -9, -7, 8, -8, 1, -1]:
            from_sq = to_sq
            while True:
                from_sq += delta
                if not (0 <= from_sq < 64):
                    break
                piece_at = child.piece_at(from_sq)
                if piece_at is None:
                    res.append(from_sq)
                else:
                    if piece_at.color != piece.color:
                        res.append(from_sq)
                    break
    
    elif piece.piece_type == chess.KING:
        # One square in any direction
        for delta in [1, -1, 8, -8, 9, -9, 7, -7]:
            from_sq = to_sq + delta
            if 0 <= from_sq < 64:
                res.append(from_sq)
    
    elif piece.piece_type == chess.PAWN:
        # Pawn moves (reverse)
        direction = 1 if piece.color == chess.WHITE else -1
        
        # One-step advance
        from_sq = to_sq - 8 * direction
        if 0 <= from_sq < 64:
            res.append(from_sq)
        
        # Two-step advance (from starting rank)
        to_rank = chess.square_rank(to_sq)
        if (piece.color == chess.WHITE and to_rank == 3) or \
           (piece.color == chess.BLACK and to_rank == 4):
            from_sq = to_sq - 16 * direction
            if 0 <= from_sq < 64:
                res.append(from_sq)
        
        # Diagonal captures
        for diag_delta in [7 * direction, 9 * direction]:
            from_sq = to_sq - diag_delta
            if 0 <= from_sq < 64:
                res.append(from_sq)
    
    # Filter out origins occupied by same-color pieces
    valid = []
    for from_sq in res:
        pc = child.piece_at(from_sq)
        if pc is None or pc.color != piece.color:
            valid.append(from_sq)
    
    return valid


def construct_parents(child: chess.Board, max_candidates: int = 8) -> List[Tuple[chess.Board, chess.Move]]:
    """
    Construct plausible parent positions that could lead to child in one move.
    
    Returns list of (parent_board, move_to_child) tuples.
    """
    candidates = []
    stm_child = child.turn
    
    # The parent must have opposite side to move
    parent_turn = not stm_child
    
    # Try to reverse moves for pieces that likely just moved
    # (pieces belonging to the side that just played)
    moved_side = not stm_child
    
    for to_sq in range(64):
        piece = child.piece_at(to_sq)
        if not piece or piece.color != moved_side:
            continue
        
        # Get plausible origin squares
        from_squares = plausible_from_squares(piece, to_sq, child)
        
        for from_sq in from_squares:
            # Build parent by moving piece back
            parent = child.copy(stack=False)
            parent.turn = parent_turn
            
            # Move piece back from to_sq to from_sq
            parent.remove_piece_at(to_sq)
            parent.set_piece_at(from_sq, piece)
            
            # Clear history ambiguity
            parent.castling_rights = 0
            parent.ep_square = None
            parent.halfmove_clock = 0
            parent.fullmove_number = child.fullmove_number - (1 if parent.turn == chess.BLACK else 0)
            
            # Test if move from parent leads to child
            test_move = chess.Move(from_sq, to_sq)
            
            try:
                # Check if move is legal
                if test_move not in parent.legal_moves:
                    continue
                
                # Test if making the move reproduces child
                test_board = parent.copy(stack=False)
                test_board.push(test_move)
                
                # Compare board state (ignore history fields)
                if test_board.board_fen() == child.board_fen() and \
                   test_board.turn == child.turn:
                    candidates.append((parent, test_move))
                    
                    if len(candidates) >= max_candidates:
                        return candidates
            except:
                continue
    
    return candidates


async def choose_clean_parent(
    child: chess.Board,
    candidates: List[Tuple[chess.Board, chess.Move]],
    engine: chess.engine.SimpleEngine,
    cp_gap: int = CP_GAP
) -> Optional[Tuple[chess.Board, chess.Move, List[chess.Move]]]:
    """
    Select the best parent where the move to child is clearly unique (best by big margin).
    
    Returns (parent_board, move_to_child, pv_from_parent) or None.
    """
    best = None
    best_score = -1e9
    
    for parent, m_star in candidates:
        try:
            # Analyze parent with MultiPV=3
            analysis = await engine.analyse(parent, chess.engine.Limit(time=0.2), multipv=3)
            
            if not analysis:
                continue
            
            # Convert to list if needed
            if not isinstance(analysis, list):
                analysis = [analysis]
            
            # Find m_star in top moves
            lines = []
            for info in analysis[:3]:
                pv = info.get("pv", [])
                if not pv:
                    continue
                
                score_obj = info.get("score")
                if score_obj and score_obj.relative:
                    eval_cp = score_obj.relative.score(mate_score=10000)
                else:
                    eval_cp = 0
                
                lines.append({
                    "move": pv[0],
                    "eval_cp": eval_cp,
                    "pv": pv
                })
            
            if not lines:
                continue
            
            # Check if m_star is the top move
            top_move = lines[0]["move"]
            if top_move != m_star:
                continue
            
            # Check uniqueness gap
            if len(lines) > 1:
                gap = lines[0]["eval_cp"] - lines[1]["eval_cp"]
            else:
                gap = 1000  # Only one move, clearly unique
            
            if gap < cp_gap:
                continue
            
            # Verify move leads to child
            test_board = parent.copy(stack=False)
            test_board.push(m_star)
            
            if not boards_equal_strict(test_board, child):
                continue
            
            # Good parent!
            if gap > best_score:
                best = (parent, m_star, lines[0]["pv"])
                best_score = gap
        
        except Exception as e:
            continue
    
    return best


async def backtrack_from_position(
    end_fen: str,
    steps_back: int,
    engine: chess.engine.SimpleEngine
) -> Tuple[str, List[str]]:
    """
    Backtrack from a finished position to create a puzzle with a unique solution.
    
    Args:
        end_fen: Position with theme already achieved
        steps_back: Number of moves to backtrack (4-8 recommended)
        engine: Stockfish engine instance
        
    Returns:
        (starting_fen, mainline_moves) where mainline shows how to reach end_fen
    """
    chain = []
    child = chess.Board(end_fen)
    
    for step in range(steps_back):
        # Construct candidate parents
        candidates = construct_parents(child, max_candidates=8)
        
        if not candidates:
            # Can't go back further - return what we have
            break
        
        # Choose cleanest parent (unique move)
        chosen = await choose_clean_parent(child, candidates, engine, cp_gap=CP_GAP)
        
        if not chosen:
            # No clean parent found - return what we have
            break
        
        parent, m_star, pv = chosen
        chain.append({
            "parent_fen": parent.fen(),
            "move_to_child": m_star,
            "pv": pv
        })
        
        # Continue from parent
        child = parent
    
    # child is now the starting position
    starting_board = child
    starting_fen = starting_board.fen()
    
    # Build forward mainline (reversed chain)
    mainline = []
    for node in reversed(chain):
        mainline.append(node["move_to_child"])
    
    # Convert moves to SAN notation
    mainline_san = []
    temp_board = starting_board.copy()
    for move in mainline:
        san = temp_board.san(move)
        mainline_san.append(san)
        temp_board.push(move)
    
    return starting_fen, mainline_san




