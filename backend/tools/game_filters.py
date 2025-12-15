"""
Game Filters Tool
Enhanced game fetching with advanced filtering capabilities
Extends existing GameFetcher functionality
"""

from typing import Dict, List, Optional, Literal
from datetime import datetime
import re


async def fetch_games_filtered(
    username: str,
    platform: Literal["chess.com", "lichess"] = "chess.com",
    date_from: str = None,
    date_to: str = None,
    opponent: str = None,
    opening_eco: str = None,
    time_control: str = None,
    result: str = None,
    min_opponent_rating: int = None,
    max_opponent_rating: int = None,
    color: str = None,
    min_moves: int = None,
    max_games: int = 50
) -> Dict:
    """
    Fetch games with advanced filtering.
    
    Args:
        username: Player username
        platform: chess.com or lichess
        date_from: Start date (YYYY-MM-DD)
        date_to: End date (YYYY-MM-DD)
        opponent: Filter by specific opponent
        opening_eco: Filter by ECO code (e.g., "B50", "E4")
        time_control: bullet/blitz/rapid/classical
        result: win/loss/draw
        color: white/black
        min_opponent_rating: Minimum opponent rating
        max_opponent_rating: Maximum opponent rating
        min_moves: Minimum game length
        max_games: Maximum games to return
        
    Returns:
        {
            "games": [
                {
                    "pgn": "...",
                    "white": "player1",
                    "black": "player2",
                    "result": "1-0",
                    "date": "2024-01-15",
                    "time_control": "blitz",
                    "opening_eco": "B50",
                    "white_rating": 2100,
                    "black_rating": 2050,
                    "url": "..."
                }
            ],
            "total_found": 150,
            "returned": 50,
            "filters_applied": ["date_range", "time_control"]
        }
    """
    try:
        # Import existing game fetcher
        from game_fetcher import GameFetcher
        
        fetcher = GameFetcher()
        
        # Build date range
        if date_from and date_to:
            # Fetch games in date range
            all_games = await _fetch_with_dates(fetcher, username, platform, date_from, date_to)
        else:
            # Fetch recent games
            all_games = await fetcher.fetch_games(
                username=username,
                platform=platform,
                max_games=max_games * 3  # Fetch more for filtering
            )
        
        if not all_games:
            return {
                "games": [],
                "total_found": 0,
                "returned": 0,
                "filters_applied": [],
                "error": "No games found"
            }
        
        # Apply filters
        filtered_games = all_games
        filters_applied = []
        
        if opponent:
            filtered_games = [g for g in filtered_games if _matches_opponent(g, opponent)]
            filters_applied.append("opponent")
        
        if opening_eco:
            filtered_games = [g for g in filtered_games if _matches_eco(g, opening_eco)]
            filters_applied.append("opening_eco")
        
        if time_control:
            filtered_games = [g for g in filtered_games if _matches_time_control(g, time_control)]
            filters_applied.append("time_control")
        
        if result:
            filtered_games = [g for g in filtered_games if _matches_result(g, result, username)]
            filters_applied.append("result")
        
        if color:
            filtered_games = [g for g in filtered_games if _matches_color(g, color, username)]
            filters_applied.append("color")
        
        if min_opponent_rating:
            filtered_games = [g for g in filtered_games if _check_opponent_rating(g, username, min_opponent_rating, "min")]
            filters_applied.append("min_opponent_rating")
        
        if max_opponent_rating:
            filtered_games = [g for g in filtered_games if _check_opponent_rating(g, username, max_opponent_rating, "max")]
            filters_applied.append("max_opponent_rating")
        
        if min_moves:
            filtered_games = [g for g in filtered_games if _check_game_length(g, min_moves)]
            filters_applied.append("min_moves")
        
        # Sort by date (newest first)
        filtered_games = sorted(
            filtered_games,
            key=lambda g: g.get("date", ""),
            reverse=True
        )
        
        # Limit results
        total_found = len(filtered_games)
        filtered_games = filtered_games[:max_games]
        
        return {
            "games": filtered_games,
            "total_found": total_found,
            "returned": len(filtered_games),
            "filters_applied": filters_applied
        }
        
    except Exception as e:
        return {
            "games": [],
            "total_found": 0,
            "returned": 0,
            "filters_applied": [],
            "error": str(e)
        }


async def _fetch_with_dates(
    fetcher,
    username: str,
    platform: str,
    date_from: str,
    date_to: str
) -> List[Dict]:
    """Fetch games within date range"""
    # Parse dates
    try:
        start = datetime.strptime(date_from, "%Y-%m-%d")
        end = datetime.strptime(date_to, "%Y-%m-%d")
    except:
        return []
    
    # Fetch games (fetcher handles pagination)
    all_games = await fetcher.fetch_games(
        username=username,
        platform=platform,
        max_games=500  # Fetch more for date filtering
    )
    
    # Filter by date
    filtered = []
    for game in all_games:
        game_date_str = game.get("date", "")
        if not game_date_str:
            continue
        
        try:
            game_date = datetime.strptime(game_date_str[:10], "%Y-%m-%d")
            if start <= game_date <= end:
                filtered.append(game)
        except:
            continue
    
    return filtered


def _matches_opponent(game: Dict, opponent: str) -> bool:
    """Check if game is against specific opponent"""
    white = game.get("white", "").lower()
    black = game.get("black", "").lower()
    opponent = opponent.lower()
    
    return opponent in white or opponent in black


def _matches_eco(game: Dict, eco_filter: str) -> bool:
    """Check if game matches ECO code"""
    game_eco = game.get("opening_eco", game.get("eco", "")).upper()
    eco_filter = eco_filter.upper()
    
    # Allow partial matches (e.g., "B5" matches "B50", "B51", etc.)
    return game_eco.startswith(eco_filter)


def _matches_time_control(game: Dict, time_control: str) -> bool:
    """Check if game matches time control category"""
    game_tc = game.get("time_control", "").lower()
    game_tc_type = game.get("time_control_type", "").lower()
    
    time_control = time_control.lower()
    
    # Check explicit type
    if game_tc_type:
        return time_control in game_tc_type
    
    # Parse time control string (e.g., "180+2", "600", "10|0")
    try:
        # Extract base time in seconds
        tc_clean = game_tc.replace("|", "+").split("+")[0]
        base_seconds = int(tc_clean)
        
        if time_control == "bullet":
            return base_seconds <= 60
        elif time_control == "blitz":
            return 60 < base_seconds <= 300
        elif time_control == "rapid":
            return 300 < base_seconds <= 1500
        elif time_control == "classical":
            return base_seconds > 1500
    except:
        pass
    
    return time_control in game_tc


def _matches_result(game: Dict, result: str, username: str) -> bool:
    """Check if game has specific result for the player"""
    game_result = game.get("result", "")
    white = game.get("white", "").lower()
    username = username.lower()
    
    player_is_white = username in white
    
    if result == "win":
        if player_is_white:
            return game_result == "1-0"
        else:
            return game_result == "0-1"
    elif result == "loss":
        if player_is_white:
            return game_result == "0-1"
        else:
            return game_result == "1-0"
    elif result == "draw":
        return game_result == "1/2-1/2"
    
    return False


def _matches_color(game: Dict, color: str, username: str) -> bool:
    """Check if player played specific color"""
    white = game.get("white", "").lower()
    black = game.get("black", "").lower()
    username = username.lower()
    
    if color == "white":
        return username in white
    elif color == "black":
        return username in black
    
    return False


def _check_opponent_rating(game: Dict, username: str, rating: int, check_type: str) -> bool:
    """Check opponent rating against threshold"""
    white = game.get("white", "").lower()
    username = username.lower()
    
    if username in white:
        opponent_rating = game.get("black_rating", 0)
    else:
        opponent_rating = game.get("white_rating", 0)
    
    if check_type == "min":
        return opponent_rating >= rating
    else:
        return opponent_rating <= rating


def _check_game_length(game: Dict, min_moves: int) -> bool:
    """Check if game has minimum number of moves"""
    # Try to count moves from PGN
    pgn = game.get("pgn", "")
    
    # Count move numbers in PGN
    move_numbers = re.findall(r'\d+\.', pgn)
    if move_numbers:
        return len(move_numbers) >= min_moves
    
    return True  # If can't determine, include game


# Tool schema for LLM
TOOL_FETCH_GAMES_FILTERED = {
    "type": "function",
    "function": {
        "name": "fetch_games_filtered",
        "description": "Fetch chess games with advanced filtering. Filter by date range, opponent, opening, time control, result, color, and rating.",
        "parameters": {
            "type": "object",
            "properties": {
                "username": {
                    "type": "string",
                    "description": "Player username on the platform"
                },
                "platform": {
                    "type": "string",
                    "enum": ["chess.com", "lichess"],
                    "description": "Chess platform",
                    "default": "chess.com"
                },
                "date_from": {
                    "type": "string",
                    "description": "Start date (YYYY-MM-DD)"
                },
                "date_to": {
                    "type": "string",
                    "description": "End date (YYYY-MM-DD)"
                },
                "opponent": {
                    "type": "string",
                    "description": "Filter by opponent username"
                },
                "opening_eco": {
                    "type": "string",
                    "description": "Filter by ECO code (e.g., 'B50', 'E4')"
                },
                "time_control": {
                    "type": "string",
                    "enum": ["bullet", "blitz", "rapid", "classical"],
                    "description": "Time control category"
                },
                "result": {
                    "type": "string",
                    "enum": ["win", "loss", "draw"],
                    "description": "Game result for the player"
                },
                "color": {
                    "type": "string",
                    "enum": ["white", "black"],
                    "description": "Color played"
                },
                "min_opponent_rating": {
                    "type": "integer",
                    "description": "Minimum opponent rating"
                },
                "max_games": {
                    "type": "integer",
                    "description": "Maximum games to return (default 50)",
                    "default": 50
                }
            },
            "required": ["username"]
        }
    }
}

