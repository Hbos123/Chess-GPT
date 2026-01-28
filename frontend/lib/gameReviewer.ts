/**
 * Frontend Game Reviewer
 * Analyzes games move-by-move using Stockfish WASM engine
 */

import { Chess } from "chess.js";
import { analyzePositionWasm } from "./wasmEngine";
import type {
  GameMetadata,
  GameReview,
  GameReviewOptions,
  PlyRecord,
  GameReviewStats,
  ReviewProgressCallback,
} from "./gameReviewTypes";

/**
 * Analyze a game move-by-move
 */
export async function reviewGame(
  game: GameMetadata,
  options: GameReviewOptions = {},
  progressCallback?: ReviewProgressCallback
): Promise<GameReview> {
  const {
    depth = 14,
    focus_color,
    review_subject = "player",
  } = options;

  const pgn = game.pgn;
  if (!pgn) {
    throw new Error("Game PGN is required");
  }

  // Determine focus color
  const playerColor = game.player_color;
  let focusColor: "white" | "black" | "both" = focus_color || playerColor;
  if (review_subject === "opponent") {
    focusColor = playerColor === "white" ? "black" : "white";
  } else if (review_subject === "both") {
    focusColor = "both";
  }

  // Parse PGN
  const chess = new Chess();
  chess.loadPgn(pgn);

  // Get all moves
  const moves = chess.history();
  const history = chess.history({ verbose: true });

  // Analyze each move
  const plyRecords: PlyRecord[] = [];
  let currentBoard = new Chess();

  const totalMoves = moves.length;
  let moveIndex = 0;

  for (const move of history) {
    moveIndex++;
    const ply = moveIndex;
    const isWhiteMove = ply % 2 === 1;
    const moveColor = isWhiteMove ? "white" : "black";

    // Skip if not focusing on this color
    if (focusColor !== "both" && moveColor !== focusColor) {
      currentBoard.move(move);
      continue;
    }

    // Update progress
    if (progressCallback) {
      const progress = moveIndex / totalMoves;
      progressCallback(
        "analyzing",
        `Analyzing move ${moveIndex}/${totalMoves}...`,
        progress
      );
    }

    const fenBefore = currentBoard.fen();

    // Analyze position before move
    try {
      const analysisBefore = await analyzePositionWasm(fenBefore, 1, depth);
      const evalBeforeCp =
        analysisBefore.candidates?.[0]?.eval_cp || 0;

      // Make the move
      currentBoard.move(move);
      const fenAfter = currentBoard.fen();

      // Analyze position after move
      const analysisAfter = await analyzePositionWasm(fenAfter, 1, depth);
      const evalAfterCp =
        analysisAfter.candidates?.[0]?.eval_cp || 0;

      // Calculate CP loss (from player's perspective)
      // If player is black, flip the evaluation
      const playerEvalBefore =
        moveColor === "white" ? evalBeforeCp : -evalBeforeCp;
      const playerEvalAfter =
        moveColor === "white" ? evalAfterCp : -evalAfterCp;

      // CP loss is how much worse the position got
      const cpLoss = Math.max(0, playerEvalBefore - playerEvalAfter);

      // Get best move
      const bestMove = analysisBefore.candidates?.[0]?.move || "";
      const bestMoveEvalCp = analysisBefore.candidates?.[0]?.eval_cp || 0;
      const bestMoveEvalFromPlayer =
        moveColor === "white" ? bestMoveEvalCp : -bestMoveEvalCp;

      // Classify move quality
      const isBlunder = cpLoss >= 200;
      const isMistake = cpLoss >= 100 && cpLoss < 200;
      const isInaccuracy = cpLoss >= 50 && cpLoss < 100;

      // Check for missed win (if best move was much better)
      const missedWinThreshold = 300;
      const isMissedWin =
        bestMoveEvalFromPlayer - playerEvalAfter >= missedWinThreshold &&
        bestMoveEvalFromPlayer >= 200;

      // Determine phase
      const phase = determinePhase(ply, totalMoves);

      const plyRecord: PlyRecord = {
        ply,
        move_san: move.san,
        fen_before: fenBefore,
        fen_after: fenAfter,
        eval_before_cp: evalBeforeCp,
        eval_after_cp: evalAfterCp,
        cp_loss: cpLoss,
        is_blunder: isBlunder,
        is_mistake: isMistake,
        is_inaccuracy: isInaccuracy,
        is_missed_win: isMissedWin,
        best_move_san: bestMove,
        best_move_eval_cp: bestMoveEvalCp,
        phase,
      };

      plyRecords.push(plyRecord);
    } catch (error) {
      console.error(`Error analyzing move ${moveIndex}:`, error);
      // Continue with next move
      currentBoard.move(move);
    }
  }

  // Calculate statistics
  const stats = calculateStats(plyRecords, playerColor);

  // Determine opening
  const opening = determineOpening(chess, plyRecords);

  // Build review object
  const review: GameReview = {
    pgn,
    ply_records: plyRecords,
    stats,
    opening,
    game_metadata: {
      player_color: playerColor,
      focus_color: focusColor,
      review_subject,
    },
    metadata: {
      platform: game.platform,
      player_rating: game.player_rating,
      result: game.result,
      player_color: playerColor,
      focus_color: focusColor,
      review_subject,
      time_control: game.time_control,
      time_category: game.time_category,
      termination: game.termination,
      date: game.date,
    },
  };

  return review;
}

/**
 * Determine game phase based on ply number
 */
function determinePhase(
  ply: number,
  totalMoves: number
): "opening" | "middlegame" | "endgame" {
  if (ply <= 20) {
    return "opening";
  } else if (ply <= totalMoves - 20) {
    return "middlegame";
  } else {
    return "endgame";
  }
}

/**
 * Calculate game statistics
 */
function calculateStats(
  plyRecords: PlyRecord[],
  playerColor: "white" | "black"
): GameReviewStats {
  if (plyRecords.length === 0) {
    return {
      overall_accuracy: 0,
      opening_accuracy: 0,
      middlegame_accuracy: 0,
      endgame_accuracy: 0,
      avg_cp_loss: 0,
      blunders: 0,
      mistakes: 0,
      inaccuracies: 0,
      missed_wins: 0,
      total_moves: 0,
    };
  }

  // Filter player moves only
  const playerMoves = plyRecords.filter((record) => {
    const isWhiteMove = record.ply % 2 === 1;
    return (
      (playerColor === "white" && isWhiteMove) ||
      (playerColor === "black" && !isWhiteMove)
    );
  });

  if (playerMoves.length === 0) {
    return {
      overall_accuracy: 0,
      opening_accuracy: 0,
      middlegame_accuracy: 0,
      endgame_accuracy: 0,
      avg_cp_loss: 0,
      blunders: 0,
      mistakes: 0,
      inaccuracies: 0,
      missed_wins: 0,
      total_moves: 0,
    };
  }

  // Calculate accuracy (percentage of moves with CP loss < 50)
  const accurateMoves = playerMoves.filter(
    (m) => (m.cp_loss || 0) < 50
  ).length;
  const overallAccuracy = (accurateMoves / playerMoves.length) * 100;

  // Calculate phase-specific accuracies
  const openingMoves = playerMoves.filter((m) => m.phase === "opening");
  const middlegameMoves = playerMoves.filter(
    (m) => m.phase === "middlegame"
  );
  const endgameMoves = playerMoves.filter((m) => m.phase === "endgame");

  const openingAccuracy =
    openingMoves.length > 0
      ? (openingMoves.filter((m) => (m.cp_loss || 0) < 50).length /
          openingMoves.length) *
        100
      : 0;

  const middlegameAccuracy =
    middlegameMoves.length > 0
      ? (middlegameMoves.filter((m) => (m.cp_loss || 0) < 50).length /
          middlegameMoves.length) *
        100
      : 0;

  const endgameAccuracy =
    endgameMoves.length > 0
      ? (endgameMoves.filter((m) => (m.cp_loss || 0) < 50).length /
          endgameMoves.length) *
        100
      : 0;

  // Calculate average CP loss
  const totalCpLoss = playerMoves.reduce(
    (sum, m) => sum + (m.cp_loss || 0),
    0
  );
  const avgCpLoss = totalCpLoss / playerMoves.length;

  // Count errors
  const blunders = playerMoves.filter((m) => m.is_blunder).length;
  const mistakes = playerMoves.filter((m) => m.is_mistake).length;
  const inaccuracies = playerMoves.filter((m) => m.is_inaccuracy).length;
  const missedWins = playerMoves.filter((m) => m.is_missed_win).length;

  return {
    overall_accuracy: Math.round(overallAccuracy * 10) / 10,
    opening_accuracy: Math.round(openingAccuracy * 10) / 10,
    middlegame_accuracy: Math.round(middlegameAccuracy * 10) / 10,
    endgame_accuracy: Math.round(endgameAccuracy * 10) / 10,
    avg_cp_loss: Math.round(avgCpLoss * 10) / 10,
    blunders,
    mistakes,
    inaccuracies,
    missed_wins: missedWins,
    total_moves: playerMoves.length,
  };
}

/**
 * Determine opening from game
 */
function determineOpening(
  chess: Chess,
  plyRecords: PlyRecord[]
): { name_final?: string; eco_final?: string; theory_exit_ply?: number } {
  // Try to extract from PGN headers
  const pgn = chess.pgn();
  const headerLines = pgn.split("\n").filter((line) => line.startsWith("["));
  
  let openingName = "";
  let eco = "";
  
  for (const line of headerLines) {
    const nameMatch = line.match(/\[Opening\s+"([^"]+)"\]/);
    if (nameMatch) openingName = nameMatch[1];
    
    const ecoMatch = line.match(/\[ECO\s+"([^"]+)"\]/);
    if (ecoMatch) eco = ecoMatch[1];
  }

  // Find theory exit ply (first move with CP loss > 20)
  let theoryExitPly: number | undefined;
  for (const record of plyRecords) {
    if ((record.cp_loss || 0) > 20) {
      theoryExitPly = record.ply;
      break;
    }
  }

  return {
    name_final: openingName || undefined,
    eco_final: eco || undefined,
    theory_exit_ply: theoryExitPly,
  };
}
