"""
Opening query resolver - normalizes user input to opening identity.
"""

import re
import chess
from typing import Dict, List, Optional
from opening_explorer import LichessExplorerClient


# ECO code to opening name mapping (subset)
ECO_CODES = {
    "B90": {"name": "Sicilian Najdorf", "moves": ["e4", "c5", "Nf3", "d6", "d4", "cxd4", "Nxd4", "Nf6", "Nc3", "a6"]},
    "B92": {"name": "Sicilian Najdorf: Opocensky Variation", "moves": ["e4", "c5", "Nf3", "d6", "d4", "cxd4", "Nxd4", "Nf6", "Nc3", "a6", "Be2"]},
    "B94": {"name": "Sicilian Najdorf: 6.Bg5", "moves": ["e4", "c5", "Nf3", "d6", "d4", "cxd4", "Nxd4", "Nf6", "Nc3", "a6", "Bg5"]},
    "C42": {"name": "Russian Game", "moves": ["e4", "e5", "Nf3", "Nf6"]},
    "C50": {"name": "Italian Game", "moves": ["e4", "e5", "Nf3", "Nc6", "Bc4"]},
    "C54": {"name": "Italian Game: Giuoco Piano", "moves": ["e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5"]},
    "D06": {"name": "Queen's Gambit", "moves": ["d4", "d5", "c4"]},
    "D37": {"name": "Queen's Gambit Declined: Three Knights", "moves": ["d4", "d5", "c4", "e6", "Nf3", "Nf6", "Nc3"]},
    "D85": {"name": "Grünfeld Defense: Exchange Variation", "moves": ["d4", "Nf6", "c4", "g6", "Nc3", "d5", "cxd5", "Nxd5", "e4"]},
    "E20": {"name": "Nimzo-Indian Defense", "moves": ["d4", "Nf6", "c4", "e6", "Nc3", "Bb4"]},
    "E60": {"name": "King's Indian Defense", "moves": ["d4", "Nf6", "c4", "g6"]},
    "A40": {"name": "English Defense", "moves": ["d4", "b6"]},
    "B00": {"name": "King's Pawn Game", "moves": ["e4"]},
    "D00": {"name": "Queen's Pawn Game", "moves": ["d4", "d5"]},
    "A45": {"name": "Indian Defense", "moves": ["d4", "Nf6"]},
    "B01": {"name": "Scandinavian Defense", "moves": ["e4", "d5"]},
    "B02": {"name": "Alekhine's Defense", "moves": ["e4", "Nf6"]},
    "B07": {"name": "Pirc Defense", "moves": ["e4", "d6", "d4", "Nf6"]},
}

# Common opening name patterns
OPENING_PATTERNS = {
    "najdorf": {"eco": "B90", "keywords": ["sicilian", "najdorf"]},
    "caro-kann": {"eco": "B10", "keywords": ["caro", "kann"], "moves": ["e4", "c6"]},
    "french": {"eco": "C00", "keywords": ["french"], "moves": ["e4", "e6"]},
    "scandinavian": {"eco": "B01", "keywords": ["scandinavian", "center counter"], "moves": ["e4", "d5"]},
    "sicilian": {"eco": "B20", "keywords": ["sicilian"], "moves": ["e4", "c5"]},
    "italian": {"eco": "C50", "keywords": ["italian", "giuoco"], "moves": ["e4", "e5", "Nf3", "Nc6", "Bc4"]},
    "spanish": {"eco": "C60", "keywords": ["spanish", "ruy", "lopez"], "moves": ["e4", "e5", "Nf3", "Nc6", "Bb5"]},
    "queen's gambit": {"eco": "D06", "keywords": ["queen", "gambit"], "moves": ["d4", "d5", "c4"]},
    "king's indian": {"eco": "E60", "keywords": ["king", "indian"], "moves": ["d4", "Nf6", "c4", "g6"]},
    "nimzo-indian": {"eco": "E20", "keywords": ["nimzo"], "moves": ["d4", "Nf6", "c4", "e6", "Nc3", "Bb4"]},
    "grunfeld": {"eco": "D85", "keywords": ["grunfeld", "grünfeld"], "moves": ["d4", "Nf6", "c4", "g6", "Nc3", "d5"]},
    "london": {"eco": "D02", "keywords": ["london"], "moves": ["d4", "d5", "Nf3", "Nf6", "Bf4"]},
    "pirc": {"eco": "B07", "keywords": ["pirc"], "moves": ["e4", "d6", "d4", "Nf6"]},
    "alekhine": {"eco": "B02", "keywords": ["alekhine"], "moves": ["e4", "Nf6"]},
    "russian": {"eco": "C42", "keywords": ["russian", "petrov"], "moves": ["e4", "e5", "Nf3", "Nf6"]},
    "petrov": {"eco": "C42", "keywords": ["russian", "petrov"], "moves": ["e4", "e5", "Nf3", "Nf6"]},
}
def _normalize_pattern_data(data: Dict) -> Optional[Dict]:
    """Ensure pattern data contains a SAN move list."""
    normalized = dict(data)
    if "moves" not in normalized:
        eco = normalized.get("eco")
        if eco and eco in ECO_CODES:
            normalized["moves"] = ECO_CODES[eco]["moves"]
    return normalized if "moves" in normalized else None



def detect_eco_code(query: str) -> Optional[str]:
    """Detect if query is an ECO code (e.g., 'B90', 'C42')."""
    eco_pattern = re.match(r'^([A-E]\d{2})$', query.upper().strip())
    if eco_pattern:
        eco_code = eco_pattern.group(1)
        if eco_code in ECO_CODES:
            return eco_code
    return None


def detect_san_sequence(query: str) -> Optional[List[str]]:
    """Detect if query is a sequence of SAN moves."""
    # Try to parse as moves (e.g., "1.e4 c5 2.Nf3 d6")
    # Remove move numbers
    clean_query = re.sub(r'\d+\.', '', query)
    moves = clean_query.split()
    
    # Filter out empty strings and common non-move words
    moves = [m.strip() for m in moves if m.strip() and len(m.strip()) >= 2]
    
    if len(moves) < 2:
        return None
    
    # Try to validate as chess moves
    board = chess.Board()
    valid_moves = []
    
    for move_san in moves:
        try:
            move = board.parse_san(move_san)
            board.push(move)
            valid_moves.append(move_san)
        except:
            # Not a valid sequence
            return None
    
    return valid_moves if len(valid_moves) >= 2 else None


def fuzzy_match_opening(query: str) -> Optional[Dict]:
    """Fuzzy match query to known opening patterns."""
    query_lower = query.lower().strip()
    
    # Direct lookup
    if query_lower in OPENING_PATTERNS:
        normalized = _normalize_pattern_data(OPENING_PATTERNS[query_lower])
        if normalized:
            return normalized
    
    # Keyword matching - check if any keyword from patterns appears in the query
    for opening_name, data in OPENING_PATTERNS.items():
        keywords = data.get("keywords", [])
        if any(keyword in query_lower for keyword in keywords):
            normalized = _normalize_pattern_data(data)
            if normalized:
                return normalized
    
    return None


def infer_orientation(query: str, opening_name: str) -> str:
    """Infer which color the lesson should teach (default: white)."""
    query_lower = query.lower()
    name_lower = opening_name.lower()
    
    # Explicit color indicators
    if "as black" in query_lower or "for black" in query_lower:
        return "black"
    
    # Defense/counter patterns suggest Black
    defense_keywords = ["defense", "defence", "counter", "gambit declined"]
    if any(keyword in name_lower for keyword in defense_keywords):
        # But some gambits are for White
        if "king's gambit" in name_lower or "queen's gambit accepted" in name_lower:
            return "white"
        return "black"
    
    return "white"


async def resolve_opening(
    query: str,
    explorer: LichessExplorerClient
) -> Dict:
    """
    Normalize user input to opening identity.
    
    Args:
        query: User input (e.g., "Najdorf", "B90", "1.e4 c5 2.Nf3")
        explorer: Lichess explorer client
    
    Returns:
        {
            "name": str,
            "eco": str | None,
            "seed_fen": str,
            "seed_moves_san": List[str],
            "orientation": "white" | "black"
        }
    """
    query = query.strip()
    
    # Try ECO code
    eco_code = detect_eco_code(query)
    if eco_code:
        eco_data = ECO_CODES[eco_code]
        seed_fen = await explorer.parse_san_to_fen(eco_data["moves"])
        orientation = infer_orientation(query, eco_data["name"])
        
        return {
            "name": eco_data["name"],
            "eco": eco_code,
            "seed_fen": seed_fen,
            "seed_moves_san": eco_data["moves"],
            "orientation": orientation
        }
    
    # Try SAN sequence
    san_moves = detect_san_sequence(query)
    if san_moves:
        seed_fen = await explorer.parse_san_to_fen(san_moves)
        
        # Query explorer to get opening name if available
        explorer_data = await explorer.query_position(seed_fen)
        opening_info = explorer_data.get("opening", {})
        opening_name = opening_info.get("name", f"Custom Position ({len(san_moves)} moves)")
        eco = opening_info.get("eco")
        
        orientation = infer_orientation(query, opening_name)
        
        return {
            "name": opening_name,
            "eco": eco,
            "seed_fen": seed_fen,
            "seed_moves_san": san_moves,
            "orientation": orientation
        }
    
    # Try fuzzy match
    pattern_match = fuzzy_match_opening(query)
    if pattern_match:
        moves = pattern_match["moves"]
        seed_fen = await explorer.parse_san_to_fen(moves)
        
        # Get full name from explorer
        explorer_data = await explorer.query_position(seed_fen)
        opening_info = explorer_data.get("opening", {})
        opening_name = opening_info.get("name", query.title())
        eco = opening_info.get("eco", pattern_match.get("eco"))
        
        orientation = infer_orientation(query, opening_name)
        
        return {
            "name": opening_name,
            "eco": eco,
            "seed_fen": seed_fen,
            "seed_moves_san": moves,
            "orientation": orientation
        }
    
    # Fallback: Try to treat as a single opening move (e.g., "e4", "d4")
    # Only try this if it's a single word AND looks like a chess move (2-4 chars, starts with letter)
    if len(query.split()) == 1 and len(query) >= 2 and len(query) <= 4 and query[0].isalpha():
        try:
            board = chess.Board()
            move = board.parse_san(query)
            board.push(move)
            seed_fen = board.fen()
            
            # Query explorer to get opening name
            explorer_data = await explorer.query_position(seed_fen)
            opening_info = explorer_data.get("opening", {})
            opening_name = opening_info.get("name", f"{query.upper()} Opening")
            eco = opening_info.get("eco")
            
            return {
                "name": opening_name,
                "eco": eco,
                "seed_fen": seed_fen,
                "seed_moves_san": [query],
                "orientation": "white"  # Single first move is always white
            }
        except:
            pass
    
    # Ultimate fallback: start from starting position
    # This handles completely unrecognized queries
    startpos = chess.STARTING_FEN
    
    return {
        "name": f"{query.title()} Opening",
        "eco": None,
        "seed_fen": startpos,
        "seed_moves_san": [],
        "orientation": infer_orientation(query, query)
    }

