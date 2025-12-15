"""
Square Control Module - Analyzes which pieces control key squares.
"""

import chess
from typing import Dict, List, Set, Tuple

# Key square definitions
CENTER_SQUARES = ["d4", "d5", "e4", "e5"]
EXTENDED_CENTER = ["c3", "c4", "c5", "c6", "d3", "d6", "e3", "e6", "f3", "f4", "f5", "f6"]

# Square importance categories
SQUARE_IMPORTANCE = {
    "center": 1.0,
    "extended_center": 0.7,
    "outpost": 0.9,
    "kingside": 0.6,
    "queenside": 0.5,
}


def get_key_squares(board: chess.Board) -> Dict[str, List[str]]:
    """
    Get key squares for the current position.
    Dynamically computes outpost squares based on pawn structure.
    
    Returns:
        {"center": [...], "extended_center": [...], "outpost_white": [...], "outpost_black": [...]}
    """
    result = {
        "center": CENTER_SQUARES.copy(),
        "extended_center": EXTENDED_CENTER.copy(),
        "outpost_white": [],
        "outpost_black": [],
    }
    
    # Find outpost squares for each side
    # An outpost is a square that cannot be attacked by enemy pawns
    for sq in chess.SQUARES:
        file_idx = chess.square_file(sq)
        rank_idx = chess.square_rank(sq)
        sq_name = chess.square_name(sq)
        
        # White outposts (ranks 4-6)
        if 3 <= rank_idx <= 5:
            # Check if black pawns can attack this square
            can_be_attacked = False
            # Check adjacent files for black pawns that could advance
            for adj_file in [file_idx - 1, file_idx + 1]:
                if 0 <= adj_file <= 7:
                    # Check ranks above for black pawns
                    for check_rank in range(rank_idx + 1, 8):
                        check_sq = chess.square(adj_file, check_rank)
                        piece = board.piece_at(check_sq)
                        if piece and piece.piece_type == chess.PAWN and piece.color == chess.BLACK:
                            can_be_attacked = True
                            break
                if can_be_attacked:
                    break
            
            if not can_be_attacked:
                result["outpost_white"].append(sq_name)
        
        # Black outposts (ranks 3-5)
        if 2 <= rank_idx <= 4:
            can_be_attacked = False
            for adj_file in [file_idx - 1, file_idx + 1]:
                if 0 <= adj_file <= 7:
                    for check_rank in range(0, rank_idx):
                        check_sq = chess.square(adj_file, check_rank)
                        piece = board.piece_at(check_sq)
                        if piece and piece.piece_type == chess.PAWN and piece.color == chess.WHITE:
                            can_be_attacked = True
                            break
                if can_be_attacked:
                    break
            
            if not can_be_attacked:
                result["outpost_black"].append(sq_name)
    
    return result


def get_piece_attacks(board: chess.Board, square: int, piece: chess.Piece) -> Set[int]:
    """Get squares attacked by a piece at a given square."""
    # Use board.attacks() which handles all piece types correctly
    attacks_bb = board.attacks(square)
    return set(chess.SquareSet(attacks_bb))


def compute_square_control(
    board: chess.Board,
    piece_id_map: Dict[str, int] = None
) -> Dict[str, Dict]:
    """
    For each key square, identify which pieces control it.
    
    Args:
        board: Chess board
        piece_id_map: Optional mapping of piece_id → square_index
    
    Returns:
        {
            "e5": {
                "white_controllers": ["white_knight_f3", "white_pawn_d4"],
                "black_controllers": ["black_pawn_e6"],
                "net_control": "white",  # or "black", "contested", "none"
                "importance": "high",    # or "medium", "low"
                "white_attack_count": 2,
                "black_attack_count": 1
            }
        }
    """
    key_squares = get_key_squares(board)
    all_key = set()
    for sq_list in key_squares.values():
        all_key.update(sq_list)
    
    # Build piece_id_map if not provided
    if piece_id_map is None:
        piece_id_map = {}
        for sq in chess.SQUARES:
            piece = board.piece_at(sq)
            if piece:
                color = "white" if piece.color == chess.WHITE else "black"
                piece_type = chess.piece_name(piece.piece_type)
                sq_name = chess.square_name(sq)
                piece_id = f"{color}_{piece_type}_{sq_name}"
                piece_id_map[piece_id] = sq
    
    # Reverse map: square → piece_id
    square_to_piece_id = {v: k for k, v in piece_id_map.items()}
    
    result = {}
    
    for sq_name in all_key:
        sq_idx = chess.parse_square(sq_name)
        
        white_controllers = []
        black_controllers = []
        white_attacks = 0
        black_attacks = 0
        
        # Check each piece
        for piece_id, piece_sq in piece_id_map.items():
            piece = board.piece_at(piece_sq)
            if not piece:
                continue
            
            attacks = get_piece_attacks(board, piece_sq, piece)
            if sq_idx in attacks:
                if piece.color == chess.WHITE:
                    white_controllers.append(piece_id)
                    white_attacks += 1
                else:
                    black_controllers.append(piece_id)
                    black_attacks += 1
        
        # Determine net control
        if white_attacks > black_attacks:
            net_control = "white"
        elif black_attacks > white_attacks:
            net_control = "black"
        elif white_attacks == 0 and black_attacks == 0:
            net_control = "none"
        else:
            net_control = "contested"
        
        # Determine importance
        if sq_name in CENTER_SQUARES:
            importance = "high"
        elif sq_name in EXTENDED_CENTER:
            importance = "medium"
        elif sq_name in key_squares.get("outpost_white", []) or sq_name in key_squares.get("outpost_black", []):
            importance = "high"
        else:
            importance = "low"
        
        result[sq_name] = {
            "white_controllers": white_controllers,
            "black_controllers": black_controllers,
            "net_control": net_control,
            "importance": importance,
            "white_attack_count": white_attacks,
            "black_attack_count": black_attacks,
        }
    
    return result


def attribute_control_to_pieces(
    square_control: Dict[str, Dict],
    profiles: Dict[str, Dict]
) -> None:
    """
    Add controls_squares and key_squares_controlled to each piece profile.
    Modifies profiles in-place.
    
    Args:
        square_control: Output from compute_square_control
        profiles: Piece profiles dict to modify
    """
    # Initialize control lists
    for piece_id in profiles:
        if "controls_squares" not in profiles[piece_id]:
            profiles[piece_id]["controls_squares"] = []
        if "key_squares_controlled" not in profiles[piece_id]:
            profiles[piece_id]["key_squares_controlled"] = []
    
    # Attribute squares to pieces
    for sq_name, control_data in square_control.items():
        importance = control_data.get("importance", "low")
        
        for piece_id in control_data.get("white_controllers", []):
            if piece_id in profiles:
                profiles[piece_id]["controls_squares"].append(sq_name)
                if importance in ("high", "medium"):
                    profiles[piece_id]["key_squares_controlled"].append(sq_name)
        
        for piece_id in control_data.get("black_controllers", []):
            if piece_id in profiles:
                profiles[piece_id]["controls_squares"].append(sq_name)
                if importance in ("high", "medium"):
                    profiles[piece_id]["key_squares_controlled"].append(sq_name)


def get_control_summary(square_control: Dict[str, Dict]) -> Dict[str, Dict]:
    """
    Get a summary of square control for each side.
    
    Returns:
        {
            "white": {
                "center_control": 2,
                "total_key_squares": 5,
                "contested": 3
            },
            "black": {...}
        }
    """
    white_center = 0
    black_center = 0
    white_total = 0
    black_total = 0
    contested = 0
    
    for sq_name, data in square_control.items():
        net = data.get("net_control", "none")
        importance = data.get("importance", "low")
        
        if net == "white":
            white_total += 1
            if importance == "high":
                white_center += 1
        elif net == "black":
            black_total += 1
            if importance == "high":
                black_center += 1
        elif net == "contested":
            contested += 1
    
    return {
        "white": {
            "center_control": white_center,
            "total_key_squares": white_total,
            "contested": contested,
        },
        "black": {
            "center_control": black_center,
            "total_key_squares": black_total,
            "contested": contested,
        }
    }

