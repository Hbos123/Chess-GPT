    async def _fetch_games(self, args: Dict, status_callback = None, context: Dict = None) -> Dict:
        """
        Fetch games from Chess.com/Lichess WITHOUT Stockfish analysis.
        Fast fetch of PGN + metadata only.
        """
        username = args.get("username")
        platform = args.get("platform", "chess.com")
        
        # Fallback to context.connected_accounts
        if not username or not platform:
            if context:
                connected_accounts = context.get("connected_accounts", [])
                if connected_accounts:
                    account = connected_accounts[0]
                    if not username:
                        username = account.get("username")
                    if not platform:
                        platform = account.get("platform", "chess.com")
        
        if not username:
            return {"success": False, "error": "Username required"}
        
        max_games = args.get("max_games", 3)
        time_control = args.get("time_control", "all")
        result_filter = args.get("result", "all")
        months_back = int(args.get("months_back", 6) or 6)
        date_from = args.get("date_from")
        date_to = args.get("date_to")
        color = args.get("color")  # 'white', 'black', or None for both
        
        async def emit_status(message: str, progress: float = None):
            if status_callback:
                await status_callback(
                    phase="executing",
                    message=message,
                    tool="fetch_games",
                    progress=progress
                )
        
        await emit_status(f"Fetching games from {platform}...", 0.1)
        
        from tools.game_filters import fetch_games_filtered
        
        try:
            filtered = await fetch_games_filtered(
                username=username,
                platform=platform,
                date_from=date_from,
                date_to=date_to,
                months_back=months_back,
                max_games=max_games,
                result=result_filter,
                time_control=time_control,
                color=color
            )
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to fetch games: {str(e)}"
            }
        
        if isinstance(filtered, dict) and filtered.get("error"):
            return {
                "success": False,
                "error": filtered.get("error"),
                "message": f"No games found: {filtered.get('error')}"
            }
        
        games = filtered.get("games", []) or []
        if not games:
            return {
                "success": False,
                "error": "no_games",
                "message": f"No games found for {username} on {platform}"
            }
        
        await emit_status(f"Found {len(games)} games", 0.9)
        
        # Format games for return (PGN + metadata only, no analysis)
        formatted_games = []
        for game in games:
            formatted_games.append({
                "id": game.get("id", ""),
                "pgn": game.get("pgn", ""),
                "white": game.get("white", {}).get("username", ""),
                "black": game.get("black", {}).get("username", ""),
                "result": game.get("result", ""),
                "time_control": game.get("time_control", ""),
                "date": game.get("date", ""),
                "opening": game.get("opening", {}).get("name", ""),
                "eco": game.get("opening", {}).get("eco", ""),
                "url": game.get("url", ""),
                "platform": platform,
                "username": username
            })
        
        return {
            "success": True,
            "games": formatted_games,
            "count": len(formatted_games),
            "platform": platform,
            "username": username,
            "message": f"Fetched {len(formatted_games)} games from {platform}"
        }

