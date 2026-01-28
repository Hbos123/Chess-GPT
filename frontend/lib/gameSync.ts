/**
 * Frontend Game Sync Service
 * Saves game reviews to Supabase after each game is analyzed
 */

import { supabase } from "./supabase";
import type { GameMetadata, GameReview } from "./gameReviewTypes";

/**
 * Save a game review to Supabase
 */
export async function saveGameReview(
  userId: string,
  game: GameMetadata,
  review: GameReview
): Promise<string | null> {
  if (!supabase) {
    throw new Error("Supabase client not initialized");
  }

  try {
    // Prepare game data for saving
    const gameData = {
      user_id: userId,
      platform: game.platform,
      external_id: game.game_id,
      game_date: game.date,
      user_color: game.player_color,
      opponent_name: game.opponent_name,
      user_rating: game.player_rating,
      opponent_rating: game.opponent_rating,
      result: game.result,
      termination: game.termination || "",
      time_control: game.time_control,
      time_category: game.time_category,
      opening_eco: review.opening?.eco_final,
      opening_name: review.opening?.name_final,
      theory_exit_ply: review.opening?.theory_exit_ply,
      accuracy_overall: review.stats.overall_accuracy,
      accuracy_opening: review.stats.opening_accuracy,
      accuracy_middlegame: review.stats.middlegame_accuracy,
      accuracy_endgame: review.stats.endgame_accuracy,
      avg_cp_loss: review.stats.avg_cp_loss,
      blunders: review.stats.blunders,
      mistakes: review.stats.mistakes,
      inaccuracies: review.stats.inaccuracies,
      total_moves: review.stats.total_moves,
      game_character: review.game_metadata?.game_character,
      endgame_type: review.game_metadata?.endgame_type,
      pgn: game.pgn,
      game_review: review,
      review_type: "full",
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    // Insert game into reviewed_games table
    const { data, error } = await supabase
      .from("reviewed_games")
      .insert(gameData)
      .select("id")
      .single();

    if (error) {
      // Check if it's a duplicate (unique constraint violation)
      if (error.code === "23505") {
        console.log(
          `Game ${game.game_id} already exists, updating instead...`
        );
        // Update existing game
        const { data: updateData, error: updateError } = await supabase
          .from("reviewed_games")
          .update(gameData)
          .eq("user_id", userId)
          .eq("platform", game.platform)
          .eq("external_id", game.game_id)
          .select("id")
          .single();

        if (updateError) {
          throw updateError;
        }
        return updateData?.id || null;
      }
      throw error;
    }

    const gameId = data?.id;

    // Save moves to normalized tables if game was saved successfully
    if (gameId && review.ply_records.length > 0) {
      await saveMoves(gameId, userId, review.ply_records);
    }

    return gameId;
  } catch (error) {
    console.error("Error saving game review:", error);
    throw error;
  }
}

/**
 * Save moves from ply records to normalized tables
 */
async function saveMoves(
  gameId: string,
  userId: string,
  plyRecords: any[]
): Promise<number> {
  if (!supabase) {
    throw new Error("Supabase client not initialized");
  }

  try {
    // Prepare moves data
    const moves = plyRecords.map((record) => ({
      game_id: gameId,
      user_id: userId,
      ply: record.ply,
      move_san: record.move_san,
      fen_before: record.fen_before,
      fen_after: record.fen_after,
      eval_before_cp: record.eval_before_cp,
      eval_after_cp: record.eval_after_cp,
      cp_loss: record.cp_loss || 0,
      is_blunder: record.is_blunder || false,
      is_mistake: record.is_mistake || false,
      is_inaccuracy: record.is_inaccuracy || false,
      is_missed_win: record.is_missed_win || false,
      best_move_san: record.best_move_san,
      best_move_eval_cp: record.best_move_eval_cp,
      phase: record.phase,
    }));

    // Insert moves in batches (Supabase has limits)
    const batchSize = 100;
    let savedCount = 0;

    for (let i = 0; i < moves.length; i += batchSize) {
      const batch = moves.slice(i, i + batchSize);
      const { error } = await supabase.from("game_moves").insert(batch);

      if (error) {
        console.error(`Error saving moves batch ${i}-${i + batch.length}:`, error);
        // Continue with next batch
      } else {
        savedCount += batch.length;
      }
    }

    return savedCount;
  } catch (error) {
    console.error("Error saving moves:", error);
    return 0;
  }
}

/**
 * Check if a game has already been reviewed
 */
export async function isGameReviewed(
  userId: string,
  platform: string,
  gameId: string
): Promise<boolean> {
  if (!supabase) {
    return false;
  }

  try {
    const { data, error } = await supabase
      .from("reviewed_games")
      .select("id")
      .eq("user_id", userId)
      .eq("platform", platform)
      .eq("external_id", gameId)
      .limit(1)
      .single();

    if (error && error.code !== "PGRST116") {
      // PGRST116 is "not found" which is fine
      console.error("Error checking if game is reviewed:", error);
      return false;
    }

    return !!data;
  } catch (error) {
    console.error("Error checking game review status:", error);
    return false;
  }
}
