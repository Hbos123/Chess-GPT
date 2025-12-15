"""
Response Annotator
Parses LLM responses for tag mentions and generates board annotations.
"""

import re
from typing import Dict, List, Any, Optional, Tuple
import chess


# Tag patterns to detect in LLM text
TAG_PATTERNS = [
    # Explicit tag format: tag.category.subcategory
    r'tag\.[\w.]+',
    # Common theme mentions
    r'(diagonal|file|rank)\s+([a-h][1-8])\s*[-–]\s*([a-h][1-8])',
    r'(open|semi-open)\s+(file|diagonal)',
    r'(pin|skewer|fork|discovered\s+attack)',
    r'(weak\s+square|outpost)\s+(?:on\s+)?([a-h][1-8])',
    r'attack(?:ing|s)?\s+(?:the\s+)?([a-h][1-8])',
    r'threat\s+(?:on|to)\s+([a-h][1-8])',
    r'control(?:s|ling)?\s+(?:the\s+)?([a-h][1-8])',
]

# Square color codes for different annotation types
ANNOTATION_COLORS = {
    "threat": "#ff4444",      # Red for threats
    "attack": "#ff6b6b",      # Light red for attacks
    "defense": "#4ecdc4",     # Teal for defense
    "control": "#ffe66d",     # Yellow for control
    "diagonal": "#a855f7",    # Purple for diagonals
    "file": "#3b82f6",        # Blue for files
    "weakness": "#f97316",    # Orange for weaknesses
    "outpost": "#22c55e",     # Green for outposts
    "pin": "#ef4444",         # Red for pins
    "fork": "#f59e0b",        # Amber for forks
    "default": "#6366f1",     # Indigo default
}

# Arrow colors
ARROW_COLORS = {
    "threat": "red",
    "attack": "orange",
    "defense": "blue",
    "move": "green",
    "diagonal": "purple",
    "pin": "red",
    "fork": "yellow",
    "default": "green",
}


def parse_response_for_annotations(
    llm_response: str,
    cached_analysis: Optional[Dict] = None,
    fen: Optional[str] = None
) -> Dict[str, Any]:
    """
    Parse LLM response text and generate board annotations.
    
    Args:
        llm_response: The text response from the LLM
        cached_analysis: Cached analysis data with tags
        fen: Current board FEN
        
    Returns:
        Dict with arrows, highlights, and metadata
    """
    annotations = {
        "arrows": [],
        "highlights": [],
        "tags_found": [],
        "annotation_summary": ""
    }
    
    if not llm_response:
        return annotations
    
    # Extract explicit tags from response
    explicit_tags = re.findall(r'tag\.[\w.]+', llm_response.lower())
    annotations["tags_found"] = list(set(explicit_tags))
    
    # Get tags from cached analysis if available
    analysis_tags = []
    if cached_analysis:
        # Tags might be in different places depending on analysis type
        if "tags" in cached_analysis:
            analysis_tags = cached_analysis["tags"]
        elif "white_analysis" in cached_analysis:
            analysis_tags.extend(cached_analysis.get("white_analysis", {}).get("tags", []))
            analysis_tags.extend(cached_analysis.get("black_analysis", {}).get("tags", []))
    
    # Match mentioned tags to analysis tags
    for tag_name in annotations["tags_found"]:
        for tag_data in analysis_tags:
            tag_data_name = tag_data.get("name", "") if isinstance(tag_data, dict) else str(tag_data)
            if tag_name in tag_data_name.lower():
                # Generate annotations for this tag
                tag_annotations = generate_annotations_for_tag(tag_data, fen)
                annotations["arrows"].extend(tag_annotations.get("arrows", []))
                annotations["highlights"].extend(tag_annotations.get("highlights", []))
    
    # ALSO process ALL cached analysis tags (not just mentioned ones)
    # This ensures important tactical/positional tags are always shown
    priority_tag_types = ["threat", "pin", "fork", "skewer", "attack", "hanging", "weak"]
    for tag_data in analysis_tags:
        if isinstance(tag_data, dict):
            tag_name = tag_data.get("name", "").lower()
            # Check if it's a priority tag type
            if any(pt in tag_name for pt in priority_tag_types):
                tag_annotations = generate_annotations_for_tag(tag_data, fen)
                annotations["arrows"].extend(tag_annotations.get("arrows", []))
                annotations["highlights"].extend(tag_annotations.get("highlights", []))
            # Also include key square tags
            elif "key" in tag_name:
                tag_annotations = generate_annotations_for_tag(tag_data, fen)
                annotations["highlights"].extend(tag_annotations.get("highlights", []))
    
    # Also parse natural language mentions
    nl_annotations = parse_natural_language_annotations(llm_response, fen)
    annotations["arrows"].extend(nl_annotations.get("arrows", []))
    annotations["highlights"].extend(nl_annotations.get("highlights", []))
    
    # Deduplicate
    annotations["arrows"] = deduplicate_arrows(annotations["arrows"])
    annotations["highlights"] = deduplicate_highlights(annotations["highlights"])
    
    # Generate summary
    if annotations["arrows"] or annotations["highlights"]:
        annotations["annotation_summary"] = (
            f"{len(annotations['arrows'])} arrows, {len(annotations['highlights'])} highlights"
        )
    
    return annotations


def generate_annotations_for_tag(
    tag_data: Dict,
    fen: Optional[str] = None
) -> Dict[str, List]:
    """
    Generate visual annotations for a specific tag.
    
    Args:
        tag_data: Tag dictionary with name, squares, pieces, etc.
        fen: Current board FEN
        
    Returns:
        Dict with arrows and highlights lists
    """
    result = {"arrows": [], "highlights": []}
    
    if not isinstance(tag_data, dict):
        return result
    
    tag_name = tag_data.get("name", "").lower()
    squares = tag_data.get("squares", [])
    pieces = tag_data.get("pieces", [])
    from_square = tag_data.get("from_square")
    to_square = tag_data.get("to_square")
    target_squares = tag_data.get("target_squares", [])
    attackers = tag_data.get("attackers", [])
    
    # Diagonal tags: draw arrow along diagonal
    if "diagonal" in tag_name:
        if squares and len(squares) >= 2:
            # Draw arrow from first to last square of diagonal
            result["arrows"].append({
                "from": squares[0],
                "to": squares[-1],
                "color": ARROW_COLORS["diagonal"],
                "type": "diagonal"
            })
        # Highlight piece controlling diagonal
        for piece in pieces:
            sq = extract_square_from_piece(piece)
            if sq:
                result["highlights"].append({
                    "square": sq,
                    "color": ANNOTATION_COLORS["diagonal"],
                    "type": "diagonal_control"
                })
    
    # Threat tags: highlight threat source and target
    elif "threat" in tag_name:
        if attackers:
            for attacker in attackers:
                sq = extract_square_from_piece(attacker)
                if sq:
                    result["highlights"].append({
                        "square": sq,
                        "color": ANNOTATION_COLORS["threat"],
                        "type": "attacker"
                    })
        if target_squares:
            for target in target_squares:
                result["highlights"].append({
                    "square": target,
                    "color": ANNOTATION_COLORS["attack"],
                    "type": "target"
                })
                # Draw arrow from attacker to target
                if attackers:
                    for attacker in attackers:
                        from_sq = extract_square_from_piece(attacker)
                        if from_sq:
                            result["arrows"].append({
                                "from": from_sq,
                                "to": target,
                                "color": ARROW_COLORS["threat"],
                                "type": "threat"
                            })
    
    # Pin/skewer tags: draw line through pinned piece
    elif "pin" in tag_name or "skewer" in tag_name:
        if from_square and to_square:
            result["arrows"].append({
                "from": from_square,
                "to": to_square,
                "color": ARROW_COLORS["pin"],
                "type": "pin"
            })
        if squares:
            for sq in squares:
                result["highlights"].append({
                    "square": sq,
                    "color": ANNOTATION_COLORS["pin"],
                    "type": "pinned"
                })
    
    # Fork tags: highlight forking piece and targets
    elif "fork" in tag_name:
        if pieces:
            sq = extract_square_from_piece(pieces[0])
            if sq:
                result["highlights"].append({
                    "square": sq,
                    "color": ANNOTATION_COLORS["fork"],
                    "type": "forker"
                })
        if target_squares:
            for target in target_squares:
                result["highlights"].append({
                    "square": target,
                    "color": ANNOTATION_COLORS["attack"],
                    "type": "fork_target"
                })
                # Draw arrows to targets
                if pieces:
                    from_sq = extract_square_from_piece(pieces[0])
                    if from_sq:
                        result["arrows"].append({
                            "from": from_sq,
                            "to": target,
                            "color": ARROW_COLORS["fork"],
                            "type": "fork"
                        })
    
    # Open file tags: highlight the file
    elif "open" in tag_name and "file" in tag_name:
        if squares:
            for sq in squares:
                result["highlights"].append({
                    "square": sq,
                    "color": ANNOTATION_COLORS["file"],
                    "type": "open_file"
                })
        # Highlight rook on the file
        for piece in pieces:
            sq = extract_square_from_piece(piece)
            if sq:
                result["highlights"].append({
                    "square": sq,
                    "color": ANNOTATION_COLORS["control"],
                    "type": "file_control"
                })
    
    # Outpost tags: highlight the outpost square
    elif "outpost" in tag_name:
        if squares:
            for sq in squares:
                result["highlights"].append({
                    "square": sq,
                    "color": ANNOTATION_COLORS["outpost"],
                    "type": "outpost"
                })
    
    # Weak square tags
    elif "weak" in tag_name:
        if squares:
            for sq in squares:
                result["highlights"].append({
                    "square": sq,
                    "color": ANNOTATION_COLORS["weakness"],
                    "type": "weakness"
                })
    
    # Control tags (but NOT center.control - that's handled by center branch)
    elif "control" in tag_name and "center" not in tag_name:
        if squares:
            for sq in squares[:4]:  # Limit to avoid clutter
                result["highlights"].append({
                    "square": sq,
                    "color": ANNOTATION_COLORS["control"],
                    "type": "control"
                })
    
    # Key square tags (tag.key.e4, tag.key.d4, etc.)
    elif "key" in tag_name:
        # Extract square from tag name - match patterns like tag.key.d4 or tag.key.e4
        key_sq_match = re.search(r'\.([a-h][1-8])(?:\.|$)', tag_name)
        if key_sq_match:
            result["highlights"].append({
                "square": key_sq_match.group(1),
                "color": ANNOTATION_COLORS["control"],
                "type": "key_square"
            })
        # Also check squares field
        if squares:
            for sq in squares[:2]:
                if sq not in [h.get("square") for h in result["highlights"]]:
                    result["highlights"].append({
                        "square": sq,
                        "color": ANNOTATION_COLORS["control"],
                        "type": "key_square"
                    })
    
    # Center control tags (tag.center.control.core, etc.)
    elif "center" in tag_name:
        # Highlight central squares - core squares are d4, d5, e4, e5
        if "core" in tag_name:
            central = ["d4", "d5", "e4", "e5"]
        else:
            # Extended center includes c3-f6 region
            central = ["d4", "d5", "e4", "e5", "c4", "c5", "f4", "f5"]
        for sq in central:
            result["highlights"].append({
                "square": sq,
                "color": ANNOTATION_COLORS["control"],
                "type": "center"
            })
    
    # Status tags (attacked, defended, etc.)
    elif "status" in tag_name:
        if pieces:
            for piece in pieces:
                sq = extract_square_from_piece(piece)
                if sq:
                    if "attacked" in tag_name or "hanging" in tag_name:
                        result["highlights"].append({
                            "square": sq,
                            "color": ANNOTATION_COLORS["threat"],
                            "type": "attacked"
                        })
                    elif "defended" in tag_name:
                        result["highlights"].append({
                            "square": sq,
                            "color": ANNOTATION_COLORS["defense"],
                            "type": "defended"
                        })
    
    return result


def parse_natural_language_annotations(
    text: str,
    fen: Optional[str] = None
) -> Dict[str, List]:
    """
    Parse natural language in the response for annotation-worthy mentions.
    
    Looks for patterns like:
    - "diagonal a1-h8"
    - "attacks e5"
    - "pin on d7"
    - "control of the center"
    - Candidate moves like "1. e4", "d4", "Nf3"
    """
    result = {"arrows": [], "highlights": []}
    text_lower = text.lower()
    
    # ================================================================
    # CANDIDATE MOVES: Parse numbered moves like "1. e4" or "2. d4"
    # ================================================================
    # Pattern: numbered candidate moves
    candidate_pattern = r'(\d+)\.\s*([KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]?)\s*[-–]'
    candidate_colors = ["#22c55e", "#3b82f6", "#a855f7", "#f59e0b", "#ec4899"]  # green, blue, purple, amber, pink
    
    for match in re.finditer(candidate_pattern, text):
        rank = int(match.group(1))
        move = match.group(2)
        # Extract destination square from move
        dest_match = re.search(r'([a-h][1-8])(?:[+#])?$', move)
        if dest_match and rank <= 5:
            color = candidate_colors[(rank - 1) % len(candidate_colors)]
            result["highlights"].append({
                "square": dest_match.group(1),
                "color": color,
                "type": f"candidate_{rank}",
                "label": move
            })
    
    # Also catch moves mentioned without numbering: "e4 - Establishes..."
    move_dash_pattern = r'\b([KQRBN]?[a-h][1-8])\s*[-–]\s*[A-Z]'
    for match in re.finditer(move_dash_pattern, text):
        sq = match.group(1)[-2:]  # Last 2 chars are the square
        if sq not in [h["square"] for h in result["highlights"]]:
            result["highlights"].append({
                "square": sq,
                "color": "#6366f1",  # Indigo
                "type": "mentioned_move"
            })
    
    # Pattern: diagonal X-Y
    diagonal_pattern = r'diagonal\s+([a-h][1-8])\s*[-–to]+\s*([a-h][1-8])'
    for match in re.finditer(diagonal_pattern, text_lower):
        result["arrows"].append({
            "from": match.group(1),
            "to": match.group(2),
            "color": ARROW_COLORS["diagonal"],
            "type": "diagonal"
        })
    
    # Pattern: attacks/threatens/targets square
    attack_pattern = r'(?:attacks?|threatens?|targets?)\s+(?:the\s+)?(?:pawn\s+on\s+)?([a-h][1-8])'
    for match in re.finditer(attack_pattern, text_lower):
        result["highlights"].append({
            "square": match.group(1),
            "color": ANNOTATION_COLORS["attack"],
            "type": "attacked"
        })
    
    # Pattern: weak square on X
    weak_pattern = r'weak(?:ness)?\s+(?:on|at|square)?\s*([a-h][1-8])'
    for match in re.finditer(weak_pattern, text_lower):
        result["highlights"].append({
            "square": match.group(1),
            "color": ANNOTATION_COLORS["weakness"],
            "type": "weakness"
        })
    
    # Pattern: outpost on X
    outpost_pattern = r'outpost\s+(?:on|at)?\s*([a-h][1-8])'
    for match in re.finditer(outpost_pattern, text_lower):
        result["highlights"].append({
            "square": match.group(1),
            "color": ANNOTATION_COLORS["outpost"],
            "type": "outpost"
        })
    
    # Pattern: pin/skewer involving squares
    pin_pattern = r'(?:pin|skewer)\s+.*?([a-h][1-8]).*?([a-h][1-8])'
    for match in re.finditer(pin_pattern, text_lower):
        result["arrows"].append({
            "from": match.group(1),
            "to": match.group(2),
            "color": ARROW_COLORS["pin"],
            "type": "pin"
        })
    
    # Pattern: controls/controls the X square(s)
    control_pattern = r'controls?\s+(?:the\s+)?([a-h][1-8](?:\s*,?\s*[a-h][1-8])*)'
    for match in re.finditer(control_pattern, text_lower):
        squares_str = match.group(1)
        squares = re.findall(r'[a-h][1-8]', squares_str)
        for sq in squares[:3]:  # Limit
            result["highlights"].append({
                "square": sq,
                "color": ANNOTATION_COLORS["control"],
                "type": "control"
            })
    
    # Pattern: move notation mentioned (e.g., "Bc4 targets f7")
    move_target_pattern = r'([KQRBN]?[a-h]?[1-8]?x?[a-h][1-8])\s+(?:targets?|attacks?|threatens?)\s+([a-h][1-8])'
    for match in re.finditer(move_target_pattern, text):
        # Extract destination from move
        move_sq = re.search(r'[a-h][1-8]$', match.group(1))
        if move_sq:
            result["arrows"].append({
                "from": move_sq.group(),
                "to": match.group(2),
                "color": ARROW_COLORS["attack"],
                "type": "attack"
            })
    
    # Pattern: "central control" or "control the center"
    if "central control" in text_lower or "center" in text_lower and "control" in text_lower:
        for sq in ["d4", "d5", "e4", "e5"]:
            if sq not in [h["square"] for h in result["highlights"]]:
                result["highlights"].append({
                    "square": sq,
                    "color": ANNOTATION_COLORS["control"],
                    "type": "center"
                })
    
    # Pattern: "support a future X move" or "prepares X"
    prepare_pattern = r'(?:support|prepare|prepares|enables?|allows?)\s+(?:a\s+)?(?:future\s+)?([a-h][1-8]|[KQRBN][a-h]?[1-8]?x?[a-h][1-8])'
    for match in re.finditer(prepare_pattern, text_lower):
        sq = match.group(1)[-2:] if len(match.group(1)) >= 2 else match.group(1)
        if re.match(r'[a-h][1-8]', sq):
            result["highlights"].append({
                "square": sq,
                "color": "#22c55e",  # Green for prepared squares
                "type": "prepared"
            })
    
    # Pattern: Piece moves like "Nf3", "Bc4" mentioned in explanation
    piece_move_pattern = r'\b([KQRBN][a-h]?[1-8]?x?[a-h][1-8])\b'
    mentioned_moves = set()
    for match in re.finditer(piece_move_pattern, text):
        move = match.group(1)
        if move not in mentioned_moves:
            mentioned_moves.add(move)
            dest = re.search(r'([a-h][1-8])$', move)
            if dest and dest.group(1) not in [h["square"] for h in result["highlights"]]:
                result["highlights"].append({
                    "square": dest.group(1),
                    "color": "#6366f1",  # Indigo
                    "type": "mentioned_piece_move"
                })
    
    # Pattern: Pawn moves like "e4", "d4" mentioned
    pawn_move_pattern = r'\b([a-h][1-8])\b(?:\s*[-–]|\s+(?:is|was|would|establishes|fights|controls))'
    for match in re.finditer(pawn_move_pattern, text_lower):
        sq = match.group(1)
        if sq not in [h["square"] for h in result["highlights"]]:
            result["highlights"].append({
                "square": sq,
                "color": "#22c55e",  # Green
                "type": "mentioned_pawn_move"
            })
    
    return result


def extract_square_from_piece(piece_str: str) -> Optional[str]:
    """Extract square from piece notation like 'Bc4', 'Ne5', 'white_bishop_c4'."""
    if not piece_str:
        return None
    
    # Pattern: ends with square notation
    match = re.search(r'([a-h][1-8])$', piece_str.lower())
    if match:
        return match.group(1)
    
    # Pattern: piece_type_square format
    match = re.search(r'_([a-h][1-8])$', piece_str.lower())
    if match:
        return match.group(1)
    
    return None


def deduplicate_arrows(arrows: List[Dict]) -> List[Dict]:
    """Remove duplicate arrows."""
    seen = set()
    unique = []
    for arrow in arrows:
        key = (arrow.get("from"), arrow.get("to"), arrow.get("type"))
        if key not in seen:
            seen.add(key)
            unique.append(arrow)
    return unique


def deduplicate_highlights(highlights: List[Dict]) -> List[Dict]:
    """Remove duplicate highlights (keep most important type)."""
    # Priority order for highlight types (lower = more important)
    priority = {
        "threat": 0,
        "attacked": 1,
        "attacker": 2,
        "pin": 3,
        "fork": 4,
        "target": 5,
        "candidate_1": 6,    # Best candidate
        "candidate_2": 7,
        "candidate_3": 8,
        "candidate_4": 9,
        "candidate_5": 10,
        "weakness": 11,
        "outpost": 12,
        "key_square": 13,
        "control": 14,
        "center": 15,
        "defended": 16,
        "diagonal_control": 17,
        "mentioned_move": 18,
        "mentioned_piece_move": 19,
        "mentioned_pawn_move": 20,
        "prepared": 21,
    }
    
    square_highlights = {}
    for h in highlights:
        sq = h.get("square")
        if sq:
            h_type = h.get("type", "default")
            h_priority = priority.get(h_type, 99)
            
            if sq not in square_highlights:
                square_highlights[sq] = h
            else:
                existing_priority = priority.get(square_highlights[sq].get("type"), 99)
                if h_priority < existing_priority:
                    square_highlights[sq] = h
    
    return list(square_highlights.values())


def generate_candidate_move_annotations(
    candidates: List[Dict],
    limit: int = 3
) -> Dict[str, List]:
    """
    Generate annotations for candidate moves.
    
    Args:
        candidates: List of candidate move dicts with 'move', 'eval_cp', etc.
        limit: Max candidates to annotate
        
    Returns:
        Dict with arrows for candidate moves
    """
    result = {"arrows": [], "highlights": []}
    
    colors = ["green", "blue", "purple"]
    
    for i, candidate in enumerate(candidates[:limit]):
        move_san = candidate.get("move", "")
        if not move_san:
            continue
        
        # Parse move to get from/to squares
        # This is simplified - full implementation would need board context
        match = re.match(r'([KQRBN]?)([a-h]?)([1-8]?)x?([a-h][1-8])', move_san)
        if match:
            dest = match.group(4)
            # For now just highlight destination
            result["highlights"].append({
                "square": dest,
                "color": colors[i % len(colors)],
                "type": f"candidate_{i+1}"
            })
    
    return result

