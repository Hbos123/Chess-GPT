"use client";

import { useState, useEffect, useRef, useMemo, useCallback } from "react";
import { Chess } from "chess.js";
import Board from "./Board";
import { formatTagName } from "@/lib/tagGroups";

interface TrainingDrillProps {
  drill: any;
  onComplete: (correct: boolean, timeS: number, hintsUsed: number) => void;
  onSkip: () => void;
  currentIndex: number;
  totalDrills: number;
}

export default function TrainingDrill({
  drill,
  onComplete,
  onSkip,
  currentIndex,
  totalDrills
}: TrainingDrillProps) {
  const [showHint, setShowHint] = useState(false);
  const [hintsUsed, setHintsUsed] = useState(0);
  const [startTime] = useState(Date.now());
  const [userMove, setUserMove] = useState("");
  const [feedback, setFeedback] = useState<{type: "correct" | "incorrect" | ""; message: string}>({type: "", message: ""});
  const [showSolution, setShowSolution] = useState(false);
  
  // INFINITE LOOP PREVENTION:
  // - Use refs to track previous values and only update when they actually change
  // - Memoize derived values to prevent new object/array references on every render
  // - Use function initializers in useState to prevent recreation on every render
  // - Check for actual value changes before calling setState in useEffect
  
  const prevDrillIdRef = useRef<string | undefined>(undefined);
  const prevFenRef = useRef<string | undefined>(undefined);

  const bestMoveUciNorm = useMemo(() => {
    const raw = drill?.best_move_uci;
    if (!raw || typeof raw !== "string") return "";
    return raw.trim().toLowerCase();
  }, [drill?.best_move_uci]);

  const bestMoveSanNorm = useMemo(() => {
    const raw = drill?.best_move_san;
    if (!raw || typeof raw !== "string") return "";
    return raw.trim().toLowerCase();
  }, [drill?.best_move_san]);

  const isCorrectMove = useCallback(
    (moveObj: any) => {
      // Prefer UCI equality to avoid SAN formatting mismatches (+/#/disambiguation)
      try {
        const from = String(moveObj?.from || "").toLowerCase();
        const to = String(moveObj?.to || "").toLowerCase();
        const promo = String(moveObj?.promotion || "").toLowerCase();
        const uci = `${from}${to}${promo}`.trim();
        if (bestMoveUciNorm && uci) return uci === bestMoveUciNorm;
      } catch {
        // fall back to SAN
      }
      const san = String(moveObj?.san || "").trim().toLowerCase();
      if (bestMoveSanNorm && san) return san === bestMoveSanNorm;
      return false;
    },
    [bestMoveUciNorm, bestMoveSanNorm]
  );
  
  // Memoize the initial FEN to prevent recreation on every render
  const initialFen = useMemo(() => {
    return drill.fen || "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";
  }, [drill.fen]);
  
  // Initialize game state - use function initializer to prevent recreation
  const [drillGame, setDrillGame] = useState<Chess>(() => {
    try {
      return new Chess(initialFen);
    } catch (e) {
      console.error("Failed to initialize drill game:", e);
      return new Chess("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1");
    }
  });
  
  // Reset state when drill changes - only when card_id actually changes
  // This prevents infinite loops by checking refs before updating state
  useEffect(() => {
    const currentDrillId = drill.card_id;
    const currentFen = drill.fen;
    
    // Only reset if drill ID or FEN actually changed (not just a new reference)
    if (prevDrillIdRef.current !== currentDrillId || prevFenRef.current !== currentFen) {
      prevDrillIdRef.current = currentDrillId;
      prevFenRef.current = currentFen;
      
      setShowHint(false);
      setHintsUsed(0);
      setUserMove("");
      setFeedback({type: "", message: ""});
      setShowSolution(false);
      
      // Only create new game if FEN actually changed
      try {
        const newGame = new Chess(currentFen || initialFen);
        setDrillGame(newGame);
      } catch (e) {
        console.error("Invalid FEN in drill:", currentFen, e);
        setDrillGame(new Chess(initialFen));
      }
    }
  }, [drill.card_id, drill.fen, initialFen]);

  const handleBoardMove = (from: string, to: string, promotion?: string) => {
    if (showSolution || feedback.message) return;
    
    try {
      const tempGame = new Chess(drill.fen);
      const move = tempGame.move({ from, to, promotion });
      
      if (!move) {
        setFeedback({
          type: "incorrect",
          message: "❌ Invalid move. Try again."
        });
        // Clear feedback so the user can keep trying
        setTimeout(() => {
          setFeedback({ type: "", message: "" });
        }, 1500);
        return;
      }
      
      const timeSpent = (Date.now() - startTime) / 1000;
      const isCorrect = isCorrectMove(move);
      
      setUserMove(move.san);
      setDrillGame(tempGame);
      
      if (isCorrect) {
        setFeedback({
          type: "correct",
          message: `✅ Correct!`,
        });
        setTimeout(() => onComplete(true, timeSpent, hintsUsed), 1500);
      } else {
        setFeedback({
          type: "incorrect",
          message: `❌ Not quite. Try again, or give up to reveal the solution.`,
        });
        // Reset board AND clear feedback after showing incorrect feedback (so retry actually works)
        setTimeout(() => {
          setDrillGame(new Chess(drill.fen));
          setFeedback({ type: "", message: "" });
          setUserMove("");
        }, 2000);
      }
    } catch (e) {
      setFeedback({
        type: "incorrect",
        message: "❌ Invalid move. Try again."
      });
      setTimeout(() => {
        setFeedback({ type: "", message: "" });
      }, 1500);
    }
  };

  const handleTextMove = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      const move = (e.target as HTMLInputElement).value.trim();
      if (!move) return;
      
      try {
        const tempGame = new Chess(drill.fen);
        const moveObj = tempGame.move(move);
        
        if (!moveObj) {
          setFeedback({
            type: "incorrect",
            message: "❌ Invalid move notation. Try again."
          });
          setTimeout(() => {
            setFeedback({ type: "", message: "" });
          }, 1500);
          return;
        }
        
        const timeSpent = (Date.now() - startTime) / 1000;
        const isCorrect = isCorrectMove(moveObj);
        
        setUserMove(move);
        setDrillGame(tempGame);
        
        if (isCorrect) {
          setFeedback({
            type: "correct",
            message: `✅ Correct!`,
          });
          setTimeout(() => onComplete(true, timeSpent, hintsUsed), 1500);
        } else {
          setFeedback({
            type: "incorrect",
            message: `❌ Not quite. Try again, or give up to reveal the solution.`,
          });
          setTimeout(() => {
            setDrillGame(new Chess(drill.fen));
            setFeedback({ type: "", message: "" });
            setUserMove("");
          }, 2000);
        }
      } catch (e) {
        setFeedback({
          type: "incorrect",
          message: "❌ Invalid move notation. Try again."
        });
        setTimeout(() => {
          setFeedback({ type: "", message: "" });
        }, 1500);
      }
    }
  };

  const handleShowHint = () => {
    setShowHint(true);
    setHintsUsed(hintsUsed + 1);
  };

  const handleShowSolution = () => {
    setShowSolution(true);
    setFeedback({
      type: "correct",
      message: `💡 Solution: ${drill.best_move_san}. ${drill.hint || ""}`
    });
    
    const timeSpent = (Date.now() - startTime) / 1000;
    
    setTimeout(() => {
      onComplete(false, timeSpent, hintsUsed + 1);
    }, 3000);
  };

  const boardOrientation = drill.side_to_move === "white" ? "white" : "black";

  const originText = useMemo(() => {
    if (drill.origin) return String(drill.origin);
    const opening = drill.opening ? String(drill.opening) : "";
    const phase = drill.phase ? String(drill.phase) : "";
    const src = drill.source || {};
    const gameId = src.game_id ? String(src.game_id).slice(0, 8) : "";
    const ply = src.ply != null ? String(src.ply) : "";
    const parts = [];
    if (opening) parts.push(opening);
    if (phase) parts.push(phase);
    if (gameId) parts.push(`game ${gameId}`);
    if (ply) parts.push(`ply ${ply}`);
    return parts.length > 0 ? parts.join(" • ") : "";
  }, [drill.origin, drill.opening, drill.phase, drill.source]);

  // Generate intelligent position description based on drill context
  const positionDescription = useMemo(() => {
    const parts: string[] = [];
    
    // Determine who played the previous move
    const source = drill.source || {};
    const errorSide = source.error_side; // "white" or "black" - who made the mistake
    const currentSide = drill.side_to_move; // who is to move now
    
    // If error_side matches current side, opponent just played; otherwise user just played
    const previousMoveWasByUser = errorSide && errorSide === currentSide;
    const actor = previousMoveWasByUser ? "You" : "Your opponent";
    const poss = previousMoveWasByUser ? "your" : "their";
    
    // Get tag transitions
    const tagTransitions = drill.tag_transitions || {};
    const tagsLost = tagTransitions.lost || [];
    const tagsGained = tagTransitions.gained || [];
    const tagsMissed = tagTransitions.missed || [];
    
    // Get piece context
    const pieceContext = drill.piece_context || {};
    const blunderedPiece = pieceContext.blundered;
    const bestMovePiece = pieceContext.best_move;
    
    // Build description based on what was lost
    if (tagsLost.length > 0) {
      const primaryTag = tagsLost[0];
      const tagDisplay = formatTagName(primaryTag);
      
      if (blunderedPiece) {
        parts.push(`${actor} played ${poss} ${blunderedPiece.toLowerCase()}, losing the chance to maintain ${tagDisplay}.`);
      } else {
        parts.push(`${actor} played a move losing the chance to maintain ${tagDisplay}.`);
      }
    } else if (tagsMissed.length > 0) {
      const primaryTag = tagsMissed[0];
      const tagDisplay = formatTagName(primaryTag);
      parts.push(`${actor} missed the opportunity to gain ${tagDisplay}.`);
    } else if (tagsGained.length > 0 && errorSide) {
      // If tags were gained but it was a mistake, describe what was lost
      const primaryTag = tagsGained[0];
      const tagDisplay = formatTagName(primaryTag);
      parts.push(`${actor} played a move that gained ${tagDisplay}, but at a cost.`);
    } else {
      // Fallback: generic description
      if (errorSide) {
        parts.push(`${actor} played a suboptimal move in this position.`);
      } else {
        parts.push(`Find the best move in this position.`);
      }
    }
    
    // Add phase/opening context if available
    if (drill.phase) {
      const phaseText = drill.phase.charAt(0).toUpperCase() + drill.phase.slice(1);
      parts.push(`This is a ${phaseText.toLowerCase()} position.`);
    }
    
    return parts.join(" ");
  }, [drill.source, drill.side_to_move, drill.tag_transitions, drill.piece_context, drill.phase]);

  return (
    <div className="training-drill-container">
      <div className="drill-header">
        <div className="drill-progress">
          Drill {currentIndex + 1} of {totalDrills}
        </div>
        <div className="drill-type-badge">{drill.type}</div>
      </div>

      <div className="drill-question">
        <h3>{drill.question}</h3>
        {drill.phase && (
          <div className="drill-meta">
            Phase: {drill.phase} {drill.opening && `• Opening: ${drill.opening}`}
          </div>
        )}
        {(drill.origin || originText) && (
          <div className="drill-origin">
            📍 {drill.origin || originText}
            {drill.game_date && (
              <span className="drill-date">
                ({new Date(drill.game_date).toLocaleDateString()})
              </span>
            )}
          </div>
        )}
      </div>

      <div className="drill-board-section">
        <div className="drill-board-wrapper">
          <Board
            fen={drillGame.fen()}
            onMove={handleBoardMove}
            orientation={boardOrientation}
            disabled={showSolution || !!feedback.message}
          />
        </div>
        <div className="drill-board-info">
          <div className="position-info">
            <div className="position-side">
              {drill.side_to_move === "white" ? "White" : "Black"} to move
            </div>
            {positionDescription && (
              <div className="position-description">
                {positionDescription}
              </div>
            )}
          </div>
          {!showSolution && !feedback.message && (
            <div className="move-input-section">
              <label>Use the main board on the left to play your move.</label>
            </div>
          )}
        </div>
      </div>

      {feedback.message && (
        <div className={`drill-feedback ${feedback.type}`}>
          {feedback.message}
        </div>
      )}

      {showSolution && drill.best_move_san && (
        <div className="solution-display">
          ✅ Solution: {drill.best_move_san}
        </div>
      )}

      <div className="drill-actions">
        {!showSolution && !feedback.message && (
          <>
            <button onClick={handleShowHint} className="hint-btn" disabled={showHint}>
              {showHint ? `💡 ${drill.hint || "No hint available"}` : "Show Hint"}
            </button>
            <button onClick={handleShowSolution} className="solution-btn">
              Give up (show solution)
            </button>
            <button onClick={onSkip} className="skip-btn">
              Skip
            </button>
          </>
        )}
      </div>

      {showHint && !showSolution && (
        <div className="drill-hint">
          {drill.hint || "No hint available for this position."}
        </div>
      )}
    </div>
  );
}

