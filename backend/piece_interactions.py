"""
Piece Interactions Module - Detects tactical/strategic relationships between pieces.
"""

import chess
from typing import Dict, List, Set, Tuple, Optional


def detect_piece_interactions(
    board: chess.Board,
    piece_id_map: Dict[str, int] = None
) -> List[Dict]:
    """
    Detect tactical/strategic relationships between pieces.
    
    Args:
        board: Chess board
        piece_id_map: Optional mapping of piece_id → square_index
    
    Returns:
        List of interaction dicts:
        [
            {"type": "battery", "pieces": [...], "axis": "d-file", "target": "d7"},
            {"type": "coordination", "pieces": [...], "target_squares": ["e5"]},
            {"type": "defending", "defender": "...", "protects": [...]},
        ]
    """
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
    
    interactions = []
    
    # Detect batteries
    interactions.extend(_detect_batteries(board, piece_id_map))
    
    # Detect coordination (pieces targeting same squares)
    interactions.extend(_detect_coordination(board, piece_id_map))
    
    # Detect defense relationships
    interactions.extend(_detect_defense_chains(board, piece_id_map))
    
    return interactions


def _detect_batteries(board: chess.Board, piece_id_map: Dict[str, int]) -> List[Dict]:
    """Detect battery formations (rook+queen on file, bishop+queen on diagonal)."""
    batteries = []
    
    # Group pieces by color
    white_pieces = {pid: sq for pid, sq in piece_id_map.items() if pid.startswith("white_")}
    black_pieces = {pid: sq for pid, sq in piece_id_map.items() if pid.startswith("black_")}
    
    for color_pieces, color in [(white_pieces, "white"), (black_pieces, "black")]:
        # Find rooks and queens
        rooks = [(pid, sq) for pid, sq in color_pieces.items() if "rook" in pid]
        queens = [(pid, sq) for pid, sq in color_pieces.items() if "queen" in pid]
        bishops = [(pid, sq) for pid, sq in color_pieces.items() if "bishop" in pid]
        
        # Rook-Queen batteries (same file or rank)
        for r_pid, r_sq in rooks:
            r_file = chess.square_file(r_sq)
            r_rank = chess.square_rank(r_sq)
            
            for q_pid, q_sq in queens:
                q_file = chess.square_file(q_sq)
                q_rank = chess.square_rank(q_sq)
                
                if r_file == q_file:
                    # File battery
                    file_name = chess.FILE_NAMES[r_file]
                    batteries.append({
                        "type": "battery",
                        "pieces": [r_pid, q_pid],
                        "axis": f"{file_name}-file",
                        "color": color,
                    })
                elif r_rank == q_rank:
                    # Rank battery
                    batteries.append({
                        "type": "battery",
                        "pieces": [r_pid, q_pid],
                        "axis": f"rank-{r_rank + 1}",
                        "color": color,
                    })
            
            # Rook-Rook connection
            for r2_pid, r2_sq in rooks:
                if r_pid >= r2_pid:  # Avoid duplicates
                    continue
                
                r2_file = chess.square_file(r2_sq)
                r2_rank = chess.square_rank(r2_sq)
                
                if r_file == r2_file or r_rank == r2_rank:
                    # Check if connected (no pieces between)
                    if _pieces_connected(board, r_sq, r2_sq):
                        batteries.append({
                            "type": "connected_rooks",
                            "pieces": [r_pid, r2_pid],
                            "axis": f"{chess.FILE_NAMES[r_file]}-file" if r_file == r2_file else f"rank-{r_rank + 1}",
                            "color": color,
                        })
        
        # Bishop-Queen batteries (same diagonal)
        for b_pid, b_sq in bishops:
            for q_pid, q_sq in queens:
                if _on_same_diagonal(b_sq, q_sq):
                    batteries.append({
                        "type": "battery",
                        "pieces": [b_pid, q_pid],
                        "axis": "diagonal",
                        "color": color,
                    })
    
    return batteries


def _detect_coordination(board: chess.Board, piece_id_map: Dict[str, int]) -> List[Dict]:
    """Detect pieces coordinating on the same target squares."""
    coordination = []
    
    # Group by color
    for color in [chess.WHITE, chess.BLACK]:
        color_name = "white" if color == chess.WHITE else "black"
        color_pieces = {pid: sq for pid, sq in piece_id_map.items() 
                       if pid.startswith(color_name)}
        
        # Compute attack maps for each piece
        attack_maps = {}
        for pid, sq in color_pieces.items():
            piece = board.piece_at(sq)
            if piece:
                attacks = set(board.attacks(sq))
                attack_maps[pid] = attacks
        
        # Find shared attack squares
        pieces_list = list(attack_maps.keys())
        for i, pid1 in enumerate(pieces_list):
            for pid2 in pieces_list[i+1:]:
                shared = attack_maps[pid1] & attack_maps[pid2]
                if shared:
                    # Filter to important squares
                    important_shared = [chess.square_name(sq) for sq in shared]
                    if len(important_shared) >= 1:
                        coordination.append({
                            "type": "coordination",
                            "pieces": [pid1, pid2],
                            "target_squares": important_shared[:5],  # Limit to 5
                            "shared_count": len(shared),
                            "color": color_name,
                        })
    
    return coordination


def _detect_defense_chains(board: chess.Board, piece_id_map: Dict[str, int]) -> List[Dict]:
    """Detect which pieces defend which."""
    defenses = []
    
    for color in [chess.WHITE, chess.BLACK]:
        color_name = "white" if color == chess.WHITE else "black"
        color_pieces = {pid: sq for pid, sq in piece_id_map.items() 
                       if pid.startswith(color_name)}
        
        for defender_pid, defender_sq in color_pieces.items():
            piece = board.piece_at(defender_sq)
            if not piece:
                continue
            
            attacks = set(board.attacks(defender_sq))
            protects = []
            
            for target_pid, target_sq in color_pieces.items():
                if defender_pid == target_pid:
                    continue
                if target_sq in attacks:
                    protects.append(target_pid)
            
            if protects:
                defenses.append({
                    "type": "defending",
                    "defender": defender_pid,
                    "protects": protects,
                    "color": color_name,
                })
    
    return defenses


def _pieces_connected(board: chess.Board, sq1: int, sq2: int) -> bool:
    """Check if two pieces on the same file/rank have no pieces between them."""
    file1, rank1 = chess.square_file(sq1), chess.square_rank(sq1)
    file2, rank2 = chess.square_file(sq2), chess.square_rank(sq2)
    
    if file1 == file2:
        # Same file - check ranks between
        min_rank, max_rank = min(rank1, rank2), max(rank1, rank2)
        for r in range(min_rank + 1, max_rank):
            if board.piece_at(chess.square(file1, r)):
                return False
        return True
    elif rank1 == rank2:
        # Same rank - check files between
        min_file, max_file = min(file1, file2), max(file1, file2)
        for f in range(min_file + 1, max_file):
            if board.piece_at(chess.square(f, rank1)):
                return False
        return True
    return False


def _on_same_diagonal(sq1: int, sq2: int) -> bool:
    """Check if two squares are on the same diagonal."""
    file1, rank1 = chess.square_file(sq1), chess.square_rank(sq1)
    file2, rank2 = chess.square_file(sq2), chess.square_rank(sq2)
    return abs(file1 - file2) == abs(rank1 - rank2)


def compute_coordination_score(board: chess.Board, color: chess.Color) -> float:
    """
    Compute 0-1 score of how well pieces work together.
    Based on mutual defense, shared targets, lack of interference.
    
    Args:
        board: Chess board
        color: Color to compute for
    
    Returns:
        Float 0-1 where 1 = excellent coordination
    """
    color_name = "white" if color == chess.WHITE else "black"
    
    # Build piece map
    piece_id_map = {}
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece and piece.color == color:
            piece_type = chess.piece_name(piece.piece_type)
            sq_name = chess.square_name(sq)
            piece_id = f"{color_name}_{piece_type}_{sq_name}"
            piece_id_map[piece_id] = sq
    
    if len(piece_id_map) <= 1:
        return 0.5  # Not enough pieces to coordinate
    
    # Count defending relationships
    defense_count = 0
    for pid, sq in piece_id_map.items():
        piece = board.piece_at(sq)
        if not piece:
            continue
        attacks = board.attacks(sq)
        for other_pid, other_sq in piece_id_map.items():
            if pid != other_pid and other_sq in attacks:
                defense_count += 1
    
    # Count shared attack squares
    attack_maps = {}
    for pid, sq in piece_id_map.items():
        attack_maps[pid] = set(board.attacks(sq))
    
    shared_attacks = 0
    pieces_list = list(attack_maps.keys())
    for i, pid1 in enumerate(pieces_list):
        for pid2 in pieces_list[i+1:]:
            shared = len(attack_maps[pid1] & attack_maps[pid2])
            if shared > 0:
                shared_attacks += 1
    
    # Normalize scores
    max_defenses = len(piece_id_map) * (len(piece_id_map) - 1)
    max_shared = len(piece_id_map) * (len(piece_id_map) - 1) / 2
    
    defense_score = min(1.0, defense_count / max(1, max_defenses / 2))
    shared_score = min(1.0, shared_attacks / max(1, max_shared / 2))
    
    # Combined score (weighted)
    return 0.6 * defense_score + 0.4 * shared_score


def add_interactions_to_profiles(
    interactions: List[Dict],
    profiles: Dict[str, Dict]
) -> None:
    """
    Add interaction data to piece profiles.
    Modifies profiles in-place.
    """
    for piece_id in profiles:
        if "coordinates_with" not in profiles[piece_id]:
            profiles[piece_id]["coordinates_with"] = []
        if "defends" not in profiles[piece_id]:
            profiles[piece_id]["defends"] = []
        if "attacks" not in profiles[piece_id]:
            profiles[piece_id]["attacks"] = []
    
    for interaction in interactions:
        int_type = interaction.get("type")
        
        if int_type in ("battery", "connected_rooks", "coordination"):
            pieces = interaction.get("pieces", [])
            for pid in pieces:
                if pid in profiles:
                    for other_pid in pieces:
                        if other_pid != pid and other_pid not in profiles[pid]["coordinates_with"]:
                            profiles[pid]["coordinates_with"].append(other_pid)
        
        elif int_type == "defending":
            defender = interaction.get("defender")
            protects = interaction.get("protects", [])
            if defender in profiles:
                for protected in protects:
                    if protected not in profiles[defender]["defends"]:
                        profiles[defender]["defends"].append(protected)

