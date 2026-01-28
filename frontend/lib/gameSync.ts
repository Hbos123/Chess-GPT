/**
 * Frontend Game Sync Service
 * Saves game reviews via backend API (which uses service role key to bypass RLS)
 */

import { getBackendBase } from "./backendBase";
import type { GameMetadata, GameReview } from "./gameReviewTypes";

/**
 * Save a game review via backend API
 * Routes through backend to avoid RLS blocking issues
 */
export async function saveGameReview(
  userId: string,
  game: GameMetadata,
  review: GameReview
): Promise<string | null> {
  console.log(`[GameSync] Saving game review for game ${game.game_id} (${game.platform}) via backend API`);
  
  try {
    const backendBase = getBackendBase();
    const response = await fetch(`${backendBase}/save_game_review`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: userId,
        game: game,
        review: review
      })
    });
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: 'Failed to save game review' }));
      throw new Error(errorData.detail || `HTTP ${response.status}: Failed to save game review`);
    }
    
    const result = await response.json();
    const gameId = result.game_id || null;
    
    if (gameId) {
      console.log(`[GameSync] Game saved successfully via backend, ID: ${gameId}`);
    } else {
      console.warn(`[GameSync] Backend returned success but no game_id`);
    }
    
    return gameId;
  } catch (error) {
    console.error("[GameSync] Error saving game review via backend:", error);
    throw error;
  }
}

/**
 * Check if a game has already been reviewed
 * Uses backend endpoint to avoid RLS issues
 */
export async function isGameReviewed(
  userId: string,
  platform: string,
  gameId: string
): Promise<boolean> {
  try {
    const backendBase = getBackendBase();
    // Use get_games_to_analyze endpoint which filters out already reviewed games
    const response = await fetch(`${backendBase}/get_games_to_analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: userId,
        username: "", // Not needed for checking
        platform: platform,
        max_games: 1, // We only need to check if this specific game exists
      })
    });
    
    if (!response.ok) {
      return false; // Assume not reviewed on error
    }
    
    const data = await response.json();
    // Check if the game_id is in the already_reviewed list
    // The endpoint returns games_to_analyze (not reviewed) and already_reviewed count
    // We need to check if our game_id is NOT in games_to_analyze
    const gamesToAnalyze = data.games_to_analyze || [];
    const gameExists = gamesToAnalyze.some(
      (g: any) => String(g.game_id || g.external_id) === String(gameId)
    );
    
    // If game is NOT in games_to_analyze, it's already reviewed
    return !gameExists;
  } catch (error) {
    console.error("Error checking game review status:", error);
    return false; // Assume not reviewed on error
  }
}
