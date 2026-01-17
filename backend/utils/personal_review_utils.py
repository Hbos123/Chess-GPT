"""
Shared utilities for Personal Review System
Tag extraction, filtering, validation functions
"""

from typing import List, Dict, Any, Optional, Tuple, Set
import chess.pgn
from io import StringIO
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.personal_review_config import config


def extract_tags(record: Dict[str, Any]) -> List[str]:
    """
    Unified tag extraction from a ply record.
    Handles both dict and string tag formats.
    
    Args:
        record: Ply record dictionary
        
    Returns:
        List of tag names as strings
    """
    tags = []
    
    # Try analyse.tags first (most common)
    analyse = record.get("analyse", {})
    if isinstance(analyse, dict):
        tag_list = analyse.get("tags", [])
        tags.extend(extract_tag_names(tag_list))
    
    # Also check raw_before and raw_after for position tags
    raw_before = record.get("raw_before", {})
    if isinstance(raw_before, dict):
        tag_list = raw_before.get("tags", [])
        tags.extend(extract_tag_names(tag_list))
    
    raw_after = record.get("raw_after", {})
    if isinstance(raw_after, dict):
        tag_list = raw_after.get("tags", [])
        tags.extend(extract_tag_names(tag_list))
    
    return list(set(tags))  # Remove duplicates


def extract_tag_names(tags: List[Any]) -> Set[str]:
    """
    Extract tag names from a list of tags (handles dict and string formats).
    
    Args:
        tags: List of tags (can be strings or dicts)
        
    Returns:
        Set of tag name strings
    """
    tag_names = set()
    
    for tag in tags:
        if isinstance(tag, dict):
            # Try different possible keys
            name = tag.get("tag_name") or tag.get("name") or tag.get("tag")
            if name:
                tag_names.add(str(name))
        elif isinstance(tag, str):
            tag_names.add(tag)
    
    return tag_names


def validate_pgn(pgn: str) -> Tuple[bool, Optional[str]]:
    """
    Validate PGN string.
    
    Args:
        pgn: PGN string to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not pgn or not isinstance(pgn, str):
        return False, "PGN is empty or not a string"
    
    if len(pgn.strip()) < 10:
        return False, "PGN is too short"
    
    try:
        # Try to parse the PGN
        pgn_io = StringIO(pgn)
        game = chess.pgn.read_game(pgn_io)
        
        if game is None:
            return False, "Failed to parse PGN - no game found"
        
        # Check if game has moves
        board = game.board()
        move_count = 0
        for move in game.mainline_moves():
            move_count += 1
            board.push(move)
            if move_count > 1000:  # Safety limit
                break
        
        if move_count < 2:
            return False, "PGN has too few moves (< 2)"
        
        return True, None
    
    except Exception as e:
        return False, f"PGN parsing error: {str(e)}"


def validate_game_data(game: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate game data structure and content.
    
    Args:
        game: Game dictionary
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check required fields
    if not isinstance(game, dict):
        return False, "Game is not a dictionary"
    
    # Validate PGN
    pgn = game.get("pgn", "")
    pgn_valid, pgn_error = validate_pgn(pgn)
    if not pgn_valid:
        return False, f"Invalid PGN: {pgn_error}"
    
    # Validate metadata
    player_rating = game.get("player_rating", 0)
    if not isinstance(player_rating, (int, float)) or player_rating < 0 or player_rating > 4000:
        return False, f"Invalid player_rating: {player_rating}"
    
    opponent_rating = game.get("opponent_rating", 0)
    if not isinstance(opponent_rating, (int, float)) or opponent_rating < 0 or opponent_rating > 4000:
        return False, f"Invalid opponent_rating: {opponent_rating}"
    
    # Validate result
    result = game.get("result", "unknown")
    if result not in ["win", "loss", "draw", "unknown"]:
        return False, f"Invalid result: {result}"
    
    # Validate player_color
    player_color = game.get("player_color", "white")
    if player_color not in ["white", "black"]:
        return False, f"Invalid player_color: {player_color}"
    
    return True, None


def normalize_game_metadata(game: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize game metadata to standard format.
    
    Args:
        game: Raw game dictionary
        
    Returns:
        Normalized game metadata dictionary
    """
    return {
        "game_id": game.get("game_id") or game.get("id"),
        "platform": game.get("platform", "chess.com"),
        "player_rating": int(game.get("player_rating", 0)),
        "opponent_rating": int(game.get("opponent_rating", 0)),
        "result": game.get("result", "unknown"),
        "player_color": game.get("player_color", "white"),
        "time_category": game.get("time_category"),
        "date": game.get("date"),
        "pgn": game.get("pgn", ""),
        "has_clock": game.get("has_clock", False),
        "opening": game.get("opening"),
    }


class GameFilter:
    """Filter application logic for games"""
    
    @staticmethod
    def apply_filters(games: List[Dict[str, Any]], filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Apply filters to game list.
        
        Args:
            games: List of game dictionaries
            filters: Filter specification dictionary
            
        Returns:
            Filtered list of games
        """
        filtered = games
        
        if "rating_min" in filters and filters["rating_min"] is not None:
            min_rating = filters["rating_min"]
            filtered = [
                g for g in filtered 
                if g.get("metadata", {}).get("player_rating", 0) >= min_rating
                or g.get("player_rating", 0) >= min_rating
            ]
        
        if "rating_max" in filters and filters["rating_max"] is not None:
            max_rating = filters["rating_max"]
            filtered = [
                g for g in filtered 
                if (g.get("metadata", {}).get("player_rating", 9999) <= max_rating
                    or g.get("player_rating", 9999) <= max_rating)
            ]
        
        if "result" in filters and filters["result"]:
            result = filters["result"]
            filtered = [
                g for g in filtered 
                if (g.get("metadata", {}).get("result") == result
                    or g.get("result") == result)
            ]
        
        if "player_color" in filters and filters["player_color"]:
            color = filters["player_color"]
            filtered = [
                g for g in filtered 
                if (g.get("metadata", {}).get("player_color") == color
                    or g.get("player_color") == color)
            ]
        
        if "time_category" in filters and filters["time_category"]:
            tc = filters["time_category"]
            filtered = [
                g for g in filtered 
                if (g.get("metadata", {}).get("time_category") == tc
                    or g.get("time_category") == tc)
            ]
        
        if "opening_eco" in filters and filters["opening_eco"]:
            eco = filters["opening_eco"]
            filtered = [
                g for g in filtered 
                if (g.get("opening", {}).get("eco_final", "").startswith(eco)
                    or g.get("metadata", {}).get("opening", "").startswith(eco))
            ]
        
        return filtered


def validate_analysis_quality(analysis_result: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate analysis result quality.
    
    Args:
        analysis_result: Analysis result dictionary
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if "error" in analysis_result:
        return False, analysis_result.get("error", "Analysis error")
    
    ply_records = analysis_result.get("ply_records", [])
    
    if len(ply_records) < config.MIN_MOVE_COUNT:
        return False, f"Too few moves analyzed: {len(ply_records)} < {config.MIN_MOVE_COUNT}"
    
    # Check eval ranges
    for record in ply_records[:10]:  # Sample first 10
        eval_after = record.get("eval_after_cp", 0)
        if isinstance(eval_after, (int, float)):
            if eval_after < config.MIN_EVAL_CP or eval_after > config.MAX_EVAL_CP:
                return False, f"Invalid eval value: {eval_after}"
    
    # Check required fields
    required_fields = ["side_moved", "san", "accuracy_pct"]
    for record in ply_records[:5]:  # Sample first 5
        for field in required_fields:
            if field not in record:
                return False, f"Missing required field: {field}"
    
    return True, None

