#!/usr/bin/env python3
"""
Extract and format PGN documentation from investigation results.

This script extracts the PGN from InvestigationResult objects and creates
a comprehensive document showing all branches, annotations, and move details.
"""

import sys
import os
from pathlib import Path
import chess
import chess.pgn
from io import StringIO
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

def parse_pgn_with_annotations(pgn_string: str) -> dict:
    """
    Parse PGN string and extract all annotations, branches, and move details.
    
    Returns:
        dict with:
            - headers: dict of PGN headers
            - starting_comment: comment on the game node
            - moves: list of move dicts with annotations
            - branches: list of branch dicts
    """
    if not pgn_string or not pgn_string.strip():
        return {
            "headers": {},
            "starting_comment": "",
            "moves": [],
            "branches": []
        }
    
    try:
        game = chess.pgn.read_game(StringIO(pgn_string))
        if not game:
            return {
                "headers": {},
                "starting_comment": "",
                "moves": [],
                "branches": []
            }
        
        result = {
            "headers": dict(game.headers),
            "starting_comment": game.comment or "",
            "moves": [],
            "branches": []
        }
        
        def extract_move_info(node, move_number=1, is_variation=False, parent_move=None):
            """Recursively extract move information from PGN tree."""
            if node.move:
                move_info = {
                    "move_number": move_number,
                    "move_san": node.san() if hasattr(node, 'san') else str(node.move),
                    "move_uci": node.move.uci(),
                    "comment": node.comment or "",
                    "is_variation": is_variation,
                    "parent_move": parent_move,
                    "eval": None,
                    "theme": None,
                    "tactic": None,
                    "tags_gained": [],
                    "tags_lost": [],
                    "threats": [],
                    "variations": []
                }
                
                # Parse comment for annotations
                comment = node.comment or ""
                
                # Extract eval
                import re
                eval_match = re.search(r'\[%eval\s+([+-]?\d+\.?\d*)\]', comment)
                if eval_match:
                    move_info["eval"] = float(eval_match.group(1))
                
                # Extract theme
                theme_match = re.search(r'\[%theme\s+"([^"]+)"\]', comment)
                if theme_match:
                    move_info["theme"] = theme_match.group(1)
                
                # Extract tactic
                tactic_match = re.search(r'\[%tactic\s+"([^"]+)"\]', comment)
                if tactic_match:
                    move_info["tactic"] = tactic_match.group(1)
                
                # Extract tags gained/lost/threats from commentary
                gained_match = re.search(r'\[gained:\s+([^\]]+)\]', comment)
                if gained_match:
                    gained_str = gained_match.group(1)
                    if gained_str != "none":
                        move_info["tags_gained"] = [t.strip() for t in gained_str.split(",")]
                
                lost_match = re.search(r'\[lost:\s+([^\]]+)\]', comment)
                if lost_match:
                    lost_str = lost_match.group(1)
                    if lost_str != "none":
                        move_info["tags_lost"] = [t.strip() for t in lost_str.split(",")]
                
                threat_match = re.search(r'\[threats:\s+([^\]]+)\]', comment)
                if threat_match:
                    threat_str = threat_match.group(1)
                    if threat_str != "none":
                        move_info["threats"] = [t.strip() for t in threat_str.split(",")]
                
                # Process variations (branches)
                for variation in node.variations:
                    var_info = extract_move_info(
                        variation,
                        move_number=move_number,
                        is_variation=True,
                        parent_move=move_info["move_san"]
                    )
                    move_info["variations"].append(var_info)
                    if is_variation:
                        result["branches"].append(var_info)
                
                if not is_variation:
                    result["moves"].append(move_info)
                
                # Process next move in main line
                if node.variations:
                    # If there are variations, the next main move is the first variation's continuation
                    # But we want the actual main line continuation
                    pass
                
                next_node = node.next()
                if next_node and not is_variation:
                    extract_move_info(next_node, move_number + 1, is_variation=False)
            
            return move_info
        
        # Start extraction from first move
        if game.next():
            extract_move_info(game.next(), move_number=1, is_variation=False)
        
        return result
    
    except Exception as e:
        print(f"Error parsing PGN: {e}")
        import traceback
        traceback.print_exc()
        return {
            "headers": {},
            "starting_comment": "",
            "moves": [],
            "branches": []
        }


def format_pgn_documentation(pgn_data: dict, pgn_string: str = "") -> str:
    """
    Format PGN data into a comprehensive markdown document.
    
    Args:
        pgn_data: Parsed PGN data from parse_pgn_with_annotations
        pgn_string: Original PGN string (for raw output)
    
    Returns:
        Formatted markdown string
    """
    doc = []
    doc.append("# Investigation PGN Documentation")
    doc.append("")
    doc.append(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
    doc.append("")
    
    # Headers
    if pgn_data["headers"]:
        doc.append("## PGN Headers")
        doc.append("")
        for key, value in pgn_data["headers"].items():
            doc.append(f"- **{key}**: {value}")
        doc.append("")
    
    # Starting position comment
    if pgn_data["starting_comment"]:
        doc.append("## Starting Position")
        doc.append("")
        doc.append(f"**Tags**: {pgn_data['starting_comment']}")
        doc.append("")
    
    # Main line moves
    doc.append("## Main Line (Principal Variation)")
    doc.append("")
    
    if not pgn_data["moves"]:
        doc.append("*No moves in main line.*")
        doc.append("")
    else:
        for move_info in pgn_data["moves"]:
            move_num = move_info["move_number"]
            move_san = move_info["move_san"]
            
            move_line = f"**{move_num}. {move_san}**"
            
            # Add annotations
            annotations = []
            if move_info["eval"] is not None:
                annotations.append(f"Eval: {move_info['eval']:+.2f}")
            if move_info["theme"]:
                annotations.append(f"Theme: {move_info['theme']}")
            if move_info["tactic"] and move_info["tactic"] != "none":
                annotations.append(f"Tactic: {move_info['tactic']}")
            
            if annotations:
                move_line += f" *({', '.join(annotations)})*"
            
            doc.append(move_line)
            
            # Add tag changes
            if move_info["tags_gained"] or move_info["tags_lost"] or move_info["threats"]:
                doc.append("  - **Tag Changes:**")
                if move_info["tags_gained"]:
                    doc.append(f"    - Gained: {', '.join(move_info['tags_gained'][:10])}")
                if move_info["tags_lost"]:
                    doc.append(f"    - Lost: {', '.join(move_info['tags_lost'][:10])}")
                if move_info["threats"]:
                    doc.append(f"    - Threats: {', '.join(move_info['threats'][:5])}")
            
            # Add comment if present and not already covered
            if move_info["comment"] and not any(x in move_info["comment"] for x in ["[%eval", "[%theme", "[%tactic", "[gained:", "[lost:", "[threats:"]):
                doc.append(f"  - **Note**: {move_info['comment']}")
            
            # Add variations (branches) at this move
            if move_info["variations"]:
                doc.append("  - **Branches:**")
                for var in move_info["variations"]:
                    var_line = f"    - {var['move_san']}"
                    if var["eval"] is not None:
                        var_line += f" (Eval: {var['eval']:+.2f})"
                    if var["theme"]:
                        var_line += f" - {var['theme']}"
                    doc.append(var_line)
                    if var["comment"]:
                        doc.append(f"      *{var['comment']}*")
            
            doc.append("")
    
    # Branches section
    if pgn_data["branches"]:
        doc.append("## Alternate Branches")
        doc.append("")
        doc.append("These are moves that were explored as variations (overestimated moves or stopped branches).")
        doc.append("")
        
        for idx, branch in enumerate(pgn_data["branches"], 1):
            doc.append(f"### Branch {idx}: {branch['move_san']}")
            doc.append("")
            
            if branch["eval"] is not None:
                doc.append(f"- **Evaluation**: {branch['eval']:+.2f}")
            if branch["theme"]:
                doc.append(f"- **Theme**: {branch['theme']}")
            if branch["tactic"] and branch["tactic"] != "none":
                doc.append(f"- **Tactic**: {branch['tactic']}")
            if branch["comment"]:
                doc.append(f"- **Comment**: {branch['comment']}")
            
            if branch["tags_gained"] or branch["tags_lost"] or branch["threats"]:
                doc.append("- **Tag Changes:**")
                if branch["tags_gained"]:
                    doc.append(f"  - Gained: {', '.join(branch['tags_gained'][:10])}")
                if branch["tags_lost"]:
                    doc.append(f"  - Lost: {', '.join(branch['tags_lost'][:10])}")
                if branch["threats"]:
                    doc.append(f"  - Threats: {', '.join(branch['threats'][:5])}")
            
            doc.append("")
    
    # Raw PGN
    if pgn_string:
        doc.append("## Raw PGN")
        doc.append("")
        doc.append("```pgn")
        doc.append(pgn_string)
        doc.append("```")
        doc.append("")
    
    return "\n".join(doc)


def create_documentation_from_pgn(pgn_string: str, output_file: str = "INVESTIGATION_PGN_EXTRACTED.md"):
    """
    Create a documentation file from a PGN string.
    
    Args:
        pgn_string: The PGN string to parse
        output_file: Output file path (default: INVESTIGATION_PGN_EXTRACTED.md)
    """
    print(f"Parsing PGN ({len(pgn_string)} chars)...")
    pgn_data = parse_pgn_with_annotations(pgn_string)
    
    print(f"Formatting documentation...")
    doc = format_pgn_documentation(pgn_data, pgn_string)
    
    output_path = Path(__file__).parent.parent.parent / output_file
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(doc)
    
    print(f"Documentation written to: {output_path}")
    print(f"  - {len(pgn_data['moves'])} main line moves")
    print(f"  - {len(pgn_data['branches'])} branches")
    return output_path


def main():
    """Main function to extract PGN from investigation results."""
    import sys
    
    if len(sys.argv) > 1:
        # PGN string provided as argument
        pgn_string = sys.argv[1]
        create_documentation_from_pgn(pgn_string)
    else:
        print("PGN Documentation Extractor")
        print("=" * 50)
        print()
        print("This script extracts PGN from InvestigationResult objects.")
        print()
        print("Usage:")
        print("  python extract_pgn_documentation.py '<pgn_string>'")
        print()
        print("Or import and use the functions:")
        print("  from extract_pgn_documentation import parse_pgn_with_annotations, format_pgn_documentation, create_documentation_from_pgn")
        print("  create_documentation_from_pgn(pgn_string, 'output.md')")
        print()
        print("Example:")
        print("  # In Python:")
        print("  from backend.scripts.extract_pgn_documentation import create_documentation_from_pgn")
        print("  create_documentation_from_pgn(investigation_result.pgn_exploration)")
        print()


if __name__ == "__main__":
    main()

