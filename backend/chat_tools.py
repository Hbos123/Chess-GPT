"""
OpenAI Function/Tool Schemas for Chess GPT
Hierarchical tool set with high-level workflows and low-level data access
"""

from typing import Dict, List, Any

# ============================================================================
# HIGH-LEVEL TOOLS (Workflows and Analysis)
# ============================================================================

TOOL_ANALYZE_POSITION = {
    "type": "function",
    "function": {
        "name": "analyze_position",
        "description": "Analyze a chess position with Stockfish. Returns evaluation, best moves, threats, and themes. Use when user asks about a specific position or the current board state.",
        "parameters": {
            "type": "object",
            "properties": {
                "fen": {
                    "type": "string",
                    "description": "FEN string of the position to analyze. If not provided, uses current board position from context."
                },
                "depth": {
                    "type": "integer",
                    "description": "Stockfish analysis depth (10-25). Default 18. Higher = more accurate but slower.",
                    "default": 18
                },
                "lines": {
                    "type": "integer",
                    "description": "Number of candidate lines to analyze (1-5). Default 3.",
                    "default": 3
                }
            },
            "required": []
        }
    }
}

TOOL_ANALYZE_MOVE = {
    "type": "function",
    "function": {
        "name": "analyze_move",
        "description": "Evaluate a specific move in a position. Returns if it's good/bad, CP loss, better alternatives, and tactical implications. Use when user asks 'Is this move good?' or 'What's wrong with my move?'",
        "parameters": {
            "type": "object",
            "properties": {
                "fen": {
                    "type": "string",
                    "description": "FEN string before the move"
                },
                "move_san": {
                    "type": "string",
                    "description": "Move in SAN notation (e.g., 'Nf3', 'e4', 'O-O')"
                },
                "depth": {
                    "type": "integer",
                    "description": "Analysis depth. Default 18.",
                    "default": 18
                }
            },
            "required": ["move_san"]
        }
    }
}

TOOL_REVIEW_FULL_GAME = {
    "type": "function",
    "function": {
        "name": "review_full_game",
        "description": "Perform complete analysis of a chess game with move-by-move evaluation, accuracy statistics, key moments, and phase breakdown. Returns comprehensive review data. ALWAYS USE THIS when user says 'review the game', 'analyze my game', 'check this game', or similar. Extract PGN from context.pgn if not provided explicitly.",
        "parameters": {
            "type": "object",
            "properties": {
                "pgn": {
                    "type": "string",
                    "description": "PGN string of the game to review"
                },
                "side_focus": {
                    "type": "string",
                    "enum": ["white", "black", "both"],
                    "description": "Which side to focus analysis on. Default 'both'.",
                    "default": "both"
                },
                "depth": {
                    "type": "integer",
                    "description": "Stockfish depth for analysis. Default 15 for speed.",
                    "default": 15
                }
            },
            "required": ["pgn"]
        }
    }
}

TOOL_FETCH_AND_REVIEW_GAMES = {
    "type": "function",
    "function": {
        "name": "fetch_and_review_games",
        "description": "Fetch games from Chess.com or Lichess, analyze them with Stockfish, and return aggregate statistics. REQUIRED: username and platform must be provided (check context.connected_accounts for user's accounts).",
        "parameters": {
            "type": "object",
            "properties": {
                "username": {
                    "type": "string",
                    "description": "Chess.com or Lichess username. REQUIRED - get from context.connected_accounts if available."
                },
                "platform": {
                    "type": "string",
                    "enum": ["chess.com", "lichess"],
                    "description": "Which platform to fetch from. REQUIRED - use 'chess.com' or 'lichess'."
                },
                "count": {
                    "type": "integer",
                    "description": "Number of games to fetch. Default 1 for 'last game', use 5-10 for 'recent games'.",
                    "default": 1
                },
                "max_games": {
                    "type": "integer",
                    "description": "Alias for count. Maximum games to fetch.",
                    "default": 5
                },
                "games_to_analyze": {
                    "type": "integer",
                    "description": "How many games to analyze with Stockfish. Default 3.",
                    "default": 3
                },
                "depth": {
                    "type": "integer",
                    "description": "Stockfish analysis depth. Default 15.",
                    "default": 15
                },
                "time_control": {
                    "type": "string",
                    "enum": ["bullet", "blitz", "rapid", "classical", "daily", "all"],
                    "description": "Filter by time control. Default 'all'."
                },
                "result_filter": {
                    "type": "string",
                    "enum": ["win", "loss", "draw", "wins", "losses", "draws", "all"],
                    "description": "Filter by game result. Default 'all'."
                },
                "months_back": {
                    "type": "integer",
                    "description": "Recency window in months when date_from/date_to not provided. Default 6.",
                    "default": 6
                },
                "date_from": {
                    "type": "string",
                    "description": "Start date (YYYY-MM-DD). Optional."
                },
                "date_to": {
                    "type": "string",
                    "description": "End date (YYYY-MM-DD). Optional."
                },
                "opponent": {
                    "type": "string",
                    "description": "Filter by opponent username (optional)."
                },
                "opening_eco": {
                    "type": "string",
                    "description": "Filter by ECO prefix (e.g., 'B50', 'C4'). Optional."
                },
                "color": {
                    "type": "string",
                    "enum": ["white", "black", "both"],
                    "description": "Filter by the player's color. Optional."
                },
                "min_moves": {
                    "type": "integer",
                    "description": "Minimum number of full moves (optional)."
                },
                "min_opponent_rating": {
                    "type": "integer",
                    "description": "Minimum opponent rating (optional)."
                },
                "max_opponent_rating": {
                    "type": "integer",
                    "description": "Maximum opponent rating (optional)."
                },
                "sort": {
                    "type": "string",
                    "enum": ["date_desc", "date_asc"],
                    "description": "Sort order for returned games (optional). Default 'date_desc'."
                },
                "offset": {
                    "type": "integer",
                    "description": "Skip first N games after filtering (optional). Default 0."
                },
                "query": {
                    "type": "string",
                    "description": "Specific question about the games (e.g., 'why am I stuck at 1200?')"
                },
                "review_subject": {
                    "type": "string",
                    "enum": ["player", "opponent", "both"],
                    "description": "Who to focus the review on. 'player' = the connected user, 'opponent' = the opponent in those games, 'both' = both sides.",
                    "default": "player"
                }
            },
            "required": ["username", "platform"]
        }
    }
}

TOOL_SELECT_GAMES = {
    "type": "function",
    "function": {
        "name": "select_games",
        "description": "Fetch a candidate set of games and deterministically select specific games (last, second last, a win, a rapid, etc.) using LLM-provided selectors. Returns game references (date/time/result/color/opponent/url) without running Stockfish analysis.",
        "parameters": {
            "type": "object",
            "properties": {
                "username": {
                    "type": "string",
                    "description": "Chess.com or Lichess username. If omitted, use context.connected_accounts."
                },
                "platform": {
                    "type": "string",
                    "enum": ["chess.com", "lichess"],
                    "description": "Which platform to fetch from. If omitted, use context.connected_accounts."
                },
                "candidate_fetch_count": {
                    "type": "integer",
                    "description": "How many games to fetch as the candidate pool (before selection). Default 50.",
                    "default": 50
                },
                "months_back": {
                    "type": "integer",
                    "description": "Recency window in months when date_from/date_to not provided. Default 6.",
                    "default": 6
                },
                "date_from": {
                    "type": "string",
                    "description": "Start date (YYYY-MM-DD). Optional."
                },
                "date_to": {
                    "type": "string",
                    "description": "End date (YYYY-MM-DD). Optional."
                },
                "global_unique": {
                    "type": "boolean",
                    "description": "If true, never return the same game twice across requests. Default true.",
                    "default": True
                },
                "global_limit": {
                    "type": "integer",
                    "description": "Optional cap on total number of selected games across all requests."
                },
                "include_pgn": {
                    "type": "boolean",
                    "description": "If true, include PGN strings for selected games (useful for opening a game in a new tab). Default false.",
                    "default": False
                },
                "requests": {
                    "type": "array",
                    "description": "Selection requests (each can specify filters + count/offset/sort).",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Label for this selection (e.g., 'last_game', 'bullet_game')."},
                            "count": {"type": "integer", "description": "How many games to select for this request (default 1).", "default": 1},
                            "offset": {"type": "integer", "description": "Skip N eligible games (after sorting + uniqueness). Useful for 'second last'.", "default": 0},
                            "sort": {"type": "string", "enum": ["date_desc", "date_asc"], "description": "Sort order within this request.", "default": "date_desc"},
                            "require_unique": {"type": "boolean", "description": "If true, game must be unique vs other selections.", "default": True},
                            "allow_reuse": {"type": "boolean", "description": "If true, this request may reuse a previously selected game (labels can overlap) without increasing the unique game count.", "default": False},
                            "filters": {
                                "type": "object",
                                "description": "Optional filters for this request.",
                                "properties": {
                                    "result": {"type": "string", "enum": ["win", "loss", "draw"], "description": "Result filter."},
                                    "time_control": {"type": "string", "enum": ["bullet", "blitz", "rapid", "classical", "daily"], "description": "Time-control category filter."},
                                    "color": {"type": "string", "enum": ["white", "black"], "description": "Color filter."},
                                    "opening_eco": {"type": "string", "description": "ECO prefix filter (e.g. 'B50')."},
                                    "opponent": {"type": "string", "description": "Opponent username contains filter."},
                                    "min_opponent_rating": {"type": "integer", "description": "Minimum opponent rating."},
                                    "max_opponent_rating": {"type": "integer", "description": "Maximum opponent rating."},
                                    "min_moves": {"type": "integer", "description": "Minimum full moves (best-effort)."},
                                    "date_from": {"type": "string", "description": "Per-request start date (YYYY-MM-DD). Optional."},
                                    "date_to": {"type": "string", "description": "Per-request end date (YYYY-MM-DD). Optional."}
                                }
                            }
                        },
                        "required": ["name"]
                    }
                }
            }
        }
    }
}

TOOL_ADD_PERSONAL_REVIEW_GRAPH = {
    "type": "function",
    "function": {
        "name": "add_personal_review_graph",
        "description": "Add a personal review graph to the chat showing performance trends. Multiple calls can layer series on the same graph. Graph appears above the final message. Use when user asks about trends, performance over time, or wants to visualize their progress.",
        "parameters": {
            "type": "object",
            "properties": {
                "data_type": {
                    "type": "string",
                    "enum": [
                        "win_rate_pct",
                        "overall_accuracy",
                        "opening_frequency_pct",
                        "opening_accuracy",
                        "piece_accuracy",
                        "time_bucket_accuracy",
                        "tag_transition_count",
                        "tag_transition_accuracy"
                    ],
                    "description": "Type of data to graph. win_rate_pct: Win rate percentage. overall_accuracy: Overall move accuracy. opening_frequency_pct: Frequency of specific opening. opening_accuracy: Accuracy with specific opening. piece_accuracy: Accuracy with specific piece type. time_bucket_accuracy: Accuracy in specific time ranges. tag_transition_count: Count of tag transitions. tag_transition_accuracy: Accuracy during tag transitions."
                },
                "series_name": {
                    "type": "string",
                    "description": "Display name for this series (e.g., 'Overall Accuracy', 'Sicilian Defense Win Rate', 'Knight Accuracy')"
                },
                "params": {
                    "type": "object",
                    "properties": {
                        "openingName": {"type": "string", "description": "Opening name (required for opening_frequency_pct, opening_accuracy)"},
                        "piece": {"type": "string", "enum": ["Pawn", "Knight", "Bishop", "Rook", "Queen", "King"], "description": "Piece type (required for piece_accuracy)"},
                        "bucket": {"type": "string", "description": "Time bucket (required for time_bucket_accuracy, e.g., '<5s', '5-15s', '15-30s', '30s-1min', '1min-2min30', '2min30-5min', '5min+')"},
                        "tag": {"type": "string", "description": "Tag name (required for tag_transition_count, tag_transition_accuracy)"},
                        "dir": {"type": "string", "enum": ["gained", "lost"], "description": "Tag transition direction (required for tag_transition_count, tag_transition_accuracy)"}
                    },
                    "description": "Additional parameters for specific data types. Required based on data_type."
                },
                "grouping": {
                    "type": "string",
                    "enum": ["game", "day", "batch5"],
                    "description": "How to group data points. 'game' = one point per game (most granular), 'day' = group by date, 'batch5' = group by 5-game batches. Default 'game'.",
                    "default": "game"
                },
                "x_axis_range": {
                    "type": "object",
                    "properties": {
                        "start_game": {"type": "integer", "description": "Starting game index (0-based). If not provided, starts from first game."},
                        "end_game": {"type": "integer", "description": "Ending game index (0-based, exclusive). If not provided, uses all available games."}
                    },
                    "description": "X-axis range to focus on. Optional - if not provided, uses all available games."
                },
                "color": {
                    "type": "string",
                    "description": "Hex color for the line (e.g., '#3b82f6', '#10b981'). Auto-assigned if not provided."
                }
            },
            "required": ["data_type", "series_name"]
        }
    }
}

TOOL_GENERATE_TRAINING = {
    "type": "function",
    "function": {
        "name": "generate_training_session",
        "description": "Generate personalized training drills from analyzed games. Use when user wants to practice or improve on specific weaknesses. Requires previously analyzed games or will analyze on-the-fly.",
        "parameters": {
            "type": "object",
            "properties": {
                "username": {
                    "type": "string",
                    "description": "Username for progress tracking"
                },
                "training_query": {
                    "type": "string",
                    "description": "What to practice (e.g., 'tactical mistakes', 'endgame technique', 'fork patterns')"
                },
                "source": {
                    "type": "string",
                    "enum": ["recent_games", "database", "both"],
                    "description": "Use recent analyzed games, saved games from database, or both. Default 'recent_games'.",
                    "default": "recent_games"
                },
                "num_drills": {
                    "type": "integer",
                    "description": "Number of drills to generate. Default 15.",
                    "default": 15
                }
            },
            "required": ["username", "training_query"]
        }
    }
}

TOOL_GET_LESSON = {
    "type": "function",
    "function": {
        "name": "get_lesson",
        "description": "Generate an interactive lesson on an opening or tactical theme with positions and explanations. Use when user wants to learn about a specific topic.",
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "Topic to teach (e.g., 'Italian Game', 'fork patterns', 'rook endgames')"
                },
                "level": {
                    "type": "string",
                    "enum": ["beginner", "intermediate", "advanced"],
                    "description": "Difficulty level. Default 'intermediate'.",
                    "default": "intermediate"
                }
            },
            "required": ["topic"]
        }
    }
}

TOOL_GENERATE_OPENING_LESSON = {
    "type": "function",
    "function": {
        "name": "generate_opening_lesson",
        "description": "Build a personalized opening lesson using current board context and user history. Use when the user asks to learn a specific opening or requests an opening lesson.",
        "parameters": {
            "type": "object",
            "properties": {
                "opening_query": {
                    "type": "string",
                    "description": "Opening name or SAN sequence to focus on (e.g., 'Sicilian Najdorf', '1.e4 c5 2.Nf3')."
                },
                "fen": {
                    "type": "string",
                    "description": "Current board position to anchor the lesson."
                },
                "eco": {
                    "type": "string",
                    "description": "ECO code if known (e.g., 'B90')."
                },
                "orientation": {
                    "type": "string",
                    "enum": ["white", "black"],
                    "description": "Perspective to teach from. Default inferred from context."
                }
            },
            "required": []
        }
    }
}

# ============================================================================
# LOW-LEVEL DATA TOOLS (Database Queries and Saves)
# ============================================================================

TOOL_QUERY_GAMES = {
    "type": "function",
    "function": {
        "name": "query_user_games",
        "description": "Search user's saved games in database with filters. Returns list of games matching criteria. Use when user asks about their game history, stats, or specific openings.",
        "parameters": {
            "type": "object",
            "properties": {
                "username": {
                    "type": "string",
                    "description": "Username to query games for"
                },
                "opening_eco": {
                    "type": "string",
                    "description": "Filter by ECO code (e.g., 'C50', 'B20-B99' for Sicilian)"
                },
                "result": {
                    "type": "string",
                    "enum": ["win", "loss", "draw"],
                    "description": "Filter by game result"
                },
                "min_rating": {
                    "type": "integer",
                    "description": "Minimum opponent rating"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum games to return. Default 20.",
                    "default": 20
                }
            },
            "required": ["username"]
        }
    }
}

TOOL_GET_GAME_DETAILS = {
    "type": "function",
    "function": {
        "name": "get_game_details",
        "description": "Get complete analysis data for a specific game including move-by-move evaluation, key moments, and statistics.",
        "parameters": {
            "type": "object",
            "properties": {
                "game_id": {
                    "type": "string",
                    "description": "Game ID to retrieve"
                }
            },
            "required": ["game_id"]
        }
    }
}

TOOL_QUERY_POSITIONS = {
    "type": "function",
    "function": {
        "name": "query_positions",
        "description": "Search saved positions by tags, themes, phase, or error category. Returns positions matching criteria with FEN and best moves. Use when user asks about saved positions or specific tactical patterns.",
        "parameters": {
            "type": "object",
            "properties": {
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Filter by tags (e.g., ['tactic.fork', 'endgame.pawn'])"
                },
                "themes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Filter by strategic themes (e.g., ['kingside_attack', 'center_control'])"
                },
                "error_categories": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Filter by error types (e.g., ['blunder', 'missed_win'])"
                },
                "phase": {
                    "type": "string",
                    "enum": ["opening", "middlegame", "endgame"],
                    "description": "Filter by game phase"
                },
                "mover_name": {
                    "type": "string",
                    "description": "Filter by side to move (e.g., 'white', 'black')"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum positions to return. Default 5.",
                    "default": 5
                }
            },
            "required": []
        }
    }
}

TOOL_GET_TRAINING_STATS = {
    "type": "function",
    "function": {
        "name": "get_training_stats",
        "description": "Get user's training progress including SRS stats, accuracy trends, and drill performance. Use when user asks about their training progress or improvement.",
        "parameters": {
            "type": "object",
            "properties": {
                "username": {
                    "type": "string",
                    "description": "Username to get stats for"
                }
            },
            "required": ["username"]
        }
    }
}

TOOL_SAVE_POSITION = {
    "type": "function",
    "function": {
        "name": "save_position",
        "description": "Save/star a position to user's database for later reference. Use when user says 'save this position' or 'remember this'.",
        "parameters": {
            "type": "object",
            "properties": {
                "username": {
                    "type": "string",
                    "description": "Username saving the position"
                },
                "fen": {
                    "type": "string",
                    "description": "FEN of position to save. If not provided, uses current board."
                },
                "note": {
                    "type": "string",
                    "description": "Optional user note about the position"
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tags to categorize position (e.g., ['tactic.fork', 'middlegame'])"
                }
            },
            "required": ["username"]
        }
    }
}

TOOL_CREATE_COLLECTION = {
    "type": "function",
    "function": {
        "name": "create_collection",
        "description": "Create a new collection/folder to organize games or positions. Use when user wants to organize their data.",
        "parameters": {
            "type": "object",
            "properties": {
                "username": {
                    "type": "string",
                    "description": "Username creating the collection"
                },
                "name": {
                    "type": "string",
                    "description": "Collection name (e.g., 'Italian Game Study', 'Tactical Mistakes')"
                },
                "description": {
                    "type": "string",
                    "description": "Optional description of what this collection is for"
                }
            },
            "required": ["username", "name"]
        }
    }
}

TOOL_SETUP_POSITION = {
    "type": "function",
    "function": {
        "name": "setup_position",
        "description": "Set up a chess position on the board for visualization. Use when user asks to 'show me a position', 'set up this game', or 'display this FEN'. Returns display instructions.",
        "parameters": {
            "type": "object",
            "properties": {
                "fen": {
                    "type": "string",
                    "description": "FEN string of the position to display (optional if PGN provided)"
                },
                "pgn": {
                    "type": "string",
                    "description": "PGN string of the game to display (optional if FEN provided)"
                },
                "orientation": {
                    "type": "string",
                    "enum": ["white", "black"],
                    "description": "Board orientation - which side faces the user. Default: white",
                    "default": "white"
                },
                "move_annotations": {
                    "type": "object",
                    "description": "Annotations per move number (e.g., {1: 'Opening principle', 5: 'Tactical blow'}). Keys are move numbers, values are annotation text.",
                    "additionalProperties": {
                        "type": "string"
                    }
                }
            },
            "required": []
        }
    }
}

# ============================================================================
# ADVANCED INVESTIGATION TOOLS
# ============================================================================

TOOL_INVESTIGATE = {
    "type": "function",
    "function": {
        "name": "investigate",
        "description": "Run a complex multi-step investigation. Use for cheating analysis, player research, performance trends, tournament reviews, and other analytical tasks that require multiple data sources and analysis steps. Examples: 'Did Hans Niemann cheat?', 'Analyze Magnus Carlsen's 2023 performance', 'Research player X'.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The investigation query (e.g., 'Did Hans Niemann cheat at Sinquefield Cup 2022?', 'Analyze Magnus Carlsen performance trend in 2023')"
                },
                "investigation_type": {
                    "type": "string",
                    "enum": ["cheating_analysis", "player_research", "performance_trend", "tournament_review", "opening_analysis", "general_investigation"],
                    "description": "Type of investigation to run. Auto-detected if not specified."
                },
                "target_player": {
                    "type": "string",
                    "description": "Primary player to investigate"
                },
                "target_event": {
                    "type": "string",
                    "description": "Specific tournament or event (optional)"
                },
                "platform": {
                    "type": "string",
                    "enum": ["chess.com", "lichess"],
                    "description": "Platform to fetch games from"
                },
                "username": {
                    "type": "string",
                    "description": "Platform username of target player"
                }
            },
            "required": ["query"]
        }
    }
}

TOOL_MULTI_DEPTH_ANALYZE = {
    "type": "function",
    "function": {
        "name": "multi_depth_analyze",
        "description": "Analyze a game at multiple Stockfish depths to detect suspiciously accurate play. Compares accuracy at depths 10, 20, 30, 40. Use for detailed cheating investigation.",
        "parameters": {
            "type": "object",
            "properties": {
                "pgn": {
                    "type": "string",
                    "description": "PGN string of the game to analyze"
                },
                "depths": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Depths to analyze at (default: [10, 20, 30])"
                },
                "focus_side": {
                    "type": "string",
                    "enum": ["white", "black", "both"],
                    "description": "Which side to focus analysis on"
                }
            },
            "required": ["pgn"]
        }
    }
}

TOOL_ENGINE_CORRELATION = {
    "type": "function",
    "function": {
        "name": "engine_correlation",
        "description": "Calculate how closely player moves match Stockfish's top recommendations. Returns match percentages and suspicion level. Use for cheating analysis.",
        "parameters": {
            "type": "object",
            "properties": {
                "pgn": {
                    "type": "string",
                    "description": "PGN string of the game to analyze"
                },
                "depth": {
                    "type": "integer",
                    "description": "Stockfish analysis depth (default 25)"
                },
                "top_n": {
                    "type": "integer",
                    "description": "Match against top N moves (default 3)"
                }
            },
            "required": ["pgn"]
        }
    }
}

# ============================================================================
# CHESS-GPT INTERNAL LEARNING/INTUITION TOOLS
# ============================================================================

TOOL_EXTEND_BASELINE_INTUITION = {
    "type": "function",
    "function": {
        "name": "extend_baseline_intuition",
        "description": "Re-run the baseline D2→D16 exploration (two-pass: from current FEN, then after D16 best move) with larger budgets to extend the PGN/tree deterministically.",
        "parameters": {
            "type": "object",
            "properties": {
                "fen": {"type": "string", "description": "FEN to analyze (optional if current board state exists in context)"},
                "d2_depth": {"type": "integer", "description": "Shallow depth (default 2)"},
                "d16_depth": {"type": "integer", "description": "Deep depth (default 16)"},
                "branching_limit": {"type": "integer", "description": "How many overestimated branches to explore (default 6)"},
                "max_pv_plies": {"type": "integer", "description": "Max PV plies to include in PGN/tree (default 24)"},
                "pgn_max_chars": {"type": "integer", "description": "Cap PGN size (default 24000; 0 means unlimited)"},
                "timeout_s": {"type": "number", "description": "Timeout budget for scan (default 30.0)"},
                "motifs_max_pattern_plies": {"type": "integer", "description": "Max motif pattern length in plies (default 5)"},
                "motifs_top": {"type": "integer", "description": "Number of motifs returned (default 40)"},
                "motifs_max_line_plies": {"type": "integer", "description": "Max line length used for motif mining (default 14)"},
                "motifs_max_branch_lines": {"type": "integer", "description": "Max branch lines considered for motif mining (default 20)"},
            },
            "required": [],
        },
    },
}

TOOL_PLAYER_BASELINE = {
    "type": "function",
    "function": {
        "name": "calculate_baseline",
        "description": "Calculate a player's historical performance baseline from their games. Returns accuracy, CP loss, and blunder rate statistics.",
        "parameters": {
            "type": "object",
            "properties": {
                "games": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "List of analyzed games with metrics"
                },
                "exclude_outliers": {
                    "type": "boolean",
                    "description": "Remove statistical outliers (default True)"
                }
            },
            "required": ["games"]
        }
    }
}

TOOL_DETECT_ANOMALIES = {
    "type": "function",
    "function": {
        "name": "detect_anomalies",
        "description": "Detect statistical anomalies in player performance vs their historical baseline. Returns z-scores and anomaly flags.",
        "parameters": {
            "type": "object",
            "properties": {
                "test_games": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "Games to test for anomalies"
                },
                "baseline": {
                    "type": "object",
                    "description": "Historical baseline from calculate_baseline()"
                }
            },
            "required": ["test_games", "baseline"]
        }
    }
}

TOOL_WEB_SEARCH = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "Search the web for chess-related information. Use for player news, tournament results, and historical data. Returns relevant snippets and URLs.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (e.g., 'Magnus Carlsen 2024 tournaments')"
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum results to return (1-10)"
                },
                "search_filter": {
                    "type": "string",
                    "enum": ["all", "news", "games", "players"],
                    "description": "Filter results by type"
                }
            },
            "required": ["query"]
        }
    }
}

TOOL_SET_AI_GAME = {
    "type": "function",
    "function": {
        "name": "set_ai_game",
        "description": "Enable or disable AI game mode. When user wants to play a game with the AI (e.g., 'let's play', 'play together', 'play a game', 'play from this position'), call this tool with active=true. The AI will then play moves automatically when it's their turn. After calling this tool, continue with normal functionality (analysis, explanation, etc.).",
        "parameters": {
            "type": "object",
            "properties": {
                "active": {
                    "type": "boolean",
                    "description": "Enable (true) or disable (false) AI game mode. Set to true when user wants to play a game."
                },
                "ai_side": {
                    "type": "string",
                    "enum": ["white", "black", "auto"],
                    "description": "Which color the AI should play. 'auto' means detect from current turn. Use 'white' or 'black' if user explicitly says 'you play as white/black'."
                },
                "make_move_now": {
                    "type": "boolean",
                    "description": "If true, the AI will make a move immediately if it's their turn. Set to true if user says 'play this turn' or 'make a move'."
                }
            },
            "required": ["active"]
        }
    }
}

# ============================================================================
# TREE-FIRST TOOLS (D2/D16 move tree)
# ============================================================================

TOOL_TREE_SEARCH = {
    "type": "function",
    "function": {
        "name": "tree_search",
        "description": "Search the backend D2/D16 move tree (per thread/tab) for moves/tags/text and return ranked matches (mainline first, then deeper deviations).",
        "parameters": {
            "type": "object",
            "properties": {
                "thread_id": {
                    "type": "string",
                    "description": "Tab/thread id that owns the tree (use the current conversation thread/tab id)."
                },
                "query": {
                    "type": "string",
                    "description": "Search query. Supports move:\"SAN\" for exact SAN match, otherwise substring search across scan artifacts."
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results to return (default 25).",
                    "default": 25
                }
            },
            "required": ["thread_id", "query"]
        }
    }
}

# ============================================================================
# ALL TOOLS LIST
# ============================================================================

ALL_TOOLS = [
    # TOOL_ANALYZE_POSITION,  # Removed - handled by auto-analysis cache instead
    # TOOL_ANALYZE_MOVE,      # Removed - handled by auto-analysis cache instead
    TOOL_REVIEW_FULL_GAME,
    TOOL_FETCH_AND_REVIEW_GAMES,
    TOOL_SELECT_GAMES,
    TOOL_GENERATE_TRAINING,
    TOOL_GET_LESSON,
    TOOL_GENERATE_OPENING_LESSON,
    TOOL_QUERY_GAMES,
    TOOL_GET_GAME_DETAILS,
    TOOL_QUERY_POSITIONS,
    TOOL_GET_TRAINING_STATS,
    TOOL_SAVE_POSITION,
    TOOL_CREATE_COLLECTION,
    TOOL_SETUP_POSITION,
    TOOL_SET_AI_GAME,
    TOOL_ADD_PERSONAL_REVIEW_GRAPH,
    # Investigation tools
    TOOL_INVESTIGATE,
    TOOL_WEB_SEARCH
]

# Tool categories for selective availability
ANALYSIS_TOOLS = [TOOL_ANALYZE_POSITION, TOOL_ANALYZE_MOVE, TOOL_REVIEW_FULL_GAME, TOOL_EXTEND_BASELINE_INTUITION, TOOL_TREE_SEARCH]
WORKFLOW_TOOLS = [TOOL_FETCH_AND_REVIEW_GAMES, TOOL_SELECT_GAMES, TOOL_GENERATE_TRAINING, TOOL_GET_LESSON, TOOL_GENERATE_OPENING_LESSON, TOOL_SET_AI_GAME, TOOL_ADD_PERSONAL_REVIEW_GRAPH]
DATA_TOOLS = [TOOL_QUERY_GAMES, TOOL_GET_GAME_DETAILS, TOOL_QUERY_POSITIONS, TOOL_GET_TRAINING_STATS]
WRITE_TOOLS = [TOOL_SAVE_POSITION, TOOL_CREATE_COLLECTION]
INVESTIGATION_TOOLS = [
    TOOL_INVESTIGATE, 
    TOOL_MULTI_DEPTH_ANALYZE, 
    TOOL_ENGINE_CORRELATION,
    TOOL_PLAYER_BASELINE,
    TOOL_DETECT_ANOMALIES,
    TOOL_WEB_SEARCH
]

def get_tools_for_context(context: Dict[str, Any]) -> List[Dict]:
    """
    Return appropriate tools based on conversation context
    
    Args:
        context: Conversation context (has_fen, has_pgn, mode, etc.)
        
    Returns:
        List of tool schemas to provide to OpenAI
    """
    tools = []
    
    # Always include analysis tools
    tools.extend(ANALYSIS_TOOLS)
    
    # Include workflows if user likely needs them
    tools.extend(WORKFLOW_TOOLS)
    
    # Include data tools if user is authenticated
    if context.get("authenticated"):
        tools.extend(DATA_TOOLS)
        tools.extend(WRITE_TOOLS)
    
    # Include investigation tools (always available for complex queries)
    tools.append(TOOL_INVESTIGATE)
    tools.append(TOOL_WEB_SEARCH)
    
    return tools

