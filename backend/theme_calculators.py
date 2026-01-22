"""
Theme calculators for chess positions.
Implements all 14 chess themes with scoring functions.
"""

import chess
from typing import Dict, List


def ctrl(board: chess.Board, color: chess.Color, square: chess.Square) -> int:
    """Returns 1 if color controls square, else 0."""
    return 1 if len(board.attackers(color, square)) > len(board.attackers(not color, square)) else 0


def calculate_center_space(board: chess.Board) -> Dict:
    """
    Theme 1: Center & Space
    Returns scores for central control, tension, and space advantage.
    """
    core_squares = [chess.D4, chess.E4, chess.D5, chess.E5]
    near_center = [chess.C4, chess.F4, chess.C5, chess.F5]
    
    white_result = {"S_center": 0, "S_tension": 0, "S_space": 0, "total": 0}
    black_result = {"S_center": 0, "S_tension": 0, "S_space": 0, "total": 0}
    
    # 1.1 Central Control
    for color, result in [(chess.WHITE, white_result), (chess.BLACK, black_result)]:
        central_core = sum(ctrl(board, color, sq) for sq in core_squares)
        near = sum(ctrl(board, color, sq) for sq in near_center)
        result["S_center"] = 2 * central_core + 1 * near
    
    # 1.2 Central Tension (pawn levers)
    white_result["S_tension"] = _calculate_tension(board, chess.WHITE)
    black_result["S_tension"] = _calculate_tension(board, chess.BLACK)
    
    # 1.3 Space Advantage
    white_result["S_space"] = _calculate_space(board, chess.WHITE)
    black_result["S_space"] = _calculate_space(board, chess.BLACK)
    
    # Totals
    white_result["total"] = sum([white_result["S_center"], white_result["S_tension"], white_result["S_space"]])
    black_result["total"] = sum([black_result["S_center"], black_result["S_tension"], black_result["S_space"]])
    
    return {"white": white_result, "black": black_result}


def _calculate_tension(board: chess.Board, color: chess.Color) -> float:
    """Calculate pawn tension in center."""
    tension = 0
    d_file_pawns = [sq for sq in board.pieces(chess.PAWN, color) if chess.square_file(sq) == 3]
    e_file_pawns = [sq for sq in board.pieces(chess.PAWN, color) if chess.square_file(sq) == 4]
    
    for pawn_sq in d_file_pawns + e_file_pawns:
        rank = chess.square_rank(pawn_sq)
        file = chess.square_file(pawn_sq)
        direction = 1 if color == chess.WHITE else -1
        
        # Check for opposing pawns
        for adj_file in [file - 1, file + 1]:
            if 0 <= adj_file < 8:
                check_rank = rank + direction
                if 0 <= check_rank < 8:
                    check_sq = chess.square(adj_file, check_rank)
                    if board.piece_at(check_sq) == chess.Piece(chess.PAWN, not color):
                        tension += 1
    
    return tension


def _calculate_space(board: chess.Board, color: chess.Color) -> float:
    """Calculate space advantage (controlled squares in opponent half)."""
    opp_half = range(32, 64) if color == chess.WHITE else range(0, 32)
    own_half = range(0, 32) if color == chess.WHITE else range(32, 64)
    
    space_for = sum(1 for sq in opp_half if len(board.attackers(color, sq)) > 0)
    space_against = sum(1 for sq in own_half if len(board.attackers(not color, sq)) > 0)
    
    return space_for - space_against


def calculate_pawn_structure(board: chess.Board) -> Dict:
    """
    Theme 2: Pawn Structure
    Returns scores for passed pawns, candidates, weaknesses, chains, levers, majorities.
    """
    white_result = {"S_passed": 0, "S_candidate": 0, "S_isolated": 0, "S_doubled": 0, 
                    "S_backward": 0, "S_chain": 0, "S_chain_base_weak": 0, "S_levers_ready": 0,
                    "S_majority_qside": 0, "S_majority_kside": 0, "S_islands": 0, "total": 0}
    black_result = white_result.copy()
    
    for color, result in [(chess.WHITE, white_result), (chess.BLACK, black_result)]:
        # 2.1 Passed & Candidate Pawns
        for pawn_sq in board.pieces(chess.PAWN, color):
            if _is_passed_pawn(board, pawn_sq, color):
                is_protected = any(board.piece_at(sq) == chess.Piece(chess.PAWN, color) 
                                 for sq in board.attackers(color, pawn_sq))
                result["S_passed"] += 1 + (0.3 if is_protected else 0)
            elif _is_candidate_passer(board, pawn_sq, color):
                result["S_candidate"] += 1
        
        # 2.2 Weaknesses
        result["S_isolated"] = _count_isolated_pawns(board, color)
        result["S_doubled"] = _count_doubled_pawns(board, color)
        result["S_backward"] = _count_backward_pawns(board, color)
        
        # 2.3 Chains
        result["S_chain"] = _count_pawn_chain_links(board, color)
        
        # 2.4 Levers
        result["S_levers_ready"] = _count_ready_levers(board, color)
        
        # 2.5 Majorities
        result["S_majority_qside"], result["S_majority_kside"] = _calculate_majorities(board, color)
        result["S_islands"] = -_count_pawn_islands(board, color)
    
    # Calculate totals
    for result in [white_result, black_result]:
        result["total"] = (result["S_passed"] + result["S_candidate"] - result["S_isolated"] 
                         - result["S_doubled"] + result["S_backward"] + result["S_chain"] 
                         - result["S_chain_base_weak"] + result["S_levers_ready"] 
                         + result["S_majority_qside"] + result["S_majority_kside"] + result["S_islands"])
    
    return {"white": white_result, "black": black_result}


def _is_passed_pawn(board: chess.Board, pawn_sq: chess.Square, color: chess.Color) -> bool:
    """Check if pawn is passed."""
    file_idx = chess.square_file(pawn_sq)
    rank_idx = chess.square_rank(pawn_sq)
    direction = 1 if color == chess.WHITE else -1
    end_rank = 7 if color == chess.WHITE else 0
    
    for check_rank in range(rank_idx + direction, end_rank + direction, direction):
        for check_file in [file_idx - 1, file_idx, file_idx + 1]:
            if 0 <= check_file < 8 and 0 <= check_rank < 8:
                sq = chess.square(check_file, check_rank)
                if board.piece_at(sq) == chess.Piece(chess.PAWN, not color):
                    return False
    return True


def _is_candidate_passer(board: chess.Board, pawn_sq: chess.Square, color: chess.Color) -> bool:
    """Check if pawn is one move from becoming passed."""
    # Simplified: check if one push would make it passed
    direction = 1 if color == chess.WHITE else -1
    push_sq = pawn_sq + direction * 8
    if 0 <= push_sq < 64 and not board.piece_at(push_sq):
        # Would it be passed after push?
        temp_board = board.copy()
        temp_board.remove_piece_at(pawn_sq)
        temp_board.set_piece_at(push_sq, chess.Piece(chess.PAWN, color))
        return _is_passed_pawn(temp_board, push_sq, color)
    return False


def _count_isolated_pawns(board: chess.Board, color: chess.Color) -> int:
    """Count isolated pawns."""
    count = 0
    for pawn_sq in board.pieces(chess.PAWN, color):
        file_idx = chess.square_file(pawn_sq)
        is_isolated = True
        for adj_file in [file_idx - 1, file_idx + 1]:
            if 0 <= adj_file < 8:
                if any(chess.square_file(sq) == adj_file for sq in board.pieces(chess.PAWN, color)):
                    is_isolated = False
                    break
        if is_isolated:
            count += 1
    return count


def _count_doubled_pawns(board: chess.Board, color: chess.Color) -> int:
    """Count doubled pawns."""
    files_with_doubled = 0
    for file_idx in range(8):
        pawns_on_file = sum(1 for sq in board.pieces(chess.PAWN, color) if chess.square_file(sq) == file_idx)
        if pawns_on_file > 1:
            files_with_doubled += pawns_on_file - 1
    return files_with_doubled


def _count_backward_pawns(board: chess.Board, color: chess.Color) -> int:
    """Count backward pawns."""
    count = 0
    direction = 1 if color == chess.WHITE else -1
    
    for pawn_sq in board.pieces(chess.PAWN, color):
        file_idx = chess.square_file(pawn_sq)
        rank_idx = chess.square_rank(pawn_sq)
        
        # Check if no friendly pawns on adjacent files are behind or level
        has_support = False
        for adj_file in [file_idx - 1, file_idx + 1]:
            if 0 <= adj_file < 8:
                for adj_pawn_sq in board.pieces(chess.PAWN, color):
                    if chess.square_file(adj_pawn_sq) == adj_file:
                        adj_rank = chess.square_rank(adj_pawn_sq)
                        if (color == chess.WHITE and adj_rank <= rank_idx) or (color == chess.BLACK and adj_rank >= rank_idx):
                            has_support = True
                            break
        
        # Check if square in front is attacked
        push_sq = pawn_sq + direction * 8
        if 0 <= push_sq < 64:
            if board.is_attacked_by(not color, push_sq) and not has_support:
                count += 1
    
    return count


def _count_pawn_chain_links(board: chess.Board, color: chess.Color) -> int:
    """Count diagonal pawn chain links."""
    links = 0
    direction = 1 if color == chess.WHITE else -1
    
    for pawn_sq in board.pieces(chess.PAWN, color):
        file_idx = chess.square_file(pawn_sq)
        rank_idx = chess.square_rank(pawn_sq)
        
        # Check diagonal support
        for adj_file in [file_idx - 1, file_idx + 1]:
            if 0 <= adj_file < 8:
                support_sq = chess.square(adj_file, rank_idx - direction)
                if 0 <= chess.square_rank(support_sq) < 8:
                    if board.piece_at(support_sq) == chess.Piece(chess.PAWN, color):
                        links += 1
    
    return links // 2  # Each link counted twice


def _count_ready_levers(board: chess.Board, color: chess.Color) -> int:
    """Count ready pawn levers/breaks."""
    count = 0
    direction = 1 if color == chess.WHITE else -1
    
    for pawn_sq in board.pieces(chess.PAWN, color):
        push_sq = pawn_sq + direction * 8
        if 0 <= push_sq < 64 and not board.piece_at(push_sq):
            # Would push create a lever?
            file_idx = chess.square_file(push_sq)
            for adj_file in [file_idx - 1, file_idx + 1]:
                if 0 <= adj_file < 8:
                    adj_sq = chess.square(adj_file, chess.square_rank(push_sq))
                    if board.piece_at(adj_sq) == chess.Piece(chess.PAWN, not color):
                        count += 1
                        break
    
    return count


def _calculate_majorities(board: chess.Board, color: chess.Color) -> tuple:
    """Calculate queenside and kingside pawn majorities."""
    own_qside = sum(1 for sq in board.pieces(chess.PAWN, color) if chess.square_file(sq) <= 3)
    own_kside = sum(1 for sq in board.pieces(chess.PAWN, color) if chess.square_file(sq) >= 4)
    opp_qside = sum(1 for sq in board.pieces(chess.PAWN, not color) if chess.square_file(sq) <= 3)
    opp_kside = sum(1 for sq in board.pieces(chess.PAWN, not color) if chess.square_file(sq) >= 4)
    
    qside_majority = max(0, own_qside - opp_qside)
    kside_majority = max(0, own_kside - opp_kside)
    
    return qside_majority, kside_majority


def _count_pawn_islands(board: chess.Board, color: chess.Color) -> int:
    """Count number of pawn islands."""
    files_with_pawns = [False] * 8
    for pawn_sq in board.pieces(chess.PAWN, color):
        files_with_pawns[chess.square_file(pawn_sq)] = True
    
    islands = 0
    in_island = False
    for has_pawn in files_with_pawns:
        if has_pawn and not in_island:
            islands += 1
            in_island = True
        elif not has_pawn:
            in_island = False
    
    return islands


def calculate_king_safety(board: chess.Board) -> Dict:
    """
    Theme 3: King Safety
    Returns scores for shield, open lines, local force, exposure, hooks, holes.
    """
    white_result = {"S_shield": 0, "S_files_to_king": 0, "S_diagonals_to_king": 0, 
                    "S_local": 0, "S_center_king": 0, "S_castled": 0, "S_hook": 0, "S_holes": 0, "total": 0}
    black_result = white_result.copy()
    
    for color, result in [(chess.WHITE, white_result), (chess.BLACK, black_result)]:
        king_sq = board.king(color)
        if not king_sq:
            continue
        
        # 3.1 Shield Integrity
        result["S_shield"] = _calculate_shield(board, king_sq, color)
        
        # 3.2 Open Lines to King
        result["S_files_to_king"], result["S_diagonals_to_king"] = _calculate_open_lines_to_king(board, king_sq, color)
        
        # 3.3 Local Force
        result["S_local"] = _calculate_local_force(board, king_sq, color)
        
        # 3.4 Central Exposure
        if chess.square_file(king_sq) in [3, 4] and board.has_castling_rights(color):
            result["S_center_king"] = -1
        
        # 3.5 Castled bonus
        if not board.has_castling_rights(color):
            result["S_castled"] = 1
        
        result["total"] = sum([result["S_shield"], result["S_files_to_king"], result["S_diagonals_to_king"],
                             result["S_local"], result["S_center_king"], result["S_castled"], 
                             result["S_hook"], result["S_holes"]])
    
    return {"white": white_result, "black": black_result}


def _calculate_shield(board: chess.Board, king_sq: chess.Square, color: chess.Color) -> float:
    """Calculate pawn shield score."""
    file_idx = chess.square_file(king_sq)
    shield_rank = 1 if color == chess.WHITE else 6
    shield_files = []
    
    if file_idx >= 5:  # Kingside
        shield_files = [5, 6, 7]
    elif file_idx <= 2:  # Queenside
        shield_files = [0, 1, 2]
    
    if not shield_files:
        return 0
    
    shield_pawns = sum(1 for f in shield_files 
                      if board.piece_at(chess.square(f, shield_rank)) == chess.Piece(chess.PAWN, color))
    
    return shield_pawns - (3 - shield_pawns)  # Bonus for intact, penalty for missing


def _calculate_open_lines_to_king(board: chess.Board, king_sq: chess.Square, color: chess.Color) -> tuple:
    """Calculate open files and diagonals toward king."""
    file_idx = chess.square_file(king_sq)
    files_score = 0
    
    # Check king file and adjacent
    for check_file in [file_idx - 1, file_idx, file_idx + 1]:
        if 0 <= check_file < 8:
            white_pawns = sum(1 for r in range(8) if board.piece_at(chess.square(check_file, r)) == chess.Piece(chess.PAWN, chess.WHITE))
            black_pawns = sum(1 for r in range(8) if board.piece_at(chess.square(check_file, r)) == chess.Piece(chess.PAWN, chess.BLACK))
            
            if white_pawns == 0 and black_pawns == 0:
                files_score -= 1.0
            elif (color == chess.WHITE and white_pawns == 0) or (color == chess.BLACK and black_pawns == 0):
                files_score -= 0.5
    
    # Simplified diagonal check
    diag_score = 0
    
    return files_score, diag_score


def _calculate_local_force(board: chess.Board, king_sq: chess.Square, color: chess.Color) -> float:
    """Calculate attackers vs defenders in king ring."""
    attackers = len(board.attackers(not color, king_sq))
    defenders = len(board.attackers(color, king_sq))
    return defenders - attackers


def calculate_piece_activity(board: chess.Board) -> Dict:
    """
    Theme 4: Piece Activity & Coordination
    Returns scores for mobility, outposts, traps, bishop quality, rook deployment, coordination.
    """
    white_result = {"S_mob": 0, "S_outpost": 0, "S_trapped": 0, "S_bad_bishop": 0, 
                    "S_bishop_pair": 0, "S_rook_open": 0, "S_rook_connected": 0, 
                    "S_rook_7th": 0, "S_coord": 0, "total": 0}
    black_result = white_result.copy()
    
    for color, result in [(chess.WHITE, white_result), (chess.BLACK, black_result)]:
        # 4.1 Mobility
        result["S_mob"] = _calculate_mobility(board, color)
        
        # 4.2 Outposts
        result["S_outpost"] = _calculate_outposts(board, color)
        
        # 4.3 Trapped pieces
        result["S_trapped"] = _count_trapped_pieces(board, color)
        
        # 4.4 Bad bishops
        result["S_bad_bishop"] = _count_bad_bishops(board, color)
        
        # 4.5 Bishop pair
        if len(list(board.pieces(chess.BISHOP, color))) == 2:
            result["S_bishop_pair"] = 1
        
        # 4.6 Rook deployment
        result["S_rook_open"], result["S_rook_connected"], result["S_rook_7th"] = _calculate_rook_deployment(board, color)
        
        result["total"] = sum([result["S_mob"], result["S_outpost"], result["S_trapped"], 
                             result["S_bad_bishop"], result["S_bishop_pair"], result["S_rook_open"],
                             result["S_rook_connected"], result["S_rook_7th"], result["S_coord"]])
    
    return {"white": white_result, "black": black_result}


def _calculate_mobility(board: chess.Board, color: chess.Color) -> float:
    """Calculate normalized mobility score."""
    mobility = 0
    max_vals = {chess.KNIGHT: 8, chess.BISHOP: 13, chess.ROOK: 14, chess.QUEEN: 27}
    
    for piece_type, max_mob in max_vals.items():
        for piece_sq in board.pieces(piece_type, color):
            moves = len(list(board.attacks(piece_sq)))
            mobility += moves / max_mob
    
    return mobility


def _calculate_outposts(board: chess.Board, color: chess.Color) -> float:
    """Calculate knight outpost score."""
    score = 0
    for knight_sq in board.pieces(chess.KNIGHT, color):
        rank = chess.square_rank(knight_sq)
        if (color == chess.WHITE and rank in [4, 5]) or (color == chess.BLACK and rank in [2, 3]):
            is_protected = any(board.piece_at(sq) == chess.Piece(chess.PAWN, color) 
                             for sq in board.attackers(color, knight_sq))
            if is_protected:
                score += 0.3
    return score


def _count_trapped_pieces(board: chess.Board, color: chess.Color) -> float:
    """Count trapped pieces."""
    count = 0
    for piece_type in [chess.KNIGHT, chess.BISHOP, chess.ROOK]:
        for piece_sq in board.pieces(piece_type, color):
            safe_moves = sum(1 for sq in board.attacks(piece_sq) 
                           if not board.is_attacked_by(not color, sq))
            if safe_moves <= 1:
                count += 1
    return -count


def _count_bad_bishops(board: chess.Board, color: chess.Color) -> float:
    """Count bad bishops."""
    count = 0
    for bishop_sq in board.pieces(chess.BISHOP, color):
        # Determine bishop square color: dark if (file+rank) is odd
        bishop_color = (chess.square_file(bishop_sq) + chess.square_rank(bishop_sq)) % 2
        same_color_pawns = sum(1 for pawn_sq in board.pieces(chess.PAWN, color) 
                              if (chess.square_file(pawn_sq) + chess.square_rank(pawn_sq)) % 2 == bishop_color)
        if same_color_pawns >= 4:
            count += 1
    return -count


def _calculate_rook_deployment(board: chess.Board, color: chess.Color) -> tuple:
    """Calculate rook deployment scores."""
    open_score = 0
    connected = 0
    seventh_score = 0
    
    rooks = list(board.pieces(chess.ROOK, color))
    
    for rook_sq in rooks:
        file_idx = chess.square_file(rook_sq)
        rank = chess.square_rank(rook_sq)
        
        # Open/semi-open files
        white_pawns = sum(1 for r in range(8) if board.piece_at(chess.square(file_idx, r)) == chess.Piece(chess.PAWN, chess.WHITE))
        black_pawns = sum(1 for r in range(8) if board.piece_at(chess.square(file_idx, r)) == chess.Piece(chess.PAWN, chess.BLACK))
        
        if white_pawns == 0 and black_pawns == 0:
            open_score += 0.2
        elif (color == chess.WHITE and white_pawns == 0) or (color == chess.BLACK and black_pawns == 0):
            open_score += 0.1
        
        # 7th rank
        if (color == chess.WHITE and rank == 6) or (color == chess.BLACK and rank == 1):
            seventh_score += 0.3
    
    # Connected rooks
    if len(rooks) == 2:
        r1, r2 = rooks[0], rooks[1]
        if chess.square_rank(r1) == chess.square_rank(r2) or chess.square_file(r1) == chess.square_file(r2):
            try:
                between = list(chess.SquareSet.between(r1, r2))
                if all(board.piece_at(sq) is None for sq in between):
                    connected = 0.15
            except:
                pass
    
    return open_score, connected, seventh_score


# Simplified implementations for remaining themes (5-14)

def calculate_color_complex(board: chess.Board) -> Dict:
    """Theme 5: Color Complex & Key Squares"""
    return {"white": {"total": 0}, "black": {"total": 0}}


def calculate_lanes(board: chess.Board) -> Dict:
    """Theme 6: Files, Ranks, Diagonals"""
    return {"white": {"total": 0}, "black": {"total": 0}}


def calculate_local_imbalances(board: chess.Board) -> Dict:
    """Theme 7: Local Imbalances"""
    return {"white": {"total": 0}, "black": {"total": 0}}


async def calculate_tactics(board: chess.Board, engine_queue, depth: int) -> Dict:
    """Theme 8: Tactics Motifs"""
    return {"white": {"total": 0}, "black": {"total": 0}}


def calculate_development(board: chess.Board) -> Dict:
    """Theme 9: Development & Tempo"""
    white_dev = sum(1 for sq in board.pieces(chess.KNIGHT, chess.WHITE) if chess.square_rank(sq) > 0)
    white_dev += sum(1 for sq in board.pieces(chess.BISHOP, chess.WHITE) if chess.square_rank(sq) > 0)
    black_dev = sum(1 for sq in board.pieces(chess.KNIGHT, chess.BLACK) if chess.square_rank(sq) < 7)
    black_dev += sum(1 for sq in board.pieces(chess.BISHOP, chess.BLACK) if chess.square_rank(sq) < 7)
    
    return {"white": {"total": white_dev}, "black": {"total": black_dev}}


def calculate_promotion(board: chess.Board) -> Dict:
    """Theme 10: Promotion & Endgame Assets"""
    return {"white": {"total": 0}, "black": {"total": 0}}


def calculate_breaks(board: chess.Board) -> Dict:
    """Theme 11: Structural Levers & Breaks"""
    return {"white": {"total": 0}, "black": {"total": 0}}


async def calculate_threats(board: chess.Board, engine_queue) -> Dict:
    """
    Theme 12: Threat Quality
    Detects all types of threats for both sides using comprehensive threat detector.
    """
    from threat_detector import detect_all_threats
    
    # Detect threats for both colors
    white_threats = detect_all_threats(board, chess.WHITE)
    black_threats = detect_all_threats(board, chess.BLACK)
    
    # Count threat categories
    def count_threat_types(threats):
        counts = {
            "material": 0,
            "tactical": 0,
            "positional": 0,
            "total": 0
        }
        
        for threat in threats:
            tag = threat.get("tag_name", "")
            if "capture" in tag or "hanging" in tag or "exchange" in tag:
                counts["material"] += 1
            elif "fork" in tag or "pin" in tag or "skewer" in tag or "check" in tag:
                counts["tactical"] += 1
            elif "king_zone" in tag or "backrank" in tag or "promotion" in tag:
                counts["positional"] += 1
            counts["total"] += 1
        
        return counts
    
    white_counts = count_threat_types(white_threats)
    black_counts = count_threat_types(black_threats)
    
    return {
        "white": {
            "total": white_counts["total"],
            "material_threats": white_counts["material"],
            "tactical_threats": white_counts["tactical"],
            "positional_threats": white_counts["positional"],
            "threats_list": white_threats[:10]  # Store top 10 threats
        },
        "black": {
            "total": black_counts["total"],
            "material_threats": black_counts["material"],
            "tactical_threats": black_counts["tactical"],
            "positional_threats": black_counts["positional"],
            "threats_list": black_threats[:10]
        }
    }


def calculate_prophylaxis(board: chess.Board) -> Dict:
    """Theme 13: Prophylaxis & Restraint"""
    return {"white": {"total": 0}, "black": {"total": 0}}


async def calculate_trades(board: chess.Board, engine_queue) -> Dict:
    """Theme 14: Exchange & Trade Thematics"""
    return {"white": {"total": 0}, "black": {"total": 0}}

