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
  fen: string;
  eval_cp: number;
  pv: string[];
  phase: string;
  
  // Theme-based analysis (new structure)
  white_analysis: {
    chunk_1_immediate: {
      description: string;
      material_balance_cp: number;
      positional_cp_significance: number;
      theme_scores: { [key: string]: number };
      tags: any[];
    };
    chunk_2_plan_delta: {
      description: string;
      plan_type: string;
      plan_explanation: string;
      material_delta_cp: number;
      positional_delta_cp: number;
      theme_changes: { [key: string]: number };
    };
  };
  black_analysis: {
    chunk_1_immediate: {
      description: string;
      material_balance_cp: number;
      positional_cp_significance: number;
      theme_scores: { [key: string]: number };
      tags: any[];
    };
    chunk_2_plan_delta: {
      description: string;
      plan_type: string;
      plan_explanation: string;
      material_delta_cp: number;
      positional_delta_cp: number;
      theme_changes: { [key: string]: number };
    };
  };
  
  // Legacy fields (optional, for backward compatibility)
  candidate_moves?: CandidateMove[];
  threats?: Threat[];
  piece_quality?: PieceQuality;
  themes?: string[];
}

export interface PlayMoveResponse {
  legal: boolean;
  user_move_san: string;
  engine_move_san?: string;
  // Some flows (e.g. opening lesson side-adjust) use the engine's best move SAN.
  best_move_san?: string;
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

export interface ChatGraphData {
  graph_id: string;
  series: Array<{
    id: string;
    name: string;
    color: string;
    rawValues: Array<number | null>;
    normalizedValues: Array<number | null>;
  }>;
  xLabels: string[];
  grouping: "game" | "day" | "batch5";
}

export interface ChatMessage {
  id?: string;
  role: "user" | "assistant" | "system" | "graph" | "button" | "expandable_table" | "board";
  content: string;
  meta?: any;
  graphData?: ChatGraphData; // Updated to use proper type
  buttonAction?: string;
  buttonLabel?: string;
  tableTitle?: string;
  tableContent?: string;
  timestamp?: Date;
  fen?: string;  // Track which position this message was sent from
  tabId?: string; // Scope messages to a specific board tab
  image?: {
    data: string; // base64 or URL
    filename?: string;
    mimeType?: string;
    uploading?: boolean; // true while uploading
    uploadProgress?: number; // 0-100
  };
}

export interface AppState {
  fen: string;
  pgn: string;
  mode: Mode;
  annotations: Annotation;
  moveHistory: string[];
  currentPly: number;
}

