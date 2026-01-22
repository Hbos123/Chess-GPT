"""
Tag-to-piece mappings for the piece profile system.
Defines which tags are relevant to which piece types, with weighted relevance.
"""

from typing import Dict, List, Optional

# Weighted relevance: tag_prefix → {piece_type: weight}
# Positive weight = tag benefits this piece type
# Negative weight = tag hurts this piece type
TAG_PIECE_RELEVANCE: Dict[str, Dict[str, float]] = {
    # File control
    "tag.file.open": {"rook": 1.0, "queen": 0.7},
    "tag.file.semi": {"rook": 0.8, "queen": 0.5},
    
    # Diagonals
    "tag.diagonal.long": {"bishop": 1.0, "queen": 0.6},
    "tag.diagonal.short": {"bishop": 0.5, "queen": 0.4},
    "tag.diagonal": {"bishop": 0.8, "queen": 0.5},
    
    # Outposts/holes
    "tag.outpost": {"knight": 1.0, "bishop": 0.6, "rook": 0.3},
    "tag.hole": {"knight": 0.9, "bishop": 0.5},
    
    # Bishop-specific
    "tag.bishop.fianchetto": {"bishop": 1.0},
    "tag.bishop.bad": {"bishop": -0.8},
    "tag.bishop.good": {"bishop": 0.9},
    "tag.bishop.pair": {"bishop": 0.7},
    
    # Knight-specific
    "tag.knight.rim": {"knight": -0.6},
    "tag.knight.eternal": {"knight": 1.0},
    "tag.knight.central": {"knight": 0.8},
    
    # Rook-specific
    "tag.rook.seventh": {"rook": 1.0},
    "tag.rook.connected": {"rook": 0.8},
    "tag.rook.battery": {"rook": 0.9, "queen": 0.7},
    "tag.rook.open_file": {"rook": 0.9},
    
    # Pawn-specific
    "tag.pawn.passed": {"pawn": 1.0, "king": 0.4, "rook": 0.3},
    "tag.pawn.backward": {"pawn": -0.7},
    "tag.pawn.isolated": {"pawn": -0.6},
    "tag.pawn.doubled": {"pawn": -0.5},
    "tag.pawn.chain": {"pawn": 0.5},
    
    # King-specific
    "tag.king.exposed": {"king": -1.0, "queen": 0.5, "rook": 0.4},
    "tag.king.castled": {"king": 0.6},
    "tag.king.active_endgame": {"king": 0.9},
    "tag.king.safety": {"king": 0.8},
    
    # General positional
    "tag.center": {"knight": 0.8, "pawn": 0.7, "queen": 0.5, "bishop": 0.4},
    "tag.space": {"knight": 0.6, "bishop": 0.7, "rook": 0.4},
    "tag.activity": {"knight": 0.8, "bishop": 0.8, "rook": 0.9, "queen": 0.9},
    "tag.threat": {"knight": 0.7, "bishop": 0.7, "rook": 0.8, "queen": 0.9, "pawn": 0.5},
    "tag.development": {"knight": 0.9, "bishop": 0.9, "rook": 0.5, "queen": 0.3},
    
    # Lever/break tags
    "tag.lever": {"pawn": 1.0},
    "tag.break": {"pawn": 0.9},
}


# Phase multipliers for tag relevance
TAG_PHASE_MULTIPLIERS: Dict[str, Dict[str, float]] = {
    "opening": {
        "tag.development": 1.5,
        "tag.center": 1.3,
        "tag.king.castled": 1.2,
        "tag.king.safety": 1.3,
        "tag.rook.seventh": 0.3,
        "tag.king.active_endgame": 0.1,
        "tag.pawn.passed": 0.5,
    },
    "middlegame": {
        "tag.outpost": 1.2,
        "tag.file.open": 1.1,
        "tag.file.semi": 1.1,
        "tag.threat": 1.3,
        "tag.activity": 1.2,
        "tag.diagonal": 1.1,
        "tag.development": 0.7,
    },
    "endgame": {
        "tag.pawn.passed": 1.5,
        "tag.king.active_endgame": 1.4,
        "tag.rook.seventh": 1.3,
        "tag.development": 0.2,
        "tag.king.safety": 0.5,
        "tag.king.exposed": 0.3,  # Less bad in endgame
    }
}


# Classical term → tag category mapping
CLASSICAL_TO_TAG_CATEGORY: Dict[str, Optional[str]] = {
    "MOBILITY": "tag.activity",
    "THREAT": "tag.threat",
    "SPACE": "tag.space",
    "PASSED": "tag.pawn.passed",
    "MATERIAL": None,  # Handled by NNUE attribution directly
    "IMBALANCE": None,
    "WINNABLE": None,
    "TOTAL": None,
}


# Strategic role definitions
PIECE_ROLES: List[str] = [
    "attacker",      # High threat contribution, targets enemy king zone
    "defender",      # Protects key squares/pieces
    "blockader",     # Stops passed pawns
    "passive",       # Low mobility, not contributing
    "active",        # High mobility, flexible
    "restricted",    # Blocked by own pieces/pawns
    "dominant",      # Controls key squares unchallenged
    "vulnerable",    # Under attack or overloaded
    "undeveloped",   # Still on starting square (opening)
]


# Role classification thresholds
ROLE_THRESHOLDS = {
    "undeveloped_squares": {
        "knight": ["b1", "g1", "b8", "g8"],
        "bishop": ["c1", "f1", "c8", "f8"],
        "rook": ["a1", "h1", "a8", "h8"],
        "queen": ["d1", "d8"],
    },
    "passive_mobility_threshold": 3,  # Fewer than 3 legal moves = passive
    "active_mobility_threshold": 7,   # More than 7 = active
    "dominant_control_threshold": 2,  # Controls 2+ key squares
    "attacker_threat_threshold": 15,  # Threat contribution > 15cp
}


def get_tag_weight_for_piece(tag_name: str, piece_type: str, phase: str = "middlegame") -> float:
    """
    Get the weighted relevance of a tag for a specific piece type.
    Applies phase multipliers.
    
    Args:
        tag_name: Full tag name (e.g., "tag.file.open.d")
        piece_type: Piece type (e.g., "knight", "rook")
        phase: Game phase ("opening", "middlegame", "endgame")
    
    Returns:
        Weighted relevance (0.0 if not relevant)
    """
    # Find matching tag prefix
    base_weight = 0.0
    matched_prefix = None
    
    for prefix, piece_weights in TAG_PIECE_RELEVANCE.items():
        if tag_name.startswith(prefix):
            if piece_type in piece_weights:
                base_weight = piece_weights[piece_type]
                matched_prefix = prefix
                break
            elif "all" in piece_weights:
                base_weight = piece_weights["all"]
                matched_prefix = prefix
                break
    
    if base_weight == 0.0:
        return 0.0
    
    # Apply phase multiplier
    phase_multipliers = TAG_PHASE_MULTIPLIERS.get(phase, {})
    phase_mult = 1.0
    
    if matched_prefix:
        for mult_prefix, mult_value in phase_multipliers.items():
            if matched_prefix.startswith(mult_prefix) or tag_name.startswith(mult_prefix):
                phase_mult = mult_value
                break
    
    return base_weight * phase_mult


def get_relevant_piece_types_for_tag(tag_name: str) -> Dict[str, float]:
    """
    Get all piece types relevant to a tag and their weights.
    
    Args:
        tag_name: Full tag name
    
    Returns:
        Dict of piece_type → weight
    """
    for prefix, piece_weights in TAG_PIECE_RELEVANCE.items():
        if tag_name.startswith(prefix):
            return piece_weights.copy()
    return {}


def is_piece_on_starting_square(piece_type: str, square: str, color: str) -> bool:
    """Check if a piece is still on its starting square."""
    starting_squares = ROLE_THRESHOLDS["undeveloped_squares"].get(piece_type, [])
    
    # Filter by color (ranks 1-2 for white, 7-8 for black)
    if color == "white":
        valid_squares = [sq for sq in starting_squares if sq[1] in "12"]
    else:
        valid_squares = [sq for sq in starting_squares if sq[1] in "78"]
    
    return square in valid_squares

