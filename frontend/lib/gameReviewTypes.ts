/**
 * TypeScript types for frontend game fetching and reviewing
 */

export interface GameMetadata {
  game_id: string;
  platform: "chess.com" | "lichess";
  url: string;
  date: string;
  player_color: "white" | "black";
  player_rating: number;
  opponent_rating: number;
  opponent_name: string;
  result: "win" | "loss" | "draw" | "unknown";
  opening?: string;
  eco?: string;
  termination?: string;
  time_control?: string | number;
  time_category?: string;
  pgn: string;
  has_clock?: boolean;
  accuracies?: {
    white?: number;
    black?: number;
  };
  player_accuracy?: number;
  opponent_accuracy?: number;
}

export interface PlyRecord {
  ply: number;
  move_san: string;
  uci?: string;
  fen_before: string;
  fen_after: string;
  eval_before_cp: number;
  eval_after_cp: number;
  cp_loss?: number;
  category?: string;
  is_blunder?: boolean;
  is_mistake?: boolean;
  is_inaccuracy?: boolean;
  is_missed_win?: boolean;
  best_move_san?: string;
  best_move_uci?: string;
  best_move_eval_cp?: number;
  phase?: "opening" | "middlegame" | "endgame";
  // Tag extraction fields (matching backend format)
  analyse?: {
    tags?: Array<{ tag_name?: string; tag?: string; name?: string; [key: string]: any }>;
    [key: string]: any;
  };
  raw_before?: {
    tags?: Array<{ tag_name?: string; tag?: string; name?: string; [key: string]: any }>;
    [key: string]: any;
  };
  raw_after?: {
    tags?: Array<{ tag_name?: string; tag?: string; name?: string; [key: string]: any }>;
    [key: string]: any;
  };
  side_moved?: "white" | "black";
  engine?: {
    played_eval_after_cp?: number;
    eval_before_cp?: number;
    best_move_tags?: Array<{ tag_name?: string; tag?: string; name?: string; [key: string]: any }>;
    [key: string]: any;
  };
}

export interface GameReviewStats {
  overall_accuracy: number;
  opening_accuracy: number;
  middlegame_accuracy: number;
  endgame_accuracy: number;
  avg_cp_loss: number;
  blunders: number;
  mistakes: number;
  inaccuracies: number;
  missed_wins: number;
  total_moves: number;
}

export interface GameReview {
  pgn: string;
  ply_records: PlyRecord[];
  stats: GameReviewStats | {
    white?: GameReviewStats;
    black?: GameReviewStats;
    overall_accuracy?: number;
    opening_accuracy?: number;
    middlegame_accuracy?: number;
    endgame_accuracy?: number;
    avg_cp_loss?: number;
    blunders?: number;
    mistakes?: number;
    inaccuracies?: number;
    missed_wins?: number;
    total_moves?: number;
  };
  opening?: {
    name_final?: string;
    eco_final?: string;
    theory_exit_ply?: number;
  };
  phases?: Array<{
    from: string;
    to: string;
    ply: number;
  }>;
  side_focus?: "white" | "black" | "both";
  key_points?: Array<{
    ply: number;
    move_san: string;
    labels?: string[];
    category?: string;
    note?: string;
  }>;
  all_key_moments?: Array<{
    ply: number;
    move_san: string;
    labels?: string[];
    category?: string;
    note?: string;
    primary_label?: string;
    advantage_swing?: number;
    cp_loss?: number;
    side?: string;
    evalBefore?: number;
    evalAfter?: number;
    crossed100?: boolean;
    crossed200?: boolean;
    crossed300?: boolean;
  }>;
  game_metadata?: {
    game_character?: string;
    endgame_type?: string;
    player_color?: "white" | "black";
    focus_color?: "white" | "black" | "both";
    review_subject?: "player" | "opponent" | "both";
  };
  metadata?: {
    platform: string;
    player_rating: number;
    result: string;
    player_color: "white" | "black";
    focus_color?: "white" | "black" | "both";
    review_subject?: "player" | "opponent" | "both";
    time_control?: string | number;
    time_category?: string;
    termination?: string;
    date?: string;
  };
}

export interface GameFetchOptions {
  username: string;
  platform: "chess.com" | "lichess";
  max_games?: number;
  months_back?: number;
  date_from?: string;
  date_to?: string;
  opponent?: string;
  opening_eco?: string;
  color?: "white" | "black";
  time_control?: string;
  result_filter?: "all" | "win" | "loss" | "draw";
  min_moves?: number;
  min_opponent_rating?: number;
  max_opponent_rating?: number;
  sort?: "date_desc" | "date_asc";
  offset?: number;
}

export interface GameReviewOptions {
  depth?: number;
  focus_color?: "white" | "black" | "both";
  review_subject?: "player" | "opponent" | "both";
}

export interface ReviewProgressCallback {
  (phase: string, message: string, progress?: number, replace?: boolean): void;
}
