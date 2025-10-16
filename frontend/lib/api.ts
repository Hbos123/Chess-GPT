import type {
  MetaResponse,
  AnalyzePositionResponse,
  PlayMoveResponse,
  OpeningLookupResponse,
  TacticsPuzzle,
  Annotation,
} from "@/types";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

export async function getMeta(): Promise<MetaResponse> {
  const response = await fetch(`${BACKEND_URL}/meta`);
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
  const params = new URLSearchParams({
    fen,
    lines: lines.toString(),
    depth: depth.toString(),
  });
  const response = await fetch(`${BACKEND_URL}/analyze_position?${params}`);
  if (!response.ok) {
    throw new Error(`Failed to analyze position: ${response.statusText}`);
  }
  return response.json();
}

export async function playMove(
  fen: string,
  userMoveSan: string,
  engineElo?: number,
  timeMs?: number
): Promise<PlayMoveResponse> {
  const response = await fetch(`${BACKEND_URL}/play_move`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      fen,
      user_move_san: userMoveSan,
      engine_elo: engineElo,
      time_ms: timeMs,
    }),
  });
  if (!response.ok) {
    throw new Error(`Failed to play move: ${response.statusText}`);
  }
  return response.json();
}

export async function openingLookup(
  fen: string
): Promise<OpeningLookupResponse> {
  const params = new URLSearchParams({ fen });
  const response = await fetch(`${BACKEND_URL}/opening_lookup?${params}`);
  if (!response.ok) {
    throw new Error(`Failed to lookup opening: ${response.statusText}`);
  }
  return response.json();
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
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to fetch tactic: ${response.statusText}`);
  }
  return response.json();
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

