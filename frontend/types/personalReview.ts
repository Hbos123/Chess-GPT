/**
 * TypeScript types for Personal Review System
 * Matching backend Pydantic models
 */

export type GamePlatform = "chess.com" | "lichess" | "chesscom" | "manual";
export type GameResult = "win" | "loss" | "draw" | "unknown";
export type PlayerColor = "white" | "black";
export type AnalysisIntent = "diagnostic" | "comparison" | "trend" | "focus";
export type GamePhase = "opening" | "middlegame" | "endgame";
export type TimeCategory = "bullet" | "blitz" | "rapid" | "classical";

export interface GameMetadata {
  game_id?: string;
  platform: GamePlatform;
  player_rating: number;
  opponent_rating: number;
  result: GameResult;
  player_color: PlayerColor;
  time_category?: string;
  date?: string;
  pgn?: string;
  has_clock: boolean;
  opening?: string;
}

export interface FilterSpec {
  rating_min?: number;
  rating_max?: number;
  result?: GameResult;
  player_color?: PlayerColor;
  time_category?: TimeCategory;
  opening_eco?: string;
  date_range?: "older" | "recent";
}

export interface CohortSpec {
  label: string;
  filters: FilterSpec;
}

export interface AnalysisPlan {
  intent: AnalysisIntent;
  filters: FilterSpec;
  metrics: string[];
  games_to_analyze: number;
  analysis_depth: number;
  cohorts?: CohortSpec[];
  exemplars?: Record<string, any>;
  focus_phase?: GamePhase;
}

export interface PhaseStats {
  accuracy?: number;
  avg_cp_loss?: number;
  move_count: number;
}

export interface SummaryStats {
  total_games: number;
  wins: number;
  losses: number;
  draws: number;
  win_rate: number;
  overall_accuracy: number;
  avg_accuracy: number;
  avg_cp_loss: number;
  blunder_rate: number;
  mistake_rate: number;
  total_moves: number;
  blunders_per_game: number;
  mistakes_per_game: number;
}

export interface AccuracyByRating {
  rating_range: string;
  accuracy: number;
  game_count: number;
}

export interface OpeningPerformance {
  name: string;
  count: number;
  wins: number;
  losses: number;
  draws: number;
  win_rate: number;
  avg_accuracy: number;
  avg_cp_loss: number;
}

export interface ThemeFrequency {
  name: string;
  frequency: number;
  error_count: number;
  error_rate: number;
  weakness_level: "critical" | "moderate" | "minor";
}

export interface AggregatedStats {
  summary: SummaryStats;
  accuracy_by_rating: AccuracyByRating[];
  opening_performance: OpeningPerformance[];
  theme_frequency: ThemeFrequency[];
  phase_stats: Record<string, PhaseStats>;
  win_rate_by_phase: Record<string, number>;
  mistake_patterns: Record<string, any>;
  time_management: Record<string, any>;
  advanced_metrics: Record<string, any>;
  accuracy_by_color: Record<string, any>;
  performance_by_time_control: Array<Record<string, any>>;
  accuracy_by_time_spent: Array<Record<string, any>>;
  performance_by_tags: Record<string, any>;
  critical_moments: Record<string, any>;
  advantage_conversion: Record<string, any>;
  blunder_triggers: Record<string, any>;
  piece_activity: Array<Record<string, any>>;
  tilt_points: Array<Record<string, any>>;
  diagnostic_insights: Array<Record<string, any>>;
  total_games_analyzed: number;
  error?: string;
  action_plan?: string[];
  analyzed_game_ids?: string[];
  session_id?: string;
}

export interface ProgressUpdate {
  current: number;
  total: number;
  message: string;
  percentage: number;
}

export interface PlanReviewRequest {
  query: string;
  games: GameMetadata[];
}

export interface AggregateReviewRequest {
  plan: AnalysisPlan;
  games: GameMetadata[];
}

export interface GenerateReportRequest {
  query: string;
  plan: AnalysisPlan;
  data: AggregatedStats;
}

