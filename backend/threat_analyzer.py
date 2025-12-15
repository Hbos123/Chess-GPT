"""
Engine-based threat detection and move categorization.

Detects threats by analyzing what the opponent would play if the current player's turn was skipped.
Categorizes moves (threats and actual moves) into 22 threat types.
"""

import chess
from typing import Dict, List, Optional, Tuple


async def detect_engine_threats(
    fen: str,
    engine_queue,
    depth: int = 18
) -> Dict:
    """
    Detect threats using null-move analysis:
    1. Skip current player's turn (null move)
    2. Analyze opponent's best move
    3. If second best has CP loss > 50, it's a threat
    4. Categorize the threat by move characteristics
    
    NOTE: Null-move analysis can crash some engine versions.
    This function is currently DISABLED to prevent engine crashes.
    
    Args:
        fen: FEN string of the position
        engine_queue: Stockfish engine queue
        depth: Analysis depth
        
    Returns:
        {
            "threats": [threat_dict, ...],
            "threats_by_side": {
                "white": [threat_dict, ...],
                "black": [threat_dict, ...]
            }
        }
    """
    # DISABLED: Null-move analysis crashes Stockfish with exit code -11 (SIGSEGV)
    # The null-move technique involves creating an illegal board state that some
    # engine versions don't handle well. Until this is fixed with a separate engine
    # instance or alternative method, return empty threats.
    return {
        "threats": [],
        "threats_by_side": {"white": [], "black": []}
    }
    
    # --- Original implementation below (disabled) ---
    board = chess.Board(fen)
    current_side = board.turn
    
    # Skip turn (null move)
    board.push(chess.Move.null())
    
    try:
        # Analyze opponent's candidates (need best and second best)
        info = await engine_queue.enqueue(
            engine_queue.engine.analyse,
            board,
            chess.engine.Limit(depth=depth),
            multipv=2
        )
        
        if not info or len(info) < 1:
            return {
                "threats": [],
                "threats_by_side": {"white": [], "black": []}
            }
        
        best_move = info[0].get("pv", [])[0] if info[0].get("pv") else None
        if not best_move:
            return {
                "threats": [],
                "threats_by_side": {"white": [], "black": []}
            }
        
        # Get eval
        score = info[0]["score"].relative
        if score.is_mate():
            mate_in = score.mate()
            best_eval = 10000 if mate_in > 0 else -10000
        else:
            best_eval = score.score(mate_score=10000)
        
        # Check if second best exists and has significant gap
        is_threat = False
        gap_cp = 0
        if len(info) >= 2:
            second_score = info[1]["score"].relative
            if second_score.is_mate():
                second_mate = second_score.mate()
                second_best_eval = 10000 if second_mate > 0 else -10000
            else:
                second_best_eval = second_score.score(mate_score=10000)
            gap_cp = abs(best_eval - second_best_eval)
            is_threat = gap_cp > 50
        
        if not is_threat:
            return {
                "threats": [],
                "threats_by_side": {"white": [], "black": []}
            }
        
        # Categorize the threat
        threat_category = categorize_threat(board, best_move, best_eval)
        
        # Build threat description
        best_move_san = board.san(best_move)
        opponent_side = "white" if current_side == chess.BLACK else "black"
        
        threat = {
            "move": best_move_san,
            "move_uci": best_move.uci(),
            "side": opponent_side,
            "eval_cp": best_eval,
            "gap_cp": gap_cp,
            "category": threat_category["type"],
            "description": threat_category["description"],
            "details": threat_category["details"]
        }
        
        return {
            "threats": [threat],
            "threats_by_side": {
                opponent_side: [threat],
                "white" if opponent_side == "black" else "black": []
            }
        }
    except Exception as e:
        print(f"⚠️ Error detecting engine threats: {e}")
        import traceback
        traceback.print_exc()
        return {
            "threats": [],
            "threats_by_side": {"white": [], "black": []}
        }
    finally:
        board.pop()  # Remove null move


def categorize_threat(board: chess.Board, move: chess.Move, eval_cp: float) -> Dict:
    """
    Categorize a threat move into one of 22 threat types.
    
    Checks in priority order (most specific first):
    1. mate_threat, check, promotion_threat
    2. Material: material_gain, sacrifice
    3. Tactical: fork, pin, skewer, x_ray, deflection, overloading, removes_defender
    4. Positional: king_attack, pawn_break, prophylaxis, activity_improvement, enemy_degradation
    5. General: centralization, simplification, complication, defense, attack
    
    Args:
        board: Chess board BEFORE the move
        move: The move to categorize
        eval_cp: Evaluation after the move (from opponent's perspective)
        
    Returns:
        {
            "type": str,  # Threat category
            "description": str,  # Human-readable description
            "details": dict  # Additional details
        }
    """
    # Make the move temporarily
    board.push(move)
    
    try:
        move_type = "attack"  # Default fallback
        description = "Threatening an attacking move"
        details = {}
        
        # PRIORITY 1: Check for check/mate
        if board.is_check():
            if board.is_checkmate():
                move_type = "mate_threat"
                description = "Threatening checkmate"
                enemy_king = board.king(not board.turn)
                if enemy_king:
                    details["king_square"] = chess.square_name(enemy_king)
            else:
                move_type = "check"
                description = "Threatening check"
                enemy_king = board.king(not board.turn)
                if enemy_king:
                    details["king_square"] = chess.square_name(enemy_king)
        
        # PRIORITY 2: Check for promotion
        elif move.promotion:
            move_type = "promotion_threat"
            promotion_piece = chess.piece_name(move.promotion)
            description = f"Threatening pawn promotion to {promotion_piece}"
            details["promotion_square"] = chess.square_name(move.to_square)
            details["promotion_piece"] = promotion_piece
        
        # PRIORITY 3: Check for captures (material gain)
        elif board.is_capture(move):
            captured = board.piece_at(move.to_square)
            # Get capturing piece from before the move
            board.pop()
            capturing = board.piece_at(move.from_square)
            board.push(move)
            
            if captured and capturing:
                piece_values = {
                    chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
                    chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0
                }
                cap_val = piece_values.get(captured.piece_type, 0)
                cap_val_attacker = piece_values.get(capturing.piece_type, 0)
                
                # Check if it's a sacrifice (losing material)
                if cap_val < cap_val_attacker:
                    move_type = "sacrifice"
                    description = f"Threatening to sacrifice {capturing.symbol()} for {captured.symbol()}"
                    details["sacrificed"] = capturing.symbol()
                    details["gained"] = captured.symbol()
                elif cap_val > cap_val_attacker:
                    move_type = "material_gain"
                    description = f"Threatening to win {captured.symbol()} with {capturing.symbol()}"
                    details["captured"] = captured.symbol()
                    details["capturing"] = capturing.symbol()
                else:
                    move_type = "attack"
                    description = f"Threatening to capture {captured.symbol()}"
                    details["target"] = captured.symbol()
        
        # PRIORITY 4: Check for tactical patterns
        elif is_fork(board, move):
            move_type = "fork"
            description = "Threatening a fork"
            details.update(_get_fork_details(board, move))
        elif is_pin(board, move):
            move_type = "pin"
            description = "Threatening to pin a piece"
            details.update(_get_pin_details(board, move))
        elif is_skewer(board, move):
            move_type = "skewer"
            description = "Threatening a skewer"
            details.update(_get_skewer_details(board, move))
        elif is_xray(board, move):
            move_type = "x_ray"
            description = "Threatening an x-ray attack"
            details.update(_get_xray_details(board, move))
        elif is_deflection(board, move):
            move_type = "deflection"
            description = "Threatening to deflect a defender"
            details.update(_get_deflection_details(board, move))
        elif is_overloading(board, move):
            move_type = "overloading"
            description = "Threatening to overload a defender"
            details.update(_get_overloading_details(board, move))
        elif removes_defender(board, move):
            move_type = "removes_defender"
            description = "Threatening to remove a key defender"
            details.update(_get_removes_defender_details(board, move))
        
        # PRIORITY 5: Check for positional threats
        elif is_king_attack(board, move):
            move_type = "king_attack"
            description = "Threatening king attack"
            details.update(_get_king_attack_details(board, move))
        elif is_pawn_break(board, move):
            move_type = "pawn_break"
            description = "Threatening a pawn break"
            details.update(_get_pawn_break_details(board, move))
        elif is_prophylaxis(board, move):
            move_type = "prophylaxis"
            description = "Threatening to prevent opponent's plan"
            details.update(_get_prophylaxis_details(board, move))
        elif improves_activity(board, move):
            move_type = "activity_improvement"
            description = "Threatening to improve piece activity"
            details.update(_get_activity_improvement_details(board, move))
        elif degrades_enemy(board, move):
            move_type = "enemy_degradation"
            description = "Threatening to worsen enemy position"
            details.update(_get_enemy_degradation_details(board, move))
        
        # PRIORITY 6: General positional
        elif is_centralization(move):
            move_type = "centralization"
            description = "Threatening to centralize pieces"
            details["target_square"] = chess.square_name(move.to_square)
        elif is_simplification(board, move):
            move_type = "simplification"
            description = "Threatening to simplify the position"
            details.update(_get_simplification_details(board, move))
        elif is_complication(board, move):
            move_type = "complication"
            description = "Threatening to complicate the position"
            details.update(_get_complication_details(board, move))
        elif is_defense(board, move):
            move_type = "defense"
            description = "Threatening a defensive move"
            details.update(_get_defense_details(board, move))
        
        return {
            "type": move_type,
            "description": description,
            "details": details
        }
    finally:
        board.pop()


# ============================================================================
# HELPER FUNCTIONS FOR CATEGORIZATION
# ============================================================================

def is_fork(board: chess.Board, move: chess.Move) -> bool:
    """Check if move creates a fork (attacks multiple pieces)."""
    piece = board.piece_at(move.to_square)
    if not piece or piece.piece_type == chess.PAWN:
        return False
    
    attacks = board.attacks(move.to_square)
    enemy_pieces_attacked = []
    
    for sq in attacks:
        target = board.piece_at(sq)
        if target and target.color != piece.color:
            enemy_pieces_attacked.append(sq)
    
    return len(enemy_pieces_attacked) >= 2


def _get_fork_details(board: chess.Board, move: chess.Move) -> Dict:
    """Get details about a fork."""
    piece = board.piece_at(move.to_square)
    attacks = board.attacks(move.to_square)
    forked_pieces = []
    
    for sq in attacks:
        target = board.piece_at(sq)
        if target and target.color != piece.color:
            forked_pieces.append({
                "square": chess.square_name(sq),
                "piece": target.symbol()
            })
    
    return {
        "forking_piece": piece.symbol() if piece else "?",
        "forked_pieces": forked_pieces[:3]  # Limit to 3
    }


def is_pin(board: chess.Board, move: chess.Move) -> bool:
    """Check if move creates a pin."""
    piece = board.piece_at(move.to_square)
    if not piece or piece.piece_type not in [chess.BISHOP, chess.ROOK, chess.QUEEN]:
        return False
    
    enemy_color = not piece.color
    enemy_king = board.king(enemy_color)
    if not enemy_king:
        return False
    
    # Check if piece is on same line as enemy king
    from_file, from_rank = chess.square_file(move.from_square), chess.square_rank(move.from_square)
    to_file, to_rank = chess.square_file(move.to_square), chess.square_rank(move.to_square)
    king_file, king_rank = chess.square_file(enemy_king), chess.square_rank(enemy_king)
    
    # Check if aligned (same file, rank, or diagonal)
    is_aligned = (
        (from_file == to_file == king_file) or  # Same file
        (from_rank == to_rank == king_rank) or  # Same rank
        (abs(from_file - to_file) == abs(from_rank - to_rank) == abs(to_file - king_file) == abs(to_rank - king_rank))  # Same diagonal
    )
    
    if not is_aligned:
        return False
    
    # Check if there's an enemy piece between piece and king
    direction_file = 1 if king_file > to_file else -1 if king_file < to_file else 0
    direction_rank = 1 if king_rank > to_rank else -1 if king_rank < to_rank else 0
    
    current_file, current_rank = to_file + direction_file, to_rank + direction_rank
    while (current_file != king_file or current_rank != king_rank):
        sq = chess.square(current_file, current_rank)
        between_piece = board.piece_at(sq)
        if between_piece:
            if between_piece.color == enemy_color:
                return True  # Found pinned piece
            break
        current_file += direction_file
        current_rank += direction_rank
    
    return False


def _get_pin_details(board: chess.Board, move: chess.Move) -> Dict:
    """Get details about a pin."""
    piece = board.piece_at(move.to_square)
    enemy_color = not piece.color
    enemy_king = board.king(enemy_color)
    
    # Find pinned piece
    to_file, to_rank = chess.square_file(move.to_square), chess.square_rank(move.to_square)
    king_file, king_rank = chess.square_file(enemy_king), chess.square_rank(enemy_king)
    
    direction_file = 1 if king_file > to_file else -1 if king_file < to_file else 0
    direction_rank = 1 if king_rank > to_rank else -1 if king_rank < to_rank else 0
    
    current_file, current_rank = to_file + direction_file, to_rank + direction_rank
    while (current_file != king_file or current_rank != king_rank):
        sq = chess.square(current_file, current_rank)
        between_piece = board.piece_at(sq)
        if between_piece and between_piece.color == enemy_color:
            return {
                "pinning_piece": piece.symbol() if piece else "?",
                "pinned_piece": between_piece.symbol(),
                "pinned_square": chess.square_name(sq)
            }
        current_file += direction_file
        current_rank += direction_rank
    
    return {}


def is_skewer(board: chess.Board, move: chess.Move) -> bool:
    """Check if move creates a skewer (high-value piece attacked, low-value behind)."""
    piece = board.piece_at(move.to_square)
    if not piece or piece.piece_type not in [chess.BISHOP, chess.ROOK, chess.QUEEN]:
        return False
    
    enemy_color = not piece.color
    piece_values = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
                   chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 10}
    
    attacks = board.attacks(move.to_square)
    for target_sq in attacks:
        target = board.piece_at(target_sq)
        if target and target.color == enemy_color:
            target_val = piece_values.get(target.piece_type, 0)
            
            # Check behind target
            direction_file = chess.square_file(target_sq) - chess.square_file(move.to_square)
            direction_rank = chess.square_rank(target_sq) - chess.square_rank(move.to_square)
            
            if direction_file == 0 and direction_rank == 0:
                continue
            
            # Normalize direction
            if direction_file != 0:
                direction_file = 1 if direction_file > 0 else -1
            if direction_rank != 0:
                direction_rank = 1 if direction_rank > 0 else -1
            
            behind_file = chess.square_file(target_sq) + direction_file
            behind_rank = chess.square_rank(target_sq) + direction_rank
            
            while 0 <= behind_file < 8 and 0 <= behind_rank < 8:
                behind_sq = chess.square(behind_file, behind_rank)
                behind_piece = board.piece_at(behind_sq)
                if behind_piece:
                    if behind_piece.color == enemy_color:
                        behind_val = piece_values.get(behind_piece.piece_type, 0)
                        if behind_val < target_val:
                            return True
                    break
                behind_file += direction_file
                behind_rank += direction_rank
    
    return False


def _get_skewer_details(board: chess.Board, move: chess.Move) -> Dict:
    """Get details about a skewer."""
    piece = board.piece_at(move.to_square)
    enemy_color = not piece.color
    piece_values = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
                   chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 10}
    
    attacks = board.attacks(move.to_square)
    for target_sq in attacks:
        target = board.piece_at(target_sq)
        if target and target.color == enemy_color:
            target_val = piece_values.get(target.piece_type, 0)
            
            direction_file = chess.square_file(target_sq) - chess.square_file(move.to_square)
            direction_rank = chess.square_rank(target_sq) - chess.square_rank(move.to_square)
            
            if direction_file != 0:
                direction_file = 1 if direction_file > 0 else -1
            if direction_rank != 0:
                direction_rank = 1 if direction_rank > 0 else -1
            
            behind_file = chess.square_file(target_sq) + direction_file
            behind_rank = chess.square_rank(target_sq) + direction_rank
            
            while 0 <= behind_file < 8 and 0 <= behind_rank < 8:
                behind_sq = chess.square(behind_file, behind_rank)
                behind_piece = board.piece_at(behind_sq)
                if behind_piece and behind_piece.color == enemy_color:
                    behind_val = piece_values.get(behind_piece.piece_type, 0)
                    if behind_val < target_val:
                        return {
                            "attacker": piece.symbol() if piece else "?",
                            "front_piece": target.symbol(),
                            "behind_piece": behind_piece.symbol()
                        }
                elif behind_piece:
                    break
                behind_file += direction_file
                behind_rank += direction_rank
    
    return {}


def is_xray(board: chess.Board, move: chess.Move) -> bool:
    """Check if move creates an x-ray attack through an enemy piece."""
    piece = board.piece_at(move.to_square)
    if not piece or piece.piece_type not in [chess.BISHOP, chess.ROOK, chess.QUEEN]:
        return False
    
    # Check if piece attacks through an enemy piece
    attacks = board.attacks(move.to_square)
    enemy_color = not piece.color
    
    for target_sq in attacks:
        target = board.piece_at(target_sq)
        if target and target.color == enemy_color:
            # Check if there's an enemy piece between attacker and target
            direction_file = chess.square_file(target_sq) - chess.square_file(move.to_square)
            direction_rank = chess.square_rank(target_sq) - chess.square_rank(move.to_square)
            
            if direction_file == 0 and direction_rank == 0:
                continue
            
            if direction_file != 0:
                direction_file = 1 if direction_file > 0 else -1
            if direction_rank != 0:
                direction_rank = 1 if direction_rank > 0 else -1
            
            between_file = chess.square_file(move.to_square) + direction_file
            between_rank = chess.square_rank(move.to_square) + direction_rank
            
            while (between_file != chess.square_file(target_sq) or between_rank != chess.square_rank(target_sq)):
                between_sq = chess.square(between_file, between_rank)
                between_piece = board.piece_at(between_sq)
                if between_piece:
                    if between_piece.color == enemy_color:
                        return True  # X-ray through enemy piece
                    break
                between_file += direction_file
                between_rank += direction_rank
    
    return False


def _get_xray_details(board: chess.Board, move: chess.Move) -> Dict:
    """Get details about an x-ray."""
    piece = board.piece_at(move.to_square)
    enemy_color = not piece.color
    attacks = board.attacks(move.to_square)
    
    for target_sq in attacks:
        target = board.piece_at(target_sq)
        if target and target.color == enemy_color:
            direction_file = chess.square_file(target_sq) - chess.square_file(move.to_square)
            direction_rank = chess.square_rank(target_sq) - chess.square_rank(move.to_square)
            
            if direction_file != 0:
                direction_file = 1 if direction_file > 0 else -1
            if direction_rank != 0:
                direction_rank = 1 if direction_rank > 0 else -1
            
            between_file = chess.square_file(move.to_square) + direction_file
            between_rank = chess.square_rank(move.to_square) + direction_rank
            
            while (between_file != chess.square_file(target_sq) or between_rank != chess.square_rank(target_sq)):
                between_sq = chess.square(between_file, between_rank)
                between_piece = board.piece_at(between_sq)
                if between_piece and between_piece.color == enemy_color:
                    return {
                        "attacker": piece.symbol() if piece else "?",
                        "xrayed_piece": between_piece.symbol(),
                        "target": target.symbol()
                    }
                elif between_piece:
                    break
                between_file += direction_file
                between_rank += direction_rank
    
    return {}


def is_deflection(board: chess.Board, move: chess.Move) -> bool:
    """Check if move deflects a defender from a key square/piece."""
    # Simplified: check if move attacks a piece that defends another piece
    piece = board.piece_at(move.to_square)
    if not piece:
        return False
    
    enemy_color = not piece.color
    attacks = board.attacks(move.to_square)
    
    # Check if attacked piece defends something important
    for target_sq in attacks:
        target = board.piece_at(target_sq)
        if target and target.color == enemy_color:
            # Check what this piece defends
            defended = board.attackers(enemy_color, target_sq)
            if len(defended) > 0:
                # Check if defending something valuable
                for defended_sq in defended:
                    defended_piece = board.piece_at(defended_sq)
                    if defended_piece and defended_piece.color == enemy_color:
                        piece_values = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
                                       chess.ROOK: 5, chess.QUEEN: 9}
                        target_val = piece_values.get(target.piece_type, 0)
                        defended_val = piece_values.get(defended_piece.piece_type, 0)
                        if defended_val > target_val:
                            return True
    
    return False


def _get_deflection_details(board: chess.Board, move: chess.Move) -> Dict:
    """Get details about a deflection."""
    piece = board.piece_at(move.to_square)
    enemy_color = not piece.color
    attacks = board.attacks(move.to_square)
    
    for target_sq in attacks:
        target = board.piece_at(target_sq)
        if target and target.color == enemy_color:
            defended = board.attackers(enemy_color, target_sq)
            for defended_sq in defended:
                defended_piece = board.piece_at(defended_sq)
                if defended_piece and defended_piece.color == enemy_color:
                    piece_values = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
                                   chess.ROOK: 5, chess.QUEEN: 9}
                    target_val = piece_values.get(target.piece_type, 0)
                    defended_val = piece_values.get(defended_piece.piece_type, 0)
                    if defended_val > target_val:
                        return {
                            "deflected": target.symbol(),
                            "defended_piece": defended_piece.symbol()
                        }
    
    return {}


def is_overloading(board: chess.Board, move: chess.Move) -> bool:
    """Check if move overloads a defender (forces it to defend multiple things)."""
    piece = board.piece_at(move.to_square)
    if not piece:
        return False
    
    enemy_color = not piece.color
    attacks = board.attacks(move.to_square)
    
    # Count how many things the attacked piece defends
    for target_sq in attacks:
        target = board.piece_at(target_sq)
        if target and target.color == enemy_color:
            # Count what this piece defends
            defended_count = 0
            for sq in chess.SQUARES:
                defended_piece = board.piece_at(sq)
                if defended_piece and defended_piece.color == enemy_color and sq != target_sq:
                    defenders = board.attackers(enemy_color, sq)
                    if target_sq in defenders:
                        defended_count += 1
            if defended_count >= 2:
                return True
    
    return False


def _get_overloading_details(board: chess.Board, move: chess.Move) -> Dict:
    """Get details about overloading."""
    piece = board.piece_at(move.to_square)
    enemy_color = not piece.color
    attacks = board.attacks(move.to_square)
    
    for target_sq in attacks:
        target = board.piece_at(target_sq)
        if target and target.color == enemy_color:
            defended_pieces = []
            for sq in chess.SQUARES:
                defended_piece = board.piece_at(sq)
                if defended_piece and defended_piece.color == enemy_color and sq != target_sq:
                    defenders = board.attackers(enemy_color, sq)
                    if target_sq in defenders:
                        defended_pieces.append(defended_piece.symbol())
            if len(defended_pieces) >= 2:
                return {
                    "overloaded_piece": target.symbol(),
                    "defends": defended_pieces[:3]
                }
    
    return {}


def removes_defender(board: chess.Board, move: chess.Move) -> bool:
    """Check if move removes a key defender."""
    if not board.is_capture(move):
        return False
    
    captured = board.piece_at(move.to_square)
    if not captured:
        return False
    
    enemy_color = captured.color
    
    # Check what the captured piece was defending
    defended_count = 0
    for sq in chess.SQUARES:
        defended_piece = board.piece_at(sq)
        if defended_piece and defended_piece.color == enemy_color and sq != move.to_square:
            defenders = board.attackers(enemy_color, sq)
            if move.to_square in defenders:
                defended_count += 1
                if defended_count >= 1:
                    # Check if defending something valuable
                    piece_values = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
                                   chess.ROOK: 5, chess.QUEEN: 9}
                    defended_val = piece_values.get(defended_piece.piece_type, 0)
                    captured_val = piece_values.get(captured.piece_type, 0)
                    if defended_val >= captured_val:
                        return True
    
    return False


def _get_removes_defender_details(board: chess.Board, move: chess.Move) -> Dict:
    """Get details about removing a defender."""
    captured = board.piece_at(move.to_square)
    if not captured:
        return {}
    
    enemy_color = captured.color
    defended_pieces = []
    
    for sq in chess.SQUARES:
        defended_piece = board.piece_at(sq)
        if defended_piece and defended_piece.color == enemy_color and sq != move.to_square:
            defenders = board.attackers(enemy_color, sq)
            if move.to_square in defenders:
                piece_values = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
                               chess.ROOK: 5, chess.QUEEN: 9}
                defended_val = piece_values.get(defended_piece.piece_type, 0)
                captured_val = piece_values.get(captured.piece_type, 0)
                if defended_val >= captured_val:
                    defended_pieces.append({
                        "piece": defended_piece.symbol(),
                        "square": chess.square_name(sq)
                    })
    
    if defended_pieces:
        return {
            "removed_defender": captured.symbol(),
            "defended_pieces": defended_pieces[:2]
        }
    
    return {}


def is_king_attack(board: chess.Board, move: chess.Move) -> bool:
    """Check if move attacks enemy king zone."""
    enemy_color = not board.turn
    enemy_king = board.king(enemy_color)
    if not enemy_king:
        return False
    
    king_file = chess.square_file(enemy_king)
    king_rank = chess.square_rank(enemy_king)
    
    # Check if move attacks squares near king
    attacks = board.attacks(move.to_square)
    king_zone_squares = [
        chess.square(king_file + df, king_rank + dr)
        for df in [-1, 0, 1]
        for dr in [-1, 0, 1]
        if 0 <= king_file + df < 8 and 0 <= king_rank + dr < 8
    ]
    
    return any(sq in attacks for sq in king_zone_squares)


def _get_king_attack_details(board: chess.Board, move: chess.Move) -> Dict:
    """Get details about king attack."""
    enemy_color = not board.turn
    enemy_king = board.king(enemy_color)
    if not enemy_king:
        return {}
    
    attacks = board.attacks(move.to_square)
    king_file = chess.square_file(enemy_king)
    king_rank = chess.square_rank(enemy_king)
    
    attacked_zone_squares = []
    for df in [-1, 0, 1]:
        for dr in [-1, 0, 1]:
            sq = chess.square(king_file + df, king_rank + dr)
            if 0 <= king_file + df < 8 and 0 <= king_rank + dr < 8 and sq in attacks:
                attacked_zone_squares.append(chess.square_name(sq))
    
    return {
        "king_square": chess.square_name(enemy_king),
        "attacked_squares": attacked_zone_squares[:3]
    }


def is_pawn_break(board: chess.Board, move: chess.Move) -> bool:
    """Check if move is a pawn break."""
    piece = board.piece_at(move.to_square)
    if not piece or piece.piece_type != chess.PAWN:
        return False
    
    # Check if pawn moves forward into enemy territory
    from_rank = chess.square_rank(move.from_square)
    to_rank = chess.square_rank(move.to_square)
    
    if piece.color == chess.WHITE:
        is_advance = to_rank > from_rank
    else:
        is_advance = to_rank < from_rank
    
    if not is_advance:
        return False
    
    # Check if breaks enemy pawn structure
    enemy_color = not piece.color
    enemy_pawns = list(board.pieces(chess.PAWN, enemy_color))
    
    # Check if move attacks enemy pawn or creates passed pawn
    attacks = board.attacks(move.to_square)
    for enemy_pawn_sq in enemy_pawns:
        if enemy_pawn_sq in attacks:
            return True
    
    return False


def _get_pawn_break_details(board: chess.Board, move: chess.Move) -> Dict:
    """Get details about pawn break."""
    attacks = board.attacks(move.to_square)
    enemy_color = not board.turn
    enemy_pawns = list(board.pieces(chess.PAWN, enemy_color))
    
    attacked_pawns = []
    for enemy_pawn_sq in enemy_pawns:
        if enemy_pawn_sq in attacks:
            attacked_pawns.append(chess.square_name(enemy_pawn_sq))
    
    return {
        "target_square": chess.square_name(move.to_square),
        "attacked_pawns": attacked_pawns[:2]
    }


def is_prophylaxis(board: chess.Board, move: chess.Move) -> bool:
    """Check if move is prophylactic (prevents opponent's threats)."""
    # Simplified: check if move defends against opponent's potential threats
    enemy_color = not board.turn
    
    # Check if move defends key squares/pieces
    defended = board.attackers(board.turn, move.to_square)
    if len(defended) > 0:
        # Check if defending something important
        for sq in chess.SQUARES:
            piece = board.piece_at(sq)
            if piece and piece.color == board.turn:
                defenders = board.attackers(board.turn, sq)
                if move.to_square in defenders:
                    # Check if opponent was threatening this
                    enemy_attackers = board.attackers(enemy_color, sq)
                    if len(enemy_attackers) > 0:
                        return True
    
    return False


def _get_prophylaxis_details(board: chess.Board, move: chess.Move) -> Dict:
    """Get details about prophylaxis."""
    defended_pieces = []
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece and piece.color == board.turn:
            defenders = board.attackers(board.turn, sq)
            if move.to_square in defenders:
                enemy_color = not board.turn
                enemy_attackers = board.attackers(enemy_color, sq)
                if len(enemy_attackers) > 0:
                    defended_pieces.append(piece.symbol())
    
    if defended_pieces:
        return {
            "defended_pieces": defended_pieces[:2]
        }
    
    return {}


def improves_activity(board: chess.Board, move: chess.Move) -> bool:
    """Check if move improves piece activity."""
    piece = board.piece_at(move.to_square)
    if not piece:
        return False
    
    # Check if move increases mobility
    attacks_after = len(board.attacks(move.to_square))
    
    # Compare to before (simplified - would need board state before move)
    # For now, check if piece moves to center or active square
    to_file = chess.square_file(move.to_square)
    to_rank = chess.square_rank(move.to_square)
    
    # Center squares are more active
    center_distance = abs(to_file - 3.5) + abs(to_rank - 3.5)
    is_central = center_distance < 3
    
    # High mobility indicates activity
    return attacks_after >= 5 or is_central


def _get_activity_improvement_details(board: chess.Board, move: chess.Move) -> Dict:
    """Get details about activity improvement."""
    piece = board.piece_at(move.to_square)
    attacks = board.attacks(move.to_square)
    
    return {
        "piece": piece.symbol() if piece else "?",
        "target_square": chess.square_name(move.to_square),
        "mobility": len(attacks)
    }


def degrades_enemy(board: chess.Board, move: chess.Move) -> bool:
    """Check if move worsens enemy position."""
    enemy_color = not board.turn
    
    # Check if move restricts enemy pieces
    attacks = board.attacks(move.to_square)
    restricted_pieces = []
    
    for sq in chess.SQUARES:
        enemy_piece = board.piece_at(sq)
        if enemy_piece and enemy_piece.color == enemy_color:
            # Check if move attacks or restricts this piece
            if sq in attacks:
                restricted_pieces.append(enemy_piece.symbol())
            # Check if move controls squares enemy piece wants to use
            enemy_moves = [m for m in board.legal_moves if m.from_square == sq]
            if len(enemy_moves) == 0:
                restricted_pieces.append(enemy_piece.symbol())
    
    return len(restricted_pieces) > 0


def _get_enemy_degradation_details(board: chess.Board, move: chess.Move) -> Dict:
    """Get details about enemy degradation."""
    enemy_color = not board.turn
    attacks = board.attacks(move.to_square)
    restricted_pieces = []
    
    for sq in chess.SQUARES:
        enemy_piece = board.piece_at(sq)
        if enemy_piece and enemy_piece.color == enemy_color:
            if sq in attacks:
                restricted_pieces.append({
                    "piece": enemy_piece.symbol(),
                    "square": chess.square_name(sq)
                })
    
    return {
        "restricted_pieces": restricted_pieces[:3]
    }


def is_centralization(move: chess.Move) -> bool:
    """Check if move centralizes piece."""
    to_file = chess.square_file(move.to_square)
    to_rank = chess.square_rank(move.to_square)
    
    # Center squares: d4, d5, e4, e5 and adjacent
    center_squares = {(3, 3), (3, 4), (4, 3), (4, 4),  # d4, d5, e4, e5
                     (2, 3), (2, 4), (3, 2), (3, 5),  # c4, c5, d3, d6
                     (4, 2), (4, 5), (5, 3), (5, 4)}  # e3, e6, f4, f5
    
    return (to_file, to_rank) in center_squares


def is_simplification(board: chess.Board, move: chess.Move) -> bool:
    """Check if move simplifies position (trades pieces)."""
    if not board.is_capture(move):
        return False
    
    # Check if it's a trade (both sides lose pieces)
    captured = board.piece_at(move.to_square)
    board.pop()
    capturing = board.piece_at(move.from_square)
    board.push(move)
    
    if captured and capturing:
        # Trade of similar value pieces suggests simplification
        piece_values = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
                       chess.ROOK: 5, chess.QUEEN: 9}
        cap_val = piece_values.get(captured.piece_type, 0)
        cap_val_attacker = piece_values.get(capturing.piece_type, 0)
        
        # Similar value trade
        return abs(cap_val - cap_val_attacker) <= 1
    
    return False


def _get_simplification_details(board: chess.Board, move: chess.Move) -> Dict:
    """Get details about simplification."""
    captured = board.piece_at(move.to_square)
    board.pop()
    capturing = board.piece_at(move.from_square)
    board.push(move)
    
    if captured and capturing:
        return {
            "traded": f"{capturing.symbol()} for {captured.symbol()}"
        }
    
    return {}


def is_complication(board: chess.Board, move: chess.Move) -> bool:
    """Check if move complicates position (avoids trades, creates tension)."""
    # Check if move avoids a trade or creates new threats
    if board.is_capture(move):
        return False  # Captures usually simplify
    
    # Check if move creates multiple threats
    attacks = board.attacks(move.to_square)
    enemy_color = not board.turn
    threats_created = 0
    
    for sq in attacks:
        target = board.piece_at(sq)
        if target and target.color == enemy_color:
            threats_created += 1
    
    return threats_created >= 2


def _get_complication_details(board: chess.Board, move: chess.Move) -> Dict:
    """Get details about complication."""
    attacks = board.attacks(move.to_square)
    enemy_color = not board.turn
    threats = []
    
    for sq in attacks:
        target = board.piece_at(sq)
        if target and target.color == enemy_color:
            threats.append({
                "square": chess.square_name(sq),
                "piece": target.symbol()
            })
    
    return {
        "threats_created": threats[:3]
    }


def is_defense(board: chess.Board, move: chess.Move) -> bool:
    """Check if move is defensive."""
    # Check if move defends key pieces/squares
    defended = board.attackers(board.turn, move.to_square)
    if len(defended) == 0:
        return False
    
    # Check if defending something important
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece and piece.color == board.turn:
            defenders = board.attackers(board.turn, sq)
            if move.to_square in defenders:
                enemy_color = not board.turn
                enemy_attackers = board.attackers(enemy_color, sq)
                if len(enemy_attackers) > 0:
                    return True
    
    return False


def _get_defense_details(board: chess.Board, move: chess.Move) -> Dict:
    """Get details about defense."""
    defended_pieces = []
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece and piece.color == board.turn:
            defenders = board.attackers(board.turn, sq)
            if move.to_square in defenders:
                enemy_color = not board.turn
                enemy_attackers = board.attackers(enemy_color, sq)
                if len(enemy_attackers) > 0:
                    defended_pieces.append({
                        "piece": piece.symbol(),
                        "square": chess.square_name(sq)
                    })
    
    return {
        "defended_pieces": defended_pieces[:3]
    }

