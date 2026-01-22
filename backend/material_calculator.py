"""
Material balance calculator for chess positions.
Simple piece value calculation: P=1, N/B=3, R=5, Q=9 (in centipawns).
"""

import chess
from typing import Dict


def calculate_material_balance(board: chess.Board) -> int:
    """
    Returns material balance in centipawns (positive = white ahead).
    
    Args:
        board: Chess board position
        
    Returns:
        Material balance in centipawns (100cp = 1 pawn)
    """
    piece_values = {
        chess.PAWN: 100,
        chess.KNIGHT: 300,
        chess.BISHOP: 300,
        chess.ROOK: 500,
        chess.QUEEN: 900
    }
    
    white_material = 0
    black_material = 0
    
    for square, piece in board.piece_map().items():
        value = piece_values.get(piece.piece_type, 0)
        if piece.color == chess.WHITE:
            white_material += value
        else:
            black_material += value
    
    return white_material - black_material


def get_material_count(board: chess.Board) -> Dict:
    """
    Returns detailed material count for both sides.
    
    Returns:
        {
            "white": {"pawns": int, "knights": int, ...},
            "black": {"pawns": int, "knights": int, ...}
        }
    """
    count = {
        "white": {"pawns": 0, "knights": 0, "bishops": 0, "rooks": 0, "queens": 0},
        "black": {"pawns": 0, "knights": 0, "bishops": 0, "rooks": 0, "queens": 0}
    }
    
    for piece in board.piece_map().values():
        side = "white" if piece.color == chess.WHITE else "black"
        if piece.piece_type == chess.PAWN:
            count[side]["pawns"] += 1
        elif piece.piece_type == chess.KNIGHT:
            count[side]["knights"] += 1
        elif piece.piece_type == chess.BISHOP:
            count[side]["bishops"] += 1
        elif piece.piece_type == chess.ROOK:
            count[side]["rooks"] += 1
        elif piece.piece_type == chess.QUEEN:
            count[side]["queens"] += 1
    
    return count




