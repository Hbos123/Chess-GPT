/**
 * Frontend Game Reviewer
 * Analyzes games move-by-move using Stockfish WASM engine
 */

import { Chess } from "chess.js";
import { analyzePositionWasm } from "./wasmEngine";
import { getBackendBase } from "./backendBase";
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

  // Reduced logging - removed startup log

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

  // We'll enrich tags using backend light-raw analyzer in one batch at the end
  // (closest parity to legacy backend tagging, minimal server load).
  const bestMoveFenAfterByPly: Record<number, string> = {};

  const applyVerboseMove = (board: Chess, m: any) => {
    try {
      if (m && typeof m === "object" && m.from && m.to) {
        // Prefer from/to to avoid SAN parsing edge cases.
        const moved = (board as any).move(
          { from: m.from, to: m.to, promotion: (m.promotion as any) || undefined },
          { sloppy: true }
        );
        return moved;
      }
      if (typeof m?.san === "string") {
        return (board as any).move(m.san, { sloppy: true });
      }
      return null;
    } catch {
      return null;
    }
  };

  const getEvalCp = (analysis: any): number => {
    const direct = analysis?.eval_cp;
    if (typeof direct === "number") return direct;
    const cm0 = analysis?.candidate_moves?.[0];
    if (cm0 && typeof cm0.eval_cp === "number") return cm0.eval_cp;
    // Back-compat with older shapes
    const c0 = analysis?.candidates?.[0];
    if (c0 && typeof c0.eval_cp === "number") return c0.eval_cp;
    return 0;
  };

  const getBestMove = (analysis: any): { san: string; uci?: string; evalCp: number } => {
    const cm0 = analysis?.candidate_moves?.[0];
    if (cm0 && typeof cm0.move === "string") {
      return { san: cm0.move || "", uci: typeof cm0.uci === "string" ? cm0.uci : undefined, evalCp: typeof cm0.eval_cp === "number" ? cm0.eval_cp : 0 };
    }
    const best = typeof analysis?.best_move === "string" ? analysis.best_move : "";
    return { san: best || "", uci: undefined, evalCp: getEvalCp(analysis) };
  };

  for (const move of history) {
    moveIndex++;
    const ply = moveIndex;
    const isWhiteMove = ply % 2 === 1;
    const moveColor = isWhiteMove ? "white" : "black";

    // Skip if not focusing on this color
    if (focusColor !== "both" && moveColor !== focusColor) {
      const moved = applyVerboseMove(currentBoard, move);
      if (!moved) {
        throw new Error(`Invalid move while replaying PGN (skip path): ${JSON.stringify({ ply, move })}`);
      }
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
    // Reduce logging - only log every 10 moves or blunders/mistakes
    if (moveIndex % 10 === 0 || moveIndex === 1 || moveIndex === totalMoves) {
      console.log(`[GameReviewer] Analyzing move ${moveIndex}/${totalMoves}: ${move.san} (ply ${ply})`);
    }

    // Analyze position before move
    try {
      const analysisBefore = await analyzePositionWasm(fenBefore, 1, depth);
      const evalBeforeCp = getEvalCp(analysisBefore);

      // Make the move
      const moved = applyVerboseMove(currentBoard, move);
      if (!moved) {
        throw new Error(`Invalid move while analyzing (ply ${ply}): ${JSON.stringify({ from: (move as any)?.from, to: (move as any)?.to, san: (move as any)?.san })}`);
      }
      const fenAfter = currentBoard.fen();

      // Analyze position after move
      const analysisAfter = await analyzePositionWasm(fenAfter, 1, depth);
      const evalAfterCp = getEvalCp(analysisAfter);

      // Calculate CP loss (from player's perspective)
      // If player is black, flip the evaluation
      const playerEvalBefore =
        moveColor === "white" ? evalBeforeCp : -evalBeforeCp;
      const playerEvalAfter =
        moveColor === "white" ? evalAfterCp : -evalAfterCp;

      // CP loss is how much worse the position got
      const cpLoss = Math.max(0, playerEvalBefore - playerEvalAfter);

      // Get best move
      const best = getBestMove(analysisBefore);
      const bestMove = best.san || "";
      const bestMoveUci = best.uci;
      const bestMoveEvalCp = best.evalCp || 0;
      const bestMoveEvalFromPlayer =
        moveColor === "white" ? bestMoveEvalCp : -bestMoveEvalCp;

      // Classify move quality
      const isBlunder = cpLoss >= 200;
      const isMistake = cpLoss >= 100 && cpLoss < 200;
      const isInaccuracy = cpLoss >= 50 && cpLoss < 100;
      const category = isBlunder
        ? "blunder"
        : isMistake
          ? "mistake"
          : isInaccuracy
            ? "inaccuracy"
            : "good";

      // Check for missed win (if best move was much better)
      const missedWinThreshold = 300;
      const isMissedWin =
        bestMoveEvalFromPlayer - playerEvalAfter >= missedWinThreshold &&
        bestMoveEvalFromPlayer >= 200;

      // Determine phase
      const phase = determinePhase(ply, totalMoves);

      // Extract basic tags based on move quality (matching backend format)
      const qualityTags: Array<{ tag_name: string }> = [];
      if (isBlunder) qualityTags.push({ tag_name: "blunder" });
      if (isMistake) qualityTags.push({ tag_name: "mistake" });
      if (isInaccuracy) qualityTags.push({ tag_name: "inaccuracy" });
      if (isMissedWin) qualityTags.push({ tag_name: "missed_win" });

      // Try to compute FEN after the best move so we can tag it too (best_move_tags parity)
      try {
        if (bestMove && typeof bestMove === "string") {
          const bestBoard = new Chess(fenBefore);
          const moved = (bestBoard as any).move(bestMove, { sloppy: true });
          if (moved) {
            bestMoveFenAfterByPly[ply] = bestBoard.fen();
          }
        }
      } catch {
        // ignore best-move fen failures
      }

      const plyRecord: PlyRecord = {
        ply,
        move_san: move.san,
        uci: typeof (move as any)?.from === "string" && typeof (move as any)?.to === "string"
          ? `${(move as any).from}${(move as any).to}${(move as any).promotion || ""}`
          : undefined,
        fen_before: fenBefore,
        fen_after: fenAfter,
        eval_before_cp: evalBeforeCp,
        eval_after_cp: evalAfterCp,
        cp_loss: cpLoss,
        category,
        is_blunder: isBlunder,
        is_mistake: isMistake,
        is_inaccuracy: isInaccuracy,
        is_missed_win: isMissedWin,
        best_move_san: bestMove,
        best_move_uci: bestMoveUci,
        best_move_eval_cp: bestMoveEvalCp,
        phase,
        side_moved: moveColor,
        // Tag extraction fields (matching backend format)
        analyse: {
          tags: qualityTags.length > 0 ? qualityTags : [],
        },
        raw_before: {
          tags: [], // Would need position analysis to extract tags
        },
        raw_after: {
          tags: [], // Would need position analysis to extract tags
        },
        engine: {
          played_eval_after_cp: evalAfterCp,
          eval_before_cp: evalBeforeCp,
          best_move_san: bestMove,
          best_move_uci: bestMoveUci,
          best_move_tags: [], // Filled via backend batch tagger after analysis
        },
      };

      plyRecords.push(plyRecord);
      // Only log blunders and mistakes to reduce console spam
      if (isBlunder || isMistake) {
        console.log(`[GameReviewer] Move ${moveIndex}: ${move.san}, CP loss: ${cpLoss.toFixed(1)}, blunder: ${isBlunder}, mistake: ${isMistake}`);
      }
    } catch (error) {
      console.error(`[GameReviewer] Error analyzing move ${moveIndex}:`, error);
      // Abort this game to avoid board desync producing corrupt ply_records.
      throw error;
    }
  }

  // === Backend tag enrichment (closest parity to legacy backend tagging) ===
  // Fill: raw_before.tags, raw_after.tags, engine.best_move_tags
  try {
    const backendBase = getBackendBase();
    if (backendBase && plyRecords.length > 0) {
      const DEBUG_TAG_ENRICH =
        typeof window !== "undefined" && (window.localStorage?.getItem("chessterDebugTags") === "1");

      const debugTagSummary = (tags: any[]) => {
        if (!Array.isArray(tags) || tags.length === 0) return [];
        const out: string[] = [];
        for (const t of tags.slice(0, 5)) {
          if (typeof t === "string") out.push(t);
          else if (t && typeof t === "object") out.push(String((t as any).tag_name || (t as any).name || (t as any).tag || ""));
          else out.push(String(t));
        }
        return out.filter(Boolean);
      };

      const fenSet = new Set<string>();
      for (const r of plyRecords) {
        if (r?.fen_before) fenSet.add(r.fen_before);
        if (r?.fen_after) fenSet.add(r.fen_after);
        const bestFen = bestMoveFenAfterByPly[r.ply];
        if (bestFen) fenSet.add(bestFen);
      }
      const fens = Array.from(fenSet);
      if (fens.length > 0) {
        // Chunk for safety
        const tagsByFen: Record<string, any[]> = {};
        const chunkSize = 200;
        if (DEBUG_TAG_ENRICH) {
          console.log(
            `[TagEnrich] Starting backend tag enrichment: plies=${plyRecords.length}, uniqueFENs=${fens.length}, chunkSize=${chunkSize}, endpoint=${backendBase.replace(/\/$/, "")}/profile/position_tags`,
          );
        }
        for (let i = 0; i < fens.length; i += chunkSize) {
          const chunk = fens.slice(i, i + chunkSize);
          const url = `${backendBase.replace(/\/$/, "")}/profile/position_tags`;
          if (DEBUG_TAG_ENRICH) {
            console.log(`[TagEnrich] POST ${url} chunk ${(i / chunkSize) + 1}/${Math.ceil(fens.length / chunkSize)} size=${chunk.length}`);
          }
          const resp = await fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ fens: chunk, include_extras: false }),
          });
          if (resp.ok) {
            const data = await resp.json();
            const map = data?.tags_by_fen || {};
            for (const [k, v] of Object.entries(map)) {
              tagsByFen[k] = Array.isArray(v) ? (v as any[]) : [];
            }
            if (DEBUG_TAG_ENRICH) {
              let nonEmpty = 0;
              let firstNonEmptyFen: string | null = null;
              for (const fen of chunk) {
                const arr = tagsByFen[fen] || [];
                if (Array.isArray(arr) && arr.length > 0) {
                  nonEmpty += 1;
                  if (!firstNonEmptyFen) firstNonEmptyFen = fen;
                }
              }
              const sampleTags = firstNonEmptyFen ? debugTagSummary(tagsByFen[firstNonEmptyFen] || []) : [];
              console.log(
                `[TagEnrich] OK chunk ${(i / chunkSize) + 1}: fens=${chunk.length}, nonEmpty=${nonEmpty}, sampleTags=${sampleTags.join(", ") || "—"}`,
              );
            }
          } else {
            const text = await resp.text().catch(() => "");
            if (DEBUG_TAG_ENRICH) {
              console.warn(`[TagEnrich] FAILED chunk ${(i / chunkSize) + 1}: status=${resp.status} body=${text?.slice(0, 500)}`);
            }
          }
        }

        // Apply tags back onto ply records
        let withBefore = 0;
        let withAfter = 0;
        let withEither = 0;
        let withBest = 0;
        for (const r of plyRecords) {
          const beforeTags = tagsByFen[r.fen_before] || [];
          const afterTags = tagsByFen[r.fen_after] || [];
          const bestFen = bestMoveFenAfterByPly[r.ply];
          const bestTags = bestFen ? (tagsByFen[bestFen] || []) : [];

          r.raw_before = { tags: beforeTags };
          r.raw_after = { tags: afterTags };
          r.engine = {
            ...(r.engine || {}),
            best_move_tags: bestTags,
          };

          if (Array.isArray(beforeTags) && beforeTags.length > 0) withBefore += 1;
          if (Array.isArray(afterTags) && afterTags.length > 0) withAfter += 1;
          if ((Array.isArray(beforeTags) && beforeTags.length > 0) || (Array.isArray(afterTags) && afterTags.length > 0)) withEither += 1;
          if (Array.isArray(bestTags) && bestTags.length > 0) withBest += 1;
        }
        if (DEBUG_TAG_ENRICH) {
          console.log(
            `[TagEnrich] Applied tags to plyRecords: withRawBefore=${withBefore}/${plyRecords.length}, withRawAfter=${withAfter}/${plyRecords.length}, withEither=${withEither}/${plyRecords.length}, withBestMoveTags=${withBest}/${plyRecords.length}`,
          );
        }
      }
    }
  } catch (e) {
    // Non-fatal: proceed without backend tags
    console.warn("[GameReviewer] Backend tag enrichment failed:", e);
  }

  // Calculate statistics for both sides
  const whiteStats = calculateStats(plyRecords, "white");
  const blackStats = calculateStats(plyRecords, "black");
  const playerStats = calculateStats(plyRecords, playerColor);
  
  // Combine stats in backend format
  const stats = {
    white: whiteStats,
    black: blackStats,
    overall_accuracy: playerStats.overall_accuracy,
    opening_accuracy: playerStats.opening_accuracy,
    middlegame_accuracy: playerStats.middlegame_accuracy,
    endgame_accuracy: playerStats.endgame_accuracy,
    avg_cp_loss: playerStats.avg_cp_loss,
    blunders: playerStats.blunders,
    mistakes: playerStats.mistakes,
    inaccuracies: playerStats.inaccuracies,
    missed_wins: playerStats.missed_wins,
    total_moves: playerStats.total_moves,
  };

  // Determine opening
  const opening = determineOpening(chess, plyRecords);

  // Detect key points and key moments
  const keyPoints = detectKeyPoints(plyRecords, playerColor, focusColor);
  const allKeyMoments = detectAllKeyMoments(plyRecords);
  
  // Detect phase transitions
  const phases = detectPhaseTransitions(plyRecords);
  
  // Determine game character and endgame type
  const gameCharacter = determineGameCharacter(plyRecords, stats);
  const endgameType = determineEndgameType(chess, plyRecords);

  // Build review object
  const review: GameReview = {
    pgn,
    ply_records: plyRecords,
    stats,
    opening,
    phases,
    side_focus: focusColor === "both" ? "both" : focusColor,
    key_points: keyPoints,
    all_key_moments: allKeyMoments,
    game_metadata: {
      game_character: gameCharacter,
      endgame_type: endgameType,
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
 * Detect key points (blunders, mistakes, critical moments)
 */
function detectKeyPoints(
  plyRecords: PlyRecord[],
  playerColor: "white" | "black",
  focusColor: "white" | "black" | "both"
): Array<{ ply: number; move_san: string; labels?: string[]; category?: string; note?: string }> {
  const keyPoints: Array<{ ply: number; move_san: string; labels?: string[]; category?: string; note?: string }> = [];
  
  for (const record of plyRecords) {
    const isWhiteMove = record.ply % 2 === 1;
    const moveColor = isWhiteMove ? "white" : "black";
    
    // Apply focus color filter
    if (focusColor !== "both" && moveColor !== focusColor) {
      continue;
    }
    
    const labels: string[] = [];
    let category: string | undefined;
    let note: string | undefined;
    
    if (record.is_blunder) {
      labels.push("blunder");
      category = "blunder";
      note = `Blunder: ${record.move_san} loses ${record.cp_loss?.toFixed(1)} centipawns`;
    } else if (record.is_mistake) {
      labels.push("mistake");
      category = "mistake";
      note = `Mistake: ${record.move_san} loses ${record.cp_loss?.toFixed(1)} centipawns`;
    } else if (record.is_inaccuracy) {
      labels.push("inaccuracy");
      category = "inaccuracy";
    }
    
    if (record.is_missed_win) {
      labels.push("missed_win");
      if (!note) note = `Missed win: ${record.best_move_san} was much better`;
    }
    
    if (labels.length > 0) {
      keyPoints.push({
        ply: record.ply,
        move_san: record.move_san,
        labels,
        category,
        note,
      });
    }
  }
  
  return keyPoints;
}

/**
 * Detect all key moments for both sides (enhanced to match backend)
 */
function detectAllKeyMoments(
  plyRecords: PlyRecord[]
): Array<{ 
  ply: number; 
  move_san: string; 
  labels?: string[]; 
  category?: string; 
  note?: string;
  primary_label?: string;
  advantage_swing?: number;
  cp_loss?: number;
  side?: string;
  evalBefore?: number;
  evalAfter?: number;
  crossed100?: boolean;
  crossed200?: boolean;
  crossed300?: boolean;
}> {
  const allKeyMoments: Array<{ 
    ply: number; 
    move_san: string; 
    labels?: string[]; 
    category?: string; 
    note?: string;
    primary_label?: string;
    advantage_swing?: number;
    cp_loss?: number;
    side?: string;
    evalBefore?: number;
    evalAfter?: number;
    crossed100?: boolean;
    crossed200?: boolean;
    crossed300?: boolean;
  }> = [];
  
  for (let i = 0; i < plyRecords.length; i++) {
    const record = plyRecords[i];
    const prevRecord = i > 0 ? plyRecords[i - 1] : null;
    
    const labels: string[] = [];
    let category: string | undefined;
    let note: string | undefined;
    
    const evalCp = record.engine?.played_eval_after_cp ?? record.eval_after_cp ?? 0;
    const evalBefore = record.engine?.eval_before_cp ?? record.eval_before_cp ?? 0;
    const prevEval = prevRecord?.engine?.played_eval_after_cp ?? prevRecord?.eval_after_cp ?? 0;
    
    // === Move Quality Labels ===
    if (record.is_blunder) {
      labels.push("blunder");
      category = "blunder";
      note = `Blunder: ${record.move_san} loses ${record.cp_loss?.toFixed(1) || 0} centipawns`;
    } else if (record.is_mistake) {
      labels.push("mistake");
      category = "mistake";
      note = `Mistake: ${record.move_san} loses ${record.cp_loss?.toFixed(1) || 0} centipawns`;
    } else if (record.is_inaccuracy) {
      labels.push("inaccuracy");
      category = "inaccuracy";
    }
    
    // === Advantage Shift Detection ===
    const evalSwing = Math.abs(evalCp - prevEval);
    if (evalSwing > 100) {
      labels.push("advantage_shift");
    }
    
    // === Missed Critical Win ===
    // Dropped from winning (>300cp) to not winning (<100cp)
    if (evalBefore > 300 && evalCp < 100) {
      labels.push("missed_critical_win");
      if (!note) note = `Missed critical win: dropped from ${evalBefore.toFixed(0)}cp to ${evalCp.toFixed(0)}cp`;
    } else if (evalBefore < -300 && evalCp > -100) {
      labels.push("missed_critical_win");
      if (!note) note = `Missed critical win: dropped from ${evalBefore.toFixed(0)}cp to ${evalCp.toFixed(0)}cp`;
    }
    
    if (record.is_missed_win) {
      labels.push("missed_win");
      if (!note) note = `Missed win: ${record.best_move_san} was much better`;
    }
    
    // === Tactical Opportunity ===
    // Check if tags indicate tactical opportunity (if tags are available)
    const tagsBefore = record.raw_before?.tags || [];
    const tagNamesBefore = tagsBefore.map((t: any) => t.tag_name || t.tag || t.name || '').filter(Boolean);
    const tacticalTags = ['fork', 'pin', 'skewer', 'discovered_attack', 'tactic'];
    const hasTacticalTag = tagNamesBefore.some((name: string) => 
      tacticalTags.some(t => name.toLowerCase().includes(t))
    );
    if (hasTacticalTag && (record.is_mistake || record.is_blunder)) {
      labels.push("tactical_opportunity");
    }
    
    // === Phase Transition ===
    if (prevRecord && prevRecord.phase && record.phase && prevRecord.phase !== record.phase) {
      labels.push("phase_transition");
    }
    
    // === Theory Exit ===
    // Note: Frontend doesn't track theory exit yet, but structure is ready
    // if (record.is_theory === false && prevRecord?.is_theory === true) {
    //   labels.push("theory_exit");
    // }
    
    // === Threshold Crossings ===
    for (const threshold of [100, 200, 300]) {
      if (prevEval < threshold && evalCp >= threshold) {
        labels.push(`threshold_${threshold}_white`);
      }
      if (prevEval > -threshold && evalCp <= -threshold) {
        labels.push(`threshold_${threshold}_black`);
      }
    }
    
    // Only create key moment if there are labels
    if (labels.length > 0) {
      // Determine primary label (most severe)
      const primaryPriority = [
        "blunder", "missed_critical_win", "mistake", "advantage_shift",
        "critical_good_move", "inaccuracy", "tactical_opportunity",
        "phase_transition", "theory_exit"
      ];
      const primary = primaryPriority.find(l => labels.includes(l)) || labels[0];
      
      allKeyMoments.push({
        ply: record.ply,
        move_san: record.move_san,
        labels,
        category,
        note,
        primary_label: primary,
        advantage_swing: evalSwing,
        cp_loss: record.cp_loss,
        side: record.side_moved,
        // Add evalBefore/evalAfter for advantage shift display
        evalBefore: labels.includes("advantage_shift") ? evalBefore : undefined,
        evalAfter: labels.includes("advantage_shift") ? evalCp : undefined,
        // Add threshold crossing flags for advantage shift messages
        crossed100: labels.includes("threshold_100_white") || labels.includes("threshold_100_black"),
        crossed200: labels.includes("threshold_200_white") || labels.includes("threshold_200_black"),
        crossed300: labels.includes("threshold_300_white") || labels.includes("threshold_300_black"),
      });
    }
  }
  
  return allKeyMoments;
}

/**
 * Detect phase transitions
 */
function detectPhaseTransitions(
  plyRecords: PlyRecord[]
): Array<{ from: string; to: string; ply: number }> {
  const transitions: Array<{ from: string; to: string; ply: number }> = [];
  let currentPhase: "opening" | "middlegame" | "endgame" = "opening";
  
  for (const record of plyRecords) {
    if (record.phase && record.phase !== currentPhase) {
      transitions.push({
        from: currentPhase,
        to: record.phase,
        ply: record.ply,
      });
      currentPhase = record.phase;
    }
  }
  
  return transitions;
}

/**
 * Determine game character (tactical, positional, etc.)
 */
function determineGameCharacter(
  plyRecords: PlyRecord[],
  stats: any
): "tactical_battle" | "dynamic" | "balanced" | "positional" | "unknown" {
  const blunderRate = stats.blunders / Math.max(stats.total_moves, 1);
  const avgCpLoss = stats.avg_cp_loss || 0;
  
  // High blunder rate and high CP loss = tactical battle
  if (blunderRate > 0.1 && avgCpLoss > 80) {
    return "tactical_battle";
  }
  
  // Medium blunder rate = dynamic
  if (blunderRate > 0.05 && avgCpLoss > 50) {
    return "dynamic";
  }
  
  // Low blunder rate and low CP loss = positional
  if (blunderRate < 0.02 && avgCpLoss < 30) {
    return "positional";
  }
  
  // Medium everything = balanced
  if (blunderRate > 0.02 && blunderRate < 0.08) {
    return "balanced";
  }
  
  return "unknown";
}

/**
 * Determine endgame type
 */
function determineEndgameType(
  chess: Chess,
  plyRecords: PlyRecord[]
): "queen_endgame" | "rook_endgame" | "minor_piece_endgame" | "pawn_endgame" | "none" {
  // Check last 20 moves for endgame piece composition
  const endgameRecords = plyRecords.slice(-20);
  if (endgameRecords.length === 0) {
    return "none";
  }
  
  // Get final position
  const finalFen = endgameRecords[endgameRecords.length - 1]?.fen_after;
  if (!finalFen) {
    return "none";
  }
  
  // Count pieces in final position
  const board = new Chess(finalFen);
  const pieces = board.board();
  
  let queens = 0;
  let rooks = 0;
  let minorPieces = 0; // knights + bishops
  let pawns = 0;
  
  for (const row of pieces) {
    for (const piece of row) {
      if (!piece) continue;
      if (piece.type === "q") queens++;
      else if (piece.type === "r") rooks++;
      else if (piece.type === "n" || piece.type === "b") minorPieces++;
      else if (piece.type === "p") pawns++;
    }
  }
  
  // Determine endgame type
  if (queens > 0) {
    return "queen_endgame";
  } else if (rooks > 0) {
    return "rook_endgame";
  } else if (minorPieces > 0) {
    return "minor_piece_endgame";
  } else if (pawns > 0) {
    return "pawn_endgame";
  }
  
  return "none";
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
