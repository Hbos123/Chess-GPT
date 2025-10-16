"use client";

import { useState, useEffect } from "react";
import { Chess } from "chess.js";
import Board from "@/components/Board";
import Chat from "@/components/Chat";
import RouterHint from "@/components/RouterHint";
import FENDisplay from "@/components/FENDisplay";
import PGNViewer from "@/components/PGNViewer";
import LessonBuilder from "@/components/LessonBuilder";
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
  
  // Lesson system state
  const [showLessonBuilder, setShowLessonBuilder] = useState(false);
  const [currentLesson, setCurrentLesson] = useState<any>(null);
  const [lessonProgress, setLessonProgress] = useState({ current: 0, total: 0 });
  const [currentLessonPosition, setCurrentLessonPosition] = useState<any>(null);
  const [lessonMode, setLessonMode] = useState(false);
  const [lessonMoveIndex, setLessonMoveIndex] = useState(0); // Current move in ideal line
  const [isOffMainLine, setIsOffMainLine] = useState(false); // Player deviated from ideal line
  const [mainLineFen, setMainLineFen] = useState<string>(""); // FEN to return to

  // Helper function to call LLM through backend (avoids CORS)
  async function callLLM(messages: { role: string; content: string }[], temperature: number = 0.7, model: string = "gpt-4o-mini"): Promise<string> {
    try {
      const response = await fetch("http://localhost:8000/llm_chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages, temperature, model }),
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "LLM call failed");
      }
      
      const data = await response.json();
      return data.content;
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
    setMessages((prev) => [...prev, { role: "assistant", content, meta }]);
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

  function shouldTriggerAnalysis(msg: string): { shouldAnalyze: boolean; questionType: string } {
    const lower = msg.toLowerCase().trim();
    
    // Check for move analysis first
    const moveAnalysis = detectMoveAnalysisRequest(msg);
    if (moveAnalysis.isMoveAnalysis) {
      return { shouldAnalyze: true, questionType: "move_analysis" };
    }
    
    // Direct analysis requests - Full detailed analysis
    // Support: analyze, analyse, analayze, analize, etc.
    const analyzeVariants = ["analyze", "analyse", "analyize", "analize"];
    if (containsWordVariation(lower, analyzeVariants)) {
      if (lower.includes("position") || lower.includes("this") || lower.split(/\s+/).length === 1) {
        return { shouldAnalyze: true, questionType: "full_analysis" };
      }
    }
    
    // Support: eval, evaluate, evaluation, evalute, evalutation, etc.
    const evalVariants = ["eval", "evaluate", "evaluation", "evalute", "evalutate"];
    if (containsWordVariation(lower, evalVariants)) {
      return { shouldAnalyze: true, questionType: "evaluation" };
    }
    
    // Support: assess, assessment, asses, assesment, etc.
    const assessVariants = ["assess", "assessment", "asses", "assesment", "asess"];
    if (containsWordVariation(lower, assessVariants)) {
      return { shouldAnalyze: true, questionType: "assessment" };
    }
    
    // Question patterns - Concise advice
    // Support: should, shuld, shoud, shld, etc.
    const shouldVariants = ["should", "shuld", "shoud", "shld", "shold"];
    if (containsWordVariation(lower, shouldVariants)) {
      if (lower.includes("what") || lower.includes("how")) {
        return { shouldAnalyze: true, questionType: "what_should_i_do" };
      }
    }
    
    // Support: best, bst, besy, vbest, etc.
    const bestVariants = ["best", "bst", "besy", "vest", "bestt"];
    const moveVariants = ["move", "mov", "mvoe", "moev", "mve"];
    if (containsWordVariation(lower, bestVariants) && containsWordVariation(lower, moveVariants)) {
      return { shouldAnalyze: true, questionType: "best_move" };
    }
    
    // "what's best" or "what is best"
    if ((lower.includes("what") || lower.includes("whats")) && containsWordVariation(lower, bestVariants)) {
      return { shouldAnalyze: true, questionType: "best_move" };
    }
    
    // Support: candidate, candidat, caniddate, etc.
    const candidateVariants = ["candidate", "candidat", "caniddate", "candidte", "candiate"];
    if (containsWordVariation(lower, candidateVariants)) {
      return { shouldAnalyze: true, questionType: "show_candidates" };
    }
    
    // Support: options, option, optons, optins, etc.
    const optionsVariants = ["options", "option", "optons", "optins", "optoins"];
    if (lower.includes("what") && containsWordVariation(lower, optionsVariants)) {
      return { shouldAnalyze: true, questionType: "show_options" };
    }
    
    // "show me" patterns
    if ((lower.includes("show") || lower.includes("shw") || lower.includes("sho")) && 
        (containsWordVariation(lower, moveVariants) || containsWordVariation(lower, candidateVariants))) {
      return { shouldAnalyze: true, questionType: "show_candidates" };
    }
    
    // "help me find" or "help with move"
    if (lower.includes("help") && (lower.includes("find") || containsWordVariation(lower, moveVariants))) {
      return { shouldAnalyze: true, questionType: "help_with_move" };
    }
    
    return { shouldAnalyze: false, questionType: "none" };
  }

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
  "Unknown board state"}

Instructions:
1. Respond warmly and naturally to their greeting/message
2. Based on the board state, offer relevant suggestions:
   - If starting position: Suggest starting a game, analyzing openings, or solving tactics
   - If game in progress: Offer to analyze the position, suggest next moves, or review the game
   - If custom position: Offer to analyze the position or play from here
3. Keep response friendly, concise (2-3 sentences), and helpful
4. Don't analyze the position unless explicitly asked
`;

    try {
      const reply = await callLLM([
        { 
          role: "system", 
          content: "You are Chess GPT, a friendly chess assistant. You help users play, analyze, and learn chess. Be warm, encouraging, and concise." 
        },
        { role: "user", content: contextPrompt },
      ], 0.8);
      
      // Store minimal meta for general chat
      const meta = {
        type: "general_chat",
        boardContext,
        fen,
        moveCount
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

      const commentary = await callLLM([
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
    const arrows: any[] = [];
    const highlights: any[] = [];
    
    // Semi-transparent green for all arrows
    const arrowColor = 'rgba(34, 197, 94, 0.65)';  // Semi-transparent green
    
    // Add arrows for candidate moves (top 3)
    const candidates = analysisData.candidate_moves || [];
    candidates.slice(0, 3).forEach((candidate: any, index: number) => {
      if (candidate.uci) {
        const from = candidate.uci.substring(0, 2);
        const to = candidate.uci.substring(2, 4);
        
        arrows.push({ from, to, color: arrowColor });
      }
    });
    
    // Add threat arrows (also green now)
    const threats = analysisData.threats || [];
    threats.forEach((threat: any) => {
      // Parse first move from threat PV
      const pvMoves = threat.pv_san?.split(' ') || [];
      if (pvMoves.length > 0) {
        try {
          const tempGame = new Chess(fen);
          const threatMove = tempGame.move(pvMoves[0]);
          if (threatMove) {
            arrows.push({
              from: threatMove.from,
              to: threatMove.to,
              color: arrowColor  // Same semi-transparent green
            });
          }
        } catch (e) {
          // Skip invalid moves
        }
      }
    });
    
    // Highlight active pieces (pieces with high mobility)
    const board = new Chess(fen);
    const sideToMove = fen.split(' ')[1];
    
    board.board().forEach((row, rankIdx) => {
      row.forEach((square, fileIdx) => {
        if (square && square.color === sideToMove) {
          const squareName = String.fromCharCode(97 + fileIdx) + (8 - rankIdx);
          const moves = board.moves({ square: squareName as any });
          
          // Highlight very active pieces (4+ moves)
          if (moves.length >= 4) {
            highlights.push({
              sq: squareName,
              color: 'rgba(0, 255, 0, 0.3)'  // Light green
            });
          }
          // Highlight inactive pieces (0 moves)
          else if (moves.length === 0 && square.type !== 'k') {
            highlights.push({
              sq: squareName,
              color: 'rgba(255, 150, 0, 0.3)'  // Light orange
            });
          }
        }
      });
    });
    
    return { arrows, highlights };
  }

  async function handleAnalyzePosition(questionType: string = "full_analysis") {
    // Don't add redundant "Analyze this position" - user already asked their question
    
    try {
      const result = await analyzePosition(fen, 3, 16);
      
      // ANALYSIS 1: Generate Chess GPT structured response
      const structuredAnalysis = generateChessGPTStructuredResponse(result);
      console.log("=== ANALYSIS 1 (Chess GPT Structured) ===");
      console.log(structuredAnalysis);
      console.log("=========================================");
      
      // Generate visual annotations
      const visualAnnotations = generateVisualAnnotations(result);
      
      // Store annotations for this FEN position
      setAnnotationsByFen(prev => {
        const newMap = new Map(prev);
        newMap.set(fen, {
          arrows: visualAnnotations.arrows,
          highlights: visualAnnotations.highlights
        });
        return newMap;
      });
      
      // Apply annotations to board
      setAnnotations(prev => ({
        ...prev,
        arrows: visualAnnotations.arrows,
        highlights: visualAnnotations.highlights,
        comments: [
          ...prev.comments,
          {
            ply: game.history().length,
            text: `Analysis: ${result.eval_cp > 0 ? '+' : ''}${(result.eval_cp / 100).toFixed(2)}`
          }
        ]
      }));
      
      // After Analysis 1 is complete, generate concise final response
      if (llmEnabled) {
        await generateConciseLLMResponse(structuredAnalysis, result, questionType);
      } else {
        // If LLM disabled, show the Chess GPT structured response
        addAssistantMessage(structuredAnalysis, result);
      }
      
      addSystemMessage(`📍 Visual annotations applied: ${visualAnnotations.arrows.length} arrows, ${visualAnnotations.highlights.length} highlights`);
    } catch (err: any) {
      addSystemMessage(`Analysis error: ${err.message}`);
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

  async function generateConciseLLMResponse(structuredAnalysis: string, engineData: any, questionType: string = "full_analysis") {
    try {
      const evalCp = engineData.eval_cp || 0;
      const evalPawns = (evalCp / 100).toFixed(2);
      const phase = engineData.phase || "opening";
      const sideToMove = fen.split(' ')[1] === 'w' ? 'White' : 'Black';
      const candidates = engineData.candidate_moves || [];
      const threats = engineData.threats || [];
      const deepAnalysis = analyzePositionStrengthsWeaknesses(engineData, fen);

      // Determine prompt based on question type
      let llmPrompt = "";
      let maxTokens = 200;

      if (questionType === "what_should_i_do" || questionType === "how_to_proceed" || questionType === "help_with_move") {
        // CONCISE FORMAT for "what should I do?" type questions
        maxTokens = 100;
        llmPrompt = `You are answering "What should I do?" in a chess position. Be VERY concise and direct.

REQUIRED FORMAT (2 sentences max):
Sentence 1: "You [have/don't have] an advantage here ([brief 6-word position summary])."
Sentence 2: "Play [candidate moves] to [plan]."

ANALYSIS DATA:
Evaluation: ${evalCp > 0 ? '+' : ''}${evalPawns}
Side to move: ${sideToMove}
Top candidates: ${candidates.slice(0, 3).map((c: any) => c.move).join(", ")}
Best piece activity: ${deepAnalysis.whiteActive.concat(deepAnalysis.blackActive).slice(0, 2).join(", ") || "balanced"}
Main threat: ${threats.length > 0 ? threats[0].desc : "none"}

CHESS GPT ANALYSIS:
${structuredAnalysis}

INSTRUCTIONS:
1. Start with advantage assessment (have/don't have advantage + brief position summary in ~6 words)
2. Then give 2-3 candidate moves with the plan
3. Total response: 2 sentences, ~40-50 words max
4. Be direct and actionable`;

      } else if (questionType === "best_move") {
        // CONCISE FORMAT for "best move?" questions
        maxTokens = 80;
        llmPrompt = `You are answering "What's the best move?" in a chess position. Be EXTREMELY concise.

REQUIRED FORMAT (1-2 sentences):
"Play [move] to [reason]. Alternative: [move2]."

ANALYSIS DATA:
Best move: ${candidates[0]?.move || "Unknown"}
Reason: ${candidates[0]?.desc || ""}
Alternative: ${candidates[1]?.move || ""}
Evaluation: ${evalCp > 0 ? '+' : ''}${evalPawns}

INSTRUCTIONS:
1. State the best move and WHY in one sentence
2. Give one alternative
3. Total: 20-30 words max`;

      } else if (questionType === "show_candidates" || questionType === "show_options") {
        // CONCISE FORMAT for "show me options" questions  
        maxTokens = 100;
        llmPrompt = `You are showing candidate moves in a chess position. Be concise.

REQUIRED FORMAT:
"Your top options: [move1] ([reason]), [move2] ([reason]), or [move3] ([reason])."

ANALYSIS DATA:
Candidates: ${candidates.slice(0, 3).map((c: any) => `${c.move} - ${c.desc || 'good move'}`).join("; ")}
Evaluation: ${evalCp > 0 ? '+' : ''}${evalPawns}

INSTRUCTIONS:
1. List 3 candidate moves with brief reasons
2. Format: "Your top options: Move1 (reason), Move2 (reason), Move3 (reason)."
3. Total: 30-40 words`;

      } else {
        // FULL ANALYSIS FORMAT for "analyze" commands
        llmPrompt = `You are analyzing a chess position. Generate a concise 2-3 sentence response following this EXACT structure:

REQUIRED FORMAT:
Sentence 1: "This is [a/an] [opening/middlegame/endgame] position with [who's winning] (eval: [+/-]X.XX)."
Sentence 2: "[Side] [has the advantage/is equal/is behind] due to [evidence: material balance, positional factors, best/worst pieces, threats, king safety]."
Sentence 3: "It's [Side]'s turn to move, and they could [candidate move(s)] to [plan]."

ANALYSIS DATA:
Phase: ${phase}
Evaluation: ${evalCp > 0 ? '+' : ''}${evalPawns}
Side to move: ${sideToMove}
Top candidates: ${candidates.slice(0, 2).map((c: any) => c.move).join(", ")}
Threats: ${threats.length > 0 ? threats.map((t: any) => t.desc).join("; ") : "None"}
White mobility: ${deepAnalysis.whiteMobility} moves
Black mobility: ${deepAnalysis.blackMobility} moves
Active pieces: ${deepAnalysis.whiteActive.concat(deepAnalysis.blackActive).join(", ") || "None"}
Inactive pieces: ${deepAnalysis.whiteInactive.concat(deepAnalysis.blackInactive).join(", ") || "None"}

CHESS GPT ANALYSIS:
${structuredAnalysis}

INSTRUCTIONS:
1. Follow the 3-sentence structure EXACTLY
2. Include the CP eval in sentence 1
3. In sentence 2, give the STRONGEST evidence (pick top 2-3 from: material, piece activity, good pieces, bad pieces, threats, king safety, pawn structure)
4. In sentence 3, suggest candidate moves and a clear plan
5. Be concise and actionable`;
      }

      const conciseResponse = await callLLM([
        { 
          role: "system", 
          content: "You are a chess analysis assistant. Be concise, direct, and actionable. Follow the requested format exactly." 
        },
        { role: "user", content: llmPrompt },
      ], 0.5);
      
      // Store full Chess GPT analysis in meta for 📊 button
      const meta = {
        structuredAnalysis,
        rawEngineData: engineData,
        mode: "ANALYZE",
        fen: fen
      };
      
      addAssistantMessage(conciseResponse, meta);
    } catch (err: any) {
      addSystemMessage(`LLM error: ${err.message}`);
      // Fallback to showing structured analysis
      addAssistantMessage(structuredAnalysis, engineData);
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

      const contextMessage = `
Current Position (FEN): ${fen}
Current PGN: ${pgn}
Mode: ${inferredMode} (${modeContext})
Chat History: ${messages.slice(-3).map(m => `${m.role}: ${m.content}`).join("\n")}

${structuredAnalysis ? `Chess GPT Analysis:\n${structuredAnalysis}\n` : ""}

${toolOutput ? `Raw Engine Data:\n${JSON.stringify(toolOutput, null, 2)}\n` : ""}

User Message: ${userMessage}

Instructions: Respond naturally and conversationally. Keep your response concise (2-3 sentences). Focus on being helpful and engaging.
      `.trim();

      const reply = await callLLM([
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

        const reply = await callLLM([
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
        
        addAssistantMessage(reply.trim(), { 
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

        const reply = await callLLM([
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
        
        addAssistantMessage(reply.trim(), { 
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
      }
    }
    
    addUserMessage(message);

    let lower = message.toLowerCase().trim();

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

    // Check if this should trigger analysis
    const analysisCheck = shouldTriggerAnalysis(message);
    if (analysisCheck.shouldAnalyze) {
      if (analysisCheck.questionType === "move_analysis") {
        await handleMoveAnalysis(message);
        return;
      }
      await handleAnalyzePosition(analysisCheck.questionType);
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
    
    // Collect all special moves (blunders, critical, missed wins, advantage shifts)
    const specialMoves: any[] = [];
    
    // Step 3: Blunders
    const blunders = moves.filter((m: any) => m.quality === 'blunder');
    blunders.forEach((m: any) => specialMoves.push({ type: 'blunder', move: m }));
    
    // Step 4: Critical moves
    criticalMovesList.forEach((m: any) => specialMoves.push({ type: 'critical', move: m }));
    
    // Step 5: Missed wins
    missedWinsList.forEach((m: any) => specialMoves.push({ type: 'missed_win', move: m }));
    
    // Step 6: Advantage shifts
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
          buttonLabel: `➡️ Next Step (${stepNum}/${totalSteps})`
        }]);
        return;
      case 'blunder':
        const cpLoss = move.cpLoss || 0;
        addAssistantMessage(`**Move ${move.moveNumber}. ${move.move} - Blunder! (${move.accuracy.toFixed(1)}% accuracy)**\n\n${move.color === 'w' ? 'White' : 'Black'} played **${move.move}**, losing ${cpLoss}cp. This was a critical mistake that significantly worsened the position.`);
        await new Promise(resolve => setTimeout(resolve, 500));
        await analyzeMoveAtPosition(move);
        setMessages(prev => [...prev, {
          role: 'button',
          content: '',
          buttonAction: 'NEXT_STEP',
          buttonLabel: `➡️ Next Step (${stepNum}/${totalSteps})`
        }]);
        return;
      case 'critical':
        const gapToSecond = move.gapToSecond || 0;
        addAssistantMessage(`**Move ${move.moveNumber}. ${move.move} - Critical Move!**\n\n${move.color === 'w' ? 'White' : 'Black'} found the best move **${move.move}**, which was ${gapToSecond}cp better than the second-best option. This was the only move that maintained the advantage.`);
        await new Promise(resolve => setTimeout(resolve, 500));
        await analyzeMoveAtPosition(move);
        setMessages(prev => [...prev, {
          role: 'button',
          content: '',
          buttonAction: 'NEXT_STEP',
          buttonLabel: `➡️ Next Step (${stepNum}/${totalSteps})`
        }]);
        return;
      case 'missed_win':
        const evalBefore = move.evalBefore || 0;
        const missedGap = move.gapToSecond || 0;
        addAssistantMessage(`**Move ${move.moveNumber}. ${move.move} - Missed Win**\n\n${move.color === 'w' ? 'White' : 'Black'} played **${move.move}** in a winning position (${(evalBefore / 100).toFixed(2)}), but missed a better move that was ${missedGap}cp stronger. This was a chance to convert decisively.`);
        await new Promise(resolve => setTimeout(resolve, 500));
        await analyzeMoveAtPosition(move);
        setMessages(prev => [...prev, {
          role: 'button',
          content: '',
          buttonAction: 'NEXT_STEP',
          buttonLabel: `➡️ Next Step (${stepNum}/${totalSteps})`
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
          buttonLabel: `➡️ Next Step (${stepNum}/${totalSteps})`
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
        buttonLabel: `➡️ Next Step (${stepNum}/${totalSteps})`
      }]);
    } else if (message) {
      // Message will be added by the analysis function
      setTimeout(() => {
        // Add Next button after the analysis
        setMessages(prev => [...prev, {
          role: 'button',
          content: '',
          buttonAction: 'NEXT_STEP',
          buttonLabel: `➡️ Next Step (${stepNum}/${totalSteps})`
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
    // Add system message indicating analysis is starting
    addSystemMessage("Analyzing move...");
    
    // This will trigger the move analysis for the specific move
    // We need to set up the position before the move and analyze it
    const fenBefore = move.fenBefore;
    
    try {
      const response = await fetch(`http://localhost:8000/analyze_move?fen=${encodeURIComponent(fenBefore)}&move_san=${encodeURIComponent(move.move)}&depth=18`, {
        method: 'POST'
      });
      
      if (!response.ok) {
        throw new Error(`Backend returned ${response.status}`);
      }
      
      const data = await response.json();
      
      // Extract data from the new structure
      const playedReport = data.playedMoveReport;
      const bestReport = data.bestMoveReport;
      const isBest = data.isPlayedMoveBest;
      
      // Build structured analysis for raw data
      const evalBefore = playedReport.evalBefore;
      const evalAfter = playedReport.evalAfter;
      const evalChange = playedReport.evalChange;
      const evalChangeStr = evalChange > 0 ? `+${(evalChange / 100).toFixed(2)}` : `${(evalChange / 100).toFixed(2)}`;
      
      let structuredAnalysis = `**Move Analysis: ${move.move}**\n\n`;
      structuredAnalysis += `Evaluation: ${(evalBefore / 100).toFixed(2)} → ${(evalAfter / 100).toFixed(2)} (${evalChangeStr})\n\n`;
      
      if (isBest) {
        structuredAnalysis += `✓ This was the best move!\n\n`;
      } else {
        const bestEval = bestReport ? bestReport.evalAfter : evalAfter;
        structuredAnalysis += `The engine preferred: ${data.bestMove} (${(bestEval / 100).toFixed(2)})\n`;
        structuredAnalysis += `Difference: ${((bestEval - evalAfter) / 100).toFixed(2)} pawns\n\n`;
      }
      
      // Add themes
      if (playedReport.themesGained && playedReport.themesGained.length > 0) {
        structuredAnalysis += `Themes gained: ${playedReport.themesGained.join(", ")}\n`;
      }
      if (playedReport.themesLost && playedReport.themesLost.length > 0) {
        structuredAnalysis += `Themes lost: ${playedReport.themesLost.join(", ")}\n`;
      }
      
      // Generate LLM response
      const llmPrompt = `You are analyzing move ${move.moveNumber}. ${move.move} in a chess game.

Context:
- Evaluation before: ${(evalBefore / 100).toFixed(2)}
- Evaluation after: ${(evalAfter / 100).toFixed(2)}
- Change: ${evalChangeStr}
- Was it the best move? ${isBest ? "Yes" : `No, engine preferred ${data.bestMove}`}
${playedReport.themesGained && playedReport.themesGained.length > 0 ? `- Themes gained: ${playedReport.themesGained.join(", ")}` : ""}
${playedReport.themesLost && playedReport.themesLost.length > 0 ? `- Themes lost: ${playedReport.themesLost.join(", ")}` : ""}

Write a brief 2-3 sentence analysis explaining what this move accomplished and whether it was strong or weak. Be conversational and focus on the strategic impact.`;

      try {
        const llmResponse = await callLLM([
          { role: "system", content: "You are a helpful chess coach providing concise move analysis." },
          { role: "user", content: llmPrompt }
        ], 0.7, "gpt-4o-mini");
        
        // Add the LLM response with raw data metadata
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: llmResponse,
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
      const response = await fetch(`http://localhost:8000/review_game?pgn_string=${encodeURIComponent(cleanPgn)}`, {
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
      console.log('Total Moves Analyzed:', reviewData.moves?.length || 0);
      console.log('Move-by-Move Breakdown:', reviewData.moves);
      console.log('==========================================');

      // Update PGN with colored moves and annotations
      updatePGNWithReview(reviewData.moves);

      // Display review summary
      const moves = reviewData.moves || [];
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
      
      // Get accuracy stats from backend (includes phase-based breakdown)
      const accuracyStats = reviewData.accuracyStats || {
        overall: { white: 100.0, black: 100.0 },
        opening: { white: 100.0, black: 100.0 },
        middlegame: { white: 100.0, black: 100.0 },
        endgame: { white: 100.0, black: 100.0 }
      };
      
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
📖 Theory: ${theory}
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

📖 Opening (${openingMoves} moves):
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
          summary += `\n\n🏷️ ${tag.name}\n   ${tag.description}`;
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

      // Reset board to starting position
      const newGame = new Chess();
      setGame(newGame);
      setFen(INITIAL_FEN);
      
      // Generate LLM summary
      setReviewProgress(100);
      
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
      ], 0.7, "gpt-4o-mini").then(llmResponse => {
        // Add LLM response with metadata
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
      node.comment = `eval ${reviewData.evalAfter}cp`;
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
      
      // Generate positions for first section
      const firstTopic = plan.sections[0].topics[0];
      const posResponse = await fetch(`http://localhost:8000/generate_positions?topic_code=${firstTopic}&count=3`, {
        method: "POST"
      });
      
      if (!posResponse.ok) {
        throw new Error("Failed to generate positions");
      }
      
      const positions = await posResponse.json();
      
      if (!positions.positions || positions.positions.length === 0) {
        throw new Error("No positions were generated");
      }
      
      setCurrentLesson({
        plan,
        positions: positions.positions,
        currentIndex: 0
      });
      
      setLessonProgress({ current: 0, total: positions.count });
      setLessonMode(true);
      
      // Load first position
      await loadLessonPosition(positions.positions[0], 0, positions.count);
      
    } catch (error) {
      console.error("Lesson generation error:", error);
      addSystemMessage("Failed to generate lesson. Please try again.");
    }
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
  }
  
  async function checkLessonMove(moveSan: string, currentFen: string) {
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
          const feedbackPrompt = `The student played the correct move: ${moveSan}.

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
        
        // Determine eval change wording
        let evalDescription = "";
        if (result.cp_loss <= 10) {
          evalDescription = "~=";
        } else if (result.cp_loss <= 30) {
          evalDescription = "⩲";
        } else if (result.cp_loss <= 100) {
          evalDescription = "±";
        } else {
          evalDescription = "∓";
        }
        
        // Brief feedback with eval info
        const feedbackPrompt = `The student deviated: played ${moveSan} instead of ${expectedMove}.
CP Loss: ${result.cp_loss}
Eval impact: ${evalDescription}

Give ONE brief sentence (max 15 words) about whether this move is acceptable or problematic.`;

        const llmFeedback = await callLLM([
          { role: "system", content: "You are a concise chess coach. Be very brief." },
          { role: "user", content: feedbackPrompt }
        ], 0.7, "gpt-4o-mini");
        
        addAssistantMessage(`📝 **Deviation:** You played **${moveSan}** (expected: **${expectedMove}**)\n**Eval:** ${evalDescription} | **CP Loss:** ${result.cp_loss}cp\n\n${llmFeedback}`);
        
        // AI responds to the alternate move after a delay
        setTimeout(async () => {
          try {
            // Recreate board from current FEN and apply the player's deviation move
            const tempBoard = new Chess(currentFen);
            tempBoard.move(moveSan); // Apply the player's move that was just made
            
            console.log("[LESSON DEVIATION] Board after player deviation:", tempBoard.fen());
            
            // Get engine's best response to the alternate move
            const engineResponse = await fetch(`http://localhost:8000/analyze_position?fen=${encodeURIComponent(tempBoard.fen())}&lines=1&depth=16`);
            
            if (engineResponse.ok) {
              const analysis = await engineResponse.json();
              if (analysis.lines && analysis.lines.length > 0) {
                const bestResponse = analysis.lines[0].moves[0];
                
                console.log("[LESSON DEVIATION] Engine's best response:", bestResponse);
                
                // Play the engine's response
                const move = tempBoard.move(bestResponse);
                if (move) {
                  setFen(tempBoard.fen());
                  setGame(tempBoard);
                  moveTree.addMove(move.san, tempBoard.fen());
                  setTreeVersion(v => v + 1);
                  
                  addSystemMessage(`Opponent responds: **${move.san}**`);
                }
              }
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
        <h1>♟️ Chess GPT</h1>
        <div className="header-subtitle">Intelligent Chess Assistant</div>
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
            <button onClick={() => handleAnalyzePosition()} className="control-btn">
              📊 Analyze Position
            </button>
            <button onClick={handleReviewGame} className="control-btn">
              🎯 Review Game
            </button>
            <button onClick={handleNextTactic} className="control-btn">
              🧩 Next Tactic
            </button>
            <button onClick={handleResetBoard} className="control-btn secondary">
              🔄 Reset Board
            </button>
            <button onClick={handleCopyPGN} className="control-btn secondary">
              📋 Copy PGN
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
          />
        </div>
      </div>
      
      {showLessonBuilder && (
        <LessonBuilder
          onStartLesson={handleStartLesson}
          onClose={() => setShowLessonBuilder(false)}
        />
      )}
    </main>
  );
}

