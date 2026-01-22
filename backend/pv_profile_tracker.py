"""
PV Profile Tracker - Tracks how piece profiles change across the principal variation.
"""

import chess
from typing import Dict, List, Optional, Any, Tuple


def track_pv_profiles(
    pv_fens: List[str],
    profiles_by_fen: Dict[str, Dict[str, Dict]]
) -> Dict[str, Dict]:
    """
    Track how each piece's profile changes across the PV.
    Handles piece movement, captures, and promotions.
    
    Args:
        pv_fens: List of FEN strings for each position in PV
        profiles_by_fen: Dict of fen → {piece_id → profile}
    
    Returns:
        {
            "white_knight_g1": {
                "trajectory": [
                    {"fen_idx": 0, "square": "g1", "contribution": -20, 
                     "role": "undeveloped", "top_tag": "undeveloped"},
                    {"fen_idx": 2, "square": "f3", "contribution": -45,
                     "role": "dominant", "top_tag": "outpost"},
                ],
                "contribution_delta": -25,
                "role_change": "undeveloped → dominant",
                "fate": "active"  # or "captured", "promoted"
            }
        }
    """
    if not pv_fens or not profiles_by_fen:
        return {}
    
    # Get starting profiles (first FEN)
    start_fen = pv_fens[0]
    start_profiles = profiles_by_fen.get(start_fen, {})
    
    # Get final profiles
    end_fen = pv_fens[-1]
    end_profiles = profiles_by_fen.get(end_fen, {})
    
    # Build piece type counts for matching
    def get_piece_key(piece_id: str) -> str:
        """Get color_type key from piece_id."""
        parts = piece_id.split("_")
        if len(parts) >= 2:
            return f"{parts[0]}_{parts[1]}"
        return piece_id
    
    # Track each piece from the starting position
    trajectories = {}
    
    for piece_id, start_profile in start_profiles.items():
        color = start_profile.get("color", "")
        piece_type = start_profile.get("piece_type", "")
        start_square = start_profile.get("square", "")
        
        trajectory = [{
            "fen_idx": 0,
            "square": start_square,
            "contribution": start_profile.get("total_contribution_cp", 0),
            "role": start_profile.get("role", "active"),
            "top_tag": _get_top_tag(start_profile),
        }]
        
        # Try to find this piece in the final position
        # First try same piece_id (didn't move)
        end_profile = None
        end_square = start_square
        fate = "active"
        
        if piece_id in end_profiles:
            end_profile = end_profiles[piece_id]
            end_square = end_profile.get("square", start_square)
        else:
            # Piece moved - find by matching color + type at a different square
            # Use board replay to track the actual piece
            found_end = _find_piece_in_final(
                start_square, color, piece_type, pv_fens[0], pv_fens[-1]
            )
            if found_end:
                end_piece_id = f"{color}_{piece_type}_{found_end}"
                if end_piece_id in end_profiles:
                    end_profile = end_profiles[end_piece_id]
                    end_square = found_end
                else:
                    fate = "captured"
            else:
                fate = "captured"
        
        if end_profile:
            trajectory.append({
                "fen_idx": len(pv_fens) - 1,
                "square": end_square,
                "contribution": end_profile.get("total_contribution_cp", 0),
                "role": end_profile.get("role", "active"),
                "top_tag": _get_top_tag(end_profile),
            })
        
        trajectories[piece_id] = {
            "trajectory": trajectory,
            "contribution_delta": 0,
            "role_change": None,
            "fate": fate,
            "start_square": start_square,
            "end_square": end_square,
        }
    
    # Compute deltas and role changes
    for piece_id, data in trajectories.items():
        trajectory = data["trajectory"]
        if len(trajectory) >= 2:
            start = trajectory[0]
            end = trajectory[-1]
            
            data["contribution_delta"] = end["contribution"] - start["contribution"]
            
            if start["role"] != end["role"]:
                data["role_change"] = f"{start['role']} → {end['role']}"
    
    return trajectories


def _find_piece_in_final(
    start_square: str,
    color: str,
    piece_type: str,
    start_fen: str,
    end_fen: str
) -> Optional[str]:
    """
    Track where a piece ends up by comparing start and end positions.
    Returns the final square or None if piece was captured.
    """
    import chess
    
    start_board = chess.Board(start_fen)
    end_board = chess.Board(end_fen)
    
    try:
        start_sq = chess.parse_square(start_square)
    except:
        return None
    
    # Get the piece at start square
    start_piece = start_board.piece_at(start_sq)
    if not start_piece:
        return None
    
    # Map piece type string to chess constant
    type_map = {
        "pawn": chess.PAWN,
        "knight": chess.KNIGHT,
        "bishop": chess.BISHOP,
        "rook": chess.ROOK,
        "queen": chess.QUEEN,
        "king": chess.KING,
    }
    expected_type = type_map.get(piece_type)
    expected_color = chess.WHITE if color == "white" else chess.BLACK
    
    if not expected_type:
        return None
    
    # Count pieces of this type in start position
    start_pieces = []
    for sq in chess.SQUARES:
        p = start_board.piece_at(sq)
        if p and p.piece_type == expected_type and p.color == expected_color:
            start_pieces.append(sq)
    
    # Count pieces of this type in end position
    end_pieces = []
    for sq in chess.SQUARES:
        p = end_board.piece_at(sq)
        if p and p.piece_type == expected_type and p.color == expected_color:
            end_pieces.append(sq)
    
    # If fewer pieces in end, some were captured
    if len(end_pieces) < len(start_pieces):
        # Check if our specific piece survived
        # Heuristic: if piece was on starting square and one exists on a different square
        if start_sq not in end_pieces and len(end_pieces) > 0:
            # Piece moved - find which square has a piece not in start position
            for end_sq in end_pieces:
                if end_sq not in start_pieces:
                    return chess.square_name(end_sq)
        return None  # Piece was captured
    
    # Same or more pieces - find where our piece went
    if start_sq in end_pieces:
        return start_square  # Didn't move
    
    # Piece moved - find the new square
    for end_sq in end_pieces:
        if end_sq not in start_pieces:
            return chess.square_name(end_sq)
    
    return None


def track_piece_across_moves(
    start_fen: str,
    moves: List[chess.Move],
    piece_id: str
) -> List[Dict]:
    """
    Follow a specific piece through a sequence of moves.
    Track square changes, captures, and final fate.
    
    Args:
        start_fen: Starting FEN
        moves: List of moves in the PV
        piece_id: Piece ID to track (e.g., "white_knight_g1")
    
    Returns:
        List of positions for this piece
    """
    board = chess.Board(start_fen)
    
    # Parse piece_id to find starting square
    parts = piece_id.split("_")
    if len(parts) < 3:
        return []
    
    color_str = parts[0]
    piece_type_str = parts[1]
    start_square = parts[2]
    
    color = chess.WHITE if color_str == "white" else chess.BLACK
    
    # Map piece type string to chess constant
    type_map = {
        "pawn": chess.PAWN,
        "knight": chess.KNIGHT,
        "bishop": chess.BISHOP,
        "rook": chess.ROOK,
        "queen": chess.QUEEN,
        "king": chess.KING,
    }
    piece_type = type_map.get(piece_type_str, chess.PAWN)
    
    try:
        current_square = chess.parse_square(start_square)
    except:
        return []
    
    trajectory = [{
        "move_idx": 0,
        "square": start_square,
        "fen": start_fen,
    }]
    
    for move_idx, move in enumerate(moves, start=1):
        # Check if this move involves our piece
        if move.from_square == current_square:
            current_square = move.to_square
            board.push(move)
            trajectory.append({
                "move_idx": move_idx,
                "square": chess.square_name(current_square),
                "fen": board.fen(),
                "moved": True,
            })
        elif move.to_square == current_square:
            # Piece was captured
            board.push(move)
            trajectory.append({
                "move_idx": move_idx,
                "square": None,
                "fen": board.fen(),
                "captured": True,
            })
            break
        else:
            # Piece didn't move
            board.push(move)
    
    return trajectory


def detect_captures_in_pv(
    start_fen: str,
    moves: List[chess.Move]
) -> List[Dict]:
    """
    Identify which pieces were captured in the PV and by whom.
    
    Args:
        start_fen: Starting FEN
        moves: List of moves in PV
    
    Returns:
        [
            {"fen_idx": 3, "captured": "black_knight_c6", 
             "captured_by": "white_bishop_g2", "exchange_value": 0}
        ]
    """
    board = chess.Board(start_fen)
    captures = []
    
    for fen_idx, move in enumerate(moves, start=1):
        if board.is_capture(move):
            # Get the capturing piece
            from_sq = move.from_square
            from_piece = board.piece_at(from_sq)
            
            # Get the captured piece
            to_sq = move.to_square
            to_piece = board.piece_at(to_sq)
            
            # Handle en passant
            if to_piece is None and from_piece and from_piece.piece_type == chess.PAWN:
                # En passant capture
                ep_sq = to_sq + (-8 if from_piece.color == chess.WHITE else 8)
                to_piece = board.piece_at(ep_sq)
                to_sq = ep_sq
            
            if from_piece and to_piece:
                capturer_color = "white" if from_piece.color == chess.WHITE else "black"
                capturer_type = chess.piece_name(from_piece.piece_type)
                capturer_sq = chess.square_name(from_sq)
                capturer_id = f"{capturer_color}_{capturer_type}_{capturer_sq}"
                
                captured_color = "white" if to_piece.color == chess.WHITE else "black"
                captured_type = chess.piece_name(to_piece.piece_type)
                captured_sq = chess.square_name(to_sq)
                captured_id = f"{captured_color}_{captured_type}_{captured_sq}"
                
                # Calculate exchange value
                piece_values = {
                    chess.PAWN: 100,
                    chess.KNIGHT: 320,
                    chess.BISHOP: 330,
                    chess.ROOK: 500,
                    chess.QUEEN: 900,
                    chess.KING: 0,
                }
                
                captures.append({
                    "fen_idx": fen_idx,
                    "captured": captured_id,
                    "captured_by": capturer_id,
                    "exchange_value": piece_values.get(to_piece.piece_type, 0),
                })
        
        board.push(move)
    
    return captures


def compute_pv_fens(start_fen: str, moves: List[chess.Move]) -> List[str]:
    """
    Compute FEN for each position in the PV.
    
    Args:
        start_fen: Starting FEN
        moves: List of moves
    
    Returns:
        List of FENs (including start)
    """
    board = chess.Board(start_fen)
    fens = [start_fen]
    
    for move in moves:
        board.push(move)
        fens.append(board.fen())
    
    return fens


def _get_top_tag(profile: Dict) -> Optional[str]:
    """Get the most significant tag from a profile, with meaningful simplification."""
    tags = profile.get("tags", [])
    
    # First, try to find a meaningful tag (skip generic/problematic tags)
    sorted_tags = sorted(tags, key=lambda t: abs(t.get("phase_adjusted", 0)), reverse=True)
    
    for tag_data in sorted_tags:
        tag = tag_data.get("tag", "")
        parts = tag.split(".")
        
        if len(parts) < 2:
            continue
        
        category = parts[1] if len(parts) > 1 else ""
        descriptor = parts[2] if len(parts) > 2 else ""
        
        # Skip generic mobility tags that would give piece type names
        if category == "activity" and descriptor == "mobility":
            continue
        
        # Skip threat tags for trajectory top_tag - they're transient
        if category == "threat":
            continue
        
        # Format meaningful tags
        if category in ("file", "diagonal"):
            # "tag.file.open.d" → "open file"
            return f"{descriptor} {category}" if descriptor else category
        
        elif category == "rook":
            # "tag.rook.open_file" → "open file"
            rook_descriptors = {
                "open_file": "open file",
                "semi_open": "semi-open file",
                "rank7": "7th rank",
                "connected": "connected",
            }
            return rook_descriptors.get(descriptor, descriptor)
        
        elif category == "pawn":
            # "tag.pawn.passed.e5" → "passed"
            pawn_descriptors = {
                "passed": "passed",
                "isolated": "isolated",
                "doubled": "doubled",
                "backward": "backward",
            }
            return pawn_descriptors.get(descriptor, descriptor)
        
        elif category == "status":
            # Status tags are important for trajectories
            status_descriptors = {
                "attacked": "en prise",
                "hanging": "hanging",
                "pinned": "pinned",
                "skewered": "skewered",
                "forked": "forked",
            }
            return status_descriptors.get(descriptor, descriptor)
        
        elif category == "square" and descriptor == "outpost":
            return "outpost"
        
        elif category == "battery":
            return "battery"
        
        elif category in ("bishop", "knight", "king"):
            # "tag.bishop.pair" → "pair", "tag.bishop.bad" → "bad"
            return descriptor if descriptor else category
        
        elif category == "center":
            return "central"
        
        else:
            return descriptor if descriptor and len(descriptor) > 2 else category
    
    # Fall back to role
    role = profile.get("role", "")
    return role if role else None

