"""
Delta analyzer - computes differences between starting and ending positions.
Classifies plan types based on material and positional changes.
"""

from typing import Dict, List


def calculate_delta(
    themes_start: Dict,
    themes_final: Dict,
    material_start_cp: int,
    material_final_cp: int,
    positional_start_cp: int,
    positional_final_cp: int,
    tags_start: List = None,
    tags_final: List = None
) -> Dict:
    """
    Calculates theme deltas and classifies plan type.
    
    Args:
        themes_start: Theme analysis of starting position
        themes_final: Theme analysis of final position
        material_start_cp: Material balance at start
        material_final_cp: Material balance at end
        positional_start_cp: Positional CP significance at start
        positional_final_cp: Positional CP significance at end
        
    Returns for each side:
    {
      "white": {
        "theme_deltas": {"S_CENTER_SPACE": +5, "S_PAWN": -2, ...},
        "material_delta_cp": int,
        "positional_delta_cp": int,
        "plan_type": "advantage_conversion" | "leveraging_advantage" | "sacrifice",
        "plan_explanation": str
      },
      "black": {...}
    }
    """
    
    # Calculate theme deltas for White
    white_theme_deltas = {}
    for theme_key in themes_start.keys():
        start_total = themes_start[theme_key].get("white", {}).get("total", 0)
        final_total = themes_final[theme_key].get("white", {}).get("total", 0)
        white_theme_deltas[theme_key] = final_total - start_total
    
    # Calculate theme deltas for Black
    black_theme_deltas = {}
    for theme_key in themes_start.keys():
        start_total = themes_start[theme_key].get("black", {}).get("total", 0)
        final_total = themes_final[theme_key].get("black", {}).get("total", 0)
        black_theme_deltas[theme_key] = final_total - start_total
    
    # Material and positional deltas for White (from White's perspective)
    white_material_delta = material_final_cp - material_start_cp
    white_positional_delta = positional_final_cp - positional_start_cp
    
    # Material and positional deltas for Black (from Black's perspective)
    black_material_delta = -(material_final_cp - material_start_cp)  # Flip sign for Black
    black_positional_delta = -(positional_final_cp - positional_start_cp)  # Flip sign for Black
    
    # Classify plan types
    white_plan_type = classify_plan_type(white_material_delta, white_positional_delta)
    black_plan_type = classify_plan_type(black_material_delta, black_positional_delta)
    
    # Analyze tag changes
    white_tags_start = [t for t in (tags_start or []) if t.get("side") == "white" or t.get("side") == "both"]
    white_tags_final = [t for t in (tags_final or []) if t.get("side") == "white" or t.get("side") == "both"]
    black_tags_start = [t for t in (tags_start or []) if t.get("side") == "black" or t.get("side") == "both"]
    black_tags_final = [t for t in (tags_final or []) if t.get("side") == "black" or t.get("side") == "both"]
    
    # Generate explanations with tag-based actions
    white_explanation = generate_plan_explanation(
        white_plan_type, white_material_delta, white_positional_delta, white_theme_deltas,
        white_tags_start, white_tags_final
    )
    black_explanation = generate_plan_explanation(
        black_plan_type, black_material_delta, black_positional_delta, black_theme_deltas,
        black_tags_start, black_tags_final
    )
    
    return {
        "white": {
            "theme_deltas": white_theme_deltas,
            "material_delta_cp": white_material_delta,
            "positional_delta_cp": white_positional_delta,
            "plan_type": white_plan_type,
            "plan_explanation": white_explanation
        },
        "black": {
            "theme_deltas": black_theme_deltas,
            "material_delta_cp": black_material_delta,
            "positional_delta_cp": black_positional_delta,
            "plan_type": black_plan_type,
            "plan_explanation": black_explanation
        }
    }


def classify_plan_type(material_delta: int, positional_delta: int) -> str:
    """
    Classifies plan based on material and positional changes.
    
    Plan types:
    - Advantage conversion: positional_delta < 0, material_delta > 0
      (Trading positional advantage for material gain)
    - Leveraging advantage: positional_delta > 0, |material_delta| < 50
      (Improving position without material changes)
    - Sacrifice: material_delta < -50, positional_delta > 50
      (Sacrificing material for positional compensation)
    - Defensive: positional_delta < -100
      (Position is deteriorating)
    - Balanced: Everything else
    
    Args:
        material_delta: Change in material balance (cp)
        positional_delta: Change in positional CP significance
        
    Returns:
        Plan type string
    """
    # Advantage conversion: trading position for material
    if positional_delta < -30 and material_delta > 100:
        return "advantage_conversion"
    
    # Leveraging advantage: improving position
    if positional_delta > 30 and abs(material_delta) < 50:
        return "leveraging_advantage"
    
    # Sacrifice: giving up material for position
    if material_delta < -100 and positional_delta > 50:
        return "sacrifice"
    
    # Defensive: position worsening significantly
    if positional_delta < -100:
        return "defensive"
    
    # Material gain with position maintained
    if material_delta > 100 and positional_delta > -30:
        return "material_gain"
    
    # Default: balanced/unclear plan
    return "balanced"


def generate_plan_explanation(
    plan_type: str,
    material_delta: int,
    positional_delta: int,
    theme_deltas: Dict,
    tags_start: List = None,
    tags_final: List = None
) -> str:
    """
    Generate human-readable explanation of the plan in natural English,
    based on tag changes (what tags were gained/lost).
    
    Args:
        plan_type: Classified plan type
        material_delta: Material change in cp
        positional_delta: Positional change in cp
        theme_deltas: Changes in individual themes
        tags_start: Tags from starting position
        tags_final: Tags from final position
        
    Returns:
        Human-readable explanation string with specific actions
    """
    # Analyze tag changes to generate specific actions
    tag_actions = analyze_tag_changes(tags_start or [], tags_final or [])
    
    # Generate plan description based on type and tag changes
    if plan_type == "advantage_conversion":
        if tag_actions:
            return f"Trade pieces to convert advantages: {', then '.join(tag_actions[:2])}"
        return "Trade positional advantages for concrete material gains through simplification"
    
    elif plan_type == "leveraging_advantage":
        if tag_actions:
            return f"Build advantage by: {', then '.join(tag_actions[:3])}"
        return "Build on positional strengths through better piece coordination"
    
    elif plan_type == "sacrifice":
        if tag_actions:
            return f"Sacrifice for compensation via: {', then '.join(tag_actions[:2])}"
        return "Accept material losses to gain dynamic compensation through initiative"
    
    elif plan_type == "defensive":
        if tag_actions:
            return f"Defend by: {', then '.join(tag_actions[:2])}"
        return "Consolidate and seek counter-chances to stabilize the position"
    
    elif plan_type == "material_gain":
        if tag_actions:
            return f"Convert advantage: {', then '.join(tag_actions[:2])}"
        return "Convert material advantage into a winning position"
    
    else:  # balanced
        if tag_actions:
            return f"Continue with: {', then '.join(tag_actions[:2])}"
        return "Maintain equilibrium and look for small improvements"


def analyze_tag_changes(tags_start: List, tags_final: List) -> List[str]:
    """
    Analyze which tags were gained/lost and translate to natural language actions.
    
    Returns list of action strings like "develop your knight", "push pawns for space", etc.
    """
    actions = []
    
    # Get tag names for comparison
    start_tag_names = {t.get("tag_name") for t in tags_start}
    final_tag_names = {t.get("tag_name") for t in tags_final}
    
    # Tags gained (good things that happened)
    gained_tags = final_tag_names - start_tag_names
    
    # Tags lost (improvements made)
    lost_tags = start_tag_names - final_tag_names
    
    # Translate gained tags to actions
    for tag in gained_tags:
        action = tag_to_natural_action(tag, gained=True)
        if action:
            actions.append(action)
    
    # Translate lost bad tags to actions (e.g., lost "king.exposed" → "castle for safety")
    for tag in lost_tags:
        if is_bad_tag(tag):
            action = tag_to_natural_action(tag, gained=False)
            if action:
                actions.append(action)
    
    return actions[:4]  # Limit to top 4 actions


def tag_to_natural_action(tag_name: str, gained: bool) -> str:
    """Convert a tag to natural language action."""
    
    # Activity/Development tags
    if "activity.mobility.knight" in tag_name and gained:
        return "develop your knight"
    if "activity.mobility.bishop" in tag_name and gained:
        return "develop your bishop"
    if "activity.mobility.rook" in tag_name and gained:
        return "activate your rook"
    if "activity.mobility.queen" in tag_name and gained:
        return "activate your queen"
    
    # Center and space tags
    if "center.control.core" in tag_name and gained:
        return "control the center"
    if "center.control.near" in tag_name and gained:
        return "expand in the center"
    if "space.advantage" in tag_name and gained:
        return "push pawns for space"
    if tag_name.startswith("tag.key.") and gained:
        key_sq = tag_name.split('.')[-1]
        return f"control {key_sq}"
    
    # King safety tags
    if "king.castled.safe" in tag_name and gained:
        return "castle for safety"
    if "king.shield.intact" in tag_name and gained:
        return "maintain your pawn shield"
    if "king.center.exposed" in tag_name and not gained:  # Lost this bad tag
        return "castle to improve king safety"
    if "king.shield.missing" in tag_name and not gained:  # Lost this bad tag
        return "secure your king"
    
    # Pawn structure tags
    if "pawn.passed" in tag_name and gained:
        return "push for a passed pawn"
    if "pawn.passed.protected" in tag_name and gained:
        return "protect your passed pawn"
    
    # File control tags
    if "file.open" in tag_name and gained:
        file = tag_name.split('.')[-1]
        return f"control the {file}-file"
    if "rook.open_file" in tag_name and gained:
        return "place rook on open file"
    if "rook.rank7" in tag_name and gained:
        return "invade the 7th rank"
    if "rook.connected" in tag_name and gained:
        return "connect your rooks"
    
    # Outpost tags
    if "outpost.knight" in tag_name and gained:
        return "establish a knight outpost"
    
    # Bishop tags
    if "bishop.pair" in tag_name and gained:
        return "utilize the bishop pair"
    if "bishop.bad" in tag_name and not gained:  # Lost this bad tag
        return "improve your bad bishop"
    
    # Piece problems fixed
    if "piece.trapped" in tag_name and not gained:  # Lost this bad tag
        return "free trapped pieces"
    
    # Diagonal control
    if "diagonal.long" in tag_name and gained:
        return "control long diagonals"
    if "battery.qb" in tag_name and gained:
        return "coordinate queen and bishop"
    
    # Holes (bad if we have them, good if opponent does)
    if "color.hole" in tag_name:
        if not gained:  # We fixed our holes
            return "repair pawn weaknesses"
    
    return ""  # No translation for this tag


def is_bad_tag(tag_name: str) -> bool:
    """Check if a tag represents something negative."""
    bad_indicators = [
        "king.center.exposed",
        "king.shield.missing",
        "piece.trapped",
        "bishop.bad",
        "color.hole",
        "pawn.backward",
        "pawn.isolated"
    ]
    return any(bad in tag_name for bad in bad_indicators)


def tag_to_natural_description(tag: Dict) -> str:
    """
    Convert a tag to natural English description using tag metadata.
    
    Args:
        tag: Tag dict with tag_name, pieces, squares, files, details
        
    Returns:
        Natural English description (e.g., "opened the a1-h8 diagonal for the bishop")
    """
    tag_name = tag.get("tag_name", "")
    pieces = tag.get("pieces", [])
    squares = tag.get("squares", [])
    files = tag.get("files", [])
    
    # DIAGONAL TAGS
    if "diagonal.open.long.a1h8" in tag_name:
        piece = pieces[0][0] if pieces else "piece"
        piece_name = {"B": "bishop", "Q": "queen"}.get(piece, "piece")
        return f"placed {piece_name} on the open a1-h8 diagonal"
    
    if "diagonal.open.long.h1a8" in tag_name:
        piece = pieces[0][0] if pieces else "piece"
        piece_name = {"B": "bishop", "Q": "queen"}.get(piece, "piece")
        return f"placed {piece_name} on the open h1-a8 diagonal"
    
    if "diagonal.open." in tag_name:
        # Extract diagonal name (e.g., "d5-a2" from "tag.diagonal.open.d5-a2")
        parts = tag_name.split(".")
        if len(parts) >= 3:
            diag_name = parts[-1]  # e.g., "d5-a2"
            piece = pieces[0][0] if pieces else "piece"
            piece_name = {"B": "bishop", "Q": "queen"}.get(piece, "piece")
            return f"placed {piece_name} on the open {diag_name} diagonal"
        return "placed piece on open diagonal"
    
    if "diagonal.closed." in tag_name:
        # Extract diagonal name
        parts = tag_name.split(".")
        if len(parts) >= 3:
            diag_name = parts[-1]
            return f"closed the {diag_name} diagonal"
        return "closed a diagonal"
    
    # Legacy support for old format
    if "diagonal.long.a1h8" in tag_name:
        piece = pieces[0][0] if pieces else "piece"
        piece_name = {"B": "bishop", "Q": "queen"}.get(piece, "piece")
        return f"opened the long a1-h8 diagonal for the {piece_name}"
    
    if "diagonal.long.h1a8" in tag_name:
        piece = pieces[0][0] if pieces else "piece"
        piece_name = {"B": "bishop", "Q": "queen"}.get(piece, "piece")
        return f"opened the long h1-a8 diagonal for the {piece_name}"
    
    if "battery.qb" in tag_name:
        return "coordinated queen and bishop on the same diagonal"
    
    # FILE TAGS
    if "rook.open_file" in tag_name:
        file = files[0] if files else "a"
        return f"placed the rook on the open {file}-file"
    
    if "file.open." in tag_name:
        file = tag_name.split(".")[-1]
        return f"opened the {file}-file"
    
    if "file.semi." in tag_name:
        file = tag_name.split(".")[-1]
        return f"gained a semi-open {file}-file"
    
    if "rook.rank7" in tag_name:
        return "invaded the 7th rank with the rook"
    
    if "rook.connected" in tag_name:
        return "connected the rooks"
    
    # CENTER TAGS
    if "center.control.core" in tag_name:
        squares_list = ", ".join(squares[:4]) if squares else "d4, e4, d5, e5"
        return f"controlled the central squares ({squares_list})"
    
    if "center.control.near" in tag_name:
        return "expanded near-center control"
    
    if "space.advantage" in tag_name:
        return "gained a space advantage"
    
    # KEY SQUARES
    if tag_name.startswith("tag.key."):
        sq = tag_name.split(".")[-1]
        return f"controlled the key {sq} square"
    
    # KING SAFETY
    if "king.castled.safe" in tag_name:
        return "castled the king to safety"
    
    if "king.shield.intact" in tag_name:
        return "maintained a strong pawn shield"
    
    if "king.center.exposed" in tag_name:
        return "left the king exposed in the center"
    
    if "king.shield.missing" in tag_name:
        missing_file = tag_name.split(".")[-1] if "." in tag_name else "?"
        return f"weakened the king shield ({missing_file}-pawn missing)"
    
    if "king.file.open" in tag_name:
        return "allowed an open file toward the king"
    
    # PAWNS
    if "pawn.passed" in tag_name and len(squares) > 0:
        sq = squares[0]
        return f"created a passed pawn on {sq}"
    
    if "pawn.passed.protected" in tag_name:
        return "protected the passed pawn"
    
    if "pawn.passed.connected" in tag_name:
        return "created connected passed pawns"
    
    if tag_name.startswith("tag.lever."):
        sq = tag_name.split(".")[-1]
        return f"prepared a pawn lever on {sq}"
    
    # OUTPOSTS & HOLES
    if "outpost.knight" in tag_name:
        sq = tag_name.split(".")[-1] if "." in tag_name else "?"
        return f"established a knight outpost on {sq}"
    
    if "color.hole" in tag_name:
        color = "dark" if "dark" in tag_name else "light"
        sq = tag_name.split(".")[-1] if "." in tag_name else "?"
        return f"created a {color}-square weakness near {sq}"
    
    # BISHOP
    if "bishop.pair" in tag_name:
        return "maintained the bishop pair advantage"
    
    if "bishop.bad" in tag_name:
        return "created a bad bishop (locked by own pawns)"
    
    # PIECE PROBLEMS
    if "piece.trapped" in tag_name:
        piece_sq = pieces[0] if pieces else "piece"
        return f"trapped the {piece_sq}"
    
    # ACTIVITY
    if "activity.mobility.knight" in tag_name:
        return "activated the knight(s)"
    
    if "activity.mobility.bishop" in tag_name:
        return "activated the bishop(s)"
    
    if "activity.mobility.rook" in tag_name:
        return "activated the rook(s)"
    
    if "activity.mobility.queen" in tag_name:
        return "activated the queen"
    
    # FALLBACK: Make it readable
    readable = tag_name.replace("tag.", "").replace("_", " ").replace(".", " ")
    return readable


def compare_tags_for_move_analysis(af_before: Dict, af_after: Dict, side: str) -> Dict:
    """
    Compare tags between two positions and describe what changed in natural English.
    Used for move analysis to show what a move accomplished.
    
    Args:
        af_before: analyze_fen result before move
        af_after: analyze_fen result after move
        side: "white" or "black" (side that made the move)
    
    Returns:
        {
            "tags_gained": ["control the center", "place rook on open file"],
            "tags_lost": ["king center exposed", "piece trapped"],
            "theme_changes": {"center_space": +2.5, "king_safety": +1.0},
            "summary": "Improved center control and king safety"
        }
    """
    tags_before = af_before.get("tags", [])
    tags_after = af_after.get("tags", [])
    
    tags_before_names = {t.get("tag_name") for t in tags_before}
    tags_after_names = {t.get("tag_name") for t in tags_after}
    
    # Find gained and lost tag objects (not just names)
    gained_tags = [t for t in tags_after if t.get("tag_name") not in tags_before_names]
    lost_tags = [t for t in tags_before if t.get("tag_name") not in tags_after_names]
    
    # Special handling for diagonal tags: detect if diagonal was opened vs piece placed on open diagonal
    # Extract diagonal names (without piece info) to check if diagonal was already open
    before_diag_names = set()
    for tag in tags_before:
        tag_name = tag.get("tag_name", "")
        if "diagonal.open." in tag_name:
            # Extract diagonal identifier (e.g., "d5-a2" or "long.a1h8")
            parts = tag_name.split(".")
            if "long" in parts:
                diag_id = "long." + ("a1h8" if "a1h8" in tag_name else "h1a8")
            else:
                diag_id = parts[-1] if len(parts) >= 3 else ""
            if diag_id:
                before_diag_names.add(diag_id)
    
    # Convert to natural language descriptions using tag metadata
    tags_gained_descriptions = []
    for tag in gained_tags[:5]:
        tag_name = tag.get("tag_name", "")
        # Check if this is a diagonal tag
        if "diagonal.open." in tag_name:
            # Extract diagonal identifier
            parts = tag_name.split(".")
            if "long" in parts:
                diag_id = "long." + ("a1h8" if "a1h8" in tag_name else "h1a8")
            else:
                diag_id = parts[-1] if len(parts) >= 3 else ""
            
            # If diagonal wasn't open before, say "opened the diagonal"
            if diag_id and diag_id not in before_diag_names:
                if "long.a1h8" in diag_id:
                    tags_gained_descriptions.append("opened the a1-h8 diagonal")
                elif "long.h1a8" in diag_id:
                    tags_gained_descriptions.append("opened the h1-a8 diagonal")
                elif diag_id:
                    tags_gained_descriptions.append(f"opened the {diag_id} diagonal")
                else:
                    tags_gained_descriptions.append("opened a diagonal")
            else:
                # Diagonal was already open, piece was placed on it
                desc = tag_to_natural_description(tag)
                if desc:
                    tags_gained_descriptions.append(desc)
        else:
            # Non-diagonal tag, use normal description
            desc = tag_to_natural_description(tag)
            if desc:
                tags_gained_descriptions.append(desc)
    
    tags_gained = [d for d in tags_gained_descriptions if d and not d.startswith("tag.")]  # Filter empty and unconverted
    
    # Only describe bad tags that were lost (improvements)
    bad_tags_lost = [t for t in lost_tags if is_bad_tag(t.get("tag_name", ""))]
    tags_lost = [tag_to_natural_description(tag) for tag in bad_tags_lost[:5]]
    tags_lost = [d for d in tags_lost if d and not d.startswith("tag.")]  # Filter empty and unconverted
    
    # Theme score changes
    theme_scores_before = af_before.get("theme_scores", {}).get(side, {})
    theme_scores_after = af_after.get("theme_scores", {}).get(side, {})
    
    theme_changes = {}
    for theme_key in set(list(theme_scores_before.keys()) + list(theme_scores_after.keys())):
        if theme_key != "total":
            before_score = theme_scores_before.get(theme_key, 0)
            after_score = theme_scores_after.get(theme_key, 0)
            delta = after_score - before_score
            if abs(delta) > 0.5:
                theme_changes[theme_key] = delta
    
    # Generate summary
    if tags_gained and tags_lost:
        summary = f"Gained: {', '.join(tags_gained[:2])}. Fixed: {', '.join(tags_lost[:2])}"
    elif tags_gained:
        summary = f"Gained: {', '.join(tags_gained[:3])}"
    elif tags_lost:
        summary = f"Fixed: {', '.join(tags_lost[:2])}"
    elif theme_changes:
        top_change = max(theme_changes.items(), key=lambda x: abs(x[1]))
        summary = f"{'Improved' if top_change[1] > 0 else 'Weakened'} {top_change[0].replace('_', ' ')}"
    else:
        summary = "Minor positional adjustments"
    
    return {
        "tags_gained": tags_gained[:5],
        "tags_lost": tags_lost[:5],
        "theme_changes": theme_changes,
        "summary": summary
    }


def format_delta_for_display(delta_data: Dict) -> str:
    """
    Format delta analysis for display purposes.
    
    Args:
        delta_data: Delta analysis for one side
        
    Returns:
        Formatted string
    """
    plan_type = delta_data["plan_type"]
    mat_delta = delta_data["material_delta_cp"]
    pos_delta = delta_data["positional_delta_cp"]
    explanation = delta_data["plan_explanation"]
    
    theme_deltas = delta_data["theme_deltas"]
    significant_changes = [(k, v) for k, v in theme_deltas.items() if abs(v) > 1.0]
    significant_changes.sort(key=lambda x: abs(x[1]), reverse=True)
    
    output = f"""
Plan Type: {plan_type.replace('_', ' ').title()}
Material Change: {mat_delta:+d}cp
Positional Change: {pos_delta:+d}cp

Explanation: {explanation}

Key Theme Changes:
"""
    
    for theme, delta in significant_changes[:5]:
        direction = "↑" if delta > 0 else "↓"
        output += f"  {direction} {theme}: {delta:+.2f}\n"
    
    return output.strip()

