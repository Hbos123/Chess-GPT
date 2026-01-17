import type {
  MetaResponse,
  AnalyzePositionResponse,
  PlayMoveResponse,
  OpeningLookupResponse,
  TacticsPuzzle,
  Annotation,
} from "@/types";
import { buildLearningHeaders, flushNextActionForLastInteraction, noteInteractionCompleted } from "@/lib/learningClient";
import { getBackendBase } from "@/lib/backendBase";

const BACKEND_URL = getBackendBase();

/**
 * Retry a fetch with exponential backoff - useful for handling backend restarts
 */
async function fetchWithRetry(
  url: string,
  options?: RequestInit,
  maxRetries: number = 3,
  initialDelayMs: number = 500,
  timeoutMs: number = 30000 // Increased to 30 seconds for profile requests
): Promise<Response> {
  let lastError: Error | null = null;
  
  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      // Create abort controller for timeout
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
      
      const fetchOptions = {
        ...options,
        signal: controller.signal
      };
      
      try {
        const response = await fetch(url, fetchOptions);
        clearTimeout(timeoutId);
        return response;
      } catch (fetchErr) {
        clearTimeout(timeoutId);
        throw fetchErr;
      }
    } catch (err) {
      lastError = err instanceof Error ? err : new Error(String(err));
      // Only retry on network errors (Load failed, connection refused, etc.)
      // Don't retry on abort/timeout errors
      if (attempt < maxRetries - 1 && 
          !lastError.message.includes('aborted') && 
          lastError.name !== 'AbortError') {
        const delay = initialDelayMs * Math.pow(2, attempt);
        await new Promise(resolve => setTimeout(resolve, delay));
      } else {
        // Don't retry on timeout/abort
        break;
      }
    }
  }
  
  throw lastError || new Error("Fetch failed after retries");
}

export async function getMeta(): Promise<MetaResponse> {
  const response = await fetchWithRetry(`${BACKEND_URL}/meta`);
  if (!response.ok) {
    throw new Error(`Failed to fetch meta: ${response.statusText}`);
  }
  return response.json();
}

export async function analyzePosition(
  fen: string,
  lines: number = 3,
  depth: number = 16
): Promise<AnalyzePositionResponse> {
  // Prefer local WASM engine only in PLAY/lesson loops.
  // In DISCUSS/ANALYZE we force backend analysis (now D2/D16-backed) so results can
  // build/extend the shared tree and remain consistent with baseline intuition.
  try {
    if (typeof window !== 'undefined') {
      const allowWasm =
        Boolean((window as any).__CHESS_GPT_ALLOW_WASM_ANALYZE) ||
        String((window as any).__CHESS_GPT_MODE || '').toUpperCase() === 'PLAY';
      if (!allowWasm) throw new Error('WASM disabled for this mode');
      const { analyzePositionWasm } = await import('./wasmEngine');
      const res = await analyzePositionWasm(fen, lines, depth);
      return res as any;
    }
  } catch (e) {
    // Fallback to backend below
    console.warn('[analyzePosition] WASM fallback:', e);
  }
  const params = new URLSearchParams({ fen, lines: String(lines), depth: String(depth) });
  // Use longer timeout for position analysis (120s to match backend engine queue timeout)
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 120000); // 120 seconds
  try {
    await flushNextActionForLastInteraction("requested_line");
    const { interactionId, headers } = await buildLearningHeaders();
    const response = await fetch(`${BACKEND_URL}/analyze_position?${params}`, {
      signal: controller.signal,
      headers,
    });
    clearTimeout(timeoutId);
    if (!response.ok) throw new Error(`Failed to analyze position: ${response.statusText}`);
    const data = await response.json();
    noteInteractionCompleted(interactionId);
    return data;
  } catch (err) {
    clearTimeout(timeoutId);
    if (err instanceof Error && err.name === 'AbortError') {
      throw new Error('Position analysis timed out. The engine may be busy.');
    }
    throw err;
  }
}

export async function playMove(
  fen: string,
  userMoveSan?: string | null,
  engineElo?: number,
  timeMs?: number
): Promise<PlayMoveResponse> {
  await flushNextActionForLastInteraction("move_played");
  const { interactionId, headers } = await buildLearningHeaders();
  // Build request body - only include user_move_san if it's a valid string
  // Pydantic Optional fields should be omitted (not set to null) when not provided
  const requestBody: any = {
    fen,
    time_ms: timeMs ?? 1500,
  };
  
  // Only include user_move_san if it's a valid non-empty string
  // When omitted, Pydantic will use the default value of None
  if (userMoveSan !== undefined && userMoveSan !== null && typeof userMoveSan === 'string' && userMoveSan.trim() !== '') {
    requestBody.user_move_san = userMoveSan;
  }
  
  if (engineElo !== undefined && engineElo !== null) {
    requestBody.engine_elo = engineElo;
  }
  
  const response = await fetch(`${BACKEND_URL}/play_move`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...headers,
    },
    body: JSON.stringify(requestBody),
  });
  if (!response.ok) {
    let errorDetail = response.statusText;
    try {
      const errorText = await response.text();
      console.error('[playMove] Error response:', response.status, errorText);
      try {
        const errorData = JSON.parse(errorText);
        // Handle different error response formats
        if (typeof errorData === 'string') {
          errorDetail = errorData;
        } else if (errorData?.detail) {
          errorDetail = typeof errorData.detail === 'string' ? errorData.detail : JSON.stringify(errorData.detail);
        } else if (errorData?.message) {
          errorDetail = typeof errorData.message === 'string' ? errorData.message : JSON.stringify(errorData.message);
        } else if (errorData?.error) {
          errorDetail = typeof errorData.error === 'string' ? errorData.error : JSON.stringify(errorData.error);
        } else {
          errorDetail = JSON.stringify(errorData);
        }
      } catch {
        // If JSON parsing fails, use the raw text
        errorDetail = errorText || response.statusText;
      }
    } catch (e) {
      // If text extraction fails, use statusText
      console.error('Failed to extract error response:', e);
    }
    throw new Error(`Failed to play move: ${errorDetail}`);
  }
  const data = await response.json();
  noteInteractionCompleted(interactionId);
  return data;
}

export async function openingLookup(
  fen: string
): Promise<OpeningLookupResponse> {
  const params = new URLSearchParams({ fen });
  await flushNextActionForLastInteraction("navigation");
  const { interactionId, headers } = await buildLearningHeaders();
  const response = await fetch(`${BACKEND_URL}/opening_lookup?${params}`, { headers });
  if (!response.ok) {
    throw new Error(`Failed to lookup opening: ${response.statusText}`);
  }
  const data = await response.json();
  noteInteractionCompleted(interactionId);
  return data;
}

export async function tacticsNext(
  ratingMin?: number,
  ratingMax?: number
): Promise<TacticsPuzzle> {
  const params = new URLSearchParams();
  if (ratingMin !== undefined) params.append("rating_min", ratingMin.toString());
  if (ratingMax !== undefined) params.append("rating_max", ratingMax.toString());
  const url = params.toString()
    ? `${BACKEND_URL}/tactics_next?${params}`
    : `${BACKEND_URL}/tactics_next`;
  await flushNextActionForLastInteraction("navigation");
  const { interactionId, headers } = await buildLearningHeaders();
  const response = await fetch(url, { headers });
  if (!response.ok) {
    throw new Error(`Failed to fetch tactic: ${response.statusText}`);
  }
  const data = await response.json();
  noteInteractionCompleted(interactionId);
  return data;
}

export async function annotate(annotation: Annotation): Promise<Annotation> {
  const response = await fetch(`${BACKEND_URL}/annotate`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(annotation),
  });
  if (!response.ok) {
    throw new Error(`Failed to annotate: ${response.statusText}`);
  }
  return response.json();
}

export async function reviewGame(pgnString: string): Promise<any> {
  const params = new URLSearchParams({ pgn_string: pgnString });
  const response = await fetch(`${BACKEND_URL}/review_game?${params}`, {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error(`Failed to review game: ${response.statusText}`);
  }
  return response.json();
}

export interface LookupGameSummary {
  id: string;
  platform: string;
  white: string;
  black: string;
  result: string;
  date: string;
  fen: string;
  pgn: string;
  move_count?: number;
  opponent_name?: string;
}

export async function lookupGames(
  username: string,
  opponent?: string,
  platform: string = "chess.com",
  maxGames: number = 10
): Promise<LookupGameSummary[]> {
  const params = new URLSearchParams({
    username,
    platform,
    max_games: String(maxGames),
  });
  if (opponent) {
    params.append("opponent", opponent);
  }

  const response = await fetch(`${BACKEND_URL}/game_lookup?${params.toString()}`);
  if (!response.ok) {
    throw new Error(`Failed to lookup games: ${response.statusText}`);
  }
  const data = await response.json();
  return data?.games ?? [];
}

export interface VisionSquare {
  square: string;
  piece?: string;
  confidence: number;
}

export interface VisionBoardResponse {
  fen: string;
  confidence: number;
  orientation: "white" | "black";
  uncertain_squares: VisionSquare[];
  notes?: string | null;
}

export async function analyzeBoardPhoto(formData: FormData): Promise<VisionBoardResponse> {
  const response = await fetch(`${BACKEND_URL}/vision/board`, {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    let detail: any = null;
    try {
      detail = await response.json();
    } catch {
      // ignore
    }
    const message = detail?.detail || `Vision analysis failed: ${response.statusText}`;
    throw new Error(message);
  }
  return response.json();
}

// Lichess opening book API
export async function checkLichessBook(fen: string): Promise<any> {
  try {
    const response = await fetch(`https://explorer.lichess.ovh/masters?fen=${encodeURIComponent(fen)}`);
    if (!response.ok) return null;
    const data = await response.json();
    return data;
  } catch {
    return null;
  }
}

export interface ProfileAccountInput {
  platform: "chesscom" | "lichess";
  username: string;
}

export interface ProfileStatusSummary {
  state: string;
  message: string;
  total_accounts: number;
  completed_accounts: number;
  total_games_estimate: number;
  games_indexed: number;
  progress_percent: number;
  started_at?: string | null;
  finished_at?: string | null;
  last_updated?: string | null;
  last_error?: string | null;
}

export interface ProfileHighlight {
  label: string;
  value: string;
  platform?: string;
}

export interface ProfileGameSummary {
  game_id?: string;
  platform?: string;
  opponent_name?: string;
  result?: string;
  date?: string;
  url?: string;
  time_category?: string;
  player_color?: string;
  player_rating?: number;
}

export interface ProfileOverviewResponse {
  preferences?: {
    accounts?: ProfileAccountInput[];
    time_controls?: string[];
  };
  status: ProfileStatusSummary;
  highlights: ProfileHighlight[];
  games: ProfileGameSummary[];
}

export interface SaveProfilePreferencesPayload {
  userId: string;
  accounts: ProfileAccountInput[];
  timeControls: string[];
}

export async function saveProfilePreferences(
  payload: SaveProfilePreferencesPayload
): Promise<ProfileOverviewResponse> {
  const response = await fetch(`${BACKEND_URL}/profile/preferences`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      user_id: payload.userId,
      accounts: payload.accounts,
      time_controls: payload.timeControls,
    }),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`Failed to save profile preferences: ${detail}`);
  }
  return response.json();
}

export async function fetchProfileOverview(userId: string): Promise<ProfileOverviewResponse> {
  const params = new URLSearchParams({ user_id: userId });
  const response = await fetchWithRetry(`${BACKEND_URL}/profile/overview?${params.toString()}`);
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`Failed to fetch profile overview: ${detail}`);
  }
  return response.json();
}

export interface ProfileStatsResponse {
  stats: {
    overall?: {
      total_games: number;
      wins: number;
      losses: number;
      draws: number;
      win_rate: number;
      average_accuracy?: number | null;
      blunder_rate?: number | null;
      mistake_rate?: number | null;
    };
    openings?: {
      top: Array<{ name: string; games: number; win_rate: number; average_accuracy?: number | null; blunder_rate?: number | null }>;
      bottom: Array<{ name: string; games: number; win_rate: number; average_accuracy?: number | null; blunder_rate?: number | null }>;
    };
    tags?: {
      best: Array<{ name: string; games: number; win_rate: number; avg_cp_loss?: number | null }>;
      worst: Array<{ name: string; games: number; win_rate: number; avg_cp_loss?: number | null }>;
    };
    phases?: {
      opening?: number | null;
      middlegame?: number | null;
      endgame?: number | null;
    };
    personality?: {
      notes: string[];
      tendencies: Array<{ title: string; detail: string; confidence?: string }>;
    };
    advanced?: {
      accuracy_by_piece?: Array<{ piece: string; avg_cp_loss: number; error_rate: number; moves: number }>;
      phase_piece_heatmap?: Record<string, Record<string, number>>;
      position_types?: Array<{ type: string; avg_cp_loss: number; error_rate: number; moves: number }>;
      advantage_regimes?: Array<{ bucket: string; avg_cp_loss: number; error_rate: number; moves: number }>;
      tactic_motifs?: Array<{ motif: string; found: number; missed: number; miss_rate: number; avg_loss: number }>;
      tactic_phases?: Array<{ phase: string; opportunities: number; found: number; missed: number }>;
      structural_tags?: Array<{ tag: string; occurrences: number; avg_cp_loss: number; win_rate: number }>;
      weakness?: Record<string, { moves: number; avg_cp_loss: number }>;
      time_buckets?: Array<{ bucket: string; avg_cp_loss: number; error_rate: number; moves: number }>;
      rating_buckets?: Array<{ bucket: string; avg_cp_loss: number; error_rate: number; moves: number }>;
      playstyle?: {
        aggression_bias?: number | null;
        material_bias?: number | null;
        simplification_bias?: number | null;
        king_safety_risk?: number | null;
      };
      conversion?: {
        winning_positions: number;
        converted: number;
        holds: number;
        squandered: number;
        conversion_rate?: number | null;
        max_advantage_cp?: number;
      };
      resilience?: {
        defensive_positions: number;
        swindles: number;
        saves: number;
        collapsed: number;
        save_rate?: number | null;
        max_deficit_cp?: number;
      };
      opening_families?: Array<{ family: string; games: number; win_rate: number }>;
      endgame_skills?: {
        opening_accuracy?: number | null;
        middlegame_accuracy?: number | null;
        endgame_accuracy?: number | null;
      };
    };
    insights?: {
      accuracy?: string[];
      tactics?: string[];
      structure?: string[];
      playstyle?: string[];
      conversion?: string[];
    };
  };
}

export async function fetchProfileStats(userId: string): Promise<ProfileStatsResponse> {
  const params = new URLSearchParams({ user_id: userId });
  const response = await fetchWithRetry(`${BACKEND_URL}/profile/stats?${params.toString()}`);
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`Failed to fetch profile stats: ${detail}`);
  }
  return response.json();
}

// Habits data types
export interface HabitEntry {
  game_id: string;
  game_date: string;
  accuracy: number;
  count: number;
  significant?: boolean;
}

export interface Habit {
  name: string;
  display_name: string;
  category: string;
  habit_type: 'tag' | 'phase' | 'endgame' | 'tag_pref' | 'time';
  accuracy: number;
  baseline: number;
  deviation: number;
  deviation_percent: number;
  sample_size: number;
  total_occurrences: number;
  variance: number;
  significance: number;
  trend: 'improving' | 'declining' | 'stable';
  trend_value: number;
  sparkline: number[];
  history: HabitEntry[];
  // Optional metrics for different habit types
  win_rate?: number;
  avg_cp_loss?: number;
  error_rate?: number;
  preference_signal?: string;
  preference_strength?: number;
  created_accuracy?: number;
  removed_accuracy?: number;
  extremeness?: number;
}

export interface TrendSeries {
  name: string;
  habit_key: string;
  color: string;
  series: (HabitEntry | null)[];
}

export interface ProfileHabitsResponse {
  habits: Habit[];
  strengths: Habit[];
  weaknesses: Habit[];
  baseline_accuracy: number;
  total_games: number;
  trend_chart: {
    dates: string[];
    series: TrendSeries[];
    baseline: number;
  };
}

export async function fetchProfileHabits(userId: string): Promise<ProfileHabitsResponse> {
  // No timeout for habits - computation can take time, and data is saved to Supabase
  // so it can be fetched later even if the request is slow or cancelled
  const response = await fetch(`${BACKEND_URL}/profile/habits/${userId}`);
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`Failed to fetch profile habits: ${detail}`);
  }
  return response.json();
}

export interface OpeningLessonRequestPayload {
  userId: string;
  chatId?: string | null;
  openingQuery?: string;
  fen?: string;
  eco?: string;
  orientation?: "white" | "black";
  variationHint?: string;
}

export interface OpeningLessonSection {
  type: "personal_overview" | "model_lines" | "user_games" | "problem_patterns" | "drills" | "summary";
  title: string;
  description?: string;
}

export interface OpeningLessonBlueprint {
  lesson_id: string;
  title: string;
  sections: OpeningLessonSection[];
}

export interface OpeningPracticePosition {
  fen: string;
  // Back-compat: older/alternate shapes may nest the FEN under `position.fen`.
  position?: {
    fen?: string;
    [key: string]: any;
  };
  objective?: string;
  hints?: string[];
  candidates?: string[];
  side?: "white" | "black";
  difficulty?: string;
  themes?: string[];
}

export interface OpeningLessonResponse {
  lesson: OpeningLessonBlueprint;
  personal_overview?: Record<string, any>;
  model_lines?: Record<string, any>;
  user_games?: Array<Record<string, any>>;
  problem_patterns?: Record<string, any>;
  master_refs?: Array<Record<string, any>>;
  drills?: Record<string, any>;
  summary?: Record<string, any>;
  personalization?: any;
  metadata?: any;
  recent_lessons?: any[];
  practice_positions?: OpeningPracticePosition[];
  positions?: OpeningPracticePosition[];
  canonical_plan?: any;
  lesson_tree?: Array<Record<string, any>>;
}

export async function generateOpeningLesson(
  payload: OpeningLessonRequestPayload
): Promise<OpeningLessonResponse> {
  const response = await fetch(`${BACKEND_URL}/lessons/opening`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      user_id: payload.userId,
      chat_id: payload.chatId,
      opening_query: payload.openingQuery,
      fen: payload.fen,
      eco: payload.eco,
      orientation: payload.orientation,
      variation_hint: payload.variationHint,
    }),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`Failed to generate opening lesson: ${detail}`);
  }
  return response.json();
}

