"""
Tag detection system for chess positions.
Detects 100+ specific tags across files, diagonals, outposts, center control, king safety, etc.
"""

import chess
from typing import List, Dict, Set, Optional


def detect_file_tags(board: chess.Board) -> List[Dict]:
    """Detect open/semi-open file tags and rook placements."""
    tags = []
    
    for file_idx in range(8):
        file_name = chess.FILE_NAMES[file_idx]
        white_pawns_on_file = sum(1 for sq in chess.SquareSet(chess.BB_FILES[file_idx]) 
                                   if board.piece_at(sq) == chess.Piece(chess.PAWN, chess.WHITE))
        black_pawns_on_file = sum(1 for sq in chess.SquareSet(chess.BB_FILES[file_idx]) 
                                   if board.piece_at(sq) == chess.Piece(chess.PAWN, chess.BLACK))
        
        # Open file
        if white_pawns_on_file == 0 and black_pawns_on_file == 0:
            tags.append({
                "tag_name": f"tag.file.open.{file_name}",
                "side": "both",
                "files": [file_name],
                "squares": [chess.square_name(sq) for sq in chess.SquareSet(chess.BB_FILES[file_idx])],
                "details": {}
            })
        # Semi-open for white
        elif white_pawns_on_file == 0 and black_pawns_on_file > 0:
            tags.append({
                "tag_name": f"tag.file.semi.{file_name}",
                "side": "white",
                "files": [file_name],
                "squares": [],
                "details": {}
            })
        # Semi-open for black
        elif black_pawns_on_file == 0 and white_pawns_on_file > 0:
            tags.append({
                "tag_name": f"tag.file.semi.{file_name}",
                "side": "black",
                "files": [file_name],
                "squares": [],
                "details": {}
            })
    
    # Rook on open/semi-open files
    for color in [chess.WHITE, chess.BLACK]:
        side = "white" if color == chess.WHITE else "black"
        for rook_sq in board.pieces(chess.ROOK, color):
            file_idx = chess.square_file(rook_sq)
            file_name = chess.FILE_NAMES[file_idx]
            
            white_pawns = sum(1 for sq in chess.SquareSet(chess.BB_FILES[file_idx]) 
                            if board.piece_at(sq) == chess.Piece(chess.PAWN, chess.WHITE))
            black_pawns = sum(1 for sq in chess.SquareSet(chess.BB_FILES[file_idx]) 
                            if board.piece_at(sq) == chess.Piece(chess.PAWN, chess.BLACK))
            
            if white_pawns == 0 and black_pawns == 0:
                tags.append({
                    "tag_name": "tag.rook.open_file",
                    "side": side,
                    "pieces": [f"R{chess.square_name(rook_sq)}"],
                    "files": [file_name],
                    "squares": [chess.square_name(rook_sq)],
                    "details": {}
                })
            elif (color == chess.WHITE and white_pawns == 0) or (color == chess.BLACK and black_pawns == 0):
                tags.append({
                    "tag_name": "tag.rook.semi_open",
                    "side": side,
                    "pieces": [f"R{chess.square_name(rook_sq)}"],
                    "files": [file_name],
                    "squares": [chess.square_name(rook_sq)],
                    "details": {}
                })
            
            # Rook on 7th rank
            rank = chess.square_rank(rook_sq)
            if (color == chess.WHITE and rank == 6) or (color == chess.BLACK and rank == 1):
                tags.append({
                    "tag_name": "tag.rook.rank7",
                    "side": side,
                    "pieces": [f"R{chess.square_name(rook_sq)}"],
                    "squares": [chess.square_name(rook_sq)],
                    "details": {}
                })
    
    # Connected rooks
    for color in [chess.WHITE, chess.BLACK]:
        side = "white" if color == chess.WHITE else "black"
        rooks = list(board.pieces(chess.ROOK, color))
        if len(rooks) == 2:
            r1, r2 = rooks[0], rooks[1]
            # Check if on same rank or file
            if chess.square_rank(r1) == chess.square_rank(r2) or chess.square_file(r1) == chess.square_file(r2):
                # Check if connected (no pieces between)
                try:
                    between_squares = list(chess.SquareSet.between(r1, r2))
                    if all(board.piece_at(sq) is None for sq in between_squares):
                        tags.append({
                            "tag_name": "tag.rook.connected",
                            "side": side,
                            "pieces": [f"R{chess.square_name(r1)}", f"R{chess.square_name(r2)}"],
                            "squares": [chess.square_name(r1), chess.square_name(r2)],
                            "details": {}
                        })
                except:
                    pass
    
    return tags


def detect_lever_tags(board: chess.Board) -> List[Dict]:
    """Detect pawn lever and break opportunities."""
    tags = []
    
    # Check potential levers for each color
    for color in [chess.WHITE, chess.BLACK]:
        side = "white" if color == chess.WHITE else "black"
        direction = 1 if color == chess.WHITE else -1
        
        for pawn_sq in board.pieces(chess.PAWN, color):
            file_idx = chess.square_file(pawn_sq)
            rank_idx = chess.square_rank(pawn_sq)
            
            # Check push square
            push_sq = pawn_sq + direction * 8
            if 0 <= push_sq < 64:
                push_name = chess.square_name(push_sq)
                
                # Check if pushing creates a lever
                for adj_file in [file_idx - 1, file_idx + 1]:
                    if 0 <= adj_file < 8:
                        adj_sq = chess.square(adj_file, chess.square_rank(push_sq))
                        if board.piece_at(adj_sq) == chess.Piece(chess.PAWN, not color):
                            tags.append({
                                "tag_name": f"tag.lever.{push_name}",
                                "side": side,
                                "pieces": [f"P{chess.square_name(pawn_sq)}"],
                                "squares": [push_name],
                                "details": {"target": chess.square_name(adj_sq)}
                            })
    
    return tags


def detect_diagonal_tags(board: chess.Board) -> List[Dict]:
    """Detect open/closed diagonals.
    Tags diagonals as open or closed, and only tags diagonals that:
    1. Have a bishop/queen on them (for open diagonals)
    2. Are significant (long diagonals or 3+ squares)
    
    This allows us to say things like:
    - "You opened the X diagonal" (was closed, now open)
    - "You closed the X diagonal" (was open, now closed)
    - "You placed your bishop on the open X diagonal" (diagonal was already open)
    """
    tags = []
    
    # Helper function to check if a diagonal is open (no pieces blocking)
    def check_diagonal_open(start_file: int, start_rank: int, direction: tuple) -> tuple:
        """Returns (is_open, end_square, squares)
        A diagonal is 'open' if there are no pieces blocking the path.
        """
        df, dr = direction  # direction file/rank deltas
        squares = []
        f, r = start_file + df, start_rank + dr
        blocked = False
        
        while 0 <= f <= 7 and 0 <= r <= 7 and not blocked:
            sq = chess.square(f, r)
            piece_at_sq = board.piece_at(sq)
            
            if piece_at_sq is None:
                # Empty square - diagonal is still open
                squares.append(chess.square_name(sq))
            else:
                # Hit a piece - diagonal is blocked
                blocked = True
                # Don't include the blocking square
                break
            
            f += df
            r += dr
        
        is_open = len(squares) >= 2  # At least 2 empty squares = open
        end_sq = squares[-1] if squares else ""
        return is_open, end_sq, squares
    
    # Check all diagonals for bishops and queens
    for color in [chess.WHITE, chess.BLACK]:
        side = "white" if color == chess.WHITE else "black"
        
        # Check bishops and queens
        for piece_type in [chess.BISHOP, chess.QUEEN]:
            for piece_sq in board.pieces(piece_type, color):
                piece_file = chess.square_file(piece_sq)
                piece_rank = chess.square_rank(piece_sq)
                piece_name = chess.square_name(piece_sq)
                piece_symbol = 'B' if piece_type == chess.BISHOP else 'Q'
                
                # Check each diagonal direction
                directions = [
                    ((1, 1), "ne"),   # Northeast
                    ((-1, 1), "nw"),  # Northwest
                    ((1, -1), "se"),  # Southeast
                    ((-1, -1), "sw")  # Southwest
                ]
                
                for (df, dr), dir_name in directions:
                    is_open, end_sq, squares = check_diagonal_open(piece_file, piece_rank, (df, dr))
                    
                    if is_open and end_sq and len(squares) >= 2:
                        # Name the diagonal by start-end squares
                        diag_name = f"{piece_name}-{end_sq}"
                        tags.append({
                            "tag_name": f"tag.diagonal.open.{diag_name}",
                            "side": side,
                            "pieces": [f"{piece_symbol}{piece_name}"],
                            "squares": squares[:7],
                            "direction": dir_name,
                            "details": {"length": len(squares), "open": True}
                        })
                
                # Check main long diagonals (a1-h8 or h1-a8)
                on_main_diag = (piece_file == piece_rank)  # a1-h8 diagonal
                on_anti_diag = (piece_file + piece_rank == 7)  # h1-a8 diagonal
                
                if on_main_diag:
                    # Check a1-h8 diagonal (both directions)
                    ne_open, ne_end, ne_squares = check_diagonal_open(piece_file, piece_rank, (1, 1))
                    sw_open, sw_end, sw_squares = check_diagonal_open(piece_file, piece_rank, (-1, -1))
                    total_length = len(ne_squares) + len(sw_squares) + 1  # +1 for piece square
                    
                    if total_length >= 4:  # Significant long diagonal
                        tags.append({
                            "tag_name": "tag.diagonal.open.long.a1h8",
                            "side": side,
                            "pieces": [f"{piece_symbol}{piece_name}"],
                            "squares": [chess.square_name(chess.square(piece_file, piece_rank))] + ne_squares[:3] + sw_squares[:3],
                            "details": {"on_main_diagonal": True, "open": True}
                        })
                
                if on_anti_diag:
                    # Check h1-a8 diagonal (both directions)
                    nw_open, nw_end, nw_squares = check_diagonal_open(piece_file, piece_rank, (-1, 1))
                    se_open, se_end, se_squares = check_diagonal_open(piece_file, piece_rank, (1, -1))
                    total_length = len(nw_squares) + len(se_squares) + 1  # +1 for piece square
                    
                    if total_length >= 4:  # Significant long diagonal
                        tags.append({
                            "tag_name": "tag.diagonal.open.long.h1a8",
                            "side": side,
                            "pieces": [f"{piece_symbol}{piece_name}"],
                            "squares": [chess.square_name(chess.square(piece_file, piece_rank))] + nw_squares[:3] + se_squares[:3],
                            "details": {"on_main_diagonal": True, "open": True}
                        })
    
    # Queen-Bishop batteries
    for color in [chess.WHITE, chess.BLACK]:
        side = "white" if color == chess.WHITE else "black"
        queens = list(board.pieces(chess.QUEEN, color))
        bishops = list(board.pieces(chess.BISHOP, color))
        
        for q_sq in queens:
            for b_sq in bishops:
                # Check if on same diagonal
                if abs(chess.square_file(q_sq) - chess.square_file(b_sq)) == abs(chess.square_rank(q_sq) - chess.square_rank(b_sq)):
                    # Check if aligned toward enemy king
                    opp_king = board.king(not color)
                    if opp_king:
                        if abs(chess.square_file(q_sq) - chess.square_file(opp_king)) == abs(chess.square_rank(q_sq) - chess.square_rank(opp_king)):
                            tags.append({
                                "tag_name": "tag.battery.qb.diagonal",
                                "side": side,
                                "pieces": [f"Q{chess.square_name(q_sq)}", f"B{chess.square_name(b_sq)}"],
                                "squares": [chess.square_name(q_sq), chess.square_name(b_sq)],
                                "details": {"target": chess.square_name(opp_king) if opp_king else ""}
                            })
    
    return tags


def detect_outpost_hole_tags(board: chess.Board) -> List[Dict]:
    """Detect outposts for knights and holes in pawn structure."""
    tags = []
    
    for color in [chess.WHITE, chess.BLACK]:
        side = "white" if color == chess.WHITE else "black"
        
        # Knight outposts
        for knight_sq in board.pieces(chess.KNIGHT, color):
            rank = chess.square_rank(knight_sq)
            file = chess.square_file(knight_sq)
            
            # Check if on 5th/6th rank (4/5 for white, 3/2 for black)
            if (color == chess.WHITE and rank in [4, 5]) or (color == chess.BLACK and rank in [2, 3]):
                # Check if protected by own pawn
                is_protected = any(
                    board.piece_at(sq) == chess.Piece(chess.PAWN, color)
                    for sq in board.attackers(color, knight_sq)
                )
                
                # Check if enemy pawns can't chase it
                can_be_chased = False
                for enemy_pawn_sq in board.pieces(chess.PAWN, not color):
                    if chess.square_distance(knight_sq, enemy_pawn_sq) <= 2:
                        can_be_chased = True
                        break
                
                if is_protected and not can_be_chased:
                    tags.append({
                        "tag_name": f"tag.square.outpost.knight.{chess.square_name(knight_sq)}",
                        "side": side,
                        "pieces": [f"N{chess.square_name(knight_sq)}"],
                        "squares": [chess.square_name(knight_sq)],
                        "details": {"protected": is_protected}
                    })
        
        # Color complex holes - STRICT LOGIC (no false positives in early openings)
        # Only detect holes that are actually relevant and created by pawn structure changes
        
        king_sq = board.king(color)
        if not king_sq:
            continue
            
        # Define zones
        side_zone = range(0, 40) if color == chess.WHITE else range(24, 64)  # Own 5 ranks
        king_zone = set()  # 3x3 + next ring (distance <= 2)
        for sq in chess.SQUARES:
            if chess.square_distance(sq, king_sq) <= 2:
                king_zone.add(sq)
        
        pawn_front_band = range(16, 48) if color == chess.WHITE else range(16, 48)  # Ranks 3-6
        
        # Check for pawn structure change (gate for hole detection)
        # Detect if any pawn has moved from starting position
        has_pawn_structure_change = False
        
        for pawn_sq in board.pieces(chess.PAWN, color):
            pawn_rank = chess.square_rank(pawn_sq)
            starting_rank = 1 if color == chess.WHITE else 6
            if pawn_rank != starting_rank:
                has_pawn_structure_change = True
                break
        
        # Also check if pawn count decreased (capture/promotion)
        total_pawns = len(list(board.pieces(chess.PAWN, chess.WHITE))) + len(list(board.pieces(chess.PAWN, chess.BLACK)))
        if total_pawns < 16:
            has_pawn_structure_change = True
        
        if not has_pawn_structure_change:
            # Skip hole detection in starting position or before any pawn moves
            continue
        
        # Only check king zone for holes (most relevant)
        for sq in king_zone:
            sq_file = chess.square_file(sq)
            sq_rank = chess.square_rank(sq)
            
            # Skip if occupied
            if board.piece_at(sq):
                continue
            
            # Determine square color
            sq_color_val = (sq_file + sq_rank) % 2
            sq_color = "dark" if sq_color_val == 1 else "light"
            
            # Check if no pawn can attack/reach in 1 move
            can_be_guarded = False
            for pawn_sq in board.pieces(chess.PAWN, color):
                # Check if pawn currently attacks sq
                if sq in board.attacks(pawn_sq):
                    can_be_guarded = True
                    break
                
                # Check if pawn can attack sq in 1 move (push)
                direction = 1 if color == chess.WHITE else -1
                push_sq = pawn_sq + direction * 8
                if 0 <= push_sq < 64 and not board.piece_at(push_sq):
                    # Would pawn attack sq after push?
                    push_file = chess.square_file(push_sq)
                    if abs(sq_file - push_file) == 1 and chess.square_rank(push_sq) == sq_rank:
                        can_be_guarded = True
                        break
            
            if can_be_guarded:
                continue
            
            # Check if opponent controls this hole AND it's adjacent to where king will be
            # Only tag if opponent is pressuring the hole
            opp_control = len(board.attackers(not color, sq)) > 0
            adjacent_to_king_file = abs(sq_file - chess.square_file(king_sq)) <= 1
            
            if opp_control and adjacent_to_king_file:
                # This is a pressured hole in king zone - tag it
                tags.append({
                    "tag_name": f"tag.color.hole.{sq_color}.{chess.square_name(sq)}",
                    "side": side,
                    "squares": [chess.square_name(sq)],
                    "details": {"color": sq_color, "zone": "king_zone", "opp_control": True}
                })
    
    return tags


def detect_center_space_tags(board: chess.Board) -> List[Dict]:
    """Detect center control and space advantage."""
    tags = []
    
    core_squares = [chess.D4, chess.E4, chess.D5, chess.E5]
    near_center = [chess.C4, chess.F4, chess.C5, chess.F5]
    key_squares = {"e4": chess.E4, "d4": chess.D4, "e5": chess.E5, "d5": chess.D5}
    
    for color in [chess.WHITE, chess.BLACK]:
        side = "white" if color == chess.WHITE else "black"
        
        # Core center control
        core_control = sum(1 for sq in core_squares if len(board.attackers(color, sq)) > len(board.attackers(not color, sq)))
        if core_control >= 2:
            tags.append({
                "tag_name": "tag.center.control.core",
                "side": side,
                "squares": [chess.square_name(sq) for sq in core_squares if len(board.attackers(color, sq)) > len(board.attackers(not color, sq))],
                "details": {"count": core_control}
            })
        
        # Near center control
        near_control = sum(1 for sq in near_center if len(board.attackers(color, sq)) > len(board.attackers(not color, sq)))
        if near_control >= 2:
            tags.append({
                "tag_name": "tag.center.control.near",
                "side": side,
                "squares": [chess.square_name(sq) for sq in near_center if len(board.attackers(color, sq)) > len(board.attackers(not color, sq))],
                "details": {"count": near_control}
            })
        
        # Individual key squares
        piece_names = {chess.PAWN: 'Pawn', chess.KNIGHT: 'Knight', chess.BISHOP: 'Bishop',
                       chess.ROOK: 'Rook', chess.QUEEN: 'Queen', chess.KING: 'King'}
        
        for sq_name, sq in key_squares.items():
            if len(board.attackers(color, sq)) > len(board.attackers(not color, sq)) or (board.piece_at(sq) and board.piece_at(sq).color == color):
                # Get controlling pieces
                controlling_pieces = []
                for ctrl_sq in board.attackers(color, sq):
                    ctrl_piece = board.piece_at(ctrl_sq)
                    if ctrl_piece:
                        controlling_pieces.append({
                            "square": chess.square_name(ctrl_sq),
                            "piece": ctrl_piece.symbol(),
                            "piece_name": piece_names.get(ctrl_piece.piece_type, 'Piece')
                        })
                
                # Check if occupied
                occupant = board.piece_at(sq)
                if occupant and occupant.color == color:
                    controlling_pieces.append({
                        "square": sq_name,
                        "piece": occupant.symbol(),
                        "piece_name": piece_names.get(occupant.piece_type, 'Piece'),
                        "occupying": True
                    })
                
                tags.append({
                    "tag_name": f"tag.key.{sq_name}",
                    "side": side,
                    "squares": [sq_name],
                    "controlling_pieces": controlling_pieces[:5],  # Limit to 5
                    "details": {}
                })
        
        # Space advantage (controlled squares in opponent half)
        opp_half = range(32, 64) if color == chess.WHITE else range(0, 32)
        space_control = sum(1 for sq in opp_half if len(board.attackers(color, sq)) > 0)
        own_half = range(0, 32) if color == chess.WHITE else range(32, 64)
        opp_control_own = sum(1 for sq in own_half if len(board.attackers(not color, sq)) > 0)
        
        if space_control - opp_control_own > 5:
            tags.append({
                "tag_name": "tag.space.advantage",
                "side": side,
                "squares": [],
                "details": {"differential": space_control - opp_control_own}
            })
    
    return tags


def detect_king_safety_tags(board: chess.Board) -> List[Dict]:
    """Detect king safety factors."""
    tags = []
    
    for color in [chess.WHITE, chess.BLACK]:
        side = "white" if color == chess.WHITE else "black"
        king_sq = board.king(color)
        if not king_sq:
            continue
        
        file_idx = chess.square_file(king_sq)
        rank_idx = chess.square_rank(king_sq)
        
        # King center exposed - STRICT LOGIC (requires ALL conditions)
        # Must have: king on e/d file, central file open/semi-open, AND shield deficiency
        if file_idx in [3, 4]:  # d or e file
            # Check if central files (d and e) are open or semi-open
            central_files_open = False
            for central_file in [3, 4]:  # d and e files
                white_pawns_central = sum(1 for r in range(8) if board.piece_at(chess.square(central_file, r)) == chess.Piece(chess.PAWN, chess.WHITE))
                black_pawns_central = sum(1 for r in range(8) if board.piece_at(chess.square(central_file, r)) == chess.Piece(chess.PAWN, chess.BLACK))
                
                if white_pawns_central == 0 or black_pawns_central == 0:
                    central_files_open = True
                    break
            
            # Check shield deficiency (≤1 shield pawns remaining)
            shield_files = [5, 6, 7] if file_idx >= 5 else [5, 6, 7]  # Default to kingside
            # Determine intended castle side if not yet castled
            if board.has_castling_rights(color):
                # Default to kingside unless queenside signals detected
                if board.has_queenside_castling_rights(color) and not board.has_kingside_castling_rights(color):
                    shield_files = [0, 1, 2]  # Queenside
            
            shield_rank = 1 if color == chess.WHITE else 6
            shield_pawns = sum(1 for f in shield_files 
                             if board.piece_at(chess.square(f, shield_rank)) == chess.Piece(chess.PAWN, color))
            
            # Only emit if central file open AND shield deficiency (≤1 pawns)
            if central_files_open and shield_pawns <= 1:
                tags.append({
                    "tag_name": "tag.king.center.exposed",
                    "side": side,
                    "squares": [chess.square_name(king_sq)],
                    "details": {"shield_pawns": shield_pawns, "central_files_open": True}
                })
        
        # Shield integrity (for castled king)
        if not board.has_castling_rights(color):
            # Castled - check shield
            shield_files = []
            if file_idx >= 5:  # Kingside castle
                shield_files = [5, 6, 7]  # f, g, h
            elif file_idx <= 2:  # Queenside castle
                shield_files = [0, 1, 2]  # a, b, c
            
            if shield_files:
                shield_rank = 1 if color == chess.WHITE else 6
                shield_pawns = sum(1 for f in shield_files 
                                 if board.piece_at(chess.square(f, shield_rank)) == chess.Piece(chess.PAWN, color))
                
                if shield_pawns == 3:
                    tags.append({
                        "tag_name": "tag.king.shield.intact",
                        "side": side,
                        "squares": [chess.square_name(king_sq)],
                        "details": {"pawns": shield_pawns}
                    })
                else:
                    for f in shield_files:
                        if board.piece_at(chess.square(f, shield_rank)) != chess.Piece(chess.PAWN, color):
                            tags.append({
                                "tag_name": f"tag.king.shield.missing.{chess.FILE_NAMES[f]}",
                                "side": side,
                                "squares": [chess.square_name(king_sq)],
                                "details": {}
                            })
        
        # Open/semi-open files toward king
        for adj_file in [file_idx - 1, file_idx, file_idx + 1]:
            if 0 <= adj_file < 8:
                white_pawns = sum(1 for r in range(8) if board.piece_at(chess.square(adj_file, r)) == chess.Piece(chess.PAWN, chess.WHITE))
                black_pawns = sum(1 for r in range(8) if board.piece_at(chess.square(adj_file, r)) == chess.Piece(chess.PAWN, chess.BLACK))
                
                if white_pawns == 0 and black_pawns == 0:
                    tags.append({
                        "tag_name": "tag.king.file.open",
                        "side": side,
                        "files": [chess.FILE_NAMES[adj_file]],
                        "squares": [chess.square_name(king_sq)],
                        "details": {}
                    })
                elif (color == chess.WHITE and white_pawns == 0) or (color == chess.BLACK and black_pawns == 0):
                    tags.append({
                        "tag_name": "tag.king.file.semi",
                        "side": side,
                        "files": [chess.FILE_NAMES[adj_file]],
                        "squares": [chess.square_name(king_sq)],
                        "details": {}
                    })
    
    return tags


def detect_castling_tags(board: chess.Board) -> List[Dict]:
    """Detect castling availability and castling rights."""
    tags = []
    
    for color in [chess.WHITE, chess.BLACK]:
        side = "white" if color == chess.WHITE else "black"
        
        # Check if it's this side's turn
        is_side_to_move = (board.turn == color)
        
        # Check castling rights
        has_kingside_rights = board.has_kingside_castling_rights(color)
        has_queenside_rights = board.has_queenside_castling_rights(color)
        
        if has_kingside_rights:
            # Always expose RIGHTS when they exist (rights != legal-right-now).
            # This prevents confusing deltas like "rights lost" when castling merely becomes legal.
            tags.append({
                "tag_name": "tag.castling.rights.kingside",
                "side": side,
                "squares": [],
                "details": {"rights": True}
            })

            # Separately expose availability (legal now / would be legal on this side's turn).
            can_castle_kingside = False
            if is_side_to_move:
                # Check if O-O is a legal move
                for move in board.legal_moves:
                    if move.from_square == board.king(color):
                        try:
                            san = board.san(move)
                            if san == "O-O":
                                can_castle_kingside = True
                                break
                        except Exception:
                            continue
            else:
                # Not this side's turn - check if it would be legal on their turn
                temp_board = board.copy()
                temp_board.turn = color
                for move in temp_board.legal_moves:
                    if move.from_square == temp_board.king(color):
                        try:
                            san = temp_board.san(move)
                            if san == "O-O":
                                can_castle_kingside = True
                                break
                        except Exception:
                            continue
            
            if can_castle_kingside:
                tags.append({
                    "tag_name": "tag.castling.available.kingside",
                    "side": side,
                    "squares": [],
                    "details": {"legal": True}
                })
        
        if has_queenside_rights:
            # Always expose RIGHTS when they exist (rights != legal-right-now).
            tags.append({
                "tag_name": "tag.castling.rights.queenside",
                "side": side,
                "squares": [],
                "details": {"rights": True}
            })

            # Separately expose availability (legal now / would be legal on this side's turn).
            can_castle_queenside = False
            if is_side_to_move:
                # Check if O-O-O is a legal move
                for move in board.legal_moves:
                    if move.from_square == board.king(color):
                        try:
                            san = board.san(move)
                            if san == "O-O-O":
                                can_castle_queenside = True
                                break
                        except Exception:
                            continue
            else:
                # Not this side's turn - check if it would be legal on their turn
                temp_board = board.copy()
                temp_board.turn = color
                for move in temp_board.legal_moves:
                    if move.from_square == temp_board.king(color):
                        try:
                            san = temp_board.san(move)
                            if san == "O-O-O":
                                can_castle_queenside = True
                                break
                        except Exception:
                            continue
            
            if can_castle_queenside:
                tags.append({
                    "tag_name": "tag.castling.available.queenside",
                    "side": side,
                    "squares": [],
                    "details": {"legal": True}
                })
    
    return tags


def detect_king_safety_tags(board: chess.Board) -> List[Dict]:
    """Detect king safety factors."""
    tags = []
    
    for color in [chess.WHITE, chess.BLACK]:
        side = "white" if color == chess.WHITE else "black"
        king_sq = board.king(color)
        if not king_sq:
            continue
        
        file_idx = chess.square_file(king_sq)
        rank_idx = chess.square_rank(king_sq)
        
        # Attackers vs defenders count with piece details
        piece_names = {chess.PAWN: 'Pawn', chess.KNIGHT: 'Knight', chess.BISHOP: 'Bishop',
                       chess.ROOK: 'Rook', chess.QUEEN: 'Queen', chess.KING: 'King'}
        
        king_attackers = board.attackers(not color, king_sq)
        king_defenders = board.attackers(color, king_sq)
        
        attacker_list = []
        for atk_sq in king_attackers:
            atk_piece = board.piece_at(atk_sq)
            if atk_piece:
                attacker_list.append({
                    "square": chess.square_name(atk_sq),
                    "piece": atk_piece.symbol(),
                    "piece_name": piece_names.get(atk_piece.piece_type, 'Piece')
                })
        
        defender_list = []
        for def_sq in king_defenders:
            def_piece = board.piece_at(def_sq)
            if def_piece:
                defender_list.append({
                    "square": chess.square_name(def_sq),
                    "piece": def_piece.symbol(),
                    "piece_name": piece_names.get(def_piece.piece_type, 'Piece')
                })
        
        tags.append({
            "tag_name": "tag.king.attackers.count",
            "side": side,
            "squares": [chess.square_name(king_sq)],
            "attackers_count": len(king_attackers),
            "attacking_pieces": attacker_list,
            "details": {"count": len(king_attackers)}
        })
        
        tags.append({
            "tag_name": "tag.king.defenders.count",
            "side": side,
            "squares": [chess.square_name(king_sq)],
            "defenders_count": len(king_defenders),
            "defending_pieces": defender_list,
            "details": {"count": len(king_defenders)}
        })
    
    return tags


def detect_activity_tags(board: chess.Board) -> List[Dict]:
    """Detect piece activity and mobility."""
    tags = []
    
    for color in [chess.WHITE, chess.BLACK]:
        side = "white" if color == chess.WHITE else "black"
        
        # Mobility per piece type
        for piece_type, piece_name in [(chess.KNIGHT, "knight"), (chess.BISHOP, "bishop"), 
                                        (chess.ROOK, "rook"), (chess.QUEEN, "queen")]:
            total_mobility = 0
            for piece_sq in board.pieces(piece_type, color):
                mobility = len(list(board.attacks(piece_sq)))
                total_mobility += mobility
            
            if total_mobility > 0:
                tags.append({
                    "tag_name": f"tag.activity.mobility.{piece_name}",
                    "side": side,
                    "squares": [],
                    "details": {"mobility": total_mobility}
                })
        
        # Undeveloped pieces (on starting squares)
        starting_squares_map = {
            chess.KNIGHT: ([chess.B1, chess.G1] if color == chess.WHITE else [chess.B8, chess.G8]),
            chess.BISHOP: ([chess.C1, chess.F1] if color == chess.WHITE else [chess.C8, chess.F8]),
            chess.ROOK: ([chess.A1, chess.H1] if color == chess.WHITE else [chess.A8, chess.H8]),
            chess.QUEEN: ([chess.D1] if color == chess.WHITE else [chess.D8])
        }
        
        for piece_type, starting_squares in starting_squares_map.items():
            # IMPORTANT: emit ONE tag per undeveloped piece-square (not an aggregate list).
            # Otherwise, when one piece develops (e.g. Ng8->f6), the aggregate tag instance
            # changes shape (["b8","g8"] -> ["b8"]) and can show up as "gained" + "lost"
            # in instance-level deltas even though no piece "became undeveloped again".
            undeveloped_sqs: List[int] = []
            for sq in board.pieces(piece_type, color):
                if sq in starting_squares:
                    undeveloped_sqs.append(sq)

            if undeveloped_sqs:
                piece_name = {chess.KNIGHT: "knight", chess.BISHOP: "bishop",
                              chess.ROOK: "rook", chess.QUEEN: "queen"}[piece_type]
                piece_symbol = {chess.KNIGHT: "N", chess.BISHOP: "B",
                                chess.ROOK: "R", chess.QUEEN: "Q"}[piece_type]
                total_count = len(undeveloped_sqs)
                for sq in sorted(undeveloped_sqs):
                    sq_name = chess.square_name(sq)
                    tags.append({
                        "tag_name": f"tag.undeveloped.{piece_name}",
                        "side": side,
                        "squares": [sq_name],
                        "pieces": [f"{piece_symbol}{sq_name}"],
                        "details": {"count": 1, "count_total": total_count}
                    })
        
        # Trapped pieces
        piece_names_short = {chess.KNIGHT: 'Knight', chess.BISHOP: 'Bishop', chess.ROOK: 'Rook'}
        for piece_type in [chess.KNIGHT, chess.BISHOP, chess.ROOK]:
            for piece_sq in board.pieces(piece_type, color):
                all_moves = list(board.attacks(piece_sq))
                safe_sq_list = [sq for sq in all_moves if not board.is_attacked_by(not color, sq)]
                attacked_sq_list = [sq for sq in all_moves if board.is_attacked_by(not color, sq)]
                
                if len(safe_sq_list) <= 1:
                    tags.append({
                        "tag_name": "tag.piece.trapped",
                        "side": side,
                        "piece_type": piece_names_short[piece_type],
                        "pieces": [f"{'N' if piece_type == chess.KNIGHT else 'B' if piece_type == chess.BISHOP else 'R'}{chess.square_name(piece_sq)}"],
                        "squares": [chess.square_name(piece_sq)],
                        "safe_squares_count": len(safe_sq_list),
                        "safe_squares": [chess.square_name(sq) for sq in safe_sq_list],
                        "attacked_squares": [chess.square_name(sq) for sq in attacked_sq_list],
                        "details": {"safe_squares": len(safe_sq_list)}
                    })
        
        # Bad bishop
        for bishop_sq in board.pieces(chess.BISHOP, color):
            # Determine bishop square color: dark if (file+rank) is odd
            bishop_color = (chess.square_file(bishop_sq) + chess.square_rank(bishop_sq)) % 2
            same_color_pawns = sum(1 for pawn_sq in board.pieces(chess.PAWN, color) 
                                  if (chess.square_file(pawn_sq) + chess.square_rank(pawn_sq)) % 2 == bishop_color)
            total_pawns = len(list(board.pieces(chess.PAWN, color)))
            
            if total_pawns > 0 and same_color_pawns / total_pawns > 0.6:
                mobility = len(list(board.attacks(bishop_sq)))
                if mobility < 5:
                    tags.append({
                        "tag_name": "tag.bishop.bad",
                        "side": side,
                        "pieces": [f"B{chess.square_name(bishop_sq)}"],
                        "squares": [chess.square_name(bishop_sq)],
                        "details": {"locked_pawns": same_color_pawns, "mobility": mobility}
                    })
        
        # Bishop pair
        if len(list(board.pieces(chess.BISHOP, color))) == 2:
            tags.append({
                "tag_name": "tag.bishop.pair",
                "side": side,
                "pieces": [f"B{chess.square_name(sq)}" for sq in board.pieces(chess.BISHOP, color)],
                "squares": [],
                "details": {}
            })
    
    return tags


def detect_pawn_tags(board: chess.Board) -> List[Dict]:
    """Detect passed pawns and pawn structure."""
    tags = []
    
    for color in [chess.WHITE, chess.BLACK]:
        side = "white" if color == chess.WHITE else "black"
        direction = 1 if color == chess.WHITE else -1

        # Doubled pawns (same-file): generally a structural weakness.
        for file_idx in range(8):
            pawns_on_file = [sq for sq in board.pieces(chess.PAWN, color) if chess.square_file(sq) == file_idx]
            if len(pawns_on_file) >= 2:
                file_name = chess.FILE_NAMES[file_idx]
                tags.append({
                    "tag_name": f"tag.pawn.doubled.{file_name}",
                    "side": side,
                    "pieces": [f"P{chess.square_name(sq)}" for sq in pawns_on_file],
                    "squares": [chess.square_name(sq) for sq in pawns_on_file],
                    "details": {"file": file_name, "count": len(pawns_on_file)}
                })
        
        for pawn_sq in board.pieces(chess.PAWN, color):
            file_idx = chess.square_file(pawn_sq)
            rank_idx = chess.square_rank(pawn_sq)
            
            # Check if passed
            is_passed = True
            end_rank = 7 if color == chess.WHITE else 0
            for check_rank in range(rank_idx + direction, end_rank + direction, direction):
                # Check file and adjacent files
                for check_file in [file_idx - 1, file_idx, file_idx + 1]:
                    if 0 <= check_file < 8 and 0 <= check_rank < 8:
                        sq = chess.square(check_file, check_rank)
                        if board.piece_at(sq) == chess.Piece(chess.PAWN, not color):
                            is_passed = False
                            break
                if not is_passed:
                    break
            
            if is_passed:
                # Check if protected
                is_protected = any(board.piece_at(sq) == chess.Piece(chess.PAWN, color) 
                                 for sq in board.attackers(color, pawn_sq))
                
                tags.append({
                    "tag_name": f"tag.pawn.passed.{chess.square_name(pawn_sq)}",
                    "side": side,
                    "pieces": [f"P{chess.square_name(pawn_sq)}"],
                    "squares": [chess.square_name(pawn_sq)],
                    "details": {"protected": is_protected}
                })
                
                if is_protected:
                    tags.append({
                        "tag_name": "tag.pawn.passed.protected",
                        "side": side,
                        "pieces": [f"P{chess.square_name(pawn_sq)}"],
                        "squares": [chess.square_name(pawn_sq)],
                        "details": {}
                    })
    
    return tags


def detect_knight_rim_tags(board: chess.Board) -> List[Dict]:
    """Detect knights on the rim/edge of the board (often positionally inferior)."""
    tags: List[Dict] = []
    for color in [chess.WHITE, chess.BLACK]:
        side = "white" if color == chess.WHITE else "black"
        for knight_sq in board.pieces(chess.KNIGHT, color):
            file_idx = chess.square_file(knight_sq)
            rank_idx = chess.square_rank(knight_sq)
            # "Knight on the rim" is conventionally an a/h-file knight.
            # (Avoid tagging starting-position knights on rank 1/8, which would be noisy.)
            if file_idx in (0, 7):
                tags.append({
                    "tag_name": "tag.knight.rim",
                    "side": side,
                    "pieces": [f"N{chess.square_name(knight_sq)}"],
                    "squares": [chess.square_name(knight_sq)],
                    "details": {
                        "file": chess.FILE_NAMES[file_idx],
                        "rank": str(rank_idx + 1),
                        "is_edge_file": file_idx in (0, 7),
                        "is_edge_rank": False,
                    }
                })
    return tags


async def aggregate_all_tags(board: chess.Board, engine_queue) -> List[Dict]:
    """
    Aggregate all tag detectors and return unified tag list.
    
    Args:
        board: Chess board position
        engine_queue: Stockfish engine queue (for tactical tag detection)
        
    Returns:
        List of all detected tags
    """
    from threat_detector import detect_all_threats
    
    all_tags = []
    
    # Call all tag detectors
    all_tags.extend(detect_file_tags(board))
    all_tags.extend(detect_lever_tags(board))
    all_tags.extend(detect_diagonal_tags(board))
    all_tags.extend(detect_outpost_hole_tags(board))
    all_tags.extend(detect_center_space_tags(board))
    all_tags.extend(detect_king_safety_tags(board))
    all_tags.extend(detect_activity_tags(board))
    all_tags.extend(detect_pawn_tags(board))
    all_tags.extend(detect_knight_rim_tags(board))
    all_tags.extend(detect_castling_tags(board))
    
    # Add threat tags for both sides (with side field added)
    white_threats = detect_all_threats(board, chess.WHITE)
    for threat in white_threats:
        threat["side"] = "white"
    all_tags.extend(white_threats)
    
    black_threats = detect_all_threats(board, chess.BLACK)
    for threat in black_threats:
        threat["side"] = "black"
    all_tags.extend(black_threats)
    
    return all_tags


def detect_overworked_pieces_tags(board: chess.Board) -> List[Dict]:
    """
    Detect overworked pieces - pieces defending multiple attacked pieces.
    A piece is overworked if it defends 2+ attacked pieces and recapturing one
    leaves the other undefended.
    """
    tags = []
    
    for color in [chess.WHITE, chess.BLACK]:
        side = "white" if color == chess.WHITE else "black"
        opponent = not color
        
        # Check all piece types
        for piece_type in [chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN]:
            for defender_sq in board.pieces(piece_type, color):
                defender_piece = board.piece_at(defender_sq)
                if not defender_piece:
                    continue
                
                # Find all pieces this defender is protecting that are also attacked
                defended_pieces = []
                for target_sq in chess.SQUARES:
                    target_piece = board.piece_at(target_sq)
                    if target_piece and target_piece.color == color and target_sq != defender_sq:
                        # Check if defender attacks this target (defends it)
                        if target_sq in board.attacks(defender_sq):
                            # Check if target is attacked by opponent
                            if board.is_attacked_by(opponent, target_sq):
                                # Get all defenders of this target
                                all_defenders = list(board.attackers(color, target_sq))
                                defended_pieces.append({
                                    "square": target_sq,
                                    "piece": target_piece,
                                    "attackers": list(board.attackers(opponent, target_sq)),
                                    "all_defenders": all_defenders
                                })
                
                # Check for overworked piece (defending 2+ attacked pieces)
                if len(defended_pieces) >= 2:
                    # Check if recapturing one leaves the other undefended
                    for i, piece1 in enumerate(defended_pieces):
                        for piece2 in defended_pieces[i+1:]:
                            # Check if piece1 has other defenders besides this one
                            piece1_other_defenders = [d for d in piece1["all_defenders"] if d != defender_sq]
                            
                            # Check if piece2 has other defenders besides this one  
                            piece2_other_defenders = [d for d in piece2["all_defenders"] if d != defender_sq]
                            
                            # If both pieces have NO other defenders, this piece is overworked
                            # OR if one has no other defenders and recapturing the other leaves it undefended
                            is_overworked = False
                            if len(piece1_other_defenders) == 0 and len(piece2_other_defenders) == 0:
                                # Both rely solely on this defender
                                is_overworked = True
                            elif len(piece1_other_defenders) == 0 or len(piece2_other_defenders) == 0:
                                # At least one relies solely on this defender
                                # Check if recapturing the one with other defenders leaves the other undefended
                                if len(piece1_other_defenders) == 0:
                                    # piece1 has no other defenders, piece2 might have
                                    # If we recapture piece2's attacker, piece1 is still undefended
                                    is_overworked = True
                                elif len(piece2_other_defenders) == 0:
                                    # piece2 has no other defenders, piece1 might have
                                    # If we recapture piece1's attacker, piece2 is still undefended
                                    is_overworked = True
                            
                            if is_overworked:
                                # Both pieces rely solely on this defender - overworked!
                                piece1_name = chess.piece_name(piece1["piece"].piece_type).capitalize()
                                piece2_name = chess.piece_name(piece2["piece"].piece_type).capitalize()
                                piece_symbol = chess.piece_symbol(defender_piece.piece_type).upper()
                                
                                tags.append({
                                    "tag_name": f"tag.piece.overworked.{chess.square_name(defender_sq)}",
                                    "side": side,
                                    "pieces": [f"{piece_symbol}{chess.square_name(defender_sq)}"],
                                    "squares": [chess.square_name(defender_sq)],
                                    "defended_pieces": [
                                        {
                                            "square": chess.square_name(piece1["square"]),
                                            "piece_type": piece1_name,
                                            "attackers": [chess.square_name(sq) for sq in piece1["attackers"]]
                                        },
                                        {
                                            "square": chess.square_name(piece2["square"]),
                                            "piece_type": piece2_name,
                                            "attackers": [chess.square_name(sq) for sq in piece2["attackers"]]
                                        }
                                    ],
                                    "details": {
                                        "defended_count": len(defended_pieces),
                                        "vulnerable": True,  # Can't recapture both
                                        "description": f"{piece_symbol} on {chess.square_name(defender_sq)} defends {piece1_name} on {chess.square_name(piece1['square'])} and {piece2_name} on {chess.square_name(piece2['square'])}, but can only recapture one"
                                    }
                                })
                                break
                        # Break outer loop if we found an overworked piece for this defender
                        if len(tags) > 0 and tags[-1].get("tag_name", "").endswith(chess.square_name(defender_sq)):
                            break
    
    return tags

