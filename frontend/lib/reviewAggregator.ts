/**
 * Frontend Review Aggregator
 * Aggregates statistics and metrics across multiple game reviews
 * Replicates backend PersonalReviewAggregator logic
 */

import type { GameReview } from "./gameReviewTypes";

interface TransformedPlyRecord {
  side_moved: "white" | "black";
  accuracy_pct: number;
  cp_loss: number;
  category: "excellent" | "good" | "inaccuracy" | "mistake" | "blunder";
  quality: string;
  phase: "opening" | "middlegame" | "endgame";
  eval_before_cp?: number;
  eval_after_cp?: number;
  san?: string;
  time_spent_s?: number;
}

interface TransformedGame {
  ply_records: TransformedPlyRecord[];
  metadata: {
    game_id?: string;
    platform?: string;
    player_rating?: number;
    opponent_rating?: number;
    result: "win" | "loss" | "draw" | "unknown";
    player_color: "white" | "black";
    time_category?: string;
    date?: string;
    opening?: string;
  };
  opening?: {
    name_final?: string;
    eco_final?: string;
  };
  pgn?: string;
}

/**
 * Transform frontend GameReview to backend format
 */
function transformFrontendReviewToBackendFormat(
  review: GameReview
): TransformedGame {
  const playerColor = review.metadata?.player_color || "white";
  const transformedRecords: TransformedPlyRecord[] = [];

  for (const record of review.ply_records || []) {
    // Infer side_moved from ply number (odd = white, even = black)
    const sideMoved: "white" | "black" = record.ply % 2 === 1 ? "white" : "black";

    // Calculate accuracy_pct from CP loss (same formula as backend: 100 / (1 + (cp_loss/50)^0.7))
    const cpLoss = record.cp_loss || 0;
    const accuracyPct = 100 / (1 + Math.pow(cpLoss / 50, 0.7));

    // Derive category from boolean flags
    let category: "excellent" | "good" | "inaccuracy" | "mistake" | "blunder" = "good";
    let quality = "good";
    if (record.is_blunder) {
      category = "blunder";
      quality = "blunder";
    } else if (record.is_mistake) {
      category = "mistake";
      quality = "mistake";
    } else if (record.is_inaccuracy) {
      category = "inaccuracy";
      quality = "inaccuracy";
    } else if (cpLoss < 20) {
      category = "excellent";
      quality = "excellent";
    }

    transformedRecords.push({
      side_moved: sideMoved,
      accuracy_pct: accuracyPct,
      cp_loss: cpLoss,
      category,
      quality,
      phase: record.phase || "middlegame",
      eval_before_cp: record.eval_before_cp,
      eval_after_cp: record.eval_after_cp,
      san: record.move_san,
    });
  }

  return {
    ply_records: transformedRecords,
    metadata: {
      game_id: review.metadata?.platform ? undefined : undefined,
      platform: review.metadata?.platform,
      player_rating: review.metadata?.player_rating,
      opponent_rating: undefined,
      result: (review.metadata?.result as any) || "unknown",
      player_color: playerColor,
      time_category: review.metadata?.time_category,
      date: review.metadata?.date,
      opening: review.opening?.name_final,
    },
    opening: review.opening,
    pgn: review.pgn,
  };
}

/**
 * Calculate mean of array
 */
function mean(arr: number[]): number {
  if (arr.length === 0) return 0;
  return arr.reduce((a, b) => a + b, 0) / arr.length;
}

/**
 * Aggregate statistics across analyzed games
 */
export function aggregateReviews(
  reviews: GameReview[],
  filters?: Record<string, any>
): Record<string, any> {
  console.log(`[ReviewAggregator] Aggregating ${reviews.length} reviews`);

  if (reviews.length === 0) {
    return {
      error: "No games to aggregate",
      summary: { total_games: 0 },
      total_games_analyzed: 0,
    };
  }

  // Transform frontend reviews to backend format
  const transformedGames = reviews.map(transformFrontendReviewToBackendFormat);

  // Apply filters if provided (simplified - full filter logic would be more complex)
  let filteredGames = transformedGames;
  if (filters) {
    // Basic filtering - can be expanded
    if (filters.result) {
      filteredGames = filteredGames.filter(
        (g) => g.metadata.result === filters.result
      );
    }
    if (filters.color) {
      filteredGames = filteredGames.filter(
        (g) => g.metadata.player_color === filters.color
      );
    }
  }

  if (filteredGames.length === 0) {
    return {
      error: "No games match the specified filters",
      summary: { total_games: 0 },
      total_games_analyzed: 0,
    };
  }

  // Calculate all statistics
  const summary = calculateSummary(filteredGames);
  const accuracyByRating = calculateAccuracyByRating(filteredGames);
  const openingPerformance = calculateOpeningPerformance(filteredGames);
  const themeFrequency: any[] = []; // Frontend doesn't have tags yet
  const phaseStats = calculatePhaseStats(filteredGames);
  const winRateByPhase = calculateWinRateByPhase(filteredGames);
  const mistakePatterns = calculateMistakePatterns(filteredGames);
  const timeManagement = calculateTimeManagement(filteredGames);
  const advancedMetrics = calculateAdvancedMetrics(filteredGames);
  const accuracyByColor = calculateAccuracyByColor(filteredGames);
  const performanceByTimeControl = calculatePerformanceByTimeControl(filteredGames);
  const accuracyByTimeSpent: any[] = []; // Requires clock data from PGN
  const performanceByTags: any = {}; // Frontend doesn't have tags yet
  const criticalMoments = calculateCriticalMoments(filteredGames);
  const advantageConversion = calculateAdvantageConversion(filteredGames);
  const blunderTriggers = calculateBlunderTriggers(filteredGames);
  const pieceActivity = calculatePieceActivity(filteredGames);
  const tiltPoints: any[] = []; // Requires time data
  const diagnosticInsights = calculateDiagnosticInsights(
    filteredGames,
    summary.overall_accuracy || 75
  );

  return {
    summary,
    accuracy_by_rating: accuracyByRating,
    opening_performance: openingPerformance,
    theme_frequency: themeFrequency,
    phase_stats: phaseStats,
    win_rate_by_phase: winRateByPhase,
    mistake_patterns: mistakePatterns,
    time_management: timeManagement,
    advanced_metrics: advancedMetrics,
    accuracy_by_color: accuracyByColor,
    performance_by_time_control: performanceByTimeControl,
    accuracy_by_time_spent: accuracyByTimeSpent,
    performance_by_tags: performanceByTags,
    critical_moments: criticalMoments,
    advantage_conversion: advantageConversion,
    blunder_triggers: blunderTriggers,
    piece_activity: pieceActivity,
    tilt_points: tiltPoints,
    diagnostic_insights: diagnosticInsights,
    total_games_analyzed: filteredGames.length,
  };
}

function calculateSummary(games: TransformedGame[]): Record<string, any> {
  const totalGames = games.length;
  const results = games.map((g) => g.metadata.result);
  const wins = results.filter((r) => r === "win").length;
  const losses = results.filter((r) => r === "loss").length;
  const draws = results.filter((r) => r === "draw").length;

  const allAccuracies: number[] = [];
  const allCpLosses: number[] = [];
  let blunderCount = 0;
  let mistakeCount = 0;

  for (const game of games) {
    const playerColor = game.metadata.player_color;
    for (const record of game.ply_records) {
      if (record.side_moved === playerColor) {
        allAccuracies.push(record.accuracy_pct);
        allCpLosses.push(record.cp_loss);
        if (record.category === "blunder") blunderCount++;
        if (record.category === "mistake") mistakeCount++;
      }
    }
  }

  const overallAccuracy = mean(allAccuracies);
  const avgCpLoss = mean(allCpLosses);
  const totalMoves = allAccuracies.length;
  const blunderRate = totalMoves > 0 ? (blunderCount / totalMoves) * 100 : 0;
  const mistakeRate = totalMoves > 0 ? (mistakeCount / totalMoves) * 100 : 0;

  return {
    total_games: totalGames,
    wins,
    losses,
    draws,
    win_rate: totalGames > 0 ? wins / totalGames : 0,
    overall_accuracy: overallAccuracy,
    avg_accuracy: overallAccuracy,
    avg_cp_loss: avgCpLoss,
    blunder_rate: blunderRate,
    mistake_rate: mistakeRate,
    total_moves: totalMoves,
    blunders_per_game: totalGames > 0 ? blunderCount / totalGames : 0,
    mistakes_per_game: totalGames > 0 ? mistakeCount / totalGames : 0,
  };
}

function calculateAccuracyByRating(
  games: TransformedGame[]
): Array<{ rating_range: string; accuracy: number; game_count: number }> {
  const ratingBands: Record<
    string,
    { accuracies: number[]; count: number }
  > = {};

  for (const game of games) {
    const rating = game.metadata.player_rating || 0;
    if (rating === 0) continue;

    const bandStart = Math.floor(rating / 100) * 100;
    const bandKey = `${bandStart}-${bandStart + 99}`;

    if (!ratingBands[bandKey]) {
      ratingBands[bandKey] = { accuracies: [], count: 0 };
    }

    const playerColor = game.metadata.player_color;
    for (const record of game.ply_records) {
      if (record.side_moved === playerColor) {
        ratingBands[bandKey].accuracies.push(record.accuracy_pct);
        ratingBands[bandKey].count++;
      }
    }
  }

  return Object.entries(ratingBands)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([band, data]) => ({
      rating_range: band,
      accuracy: mean(data.accuracies),
      game_count: data.count,
    }));
}

function calculateOpeningPerformance(
  games: TransformedGame[]
): Array<{
  name: string;
  count: number;
  wins: number;
  losses: number;
  draws: number;
  win_rate: number;
  avg_accuracy: number;
  avg_cp_loss: number;
}> {
  const openingStats: Record<
    string,
    {
      count: number;
      wins: number;
      losses: number;
      draws: number;
      accuracies: number[];
      cpLosses: number[];
    }
  > = {};

  for (const game of games) {
    const openingName =
      game.opening?.name_final ||
      game.metadata.opening ||
      "Unknown Opening";
    const result = game.metadata.result;

    if (!openingStats[openingName]) {
      openingStats[openingName] = {
        count: 0,
        wins: 0,
        losses: 0,
        draws: 0,
        accuracies: [],
        cpLosses: [],
      };
    }

    const stats = openingStats[openingName];
    stats.count++;
    if (result === "win") stats.wins++;
    if (result === "loss") stats.losses++;
    if (result === "draw") stats.draws++;

    const playerColor = game.metadata.player_color;
    for (const record of game.ply_records) {
      if (record.side_moved === playerColor) {
        stats.accuracies.push(record.accuracy_pct);
        stats.cpLosses.push(record.cp_loss);
      }
    }
  }

  return Object.entries(openingStats)
    .map(([name, stats]) => ({
      name,
      count: stats.count,
      wins: stats.wins,
      losses: stats.losses,
      draws: stats.draws,
      win_rate: stats.count > 0 ? (stats.wins / stats.count) * 100 : 0,
      avg_accuracy: mean(stats.accuracies),
      avg_cp_loss: mean(stats.cpLosses),
    }))
    .sort((a, b) => b.count - a.count);
}

function calculatePhaseStats(
  games: TransformedGame[]
): Record<string, { accuracy: number | null; avg_cp_loss: number | null; move_count: number }> {
  const phaseData: Record<
    string,
    { accuracies: number[]; cpLosses: number[]; count: number }
  > = {
    opening: { accuracies: [], cpLosses: [], count: 0 },
    middlegame: { accuracies: [], cpLosses: [], count: 0 },
    endgame: { accuracies: [], cpLosses: [], count: 0 },
  };

  for (const game of games) {
    const playerColor = game.metadata.player_color;
    for (const record of game.ply_records) {
      if (record.side_moved === playerColor) {
        const phase = record.phase;
        if (phaseData[phase]) {
          phaseData[phase].accuracies.push(record.accuracy_pct);
          phaseData[phase].cpLosses.push(record.cp_loss);
          phaseData[phase].count++;
        }
      }
    }
  }

  return {
    opening: {
      accuracy:
        phaseData.opening.count > 0
          ? mean(phaseData.opening.accuracies)
          : null,
      avg_cp_loss:
        phaseData.opening.count > 0 ? mean(phaseData.opening.cpLosses) : null,
      move_count: phaseData.opening.count,
    },
    middlegame: {
      accuracy:
        phaseData.middlegame.count > 0
          ? mean(phaseData.middlegame.accuracies)
          : null,
      avg_cp_loss:
        phaseData.middlegame.count > 0
          ? mean(phaseData.middlegame.cpLosses)
          : null,
      move_count: phaseData.middlegame.count,
    },
    endgame: {
      accuracy:
        phaseData.endgame.count > 0
          ? mean(phaseData.endgame.accuracies)
          : null,
      avg_cp_loss:
        phaseData.endgame.count > 0 ? mean(phaseData.endgame.cpLosses) : null,
      move_count: phaseData.endgame.count,
    },
  };
}

function calculateWinRateByPhase(
  games: TransformedGame[]
): Record<string, number> {
  const phaseResults: Record<string, { wins: number; total: number }> = {
    opening: { wins: 0, total: 0 },
    middlegame: { wins: 0, total: 0 },
    endgame: { wins: 0, total: 0 },
  };

  for (const game of games) {
    const result = game.metadata.result;
    if (result !== "win" && result !== "loss") continue;

    const playerWon = result === "win";
    const playerColor = game.metadata.player_color;
    const phasesSeen = new Set<string>();

    for (const record of game.ply_records) {
      if (record.side_moved === playerColor) {
        phasesSeen.add(record.phase);
      }
    }

    for (const phase of phasesSeen) {
      if (phaseResults[phase]) {
        phaseResults[phase].total++;
        if (playerWon) phaseResults[phase].wins++;
      }
    }
  }

  return {
    opening:
      phaseResults.opening.total > 0
        ? (phaseResults.opening.wins / phaseResults.opening.total) * 100
        : 50.0,
    middlegame:
      phaseResults.middlegame.total > 0
        ? (phaseResults.middlegame.wins / phaseResults.middlegame.total) * 100
        : 50.0,
    endgame:
      phaseResults.endgame.total > 0
        ? (phaseResults.endgame.wins / phaseResults.endgame.total) * 100
        : 50.0,
  };
}

function calculateMistakePatterns(games: TransformedGame[]): Record<string, any> {
  const patterns: Record<string, any> = {
    blunders_in_time_trouble: 0,
    mistakes_after_opponent_blunder: 0,
    repeated_opening_mistakes: {},
    phase_with_most_mistakes: { opening: 0, middlegame: 0, endgame: 0 },
  };

  for (const game of games) {
    const playerColor = game.metadata.player_color;
    let prevOpponentQuality: string | null = null;

    for (const record of game.ply_records) {
      const sideMoved = record.side_moved;
      if (sideMoved === playerColor) {
        if (record.category === "mistake" || record.category === "blunder") {
          patterns.phase_with_most_mistakes[record.phase]++;

          if (record.time_spent_s && record.time_spent_s < 10 && record.category === "blunder") {
            patterns.blunders_in_time_trouble++;
          }
        }

        if (prevOpponentQuality === "blunder" || prevOpponentQuality === "mistake") {
          if (record.category === "mistake" || record.category === "blunder") {
            patterns.mistakes_after_opponent_blunder++;
          }
        }
      } else {
        prevOpponentQuality = record.quality;
      }
    }
  }

  return patterns;
}

function calculateTimeManagement(games: TransformedGame[]): Record<string, number> {
  const timeData: Record<string, number[]> = {
    avg_time_per_move: [],
    time_by_phase_opening: [],
    time_by_phase_middlegame: [],
    time_by_phase_endgame: [],
    fast_move_accuracy: [],
    slow_move_accuracy: [],
  };

  for (const game of games) {
    const playerColor = game.metadata.player_color;
    for (const record of game.ply_records) {
      if (record.side_moved === playerColor && record.time_spent_s) {
        timeData.avg_time_per_move.push(record.time_spent_s);
        timeData[`time_by_phase_${record.phase}`].push(record.time_spent_s);

        if (record.time_spent_s < 5) {
          timeData.fast_move_accuracy.push(record.accuracy_pct);
        } else if (record.time_spent_s > 30) {
          timeData.slow_move_accuracy.push(record.accuracy_pct);
        }
      }
    }
  }

  return {
    avg_time_per_move: mean(timeData.avg_time_per_move),
    avg_time_opening: mean(timeData.time_by_phase_opening),
    avg_time_middlegame: mean(timeData.time_by_phase_middlegame),
    avg_time_endgame: mean(timeData.time_by_phase_endgame),
    fast_move_accuracy: mean(timeData.fast_move_accuracy),
    slow_move_accuracy: mean(timeData.slow_move_accuracy),
  };
}

function calculateAdvancedMetrics(games: TransformedGame[]): Record<string, number> {
  return {
    tactical_complexity_index: 0, // Requires tags
    positional_consistency_index: 0, // Requires tags
    conversion_rate: 0,
    recovery_rate: 0,
    overpress_ratio: 0,
  };
}

function calculateAccuracyByColor(
  games: TransformedGame[]
): Record<string, { accuracy: number; game_count: number; win_rate: number }> {
  const whiteGames = games.filter((g) => g.metadata.player_color === "white");
  const blackGames = games.filter((g) => g.metadata.player_color === "black");

  const getAvgAccuracy = (colorGames: TransformedGame[]): number => {
    const accuracies: number[] = [];
    for (const game of colorGames) {
      const playerColor = game.metadata.player_color;
      for (const record of game.ply_records) {
        if (record.side_moved === playerColor) {
          accuracies.push(record.accuracy_pct);
        }
      }
    }
    return mean(accuracies);
  };

  const getWinRate = (colorGames: TransformedGame[]): number => {
    if (colorGames.length === 0) return 0;
    const wins = colorGames.filter((g) => g.metadata.result === "win").length;
    return wins / colorGames.length;
  };

  return {
    white: {
      accuracy: getAvgAccuracy(whiteGames),
      game_count: whiteGames.length,
      win_rate: getWinRate(whiteGames),
    },
    black: {
      accuracy: getAvgAccuracy(blackGames),
      game_count: blackGames.length,
      win_rate: getWinRate(blackGames),
    },
  };
}

function calculatePerformanceByTimeControl(
  games: TransformedGame[]
): Array<{ time_control: string; accuracy: number; game_count: number; win_rate: number }> {
  const timeControls: Record<string, TransformedGame[]> = {};

  for (const game of games) {
    const tc = game.metadata.time_category || "unknown";
    if (!timeControls[tc]) {
      timeControls[tc] = [];
    }
    timeControls[tc].push(game);
  }

  const getAvgAccuracy = (tcGames: TransformedGame[]): number => {
    const accuracies: number[] = [];
    for (const game of tcGames) {
      const playerColor = game.metadata.player_color;
      for (const record of game.ply_records) {
        if (record.side_moved === playerColor) {
          accuracies.push(record.accuracy_pct);
        }
      }
    }
    return mean(accuracies);
  };

  const getWinRate = (tcGames: TransformedGame[]): number => {
    if (tcGames.length === 0) return 0;
    const wins = tcGames.filter((g) => g.metadata.result === "win").length;
    return wins / tcGames.length;
  };

  return Object.entries(timeControls)
    .map(([tc, tcGames]) => ({
      time_control: tc,
      accuracy: getAvgAccuracy(tcGames),
      game_count: tcGames.length,
      win_rate: getWinRate(tcGames),
    }))
    .sort((a, b) => b.game_count - a.game_count);
}

function calculateCriticalMoments(
  games: TransformedGame[]
): Record<string, number> {
  const criticalPositions: Array<{ accuracy: number }> = [];

  for (const game of games) {
    const playerColor = game.metadata.player_color;
    let prevEval: number | null = null;

    for (const record of game.ply_records) {
      if (record.side_moved !== playerColor) continue;

      const evalAfter = record.eval_after_cp || 0;
      const evalBefore = record.eval_before_cp || 0;

      if (prevEval !== null) {
        const evalSwing = Math.abs(evalAfter - prevEval);
        if (evalSwing >= 200) {
          criticalPositions.push({ accuracy: record.accuracy_pct });
        }
      }
      prevEval = evalAfter;
    }
  }

  if (criticalPositions.length === 0) {
    return {
      total_critical: 0,
      avg_accuracy: 0,
      positions_held: 0,
      positions_lost: 0,
      hold_rate: 0,
    };
  }

  const avgAccuracy = mean(criticalPositions.map((p) => p.accuracy));
  const positionsHeld = criticalPositions.filter((p) => p.accuracy > 80).length;
  const positionsLost = criticalPositions.length - positionsHeld;

  return {
    total_critical: criticalPositions.length,
    avg_accuracy: avgAccuracy,
    positions_held: positionsHeld,
    positions_lost: positionsLost,
    hold_rate:
      criticalPositions.length > 0
        ? (positionsHeld / criticalPositions.length) * 100
        : 0,
  };
}

function calculateAdvantageConversion(
  games: TransformedGame[]
): Record<string, number> {
  let winningPositions = 0;
  let conversions = 0;
  let squandered = 0;
  const avgAdvantageSize: number[] = [];

  for (const game of games) {
    const playerColor = game.metadata.player_color;
    const result = game.metadata.result;
    let hadWinningAdvantage = false;
    let maxAdvantage = 0;

    for (const record of game.ply_records) {
      if (record.side_moved !== playerColor) continue;

      let evalAfter = record.eval_after_cp || 0;
      if (playerColor === "black") evalAfter = -evalAfter;

      if (evalAfter > 200) {
        hadWinningAdvantage = true;
        maxAdvantage = Math.max(maxAdvantage, evalAfter);
      }
    }

    if (hadWinningAdvantage) {
      winningPositions++;
      avgAdvantageSize.push(maxAdvantage);
      if (result === "win") {
        conversions++;
      } else {
        squandered++;
      }
    }
  }

  return {
    winning_positions: winningPositions,
    conversions,
    squandered,
    conversion_rate:
      winningPositions > 0 ? (conversions / winningPositions) * 100 : 0,
    avg_advantage_size: mean(avgAdvantageSize),
  };
}

function calculateBlunderTriggers(
  games: TransformedGame[]
): Record<string, number> {
  const triggers = {
    time_pressure: 0,
    after_opponent_mistake: 0,
    complex_positions: 0,
    simple_positions: 0,
    total_blunders: 0,
  };

  for (const game of games) {
    const playerColor = game.metadata.player_color;
    let prevOpponentQuality: string | null = null;

    for (const record of game.ply_records) {
      const sideMoved = record.side_moved;
      const quality = record.quality;

      if (sideMoved === playerColor && (quality === "blunder" || quality === "mistake")) {
        triggers.total_blunders++;

        if (record.time_spent_s && record.time_spent_s < 10) {
          triggers.time_pressure++;
        }

        if (prevOpponentQuality === "blunder" || prevOpponentQuality === "mistake") {
          triggers.after_opponent_mistake++;
        }
      } else if (sideMoved !== playerColor) {
        prevOpponentQuality = quality;
      }
    }
  }

  const total = triggers.total_blunders;
  return {
    total_blunders: total,
    time_pressure_pct: total > 0 ? (triggers.time_pressure / total) * 100 : 0,
    after_opponent_mistake_pct:
      total > 0 ? (triggers.after_opponent_mistake / total) * 100 : 0,
    complex_positions_pct:
      total > 0 ? (triggers.complex_positions / total) * 100 : 0,
    simple_positions_pct:
      total > 0 ? (triggers.simple_positions / total) * 100 : 0,
  };
}

function calculatePieceActivity(
  games: TransformedGame[]
): Array<{
  piece: string;
  accuracy: number | null;
  move_count: number;
  error_count: number;
  error_rate: number | null;
}> {
  const pieceStats: Record<
    string,
    { accuracies: number[]; moveCount: number; errorCount: number }
  > = {};

  for (const game of games) {
    const playerColor = game.metadata.player_color;
    for (const record of game.ply_records) {
      if (record.side_moved !== playerColor) continue;

      const san = record.san || "";
      let pieceType: string | null = null;

      if (san) {
        const firstChar = san[0];
        if (firstChar === "K") pieceType = "King";
        else if (firstChar === "Q") pieceType = "Queen";
        else if (firstChar === "R") pieceType = "Rook";
        else if (firstChar === "B") pieceType = "Bishop";
        else if (firstChar === "N") pieceType = "Knight";
        else if (firstChar === "O") pieceType = "Castling";
        else if (firstChar.match(/[a-h]/)) pieceType = "Pawn";
      }

      if (pieceType) {
        if (!pieceStats[pieceType]) {
          pieceStats[pieceType] = { accuracies: [], moveCount: 0, errorCount: 0 };
        }
        pieceStats[pieceType].accuracies.push(record.accuracy_pct);
        pieceStats[pieceType].moveCount++;
        if (
          record.quality === "mistake" ||
          record.quality === "blunder" ||
          record.quality === "inaccuracy"
        ) {
          pieceStats[pieceType].errorCount++;
        }
      }
    }
  }

  const allPieces = ["Pawn", "Knight", "Bishop", "Rook", "Queen", "King"];
  return allPieces.map((piece) => {
    const stats = pieceStats[piece] || {
      accuracies: [],
      moveCount: 0,
      errorCount: 0,
    };
    return {
      piece,
      accuracy: stats.moveCount > 0 ? mean(stats.accuracies) : null,
      move_count: stats.moveCount,
      error_count: stats.errorCount,
      error_rate:
        stats.moveCount > 0
          ? (stats.errorCount / stats.moveCount) * 100
          : null,
    };
  });
}

function calculateDiagnosticInsights(
  games: TransformedGame[],
  globalAvg: number
): Array<{ tag: string; count: number; accuracy: number; relevance: number; type: string }> {
  // Simplified - full implementation would require tags
  // For now, return empty array as frontend doesn't have tag data yet
  return [];
}
