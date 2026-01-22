"""
Game Fetcher for Personal Review System
Fetches games from Chess.com and Lichess APIs
"""

import aiohttp
import asyncio
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import json
import os
import chess.pgn
from io import StringIO


class GameFetcher:
    """Fetches games from Chess.com and Lichess"""
    
    def __init__(self):
        self.cache_dir = "backend/cache/player_games"
        os.makedirs(self.cache_dir, exist_ok=True)
        
    async def fetch_games(
        self, 
        username: str, 
        platform: str = "chess.com",
        max_games: int = 100,
        months_back: int = 6
    ) -> List[Dict]:
        """
        Fetch games from specified platform
        
        Args:
            username: Player username
            platform: "chess.com", "lichess", or "combined"
            max_games: Maximum number of games to fetch
            months_back: How many months back to fetch
            
        Returns:
            List of game dictionaries with metadata and PGN
        """
        if platform == "combined":
            games_chess_com = await self._fetch_chess_com(username, max_games // 2, months_back)
            games_lichess = await self._fetch_lichess(username, max_games // 2, months_back)
            return games_chess_com + games_lichess
        elif platform == "chess.com":
            return await self._fetch_chess_com(username, max_games, months_back)
        elif platform == "lichess":
            return await self._fetch_lichess(username, max_games, months_back)
        else:
            raise ValueError(f"Unknown platform: {platform}")
    
    async def _fetch_chess_com(
        self, 
        username: str, 
        max_games: int,
        months_back: int
    ) -> List[Dict]:
        """Fetch games from Chess.com API"""
        games = []
        
        async with aiohttp.ClientSession() as session:
            # Get archives list
            archives_url = f"https://api.chess.com/pub/player/{username}/games/archives"
            
            try:
                async with session.get(archives_url) as response:
                    if response.status != 200:
                        print(f"Chess.com API error: {response.status}")
                        return []
                    
                    data = await response.json()
                    archives = data.get("archives", [])
                    
                    # Only fetch recent months
                    recent_archives = archives[-months_back:] if len(archives) > months_back else archives
                    
                    # Fetch games from each archive
                    for archive_url in reversed(recent_archives):  # Most recent first
                        if len(games) >= max_games:
                            break
                            
                        async with session.get(archive_url) as archive_response:
                            if archive_response.status == 200:
                                archive_data = await archive_response.json()
                                month_games = archive_data.get("games", [])
                                
                                for game_data in reversed(month_games):  # Most recent in month first
                                    if len(games) >= max_games:
                                        break
                                    
                                    game = self._parse_chess_com_game(game_data, username)
                                    if game:
                                        games.append(game)
                        
                        # Rate limiting
                        await asyncio.sleep(0.1)
            
            except Exception as e:
                print(f"Error fetching Chess.com games: {e}")
        
        return games
    
    def _parse_chess_com_game(self, game_data: Dict, username: str) -> Optional[Dict]:
        """Parse Chess.com game data into standard format"""
        try:
            pgn_text = game_data.get("pgn", "")
            if not pgn_text:
                return None
            
            # Parse PGN to extract metadata
            pgn_io = chess.pgn.read_game(StringIO(pgn_text))
            if not pgn_io:
                return None
            
            headers = pgn_io.headers
            
            # Determine player color and ratings
            white_player = headers.get("White", "").lower()
            black_player = headers.get("Black", "").lower()
            username_lower = username.lower()
            
            if username_lower in white_player:
                player_color = "white"
                player_rating = int(headers.get("WhiteElo", "0"))
                opponent_rating = int(headers.get("BlackElo", "0"))
                opponent_name = headers.get("Black", "Unknown")
            elif username_lower in black_player:
                player_color = "black"
                player_rating = int(headers.get("BlackElo", "0"))
                opponent_rating = int(headers.get("WhiteElo", "0"))
                opponent_name = headers.get("White", "Unknown")
            else:
                return None
            
            # Determine result from player perspective
            result_raw = headers.get("Result", "*")
            if result_raw == "1-0":
                result = "win" if player_color == "white" else "loss"
            elif result_raw == "0-1":
                result = "win" if player_color == "black" else "loss"
            elif result_raw == "1/2-1/2":
                result = "draw"
            else:
                result = "unknown"
            
            # Extract time control - convert to integer for consistent processing
            time_control_raw = game_data.get("time_control", headers.get("TimeControl", ""))
            try:
                # TimeControl in PGN is usually just seconds (e.g., "180") or format like "180+2"
                if isinstance(time_control_raw, str):
                    # Handle formats like "180", "180+2", or "600+5"
                    base_time = time_control_raw.split('+')[0] if '+' in time_control_raw else time_control_raw
                    time_control = int(base_time) if base_time.isdigit() else time_control_raw
                else:
                    time_control = time_control_raw
            except:
                time_control = time_control_raw
            
            time_class = game_data.get("time_class", "")
            
            # Categorize time control
            if time_class:
                if "bullet" in time_class:
                    time_category = "bullet"
                elif "blitz" in time_class:
                    time_category = "blitz"
                elif "rapid" in time_class:
                    time_category = "rapid"
                elif "daily" in time_class or "correspondence" in time_class:
                    time_category = "daily"
                else:
                    time_category = "classical"
            else:
                time_category = "unknown"
            
            # Accuracy data (Chess.com provides per-side accuracies for many games)
            accuracies = game_data.get("accuracies") or {}
            player_accuracy = None
            opponent_accuracy = None
            if isinstance(accuracies, dict):
                if player_color == "white":
                    player_accuracy = accuracies.get("white")
                    opponent_accuracy = accuracies.get("black")
                else:
                    player_accuracy = accuracies.get("black")
                    opponent_accuracy = accuracies.get("white")
            
            return {
                "game_id": game_data.get("url", "").split("/")[-1],
                "platform": "chess.com",
                "url": game_data.get("url", ""),
                "date": headers.get("Date", "").replace(".", "-"),
                "player_color": player_color,
                "player_rating": player_rating,
                "opponent_rating": opponent_rating,
                "opponent_name": opponent_name,
                "result": result,
                "opening": headers.get("ECOUrl", "").split("/")[-1] if headers.get("ECOUrl") else "",
                "eco": headers.get("ECO", ""),
                "termination": headers.get("Termination", ""),
                "time_control": time_control,
                "time_category": time_category,
                "pgn": pgn_text,
                "has_clock": "[%clk" in pgn_text,
                "accuracies": accuracies,
                "player_accuracy": player_accuracy,
                "opponent_accuracy": opponent_accuracy,
            }
        
        except Exception as e:
            print(f"Error parsing Chess.com game: {e}")
            return None
    
    async def _fetch_lichess(
        self, 
        username: str, 
        max_games: int,
        months_back: int
    ) -> List[Dict]:
        """Fetch games from Lichess API"""
        games = []
        
        # Calculate since timestamp (months_back)
        since_date = datetime.now() - timedelta(days=months_back * 30)
        since_ms = int(since_date.timestamp() * 1000)
        
        async with aiohttp.ClientSession() as session:
            url = f"https://lichess.org/api/games/user/{username}"
            params = {
                "max": max_games,
                "since": since_ms,
                "pgnInJson": "true",
                "clocks": "true",
                "evals": "false",
                "opening": "true"
            }
            
            headers = {
                "Accept": "application/x-ndjson"
            }
            
            try:
                async with session.get(url, params=params, headers=headers) as response:
                    if response.status != 200:
                        print(f"Lichess API error: {response.status}")
                        return []
                    
                    # Lichess returns NDJSON (newline-delimited JSON)
                    text = await response.text()
                    lines = text.strip().split("\n")
                    
                    for line in lines:
                        if not line:
                            continue
                        
                        try:
                            game_data = json.loads(line)
                            game = self._parse_lichess_game(game_data, username)
                            if game:
                                games.append(game)
                        except json.JSONDecodeError:
                            continue
            
            except Exception as e:
                print(f"Error fetching Lichess games: {e}")
        
        return games
    
    def _parse_lichess_game(self, game_data: Dict, username: str) -> Optional[Dict]:
        """Parse Lichess game data into standard format"""
        try:
            pgn_text = game_data.get("pgn", "")
            if not pgn_text:
                return None
            
            # Parse PGN
            pgn_io = chess.pgn.read_game(StringIO(pgn_text))
            if not pgn_io:
                return None
            
            headers = pgn_io.headers
            players = game_data.get("players", {})
            
            # Determine player color
            white_player = players.get("white", {}).get("user", {}).get("name", "").lower()
            black_player = players.get("black", {}).get("user", {}).get("name", "").lower()
            username_lower = username.lower()
            
            if username_lower == white_player:
                player_color = "white"
                player_rating = players.get("white", {}).get("rating", 0)
                opponent_rating = players.get("black", {}).get("rating", 0)
                opponent_name = players.get("black", {}).get("user", {}).get("name", "Unknown")
            elif username_lower == black_player:
                player_color = "black"
                player_rating = players.get("black", {}).get("rating", 0)
                opponent_rating = players.get("white", {}).get("rating", 0)
                opponent_name = players.get("white", {}).get("user", {}).get("name", "Unknown")
            else:
                return None
            
            # Determine result
            winner = game_data.get("winner", "")
            if winner == player_color:
                result = "win"
            elif winner == "":
                result = "draw"
            else:
                result = "loss"
            
            # Time control
            speed = game_data.get("speed", "")
            time_category = speed if speed in ["bullet", "blitz", "rapid", "classical", "correspondence"] else "unknown"
            
            # Opening
            opening_data = game_data.get("opening", {})
            opening_name = opening_data.get("name", "")
            eco = opening_data.get("eco", "")
            
            # Date
            created_at = game_data.get("createdAt", 0)
            date_str = datetime.fromtimestamp(created_at / 1000).strftime("%Y-%m-%d") if created_at else ""
            
            return {
                "game_id": game_data.get("id", ""),
                "platform": "lichess",
                "url": f"https://lichess.org/{game_data.get('id', '')}",
                "date": date_str,
                "player_color": player_color,
                "player_rating": player_rating,
                "opponent_rating": opponent_rating,
                "opponent_name": opponent_name,
                "result": result,
                "opening": opening_name,
                "eco": eco,
                "termination": game_data.get("status", ""),
                "time_control": f"{game_data.get('clock', {}).get('initial', 0)//60}+{game_data.get('clock', {}).get('increment', 0)}",
                "time_category": time_category,
                "pgn": pgn_text,
                "has_clock": "[%clk" in pgn_text
            }
        
        except Exception as e:
            print(f"Error parsing Lichess game: {e}")
            return None
    
    def cache_games(self, username: str, platform: str, games: List[Dict]) -> None:
        """Cache fetched games to file"""
        try:
            cache_file = os.path.join(self.cache_dir, f"{username}_{platform}.jsonl")
            with open(cache_file, "w") as f:
                for game in games:
                    f.write(json.dumps(game) + "\n")
            print(f"✓ Cached {len(games)} games for {username} ({platform})")
        except Exception as e:
            print(f"Warning: Could not cache games: {e}")
    
    def load_cached_games(self, username: str, platform: str) -> Optional[List[Dict]]:
        """Load games from cache if available"""
        try:
            cache_file = os.path.join(self.cache_dir, f"{username}_{platform}.jsonl")
            if not os.path.exists(cache_file):
                return None
            
            # Check if cache is recent (< 24 hours old)
            cache_age = datetime.now().timestamp() - os.path.getmtime(cache_file)
            if cache_age > 86400:  # 24 hours
                return None
            
            games = []
            with open(cache_file, "r") as f:
                for line in f:
                    if line.strip():
                        games.append(json.loads(line))
            
            print(f"✓ Loaded {len(games)} games from cache for {username} ({platform})")
            return games
        
        except Exception as e:
            print(f"Warning: Could not load cached games: {e}")
            return None

