"""
Mini lesson generation from confidence tree low-confidence sublines.
Extracts key information about fake refutations and line alternates.
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import json

from tag_analyzer import TagTracker, TagInstance


@dataclass
class Subline:
    """Represents a low-confidence subline from the confidence tree."""
    starting_node_id: str
    branch_path: List[str]
    terminal_confidence: int
    key_moves: List[str]  # UCI moves along the branch
    starting_ply: int
    terminal_ply: int
    starting_fen: str
    terminal_fen: str
    tags_at_start: List[str]
    tags_at_terminal: List[str]


def identify_convincing_sublines(nodes: List[Any], baseline: int) -> List[Subline]:
    """
    Identify triangles (branch nodes) with low initial confidence that have children.
    These represent alternate moves that look promising but lead to low confidence.
    
    Args:
        nodes: List of NodeState objects from confidence tree
        baseline: Confidence threshold
        
    Returns:
        List of Subline objects representing problematic alternate lines
    """
    sublines = []
    node_by_id = {node.id: node for node in nodes}
    
    # Find triangles (nodes with branches) that have low initial confidence
    # These are the alternate moves we want to analyze
    for node in nodes:
        # Target: triangles (nodes with branches) that have low initial confidence
        if node.has_branches and node.initial_confidence is not None:
            if node.initial_confidence < baseline:
                # This is a triangle with low initial confidence - it's a problematic alternate
                # Check if it has children (branches extended from it)
                has_children = any(n.parent_id == node.id for n in nodes)
                
                if has_children:
                    # Get the terminal confidence (minimum of all branch terminals)
                    terminal_conf = (
                        node.frozen_confidence 
                        if node.frozen_confidence is not None
                        else node.confidence
                    )
                    
                    # Get branch path from PV to this node
                    branch_path = _get_branch_path_to_node(node, node_by_id)
                    key_moves = _extract_moves_from_path(branch_path, node_by_id)
                    
                    # Get tags at this node (where the alternate diverges)
                    tags_at_node = node.metadata.get("tags", [])
                    
                    # Get tags from children to see what's lost/gained
                    children = [n for n in nodes if n.parent_id == node.id]
                    child_tags = []
                    for child in children:
                        child_tags.extend(child.metadata.get("tags", []))
                    
                    # Get the move that leads to this alternate (the first move in the branch)
                    alternate_move = key_moves[0] if key_moves else None
                    if not alternate_move and node.move:
                        alternate_move = node.move
                    
                    subline = Subline(
                        starting_node_id=node.id,
                        branch_path=branch_path,
                        terminal_confidence=terminal_conf,
                        key_moves=key_moves if key_moves else ([node.move] if node.move else []),
                        starting_ply=node.ply_index,
                        terminal_ply=node.ply_index,  # The triangle itself is the focus
                        starting_fen=node.fen,
                        terminal_fen=node.fen,  # Focus on the position where alternate diverges
                        tags_at_start=[t.get("tag_name", "") for t in tags_at_node if isinstance(t, dict)],
                        tags_at_terminal=[t.get("tag_name", "") for t in child_tags if isinstance(t, dict)]
                    )
                    sublines.append(subline)
    
    # Sort by initial confidence (lowest first - most problematic)
    sublines.sort(key=lambda s: node_by_id.get(s.starting_node_id).initial_confidence if node_by_id.get(s.starting_node_id) else s.terminal_confidence)
    
    return sublines


def _get_branch_path_to_node(node: Any, node_by_id: Dict[str, Any]) -> List[str]:
    """Get the path from PV to this node."""
    path = []
    current = node
    
    while current and current.parent_id:
        path.insert(0, current.id)
        current = node_by_id.get(current.parent_id)
        # Stop if we reach a PV node
        if current and (current.role == "pv" or current.id.startswith("pv-")):
            break
    
    return path


def _extract_moves_from_path(path: List[str], node_by_id: Dict[str, Any]) -> List[str]:
    """Extract UCI moves from a node path."""
    moves = []
    for node_id in path:
        node = node_by_id.get(node_id)
        if node and hasattr(node, 'move') and node.move:
            moves.append(node.move)
    return moves


def extract_lesson_content(sublines: List[Subline], tag_tracker: TagTracker, nodes: List[Any], baseline: int = 80) -> Dict[str, Any]:
    """
    Extract key information from sublines for lesson generation.
    Focuses on triangles with low initial confidence and explains why alternates aren't as good.
    
    Args:
        sublines: List of identified low-confidence sublines (triangles with low initial confidence)
        tag_tracker: TagTracker instance with tag data
        nodes: List of all NodeState objects
        
    Returns:
        Dictionary with structured lesson content
    """
    node_by_id = {node.id: node for node in nodes}
    lesson_content = {
        "sublines": [],
        "key_candidate_moves": [],
        "fake_refutations": [],
        "line_alternates": [],
        "tag_insights": []
    }
    
    for subline in sublines:
        # Get the triangle node (where alternate diverges)
        triangle_node = node_by_id.get(subline.starting_node_id)
        if not triangle_node:
            continue
        
        # Get the alternate move (the move that leads to this triangle)
        alternate_move = subline.key_moves[0] if subline.key_moves else triangle_node.move
        
        # Get parent node to find what the PV move was (the better alternative)
        parent_node = None
        pv_move = None
        if triangle_node.parent_id:
            parent_node = node_by_id.get(triangle_node.parent_id)
            if parent_node:
                # Find the PV move from parent (the move that maintains confidence)
                # Look for PV nodes that are children of parent
                pv_children = [n for n in nodes if n.parent_id == parent_node.id and (n.role == "pv" or n.id.startswith("pv-"))]
                if pv_children:
                    pv_child = pv_children[0]
                    pv_move = pv_child.move
        
        # Get children of this triangle to see what happens after the alternate
        children = [n for n in nodes if n.parent_id == triangle_node.id]
        
        # Analyze why the alternate is problematic
        initial_conf = triangle_node.initial_confidence
        frozen_conf = triangle_node.frozen_confidence if triangle_node.frozen_confidence is not None else triangle_node.confidence
        
        # Tags analysis: what tags are present at triangle vs what's lost
        tags_at_triangle = set(subline.tags_at_start)
        tags_in_branches = set(subline.tags_at_terminal)
        tags_lost = list(tags_at_triangle - tags_in_branches)
        tags_gained = list(tags_in_branches - tags_at_triangle)
        
        # Build explanation
        why_problematic = f"This alternate move leads to only {initial_conf}% initial confidence (below {baseline}% baseline). "
        if frozen_conf is not None and frozen_conf < baseline:
            why_problematic += f"After exploring branches, the confidence remains low at {frozen_conf}%. "
        if tags_lost:
            why_problematic += f"Key positional advantages are lost: {', '.join(tags_lost[:3])}. "
        if pv_move:
            why_problematic += f"The PV move {pv_move} maintains higher confidence."
        
        lesson_content["fake_refutations"].append({
            "position_fen": triangle_node.fen,
            "move": alternate_move,
            "initial_confidence": initial_conf,
            "frozen_confidence": frozen_conf,
            "why_problematic": why_problematic,
            "terminal_confidence": frozen_conf,
            "branch_length": len(children),
            "tags_lost": tags_lost,
            "tags_gained": tags_gained,
            "better_alternative": pv_move,
            "children_count": len(children)
        })
        
        lesson_content["sublines"].append({
            "starting_node_id": subline.starting_node_id,
            "branch_path": subline.branch_path,
            "terminal_confidence": subline.terminal_confidence,
            "initial_confidence": initial_conf,
            "key_moves": subline.key_moves,
            "starting_ply": subline.starting_ply,
            "terminal_ply": subline.terminal_ply,
            "starting_fen": subline.starting_fen,
            "terminal_fen": subline.terminal_fen
        })
    
    # Analyze tag insights
    tag_relevance = tag_tracker.analyze_tag_relevance(baseline=80)  # Default baseline
    lesson_content["tag_insights"] = {
        "critical_tags": tag_relevance.get("critical_tags", [])[:5],  # Top 5
        "branching_tags": tag_relevance.get("branching_tags", [])[:5],
        "confidence_correlated_tags": tag_relevance.get("confidence_correlated_tags", [])[:5]
    }
    
    return lesson_content


def generate_mini_lesson(lesson_content: Dict[str, Any], nodes: List[Any], baseline: int = 80) -> Dict[str, Any]:
    """
    Generate interactive walkthrough structure from lesson content.
    
    Args:
        lesson_content: Dictionary from extract_lesson_content
        nodes: List of all NodeState objects
        
    Returns:
        Lesson plan compatible with existing lesson system
    """
    node_by_id = {node.id: node for node in nodes}
    steps = []
    
    # Create a step for each fake refutation (triangle with low initial confidence)
    for idx, refutation in enumerate(lesson_content.get("fake_refutations", []), 1):
        better_alternatives = []
        if refutation.get("better_alternative"):
            better_alternatives.append(refutation["better_alternative"])
        
        hints = [
            f"Initial confidence: {refutation.get('initial_confidence', 'N/A')}% (below {baseline}% baseline)",
            f"After exploring {refutation.get('children_count', 0)} branch(es), confidence: {refutation.get('frozen_confidence', refutation.get('terminal_confidence', 'N/A'))}%"
        ]
        
        if refutation.get("tags_lost"):
            hints.append(f"Positional advantages lost: {', '.join(refutation['tags_lost'][:3])}")
        
        if refutation.get("better_alternative"):
            hints.append(f"Better alternative: {refutation['better_alternative']} maintains higher confidence")
        
        step = {
            "step_number": idx,
            "position_fen": refutation["position_fen"],
            "move_to_analyze": refutation["move"],
            "title": f"Problematic Alternate #{idx}: {refutation['move']}",
            "explanation": refutation["why_problematic"],
            "better_alternatives": better_alternatives,
            "tag_insights": {
                "tags_lost": refutation.get("tags_lost", []),
                "tags_gained": refutation.get("tags_gained", []),
                "initial_confidence": refutation.get("initial_confidence"),
                "frozen_confidence": refutation.get("frozen_confidence")
            },
            "objective": f"Understand why {refutation['move']} leads to low confidence ({refutation.get('initial_confidence', 'N/A')}%) and identify the better alternative",
            "hints": hints,
            "candidates": better_alternatives
        }
        steps.append(step)
    
    # If no fake refutations, create steps from sublines
    if not steps:
        for idx, subline in enumerate(lesson_content.get("sublines", [])[:3], 1):  # Limit to 3
            step = {
                "step_number": idx,
                "position_fen": subline["starting_fen"],
                "move_to_analyze": subline["key_moves"][0] if subline["key_moves"] else None,
                "title": f"Low Confidence Line #{idx}",
                "explanation": f"This line reaches only {subline['terminal_confidence']}% confidence",
                "better_alternates": [],
                "tag_insights": {},
                "objective": "Identify why this line is problematic",
                "hints": [
                    f"Terminal confidence: {subline['terminal_confidence']}%",
                    f"Branch length: {len(subline['branch_path'])} moves"
                ],
                "candidates": []
            }
            steps.append(step)
    
    lesson_plan = {
        "title": "Confidence Tree Analysis: Problematic Lines",
        "description": f"Interactive walkthrough of {len(steps)} low-confidence lines from the confidence tree",
        "sections": [
            {
                "title": "Fake Refutations and Line Alternates",
                "description": "Explore moves that look promising but lead to low confidence",
                "positions": steps
            }
        ],
        "total_steps": len(steps),
        "tag_insights": lesson_content.get("tag_insights", {})
    }
    
    return lesson_plan


async def generate_confidence_lesson(
    nodes: List[Any],
    baseline: int = 80,
    tag_tracker: Optional[TagTracker] = None
) -> Dict[str, Any]:
    """
    Main entry point for generating a mini lesson from confidence tree.
    
    Args:
        nodes: List of NodeState objects from confidence tree
        baseline: Confidence threshold
        tag_tracker: Optional TagTracker (will create if not provided)
        
    Returns:
        Complete lesson plan ready for frontend
    """
    # Identify low-confidence sublines
    sublines = identify_convincing_sublines(nodes, baseline)
    
    if not sublines:
        return {
            "title": "No Problematic Lines Found",
            "description": "All branches meet the confidence baseline",
            "sections": [],
            "total_steps": 0
        }
    
    # Create tag tracker if not provided
    if tag_tracker is None:
        from tag_analyzer import track_tag_across_branches
        tag_tracker = track_tag_across_branches(nodes)
    
    # Extract lesson content
    lesson_content = extract_lesson_content(sublines, tag_tracker, nodes, baseline)
    
    # Generate interactive walkthrough
    lesson_plan = generate_mini_lesson(lesson_content, nodes, baseline)
    
    return lesson_plan

