"""
Piece Profiler - Builds comprehensive profiles for each piece.
Combines NNUE attribution, tags, classical terms, and strategic roles.
"""

import chess
from typing import Dict, List, Tuple, Optional, Any

from piece_tag_mappings import (
    TAG_PIECE_RELEVANCE, 
    TAG_PHASE_MULTIPLIERS,
    CLASSICAL_TO_TAG_CATEGORY,
    PIECE_ROLES,
    ROLE_THRESHOLDS,
    get_tag_weight_for_piece,
    is_piece_on_starting_square,
)
from nnue_bridge import get_nnue_dump, compute_piece_contributions, parse_piece_id
from square_control import compute_square_control, attribute_control_to_pieces
from piece_interactions import detect_piece_interactions, add_interactions_to_profiles, compute_coordination_score


def build_piece_profiles(
    fen: str,
    nnue_dump: Optional[Dict] = None,
    tags: Optional[List[Dict]] = None,
    themes: Optional[Dict] = None,
    phase: str = "middlegame"
) -> Dict[str, Dict]:
    """
    Build comprehensive profile for each piece.
    
    Args:
        fen: FEN string
        nnue_dump: Pre-computed NNUE dump (or None to fetch)
        tags: Position tags from tag_detector
        themes: Theme data from fen_analyzer
        phase: Game phase ("opening", "middlegame", "endgame")
    
    Returns:
        Dict of piece_id → profile
    """
    board = chess.Board(fen)
    
    # Get NNUE dump if not provided
    if nnue_dump is None:
        nnue_dump = get_nnue_dump(fen)
    
    # Compute piece contributions from NNUE
    contributions = {}
    if nnue_dump:
        contributions = compute_piece_contributions(nnue_dump)
    
    # Build piece_id_map
    piece_id_map = {}
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece:
            color = "white" if piece.color == chess.WHITE else "black"
            piece_type = chess.piece_name(piece.piece_type)
            sq_name = chess.square_name(sq)
            piece_id = f"{color}_{piece_type}_{sq_name}"
            piece_id_map[piece_id] = sq
    
    # Initialize profiles
    profiles = {}
    for piece_id, sq_idx in piece_id_map.items():
        parsed = parse_piece_id(piece_id)
        piece = board.piece_at(sq_idx)
        
        contrib = contributions.get(piece_id, {
            "nnue_contribution_cp": 0,
            "classical_contribution_cp": 0,
            "total_contribution_cp": 0,
        })
        
        # Score the piece's NNUE contribution
        from significance_scorer import SignificanceScorer
        nnue_score = SignificanceScorer.score_piece_nnue_contribution(
            contrib["nnue_contribution_cp"],
            parsed["piece_type"]
        )
        
        profiles[piece_id] = {
            "piece_id": piece_id,
            "square": parsed["square"],
            "piece_type": parsed["piece_type"],
            "color": parsed["color"],
            "nnue_contribution_cp": contrib["nnue_contribution_cp"],
            "classical_contribution_cp": contrib["classical_contribution_cp"],
            "total_contribution_cp": contrib["total_contribution_cp"],
            "nnue_contribution_score": nnue_score,  # NEW: Significance score
            "classical_breakdown": {},
            "tags": [],
            "role": "active",
            "role_confidence": 0.5,
            "controls_squares": [],
            "key_squares_controlled": [],
            "coordinates_with": [],
            "defends": [],
            "attacks": [],
            "top_descriptors": [],
        }
    
    # Add square control data
    square_control = compute_square_control(board, piece_id_map)
    attribute_control_to_pieces(square_control, profiles)
    
    # Add piece interactions
    interactions = detect_piece_interactions(board, piece_id_map)
    add_interactions_to_profiles(interactions, profiles)
    
    # Add attack targets (enemy pieces)
    _compute_attack_targets(board, piece_id_map, profiles)
    
    # Assign tags to pieces
    if tags:
        _assign_tags_to_pieces(tags, profiles, phase)
    
    # Attribute classical terms to pieces
    if nnue_dump:
        classical_terms = nnue_dump.get("classical_terms", {})
        _attribute_classical_to_pieces(classical_terms, board, profiles)
    
    # Classify roles
    for piece_id, profile in profiles.items():
        sq_idx = piece_id_map[piece_id]
        role, confidence = classify_piece_role(profile, board, sq_idx, phase)
        profile["role"] = role
        profile["role_confidence"] = confidence
    
    # Generate top descriptors
    for piece_id, profile in profiles.items():
        profile["top_descriptors"] = _generate_top_descriptors(profile)
    
    return profiles


def _compute_attack_targets(
    board: chess.Board,
    piece_id_map: Dict[str, int],
    profiles: Dict[str, Dict]
) -> None:
    """Compute which enemy pieces each piece attacks."""
    for piece_id, sq in piece_id_map.items():
        piece = board.piece_at(sq)
        if not piece:
            continue
        
        attacks = board.attacks(sq)
        color = piece.color
        
        for target_sq in attacks:
            target_piece = board.piece_at(target_sq)
            if target_piece and target_piece.color != color:
                # Find target piece_id
                target_color = "white" if target_piece.color == chess.WHITE else "black"
                target_type = chess.piece_name(target_piece.piece_type)
                target_sq_name = chess.square_name(target_sq)
                target_id = f"{target_color}_{target_type}_{target_sq_name}"
                
                if target_id in piece_id_map:
                    profiles[piece_id]["attacks"].append(target_id)


def _assign_tags_to_pieces(
    tags: List[Dict],
    profiles: Dict[str, Dict],
    phase: str
) -> None:
    """
    Assign position tags to relevant pieces based on tag type and piece location.
    """
    # Track which tags have been assigned to each piece to avoid duplicates
    assigned_tags: Dict[str, set] = {pid: set() for pid in profiles}
    
    for tag_data in tags:
        tag_name = tag_data.get("tag_name", "")
        tag_squares = tag_data.get("squares", [])
        tag_side = tag_data.get("side", "both")
        
        # Special handling for threat tags - assign to BOTH attacker AND target
        if tag_name.startswith("tag.threat."):
            
            # Helper to assign threat tag to attacker piece
            def assign_to_attacker(attacker_sq: str, target_info: str = ""):
                for piece_id, profile in profiles.items():
                    if profile["square"] == attacker_sq:
                        piece_type = profile["piece_type"]
                        if piece_type == "king":
                            return  # Kings don't "threaten"
                        
                        full_tag = f"{tag_name}.{target_info}" if target_info else tag_name
                        if full_tag not in assigned_tags[piece_id]:
                            profile["tags"].append({
                                "tag": tag_name,
                                "weight": 0.9,
                                "phase_adjusted": 0.9,
                                "target": target_info if target_info else None,
                            })
                            assigned_tags[piece_id].add(full_tag)
                        return
            
            # Helper to assign status tag to target piece
            def assign_to_target(target_sq: str, status_tag: str, attacker_info: list = None):
                for piece_id, profile in profiles.items():
                    if profile["square"] == target_sq:
                        if status_tag not in assigned_tags[piece_id]:
                            tag_entry = {
                                "tag": status_tag,
                                "weight": -0.9,
                                "phase_adjusted": -0.9,
                            }
                            if attacker_info:
                                tag_entry["attackers"] = attacker_info
                            profile["tags"].append(tag_entry)
                            assigned_tags[piece_id].add(status_tag)
                        return
            
            # 1. tag.threat.capture.undefended - piece attacked with no defenders
            if tag_name == "tag.threat.capture.undefended":
                attackers = tag_data.get("attackers", [])
                target_square = tag_data.get("target_square", "")
                
                for attacker_sq in attackers:
                    assign_to_attacker(attacker_sq, target_square)
                
                if target_square:
                    assign_to_target(target_square, "tag.status.attacked.undefended", attackers)
                continue
            
            # 2. tag.threat.capture.more_value - attacking higher value piece
            if tag_name == "tag.threat.capture.more_value":
                from_sq = tag_data.get("from_square", "")
                to_sq = tag_data.get("to_square", "")
                
                if from_sq:
                    assign_to_attacker(from_sq, to_sq)
                if to_sq:
                    assign_to_target(to_sq, "tag.status.attacked.higher_value", [from_sq])
                continue
            
            # 3. tag.threat.hanging - attacked more times than defended
            if tag_name == "tag.threat.hanging":
                attackers = tag_data.get("attackers", [])
                target_square = tag_data.get("target_square", "")
                
                for attacker_sq in attackers:
                    assign_to_attacker(attacker_sq, target_square)
                
                if target_square:
                    assign_to_target(target_square, "tag.status.hanging", attackers)
                continue
            
            # 4. tag.threat.pin - piece pinned to higher value piece
            if tag_name == "tag.threat.pin":
                pinner_sq = tag_data.get("pinner_square", "")
                pinned_sq = tag_data.get("pinned_square", "")
                
                if pinner_sq:
                    assign_to_attacker(pinner_sq, pinned_sq)
                if pinned_sq:
                    assign_to_target(pinned_sq, "tag.status.pinned", [pinner_sq])
                continue
            
            # 5. tag.threat.skewer - piece in front can be forced to move
            if tag_name == "tag.threat.skewer":
                attacker_sq = tag_data.get("attacker_square", "")
                front_sq = tag_data.get("front_square", "")
                behind_sq = tag_data.get("behind_square", "")
                
                if attacker_sq:
                    assign_to_attacker(attacker_sq, front_sq)
                if front_sq:
                    assign_to_target(front_sq, "tag.status.skewered", [attacker_sq])
                if behind_sq:
                    assign_to_target(behind_sq, "tag.status.skewer_target", [attacker_sq])
                continue
            
            # 6. tag.threat.fork - piece attacks 2+ pieces
            if tag_name == "tag.threat.fork":
                from_sq = tag_data.get("from_square", "")
                to_sq = tag_data.get("to_square", "")
                targets = tag_data.get("targets", [])
                
                # Only real forks with 2+ targets
                if len(targets) >= 2:
                    if from_sq:
                        # For forks, check piece type - kings can't threaten forks
                        for piece_id, profile in profiles.items():
                            if profile["square"] == from_sq:
                                piece_type = profile["piece_type"]
                                if piece_type == "king":
                                    break
                                
                                full_tag = f"{tag_name}.{to_sq}"
                                if full_tag not in assigned_tags[piece_id]:
                                    target_squares = [t.get("square", "") for t in targets]
                                    profile["tags"].append({
                                        "tag": tag_name,
                                        "weight": 0.9,
                                        "phase_adjusted": 0.9,
                                        "targets": target_squares,
                                    })
                                    assigned_tags[piece_id].add(full_tag)
                                break
                    
                    # Assign forked status to each target
                    for target in targets:
                        target_sq = target.get("square", "")
                        if target_sq:
                            assign_to_target(target_sq, "tag.status.forked", [from_sq])
                continue
            
            # 7. tag.threat.check_imminent - can give check
            if tag_name == "tag.threat.check_imminent":
                from_sq = tag_data.get("from_square", "")
                if from_sq:
                    assign_to_attacker(from_sq, "check")
                continue
            
            # 8. Other threat tags with from_square (fallback)
            from_square = tag_data.get("from_square", "")
            if from_square:
                for piece_id, profile in profiles.items():
                    if profile["square"] == from_square:
                        piece_type = profile["piece_type"]
                        
                        if piece_type == "king":
                            break
                        
                        if tag_name not in assigned_tags[piece_id]:
                            base_weight = 0.8
                            phase_adjusted = get_tag_weight_for_piece(tag_name, piece_type, phase)
                            profile["tags"].append({
                                "tag": tag_name,
                                "weight": base_weight,
                                "phase_adjusted": phase_adjusted if phase_adjusted != 0 else base_weight,
                            })
                            assigned_tags[piece_id].add(tag_name)
                        break
            
            continue
        
        # Special handling for piece-type-specific mobility tags
        # e.g., "tag.activity.mobility.knight" should only go to knights
        if tag_name.startswith("tag.activity.mobility."):
            target_piece_type = tag_name.split(".")[-1]  # "knight", "bishop", etc.
            for piece_id, profile in profiles.items():
                if profile["piece_type"] == target_piece_type:
                    piece_color = profile["color"]
                    if tag_side != "both" and tag_side != piece_color:
                        continue
                    if tag_name not in assigned_tags[piece_id]:
                        base_weight = 0.8
                        phase_adjusted = get_tag_weight_for_piece(tag_name, target_piece_type, phase)
                        profile["tags"].append({
                            "tag": tag_name,
                            "weight": base_weight,
                            "phase_adjusted": phase_adjusted if phase_adjusted != 0 else base_weight,
                        })
                        assigned_tags[piece_id].add(tag_name)
            continue
        
        # Special handling for diagonal tags - only assign to the piece that controls it
        # Diagonal tags have a "pieces" field like ["Bf1"] or ["Qd1"]
        if tag_name.startswith("tag.diagonal."):
            tag_pieces = tag_data.get("pieces", [])
            for piece_str in tag_pieces:
                # Parse piece string like "Bf1" or "Qd1"
                if len(piece_str) >= 2:
                    piece_symbol = piece_str[0]
                    piece_square = piece_str[1:].lower()
                    
                    # Map symbol to type
                    symbol_to_type = {"B": "bishop", "Q": "queen", "R": "rook", "N": "knight", "P": "pawn", "K": "king"}
                    piece_type = symbol_to_type.get(piece_symbol.upper(), "")
                    
                    # Find matching piece in profiles
                    for piece_id, profile in profiles.items():
                        if (profile["piece_type"] == piece_type and 
                            profile["square"] == piece_square and
                            (tag_side == "both" or tag_side == profile["color"])):
                            
                            if tag_name not in assigned_tags[piece_id]:
                                base_weight = 1.0 if piece_type == "bishop" else 0.8
                                phase_adjusted = get_tag_weight_for_piece(tag_name, piece_type, phase)
                                profile["tags"].append({
                                    "tag": tag_name,
                                    "weight": base_weight,
                                    "phase_adjusted": phase_adjusted if phase_adjusted != 0 else base_weight,
                                })
                                assigned_tags[piece_id].add(tag_name)
                            break
            continue
        
        # Handle ANY tag with "pieces" field - assign only to those specific pieces
        # Format: "pieces": ["Ra1", "Bf3", "Nc6", "Qd1", "Pe4"]
        tag_pieces = tag_data.get("pieces", [])
        if tag_pieces:
            symbol_to_type = {"B": "bishop", "Q": "queen", "R": "rook", "N": "knight", "P": "pawn", "K": "king"}
            
            for piece_str in tag_pieces:
                if len(piece_str) >= 2:
                    piece_symbol = piece_str[0].upper()
                    piece_square = piece_str[1:].lower()
                    piece_type = symbol_to_type.get(piece_symbol, "")
                    
                    if not piece_type:
                        continue
                    
                    # Find the matching piece
                    for piece_id, profile in profiles.items():
                        if (profile["piece_type"] == piece_type and 
                            profile["square"] == piece_square and
                            (tag_side == "both" or tag_side == profile["color"])):
                            
                            if tag_name not in assigned_tags[piece_id]:
                                base_weight = 0.9  # High weight for specific piece tags
                                phase_adjusted = get_tag_weight_for_piece(tag_name, piece_type, phase)
                                profile["tags"].append({
                                    "tag": tag_name,
                                    "weight": base_weight,
                                    "phase_adjusted": phase_adjusted if phase_adjusted != 0 else base_weight,
                                })
                                assigned_tags[piece_id].add(tag_name)
                            break
            continue
        
        # Get relevant piece types for this tag
        relevant_types = {}
        for prefix, piece_weights in TAG_PIECE_RELEVANCE.items():
            if tag_name.startswith(prefix):
                relevant_types = piece_weights
                break
        
        if not relevant_types:
            continue
        
        # Assign to pieces
        for piece_id, profile in profiles.items():
            piece_type = profile["piece_type"]
            piece_color = profile["color"]
            piece_square = profile["square"]
            
            # Skip if tag already assigned to this piece
            if tag_name in assigned_tags[piece_id]:
                continue
            
            # Check if tag is relevant to this piece type
            if piece_type not in relevant_types and "all" not in relevant_types:
                continue
            
            # Check side relevance
            if tag_side != "both" and tag_side != piece_color:
                continue
            
            # Check square relevance (if tag has squares)
            square_relevant = len(tag_squares) == 0 or piece_square in tag_squares
            
            # For some tags, piece needs to be on or near the tag's squares
            if tag_squares and not square_relevant:
                # Check if piece is adjacent to any tag square
                square_relevant = _is_adjacent_to_any(piece_square, tag_squares)
            
            if square_relevant or len(tag_squares) == 0:
                base_weight = relevant_types.get(piece_type, relevant_types.get("all", 0))
                phase_adjusted = get_tag_weight_for_piece(tag_name, piece_type, phase)
                
                if abs(base_weight) > 0.1:  # Only add if significant
                    profile["tags"].append({
                        "tag": tag_name,
                        "weight": base_weight,
                        "phase_adjusted": phase_adjusted if phase_adjusted != 0 else base_weight,
                    })
                    assigned_tags[piece_id].add(tag_name)


def _is_adjacent_to_any(square: str, squares: List[str]) -> bool:
    """Check if a square is adjacent to any square in the list."""
    try:
        sq_idx = chess.parse_square(square)
        sq_file = chess.square_file(sq_idx)
        sq_rank = chess.square_rank(sq_idx)
        
        for other in squares:
            other_idx = chess.parse_square(other)
            other_file = chess.square_file(other_idx)
            other_rank = chess.square_rank(other_idx)
            
            if abs(sq_file - other_file) <= 1 and abs(sq_rank - other_rank) <= 1:
                return True
    except:
        pass
    return False


def _attribute_classical_to_pieces(
    classical_terms: Dict[str, Dict[str, int]],
    board: chess.Board,
    profiles: Dict[str, Dict]
) -> None:
    """
    Distribute classical evaluation terms to individual pieces.
    Uses heuristics based on piece characteristics.
    """
    # Initialize classical breakdown for all pieces
    for profile in profiles.values():
        profile["classical_breakdown"] = {
            "mobility": 0,
            "threat": 0,
            "space": 0,
            "king_safety": 0,
        }
    
    # Get term values (white perspective)
    mobility_white = classical_terms.get("MOBILITY", {}).get("white_mg", 0)
    mobility_black = classical_terms.get("MOBILITY", {}).get("black_mg", 0)
    threat_white = classical_terms.get("THREAT", {}).get("white_mg", 0)
    threat_black = classical_terms.get("THREAT", {}).get("black_mg", 0)
    space_white = classical_terms.get("SPACE", {}).get("white_mg", 0)
    space_black = classical_terms.get("SPACE", {}).get("black_mg", 0)
    
    # Compute mobility per piece
    white_mobility_total = 0
    black_mobility_total = 0
    piece_mobility = {}
    
    for piece_id, profile in profiles.items():
        sq = chess.parse_square(profile["square"])
        piece = board.piece_at(sq)
        if not piece:
            continue
        
        mobility = len(list(board.attacks(sq)))
        piece_mobility[piece_id] = mobility
        
        if piece.color == chess.WHITE:
            white_mobility_total += mobility
        else:
            black_mobility_total += mobility
    
    # Distribute mobility proportionally
    for piece_id, mobility in piece_mobility.items():
        color = profiles[piece_id]["color"]
        if color == "white" and white_mobility_total > 0:
            share = mobility / white_mobility_total
            profiles[piece_id]["classical_breakdown"]["mobility"] = int(mobility_white * share)
        elif color == "black" and black_mobility_total > 0:
            share = mobility / black_mobility_total
            profiles[piece_id]["classical_breakdown"]["mobility"] = int(mobility_black * share)
    
    # Attribute threats to pieces that attack enemy pieces
    for piece_id, profile in profiles.items():
        attacks = profile.get("attacks", [])
        if attacks:
            color = profile["color"]
            threat_value = threat_white if color == "white" else threat_black
            # Divide threat among attacking pieces (simplified)
            profile["classical_breakdown"]["threat"] = int(threat_value * len(attacks) / max(1, len(attacks)))
    
    # Attribute space to pieces on advanced squares
    for piece_id, profile in profiles.items():
        sq = chess.parse_square(profile["square"])
        rank = chess.square_rank(sq)
        color = profile["color"]
        
        # Advanced = ranks 4-7 for white, ranks 0-3 for black
        if color == "white" and rank >= 3:
            advancement = (rank - 3) / 4  # 0-1 scale
            profile["classical_breakdown"]["space"] = int(space_white * advancement * 0.3)
        elif color == "black" and rank <= 4:
            advancement = (4 - rank) / 4
            profile["classical_breakdown"]["space"] = int(space_black * advancement * 0.3)


def classify_piece_role(
    profile: Dict,
    board: chess.Board,
    sq_idx: int,
    phase: str
) -> Tuple[str, float]:
    """
    Determine the strategic role of a piece.
    
    Returns:
        (role_name, confidence)
    """
    piece = board.piece_at(sq_idx)
    if not piece:
        return ("passive", 0.5)
    
    piece_type = profile["piece_type"]
    color = profile["color"]
    square = profile["square"]
    contribution = profile.get("total_contribution_cp", 0)
    key_squares = profile.get("key_squares_controlled", [])
    attacks = profile.get("attacks", [])
    mobility = len(list(board.attacks(sq_idx)))
    
    # Check for undeveloped (opening phase, still on starting square)
    if phase == "opening" and is_piece_on_starting_square(piece_type, square, color):
        return ("undeveloped", 0.9)
    
    # Check for passive (very low mobility)
    if mobility < ROLE_THRESHOLDS["passive_mobility_threshold"]:
        return ("passive", 0.8)
    
    # Check for dominant (controls multiple key squares)
    if len(key_squares) >= ROLE_THRESHOLDS["dominant_control_threshold"]:
        return ("dominant", 0.85)
    
    # Check for attacker (attacking enemy pieces, high threat)
    threat_contribution = profile.get("classical_breakdown", {}).get("threat", 0)
    if len(attacks) >= 2 or threat_contribution > ROLE_THRESHOLDS["attacker_threat_threshold"]:
        return ("attacker", 0.75)
    
    # Check for defender (protecting many pieces)
    if len(profile.get("defends", [])) >= 2:
        return ("defender", 0.7)
    
    # Check for active (high mobility)
    if mobility >= ROLE_THRESHOLDS["active_mobility_threshold"]:
        return ("active", 0.7)
    
    # Check for restricted (low mobility but not passive)
    if mobility < 5:
        return ("restricted", 0.6)
    
    # Default to active
    return ("active", 0.5)


def _generate_top_descriptors(profile: Dict) -> List[str]:
    """Generate top 3 natural language descriptors for a piece."""
    descriptors = []
    piece_type = profile.get("piece_type", "")
    
    # Add role first (most important descriptor)
    role = profile.get("role", "active")
    if role != "active":  # "active" is too generic
        descriptors.append(role)
    
    # Add key square control
    key_squares = profile.get("key_squares_controlled", [])
    if key_squares:
        descriptors.append(f"controls {key_squares[0]}")
    
    # Add meaningful tag descriptors
    tags = sorted(profile.get("tags", []), key=lambda t: abs(t.get("phase_adjusted", 0)), reverse=True)
    for tag_data in tags[:3]:
        tag = tag_data.get("tag", "")
        parts = tag.split(".")
        
        # Extract meaningful part of tag name
        simple = None
        if len(parts) >= 3:
            # E.g., "tag.file.open" → "open file", "tag.bishop.bad" → "bad bishop"
            category = parts[1] if len(parts) > 1 else ""
            descriptor = parts[2] if len(parts) > 2 else ""
            
            # Skip generic activity/mobility tags that would give piece names
            if category == "activity" and descriptor == "mobility":
                continue
            
            # Format based on tag structure
            if category in ("file", "diagonal"):
                # "tag.file.open.d" → "open file"
                simple = f"{descriptor} {category}" if descriptor else category
            elif category == "threat":
                # "tag.threat.fork" → "threatens fork"
                # "tag.threat.capture.undefended" → "threatens <target>"
                if descriptor == "capture":
                    target = tag_data.get("target", "")
                    if target:
                        simple = f"threatens {target}"
                    else:
                        simple = "threatens capture"
                else:
                    simple = f"threatens {descriptor}"
            elif category == "rook":
                # "tag.rook.open_file" → "open file"
                rook_descriptors = {
                    "open_file": "open file",
                    "semi_open": "semi-open file",
                    "rank7": "7th rank",
                    "connected": "connected",
                }
                simple = rook_descriptors.get(descriptor, descriptor)
            elif category == "pawn":
                # "tag.pawn.passed.e5" → "passed"
                pawn_descriptors = {
                    "passed": "passed",
                    "isolated": "isolated",
                    "doubled": "doubled",
                    "backward": "backward",
                    "chain": "pawn chain",
                }
                simple = pawn_descriptors.get(descriptor, descriptor)
            elif category == "square":
                # "tag.square.outpost.knight.f5" → "outpost"
                if descriptor == "outpost":
                    simple = "outpost"
                else:
                    simple = descriptor
            elif category == "battery":
                # "tag.battery.qb.diagonal" → "battery"
                simple = "battery"
            elif category in ("bishop", "knight", "king"):
                # "tag.bishop.bad" → "bad" (piece type is already known)
                simple = descriptor
            elif category == "center":
                simple = "central"
            elif category == "outpost":
                simple = "outpost"
            elif category == "status":
                # Handle all status tags with clear descriptors
                status_descriptors = {
                    "attacked": "en prise",
                    "hanging": "hanging",
                    "pinned": "pinned",
                    "skewered": "skewered",
                    "skewer_target": "exposed",
                    "forked": "forked",
                }
                simple = status_descriptors.get(descriptor, descriptor)
            else:
                simple = descriptor if len(descriptor) > 2 else category
        elif len(parts) == 2:
            simple = parts[1]
        
        if simple and simple not in descriptors and len(simple) > 2:
            descriptors.append(simple)
            if len(descriptors) >= 3:
                break
    
    # Add coordination if space permits
    if len(descriptors) < 3 and profile.get("coordinates_with"):
        descriptors.append("coordinated")
    
    return descriptors[:3]


def get_profile_summary(profiles: Dict[str, Dict]) -> Dict[str, Dict]:
    """
    Get summary statistics for piece profiles.
    
    Returns:
        {
            "white": {
                "total_contribution": 145,
                "most_valuable_piece": "white_queen_d1",
                "weakest_piece": "white_knight_b1",
                "active_pieces": 5,
                "passive_pieces": 2
            },
            "black": {...}
        }
    """
    summary = {
        "white": {
            "total_contribution": 0,
            "most_valuable_piece": None,
            "most_valuable_contribution": float("-inf"),
            "weakest_piece": None,
            "weakest_contribution": float("inf"),
            "active_pieces": 0,
            "passive_pieces": 0,
            "piece_count": 0,
        },
        "black": {
            "total_contribution": 0,
            "most_valuable_piece": None,
            "most_valuable_contribution": float("-inf"),
            "weakest_piece": None,
            "weakest_contribution": float("inf"),
            "active_pieces": 0,
            "passive_pieces": 0,
            "piece_count": 0,
        }
    }
    
    for piece_id, profile in profiles.items():
        color = profile["color"]
        contrib = profile.get("total_contribution_cp", 0)
        role = profile.get("role", "active")
        
        summary[color]["total_contribution"] += contrib
        summary[color]["piece_count"] += 1
        
        # Track most/least valuable
        # For white, higher contribution is better; for black, lower (more negative) is better
        if color == "white":
            if contrib > summary[color]["most_valuable_contribution"]:
                summary[color]["most_valuable_contribution"] = contrib
                summary[color]["most_valuable_piece"] = piece_id
            if contrib < summary[color]["weakest_contribution"]:
                summary[color]["weakest_contribution"] = contrib
                summary[color]["weakest_piece"] = piece_id
        else:
            # For black pieces, more negative = more valuable (hurts white more)
            if contrib < summary[color]["most_valuable_contribution"]:
                summary[color]["most_valuable_contribution"] = contrib
                summary[color]["most_valuable_piece"] = piece_id
            if contrib > summary[color]["weakest_contribution"]:
                summary[color]["weakest_contribution"] = contrib
                summary[color]["weakest_piece"] = piece_id
        
        # Count active/passive
        if role in ("active", "dominant", "attacker"):
            summary[color]["active_pieces"] += 1
        elif role in ("passive", "undeveloped", "restricted"):
            summary[color]["passive_pieces"] += 1
    
    # Clean up infinity values
    for color in ["white", "black"]:
        if summary[color]["most_valuable_contribution"] == float("-inf"):
            summary[color]["most_valuable_contribution"] = 0
        if summary[color]["weakest_contribution"] == float("inf"):
            summary[color]["weakest_contribution"] = 0
    
    return summary

