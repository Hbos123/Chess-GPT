/**
 * Frontend Game Sync Service
 * Saves game reviews via backend API (which uses service role key to bypass RLS)
 */

import { getBackendBase } from "./backendBase";
import type { GameMetadata, GameReview } from "./gameReviewTypes";

/**
 * Save a game review via backend API
 * Routes through backend to avoid RLS blocking issues
 * @param forPersonalAnalytics - If true, skips daily game review limit (for profile storage)
 */
export async function saveGameReview(
  userId: string,
  game: GameMetadata,
  review: GameReview,
  forPersonalAnalytics: boolean = true  // Default to true since most saves are for personal analytics
): Promise<string | null> {
  // Reduced logging - removed save log
  
  try {
    const DEBUG_TAG_SAVE =
      typeof window !== "undefined" && (window.localStorage?.getItem("chessterDebugTags") === "1");
    if (DEBUG_TAG_SAVE) {
      const ply = Array.isArray((review as any)?.ply_records) ? (review as any).ply_records : [];
      let withBefore = 0;
      let withAfter = 0;
      let withEither = 0;
      let withAnalyse = 0;
      let withCpLoss = 0;
      let withCategory = 0;
      let maxCpLoss = 0;
      for (const r of ply) {
        const a = (r?.analyse && Array.isArray(r.analyse.tags)) ? r.analyse.tags : [];
        const b = (r?.raw_before && Array.isArray(r.raw_before.tags)) ? r.raw_before.tags : [];
        const c = (r?.raw_after && Array.isArray(r.raw_after.tags)) ? r.raw_after.tags : [];
        if (a.length > 0) withAnalyse += 1;
        if (b.length > 0) withBefore += 1;
        if (c.length > 0) withAfter += 1;
        if (b.length > 0 || c.length > 0) withEither += 1;
        const cp = typeof r?.cp_loss === "number" ? r.cp_loss : undefined;
        if (typeof cp === "number" && cp > 0) {
          withCpLoss += 1;
          if (cp > maxCpLoss) maxCpLoss = cp;
        }
        if (typeof r?.category === "string" && r.category) withCategory += 1;
      }
      console.log(
        `[GameSync] /save_game_review payload coverage: plies=${ply.length}, withCpLoss=${withCpLoss}, maxCpLoss=${maxCpLoss.toFixed?.(1) ?? maxCpLoss}, withCategory=${withCategory}, withAnalyseTags=${withAnalyse}, withRawBefore=${withBefore}, withRawAfter=${withAfter}, withEitherRaw=${withEither}`,
      );
      if (ply[0] && typeof ply[0] === "object") {
        console.log("[GameSync] sample ply_record keys:", Object.keys(ply[0]).slice(0, 30));
        console.log("[GameSync] sample ply_record core:", {
          ply: ply[0].ply,
          move_san: ply[0].move_san,
          uci: ply[0].uci,
          cp_loss: ply[0].cp_loss,
          category: ply[0].category,
          fen_before: typeof ply[0].fen_before === "string" ? `${ply[0].fen_before.slice(0, 32)}...` : undefined,
        });
      }
      const sample = ply.find((r: any) => (r?.raw_before?.tags?.length || 0) > 0 || (r?.raw_after?.tags?.length || 0) > 0);
      if (sample) {
        console.log("[GameSync] sample ply record with raw tags:", {
          ply: sample.ply,
          move: sample.move_san,
          raw_before_tags: sample.raw_before?.tags?.slice?.(0, 5),
          raw_after_tags: sample.raw_after?.tags?.slice?.(0, 5),
          analyse_tags: sample.analyse?.tags?.slice?.(0, 5),
        });
      } else {
        console.warn("[GameSync] no ply records had raw_before/raw_after tags at save time (tag transitions will be empty)");
      }
    }

    const backendBase = getBackendBase();
    const response = await fetch(`${backendBase}/save_game_review`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: userId,
        game: game,
        review: review,
        for_personal_analytics: forPersonalAnalytics  // Pass flag to skip daily limit
      })
    });
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: 'Failed to save game review' }));
      throw new Error(errorData.detail || `HTTP ${response.status}: Failed to save game review`);
    }
    
    const result = await response.json();
    const gameId = result.game_id || null;
    
    if (!gameId) {
      console.warn(`[GameSync] Save succeeded but no game_id returned`);
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
