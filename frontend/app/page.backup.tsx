"use client";

import { useState, useEffect } from "react";
import { Chess } from "chess.js";
import Board from "@/components/Board";
import Chat from "@/components/Chat";
import RouterHint from "@/components/RouterHint";
import FENDisplay from "@/components/FENDisplay";
import PGNViewer from "@/components/PGNViewer";
import LessonBuilder from "@/components/LessonBuilder";
import ExpandableTable from "@/components/ExpandableTable";
import PersonalReview from "@/components/PersonalReview";
import TrainingManager from "@/components/TrainingManager";
import type { Mode, ChatMessage, Annotation, TacticsPuzzle } from "@/types";
import {
  getMeta,
  analyzePosition,
  playMove,
  tacticsNext,
  annotate,
} from "@/lib/api";
import { MoveTree } from "@/lib/moveTree";
import type { MoveNode } from "@/lib/moveTree";

const INITIAL_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

export default function Home() {
  const [fen, setFen] = useState(INITIAL_FEN);
  const [pgn, setPgn] = useState("");
  const [mode, setMode] = useState<Mode>("DISCUSS"); // Default to DISCUSS
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [annotations, setAnnotations] = useState<Annotation>({
    fen: INITIAL_FEN,
    pgn: "",
    comments: [],
    nags: [],
    arrows: [],
    highlights: [],
  });
  // Store annotations per FEN position
  const [annotationsByFen, setAnnotationsByFen] = useState<Map<string, { arrows: any[], highlights: any[] }>>(new Map());
  // Store raw analysis data per FEN position
  const [analysisDataByFen, setAnalysisDataByFen] = useState<Map<string, any>>(new Map());
  const [systemPrompt, setSystemPrompt] = useState("");
  const [llmEnabled, setLlmEnabled] = useState(true);
  const [currentTactic, setCurrentTactic] = useState<TacticsPuzzle | null>(null);
  const [tacticAttempts, setTacticAttempts] = useState<string[]>([]);
  const [game, setGame] = useState(new Chess());
  const [waitingForEngine, setWaitingForEngine] = useState(false);
  const [boardOrientation, setBoardOrientation] = useState<"white" | "black">("white");
  const [moveTree, setMoveTree] = useState<MoveTree>(new MoveTree());
  const [treeVersion, setTreeVersion] = useState(0); // Force re-render counter
  const [lastAdvantageLevel, setLastAdvantageLevel] = useState<string>("equal"); // Track advantage changes
  const [isReviewing, setIsReviewing] = useState(false);
  const [reviewProgress, setReviewProgress] = useState(0);
  const [walkthroughActive, setWalkthroughActive] = useState(false);
  const [walkthroughData, setWalkthroughData] = useState<any>(null);
  const [walkthroughStep, setWalkthroughStep] = useState(0);
  const [gameReviewData, setGameReviewData] = useState<any>(null); // Store full review for LLM access
  const [reviewSideFocus, setReviewSideFocus] = useState<"white" | "black" | "both">("both");
  const [reviewPresentationMode, setReviewPresentationMode] = useState<"talk" | "tables">("talk");
  const [gameReviewKeyPoints, setGameReviewKeyPoints] = useState<any[]>([]); // Store key points for clicking
  const [retryMoveData, setRetryMoveData] = useState<any>(null); // Store move to retry
  const [isRetryMode, setIsRetryMode] = useState(false); // Track if in retry mode
  
  // Lesson system state
  const [showLessonBuilder, setShowLessonBuilder] = useState(false);
  const [showOpeningModal, setShowOpeningModal] = useState(false);
  const [openingQuery, setOpeningQuery] = useState("");
  const [currentLesson, setCurrentLesson] = useState<any>(null);
  const [lessonProgress, setLessonProgress] = useState({ current: 0, total: 0 });
  const [currentLessonPosition, setCurrentLessonPosition] = useState<any>(null);
  const [lessonMode, setLessonMode] = useState(false);
  const [lessonMoveIndex, setLessonMoveIndex] = useState(0); // Current move in ideal line
  const [isOffMainLine, setIsOffMainLine] = useState(false); // Player deviated from ideal line
  const [mainLineFen, setMainLineFen] = useState<string>(""); // FEN to return to
  
  // Personal Review state
  const [showPersonalReview, setShowPersonalReview] = useState(false);
  
  // Training & Drills state
  const [showTraining, setShowTraining] = useState(false);
  
  // Analysis cache - store analysis by FEN for instant LLM access
  const [analysisCache, setAnalysisCache] = useState<Record<string, any>>({});
  const [isAnalyzing, setIsAnalyzing] = useState(false);

  // Helper function to call LLM through backend (avoids CORS)
  // Helper to format evaluations (convert mate scores to M# notation)
  function formatEval(cp: number | string, mateScore: number = 10000): string {
    if (typeof cp === 'string') {
      // Already formatted (e.g., "M8")
      if (cp.startsWith('M')) return cp;
      cp = parseInt(cp);
    }
    
    if (Math.abs(cp) >= mateScore - 100) {
      // Within 100cp of mate score - it's a mate
      if (cp > 0) {
        const movesToMate = Math.floor((mateScore - cp) / 100) + 1;
        return `M${movesToMate}`;
      } else {
        const movesToMate = Math.floor((mateScore + cp) / 100) + 1;
        return `M-${movesToMate}`;
      }
    }
    return cp.toString();
  }
  
  // Helper to get last N non-system messages for chat context
  function getRecentChatContext(n: number = 3): { role: string; content: string }[] {
    const nonSystemMessages = messages.filter(m => 
      m.role !== 'system' && 
      m.role !== 'button' && 
      m.role !== 'graph' && 
      m.role !== 'expandable_table'
    );
    return nonSystemMessages.slice(-n).map(m => ({
      role: m.role === 'user' ? 'user' : 'assistant',
      content: m.content || ''
    }));
  }

  // Calculate move quality from cached position analyses (NO duplicate Stockfish!)
  function calculateMoveQuality(
    moveSan: string,
    positionBefore: any,
    positionAfter: any
  ): any {
    try {
      // Get evaluations from position analyses
      const evalBefore = positionBefore?.eval_cp || 0;
      const evalAfter = positionAfter?.eval_cp || 0;
      
      // Get best move from position before
      const candidatesBefore = positionBefore?.candidate_moves || [];
      const bestMoveBefore = candidatesBefore[0];
      const bestEvalBefore = bestMoveBefore?.eval_cp || evalBefore;
      const secondBest = candidatesBefore[1];
      const secondBestGap = secondBest ? Math.abs(bestEvalBefore - secondBest.eval_cp) : 0;
      
      // Calculate CP loss (from perspective of side that moved)
      const cpLoss = Math.abs(bestEvalBefore - evalAfter);
      
      // Determine quality (same rules as game review)
      let quality = '';
      if (cpLoss === 0 && secondBestGap >= 50) {
        quality = '⚡ CRITICAL BEST';
      } else if (cpLoss === 0) {
        quality = '✓ BEST';
      } else if (cpLoss < 20) {
        quality = '✓ Excellent';
      } else if (cpLoss < 50) {
        quality = '✓ Good';
      } else if (cpLoss < 80) {
        quality = '!? Inaccuracy';
      } else if (cpLoss < 200) {
        quality = '? Mistake';
      } else {
        quality = '?? Blunder';
      }
      
      return {
        move_san: moveSan,
        cp_loss: cpLoss,
        quality: quality,
        best_move_san: bestMoveBefore?.move || 'N/A',
        eval_before_cp: evalBefore,
        eval_after_cp: evalAfter,
        second_best_gap_cp: secondBestGap,
        better_alternatives: cpLoss > 20 ? candidatesBefore.slice(0, 3) : []
      };
    } catch (error) {
      console.error('Error calculating move quality:', error);
      return null;
    }
  }

  // Auto-analyze position AND calculate move quality (runs in background)
  async function autoAnalyzePositionAndMove(currentFen: string, moveSan: string, fenBeforeMove: string) {
    // Skip if already cached
    if (analysisCache[currentFen]) {
      console.log('💾 Analysis already cached for this position');
      return;
    }
    
    setIsAnalyzing(true);
    console.log('🔄 Auto-analyzing position in background...');
    
    try {
      // SINGLE Stockfish call - analyze the new position only
      const positionResponse = await fetch(`http://localhost:8000/analyze_position?fen=${encodeURIComponent(currentFen)}&depth=18&lines=3`);
      if (!positionResponse.ok) {
        console.error('Position analysis failed:', positionResponse.statusText);
        setIsAnalyzing(false);
        return;
      }
      
      const positionAnalysis = await positionResponse.json();
      console.log('✅ Position analysis complete (single Stockfish call)');
      
      // Calculate move quality from CACHED position data (no additional Stockfish!)
      const positionBefore = analysisCache[fenBeforeMove];
      const moveQuality = positionBefore ? 
        calculateMoveQuality(moveSan, positionBefore, positionAnalysis) : 
        null;
      
      if (moveQuality) {
        console.log(`✅ Move quality calculated: ${moveQuality.quality} (${moveQuality.cp_loss}cp loss)`);
      } else {
        console.log('⚠️ No previous position cached - move quality unavailable');
      }
      
      // Cache position + move quality together
      setAnalysisCache(prev => ({
        ...prev,
        [currentFen]: {
          ...positionAnalysis,
          move_analysis: moveQuality  // Calculated from cache, not Stockfish!
        }
      }));
      
      console.log('✅ Analysis cached (optimized - no duplicate Stockfish)');
    } catch (error) {
      console.error('Auto-analysis error:', error);
    } finally {
      setIsAnalyzing(false);
    }
  }

  async function callLLM(
    messages: { role: string; content: string }[], 
    temperature: number = 0.7, 
    model: string = "gpt-4o-mini",
    useTools: boolean = true
  ): Promise<{content: string, tool_calls?: any[], context?: any, raw_data?: any}> {
    try {
      // Build context for tools - include cached analysis if available
      const cachedAnalysis = analysisCache[fen];
      const context = {
        fen: fen,
        cached_analysis: cachedAnalysis || null,  // Include pre-computed analysis
        pgn: pgn,
        mode: mode,
        has_fen: fen !== INITIAL_FEN,
        has_pgn: pgn.length > 0,
        board_state: game.fen()
      };
      
      const response = await fetch("http://localhost:8000/llm_chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          messages, 
          temperature, 
          model,
          use_tools: useTools,
          context: context
        }),
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "LLM call failed");
      }
      
      const data = await response.json();
      
      // Log tool calls if any
      let shouldTriggerAnalysis = false;
      
      if (data.tool_calls && data.tool_calls.length > 0) {
        console.log(`🔧 Tools called (${data.iterations} iterations):`, data.tool_calls.map((tc: any) => tc.tool).join(', '));
        data.tool_calls.forEach((tc: any) => {
          console.log(`   ${tc.tool}:`, tc.arguments);
          console.log(`   Result:`, tc.result_text || tc.result);
          
          // Check if tool wants to trigger analyze position flow
          if (tc.result_text && tc.result_text.includes('__TRIGGER_ANALYZE_POSITION__')) {
            console.log('   🎯 Will trigger full analyze position flow...');
            shouldTriggerAnalysis = true;
          }
        });
      }
      
      // If we need to trigger analysis, do it and return empty content (suppress LLM response)
      if (shouldTriggerAnalysis) {
        console.log('🎯 Suppressing generic LLM response, running full analysis instead...');
        setTimeout(() => handleAnalyzePosition(), 100);
        return {
          content: "",  // Empty - don't show the generic LLM response
          tool_calls: data.tool_calls || [],
          context: context,
          raw_data: {
            tool_calls: data.tool_calls,
            triggered_analysis: true
          }
        };
      }
      
      return {
        content: data.content,
        tool_calls: data.tool_calls || [],
        context: context,
        raw_data: {
          tool_calls: data.tool_calls,
          iterations: data.iterations,
          usage: data.usage
        }
      };
    } catch (error) {
      console.error("LLM call error:", error);
      throw error;
    }
  }

  // Update annotations when FEN changes to show position-specific annotations
  useEffect(() => {
    const fenAnnotations = annotationsByFen.get(fen);
    if (fenAnnotations) {
      setAnnotations(prev => ({
        ...prev,
        fen,
        arrows: fenAnnotations.arrows,
        highlights: fenAnnotations.highlights
      }));
    } else {
      // Clear annotations if none exist for this position
      setAnnotations(prev => ({
        ...prev,
        fen,
        arrows: [],
        highlights: []
      }));
    }
  }, [fen, annotationsByFen]);

  // Load system prompt on mount
  useEffect(() => {
    let initialized = false;
    
    if (!initialized) {
    getMeta()
      .then((meta) => {
        setSystemPrompt(meta.system_prompt);
          if (messages.length === 0) { // Only add if no messages yet
            addSystemMessage("Chess GPT ready! Ask me anything about chess, or make a move on the board to start playing. You can also say 'let's play', 'analyze', or 'give me a puzzle'!");
          }
      })
      .catch((err) => {
        console.error("Failed to load meta:", err);
          if (messages.length === 0) {
        addSystemMessage("⚠ Backend not available. Start the backend server.");
          }
      });
      
      initialized = true;
    }
  }, []);

  // Update annotations when FEN or PGN changes
  useEffect(() => {
    setAnnotations((prev) => ({
      ...prev,
      fen,
      pgn,
    }));
  }, [fen, pgn]);

  // Keyboard shortcuts for navigation
  useEffect(() => {
    const handleKeyPress = (e: KeyboardEvent) => {
      // Only handle if not typing in input/textarea
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
        return;
      }

      switch (e.key) {
        case 'ArrowLeft':
          e.preventDefault();
          handleNavigateBack();
          break;
        case 'ArrowRight':
          e.preventDefault();
          handleNavigateForward();
          break;
        case 'Home':
          e.preventDefault();
          handleNavigateStart();
          break;
        case 'End':
          e.preventDefault();
          handleNavigateEnd();
          break;
      }
    };

    window.addEventListener('keydown', handleKeyPress);
    return () => window.removeEventListener('keydown', handleKeyPress);
  }, [moveTree, fen]);

  function addSystemMessage(content: string) {
    setMessages((prev) => [...prev, { role: "system", content }]);
  }

  function addUserMessage(content: string) {
    setMessages((prev) => [...prev, { role: "user", content }]);
  }

  function addAssistantMessage(content: string, meta?: any) {
    // Ensure meta always includes cached analysis for raw data button
    const enrichedMeta = {
      ...meta,
      rawEngineData: meta?.rawEngineData || 
                     meta?.tool_raw_data?.endpoint_response ||
                     analysisCache[fen]
    };
    
    setMessages((prev) => [...prev, { role: "assistant", content, meta: enrichedMeta }]);
    
    // Auto-apply LLM annotations for all responses
    setTimeout(() => {
      // Try to get analysis data from multiple sources
      const engineData = enrichedMeta.rawEngineData;
      
      if (engineData && content) {
        applyLLMAnnotations(content, engineData);
      }
    }, 500); // Small delay to let message render first
  }

  // Fuzzy matching helper - checks if word is similar to target (allows 1-2 char difference)
  function isSimilarWord(word: string, target: string, maxDiff: number = 2): boolean {
    if (word === target) return true;
    if (Math.abs(word.length - target.length) > maxDiff) return false;
    
    // Simple Levenshtein-like check
    let differences = 0;
    const minLen = Math.min(word.length, target.length);
    const maxLen = Math.max(word.length, target.length);
    
    for (let i = 0; i < minLen; i++) {
      if (word[i] !== target[i]) differences++;
    }
    differences += maxLen - minLen;
    
    return differences <= maxDiff;
  }

  // Check if message contains any variation of a word (typos, alternate spellings)
  function containsWordVariation(msg: string, variations: string[]): boolean {
    const words = msg.toLowerCase().split(/\s+/);
    for (const word of words) {
      for (const variant of variations) {
        if (isSimilarWord(word, variant, 2)) return true;
      }
    }
    return false;
  }

  function isGeneralChat(msg: string): boolean {
    const lower = msg.toLowerCase().trim();
    
    // Greetings and pleasantries
    const greetings = ["hi", "hello", "hey", "yo", "sup", "howdy", "greetings"];
    if (greetings.includes(lower)) return true;
    
    // Questions about the app itself
    if (lower.includes("what can you do") || 
        lower.includes("what are you") ||
        lower.includes("who are you") ||
        lower.includes("help me") ||
        lower.includes("how does this work")) return true;
    
    // General pleasantries
    if (lower.includes("how are you") || 
        lower.includes("what's up") ||
        lower.includes("thanks") ||
        lower.includes("thank you")) return true;
    
    return false;
  }

  function detectMoveAnalysisRequest(msg: string): { 
    isMoveAnalysis: boolean; 
    move: string | null; 
    isHypothetical: boolean;
    referenceMove?: string; // For "instead of X" patterns
  } {
    const lower = msg.toLowerCase().trim();
    
    // EXPANDED: Hypothetical move patterns (future/conditional)
    const hypotheticalPatterns = [
      // What if patterns
      "what if i play", "what if i played", "what if i had played",
      "what if we play", "what if i go", "what if i went",
      
      // Question patterns
      "what about", "how about", "what do you think about",
      "should i play", "should i have played", "should i go with",
      "is it good to play", "is it worth playing",
      
      // Would/Could patterns
      "would it be good", "would it work", "would playing",
      "could i play", "can i play", "could i have played",
      
      // Conditional patterns
      "if i play", "if i played", "if i had played",
      "if i go", "if i went", "if i move",
      
      // Consider patterns
      "consider", "considering", "thinking about",
      "exploring", "looking at", "trying",
      
      // Better/instead patterns
      "better to play", "instead of", "rather than",
      "prefer", "alternative"
    ];
    
    const isHypothetical = hypotheticalPatterns.some(pattern => lower.includes(pattern));
    
    // EXPANDED: Analysis patterns (evaluating a move)
    const analyzePatterns = [
      // Analyze keywords
      "analyze", "analyse", "analayze", "analize",
      "analysis of", "break down", "look at",
      
      // Rate/evaluate
      "rate", "rating", "evaluate", "evaluation", "assess", "assessment",
      "judge", "review", "check", "examine",
      
      // Opinion patterns
      "what do you think of", "what do you think about",
      "what do you make of", "your thoughts on", "thoughts on",
      "opinion on", "view on", "take on",
      
      // Quality questions
      "how is", "how was", "how's", "how good is",
      "is this good", "was this good", "is that good", "was that good",
      "is it good", "was it good", "good move",
      
      // Comparison
      "compare", "better", "worse", "stronger", "weaker"
    ];
    
    // EXPANDED: Current position patterns
    const currentPositionPatterns = [
      "here", "in this position", "from here", "from this position",
      "now", "currently", "at this point", "right now",
      "this position", "current position"
    ];
    
    // EXPANDED: Previous move patterns
    const previousMovePatterns = [
      "last move", "previous move", "that move", "this move",
      "my move", "my last move", "the move i played",
      "that last move", "the move", "recent move"
    ];
    
    // Check for "instead of" patterns (comparing hypotheticals to played moves)
    const insteadOfMatch = lower.match(/(instead of|rather than|vs|versus|compared to|over)\s+([a-h][1-8]|[KQRBN][a-h]?[1-8]?x?[a-h][1-8])/i);
    let referenceMove: string | undefined = undefined;
    if (insteadOfMatch) {
      referenceMove = insteadOfMatch[2];
    }
    
    // Check if message contains any analysis pattern OR is hypothetical OR references position
    const hasAnalysisPattern = analyzePatterns.some(pattern => lower.includes(pattern)) || 
                               isHypothetical ||
                               currentPositionPatterns.some(pattern => lower.includes(pattern));
    
    if (!hasAnalysisPattern) {
      return { isMoveAnalysis: false, move: null, isHypothetical: false };
    }
    
    // Try to extract move notation (e.g., "e4", "Nf3", "O-O", "Qxe5+")
    // Look for chess move patterns in the message
    const movePattern = /\b([KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]?|O-O(?:-O)?)\b/gi;
    const matches = msg.match(movePattern);
    
    if (matches && matches.length > 0) {
      // If there's a reference move (instead of), use the first match as the main move
      const mainMove = matches[0];
      
      // Return the move found
      return { isMoveAnalysis: true, move: mainMove, isHypothetical, referenceMove };
    }
    
    // Check if they're asking about the last/previous move (not hypothetical)
    if (!isHypothetical && previousMovePatterns.some(pattern => lower.includes(pattern))) {
      // We'll need to get the last move from the game history
      return { isMoveAnalysis: true, move: "LAST_MOVE", isHypothetical: false };
    }
    
    return { isMoveAnalysis: false, move: null, isHypothetical: false };
  }

  // REMOVED: shouldTriggerAnalysis() - Now redundant
  // All analysis is auto-cached after moves, LLM uses cached data automatically

  // Comprehensive mode detection with typo tolerance
  function detectMode(msg: string): Mode | null {
    const lower = msg.toLowerCase().trim();
    
    // Priority 1: TACTICS Mode Detection
    const tacticVariants = ["tactic", "tactics", "tatic", "tatcic", "puzzle", "puzzel", "puzle"];
    const mateVariants = ["mate", "checkmate", "mating", "checkmating"];
    
    if (containsWordVariation(lower, tacticVariants)) return "TACTICS";
    if (containsWordVariation(lower, mateVariants) && lower.includes("in")) return "TACTICS";
    if (lower.includes("puzzle") || lower.includes("training") || lower.includes("exercise")) return "TACTICS";
    if (lower.includes("find the") && (lower.includes("tactic") || lower.includes("win") || lower.includes("combination"))) return "TACTICS";
    if (lower.includes("solve") || lower.includes("solution")) return "TACTICS";
    
    // Priority 2: ANALYZE Mode Detection (already handled by shouldTriggerAnalysis)
    // We return ANALYZE if analysis was already triggered, otherwise check for other modes
    
    // Priority 3: DISCUSS Mode Detection
    const explainVariants = ["explain", "explan", "explian", "why", "whi", "how"];
    const discussVariants = ["discuss", "discus", "tell", "describe", "talk"];
    
    if (containsWordVariation(lower, explainVariants) && !lower.includes("should")) return "DISCUSS";
    if (containsWordVariation(lower, discussVariants)) return "DISCUSS";
    if (lower.includes("why") && (lower.includes("move") || lower.includes("good") || lower.includes("bad"))) return "DISCUSS";
    if (lower.includes("how") && lower.includes("work")) return "DISCUSS";
    if (lower.includes("what") && (lower.includes("idea") || lower.includes("plan") || lower.includes("concept"))) return "DISCUSS";
    if (lower.includes("tell me about")) return "DISCUSS";
    if (lower.includes("what does") || lower.includes("what is")) return "DISCUSS";
    
    // Priority 4: PLAY Mode Detection (Natural game invitations)
    const playVariants = ["play", "plya", "paly", "ply"];
    const gameVariants = ["game", "gam", "gaem", "match"];
    
    // Check for SAN move pattern (highest confidence for PLAY)
    if (/^[KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](=[QRBN])?[+#]?$/.test(msg.trim())) return "PLAY";
    
    // Check for coordinate notation (e2e4, g1f3, etc.)
    if (/^[a-h][1-8][a-h][1-8][qrbn]?$/i.test(msg.trim())) return "PLAY";
    
    // Game invitations and setup (comprehensive)
    if (lower.includes("let") && containsWordVariation(lower, playVariants)) return "PLAY";
    if (lower.includes("lets") && containsWordVariation(lower, playVariants)) return "PLAY";
    if (lower.includes("wanna") && containsWordVariation(lower, playVariants)) return "PLAY";
    if (lower.includes("want to") && containsWordVariation(lower, playVariants)) return "PLAY";
    if (lower.includes("want") && containsWordVariation(lower, playVariants) && containsWordVariation(lower, gameVariants)) return "PLAY";
    if (lower.includes("can we") && containsWordVariation(lower, playVariants)) return "PLAY";
    if (lower.includes("shall we") && containsWordVariation(lower, playVariants)) return "PLAY";
    if (lower.includes("could we") && containsWordVariation(lower, playVariants)) return "PLAY";
    if (lower.includes("would you") && containsWordVariation(lower, playVariants)) return "PLAY";
    if (lower.includes("can i") && containsWordVariation(lower, playVariants)) return "PLAY";
    if (lower.includes("may i") && containsWordVariation(lower, playVariants)) return "PLAY";
    
    // "I want to play a game" patterns
    if (lower.includes("i want") && containsWordVariation(lower, playVariants)) return "PLAY";
    if (lower.includes("id like") && containsWordVariation(lower, playVariants)) return "PLAY";
    if (lower.includes("i'd like") && containsWordVariation(lower, playVariants)) return "PLAY";
    if (lower.includes("i would like") && containsWordVariation(lower, playVariants)) return "PLAY";
    
    // Game setup phrases
    if (containsWordVariation(lower, playVariants) && containsWordVariation(lower, gameVariants)) return "PLAY";
    if (lower.includes("start") && containsWordVariation(lower, gameVariants)) return "PLAY";
    if (lower.includes("new") && containsWordVariation(lower, gameVariants)) return "PLAY";
    if (lower.includes("begin") && containsWordVariation(lower, gameVariants)) return "PLAY";
    
    // Color selection (strong play indicator)
    if (lower.includes("i'll play") || lower.includes("ill play")) return "PLAY";
    if (lower.includes("i'll be") || lower.includes("ill be")) return "PLAY";
    if (lower.includes("i'll start") || lower.includes("ill start")) return "PLAY";
    if (lower.includes("as white") || lower.includes("as black")) return "PLAY";
    if (lower.includes("with white") || lower.includes("with black")) return "PLAY";
    if (lower.includes("play white") || lower.includes("play black")) return "PLAY";
    if (lower.includes("i am white") || lower.includes("i am black")) return "PLAY";
    if (lower.includes("im white") || lower.includes("im black")) return "PLAY";
    
    // Play against/with
    if (lower.includes("play against")) return "PLAY";
    if (lower.includes("play with")) return "PLAY";
    if (lower.includes("challenge")) return "PLAY";
    
    // Simple play command
    if (lower === "play" || lower === "lets play" || lower === "let's play") return "PLAY";
    if (lower === "start" || lower === "begin" || lower === "go") return "PLAY";
    
    // Move commands
    if (lower === "make a move" || lower === "your move" || lower === "engine move") return "PLAY";
    if (lower === "continue" || lower === "keep playing" || lower === "continue playing") return "PLAY";
    if (lower === "next move" || lower === "play next") return "PLAY";
    
    return null; // No clear mode detected - will default to DISCUSS
  }

  // Legacy function - keeping for backward compatibility but will use detectMode
  function inferModeFromMessage(msg: string): Mode | undefined {
    return detectMode(msg) || undefined;
  }

  function getBoardContext(): string {
    const isStartPosition = fen === INITIAL_FEN;
    const hasMoves = pgn.length > 0 && game.history().length > 0;
    const moveCount = game.history().length;
    
    if (isStartPosition && !hasMoves) {
      return "starting_position_empty";
    } else if (hasMoves) {
      return `game_in_progress_${moveCount}_moves`;
    } else if (!isStartPosition) {
      return "custom_position_set";
    }
    return "unknown";
  }

  async function handleGeneralChat(message: string) {
    const boardContext = getBoardContext();
    const isStartPosition = fen === INITIAL_FEN;
    const hasMoves = pgn.length > 0 && game.history().length > 0;
    const moveCount = game.history().length;

    if (!llmEnabled) {
      // Provide helpful suggestions without LLM
      let response = "Hello! I'm Chess GPT. ";
      
      if (boardContext === "starting_position_empty") {
        response += "Here's what you can do:\n\n";
        response += "• Type a move like 'e4' to start playing\n";
        response += "• Click 'Analyze Position' to get insights\n";
        response += "• Click 'Next Tactic' to solve puzzles\n";
        response += "• Ask me anything about chess!";
      } else if (boardContext.includes("game_in_progress")) {
        response += `I see you've played ${moveCount} move${moveCount > 1 ? 's' : ''}. `;
        response += "You can:\n\n";
        response += "• Continue playing (make your next move)\n";
        response += "• Click 'Analyze Position' to evaluate the current position\n";
        response += "• Ask 'What should I do?' for advice\n";
        response += "• Click 'Copy PGN' to save your game";
      } else if (boardContext === "custom_position_set") {
        response += "I see you have a custom position set up. You can:\n\n";
        response += "• Click 'Analyze Position' to evaluate it\n";
        response += "• Start playing from this position\n";
        response += "• Ask questions about the position";
      }
      
      addAssistantMessage(response);
      return;
    }

    // Add game review context if available
    let gameReviewContext = "";
    if (gameReviewData && gameReviewData.ply_records && gameReviewData.ply_records.length > 0) {
      const stats = gameReviewData.stats || { white: {}, black: {} };
      const whiteAcc = stats.white?.overall_accuracy || 100;
      const blackAcc = stats.black?.overall_accuracy || 100;
      const openingName = gameReviewData.opening?.name_final || "Unknown";
      const totalMoves = gameReviewData.ply_records.length;
      const keyPoints = gameReviewData.key_points || [];
      
      gameReviewContext = `

GAME REVIEW DATA AVAILABLE:
- Opening: ${openingName}
- Total moves analyzed: ${totalMoves}
- White accuracy: ${whiteAcc.toFixed(1)}%
- Black accuracy: ${blackAcc.toFixed(1)}%
- Key moments: ${keyPoints.length}
- Side focus: ${gameReviewData.side_focus || 'both'}

The user can ask questions about this reviewed game (specific moves, mistakes, key moments, etc.).
If they ask about the game, refer to this data.
`;
    }
    
    // Generate context-aware LLM response
    const contextPrompt = `
User sent a general greeting/chat message: "${message}"

Current Board State:
- FEN: ${fen}
- Is starting position: ${isStartPosition}
- Has moves played: ${hasMoves}
- Move count: ${moveCount}
- PGN: ${pgn || "Empty"}

Context Analysis:
${boardContext === "starting_position_empty" ? 
  "The board is at the starting position with no moves played yet." :
  boardContext.includes("game_in_progress") ?
  `There's a game in progress with ${moveCount} moves played.` :
  boardContext === "custom_position_set" ?
  "There's a custom chess position set up on the board." :
  "Unknown board state"}${gameReviewContext}

Instructions:
1. Respond warmly and naturally to their greeting/message
2. Based on the board state, offer relevant suggestions:
   - If starting position: Suggest starting a game, analyzing openings, or solving tactics
   - If game in progress: Offer to analyze the position, suggest next moves, or review the game
   - If custom position: Offer to analyze the position or play from here
   - If game review data is available and they ask about it: Reference the specific statistics and findings
3. Keep response friendly, concise (2-3 sentences), and helpful
4. Don't analyze the position unless explicitly asked
`;

    try {
      const result = await callLLM([
        { 
          role: "system", 
          content: "You are Chess GPT, a friendly chess assistant. You help users play, analyze, and learn chess. Be warm, encouraging, and concise." 
        },
        { role: "user", content: contextPrompt },
      ], 0.8);
      
      const reply = result.content;
      
      // Store minimal meta for general chat with cached analysis
      const meta = {
        type: "general_chat",
        boardContext,
        fen,
        moveCount,
        tool_context: result.context,
        tool_raw_data: result.raw_data,
        rawEngineData: analysisCache[fen] // Include cached analysis for annotations
      };
      
      addAssistantMessage(reply, meta);
    } catch (err: any) {
      addSystemMessage(`Error: ${err.message}`);
    }
  }

  function describeMoveType(move: any, board: Chess): string {
    // Describe the move type based on chess.js Move object
    const descriptions = [];
    
    if (move.captured) {
      descriptions.push("captures");
    }
    if (move.flags.includes('k') || move.flags.includes('q')) {
      descriptions.push("castles");
    }
    if (move.flags.includes('e')) {
      descriptions.push("en passant");
    }
    if (move.flags.includes('p')) {
      descriptions.push("promotes");
    }
    if (move.san.includes('+')) {
      descriptions.push("gives check");
    }
    if (move.san.includes('#')) {
      descriptions.push("checkmate!");
    }
    
    // If no special flags, describe by piece
    if (descriptions.length === 0) {
      const piece = move.piece;
      if (piece === 'p') descriptions.push("advances pawn");
      if (piece === 'n') descriptions.push("develops knight");
      if (piece === 'b') descriptions.push("develops bishop");
      if (piece === 'r') descriptions.push("activates rook");
      if (piece === 'q') descriptions.push("mobilizes queen");
      if (piece === 'k') descriptions.push("moves king");
    }
    
    return descriptions.join(", ") || "makes move";
  }

  async function generatePlayModeCommentary(userMove: string, userMoveDesc: string, engineResponse: any, userFenAfter: string) {
    try {
      // Analyze position after user's move to get accurate eval
      const userAnalysis = await analyzePosition(userFenAfter, 1, 12);
      
      const evalBefore = engineResponse.eval_cp_before || 0;
      const evalAfter = userAnalysis.eval_cp || engineResponse.eval_cp_after || 0;
      const evalChange = Math.abs(evalAfter - evalBefore);
      
      // Determine move quality based on centipawn loss
      let moveQuality = "the best move";
      if (evalChange === 0) moveQuality = "the best move";
      else if (evalChange < 30) moveQuality = "an excellent move";
      else if (evalChange < 50) moveQuality = "a good move";
      else if (evalChange < 80) moveQuality = "an inaccuracy";
      else if (evalChange < 200) moveQuality = "a mistake";
      else moveQuality = "a blunder";
      
      console.log(`💯 Move Quality: ${userMove} | CP Loss: ${evalChange}cp | ${moveQuality}`);
      
      // Get candidate moves from engine's position to understand purpose
      const engineAnalysis = await analyzePosition(engineResponse.new_fen, 3, 12);
      const engineCandidates = engineAnalysis.candidate_moves || [];
      const engineBestMove = engineCandidates[0];
      const engineThreats = engineAnalysis.threats || [];
      
      const prompt = `You're a chess coach commenting on moves.

USER MOVE: ${userMove}
QUALITY: ${moveQuality} (centipawn loss: ${evalChange})
EVAL: ${evalAfter}cp

ENGINE MOVE: ${engineResponse.engine_move_san}
ENGINE'S NEXT PLAN: ${engineBestMove ? engineBestMove.move : 'developing'}
ENGINE THREATS: ${engineThreats.length > 0 ? engineThreats[0].desc : 'none'}

Generate 2 sentences:
Sentence 1: ${userMove} is ${moveQuality}
Sentence 2: I played ${engineResponse.engine_move_san} to [purpose: defend/attack/develop/prepare/threaten/control center/improve position]

Determine the purpose from the engine's move and position. Be specific but concise.

IMPORTANT: Do NOT use quotation marks in your response. Write plain text only.

Examples:
- 1.e4 is the best move. I played 1...e5 to fight for the center and open lines.
- 2.Nf3 is an excellent move. I played 2...Nc6 to develop and prepare d5.
- 3.h4 is a mistake. I played 3...d5 to punish the weakening and seize the center.
- 4.Nxe5 is a good move. I played 4...d6 to attack the knight and regain material.`;

      const {content: commentary} = await callLLM([
        { role: "system", content: "You are a concise chess coach. Format: Sentence 1 judges user move. Sentence 2 explains engine's purpose. NEVER use quotation marks in your response." },
        { role: "user", content: prompt },
      ], 0.6);
      
      // Add meta with CP loss and best move for tooltip
      const commentaryMeta = {
        cpLoss: evalChange,
        bestMove: engineBestMove?.move || userMove,
        evalAfter: evalAfter,
        quality: moveQuality
      };
      
      addAssistantMessage(commentary, commentaryMeta);
      
      // Check for advantage shifts
      await checkAdvantageShift(evalBefore, evalAfter, engineAnalysis, "engine", engineResponse.new_fen);
      
    } catch (err: any) {
      console.error('Commentary generation error:', err);
      addAssistantMessage(
        `${userMove} is a good move. I played ${engineResponse.engine_move_san}.`
      );
    }
  }

  async function checkAdvantageShift(evalBefore: number, evalAfter: number, analysis: any, side: "user" | "engine", newFen?: string) {
    // Determine advantage thresholds
    // 1 pawn = 100cp
    const getAdvantageLevel = (cp: number) => {
      const absCp = Math.abs(cp);
      if (absCp < 50) return "equal";
      if (absCp < 100) return "slight"; // ~0.5 pawns
      if (absCp < 200) return "clear"; // 1-2 pawns
      return "strong"; // 2+ pawns
    };
    
    const beforeLevel = getAdvantageLevel(evalBefore);
    const afterLevel = getAdvantageLevel(evalAfter);
    
    // Determine who has advantage and create a combined key
    const whoHasAdvantage = evalAfter > 50 ? "White" : evalAfter < -50 ? "Black" : "Equal";
    const currentAdvantageKey = whoHasAdvantage === "Equal" ? "equal" : `${whoHasAdvantage}-${afterLevel}`;
    
    // Only comment if advantage key changed (prevents spam)
    if (currentAdvantageKey !== lastAdvantageLevel && afterLevel !== "equal") {
      setLastAdvantageLevel(currentAdvantageKey);
      
      const isPlayerWhite = fen.split(' ')[1] === 'b'; // After engine move, it's black's turn means player is white
      const isAdvantageForPlayer = (isPlayerWhite && whoHasAdvantage === "White") || 
                                    (!isPlayerWhite && whoHasAdvantage === "Black");
      
      const who = isAdvantageForPlayer ? "You" : "I";
      
      // Analyze why the advantage exists with sophisticated logic
      const materialBalance = analysis.material_balance || 0;
      const threats = analysis.threats || [];
      const candidates = analysis.candidate_moves || [];
      const absCp = Math.abs(evalAfter);
      
      let reason = "";
      let reasonType = "positional";
      
      // Check 1: Material Balance
      // If material explains most of the eval (material value ~= eval)
      const materialCp = Math.abs(materialBalance) * 100; // 1 pawn = 100cp
      if (materialCp >= absCp * 0.7) { // Material accounts for 70%+ of eval
        reasonType = "material";
        const materialDiff = Math.abs(materialBalance);
        reason = `my material advantage (up ${materialDiff} pawn${materialDiff > 1 ? 's' : ''})`;
      }
      // Check 2: Tactical Threats
      // Play our best move, skip opponent, then check what we can do next
      // This reveals real threats that opponent can't defend
      else if (candidates.length >= 1 && newFen) {
        try {
          // Create a temp game and play our best move
          const threatTest = new Chess(newFen);
          const bestMove = threatTest.move(candidates[0].move);
          
          if (bestMove) {
            // Skip opponent's turn by flipping the side to move
            const fenAfterBestMove = threatTest.fen();
            const parts = fenAfterBestMove.split(' ');
            // Flip side to move (w→b or b→w)
            parts[1] = parts[1] === 'w' ? 'b' : 'w';
            const fenSameSideAgain = parts.join(' ');
            
            // Analyze what we could do if we move twice
            const doubleMove = new Chess(fenSameSideAgain);
            const followUps = doubleMove.moves({ verbose: true });
            
            if (followUps.length > 0) {
              // Check if there's a winning/forcing continuation
              const hasCheckmate = followUps.some(m => m.san.includes('#'));
              const hasFork = followUps.some(m => m.captured);
              
              if (hasCheckmate) {
                reasonType = "threat";
                reason = `my unstoppable threat: ${candidates[0].move} (threatens mate)`;
              } else if (hasFork && candidates.length >= 2) {
                // Compare first candidate vs second in original position
                const bestEval = candidates[0].eval_cp || 0;
                const secondEval = candidates[1].eval_cp || 0;
                const gap = Math.abs(bestEval - secondEval);
                
                if (gap >= 50) {
                  reasonType = "threat";
                  reason = `my current threat: ${candidates[0].move}`;
                }
              }
            }
          }
        } catch (err) {
          // If threat analysis fails, fall through to positional
        }
      }
      
      // Check 3: Positional Advantage (default)
      if (reasonType === "positional") {
        // Analyze piece activity using the deepAnalysis we already have
        const deepAnalysis = analyzePositionStrengthsWeaknesses(analysis, newFen || fen);
        
        const myMobility = whoHasAdvantage === "White" ? deepAnalysis.whiteMobility : deepAnalysis.blackMobility;
        const oppMobility = whoHasAdvantage === "White" ? deepAnalysis.blackMobility : deepAnalysis.whiteMobility;
        const myActive = whoHasAdvantage === "White" ? deepAnalysis.whiteActive : deepAnalysis.blackActive;
        const myInactive = whoHasAdvantage === "White" ? deepAnalysis.whiteInactive : deepAnalysis.blackInactive;
        const oppInactive = whoHasAdvantage === "White" ? deepAnalysis.blackInactive : deepAnalysis.whiteInactive;
        
        const mobilityGap = myMobility - oppMobility;
        
        // Determine positional factors
        const factors = [];
        
        if (mobilityGap >= 10) {
          factors.push("superior piece mobility");
        }
        if (myActive.length >= 3 && myInactive.length === 0) {
          factors.push(`active pieces (${myActive.slice(0, 2).join(", ")})`);
        }
        if (oppInactive.length >= 2) {
          factors.push(`opponent's inactive ${oppInactive[0]}`);
        }
        if (threats.length > 0) {
          factors.push(`pressure (${threats[0].desc})`);
        }
        
        // Check for trapped/pinned pieces (extra feature)
        const phase = analysis.phase || "middlegame";
        if (phase === "opening" && myActive.length > oppInactive.length) {
          factors.push("better development");
        }
        
        if (factors.length > 0) {
          reason = `my ${factors.slice(0, 2).join(" and ")}`;
        } else {
          reason = "my better position and control";
        }
      }
      
      const advantageMessage = `${who} now ${who === "I" ? "have" : "have"} a ${afterLevel} advantage because of ${reason}`;
      
      // Use setTimeout to ensure this message appears after the move commentary
      setTimeout(() => {
        addSystemMessage(advantageMessage);
      }, 100);
    }
  }

  async function handleMove(from: string, to: string, promotion?: string) {
    if (waitingForEngine) return;

    try {
      // Create a new game from current FEN to ensure state sync
      const tempGame = new Chess(fen);
      const moveSan = tempGame.move({ from, to, promotion: promotion as any });
      
      if (!moveSan) {
        addSystemMessage("Illegal move!");
        return;
      }

      // Check if in retry mode (game review challenge)
      if (isRetryMode) {
        const wasCorrect = await checkRetryMove(moveSan.san);
        if (wasCorrect) {
          // Correct move found - update board
          setGame(tempGame);
          setFen(tempGame.fen());
          
          // Add to move tree
          const newTree = moveTree.clone();
          newTree.addMove(moveSan.san, tempGame.fen());
          setMoveTree(newTree);
          setPgn(newTree.toPGN());
        }
        // Wrong moves handled in checkRetryMove
        return;
      }

      // Store the FEN BEFORE the move for backend
      const fenBeforeMove = fen;
      
      // Update the main game object with the new position
      setGame(tempGame);
      const newFen = tempGame.fen();
      
      // Add move to tree
      const newTree = moveTree.clone();
      newTree.addMove(moveSan.san, newFen);
      setMoveTree(newTree);
      
      const newPgn = newTree.toPGN();
      
      setFen(newFen);
      setPgn(newPgn);
      
      // Auto-analyze the new position AND the move in background (don't await)
      autoAnalyzePositionAndMove(newFen, moveSan.san, fenBeforeMove).catch(err => console.error('Auto-analysis failed:', err));

      // Check if we should auto-enter PLAY mode and get engine response
      const shouldEnterPlayMode = mode !== "PLAY";
      
      // Only announce moves and get engine response if already in PLAY mode
      // or if user explicitly requested to play
      if (mode === "PLAY") {
        if (shouldEnterPlayMode) {
          setMode("PLAY");
        }
        // Describe the move for AI commentary
        const moveDescription = describeMoveType(moveSan, tempGame);
        
        // Get move number for display
        const moveNum = Math.floor(game.history().length / 2) + 1;
        const isWhiteMove = fen.split(' ')[1] === 'w';
        const userMoveMessage = isWhiteMove ? `I played ${moveNum}.${moveSan.san}` : `I played ${moveNum}...${moveSan.san}`;
        addUserMessage(userMoveMessage);
        
        setWaitingForEngine(true);
        
        try {
        const response = await playMove(fenBeforeMove, moveSan.san, 1600, 1500);
          
          if (response.legal && response.engine_move_san && response.new_fen) {
            // Apply engine move to a new game object
            const gameAfterEngine = new Chess(newFen);
            gameAfterEngine.move(response.engine_move_san);
            
            setGame(gameAfterEngine);
            setFen(response.new_fen);
            
            // Auto-analyze the new position AND engine's move (don't await)
            autoAnalyzePositionAndMove(response.new_fen, response.engine_move_san, newFen).catch(err => console.error('Auto-analysis failed:', err));
            
            // Add engine move to tree with comment
            const treeAfterEngine = newTree.clone();
            const evalComment = `eval ${response.eval_cp_after || 0}cp`;
            treeAfterEngine.addMove(response.engine_move_san, response.new_fen, evalComment);
            setMoveTree(treeAfterEngine);
            setPgn(treeAfterEngine.toPGN());
            
            // Add auto-annotation
            const newComment = {
              ply: gameAfterEngine.history().length,
              text: `${response.engine_move_san}: eval ${response.eval_cp_after || 0}cp`,
            };
            
            setAnnotations((prev) => ({
              ...prev,
              comments: [...prev.comments, newComment],
            }));

            // Generate AI commentary on user's move + engine response
            if (llmEnabled) {
              await generatePlayModeCommentary(moveSan.san, moveDescription, response, newFen);
            } else {
            addAssistantMessage(
                `${moveSan.san} is a good move. I played ${response.engine_move_san}.`
            );
            }
          } else if (!response.legal) {
            addSystemMessage(`Backend error: ${response.error || "Illegal move"}`);
          }
        } catch (err: any) {
          addSystemMessage(`Engine error: ${err.message}`);
        } finally {
          setWaitingForEngine(false);
        }
      }
    } catch (err: any) {
      console.error('Move error:', err);
      addSystemMessage(`Move error: ${err.message}`);
    }
  }

  function generateVisualAnnotations(analysisData: any): { arrows: any[], highlights: any[] } {
    // NEW: Tag-based annotation system
    // Import is done dynamically to avoid circular dependencies
    const { generateAnnotationsFromTags, generatePlanArrows } = require('@/lib/tagAnnotations');
    
    // Get current side's tags from CHUNK 1 (immediate position)
    const sideToMove = fen.split(' ')[1];
    const currentSide = sideToMove === 'w' ? 'white' : 'black';
    const analysis = sideToMove === 'w' ? 
      analysisData.white_analysis : 
      analysisData.black_analysis;
    
    const tags = analysis?.chunk_1_immediate?.tags || [];
    const planExplanation = analysis?.chunk_2_plan_delta?.plan_explanation || '';
    
    console.log(`🎨 Generating tag-based annotations for ${tags.length} tags`);
    
    // Generate annotations from tags
    const tagAnnotations = generateAnnotationsFromTags(tags, fen, sideToMove);
    
    // Generate plan-based arrows (example moves for plan actions)
    const planArrows = generatePlanArrows(planExplanation, new Chess(fen), sideToMove);
    
    console.log(`   → ${tagAnnotations.arrows.length} tag arrows + ${planArrows.length} plan arrows, ${tagAnnotations.highlights.length} highlights`);
    
    // Combine tag and plan annotations
    return {
      arrows: [...tagAnnotations.arrows, ...planArrows],
      highlights: tagAnnotations.highlights
    };
  }

  async function handleAnalyzePosition(questionType: string = "full_analysis", userQuestion: string = "") {
    // Show progress notifications
    addSystemMessage("Analyzing position with Stockfish...");
    
    try {
      const result = await analyzePosition(fen, 3, 18);
      
      addSystemMessage("Detecting chess themes and tags...");
      
      // Log theme-based analysis to console
      console.log("=== THEME-BASED ANALYSIS ===");
      console.log("White Analysis:", result.white_analysis);
      console.log("Black Analysis:", result.black_analysis);
      console.log("============================");
      
      addSystemMessage("Computing positional delta and plan classification...");
      
      // Clear annotations - let applyLLMAnnotations handle them based on what LLM mentions
      setAnnotations(prev => ({
        ...prev,
        arrows: [],
        highlights: [],
        comments: [
          ...prev.comments,
          {
            ply: game.history().length,
            text: `Analysis: ${result.eval_cp > 0 ? '+' : ''}${(result.eval_cp / 100).toFixed(2)}`
          }
        ]
      }));
      
      addSystemMessage("✅ Analysis complete!");
      
      // Generate LLM response using theme-based data
      if (llmEnabled) {
        // If user asked a specific question, answer it; otherwise do full analysis
        await generateConciseLLMResponse(userQuestion, result, questionType);
      } else {
        // If LLM disabled, show summary using chunk structure
        const sideToMove = fen.split(' ')[1] === 'w' ? 'White' : 'Black';
        const currentSide = sideToMove === 'White' ? result.white_analysis : result.black_analysis;
        const immediate = currentSide.chunk_1_immediate || {};
        const planData = currentSide.chunk_2_plan_delta || {};
        
        addSystemMessage(`IMMEDIATE POSITION:\nMaterial: ${immediate.material_balance_cp}cp, Positional: ${immediate.positional_cp_significance}cp`);
        addSystemMessage(`PLAN: ${planData.plan_type}\n${planData.plan_explanation}`);
      }
      
      // Annotations will be applied by applyLLMAnnotations based on LLM response
    } catch (err: any) {
      addSystemMessage(`❌ Analysis error: ${err.message}`);
      console.error("Analysis error details:", err);
    }
  }

  async function handleAnalyzeLastMove() {
    // Get move history from move tree (more reliable than game.history)
    const mainLine = moveTree.getMainLine();
    if (mainLine.length === 0) {
      addSystemMessage("⚠️ No moves played yet");
      return;
    }
    
    const lastMoveNode = mainLine[mainLine.length - 1];
    const lastMoveSan = lastMoveNode.move;  // SAN notation
    
    // Get FEN before last move (parent's FEN, or initial if no parent)
    let fenBeforeLastMove;
    if (lastMoveNode.parent) {
      fenBeforeLastMove = lastMoveNode.parent.fen;
    } else if (mainLine.length >= 2) {
      // If no parent but multiple moves, use second-to-last move's FEN
      fenBeforeLastMove = mainLine[mainLine.length - 2].fen;
    } else {
      // First move - use initial position
      fenBeforeLastMove = INITIAL_FEN;
    }
    
    console.log(`Analyzing last move: ${lastMoveSan} from position:`, fenBeforeLastMove);
    console.log(`Move tree has ${mainLine.length} moves`);
    addSystemMessage(`Analyzing move: ${lastMoveSan}...`);
    
    try {
      const response = await fetch(
        `http://localhost:8000/analyze_move?fen=${encodeURIComponent(fenBeforeLastMove)}&move_san=${encodeURIComponent(lastMoveSan)}&depth=18`,
        {method: "POST"}
      );
      
      if (!response.ok) {
        const errorText = await response.text();
        console.error("Analyze move error response:", errorText);
        throw new Error(`Failed to analyze move: ${response.status}`);
      }
      
      const data = await response.json();
      
      // Generate LLM response using move analysis template
      await generateMoveAnalysisResponse(data);
      
    } catch (error: any) {
      addSystemMessage(`❌ Error analyzing move: ${error.message}`);
      console.error("Move analysis error:", error);
    }
  }
  
  async function generateMoveAnalysisResponse(moveData: any) {
    try {
      // Use side_to_move from backend response (side that made the move being analyzed)
      const sideKey = moveData.side_to_move || 'white';  // lowercase: 'white' or 'black'
      const sidePlayed = sideKey === 'white' ? 'White' : 'Black';  // Capitalized for display
      console.log(`Analyzing move from ${sidePlayed}'s perspective (key: ${sideKey})`);
      
      if (moveData.case === "best_move") {
      // BEST MOVE TEMPLATE
      const comparison1 = generateTagComparison(moveData.analysis.af_starting, moveData.analysis.af_best, sideKey);
      const comparison2 = generateTagComparison(moveData.analysis.af_best, moveData.analysis.af_pv_best, sideKey);
      
      const llmPrompt = `You are analyzing a chess move that was the BEST move. Write in natural, flowing English.

MOVE QUALITY:
Side: ${sidePlayed}
Move: ${moveData.move_played}
Status: BEST MOVE ✓
Eval Before: ${moveData.eval_before}cp
Eval After: ${moveData.eval_after_move}cp

WHAT THE MOVE DID (immediate):
${comparison1}

HOW IT HELPS LONG-TERM:
${comparison2}

INSTRUCTIONS:
1. First sentence: "${moveData.move_played} was the best move"
2. Second sentence: Weave the immediate accomplishments into natural English
3. Third sentence: Explain long-run benefits
Total: 3 sentences, flowing and concise

EXAMPLE TEMPLATE (use this style):
"Nf3 was the best move (eval: +35cp). This developed the knight and opened the long diagonal for the bishop, strengthening center control. In the long run, it improves king safety after castling and maintains piece coordination."

NOT THIS (too technical):
"Nf3 was the best move. Gained tag.diagonal.long and tag.activity.mobility.knight. Theme changes: S_CENTER +2."

USE the talking points above but write them as flowing chess commentary, not a list of tags.`;

      const {content: response} = await callLLM([
        {role: "system", content: "You are a chess commentator analyzing moves. Use the provided tag descriptions (already in natural English) to write flowing commentary. Weave them into sentences, don't list them. Sound like a human expert, not a technical report."},
        {role: "user", content: llmPrompt}
      ], 0.5);
      
      addAssistantMessage(response, {rawEngineData: moveData, mode: "ANALYZE"});
      
    } else {
      // NOT BEST MOVE TEMPLATE
      const cpLossSeverity = moveData.cp_loss < 30 ? "inaccuracy" : 
                            moveData.cp_loss < 100 ? "mistake" :
                            moveData.cp_loss < 300 ? "blunder" : "serious blunder";
      
      const comparison1 = generateTagComparison(moveData.analysis.af_starting, moveData.analysis.af_played, sideKey);
      const comparison2 = generateTagComparison(moveData.analysis.af_played, moveData.analysis.af_best, sideKey);
      const comparison3 = generateTagComparison(moveData.analysis.af_pv_played, moveData.analysis.af_pv_best, sideKey);
      
      const llmPrompt = `You are analyzing a move that was NOT the best. Write in natural, flowing English.

MOVE QUALITY:
Side: ${sidePlayed}
Move Played: ${moveData.move_played}
Best Move: ${moveData.best_move}
CP Loss: ${moveData.cp_loss}cp (${cpLossSeverity})

WHAT ${moveData.move_played} DID:
${comparison1}

WHAT ${moveData.best_move} DOES BETTER:
${comparison2}

LONG-RUN COMPARISON:
${comparison3}

INSTRUCTIONS:
1. "${moveData.move_played} was ${['an', 'a'].includes(cpLossSeverity[0].toLowerCase()) ? 'an' : 'a'} ${cpLossSeverity} (${moveData.cp_loss}cp loss)"
2. What ${moveData.move_played} accomplished (weave comparison 1 naturally)
3. Why ${moveData.best_move} is better (weave comparison 2 naturally)
4. Long-term impact (weave comparison 3 naturally)
Total: 4 sentences, flowing commentary

EXAMPLE TEMPLATE (use this style):
"d3 was a mistake (45cp loss). This move opened the long diagonal for the bishop but failed to control the key central squares. In contrast, d4 would have controlled the center immediately and gained the key d4 square. Over the long run, d3 loses central control and piece activity, while d4 maintains pressure and better piece coordination."

NOT THIS (too list-like):
"d3 was a mistake. Gained: tag.diagonal.long.a1h8, tag.center.control.near. Best move gains: tag.center.control.core. Long-run: S_CENTER -2.0, S_ACTIVITY -1.3."

WEAVE the talking points into natural sentences. Make it sound like a chess commentator, not a technical report.`;

      const {content: response} = await callLLM([
        {role: "system", content: "You are a chess commentator analyzing moves. Use the provided tag descriptions (already in natural English) to write flowing commentary. Weave them into sentences like a human expert. Avoid list-like or technical phrasing."},
        {role: "user", content: llmPrompt}
      ], 0.5);
      
      addAssistantMessage(response, {rawEngineData: moveData, mode: "ANALYZE"});
    }
    } catch (error: any) {
      console.error("Error in generateMoveAnalysisResponse:", error);
      addSystemMessage(`❌ Error generating move analysis: ${error.message}`);
    }
  }
  
  function generateTagComparison(afBefore: any, afAfter: any, side: string): string {
    // Simple frontend implementation - extract tag/theme changes
    if (!afBefore || !afAfter) {
      return "Minor positional adjustments";
    }
    
    try {
      const tagsBefore = new Set((afBefore.tags || []).map((t: any) => t.tag_name));
      const tagsAfter = new Set((afAfter.tags || []).map((t: any) => t.tag_name));
      
      const gained = Array.from(tagsAfter).filter(t => !tagsBefore.has(t));
      const lost = Array.from(tagsBefore).filter(t => !tagsAfter.has(t));
      
      // Access theme_scores for the specified side
      const sideKey = side.toLowerCase();
      const themesBefore = afBefore.theme_scores?.[sideKey] || {};
      const themesAfter = afAfter.theme_scores?.[sideKey] || {};
      
      let changes = [];
      for (const [key, afterVal] of Object.entries(themesAfter)) {
        if (key !== 'total') {
          const beforeVal = (themesBefore as any)[key] || 0;
          const delta = (afterVal as number) - beforeVal;
          if (Math.abs(delta) > 0.5) {
            changes.push(`${key}: ${delta > 0 ? '+' : ''}${delta.toFixed(1)}`);
          }
        }
      }
      
      let summary = "";
      if (gained.length > 0) summary += `Gained tags: ${gained.slice(0, 3).join(', ')}. `;
      if (lost.length > 0) summary += `Lost tags: ${lost.slice(0, 3).join(', ')}. `;
      if (changes.length > 0) summary += `Theme changes: ${changes.slice(0, 3).join(', ')}`;
      
      return summary || "Minor positional adjustments";
    } catch (error) {
      console.error("Error in generateTagComparison:", error);
      return "Minor positional adjustments";
    }
  }
  
  async function handleNextTactic() {
    try {
      const tactic = await tacticsNext();
      setCurrentTactic(tactic);
      setTacticAttempts([]);
      
      setFen(tactic.fen);
      setBoardOrientation(tactic.side_to_move === "w" ? "white" : "black");
      
      const tacticGame = new Chess(tactic.fen);
      setGame(tacticGame);
      setPgn(tacticGame.pgn());
      
      addSystemMessage(
        `📝 TACTIC #${tactic.id} (Rating: ${tactic.rating})\n\n${tactic.prompt}\n\nThemes: ${tactic.themes.join(", ")}\n\nFind the best move!`
      );
    } catch (err: any) {
      addSystemMessage(`Tactic error: ${err.message}`);
    }
  }

  async function handleRevealTactic() {
    if (!currentTactic) return;
    
    addSystemMessage(
      `💡 SOLUTION:\n\n${currentTactic.solution_pv_san}\n\nAttempts: ${tacticAttempts.length}`
    );
  }

  function analyzePositionStrengthsWeaknesses(analysisData: any, currentFen: string): any {
    const board = new Chess(currentFen);
    const pieceMap = board.board();
    const evalCp = analysisData.eval_cp || 0;
    
    // Analyze piece activity
    const whitePieces: any[] = [];
    const blackPieces: any[] = [];
    
    pieceMap.forEach((row, rankIdx) => {
      row.forEach((square, fileIdx) => {
        if (square) {
          const squareName = String.fromCharCode(97 + fileIdx) + (8 - rankIdx);
          const piece = {
            type: square.type,
            color: square.color,
            square: squareName,
            mobility: 0
          };
          
          // Calculate mobility
          const moves = board.moves({ square: squareName as any, verbose: true });
          piece.mobility = moves.length;
          
          if (square.color === 'w') {
            whitePieces.push(piece);
          } else {
            blackPieces.push(piece);
          }
        }
      });
    });
    
    // Find most active pieces
    const whiteActive = whitePieces.filter(p => p.mobility > 3).map(p => `${p.type.toUpperCase()}${p.square}`);
    const blackActive = blackPieces.filter(p => p.mobility > 3).map(p => `${p.type}${p.square}`);
    
    // Find inactive pieces (low mobility)
    const whiteInactive = whitePieces.filter(p => p.mobility === 0).map(p => `${p.type.toUpperCase()}${p.square}`);
    const blackInactive = blackPieces.filter(p => p.mobility === 0).map(p => `${p.type}${p.square}`);
    
    // Analyze pawn structure
    const whitePawns = whitePieces.filter(p => p.type === 'p');
    const blackPawns = blackPieces.filter(p => p.type === 'p');
    
    // Check for doubled pawns, isolated pawns
    const pawnStructure = {
      whiteDoubled: 0,
      blackDoubled: 0,
      whiteIsolated: 0,
      blackIsolated: 0
    };
    
    // Simple doubled pawn check
    const whiteFiles = whitePawns.map(p => p.square[0]);
    const blackFiles = blackPawns.map(p => p.square[0]);
    pawnStructure.whiteDoubled = whiteFiles.length - new Set(whiteFiles).size;
    pawnStructure.blackDoubled = blackFiles.length - new Set(blackFiles).size;
    
    return {
      evaluation: evalCp,
      whiteMobility: whitePieces.reduce((sum, p) => sum + p.mobility, 0),
      blackMobility: blackPieces.reduce((sum, p) => sum + p.mobility, 0),
      whiteActive,
      blackActive,
      whiteInactive,
      blackInactive,
      pawnStructure,
      threats: analysisData.threats || [],
      pieceQuality: analysisData.piece_quality || {},
    };
  }

  function generateChessGPTStructuredResponse(analysisData: any): string {
    // Generate the structured Chess GPT response format
    const evalCp = analysisData.eval_cp || 0;
    const verdict = evalCp > 150 ? "+/- (White is better)" :
                    evalCp > 50 ? "+/= (White is slightly better)" :
                    evalCp < -150 ? "-/+ (Black is better)" :
                    evalCp < -50 ? "=/+ (Black is slightly better)" :
                    "= (Equal position)";

    const themes = analysisData.themes && analysisData.themes.length > 0 
      ? analysisData.themes.slice(0, 3)
      : ["Opening development", "Center control", "Pawn structure"];

    const candidates = analysisData.candidate_moves || [];
    const candidateText = candidates.slice(0, 3).map((c: any, i: number) => 
      `${i + 1}. ${c.move} - ${getCandidateDescription(c)}`
    ).join("\n");

    const firstMove = candidates[0];
    const criticalLine = firstMove ? `${firstMove.pv_san || ""}` : "No line available";
    
    // Enhanced analysis
    const deepAnalysis = analyzePositionStrengthsWeaknesses(analysisData, fen);
    
    const strengths = [];
    const weaknesses = [];
    
    // Analyze for side to move
    const sideToMove = fen.split(' ')[1] === 'w' ? 'White' : 'Black';
    const oppSide = sideToMove === 'White' ? 'Black' : 'White';
    
    if (sideToMove === 'White') {
      if (deepAnalysis.whiteMobility > deepAnalysis.blackMobility * 1.2) {
        strengths.push("Superior piece mobility");
      }
      if (deepAnalysis.whiteActive.length > deepAnalysis.blackActive.length) {
        strengths.push(`Active pieces: ${deepAnalysis.whiteActive.slice(0, 3).join(', ')}`);
      }
      if (deepAnalysis.whiteInactive.length > 0) {
        weaknesses.push(`Inactive pieces: ${deepAnalysis.whiteInactive.slice(0, 2).join(', ')}`);
      }
      if (deepAnalysis.pawnStructure.whiteDoubled > 0) {
        weaknesses.push(`Doubled pawns (${deepAnalysis.pawnStructure.whiteDoubled})`);
      }
    } else {
      if (deepAnalysis.blackMobility > deepAnalysis.whiteMobility * 1.2) {
        strengths.push("Superior piece mobility");
      }
      if (deepAnalysis.blackActive.length > deepAnalysis.whiteActive.length) {
        strengths.push(`Active pieces: ${deepAnalysis.blackActive.slice(0, 3).join(', ')}`);
      }
      if (deepAnalysis.blackInactive.length > 0) {
        weaknesses.push(`Inactive pieces: ${deepAnalysis.blackInactive.slice(0, 2).join(', ')}`);
      }
      if (deepAnalysis.pawnStructure.blackDoubled > 0) {
        weaknesses.push(`Doubled pawns (${deepAnalysis.pawnStructure.blackDoubled})`);
      }
    }
    
    // Threats section
    const threatsText = deepAnalysis.threats.length > 0 
      ? deepAnalysis.threats.map((t: any) => `• ${t.desc}`).join('\n')
      : "No immediate threats";

    const structuredResponse = `Verdict: ${verdict}

Key Themes:
${themes.map((t: string, i: number) => `${i + 1}. ${t}`).join("\n")}

Strengths:
${strengths.length > 0 ? strengths.map((s, i) => `${i + 1}. ${s}`).join('\n') : "• Balanced position"}

Weaknesses:
${weaknesses.length > 0 ? weaknesses.map((w, i) => `${i + 1}. ${w}`).join('\n') : "• No significant weaknesses"}

Threats:
${threatsText}

Candidate Moves:
${candidateText || "No candidates available"}

Critical Line${firstMove ? ` (${firstMove.move})` : ""}:
${formatPVLine(criticalLine)}

Plan: ${generatePlan(analysisData, strengths, weaknesses)}

One Thing to Avoid: ${generateAvoidance(weaknesses, analysisData)}`;

    return structuredResponse;
  }
  
  function generatePlan(analysisData: any, strengths: string[], weaknesses: string[]): string {
    const phase = analysisData.phase || "middlegame";
    const evalCp = analysisData.eval_cp || 0;
    
    if (phase === "opening") {
      return "Complete development, castle for king safety, and fight for central control.";
    } else if (phase === "endgame") {
      return "Activate the king, create passed pawns, and improve piece coordination.";
    } else {
      if (weaknesses.some(w => w.includes("Inactive"))) {
        return "Activate inactive pieces and improve piece coordination before launching an attack.";
      }
      if (strengths.some(s => s.includes("mobility"))) {
        return "Exploit superior mobility with tactical opportunities and control key squares.";
      }
      return "Improve piece positioning, control key squares, and look for tactical opportunities.";
    }
  }
  
  function generateAvoidance(weaknesses: string[], analysisData: any): string {
    if (weaknesses.some(w => w.includes("Inactive"))) {
      return "Avoid leaving pieces undeveloped or trapped on poor squares.";
    }
    if (weaknesses.some(w => w.includes("Doubled pawns"))) {
      return "Avoid further pawn weaknesses and be careful with pawn trades.";
    }
    const phase = analysisData.phase || "middlegame";
    if (phase === "opening") {
      return "Avoid moving the same piece multiple times unless necessary.";
    }
    return "Avoid creating new weaknesses and maintain piece coordination.";
  }

  function getCandidateDescription(candidate: any): string {
    const move = candidate.move;
    // Simple heuristics for move descriptions
    if (move.includes("e4") || move.includes("d4")) {
      return "Establishes central control and opens lines for development.";
    } else if (move.includes("Nf") || move.includes("Nc")) {
      return "Develops a knight and prepares for castling.";
    } else if (move.includes("Bc") || move.includes("Bf")) {
      return "Develops the bishop to an active square.";
    } else if (move.includes("O-O")) {
      return "Castles to safety while connecting the rooks.";
    }
    return `Eval: ${(candidate.eval_cp / 100).toFixed(2)}`;
  }

  function formatPVLine(pv: string): string {
    // Format the principal variation into numbered moves
    const moves = pv.split(" ");
    let formatted = "";
    for (let i = 0; i < Math.min(6, moves.length); i += 2) {
      const moveNum = Math.floor(i / 2) + 1;
      formatted += `${moveNum}. ${moves[i]} ${moves[i + 1] || ""}\n`;
    }
    return formatted.trim() || "No critical line available";
  }

  function formatAnalysisCard(analysisData: any): string {
    if (!analysisData) return "No analysis available";
    
    const evalCp = analysisData.eval_cp || 0;
    const evalPawns = (evalCp / 100).toFixed(2);
    const verdict = evalCp > 100 ? "+- (White is winning)" :
                    evalCp > 50 ? "+/= (White is slightly better)" :
                    evalCp > -50 ? "= (Equal position)" :
                    evalCp > -100 ? "=/+ (Black is slightly better)" :
                    "-+ (Black is winning)";
    
    const candidates = analysisData.candidate_moves || [];
    const themes = analysisData.themes || [];
    const threats = analysisData.threats || [];
    const pieceQuality = analysisData.piece_quality || {};
    
    let card = `Verdict: ${verdict}\n`;
    card += `Eval: ${evalCp > 0 ? '+' : ''}${evalPawns}\n\n`;
    
    if (themes.length > 0) {
      card += `Key Themes:\n${themes.slice(0, 3).map((t: string, i: number) => `${i + 1}. ${t}`).join("\n")}\n\n`;
    }
    
    // Add Strengths (Active Pieces)
    const whitePieces = pieceQuality.W || {};
    const blackPieces = pieceQuality.B || {};
    const whiteActive = Object.entries(whitePieces).filter(([_, q]) => (q as number) >= 0.6).map(([p, _]) => p);
    const blackActive = Object.entries(blackPieces).filter(([_, q]) => (q as number) >= 0.6).map(([p, _]) => p);
    
    if (whiteActive.length > 0 || blackActive.length > 0) {
      card += `Strengths:\n`;
      if (whiteActive.length > 0) {
        card += `  White: ${whiteActive.join(", ")}\n`;
      }
      if (blackActive.length > 0) {
        card += `  Black: ${blackActive.join(", ")}\n`;
      }
      card += `\n`;
    }
    
    // Add Weaknesses (Inactive Pieces)
    const whiteInactive = Object.entries(whitePieces).filter(([_, q]) => (q as number) <= 0.3).map(([p, _]) => p);
    const blackInactive = Object.entries(blackPieces).filter(([_, q]) => (q as number) <= 0.3).map(([p, _]) => p);
    
    if (whiteInactive.length > 0 || blackInactive.length > 0) {
      card += `Weaknesses:\n`;
      if (whiteInactive.length > 0) {
        card += `  White: ${whiteInactive.join(", ")}\n`;
      }
      if (blackInactive.length > 0) {
        card += `  Black: ${blackInactive.join(", ")}\n`;
      }
      card += `\n`;
    }
    
    if (candidates.length > 0) {
      card += `Candidate Moves:\n`;
      candidates.slice(0, 3).forEach((c: any, i: number) => {
        const evalStr = c.eval_cp !== undefined ? `Eval: ${(c.eval_cp / 100).toFixed(2)}` : '';
        card += `${i + 1}. ${c.move} - ${evalStr}\n`;
      });
      card += `\n`;
    }
    
    if (threats.length > 0) {
      card += `Threats:\n`;
      threats.slice(0, 3).forEach((t: any) => {
        card += `• ${t.desc} (${t.delta_cp > 0 ? '+' : ''}${t.delta_cp}cp)\n`;
      });
    }
    
    return card.trim();
  }

  async function generateConciseLLMResponse(userQuestion: string, engineData: any, questionType: string = "full_analysis") {
    try {
      const evalCp = engineData.eval_cp || 0;
      const evalPawns = evalCp / 100;  // Keep as number for comparisons
      const evalPawnsDisplay = evalPawns.toFixed(2);  // String for display
      const phase = engineData.phase || "opening";
      const sideToMove = fen.split(' ')[1] === 'w' ? 'White' : 'Black';
      
      // Extract theme-based analysis using new chunk structure
      const whiteAnalysis = engineData.white_analysis || {};
      const blackAnalysis = engineData.black_analysis || {};
      const currentSideAnalysis = sideToMove === 'White' ? whiteAnalysis : blackAnalysis;
      
      // CHUNK 1: Immediate position (what IS)
      const currentRawData = currentSideAnalysis.chunk_1_immediate || {};
      const themeScores = currentRawData.theme_scores || {};
      const tags = currentRawData.tags || [];
      const positionalCp = currentRawData.positional_cp_significance || 0;
      const materialCp = currentRawData.material_balance_cp || 0;
      
      // CHUNK 2: Plan/Delta (how it should unfold)
      const plan = currentSideAnalysis.chunk_2_plan_delta || {};
      const planType = plan.plan_type || "balanced";
      const planExplanation = plan.plan_explanation || "";
      const themeChanges = plan.theme_changes || {};

      // Determine prompt based on question type or user question
      let llmPrompt = "";
      let maxTokens = 200;
      
      // If user asked a specific question, answer it directly
      if (userQuestion && questionType === "answer_question") {
        llmPrompt = `USER ASKED: "${userQuestion}"

RAW ANALYSIS DATA:
Evaluation: ${evalPawns > 0 ? '+' : ''}${evalPawnsDisplay} pawns (${evalCp}cp)
Material balance: ${materialCp}cp
Positional value: ${positionalCp}cp
Turn to move: ${sideToMove}
Phase: ${phase}

${engineData.move_analysis ? `LAST MOVE PLAYED: ${engineData.move_analysis.move_san || 'N/A'}
${engineData.move_analysis.is_theory ? `📚 OPENING THEORY: ${engineData.move_analysis.opening_name || 'Known opening'}` : ''}
Move Quality: ${engineData.move_analysis.move_category || 'N/A'}${!engineData.move_analysis.is_theory ? ` (${engineData.move_analysis.cp_loss || 0}cp loss)` : ''}
Best alternative: ${engineData.move_analysis.best_move_san || 'N/A'}
Eval before: ${((engineData.move_analysis.eval_before_cp || 0) / 100).toFixed(2)} pawns → Eval after: ${((engineData.move_analysis.eval_after_cp || 0) / 100).toFixed(2)} pawns
${engineData.move_analysis.second_best_gap_cp >= 50 && !engineData.move_analysis.is_theory ? `⚠️ Critical position: Only ${engineData.move_analysis.best_move_san} keeps advantage (50+cp gap to 2nd best)` : ''}

` : ''}CANDIDATE MOVES (What to consider now):
${(() => {
  const candidates = engineData.candidate_moves || [];
  if (candidates.length === 0) return 'No candidates available';
  
  const best = candidates[0];
  const bestEval = best.eval_cp;
  const secondBest = candidates[1];
  const secondBestGap = secondBest ? Math.abs(bestEval - secondBest.eval_cp) : 0;
  
  return candidates.slice(0, 3).map((c: any, i: number) => {
    const cpLoss = Math.abs(c.eval_cp - bestEval);
    let quality = '';
    
    // Use same rules as game review
    if (cpLoss === 0 && secondBestGap >= 50) {
      quality = '⚡ CRITICAL BEST (only good move!)';
    } else if (cpLoss === 0) {
      quality = '✓ BEST';
    } else if (cpLoss < 20) {
      quality = '✓ Excellent';
    } else if (cpLoss < 50) {
      quality = '✓ Good';
    } else if (cpLoss < 80) {
      quality = '!? Inaccuracy';
    } else if (cpLoss < 200) {
      quality = '? Mistake';
    } else {
      quality = '?? Blunder';
    }
    
    const evalPawns = (c.eval_cp / 100).toFixed(2);
    return `${i + 1}. ${c.move} (${evalPawns} pawns) ${quality}`;
  }).join('\\n');
})()}

Top themes: ${Object.entries(themeScores)
  .filter(([k, v]) => k !== 'total' && Math.abs(v as number) > 0.01)
  .sort((a, b) => Math.abs((b[1] as number)) - Math.abs((a[1] as number)))
  .slice(0, 5)
  .map(([theme, score]) => `${theme}: ${(score as number).toFixed(1)}`)
  .join(", ")}

Key tags: ${tags.slice(0, 15).map((t: any) => {
  const name = t.tag_name?.replace('tag.', '') || '';
  // Add threat details if present
  if (t.tag_name?.includes('threat')) {
    const details = [];
    if (t.attacker && t.victim) details.push(`${t.attacker}→${t.victim}`);
    if (t.target_piece) details.push(`attacking ${t.target_piece}`);
    if (t.from_square && t.to_square) details.push(`${t.from_square}-${t.to_square}`);
    return details.length > 0 ? `${name} (${details.join(', ')})` : name;
  }
  return name;
}).filter((t: any) => t).join(", ")}

PLAN: ${planExplanation}

INSTRUCTIONS:
${engineData.move_analysis?.is_theory ? `
⚠️ CRITICAL: This move is OPENING THEORY (${engineData.move_analysis.opening_name})
YOU MUST say "This is opening theory from the ${engineData.move_analysis.opening_name}" in your FIRST sentence.
DO NOT say "excellent" or "good" - say it's THEORY!
` : ''}
1. Answer their question DIRECTLY in the first sentence
2. Express ALL evaluations in PAWNS (e.g., "+0.24 pawns" NEVER "+24" or "+24cp")
3. When mentioning moves, be specific: "Bc4 develops the bishop to c4, targeting f7"
4. When mentioning themes, be specific: "controls d4 and e5" not just "central control"
5. Keep it concise - max 3 sentences total`;
        
        maxTokens = 150;
      } else {
        // Format top themes (only non-zero)
      const topThemes = Object.entries(themeScores)
        .filter(([k, v]) => k !== 'total' && Math.abs(v as number) > 0.01)
        .sort((a, b) => Math.abs((b[1] as number)) - Math.abs((a[1] as number)))
        .slice(0, 5)
        .map(([theme, score]) => `${theme}: ${(score as number).toFixed(1)}`)
        .join(", ");
      
      const keyTags = tags
        .slice(0, 10)
        .map((t: any) => t.tag_name)
        .join(", ");
      
      if (questionType === "what_should_i_do" || questionType === "how_to_proceed" || questionType === "help_with_move") {
        // CONCISE FORMAT for "what should I do?" type questions
        maxTokens = 80;
        
        llmPrompt = `Eval: ${evalCp}cp. Top themes: ${topThemes || "balanced"}. Plan: ${planExplanation || planType}.

In 1-2 sentences: What should ${sideToMove} do and why?`;

      } else if (questionType === "best_move") {
        // CONCISE FORMAT for "best move?" questions
        maxTokens = 50;
        
        llmPrompt = `Eval: ${evalCp}cp. Plan: ${planExplanation || planType}.

In one sentence: What move(s) should ${sideToMove} play?`;

      } else if (questionType === "show_candidates" || questionType === "show_options") {
        // CONCISE FORMAT for "show me options" questions  
        maxTokens = 60;
        
        llmPrompt = `Eval: ${evalCp}cp. Plan: ${planExplanation || planType}.

List 2-3 candidate moves for ${sideToMove} in one sentence.`;

      } else {
        // FULL ANALYSIS FORMAT for "analyze" commands
        maxTokens = 150;
        
        const absEval = Math.abs(evalCp);
        const advantageLevel = absEval < 20 ? 'roughly equal' : 
                              absEval < 50 ? 'slight advantage' :
                              absEval < 100 ? 'clear advantage' : 'winning';
        
        llmPrompt = `Eval: ${evalCp}cp (${advantageLevel}). Material: ${materialCp}cp. Top themes: ${topThemes || "balanced"}.
Plan: ${planExplanation || planType}.

In 2-3 sentences: Explain the position and what ${sideToMove} should do.`;
      }
      } // Close outer else block

      // Get recent chat context (last 3 messages)
      const chatContext = getRecentChatContext(3);
      
      const {content: conciseResponse} = await callLLM([
        { 
          role: "system", 
          content: `You are a friendly chess coach with deep analytical skills. 

CRITICAL: Always reference SPECIFIC data from the analysis to support your answers:
- Quote EXACT evaluations in PAWNS (e.g., "+0.38 pawns" NOT "+38cp" or "+38")
- If move is 📚 THEORY, say so and mention the opening name
- Cite SPECIFIC themes with their scores (e.g., "central_space: -1.2")
- Mention CONCRETE tags (e.g., "semi-open e-file", "knight attacking queen on c3→d5")
- Reference the BEST MOVE and alternatives (e.g., "Best is Nf3, also consider d4")
- Use MATERIAL BALANCE and POSITIONAL VALUE to explain the eval
- Cite the PLAN when explaining what to do next

Answer style:
1. Start by DIRECTLY answering their question (e.g., "White is winning")
2. If it's a theory move, say "This is opening theory (Italian Game)" or similar
3. Support with 2-3 SPECIFIC data points from the analysis
4. Express ALL evals in pawns, never centipawns
5. Be conversational but DATA-DRIVEN
6. Max 3 sentences total` 
        },
        ...chatContext,
        { role: "user", content: llmPrompt },
      ], 0.5);
      
      // Store theme-based raw data in meta for button
      const meta = {
        rawEngineData: engineData,
        mode: "ANALYZE",
        fen: fen
      };
      
      addAssistantMessage(conciseResponse, meta);
      
      // Annotations now applied automatically via addAssistantMessage
      
    } catch (err: any) {
      addSystemMessage(`LLM error: ${err.message}`);
      console.error("LLM error details:", err);
    }
  }
  
  // DEBUG: Manual test function
  function testAnnotations() {
    console.log('🧪 Testing manual annotations...');
    setAnnotations(prev => ({
      ...prev,
      arrows: [
        { from: 'e2', to: 'e4', color: 'rgba(76, 175, 80, 0.9)' },
        { from: 'd2', to: 'd4', color: 'rgba(76, 175, 80, 0.7)' }
      ],
      highlights: [
        { sq: 'e4', color: 'rgba(76, 175, 80, 0.6)' },
        { sq: 'd4', color: 'rgba(76, 175, 80, 0.6)' }
      ]
    }));
    addSystemMessage('🧪 Test annotations applied: 2 arrows, 2 highlights');
  }
  
  // Expose for console testing
  (window as any).testAnnotations = testAnnotations;

  function applyLLMAnnotations(llmText: string, engineData: any) {
    try {
      console.log('🎨 Starting annotation generation...');
      console.log('   LLM text:', llmText.substring(0, 100) + '...');
      console.log('   Has engine data:', !!engineData);
      console.log('   Current FEN:', fen);
      
      const { parseLLMResponse, generateMoveArrows } = require('@/lib/llmAnnotations');
      const { generateThemeAnnotations } = require('@/lib/themeAnnotations');
      
      // Parse LLM response for moves and themes/tags
      const parsed = parseLLMResponse(llmText, engineData, fen);
      
      console.log('🎨 LLM referenced:', {
        moves: parsed.moves,
        themes: parsed.themes,
        tags: parsed.tags
      });
      
      // PRIORITY 1: Specific squares/pieces mentioned in text (most relevant!)
      const specificHighlights = parsed.highlights || [];
      const specificArrows = parsed.arrows || [];
      console.log('   Specific mentions:', { arrows: specificArrows.length, highlights: specificHighlights.length });
      
      // PRIORITY 2: Move arrows (suggested moves cross-referenced with candidates)
      const candidates = engineData.candidate_moves || [];
      const moveArrows = generateMoveArrows(parsed.moves, fen, candidates);
      console.log('   Move arrows generated:', moveArrows.length);
      
      // PRIORITY 3: Theme/tag annotations (only if mentioned and not too cluttered)
      const sideToMove = fen.split(' ')[1] === 'w' ? 'white' : 'black';
      const sideAnalysis = sideToMove === 'white' ? 
        engineData.white_analysis : 
        engineData.black_analysis;
      const tags = sideAnalysis?.chunk_1_immediate?.tags || [];
      
      console.log('   Themes mentioned:', parsed.themes);
      console.log('   Tags matched:', parsed.tags.length);
      
      // Only add theme annotations if we don't have too many specific ones already
      let themeAnnotations = { arrows: [] as any[], highlights: [] as any[] };
      if (specificHighlights.length < 3) {  // Leave room for theme annotations
        themeAnnotations = generateThemeAnnotations(
          parsed.themes,
          tags.filter((t: any) => parsed.tags.includes(t.tag_name)),
          engineData,
          fen,
          sideToMove
        );
      }
      
      console.log('   Theme annotations:', themeAnnotations);
      
      // Combine with priority order (specific > moves > themes)
      const combinedArrows = [...specificArrows, ...moveArrows, ...themeAnnotations.arrows].slice(0, 10);
      const combinedHighlights = [...specificHighlights, ...themeAnnotations.highlights].slice(0, 12);
      
      console.log('📍 Final annotations to apply:', {
        arrows: combinedArrows,
        highlights: combinedHighlights
      });
      
      if (combinedArrows.length === 0 && combinedHighlights.length === 0) {
        console.warn('⚠️ No annotations generated - check parsing logic');
        // Still apply empty arrays to clear any previous annotations
        setAnnotations(prev => ({
          ...prev,
          arrows: [],
          highlights: []
        }));
        return;
      }
      
      // Apply to board
      console.log('   Setting annotations state...');
      setAnnotations(prev => {
        const newState = {
          ...prev,
          arrows: combinedArrows,
          highlights: combinedHighlights
        };
        console.log('   New annotation state:', newState);
        return newState;
      });
      
      // Only show message if we actually applied annotations
      if (combinedArrows.length > 0 || combinedHighlights.length > 0) {
        addSystemMessage(`📍 Visual annotations applied: ${combinedArrows.length} arrows, ${combinedHighlights.length} highlights`);
      }
      
    } catch (error) {
      console.error('❌ Error applying LLM annotations:', error);
      addSystemMessage(`❌ Annotation error: ${error}`);
    }
  }

  async function generateLLMResponse(userMessage: string, toolOutput?: any, structuredAnalysis?: string) {
    if (!llmEnabled) return;

    try {
      // Determine the mode from user message if needed
      const inferredMode = inferModeFromMessage(userMessage) || mode;
      const modeContext = inferredMode === "PLAY" ? "playing a game" :
                         inferredMode === "ANALYZE" ? "analyzing positions" :
                         inferredMode === "TACTICS" ? "solving tactics" :
                         "discussing chess";

      // Extract theme-based analysis using chunk structure
      // First try toolOutput, then check if we have stored analysis for this FEN
      let analysisToUse = toolOutput;
      if (!analysisToUse || !analysisToUse.white_analysis) {
        // Check if we have stored analysis data for current FEN
        analysisToUse = analysisDataByFen.get(fen);
      }
      
      let themeAnalysisSummary = "";
      if (analysisToUse && analysisToUse.white_analysis) {
        const sideToMove = fen.split(' ')[1] === 'w' ? 'White' : 'Black';
        const currentSide = sideToMove === 'White' ? analysisToUse.white_analysis : analysisToUse.black_analysis;
        
        // CHUNK 1: Immediate position
        const immediate = currentSide.chunk_1_immediate || {};
        const topThemes = Object.entries(immediate.theme_scores || {})
          .filter(([k, v]) => k !== 'total' && Math.abs(v as number) > 0.01)
          .sort((a, b) => Math.abs((b[1] as number)) - Math.abs((a[1] as number)))
          .slice(0, 3)
          .map(([theme, score]) => `${theme}: ${(score as number).toFixed(1)}`)
          .join(", ");
        
        // CHUNK 2: Plan
        const planData = currentSide.chunk_2_plan_delta || {};
        
        themeAnalysisSummary = `
Theme-Based Analysis for this position:
- Eval: ${analysisToUse.eval_cp}cp (Material: ${immediate.material_balance_cp}cp, Positional: ${immediate.positional_cp_significance}cp)
- Immediate Themes: ${topThemes || "balanced position"}
- Plan: ${planData.plan_explanation || planData.plan_type || "balanced"}
`;
      }

      const contextMessage = `
Current Position (FEN): ${fen}
Current PGN: ${pgn}
Mode: ${inferredMode} (${modeContext})
Chat History: ${messages.slice(-3).map(m => `${m.role}: ${m.content}`).join("\n")}

${themeAnalysisSummary}

User Message: ${userMessage}

Instructions: Respond naturally and conversationally. Use themes to justify any positional claims. Keep your response concise (2-3 sentences). Focus on being helpful and engaging.
      `.trim();

      const {content: reply} = await callLLM([
        { role: "system", content: systemPrompt },
        { role: "user", content: contextMessage },
      ], 0.7);
      
      const meta = toolOutput ? { 
        rawEngineData: toolOutput, 
        fen: fen,
        mode: inferredMode,
        structuredAnalysis: structuredAnalysis
      } : undefined;
      
      addAssistantMessage(reply, meta);
    } catch (err: any) {
      addSystemMessage(`LLM error: ${err.message}`);
    }
  }

  async function handleMoveAnalysis(message: string) {
    try {
      // Extract move from message
      const moveDetection = detectMoveAnalysisRequest(message);
      let moveToAnalyze = moveDetection.move;
      const isHypothetical = moveDetection.isHypothetical;
      const referenceMove = moveDetection.referenceMove;
      
      // Default to current position for analysis
      let fenToAnalyze = fen;
      
      // If they're asking about the last move, get it from move history
      if (moveToAnalyze === "LAST_MOVE") {
        const mainLine = moveTree.getMainLine();
        if (mainLine.length === 0) {
          addSystemMessage("No moves have been played yet.");
          return;
        }
        const lastNode = mainLine[mainLine.length - 1];
        moveToAnalyze = lastNode.move;
        
        // Add system message indicating analysis is starting
        addSystemMessage("Analyzing move...");
        
        // Get the FEN before this move
        const fenBefore = mainLine.length > 1 ? mainLine[mainLine.length - 2].fen : "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";
        
        // Call analyze_move endpoint
        const response = await fetch(`http://localhost:8000/analyze_move?fen=${encodeURIComponent(fenBefore)}&move_san=${encodeURIComponent(moveToAnalyze)}&depth=18`, {
          method: 'POST'
        });
        
        if (!response.ok) {
          throw new Error(`Failed to analyze move: ${response.status}`);
        }
        
        const analysis = await response.json();
        const report = analysis.playedMoveReport;
        
        // Create LLM prompt with move analysis data
        const llmPrompt = `You are analyzing the last move played in the game. Provide a concise, natural language response (2-3 sentences).

POSITION BEFORE MOVE: ${fenBefore}
CURRENT PGN: ${moveTree.toPGN() || 'Opening'}
MOVE ANALYZED: ${moveToAnalyze}
WAS BEST MOVE: ${report.wasTheBestMove ? 'Yes' : 'No'}
${!report.wasTheBestMove ? `BEST MOVE: ${analysis.bestMove}` : ''}
EVAL CHANGE: ${report.evalChange}cp (${report.evalChange > 0 ? 'improved' : report.evalChange < 0 ? 'worsened' : 'unchanged'})
EVAL BEFORE: ${report.evalBefore}cp
EVAL AFTER: ${report.evalAfter}cp

THEMES GAINED: ${report.themesGained.join(", ") || 'none'}
THEMES LOST: ${report.themesLost.join(", ") || 'none'}

PIECES ACTIVATED: ${report.piecesActivated.join(", ") || 'none'}
PIECES DEACTIVATED: ${report.piecesDeactivated.join(", ") || 'none'}

THREATS CREATED: ${report.threatsCountAfter}
THREATS NEUTRALIZED: ${report.threatsCountBefore > report.threatsCountAfter ? report.threatsCountBefore - report.threatsCountAfter : 0}

INSTRUCTIONS:
Sentence 1: State if it was the best move and the evaluation change.
Sentence 2: Explain the main positional impact (themes gained/lost, pieces activated/deactivated).
Sentence 3: Mention key threats created or neutralized${!report.wasTheBestMove ? ', and briefly what the best move would have achieved.' : '.'}

Keep it concise and actionable.`;

        const {content: reply} = await callLLM([
          { role: "system", content: "You are a concise chess move analyst. Be direct and insightful." },
          { role: "user", content: llmPrompt }
        ], 0.6);
        
        // Create structured analysis cards for before/after/best
        const structuredAnalysis = `
=== POSITION BEFORE MOVE ===
${formatAnalysisCard(analysis.analysisBefore)}

=== POSITION AFTER ${moveToAnalyze} ===
${formatAnalysisCard(analysis.playedMoveReport.analysisAfter)}

${!report.wasTheBestMove && analysis.bestMoveReport ? `
=== POSITION AFTER BEST MOVE (${analysis.bestMove}) ===
${formatAnalysisCard(analysis.bestMoveReport.analysisAfter)}
` : ''}
        `.trim();
        
        addAssistantMessage(reply, { 
          moveAnalysis: analysis,
          structuredAnalysis,
          rawEngineData: analysis,
          mode: "MOVE_ANALYSIS",
          fen: fenBefore
        });
        
      } else if (moveToAnalyze) {
        // They specified a specific move - analyze it from current position
        const statusMsg = isHypothetical ? 
          `Exploring hypothetical move ${moveToAnalyze}...` : 
          `Analyzing move ${moveToAnalyze} from current position...`;
        addSystemMessage(statusMsg);
        
        // Call analyze_move endpoint with current position
        const response = await fetch(`http://localhost:8000/analyze_move?fen=${encodeURIComponent(fenToAnalyze)}&move_san=${encodeURIComponent(moveToAnalyze)}&depth=18`, {
          method: 'POST'
        });
        
        if (!response.ok) {
          throw new Error(`Failed to analyze move: ${response.status}`);
        }
        
        const analysis = await response.json();
        const report = analysis.playedMoveReport;
        
        // If hypothetical, add it to the move tree
        if (isHypothetical) {
          try {
            const testGame = new Chess(fenToAnalyze);
            const moveObj = testGame.move(moveToAnalyze);
            
            if (moveObj) {
              const newFen = testGame.fen();
              const newTree = moveTree.clone();
              newTree.addMove(moveObj.san, newFen, `hypothetical eval ${report.evalAfter}cp`);
              setMoveTree(newTree);
              setFen(newFen);
              setPgn(newTree.toPGN());
              setGame(testGame);
              setTreeVersion(v => v + 1);
            }
          } catch (err) {
            console.error("Failed to add hypothetical move to tree:", err);
          }
        }
        
        // Create LLM prompt with move analysis data
        const contextDescription = isHypothetical ? 
          (referenceMove ? ` (hypothetical - comparing to "${referenceMove}")` : ' (hypothetical - user is exploring "what if I play this")') : 
          ' from the current position';
        
        const llmPrompt = `You are analyzing a chess move${contextDescription}. Provide a concise, natural language response (2-3 sentences).

CURRENT POSITION FEN: ${fenToAnalyze}
CURRENT PGN: ${pgn || 'Starting position'}
MOVE ANALYZED: ${moveToAnalyze}
${referenceMove ? `COMPARING TO: ${referenceMove} (user asked about this move instead of ${referenceMove})` : ''}
WAS BEST MOVE: ${report.wasTheBestMove ? 'Yes' : 'No'}
${!report.wasTheBestMove ? `BEST MOVE: ${analysis.bestMove}` : ''}
EVAL CHANGE: ${report.evalChange}cp (${report.evalChange > 0 ? 'would improve' : report.evalChange < 0 ? 'would worsen' : 'unchanged'})
EVAL BEFORE: ${report.evalBefore}cp
EVAL AFTER: ${report.evalAfter}cp

THEMES GAINED: ${report.themesGained.join(", ") || 'none'}
THEMES LOST: ${report.themesLost.join(", ") || 'none'}

PIECES ACTIVATED: ${report.piecesActivated.join(", ") || 'none'}
PIECES DEACTIVATED: ${report.piecesDeactivated.join(", ") || 'none'}

THREATS CREATED: ${report.threatsCountAfter}
THREATS NEUTRALIZED: ${report.threatsCountBefore > report.threatsCountAfter ? report.threatsCountBefore - report.threatsCountAfter : 0}

INSTRUCTIONS:
${isHypothetical ? 'Frame as "if you play this" or "this would...".' : 'Frame as analysis of the position.'}
${referenceMove ? `Compare this move to ${referenceMove} if relevant.` : ''}
Sentence 1: State if it's the best move and the evaluation change.
Sentence 2: Explain the main positional impact (themes gained/lost, pieces activated/deactivated).
Sentence 3: Mention key threats created or neutralized${!report.wasTheBestMove ? ', and briefly what the best move would achieve.' : '.'}

Keep it concise and actionable.`;

        const {content: reply} = await callLLM([
          { role: "system", content: "You are a concise chess move analyst. Be direct and insightful." },
          { role: "user", content: llmPrompt }
        ], 0.6);
        
        // Create structured analysis cards for before/after/best
        const structuredAnalysis = `
=== POSITION BEFORE MOVE ===
${formatAnalysisCard(analysis.analysisBefore)}

=== POSITION AFTER ${moveToAnalyze} ===
${formatAnalysisCard(analysis.playedMoveReport.analysisAfter)}

${!report.wasTheBestMove && analysis.bestMoveReport ? `
=== POSITION AFTER BEST MOVE (${analysis.bestMove}) ===
${formatAnalysisCard(analysis.bestMoveReport.analysisAfter)}
` : ''}
        `.trim();
        
        addAssistantMessage(reply, { 
          moveAnalysis: analysis,
          structuredAnalysis,
          rawEngineData: analysis,
          mode: "MOVE_ANALYSIS",
          fen: fen
        });
      } else {
        addSystemMessage("I couldn't find a move in your message. Try: 'analyze e4' or 'what do you think of Nf3?'");
      }
      
    } catch (err: any) {
      addSystemMessage(`Move analysis failed: ${err.message}`);
    }
  }

  async function handleSendMessage(message: string) {
    // Check for button actions first (before adding user message)
    if (message.startsWith('__BUTTON_ACTION__')) {
      const action = message.replace('__BUTTON_ACTION__', '');
      if (action === 'START_WALKTHROUGH') {
        await startWalkthrough();
        return;
      } else if (action === 'NEXT_STEP') {
        await continueWalkthrough();
        return;
      } else if (action === 'LESSON_SKIP') {
        await skipLessonPosition();
        return;
      } else if (action === 'LESSON_PREVIOUS') {
        await previousLessonPosition();
        return;
      } else if (action.startsWith('JUMP_TO_PLY_')) {
        const ply = parseInt(action.replace('JUMP_TO_PLY_', ''));
        await jumpToKeyPoint(ply);
        return;
      } else if (action === 'RETRY_MOVE') {
        await startRetryMove();
        return;
      } else if (action === 'SHOW_SOLUTION') {
        await showRetrySolution();
        return;
      }
    }
    
    addUserMessage(message);

    let lower = message.toLowerCase().trim();
    
    // ALWAYS trigger full analysis for position evaluation questions
    const positionEvalWords = ['winning', 'better', 'advantage', 'ahead', 'eval'];
    const asksWhoQuestion = lower.includes('who') || lower.includes('what') || lower.includes('how');
    
    if (asksWhoQuestion && positionEvalWords.some(word => lower.includes(word)) && fen !== INITIAL_FEN) {
      console.log('🎯 Position evaluation question detected - triggering full analysis');
      // Store the user's question to answer it specifically after analysis
      await handleAnalyzePosition('answer_question', message);
      return;
    }

    // Check if user wants to continue walkthrough
    if (walkthroughActive) {
      if (lower.includes("next") || lower.includes("continue") || lower === "yes" || lower === "y") {
        await continueWalkthrough();
        return;
      } else if (lower.includes("stop") || lower.includes("end") || lower === "no") {
        setWalkthroughActive(false);
        setWalkthroughData(null);
        setWalkthroughStep(0);
        addSystemMessage("Walkthrough ended. Feel free to ask any questions!");
        return;
      }
    }

    // Check if this is general chat/greeting first
    if (isGeneralChat(message)) {
      await handleGeneralChat(message);
      return;
    }

    // Detect mode from message
    const detectedMode = detectMode(message);
    const effectiveMode = detectedMode || mode;
    lower = message.toLowerCase().trim();

    // If in PLAY mode or message looks like a move, try to parse as move
    if (effectiveMode === "PLAY") {
        // Try to parse as a move
        try {
        // Create a temporary game to test the move using current FEN
        const testGame = new Chess(fen);
        const move = testGame.move(message.trim());
        
          if (move) {
          
          // Move is valid, update the main game
          setGame(testGame);
          const newFen = testGame.fen();
          
          // Add move to tree (IMPORTANT!)
          const newTree = moveTree.clone();
          newTree.addMove(move.san, newFen);
          setMoveTree(newTree);
          const newPgn = newTree.toPGN();
          
          setFen(newFen);
          setPgn(newPgn);
            
            // Get engine response
              setWaitingForEngine(true);
              try {
            const response = await playMove(newFen, move.san, 1600, 1500);
                if (response.legal && response.engine_move_san && response.new_fen) {
              
              // Create game with engine's move
              const gameAfterEngine = new Chess(newFen);
              gameAfterEngine.move(response.engine_move_san);
              
              setGame(gameAfterEngine);
                  setFen(response.new_fen);
              
              // Add engine move to tree
              const treeAfterEngine = newTree.clone();
              const evalComment = `eval ${response.eval_cp_after || 0}cp`;
              treeAfterEngine.addMove(response.engine_move_san, response.new_fen, evalComment);
              setMoveTree(treeAfterEngine);
              setPgn(treeAfterEngine.toPGN());
              
                  addAssistantMessage(`Engine plays: ${response.engine_move_san}\nEval: ${response.eval_cp_after || 0}cp`);
                }
              } catch (err: any) {
                addSystemMessage(`Engine error: ${err.message}`);
              } finally {
                setWaitingForEngine(false);
              }
          return; // Successfully processed move
        }
      } catch (err: any) {
        // Not a valid move, fall through to general chat
      }
      
      // If we got here, it wasn't a valid move
      // Allow general conversation if LLM is enabled
      if (llmEnabled) {
        await generateLLMResponse(message);
          } else {
        addSystemMessage("Not a valid move. Use board or standard notation, or enable LLM for chat.");
          }
      return;
        }

    // Route based on other modes
    // Handle specific modes
    if (effectiveMode === "ANALYZE") {
        await handleAnalyzePosition();
      return;
    }
    
    if (effectiveMode === "TACTICS") {
      // Check if asking for next puzzle or solution
      if (lower.includes("next") || lower.includes("new") || lower.includes("another")) {
        await handleNextTactic();
      } else if (lower.includes("reveal") || lower.includes("solution") || lower.includes("answer") || lower.includes("show")) {
          await handleRevealTactic();
        } else {
        // Start a new tactic
        await handleNextTactic();
        }
      return;
    }

    if (effectiveMode === "DISCUSS") {
        await generateLLMResponse(message);
      return;
    }
    
    // Fallback: if no mode detected, try LLM conversation
    if (llmEnabled) {
      await generateLLMResponse(message);
    } else {
      addSystemMessage("I'm not sure what you want. Try asking for analysis, making a move, or requesting a tactic puzzle.");
    }
  }

  function handleResetBoard() {
    const newGame = new Chess();
    setGame(newGame);
    setFen(INITIAL_FEN);
    setPgn("");
    setAnnotations({
      fen: INITIAL_FEN,
      pgn: "",
      comments: [],
      nags: [],
      arrows: [],
      highlights: [],
    });
    setCurrentTactic(null);
    setTacticAttempts([]);
    setBoardOrientation("white");
    addSystemMessage("Board reset to starting position");
  }

  function handleCopyPGN() {
    navigator.clipboard.writeText(pgn || "No moves yet");
    addSystemMessage("PGN copied to clipboard");
  }

  // AI Board Control Functions
  async function aiPushMove(moveSan: string): Promise<boolean> {
    try {
      const tempGame = new Chess(fen);
      const move = tempGame.move(moveSan);
      
      if (move) {
        setGame(tempGame);
        setFen(tempGame.fen());
        setPgn(tempGame.pgn());
        addSystemMessage(`🤖 AI pushed move: ${moveSan}`);
        return true;
      }
      return false;
    } catch (err) {
      return false;
    }
  }

  function aiNavigateToMove(moveNumber: number): boolean {
    try {
      const newGame = new Chess();
      const moves = game.history();
      
      if (moveNumber < 0 || moveNumber > moves.length) {
        return false;
      }
      
      for (let i = 0; i < moveNumber; i++) {
        newGame.move(moves[i]);
      }
      
      setGame(newGame);
      setFen(newGame.fen());
      setPgn(newGame.pgn());
      addSystemMessage(`🤖 AI navigated to move ${moveNumber}`);
      return true;
    } catch (err) {
      return false;
    }
  }

  function aiSetPosition(newFen: string): boolean {
    try {
      const newGame = new Chess(newFen);
      setGame(newGame);
      setFen(newFen);
      setPgn(newGame.pgn());
      addSystemMessage(`🤖 AI set new position`);
      return true;
    } catch (err) {
      return false;
    }
  }

  function aiAddArrow(from: string, to: string, color: string = "#00aa00"): void {
    setAnnotations(prev => ({
      ...prev,
      arrows: [...prev.arrows, { from, to, color }]
    }));
    addSystemMessage(`🤖 AI added arrow: ${from} → ${to}`);
  }

  function aiRemoveAllArrows(): void {
    setAnnotations(prev => ({
      ...prev,
      arrows: []
    }));
    addSystemMessage(`🤖 AI cleared all arrows`);
  }

  function aiHighlightSquare(square: string, color: string = "rgba(255, 255, 0, 0.4)"): void {
    setAnnotations(prev => ({
      ...prev,
      highlights: [...prev.highlights, { sq: square, color }]
    }));
    addSystemMessage(`🤖 AI highlighted square: ${square}`);
  }

  function aiRemoveAllHighlights(): void {
    setAnnotations(prev => ({
      ...prev,
      highlights: []
    }));
    addSystemMessage(`🤖 AI cleared all highlights`);
  }

  function aiAddComment(text: string): void {
    setAnnotations(prev => ({
      ...prev,
      comments: [...prev.comments, {
        ply: game.history().length,
        text
      }]
    }));
    addSystemMessage(`🤖 AI added comment`);
  }

  function aiClearAllAnnotations(): void {
    setAnnotations({
      fen: fen,
      pgn: pgn,
      comments: [],
      nags: [],
      arrows: [],
      highlights: []
    });
    addSystemMessage(`🤖 AI cleared all annotations`);
  }

  // Move Tree Handlers
  function handleMoveClick(node: MoveNode) {
    // Navigate to clicked move
    const newTree = moveTree.clone();
    newTree.goToNode(node);
    setMoveTree(newTree);
    
    // Update game and board
    const newGame = new Chess();
    newGame.load(newTree.currentNode.fen);
    setGame(newGame);
    setFen(newTree.currentNode.fen);
    setPgn(newTree.toPGN());
  }

  function handleDeleteMove(node: MoveNode) {
    try {
      const newTree = moveTree.clone();
      newTree.goToNode(node);
      const parent = newTree.deleteMove();
      
      if (parent) {
        const newPgn = newTree.toPGN();
        const newGame = new Chess();
        newGame.load(parent.fen);
        
        setMoveTree(newTree);
        setGame(newGame);
        setFen(parent.fen);
        setPgn(newPgn);
        setTreeVersion(v => v + 1);
        
        setAnnotations(prev => ({ 
          ...prev, 
          fen: parent.fen,
          pgn: newPgn 
        }));
      }
    } catch (err) {
      console.error('Delete move error:', err);
      addSystemMessage('Error deleting move');
    }
  }

  function handleDeleteVariation(node: MoveNode) {
    try {
      const newTree = moveTree.clone();
      newTree.goToNode(node);
      const parent = newTree.deleteVariation();
      
      if (parent) {
        const newPgn = newTree.toPGN();
        const newGame = new Chess();
        newGame.load(parent.fen);
        
        setMoveTree(newTree);
        setGame(newGame);
        setFen(parent.fen);
        setPgn(newPgn);
        setTreeVersion(v => v + 1);
        
        setAnnotations(prev => ({ 
          ...prev, 
          fen: parent.fen,
          pgn: newPgn 
        }));
      }
    } catch (err) {
      console.error('Delete variation error:', err);
      addSystemMessage('Error deleting variation');
    }
  }

  function handlePromoteVariation(node: MoveNode) {
    try {
      const newTree = moveTree.clone();
      newTree.goToNode(node);
      const success = newTree.promoteVariation();
      
      if (success) {
        const newPgn = newTree.toPGN();
        
        setMoveTree(newTree);
        setPgn(newPgn);
        setTreeVersion(v => v + 1);
        
        setAnnotations(prev => ({ 
          ...prev, 
          pgn: newPgn 
        }));
      }
    } catch (err) {
      console.error('Promote variation error:', err);
      addSystemMessage('Error promoting variation');
    }
  }

  function handleAddComment(node: MoveNode, comment: string) {
    try {
      const newTree = moveTree.clone();
      newTree.goToNode(node);
      newTree.addComment(comment);
      
      const newPgn = newTree.toPGN();
      
      setMoveTree(newTree);
      setPgn(newPgn);
      setTreeVersion(v => v + 1);
      
      setAnnotations(prev => ({ 
        ...prev, 
        pgn: newPgn 
      }));
    } catch (err) {
      console.error('Add comment error:', err);
      addSystemMessage('Error adding comment');
    }
  }

  function handleNavigateBack() {
    const newTree = moveTree.clone();
    const parent = newTree.goBack();
    
    if (parent) {
      setMoveTree(newTree);
      setFen(parent.fen);
      const newGame = new Chess();
      newGame.load(parent.fen);
      setGame(newGame);
    }
  }

  function handleNavigateForward() {
    const newTree = moveTree.clone();
    const next = newTree.goForward();
    
    if (next) {
      setMoveTree(newTree);
      setFen(next.fen);
      const newGame = new Chess();
      newGame.load(next.fen);
      setGame(newGame);
    }
  }

  function handleNavigateStart() {
    const newTree = moveTree.clone();
    newTree.goToStart();
    setMoveTree(newTree);
    setFen(INITIAL_FEN);
    const newGame = new Chess();
    setGame(newGame);
  }

  function handleNavigateEnd() {
    const newTree = moveTree.clone();
    newTree.goToEnd();
    setMoveTree(newTree);
    setFen(newTree.currentNode.fen);
    const newGame = new Chess();
    newGame.load(newTree.currentNode.fen);
    setGame(newGame);
  }

  function handleLoadFen(newFen: string) {
    try {
      const newGame = new Chess(newFen);
      setGame(newGame);
      setFen(newFen);
      
      // Reset move tree when loading new FEN
      const newTree = new MoveTree();
      newTree.root.fen = newFen;
      newTree.currentNode = newTree.root;
      setMoveTree(newTree);
      setPgn("");
      
      addSystemMessage(`Position loaded from FEN`);
    } catch (err: any) {
      addSystemMessage(`Invalid FEN: ${err.message}`);
    }
  }

  async function startWalkthrough() {
    if (!walkthroughData) return;
    
    setWalkthroughActive(true);
    setWalkthroughStep(0);
    addSystemMessage("Starting guided walkthrough...");
    
    // Start with first step immediately (don't wait for state update)
    setTimeout(() => continueWalkthrough(), 100);
  }

  async function continueWalkthrough() {
    if (!walkthroughData) return;
    
    const { moves, openingName, gameTags, avgWhiteAccuracy, avgBlackAccuracy, 
            accuracyStats, leftTheoryMove, criticalMovesList, missedWinsList,
            crossed100, crossed200, crossed300 } = walkthroughData;
    
    const step = walkthroughStep;
    
    // Define walkthrough sequence
    const sequence: any[] = [];
    
    // Step 1: Opening (navigate to last theory move)
    const lastTheoryMove = moves.filter((m: any) => m.isTheoryMove).pop();
    if (lastTheoryMove) {
      sequence.push({ type: 'opening', move: lastTheoryMove });
    }
    
    // Step 2: Left theory move
    if (leftTheoryMove) {
      sequence.push({ type: 'left_theory', move: leftTheoryMove });
    }
    
    // Collect all special moves with PRIORITY ORDER
    const specialMoves: any[] = [];
    
    // Priority 1: Blunders, Mistakes, Inaccuracies (HIGHEST PRIORITY)
    const errors = moves.filter((m: any) => 
      m.quality === 'blunder' || m.quality === 'mistake' || m.quality === 'inaccuracy'
    );
    errors.forEach((m: any) => {
      const type = m.quality === 'blunder' ? 'blunder' : 
                  m.quality === 'mistake' ? 'mistake' : 'inaccuracy';
      specialMoves.push({ type, move: m });
    });
    
    // Priority 2: Critical moves (only if not already an error)
    criticalMovesList.forEach((m: any) => {
      if (!specialMoves.find((s: any) => s.move.moveNumber === m.moveNumber && s.move.move === m.move)) {
        specialMoves.push({ type: 'critical', move: m });
      }
    });
    
    // Priority 3: Missed wins (only if not already flagged)
    missedWinsList.forEach((m: any) => {
      if (!specialMoves.find((s: any) => s.move.moveNumber === m.moveNumber && s.move.move === m.move)) {
        specialMoves.push({ type: 'missed_win', move: m });
      }
    });
    
    // Priority 4: Advantage shifts (LOWEST PRIORITY - only if not already flagged)
    [...crossed100, ...crossed200, ...crossed300].forEach((m: any) => {
      if (!specialMoves.find((s: any) => s.move.moveNumber === m.moveNumber && s.move.move === m.move)) {
        specialMoves.push({ type: 'advantage_shift', move: m });
      }
    });
    
    // Sort special moves by move number to maintain chronological order
    specialMoves.sort((a, b) => a.move.moveNumber - b.move.moveNumber);
    
    // Add sorted special moves to sequence
    specialMoves.forEach(sm => sequence.push(sm));
    
    // Step 7: Middlegame transition
    const middlegameStart = moves.find((m: any) => m.phase === 'middlegame');
    if (middlegameStart) {
      sequence.push({ type: 'middlegame', move: middlegameStart });
    }
    
    // Step 8: Final position
    sequence.push({ type: 'final', move: moves[moves.length - 1] });
    
    // Check if we're done
    if (step >= sequence.length) {
      setWalkthroughActive(false);
      setWalkthroughStep(0);
      addAssistantMessage("That completes the walkthrough! Feel free to ask any questions about the game.");
      return;
    }
    
    const current = sequence[step];
    await executeWalkthroughStep(current, step + 1, sequence.length);
    
    setWalkthroughStep(step + 1);
  }

  async function executeWalkthroughStep(step: any, stepNum: number, totalSteps: number) {
    const { type, move } = step;
    
    // Navigate to the move
    await navigateToMove(move.moveNumber);
    
    // Wait a bit for board to update
    await new Promise(resolve => setTimeout(resolve, 300));
    
    let message = "";
    
    switch (type) {
      case 'opening':
        message = await generateOpeningAnalysis(move);
        break;
      case 'left_theory':
        // First show the context message
        const evalAtTheory = move.evalBefore ? `${move.evalBefore > 0 ? '+' : ''}${(move.evalBefore / 100).toFixed(2)}` : '0.00';
        addAssistantMessage(`**Move ${move.moveNumber}. ${move.move} - Left Opening Theory**\n\n${move.color === 'w' ? 'White' : 'Black'} played **${move.move}**, departing from known opening theory. The evaluation was ${evalAtTheory} before this move. Let's analyze what this novelty means for the position.`);
        
        // Wait a bit, then analyze
        await new Promise(resolve => setTimeout(resolve, 500));
        await analyzeMoveAtPosition(move);
        
        // Return early to skip the normal message handling
        setMessages(prev => [...prev, {
          role: 'button',
          content: '',
          buttonAction: 'NEXT_STEP',
          buttonLabel: `Next Step (${stepNum}/${totalSteps})`
        }]);
        return;
      case 'blunder':
      case 'mistake':
      case 'inaccuracy':
        const cpLoss = move.cpLoss || 0;
        const severity = move.quality === 'blunder' ? 'Blunder!' : 
                        move.quality === 'mistake' ? 'Mistake' : 'Inaccuracy';
        addAssistantMessage(`**Move ${move.moveNumber}. ${move.move} - ${severity} (${move.accuracy.toFixed(1)}% accuracy)**\n\n${move.color === 'w' ? 'White' : 'Black'} played **${move.move}**, losing ${cpLoss}cp. The best move was **${move.bestMove}**. Would you like to retry this position?`);
        await new Promise(resolve => setTimeout(resolve, 500));
        await analyzeMoveAtPosition(move);
        
        // Store retry data and add retry button
        setRetryMoveData(move);
        setMessages(prev => [...prev, {
          role: 'button',
          content: '',
          buttonAction: 'RETRY_MOVE',
          buttonLabel: `Retry Move ${move.moveNumber}`
        }, {
          role: 'button',
          content: '',
          buttonAction: 'NEXT_STEP',
          buttonLabel: `Next Step (${stepNum}/${totalSteps})`
        }]);
        return;
      case 'critical':
        const gapToSecond = move.gapToSecondBest || 0;
        addAssistantMessage(`**Move ${move.moveNumber}. ${move.move} - Critical Move!**\n\n${move.color === 'w' ? 'White' : 'Black'} found the best move **${move.move}**, which was ${gapToSecond}cp better than the second-best option. This was the only move that maintained the advantage.`);
        await new Promise(resolve => setTimeout(resolve, 500));
        await analyzeMoveAtPosition(move);
        setMessages(prev => [...prev, {
          role: 'button',
          content: '',
          buttonAction: 'NEXT_STEP',
          buttonLabel: `Next Step (${stepNum}/${totalSteps})`
        }]);
        return;
      case 'missed_win':
        const evalBefore = move.evalBefore || 0;
        const missedGap = move.gapToSecondBest || 0;
        addAssistantMessage(`**Move ${move.moveNumber}. ${move.move} - Missed Win**\n\n${move.color === 'w' ? 'White' : 'Black'} played **${move.move}** in a winning position (${(evalBefore / 100).toFixed(2)}), but missed a better move that was ${missedGap}cp stronger. This was a chance to convert decisively.`);
        await new Promise(resolve => setTimeout(resolve, 500));
        await analyzeMoveAtPosition(move);
        setMessages(prev => [...prev, {
          role: 'button',
          content: '',
          buttonAction: 'NEXT_STEP',
          buttonLabel: `Next Step (${stepNum}/${totalSteps})`
        }]);
        return;
      case 'advantage_shift':
        const evalChange = move.evalAfter - move.evalBefore;
        const crossedThreshold = 
          move.crossed300 ? '±300cp (decisive)' :
          move.crossed200 ? '±200cp (clear advantage)' :
          move.crossed100 ? '±100cp (slight advantage)' : 'significant';
        addAssistantMessage(`**Move ${move.moveNumber}. ${move.move} - Advantage Shift**\n\n${move.color === 'w' ? 'White' : 'Black'} played **${move.move}**, crossing the ${crossedThreshold} threshold. The evaluation shifted from ${(move.evalBefore / 100).toFixed(2)} to ${(move.evalAfter / 100).toFixed(2)} (${evalChange > 0 ? '+' : ''}${(evalChange / 100).toFixed(2)}). Let's examine the resulting position.`);
        addSystemMessage("Analyzing position...");
        await new Promise(resolve => setTimeout(resolve, 500));
        await handleAnalyzePosition("full_analysis");
        setMessages(prev => [...prev, {
          role: 'button',
          content: '',
          buttonAction: 'NEXT_STEP',
          buttonLabel: `Next Step (${stepNum}/${totalSteps})`
        }]);
        return;
      case 'middlegame':
        message = await generateMiddlegameAnalysis(move);
        addSystemMessage("Analyzing position...");
        await handleAnalyzePosition("full_analysis");
        break;
      case 'final':
        message = await generateFinalAnalysis(move);
        addSystemMessage("Analyzing position...");
        await handleAnalyzePosition("full_analysis");
        break;
    }
    
    if (message && !message.includes("Let me analyze")) {
      addAssistantMessage(message);
      // Add Next button
      setMessages(prev => [...prev, {
        role: 'button',
        content: '',
        buttonAction: 'NEXT_STEP',
        buttonLabel: `Next Step (${stepNum}/${totalSteps})`
      }]);
    } else if (message) {
      // Message will be added by the analysis function
      setTimeout(() => {
        // Add Next button after the analysis
        setMessages(prev => [...prev, {
          role: 'button',
          content: '',
          buttonAction: 'NEXT_STEP',
          buttonLabel: `Next Step (${stepNum}/${totalSteps})`
        }]);
      }, 1500);
    }
  }

  async function navigateToMove(moveNumber: number, animate: boolean = true) {
    // Navigate to specific move in the tree with optional smooth animation
    const mainLine = moveTree.getMainLine();
    const currentNode = moveTree.currentNode;
    const currentMoveNum = currentNode?.moveNumber || 0;
    
    const targetNode = mainLine.find((n: any) => n.moveNumber === moveNumber);
    
    if (!targetNode) return;
    
    const newTree = moveTree.clone();
    const currentIndex = mainLine.findIndex((n: any) => n.moveNumber === currentMoveNum);
    const targetIndex = mainLine.findIndex((n: any) => n.moveNumber === moveNumber);
    
    if (!animate || Math.abs(targetIndex - currentIndex) <= 1) {
      // Instant jump for small distances or if animation disabled
      newTree.goToStart();
      for (let i = 0; i < targetIndex; i++) {
        newTree.goForward();
      }
      
      setMoveTree(newTree);
      setFen(targetNode.fen);
      const tempGame = new Chess(targetNode.fen);
      setGame(tempGame);
      return;
    }
    
    // Animate move-by-move for smooth transition
    const direction = targetIndex > currentIndex ? 1 : -1;
    const steps = Math.abs(targetIndex - currentIndex);
    
    // Position tree at current location
    newTree.goToStart();
    for (let i = 0; i < currentIndex; i++) {
      newTree.goForward();
    }
    
    // Animate each step
    for (let step = 0; step < steps; step++) {
      await new Promise(resolve => setTimeout(resolve, 200)); // 200ms delay per move
      
      if (direction > 0) {
        newTree.goForward();
      } else {
        newTree.goBack();
      }
      
      const node = newTree.currentNode;
      if (node) {
        setMoveTree(newTree.clone());
        setFen(node.fen);
        const tempGame = new Chess(node.fen);
        setGame(tempGame);
      }
    }
  }

  async function generateOpeningAnalysis(move: any): Promise<string> {
    const { openingName, avgWhiteAccuracy, avgBlackAccuracy, accuracyStats } = walkthroughData;
    
    const prompt = `Analyze the opening phase of this chess game:

Opening: ${openingName}

Opening Accuracy:
White: ${accuracyStats.opening.white.toFixed(1)}%
Black: ${accuracyStats.opening.black.toFixed(1)}%

Write 2-3 sentences about:
1. The opening choice and its key themes
2. How well each side played in the opening phase

Be conversational and educational. Do not mention specific moves or positions - the next step will cover that.`;

    try {
      const response = await callLLM([
        { role: "system", content: "You are a helpful chess coach." },
        { role: "user", content: prompt }
      ]);
      return `**Opening: ${openingName}**\n\n${response}`;
    } catch (err) {
      return `**Opening: ${openingName}**\n\nWhite: ${accuracyStats.opening.white.toFixed(1)}% | Black: ${accuracyStats.opening.black.toFixed(1)}%`;
    }
  }

  async function generateMiddlegameAnalysis(move: any): Promise<string> {
    const { accuracyStats } = walkthroughData;
    
    // Get material balance
    const tempGame = new Chess(move.fen);
    const board = tempGame.board();
    let material = { white: 0, black: 0 };
    
    const pieceValues: any = { p: 1, n: 3, b: 3, r: 5, q: 9, k: 0 };
    
    board.forEach((row: any) => {
      row.forEach((square: any) => {
        if (square) {
          const value = pieceValues[square.type];
          if (square.color === 'w') material.white += value;
          else material.black += value;
        }
      });
    });
    
    const materialDiff = material.white - material.black;
    const materialStr = materialDiff > 0 ? `White +${materialDiff}` : materialDiff < 0 ? `Black +${Math.abs(materialDiff)}` : "Equal";
    
    const evalStr = move.evalAfter ? `${move.evalAfter > 0 ? '+' : ''}${(move.evalAfter / 100).toFixed(2)}` : '0.00';
    
    return `**Middlegame Transition (Move ${move.moveNumber})**\n\nBy move ${move.moveNumber}, the game has entered the middlegame phase. The position is evaluated at ${evalStr}.\n\n**Material Balance:** ${materialStr}\n**Middlegame Accuracy:** White ${accuracyStats.middlegame.white.toFixed(1)}% | Black ${accuracyStats.middlegame.black.toFixed(1)}%\n\nLet's analyze the key features of this middlegame position.`;
  }

  async function generateFinalAnalysis(move: any): Promise<string> {
    const { avgWhiteAccuracy, avgBlackAccuracy, gameTags, accuracyStats } = walkthroughData;
    
    const finalEval = move.evalAfter;
    let result = "The game ended in a drawn position";
    if (finalEval > 300) result = "White won this game";
    else if (finalEval < -300) result = "Black won this game";
    
    const finalEvalStr = `${finalEval > 0 ? '+' : ''}${(finalEval / 100).toFixed(2)}`;
    const tags = gameTags.map((t: any) => t.name).join(", ");
    
    return `**Final Position (Move ${move.moveNumber})**\n\n${result} with a final evaluation of ${finalEvalStr}.\n\n**Overall Accuracy:** White ${avgWhiteAccuracy}% | Black ${avgBlackAccuracy}%\n**Endgame Accuracy:** White ${accuracyStats.endgame.white.toFixed(1)}% | Black ${accuracyStats.endgame.black.toFixed(1)}%\n**Game Tags:** ${tags || "Balanced game"}\n\nLet me provide a final assessment of this position.`;
  }

  async function analyzeMoveAtPosition(move: any) {
    // OPTIMIZED FLOW: Start LLM request first, then setup board in parallel
    const fenBefore = move.fenBefore;
    const fenAfter = move.fen;
    
    // Start LLM request immediately (don't await yet)
    const llmRequestPromise = fetch(`http://localhost:8000/analyze_move?fen=${encodeURIComponent(fenBefore)}&move_san=${encodeURIComponent(move.move)}&depth=18`, {
      method: 'POST'
    });
    
    // While LLM is processing, setup board and visuals
    try {
      // Setup board to position AFTER the move
      const newGame = new Chess(fenAfter);
      setGame(newGame);
      setFen(fenAfter);
      
      // Extract move squares and draw arrow
      const boardBefore = new Chess(fenBefore);
      const chessMove = boardBefore.moves({ verbose: true }).find((m: any) => m.san === move.move);
      
      if (chessMove) {
        const fromSquare = chessMove.from;
        const toSquare = chessMove.to;
        
        // Draw arrow showing the move that was played
        setAnnotations(prev => ({
          ...prev,
          fen: fenAfter,
          arrows: [{ from: fromSquare, to: toSquare, color: '#3b82f6' }],
          highlights: []
        }));
      }
    } catch (error) {
      console.error("Failed to set board position:", error);
    }
    
    // Add system message after board is setup
    addSystemMessage("Analyzing move...");
    
    // Now await the LLM response
    try {
      const response = await llmRequestPromise;
      
      if (!response.ok) {
        throw new Error(`Backend returned ${response.status}`);
      }
      
      const data = await response.json();
      
      // Adapt new backend format (with af_starting, af_best, etc.) to old frontend format
      const isBest = data.is_best_move || false;
      const evalBefore = data.eval_before || data.eval_after_move || 0;
      const evalAfter = data.eval_after_move || 0;
      const evalChange = Math.abs(evalBefore - evalAfter);
      const evalChangeStr = evalChange > 0 ? `+${(evalChange / 100).toFixed(2)}` : `${(evalChange / 100).toFixed(2)}`;
      const bestMove = data.best_move || move.move;
      const cpLoss = data.cp_loss || 0;
      
      // Extract tag changes from analysis if available
      let themesGained: string[] = [];
      let themesLost: string[] = [];
      
      if (data.analysis) {
        const afBefore = data.analysis.af_starting;
        const afAfter = isBest ? data.analysis.af_best : data.analysis.af_played;
        
        if (afBefore && afAfter) {
          const tagsBefore = new Set((afBefore.tags || []).map((t: any) => t.tag_name));
          const tagsAfter = new Set((afAfter.tags || []).map((t: any) => t.tag_name));
          
          themesGained = Array.from(tagsAfter).filter(t => !tagsBefore.has(t as string)).slice(0, 5) as string[];
          themesLost = Array.from(tagsBefore).filter(t => !tagsAfter.has(t as string)).slice(0, 5) as string[];
        }
      }
      
      // Build structured analysis
      let structuredAnalysis = `**Move Analysis: ${move.move}**\n\n`;
      structuredAnalysis += `Evaluation: ${(evalBefore / 100).toFixed(2)} → ${(evalAfter / 100).toFixed(2)} (${evalChangeStr})\n`;
      structuredAnalysis += `CP Loss: ${cpLoss}cp\n\n`;
      
      if (isBest) {
        structuredAnalysis += `✓ This was the best move!\n\n`;
      } else {
        const bestEval = data.eval_after_best || evalAfter;
        structuredAnalysis += `The engine preferred: ${bestMove} (${(bestEval / 100).toFixed(2)})\n`;
        structuredAnalysis += `Difference: ${(cpLoss / 100).toFixed(2)} pawns\n\n`;
      }
      
      // Add themes
      if (themesGained.length > 0) {
        structuredAnalysis += `Themes gained: ${themesGained.join(", ")}\n`;
      }
      if (themesLost.length > 0) {
        structuredAnalysis += `Themes lost: ${themesLost.join(", ")}\n`;
      }
      
      // Generate LLM response (CONCISE)
      const llmPrompt = `Analyze move ${move.moveNumber}. ${move.move}.

Eval: ${(evalBefore / 100).toFixed(2)} → ${(evalAfter / 100).toFixed(2)} (${evalChangeStr}, ${cpLoss}cp loss)
Best move: ${isBest ? "Yes" : bestMove}
${themesGained.length > 0 ? `Gained: ${themesGained.slice(0, 2).join(", ")}` : ""}
${themesLost.length > 0 ? `Lost: ${themesLost.slice(0, 2).join(", ")}` : ""}

In 1-2 sentences: What did this move accomplish strategically?`;

      try {
        // Get recent chat context (last 3 messages)
        const chatContext = getRecentChatContext(3);
        
        const llmResponse = await callLLM([
          { role: "system", content: "You are a chess coach. Answer in 1-2 sentences maximum. Focus on strategic impact only." },
          ...chatContext,
          { role: "user", content: llmPrompt }
        ], 0.5, "gpt-4o-mini");
        
        // Add the LLM response with raw data metadata
        const {content: llmContent} = llmResponse;
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: llmContent,
          meta: {
            structuredAnalysis: structuredAnalysis,
            rawEngineData: data
          }
        }]);
      } catch (err) {
        console.error("LLM call failed:", err);
        // Fallback to structured analysis
        addAssistantMessage(structuredAnalysis);
      }
      
    } catch (err: any) {
      console.error("Move analysis failed:", err);
      addAssistantMessage(`Move ${move.moveNumber}. ${move.move} - Accuracy: ${move.accuracy.toFixed(1)}%`);
    }
  }

  async function analyzeCurrentPosition() {
    // Analyze the current position
    try {
      const response = await fetch(`http://localhost:8000/analyze_position?fen=${encodeURIComponent(fen)}&lines=3&depth=12`);
      
      if (!response.ok) {
        throw new Error(`Backend returned ${response.status}`);
      }
      
      const data = await response.json();
      
      const evalCp = data.eval_cp || 0;
      const evalPawns = (evalCp / 100).toFixed(2);
      const verdict = evalCp > 100 ? "+- (White is winning)" :
                      evalCp > 50 ? "+/= (White is slightly better)" :
                      evalCp > -50 ? "= (Equal position)" :
                      evalCp > -100 ? "=/+ (Black is slightly better)" :
                      "-+ (Black is winning)";
      
      let message = `**Position Analysis**\n\nEval: ${evalCp > 0 ? '+' : ''}${evalPawns} ${verdict}\n\n`;
      
      if (data.themes && data.themes.length > 0) {
        message += `Key themes: ${data.themes.slice(0, 3).join(", ")}\n\n`;
      }
      
      if (data.candidate_moves && data.candidate_moves.length > 0) {
        message += `Best moves:\n`;
        data.candidate_moves.slice(0, 3).forEach((c: any, i: number) => {
          message += `${i + 1}. ${c.move} (${(c.eval_cp / 100).toFixed(2)})\n`;
        });
      }
      
      addAssistantMessage(message);
      
    } catch (err: any) {
      console.error("Position analysis failed:", err);
    }
  }

  function displaySummaryTables(reviewData: any, moves: any[], accuracyStats: any, openingName: string) {
    // Summary Tables Mode - Display all statistics and data at once
    
    const stats = reviewData.stats || { white: {}, black: {} };
    const keyPoints = reviewData.key_points || [];
    const phases = reviewData.phases || [];
    const plyRecords = reviewData.ply_records || [];
    
    // 1. Show eval graph
    setMessages(prev => [...prev, {
      role: 'graph',
      content: '',
      graphData: moves
    }]);
    
    // 2. Calculate top themes per phase and overall
    const themesByPhase = calculateTopThemesPerPhase(plyRecords);
    const overallTopThemes = calculateOverallTopThemes(plyRecords);
    
    // 3. Accuracy table
    const whiteAcc = stats.white?.overall_accuracy || 100;
    const blackAcc = stats.black?.overall_accuracy || 100;
    const whiteCounts = stats.white?.counts || {};
    const blackCounts = stats.black?.counts || {};
    
    const accTable = `
## Game Review Summary

**Opening:** ${openingName}  
**Side Focus:** ${reviewSideFocus === 'both' ? 'Both Sides' : reviewSideFocus === 'white' ? 'White Only' : 'Black Only'}

### Overall Top Themes

| Rank | Theme | Occurrences | Avg Score |
|------|-------|-------------|-----------|
${overallTopThemes.slice(0, 5).map((t: any, i: number) => `| ${i + 1} | ${t.theme} | ${t.count} | ${t.avgScore.toFixed(1)} |`).join('\n')}

### Accuracy Summary

| Side | Accuracy | Critical | Excellent | Good | Inaccurate | Mistake | Blunder | Avg CP Loss |
|------|----------|----------|-----------|------|------------|---------|---------|-------------|
| White | ${whiteAcc.toFixed(1)}% | ${whiteCounts.critical_best || 0} | ${whiteCounts.excellent || 0} | ${whiteCounts.good || 0} | ${whiteCounts.inaccuracy || 0} | ${whiteCounts.mistake || 0} | ${whiteCounts.blunder || 0} | ${stats.white?.avg_cp_loss?.toFixed(1) || 'N/A'} |
| Black | ${blackAcc.toFixed(1)}% | ${blackCounts.critical_best || 0} | ${blackCounts.excellent || 0} | ${blackCounts.good || 0} | ${blackCounts.inaccuracy || 0} | ${blackCounts.mistake || 0} | ${blackCounts.blunder || 0} | ${stats.black?.avg_cp_loss?.toFixed(1) || 'N/A'} |

### Phase-Based Accuracy & Top Themes

| Phase | White Acc | Black Acc | Moves | Top Themes |
|-------|-----------|-----------|-------|------------|
| Opening | ${accuracyStats.opening.white.toFixed(1)}% | ${accuracyStats.opening.black.toFixed(1)}% | ${moves.filter((m: any) => m.phase === 'opening').length} | ${themesByPhase.opening.join(', ')} |
| Middlegame | ${accuracyStats.middlegame.white.toFixed(1)}% | ${accuracyStats.middlegame.black.toFixed(1)}% | ${moves.filter((m: any) => m.phase === 'middlegame').length} | ${themesByPhase.middlegame.join(', ')} |
| Endgame | ${accuracyStats.endgame.white.toFixed(1)}% | ${accuracyStats.endgame.black.toFixed(1)}% | ${moves.filter((m: any) => m.phase === 'endgame').length} | ${themesByPhase.endgame.join(', ')} |

### Key Points (${keyPoints.length} total)

| Move | Side | Eval | Category | Labels | Top Themes |
|------|------|------|----------|--------|------------|
${keyPoints.slice(0, 15).map((kp: any) => {
  const moveNum = Math.floor((kp.ply + 1) / 2);
  const labels = (kp.key_point_labels || []).join(', ');
  // Use pre-formatted eval string if available, otherwise format it
  let evalStr = 'N/A';
  if (kp.engine?.played_eval_after_str) {
    evalStr = kp.engine.played_eval_after_str;
  } else if (kp.engine?.played_eval_after_cp !== undefined) {
    const formatted = formatEval(kp.engine.played_eval_after_cp);
    evalStr = formatted.startsWith('M') ? formatted : 
      (kp.engine.played_eval_after_cp > 0 ? `+${(kp.engine.played_eval_after_cp / 100).toFixed(2)}` : 
       `${(kp.engine.played_eval_after_cp / 100).toFixed(2)}`);
  }
  const sideName = kp.side_moved === 'white' ? 'White' : 'Black';
  
  // Extract top themes from this move's analysis
  const moveThemes = extractTopThemesFromMove(kp);
  
  return `| ${moveNum}. ${kp.san} | ${sideName} | ${evalStr} | ${kp.category || 'N/A'} | ${labels} | ${moveThemes} |`;
}).join('\n')}

${keyPoints.length > 15 ? `\n*...and ${keyPoints.length - 15} more key moments*` : ''}

*Click the buttons below to jump to any key point:*

### Phase Transitions

| Move | Transition |
|------|------------|
${phases.length > 0 ? phases.map((p: any) => `| ${Math.floor((p.ply + 1) / 2)} | ${p.from_phase} to ${p.to_phase} |`).join('\n') : '| - | No phase transitions detected |'}

---

*Click on move numbers in Key Points to jump to that position. You can also ask me questions about specific moves!*
    `.trim();
    
    addAssistantMessage(accTable);
    
    // Make key points clickable by storing them
    setGameReviewKeyPoints(keyPoints);
    
    // Add expandable sections
    
    // 1. Accuracy by Theme (expandable)
    const accuracyByTheme = calculateAccuracyByTheme(plyRecords);
    const themeAccuracyTable = `
| Theme | Avg Accuracy | Moves |
|-------|--------------|-------|
${accuracyByTheme.slice(0, 10).map((t: any) => `| ${t.theme} | ${t.avgAccuracy.toFixed(1)}% | ${t.moves} |`).join('\n')}
    `.trim();
    
    setMessages(prev => [...prev, {
      role: 'expandable_table',
      content: '',
      tableTitle: 'Accuracy by Theme',
      tableContent: themeAccuracyTable
    }]);
    
    // 2. Key Point Navigation (expandable)
    const keyPointButtonsTable = `
| Move | Side | Category | Action |
|------|------|----------|--------|
${keyPoints.slice(0, 15).map((kp: any) => {
  const moveNum = Math.floor((kp.ply + 1) / 2);
  const sideName = kp.side_moved === 'white' ? 'White' : 'Black';
  return `| ${moveNum}. ${kp.san} | ${sideName} | ${kp.category} | [Jump](#move-${kp.ply}) |`;
}).join('\n')}
    `.trim();
    
    setMessages(prev => [...prev, {
      role: 'expandable_table',
      content: '',
      tableTitle: `Key Point Navigation (${keyPoints.length} moments)`,
      tableContent: keyPointButtonsTable
    }]);
    
    // Add buttons after expandable sections (fewer buttons, just top 5)
    keyPoints.slice(0, 5).forEach((kp: any) => {
      const moveNum = Math.floor((kp.ply + 1) / 2);
      const sideName = kp.side_moved === 'white' ? 'White' : 'Black';
      setMessages(prev => [...prev, {
        role: 'button',
        content: '',
        buttonAction: `JUMP_TO_PLY_${kp.ply}`,
        buttonLabel: `${sideName} ${moveNum}. ${kp.san} - ${kp.category}`
      }]);
    });
  }
  
  async function startRetryMove() {
    if (!retryMoveData) {
      addSystemMessage("No move to retry");
      return;
    }
    
    // Set up board to position BEFORE the mistake
    const fenBefore = retryMoveData.fenBefore;
    const bestMove = retryMoveData.bestMove;
    
    try {
      const newGame = new Chess(fenBefore);
      setGame(newGame);
      setFen(fenBefore);
      setIsRetryMode(true);
      
      addSystemMessage(`**Retry Challenge: Move ${retryMoveData.moveNumber}**\n\nFind the best move for ${retryMoveData.color === 'w' ? 'White' : 'Black'}. The position has been set up. Make your move on the board!`);
    } catch (error: any) {
      addSystemMessage(`Error setting up retry position: ${error.message}`);
    }
  }
  
  async function checkRetryMove(moveSan: string) {
    if (!retryMoveData || !isRetryMode) return false;
    
    const bestMove = retryMoveData.bestMove;
    
    if (moveSan === bestMove) {
      // Correct!
      addAssistantMessage(`**Excellent!** You found the best move **${bestMove}**! This move is much stronger than the original **${retryMoveData.move}** (difference: ${retryMoveData.cpLoss}cp).`);
      setIsRetryMode(false);
      setRetryMoveData(null);
      
      // Add continue button
      setMessages(prev => [...prev, {
        role: 'button',
        content: '',
        buttonAction: 'NEXT_STEP',
        buttonLabel: 'Continue Review'
      }]);
      
      return true;
    } else {
      // Wrong move
      addAssistantMessage(`**Not quite.** You played **${moveSan}**, but the best move was **${bestMove}**. Try again or click "Show Solution" to see the answer.`);
      
      // Reset board to retry position
      const newGame = new Chess(retryMoveData.fenBefore);
      setGame(newGame);
      setFen(retryMoveData.fenBefore);
      
      // Add buttons
      setMessages(prev => [...prev, {
        role: 'button',
        content: '',
        buttonAction: 'SHOW_SOLUTION',
        buttonLabel: 'Show Solution'
      }]);
      
      return false;
    }
  }
  
  async function showRetrySolution() {
    if (!retryMoveData) return;
    
    // Play the best move
    const newGame = new Chess(retryMoveData.fenBefore);
    const bestMove = newGame.moves({ verbose: true }).find((m: any) => m.san === retryMoveData.bestMove);
    
    if (bestMove) {
      newGame.move(bestMove);
      setGame(newGame);
      setFen(newGame.fen());
      
      // Draw arrow showing the best move
      setAnnotations(prev => ({
        ...prev,
        fen: newGame.fen(),
        arrows: [{ from: bestMove.from, to: bestMove.to, color: '#22c55e' }],
        highlights: []
      }));
      
      addAssistantMessage(`**Solution:** The best move was **${retryMoveData.bestMove}**. This avoids losing ${retryMoveData.cpLoss}cp compared to the original move **${retryMoveData.move}**.`);
    }
    
    setIsRetryMode(false);
    setRetryMoveData(null);
    
    // Add continue button
    setMessages(prev => [...prev, {
      role: 'button',
      content: '',
      buttonAction: 'NEXT_STEP',
      buttonLabel: 'Continue Review'
    }]);
  }
  
  async function jumpToKeyPoint(ply: number) {
    // Find the key point with this ply
    const keyPoint = gameReviewKeyPoints.find((kp: any) => kp.ply === ply);
    
    if (!keyPoint) {
      addSystemMessage(`Could not find move at ply ${ply}`);
      return;
    }
    
    // Update board to FEN after this move
    const targetFen = keyPoint.fen_after;
    const fenBefore = keyPoint.fen_before;
    
    try {
      const newGame = new Chess(targetFen);
      setGame(newGame);
      setFen(targetFen);
      
      // Extract move squares and draw arrow
      const boardBefore = new Chess(fenBefore);
      const chessMove = boardBefore.moves({ verbose: true }).find((m: any) => m.san === keyPoint.san);
      
      if (chessMove) {
        const fromSquare = chessMove.from;
        const toSquare = chessMove.to;
        
        // Draw arrow showing the move
        setAnnotations(prev => ({
          ...prev,
          fen: targetFen,
          arrows: [{ from: fromSquare, to: toSquare, color: '#3b82f6' }],
          highlights: []
        }));
      }
      
      // Show analysis of this position
      const moveNum = Math.floor((ply + 1) / 2);
      const moveSide = keyPoint.side_moved === 'white' ? 'White' : 'Black';
      const evalStr = keyPoint.engine?.played_eval_after_cp ? 
        `${keyPoint.engine.played_eval_after_cp > 0 ? '+' : ''}${(keyPoint.engine.played_eval_after_cp / 100).toFixed(2)}` : 
        'N/A';
      
      // Get themes for this move
      const moveThemes = extractTopThemesFromMove(keyPoint);
      
      addSystemMessage(`Jumped to Move ${moveNum}. ${keyPoint.san} (${moveSide})\nEval: ${evalStr} | Category: ${keyPoint.category}\nLabels: ${keyPoint.key_point_labels.join(', ')}\nThemes: ${moveThemes}`);
    } catch (error: any) {
      addSystemMessage(`Error jumping to position: ${error.message}`);
    }
  }
  
  function calculateTopThemesPerPhase(plyRecords: any[]): { opening: string[], middlegame: string[], endgame: string[] } {
    const themeCountsByPhase: any = {
      opening: {},
      middlegame: {},
      endgame: {}
    };
    
    // Count theme occurrences per phase
    plyRecords.forEach((record: any) => {
      const phase = record.phase || 'opening';
      const analysis = record.analyse;
      
      if (analysis && analysis.theme_scores) {
        // Get both white and black theme scores
        const whiteThemes = analysis.theme_scores.white || {};
        const blackThemes = analysis.theme_scores.black || {};
        
        // Combine and count significant themes (score > 1.0)
        Object.entries(whiteThemes).forEach(([theme, score]: [string, any]) => {
          if (theme !== 'total' && score > 1.0) {
            if (!themeCountsByPhase[phase][theme]) {
              themeCountsByPhase[phase][theme] = 0;
            }
            themeCountsByPhase[phase][theme]++;
          }
        });
        
        Object.entries(blackThemes).forEach(([theme, score]: [string, any]) => {
          if (theme !== 'total' && score > 1.0) {
            if (!themeCountsByPhase[phase][theme]) {
              themeCountsByPhase[phase][theme] = 0;
            }
            themeCountsByPhase[phase][theme]++;
          }
        });
      }
    });
    
    // Get top 3 themes per phase
    const result: any = {
      opening: [],
      middlegame: [],
      endgame: []
    };
    
    (['opening', 'middlegame', 'endgame'] as const).forEach(phase => {
      const themeCounts = themeCountsByPhase[phase];
      const sorted = Object.entries(themeCounts)
        .sort((a: any, b: any) => b[1] - a[1])
        .slice(0, 3)
        .map(([theme, _]: [string, any]) => theme.replace(/_/g, ' '));
      
      result[phase] = sorted.length > 0 ? sorted : ['balanced play'];
    });
    
    return result;
  }
  
  function calculateOverallTopThemes(plyRecords: any[]): Array<{theme: string, count: number, avgScore: number}> {
    const themeData: any = {};
    
    // Aggregate all themes across all moves
    plyRecords.forEach((record: any) => {
      const analysis = record.analyse;
      
      if (analysis && analysis.theme_scores) {
        const whiteThemes = analysis.theme_scores.white || {};
        const blackThemes = analysis.theme_scores.black || {};
        
        // Process both sides' themes
        Object.entries(whiteThemes).forEach(([theme, score]: [string, any]) => {
          if (theme !== 'total' && score > 1.0) {
            if (!themeData[theme]) {
              themeData[theme] = { count: 0, totalScore: 0 };
            }
            themeData[theme].count++;
            themeData[theme].totalScore += score;
          }
        });
        
        Object.entries(blackThemes).forEach(([theme, score]: [string, any]) => {
          if (theme !== 'total' && score > 1.0) {
            if (!themeData[theme]) {
              themeData[theme] = { count: 0, totalScore: 0 };
            }
            themeData[theme].count++;
            themeData[theme].totalScore += score;
          }
        });
      }
    });
    
    // Convert to sorted array
    const themesArray = Object.entries(themeData).map(([theme, data]: [string, any]) => ({
      theme: theme.replace(/_/g, ' '),
      count: data.count,
      avgScore: data.totalScore / data.count
    }));
    
    // Sort by count (most common first)
    themesArray.sort((a, b) => b.count - a.count);
    
    return themesArray;
  }
  
  function extractTopThemesFromMove(keyPoint: any): string {
    // Extract top 3 themes from this specific move's analysis
    const analysis = keyPoint.analyse;
    
    if (!analysis || !analysis.theme_scores) {
      return 'N/A';
    }
    
    const whiteThemes = analysis.theme_scores.white || {};
    const blackThemes = analysis.theme_scores.black || {};
    
    // Get the side that moved
    const themesToUse = keyPoint.side_moved === 'white' ? whiteThemes : blackThemes;
    
    // Get top 3 themes with score > 1.0
    const topThemes = Object.entries(themesToUse)
      .filter(([k, v]: [string, any]) => k !== 'total' && v > 1.0)
      .sort((a: any, b: any) => b[1] - a[1])
      .slice(0, 3)
      .map(([theme, _]: [string, any]) => theme.replace(/_/g, ' '));
    
    return topThemes.length > 0 ? topThemes.join(', ') : 'balanced';
  }
  
  function calculateAccuracyByTheme(plyRecords: any[]): Array<{theme: string, avgAccuracy: number, moves: number}> {
    const themeAccuracyData: any = {};
    
    // Aggregate accuracy by theme
    plyRecords.forEach((record: any) => {
      const analysis = record.analyse;
      const accuracy = record.accuracy_pct || 100;
      
      if (analysis && analysis.theme_scores) {
        const whiteThemes = analysis.theme_scores.white || {};
        const blackThemes = analysis.theme_scores.black || {};
        
        // Get themes for the side that moved
        const themesToUse = record.side_moved === 'white' ? whiteThemes : blackThemes;
        
        // For each significant theme in this move, add to accuracy tracking
        Object.entries(themesToUse).forEach(([theme, score]: [string, any]) => {
          if (theme !== 'total' && score > 1.0) {
            if (!themeAccuracyData[theme]) {
              themeAccuracyData[theme] = { totalAccuracy: 0, count: 0 };
            }
            themeAccuracyData[theme].totalAccuracy += accuracy;
            themeAccuracyData[theme].count++;
          }
        });
      }
    });
    
    // Convert to array and calculate averages
    const themesArray = Object.entries(themeAccuracyData).map(([theme, data]: [string, any]) => ({
      theme: theme.replace(/_/g, ' '),
      avgAccuracy: data.totalAccuracy / data.count,
      moves: data.count
    }));
    
    // Sort by move count (most common themes first)
    themesArray.sort((a, b) => b.moves - a.moves);
    
    return themesArray;
  }

  async function handleReviewGame() {
    // Get the full main line from move tree (from start)
    const mainLine = moveTree.getMainLine();
    const moveCount = mainLine.length;

    if (moveCount === 0) {
      addSystemMessage("No game to review! Play some moves first.");
      return;
    }

    // Build clean PGN from main line
    let cleanPgn = "";
    for (let i = 0; i < mainLine.length; i++) {
      const node = mainLine[i];
      if (i % 2 === 0) {
        cleanPgn += `${node.moveNumber}. `;
      }
      cleanPgn += node.move + " ";
    }
    cleanPgn = cleanPgn.trim();
    
    // Start review with progress tracking
    setIsReviewing(true);
    setReviewProgress(0);
    
    // Simulate progress (since backend doesn't stream)
    const progressInterval = setInterval(() => {
      setReviewProgress(prev => Math.min(95, prev + 5));
    }, 1000);

    try {
      const response = await fetch(`http://localhost:8000/review_game?pgn_string=${encodeURIComponent(cleanPgn)}&side_focus=${reviewSideFocus}&include_timestamps=true`, {
        method: 'POST'
      });
      
      clearInterval(progressInterval);

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Backend returned ${response.status}: ${errorText}`);
      }

      const reviewData = await response.json();

      console.log('========== GAME REVIEW COMPLETE ==========');
      console.log('Full Review Data:', reviewData);
      console.log('Total Plies Analyzed:', reviewData.ply_records?.length || 0);
      console.log('==========================================');

      // Transform new backend format to old frontend format for compatibility
      const moves = (reviewData.ply_records || []).map((record: any, idx: number) => {
        // Convert to White-perspective evals (+ for White advantage, - for Black advantage)
        // Backend returns eval from mover's perspective, we need absolute White perspective
        const isWhiteMove = record.side_moved === 'white';
        
        // evalBefore is always from White's perspective (before the move)
        const evalBeforeWhitePerspective = record.engine.eval_before_cp;
        
        // evalAfter: backend returns played_eval_after_cp from mover's perspective
        // If Black moved, flip the sign to get White perspective
        const evalAfterWhitePerspective = isWhiteMove 
          ? record.engine.played_eval_after_cp 
          : -record.engine.played_eval_after_cp;
        
        return {
          moveNumber: Math.floor((record.ply + 1) / 2),
          move: record.san,
          fen: record.fen_after,
          fenBefore: record.fen_before,
          color: isWhiteMove ? 'w' : 'b',
          evalBefore: evalBeforeWhitePerspective,
          evalAfter: evalAfterWhitePerspective,
          evalChange: Math.abs(evalBeforeWhitePerspective - evalAfterWhitePerspective),
          cpLoss: record.cp_loss,
          quality: record.category === 'critical_best' ? 'best' : record.category,
          accuracy: record.accuracy_pct,
          isCritical: record.category === 'critical_best',
          isMissedWin: false,
          isTheoryMove: record.is_theory,
          openingName: record.opening_name,
          bestMove: record.engine.best_move_san,
          secondBestMove: null,
          gapToSecondBest: record.engine.second_best_gap_cp,
          phase: record.phase,
          advantageLevel: Math.abs(evalAfterWhitePerspective) > 300 ? 'winning' :
                         Math.abs(evalAfterWhitePerspective) > 150 ? 'strong' :
                         Math.abs(evalAfterWhitePerspective) > 50 ? 'slight' : 'equal',
          leftTheory: record.key_point_labels?.includes('theory_exit'),
          enteredMiddlegame: record.phase === 'middlegame' && record.ply > 1,
          crossed100: record.key_point_labels?.some((l: string) => l.includes('threshold_100')),
          crossed200: record.key_point_labels?.some((l: string) => l.includes('threshold_200')),
          crossed300: record.key_point_labels?.some((l: string) => l.includes('threshold_300')),
          // Add full record for detailed analysis
          _fullRecord: record
        };
      });

      // Create compatible accuracy stats
      const accuracyStats = {
        overall: {
          white: reviewData.stats?.white?.overall_accuracy || 100,
          black: reviewData.stats?.black?.overall_accuracy || 100
        },
        opening: {
          white: reviewData.stats?.white?.by_phase?.opening?.accuracy || 100,
          black: reviewData.stats?.black?.by_phase?.opening?.accuracy || 100
        },
        middlegame: {
          white: reviewData.stats?.white?.by_phase?.middlegame?.accuracy || 100,
          black: reviewData.stats?.black?.by_phase?.middlegame?.accuracy || 100
        },
        endgame: {
          white: reviewData.stats?.white?.by_phase?.endgame?.accuracy || 100,
          black: reviewData.stats?.black?.by_phase?.endgame?.accuracy || 100
        }
      };

      // Add back to reviewData for compatibility
      reviewData.moves = moves;
      reviewData.accuracyStats = accuracyStats;
      
      // Store review data for LLM access
      setGameReviewData(reviewData);

      // Update PGN with colored moves and annotations
      updatePGNWithReview(moves);

      // Display review summary
      const theory = moves.filter((m: any) => m.quality === 'theory').length;
      const blunders = moves.filter((m: any) => m.quality === 'blunder').length;
      const mistakes = moves.filter((m: any) => m.quality === 'mistake').length;
      const inaccuracies = moves.filter((m: any) => m.quality === 'inaccuracy').length;
      const excellent = moves.filter((m: any) => m.quality === 'excellent').length;
      const good = moves.filter((m: any) => m.quality === 'good').length;
      const best = moves.filter((m: any) => m.quality === 'best').length;
      
      // Get opening name from first theory move
      const firstTheoryMove = moves.find((m: any) => m.openingName);
      const openingName = firstTheoryMove?.openingName || "Unknown Opening";
      
      // Find key moments
      const leftTheoryMove = moves.find((m: any) => m.leftTheory);
      const enteredMiddlegameMove = moves.find((m: any) => m.enteredMiddlegame);
      const criticalMovesList = moves.filter((m: any) => m.isCritical);
      const missedWinsList = moves.filter((m: any) => m.isMissedWin);
      
      // Find advantage threshold crossings
      const crossed100 = moves.filter((m: any) => m.crossed100);
      const crossed200 = moves.filter((m: any) => m.crossed200);
      const crossed300 = moves.filter((m: any) => m.crossed300);
      
      // Use accuracy stats already created above
      const avgWhiteAccuracy = accuracyStats.overall.white.toFixed(1);
      const avgBlackAccuracy = accuracyStats.overall.black.toFixed(1);
      
      // Build PGN with accuracy annotations
      let pgnWithAccuracy = "";
      for (let i = 0; i < moves.length; i++) {
        const m = moves[i];
        if (m.color === 'w') {
          pgnWithAccuracy += `${m.moveNumber}. `;
        }
        pgnWithAccuracy += `${m.move} {${m.accuracy}%} `;
        if (m.color === 'b') {
          pgnWithAccuracy += "\n";
        }
      }
      pgnWithAccuracy = pgnWithAccuracy.trim();

      // Count moves per phase
      const openingMoves = moves.filter((m: any) => m.phase === 'opening').length;
      const middlegameMoves = moves.filter((m: any) => m.phase === 'middlegame').length;
      const endgameMoves = moves.filter((m: any) => m.phase === 'endgame').length;

      let summary = `
Game Review Complete!

Opening: ${openingName}

Move Quality:
Theory: ${theory}
✓ Best: ${best}
✓ Excellent: ${excellent}
✓ Good: ${good}
⚠ Inaccuracies: ${inaccuracies}
❌ Mistakes: ${mistakes}
❌ Blunders: ${blunders}

Overall Accuracy:
⚪ White: ${avgWhiteAccuracy}%
⚫ Black: ${avgBlackAccuracy}%

Phase-Based Accuracy:

Opening (${openingMoves} moves):
  ⚪ White: ${accuracyStats.opening.white.toFixed(1)}%
  ⚫ Black: ${accuracyStats.opening.black.toFixed(1)}%

⚔️ Middlegame (${middlegameMoves} moves):
  ⚪ White: ${accuracyStats.middlegame.white.toFixed(1)}%
  ⚫ Black: ${accuracyStats.middlegame.black.toFixed(1)}%

👑 Endgame (${endgameMoves} moves):
  ⚪ White: ${accuracyStats.endgame.white.toFixed(1)}%
  ⚫ Black: ${accuracyStats.endgame.black.toFixed(1)}%

The PGN viewer has been updated with detailed analysis!`;

      // Add game tags if present
      const gameTags = reviewData.gameTags || [];
      if (gameTags.length > 0) {
        summary += `\n\n--- Game Characteristics ---`;
        gameTags.forEach((tag: any) => {
          summary += `\n\n${tag.name}\n   ${tag.description}`;
        });
      }

      summary += `\n\n--- Key Moments ---`;

      if (leftTheoryMove) {
        summary += `\n\nLeft Opening Theory: ${leftTheoryMove.moveNumber}. ${leftTheoryMove.move}`;
      }
      
      if (criticalMovesList.length > 0) {
        summary += `\n\nCritical Moves (gap >50cp to 2nd best):`;
        criticalMovesList.forEach((m: any) => {
          summary += `\n  ${m.moveNumber}. ${m.move} (${m.evalAfter > 0 ? '+' : ''}${m.evalAfter}cp)`;
        });
      }
      
      if (missedWinsList.length > 0) {
        summary += `\n\nMissed Wins:`;
        missedWinsList.forEach((m: any) => {
          summary += `\n  ${m.moveNumber}. ${m.move} (${m.evalAfter > 0 ? '+' : ''}${m.evalAfter}cp)`;
        });
      }
      
      if (crossed100.length > 0 || crossed200.length > 0 || crossed300.length > 0) {
        summary += `\n\nAdvantage Shifts:`;
        
        if (crossed100.length > 0) {
          summary += `\n  ±100cp threshold:`;
          crossed100.forEach((m: any) => {
            const side = m.evalAfter > 0 ? 'White' : 'Black';
            summary += `\n    ${m.moveNumber}. ${m.move} (${side} gains advantage)`;
          });
        }
        
        if (crossed200.length > 0) {
          summary += `\n  ±200cp threshold:`;
          crossed200.forEach((m: any) => {
            const side = m.evalAfter > 0 ? 'White' : 'Black';
            summary += `\n    ${m.moveNumber}. ${m.move} (${side} strong advantage)`;
          });
        }
        
        if (crossed300.length > 0) {
          summary += `\n  ±300cp threshold:`;
          crossed300.forEach((m: any) => {
            const side = m.evalAfter > 0 ? 'White' : 'Black';
            summary += `\n    ${m.moveNumber}. ${m.move} (${side} winning)`;
          });
        }
      }
      
      // Add full PGN with accuracy at the end
      summary += `\n\n--- Full PGN with Accuracy ---\n\n${pgnWithAccuracy}`;
      
      summary = summary.trim();

      // Don't reset board - keep current position
      // (User reported: board should stay at current position, not jump back)
      
      // Generate LLM summary
      setReviewProgress(100);
      
      // Presentation mode: Talk Through or Summary Tables
      if (reviewPresentationMode === "tables") {
        // Summary Tables Mode - show all data at once
        displaySummaryTables(reviewData, moves, accuracyStats, openingName);
        setIsReviewing(false);
        return;
      }
      
      // Otherwise: Talk Through Mode (default)
      
      // Determine game result based on final eval
      const finalEval = moves[moves.length - 1]?.evalAfter || 0;
      let result = "drawn";
      let winner = "Neither side";
      if (finalEval > 300) {
        result = "won by White";
        winner = "White";
      } else if (finalEval < -300) {
        result = "won by Black";
        winner = "Black";
      }
      
      // Build LLM prompt
      const tagDescriptions = gameTags.map((t: any) => `${t.name} (${t.description})`).join(", ");
      const tagSummary = gameTags.length > 0 ? tagDescriptions : "a balanced positional game";
      
      const llmPrompt = `You are analyzing a chess game. Here's the summary:

Opening: ${openingName}
Game Tags: ${tagSummary}
Result: ${result}

White Accuracy: ${avgWhiteAccuracy}%
Black Accuracy: ${avgBlackAccuracy}%

Key Statistics:
- Theory moves: ${theory}
- Best moves: ${best}
- Excellent moves: ${excellent}
- Good moves: ${good}
- Inaccuracies: ${inaccuracies}
- Mistakes: ${mistakes}
- Blunders: ${blunders}

Write a concise 2-3 sentence summary of this game, mentioning:
1. The game type/tags and opening
2. Who won and why (based on accuracy and key moments)

Be conversational and natural. Don't use bullet points. Don't ask questions at the end.`;

      // Call LLM for summary
      callLLM([
        { role: "system", content: "You are a helpful chess coach providing game analysis." },
        { role: "user", content: llmPrompt }
      ], 0.7, "gpt-4o-mini").then(llmResult => {
        // Add LLM response with metadata
        const {content: llmResponse} = llmResult;
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: llmResponse,
          meta: {
            structuredAnalysis: summary,
            rawEngineData: reviewData
          }
        }]);
        
        // Add evaluation graph as a special message
        setMessages(prev => [...prev, {
          role: 'graph',
          content: '',
          graphData: moves
        }]);
        
        // Store walkthrough data for later
        setWalkthroughData({
          moves,
          reviewData,
          openingName,
          gameTags,
          avgWhiteAccuracy,
          avgBlackAccuracy,
          accuracyStats,
          leftTheoryMove,
          criticalMovesList,
          missedWinsList,
          crossed100,
          crossed200,
          crossed300
        });
        
        // Add walkthrough button
        setMessages(prev => [...prev, {
          role: 'button',
          content: '',
          buttonAction: 'START_WALKTHROUGH',
          buttonLabel: '🎓 Start Guided Walkthrough'
        }]);
        
        setTimeout(() => {
          setIsReviewing(false);
          setReviewProgress(0);
        }, 500);
      }).catch(err => {
        console.error("LLM summary failed:", err);
        // Fallback to showing the summary directly
        addAssistantMessage(summary);
        
        setMessages(prev => [...prev, {
          role: 'graph',
          content: '',
          graphData: moves
        }]);
        
        setTimeout(() => {
          setIsReviewing(false);
          setReviewProgress(0);
        }, 500);
      });
      
    } catch (err: any) {
      clearInterval(progressInterval);
      setIsReviewing(false);
      setReviewProgress(0);
      addSystemMessage(`Review failed: ${err.message}`);
    }
  }

  function updatePGNWithReview(moves: any[]) {
    if (!moves || moves.length === 0) return;

    // Update the move tree with review data
    const newTree = moveTree.clone();

    // Map moves back to tree nodes by move number
    const moveMap = new Map();
    moves.forEach(move => {
      moveMap.set(move.moveNumber, move);
    });

    // Update tree nodes with review data
    newTree.root.children.forEach((child, index) => {
      updateNodeWithReview(child, moveMap);
    });

    setMoveTree(newTree);
    const newPgn = newTree.toPGN();
    setPgn(newPgn);
    setTreeVersion(v => v + 1);
  }

  function updateNodeWithReview(node: any, moveMap: Map<number, any>) {
    // Find matching review data by move number AND move text
    let reviewData = null;
    for (const [moveNum, data] of moveMap.entries()) {
      if (data.moveNumber === node.moveNumber && data.move === node.move) {
        reviewData = data;
        break;
      }
    }
    
    if (reviewData) {
      // Store quality data directly on node - this persists through state updates
      // Format eval with mate notation if applicable
      const evalAfter = reviewData.evalAfter || 0;
      const formatted = formatEval(evalAfter);
      
      // Display format: "+0.45" or "-1.23" or "+M8" or "-M8"
      if (formatted.startsWith('M')) {
        // Mate score
        // formatEval returns "M8" for positive, "M-8" for negative
        // We want "+M8" for white winning, "-M8" for black winning
        if (formatted.includes('-')) {
          // Already has negative sign, just ensure it's "-M8" format
          node.comment = `-M${formatted.split('-')[1]}`;
        } else {
          // Positive mate, add + sign
          node.comment = `+${formatted}`;
        }
      } else {
        // Regular centipawn score - convert to pawns with +/- prefix
        const pawns = (evalAfter / 100).toFixed(2);
        node.comment = evalAfter >= 0 ? `+${pawns}` : pawns;
      }
      
      node.quality = reviewData.quality;
      node.isCritical = reviewData.isCritical;
      node.isMissedWin = reviewData.isMissedWin;
      node.reviewData = reviewData; // Store full data
      node.nags = [];
    }

    node.children.forEach((child: any) => updateNodeWithReview(child, moveMap));
  }

  // ============================================================================
  // LESSON SYSTEM HANDLERS
  // ============================================================================
  
  async function handleStartLesson(description: string, level: number) {
    setShowLessonBuilder(false);
    addSystemMessage("🎓 Generating your custom lesson...");
    
    try {
      // Generate lesson plan
      const response = await fetch("http://localhost:8000/generate_lesson", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ description, target_level: level, count: 5 })
      });
      
      if (!response.ok) {
        throw new Error("Failed to generate lesson plan");
      }
      
      const plan = await response.json();
      
      addAssistantMessage(`**${plan.title}**\n\n${plan.description}\n\nGenerating ${plan.total_positions} training positions...`);
      
      // Generate positions for ALL sections and topics
      const allPositions: any[] = [];
      
      for (const section of plan.sections) {
        const positionsPerTopic = section.positions_per_topic || 2;
        
        for (const topicCode of section.topics) {
          try {
            const posResponse = await fetch(`http://localhost:8000/generate_positions?topic_code=${topicCode}&count=${positionsPerTopic}`, {
              method: "POST"
            });
            
            if (posResponse.ok) {
              const positionsData = await posResponse.json();
              if (positionsData.positions && positionsData.positions.length > 0) {
                allPositions.push(...positionsData.positions);
              }
            } else {
              console.error(`Failed to generate positions for topic ${topicCode}`);
            }
          } catch (err) {
            console.error(`Error generating positions for ${topicCode}:`, err);
          }
        }
      }
      
      if (allPositions.length === 0) {
        throw new Error("No positions were generated");
      }
      
      addSystemMessage(`✅ Generated ${allPositions.length} training positions with computer-verified ideal lines!`);
      
      setCurrentLesson({
        plan,
        positions: allPositions,
        currentIndex: 0
      });
      
      setLessonProgress({ current: 0, total: allPositions.length });
      setLessonMode(true);
      
      // Load first position
      await loadLessonPosition(allPositions[0], 0, allPositions.length);
      
    } catch (error) {
      console.error("Lesson generation error:", error);
      addSystemMessage("Failed to generate lesson. Please try again.");
    }
  }

  async function handleCreateOpeningLesson() {
    if (!openingQuery.trim()) {
      addSystemMessage("⚠️ Please enter an opening name or moves");
      return;
    }
    
    setShowOpeningModal(false);
    addSystemMessage(`Building opening lesson for "${openingQuery}"...`);
    
    try {
      const response = await fetch(`http://localhost:8000/generate_opening_lesson`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({query: openingQuery})
      });
      
      if (!response.ok) {
        throw new Error("Failed to generate opening lesson");
      }
      
      const lessonPlan = await response.json();
      
      // Extract all checkpoint FENs from sections
      const checkpointFens: any[] = [];
      
      for (const section of lessonPlan.sections) {
        if (section.type === "walkthrough" && section.checkpoints) {
          checkpointFens.push(...section.checkpoints);
        } else if (section.type === "alternates" && section.branches) {
          for (const branch of section.branches) {
            if (branch.checkpoints) {
              checkpointFens.push(...branch.checkpoints.slice(0, 2)); // Max 2 per alt
            }
          }
        }
      }
      
      if (checkpointFens.length === 0) {
        addSystemMessage("⚠️ No practice positions were generated. Try a different opening.");
        return;
      }
      
      addSystemMessage(`✅ Created lesson: ${lessonPlan.title}`);
      addSystemMessage(`📚 ${checkpointFens.length} checkpoint positions to practice`);
      
      setCurrentLesson({
        plan: lessonPlan,
        positions: checkpointFens,
        currentIndex: 0,
        type: "opening"  // Mark as opening lesson
      });
      
      setLessonMode(true);
      setLessonProgress({ current: 0, total: checkpointFens.length });
      
      // Load first position
      await loadOpeningPosition(checkpointFens[0], lessonPlan, 0, checkpointFens.length);
      
    } catch (error: any) {
      console.error("Opening lesson error:", error);
      addSystemMessage(`❌ Error: ${error.message}`);
    }
  }

  async function loadOpeningPosition(checkpoint: any, lessonPlan: any, index: number, total: number) {
    const {fen, objective, popular_replies} = checkpoint;
    
    // Load position on board
    const newGame = new Chess(fen);
    setGame(newGame);
    
    // Add context message
    addSystemMessage(`**Position ${index + 1} of ${total}**`);
    addSystemMessage(objective);
    
    if (popular_replies && popular_replies.length > 0) {
      const repliesText = popular_replies
        .map((r: any) => `${r.san} (${(r.pop * 100).toFixed(0)}%)`)
        .join(", ");
      addSystemMessage(`Popular replies: ${repliesText}`);
    }
    
    // Add navigation buttons
    setTimeout(() => {
      if (index > 0) {
        setMessages(prev => [...prev, {
          role: 'button',
          content: '',
          buttonLabel: '⬅️ Previous Position',
          buttonAction: 'LESSON_PREVIOUS'
        }]);
      }
      
      if (index < total - 1) {
        setMessages(prev => [...prev, {
          role: 'button',
          content: '',
          buttonLabel: 'Skip Position',
          buttonAction: 'LESSON_SKIP'
        }]);
      }
    }, 1000);
  }

  async function checkOpeningMove(moveSan: string, currentFen: string) {
    if (!currentLesson || !currentLesson.plan) return;
    
    try {
      const lessonId = currentLesson.plan.lesson_id;
      
      const response = await fetch(
        `http://localhost:8000/check_opening_move?fen=${encodeURIComponent(currentFen)}&move_san=${moveSan}&lesson_id=${lessonId}`,
        {method: "POST"}
      );
      
      if (!response.ok) {
        throw new Error("Failed to check opening move");
      }
      
      const result = await response.json();
      
      if (result.is_popular) {
        addSystemMessage(`✅ ${result.feedback}`);
        
        // Move to next checkpoint after a correct move
        setTimeout(async () => {
          const nextIndex = lessonProgress.current + 1;
          if (nextIndex < currentLesson.positions.length) {
            setLessonProgress({ current: nextIndex, total: lessonProgress.total });
            await loadOpeningPosition(
              currentLesson.positions[nextIndex],
              currentLesson.plan,
              nextIndex,
              currentLesson.positions.length
            );
          } else {
            addSystemMessage("🎉 Congratulations! You've completed the opening lesson!");
            setLessonMode(false);
          }
        }, 2000);
      } else {
        addSystemMessage(`⚠️ ${result.feedback}`);
        
        if (result.popular_alternatives && result.popular_alternatives.length > 0) {
          const alts = result.popular_alternatives
            .slice(0, 3)
            .map((a: any) => `${a.san} (${(a.pop * 100).toFixed(0)}%)`)
            .join(", ");
          addSystemMessage(`More popular moves: ${alts}`);
        }
      }
    } catch (error: any) {
      console.error("Opening move check error:", error);
      addSystemMessage(`Error checking move: ${error.message}`);
    }
  }
  
  async function skipLessonPosition() {
    if (!currentLesson) return;
    
    const nextIndex = lessonProgress.current + 1;
    if (nextIndex >= currentLesson.positions.length) {
      addSystemMessage("You've reached the last position in this lesson!");
      return;
    }
    
    addSystemMessage("⏭️ Skipping to next position...");
    setLessonProgress({ current: nextIndex, total: lessonProgress.total });
    await loadLessonPosition(currentLesson.positions[nextIndex], nextIndex, lessonProgress.total);
  }
  
  async function previousLessonPosition() {
    if (!currentLesson) return;
    
    const prevIndex = lessonProgress.current - 1;
    if (prevIndex < 0) {
      addSystemMessage("You're already at the first position!");
      return;
    }
    
    addSystemMessage("⏮️ Going back to previous position...");
    setLessonProgress({ current: prevIndex, total: lessonProgress.total });
    await loadLessonPosition(currentLesson.positions[prevIndex], prevIndex, lessonProgress.total);
  }
  
  async function loadLessonPosition(pos: any, index: number, total: number) {
    setCurrentLessonPosition(pos);
    
    // Set board to position FEN
    setFen(pos.fen);
    const newGame = new Chess(pos.fen);
    setGame(newGame);
    
    // Reset move tree
    const newTree = new MoveTree();
    setMoveTree(newTree);
    setTreeVersion(v => v + 1);
    
    // Reset lesson line tracking
    setLessonMoveIndex(0);
    setIsOffMainLine(false);
    setMainLineFen(pos.fen);
    
    // Generate LLM introduction to the position
    const introPrompt = `You are teaching a chess lesson. Introduce this position to the student:

Topic: ${pos.topic_name}
Objective: ${pos.objective}
Position: ${pos.fen}

Write 2-3 sentences to introduce this training position. Be encouraging and explain what they should look for. Do NOT reveal the specific moves to play.`;

    try {
      const intro = await callLLM([
        { role: "system", content: "You are an encouraging chess coach." },
        { role: "user", content: introPrompt }
      ]);
      
      addAssistantMessage(`**📚 Lesson Position ${index + 1}/${total}**\n\n${intro}`);
    } catch (err) {
      addAssistantMessage(`**📚 Lesson Position ${index + 1}/${total}**\n\n${pos.objective}`);
    }
    
    // Show objective card in chat
    setTimeout(() => {
      addSystemMessage(`💡 **Objective:** ${pos.objective}\n\n**Hints:**\n${pos.hints.map((h: string) => `• ${h}`).join('\n')}`);
    }, 1000);
    
    // Add navigation buttons after a short delay
    setTimeout(() => {
      if (index > 0) {
        // Add "Previous Position" button
        setMessages(prev => [...prev, {
          role: 'button',
          content: '',
          buttonLabel: '⬅️ Previous Position',
          buttonAction: 'LESSON_PREVIOUS'
        }]);
      }
      
      if (index < total - 1) {
        // Add "Skip Position" button
        setMessages(prev => [...prev, {
          role: 'button',
          content: '',
          buttonLabel: 'Skip Position',
          buttonAction: 'LESSON_SKIP'
        }]);
      }
    }, 1500);
  }
  
  async function checkLessonMove(moveSan: string, currentFen: string) {
    // Check if this is an opening lesson
    if (currentLesson && currentLesson.type === "opening") {
      await checkOpeningMove(moveSan, currentFen);
      return;
    }
    
    if (!currentLessonPosition || !currentLessonPosition.ideal_line) return;
    
    addSystemMessage("Checking your move...");
    
    try {
      const idealLine = currentLessonPosition.ideal_line;
      const playerSide = currentLessonPosition.side; // "white" or "black"
      const expectedMove = idealLine[lessonMoveIndex];
      
      // Determine if this move should be from the player based on whose turn it is
      const currentBoard = new Chess(currentFen);
      const isPlayerTurn = (playerSide === "white" && currentBoard.turn() === 'w') || 
                          (playerSide === "black" && currentBoard.turn() === 'b');
      
      // Check if move matches the ideal line
      const isOnMainLine = moveSan === expectedMove;
      
      if (isOnMainLine) {
        // Correct move on the main line!
        const newIndex = lessonMoveIndex + 1;
        setLessonMoveIndex(newIndex);
        
        // Generate encouraging feedback only for player moves
        if (isPlayerTurn) {
          const recentMessages = messages.slice(-3).map(m => `${m.role}: ${m.content}`).join("\n");
          
          const feedbackPrompt = `The student played the correct move: ${moveSan}.

Recent chat context:
${recentMessages}

Give very brief, encouraging feedback (1-2 sentences) about why this move is good. Be specific to the move.`;

          const llmFeedback = await callLLM([
            { role: "system", content: "You are an encouraging chess coach. Be brief and specific." },
            { role: "user", content: feedbackPrompt }
          ]);
          
          addAssistantMessage(`✅ **Correct!** ${llmFeedback}`);
        }
        
        // Check if there's a next move in the ideal line (engine's response)
        if (newIndex < idealLine.length) {
          const nextMove = idealLine[newIndex];
          
          console.log("[LESSON] newIndex:", newIndex, "nextMove:", nextMove, "idealLine.length:", idealLine.length);
          console.log("[LESSON] playerSide:", playerSide);
          
          // Wait for state to update, then check if we need to auto-play
          setTimeout(() => {
            try {
              // Recreate board from current FEN to get the actual position after player's move
              // We need to get the FEN from the DOM or use a fresh board
              const tempGame = new Chess(currentFen);
              tempGame.move(moveSan); // Apply the player's move that was just made
              
              console.log("[LESSON] Board after player move:", tempGame.fen());
              console.log("[LESSON] Turn is:", tempGame.turn());
              
              // Check if next move is the opponent's
              const isNextMoveOpponent = (playerSide === "white" && tempGame.turn() === 'b') || 
                                         (playerSide === "black" && tempGame.turn() === 'w');
              
              console.log("[LESSON] isNextMoveOpponent:", isNextMoveOpponent);
              
              if (isNextMoveOpponent) {
                // Auto-play the opponent's move
                console.log("[LESSON] Auto-playing opponent move:", nextMove);
                const move = tempGame.move(nextMove);
                if (move) {
                  // Update board state
                  setFen(tempGame.fen());
                  setGame(tempGame);
                  
                  // Update move tree
                  moveTree.addMove(move.san, tempGame.fen());
                  setTreeVersion(v => v + 1);
                  
                  // Increment the lesson move index for the engine move
                  setLessonMoveIndex(newIndex + 1);
                  
                  addSystemMessage(`Opponent plays: **${move.san}**`);
                  
                  // Check if line is completed after engine move
                  if (newIndex + 1 >= idealLine.length) {
                    addAssistantMessage("🎉 **Perfect!** You've completed the ideal line for this position!");
                    
                    // Move to next position
                    setTimeout(async () => {
                      const nextPosIndex = lessonProgress.current + 1;
                      
                      if (nextPosIndex < lessonProgress.total && currentLesson) {
                        setLessonProgress({ current: nextPosIndex, total: lessonProgress.total });
                        await loadLessonPosition(currentLesson.positions[nextPosIndex], nextPosIndex, lessonProgress.total);
                      } else {
                        // Lesson complete!
                        addAssistantMessage("🏆 **Lesson Complete!** You've successfully completed all positions. Excellent work!");
                        setLessonMode(false);
                        setCurrentLesson(null);
                        setCurrentLessonPosition(null);
                      }
                    }, 2000);
                  }
                } else {
                  console.error("[LESSON] Failed to apply opponent move:", nextMove);
                }
              } else {
                console.log("[LESSON] Not opponent's turn, skipping auto-play");
              }
            } catch (err) {
              console.error("Failed to auto-play opponent move:", err);
            }
          }, 1500);
        } else {
          // Line completed (no more moves)
          addAssistantMessage("🎉 **Perfect!** You've completed the ideal line for this position!");
          
          setTimeout(async () => {
            const nextPosIndex = lessonProgress.current + 1;
            
            if (nextPosIndex < lessonProgress.total && currentLesson) {
              setLessonProgress({ current: nextPosIndex, total: lessonProgress.total });
              await loadLessonPosition(currentLesson.positions[nextPosIndex], nextPosIndex, lessonProgress.total);
            } else {
              addAssistantMessage("🏆 **Lesson Complete!** You've successfully completed all positions. Excellent work!");
              setLessonMode(false);
              setCurrentLesson(null);
              setCurrentLessonPosition(null);
            }
          }, 2000);
        }
        
      } else {
        // Move deviates from main line - evaluate it
        const response = await fetch(`http://localhost:8000/check_lesson_move?fen=${encodeURIComponent(currentFen)}&move_san=${encodeURIComponent(moveSan)}`, {
          method: "POST"
        });
        
        if (!response.ok) {
          throw new Error("Failed to check move");
        }
        
        const result = await response.json();
        
        // Mark as off main line
        if (!isOffMainLine) {
          setIsOffMainLine(true);
          setMainLineFen(currentFen);
        }
        
        // Run full analyze_move on the deviation
        addSystemMessage("Analyzing your move...");
        const analyzeMoveResponse = await fetch(
          `http://localhost:8000/analyze_move?fen=${encodeURIComponent(currentFen)}&move_san=${encodeURIComponent(moveSan)}&depth=18`,
          { method: "POST" }
        );
        
        let moveAnalysis = null;
        if (analyzeMoveResponse.ok) {
          moveAnalysis = await analyzeMoveResponse.json();
          console.log("[LESSON DEVIATION] analyze_move response:", JSON.stringify(moveAnalysis, null, 2));
        } else {
          console.error("[LESSON DEVIATION] analyze_move failed:", analyzeMoveResponse.status);
        }
        
        // Format the deviation message using analyze_move data
        let deviationMessage = `**Deviation:** You played **${moveSan}** (expected: **${expectedMove}**)\n\n`;
        
        if (moveAnalysis) {
          // Adapt new backend format
          const cpLoss = moveAnalysis.cp_loss || 0;
          const playedEval = moveAnalysis.eval_after_played || moveAnalysis.eval_after_move || 0;
          const bestEval = moveAnalysis.eval_after_best || 0;
          const bestMove = moveAnalysis.best_move || expectedMove;
          
          deviationMessage += `**Your move (${moveSan}):** ${playedEval > 0 ? '+' : ''}${(playedEval / 100).toFixed(2)}\n`;
          deviationMessage += `**Best move (${bestMove}):** ${bestEval > 0 ? '+' : ''}${(bestEval / 100).toFixed(2)}\n`;
          
          // Determine quality label
          let qualityLabel = "Move";
          if (cpLoss < 10) qualityLabel = "Excellent alternative";
          else if (cpLoss < 30) qualityLabel = "Good alternative";
          else if (cpLoss < 50) qualityLabel = "Slight inaccuracy";
          else if (cpLoss < 100) qualityLabel = "Inaccuracy";
          else if (cpLoss < 200) qualityLabel = "Mistake";
          else qualityLabel = "Blunder";
          
          deviationMessage += `**Assessment:** ${qualityLabel} (${cpLoss}cp loss)\n\n`;
          
          // Extract tag changes from analysis
          const differences: string[] = [];
          
          if (moveAnalysis.analysis) {
            const afPlayed = moveAnalysis.analysis.af_played;
            const afBest = moveAnalysis.analysis.af_best;
            
            if (afPlayed && afBest) {
              const tagsPlayed = new Set((afPlayed.tags || []).map((t: any) => t.tag_name));
              const tagsBest = new Set((afBest.tags || []).map((t: any) => t.tag_name));
              
              tagsBest.forEach((tag: unknown) => {
                const tagStr = tag as string;
                if (!tagsPlayed.has(tagStr)) {
                  differences.push(`Best move gains ${tagStr.replace(/tag\./g, '')}`);
                }
              });
            }
          }
          
          if (differences.length > 0) {
            deviationMessage += `**Key differences:**\n`;
            differences.slice(0, 3).forEach((diff: string) => {
              deviationMessage += `• ${diff}\n`;
            });
            deviationMessage += `\n`;
          }
          
          // Add summary if available (legacy support)
          if (moveAnalysis.summary) {
            deviationMessage += `**Your move:** ${moveAnalysis.summary}\n`;
          }
        } else {
          // Fallback if analysis failed or incomplete
          deviationMessage += `**CP Loss:** ${result.cp_loss}cp\n\n`;
          deviationMessage += `This move deviates from the optimal line. The expected move was **${expectedMove}**.`;
        }
        
        addAssistantMessage(deviationMessage);
        
        // Get LLM commentary on the deviation
        if (moveAnalysis && moveAnalysis.playedMoveReport && moveAnalysis.bestMoveReport) {
          const recentMessages = messages.slice(-3).map(m => `${m.role}: ${m.content}`).join("\n");
          
          const llmPrompt = `The student deviated from the ideal lesson line.

Position: ${currentFen}
Expected move: ${expectedMove}
Student played: ${moveSan}

Analysis results:
- Student's move evaluation: ${moveAnalysis.playedMoveReport.evalAfter}cp
- Best move evaluation: ${moveAnalysis.bestMoveReport.evalAfter}cp
- CP Loss: ${Math.abs((moveAnalysis.bestMoveReport.evalAfter || 0) - (moveAnalysis.playedMoveReport.evalAfter || 0))}cp

Recent context:
${recentMessages}

Full analysis data:
${JSON.stringify(moveAnalysis, null, 2)}

Provide 2-3 sentences of natural language commentary explaining why this deviation is problematic or acceptable, what the key difference is between the moves, and what the student should focus on.`;

          const llmResult = await callLLM([
            { role: "system", content: "You are a chess coach providing clear, educational feedback on move choices." },
            { role: "user", content: llmPrompt }
          ], 0.7, "gpt-4o-mini");
          
          const {content: llmCommentary} = llmResult;
          
          addAssistantMessage(llmCommentary, {
            moveAnalysis,
            rawAnalysisData: moveAnalysis,
            deviationContext: {
              fen: currentFen,
              expectedMove,
              playedMove: moveSan,
              cpLoss: Math.abs((moveAnalysis.bestMoveReport.evalAfter || 0) - (moveAnalysis.playedMoveReport.evalAfter || 0))
            }
          });
        }
        
        // AI ALWAYS responds to the alternate move - using Stockfish to play best response
        setTimeout(async () => {
          try {
            // Calculate the position AFTER the player's move by applying it to currentFen
            // We can't rely on game.fen() because React state updates are asynchronous
            const tempBoard = new Chess(currentFen);
            const playerMove = tempBoard.move(moveSan);
            
            if (!playerMove) {
              console.error("[LESSON DEVIATION] Failed to apply player move:", moveSan);
              return;
            }
            
            const currentPosition = tempBoard.fen();
            
            console.log("[LESSON DEVIATION] Position before player move:", currentFen);
            console.log("[LESSON DEVIATION] Player played:", moveSan);
            console.log("[LESSON DEVIATION] Position after player move:", currentPosition);
            console.log("[LESSON DEVIATION] Turn is now:", tempBoard.turn());
            
            // Determine whose turn it is now (should be opponent's turn)
            const isOpponentTurn = (playerSide === "white" && tempBoard.turn() === 'b') || 
                                   (playerSide === "black" && tempBoard.turn() === 'w');
            
            console.log("[LESSON DEVIATION] Player side:", playerSide);
            console.log("[LESSON DEVIATION] Is opponent's turn?", isOpponentTurn);
            
            if (isOpponentTurn) {
              // Get engine's best response using Stockfish
              const engineResponse = await fetch(`http://localhost:8000/analyze_position?fen=${encodeURIComponent(currentPosition)}&lines=1&depth=16`);
              
              if (engineResponse.ok) {
                const analysis = await engineResponse.json();
                if (analysis.candidate_moves && analysis.candidate_moves.length > 0) {
                  const bestResponse = analysis.candidate_moves[0].move;
                  
                  console.log("[LESSON DEVIATION] Engine's best response:", bestResponse);
                  
                  // Play the engine's response on the tempBoard
                  const move = tempBoard.move(bestResponse);
                  if (move) {
                    setFen(tempBoard.fen());
                    setGame(tempBoard);
                    moveTree.addMove(move.san, tempBoard.fen());
                    setTreeVersion(v => v + 1);
                    
                    addSystemMessage(`Opponent responds with best move: **${move.san}**`);
                  } else {
                    console.error("[LESSON DEVIATION] Failed to apply move:", bestResponse);
                  }
                } else {
                  console.error("[LESSON DEVIATION] No candidate moves in analysis");
                }
              } else {
                console.error("[LESSON DEVIATION] Engine response failed:", engineResponse.status);
              }
            } else {
              console.log("[LESSON DEVIATION] Not opponent's turn, skipping auto-response");
            }
          } catch (err) {
            console.error("Failed to get engine response:", err);
          }
        }, 1500);
      }
      
    } catch (error) {
      console.error("Move check error:", error);
      addSystemMessage("Failed to check move. Please try again.");
    }
  }
  
  function returnToMainLine() {
    if (!mainLineFen || !currentLessonPosition) return;
    
    // Reset board to the FEN where they left the main line
    setFen(mainLineFen);
    const newGame = new Chess(mainLineFen);
    setGame(newGame);
    
    // Reset move tree to that position
    const newTree = new MoveTree();
    setMoveTree(newTree);
    setTreeVersion(v => v + 1);
    
    // Reset lesson state
    setIsOffMainLine(false);
    
    addSystemMessage("♻️ Returned to main line. Try again!");
  }
  
  // Override handleMove in lesson mode
  const oldHandleMove = handleMove;
  const wrappedHandleMove = lessonMode && currentLessonPosition ? 
    (from: string, to: string, promotion?: string) => {
      const currentFenBeforeMove = fen; // Capture FEN before move
      const tempGame = new Chess(fen);
      const move = tempGame.move({ from, to, promotion });
      
      if (move) {
        oldHandleMove(from, to, promotion);
        checkLessonMove(move.san, currentFenBeforeMove);
      }
    } : handleMove;

  return (
    <main className="app-container">
      <header className="app-header">
        <div className="header-left">
          <h1>♟️ Chess GPT</h1>
          <div className="header-subtitle">Intelligent Chess Assistant</div>
        </div>
        <div className="header-actions">
          <button 
            className="personal-review-trigger"
            onClick={() => setShowPersonalReview(true)}
          >
            🎯 Personal Review
          </button>
          <button 
            className="training-trigger"
            onClick={() => setShowTraining(true)}
          >
            📚 Training & Drills
          </button>
        </div>
      </header>

      <div className="main-content">
        <div className="board-panel">
          {lessonMode && (
            <div className="lesson-mode-indicator">
              📚 Lesson Mode {isOffMainLine && <span style={{color: '#f59e0b'}}>(Off Main Line)</span>}
            </div>
          )}
          
          {lessonMode && isOffMainLine && (
            <button 
              className="return-to-main-line-button"
              onClick={returnToMainLine}
            >
              ♻️ Return to Main Line
            </button>
          )}
          
          <Board
            fen={fen}
            onMove={wrappedHandleMove}
            arrows={annotations.arrows}
            highlights={annotations.highlights}
            orientation={boardOrientation}
            disabled={waitingForEngine || (mode === "TACTICS" && currentTactic !== null)}
          />
          
          {isAnalyzing && (
            <div style={{ 
              position: 'absolute', 
              top: '10px', 
              right: '10px', 
              background: 'rgba(0, 0, 0, 0.7)', 
              color: '#4CAF50', 
              padding: '4px 8px', 
              borderRadius: '4px', 
              fontSize: '11px',
              display: 'flex',
              alignItems: 'center',
              gap: '5px'
            }}>
              <span style={{ animation: 'pulse 1.5s ease-in-out infinite' }}>●</span>
              Caching analysis...
            </div>
          )}
          
          {lessonMode && currentLesson && (
            <div className="lesson-progress">
              <div className="lesson-progress-header">
                <span className="lesson-progress-title">{currentLesson.plan.title}</span>
                <span className="lesson-progress-count">
                  {lessonProgress.current + 1}/{lessonProgress.total}
                </span>
              </div>
              <div className="lesson-progress-bar">
                <div 
                  className="lesson-progress-fill"
                  style={{ width: `${((lessonProgress.current + 1) / lessonProgress.total) * 100}%` }}
                />
              </div>
            </div>
          )}
          
          {/* FEN Display */}
          <FENDisplay fen={fen} onFenLoad={handleLoadFen} />
          
          {/* Navigation Buttons */}
          <div className="navigation-buttons">
            <button onClick={handleNavigateStart} className="nav-button" title="Go to start">
              ⏮️
            </button>
            <button onClick={handleNavigateBack} className="nav-button" title="Previous move">
              ◀️
            </button>
            <button onClick={handleNavigateForward} className="nav-button" title="Next move">
              ▶️
            </button>
            <button onClick={handleNavigateEnd} className="nav-button" title="Go to end">
              ⏭️
            </button>
          </div>
          
          {/* PGN Viewer with variations */}
          <PGNViewer
            key={`pgn-${treeVersion}-${pgn.length}`}
            rootNode={moveTree.root}
            currentNode={moveTree.currentNode}
            onMoveClick={handleMoveClick}
            onDeleteMove={handleDeleteMove}
            onDeleteVariation={handleDeleteVariation}
            onPromoteVariation={handlePromoteVariation}
            onAddComment={handleAddComment}
          />
          
          <div className="board-controls">
            <button onClick={() => setShowLessonBuilder(true)} className="control-btn">
              🎓 Create Lesson
            </button>
            <button onClick={() => setShowOpeningModal(true)} className="control-btn">
              Opening Lesson
            </button>
            <button onClick={() => handleAnalyzePosition()} className="control-btn">
              Analyze Position
            </button>
            <button onClick={handleAnalyzeLastMove} className="control-btn">
              Analyze Last Move
            </button>
            
            {/* Game Review Configuration */}
            <div style={{ 
              display: 'flex', 
              gap: '10px', 
              alignItems: 'center', 
              marginTop: '10px',
              padding: '10px',
              border: '1px solid #333',
              borderRadius: '8px',
              backgroundColor: '#1a1a1a'
            }}>
              <div style={{ flex: 1 }}>
                <label style={{ fontSize: '12px', color: '#888', display: 'block', marginBottom: '4px' }}>
                  Review Focus
                </label>
                <select 
                  value={reviewSideFocus} 
                  onChange={(e) => setReviewSideFocus(e.target.value as any)}
                  style={{
                    width: '100%',
                    padding: '6px',
                    backgroundColor: '#2a2a2a',
                    color: '#fff',
                    border: '1px solid #444',
                    borderRadius: '4px',
                    fontSize: '13px'
                  }}
                >
                  <option value="both">Both Sides</option>
                  <option value="white">White Only</option>
                  <option value="black">Black Only</option>
                </select>
              </div>
              
              <div style={{ flex: 1 }}>
                <label style={{ fontSize: '12px', color: '#888', display: 'block', marginBottom: '4px' }}>
                  Presentation
                </label>
                <select
                  value={reviewPresentationMode}
                  onChange={(e) => setReviewPresentationMode(e.target.value as any)}
                  style={{
                    width: '100%',
                    padding: '6px',
                    backgroundColor: '#2a2a2a',
                    color: '#fff',
                    border: '1px solid #444',
                    borderRadius: '4px',
                    fontSize: '13px'
                  }}
                >
                  <option value="talk">Talk Through</option>
                  <option value="tables">Summary Tables</option>
                </select>
              </div>
            </div>
            
            <button onClick={handleReviewGame} className="control-btn" style={{ marginTop: '10px' }}>
              Review Game
            </button>
            <button onClick={handleNextTactic} className="control-btn">
              Next Tactic
            </button>
            <button onClick={handleResetBoard} className="control-btn secondary">
              Reset Board
            </button>
            <button onClick={handleCopyPGN} className="control-btn secondary">
              Copy PGN
            </button>
          </div>

          {currentTactic && (
            <div className="tactic-info">
              <strong>Tactic #{currentTactic.id}</strong> (Rating: {currentTactic.rating})
              <button onClick={handleRevealTactic} className="reveal-btn">
                💡 Reveal Solution
              </button>
            </div>
          )}
        </div>

        <div className="chat-panel">
          <Chat
            messages={messages}
            onSendMessage={handleSendMessage}
            mode={mode}
            fen={fen}
            pgn={pgn}
            annotations={annotations}
            systemPrompt={systemPrompt}
            llmEnabled={llmEnabled}
            onToggleLLM={() => setLlmEnabled(!llmEnabled)}
            isReviewing={isReviewing}
            reviewProgress={reviewProgress}
            totalMoves={moveTree.getMainLine().length}
            lessonMode={lessonMode}
            isOffMainLine={isOffMainLine}
            onReturnToMainLine={returnToMainLine}
            isAnalyzing={isAnalyzing}
          />
        </div>
      </div>
      
      {showLessonBuilder && (
        <LessonBuilder
          onStartLesson={handleStartLesson}
          onClose={() => setShowLessonBuilder(false)}
        />
      )}
      
      {showOpeningModal && (
        <div className="modal-overlay" onClick={() => setShowOpeningModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h2>Create Opening Lesson</h2>
            <p>Enter an opening name, ECO code, or move sequence:</p>
            <input
              type="text"
              placeholder="e.g., Sicilian Najdorf, B90, 1.e4 c5 2.Nf3..."
              value={openingQuery}
              onChange={(e) => setOpeningQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  handleCreateOpeningLesson();
                }
              }}
              style={{
                width: '100%',
                padding: '10px',
                marginTop: '10px',
                fontSize: '14px',
                border: '1px solid #ccc',
                borderRadius: '4px'
              }}
            />
            <div style={{ marginTop: '20px', display: 'flex', gap: '10px', justifyContent: 'flex-end' }}>
              <button onClick={() => setShowOpeningModal(false)} style={{ padding: '10px 20px' }}>
                Cancel
              </button>
              <button 
                onClick={handleCreateOpeningLesson} 
                style={{ 
                  padding: '10px 20px', 
                  background: '#4CAF50', 
                  color: 'white', 
                  border: 'none',
                  borderRadius: '4px',
                  cursor: 'pointer'
                }}
              >
                Generate Lesson
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Personal Review Modal */}
      {showPersonalReview && (
        <PersonalReview onClose={() => setShowPersonalReview(false)} />
      )}
      
      {/* Training & Drills Modal */}
      {showTraining && (
        <TrainingManager onClose={() => setShowTraining(false)} />
      )}
    </main>
  );
}

