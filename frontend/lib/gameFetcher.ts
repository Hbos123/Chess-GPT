/**
 * Frontend Game Fetcher
 * Fetches games directly from Chess.com and Lichess APIs
 */

import { Chess } from "chess.js";
import type { GameMetadata, GameFetchOptions } from "./gameReviewTypes";

/**
 * Fetch games from Chess.com API
 */
async function fetchChessComGames(
  username: string,
  options: GameFetchOptions
): Promise<GameMetadata[]> {
  const games: GameMetadata[] = [];
  const maxGames = options.max_games || 100;
  const monthsBack = options.months_back || 6;

  try {
    // Get archives list
    const archivesUrl = `https://api.chess.com/pub/player/${username}/games/archives`;
    const archivesResponse = await fetch(archivesUrl);

    if (!archivesResponse.ok) {
      throw new Error(`Chess.com API error: ${archivesResponse.status}`);
    }

    const archivesData = await archivesResponse.json();
    const archives = archivesData.archives || [];

    // Only fetch recent months
    const recentArchives =
      archives.length > monthsBack
        ? archives.slice(-monthsBack)
        : archives;

    // Fetch games from each archive (most recent first)
    for (const archiveUrl of recentArchives.reverse()) {
      if (games.length >= maxGames) break;

      // Rate limiting
      await new Promise((resolve) => setTimeout(resolve, 100));

      const archiveResponse = await fetch(archiveUrl);
      if (!archiveResponse.ok) continue;

      const archiveData = await archiveResponse.json();
      const monthGames = archiveData.games || [];

      for (const gameData of monthGames.reverse()) {
        if (games.length >= maxGames) break;

        const game = parseChessComGame(gameData, username);
        if (game) {
          // Apply filters
          if (matchesFilters(game, options)) {
            games.push(game);
          }
        }
      }
    }
  } catch (error) {
    console.error("Error fetching Chess.com games:", error);
    throw error;
  }

  return games;
}

/**
 * Parse Chess.com game data into standard format
 */
function parseChessComGame(
  gameData: any,
  username: string
): GameMetadata | null {
  try {
    const pgnText = gameData.pgn || "";
    if (!pgnText) return null;

    // Parse PGN to extract metadata
    const chess = new Chess();
    const pgn = chess.pgn({ pgn: pgnText });
    if (!pgn) return null;

    // Parse headers from PGN
    const headers: Record<string, string> = {};
    const headerLines = pgnText.split("\n").filter((line: string) =>
      line.startsWith("[")
    );
    for (const line of headerLines) {
      const match = line.match(/\[(\w+)\s+"([^"]+)"\]/);
      if (match) {
        headers[match[1]] = match[2];
      }
    }

    // Determine player color and ratings
    const whitePlayer = (headers.White || "").toLowerCase();
    const blackPlayer = (headers.Black || "").toLowerCase();
    const usernameLower = username.toLowerCase();

    let playerColor: "white" | "black";
    let playerRating: number;
    let opponentRating: number;
    let opponentName: string;

    if (usernameLower === whitePlayer) {
      playerColor = "white";
      playerRating = parseInt(headers.WhiteElo || "0", 10);
      opponentRating = parseInt(headers.BlackElo || "0", 10);
      opponentName = headers.Black || "Unknown";
    } else if (usernameLower === blackPlayer) {
      playerColor = "black";
      playerRating = parseInt(headers.BlackElo || "0", 10);
      opponentRating = parseInt(headers.WhiteElo || "0", 10);
      opponentName = headers.White || "Unknown";
    } else {
      return null;
    }

    // Determine result from player perspective
    const resultRaw = headers.Result || "*";
    let result: "win" | "loss" | "draw" | "unknown";
    if (resultRaw === "1-0") {
      result = playerColor === "white" ? "win" : "loss";
    } else if (resultRaw === "0-1") {
      result = playerColor === "black" ? "win" : "loss";
    } else if (resultRaw === "1/2-1/2") {
      result = "draw";
    } else {
      result = "unknown";
    }

    // Extract time control
    const timeControlRaw =
      gameData.time_control || headers.TimeControl || "";
    let timeControl: string | number = timeControlRaw;
    try {
      if (typeof timeControlRaw === "string") {
        const baseTime = timeControlRaw.split("+")[0];
        if (baseTime && /^\d+$/.test(baseTime)) {
          timeControl = parseInt(baseTime, 10);
        }
      }
    } catch {
      // Keep original value
    }

    const timeClass = gameData.time_class || "";
    let timeCategory = "unknown";
    if (timeClass.includes("bullet")) timeCategory = "bullet";
    else if (timeClass.includes("blitz")) timeCategory = "blitz";
    else if (timeClass.includes("rapid")) timeCategory = "rapid";
    else if (timeClass.includes("daily") || timeClass.includes("correspondence"))
      timeCategory = "daily";
    else if (timeClass) timeCategory = "classical";

    // Accuracy data
    const accuracies = gameData.accuracies || {};
    const playerAccuracy =
      playerColor === "white"
        ? accuracies.white
        : accuracies.black;
    const opponentAccuracy =
      playerColor === "white"
        ? accuracies.black
        : accuracies.white;

    return {
      game_id: (gameData.url || "").split("/").pop() || "",
      platform: "chess.com",
      url: gameData.url || "",
      date: (headers.Date || "").replace(/\./g, "-"),
      player_color: playerColor,
      player_rating: playerRating,
      opponent_rating: opponentRating,
      opponent_name: opponentName,
      result,
      opening: headers.ECOUrl
        ? headers.ECOUrl.split("/").pop() || ""
        : "",
      eco: headers.ECO || "",
      termination: headers.Termination || "",
      time_control: timeControl,
      time_category: timeCategory,
      pgn: pgnText,
      has_clock: pgnText.includes("[%clk"),
      accuracies,
      player_accuracy: playerAccuracy,
      opponent_accuracy: opponentAccuracy,
    };
  } catch (error) {
    console.error("Error parsing Chess.com game:", error);
    return null;
  }
}

/**
 * Fetch games from Lichess API
 */
async function fetchLichessGames(
  username: string,
  options: GameFetchOptions
): Promise<GameMetadata[]> {
  const games: GameMetadata[] = [];
  const maxGames = options.max_games || 100;
  const monthsBack = options.months_back || 6;

  try {
    // Calculate since timestamp
    const sinceDate = new Date();
    sinceDate.setMonth(sinceDate.getMonth() - monthsBack);
    const sinceMs = sinceDate.getTime();

    const url = `https://lichess.org/api/games/user/${username}`;
    const params = new URLSearchParams({
      max: String(maxGames),
      since: String(sinceMs),
      pgnInJson: "true",
      clocks: "true",
      evals: "false",
      opening: "true",
    });

    const response = await fetch(`${url}?${params}`, {
      headers: {
        Accept: "application/x-ndjson",
      },
    });

    if (!response.ok) {
      throw new Error(`Lichess API error: ${response.status}`);
    }

    // Lichess returns NDJSON (newline-delimited JSON)
    const text = await response.text();
    const lines = text.trim().split("\n");

    for (const line of lines) {
      if (!line.trim()) continue;

      try {
        const gameData = JSON.parse(line);
        const game = parseLichessGame(gameData, username);
        if (game && matchesFilters(game, options)) {
          games.push(game);
        }
      } catch (e) {
        console.warn("Failed to parse Lichess game line:", e);
      }
    }
  } catch (error) {
    console.error("Error fetching Lichess games:", error);
    throw error;
  }

  return games;
}

/**
 * Parse Lichess game data into standard format
 */
function parseLichessGame(
  gameData: any,
  username: string
): GameMetadata | null {
  try {
    const pgnText = gameData.pgn || "";
    if (!pgnText) return null;

    const players = gameData.players || {};
    const whitePlayer = (
      players.white?.user?.name || ""
    ).toLowerCase();
    const blackPlayer = (
      players.black?.user?.name || ""
    ).toLowerCase();
    const usernameLower = username.toLowerCase();

    let playerColor: "white" | "black";
    let playerRating: number;
    let opponentRating: number;
    let opponentName: string;

    if (usernameLower === whitePlayer) {
      playerColor = "white";
      playerRating = players.white?.rating || 0;
      opponentRating = players.black?.rating || 0;
      opponentName = players.black?.user?.name || "Unknown";
    } else if (usernameLower === blackPlayer) {
      playerColor = "black";
      playerRating = players.black?.rating || 0;
      opponentRating = players.white?.rating || 0;
      opponentName = players.white?.user?.name || "Unknown";
    } else {
      return null;
    }

    // Determine result
    const winner = gameData.winner || "";
    let result: "win" | "loss" | "draw" | "unknown";
    if (winner === playerColor) {
      result = "win";
    } else if (winner === "") {
      result = "draw";
    } else {
      result = "loss";
    }

    // Time control
    const speed = gameData.speed || "";
    const timeCategory =
      ["bullet", "blitz", "rapid", "classical", "correspondence"].includes(
        speed
      )
        ? speed
        : "unknown";

    const clock = gameData.clock || {};
    const timeControl = clock.initial
      ? `${Math.floor(clock.initial / 60)}+${clock.increment || 0}`
      : "";

    // Opening
    const openingData = gameData.opening || {};
    const openingName = openingData.name || "";
    const eco = openingData.eco || "";

    // Date
    const createdAt = gameData.createdAt || 0;
    const dateStr = createdAt
      ? new Date(createdAt).toISOString().split("T")[0]
      : "";

    return {
      game_id: gameData.id || "",
      platform: "lichess",
      url: `https://lichess.org/${gameData.id || ""}`,
      date: dateStr,
      player_color: playerColor,
      player_rating: playerRating,
      opponent_rating: opponentRating,
      opponent_name: opponentName,
      result,
      opening: openingName,
      eco,
      termination: gameData.status || "",
      time_control: timeControl,
      time_category: timeCategory,
      pgn: pgnText,
      has_clock: pgnText.includes("[%clk"),
    };
  } catch (error) {
    console.error("Error parsing Lichess game:", error);
    return null;
  }
}

/**
 * Check if game matches filters
 */
function matchesFilters(
  game: GameMetadata,
  options: GameFetchOptions
): boolean {
  // Opponent filter
  if (
    options.opponent &&
    !game.opponent_name.toLowerCase().includes(options.opponent.toLowerCase())
  ) {
    return false;
  }

  // Color filter
  if (options.color && game.player_color !== options.color) {
    return false;
  }

  // Result filter
  if (
    options.result_filter &&
    options.result_filter !== "all" &&
    game.result !== options.result_filter
  ) {
    return false;
  }

  // Time control filter
  if (
    options.time_control &&
    options.time_control !== "all" &&
    game.time_category !== options.time_control
  ) {
    return false;
  }

  // Opening ECO filter
  if (options.opening_eco && game.eco !== options.opening_eco) {
    return false;
  }

  // Rating filters
  if (
    options.min_opponent_rating &&
    game.opponent_rating < options.min_opponent_rating
  ) {
    return false;
  }
  if (
    options.max_opponent_rating &&
    game.opponent_rating > options.max_opponent_rating
  ) {
    return false;
  }

  // Date filters
  if (options.date_from && game.date < options.date_from) {
    return false;
  }
  if (options.date_to && game.date > options.date_to) {
    return false;
  }

  return true;
}

/**
 * Main function to fetch games
 */
export async function fetchGames(
  options: GameFetchOptions
): Promise<GameMetadata[]> {
  const { platform, username } = options;

  if (platform === "chess.com") {
    return fetchChessComGames(username, options);
  } else if (platform === "lichess") {
    return fetchLichessGames(username, options);
  } else {
    throw new Error(`Unknown platform: ${platform}`);
  }
}
