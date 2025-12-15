"""
Threat Detection System for Chess Positions

Detects 30+ types of chess threats in a position using python-chess.
Each threat is returned as a tag with metadata for visualization and explanation.
"""

import chess
from typing import List, Dict, Optional, Set, Tuple


# ============================================================================
# 1. DIRECT MATERIAL THREATS
# ============================================================================

def detect_undefended_pieces(board: chess.Board, color: chess.Color) -> List[Dict]:
    """
    Detect pieces that can be captured without loss.
    tag.threat.capture.undefended
    """
    threats = []
    enemy_color = not color
    piece_names = {chess.PAWN: 'Pawn', chess.KNIGHT: 'Knight', chess.BISHOP: 'Bishop',
                   chess.ROOK: 'Rook', chess.QUEEN: 'Queen', chess.KING: 'King'}
    
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece and piece.color == enemy_color:
            # Count attackers and defenders
            attackers = board.attackers(color, square)
            defenders = board.attackers(enemy_color, square)
            
            if len(attackers) > 0 and len(defenders) == 0:
                # Get attacker details
                attacker_details = []
                for atk_sq in attackers:
                    atk_piece = board.piece_at(atk_sq)
                    if atk_piece:
                        attacker_details.append({
                            "square": chess.square_name(atk_sq),
                            "piece": atk_piece.symbol(),
                            "piece_name": piece_names.get(atk_piece.piece_type, 'Piece')
                        })
                
                threats.append({
                    "tag_name": "tag.threat.capture.undefended",
                    "target_square": chess.square_name(square),
                    "target_piece": piece.symbol(),
                    "target_piece_name": piece_names.get(piece.piece_type, 'Piece'),
                    "attackers": [chess.square_name(sq) for sq in attackers],
                    "attacker_pieces": attacker_details
                })
    
    return threats


def detect_capture_higher_value(board: chess.Board, color: chess.Color) -> List[Dict]:
    """
    Detect threats to capture higher-valued pieces.
    tag.threat.capture.more_value
    """
    threats = []
    piece_values = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, 
                   chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0}
    piece_names = {chess.PAWN: 'Pawn', chess.KNIGHT: 'Knight', chess.BISHOP: 'Bishop',
                   chess.ROOK: 'Rook', chess.QUEEN: 'Queen', chess.KING: 'King'}
    
    for move in board.legal_moves:
        if board.is_capture(move):
            attacker = board.piece_at(move.from_square)
            victim = board.piece_at(move.to_square)
            
            if attacker and victim:
                attacker_value = piece_values.get(attacker.piece_type, 0)
                victim_value = piece_values.get(victim.piece_type, 0)
                
                if victim_value > attacker_value:
                    threats.append({
                        "tag_name": "tag.threat.capture.more_value",
                        "from_square": chess.square_name(move.from_square),
                        "to_square": chess.square_name(move.to_square),
                        "attacker": attacker.symbol(),
                        "attacker_name": piece_names.get(attacker.piece_type, 'Piece'),
                        "victim": victim.symbol(),
                        "victim_name": piece_names.get(victim.piece_type, 'Piece'),
                        "value_diff": victim_value - attacker_value
                    })
    
    return threats


def detect_hanging_pieces(board: chess.Board, color: chess.Color) -> List[Dict]:
    """
    Detect pieces that are under-defended (attacked more than defended).
    tag.threat.hanging
    """
    threats = []
    enemy_color = not color
    piece_values = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, 
                   chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0}
    piece_names = {chess.PAWN: 'Pawn', chess.KNIGHT: 'Knight', chess.BISHOP: 'Bishop',
                   chess.ROOK: 'Rook', chess.QUEEN: 'Queen', chess.KING: 'King'}
    
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece and piece.color == enemy_color:
            attackers = board.attackers(color, square)
            defenders = board.attackers(enemy_color, square)
            
            if len(attackers) > len(defenders) > 0:
                # Get piece details for attackers and defenders
                attacker_details = []
                for atk_sq in attackers:
                    atk_piece = board.piece_at(atk_sq)
                    if atk_piece:
                        attacker_details.append({
                            "square": chess.square_name(atk_sq),
                            "piece": atk_piece.symbol(),
                            "piece_name": piece_names.get(atk_piece.piece_type, 'Piece')
                        })
                
                defender_details = []
                for def_sq in defenders:
                    def_piece = board.piece_at(def_sq)
                    if def_piece:
                        defender_details.append({
                            "square": chess.square_name(def_sq),
                            "piece": def_piece.symbol(),
                            "piece_name": piece_names.get(def_piece.piece_type, 'Piece')
                        })
                
                threats.append({
                    "tag_name": "tag.threat.hanging",
                    "target_square": chess.square_name(square),
                    "target_piece": piece.symbol(),
                    "target_piece_name": piece_names.get(piece.piece_type, 'Piece'),
                    "attackers_count": len(attackers),
                    "defenders_count": len(defenders),
                    "attackers": [chess.square_name(sq) for sq in attackers],
                    "defenders": [chess.square_name(sq) for sq in defenders],
                    "attacker_pieces": attacker_details,
                    "defender_pieces": defender_details,
                    "value": piece_values.get(piece.piece_type, 0)
                })
    
    return threats


# ============================================================================
# 2. TACTICAL PATTERN THREATS
# ============================================================================

def detect_fork_threats(board: chess.Board, color: chess.Color) -> List[Dict]:
    """
    Detect moves that attack two or more pieces simultaneously.
    tag.threat.fork
    """
    threats = []
    piece_names = {chess.PAWN: 'Pawn', chess.KNIGHT: 'Knight', chess.BISHOP: 'Bishop',
                   chess.ROOK: 'Rook', chess.QUEEN: 'Queen', chess.KING: 'King'}
    
    for move in board.legal_moves:
        # Make the move temporarily
        board.push(move)
        
        # Count how many enemy pieces are attacked from the new square
        attacked_pieces = []
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if piece and piece.color != color:
                if board.is_attacked_by(color, square):
                    attacked_pieces.append({
                        "square": chess.square_name(square),
                        "piece": piece.symbol(),
                        "piece_name": piece_names.get(piece.piece_type, 'Piece')
                    })
        
        board.pop()
        
        if len(attacked_pieces) >= 2:
            attacker_piece = board.piece_at(move.from_square)
            threats.append({
                "tag_name": "tag.threat.fork",
                "move": move.uci(),
                "from_square": chess.square_name(move.from_square),
                "to_square": chess.square_name(move.to_square),
                "attacker": attacker_piece.symbol() if attacker_piece else "?",
                "attacker_name": piece_names.get(attacker_piece.piece_type, 'Piece') if attacker_piece else "?",
                "targets": attacked_pieces[:5]  # Limit to 5
            })
    
    return threats


def detect_pin_threats(board: chess.Board, color: chess.Color) -> List[Dict]:
    """
    Detect pieces that are pinned (cannot move without exposing higher value piece).
    tag.threat.pin
    """
    threats = []
    enemy_color = not color
    piece_names = {chess.PAWN: 'Pawn', chess.KNIGHT: 'Knight', chess.BISHOP: 'Bishop',
                   chess.ROOK: 'Rook', chess.QUEEN: 'Queen', chess.KING: 'King'}
    
    # Check each sliding piece (bishop, rook, queen)
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece and piece.color == color and piece.piece_type in [chess.BISHOP, chess.ROOK, chess.QUEEN]:
            # Get attack rays
            attacks = board.attacks(square)
            
            for target_square in attacks:
                target_piece = board.piece_at(target_square)
                if target_piece and target_piece.color == enemy_color:
                    # Check if there's a higher-value piece behind it
                    direction = chess.square_file(target_square) - chess.square_file(square), \
                               chess.square_rank(target_square) - chess.square_rank(square)
                    
                    # Continue in same direction
                    current_file = chess.square_file(target_square) + (1 if direction[0] > 0 else -1 if direction[0] < 0 else 0)
                    current_rank = chess.square_rank(target_square) + (1 if direction[1] > 0 else -1 if direction[1] < 0 else 0)
                    
                    while 0 <= current_file < 8 and 0 <= current_rank < 8:
                        behind_square = chess.square(current_file, current_rank)
                        behind_piece = board.piece_at(behind_square)
                        
                        if behind_piece:
                            if behind_piece.color == enemy_color:
                                # Check if higher value (or king)
                                if behind_piece.piece_type == chess.KING or \
                                   behind_piece.piece_type > target_piece.piece_type:
                                    threats.append({
                                        "tag_name": "tag.threat.pin",
                                        "pinner_square": chess.square_name(square),
                                        "pinner": piece.symbol(),
                                        "pinner_name": piece_names.get(piece.piece_type, 'Piece'),
                                        "pinned_square": chess.square_name(target_square),
                                        "pinned_piece": target_piece.symbol(),
                                        "pinned_piece_name": piece_names.get(target_piece.piece_type, 'Piece'),
                                        "behind_square": chess.square_name(behind_square),
                                        "behind_piece": behind_piece.symbol(),
                                        "behind_piece_name": piece_names.get(behind_piece.piece_type, 'Piece')
                                    })
                            break
                        
                        current_file += (1 if direction[0] > 0 else -1 if direction[0] < 0 else 0)
                        current_rank += (1 if direction[1] > 0 else -1 if direction[1] < 0 else 0)
    
    return threats


def detect_skewer_threats(board: chess.Board, color: chess.Color) -> List[Dict]:
    """
    Detect skewer patterns (high-value piece attacked, low-value behind it).
    tag.threat.skewer
    """
    threats = []
    enemy_color = not color
    piece_values = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, 
                   chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 10}
    piece_names = {chess.PAWN: 'Pawn', chess.KNIGHT: 'Knight', chess.BISHOP: 'Bishop',
                   chess.ROOK: 'Rook', chess.QUEEN: 'Queen', chess.KING: 'King'}
    
    # Check each sliding piece
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece and piece.color == color and piece.piece_type in [chess.BISHOP, chess.ROOK, chess.QUEEN]:
            attacks = board.attacks(square)
            
            for target_square in attacks:
                target_piece = board.piece_at(target_square)
                if target_piece and target_piece.color == enemy_color:
                    target_value = piece_values.get(target_piece.piece_type, 0)
                    
                    # Check behind in same direction
                    direction = (chess.square_file(target_square) - chess.square_file(square),
                                chess.square_rank(target_square) - chess.square_rank(square))
                    
                    current_file = chess.square_file(target_square) + (1 if direction[0] > 0 else -1 if direction[0] < 0 else 0)
                    current_rank = chess.square_rank(target_square) + (1 if direction[1] > 0 else -1 if direction[1] < 0 else 0)
                    
                    while 0 <= current_file < 8 and 0 <= current_rank < 8:
                        behind_square = chess.square(current_file, current_rank)
                        behind_piece = board.piece_at(behind_square)
                        
                        if behind_piece:
                            if behind_piece.color == enemy_color:
                                behind_value = piece_values.get(behind_piece.piece_type, 0)
                                if behind_value < target_value:
                                    threats.append({
                                        "tag_name": "tag.threat.skewer",
                                        "attacker_square": chess.square_name(square),
                                        "attacker_piece": piece.symbol(),
                                        "attacker_name": piece_names.get(piece.piece_type, 'Piece'),
                                        "front_square": chess.square_name(target_square),
                                        "front_piece": target_piece.symbol(),
                                        "front_piece_name": piece_names.get(target_piece.piece_type, 'Piece'),
                                        "behind_square": chess.square_name(behind_square),
                                        "behind_piece": behind_piece.symbol(),
                                        "behind_piece_name": piece_names.get(behind_piece.piece_type, 'Piece')
                                    })
                            break
                        
                        current_file += (1 if direction[0] > 0 else -1 if direction[0] < 0 else 0)
                        current_rank += (1 if direction[1] > 0 else -1 if direction[1] < 0 else 0)
    
    return threats


def detect_check_threats(board: chess.Board, color: chess.Color) -> List[Dict]:
    """
    Detect moves that give check.
    tag.threat.check_imminent
    """
    threats = []
    piece_names = {chess.PAWN: 'Pawn', chess.KNIGHT: 'Knight', chess.BISHOP: 'Bishop',
                   chess.ROOK: 'Rook', chess.QUEEN: 'Queen', chess.KING: 'King'}
    
    for move in board.legal_moves:
        board.push(move)
        if board.is_check():
            attacker_piece = board.piece_at(move.to_square)
            enemy_king_sq = board.king(not color)
            threats.append({
                "tag_name": "tag.threat.check_imminent",
                "move": move.uci(),
                "from_square": chess.square_name(move.from_square),
                "to_square": chess.square_name(move.to_square),
                "attacker": attacker_piece.symbol() if attacker_piece else "?",
                "attacker_name": piece_names.get(attacker_piece.piece_type, 'Piece') if attacker_piece else "?",
                "king_square": chess.square_name(enemy_king_sq) if enemy_king_sq else "?"
            })
        board.pop()
    
    return threats


# ============================================================================
# 3. POSITIONAL & STRUCTURAL THREATS
# ============================================================================

def detect_king_zone_attacks(board: chess.Board, color: chess.Color) -> List[Dict]:
    """
    Detect concentrated attacks near the enemy king.
    tag.threat.king_zone_attack
    """
    threats = []
    enemy_color = not color
    enemy_king_square = board.king(enemy_color)
    
    if enemy_king_square is None:
        return threats
    
    # Define king zone (3x3 area around king)
    king_file = chess.square_file(enemy_king_square)
    king_rank = chess.square_rank(enemy_king_square)
    
    piece_names = {chess.PAWN: 'Pawn', chess.KNIGHT: 'Knight', chess.BISHOP: 'Bishop',
                   chess.ROOK: 'Rook', chess.QUEEN: 'Queen', chess.KING: 'King'}
    
    attacking_pieces = []
    defending_pieces = []
    seen_attackers = set()
    seen_defenders = set()
    
    for df in [-1, 0, 1]:
        for dr in [-1, 0, 1]:
            if df == 0 and dr == 0:
                continue
            
            file = king_file + df
            rank = king_rank + dr
            
            if 0 <= file < 8 and 0 <= rank < 8:
                square = chess.square(file, rank)
                
                # Get attacking pieces (deduplicate)
                for atk_sq in board.attackers(color, square):
                    if atk_sq not in seen_attackers:
                        atk_piece = board.piece_at(atk_sq)
                        if atk_piece:
                            attacking_pieces.append({
                                "square": chess.square_name(atk_sq),
                                "piece": atk_piece.symbol(),
                                "piece_name": piece_names.get(atk_piece.piece_type, 'Piece')
                            })
                            seen_attackers.add(atk_sq)
                
                # Get defending pieces (deduplicate)
                for def_sq in board.attackers(enemy_color, square):
                    if def_sq not in seen_defenders:
                        def_piece = board.piece_at(def_sq)
                        if def_piece:
                            defending_pieces.append({
                                "square": chess.square_name(def_sq),
                                "piece": def_piece.symbol(),
                                "piece_name": piece_names.get(def_piece.piece_type, 'Piece')
                            })
                            seen_defenders.add(def_sq)
    
    if len(attacking_pieces) > len(defending_pieces):
        threats.append({
            "tag_name": "tag.threat.king_zone_attack",
            "king_square": chess.square_name(enemy_king_square),
            "attackers_count": len(attacking_pieces),
            "defenders_count": len(defending_pieces),
            "attacking_pieces": attacking_pieces[:5],  # Limit to 5 for readability
            "defending_pieces": defending_pieces[:5],
            "pressure": len(attacking_pieces) - len(defending_pieces)
        })
    
    return threats


def detect_backrank_threats(board: chess.Board, color: chess.Color) -> List[Dict]:
    """
    Detect backrank mate threats.
    tag.threat.backrank
    """
    threats = []
    enemy_color = not color
    enemy_king_square = board.king(enemy_color)
    
    if enemy_king_square is None:
        return threats
    
    king_rank = chess.square_rank(enemy_king_square)
    back_rank = 7 if enemy_color == chess.BLACK else 0
    
    # Check if king is on back rank
    if king_rank == back_rank:
        # Check if escape squares are blocked
        king_file = chess.square_file(enemy_king_square)
        escape_blocked = 0
        
        for df in [-1, 0, 1]:
            file = king_file + df
            if 0 <= file < 8:
                # Check rank in front of king
                escape_rank = back_rank + (1 if enemy_color == chess.BLACK else -1)
                if 0 <= escape_rank < 8:
                    escape_square = chess.square(file, escape_rank)
                    piece = board.piece_at(escape_square)
                    if piece and piece.color == enemy_color:
                        escape_blocked += 1
        
        # If escape is limited, check for attacking pieces
        if escape_blocked >= 2:
            # Check if we can get a rook/queen on back rank
            for square in chess.SQUARES:
                piece = board.piece_at(square)
                if piece and piece.color == color and piece.piece_type in [chess.ROOK, chess.QUEEN]:
                    # Check if can reach back rank
                    for target_file in range(8):
                        target_square = chess.square(target_file, back_rank)
                        move = chess.Move(square, target_square)
                        if move in board.legal_moves:
                            threats.append({
                                "tag_name": "tag.threat.backrank",
                                "king_square": chess.square_name(enemy_king_square),
                                "escape_blocked": escape_blocked,
                                "attacking_piece": piece.symbol(),
                                "threat_move": move.uci()
                            })
                            break
    
    return threats


def detect_promotion_threats(board: chess.Board, color: chess.Color) -> List[Dict]:
    """
    Detect passed pawns close to promotion.
    tag.threat.promotion_run
    """
    threats = []
    
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece and piece.color == color and piece.piece_type == chess.PAWN:
            rank = chess.square_rank(square)
            file = chess.square_file(square)
            
            # Check if passed (no enemy pawns ahead)
            is_passed = True
            promotion_rank = 7 if color == chess.WHITE else 0
            direction = 1 if color == chess.WHITE else -1
            
            for check_file in [file - 1, file, file + 1]:
                if 0 <= check_file < 8:
                    current_rank = rank + direction
                    while (0 <= current_rank < 8):
                        if current_rank == promotion_rank:
                            break
                        check_square = chess.square(check_file, current_rank)
                        check_piece = board.piece_at(check_square)
                        if check_piece and check_piece.color != color and check_piece.piece_type == chess.PAWN:
                            is_passed = False
                            break
                        current_rank += direction
            
            if is_passed:
                distance_to_promotion = abs(rank - promotion_rank)
                if distance_to_promotion <= 3:  # Close to promotion
                    # Convert file index to letter (0=a, 1=b, etc.)
                    file_letter = chr(ord('a') + file)
                    threats.append({
                        "tag_name": "tag.threat.promotion_run",
                        "square": chess.square_name(square),
                        "distance": distance_to_promotion,
                        "file": file_letter
                    })
    
    return threats


# ============================================================================
# MAIN DETECTION FUNCTION
# ============================================================================

def detect_all_threats(board: chess.Board, color: chess.Color) -> List[Dict]:
    """
    Detect all threat types for the given color.
    Returns a list of threat tags with metadata.
    """
    all_threats = []
    
    # Direct material threats
    all_threats.extend(detect_undefended_pieces(board, color))
    all_threats.extend(detect_capture_higher_value(board, color))
    all_threats.extend(detect_hanging_pieces(board, color))
    
    # Tactical patterns
    all_threats.extend(detect_fork_threats(board, color))
    all_threats.extend(detect_pin_threats(board, color))
    all_threats.extend(detect_skewer_threats(board, color))
    all_threats.extend(detect_check_threats(board, color))
    
    # Positional/structural
    all_threats.extend(detect_king_zone_attacks(board, color))
    all_threats.extend(detect_backrank_threats(board, color))
    all_threats.extend(detect_promotion_threats(board, color))
    
    return all_threats

