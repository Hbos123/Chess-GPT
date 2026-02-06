"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Chess } from "chess.js";
import TrainingDrill from "./TrainingDrill";
import { getBackendBase } from "@/lib/backendBase";

interface TrainingSessionProps {
  session: any;
  username: string;
  onComplete: (results: any) => void;
  onClose: () => void;
  onSwitchToChat?: () => void; // New prop to switch to chat
  // Optional: integrate with the main board (left dock) so it becomes the primary move entry UI.
  onRegisterExternalMoveHandler?: (
    handler: ((from: string, to: string, promotion?: string) => void) | null
  ) => void;
  onExternalSetPosition?: (fen: string, orientation?: "white" | "black") => void;
}

export default function TrainingSession({
  session,
  username,
  onComplete,
  onClose,
  onSwitchToChat,
  onRegisterExternalMoveHandler,
  onExternalSetPosition
}: TrainingSessionProps) {
  const BACKEND_BASE = getBackendBase();
  const [currentDrillIndex, setCurrentDrillIndex] = useState(0);
  const [results, setResults] = useState<any[]>([]);
  const [isComplete, setIsComplete] = useState(false);
  const [activeTab, setActiveTab] = useState<'training' | 'chat'>('training');
  const useExternalBoard = Boolean(onRegisterExternalMoveHandler && onExternalSetPosition);
  const resultsRef = useRef<any[]>([]);
  useEffect(() => {
    resultsRef.current = results;
  }, [results]);

  // External-board drill state (kept in TrainingSession so we can remove the mini board).
  const [showHint, setShowHint] = useState(false);
  const [hintsUsed, setHintsUsed] = useState(0);
  const [feedback, setFeedback] = useState<{ type: "correct" | "incorrect" | ""; message: string }>({
    type: "",
    message: "",
  });
  const [showSolution, setShowSolution] = useState(false);
  const startTimeRef = useRef<number>(Date.now());

  const currentDrill = session?.cards?.[currentDrillIndex];
  const drillFen = useMemo(() => {
    return currentDrill?.fen || "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";
  }, [currentDrill?.fen]);
  const drillOrientation = useMemo<"white" | "black">(() => {
    const stm = String(currentDrill?.side_to_move || "").toLowerCase();
    return stm === "black" ? "black" : "white";
  }, [currentDrill?.side_to_move]);

  // Generate deterministic hint based on drill tags
  const generateDeterministicHint = useCallback((drill: any): string => {
    if (!drill) return "Look for the best move in this position.";
    
    // Get tags from various sources
    const tags = drill.tags || [];
    const tagTransitions = drill.tag_transitions || {};
    const tagsAfterBest = tagTransitions.gained || [];
    const tagsMissed = tagTransitions.missed || [];
    
    // Priority: tags that would be gained by the best move
    const relevantTags = tagsAfterBest.length > 0 ? tagsAfterBest : (tagsMissed.length > 0 ? tagsMissed : tags);
    
    if (relevantTags.length === 0) {
      return drill.hint || "Look for the best move in this position.";
    }
    
    // Format tag names for display
    const formatTagName = (tag: string): string => {
      return tag
        .replace(/tag\./g, "")
        .replace(/\./g, " ")
        .replace(/_/g, " ")
        .split(" ")
        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
        .join(" ");
    };
    
    // Generate hint phrase
    const primaryTag = relevantTags[0];
    const tagDisplay = formatTagName(primaryTag);
    
    // Generate deterministic hint phrase
    const hintPhrases = [
      `Look for a move that ${tagDisplay.toLowerCase()}.`,
      `Try to find a move that achieves ${tagDisplay.toLowerCase()}.`,
      `Consider moves that ${tagDisplay.toLowerCase()}.`,
      `The best move involves ${tagDisplay.toLowerCase()}.`,
    ];
    
    // Deterministic selection based on tag hash
    const tagHash = primaryTag.split("").reduce((acc: number, char: string) => acc + char.charCodeAt(0), 0);
    const selectedPhrase = hintPhrases[tagHash % hintPhrases.length];
    
    return selectedPhrase;
  }, []);

  // Guard: Check if session has valid cards
  if (!session?.cards || session.cards.length === 0) {
    return (
      <div className="training-session-container">
        <div style={{ padding: "40px", textAlign: "center", color: "#9ca3af" }}>
          <h3>No drills available</h3>
          <p>This session has no drill cards. Please try starting a new drill.</p>
          <button onClick={onClose} className="exit-session-btn" style={{ marginTop: "20px" }}>
            Close
          </button>
        </div>
      </div>
    );
  }

  const handleDrillComplete = useCallback(async (correct: boolean, timeS: number, hintsUsed: number) => {
    const drill = session.cards[currentDrillIndex];
    
    if (!drill) {
      console.error("[TrainingSession] Drill not found at index", currentDrillIndex);
      return;
    }
    
    // Record result
    const result = {
      card_id: drill.card_id,
      correct,
      time_s: timeS,
      hints_used: hintsUsed
    };
    
    setResults((prev) => [...prev, result]);
    
    // Update backend SRS
    try {
      const backendUrl = BACKEND_BASE.replace(/\/$/, "");
      const response = await fetch(`${backendUrl}/update_drill_result`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username,
          card_id: drill.card_id,
          correct,
          time_s: timeS,
          hints_used: hintsUsed
        })
      });
      
      if (!response.ok) {
        console.warn(`[TrainingSession] update_drill_result returned ${response.status}:`, await response.text().catch(() => ""));
      }
    } catch (err) {
      // Silently fail - SRS update is not critical for drill functionality
      console.warn("[TrainingSession] Failed to update drill result (non-critical):", err);
    }
    
    // Move to next drill or finish
    if (currentDrillIndex + 1 < session.cards.length) {
      setTimeout(() => {
        setCurrentDrillIndex(currentDrillIndex + 1);
      }, 500);
    } else {
      setTimeout(() => {
        setIsComplete(true);
        onComplete([...resultsRef.current, result]);
      }, 500);
    }
  }, [BACKEND_BASE, currentDrillIndex, onComplete, session.cards, username]);

  const handleSkip = useCallback(() => {
    // Mark as incorrect skip
    handleDrillComplete(false, 0, 0);
  }, [handleDrillComplete]);

  // Keep external board synced to the current drill.
  useEffect(() => {
    if (!useExternalBoard) return;
    // Reset per-drill UI state
    setShowHint(false);
    setHintsUsed(0);
    setFeedback({ type: "", message: "" });
    setShowSolution(false);
    startTimeRef.current = Date.now();
    onExternalSetPosition?.(drillFen, drillOrientation);
  }, [useExternalBoard, drillFen, drillOrientation, onExternalSetPosition, currentDrillIndex]);

  // Register a move handler so the main board can drive training validation.
  useEffect(() => {
    if (!useExternalBoard) return;
    const handler = (from: string, to: string, promotion?: string) => {
      // Ignore moves while feedback is shown or solution revealed.
      if (showSolution || Boolean(feedback.message)) return;

      try {
        const tmp = new Chess(drillFen);
        const move = tmp.move({ from, to, promotion: promotion as any });
        if (!move) {
          setFeedback({ type: "incorrect", message: "❌ Illegal move. Try again." });
          setTimeout(() => setFeedback({ type: "", message: "" }), 1200);
          // Reset board
          onExternalSetPosition?.(drillFen, drillOrientation);
          return;
        }

        // Show the played move briefly on the main board.
        onExternalSetPosition?.(tmp.fen(), drillOrientation);

        const spentS = (Date.now() - startTimeRef.current) / 1000;

        const bestUci = String(currentDrill?.best_move_uci || "").trim().toLowerCase();
        const bestSan = String(currentDrill?.best_move_san || "").trim().toLowerCase();
        const playedUci = `${String(move.from || "").toLowerCase()}${String(move.to || "").toLowerCase()}${String(
          move.promotion || ""
        ).toLowerCase()}`.trim();
        const playedSan = String(move.san || "").trim().toLowerCase();

        const correct =
          (bestUci && playedUci && playedUci === bestUci) || (bestSan && playedSan && playedSan === bestSan);

        if (correct) {
          setFeedback({ type: "correct", message: "✅ That move was right!" });
          // Keep the move on the board - don't reset
          setTimeout(() => {
            handleDrillComplete(true, spentS, hintsUsed);
          }, 2000);
          return;
        }

        // Wrong move: show feedback, then push back after 2 seconds
        setFeedback({ type: "incorrect", message: "❌ That move wasn't it - try again" });
        setTimeout(() => {
          setFeedback({ type: "", message: "" });
          // Reset board to original position (push back)
          onExternalSetPosition?.(drillFen, drillOrientation);
        }, 2000);
      } catch (e) {
        setFeedback({ type: "incorrect", message: "❌ Invalid move. Try again." });
        setTimeout(() => setFeedback({ type: "", message: "" }), 1200);
        onExternalSetPosition?.(drillFen, drillOrientation);
      }
    };

    onRegisterExternalMoveHandler?.(handler);
    return () => {
      onRegisterExternalMoveHandler?.(null);
    };
  }, [
    useExternalBoard,
    onRegisterExternalMoveHandler,
    onExternalSetPosition,
    drillFen,
    drillOrientation,
    currentDrill?.best_move_uci,
    currentDrill?.best_move_san,
    showSolution,
    feedback.message,
    hintsUsed,
    handleDrillComplete,
  ]);

  const handleShowHint = () => {
    setShowHint(true);
    setHintsUsed((v) => v + 1);
  };

  const handleGiveUp = () => {
    setShowSolution(true);
    const spentS = (Date.now() - startTimeRef.current) / 1000;
    setFeedback({
      type: "correct",
      message: `💡 Solution: ${currentDrill?.best_move_san || currentDrill?.best_move_uci || "—"}. ${currentDrill?.hint || ""}`,
    });
    setTimeout(() => {
      handleDrillComplete(false, spentS, hintsUsed + 1);
    }, 2200);
  };

  if (isComplete) {
    const correctCount = results.filter(r => r.correct).length;
    const accuracy = (correctCount / results.length) * 100;
    const avgTime = results.reduce((sum, r) => sum + r.time_s, 0) / results.length;

    return (
      <div className="training-session-complete">
        <h2>🎯 Session Complete!</h2>
        
        <div className="session-summary">
          <div className="summary-stat">
            <div className="stat-label">Accuracy</div>
            <div className="stat-value">{accuracy.toFixed(0)}%</div>
          </div>
          <div className="summary-stat">
            <div className="stat-label">Drills Completed</div>
            <div className="stat-value">{correctCount}/{results.length}</div>
          </div>
          <div className="summary-stat">
            <div className="stat-label">Avg Time</div>
            <div className="stat-value">{avgTime.toFixed(1)}s</div>
          </div>
        </div>

        <div className="session-feedback">
          {accuracy >= 80 && <p>🌟 Excellent work! Your pattern recognition is strong.</p>}
          {accuracy >= 60 && accuracy < 80 && <p>👍 Good session! Keep practicing these patterns.</p>}
          {accuracy < 60 && <p>💪 Keep training! Review the missed drills and try again.</p>}
        </div>

        <div className="session-actions">
          <button className="review-mistakes-btn" onClick={() => setCurrentDrillIndex(0)}>
            Review Mistakes
          </button>
          <button className="close-session-btn" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="training-session-container">
      <div className="session-header">
        <h3>Training Session: {session.mode}</h3>
        {session.intro && (
          <div className="session-intro">
            {session.intro}
          </div>
        )}
        <div className="session-composition">
          New: {session.composition.new} • Learning: {session.composition.learning} • Review: {session.composition.review}
        </div>
      </div>

      {/* Tab switcher */}
      <div className="training-tabs">
        <button
          className={`training-tab ${activeTab === 'training' ? 'active' : ''}`}
          onClick={() => setActiveTab('training')}
        >
          Training
        </button>
        <button
          className={`training-tab ${activeTab === 'chat' ? 'active' : ''}`}
          onClick={() => {
            setActiveTab('chat');
            if (onSwitchToChat) {
              onSwitchToChat();
            }
          }}
        >
          Chat
        </button>
      </div>

      {/* Always-visible feedback (shows even if you're on the Chat sub-tab) */}
      {feedback.message && (
        <div className={`drill-feedback ${feedback.type}`} aria-live="polite" style={{ marginTop: '1rem', marginBottom: '1rem' }}>
          {feedback.message}
        </div>
      )}

      {activeTab === 'training' && (
        <div className="training-content">
          {useExternalBoard ? (
            <div className="training-drill-container">
              <div className="drill-header">
                <div className="drill-progress">
                  Drill {currentDrillIndex + 1} of {session.cards.length}
                </div>
                <div className="drill-type-badge">{currentDrill?.type || "tactics"}</div>
              </div>

              <div className="drill-question">
                <h3>{currentDrill?.question || "Find the best move"}</h3>
                {currentDrill?.phase && (
                  <div className="drill-meta">
                    Phase: {currentDrill.phase} {currentDrill.opening && `• Opening: ${currentDrill.opening}`}
                  </div>
                )}
                <div className="drill-meta" style={{ marginTop: 8 }}>
                  Use the main board on the left to play your move.
                </div>
                <div className="drill-meta">
                  {String(currentDrill?.side_to_move || "white").toLowerCase() === "black" ? "Black" : "White"} to move
                </div>
              </div>

              {showHint && !showSolution && (
                <div className="drill-hint">
                  <h4>💡 Hint:</h4>
                  <p>{generateDeterministicHint(currentDrill) || currentDrill?.hint || "Look for the best move in this position."}</p>
                </div>
              )}

              <div className="drill-actions">
                {!showSolution && !feedback.message && (
                  <>
                    <button onClick={handleShowHint} className="hint-btn" disabled={showHint}>
                      {showHint ? "💡 Hint shown" : "Show Hint"}
                    </button>
                    <button onClick={handleGiveUp} className="solution-btn">
                      Give up (show solution)
                    </button>
                    <button onClick={handleSkip} className="skip-btn">
                      Skip
                    </button>
                  </>
                )}
              </div>
            </div>
          ) : (
          <TrainingDrill
            drill={session.cards[currentDrillIndex]}
            onComplete={handleDrillComplete}
            onSkip={handleSkip}
            currentIndex={currentDrillIndex}
            totalDrills={session.cards.length}
          />
          )}
        </div>
      )}

      {activeTab === 'chat' && onSwitchToChat && (
        <div className="training-chat-placeholder">
          <p>Switch to chat tab to continue conversation</p>
        </div>
      )}

      <div className="session-footer">
        <button onClick={onClose} className="exit-session-btn">
          Exit Session
        </button>
      </div>
    </div>
  );
}

