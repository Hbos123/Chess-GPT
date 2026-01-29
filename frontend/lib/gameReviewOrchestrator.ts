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

  // Reduced logging - only log start
  if (max_games <= 5) {
    console.log(`[GameReviewOrchestrator] Starting review: ${max_games} games`);
  }

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

    const gamesToAnalyze = await getGamesToAnalyze(
      userId,
      username,
      platform,
      fetchOptions
    );
    
    // Limit to max_games from subscription tier (this is the authoritative source)
    const limitedGames = gamesToAnalyze.slice(0, max_games);
    if (limitedGames.length < gamesToAnalyze.length) {
      console.log(`[GameReviewOrchestrator] Limiting to ${max_games} games (tier limit) from ${gamesToAnalyze.length} available`);
    }
    
    // Reduced logging - only log if many games
    if (limitedGames.length > 10) {
      console.log(`[GameReviewOrchestrator] ${limitedGames.length} games to analyze (of ${gamesToAnalyze.length} available)`);
    }

    if (!limitedGames || limitedGames.length === 0) {
      result.success = true;
      return result;
    }

    result.games_fetched = limitedGames.length;

    if (progressCallback) {
      progressCallback(
        "analyzing",
        `Found ${limitedGames.length} game(s) to analyze (of ${gamesToAnalyze.length} available)`,
        0.1
      );
    }

    // Step 2: Analyze each game
    const reviews: GameReview[] = [];
    const errors: string[] = [];

    for (let i = 0; i < limitedGames.length; i++) {
      const game = limitedGames[i];
      const gameProgress = 0.1 + (0.7 * i) / limitedGames.length;
      const nextGameProgress = 0.1 + (0.7 * (i + 1)) / limitedGames.length;

      try {
        if (progressCallback) {
          progressCallback(
            "analyzing",
            `Analyzing game ${i + 1}/${limitedGames.length}...`,
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
              // Format message to include both game and move info for better parsing
              const moveMatch = message.match(/move (\d+)\/(\d+)/i) || message.match(/Analyzing move (\d+)\/(\d+)/i);
              if (moveMatch) {
                // Use limitedGames.length (max_games from subscription tier) instead of gamesToAnalyze.length
                progressCallback(phase, `Game ${i + 1}/${limitedGames.length} - Move ${moveMatch[1]}/${moveMatch[2]}`, scaledProgress, replace);
              } else {
                progressCallback(phase, `Game ${i + 1}/${limitedGames.length} - ${message}`, scaledProgress, replace);
              }
            }
          }
        );

        // Reduced logging - only log every 5th game or last game
        if (i % 5 === 0 || i === limitedGames.length - 1) {
          const accuracy = typeof review.stats === 'object' && 'overall_accuracy' in review.stats
            ? (review.stats as any).overall_accuracy ?? 0
            : (review.stats as any).overall_accuracy ?? 0;
          console.log(`[GameReviewOrchestrator] Game ${i + 1}/${limitedGames.length}: ${accuracy.toFixed(1)}%`);
        }
        reviews.push(review);

        // Step 3: Save immediately after each game review
        if (progressCallback) {
          progressCallback(
            "saving",
            `Saving game ${i + 1}/${limitedGames.length}...`,
            nextGameProgress - 0.05
          );
        }

        try {
          // Pass forPersonalAnalytics=true to skip daily game review limit (these are for profile storage)
          const gameId = await saveGameReview(userId, game, review, true);
          if (gameId) {
            result.games_saved++;
            // Reduced logging - only log every 5th save or errors
            if (result.games_saved % 5 === 0 || result.games_saved === limitedGames.length) {
              console.log(`[GameReviewOrchestrator] Saved ${result.games_saved}/${limitedGames.length} games`);
            }
          } else {
            errors.push(`Failed to save game ${i + 1}`);
          }
        } catch (saveError: any) {
          console.error(`[GameReviewOrchestrator] Error saving game ${i + 1}:`, saveError);
          // Check if it's a tier limit error
          const errorMessage = saveError.message || String(saveError);
          if (errorMessage.includes("not available") || 
              errorMessage.includes("limit") || 
              errorMessage.includes("storage") ||
              errorMessage.includes("403") ||
              errorMessage.includes("429")) {
            errors.push(`Cannot save game ${i + 1}: ${errorMessage}`);
            // Stop trying to save more games if it's a limit issue
            if (errorMessage.includes("not available") || errorMessage.includes("storage")) {
              console.warn(`[GameReviewOrchestrator] Stopping saves due to tier limit: ${errorMessage}`);
              break;
            }
          } else {
            errors.push(`Failed to save game ${i + 1}: ${errorMessage}`);
          }
          // Continue with next game for other errors
        }

        result.games_analyzed++;

        if (progressCallback) {
          progressCallback(
            "complete",
            `Completed game ${i + 1}/${limitedGames.length}`,
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
    
    // Reduced logging - only log summary
    if (result.success) {
      console.log(`[GameReviewOrchestrator] Complete: ${result.games_saved} saved`);
    } else if (errors.length > 0) {
      console.warn(`[GameReviewOrchestrator] Errors: ${errors.length}`);
    }

    // Set first game and review
    if (limitedGames.length > 0) {
      result.first_game = limitedGames[0];
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
