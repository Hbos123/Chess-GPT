/**
 * Main Orchestrator for Frontend Game Review
 * Coordinates fetching, analyzing, and saving games
 */

import { fetchGames } from "./gameFetcher";
import { reviewGame } from "./gameReviewer";
import { saveGameReview, isGameReviewed } from "./gameSync";
import { getBackendBase } from "./backendBase";
import type {
  GameMetadata,
  GameReview,
  GameFetchOptions,
  GameReviewOptions,
  ReviewProgressCallback,
} from "./gameReviewTypes";

export interface ReviewResult {
  success: boolean;
  games_fetched: number;
  games_analyzed: number;
  games_saved: number;
  errors: string[];
  reviews: GameReview[];
  first_game?: GameMetadata;
  first_game_review?: GameReview;
}

/**
 * Main function to fetch and review games on the frontend
 * Falls back to backend if frontend fails
 */
export async function fetchAndReviewGamesFrontend(
  options: GameFetchOptions & GameReviewOptions,
  userId: string,
  progressCallback?: ReviewProgressCallback
): Promise<ReviewResult> {
  const {
    username,
    platform,
    max_games = 1,
    depth = 14,
    focus_color,
    review_subject = "player",
    ...fetchOptions
  } = options;

  console.log(`[GameReviewOrchestrator] Starting frontend review for ${username} on ${platform}, max_games: ${max_games}, depth: ${depth}`);

  const result: ReviewResult = {
    success: false,
    games_fetched: 0,
    games_analyzed: 0,
    games_saved: 0,
    errors: [],
    reviews: [],
  };

  try {
    // Step 1: Get list of games that need analysis from backend
    if (progressCallback) {
      progressCallback("fetching", "Getting games to analyze...", 0.05);
    }

    console.log(`[GameReviewOrchestrator] Requesting games to analyze from backend...`);
    const gamesToAnalyze = await getGamesToAnalyze(
      userId,
      username,
      platform,
      fetchOptions
    );
    console.log(`[GameReviewOrchestrator] Received ${gamesToAnalyze.length} game(s) to analyze`);

    if (!gamesToAnalyze || gamesToAnalyze.length === 0) {
      result.success = true;
      return result;
    }

    result.games_fetched = gamesToAnalyze.length;

    if (progressCallback) {
      progressCallback(
        "analyzing",
        `Found ${gamesToAnalyze.length} game(s) to analyze`,
        0.1
      );
    }

    // Step 2: Analyze each game
    const reviews: GameReview[] = [];
    const errors: string[] = [];

    for (let i = 0; i < gamesToAnalyze.length; i++) {
      const game = gamesToAnalyze[i];
      const gameProgress = 0.1 + (0.7 * i) / gamesToAnalyze.length;
      const nextGameProgress = 0.1 + (0.7 * (i + 1)) / gamesToAnalyze.length;

      try {
        console.log(`[GameReviewOrchestrator] Starting review for game ${i + 1}/${gamesToAnalyze.length}: ${game.game_id}`);
        
        if (progressCallback) {
          progressCallback(
            "analyzing",
            `Reviewing game ${i + 1}/${gamesToAnalyze.length}...`,
            gameProgress
          );
        }

        // Review game using Stockfish
        const review = await reviewGame(
          game,
          { depth, focus_color, review_subject },
          (phase, message, progress, replace) => {
            if (progressCallback && progress !== undefined) {
              // Scale progress within this game's range
              const scaledProgress =
                gameProgress + (progress || 0) * (nextGameProgress - gameProgress);
              progressCallback(phase, message, scaledProgress, replace);
            }
          }
        );

        console.log(`[GameReviewOrchestrator] Review completed for game ${i + 1}, accuracy: ${review.stats.overall_accuracy.toFixed(1)}%`);
        reviews.push(review);

        // Step 3: Save immediately after each game review
        if (progressCallback) {
          progressCallback(
            "saving",
            `Saving game ${i + 1}/${gamesToAnalyze.length}...`,
            nextGameProgress - 0.05
          );
        }

        try {
          console.log(`[GameReviewOrchestrator] Saving game ${i + 1} to Supabase...`);
          const gameId = await saveGameReview(userId, game, review);
          if (gameId) {
            result.games_saved++;
            console.log(`[GameReviewOrchestrator] Game ${i + 1} saved successfully, ID: ${gameId}`);
          } else {
            console.warn(`[GameReviewOrchestrator] Failed to save game ${i + 1}: no game ID returned`);
            errors.push(`Failed to save game ${i + 1}`);
          }
        } catch (saveError: any) {
          console.error(`[GameReviewOrchestrator] Error saving game ${i + 1}:`, saveError);
          errors.push(`Failed to save game ${i + 1}: ${saveError.message}`);
          // Continue with next game
        }

        result.games_analyzed++;

        if (progressCallback) {
          progressCallback(
            "complete",
            `Completed game ${i + 1}/${gamesToAnalyze.length}`,
            nextGameProgress
          );
        }
      } catch (error: any) {
        console.error(`Error reviewing game ${i + 1}:`, error);
        errors.push(`Game ${i + 1}: ${error.message || "Unknown error"}`);
        // Continue with next game
      }
    }

    result.reviews = reviews;
    result.errors = errors;
    result.success = result.games_analyzed > 0;
    
    console.log(`[GameReviewOrchestrator] Review complete: ${result.games_analyzed} analyzed, ${result.games_saved} saved, ${errors.length} errors`);

    // Set first game and review
    if (gamesToAnalyze.length > 0) {
      result.first_game = gamesToAnalyze[0];
    }
    if (reviews.length > 0) {
      result.first_game_review = reviews[0];
    }

    if (progressCallback) {
      progressCallback(
        "complete",
        `Analysis complete: ${result.games_analyzed} game(s) reviewed`,
        0.95
      );
    }

    return result;
  } catch (error: any) {
    console.error("Error in fetchAndReviewGamesFrontend:", error);
    result.errors.push(error.message || "Unknown error");
    result.success = false;
    return result;
  }
}

/**
 * Get games that need to be analyzed from backend
 */
async function getGamesToAnalyze(
  userId: string,
  username: string,
  platform: string,
  options: Partial<GameFetchOptions>
): Promise<GameMetadata[]> {
  console.log(`[GameReviewOrchestrator] Requesting games to analyze: ${username} on ${platform}`);
  
  try {
    const response = await fetch(`${getBackendBase()}/get_games_to_analyze`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        user_id: userId,
        username,
        platform,
        max_games: options.max_games || 100,
        months_back: options.months_back || 6,
        date_from: options.date_from,
        date_to: options.date_to,
        opponent: options.opponent,
        opening_eco: options.opening_eco,
        color: options.color,
        time_control: options.time_control,
        result_filter: options.result_filter || "all",
        min_moves: options.min_moves,
        min_opponent_rating: options.min_opponent_rating,
        max_opponent_rating: options.max_opponent_rating,
        sort: options.sort || "date_desc",
        offset: options.offset || 0,
      }),
    });

    if (!response.ok) {
      throw new Error(`Backend error: ${response.statusText}`);
    }

    const data = await response.json();
    console.log(`[GameReviewOrchestrator] Backend response: ${data.needs_analysis || 0} games need analysis, ${data.already_reviewed || 0} already reviewed`);
    return data.games_to_analyze || [];
  } catch (error: any) {
    console.error("[GameReviewOrchestrator] Error getting games to analyze:", error);
    // Fallback: try fetching directly (will need to filter duplicates client-side)
    try {
      const games = await fetchGames({
        username,
        platform,
        ...options,
      } as GameFetchOptions);

      // Filter out already reviewed games
      const gamesToAnalyze: GameMetadata[] = [];
      for (const game of games) {
        const reviewed = await isGameReviewed(
          userId,
          platform,
          game.game_id
        );
        if (!reviewed) {
          gamesToAnalyze.push(game);
        }
      }
      return gamesToAnalyze;
    } catch (fetchError) {
      console.error("Fallback fetch also failed:", fetchError);
      throw error; // Throw original error
    }
  }
}

/**
 * Check if frontend review is available (has Stockfish worker)
 */
export function isFrontendReviewAvailable(): boolean {
  return typeof window !== "undefined" && "Worker" in window;
}
