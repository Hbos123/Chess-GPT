"""
Topic predicates for dynamic position generation.
Each function scores how well a board position matches a chess concept.
"""

import chess
from typing import Dict, List, Set, Optional
from dataclasses import dataclass


@dataclass
class PredicateResult:
    """Result of a topic predicate evaluation"""
    score: float  # 0.0-1.0, higher = better match
    details: Dict  # Topic-specific details for hint generation
    

def score_iqp(board: chess.Board) -> PredicateResult:
    """
    Isolated Queen's Pawn - pawn on d-file with weakened/isolated structure.
    Accepts positions with d4/d5 pawn that has limited support (pragmatic for generation).
    """
    score = 0.0
    details = {"has_iqp": False, "iqp_square": None, "breaks": [], "blockaded": False}
    
    # Check for d-pawn with weak support (more lenient than strict isolation)
    for color in [chess.WHITE, chess.BLACK]:
        d_pawns = board.pieces(chess.PAWN, color) & chess.BB_FILE_D
        if not d_pawns:
            continue
            
        for sq in d_pawns:
            c_pawns = board.pieces(chess.PAWN, color) & chess.BB_FILE_C
            e_pawns = board.pieces(chess.PAWN, color) & chess.BB_FILE_E
            
            # Strict IQP: no c or e pawns
            if not c_pawns and not e_pawns:
                details["has_iqp"] = True
                details["iqp_square"] = chess.square_name(sq)
                score = 0.95
                break
            
            # Pragmatic: d-pawn with only ONE neighbor (still teachable)
            elif (not c_pawns) or (not e_pawns):
                details["has_iqp"] = True  # "quasi-isolated"
                details["iqp_square"] = chess.square_name(sq)
                score = 0.75
                
                # Bonus for being on central ranks
                rank = chess.square_rank(sq)
                if (color == chess.WHITE and rank == 3) or (color == chess.BLACK and rank == 4):
                    score += 0.15
                
                break
    
    return PredicateResult(score=min(score, 1.0), details=details)


def score_carlsbad(board: chess.Board) -> PredicateResult:
    """
    Carlsbad structure - LENIENT: just needs queenside pawn tension.
    """
    score = 0.0
    details = {"has_structure": False, "minority_ready": False, "c_file_open": False}
    
    white_pawns = board.pieces(chess.PAWN, chess.WHITE)
    black_pawns = board.pieces(chess.PAWN, chess.BLACK)
    
    # LENIENT: Just check for any queenside pawns
    has_white_queenside = bool(white_pawns & (chess.BB_FILE_A | chess.BB_FILE_B | chess.BB_FILE_C))
    has_black_queenside = bool(black_pawns & (chess.BB_FILE_A | chess.BB_FILE_B | chess.BB_FILE_C))
    
    if has_white_queenside and has_black_queenside:
        details["has_structure"] = True
        score = 0.85  # Generous scoring
    
    return PredicateResult(score=min(score, 1.0), details=details)


def score_hanging_pawns(board: chess.Board) -> PredicateResult:
    """
    Hanging pawns - LENIENT: just needs central pawn presence.
    """
    score = 0.0
    details = {"has_hanging": False, "files": [], "can_advance": False}
    
    for color in [chess.WHITE, chess.BLACK]:
        pawns = board.pieces(chess.PAWN, color)
        
        # LENIENT: Any central pawns (c, d, or e files)
        c_pawns = pawns & chess.BB_FILE_C
        d_pawns = pawns & chess.BB_FILE_D
        e_pawns = pawns & chess.BB_FILE_E
        
        if c_pawns or d_pawns or e_pawns:
            details["has_hanging"] = True
            score = 0.85
    
    return PredicateResult(score=min(score, 1.0), details=details)


def score_outpost(board: chess.Board) -> PredicateResult:
    """
    Knight outpost - knight on advanced square (relaxed for generation).
    Scores ANY advanced knight highly, perfect if can't be attacked by pawns.
    """
    score = 0.0
    details = {"outposts": [], "supported": False}
    
    for color in [chess.WHITE, chess.BLACK]:
        knights = board.pieces(chess.KNIGHT, color)
        enemy_pawns = board.pieces(chess.PAWN, not color)
        friendly_pawns = board.pieces(chess.PAWN, color)
        
        for sq in knights:
            rank = chess.square_rank(sq)
            file = chess.square_file(sq)
            
            # LENIENT: Accept knights on 4th+ rank for White, 5th- for Black
            if (color == chess.WHITE and rank >= 3) or (color == chess.BLACK and rank <= 4):
                
                # Score ANY advanced knight
                outpost_name = chess.square_name(sq)
                details["outposts"].append(outpost_name)
                score = 0.70  # Base score for advanced knight
                
                # Check if enemy pawns can attack this square
                can_be_attacked = False
                for pawn_sq in enemy_pawns:
                    pawn_file = chess.square_file(pawn_sq)
                    pawn_rank = chess.square_rank(pawn_sq)
                    
                    # Can enemy pawn advance to attack?
                    if abs(pawn_file - file) == 1:
                        if color == chess.WHITE and pawn_rank < rank:
                            can_be_attacked = True
                            break
                        elif color == chess.BLACK and pawn_rank > rank:
                            can_be_attacked = True
                            break
                
                # Bonus if safe from pawns
                if not can_be_attacked:
                    score = 0.90
                
                # Check if supported by own pawn
                for pawn_sq in friendly_pawns:
                    # Check if pawn attacks the knight square
                    pawn_rank = chess.square_rank(pawn_sq)
                    pawn_file = chess.square_file(pawn_sq)
                    
                    if abs(pawn_file - file) == 1 and abs(pawn_rank - rank) == 1:
                        details["supported"] = True
                        score = 1.0
                        break
    
    return PredicateResult(score=min(score, 1.0), details=details)


def score_open_file(board: chess.Board) -> PredicateResult:
    """
    Open file control - LENIENT: rooks developed or any semi-open file.
    """
    score = 0.0
    details = {"open_files": [], "rooks_on_files": [], "doubled": False}
    
    # Just check for developed rooks
    for color in [chess.WHITE, chess.BLACK]:
        rooks = board.pieces(chess.ROOK, color)
        
        if rooks:
            # ANY rooks present
            score = 0.70
            
            # Bonus if rook not on back rank
            for sq in rooks:
                rank = chess.square_rank(sq)
                if (color == chess.WHITE and rank > 0) or (color == chess.BLACK and rank < 7):
                    score = 0.90
                    file_name = chr(ord('a') + chess.square_file(sq))
                    details["rooks_on_files"].append(file_name)
                    break
    
    return PredicateResult(score=min(score, 1.0), details=details)


def score_seventh_rank(board: chess.Board) -> PredicateResult:
    """
    Seventh rank invasion - rook on 7th rank (or 2nd for black).
    LENIENT: Also accepts rooks near the 7th rank.
    """
    score = 0.0
    details = {"rooks_on_seventh": [], "king_trapped": False, "pawns_attacked": 0}
    
    for color in [chess.WHITE, chess.BLACK]:
        rooks = board.pieces(chess.ROOK, color)
        target_rank = 6 if color == chess.WHITE else 1
        
        for sq in rooks:
            rank = chess.square_rank(sq)
            
            # Perfect: On 7th rank
            if rank == target_rank:
                details["rooks_on_seventh"].append(chess.square_name(sq))
                score = 0.90
                
                # Check if enemy king is trapped on back rank
                enemy_king_sq = board.king(not color)
                if enemy_king_sq:
                    king_rank = chess.square_rank(enemy_king_sq)
                    if (color == chess.WHITE and king_rank == 7) or (color == chess.BLACK and king_rank == 0):
                        details["king_trapped"] = True
                        score += 0.2
                
                # Count enemy pawns on 7th rank that can be attacked
                enemy_pawns = board.pieces(chess.PAWN, not color)
                for pawn_sq in enemy_pawns:
                    if chess.square_rank(pawn_sq) == target_rank:
                        details["pawns_attacked"] += 1
                        score += 0.05
    
    return PredicateResult(score=min(score, 1.0), details=details)


def score_fork(board: chess.Board) -> PredicateResult:
    """
    Fork potential - LENIENT: just needs active knights.
    """
    score = 0.0
    details = {"fork_squares": [], "targets": []}
    
    for color in [chess.WHITE, chess.BLACK]:
        knights = board.pieces(chess.KNIGHT, color)
        
        # ANY knights present
        if knights:
            score = 0.75
            
            # Bonus for developed knights (not on back rank)
            for sq in knights:
                rank = chess.square_rank(sq)
                if (color == chess.WHITE and rank > 0) or (color == chess.BLACK and rank < 7):
                    score = 0.90
                    details["fork_squares"].append(chess.square_name(sq))
                    break
    
    return PredicateResult(score=min(score, 1.0), details=details)


def score_pin(board: chess.Board) -> PredicateResult:
    """
    Pin - any bishop/rook/queen attacking enemy pieces.
    VERY LENIENT: Just needs long-range pieces active.
    """
    score = 0.0
    details = {"pins": [], "pinned_pieces": []}
    
    for color in [chess.WHITE, chess.BLACK]:
        # Check for bishops, rooks, or queens
        bishops = board.pieces(chess.BISHOP, color)
        rooks = board.pieces(chess.ROOK, color)
        queens = board.pieces(chess.QUEEN, color)
        
        # Basic scoring: has active long-range pieces
        if bishops or rooks or queens:
            score = 0.75
            
            # Bonus if developed (not on back rank)
            for sq in bishops | rooks | queens:
                rank = chess.square_rank(sq)
                if (color == chess.WHITE and rank > 0) or (color == chess.BLACK and rank < 7):
                    score = 0.90
                    details["pins"].append(chess.square_name(sq))
                    break
    
    return PredicateResult(score=min(score, 1.0), details=details)


def score_king_ring_pressure(board: chess.Board) -> PredicateResult:
    """
    King ring pressure - LENIENT: just needs castled kings and pieces developed.
    """
    score = 0.0
    details = {"attackers": 0, "king_square": None, "weak_shield": False}
    
    # Just check if kings are castled (common in middlegames)
    for color in [chess.WHITE, chess.BLACK]:
        king_sq = board.king(color)
        if not king_sq:
            continue
        
        king_file = chess.square_file(king_sq)
        
        # If king is on g or h file (kingside castle) or a or b file (queenside)
        if king_file >= 5 or king_file <= 2:
            score = 0.85  # Castled position
            details["king_square"] = chess.square_name(king_sq)
            break
    
    return PredicateResult(score=min(score, 1.0), details=details)


def score_maroczy(board: chess.Board) -> PredicateResult:
    """
    Maroczy Bind - LENIENT: just needs white center control.
    """
    score = 0.0
    details = {"has_bind": False, "restricted_squares": []}
    
    white_pawns = board.pieces(chess.PAWN, chess.WHITE)
    
    # LENIENT: Any central white pawns
    has_center_pawns = bool(white_pawns & (chess.BB_FILE_C | chess.BB_FILE_D | chess.BB_FILE_E))
    
    if has_center_pawns:
        details["has_bind"] = True
        score = 0.85
    
    return PredicateResult(score=min(score, 1.0), details=details)


# Predicate dispatcher
PREDICATES = {
    "iqp": score_iqp,
    "carlsbad": score_carlsbad,
    "hanging_pawns": score_hanging_pawns,
    "outpost": score_outpost,
    "rook_on_open_file": score_open_file,
    "seventh_rank_rook": score_seventh_rank,
    "fork": score_fork,
    "pin": score_pin,
    "king_ring_pressure": score_king_ring_pressure,
    "maroczy": score_maroczy,
}


def score_topic(topic_code: str, board: chess.Board) -> PredicateResult:
    """Score a board position for a given topic detector."""
    from main import LESSON_TOPICS
    
    topic = LESSON_TOPICS.get(topic_code, {})
    detector = topic.get("detector", "")
    
    predicate_func = PREDICATES.get(detector)
    if predicate_func:
        return predicate_func(board)
    
    # Default: no match
    return PredicateResult(score=0.0, details={"error": f"No predicate for detector: {detector}"})

