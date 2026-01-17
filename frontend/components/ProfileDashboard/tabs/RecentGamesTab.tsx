"use client";

import { useState, useEffect } from "react";
import TrainingSession from "@/components/TrainingSession";
import { getBackendBase } from "@/lib/backendBase";

const INITIAL_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

interface RecentGamesTabProps {
  userId: string;
  onStartTraining?: (lessonData: any) => void;
  onCreateNewTab?: (params: any) => void;
}

export default function RecentGamesTab({ userId, onStartTraining, onCreateNewTab }: RecentGamesTabProps) {
  const [games, setGames] = useState<any[]>([]);
  const [displayedGames, setDisplayedGames] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingGameId, setLoadingGameId] = useState<string | null>(null);
  const [trainingLesson, setTrainingLesson] = useState<any>(null);
  const [gamesToShow, setGamesToShow] = useState(5);
  const [hasMore, setHasMore] = useState(false);
  const backendBase = getBackendBase();

  useEffect(() => {
    const loadGames = async () => {
      try {
        // Only fetch 5 initially for faster loading
        const response = await fetch(`${backendBase}/profile/analyzed_games?user_id=${userId}&limit=5`);
        if (response.ok) {
          const data = await response.json();
          // Only log in development
          if (process.env.NODE_ENV === 'development') {
            console.log("[RecentGamesTab] Loaded games:", data);
            console.log("[RecentGamesTab] Sample game structure:", data.games?.[0]);
          }
          const loadedGames = data.games || [];
          setGames(loadedGames);
          setDisplayedGames(loadedGames);
          setHasMore(loadedGames.length >= 5); // If we got 5, there might be more
        } else {
          const errorText = await response.text();
          console.error("[RecentGamesTab] Failed to load games:", response.status, errorText);
        }
      } catch (error) {
        console.error("Error loading recent games:", error);
      } finally {
        setLoading(false);
      }
    };
    loadGames();
  }, [userId]);

  const loadMoreGames = async () => {
    try {
      const newLimit = gamesToShow + 5;
      const response = await fetch(`${backendBase}/profile/analyzed_games?user_id=${userId}&limit=${newLimit}`);
      if (response.ok) {
        const data = await response.json();
        const loadedGames = data.games || [];
        setGames(loadedGames);
        setGamesToShow(newLimit);
        setDisplayedGames(loadedGames);
        setHasMore(loadedGames.length >= newLimit);
      }
    } catch (error) {
      console.error("Error loading more games:", error);
    }
  };

  const handleViewAnalysis = async (game: any) => {
    const gameId = game.id || game.game_id;
    if (!gameId) {
      console.error("No game ID available");
      return;
    }

    if (!onCreateNewTab) {
      console.error("onCreateNewTab not provided");
      return;
    }

    setLoadingGameId(gameId);
    try {
      // Extract game info for fetch_and_review_games
      const platform = game.platform || "chess.com";
      const externalId = game.game_id || game.external_id;
      
      // Get username from game or use a placeholder
      const username = game.white || game.black || "";
      
      // Create a new tab with the review request
      // Note: game.pgn and game.fen may not be available in minimal metadata fetch
      // The backend will fetch the full game when the review request is processed
      onCreateNewTab({
        action: 'new_tab',
        title: `Game Review: ${game.opponent_name || game.metadata?.opponent_name || 'Opponent'}`,
        type: 'review',
        fen: INITIAL_FEN, // Start from initial position - backend will load the game
        pgn: "", // Empty PGN - backend will fetch it
        initialMessage: `Review my game${externalId ? ` ${externalId}` : ""} from ${platform}${username ? `. Username: ${username}` : ""}`,
        gameId: gameId,
        platform: platform,
        externalId: externalId
      });
    } catch (error) {
      console.error("Error starting game review:", error);
    } finally {
      setLoadingGameId(null);
    }
  };

  const handleTraining = async (game: any) => {
    const gameId = game.id || game.game_id;
    if (!gameId) {
      console.error("No game ID available");
      return;
    }

    if (!onCreateNewTab) {
      console.error("onCreateNewTab not provided");
      return;
    }

    setLoadingGameId(gameId);
    try {
      const response = await fetch(
        `${backendBase}/profile/game/${gameId}/training_lesson`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            user_id: userId,
          }),
        }
      );

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Failed to generate training lesson: ${errorText}`);
      }

      const lessonData = await response.json();
      
      // Convert lesson data to TrainingSession format
      const session = {
        mode: "Game-Based Training",
        composition: {
          new: lessonData.total_drills || 0,
          learning: 0,
          review: 0
        },
        cards: (lessonData.drills || []).map((drill: any, idx: number) => ({
          card_id: drill.card_id || `drill-${idx}`,
          fen: drill.fen,
          side_to_move: drill.side_to_move || "white",
          best_move_san: drill.best_move_san,
          best_move_uci: drill.best_move_uci,
          type: drill.type || "tactics",
          question: drill.question || `Find the best move`,
          hint: drill.hint || "",
          phase: drill.phase,
          opening: drill.opening,
          origin: drill.origin,
          game_date: drill.game_date,
          source_game_id: drill.source_game_id,
          source_ply: drill.source_ply,
          is_from_current_game: drill.is_from_current_game
        })),
        intro: lessonData.intro
      };
      
      // Create a new tab with the training lesson
      // Use the first drill's FEN if available, otherwise starting position
      const firstDrillFen = session.cards[0]?.fen || "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";
      
      onCreateNewTab({
        action: 'new_tab',
        title: `Training: ${game.opponent_name || 'Game'}`,
        type: 'training',
        fen: firstDrillFen,
        pgn: "",
        trainingSession: session,
        initialMessage: lessonData.intro || `Training lesson ready! ${lessonData.total_drills || 0} drills from this game.`
      });
    } catch (error) {
      console.error("Error generating training lesson:", error);
    } finally {
      setLoadingGameId(null);
    }
  };

  if (loading) {
    return (
      <div className="dashboard-loading">
        <div className="spinner"></div>
        <p>Loading recent games...</p>
      </div>
    );
  }

  // If training lesson is active, show it
  if (trainingLesson) {
    return (
      <div className="recent-games-tab">
        {trainingLesson.intro && (
          <div className="training-intro" style={{
            padding: '20px',
            marginBottom: '20px',
            backgroundColor: '#f5f5f5',
            borderRadius: '8px',
            border: '1px solid #ddd'
          }}>
            <p style={{ margin: 0, lineHeight: '1.6' }}>{trainingLesson.intro}</p>
          </div>
        )}
        <TrainingSession
          session={trainingLesson}
          username={userId}
          onComplete={(results) => {
            console.log("Training session complete:", results);
            setTrainingLesson(null);
          }}
          onClose={() => setTrainingLesson(null)}
        />
      </div>
    );
  }

  return (
    <div className="recent-games-tab">
      <div className="tab-section">
        <h2>Recently Analyzed Games</h2>
        <div className="games-list">
          {games.length === 0 ? (
            <div className="no-games">
              <p>No analyzed games yet. Use the Personal Review feature to analyze your games!</p>
            </div>
          ) : (
            <>
              {displayedGames.map((game, idx) => {
              // Handle date - try multiple fields
              const gameDate = game.created_at || game.date || game.analyzed_at;
              let dateDisplay = "Invalid Date";
              try {
                if (gameDate) {
                  const date = new Date(gameDate);
                  if (!isNaN(date.getTime())) {
                    dateDisplay = date.toLocaleDateString();
                  }
                }
              } catch (e) {
                console.warn("Invalid date for game:", gameDate, e);
              }
              
              // Get metadata - check both old and new format
              const metadata = game.metadata || {
                result: game.result || "unknown",
                player_rating: game.player_rating || 0,
                opponent_name: game.opponent_name || "Unknown",
                opponent_rating: game.opponent_rating || 0,
              };
              
              const rating = metadata.player_rating || game.player_rating || 0;
              const opponentName = metadata.opponent_name || game.opponent_name || "Unknown";
              const opponentRating = metadata.opponent_rating || game.opponent_rating || 0;
              const platform = game.platform || "manual";
              const gameId = game.game_id || game.id || "";
              
              // Build platform link
              let platformLink = "";
              if (platform === "chess.com" && gameId) {
                platformLink = `https://www.chess.com/game/live/${gameId}`;
              } else if (platform === "lichess" && gameId) {
                platformLink = `https://lichess.org/${gameId}`;
              }
              
              return (
                <div key={game.id || game.game_id || idx} className="game-card">
                  <div className="game-header">
                    <div className="game-meta">
                      <span className="game-date">{dateDisplay}</span>
                      <span className="game-result">{metadata.result?.toUpperCase() || "UNKNOWN"}</span>
                      {platformLink ? (
                        <a 
                          href={platformLink} 
                          target="_blank" 
                          rel="noopener noreferrer"
                          className="game-platform-link"
                          onClick={(e) => e.stopPropagation()}
                        >
                          {platform === "chess.com" ? "Chess.com" : "Lichess"}
                        </a>
                      ) : (
                        <span className="game-platform">{platform}</span>
                      )}
                    </div>
                    <div className="game-opponent">
                      vs {opponentName} ({opponentRating > 0 ? opponentRating : '?'})
                    </div>
                  </div>
                  <div className="game-actions">
                    <button 
                      className="view-game-btn"
                      onClick={() => handleViewAnalysis(game)}
                      disabled={loadingGameId === (game.id || game.game_id)}
                    >
                      {loadingGameId === (game.id || game.game_id) ? "Loading..." : "View Analysis"}
                    </button>
                    <button 
                      className="generate-training-btn"
                      onClick={() => handleTraining(game)}
                      disabled={loadingGameId === (game.id || game.game_id)}
                    >
                      {loadingGameId === (game.id || game.game_id) ? "Generating..." : "Training"}
                    </button>
                  </div>
                </div>
              );
              })}
              {hasMore && (
                <div className="games-load-more">
                  <button 
                    className="load-more-btn"
                    onClick={loadMoreGames}
                  >
                    Show More (5 more)
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}



