"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
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
  const FEEDBACK_TOAST_MS = 3000;
  const WRONG_RESET_MS = 2000;
  const [mounted, setMounted] = useState(false);
  const [currentDrillIndex, setCurrentDrillIndex] = useState(0);
  const [results, setResults] = useState<any[]>([]);
  const [isComplete, setIsComplete] = useState(false);
  const [activeTab, setActiveTab] = useState<'training' | 'chat'>('training');
  const useExternalBoard = Boolean(onRegisterExternalMoveHandler && onExternalSetPosition);
  const resultsRef = useRef<any[]>([]);
  const feedbackTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const resetTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const completeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const correctLockRef = useRef(false);
  const drillFenRef = useRef<string>("");
  const drillOrientationRef = useRef<"white" | "black">("white");
  const bestUciRef = useRef<string>("");
  const bestSanRef = useRef<string>("");
  const hintsUsedRef = useRef<number>(0);
  const showSolutionRef = useRef<boolean>(false);
  const feedbackRef = useRef<{ type: "correct" | "incorrect" | ""; message: string }>({ type: "", message: "" });
  const onExternalSetPositionRef = useRef<typeof onExternalSetPosition>(onExternalSetPosition);
  const handleDrillCompleteRef = useRef<
    ((correct: boolean, timeS: number, hintsUsed: number) => Promise<void>) | null
  >(null);
  useEffect(() => {
    resultsRef.current = results;
  }, [results]);
  useEffect(() => {
    setMounted(true);
  }, []);
  useEffect(() => {
    onExternalSetPositionRef.current = onExternalSetPosition;
  }, [onExternalSetPosition]);

  // External-board drill state (kept in TrainingSession so we can remove the mini board).
  const [hintLevel, setHintLevel] = useState(0);
  const [hintsUsed, setHintsUsed] = useState(0);
  const [feedback, setFeedback] = useState<{ type: "correct" | "incorrect" | ""; message: string }>({
    type: "",
    message: "",
  });
  const [showSolution, setShowSolution] = useState(false);
  const startTimeRef = useRef<number>(Date.now());
  useEffect(() => {
    showSolutionRef.current = showSolution;
  }, [showSolution]);
  useEffect(() => {
    hintsUsedRef.current = hintsUsed;
  }, [hintsUsed]);
  useEffect(() => {
    feedbackRef.current = feedback;
  }, [feedback]);

  const currentDrill = session?.cards?.[currentDrillIndex];
  const drillFen = useMemo(() => {
    return currentDrill?.fen || "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";
  }, [currentDrill?.fen]);
  const drillOrientation = useMemo<"white" | "black">(() => {
    const stm = String(currentDrill?.side_to_move || "").toLowerCase();
    return stm === "black" ? "black" : "white";
  }, [currentDrill?.side_to_move]);
  useEffect(() => {
    drillFenRef.current = drillFen;
    drillOrientationRef.current = drillOrientation;
    // Update best move refs too (card schema varies by source)
    bestUciRef.current = String(currentDrill?.best_move_uci || "").trim().toLowerCase();
    bestSanRef.current = String(currentDrill?.best_move_san || "").trim().toLowerCase();
  }, [drillFen, drillOrientation, currentDrill?.best_move_uci, currentDrill?.best_move_san]);

  const formatTagName = useCallback((tag: string): string => {
    return String(tag || "")
      .replace(/tag\./g, "")
      .replace(/\./g, " ")
      .replace(/_/g, " ")
      .split(" ")
      .filter(Boolean)
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(" ");
  }, []);

  // Deterministic, multi-step hints (deeper than just "do tag X")
  const buildHintSteps = useCallback(
    (drill: any): string[] => {
      if (!drill) return ["Look for the best move in this position."];

      const transitions = drill.tag_transitions || {};
      const gained: string[] = Array.isArray(transitions.gained) ? transitions.gained : [];
      const missed: string[] = Array.isArray(transitions.missed) ? transitions.missed : [];
      const lost: string[] = Array.isArray(transitions.lost) ? transitions.lost : [];
      const tags: string[] = Array.isArray(drill.tags) ? drill.tags : [];

      // Priority: what the best move gains, then what was missed, then anything present.
      const primaryTag = gained[0] || missed[0] || lost[0] || tags[0] || "";
      const primaryDisplay = primaryTag ? formatTagName(primaryTag) : "";

      const steps: string[] = [];

      // Step 1: theme-oriented hint
      if (primaryDisplay) {
        const kind = gained[0] ? "create" : missed[0] ? "restore" : lost[0] ? "avoid losing" : "improve";
        const phrasing = [
          `Theme: ${primaryDisplay}. Try to ${kind} it with your move.`,
          `Focus: ${primaryDisplay}. Find the move that helps you ${kind} it.`,
          `Key idea: ${primaryDisplay}. Look for a move that lets you ${kind} it.`,
        ];
        const tagHash = primaryTag.split("").reduce((acc: number, char: string) => acc + char.charCodeAt(0), 0);
        steps.push(phrasing[tagHash % phrasing.length]);
      } else if (drill.hint) {
        steps.push(String(drill.hint));
      } else {
        steps.push("Look for the best move in this position.");
      }

      // Step 2: surface a couple more cues from transitions (deterministic ordering)
      const secondaryTags = [...gained.slice(0, 2), ...missed.slice(0, 2), ...lost.slice(0, 2)]
        .filter(Boolean)
        .slice(0, 3)
        .map(formatTagName)
        .filter(Boolean);
      if (secondaryTags.length > 0) {
        steps.push(`Secondary cues: ${secondaryTags.join(", ")}.`);
      } else {
        steps.push("Shortlist candidate moves and calculate 1–2 plies: checks, captures, and direct threats first.");
      }

      // Step 3: generic but useful search heuristic
      steps.push("If nothing is forcing, improve your worst piece or address king safety / hanging pieces.");

      return steps;
    },
    [formatTagName]
  );

  const hintSteps = useMemo(() => buildHintSteps(currentDrill), [buildHintSteps, currentDrill]);

  const setFeedbackState = useCallback(
    (next: { type: "correct" | "incorrect" | ""; message: string }) => {
      feedbackRef.current = next;
      setFeedback(next);
    },
    []
  );

  const clearTimers = useCallback(() => {
    if (feedbackTimerRef.current) {
      clearTimeout(feedbackTimerRef.current);
      feedbackTimerRef.current = null;
    }
    if (resetTimerRef.current) {
      clearTimeout(resetTimerRef.current);
      resetTimerRef.current = null;
    }
    if (completeTimerRef.current) {
      clearTimeout(completeTimerRef.current);
      completeTimerRef.current = null;
    }
  }, []);

  const showFeedback = useCallback(
    (type: "correct" | "incorrect", message: string, ttlMs: number = FEEDBACK_TOAST_MS) => {
      // Replace any existing banner immediately.
      if (feedbackTimerRef.current) {
        clearTimeout(feedbackTimerRef.current);
        feedbackTimerRef.current = null;
      }
      setFeedbackState({ type, message });
      feedbackTimerRef.current = setTimeout(() => {
        setFeedbackState({ type: "", message: "" });
        feedbackTimerRef.current = null;
      }, ttlMs);
    },
    [FEEDBACK_TOAST_MS, setFeedbackState]
  );

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
  useEffect(() => {
    handleDrillCompleteRef.current = handleDrillComplete;
  }, [handleDrillComplete]);

  const handleSkip = useCallback(() => {
    // Mark as incorrect skip
    handleDrillComplete(false, 0, 0);
  }, [handleDrillComplete]);

  // Keep external board synced to the current drill.
  useEffect(() => {
    if (!useExternalBoard) return;
    // Reset per-drill UI state
    clearTimers();
    correctLockRef.current = false;
    setHintLevel(0);
    setHintsUsed(0);
    setFeedbackState({ type: "", message: "" });
    setShowSolution(false);
    startTimeRef.current = Date.now();
    onExternalSetPositionRef.current?.(drillFenRef.current, drillOrientationRef.current);
  }, [useExternalBoard, drillFen, drillOrientation, onExternalSetPosition, currentDrillIndex, clearTimers]);

  // Register a move handler so the main board can drive training validation.
  const externalMoveHandler = useCallback(
    (from: string, to: string, promotion?: string) => {
      // Never accept moves when solution is revealed, or after a correct move (until we advance).
      if (showSolutionRef.current || correctLockRef.current) return;

      // If user plays again while an incorrect/illegal banner is showing, replace it with the new outcome.
      const fb = feedbackRef.current;
      if (fb.message && fb.type !== "correct") {
        clearTimers();
        setFeedbackState({ type: "", message: "" });
      }

      const baseFen = drillFenRef.current;
      const orientation = drillOrientationRef.current;
      const bestUci = bestUciRef.current;
      const bestSan = bestSanRef.current;

      try {
        const tmp = new Chess(baseFen);
        const move = tmp.move({ from, to, promotion: promotion as any });
        if (!move) {
          showFeedback("incorrect", "❌ Illegal move. Try again.", FEEDBACK_TOAST_MS);
          onExternalSetPositionRef.current?.(baseFen, orientation);
          return;
        }

        // Show the played move on the main board.
        onExternalSetPositionRef.current?.(tmp.fen(), orientation);

        const spentS = (Date.now() - startTimeRef.current) / 1000;

        const playedUci = `${String(move.from || "").toLowerCase()}${String(move.to || "").toLowerCase()}${String(
          move.promotion || ""
        ).toLowerCase()}`.trim();
        const playedSan = String(move.san || "").trim().toLowerCase();

        const isCorrect =
          (bestUci && playedUci && playedUci === bestUci) || (bestSan && playedSan && playedSan === bestSan);

        if (isCorrect) {
          correctLockRef.current = true;
          showFeedback("correct", "✅ Correct!", FEEDBACK_TOAST_MS);
          completeTimerRef.current = setTimeout(() => {
            handleDrillCompleteRef.current?.(true, spentS, hintsUsedRef.current);
            completeTimerRef.current = null;
          }, FEEDBACK_TOAST_MS);
          return;
        }

        // Wrong move: show feedback, then push back after 2 seconds (but banner stays 3 seconds)
        showFeedback("incorrect", "❌ Not quite — retry.", FEEDBACK_TOAST_MS);
        resetTimerRef.current = setTimeout(() => {
          onExternalSetPositionRef.current?.(baseFen, orientation);
          resetTimerRef.current = null;
        }, WRONG_RESET_MS);
      } catch (e) {
        showFeedback("incorrect", "❌ Invalid move. Try again.", FEEDBACK_TOAST_MS);
        onExternalSetPositionRef.current?.(baseFen, orientation);
      }
    },
    [clearTimers, setFeedbackState, showFeedback, FEEDBACK_TOAST_MS, WRONG_RESET_MS]
  );

  useEffect(() => {
    if (!useExternalBoard) return;
    onRegisterExternalMoveHandler?.(externalMoveHandler);
    return () => {
      onRegisterExternalMoveHandler?.(null);
    };
  }, [useExternalBoard, onRegisterExternalMoveHandler, externalMoveHandler]);

  const handleShowHint = () => {
    setHintLevel((lvl) => Math.min(lvl + 1, hintSteps.length));
    setHintsUsed((v) => v + 1);
  };

  const handleGiveUp = () => {
    setShowSolution(true);
    const spentS = (Date.now() - startTimeRef.current) / 1000;
    setFeedbackState({
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
      {mounted && feedback.message
        ? createPortal(
            <div className={`drill-feedback toast ${feedback.type}`} aria-live="polite">
              {feedback.message}
            </div>,
            document.body
          )
        : null}

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

              {hintLevel > 0 && !showSolution && (
                <div className="drill-hint">
                  <h4>💡 Hint {hintLevel}:</h4>
                  <p>{hintSteps[Math.max(0, hintLevel - 1)] || currentDrill?.hint || "Look for the best move in this position."}</p>
                </div>
              )}

              <div className="drill-actions">
                {!showSolution && !feedback.message && (
                  <>
                    <button onClick={handleShowHint} className="hint-btn" disabled={hintLevel >= hintSteps.length}>
                      {hintLevel <= 0 ? "Show Hint" : "Show next hint"}
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

