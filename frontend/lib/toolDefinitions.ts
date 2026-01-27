// Tool definitions for autocomplete and @ syntax parsing
export interface ToolDefinition {
  name: string;
  description: string;
  args: Array<{name: string; type: string; required: boolean; description: string}>;
}

export const AVAILABLE_TOOLS: ToolDefinition[] = [
  {
    name: "analyze_position",
    description: "Analyze a chess position with Stockfish",
    args: [
      { name: "fen", type: "string", required: false, description: "FEN string (uses current board if not provided)" },
      { name: "depth", type: "integer", required: false, description: "Analysis depth (10-25, default 18)" },
      { name: "lines", type: "integer", required: false, description: "Number of candidate lines (1-5, default 3)" }
    ]
  },
  {
    name: "analyze_move",
    description: "Evaluate a specific move in a position",
    args: [
      { name: "move_san", type: "string", required: true, description: "Move in SAN notation (e.g., 'Nf3', 'e4')" },
      { name: "fen", type: "string", required: false, description: "FEN string before the move" },
      { name: "depth", type: "integer", required: false, description: "Analysis depth (default 18)" }
    ]
  },
  {
    name: "review_full_game",
    description: "Perform complete analysis of a chess game",
    args: [
      { name: "pgn", type: "string", required: true, description: "PGN string of the game" },
      { name: "side_focus", type: "string", required: false, description: "Focus: 'white', 'black', or 'both' (default 'both')" },
      { name: "depth", type: "integer", required: false, description: "Stockfish depth (default 15)" }
    ]
  },
  {
    name: "fetch_games",
    description: "Fetch games from Chess.com/Lichess (no analysis, fast)",
    args: [
      { name: "username", type: "string", required: true, description: "Username" },
      { name: "platform", type: "string", required: true, description: "'chess.com' or 'lichess'" },
      { name: "max_games", type: "integer", required: false, description: "Number to fetch (default 3)" },
      { name: "time_control", type: "string", required: false, description: "rapid/blitz/bullet/all" },
      { name: "result", type: "string", required: false, description: "win/loss/draw/all" },
      { name: "color", type: "string", required: false, description: "white/black (both if omitted)" },
      { name: "months_back", type: "integer", required: false, description: "How far back to search (default 6)" }
    ]
  },
  {
    name: "fetch_and_review_games",
    description: "Fetch and analyze games with Stockfish (slower but complete)",
    args: [
      { name: "username", type: "string", required: true, description: "Chess.com or Lichess username" },
      { name: "platform", type: "string", required: true, description: "'chess.com' or 'lichess'" },
      { name: "max_games", type: "integer", required: false, description: "Number of games to fetch (default 1)" },
      { name: "games_to_analyze", type: "integer", required: false, description: "Games to analyze (default: max_games)" },
      { name: "depth", type: "integer", required: false, description: "Analysis depth (default 15)" }
    ]
  },
  {
    name: "generate_opening_lesson",
    description: "Build a personalized opening lesson",
    args: [
      { name: "opening_query", type: "string", required: false, description: "Opening name or SAN sequence" },
      { name: "fen", type: "string", required: false, description: "Current board position" },
      { name: "eco", type: "string", required: false, description: "ECO code if known" },
      { name: "orientation", type: "string", required: false, description: "'white' or 'black' perspective" }
    ]
  },
  {
    name: "setup_position",
    description: "Set up a chess position on the board",
    args: [
      { name: "fen", type: "string", required: false, description: "FEN string of position" },
      { name: "pgn", type: "string", required: false, description: "PGN string of game" },
      { name: "orientation", type: "string", required: false, description: "Board orientation: 'white' or 'black' (default 'white')" }
    ]
  },
  {
    name: "generate_graph",
    description: "Generate performance graph from analyzed games",
    args: [
      { name: "graph_type", type: "string", required: true, description: "accuracy_trend/rating_progression/opening_success" },
      { name: "data_type", type: "string", required: false, description: "overall_accuracy/piece_accuracy/time_accuracy" },
      { name: "grouping", type: "string", required: false, description: "game/day/batch5 (default: game)" },
      { name: "limit", type: "integer", required: false, description: "Number of games to include (default 20)" }
    ]
  },
  {
    name: "generate_table",
    description: "Generate comparison table from games data",
    args: [
      { name: "table_type", type: "string", required: true, description: "opening_comparison/time_control_stats/color_comparison" },
      { name: "games", type: "array", required: true, description: "Array of game data" },
      { name: "filters", type: "object", required: false, description: "Additional filters" }
    ]
  }
];
