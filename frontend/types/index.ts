// Backend API response types

export interface MetaResponse {
  name: string;
  version: string;
  modes: string[];
  system_prompt: string;
}

export interface CandidateMove {
  move: string;
  uci: string;
  eval_cp: number;
  pv_san: string;
  depth: number;
}

export interface Threat {
  side: "W" | "B";
  desc: string;
  delta_cp: number;
  pv_san: string;
}

export interface PieceQuality {
  W: { [piece: string]: number };
  B: { [piece: string]: number };
}

export interface AnalyzePositionResponse {
  eval_cp: number;
  win_prob: number;
  phase: string;
  candidate_moves: CandidateMove[];
  threats: Threat[];
  piece_quality: PieceQuality;
  themes: string[];
}

export interface PlayMoveResponse {
  legal: boolean;
  user_move_san: string;
  engine_move_san?: string;
  new_fen?: string;
  eval_cp_after?: number;
  commentary_points?: string[];
  error?: string;
}

export interface OpeningLookupResponse {
  eco: string;
  name: string;
  book_moves: string[];
  novelty_ply: number | null;
}

export interface TacticsPuzzle {
  id: string;
  rating: number;
  fen: string;
  side_to_move: "w" | "b";
  prompt: string;
  solution_pv_san: string;
  themes: string[];
}

export interface AnnotationComment {
  ply: number;
  text: string;
}

export interface AnnotationNAG {
  ply: number;
  nag: string;
}

export interface AnnotationArrow {
  from: string;
  to: string;
  color?: string;
}

export interface AnnotationHighlight {
  sq: string;
  color?: string;
}

export interface Annotation {
  fen: string;
  pgn: string;
  comments: AnnotationComment[];
  nags: AnnotationNAG[];
  arrows: AnnotationArrow[];
  highlights: AnnotationHighlight[];
}

// Frontend types

export type Mode = "PLAY" | "ANALYZE" | "TACTICS" | "DISCUSS";

export interface ChatMessage {
  role: "user" | "assistant" | "system" | "graph" | "button";
  content: string;
  meta?: any;
  graphData?: any[];
  buttonAction?: string;
  buttonLabel?: string;
}

export interface AppState {
  fen: string;
  pgn: string;
  mode: Mode;
  annotations: Annotation;
  moveHistory: string[];
  currentPly: number;
}

