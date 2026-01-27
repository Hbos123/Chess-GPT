"use client";

import { useState, useEffect, useRef, useCallback, CSSProperties, MouseEvent as ReactMouseEvent, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { Chess, type Move } from "chess.js";
import Board from "@/components/Board";
import TopBar from "@/components/TopBar";
import HeroComposer from "@/components/HeroComposer";
import BottomComposer from "@/components/BottomComposer";
import Conversation from "@/components/Conversation";
import BoardDock from "@/components/BoardDock";
import HistoryCurtain from "@/components/HistoryCurtain";
import LoadGamePanel, { LoadedGamePayload } from "@/components/LoadGamePanel";
import RotatingExamples, { useRotatingPlaceholder } from "@/components/RotatingExamples";
import AuthModal from "@/components/AuthModal";
import PersonalReview from "@/components/PersonalReview";
import ProfileSetupModal, { ProfilePreferences } from "@/components/ProfileSetupModal";
import StatusIndicator from "@/components/StatusIndicator";
import FactsCard from "@/components/FactsCard";
import IntentBox from "@/components/IntentBox";
import ExecutionPlan from "@/components/ExecutionPlan";
import ThinkingStage from "@/components/ThinkingStage";
import TabBar, { BoardTab, createDefaultTab, createTabFromGame, generateTabName } from "@/components/TabBar";
import ProfileDashboard from "@/components/ProfileDashboard/ProfileDashboard";
import GameSetupModal from "@/components/GameSetupModal";
import OpeningLessonModal from "@/components/OpeningLessonModal";
import TrainingSession from "@/components/TrainingSession";
import { useAuth } from "@/contexts/AuthContext";
import { stripEmojis } from "@/utils/emojiFilter";
import type {
  Mode,
  ChatMessage,
  ChatGraphData,
  Annotation,
  TacticsPuzzle,
  AnnotationArrow,
} from "@/types";
import type { MoveNode } from "@/lib/moveTree";
import { MoveTree } from "@/lib/moveTree";
import { handleUICommands } from "@/lib/commandHandler";
import {
  getMeta,
  analyzePosition,
  playMove,
  openingLookup,
  tacticsNext,
  annotate,
  reviewGame as legacyReviewGame,
  saveProfilePreferences as saveProfilePreferencesApi,
  fetchProfileOverview,
  fetchProfileStats,
  generateOpeningLesson,
  type ProfileOverviewResponse,
  type ProfileStatsResponse,
  type OpeningLessonResponse,
  type OpeningPracticePosition,
} from "@/lib/api";
import { getBackendBase } from "@/lib/backendBase";
import "../styles/chatUI.css";
import "./styles.css";

const INITIAL_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";
const MAX_BOARD_TABS = 5;
const LESSON_ARROW_COLORS = {
  main: "rgba(34, 139, 34, 0.7)", // Dark semi-transparent green
  alternate: "#17c37b",
  threat: "#f87171",
} as const;

function HomeInner() {
  const searchParams = useSearchParams();
  const mobileParam = searchParams.get("mobile");
  const [autoMobileMode, setAutoMobileMode] = useState(false);

  useEffect(() => {
    // If URL explicitly forces mobile mode, don't auto-detect.
    if (mobileParam === "true" || mobileParam === "false") return;
    if (typeof window === "undefined") return;

    const mq = window.matchMedia("(max-width: 768px)");
    const update = () => setAutoMobileMode(mq.matches);

    update();

    // Safari < 14 fallback
    if (typeof mq.addEventListener === "function") {
      mq.addEventListener("change", update);
      return () => mq.removeEventListener("change", update);
    }

    mq.addListener(update);
    return () => mq.removeListener(update);
  }, [mobileParam]);

  const isMobileMode =
    mobileParam === "true" ? true : mobileParam === "false" ? false : autoMobileMode;

  return <Home isMobileMode={isMobileMode} />;
}

function Home({ isMobileMode = true }: { isMobileMode?: boolean }) {
  const searchParams = useSearchParams();
  const settingsParam = searchParams.get("settings");
  const checkoutStatus = searchParams.get("checkout");
  
  // Rotating placeholder text for hero composer
  const { text: rotatingPlaceholder, isVisible: placeholderVisible } = useRotatingPlaceholder();
  
  const [fen, setFen] = useState(INITIAL_FEN);
  const [pgn, setPgn] = useState("");
  
  // Refs to track current values for use in callbacks (avoid stale closures)
  const pgnRef = useRef(pgn);
  const fenRef = useRef(fen);
  
  // Keep refs in sync with state
  useEffect(() => {
    pgnRef.current = pgn;
    fenRef.current = fen;
  }, [pgn, fen]);
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
  const [liveStatusMessages, setLiveStatusMessages] = useState<any[]>([]); // Live status during LLM call
  const [factsByTask, setFactsByTask] = useState<Record<string, any>>({});
  const lastStatusUpdateRef = useRef<number>(0); // Throttle status updates to prevent flashing
  // Prevent cross-run mixing (e.g. if a previous SSE stream finishes late).
  const activeStatusRunIdRef = useRef<string | null>(null);
  const [isLLMProcessing, setIsLLMProcessing] = useState(false);
  // Treat a running SSE analysis as "in progress" so we can pause noisy background polling.
  const [analysisInProgress, setAnalysisInProgress] = useState(false);

  // Declare state variables that are used in useEffect hooks before the hooks themselves
  const [aiGameActive, setAiGameActive] = useState(false); // Track if actively playing a game with AI
  const [lessonMode, setLessonMode] = useState(false);

  // Expose current mode to helper libs (e.g., to gate WASM analysis to PLAY only).
  useEffect(() => {
    try {
      if (typeof window !== "undefined") {
        (window as any).__CHESS_GPT_MODE = mode;
        (window as any).__CHESS_GPT_ALLOW_WASM_ANALYZE = Boolean(mode === "PLAY" || aiGameActive || lessonMode);
      }
    } catch {
      // ignore
    }
  }, [mode, aiGameActive, lessonMode]);
  const [executionPlan, setExecutionPlan] = useState<any>(null); // Execution plan from Planner
  const [thinkingStage, setThinkingStage] = useState<any>(null); // Thinking stage info
  const [boardOrientation, setBoardOrientation] = useState<"white" | "black">("white");
  const [moveTree, setMoveTree] = useState<MoveTree>(new MoveTree());
  const [treeVersion, setTreeVersion] = useState(0); // Force re-render counter
  const [lastAdvantageLevel, setLastAdvantageLevel] = useState<string>("equal"); // Track advantage changes
  const [isReviewing, setIsReviewing] = useState(false);
  const [reviewProgress, setReviewProgress] = useState(0);
  const [walkthroughActive, setWalkthroughActive] = useState(false);
  const [walkthroughData, setWalkthroughData] = useState<any>(null);
  const [walkthroughStep, setWalkthroughStep] = useState(0);
  const [isProcessingStep, setIsProcessingStep] = useState(false);
  const [isGeneratingLesson, setIsGeneratingLesson] = useState(false);
  const [gameReviewData, setGameReviewData] = useState<any>(null); // Store full review for LLM access
  const [reviewSideFocus, setReviewSideFocus] = useState<"white" | "black" | "both">("both");
  const [reviewPresentationMode, setReviewPresentationMode] = useState<"talk" | "tables">("talk");
  const [gameReviewKeyPoints, setGameReviewKeyPoints] = useState<any[]>([]); // Store key points for clicking
  const [retryMoveData, setRetryMoveData] = useState<any>(null); // Store move to retry
  const [isRetryMode, setIsRetryMode] = useState(false); // Track if in retry mode
  const [aiGameElo, setAiGameElo] = useState<number>(1500);
  const [aiGameUserSide, setAiGameUserSide] = useState<"white" | "black" | null>(null);
  const [pendingConfirmation, setPendingConfirmation] = useState<{action: string, intent: string} | null>(null); // Track pending confirmations
  const [limitExceededInfo, setLimitExceededInfo] = useState<{
    type: string;
    message: string;
    usage: any;
    next_step: string;
    available_tools: any;
  } | null>(null);
  const [openSettingsNonce, setOpenSettingsNonce] = useState(0);
  const [lightningMode, setLightningMode] = useState(false);

  // Stable per-tab session id for backend-side LLM prefix caching.
  // Use sessionStorage (tab-scoped) to avoid collisions across tabs.
  // Use useEffect to avoid hydration mismatch - only generate on client
  const [sessionId, setSessionId] = useState<string>("");
  
  useEffect(() => {
    if (typeof window === "undefined") return;
    
    try {
      const key = "chessgpt_session_id";
      const existing = window.sessionStorage.getItem(key);
      if (existing) {
        setSessionId(existing);
        return;
      }
      const id =
        typeof crypto !== "undefined" && "randomUUID" in crypto
          ? crypto.randomUUID()
          : `sess_${Date.now()}_${Math.random().toString(16).slice(2)}`;
      window.sessionStorage.setItem(key, id);
      setSessionId(id);
    } catch {
      const id = `sess_${Date.now()}_${Math.random().toString(16).slice(2)}`;
      setSessionId(id);
    }
  }, []);
  
  // Handle settings query param to open settings modal
  useEffect(() => {
    if (settingsParam === 'open') {
      setShowHistory(true);
      setOpenSettingsNonce((n) => n + 1);
      
      // Show success/cancel message if from checkout
      if (checkoutStatus === 'success') {
        console.log('Checkout successful');
      } else if (checkoutStatus === 'canceled') {
        console.log('Checkout canceled');
      }
      
      // Clean up URL
      if (typeof window !== 'undefined') {
        const url = new URL(window.location.href);
        url.searchParams.delete('settings');
        url.searchParams.delete('checkout');
        window.history.replaceState({}, '', url.toString());
      }
    }
  }, [settingsParam, checkoutStatus]);
  
  
  // Lesson system state
  const [showLessonBuilder, setShowLessonBuilder] = useState(false);
  const [showOpeningModal, setShowOpeningModal] = useState(false);
  const [openingQuery, setOpeningQuery] = useState("");
  const [currentLesson, setCurrentLesson] = useState<any>(null);
  const [lessonProgress, setLessonProgress] = useState({ current: 0, total: 0 });
  const [currentLessonPosition, setCurrentLessonPosition] = useState<any>(null);
  const [lessonMoveIndex, setLessonMoveIndex] = useState(0); // Current move in ideal line
  const [isOffMainLine, setIsOffMainLine] = useState(false); // Player deviated from ideal line
  const [mainLineFen, setMainLineFen] = useState<string>(""); // FEN to return to
  type LessonMoveDescriptor = {
    san: string;
    uci?: string;
    from?: string;
    to?: string;
    promotion?: string | null;
    source?: string;
    popularity?: number;
    win_rate?: number;
    personal_record?: { games: number; wins: number; losses: number; draws: number };
    last_played?: string | null;
    platform?: string | null;
  };
  type LessonCueSnapshot = {
    arrows: AnnotationArrow[];
    description: string;
  };
  type LessonDataSection = {
    title: string;
    body: string;
  };
  type SnapshotCandidate = {
    san: string;
    pop?: number;
    score?: number;
  };
  type LessonTreeNode = {
    id: string;
    fen: string;
    side?: string;
    objective?: string;
    hints?: string[];
    main_move?: LessonMoveDescriptor | null;
    alternate_moves?: LessonMoveDescriptor[];
    tag_highlights?: string[];
    tags?: { white?: string[]; black?: string[] };
    next_node_id?: string | null;
    ai_responses?: LessonMoveDescriptor[];
    history?: string[];
  };
  const [lessonTree, setLessonTree] = useState<LessonTreeNode[]>([]);
  const [lessonNodeId, setLessonNodeId] = useState<string | null>(null);
  const [lessonArrows, setLessonArrows] = useState<AnnotationArrow[]>([]);
  const [lessonOrientation, setLessonOrientation] = useState<"white" | "black">("white");
  const [lessonCueSnapshot, setLessonCueSnapshot] = useState<LessonCueSnapshot | null>(null);
  const [lessonCueButtonActive, setLessonCueButtonActive] = useState(false);
  const [lessonAttemptLog, setLessonAttemptLog] = useState<Record<string, number>>({});
  const [lessonDataSections, setLessonDataSections] = useState<LessonDataSection[] | null>(null);
  const [showLessonDataPanel, setShowLessonDataPanel] = useState(false);
  
  // Personal Review state
  const [showPersonalReview, setShowPersonalReview] = useState(false);
  const [showProfileDashboard, setShowProfileDashboard] = useState(false);
  
  // Training & Drills state
  const [showTraining, setShowTraining] = useState(false);
  
  // Analysis cache - store analysis by FEN for instant LLM access
  const [analysisCache, setAnalysisCache] = useState<Record<string, any>>({});
  const [inlineAnalysisCache, setInlineAnalysisCache] = useState<Record<string, any>>({});
  const [inlineContexts, setInlineContexts] = useState<{id: string, fen: string, pgn?: string, orientation?: 'white' | 'black'}[]>([]);
  const [showDevTools, setShowDevTools] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [abortController, setAbortController] = useState<AbortController | null>(null);

  // Cancel processing function
  function cancelProcessing() {
    if (abortController) {
      abortController.abort();
      setAbortController(null);
    }
    setIsAnalyzing(false);
    setIsProcessingStep(false);
    setIsGeneratingLesson(false);
    addSystemMessage("Processing cancelled.");
  }
  type LoaderEntry = {
    id: string;
    type: 'stockfish' | 'llm' | 'game_review' | 'training' | 'general';
    message: string;
  };
  const [activeLoaders, setActiveLoaders] = useState<LoaderEntry[]>([]);

  // ==========================================
  // MULTI-TAB CHESS BOARD STATE
  // ==========================================
  
  // Extended BoardTab with per-tab state
  interface BoardTabState extends BoardTab {
    // Per-tab chess state
    fen: string;
    pgn: string;
    moveHistory: { from: string; to: string; san: string }[];
    annotations: Annotation;
    analysisCache: Record<string, any>;
    messages: ChatMessage[];
    game: Chess;
    moveTree: MoveTree;
    tabType?: 'review' | 'lesson' | 'play' | 'discuss' | 'training';
    trainingSession?: any; // Training session data for training tabs
    
    // Tab UI state
    isAnalyzing: boolean;
    hasUnread: boolean;
    isModified: boolean;
  }
  
  // Initialize with one default tab
  const createInitialTab = (): BoardTabState => ({
    ...createDefaultTab(1),
    fen: INITIAL_FEN,
    pgn: '',
    moveHistory: [],
    tabType: 'discuss',
    annotations: {
      fen: INITIAL_FEN,
      pgn: '',
      comments: [],
      nags: [],
      arrows: [],
      highlights: [],
    },
    analysisCache: {},
    messages: [],
    game: new Chess(),
    moveTree: new MoveTree(),
    isAnalyzing: false,
    hasUnread: false,
    isModified: false,
  });
  
  const [tabs, setTabs] = useState<BoardTabState[]>(() => [createInitialTab()]);
  const [activeTabId, setActiveTabId] = useState<string>(() => tabs[0]?.id || '');
  // Backend D2/D16 tree node pointer per tab (thread_id = tab.id)
  const backendTreeNodeByTabRef = useRef<Record<string, string>>({});

  // NEW: UI Command Handler Integration
  const executeUICommands = useCallback((commands: any[], sendMessageFn?: (msg: string) => void) => {
    if (!commands || commands.length === 0) {
      console.log("[executeUICommands] No commands to execute");
      return;
    }
    
    console.log(`[executeUICommands] Executing ${commands.length} UI command(s):`, commands.map(c => `${c.action}${c.params?.pgn ? ` (PGN length: ${c.params.pgn.length})` : ''}`));
    
    try {
      handleUICommands(commands, {
        setFen: (newFen: string) => {
          setFen(newFen);
          setGame(new Chess(newFen));
        },
        setPgn: (newPgn: string) => {
          setPgn(newPgn);
          // Also need to rebuild the move tree if PGN changes
          try {
            const tree = MoveTree.fromPGN(newPgn);
            setMoveTree(tree);
          } catch (e) {
            console.error("Failed to rebuild move tree from PGN:", e);
          }
        },
        setAnnotations: (ann: any) => {
          setAnnotations(prev => ({
            ...prev,
            arrows: ann.arrows || [],
            highlights: ann.highlights || []
          }));
        },
        navigate: (index?: number, offset?: number) => {
          if (index !== undefined) {
            // Find node by index (ply)
            const node = moveTree.findNodeByPly(index);
            if (node) handleMoveClick(node);
          } else if (offset !== undefined) {
            // Navigate forward/backward
            if (offset > 0) {
              // Go forward in main line
              let current = moveTree.currentNode;
              for (let i = 0; i < offset; i++) {
                if (current.children.length > 0) {
                  current = current.children[0];
                } else break;
              }
              handleMoveClick(current);
            } else if (offset < 0) {
              // Go backward
              let current = moveTree.currentNode;
              for (let i = 0; i < Math.abs(offset); i++) {
                if (current.parent) {
                  current = current.parent;
                } else break;
              }
              handleMoveClick(current);
            }
          }
        },
        pushMove: (san: string) => {
          // Play a move on the board
          const tempGame = new Chess(fen);
          const move = tempGame.move(san);
          if (move) {
            handleMove(move.from, move.to, move.promotion);
          }
        },
        deleteMove: (ply?: number) => {
          if (typeof ply === "number") {
            const node = moveTree.findNodeByPly(ply);
            if (node) handleDeleteMove(node);
            return;
          }
          handleDeleteMove(moveTree.currentNode);
        },
        deleteVariation: (ply?: number) => {
          if (typeof ply === "number") {
            const node = moveTree.findNodeByPly(ply);
            if (node) handleDeleteVariation(node);
            return;
          }
          handleDeleteVariation(moveTree.currentNode);
        },
        promoteVariation: (ply?: number) => {
          if (typeof ply === "number") {
            const node = moveTree.findNodeByPly(ply);
            if (node) handlePromoteVariation(node);
            return;
          }
          handlePromoteVariation(moveTree.currentNode);
        },
        setAiGame: async (active: boolean, aiSide: 'white' | 'black' | null = null, makeMoveNow: boolean = false) => {
          console.log(`[setAiGame] Setting AI game: active=${active}, aiSide=${aiSide}, makeMoveNow=${makeMoveNow}`);
          setAiGameActive(active);
          if (active) {
            setMode("PLAY");
            // If makeMoveNow is true, check if it's the AI's turn and make a move
            if (makeMoveNow) {
              const currentTurn = fen.split(' ')[1]; // 'w' or 'b'
              // Determine if it's the AI's turn
              // If aiSide is null, AI plays the current turn
              // Otherwise, check if currentTurn matches aiSide
              const isAiTurn = aiSide === null || 
                              (aiSide === 'white' && currentTurn === 'w') || 
                              (aiSide === 'black' && currentTurn === 'b');
              
              if (isAiTurn) {
                console.log(`[setAiGame] Making AI move (turn: ${currentTurn}, aiSide: ${aiSide})`);
                try {
                  // Use playMove endpoint which correctly handles side-to-move
                  // This ensures the engine chooses the best move for the side to move
                  const response = await playMove(fen, "", undefined, 1500);
                  
                  if (response.legal && response.engine_move_san && response.new_fen) {
                    console.log(`[setAiGame] Engine recommends: ${response.engine_move_san}`);
                    
                    // Apply the engine move using handleMove
                    const tempGame = new Chess(fen);
                    const move = tempGame.move(response.engine_move_san);
                    if (move) {
                      console.log(`[setAiGame] Applying move: ${move.from}${move.to}`);
                      // Use handleMove to properly trigger all move handling logic
                      handleMove(move.from, move.to, move.promotion);
                    } else {
                      console.error(`[setAiGame] Invalid move: ${response.engine_move_san}`);
                    }
                  } else {
                    console.error('[setAiGame] Invalid response from playMove:', response);
                  }
                } catch (err) {
                  console.error('[setAiGame] Error making AI move:', err);
                }
              } else {
                console.log(`[setAiGame] Not AI's turn (turn: ${currentTurn}, aiSide: ${aiSide})`);
              }
            }
          } else {
            // Disable AI game mode
            setMode("DISCUSS");
          }
        },
        newTab: (params: any) => {
          if (tabs.length >= MAX_BOARD_TABS) return; // Limit tabs
          
          const newTabId =
            typeof crypto !== "undefined" && "randomUUID" in crypto
              ? `tab-${crypto.randomUUID()}`
              : `tab-${Date.now()}-${Math.random().toString(16).slice(2)}`;
          let newMoveTree = new MoveTree();
          const newTab: BoardTabState = {
            ...createDefaultTab(tabs.length + 1),
            id: newTabId,
            name: params.title || (params.type === 'lesson' ? 'Lesson' : 'Review'),
            tabType: params.type || 'review',
            fen: params.fen || INITIAL_FEN,
            pgn: params.pgn || '',
            game: new Chess(params.fen || INITIAL_FEN),
            moveTree: newMoveTree,
            isAnalyzing: false,
            hasUnread: false,
            isModified: false,
            messages: [],
            annotations: {
              fen: params.fen || INITIAL_FEN,
              pgn: params.pgn || '',
              arrows: [],
              highlights: [],
              comments: [],
              nags: []
            },
            analysisCache: {},
            moveHistory: []
          };
          
          if (params.pgn) {
            try {
              console.log(`[newTab] Loading PGN into new tab. PGN length: ${params.pgn.length}, preview: ${params.pgn.substring(0, 100)}...`);
              newMoveTree = MoveTree.fromPGN(params.pgn);
              newTab.moveTree = newMoveTree;
              // Recreate game from PGN to ensure board state matches
              const gameFromPgn = new Chess();
              gameFromPgn.loadPgn(params.pgn);
              newTab.game = gameFromPgn;
              newTab.fen = gameFromPgn.fen();
              // Update annotations to match
              newTab.annotations.fen = gameFromPgn.fen();
              newTab.annotations.pgn = params.pgn;
              // Also update the tab's pgn field
              newTab.pgn = params.pgn;
              console.log(`[newTab] Successfully loaded PGN. Final FEN: ${newTab.fen}, moveTree length: ${newTab.moveTree.getMainLine().length}`);
            } catch (e) {
              console.error("[newTab] Failed to load PGN into new tab:", e);
              console.error("[newTab] PGN that failed:", params.pgn?.substring(0, 200));
              // Still set the PGN even if parsing fails, so it's available
              newTab.pgn = params.pgn;
              newTab.annotations.pgn = params.pgn;
            }
          } else {
            console.warn("[newTab] No PGN provided in params:", params);
          }
          
          setTabs(prev => (prev.some(t => t.id === newTabId) ? prev : [...prev, newTab]));
          setActiveTabId(newTabId);
          
          // Update global state
          setFen(newTab.fen);
          setPgn(newTab.pgn);
          setGame(newTab.game);
          setMoveTree(newTab.moveTree);
          
          // If initialMessage is provided, send it after a short delay to ensure tab is active
          if (params.initialMessage && sendMessageFn) {
            const messageToSend = params.initialMessage;
            const tabIdToCheck = newTabId;
            setTimeout(() => {
              // Check if this tab is still active by reading current state
              setTabs(currentTabs => {
                const tabStillExists = currentTabs.some(t => t.id === tabIdToCheck);
                if (tabStillExists) {
                  sendMessageFn(messageToSend);
                }
                return currentTabs;
              });
            }, 100);
          }
        }
      });
    } catch (err) {
      console.error("[executeUICommands] Error executing UI commands:", err);
    }
  }, [tabs, activeTabId, fen, moveTree, handleMove, handleMoveClick]);
  
  // Get active tab
  const activeTab = tabs.find(t => t.id === activeTabId) || tabs[0];
  
  // Tab management functions
  const updateActiveTab = useCallback((updates: Partial<BoardTabState>) => {
    setTabs(prevTabs => prevTabs.map(tab => 
      tab.id === activeTabId 
        ? { ...tab, ...updates, isModified: true }
        : tab
    ));
  }, [activeTabId]);
  
  // Guard to prevent multiple simultaneous tab switches
  const isSwitchingTabsRef = useRef(false);
  
  const handleTabSelect = useCallback((tabId: string) => {
    if (tabId === activeTabId) return; // Already on this tab
    if (isSwitchingTabsRef.current) {
      console.warn('⚠️ Tab switch already in progress, ignoring');
      return;
    }
    
    isSwitchingTabsRef.current = true;
    console.log('🔄 Switching tabs:', { from: activeTabId, to: tabId, currentPgnLength: pgnRef.current.length });
    
    // CRITICAL: Force a sync of current state to active tab BEFORE switching
    // Use refs to get the absolute latest values (avoid stale closures)
    const currentFen = fenRef.current;
    const currentPgn = pgnRef.current;
    
    setTabs(prevTabs => {
      const currentTab = prevTabs.find(t => t.id === activeTabId);
      if (!currentTab) {
        isSwitchingTabsRef.current = false;
        return prevTabs;
      }
      
      // Always sync - use refs to ensure we have latest values
      const needsSync = currentTab.fen !== currentFen || currentTab.pgn !== currentPgn;
      if (needsSync) {
        console.log('💾 Syncing current tab before switch:', {
          tabId: currentTab.id,
          oldPgnLength: currentTab.pgn.length,
          newPgnLength: currentPgn.length,
          pgnChanged: currentTab.pgn !== currentPgn
        });
      }
      
      // Find the new tab
      const newTab = prevTabs.find(t => t.id === tabId);
      if (!newTab) {
        console.warn('⚠️ Tab not found:', tabId);
        isSwitchingTabsRef.current = false;
        return prevTabs;
      }
      
      // Handle game mode state on tab switch
      // Store game state in current tab before switching
      const currentTabGameState = {
        aiGameActive: aiGameActive,
        aiGameElo: aiGameElo,
        aiGameUserSide: aiGameUserSide
      };
      
      // Update tabs: sync current tab with game state, mark new tab as read
      const updatedTabs = prevTabs.map(tab => {
        if (tab.id === activeTabId) {
          // Always update with latest global state (even if it looks the same, use refs)
          return { 
            ...tab, 
            fen: currentFen, 
            pgn: currentPgn, 
            game: new Chess(currentFen), 
            isModified: currentFen !== INITIAL_FEN,
            ...currentTabGameState
          };
        }
        if (tab.id === tabId) {
          return { ...tab, hasUnread: false };
        }
        return tab;
      });
      
      // Store the new tab's data
      const newTabData = {
        fen: newTab.fen,
        pgn: newTab.pgn,
        moveTree: newTab.moveTree || new MoveTree()
      };
      
      console.log('📋 Tab states after sync:', {
        currentTab: {
          id: currentTab.id,
          pgnLength: currentPgn.length,
          pgnPreview: currentPgn.substring(0, 50)
        },
        newTab: {
          id: newTab.id,
          pgnLength: newTab.pgn.length,
          pgnPreview: newTab.pgn.substring(0, 50)
        }
      });
      
      // Check if the tab we're entering has game state
      const enteringTabGameState = newTab.aiGameActive === true;
      const leavingTabGameState = currentTabGameState.aiGameActive === true;
      
      // Note: Game mode pause/resume will be handled inside setTimeout after tab data loads
      
      // Load the new tab's state into global (use setTimeout to ensure setTabs completes)
      setTimeout(() => {
        console.log('📥 Loading new tab state into global:', {
          pgnLength: newTabData.pgn.length,
          pgnPreview: newTabData.pgn.substring(0, 50)
        });
        
        isSwitchingTabRef.current = true; // Prevent sync useEffect from interfering
        
        setActiveTabId(tabId);
        setFen(newTabData.fen);
        setPgn(newTabData.pgn);
        setLessonMode(newTab.tabType === 'lesson');
        
        // CRITICAL: Load the tab's messages into global state
        const tabMessages = newTab.messages || [];
        console.log('💬 Loading tab messages into global state:', { tabId, messageCount: tabMessages.length });
        setMessages(tabMessages);
        
        const newGame = new Chess();
        let loadedMoveTree = newTabData.moveTree;
        
        // CRITICAL: Rebuild moveTree from PGN to ensure it's in sync
        // The stored moveTree might be stale or not properly serialized
        if (newTabData.pgn && newTabData.pgn.trim()) {
          try { 
            newGame.loadPgn(newTabData.pgn); 
            console.log('✅ Successfully loaded PGN from tab');
            
            // Rebuild moveTree from PGN to ensure it matches
            try {
              const rebuilt = rebuildMoveTreeFromPGN(newTabData.pgn);
              loadedMoveTree = rebuilt.tree;
              
              // Navigate to the end of the game to show all moves in PGNViewer
              // The rebuild function calls goToStart(), so we need to go to the end
              let node = loadedMoveTree.root;
              while (node.children.length > 0) {
                node = node.children[0]; // Follow main line
              }
              loadedMoveTree.currentNode = node;
              
              // Update FEN to match the rebuilt game (in case it differs)
              const finalFen = rebuilt.finalFen;
              if (finalFen !== newTabData.fen) {
                console.log('🔄 FEN updated from rebuilt PGN:', finalFen.substring(0, 30));
                setFen(finalFen);
                newGame.load(finalFen);
              } else {
                setFen(finalFen);
              }
              
              console.log('✅ Rebuilt moveTree from PGN, positioned at end');
            } catch (treeError) {
              console.warn('⚠️ Failed to rebuild moveTree, using stored:', treeError);
              // Fall back to stored moveTree, but try to position it correctly
              if (loadedMoveTree && newTabData.fen) {
                // Try to find the node matching the current FEN
                const findNodeByFen = (node: MoveNode, targetFen: string): MoveNode | null => {
                  if (node.fen === targetFen) return node;
                  for (const child of node.children) {
                    const found = findNodeByFen(child, targetFen);
                    if (found) return found;
                  }
                  return null;
                };
                const matchingNode = findNodeByFen(loadedMoveTree.root, newTabData.fen);
                if (matchingNode) {
                  loadedMoveTree.currentNode = matchingNode;
                }
              }
            }
          } catch (e) { 
            console.warn('❌ Failed to load PGN:', e);
            // If PGN fails, try loading from FEN
            if (newTabData.fen !== INITIAL_FEN) {
              try { 
                newGame.load(newTabData.fen); 
                console.log('✅ Loaded FEN from tab (PGN failed)');
              } catch (e2) { 
                console.warn('❌ Failed to load FEN:', e2); 
              }
            }
          }
        } else if (newTabData.fen !== INITIAL_FEN) {
          try { 
            newGame.load(newTabData.fen); 
            console.log('✅ Loaded FEN from tab');
          } catch (e) { 
            console.warn('❌ Failed to load FEN:', e); 
          }
        }
        
        setGame(newGame);
        setMoveTree(loadedMoveTree);
        
        // Handle game mode pause/resume after tab data is loaded
        // Use the captured variables from the outer scope
        const shouldPause = leavingTabGameState && !enteringTabGameState;
        const shouldResume = !leavingTabGameState && enteringTabGameState;
        
        if (shouldPause) {
          // Leaving game tab - pause game mode
          setAiGameActive(false);
          // Add system message (only once)
          const filteredContent = stripEmojis("Game mode is paused. Return to the previous tab to resume.");
          setMessages((prev) => {
            // Check if message already exists to prevent duplicates
            const lastMessage = prev[prev.length - 1];
            if (lastMessage?.role === "system" && lastMessage?.content === filteredContent) {
              return prev;
            }
            return [...prev, { 
              role: "system", 
              content: filteredContent, 
              fen: newTabData.fen, 
              tabId: tabId 
            }];
          });
        } else if (shouldResume) {
          // Returning to game tab - resume game mode
          setAiGameActive(true);
          setAiGameElo(newTab.aiGameElo || 1500);
          setAiGameUserSide(newTab.aiGameUserSide || null);
          // Add system message (only once)
          const filteredContent = stripEmojis("Game resumed.");
          setMessages((prev) => {
            // Check if message already exists to prevent duplicates
            const lastMessage = prev[prev.length - 1];
            if (lastMessage?.role === "system" && lastMessage?.content === filteredContent) {
              return prev;
            }
            return [...prev, { 
              role: "system", 
              content: filteredContent, 
              fen: newTabData.fen, 
              tabId: tabId 
            }];
          });
        }
        
        // Verify the PGN was set correctly
        setTimeout(() => {
          console.log('✅ Tab switch complete. PGN length:', pgnRef.current.length);
          isSwitchingTabRef.current = false;
          isSwitchingTabsRef.current = false;
        }, 50);
      }, 0);
      
      return updatedTabs;
    });
  }, [activeTabId, aiGameActive, aiGameElo, aiGameUserSide]); // Added game state to deps
  
  const handleTabClose = useCallback((tabId: string) => {
    setTabs(prevTabs => {
      if (prevTabs.length <= 1) return prevTabs;
      const newTabs = prevTabs.filter(t => t.id !== tabId);
      // If closing active tab, switch to previous or first tab
      if (tabId === activeTabId) {
        const closedIndex = prevTabs.findIndex(t => t.id === tabId);
        const newActiveIndex = Math.max(0, closedIndex - 1);
        setActiveTabId(newTabs[newActiveIndex]?.id || newTabs[0]?.id);
      }
      return newTabs;
    });
  }, [activeTabId]);
  
  const handleTabRename = useCallback((tabId: string, newName: string) => {
    setTabs(prevTabs => prevTabs.map(tab => 
      tab.id === tabId ? { ...tab, name: newName } : tab
    ));
  }, []);
  
  const handleTabDuplicate = useCallback((tabId: string) => {
    const tabToDuplicate = tabs.find(t => t.id === tabId);
    if (!tabToDuplicate || tabs.length >= 5) return;
    
    const newTab: BoardTabState = {
      ...tabToDuplicate,
      id: `tab-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      name: `${tabToDuplicate.name} (copy)`,
      createdAt: Date.now(),
      game: new Chess(tabToDuplicate.fen),
      moveTree: new MoveTree(), // Start fresh tree
      hasUnread: false,
    };
    
    setTabs(prevTabs => [...prevTabs, newTab]);
    setActiveTabId(newTab.id);
  }, [tabs]);
  
  const handleNewTab = useCallback(() => {
    if (tabs.length >= 5) return;
    
    // Save current tab state before creating new one
    if (activeTabId) {
      setTabs(prevTabs => prevTabs.map(tab => 
        tab.id === activeTabId 
          ? { ...tab, fen: fenRef.current, pgn: pgnRef.current, game: new Chess(fenRef.current) }
          : tab
      ));
    }
    
    const newTab = createInitialTab();
    newTab.name = `Board ${tabs.length + 1}`;
    
    setTabs(prevTabs => [...prevTabs, newTab]);
    setActiveTabId(newTab.id);
    
    // Reset global state to match new tab (empty PGN, starting position)
    setFen(INITIAL_FEN);
    setPgn('');
    setGame(new Chess());
    setMoveTree(new MoveTree());
    
    console.log('✅ Created new tab with empty PGN and starting position');
  }, [tabs.length, activeTabId]);
  
  // Helper functions for PGN loading (defined before loadGameIntoTab)
  const getStartingFENFromPGN = (pgnString: string) => {
    const setupMatch = pgnString.match(/\[SetUp\s+"1"\]/i);
    const fenMatch = pgnString.match(/\[FEN\s+"([^"]+)"\]/i);
    if (setupMatch && fenMatch && fenMatch[1]) {
      return fenMatch[1];
    }
    return INITIAL_FEN;
  };

  const rebuildMoveTreeFromPGN = (pgnString: string) => {
    const parser = new Chess();
    const loadResult = (parser as any).loadPgn(pgnString, { sloppy: true }) as boolean | undefined;
    if (loadResult === false) {
      throw new Error("Invalid PGN string");
    }
    const startFen = getStartingFENFromPGN(pgnString);

    const verboseMoves = parser.history({ verbose: true }) as Move[];
    console.log('[PGN Loader] Parsed moves', {
      moveCount: verboseMoves.length,
      startFen,
    });
    const playback = new Chess(startFen);
    const newTree = new MoveTree();
    newTree.root.fen = startFen;
    newTree.currentNode = newTree.root;

    verboseMoves.forEach((move) => {
      if (move?.san) {
        playback.move(move.san);
        newTree.addMove(move.san, playback.fen());
      }
    });

    // Set currentNode to the end of the main line (not start) to show full game
    let endNode = newTree.root;
    while (endNode.children.length > 0) {
      endNode = endNode.children[0]; // Follow main line
    }
    newTree.currentNode = endNode;
    
    return { tree: newTree, finalGame: playback, finalFen: playback.fen() };
  };
  
  // Load game into tab (new or current based on current state)
  const loadGameIntoTab = useCallback((gameData: {
    pgn: string;
    fen?: string;
    white?: string;
    black?: string;
    date?: string;
    result?: string;
    timeControl?: string;
    opening?: string;
  }, options?: { forceNewTab?: boolean }) => {
    const { forceNewTab = false } = options || {};
    const isCurrentTabEmpty = activeTab.pgn === '' && activeTab.fen === INITIAL_FEN;
    
    const loadIntoCurrentTab = () => {
      if (!gameData.pgn) {
        console.warn('No PGN provided to loadGameIntoTab');
        return;
      }
      
      let finalGame: Chess;
      let finalFen: string;
      let tree: MoveTree;
      
      try {
        const { tree: rebuiltTree, finalGame: rebuiltGame, finalFen: rebuiltFen } = rebuildMoveTreeFromPGN(gameData.pgn);
        finalGame = rebuiltGame;
        finalFen = rebuiltFen;
        tree = rebuiltTree;
      } catch (e) {
        console.warn('Failed to rebuild moveTree from PGN:', e);
        const newGame = new Chess();
        try {
          newGame.loadPgn(gameData.pgn);
        } catch (loadErr) {
          console.warn('Failed to load PGN:', loadErr);
          return;
        }
        finalGame = newGame;
        finalFen = finalGame.fen();
        const emptyTree = new MoveTree();
        emptyTree.root.fen = finalFen;
        emptyTree.currentNode = emptyTree.root;
        tree = emptyTree;
      }
      
      let endNode = tree.root;
      while (endNode.children.length > 0) {
        endNode = endNode.children[0];
      }
      tree.currentNode = endNode;
      
      setPgn(gameData.pgn);
      setFen(finalFen);
      setGame(finalGame);
      setMoveTree(tree);
      
      updateActiveTab({
        pgn: gameData.pgn,
        fen: finalFen,
        game: finalGame,
        moveTree: tree,
        name: generateTabName({
          pgn: gameData.pgn,
          metadata: {
            white: gameData.white,
            black: gameData.black,
            date: gameData.date,
            result: gameData.result,
            timeControl: gameData.timeControl,
            opening: gameData.opening,
          }
        }),
        metadata: {
          white: gameData.white,
          black: gameData.black,
          date: gameData.date,
          result: gameData.result,
          timeControl: gameData.timeControl,
          opening: gameData.opening,
        },
        isModified: false,
      });
    };
    
    if (isCurrentTabEmpty && !forceNewTab) {
      loadIntoCurrentTab();
      return;
    }
    
    if (tabs.length < MAX_BOARD_TABS) {
      const newTab = createTabFromGame(gameData) as BoardTabState;
      const newGame = new Chess();
      if (gameData.pgn) {
        try {
          newGame.loadPgn(gameData.pgn);
        } catch (e) {
          console.warn('Failed to load PGN:', e);
        }
      }
      
      newTab.fen = newGame.fen();
      newTab.game = newGame;
      newTab.moveTree = new MoveTree();
      newTab.annotations = {
        fen: newGame.fen(),
        pgn: gameData.pgn,
        comments: [],
        nags: [],
        arrows: [],
        highlights: [],
      };
      newTab.analysisCache = {};
      newTab.messages = [];
      newTab.moveHistory = [];
      newTab.isAnalyzing = false;
      newTab.hasUnread = false;
      newTab.isModified = false;
      
      setTabs(prevTabs => (prevTabs.some(t => t.id === newTab.id) ? prevTabs : [...prevTabs, newTab]));
      setActiveTabId(newTab.id);
      return;
    }
    
    console.warn('⚠️ Maximum board tabs reached; loading into active tab instead.');
    loadIntoCurrentTab();
  }, [activeTab, tabs.length, updateActiveTab]);
  
  // Mark tab as analyzing
  const setTabAnalyzing = useCallback((tabId: string, isAnalyzing: boolean) => {
    setTabs(prevTabs => prevTabs.map(tab => 
      tab.id === tabId ? { ...tab, isAnalyzing } : tab
    ));
  }, []);
  
  // Mark tab as having unread messages
  const setTabHasUnread = useCallback((tabId: string, hasUnread: boolean) => {
    setTabs(prevTabs => prevTabs.map(tab => 
      tab.id === tabId ? { ...tab, hasUnread } : tab
    ));
  }, []);
  
  // Sync global state changes back to active tab (when moves are made)
  // Track if we're currently switching tabs to prevent race condition
  const isSwitchingTabRef = useRef(false);
  
  useEffect(() => {
    if (!activeTabId) return;
    
    // Skip sync if we're in the middle of a tab switch
    if (isSwitchingTabRef.current) {
      return;
    }
    
    // Use functional update to get latest tabs state
    setTabs(prevTabs => {
      const currentTab = prevTabs.find(t => t.id === activeTabId);
      if (!currentTab) return prevTabs;
      
      // Only sync if tab's data differs from global (prevents overwriting during tab switch)
      // This ensures we only update the tab when global state changes, not when we're loading tab state
      if (currentTab.fen !== fen || currentTab.pgn !== pgn) {
        return prevTabs.map(tab => 
          tab.id === activeTabId 
            ? { ...tab, fen, pgn, game: new Chess(fen), isModified: fen !== INITIAL_FEN }
            : tab
        );
      }
      return prevTabs;
    });
  }, [fen, pgn, activeTabId]); // Removed 'tabs' from deps to prevent re-running on tab changes
  
  // ==========================================
  // TAB PERSISTENCE (localStorage)
  // ==========================================
  
  const TABS_STORAGE_KEY = 'chess-gpt-tabs';
  const MAX_STORAGE_AGE_MS = 7 * 24 * 60 * 60 * 1000; // 7 days
  
  // Load tabs from localStorage on mount
  useEffect(() => {
    try {
      const saved = localStorage.getItem(TABS_STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        const { tabs: savedTabs, activeTabId: savedActiveId, savedAt } = parsed;
        
        console.log(`🔍 [TAB RESTORE] Loading from localStorage:`, {
          tabCount: savedTabs?.length || 0,
          savedAt: new Date(savedAt).toISOString(),
          activeTabId: savedActiveId,
        });
        
        // Log what's in each saved tab
        if (savedTabs && savedTabs.length > 0) {
          savedTabs.forEach((t: any, idx: number) => {
            console.log(`🔍 [TAB RESTORE] Tab ${idx}:`, {
              id: t.id,
              name: t.name,
              pgnLength: (t.pgn || '').length,
              pgnPreview: (t.pgn || '').substring(0, 100),
              fen: t.fen?.substring(0, 30),
              hasPgn: !!(t.pgn && t.pgn.trim()),
            });
          });
        }
        
        // Check if data is too old
        if (Date.now() - savedAt > MAX_STORAGE_AGE_MS) {
          console.log('🗑️ Clearing old tab session (> 7 days)');
          localStorage.removeItem(TABS_STORAGE_KEY);
          return;
        }
        
        // Restore tabs (need to recreate Chess and MoveTree objects)
        if (savedTabs && savedTabs.length > 0) {
          // De-dupe tab ids (React keys) and re-id collisions to prevent "duplicate key" crashes.
          const seen = new Set<string>();
          const restoredTabs: BoardTabState[] = savedTabs.map((t: any, idx: number) => {
            const rawId = typeof t?.id === "string" ? t.id : "";
            const needsNewId = !rawId || seen.has(rawId);
            const safeId = needsNewId
              ? (typeof crypto !== "undefined" && "randomUUID" in crypto
                  ? `tab-${crypto.randomUUID()}`
                  : `tab-${Date.now()}-${idx}-${Math.random().toString(16).slice(2)}`)
              : rawId;
            seen.add(safeId);
            
            // Load PGN into moveTree if available
            let moveTree = new MoveTree();
            let game = new Chess(t.fen || INITIAL_FEN);
            const tabPgn = t.pgn || '';
            
            console.log(`🔍 [TAB RESTORE] Processing tab ${safeId}:`, {
              originalId: rawId,
              pgnLength: tabPgn.length,
              pgnPreview: tabPgn.substring(0, 50),
              hasPgn: !!(tabPgn && tabPgn.trim()),
              savedFen: t.fen?.substring(0, 30),
            });
            
            if (tabPgn && tabPgn.trim()) {
              try {
                // Load PGN into Chess game
                game.loadPgn(tabPgn);
                
                // Build moveTree from PGN
                moveTree = MoveTree.fromPGN(tabPgn);
                
                // Navigate to the end of the game to show all moves
                let node = moveTree.root;
                while (node.children.length > 0) {
                  node = node.children[0]; // Follow main line
                }
                moveTree.currentNode = node;
                
                // Update FEN to match the final position from PGN
                const finalFen = game.fen();
                console.log(`✅ [TAB RESTORE] Tab ${safeId}: PGN loaded successfully`, {
                  pgnLength: tabPgn.length,
                  finalFen: finalFen.substring(0, 30),
                  moveTreeNodes: moveTree.getMainLine().length,
                });
              } catch (e) {
                console.warn(`⚠️ [TAB RESTORE] Failed to load PGN for tab ${safeId}:`, e);
                console.warn(`⚠️ [TAB RESTORE] PGN that failed:`, tabPgn.substring(0, 200));
                // Fallback to FEN-only
                game = new Chess(t.fen || INITIAL_FEN);
                moveTree = new MoveTree();
              }
            } else {
              console.log(`⚠️ [TAB RESTORE] Tab ${safeId}: No PGN found, using FEN only`);
              // No PGN, just use FEN
              game = new Chess(t.fen || INITIAL_FEN);
              moveTree = new MoveTree();
            }
            
            const restoredTab = {
              ...t,
              id: safeId,
              game,
              moveTree,
              fen: game.fen(), // Ensure FEN matches the loaded game
              pgn: tabPgn, // Preserve the PGN string
              annotations: t.annotations || {
                fen: game.fen(),
                pgn: tabPgn,
                comments: [],
                nags: [],
                arrows: [],
                highlights: [],
              },
            };
            
            console.log(`📂 [TAB RESTORE] Restored tab ${safeId}:`, {
              name: restoredTab.name,
              pgnLength: restoredTab.pgn.length,
              fen: restoredTab.fen.substring(0, 30),
            });
            
            return restoredTab;
          });
          setTabs(restoredTabs);
          
          // Restore active tab and immediately set global state to prevent sync from overwriting
          const firstId = restoredTabs[0]?.id;
          const activeId = (savedActiveId && restoredTabs.some((t: BoardTabState) => t.id === savedActiveId)) 
            ? savedActiveId 
            : firstId;
          
          if (activeId) {
            const activeTab = restoredTabs.find((t: BoardTabState) => t.id === activeId);
            if (activeTab) {
              console.log(`📂 [TAB RESTORE] Restoring active tab ${activeId}:`, {
                name: activeTab.name,
                pgnLength: activeTab.pgn.length,
                fen: activeTab.fen.substring(0, 30),
              });
              
              // CRITICAL: Prevent sync useEffect from overwriting during restore
              isSwitchingTabRef.current = true;
              
              // Set the refs first to ensure they're available
              fenRef.current = activeTab.fen;
              pgnRef.current = activeTab.pgn;
              
              // Then set the state
              setFen(activeTab.fen);
              setPgn(activeTab.pgn);
              setGame(activeTab.game);
              setMoveTree(activeTab.moveTree);
              setLessonMode(activeTab.tabType === 'lesson');
              
              // Set active tab ID last
              setActiveTabId(activeId);
              
              // Clear the flag after a short delay to allow state to settle
              setTimeout(() => {
                isSwitchingTabRef.current = false;
                console.log(`✅ [TAB RESTORE] Restore complete for tab ${activeId}`);
              }, 100);
            }
          }
          
          console.log(`📂 [TAB RESTORE] Restored ${restoredTabs.length} tabs from session`);
        }
      } else {
        console.log(`🔍 [TAB RESTORE] No saved tabs found in localStorage`);
      }
    } catch (e) {
      console.warn('❌ [TAB RESTORE] Failed to load tabs from localStorage:', e);
    }
  }, []); // Only run on mount
  
  // Save tabs to localStorage on changes (debounced)
  useEffect(() => {
    const saveTimeout = setTimeout(() => {
      try {
        // Serialize tabs (excluding non-serializable objects)
        const serializableTabs = tabs.map(t => {
          const serialized = {
            id: t.id,
            name: t.name,
            fen: t.fen,
            pgn: t.pgn,
            moveHistory: t.moveHistory,
            analysisCache: Object.keys(t.analysisCache || {}).length > 50 
              ? {} // Clear if too large
              : t.analysisCache,
            messages: t.messages.slice(-50), // Keep last 50 messages per tab
            metadata: t.metadata,
            isAnalyzing: false, // Reset
            hasUnread: false, // Reset
            isModified: t.isModified,
            createdAt: t.createdAt,
          };
          
          console.log(`💾 [TAB SAVE] Saving tab ${t.id}:`, {
            name: serialized.name,
            pgnLength: (serialized.pgn || '').length,
            pgnPreview: (serialized.pgn || '').substring(0, 50),
            fen: serialized.fen?.substring(0, 30),
          });
          
          return serialized;
        });
        
        const saveData = {
          tabs: serializableTabs,
          activeTabId,
          savedAt: Date.now(),
        };
        
        console.log(`💾 [TAB SAVE] Saving ${serializableTabs.length} tabs to localStorage`);
        localStorage.setItem(TABS_STORAGE_KEY, JSON.stringify(saveData));
      } catch (e) {
        console.warn('❌ [TAB SAVE] Failed to save tabs to localStorage:', e);
      }
    }, 1000); // Debounce 1 second
    
    return () => clearTimeout(saveTimeout);
  }, [tabs, activeTabId]);
  
  // ==========================================
  // END MULTI-TAB STATE
  // ==========================================

  // NEW: ChatGPT-style UI state
  const [isFirstMessage, setIsFirstMessage] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [showLoadGame, setShowLoadGame] = useState(false);
  const [boardDockOpen, setBoardDockOpen] = useState(false);
  const [showRequestOptions, setShowRequestOptions] = useState(false);
  const [showGameSetup, setShowGameSetup] = useState(false);
  const [isLegacyReviewing, setIsLegacyReviewing] = useState(false);
  const [showAuthModal, setShowAuthModal] = useState(false);
  const pendingOpeningLessonQueryRef = useRef<string | undefined>(undefined);
  const [pendingImage, setPendingImage] = useState<{ data: string; filename: string; mimeType: string } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleShowBoardFromMessage = useCallback((payload?: {
    finalPgn?: string;
    fen?: string;
    showBoardLink?: string;
  }) => {
    if (!payload) return;
    
    let finalPgn = payload.finalPgn;
    let fenOverride = payload.fen;
    
    if (!finalPgn && payload.showBoardLink) {
      try {
        const base = typeof window !== 'undefined' ? window.location.origin : 'http://localhost:3000';
        const url = new URL(payload.showBoardLink, base);
        finalPgn = url.searchParams.get('pgn') || undefined;
        fenOverride = fenOverride || url.searchParams.get('fen') || undefined;
      } catch (err) {
        console.warn('Failed to parse show_board_link:', err);
      }
    }
    
    if (!finalPgn) {
      console.warn('Show Board requested but no PGN available');
      return;
    }
    
    setBoardDockOpen(true);
    loadGameIntoTab(
      {
        pgn: finalPgn,
        fen: fenOverride,
      },
      { forceNewTab: true }
    );
  }, [loadGameIntoTab]);

  const describeCandidateSource = (candidate: any) => {
    if (!candidate) return "master database sample";
    if (candidate.source === "personal") {
      const result = candidate.personal_result ? ` (${candidate.personal_result})` : "";
      const opp = candidate.opponent ? ` vs ${candidate.opponent}` : "";
      return `your game${opp}${result}`.trim();
    }
    if (candidate.source === "master") return "top-player sample";
    if (candidate.source === "titlebase") return "GM database";
    return candidate.source || "database sample";
  };

  const personalCandidateNote = (candidate: any) => {
    if (!candidate || candidate.source !== "personal") return "";
    if (candidate.was_mistake === true) return " (in your game this was punished)";
    if (candidate.was_mistake === false) return " (you handled this well in your own game)";
    const result = candidate.personal_result ? ` (${candidate.personal_result})` : "";
    return ` (seen in your own game${result})`;
  };

  const formatOpeningCandidateLine = (candidate: any) => {
    if (!candidate) return null;
    const moveLabel = candidate.san || candidate.move || candidate.uci || "…";
    const usage =
      typeof candidate.play_rate === "number"
        ? `${Math.round(candidate.play_rate * 100)}% usage`
        : candidate.popularity != null
          ? `${Math.round(candidate.popularity * 100)}% usage`
          : null;
    const success =
      typeof candidate.win_rate === "number"
        ? `${Math.round(candidate.win_rate * 100)}% success`
        : candidate.score != null
          ? `${Math.round(candidate.score * 100)}% score`
          : null;
    const stats = [usage, success].filter(Boolean).join(" · ");
    const plan =
      candidate.plan ||
      candidate.comment ||
      candidate.summary ||
      candidate.idea ||
      candidate.description ||
      "Keeps the structure flexible.";
    const personalNote = personalCandidateNote(candidate);
    return `• **${moveLabel}**${stats ? ` (${stats})` : ""} – ${plan} — ${describeCandidateSource(candidate)}${personalNote}`;
  };

  const enterLessonMode = useCallback(() => {
    console.log("[LESSON DEBUG] enterLessonMode invoked");
    setLessonMode(true);
    setAiGameActive(false);
    setWaitingForEngine(false);
    setMode((prev) => {
      if (prev === "PLAY") {
        console.log("[LESSON DEBUG] Forcing mode DISCUSS while entering lesson mode");
        return "DISCUSS";
      }
      return prev;
    });
  }, []);

  useEffect(() => {
    if (lessonMode) {
      console.log("[LESSON DEBUG] lessonMode active → disabling aiGameActive/waitingForEngine");
      setAiGameActive(false);
      setWaitingForEngine(false);
    }
  }, [lessonMode]);

  const restoreOpeningLessonVisuals = useCallback(async (targetFen?: string) => {
    if (currentLesson?.type !== "opening" || !lessonMode) return;
    
    // Use provided FEN or fall back to state FEN
    const fenToUse = targetFen || fen;
    
    try {
      // Query the current position for candidate moves
      const response = await fetch(
        `${getBackendBase()}/analyze_position?fen=${encodeURIComponent(fenToUse)}&lines=4&depth=16`
      );
      if (!response.ok) {
        console.warn("[OPENING] Failed to query position for arrows");
        return;
      }
      const analysis = await response.json();
      const candidates = Array.isArray(analysis?.candidate_moves) ? analysis.candidate_moves : [];
      
      if (candidates.length === 0) {
        setLessonArrows([]);
        setLessonCueSnapshot(null);
        return;
      }
      
      // Build a position-like object from the analysis
      const positionData = {
        fen: fenToUse,
        popular_replies: candidates.map((c: any) => ({
          san: c.san || c.move,
          popularity: c.play_rate ?? c.popularity,
          score: c.win_rate ?? c.score,
          plan: c.plan,
          comment: c.comment,
        })),
      };
      
      // Build new cue snapshot from current position
      // Note: buildLessonCueSnapshot is defined later in the file but is a pure function
      const rawCandidates = positionData.popular_replies || [];
      const parsed: SnapshotCandidate[] = rawCandidates
        .map((entry: any): SnapshotCandidate | null => {
          if (!entry) return null;
          if (typeof entry === "string") return { san: entry };
          if (typeof entry === "object" && entry.san) {
            return {
              san: entry.san,
              pop: entry.popularity ?? entry.pop,
              score: entry.score ?? entry.win_rate,
            };
          }
          return null;
        })
        .filter((val: SnapshotCandidate | null): val is SnapshotCandidate => Boolean(val));
      
      if (!parsed.length) {
        setLessonArrows([]);
        setLessonCueSnapshot(null);
        return;
      }
      
      const arrows: AnnotationArrow[] = [];
      const main = parsed[0];
      parsed.slice(0, 4).forEach((candidate: SnapshotCandidate, idx: number) => {
        try {
          const tempBoard = new Chess(positionData.fen);
          const move = tempBoard.move(candidate.san);
          if (move?.from && move?.to) {
            arrows.push({
              from: move.from,
              to: move.to,
              color: idx === 0 ? LESSON_ARROW_COLORS.main : LESSON_ARROW_COLORS.alternate,
            });
          }
        } catch (err) {
          // Ignore parsing failures
        }
      });
      
      const fmtPercent = (value?: number) => {
        if (typeof value !== "number" || Number.isNaN(value)) return null;
        return `${Math.round(value * 100)}%`;
      };
      const describe = (candidate: { san: string; pop?: number; score?: number }) => {
        const usage = fmtPercent(candidate.pop);
        const winRate = typeof candidate.score === "number" ? `${Math.round(candidate.score * 100)}%` : null;
        const parts = [usage ? `${usage} usage` : null, winRate ? `${winRate} score` : null].filter(Boolean);
        return parts.length ? `${candidate.san} (${parts.join(" • ")})` : candidate.san;
      };
      
      const description = [
        `Main line: ${describe(main)}`,
        parsed.slice(1, 4).length ? `Alternates: ${parsed.slice(1, 4).map(describe).join(", ")}` : "",
      ]
        .filter(Boolean)
        .join("\n");
      
      const newSnapshot = { arrows, description };
      setLessonCueSnapshot(newSnapshot);
      setLessonArrows(arrows);
      setLessonCueButtonActive(false);
    } catch (err) {
      console.error("[OPENING] Failed to restore lesson visuals:", err);
      setLessonArrows([]);
    }
  }, [currentLesson?.type, lessonMode, fen]);

  const autoPlayOpeningResponse = useCallback(
    async (fenBeforeMove: string, playerMoveSan: string) => {
      if (!lessonMode || currentLesson?.type !== "opening") return;
      try {
        const boardAfterPlayer = new Chess(fenBeforeMove);
        const appliedMove = boardAfterPlayer.move(playerMoveSan);
        if (!appliedMove) {
          console.warn("[OPENING] Failed to apply player move for auto-response:", playerMoveSan);
          return;
        }
        const positionAfterPlayer = boardAfterPlayer.fen();
        setWaitingForEngine(true);

        const engineResponse = await fetch(
          `${getBackendBase()}/analyze_position?fen=${encodeURIComponent(positionAfterPlayer)}&lines=4&depth=16`
        );
        if (!engineResponse.ok) {
          console.error("[OPENING] analyze_position failed:", engineResponse.status);
          if (engineResponse.status >= 500 || engineResponse.status === 0) {
            throw new Error("Connection issue - server unavailable");
          }
          throw new Error(`Server error: ${engineResponse.status}`);
        }
        const analysis = await engineResponse.json();
        const candidates = Array.isArray(analysis?.candidate_moves) ? analysis.candidate_moves : [];
        console.log(`[OPENING] Received ${candidates.length} candidate moves`);
        
        // Query opening explorer for move popularity data
        let allExplorerMoves: Map<string, number> = new Map();
        try {
          if (currentLesson?.plan?.lesson_id) {
            const lessonId = currentLesson.plan.lesson_id;
            // Query for each candidate move to get popularity
            // Start with the first move
            const firstMoveSan = candidates[0]?.move || candidates[0]?.san;
            if (firstMoveSan) {
              const firstMoveResponse = await fetch(
                `${getBackendBase()}/check_opening_move?fen=${encodeURIComponent(positionAfterPlayer)}&move_san=${firstMoveSan}&lesson_id=${lessonId}`,
                { method: "POST" }
              );
              if (firstMoveResponse.ok) {
                const firstMoveData = await firstMoveResponse.json();
                // Add the queried move's popularity
                if (firstMoveData.popularity != null) {
                  allExplorerMoves.set(firstMoveSan, firstMoveData.popularity);
                }
                // Add alternatives
                if (firstMoveData.popular_alternatives) {
                  firstMoveData.popular_alternatives.forEach((alt: any) => {
                    allExplorerMoves.set(alt.san, alt.pop);
                  });
                }
              }
            }
          }
        } catch (err) {
          console.warn("[OPENING] Failed to fetch explorer data:", err);
        }
        
        // Enrich candidates with popularity data from explorer
        const enrichedCandidates = candidates.map((cand: any) => {
          const moveSan = cand.san || cand.move;
          const popularity = allExplorerMoves.get(moveSan);
          if (popularity != null) {
            return {
              ...cand,
              popularity: popularity,
              play_rate: popularity,
              source: "database"
            };
          }
          return { ...cand, source: "database" };
        });
        
        const bestCandidate = enrichedCandidates[0];
        const bestMoveSan = bestCandidate?.san || bestCandidate?.move;
        if (!bestMoveSan) {
          console.warn("[OPENING] No candidate moves returned for auto-response");
          return;
        }

        const replyBoard = new Chess(positionAfterPlayer);
        const replyMove = replyBoard.move(bestMoveSan);
        if (!replyMove) {
          console.warn("[OPENING] Failed to apply auto-response move:", bestMoveSan);
          return;
        }

        setFen(replyBoard.fen());
        setGame(replyBoard);
        setMoveTree((prev) => {
          const nextTree = prev.clone();
          nextTree.addMove(replyMove.san, replyBoard.fen());
          setPgn(nextTree.toPGN());
          return nextTree;
        });
        setTreeVersion((v) => v + 1);

        const positionAfterAI = replyBoard.fen();

        const replyPlan =
          bestCandidate?.plan ||
          bestCandidate?.comment ||
          bestCandidate?.summary ||
          `${replyMove.color === 'w' ? 'White' : 'Black'} improves control of ${replyMove.to.toUpperCase()} and keeps the initiative.`;
        const usageStat =
          typeof bestCandidate?.play_rate === "number"
            ? `${Math.round(bestCandidate.play_rate * 100)}% usage`
            : bestCandidate?.popularity != null
              ? `${Math.round(bestCandidate.popularity * 100)}% usage`
              : null;
        const successStat =
          typeof bestCandidate?.win_rate === "number"
            ? `${Math.round(bestCandidate.win_rate * 100)}% success`
            : bestCandidate?.score != null
              ? `${Math.round(bestCandidate.score * 100)}% score`
              : null;
        const mainStats = [usageStat, successStat].filter(Boolean).join(" · ");
        const evalCp =
          typeof bestCandidate?.score === "number"
            ? `${bestCandidate.score > 0 ? "+" : ""}${(bestCandidate.score / 100).toFixed(2)}`
            : null;
        const personalNote = personalCandidateNote(bestCandidate);
        // Format as "I played [move] — ..."
        let replyMessage = `I played **${replyMove.san}**${mainStats ? ` (${mainStats})` : ""} — ${replyPlan}${personalNote}`;
        if (evalCp) replyMessage += ` (eval ${evalCp})`;

        // Get player's options from the NEW position (after AI's move)
        let playerAlternatives: any[] = [];
        let playerAlternativesWithPopularity: Map<string, number> = new Map();
        try {
          // Analyze the position after AI's move to get player's options
          const playerOptionsResponse = await fetch(
            `${getBackendBase()}/analyze_position?fen=${encodeURIComponent(positionAfterAI)}&lines=4&depth=16`
          );
          if (playerOptionsResponse.ok) {
            const playerOptionsAnalysis = await playerOptionsResponse.json();
            playerAlternatives = Array.isArray(playerOptionsAnalysis?.candidate_moves) 
              ? playerOptionsAnalysis.candidate_moves.slice(0, 3) 
              : [];
            
            // Get popularity for all player alternatives
            if (currentLesson?.plan?.lesson_id && playerAlternatives.length > 0) {
              const lessonId = currentLesson.plan.lesson_id;
              // Query explorer for each player alternative to get popularity
              const popularityPromises = playerAlternatives.map(async (alt: any) => {
                const moveSan = alt.san || alt.move;
                if (!moveSan) return null;
                try {
                  const explorerResponse = await fetch(
                    `${getBackendBase()}/check_opening_move?fen=${encodeURIComponent(positionAfterAI)}&move_san=${moveSan}&lesson_id=${lessonId}`,
                    { method: "POST" }
                  );
                  if (explorerResponse.ok) {
                    const explorerData = await explorerResponse.json();
                    return { move: moveSan, popularity: explorerData.popularity };
                  }
                } catch (err) {
                  console.warn(`[OPENING] Failed to get popularity for ${moveSan}:`, err);
                }
                return null;
              });
              
              const popularityResults = await Promise.all(popularityPromises);
              popularityResults.forEach((result) => {
                if (result && result.popularity != null) {
                  playerAlternativesWithPopularity.set(result.move, result.popularity);
                }
              });
            }
          }
        } catch (err) {
          console.warn("[OPENING] Failed to get player alternatives:", err);
        }

        // Helper to infer move description from move notation
        const inferMoveDescription = (moveSan: string, positionFen: string): string => {
          if (!moveSan) return "Keeps the structure flexible.";
          
          const moveUpper = moveSan.toUpperCase();
          const descriptions: string[] = [];
          
          // Check for castling
          if (moveUpper === "O-O" || moveUpper === "0-0") {
            descriptions.push("castles kingside and secures the king");
          } else if (moveUpper === "O-O-O" || moveUpper === "0-0-0") {
            descriptions.push("castles queenside and secures the king");
          } else {
            // Check piece type
            if (moveUpper.startsWith("N")) {
              descriptions.push("develops the knight");
            } else if (moveUpper.startsWith("B")) {
              descriptions.push("develops the bishop");
            } else if (moveUpper.startsWith("R")) {
              descriptions.push("develops the rook");
            } else if (moveUpper.startsWith("Q")) {
              descriptions.push("activates the queen");
            } else if (moveUpper.startsWith("K")) {
              descriptions.push("moves the king");
            } else {
              // Pawn move
              descriptions.push("advances a pawn");
            }
            
            // Check if it's a capture
            if (moveSan.includes("x")) {
              descriptions.push("captures material");
            }
            
            // Check if it's a check
            if (moveSan.includes("+")) {
              descriptions.push("gives check");
            }
            
            // Check center squares (e4, e5, d4, d5)
            const centerSquares = ["E4", "E5", "D4", "D5"];
            if (centerSquares.some(sq => moveUpper.includes(sq))) {
              descriptions.push("influences the center");
            }
          }
          
          return descriptions.length > 0 ? descriptions.join(", ") : "Keeps the structure flexible.";
        };

        // Format alternate moves with descriptions - these are the PLAYER's options from the new position
        console.log(`[OPENING] Found ${playerAlternatives.length} player alternative moves to display`);
        if (playerAlternatives.length > 0) {
          replyMessage += `\n\n**You have some options from here:**`;
          playerAlternatives.forEach((alt: any) => {
            console.log(`[OPENING] Processing player alternative move:`, alt);
            const moveLabel = alt.san || alt.move || alt.uci || "…";
            
            // Build description - try tags first, then plan/comment, then infer from move
            let plan = "";
            if (alt.tags && Array.isArray(alt.tags) && alt.tags.length > 0) {
              // Use tags to generate description
              const tagDescriptions: string[] = [];
              alt.tags.forEach((tag: string) => {
                if (tag === "development") tagDescriptions.push("develops a piece");
                else if (tag === "control") tagDescriptions.push("controls key squares");
                else if (tag === "attack") tagDescriptions.push("creates attacking chances");
                else if (tag === "defense") tagDescriptions.push("strengthens the position");
                else if (tag === "center") tagDescriptions.push("influences the center");
                else if (tag === "pawn") tagDescriptions.push("advances a pawn");
                else if (tag === "knight") tagDescriptions.push("develops the knight");
                else if (tag === "bishop") tagDescriptions.push("develops the bishop");
                else if (tag === "queen") tagDescriptions.push("activates the queen");
                else if (tag === "castling") tagDescriptions.push("castles and secures the king");
                else tagDescriptions.push(tag);
              });
              plan = tagDescriptions.join(", ");
            } else if (alt.plan || alt.comment || alt.summary || alt.idea || alt.description) {
              // Use provided description
              plan = alt.plan || alt.comment || alt.summary || alt.idea || alt.description;
            } else {
              // Infer from move notation
              plan = inferMoveDescription(moveLabel, positionAfterAI);
            }
            
            // Get popularity percentage from explorer data
            const popularity = playerAlternativesWithPopularity.get(moveLabel);
            const popularityText = popularity != null ? ` (${Math.round(popularity * 100)}% popularity)` : "";
            
            // Format source for personal games only
            let sourceText = "";
            if (alt.source === "personal") {
              const result = alt.personal_result ? ` (${alt.personal_result})` : "";
              const opp = alt.opponent ? ` vs ${alt.opponent}` : "";
              sourceText = ` — your game${opp}${result}`.trim();
              if (alt.was_mistake === true) sourceText += " (this was punished)";
              if (alt.was_mistake === false) sourceText += " (you handled this well)";
            }
            
            replyMessage += `\n• **${moveLabel}** – ${plan}${popularityText}${sourceText}`;
          });
        }

        addAssistantMessage(replyMessage);
        await restoreOpeningLessonVisuals(replyBoard.fen());
      } catch (err: any) {
        console.error("[OPENING] Failed to auto-play response:", err);
        const errorMsg = err?.message || String(err);
        if (errorMsg.includes("Connection") || errorMsg.includes("network") || errorMsg.includes("fetch") || errorMsg.includes("unavailable")) {
          addSystemMessage("⚠️ Connection issue - AI response delayed. The move was recorded, but I couldn't generate a response. Please try again in a moment.");
        } else {
          addSystemMessage(`⚠️ Could not generate AI response: ${errorMsg}`);
        }
      } finally {
        setWaitingForEngine(false);
      }
    },
    [lessonMode, currentLesson?.type, restoreOpeningLessonVisuals, addAssistantMessage]
  );

  // Handlers to ensure layout expands into chat + 50/50 when triggered from hero
  const handleToggleBoard = () => {
    const next = !boardDockOpen;
    setBoardDockOpen(next);
    if (next && isFirstMessage) {
      setIsFirstMessage(false);
    }
  };

  const handleShowLoadGame = () => {
    setShowLoadGame(true);
    if (isFirstMessage) {
      setIsFirstMessage(false);
    }
    if (!boardDockOpen) {
      setBoardDockOpen(true);
    }
  };
  const handleSaveProfilePreferences = async (prefs: ProfilePreferences) => {
    if (!user) {
      setProfilePreferences(prefs);
      setShowProfileSetupModal(false);
      return;
    }

    try {
      const overview = await saveProfilePreferencesApi({
        userId: user.id,
        accounts: prefs.accounts.map(({ platform, username }) => ({ platform, username })),
        timeControls: prefs.timeControls,
      });
      setProfileOverview(overview);
      setProfileStatus(overview.status);
      const normalized = normalizeProfilePreferences(overview.preferences as any) ?? prefs;
      setProfilePreferences(normalized);
      try {
        const statsResponse = await fetchProfileStats(user.id);
        setProfileStats(statsResponse.stats || null);
      } catch (error) {
        console.warn("Failed to refresh profile stats:", error);
      }
      setShowProfileSetupModal(false);
      addSystemMessage("Profile preferences saved. Indexing your recent games now.");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to save profile preferences.";
      addSystemMessage(message);
      throw err;
    }
  };
  const handleSignInClick = () => {
    if (!user) {
      setShowAuthModal(true);
    }
  };

  const handleAuthSignOut = async () => {
    try {
      await signOut();
      addSystemMessage("Signed out.");
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      addSystemMessage(`Sign out failed: ${message}`);
      console.error("Sign out failed", err);
    }
  };

  const handleSwitchAccount = async () => {
    try {
      await signOut();
      addSystemMessage("Signed out. Choose another account to continue.");
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      addSystemMessage(`Sign out failed: ${message}`);
      console.error("Sign out failed", err);
    } finally {
      setShowAuthModal(true);
    }
  };
  const theme = "night" as const;
  const [currentThreadId, setCurrentThreadId] = useState<string | null>(null);
  type LayoutSizes = { board: number; load: number; chat: number };
  const defaultLayoutSizes: LayoutSizes = { board: 0.275, load: 0.2, chat: 0.525 };
  const [layoutSizes, setLayoutSizes] = useState<LayoutSizes>(defaultLayoutSizes);
  
  // Load layout sizes from localStorage on client only to avoid hydration mismatch
  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      const stored = window.localStorage.getItem("cg_layout_sizes");
      if (stored) {
        const parsed = JSON.parse(stored);
        if (
          typeof parsed?.board === "number" &&
          typeof parsed?.load === "number" &&
          typeof parsed?.chat === "number"
        ) {
          setLayoutSizes(parsed);
        }
      }
    } catch (err) {
      console.warn("Failed to load layout sizes:", err);
    }
  }, []);
  type DragType = "board-load" | "load-chat" | "board-chat";
  const [dragState, setDragState] = useState<
    null | { type: DragType; axis: "x" | "y"; start: number; sizes: LayoutSizes }
  >(null);
  const layoutRef = useRef<HTMLDivElement | null>(null);
  const { user, loading: authLoading, signOut } = useAuth();
  const authUserEmail = user?.email ?? null;
  const authUserName =
    (user?.user_metadata?.username as string | undefined) ||
    (user?.user_metadata?.full_name as string | undefined) ||
    (user?.user_metadata?.name as string | undefined) ||
    (authUserEmail ? authUserEmail.split("@")[0] : null);
  const [profilePreferences, setProfilePreferences] = useState<ProfilePreferences | null>(null);
  const [profileStatus, setProfileStatus] = useState<ProfileOverviewResponse["status"] | null>(null);
  const [profileStats, setProfileStats] = useState<ProfileStatsResponse["stats"] | null>(null);
  const [profileOverview, setProfileOverview] = useState<ProfileOverviewResponse | null>(null);
  const [showProfileSetupModal, setShowProfileSetupModal] = useState(false);
  const isRefreshingRef = useRef(false); // Prevent concurrent refreshes

  useEffect(() => {
    if (typeof window !== "undefined") {
      window.localStorage.setItem("cg_layout_sizes", JSON.stringify(layoutSizes));
    }
  }, [layoutSizes]);

  const normalizeProfilePreferences = (raw?: { accounts?: Array<{ platform: "chesscom" | "lichess"; username: string }>; time_controls?: string[] | null; timeControls?: string[] | null; }): ProfilePreferences | null => {
    if (!raw) {
      return null;
    }
    
    // Handle both array and object formats
    let accountsArray = raw.accounts;
    if (!Array.isArray(accountsArray)) {
      accountsArray = [];
    }
    
    const allowed = new Set(["bullet", "blitz", "rapid"]);
    const accounts = accountsArray.map((acc, index) => {
      // Handle both object and string formats
      const platform = typeof acc === 'string' ? acc : (acc?.platform || 'chesscom');
      const username = typeof acc === 'string' ? '' : (acc?.username || '');
      
      return {
        id: `${platform}-${username || index}-${index}`,
        platform: platform as "chesscom" | "lichess",
        username: username,
      };
    });
    
    const timeControls = (raw.time_controls ?? raw.timeControls ?? [])
      .map((tc) => String(tc).toLowerCase())
      .filter((tc): tc is "bullet" | "blitz" | "rapid" => allowed.has(tc));
    
    const result: ProfilePreferences = {
      accounts,
      timeControls: timeControls.length ? timeControls : (["blitz", "rapid"] as Array<"bullet" | "blitz" | "rapid">),
    };
    
    // Return result even if accounts is empty (user might not have set up yet)
    return result;
  };

  // Reusable function to refresh profile data
  const refreshProfileData = useCallback(async () => {
    if (!user) {
      console.warn("🔄 Refresh skipped: no user");
      return;
    }
    
    // Prevent concurrent refreshes
    if (isRefreshingRef.current) {
      console.log("🔄 Refresh already in progress, skipping...");
      return;
    }
    
    isRefreshingRef.current = true;
    const startTime = Date.now();
    
    try {
      console.log("🔄 Refreshing profile data...");
      
      // fetchWithRetry now has built-in timeout (8s)
      const data = await fetchProfileOverview(user.id);
      
      // Update state with new data (don't clear first - causes re-render loops)
      setProfileOverview(data);
      if (data.status) {
        setProfileStatus(data.status);
      }
      
      const normalized = normalizeProfilePreferences(data.preferences as any);
      
      if (normalized && normalized.accounts.length > 0) {
        // Create new object to force React update
        setProfilePreferences({
          accounts: [...normalized.accounts],
          timeControls: [...normalized.timeControls]
        });
        setShowProfileSetupModal(false);
      } else {
        console.warn("⚠️ No normalized preferences or empty accounts");
        // Don't set to null if we have data, just keep existing
        if (!normalized) {
          setProfilePreferences(null);
          setShowProfileSetupModal(true);
        }
      }
      
      // Also refresh stats (don't wait for it)
      fetchProfileStats(user.id)
        .then(statsResponse => {
          console.log("📈 Stats received:", !!statsResponse.stats);
          setProfileStats(statsResponse.stats || null);
        })
        .catch(statsErr => {
          console.warn("⚠️ Stats refresh failed (optional):", statsErr);
        });
      
      const duration = Date.now() - startTime;
      console.log(`✅ Profile data refreshed successfully in ${duration}ms`);
    } catch (err) {
      const duration = Date.now() - startTime;
      // Don't show error for aborted requests (timeout) - they're expected for slow requests
      const isAbortError = err instanceof Error && 
        (err.name === 'AbortError' || err.message.includes('aborted'));
      
      if (isAbortError) {
        console.warn(`⚠️ Profile refresh timed out after ${duration}ms (request aborted)`);
        // Don't show error message to user for timeouts
      } else {
        console.error(`❌ Failed to refresh profile after ${duration}ms:`, err);
        // Only show error to user for non-timeout errors
        if (err instanceof Error) {
          addSystemMessage(`Failed to refresh profile: ${err.message}`);
        }
      }
    } finally {
      // Always clear the flag
      isRefreshingRef.current = false;
      console.log("🔄 Refresh completed, flag cleared");
    }
  }, [user]); // addSystemMessage is stable, doesn't need to be in deps

  useEffect(() => {
    if (!user) {
      setProfilePreferences(null);
      setProfileOverview(null);
      setProfileStatus(null);
      setProfileStats(null);
      setShowProfileSetupModal(false);
      return;
    }

    let cancelled = false;

    const loadProfileOverview = async () => {
      try {
        if (analysisInProgress) return;
        const data = await fetchProfileOverview(user.id);
        if (cancelled) return;
        setProfileOverview(data);
        setProfileStatus(data.status);
        const normalized = normalizeProfilePreferences(data.preferences as any);
        if (normalized) {
          setProfilePreferences(normalized);
          setShowProfileSetupModal(false);
        } else {
          setProfilePreferences(null);
          setShowProfileSetupModal(true);
        }
      } catch (err) {
        if (!cancelled) {
          console.warn("Failed to load profile overview:", err);
        }
      }
    };

    loadProfileOverview();
    const interval = setInterval(loadProfileOverview, 15000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [user, analysisInProgress]);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;

    const loadStats = async () => {
      try {
        if (analysisInProgress) return;
        const response = await fetchProfileStats(user.id);
        if (!cancelled) {
          setProfileStats(response.stats || null);
        }
      } catch (error) {
        if (!cancelled) {
          console.warn("Failed to load profile stats:", error);
        }
      }
    };

    loadStats();
    const interval = setInterval(loadStats, 60000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [user, analysisInProgress]);

  useEffect(() => {
    if (user && showAuthModal) {
      setShowAuthModal(false);
    }
  }, [user, showAuthModal]);

  const clamp = (value: number, min: number, max: number) => Math.min(Math.max(value, min), max);

  useEffect(() => {
    if (!dragState) return;
    const MIN = { board: 0.18, load: 0.12, chat: 0.22 };
    const handleMove = (event: PointerEvent | MouseEvent) => {
      if (!layoutRef.current) return;
      const axis = dragState.axis;
      const containerSize =
        axis === "y"
          ? (layoutRef.current.clientHeight || window.innerHeight || 1)
          : (layoutRef.current.clientWidth || window.innerWidth || 1);
      const currentCoord =
        axis === "y"
          ? ("clientY" in event ? event.clientY : 0)
          : ("clientX" in event ? event.clientX : 0);
      const deltaRatio = (currentCoord - dragState.start) / containerSize;
      const { board: startBoard, load: startLoad, chat: startChat } = dragState.sizes;
      if (dragState.type === "board-load") {
        const groupTotal = startBoard + startLoad;
        const maxBoard = groupTotal - MIN.load;
        const minBoard = MIN.board;
        let newBoard = clamp(startBoard + deltaRatio, minBoard, maxBoard);
        let newLoad = groupTotal - newBoard;
        if (newLoad < MIN.load) {
          newLoad = MIN.load;
          newBoard = groupTotal - newLoad;
        }
        setLayoutSizes(prev => ({ ...prev, board: newBoard, load: newLoad }));
      } else if (dragState.type === "load-chat") {
        const groupTotal = startLoad + startChat;
        const maxLoad = groupTotal - MIN.chat;
        const minLoad = MIN.load;
        let newLoad = clamp(startLoad + deltaRatio, minLoad, maxLoad);
        let newChat = groupTotal - newLoad;
        if (newChat < MIN.chat) {
          newChat = MIN.chat;
          newLoad = groupTotal - newChat;
        }
        setLayoutSizes(prev => ({ ...prev, load: newLoad, chat: newChat }));
      } else {
        const groupTotal = startBoard + startChat;
        const maxBoard = groupTotal - MIN.chat;
        const minBoard = MIN.board;
        let newBoard = clamp(startBoard + deltaRatio, minBoard, maxBoard);
        let newChat = groupTotal - newBoard;
        if (newChat < MIN.chat) {
          newChat = MIN.chat;
          newBoard = groupTotal - newChat;
        }
        setLayoutSizes(prev => ({ ...prev, board: newBoard, chat: newChat }));
      }
    };
    const handleUp = () => setDragState(null);
    window.addEventListener("pointermove", handleMove as any);
    window.addEventListener("pointerup", handleUp);
    window.addEventListener("pointercancel", handleUp);
    return () => {
      window.removeEventListener("pointermove", handleMove as any);
      window.removeEventListener("pointerup", handleUp);
      window.removeEventListener("pointercancel", handleUp);
    };
  }, [dragState]);

  const totalLayout = layoutSizes.board + layoutSizes.load + layoutSizes.chat || 1;
  const boardFractionAll = layoutSizes.board / totalLayout;
  const loadFractionAll = layoutSizes.load / totalLayout;
  const chatFractionAll = layoutSizes.chat / totalLayout;
  const boardChatTotal = layoutSizes.board + layoutSizes.chat || 1;
  const boardFraction = boardDockOpen ? (layoutSizes.board / boardChatTotal) : 0;
  const chatFraction = boardDockOpen ? (layoutSizes.chat / boardChatTotal) : 1;
  const beginDrag = (
    type: DragType,
    axis: "x" | "y",
    event: React.PointerEvent<HTMLDivElement> | ReactMouseEvent<HTMLDivElement>
  ) => {
    event.preventDefault();
    event.stopPropagation();
    const pointerEvent = event as React.PointerEvent<HTMLDivElement>;
    try {
      if (typeof pointerEvent.pointerId === "number") {
        pointerEvent.currentTarget.setPointerCapture(pointerEvent.pointerId);
      }
    } catch {
      // ignore (some browsers / elements may not support)
    }
    const start = axis === "y" ? (event as any).clientY : (event as any).clientX;
    setDragState({ type, axis, start, sizes: layoutSizes });
  };
  const layoutStyle: CSSProperties | undefined = boardDockOpen
    ? ({
        "--board-column-width": `${(boardFraction * 100).toFixed(2)}%`,
        "--chat-column-width": `${(chatFraction * 100).toFixed(2)}%`,
        "--composer-offset": `${(boardFraction * 100).toFixed(2)}%`,
      } as CSSProperties)
    : undefined;
  const boardColumnStyle = boardDockOpen
    ? (isMobileMode
        ? // Mobile is vertical: treat board/chat split as a row height ratio.
          ({ flex: `0 0 ${(boardFraction * 100).toFixed(2)}%` } as CSSProperties)
        : ({ flexBasis: `${(boardFraction * 100).toFixed(2)}%` } as CSSProperties))
    : undefined;
  const chatColumnStyle = boardDockOpen
    ? (isMobileMode
        ? // Let chat fill the rest on mobile.
          ({ flex: "1 1 0" } as CSSProperties)
        : ({ flexBasis: `${(chatFraction * 100).toFixed(2)}%` } as CSSProperties))
    : undefined;

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
    const loadingId = addLoadingMessage('stockfish', 'Analyzing position...');
    
    try {
      // SINGLE Stockfish call - analyze the new position only
      // Add timeout to prevent hanging (increased to 90s for complex positions)
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 90000); // 90 second timeout
      
      const positionResponse = await fetch(
        `${getBackendBase()}/analyze_position?fen=${encodeURIComponent(currentFen)}&depth=18&lines=3`,
        { signal: controller.signal }
      );
      
      clearTimeout(timeoutId);
      
      if (!positionResponse.ok) {
        console.error('Position analysis failed:', positionResponse.statusText);
        removeLoadingMessage(loadingId);
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
      // IMPORTANT: Don't include nested cached_analysis to prevent exponential growth
      setAnalysisCache(prev => {
        const newEntry: any = {
          ...positionAnalysis,
          move_analysis: moveQuality  // Calculated from cache, not Stockfish!
        };
        
        // Remove any nested cached_analysis if it exists
        if (newEntry.cached_analysis) {
          delete newEntry.cached_analysis;
        }
        if (newEntry.move_analysis?.cached_analysis) {
          delete newEntry.move_analysis.cached_analysis;
        }
        
        return {
          ...prev,
          [currentFen]: newEntry
        };
      });
      
      console.log('✅ Analysis cached (optimized - no duplicate Stockfish)');
    } catch (error: any) {
      if (error.name === 'AbortError' || error.message?.includes('timed out')) {
        console.error('⏱️ Position analysis timed out');
        addSystemMessage('Position analysis timed out. The engine may be busy.');
      } else {
        console.error('Auto-analysis error:', error);
        addSystemMessage(`Analysis error: ${error.message || 'Unknown error'}`);
      }
    } finally {
      removeLoadingMessage(loadingId);
      setIsAnalyzing(false);
    }
  }

  // Prefetch baseline intuition (single-pass Scan A) in the background so the user can send a message while it runs.
  const prefetchBaselineIntuition = useCallback(async (targetFen: string) => {
    try {
      if (!targetFen) return;
      if (!(mode === "DISCUSS" || mode === "ANALYZE")) return;
      // Avoid extra load during lessons / explicit play loops
      if (lessonMode || aiGameActive) return;

      const isVerboseAI =
        typeof window !== "undefined" &&
        (new URLSearchParams(window.location.search).get("verbose_ai") === "1" ||
          localStorage.getItem("CHESSTER_VERBOSE_AI") === "1" ||
          process.env.NEXT_PUBLIC_VERBOSE_AI_LOGGING === "1");

      if (isVerboseAI) console.log('🔄 [BASELINE PREFETCH] Starting baseline intuition prefetch:', {
        fen: targetFen.substring(0, 50) + '...',
        mode,
        thread_id: activeTab?.id || sessionId || null
      });

      const { buildLearningHeaders } = await import("@/lib/learningClient");
      const { headers } = await buildLearningHeaders();
      const response = await fetch(`${getBackendBase()}/board/baseline_intuition_start`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...headers },
        body: JSON.stringify({ start_fen: targetFen, thread_id: activeTab?.id || sessionId || null })
      });
      
      if (response.ok) {
        const result = await response.json();
        if (isVerboseAI) console.log('✅ [BASELINE PREFETCH] Baseline intuition started:', {
          success: result.success,
          key: result.key,
          status: result.status
        });
      } else {
        if (isVerboseAI) console.warn('⚠️ [BASELINE PREFETCH] Failed to start baseline intuition:', response.status);
      }
    } catch (e) {
      // Non-fatal prefetch; chat will still await baseline server-side if needed.
      console.warn("❌ [BASELINE PREFETCH] Baseline intuition prefetch failed:", e);
    }
  }, [mode, lessonMode, aiGameActive, activeTab?.id, sessionId]);

  // Ensure backend D2/D16 tree exists for this tab in DISCUSS/ANALYZE.
  const ensureBackendTreeForTab = useCallback(async (tabId: string, startFen: string) => {
    try {
      if (!tabId || !startFen) return;
      // Fast path: if we already have a node pointer, assume tree exists.
      if (backendTreeNodeByTabRef.current[tabId]) return;

      const isVerboseAI =
        typeof window !== "undefined" &&
        (new URLSearchParams(window.location.search).get("verbose_ai") === "1" ||
          localStorage.getItem("CHESSTER_VERBOSE_AI") === "1" ||
          process.env.NEXT_PUBLIC_VERBOSE_AI_LOGGING === "1");

      if (isVerboseAI) console.log("🌳 [BACKEND TREE] ensureBackendTreeForTab start", { tabId, fen: startFen.slice(0, 50) + "..." });

      const getResp = await fetch(
        `${getBackendBase()}/board/tree/get?thread_id=${encodeURIComponent(tabId)}&include_scan=false`
      );
      if (isVerboseAI) console.log("🌳 [BACKEND TREE] tree/get", { ok: getResp.ok, status: getResp.status });
      if (getResp.ok) {
        const data = await getResp.json().catch(() => null);
        // Backend returns { success: false, tree: null } when tree doesn't exist yet.
        if (data?.success && data?.tree) {
          const currentId = data?.tree?.current_id || "root";
          backendTreeNodeByTabRef.current[tabId] = currentId;
          if (isVerboseAI) console.log("🌳 [BACKEND TREE] tree exists", { currentId });
          return;
        }
      }

      await fetch(`${getBackendBase()}/board/tree/init`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ thread_id: tabId, start_fen: startFen }),
      });
      backendTreeNodeByTabRef.current[tabId] = "root";
      if (isVerboseAI) console.log("🌳 [BACKEND TREE] tree initialized", { tabId });
    } catch (e) {
      console.warn("ensureBackendTreeForTab failed:", e);
    }
  }, []);

  // Auto-prefetch baseline intuition whenever the board position changes in DISCUSS/ANALYZE.
  useEffect(() => {
    if (fen && (mode === "DISCUSS" || mode === "ANALYZE")) {
      prefetchBaselineIntuition(fen);
    }
  }, [fen, mode, prefetchBaselineIntuition]);

  // Initialize backend tree (tab-scoped) for DISCUSS/ANALYZE so later moves can extend it.
  useEffect(() => {
    if (fen && (mode === "DISCUSS" || mode === "ANALYZE")) {
      const tabId = activeTab?.id || activeTabId || sessionId;
      ensureBackendTreeForTab(tabId, fen);
    }
  }, [fen, mode, activeTab?.id, activeTabId, sessionId, ensureBackendTreeForTab]);

  async function callLLM(
    messages: { role: string; content: string }[], 
    temperature: number = 0.7, 
    model: string = "gpt-4o-mini",
    useTools: boolean = true
  ): Promise<{
    content: string, 
    tool_calls?: any[], 
    context?: any, 
    raw_data?: any, 
    annotations?: any,
    status_messages?: any[],
    detected_intent?: string | null,
    tools_used?: string[],
    orchestration?: any,
    graphData?: any
  }> {
    try {
      // Note: backend replaces the first system message with its interpreter-driven prompt,
      // so adding extra system-level tool policy here is redundant and wastes tokens.
      const finalMessages = messages;
      // Build context for tools - include cached analysis if available
      // In DISCUSS/ANALYZE, raw cached analysis is redundant with baseline intuition.
      // Keep cached_analysis only for PLAY/lesson loops where move-quality depends on it.
      const cachedAnalysis = (mode === "PLAY" || aiGameActive || lessonMode) ? analysisCache[fen] : null;
      
      // Extract last move and FEN before it from PGN (for "rate that move" requests)
      let lastMoveInfo = null;
      if (pgn && pgn.length > 0 && moveTree.getMainLine().length > 0) {
        try {
          const mainLine = moveTree.getMainLine();
          const lastNode = mainLine[mainLine.length - 1];
          const fenBeforeLastMove = mainLine.length > 1 ? mainLine[mainLine.length - 2].fen : "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";
          lastMoveInfo = {
            move: lastNode.move,
            fen_before: fenBeforeLastMove,
            fen_after: lastNode.fen
          };
        } catch (e) {
          console.warn("Failed to extract last move info:", e);
        }
      }
      
      // Clean cached_analysis before sending - remove large confidence tree data
      // This prevents exponential growth from nested cached_analysis
      const cleanCachedAnalysis = (analysis: any, depth: number = 0): any => {
        if (!analysis || depth > 2) return null; // Prevent infinite recursion
        
        const cleaned: any = {};
        
        // Keep essential fields only
        if (analysis.fen !== undefined) cleaned.fen = analysis.fen;
        if (analysis.eval_cp !== undefined) cleaned.eval_cp = analysis.eval_cp;
        if (analysis.pv !== undefined) cleaned.pv = analysis.pv;
        if (analysis.best_move !== undefined) cleaned.best_move = analysis.best_move;
        if (analysis.candidate_moves !== undefined) cleaned.candidate_moves = analysis.candidate_moves;
        if (analysis.phase !== undefined) cleaned.phase = analysis.phase;
        if (analysis.white_analysis !== undefined) cleaned.white_analysis = analysis.white_analysis;
        if (analysis.black_analysis !== undefined) cleaned.black_analysis = analysis.black_analysis;
        if (analysis.position_confidence !== undefined) {
          // Keep confidence summary but remove nodes/snapshots
          const posConf = analysis.position_confidence;
          cleaned.position_confidence = {
            overall_confidence: posConf.overall_confidence,
            line_confidence: posConf.line_confidence,
            end_confidence: posConf.end_confidence,
            lowest_confidence: posConf.lowest_confidence,
            // Explicitly exclude nodes and snapshots - they're huge!
          };
        }
        if (analysis.move_analysis !== undefined && analysis.move_analysis !== null) {
          // Keep move analysis but clean nested confidence
          const moveAnalysis = analysis.move_analysis;
          // Only include if moveAnalysis has actual data
          if (moveAnalysis && typeof moveAnalysis === 'object') {
            cleaned.move_analysis = {
              quality: moveAnalysis.quality,
              cp_loss: moveAnalysis.cp_loss,
              is_best_move: moveAnalysis.is_best_move,
              eval_before: moveAnalysis.eval_before,
              eval_after: moveAnalysis.eval_after,
              best_move: moveAnalysis.best_move,
              alternatives: moveAnalysis.alternatives,
              // Include confidence summary only (no nodes/snapshots)
              confidence: moveAnalysis.confidence ? {
                overall_confidence: moveAnalysis.confidence.overall_confidence,
                line_confidence: moveAnalysis.confidence.line_confidence,
                end_confidence: moveAnalysis.confidence.end_confidence,
                lowest_confidence: moveAnalysis.confidence.lowest_confidence,
              } : undefined
            };
          }
        }
        
        // Explicitly exclude any nested cached_analysis to prevent recursion
        // Don't include cached_analysis field even if it exists
        
        return cleaned;
      };
      
      // Build connected accounts from profile preferences
      const connectedAccounts = profilePreferences?.accounts
        ?.filter(acc => acc.username)
        ?.map(acc => ({ platform: acc.platform, username: acc.username })) || [];
      
      // Use active tab's PGN/FEN to ensure context matches the correct tab
      const tabFen = activeTab?.fen || fen;
      const tabPgn = activeTab?.pgn || pgn;
      const tabGame = activeTab?.game || game;
      
      const context = {
        fen: tabFen,
        cached_analysis: cleanCachedAnalysis(cachedAnalysis),  // Clean before sending
        pgn: tabPgn,
        mode: mode,
        has_fen: tabFen !== INITIAL_FEN,
        has_pgn: tabPgn.length > 0,
        board_state: tabGame.fen(),
        last_move: lastMoveInfo,  // Helper info for "rate that move" requests
        inline_boards: inlineContexts.map((c) => ({
          id: c.id,
          fen: c.fen,
          pgn: c.pgn,
          orientation: c.orientation,
          cached_analysis: cleanCachedAnalysis(inlineAnalysisCache[c.fen])  // Clean inline boards too
        })),
        connected_accounts: connectedAccounts,  // Chess.com/Lichess accounts
        aiGameActive: aiGameActive,  // Whether AI game mode is active
        active_tab_id: activeTabId,  // Include active tab ID for tab management
        available_tabs: tabs.map(t => ({ id: t.id, name: t.name, pgn_length: t.pgn.length }))  // Tab info for LLM
      };
      
      // Detailed logging of what's being sent
      console.log('\n' + '='.repeat(80));
      console.log('📤 FRONTEND: SENDING TO LLM');
      console.log('='.repeat(80));
      console.log('Model:', model);
      console.log('Temperature:', temperature);
      console.log('Use tools:', useTools);
      
      // Log messages
      console.log(`\n📝 MESSAGES (${finalMessages.length} total):`);
      let totalMessageChars = 0;
      finalMessages.forEach((m, i) => {
        const content = typeof m.content === 'string' ? m.content : JSON.stringify(m.content);
        const len = content.length;
        totalMessageChars += len;
        console.log(`  [${i+1}] ${m.role.toUpperCase()}: ${len.toLocaleString()} chars`);
        if (m.role === 'system') {
          const preview = len > 500 ? content.substring(0, 500) + '...' : content;
          console.log(`      Preview: ${preview.substring(0, 200)}...`);
        } else if (m.role === 'user') {
          const preview = len > 200 ? content.substring(0, 200) + '...' : content;
          console.log(`      Content: ${preview}`);
        }
      });
      
      // Log context breakdown
      console.log('\n🌐 CONTEXT BREAKDOWN:');
      const contextStr = JSON.stringify(context);
      const contextLen = contextStr.length;
      console.log(`  Total context: ${contextLen.toLocaleString()} chars`);
      
      // Show original cached_analysis size for comparison
      if (cachedAnalysis) {
        const originalSize = JSON.stringify(cachedAnalysis).length;
        const cleanedSize = context.cached_analysis ? JSON.stringify(context.cached_analysis).length : 0;
        const reduction = originalSize - cleanedSize;
        console.log(`  📉 Cached analysis cleaned: ${originalSize.toLocaleString()} → ${cleanedSize.toLocaleString()} chars (saved ${reduction.toLocaleString()})`);
      }
      
      // Break down by key
      Object.entries(context).forEach(([key, value]) => {
        let size = 0;
        if (value === null || value === undefined) {
          size = 0;
        } else if (typeof value === 'string') {
          size = value.length;
        } else if (Array.isArray(value) || typeof value === 'object') {
          size = JSON.stringify(value).length;
        } else {
          size = String(value).length;
        }
        
        let extra = '';
        if (key === 'pgn' && typeof value === 'string') {
          extra = ` (PGN: ${value.length} chars)`;
        } else if (key === 'cached_analysis' && value) {
          const cached = value as any;
          if (cached.position_confidence) {
            extra = ` (confidence summary only - nodes/snapshots removed)`;
          } else if (cached.move_analysis?.confidence) {
            extra = ` (move confidence summary only)`;
          } else {
            extra = ` (keys: ${Object.keys(cached).join(', ')})`;
          }
        }
        console.log(`    ${key}: ${size.toLocaleString()} chars${extra}`);
      });
      
      // Token estimate
      const totalChars = totalMessageChars + contextLen;
      const estimatedTokens = Math.ceil(totalChars / 4);
      console.log(`\n📊 ESTIMATED TOKENS: ~${estimatedTokens.toLocaleString()} (${totalChars.toLocaleString()} chars)`);
      if (estimatedTokens > 100000) {
        console.warn(`⚠️  WARNING: Estimated tokens (${estimatedTokens.toLocaleString()}) exceeds 100k!`);
      }
      console.log('='.repeat(80) + '\n');
      
      const response = await fetch(`${getBackendBase()}/llm_chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          messages: finalMessages, 
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
      console.log('[LLM] Response JSON:', data);
      
      // Log tool calls if any
      let shouldTriggerAnalysis = false;
      let reviewData: any = null;
      let fullToolResult: any = null;  // Store full tool result for selected_key_moments/selection_rationale
      let hasGameReview = false;
      let hasPersonalReview = false;
      let shouldTriggerWalkthrough = false;
      const graphDataCollection: any[] = []; // Collect graph data from multiple tool calls
      
      if (data.tool_calls && data.tool_calls.length > 0) {
        console.log(`🔧 Tools called (${data.iterations} iterations):`, data.tool_calls.map((tc: any) => tc.tool).join(', '));
        const miniBoards: any[] = [];
        // graphDataCollection is declared above so it can be referenced after this block
        
        // First pass: Check if review_full_game or fetch_and_review_games was called
        hasGameReview = data.tool_calls.some((tc: any) => tc.tool === 'review_full_game');
        hasPersonalReview = data.tool_calls.some((tc: any) => tc.tool === 'fetch_and_review_games');
        
        data.tool_calls.forEach((tc: any, idx: number) => {
          console.log(`[LLM] Tool #${idx + 1}`, tc);
          console.log(`   ${tc.tool} args:`, tc.arguments);
          console.log(`   ${tc.tool} result_text:`, tc.result_text);
          console.log(`   ${tc.tool} result obj:`, tc.result);
          
          // Extract review data from review_full_game tool and trigger walkthrough
          if (tc.tool === 'review_full_game' && tc.result && tc.result.review) {
            reviewData = tc.result.review;
            fullToolResult = tc.result;  // Save full result for selected_key_moments/selection_rationale
            shouldTriggerWalkthrough = true;
            console.log('📊 Game review data extracted - will trigger walkthrough:', reviewData);
          }
          
          // Check if tool wants to trigger analyze position flow
          // BUT skip if game review was called (game review takes precedence)
          if (tc.result_text && tc.result_text.includes('__TRIGGER_ANALYZE_POSITION__') && !hasGameReview) {
            console.log('   🎯 Will trigger full analyze position flow...');
            shouldTriggerAnalysis = true;
          } else if (tc.result_text && tc.result_text.includes('__TRIGGER_ANALYZE_POSITION__') && hasGameReview) {
            console.log('   ⏭️  Skipping analyze position flow - game review takes precedence');
          }

          // Handle add_personal_review_graph tool calls
          if (tc.tool === 'add_personal_review_graph' && tc.result) {
            const graphResult = tc.result;
            // Check if result has error
            if (graphResult.error) {
              console.warn(`[Graph Tool] Error: ${graphResult.error}`);
            } else if (graphResult.graph_id && graphResult.series) {
              // Merge series if same graph_id, otherwise create new graph
              const existingGraph = graphDataCollection.find(g => g.graph_id === graphResult.graph_id);
              if (existingGraph) {
                // Merge series into existing graph
                existingGraph.series.push(...graphResult.series);
              } else {
                // Add new graph
                graphDataCollection.push({
                  graph_id: graphResult.graph_id,
                  series: graphResult.series,
                  xLabels: graphResult.xLabels,
                  grouping: graphResult.grouping,
                });
              }
              console.log(`[Graph Tool] Collected graph data: ${graphResult.series.length} series`);
            }
          }
          
          // Setup-position → emit a mini-board message in chat
          if (tc.tool === 'setup_position' && tc.result) {
            const r = tc.result;
            const miniFen = r.fen || (r.endpoint_response && r.endpoint_response.fen);
            const miniPgn = r.pgn || (r.endpoint_response && r.endpoint_response.pgn);
            const miniOrientation = r.orientation || 'white';
            if (miniFen) {
              miniBoards.push({ fen: miniFen, pgn: miniPgn, orientation: miniOrientation });
              console.log('[LLM] Collected mini board (result):', miniFen);
            }
          } else if (tc.tool === 'setup_position' && tc.result_text && !tc.result) {
            // Try parsing result_text as JSON (fallback)
            try {
              const parsed = JSON.parse(tc.result_text);
              const miniFen2 = parsed.fen || parsed.endpoint_response?.fen;
              const miniPgn2 = parsed.pgn || parsed.endpoint_response?.pgn;
              const miniOrientation2 = parsed.orientation || 'white';
              if (miniFen2) {
                miniBoards.push({ fen: miniFen2, pgn: miniPgn2, orientation: miniOrientation2 });
                console.log('[LLM] Collected mini board (parsed result_text):', miniFen2);
              }
            } catch (e) {
              console.warn('[LLM] Failed to parse setup_position result_text as JSON');
            }
          }
        });

        // Push all collected mini boards as chat messages
        if (miniBoards.length > 0) {
          miniBoards.forEach((mb) => {
            setMessages(prev => [...prev, {
              role: 'graph',
              content: '',
              meta: { miniBoard: mb }
            }]);
          });
        } else {
          console.log('[LLM] No mini boards collected from tool calls');
        }
      }
      
      // If game review was successful, transform data and trigger walkthrough
      if (shouldTriggerWalkthrough && reviewData) {
        console.log('🎮 Game review complete - transforming data for walkthrough');
        
        // Transform backend format to walkthrough format
        const transformedMoves = (reviewData.ply_records || []).map((record: any, idx: number) => {
          const plyValue = typeof record.ply === 'number' ? record.ply : idx + 1;
          const moveNumber = Math.floor(plyValue / 2) + 1;
          const moveSan = record.san || record.move || '';
          const fenAfter = record.fen_after || record.fenAfter || '';
          const color = record.side_moved === 'white' ? 'w' : record.side_moved === 'black' ? 'b' : (plyValue % 2 === 1 ? 'w' : 'b');
          const engineInfo = record.engine || {};
          const hintSources = [engineInfo.best_move_tags, engineInfo.best_move_themes, record.tags];
          let hint: string | null = null;
          for (const source of hintSources) {
            if (Array.isArray(source) && source.length) {
              const formatted = source
                .map((item: any) => typeof item === 'string' ? item : item?.tag_name || item?.name)
                .filter(Boolean)
                .map((raw: string) => raw.replace(/^tag\./, '').replace(/_/g, ' ').replace(/\./g, ' ').replace(/\s+/g, ' ').trim())
                .filter(Boolean);
              if (formatted.length) {
                hint = `Focus on ${formatted.slice(0, 2).join(' and ')}`;
                break;
              }
            }
          }
          if (!hint && engineInfo.best_move_explanation) {
            hint = engineInfo.best_move_explanation;
          } else if (!hint && engineInfo.best_move_commentary) {
            hint = engineInfo.best_move_commentary;
          } else if (!hint && record.plan_delta?.plan_explanation) {
            hint = record.plan_delta.plan_explanation;
          }
          return {
            ...record,
            moveNumber,
            move: moveSan,
            quality: record.category,
            isTheoryMove: record.is_theory,
            phase: record.phase,
            color,
            evalBefore: engineInfo.eval_before_cp ?? 0,
            evalAfter: engineInfo.played_eval_after_cp ?? 0,
            cpLoss: record.cp_loss ?? 0,
            accuracy: record.accuracy_pct ?? 100,
            bestMove: engineInfo.best_move_san || '',
            fen: fenAfter,
            fenBefore: record.fen_before || engineInfo.fen_before || record._fen_before || '',
            gapToSecondBest: engineInfo.second_best_gap_cp ?? null,
            hint,
            _fullRecord: record
          };
        });
        
        const whiteStats = reviewData.stats?.white || {};
        const blackStats = reviewData.stats?.black || {};
        console.log('🔍 [Transform] Raw stats:', {
          white_overall: whiteStats.overall_accuracy,
          black_overall: blackStats.overall_accuracy,
          white_opening: whiteStats.by_phase?.opening?.accuracy,
          black_opening: blackStats.by_phase?.opening?.accuracy,
          opening_name_final: reviewData.opening?.name_final,
          game_metadata_opening: reviewData.game_metadata?.opening
        });
        const phaseAccuracy = {
          opening: {
            white: whiteStats.by_phase?.opening?.accuracy ?? whiteStats.overall_accuracy ?? 0,
            black: blackStats.by_phase?.opening?.accuracy ?? blackStats.overall_accuracy ?? 0
          },
          middlegame: {
            white: whiteStats.by_phase?.middlegame?.accuracy ?? whiteStats.overall_accuracy ?? 0,
            black: blackStats.by_phase?.middlegame?.accuracy ?? blackStats.overall_accuracy ?? 0
          },
          endgame: {
            white: whiteStats.by_phase?.endgame?.accuracy ?? whiteStats.overall_accuracy ?? 0,
            black: blackStats.by_phase?.endgame?.accuracy ?? blackStats.overall_accuracy ?? 0
          }
        };
        
        const transformedData = {
          moves: transformedMoves,
          openingName: reviewData.opening?.name_final || reviewData.game_metadata?.opening || 'Unknown Opening',
          gameTags: reviewData.game_metadata?.game_character ? [reviewData.game_metadata.game_character] : [],
          avgWhiteAccuracy: whiteStats.overall_accuracy ?? 0,
          avgBlackAccuracy: blackStats.overall_accuracy ?? 0,
          accuracyStats: phaseAccuracy,
          leftTheoryMove: reviewData.opening?.left_theory_ply !== null 
            ? transformedMoves[reviewData.opening.left_theory_ply] 
            : null,
          criticalMovesList: transformedMoves.filter((m: any) => 
            m.category === 'critical_best' || m.category === 'mistake' || m.category === 'blunder'
          ),
          missedWinsList: transformedMoves.filter((m: any) => 
            Array.isArray(m.key_point_labels) && m.key_point_labels.includes('missed_win')
          ),
          crossed100: transformedMoves.filter((m: any) => 
            Array.isArray(m.key_point_labels) && m.key_point_labels.some((l: string) => l.includes('threshold_100'))
          ),
          crossed200: transformedMoves.filter((m: any) => 
            Array.isArray(m.key_point_labels) && m.key_point_labels.some((l: string) => l.includes('threshold_200'))
          ),
          crossed300: transformedMoves.filter((m: any) => 
            Array.isArray(m.key_point_labels) && m.key_point_labels.some((l: string) => l.includes('threshold_300'))
          ),
          // NEW: Include LLM-selected key moments for query-aware walkthrough
          // Use fullToolResult for these as they're at tc.result level, not inside tc.result.review
          selectedKeyMoments: fullToolResult?.selected_key_moments || [],
          selectionRationale: fullToolResult?.selection_rationale || {},
          queryIntent: fullToolResult?.selection_rationale?.query_intent || 'general',
          preCommentaryByPly: fullToolResult?.pre_commentary_by_ply || {}
        };
        
        console.log('🔄 Transformed walkthrough data:', {
          openingName: transformedData.openingName,
          avgWhiteAccuracy: transformedData.avgWhiteAccuracy,
          avgBlackAccuracy: transformedData.avgBlackAccuracy,
          opening_white: transformedData.accuracyStats.opening.white,
          opening_black: transformedData.accuracyStats.opening.black,
          moves_count: transformedData.moves.length,
          selectedKeyMoments: transformedData.selectedKeyMoments?.length || 0,
          queryIntent: transformedData.queryIntent
        });
        setWalkthroughData(transformedData);
        
        // Suppress LLM response and trigger walkthrough immediately
        console.log('🎬 Starting walkthrough with data...');
        setTimeout(() => startWalkthroughWithData(transformedData), 200);
        
        return {
          // Always keep some LLM text available for the chat UI, even when we auto-start walkthrough.
          content: typeof data.content === "string" ? data.content : "",
          tool_calls: data.tool_calls || [],
          context: context,
          raw_data: {
            tool_calls: data.tool_calls,
            review: reviewData,  // Store original review data for table
            triggered_walkthrough: true
          }
        };
      }
      
      // If personal review was called, display narrative and charts
      if (hasPersonalReview) {
        const personalReviewTool = data.tool_calls?.find((tc: any) => tc.tool === 'fetch_and_review_games');
        if (personalReviewTool?.result) {
          const result = personalReviewTool.result;
          
          // Check if username/platform info was required
          if (result.error === 'username_required' || result.error === 'info_required') {
            console.log('📝 [Personal Review] Additional info required:', result.missing_fields || ['username']);
            addAssistantMessage(result.message || 'Please provide your username and platform.');
            addSystemMessage("💡 Tip: Save your username in Settings to skip this step next time!");
            return {
              content: "",
              tool_calls: data.tool_calls || [],
              context: context
            };
          }
          
          // Show loading/progress messages
          if (result.success) {
            const platform = result.platform || 'chess platform';
            const username = result.username || 'user';
            const gamesFetched = result.games_fetched || 0;
            const gamesAnalyzed = result.games_analyzed || 0;
            
            addSystemMessage(`🔍 Fetched ${gamesFetched} games from ${platform} for ${username}`);
            addSystemMessage(`⚙️ Analyzed ${gamesAnalyzed} games with Stockfish`);
          }
          
          // Display narrative if available
          // NOTE: Narrative is handled in handleLLMResponse to avoid duplicates
          // Don't add it here to prevent duplicate messages
          if (result.narrative) {
            console.log('📊 [Personal Review] Narrative available, will be displayed in handleLLMResponse');
          }
          
          // Auto-load first game into tab (ALWAYS create new tab since user asked for their Chess.com game)
          // Load game even if there's no narrative (short-circuit pathway may not have narrative)
          if (result.first_game && result.first_game.pgn) {
            console.log('🎯 [Personal Review] Auto-loading game into NEW tab');
            loadGameIntoTab({
              pgn: result.first_game.pgn,
              white: result.first_game.white,
              black: result.first_game.black,
              date: result.first_game.date,
              result: result.first_game.result,
              timeControl: result.first_game.time_control,
              opening: result.first_game.opening,
            }, { forceNewTab: true });
            
            // Trigger walkthrough if we have review data
            if (result.first_game_review) {
                console.log('🎬 [Personal Review] Triggering walkthrough with review data');
                const reviewData = result.first_game_review;
                
                // Transform for walkthrough (same as review_full_game)
                const transformedMoves = (reviewData.ply_records || []).map((record: any, idx: number) => {
                  const plyValue = typeof record.ply === 'number' ? record.ply : idx + 1;
                  const moveNumber = Math.floor(plyValue / 2) + 1;
                  const moveSan = record.san || record.move || '';
                  const fenAfter = record.fen_after || record.fenAfter || '';
                  const color = record.side_moved === 'white' ? 'w' : record.side_moved === 'black' ? 'b' : (plyValue % 2 === 1 ? 'w' : 'b');
                  const engineInfo = record.engine || {};
                  
                  return {
                    ...record,
                    moveNumber,
                    move: moveSan,
                    quality: record.category,
                    isTheoryMove: record.is_theory,
                    phase: record.phase,
                    color,
                    evalBefore: engineInfo.eval_before_cp ?? 0,
                    evalAfter: engineInfo.played_eval_after_cp ?? 0,
                    cpLoss: record.cp_loss ?? 0,
                    accuracy: record.accuracy_pct ?? 100,
                    bestMove: engineInfo.best_move_san || '',
                    fen: fenAfter,
                    fenBefore: record.fen_before || '',
                    gapToSecondBest: engineInfo.second_best_gap_cp ?? null,
                    _fullRecord: record
                  };
                });
                
                const whiteStats = reviewData.stats?.white || {};
                const blackStats = reviewData.stats?.black || {};
                
                const walkthroughDataTransformed = {
                  moves: transformedMoves,
                  openingName: reviewData.opening?.name_final || result.first_game.opening || '',
                  avgWhiteAccuracy: whiteStats.overall_accuracy ?? 0,
                  avgBlackAccuracy: blackStats.overall_accuracy ?? 0,
                  gameTags: [],
                  pgn: result.first_game.pgn,
                  stats: reviewData.stats,
                  // Expose metadata at top-level for walkthrough (player/focus/review_subject)
                  game_metadata: reviewData.game_metadata || {},
                  // NEW: Include LLM-selected key moments
                  selectedKeyMoments: result.selected_key_moments || [],
                  selectionRationale: result.selection_rationale || {},
                  queryIntent: result.selection_rationale?.query_intent || 'general',
                  // Batch pre-commentary generated on backend (ply -> text)
                  preCommentaryByPly: result.pre_commentary_by_ply || {}
                };
                
                setTimeout(() => {
                  setWalkthroughData(walkthroughDataTransformed);
                  startWalkthroughWithData(walkthroughDataTransformed);
                }, 500);
              }
          }
          
          // Add single chart message with complete data (only if narrative was shown)
          if (result.narrative && result.charts) {
            setMessages(prev => [...prev, {
              role: 'assistant',
              content: '📊 **Visual Analysis**\n\nInteractive charts showing your performance breakdown.',
              meta: {
                personalReviewChart: {
                  data: result.charts  // Full object with all chart types
                }
              }
            }]);
          }
          
          return {
            // Keep backend content available (frontend may still want to show a message).
            content: typeof data.content === "string" ? data.content : "",
            tool_calls: data.tool_calls || [],
            context: context,
            raw_data: {
              tool_calls: data.tool_calls,
              personal_review: result
            }
          };
        }
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
      
      // Fallback: extract FEN from assistant text (handles markdown) and display mini board
      try {
        if ((!data.tool_calls || data.tool_calls.length === 0) && typeof data.content === 'string') {
          const detectedFen = extractFenFromText(data.content);
          if (detectedFen) {
            console.log('[LLM-Fallback] Detected FEN in assistant content:', detectedFen);
            try {
              const temp = new Chess(detectedFen);
              setGame(temp);
              setFen(detectedFen);
              setMessages(prev => [...prev, {
                role: 'graph',
                content: '',
                meta: { miniBoard: { fen: detectedFen, pgn: '', orientation: boardOrientation } }
              }]);
            } catch (e) {
              console.warn('[LLM-Fallback] Failed to load detected FEN:', detectedFen, e);
            }
          }
        }
      } catch (e) {
        console.warn('[LLM-Fallback] FEN detection fallback error:', e);
      }

      // Log chain-of-thought / status data
      console.log('📋 [callLLM] Chain-of-thought data:', {
        status_messages: data.status_messages?.length || 0,
        detected_intent: data.detected_intent,
        tools_used: data.tools_used,
        orchestration_mode: data.orchestration?.mode
      });

      // Merge graph data if multiple graphs were collected (shouldn't happen, but handle it)
      const finalGraphData = graphDataCollection.length > 0 
        ? (graphDataCollection.length === 1 
          ? graphDataCollection[0] 
          : graphDataCollection[0]) // Use first graph if multiple (could merge in future)
        : undefined;
      
      return {
        content: data.content,
        tool_calls: data.tool_calls || [],
        context: context,
        annotations: data.annotations || null,  // Backend-generated annotations
        // Chain-of-thought / status tracking
        status_messages: data.status_messages || [],
        detected_intent: data.detected_intent || null,
        tools_used: data.tools_used || [],
        orchestration: data.orchestration || null,
        graphData: finalGraphData, // Include graph data if any graph tools were called
        raw_data: {
          tool_calls: data.tool_calls,
          iterations: data.iterations,
          usage: data.usage,
          review: reviewData  // Include game review data if present
        }
      };
    } catch (error) {
      console.error("LLM call error:", error);
      throw error;
    }
  }

  /**
   * SSE streaming version of callLLM - provides real-time status updates
   */
  async function callLLMStream(
    messages: { role: string; content: string }[], 
    temperature: number = 0.7, 
    model: string = "gpt-4o-mini",
    useTools: boolean = true,
    onStatus: (status: { phase: string; message: string; tool?: string; timestamp: number; replace?: boolean; progress?: number }) => void,
    abortSignal?: AbortSignal
  ): Promise<{
    content: string, 
    tool_calls?: any[], 
    annotations?: any,
    status_messages?: any[],
    detected_intent?: string | null,
    tools_used?: string[],
    orchestration?: any,
    narrative_decision?: any,
    baseline_intuition?: any,
    frontend_commands?: any[],
    final_pgn?: any,
    show_board_link?: any,
    buttons?: any[],
    graphData?: any
  }> {
    return new Promise((resolve, reject) => {
      // Capture abortSignal in outer scope for use in promise chain
      const signal = abortSignal;
      
      // Per-request run id to avoid cross-run status mixing in the UI.
      const streamRunId = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
      const isVerboseAI =
        typeof window !== "undefined" &&
        (new URLSearchParams(window.location.search).get("verbose_ai") === "1" ||
          localStorage.getItem("CHESSTER_VERBOSE_AI") === "1" ||
          process.env.NEXT_PUBLIC_VERBOSE_AI_LOGGING === "1");

      const vLog = (...args: any[]) => {
        if (!isVerboseAI) return;
        console.log(`[AI_VERBOSE][run=${streamRunId}]`, ...args);
      };
      const vWarn = (...args: any[]) => {
        if (!isVerboseAI) return;
        console.warn(`[AI_VERBOSE][run=${streamRunId}]`, ...args);
      };
      // Local capture of what the UI actually received during this run.
      const streamedStatusHistory: any[] = [];
      // Note: backend replaces the first system message with its interpreter-driven prompt,
      // so adding extra system-level tool policy here is redundant and wastes tokens.
      const finalMessages = messages;
      
      // Extract last user message for tool call parsing
      const lastUserMessageObj = finalMessages.find((m, idx, arr) => {
        // Find last user message
        for (let i = arr.length - 1; i >= 0; i--) {
          if (arr[i].role === 'user') {
            return i === idx;
          }
        }
        return false;
      });
      const last_user_message = lastUserMessageObj?.content || '';
      
      // Parse tool calls from message (@tool_name(args))
      const parseToolCalls = (message: string): Array<{tool: string, args: any}> => {
        const toolCalls: Array<{tool: string, args: any}> = [];
        const regex = /@(\w+)\s*\(([^)]*)\)/g;
        let match;
        
        while ((match = regex.exec(message)) !== null) {
          const toolName = match[1];
          const argsString = match[2].trim();
          
          // Parse arguments - handle partial args with `-` placeholders
          const args: any = {};
          if (argsString) {
            const argParts = argsString.split(',').map(s => s.trim());
            // Store as array with placeholders, backend will map to tool schema
            args._raw_args = argParts;
          }
          
          toolCalls.push({ tool: toolName, args });
        }
        
        return toolCalls;
      };
      
      const parsedToolCalls = parseToolCalls(last_user_message);
      const cleanedMessage = last_user_message.replace(/@\w+\s*\([^)]*\)/g, '').trim();
      
      // Update messages to use cleaned message (keep tool calls in context)
      const messagesWithCleaned = finalMessages.map((msg) => {
        if (msg.role === 'user' && msg.content === last_user_message) {
          return { ...msg, content: cleanedMessage || msg.content };
        }
        return msg;
      });
      
      // Build context
      const cachedAnalysis = analysisCache[fen];
      let lastMoveInfo = null;
      if (pgn && pgn.length > 0 && moveTree.getMainLine().length > 0) {
        try {
          const mainLine = moveTree.getMainLine();
          const lastNode = mainLine[mainLine.length - 1];
          const fenBeforeLastMove = mainLine.length > 1 ? mainLine[mainLine.length - 2].fen : "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";
          lastMoveInfo = {
            move: lastNode.move,
            fen_before: fenBeforeLastMove,
            fen_after: lastNode.fen
          };
        } catch (e) {
          console.warn("Failed to extract last move info:", e);
        }
      }
      
      // Build connected accounts from profile preferences
      const connectedAccounts = profilePreferences?.accounts
        ?.filter(acc => acc.username)
        ?.map(acc => ({ platform: acc.platform, username: acc.username })) || [];
      
      const context = {
        fen: fen,
        cached_analysis: cachedAnalysis,
        pgn: pgn,
        mode: mode,
        has_fen: !!fen,
        has_pgn: !!pgn && pgn.length > 0,
        board_state: fen,
        last_move: lastMoveInfo,
        inline_boards: [],
        connected_accounts: connectedAccounts,  // Chess.com/Lichess accounts
        aiGameActive: aiGameActive,  // Whether AI game mode is active
        active_tab_id: activeTabId,  // Add this for baseline_intuition lookup
        session_id: sessionId  // Add this too
      };
      
      // VERBOSE LOGGING FOR AI PATHWAY (enable with ?verbose_ai=1 or localStorage.CHESSTER_VERBOSE_AI=1)
      if (isVerboseAI) {
        console.log('\n' + '='.repeat(80));
        console.log(`🤖 FRONTEND: AI PATHWAY DEBUG (run=${streamRunId})`);
        console.log('='.repeat(80));
        console.log('Model:', model);
        console.log('Mode:', mode);
        console.log('FEN:', fen);
        console.log('Has cached_analysis:', !!cachedAnalysis);
        console.log('Context keys:', Object.keys(context));
        console.log('Context size:', JSON.stringify(context).length, 'chars');
        console.log('Last move:', lastMoveInfo);
        if (cachedAnalysis) {
          console.log('Cached analysis keys:', Object.keys(cachedAnalysis));
        }
        console.log('Active tab ID:', activeTabId);
        console.log('Session ID:', sessionId);
        console.log('='.repeat(80) + '\n');
      }
      
      // Get interpreter model from localStorage (set via console command)
      const interpreterModel = typeof window !== 'undefined' 
        ? localStorage.getItem('CHESSTER_INTERPRETER_MODEL') 
        : null;
      
      const requestBody = JSON.stringify({
        messages: messagesWithCleaned,
        temperature,
        model: lightningMode ? "gpt-4o-mini" : model,
        use_tools: useTools,
        session_id: sessionId,
        task_id: activeTab?.id || null,
        context,
        lightning_mode: lightningMode,
        forced_tool_calls: parsedToolCalls.length > 0 ? parsedToolCalls : undefined
      });
      vLog("POST /llm_chat_stream bytes", requestBody.length);
      
      // Use fetch with ReadableStream for SSE (learning-first logging headers + passive next-action flush)
      Promise.resolve()
        .then(async () => {
          const { buildLearningHeaders, flushNextActionForLastInteraction } = await import("@/lib/learningClient");
          await flushNextActionForLastInteraction("asked_followup");
          return buildLearningHeaders();
        })
        .then(({ interactionId, headers }) => {
          return fetch(`${getBackendBase()}/llm_chat_stream`, {
        method: "POST",
            headers: { "Content-Type": "application/json", ...headers },
        body: requestBody,
        signal: signal
          }).then(async (response) => ({ response, interactionId }));
        })
        .then(async ({ response, interactionId }) => {
        if (!response.ok) {
          const errorData = await response.json();
          reject(new Error(errorData.detail || "SSE connection failed"));
          return;
        }

        // Mark completion at stream start (approx) to enable time-to-next-action.
        try {
          const { noteInteractionCompleted } = await import("@/lib/learningClient");
          noteInteractionCompleted(interactionId);
        } catch {}
        
        const reader = response.body?.getReader();
        if (!reader) {
          reject(new Error("No response body"));
          return;
        }
        
        const decoder = new TextDecoder();
        let buffer = "";
        
        // Accumulate chunked data from game review
        let chunkedGameData: any = null;
        let chunkedStatsData: any = null;
        let chunkedNarrativeData: any = null;
        let chunkedWalkthroughData: any = null;
        
        // Persistent event type across buffer chunks (for large events)
        let currentEventType = "";
        
        const processBuffer = () => {
          // Parse SSE events from buffer
          const lines = buffer.split("\n");
          buffer = lines.pop() || ""; // Keep incomplete line in buffer
          
          let eventData = "";
          
          for (const line of lines) {
            if (line.trim() === "") {
              // Blank line signals end of event - reset event type
              currentEventType = "";
              continue;
            }
            
            if (line.startsWith("event: ")) {
              currentEventType = line.slice(7).trim();
            } else if (line.startsWith("data: ")) {
              eventData = line.slice(6);
              
              try {
                const data = JSON.parse(eventData);
                
                // Use the current event type (persisted across buffer chunks)
                const eventType = currentEventType;
                vLog("SSE", {
                  type: eventType,
                  keys: data && typeof data === "object" ? Object.keys(data) : [],
                  preview: JSON.stringify(data).slice(0, 220),
                });
                
                if (eventType === "status") {
                  const enriched = { ...data, _runId: streamRunId };
                  streamedStatusHistory.push(enriched);
                  onStatus(enriched);
                } else if (eventType === "milestone") {
                  const name = String(data?.name || "");
                  const kind = String(data?.kind || "");
                  const phase =
                    name === "task_started" ? "loading" :
                    name === "fast_classify_done" ? "interpreting" :
                    name === "plan_ready" ? "planning" :
                    name === "goal_built" ? "interpreting" :
                    name === "fast_path_taken" ? "loading" :
                    name === "engine_light_done" ? "investigating" :
                    name === "engine_deep_done" ? "investigating" :
                    name === "claims_ready" ? "summarising" :
                    name === "draft_ready" ? "explaining" :
                    name === "final_ready" ? "explaining" :
                    name === "stopped" ? "explaining" :
                    "loading";
                  const message =
                    name === "task_started" ? "Task started…" :
                    name === "fast_classify_done" ? "Intent classified…" :
                    name === "plan_ready" ? "Plan ready…" :
                    name === "goal_built" ? "Goal built…" :
                    name === "fast_path_taken" ? `Fast path${kind ? ` (${kind})` : ""}…` :
                    name === "engine_light_done" ? "Engine (light) done…" :
                    name === "engine_deep_done" ? "Engine (deep) done…" :
                    name === "claims_ready" ? "Claims ready…" :
                    name === "draft_ready" ? "Draft ready…" :
                    name === "final_ready" ? "Finalizing…" :
                    name === "stopped" ? "Stopped…" :
                    `Milestone: ${name || "unknown"}`;
                  onStatus({ phase, message, timestamp: Date.now(), replace: true });
                } else if (eventType === "facts_ready") {
                  // Cursor-like: commit small, grounded facts early (eval + candidates) before prose.
                  const evalCp = typeof data?.eval_cp === "number" ? data.eval_cp : undefined;
                  const recommended = typeof data?.recommended_move === "string" ? data.recommended_move : undefined;
                  const topMoves = Array.isArray(data?.top_moves) ? data.top_moves : [];
                  const brief = topMoves
                    .slice(0, 3)
                    .map((m: any) => `${m?.move ?? "?"}${typeof m?.eval_cp === "number" ? ` (${m.eval_cp}cp)` : ""}`)
                    .join(", ");
                  const msg =
                    `Facts ready${evalCp !== undefined ? `: eval ${evalCp}cp` : ""}` +
                    `${recommended ? `, candidate: ${recommended}` : ""}` +
                    `${brief ? `, top: ${brief}` : ""}`;
                  onStatus({ phase: "investigating", message: msg.slice(0, 180), timestamp: Date.now() });
                  // Store for rendering (per task/thread)
                  try {
                    const taskKey = activeTab?.id || "default";
                    setFactsByTask(prev => ({
                      ...prev,
                      [taskKey]: {
                        eval_cp: evalCp,
                        recommended_move: recommended,
                        recommended_reason: typeof data?.recommended_reason === "string" ? data.recommended_reason : undefined,
                        top_moves: topMoves,
                        source: "facts_ready",
                        _ts: Date.now()
                      }
                    }));
                  } catch (e) {
                    // ignore
                  }
                } else if (eventType === "summariser_start") {
                  onStatus({ phase: "summarising", message: "Summariser started…", timestamp: Date.now(), replace: true });
                } else if (eventType === "summariser_progress") {
                  const step = data.step || "progress";
                  const dur = typeof data.duration_s === "number" ? ` ${data.duration_s.toFixed(2)}s` : "";
                  onStatus({ phase: "summarising", message: `Summariser ${step}${dur}`, timestamp: Date.now(), replace: true });
                } else if (eventType === "summariser_claim_chunk") {
                  const idx = (typeof data.index === "number" ? data.index : 0) + 1;
                  const total = typeof data.total === "number" ? data.total : undefined;
                  const summary = data?.claim?.summary || "";
                  onStatus({
                    phase: "summarising",
                    message: `Claim ${idx}${total ? `/${total}` : ""}: ${summary}`.slice(0, 160),
                    timestamp: Date.now()
                  });
                } else if (eventType === "summariser_done") {
                  const n = typeof data.claims_count === "number" ? data.claims_count : undefined;
                  onStatus({ phase: "summarising", message: `Summariser done${n !== undefined ? ` (${n} claims)` : ""}`, timestamp: Date.now(), replace: true });
                } else if (eventType === "explainer_start") {
                  onStatus({ phase: "explaining", message: "Explainer started…", timestamp: Date.now(), replace: true });
                } else if (eventType === "explainer_prompt_audit") {
                  // Useful for debugging token bloat in the UI logs.
                  const approx = typeof data.approx_total_tokens === "number" ? data.approx_total_tokens : undefined;
                  onStatus({
                    phase: "explaining",
                    message: `Explainer prompt ~${approx ?? "?"} tok`,
                    timestamp: Date.now()
                  });
                } else if (eventType === "explainer_progress") {
                  const step = data.step || "progress";
                  const dur = typeof data.duration_s === "number" ? ` ${data.duration_s.toFixed(2)}s` : "";
                  onStatus({ phase: "explaining", message: `Explainer ${step}${dur}`, timestamp: Date.now(), replace: true });
                } else if (eventType === "explainer_chunk") {
                  const idx = (typeof data.index === "number" ? data.index : 0) + 1;
                  const total = typeof data.total === "number" ? data.total : undefined;
                  onStatus({
                    phase: "explaining",
                    message: `Explanation chunk ${idx}${total ? `/${total}` : ""}…`,
                    timestamp: Date.now()
                  });
                } else if (eventType === "plan_created") {
                  // Execution plan created by Planner
                  vLog("📋 SSE plan_created received", data);
                  setAnalysisInProgress(true);
                  setExecutionPlan({ ...data, startTime: Date.now() });
                } else if (eventType === "step_update") {
                  // Step status update from Executor
                  vLog("📝 SSE step_update received", data);
                  setExecutionPlan((prev: any) => {
                    if (!prev) return prev;
                    // Plans can expand at runtime (executor may inject additional steps).
                    const incomingStepNum = typeof data.step_number === "number" ? data.step_number : 0;
                    const prevMaxStep = Array.isArray(prev.steps)
                      ? prev.steps.reduce((m: number, s: any) => Math.max(m, Number(s?.step_number || 0)), 0)
                      : 0;
                    const maxStepNum = Math.max(prevMaxStep, incomingStepNum);
                    const hasStep = Array.isArray(prev.steps) && prev.steps.some((s: any) => s?.step_number === incomingStepNum);
                    const nextSteps = hasStep
                      ? prev.steps.map((step: any) =>
                          step.step_number === data.step_number ? { ...step, status: data.status } : step
                        )
                      : [
                          ...(Array.isArray(prev.steps) ? prev.steps : []),
                          {
                            step_number: incomingStepNum,
                            action_type: data.action_type || "unknown",
                            purpose: data.purpose || "",
                            status: data.status || "in_progress",
                          },
                        ].sort((a: any, b: any) => (a.step_number || 0) - (b.step_number || 0));
                    return {
                      ...prev,
                      steps: nextSteps,
                      total_steps: typeof prev.total_steps === "number" ? Math.max(prev.total_steps, maxStepNum) : maxStepNum,
                    };
                  });
                } else if (eventType === "thinking_started") {
                  // Thinking stage started during investigation
                  vLog("🧠 SSE thinking_started received", data);
                  setThinkingStage({ ...data, startTime: Date.now() });
                } else if (eventType === "plan_progress") {
                  // Overall plan progress update
                  vLog("📊 SSE plan_progress received", data);
                  // Keep plan totals in sync (executor-injected steps can change total).
                  if (typeof data.total === "number") {
                    setExecutionPlan((prev: any) => {
                      if (!prev) return prev;
                      return { ...prev, total_steps: Math.max(Number(prev.total_steps || 0), data.total) };
                    });
                  }
                  // Mark as complete when 100%
                  if (data.percentage === 100) {
                    setExecutionPlan((prev: any) => {
                      if (!prev) return prev;
                      const startTime = prev.startTime || Date.now();
                      const thinkingTimeSeconds = Math.round((Date.now() - startTime) / 1000);
                      return {
                        ...prev,
                        isComplete: true,
                        thinkingTimeSeconds
                      };
                    });
                    setThinkingStage((prev: any) => {
                      if (!prev) return prev;
                      const startTime = prev.startTime || Date.now();
                      const thinkingTimeSeconds = Math.round((Date.now() - startTime) / 1000);
                      return {
                        ...prev,
                        isComplete: true,
                        thinkingTimeSeconds
                      };
                    });
                  }
                } else if (eventType === "pgn_update") {
                  // PGN update during investigation (for live board view)
                  vLog("♟️ SSE pgn_update received", data);
                  // Handle status messages from pgn_update
                  if (data.type === "status" && data.message) {
                    onStatus({ phase: "investigating", message: data.message, timestamp: Date.now() });
                  } else if (data.move_san) {
                    onStatus({ phase: "investigating", message: `Exploring move ${data.move_san}...`, timestamp: Date.now() });
                  }
                } else if (eventType === "board_state") {
                  // NEW: FEN updates during investigation (for board preview)
                  vLog("♟️ SSE board_state received", data);
                  if (data.type === "move_investigation_start" || data.type === "move_played") {
                    // Show FEN preview during investigation
                    if (data.fen) {
                      setPreviewFEN(data.fen);
                      if (data.move_san) {
                        onStatus({ phase: "investigating", message: `Investigating ${data.move_san}...`, timestamp: Date.now() });
                      }
                    }
                  } else if (data.type === "investigation_complete" && data.is_reverting) {
                    // Revert to original FEN
                    setPreviewFEN(null);
                  }
                } else if (eventType === "game_loaded") {
                  // Chunked SSE: Game data for tab loading
                  console.log("📦 [SSE] game_loaded received", { keys: Object.keys(data), hasFirstGame: !!data.first_game });
                  vLog("📦 SSE game_loaded received");
                  chunkedGameData = data;
                  onStatus({ phase: "loading", message: "Game loaded...", progress: 0.92, timestamp: Date.now() });
                } else if (eventType === "stats_ready") {
                  // Chunked SSE: Statistics and charts
                  console.log("📊 [SSE] stats_ready received", { keys: Object.keys(data) });
                  vLog("📊 SSE stats_ready received");
                  chunkedStatsData = data;
                  onStatus({ phase: "loading", message: "Statistics ready...", progress: 0.94, timestamp: Date.now() });
                } else if (eventType === "narrative") {
                  // Chunked SSE: Narrative text
                  console.log("📝 [SSE] narrative received", { hasNarrative: !!data.narrative });
                  vLog("📝 SSE narrative received");
                  chunkedNarrativeData = data;
                  onStatus({ phase: "loading", message: "Narrative ready...", progress: 0.96, timestamp: Date.now() });
                } else if (eventType === "walkthrough_data") {
                  // Chunked SSE: Walkthrough data (minimal ply records)
                  console.log("🚶 [SSE] walkthrough_data received", { plies: data.ply_records?.length, keys: Object.keys(data) });
                  vLog("🚶 SSE walkthrough_data received", { plies: data.ply_records?.length });
                  chunkedWalkthroughData = data;
                  onStatus({ phase: "loading", message: "Walkthrough ready...", progress: 0.98, timestamp: Date.now() });
                } else if (eventType === "complete") {
                  console.log("🎉 [SSE] complete received", { 
                    hasToolCalls: !!data.tool_calls, 
                    toolCallsCount: data.tool_calls?.length,
                    chunkedGameData: !!chunkedGameData,
                    chunkedStatsData: !!chunkedStatsData,
                    chunkedNarrativeData: !!chunkedNarrativeData,
                    chunkedWalkthroughData: !!chunkedWalkthroughData
                  });
                  vLog("🎉 SSE complete received", (data.response?.slice(0, 140) || data.content?.slice(0, 140)));
                  setAnalysisInProgress(false);
                  
                  // Merge chunked data into tool_calls if available
                  let mergedToolCalls = data.tool_calls || [];
                  const graphDataCollection: any[] = []; // Collect graph data from multiple tool calls
                  
                  // Process graph tool calls
                  if (mergedToolCalls.length > 0) {
                    mergedToolCalls.forEach((tc: any) => {
                      if (tc.tool === 'add_personal_review_graph' && tc.result) {
                        const graphResult = tc.result;
                        if (graphResult.error) {
                          console.warn(`[Graph Tool] Error: ${graphResult.error}`);
                        } else if (graphResult.graph_id && graphResult.series) {
                          const existingGraph = graphDataCollection.find(g => g.graph_id === graphResult.graph_id);
                          if (existingGraph) {
                            existingGraph.series.push(...graphResult.series);
                          } else {
                            graphDataCollection.push({
                              graph_id: graphResult.graph_id,
                              series: graphResult.series,
                              xLabels: graphResult.xLabels,
                              grouping: graphResult.grouping,
                            });
                          }
                          console.log(`[Graph Tool] Collected graph data: ${graphResult.series.length} series`);
                        }
                      }
                    });
                  }
                  
                  // Check if we need to merge chunked data
                  // Run merge if: (1) chunked data exists, OR (2) result is marked as chunked/truncated
                  const hasChunkedData = chunkedGameData || chunkedStatsData || chunkedNarrativeData || chunkedWalkthroughData;
                  const hasChunkedFlag = mergedToolCalls.some((tc: any) => 
                    tc.tool === "fetch_and_review_games" && 
                    (tc.result?._chunked === true || tc.result?._truncated === true)
                  );
                  const needsChunkedMerge = hasChunkedData || hasChunkedFlag;
                  
                  if (needsChunkedMerge) {
                    console.log("📦 Merging chunked data into result...", {
                      hasChunkedData,
                      hasChunkedFlag,
                      chunkedGameData: !!chunkedGameData,
                      chunkedStatsData: !!chunkedStatsData,
                      chunkedNarrativeData: !!chunkedNarrativeData,
                      chunkedWalkthroughData: !!chunkedWalkthroughData
                    });
                    // Find the game review tool call and enhance it
                    mergedToolCalls = mergedToolCalls.map((tc: any) => {
                      if (tc.tool === "fetch_and_review_games" || tc.result?._chunked === true || tc.result?._truncated === true) {
                        // Check if result is truncated or chunked - if so, build from chunked data
                        const isTruncated = tc.result?._truncated === true;
                        const isChunked = tc.result?._chunked === true;
                        const baseResult = (isTruncated || isChunked) ? {} : (tc.result || {});
                        
                        console.log(`📦 [Chunked Merge] Tool: ${tc.tool}, isTruncated: ${isTruncated}, isChunked: ${isChunked}`);
                        console.log(`📦 [Chunked Merge] chunkedGameData keys:`, chunkedGameData ? Object.keys(chunkedGameData) : []);
                        console.log(`📦 [Chunked Merge] chunkedStatsData keys:`, chunkedStatsData ? Object.keys(chunkedStatsData) : []);
                        console.log(`📦 [Chunked Merge] chunkedNarrativeData keys:`, chunkedNarrativeData ? Object.keys(chunkedNarrativeData) : []);
                        console.log(`📦 [Chunked Merge] chunkedWalkthroughData keys:`, chunkedWalkthroughData ? Object.keys(chunkedWalkthroughData) : []);
                        
                        // Build first_game from chunkedGameData if available
                        let firstGame = baseResult.first_game;
                        if (chunkedGameData) {
                          // chunkedGameData might have first_game directly, or we need to construct it
                          if (chunkedGameData.first_game) {
                            firstGame = chunkedGameData.first_game;
                          } else if (chunkedGameData.pgn) {
                            // Construct first_game from available data
                            firstGame = {
                              pgn: chunkedGameData.pgn,
                              white: chunkedGameData.white || chunkedGameData.first_game?.white,
                              black: chunkedGameData.black || chunkedGameData.first_game?.black,
                              date: chunkedGameData.date || chunkedGameData.first_game?.date,
                              result: chunkedGameData.result || chunkedGameData.first_game?.result,
                              time_control: chunkedGameData.time_control || chunkedGameData.first_game?.time_control,
                              opening: chunkedGameData.opening || chunkedGameData.first_game?.opening,
                            };
                          }
                        }
                        
                        return {
                          ...tc,
                          result: {
                            ...baseResult,
                            // Merge in chunked data (these will override truncated placeholder)
                            ...(chunkedGameData || {}),
                            ...(chunkedStatsData || {}),
                            ...(chunkedNarrativeData || {}),
                            // Ensure first_game is set from chunked data if available
                            first_game: firstGame || baseResult.first_game,
                            // Build first_game_review from walkthrough data
                            first_game_review: chunkedWalkthroughData ? {
                              ply_records: chunkedWalkthroughData.ply_records || [],
                              key_points: chunkedWalkthroughData.key_points || [],
                              opening: chunkedWalkthroughData.opening || {},
                              game_metadata: chunkedWalkthroughData.game_metadata || {},
                              stats: chunkedWalkthroughData.stats || {}
                            } : (baseResult.first_game_review || chunkedWalkthroughData),
                            selected_key_moments: chunkedWalkthroughData?.selected_key_moments || baseResult?.selected_key_moments,
                            selection_rationale: chunkedWalkthroughData?.selection_rationale || baseResult?.selection_rationale,
                            pre_commentary_by_ply: chunkedWalkthroughData?.pre_commentary_by_ply || baseResult?.pre_commentary_by_ply,
                            // Ensure success is set if we have data
                            success: baseResult.success !== undefined ? baseResult.success : (chunkedGameData || chunkedStatsData || chunkedNarrativeData ? true : undefined),
                            _chunked: false, // Mark as merged
                            _truncated: false // Clear truncation flag
                          }
                        };
                      }
                      return tc;
                    });
                  } else {
                    // Even if no chunked data, check if result is truncated/chunked and log warning
                    mergedToolCalls.forEach((tc: any) => {
                      if (tc.tool === "fetch_and_review_games") {
                        if (tc.result?._truncated === true) {
                          console.warn('⚠️ [Chunked Merge] Result is truncated but no chunked data received! Size:', tc.result._size);
                          console.warn('⚠️ [Chunked Merge] This may indicate chunked data events arrived after complete event');
                        }
                        if (tc.result?._chunked === true && !hasChunkedData) {
                          console.warn('⚠️ [Chunked Merge] Result is marked as chunked but no chunked data received!');
                          console.warn('⚠️ [Chunked Merge] Chunked events may have been lost or arrived out of order');
                        }
                      }
                    });
                  }
                  
                  // Merge graph data if multiple graphs were collected
                  const finalGraphData = graphDataCollection.length > 0 
                    ? (graphDataCollection.length === 1 
                      ? graphDataCollection[0] 
                      : graphDataCollection[0]) // Use first graph if multiple
                    : undefined;
                  
                  // Use response field if available, otherwise fallback to content
                  const finalContent = data.response || data.content || "";

                  // If backend provides a v2 envelope, store FactsCard for this task
                  try {
                    const taskKey = activeTab?.id || "default";
                    const env = data?.envelope;
                    const fc = env?.facts_card;
                    if (fc) {
                      const topMoves =
                        Array.isArray(fc?.top_moves)
                          ? fc.top_moves.slice(0, 5).map((m: any) => ({
                              move: m?.san,
                              eval_cp: typeof m?.eval_cp === "number" ? m.eval_cp : undefined
                            }))
                          : [];
                      setFactsByTask(prev => ({
                        ...prev,
                        [taskKey]: {
                          eval_cp: typeof fc?.eval_cp === "number" ? fc.eval_cp : undefined,
                          recommended_move: typeof env?.recommended_move === "string" ? env.recommended_move : undefined,
                          recommended_reason: typeof env?.stop_reason === "string" ? env.stop_reason : undefined,
                          top_moves: topMoves,
                          source: "envelope",
                          _ts: Date.now()
                        }
                      }));
                    }
                  } catch (e) {
                    // ignore
                  }
                  
                  // Mark execution plan and thinking stage as complete with thinking time
                  setExecutionPlan((prev: any) => {
                    if (!prev) return prev;
                    const startTime = prev.startTime || Date.now();
                    const thinkingTimeSeconds = Math.round((Date.now() - startTime) / 1000);
                    return {
                      ...prev,
                      isComplete: true,
                      thinkingTimeSeconds
                    };
                  });
                  setThinkingStage((prev: any) => {
                    if (!prev) return prev;
                    const startTime = prev.startTime || Date.now();
                    const thinkingTimeSeconds = Math.round((Date.now() - startTime) / 1000);
                    return {
                      ...prev,
                      isComplete: true,
                      thinkingTimeSeconds
                    };
                  });
                  
                  // Handle buttons for play-against-AI side selection
                  if (Array.isArray(data.buttons) && data.buttons.length > 0) {
                    // Store buttons to add after the message
                    resolve({
                      content: finalContent,
                      tool_calls: mergedToolCalls,
                      annotations: data.annotations,
                      // Prefer the exact stream history we received client-side; fall back to backend summary.
                      status_messages: (streamedStatusHistory.length > 0 ? streamedStatusHistory : (data.status_messages || [])),
                      detected_intent: data.detected_intent,
                      tools_used: data.tools_used,
                      orchestration: data.orchestration,
                      narrative_decision: data.narrative_decision,
                      baseline_intuition: data.baseline_intuition || data.envelope?.baseline_intuition,
                      final_pgn: data.final_pgn,
                      show_board_link: data.show_board_link,
                      buttons: data.buttons,
                      graphData: finalGraphData
                    });
                    
                    // Log merged tool calls for debugging
                    mergedToolCalls.forEach((tc: any) => {
                      if (tc.tool === "fetch_and_review_games") {
                        console.log('✅ [Resolve] Merged tool call result:', {
                          hasResult: !!tc.result,
                          success: tc.result?.success,
                          hasFirstGame: !!tc.result?.first_game,
                          hasFirstGameReview: !!tc.result?.first_game_review,
                          isTruncated: tc.result?._truncated,
                          resultKeys: tc.result ? Object.keys(tc.result) : []
                        });
                      }
                    });
                    
                    return true;
                  }
                  
                  // Execute UI commands if present
                  if (Array.isArray(data.ui_commands) && data.ui_commands.length > 0) {
                    executeUICommands(data.ui_commands, handleSendMessage);
                  } else if (Array.isArray(data.envelope?.ui_commands) && data.envelope.ui_commands.length > 0) {
                    executeUICommands(data.envelope.ui_commands, handleSendMessage);
                  }
                  
                  resolve({
                    content: finalContent,
                    tool_calls: mergedToolCalls,
                    annotations: data.annotations,
                    status_messages: (streamedStatusHistory.length > 0 ? streamedStatusHistory : (data.status_messages || [])),
                    detected_intent: data.detected_intent,
                    tools_used: data.tools_used,
                    orchestration: data.orchestration,
                    narrative_decision: data.narrative_decision,
                    baseline_intuition: data.baseline_intuition || data.envelope?.baseline_intuition,
                    final_pgn: data.final_pgn,  // NEW: PGN with all investigated lines
                    show_board_link: data.show_board_link,  // NEW: Link to chess board page
                    buttons: data.buttons || [],  // Include buttons (empty array if not present)
                    graphData: finalGraphData  // Include graph data if any graph tools were called
                  });
                  
                  // Log merged tool calls for debugging
                  mergedToolCalls.forEach((tc: any) => {
                    if (tc.tool === "fetch_and_review_games") {
                      console.log('✅ [Resolve] Merged tool call result:', {
                        hasResult: !!tc.result,
                        success: tc.result?.success,
                        hasFirstGame: !!tc.result?.first_game,
                        hasFirstGameReview: !!tc.result?.first_game_review,
                        isTruncated: tc.result?._truncated,
                        resultKeys: tc.result ? Object.keys(tc.result) : []
                      });
                    }
                  });
                  
                  return true; // Signal completion
                } else if (eventType === "limit_exceeded") {
                  // Handle limit exceeded - show popup but continue conversation
                  vLog("⚠️ SSE limit_exceeded received", data);
                  setLimitExceededInfo({
                    type: data.type || "token_limit",
                    message: data.message || "Limit exceeded",
                    usage: data.usage || {},
                    next_step: data.next_step || "upgrade",
                    available_tools: data.available_tools || {}
                  });
                  // Don't block - conversation continues
                } else if (eventType === "error") {
                  setAnalysisInProgress(false);
                  reject(new Error(data.message));
                  return true; // Signal completion
                } else if (eventType === "summariser_claims" || eventType === "summariser_pre_final") {
                  // Backend emits these for richer progress/debug; keep UI quiet (no unknown-event spam).
                  onStatus({ phase: "summarising", message: "Summariser produced narrative…", timestamp: Date.now() });
                } else if (eventType === "explainer_done") {
                  // Backend emits a final explainer metrics event; ignore quietly.
                  const len = typeof data.length === "number" ? data.length : undefined;
                  onStatus({ phase: "explaining", message: `Explainer done${len !== undefined ? ` (${len} chars)` : ""}`, timestamp: Date.now() });
                } else if (eventType === "") {
                  // Empty event type - might be a continuation or malformed event
                  console.warn("⚠️ SSE event with empty type, data preview:", JSON.stringify(data).slice(0, 100));
                } else {
                  // Log unknown event types for debugging
                  console.log("⚠️ Unknown SSE event type:", eventType, "data preview:", JSON.stringify(data).slice(0, 100));
                }
              } catch (parseErr) {
                console.warn("❌ Failed to parse SSE event:", parseErr, "eventType:", currentEventType, "data preview:", eventData?.slice(0, 200));
              }
            }
          }
          return false; // Not complete yet
        };
        
        while (true) {
          const { done, value } = await reader.read();
          
          if (value) {
            buffer += decoder.decode(value, { stream: true });
          }
          
          if (processBuffer()) {
            return; // Complete event was processed
          }
          
          if (done) {
            // Process any remaining buffer - try multiple times with different line endings
            if (buffer.trim()) {
              // Try processing as-is first
              if (processBuffer()) {
                return;
              }
              // Try with explicit newline
              buffer += "\n";
              if (processBuffer()) {
                return;
              }
              // Try with double newline (SSE format requires blank line)
              buffer += "\n";
              if (processBuffer()) {
                return;
              }
              // Log what we have in the buffer for debugging
              console.warn("SSE stream ended with unprocessed buffer:", buffer.slice(0, 500));
            }
            console.warn("SSE stream ended without complete event");
            reject(new Error("Stream ended unexpectedly"));
            break;
          }
        }
      }).catch((error) => {
        // Handle abort errors gracefully
        if (error.name === 'AbortError' || (abortSignal && abortSignal.aborted)) {
          reject(new Error('Request cancelled'));
        } else {
          reject(error);
        }
      });
    });
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

  // Load system prompt on mount (guard against StrictMode double invoke)
  const greetedRef = useRef(false);

  // Robust FEN extraction from LLM text (handles markdown and code blocks)
  function extractFenFromText(text: string): string | null {
    if (!text) return null;
    // 1) Try backtick code spans first
    const codeSpanRegex = /`([^`]+)`/g;
    const codeBlockRegex = /```[a-zA-Z]*\n([\s\S]*?)```/g;
    const candidates: string[] = [];
    let m: RegExpExecArray | null;
    while ((m = codeSpanRegex.exec(text)) !== null) {
      candidates.push(m[1]);
    }
    while ((m = codeBlockRegex.exec(text)) !== null) {
      candidates.push(m[1]);
    }

    // 2) Regex to find inline FEN-like patterns anywhere in text
    const inlineFenRegex = /([rnbqkpRNBQKP1-8\/]{1,}\/[^\s]*\/[^\s]*\/[^\s]*\/[^\s]*\/[^\s]*\/[^\s]*\/[^\s]*)\s([wb])\s([-KQkq]+|-)\s([-a-h0-9]+|-)\s(\d+)\s(\d+)/g;
    while ((m = inlineFenRegex.exec(text)) !== null) {
      const fen = `${m[1]} ${m[2]} ${m[3]} ${m[4]} ${m[5]} ${m[6]}`;
      candidates.push(fen);
    }

    // 3) Clean candidates from markdown emphasis and punctuation
    const cleaned = candidates
      .map((c) => c.replace(/[\*#_]+/g, ' ').replace(/[\u2018\u2019\u201C\u201D]/g, '"').trim())
      .map((c) => c.replace(/^[^rnbqkpRNBQK0-9]+/, '').replace(/[^\w\s\/-]+$/, ''));

    // 4) Validate candidates using chess.js
    for (const cand of cleaned) {
      try {
        const tmp = new Chess(cand);
        // Ensure there are 6 fields and 7 slashes in piece placement
        const parts = cand.split(/\s+/);
        if (parts.length >= 6 && (parts[0].match(/\//g) || []).length === 7) {
          return cand;
        }
      } catch (e) {
        // ignore invalid
      }
    }
    return null;
  }
  useEffect(() => {
    if (greetedRef.current) return;
    greetedRef.current = true;
    getMeta()
      .then((meta) => {
        setSystemPrompt(meta.system_prompt);
        if (messages.length === 0) {
            addSystemMessage("Chesster ready! Ask me anything about chess, or make a move on the board to start playing. You can also say 'let's play', 'analyze', or 'give me a puzzle'!");
          }
      })
      .catch((err) => {
        // Don't show error for aborted requests (timeout)
        const isAbortError = err instanceof Error && 
          (err.name === 'AbortError' || err.message.includes('aborted'));
        
        if (!isAbortError) {
          console.error("Failed to load meta:", err);
          if (messages.length === 0) {
            addSystemMessage("⚠ Backend not available. Start the backend server.");
          }
        } else {
          console.warn("Meta request timed out (this is normal for slow requests)");
        }
      });
  }, []);

  // Listen for inline board changes and analyze those positions independently
  useEffect(() => {
    const onInlineChanged = async (e: any) => {
      try {
        const detail = e.detail || {};
        const { id, fen: inlineFen, pgn: inlinePgn } = detail;
        if (!inlineFen) return;
        console.log('[InlineBoard] Changed', detail);
        // Analyze inline position (do not mutate main game)
        const res = await analyzePosition(inlineFen);
        setInlineAnalysisCache(prev => ({ ...prev, [inlineFen]: res }));
        // Track recent inline contexts (cap to last 5)
        setInlineContexts(prev => {
          const next = [...prev.filter(c => !(c.id === id || c.fen === inlineFen)), { id, fen: inlineFen, pgn: inlinePgn, orientation: detail.orientation }];
          return next.slice(-5);
        });
      } catch (err) {
        console.warn('[InlineBoard] Analysis failed', err);
      }
    };
    if (typeof window !== 'undefined') {
      window.addEventListener('inlineBoardChanged', onInlineChanged as any);
      
      // Listen for confidence lesson events
      const handleConfidenceLesson = (event: CustomEvent) => {
        const lesson = event.detail;
        console.log('📚 Confidence lesson received:', lesson);
        
        if (!lesson || !lesson.sections || lesson.sections.length === 0) {
          addSystemMessage('No problematic lines found to create a lesson from.');
          return;
        }
        
        addSystemMessage(`🎓 Generated confidence lesson: ${lesson.title}`);
        addAssistantMessage(`**${lesson.title}**\n\n${lesson.description}\n\nThis lesson contains ${lesson.total_steps} step(s) analyzing low-confidence lines from the confidence tree.`);
        
        // Convert confidence lesson format to match existing lesson system
        const allPositions: any[] = [];
        for (const section of lesson.sections) {
          if (section.positions && Array.isArray(section.positions)) {
            for (const pos of section.positions) {
              allPositions.push({
                fen: pos.position_fen,
                objective: pos.objective || pos.explanation,
                hints: pos.hints || [],
                candidates: pos.candidates || [],
                side: 'white', // Default, could be determined from FEN
                difficulty: 'intermediate',
                themes: ['confidence_analysis', 'line_evaluation']
              });
            }
          }
        }
        
        if (allPositions.length === 0) {
          addSystemMessage('No positions found in the lesson.');
          return;
        }
        
        // Set up lesson state
        setCurrentLesson({
          plan: {
            title: lesson.title,
            description: lesson.description,
            lesson_id: lesson.lesson_id || 'confidence-lesson'
          },
          positions: allPositions,
          currentIndex: 0
        });
        
        setLessonProgress({ current: 0, total: allPositions.length });
        enterLessonMode();
        
        // Load first position
        loadLessonPosition(allPositions[0], 0, allPositions.length);
      };
      
      return () => window.removeEventListener('inlineBoardChanged', onInlineChanged as any);
    }
  }, [enterLessonMode]);

  // Listen for confidence lesson events
  useEffect(() => {
    if (typeof window === 'undefined') return;
    
    const handleConfidenceLesson = (event: CustomEvent) => {
      const lesson = event.detail;
      console.log('📚 Confidence lesson received:', lesson);
      
      if (!lesson || !lesson.sections || lesson.sections.length === 0) {
        addSystemMessage('No problematic lines found to create a lesson from.');
        return;
      }
      
      addSystemMessage(`🎓 Generated confidence lesson: ${lesson.title}`);
      addAssistantMessage(`**${lesson.title}**\n\n${lesson.description}\n\nThis lesson contains ${lesson.total_steps || 0} step(s) analyzing low-confidence lines from the confidence tree.`);
      
      // Convert confidence lesson format to match existing lesson system
      const allPositions: any[] = [];
      for (const section of lesson.sections) {
        if (section.positions && Array.isArray(section.positions)) {
          for (const pos of section.positions) {
            allPositions.push({
              fen: pos.position_fen,
              objective: pos.objective || pos.explanation,
              hints: pos.hints || [],
              candidates: pos.candidates || [],
              side: 'white', // Default, could be determined from FEN
              difficulty: 'intermediate',
              themes: ['confidence_analysis', 'line_evaluation']
            });
          }
        }
      }
      
      if (allPositions.length === 0) {
        addSystemMessage('No positions found in the lesson.');
        return;
      }
      
      // Set up lesson state
      setCurrentLesson({
        plan: {
          title: lesson.title,
          description: lesson.description,
          lesson_id: lesson.lesson_id || 'confidence-lesson'
        },
        positions: allPositions,
        currentIndex: 0
      });
      
      setLessonProgress({ current: 0, total: allPositions.length });
      enterLessonMode();
      
      // Load first position
      loadLessonPosition(allPositions[0], 0, allPositions.length);
    };
    
    window.addEventListener('startConfidenceLesson', handleConfidenceLesson as any);
    
    return () => {
      window.removeEventListener('startConfidenceLesson', handleConfidenceLesson as any);
    };
  }, [addSystemMessage, addAssistantMessage, setCurrentLesson, setLessonProgress, loadLessonPosition, enterLessonMode]);

  const formatBulletList = (items?: string[]) =>
    items && items.length ? items.map((item) => `• ${item}`).join("\n") : "• —";

  const formatPlayerName = (player: any, fallback: string) => {
    if (!player) return fallback;
    if (typeof player === "string") return player;
    if (typeof player === "object") {
      const title = typeof player.title === "string" ? player.title.toUpperCase() : null;
      const name =
        player.name ||
        player.username ||
        player.player ||
        player.full_name ||
        player.display_name ||
        fallback;
      const rating = player.rating ? `(${player.rating})` : null;
      return [title, name, rating].filter(Boolean).join(" ").trim() || fallback;
    }
    return fallback;
  };

  const presentOpeningLessonSections = (
    payload: OpeningLessonResponse,
    options?: { announce?: boolean }
  ) => {
    if (!payload.lesson) return;
    const shouldAnnounce = options?.announce ?? true;
    const perspective = payload.metadata?.orientation === "black" ? "Black" : "White";
    if (shouldAnnounce) {
      addAssistantMessage(
        `**${payload.lesson.title} (${perspective})**\nNew guided lesson prepared with ${payload.lesson.sections.length} focus areas.`
      );
    }
    const sections: LessonDataSection[] = [];

    if (payload.personal_overview) {
      const overview = payload.personal_overview as any;
      const lines = [
        `Games: ${overview.games_played ?? "—"}`,
        `Win rate: ${overview.win_rate != null ? `${overview.win_rate}%` : "—"}`,
        `Opening accuracy: ${overview.opening_accuracy != null ? `${overview.opening_accuracy}%` : "—"}`,
      ];
      if (overview.strengths?.length) {
        lines.push("", "Strengths:", formatBulletList(overview.strengths));
      }
      if (overview.issues?.length) {
        lines.push("", "Growth targets:", formatBulletList(overview.issues));
      }
      sections.push({ title: "Personal overview", body: lines.filter(Boolean).join("\n") });
    }

    if (payload.model_lines) {
      const modelLines = payload.model_lines as any;
      const mainLineMoves = modelLines.main_line?.moves?.slice(0, 12).join(" ") || "—";
      const alternates =
        modelLines.alternates?.map((alt: any) => `• ${alt.name || "Alternate line"}`) || [];
      const alternateText = alternates.length ? `\n\nAlternates:\n${alternates.join("\n")}` : "";
      sections.push({
        title: "Model lines",
        body: `Main plan: ${mainLineMoves}${alternateText}`,
      });
    }

    if (payload.user_games?.length) {
      const summaries = payload.user_games.slice(0, 4).map((game: any) => {
        if (game.moves?.length) {
          const header = `vs ${game.opponent || "opponent"}${game.result ? ` (${game.result})` : ""}${
            game.date ? ` – ${game.date}` : ""
          }`;
          return `• ${header}\n  Moves: ${game.moves.slice(0, 10).join(" ")}`;
        }
        if (game.prompt) {
          return `• ${game.prompt}${game.correct_move ? ` → best: ${game.correct_move}` : ""}`;
        }
        return null;
      }).filter(Boolean) as string[];
      if (summaries.length) {
        sections.push({ title: "Your games in this line", body: summaries.join("\n") });
      }
    }

    if (payload.master_refs?.length) {
      const refs = payload.master_refs.slice(0, 3).map((ref: any) => {
        const players = `${formatPlayerName(ref.white, "White")} vs ${formatPlayerName(ref.black, "Black")}`;
        const year = ref.year ? ` (${ref.year})` : "";
        const winner = ref.winner ? ` – winner: ${ref.winner}` : "";
        const moves = ref.moves?.length ? `\n  Segment: ${ref.moves.slice(0, 10).join(" ")}` : "";
        return `• ${players}${year}${winner}${moves}`;
      });
      sections.push({ title: "Model references", body: refs.join("\n") });
    }

    if (payload.problem_patterns?.patterns?.length) {
      const patternLines = (payload.problem_patterns.patterns as any[])
        .slice(0, 3)
        .map((pattern) => `• ${pattern.label}: ${pattern.detail}`);
      sections.push({ title: "Problem patterns", body: patternLines.join("\n") });
    }

    if (payload.drills) {
      const drillCount = payload.drills.tactics?.length || 0;
      const practiceCount = payload.drills.practice_positions?.length || 0;
      sections.push({
        title: "Drills queued",
        body: `Tactics: ${drillCount}\nPractice boards: ${practiceCount}\nUse the practice controls below when you're ready to play through them.`,
      });
    }

    if (payload.summary?.takeaways?.length) {
      sections.push({ title: "Lesson summary", body: formatBulletList(payload.summary.takeaways) });
    }

    if (sections.length) {
      setLessonDataSections(sections);
      setShowLessonDataPanel(false);
      if (shouldAnnounce) {
        addAssistantMessage("Lesson data saved. Use the Lesson Data button anytime to review the raw breakdown.");
      }
    } else {
      setLessonDataSections(null);
    }

    if (payload.lesson_tree?.length && shouldAnnounce) {
      addAssistantMessage(
        "Interactive tree ready — play the blue main line, explore green alternates, and track the red arrow for the opponent's threat."
      );
    }
  };

  const normalizePracticePosition = (pos: any, idx: number, fallbackTitle: string) => {
    const normalizeObjective = (objective: any) => {
      if (!objective) return "Find the best continuation";
      if (typeof objective === "string") return objective;
      if (typeof objective === "object") {
        return (
          objective.text ||
          objective.title ||
          objective.description ||
          "Find the best continuation"
        );
      }
      return String(objective);
    };

    const normalizeHints = (hints: any): string[] => {
      if (!Array.isArray(hints)) return [];
      return hints
        .map((hint) => {
          if (!hint) return null;
          if (typeof hint === "string") return hint;
          if (typeof hint === "object") {
            return hint.text || hint.hint || hint.note || JSON.stringify(hint);
          }
          return String(hint);
        })
        .filter((val): val is string => Boolean(val));
    };

    const normalizeTopic = () => {
      if (typeof pos.topic_name === "string") return pos.topic_name;
      if (typeof pos.topic === "string") return pos.topic;
      if (typeof pos.topic === "object" && pos.topic) {
        return pos.topic.name || pos.topic.title || fallbackTitle;
      }
      return fallbackTitle || "Opening idea";
    };

    return {
      fen: pos.fen,
      objective: normalizeObjective(pos.objective),
      hints: normalizeHints(pos.hints),
      candidates: pos.candidates || [],
      side: pos.side || "white",
      difficulty: pos.difficulty || "intermediate",
      themes: pos.themes || ["opening"],
      id: `opening-${idx}`,
      topic_name: normalizeTopic(),
    };
  };

  // Listen for opening lesson events
  useEffect(() => {
    if (typeof window === "undefined") return;

    const handleOpeningLesson = (event: CustomEvent<OpeningLessonResponse>) => {
      const payload = event.detail;
      if (!payload || !payload.lesson) {
        addSystemMessage("Opening lesson payload missing.");
        return;
      }

      presentOpeningLessonSections(payload, { announce: false });

      const treeOrientation = payload.metadata?.orientation === "black" ? "black" : "white";
      if (payload.lesson_tree && payload.lesson_tree.length) {
        console.log(
          "[LESSON DEBUG] Lesson tree detected but tree playback disabled for opening lessons.",
          { nodes: payload.lesson_tree.length, treeOrientation }
        );
      }

      let rawPositions: OpeningPracticePosition[] =
        payload.practice_positions && payload.practice_positions.length
          ? payload.practice_positions
          : payload.positions && payload.positions.length
            ? payload.positions
            : [];

      if ((!rawPositions || rawPositions.length === 0) && payload.lesson_tree?.length) {
        rawPositions = (payload.lesson_tree as any[])
          .map((node: any, idx: number) => {
            if (!node?.fen) return null;
            const sideFromFen = typeof node.fen === "string" && node.fen.includes(" b ") ? "black" : "white";
            const hints: string[] = [];
            if (node.main_move?.san) {
              hints.push(`Main line: ${node.main_move.san}`);
            }
            if (Array.isArray(node.alternate_moves)) {
              node.alternate_moves.slice(0, 2).forEach((alt: any, altIdx: number) => {
                if (alt?.san) hints.push(`Alternate ${altIdx + 1}: ${alt.san}`);
              });
            }
            return {
              fen: node.fen,
              objective:
                node.objective ||
                node.prompt ||
                node.metadata?.objective ||
                `Play the plan for checkpoint ${idx + 1}`,
              hints,
              candidates: [node.main_move?.san].filter(Boolean),
              side: node.side || sideFromFen,
              difficulty: node.difficulty || "intermediate",
              themes: node.tags?.themes || node.themes || ["opening"],
            } as OpeningPracticePosition;
          })
          .filter(Boolean) as OpeningPracticePosition[];
      }

      if (!rawPositions.length) {
        addSystemMessage("No practice positions returned for the opening lesson.");
        return;
      }

      const practicePositions = rawPositions.map((pos, idx) =>
        normalizePracticePosition(pos, idx, payload.lesson.title)
      );

      setCurrentLesson({
        plan: payload.lesson,
        positions: practicePositions,
        currentIndex: 0,
        type: "opening",
        sections: payload.lesson.sections,
      });

      setLessonProgress({ current: 0, total: practicePositions.length || 1 });
      enterLessonMode();

      const primaryPosition = practicePositions[0] || null;
      if (primaryPosition) {
        setCurrentLessonPosition(primaryPosition);
        setBoardOrientation(primaryPosition.side === "black" ? "black" : "white");
        try {
          const lessonStartGame = new Chess(primaryPosition.fen);
          setGame(lessonStartGame);
          setFen(lessonStartGame.fen());
          const freshTree = new MoveTree();
          freshTree.root.fen = lessonStartGame.fen();
          freshTree.currentNode = freshTree.root;
          setMoveTree(freshTree);
          setPgn("");
          setTreeVersion((v) => v + 1);
          setMainLineFen(primaryPosition.fen);
          setLessonMoveIndex(0);
          setIsOffMainLine(false);
        } catch (err) {
          console.error("[OPENING] Failed to set initial lesson position:", err);
        }
        const cueSnapshot = buildLessonCueSnapshot(primaryPosition);
        setLessonCueSnapshot(cueSnapshot);
        setLessonArrows(cueSnapshot?.arrows || []);
        setLessonCueButtonActive(false);
      } else {
        setCurrentLessonPosition(null);
        setBoardOrientation(treeOrientation);
        setLessonCueSnapshot(null);
        setLessonArrows([]);
        setLessonCueButtonActive(false);
      }

      const lessonLabel = payload.lesson.title?.replace(/\s+-\s+Opening Lesson$/i, "") || payload.lesson.title;
      addAssistantMessage(
        `Let's explore **${payload.lesson.title}** right from this board. Play your moves and I'll immediately reply with ${lessonLabel || "fresh"} theory cues, alternates, and quick master references.`
      );
    };

    window.addEventListener("startOpeningLesson", handleOpeningLesson as any);
    return () => {
      window.removeEventListener("startOpeningLesson", handleOpeningLesson as any);
    };
  }, [
    addSystemMessage,
    addAssistantMessage,
    setCurrentLesson,
    setLessonProgress,
    presentOpeningLessonSections,
    normalizePracticePosition,
    enterLessonMode,
    setBoardOrientation,
  ]);

  useEffect(() => {
    if (!fen || fen === INITIAL_FEN) return;
    if (!pgn || pgn.trim().length < 4) return;
    if (!aiGameActive && mode !== "PLAY") return;
    let cancelled = false;

    (async () => {
      try {
        const lookup = await openingLookup(fen);
        if (cancelled || !lookup?.name) return;
        const perspective = boardOrientation === "black" ? "Black" : "White";
        const key = `${lookup.name}-${perspective}`;
        if (openingAnnouncementRef.current.has(key)) return;
        openingAnnouncementRef.current.add(key);
        const plan = getOpeningPlanHint(lookup.name, perspective as "White" | "Black");
        const keyMoves = (lookup.book_moves || []).slice(0, 4).join(", ");
        const message = `**${lookup.name}** detected (${perspective}). ${plan}${
          keyMoves ? `\nKey moves so far: ${keyMoves}.` : ""
        }`;
        const filteredMessage = stripEmojis(message);
        setMessages((prev) => [...prev, { role: "system", content: filteredMessage, fen }]);
      } catch (err) {
        console.warn("Opening highlight failed:", err);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [aiGameActive, mode, fen, pgn, boardOrientation, setMessages]);

  // Dev Tools: expose quick graph rendering in chat
  useEffect(() => {
    if (typeof window === 'undefined') return;
    try {
      const params = new URLSearchParams(window.location.search);
      const shouldShow = params.get('dev') === '1' || localStorage.getItem('cg_devtools') === '1';
      setShowDevTools(!!shouldShow);
      (window as any).CG_renderGraph = (customFen?: string, opts?: { orientation?: 'white' | 'black' }) => {
        const f = customFen || fen;
        const o = (opts?.orientation as any) || boardOrientation;
        setMessages((prev) => [
          ...prev,
          {
            role: 'graph',
            content: '',
            meta: { miniBoard: { id: `dbg-${Date.now()}`, fen: f, pgn, orientation: o } },
          },
        ]);
      };
      (window as any).CG_toggleDev = (on?: boolean) => {
        const val = on === undefined ? !shouldShow : on;
        localStorage.setItem('cg_devtools', val ? '1' : '0');
        setShowDevTools(val);
      };
    } catch {}
  }, [fen, pgn, boardOrientation]);

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

  function handleImageSelected(file: File) {
    const reader = new FileReader();
    reader.onload = (event) => {
      const result = event.target?.result as string;
      // Store image as pending - will be attached to next message
      setPendingImage({
        data: result,
        filename: file.name,
        mimeType: file.type,
      });
      // Add image preview to chat immediately with uploading state
      const imageMessage: ChatMessage = {
        role: 'user',
        content: '',
        image: {
          data: result,
          filename: file.name,
          mimeType: file.type,
          uploading: true,
          uploadProgress: 0,
        },
        fen,
        tabId: activeTabId,
      };
      setMessages((prev) => [...prev, imageMessage]);
      // Update tab messages
      setTabs(prevTabs => prevTabs.map(tab => {
        if (tab.id === activeTabId) {
          return { ...tab, messages: [...(tab.messages || []), imageMessage] };
        }
        return tab;
      }));
      // Simulate upload progress (in real app, this would be actual upload)
      let progress = 0;
      const progressInterval = setInterval(() => {
        progress += 10;
        if (progress >= 100) {
          clearInterval(progressInterval);
          // Mark upload as complete
          setMessages((prev) => prev.map((msg, idx) => {
            if (idx === prev.length - 1 && msg.image?.uploading) {
              return {
                ...msg,
                image: {
                  ...msg.image,
                  uploading: false,
                  uploadProgress: 100,
                },
              };
            }
            return msg;
          }));
          // Update tab messages
          setTabs(prevTabs => prevTabs.map(tab => {
            if (tab.id === activeTabId) {
              return {
                ...tab,
                messages: (tab.messages || []).map((msg, idx) => {
                  const tabMessages = tab.messages || [];
                  if (idx === tabMessages.length - 1 && msg.image?.uploading) {
                    return {
                      ...msg,
                      image: {
                        ...msg.image,
                        uploading: false,
                        uploadProgress: 100,
                      },
                    };
                  }
                  return msg;
                }),
              };
            }
            return tab;
          }));
        } else {
          // Update progress
          setMessages((prev) => prev.map((msg, idx) => {
            if (idx === prev.length - 1 && msg.image?.uploading) {
              return {
                ...msg,
                image: {
                  ...msg.image,
                  uploadProgress: progress,
                },
              };
            }
            return msg;
          }));
        }
      }, 200);
    };
    reader.readAsDataURL(file);
  }

  function addUserMessage(content: string, image?: { data: string; filename?: string; mimeType?: string; uploading?: boolean; uploadProgress?: number }) {
    // Check for duplicates - don't add if the last message is identical (unless it has an image)
    setMessages((prev) => {
      const lastMessage = prev[prev.length - 1];
      if (lastMessage?.role === "user" && lastMessage?.content === content && lastMessage?.tabId === activeTabId && !image && !lastMessage.image) {
        console.log('⚠️ Duplicate user message detected, skipping:', content);
        return prev;
      }
      const newMessage: ChatMessage = { 
        role: "user" as const, 
        content, 
        fen, 
        tabId: activeTabId,
        ...(image && { image }),
      };
      return [...prev, newMessage];
    });
    
    // Also update the active tab's messages (with deduplication)
    setTabs(prevTabs => prevTabs.map(tab => {
      if (tab.id === activeTabId) {
        const tabMessages = tab.messages || [];
        const lastTabMessage = tabMessages[tabMessages.length - 1];
        // Skip if duplicate (unless it has an image)
        if (lastTabMessage?.role === "user" && lastTabMessage?.content === content && !image && !lastTabMessage.image) {
          return tab;
        }
        const newMessage: ChatMessage = { 
          role: "user" as const, 
          content, 
          fen, 
          tabId: activeTabId,
          ...(image && { image }),
        };
        return { ...tab, messages: [...tabMessages, newMessage] };
      }
      return tab;
    }));
  }

  function addAssistantMessage(content: string, meta?: any, graphData?: any) {
    // Strip all emoji from content (monochrome UI requirement)
    const filteredContent = stripEmojis(content);
    // Check if we have buttons - if so, allow empty content
    const hasButtons = Array.isArray(meta?.buttons) && meta.buttons.length > 0;
    // Don't add empty messages unless we have buttons or graphData
    if ((!filteredContent || !filteredContent.trim()) && !hasButtons && !graphData) return;
    
    // Ensure meta always includes cached analysis for raw data button
    const enrichedMeta = {
      ...meta,
      rawEngineData: meta?.rawEngineData || 
                     meta?.tool_raw_data?.endpoint_response ||
                     analysisCache[fen]
    };
    
    // Handle buttons if provided in meta
    const buttons = meta?.buttons;
    let buttonMessages: any[] = [];
    if (Array.isArray(buttons) && buttons.length > 0) {
      buttonMessages = buttons.map((btn: any) => ({
        role: 'button' as const,
        content: btn.label || btn.action,
        buttonAction: btn.action,
        buttonLabel: btn.label,
        meta: { ...btn.data, buttonId: `btn-${Date.now()}-${Math.random()}` }
      }));
    }
    
    // Include tabId for context scoping, and graphData if provided
    const assistantMessage = { 
      role: "assistant" as const, 
      content: filteredContent, 
      meta: enrichedMeta, 
      fen, 
      tabId: activeTabId,
      ...(graphData && { graphData })
    };
    setMessages((prev) => {
      const newMessages = [...prev, assistantMessage];
      // Add button messages after the assistant message
      if (buttonMessages.length > 0) {
        newMessages.push(...buttonMessages);
      }
      return newMessages;
    });
    
    // Also update the active tab's messages
    const tabMessages = [...(activeTab?.messages || []), assistantMessage, ...buttonMessages];
    updateActiveTab({ messages: tabMessages });
    
    // Mark tab as having unread if not the active tab (shouldn't happen, but defensive)
    if (activeTabId !== activeTab?.id) {
      setTabHasUnread(activeTabId, true);
    }
    
    // Auto-apply annotations for all responses
    setTimeout(() => {
      // PRIORITY 1: Use backend-generated annotations if available
      const backendAnnotations = meta?.backendAnnotations;
      if (backendAnnotations) {
        // Check if we have direct arrows/highlights
        if (backendAnnotations.arrows?.length || backendAnnotations.highlights?.length) {
          console.log('📍 Using backend annotations (direct):', backendAnnotations);
          setAnnotations(prev => ({
            ...prev,
            arrows: backendAnnotations.arrows || [],
            highlights: backendAnnotations.highlights || []
          }));
          if (backendAnnotations.arrows?.length || backendAnnotations.highlights?.length) {
            addSystemMessage(`📍 Visual annotations applied: ${backendAnnotations.arrows?.length || 0} arrows, ${backendAnnotations.highlights?.length || 0} highlights`);
          }
          return;
        }
        
        // Check if we have themes/tactics data to generate annotations from
        const themes = backendAnnotations.themes || backendAnnotations.themes_identified || [];
        const tags = backendAnnotations.tags || [];
        const twoMoveTactics = backendAnnotations.two_move_tactics;
        
        if (themes.length > 0 || tags.length > 0 || twoMoveTactics) {
          console.log('🎨 Generating annotations from backend investigation data:', {
            themes: themes.slice(0, 5),
            tags: tags.length,
            twoMoveTactics: !!twoMoveTactics
          });
          
          try {
            const { generateThemeAnnotations } = require('@/lib/themeAnnotations');
            const sideToMove = fen.includes(' w ') ? 'white' : 'black';
            const engineData = enrichedMeta.rawEngineData || {};
            
            // Normalize tags structure if needed (backend uses "tag" field, frontend expects "tag_name")
            const normalizedTags = tags.map((tag: any) => {
              if (tag && typeof tag === 'object' && tag.tag && !tag.tag_name) {
                return {
                  ...tag,
                  tag_name: tag.tag,
                  name: tag.tag
                };
              }
              return tag;
            });
            
            // Generate annotations from themes and tags
            const themeAnnotations = generateThemeAnnotations(themes, normalizedTags, engineData, fen, sideToMove);
            
            // Add tactical annotations if two_move_tactics available
            if (twoMoveTactics && twoMoveTactics.open_tactics) {
              const tactics = twoMoveTactics.open_tactics;
              console.log('   🎯 Found tactical opportunities:', tactics.length);
              // TODO: Add tactical arrow/highlight annotations based on tactics
            }
            
            console.log('📍 Generated annotations from backend data:', {
              arrows: themeAnnotations.arrows.length,
              highlights: themeAnnotations.highlights.length
            });
            
            setAnnotations(prev => ({
              ...prev,
              arrows: themeAnnotations.arrows || [],
              highlights: themeAnnotations.highlights || []
            }));
            
            if (themeAnnotations.arrows?.length || themeAnnotations.highlights?.length) {
              addSystemMessage(`📍 Visual annotations generated: ${themeAnnotations.arrows?.length || 0} arrows, ${themeAnnotations.highlights?.length || 0} highlights`);
            }
            return;
          } catch (e) {
            console.warn('   ⚠️ Failed to generate annotations from backend data:', e);
          }
        }
      }
      
      // PRIORITY 2: Fallback to frontend parsing
      const engineData = enrichedMeta.rawEngineData;
      if (engineData && filteredContent) {
        applyLLMAnnotations(filteredContent, engineData);
      }
    }, 500); // Small delay to let message render first
  }

  function addSystemMessage(content: string) {
    // Strip emoji from system messages too
    const filteredContent = stripEmojis(content);
    setMessages((prev) => [...prev, { role: "system", content: filteredContent, fen, tabId: activeTabId }]);
  }

  function handleAddBoard() {
    if (!fen) {
      console.warn('Cannot add board: no FEN available');
      return;
    }
    
    // Find existing board message and replace with system notification
    setMessages((prev) => {
      const hasExistingBoard = prev.some(msg => msg.role === 'board');
      const boardMessage = { role: "board" as const, content: "", fen, tabId: activeTabId, meta: { pgn } };
      
      if (hasExistingBoard) {
        // Replace existing board messages with system notification
        const newMessages = prev.map(msg => {
          if (msg.role === 'board') {
            return { role: "system" as const, content: "Board closed", fen, tabId: activeTabId };
          }
          return msg;
        });
        // Add new board message at the end
        console.log('Replacing existing board, adding new board message:', boardMessage);
        return [...newMessages, boardMessage];
      } else {
        // Just add board message
        console.log('Adding first board message:', boardMessage);
        return [...prev, boardMessage];
      }
    });
    
    // Also update the active tab's messages
    const activeTab = tabs.find(t => t.id === activeTabId);
    if (activeTab) {
      const tabMessages = activeTab.messages || [];
      const hasExistingBoard = tabMessages.some(msg => msg.role === 'board');
      const boardMessage = { role: "board" as const, content: "", fen, tabId: activeTabId, meta: { pgn } };
      
      if (hasExistingBoard) {
        const newTabMessages = tabMessages.map(msg => {
          if (msg.role === 'board') {
            return { role: "system" as const, content: "Board closed", fen, tabId: activeTabId };
          }
          return msg;
        });
        updateActiveTab({ messages: [...newTabMessages, boardMessage] });
      } else {
        updateActiveTab({ messages: [...tabMessages, boardMessage] });
      }
    }
  }

  function addAutomatedMessage(content: string) {
    // Add automated assistant message with "Chesster Automated" as sender
    // Ensure proper line breaks (double newlines for paragraph breaks)
    const formattedContent = content.replace(/\n\n+/g, '\n\n').trim();
    const filteredContent = stripEmojis(formattedContent);
    setMessages((prev) => [
      ...prev,
      {
        role: "system",
        content: filteredContent,
        fen,
        tabId: activeTabId,
        meta: { automated: true },
      },
    ]);
  }

  const DEFAULT_LOADING_LABELS: Record<string, string> = {
    stockfish: 'Analyzing position…',
    llm: 'Thinking through the response…',
    game_review: 'Compiling the review…',
    training: 'Preparing a drill…',
    general: 'Working on it…',
  };

  function addLoadingMessage(type: 'stockfish' | 'llm' | 'game_review' | 'training' | 'general', customMessage?: string): string {
    const id = `loading-${Date.now()}`;
    const message = customMessage || DEFAULT_LOADING_LABELS[type] || 'Working…';
    setActiveLoaders(prev => [...prev, { id, type, message }]);
    return id;
  }

  function removeLoadingMessage(id: string | null) {
    if (!id) return;
    setActiveLoaders(prev => prev.filter(loader => loader.id !== id));
  }

  function handleApplyPGNSequence(fenAtEnd: string, pgnSequence: string) {
    try {
      const chess = new Chess();
      // Parse the PGN sequence
      const movePattern = /\d+\.\s*(?:\.\.\.?\s*)?([a-zA-Z][a-zA-Z0-9\-+=x#]+)(?:\s+([a-zA-Z][a-zA-Z0-9\-+=x#]+))?/g;
      const matches = pgnSequence.matchAll(movePattern);
      
      for (const match of matches) {
        if (match[1]) chess.move(match[1]); // White move
        if (match[2]) chess.move(match[2]); // Black move
      }
      
      setFen(chess.fen());
      setPgn(chess.pgn());
      setGame(chess);
      setAiGameActive(false); // End AI game session when loading new position
      addSystemMessage(`Applied sequence: ${pgnSequence}`);
    } catch (e) {
      console.error('Failed to apply PGN sequence:', e);
    }
  }

  const [previewFEN, setPreviewFEN] = useState<string | null>(null);

  function handlePreviewFEN(fenToPreview: string | null) {
    setPreviewFEN(fenToPreview);
    // Board will show preview FEN on hover, return to current FEN when hover ends
  }

  const handleLoadedGame = (payload: LoadedGamePayload) => {
    if (!payload) {
      addSystemMessage("No game data provided.");
      return;
    }

    const { fen: payloadFen, pgn: payloadPgn, orientation, source, whitePlayer, blackPlayer } = payload;
    console.log('[handleLoadedGame] Incoming payload', {
      source,
      hasFen: Boolean(payloadFen),
      pgnLength: payloadPgn?.length || 0,
      whitePlayer,
      blackPlayer,
    });

    try {
      let updatedGame: Chess;
      let resultingFen: string;
      let nextTree: MoveTree | null = null;
      const normalizedPgn = payloadPgn?.trim() ?? "";

      if (normalizedPgn) {
        console.log('[handleLoadedGame] Rebuilding from PGN...');
        const { tree, finalGame, finalFen } = rebuildMoveTreeFromPGN(normalizedPgn);
        updatedGame = finalGame;
        resultingFen = finalFen;
        nextTree = tree;
        console.log('[handleLoadedGame] PGN rebuild complete', {
          finalFen,
          moveCount: finalGame.history().length,
        });
      } else if (payloadFen) {
        updatedGame = new Chess(payloadFen);
        resultingFen = updatedGame.fen();
        const emptyTree = new MoveTree();
        emptyTree.root.fen = resultingFen;
        emptyTree.currentNode = emptyTree.root;
        nextTree = emptyTree;
      } else {
        throw new Error("Missing FEN data");
      }

      setGame(updatedGame);
      setFen(resultingFen);
      setPgn(normalizedPgn);
      if (nextTree) {
        console.log('[handleLoadedGame] Updating move tree', {
          totalMoves: nextTree.getMainLine().length,
        });
        setMoveTree(nextTree);
      }
      setPreviewFEN(null);
      if (orientation) {
        setBoardOrientation(orientation);
      }
      if (!boardDockOpen) {
        setBoardDockOpen(true);
      }

      const sourceLabel =
        source === "lookup" ? "lookup" :
        source === "pgn" ? "PGN" :
        source === "fen" ? "FEN" :
        source;
      const matchup =
        whitePlayer && blackPlayer ? ` (${whitePlayer} vs ${blackPlayer})` : "";

      addSystemMessage(`Game loaded${sourceLabel ? ` from ${sourceLabel}` : ""}${matchup}.`);
      setShowLoadGame(false);
    } catch (error) {
      console.error("Failed to load the supplied game:", error);
      addSystemMessage("Unable to load that game. Please double-check the PGN or FEN.");
    }
  };
  
  // Handle first message send - triggers layout transition
  function handleFirstSend(message: string) {
    setIsFirstMessage(false);
    handleSendMessage(message);
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
    // Route ALL chat messages to the LLM interpreter
    // The LLM interpreter handles all intent detection intelligently
    // No more pattern matching - let the AI decide
    return msg.trim().length > 0;
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

  // Intent Detection with Confidence Scoring
  interface IntentDetection {
    intent: string;
    confidence: number;
    keywords: string[];
    contextRequirements?: string[];
    description: string;
  }

  function detectIntentWithConfidence(message: string, context: {
    aiGameActive: boolean;
    mode: Mode;
    walkthroughActive: boolean;
    fen: string;
    pgn: string;
  }): IntentDetection[] {
    const lower = message.toLowerCase().trim();
    const intents: IntentDetection[] = [];
    let openingIntentDetected = false;

    // 1. End Game Intent (works in all modes, but higher confidence if game active)
    const resignationKeywords = ['resign', 'i resign', 'i give up', 'give up'];
    const endGameKeywords = ['end game', 'end the game', 'end this game', 'stop game', 'quit game', 'finish game', 'game ended', 'game over'];
    const hasEnd = lower.includes('end') && (lower.includes('game') || lower.includes('this'));
    const hasResign = resignationKeywords.some(k => lower.includes(k));
    const hasEndGame = endGameKeywords.some(k => lower.includes(k)) || hasEnd;
    
    if (hasResign || hasEndGame) {
      let confidence = 0.5; // Base confidence for all modes
      if (context.aiGameActive || context.mode === "PLAY") confidence += 0.3;
      if (hasResign) confidence += 0.1;
      intents.push({
        intent: hasResign ? 'resign' : 'endGame',
        confidence: Math.min(confidence, 1.0),
        keywords: hasResign ? resignationKeywords : endGameKeywords,
        description: hasResign ? 'Resign from the game' : 'End the current game'
      });
    }

    // 2. End Walkthrough Intent
    if (lower.includes('end') && (lower.includes('walkthrough') || lower.includes('lesson'))) {
      let confidence = 0.5;
      if (context.walkthroughActive) confidence += 0.4;
      intents.push({
        intent: 'endWalkthrough',
        confidence: Math.min(confidence, 1.0),
        keywords: ['end walkthrough', 'end lesson', 'stop walkthrough'],
        description: 'End the current walkthrough'
      });
    }

    // 3. Analyze Position Intent
    const analyzeKeywords = ['analyze', 'analyse', 'analysis', 'evaluate', 'assess', 'what should', 'best move', 'candidates'];
    const hasAnalyze = analyzeKeywords.some(k => lower.includes(k));
    if (hasAnalyze) {
      let confidence = 0.5;
      if (context.mode === "ANALYZE") confidence += 0.2;
      if (lower.includes('position') || lower.includes('this')) confidence += 0.2;
      intents.push({
        intent: 'analyzePosition',
        confidence: Math.min(confidence, 1.0),
        keywords: analyzeKeywords,
        description: 'Analyze the current position'
      });
    }

    // 4. Play Game Intent
    const playKeywords = ['play', 'game', 'let\'s play', 'play me', 'play a game', 'play against'];
    const hasPlay = playKeywords.some(k => lower.includes(k));
    const lessonLanguagePresent = lower.includes('teach') || lower.includes('lesson') || lower.includes('learn');
    if (hasPlay && !context.aiGameActive && !openingIntentDetected && !lessonLanguagePresent) {
      let confidence = 0.6;
      if (lower.includes('play') && lower.includes('game')) confidence += 0.2;
      intents.push({
        intent: 'startGame',
        confidence: Math.min(confidence, 1.0),
        keywords: playKeywords,
        description: 'Start a new game'
      });
    }

    // 5. Tactics Intent
    const tacticsKeywords = ['tactic', 'tactics', 'puzzle', 'training', 'exercise'];
    const hasTactics = tacticsKeywords.some(k => lower.includes(k));
    if (hasTactics) {
      intents.push({
        intent: 'tactics',
        confidence: 0.7,
        keywords: tacticsKeywords,
        description: 'Start a tactics puzzle'
      });
    }

    // 6. General Chat Intent
    const chatKeywords = ['hi', 'hello', 'hey', 'thanks', 'thank you', 'how are you'];
    const hasChat = chatKeywords.some(k => lower === k || lower.includes(k));
    if (hasChat) {
      intents.push({
        intent: 'generalChat',
        confidence: 0.8,
        keywords: chatKeywords,
        description: 'General conversation'
      });
    }

    // 7. Move Analysis Intent
    const moveAnalysisKeywords = ['rate', 'evaluate', 'how good', 'what about', 'analyze move'];
    const hasMoveAnalysis = moveAnalysisKeywords.some(k => lower.includes(k));
    if (hasMoveAnalysis) {
      let confidence = 0.5;
      // Check if message contains a move notation
      const movePattern = /\b([KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]?|O-O(?:-O)?)\b/gi;
      if (movePattern.test(message)) confidence += 0.3;
      intents.push({
        intent: 'analyzeMove',
        confidence: Math.min(confidence, 1.0),
        keywords: moveAnalysisKeywords,
        description: 'Analyze a specific move'
      });
    }

    // 8. Reset Board Intent
    if (lower.includes('reset') && (lower.includes('board') || lower.includes('position'))) {
      intents.push({
        intent: 'resetBoard',
        confidence: 0.8,
        keywords: ['reset board', 'reset position'],
        description: 'Reset the board to starting position'
      });
    }

    // 9. Switch to Analyze Mode Intent
    const analyzeModeKeywords = ['analyze mode', 'switch to analyze', 'go to analyze', 'enter analyze'];
    const hasAnalyzeMode = analyzeModeKeywords.some(k => lower.includes(k));
    if (hasAnalyzeMode || (lower.includes('analyze') && (lower.includes('mode') || lower.includes('switch')))) {
      intents.push({
        intent: 'switchToAnalyze',
        confidence: 0.7,
        keywords: analyzeModeKeywords,
        description: 'Switch to analyze mode'
      });
    }

    // 10. Switch to Discuss Mode Intent
    const discussModeKeywords = ['discuss mode', 'switch to discuss', 'go to discuss', 'enter discuss', 'chat mode'];
    const hasDiscussMode = discussModeKeywords.some(k => lower.includes(k));
    if (hasDiscussMode || (lower.includes('discuss') && lower.includes('mode'))) {
      intents.push({
        intent: 'switchToDiscuss',
        confidence: 0.7,
        keywords: discussModeKeywords,
        description: 'Switch to discuss mode'
      });
    }

    // 11. Switch to Tactics Mode Intent
    const tacticsModeKeywords = ['tactics mode', 'switch to tactics', 'go to tactics', 'enter tactics', 'puzzle mode'];
    const hasTacticsMode = tacticsModeKeywords.some(k => lower.includes(k));
    if (hasTacticsMode || (lower.includes('tactics') && lower.includes('mode'))) {
      intents.push({
        intent: 'switchToTactics',
        confidence: 0.7,
        keywords: tacticsModeKeywords,
        description: 'Switch to tactics mode'
      });
    }

    // 12. Help Intent
    const helpKeywords = ['help', 'what can you do', 'how does this work', 'what are you', 'who are you', 'capabilities'];
    const hasHelp = helpKeywords.some(k => lower.includes(k));
    if (hasHelp) {
      let confidence = 0.7;
      if (lower === 'help' || lower === 'what can you do') confidence = 0.9;
      intents.push({
        intent: 'help',
        confidence: confidence,
        keywords: helpKeywords,
        description: 'Get help or information about capabilities'
      });
    }

    // 13. Describe Position Intent
    const describeKeywords = ['describe', 'explain', 'tell me about', 'what is', 'what\'s happening', 'what\'s going on'];
    const hasDescribe = describeKeywords.some(k => lower.includes(k));
    if (hasDescribe && (lower.includes('position') || lower.includes('this') || context.fen !== INITIAL_FEN)) {
      let confidence = 0.6;
      if (lower.includes('position') || lower.includes('this')) confidence += 0.2;
      intents.push({
        intent: 'describePosition',
        confidence: Math.min(confidence, 1.0),
        keywords: describeKeywords,
        description: 'Describe or explain the current position'
      });
    }

    // 14. Review Game Intent
    const reviewKeywords = ['review', 'review game', 'analyze game', 'game review', 'review this game'];
    const hasReview = reviewKeywords.some(k => lower.includes(k));
    if (hasReview && (lower.includes('game') || context.pgn.length > 0)) {
      let confidence = 0.6;
      if (lower.includes('game') && context.pgn.length > 0) confidence += 0.2;
      intents.push({
        intent: 'reviewGame',
        confidence: Math.min(confidence, 1.0),
        keywords: reviewKeywords,
        description: 'Review the current game'
      });
    }

    // 15. Start Lesson Intent
    const lessonKeywords = ['lesson', 'opening lesson', 'start lesson', 'create lesson', 'build lesson'];
    const hasLesson = lessonKeywords.some(k => lower.includes(k));
    if (hasLesson) {
      let confidence = 0.7;
      if (lower.includes('opening')) confidence += 0.1;
      intents.push({
        intent: 'startLesson',
        confidence: Math.min(confidence, 1.0),
        keywords: lessonKeywords,
        description: 'Start or create a lesson'
      });
    }

    const openingLessonKeywords = [
      'opening lesson',
      'teach me this opening',
      'learn this opening',
      'teach this opening',
      'teach me the',
      'teach the',
      'teach me',
      'teach em',
      'teach em the'
    ];
    const openingDescriptors = ['opening', 'game', 'defense', 'attack', 'gambit', 'variation', 'system'];
    const hasOpeningLesson =
      openingLessonKeywords.some(k => lower.includes(k)) ||
      (
        (lower.includes('teach') || lower.includes('lesson') || lower.includes('learn')) &&
        openingDescriptors.some(word => lower.includes(word))
      );
    if (hasOpeningLesson) {
      openingIntentDetected = true;
      intents.push({
        intent: 'openingLesson',
        confidence: 0.85,
        keywords: openingLessonKeywords,
        description: 'Generate an opening lesson'
      });
    }

    // 16. Show Candidates Intent
    const candidatesKeywords = ['candidates', 'candidate moves', 'what moves', 'options', 'possible moves', 'moves available'];
    const hasCandidates = candidatesKeywords.some(k => lower.includes(k));
    if (hasCandidates) {
      intents.push({
        intent: 'showCandidates',
        confidence: 0.7,
        keywords: candidatesKeywords,
        description: 'Show candidate moves for the current position'
      });
    }

    // 17. Show Evaluation Intent
    const evalKeywords = ['evaluation', 'eval', 'what is the eval', 'what\'s the eval', 'position eval', 'score'];
    const hasEval = evalKeywords.some(k => lower.includes(k));
    if (hasEval) {
      intents.push({
        intent: 'showEvaluation',
        confidence: 0.7,
        keywords: evalKeywords,
        description: 'Show the evaluation of the current position'
      });
    }

    // 18. Clear/Close Intent (general)
    const clearKeywords = ['clear', 'close', 'cancel', 'dismiss', 'remove'];
    const hasClear = clearKeywords.some(k => lower.includes(k));
    if (hasClear && !lower.includes('board') && !lower.includes('position')) {
      // Only if not reset board
      let confidence = 0.4;
      if (lower === 'clear' || lower === 'close' || lower === 'cancel') confidence = 0.6;
      intents.push({
        intent: 'clear',
        confidence: confidence,
        keywords: clearKeywords,
        description: 'Clear or close current activity'
      });
    }

    return intents.sort((a, b) => b.confidence - a.confidence);
  }

  function generateClarifyingQuestion(intents: IntentDetection[], context: {
    aiGameActive: boolean;
    walkthroughActive: boolean;
  }): string {
    const topIntents = intents.slice(0, 3);
    
    if (topIntents.length === 0) {
      return "I'm not sure what you'd like to do. Could you clarify?";
    }

    if (topIntents.length === 1) {
      return `Did you want to ${topIntents[0].description.toLowerCase()}?`;
    }

    // Generate numbered options with proper line breaks
    const options = topIntents.map((intent, idx) => 
      `${idx + 1}. ${intent.description}`
    ).join('\n\n');

    return `I'm not sure what you'd like to do. Did you want to:\n\n${options}\n\nPlease respond with the number or describe what you'd like.`;
  }

  function handleAmbiguousIntent(
    intents: IntentDetection[],
    message: string,
    context: {
      aiGameActive: boolean;
      mode: Mode;
      walkthroughActive: boolean;
      fen: string;
      pgn: string;
    }
  ): boolean {
    if (intents.length === 0) return false;

    const sorted = intents.sort((a, b) => b.confidence - a.confidence);
    const topIntent = sorted[0];
    const secondIntent = sorted[1];

    // If only one intent or gap is large enough, proceed
    if (sorted.length === 1 || (secondIntent && topIntent.confidence - secondIntent.confidence >= 0.2)) {
      return false; // Not ambiguous, proceed normally
    }

    // Ambiguous - ask for clarification
    const question = generateClarifyingQuestion(sorted, context);
    addAutomatedMessage(question);
    
    // Store pending confirmation
    setPendingConfirmation({
      action: 'clarify',
      intent: JSON.stringify(sorted.slice(0, 3))
    });

    return true; // Handled, don't proceed
  }

  interface IntentInterpretation {
    intent: string;
    rationale?: string;
    secondary?: IntentDetection[];
  }

  function interpretIntents(
    intents: IntentDetection[],
    message: string,
    context: {
      aiGameActive: boolean;
      mode: Mode;
      walkthroughActive: boolean;
    }
  ): IntentInterpretation | null {
    if (!intents.length) return null;
    const lower = message.toLowerCase();
    const lessonWords = /teach|learn|lesson|opening lesson/;
    const wantsLesson = lessonWords.test(lower);
    const openingIntent = intents.find((i) => i.intent === "openingLesson");
    if (openingIntent) {
      return {
        intent: "openingLesson",
        rationale: wantsLesson
          ? "Got it—since you asked to learn this opening, I’ll build an opening lesson instead of starting a game."
          : "Focusing on the opening lesson you requested.",
        secondary: intents.filter((i) => i.intent !== "openingLesson"),
      };
    }

    if (wantsLesson) {
      const lessonIntent = intents.find((i) => i.intent === "startLesson");
      if (lessonIntent) {
        return {
          intent: "startLesson",
          rationale: "You mentioned learning/lesson, so I’ll start a lesson rather than switching modes.",
          secondary: intents.filter((i) => i.intent !== "startLesson"),
        };
      }
    }

    return null;
  }

  function executeIntent(intent: string, message: string, context: {
    aiGameActive: boolean;
    mode: Mode;
    walkthroughActive: boolean;
  }): boolean {
    const lower = message.toLowerCase().trim();

    switch (intent) {
      case 'resign':
        // Check if game is active
        if (!context.aiGameActive && context.mode !== "PLAY") {
          addAutomatedMessage("There is no active game to resign from.");
          return true;
        }
        addAutomatedMessage("You resigned. Game ended.");
        setAiGameActive(false);
        setMode("DISCUSS");
        return true;

      case 'endGame':
        // Check if game is active
        if (!context.aiGameActive && context.mode !== "PLAY") {
          addAutomatedMessage("There is no active game to end.");
          return true;
        }
        // Multi-step confirmation for critical action
        if (!pendingConfirmation || pendingConfirmation.intent !== 'endGame') {
          addAutomatedMessage("Are you sure you want to end the current game?\n\nType 'yes' to confirm or 'no' to cancel.");
          setPendingConfirmation({ action: 'confirm', intent: 'endGame' });
          return true;
        }
        if (lower === 'yes' || lower === 'y') {
          addAutomatedMessage("Game ended.");
          setAiGameActive(false);
          setMode("DISCUSS");
          setPendingConfirmation(null);
          return true;
        } else if (lower === 'no' || lower === 'n') {
          addAutomatedMessage("Game continues.");
          setPendingConfirmation(null);
          return true;
        }
        return false;

      case 'endWalkthrough':
        if (!context.walkthroughActive) {
          addAutomatedMessage("There is no active walkthrough to end.");
          return true;
        }
        setWalkthroughActive(false);
        setWalkthroughData(null);
        setWalkthroughStep(0);
        addAutomatedMessage("Walkthrough ended. Feel free to ask any questions!");
        return true;

      case 'startGame':
        if (llmEnabled && !aiGameActive) {
          setAiGameActive(true);
          setMode("PLAY");
          addSystemMessage("AI Game Mode Activated! Make your moves on the board.");
          return true;
        }
        return false;

      case 'resetBoard':
        // Multi-step confirmation for critical action
        if (!pendingConfirmation || pendingConfirmation.intent !== 'resetBoard') {
          addAutomatedMessage("Are you sure you want to reset the board?\n\nType 'yes' to confirm or 'no' to cancel.");
          setPendingConfirmation({ action: 'confirm', intent: 'resetBoard' });
          return true;
        }
        if (lower === 'yes' || lower === 'y') {
          setGame(new Chess());
          setFen(INITIAL_FEN);
          setPgn("");
          setMoveTree(new MoveTree());
          setAiGameActive(false);
          addAutomatedMessage("Board reset to starting position.");
          setPendingConfirmation(null);
          return true;
        } else if (lower === 'no' || lower === 'n') {
          addAutomatedMessage("Reset cancelled.");
          setPendingConfirmation(null);
          return true;
        }
        return false;

      case 'switchToAnalyze':
        setMode("ANALYZE");
        addAutomatedMessage("Switched to Analyze mode.");
        return true;

      case 'switchToDiscuss':
        setMode("DISCUSS");
        addAutomatedMessage("Switched to Discuss mode.");
        return true;

      case 'switchToTactics':
        setMode("TACTICS");
        addAutomatedMessage("Switched to Tactics mode.");
        return true;

      case 'help':
        // Let normal LLM flow handle help requests
        return false;

      case 'describePosition':
        // Trigger position description via normal flow
        return false;

      case 'reviewGame':
        // Trigger game review via normal flow
        return false;

      case 'startLesson':
        // Trigger lesson creation via normal flow
        return false;
      case 'openingLesson':
        {
          const pendingQuery = pendingOpeningLessonQueryRef.current;
          pendingOpeningLessonQueryRef.current = undefined;
          handleGenerateOpeningLesson('intent', pendingQuery ?? message);
        }
        return true;

      case 'showCandidates':
        // Trigger candidate moves display via normal flow
        return false;

      case 'showEvaluation':
        // Trigger evaluation display via normal flow
        return false;

      case 'clear':
        // Generic clear - context dependent
        if (walkthroughActive) {
          setWalkthroughActive(false);
          setWalkthroughData(null);
          setWalkthroughStep(0);
          addAutomatedMessage("Cleared current activity.");
          return true;
        }
        // Otherwise let normal flow handle
        return false;

      case 'analyzePosition':
        // Trigger position analysis
        handleAnalyzePosition().catch(err => {
          addSystemMessage(`Analysis error: ${err.message}`);
        });
        return true;

      case 'tactics':
        // Trigger tactics puzzle
        handleNextTactic().catch(err => {
          addSystemMessage(`Tactics error: ${err.message}`);
        });
        return true;

      default:
        return false;
    }
  }

  async function handleGeneralChat(message: string) {
    const boardContext = getBoardContext();
    const isStartPosition = fen === INITIAL_FEN;
    const hasMoves = pgn.length > 0 && game.history().length > 0;
    const moveCount = game.history().length;

    if (!llmEnabled) {
      // Provide helpful suggestions without LLM
      let response = "Hello! I'm Chesster. ";
      
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
    
    // Send the raw user message - the backend interpreter handles classification
    // Context (FEN, PGN, etc.) is already sent via the context object in callLLMStream
    // DO NOT wrap the message with "User sent a general greeting/chat message" as this contaminates interpretation
    const userMessage = message;

    // Show loading indicator while LLM processes
    const loaderId = addLoadingMessage('llm', 'Understanding request...');
    setIsLLMProcessing(true);
    setLiveStatusMessages([]);  // Clear previous status
    activeStatusRunIdRef.current = null;
    
    try {
      // Build recent chat history for context (last 5 messages, keep errors)
      // This helps the interpreter understand "try again", follow-ups, etc.
      const validRoles = ['user', 'assistant', 'system'];  // OpenAI-supported roles
      const recentHistory = messages
        .filter(m => (m as any).tabId === activeTabId || !(m as any).tabId)  // Current tab or no tab
        .filter(m => validRoles.includes(m.role))  // Only include valid OpenAI roles
        .slice(-5)  // Last 5 messages
        .map(m => ({
          role: m.role === 'system' ? 'assistant' : m.role,  // Map system->assistant for LLM
          content: m.content.slice(0, 300)  // Cap at 300 chars to save tokens
        }));
      
      // Use streaming endpoint for real-time status updates
      // Send the raw user message - backend handles all classification and context
      const result = await callLLMStream(
        [
          { 
            role: "system", 
            content: "You are Chesster, a friendly chess assistant. You help users play, analyze, and learn chess. Be warm, encouraging, and concise." 
          },
          ...recentHistory,  // Include recent chat for context
          { role: "user", content: userMessage },  // Raw message, not wrapped
        ], 
        0.8,
        "gpt-4o-mini",
        true,
        // Real-time status callback with replace support + throttling
        (status) => {
          const now = Date.now();
          const timeSinceLastUpdate = now - lastStatusUpdateRef.current;
          
          // If update is faster than 200ms, mark as instant (no animation)
          // Only animate if >1 second since last update
          const shouldAnimate = timeSinceLastUpdate > 1000;
          
          setLiveStatusMessages(prev => {
            // Ignore late events from previous runs; lock to first seen run id.
            const runId = (status as any)?._runId as (string | undefined);
            if (runId) {
              if (!activeStatusRunIdRef.current) activeStatusRunIdRef.current = runId;
              if (activeStatusRunIdRef.current && runId !== activeStatusRunIdRef.current) return prev;
            }
            lastStatusUpdateRef.current = now;
            const enrichedStatus = { ...status, instant: !shouldAnimate };
            
            if (status.replace && prev.length > 0) {
              // Replace the last message instead of adding
              return [...prev.slice(0, -1), enrichedStatus];
            }
            return [...prev, enrichedStatus];
          });
        },
        abortController?.signal
      );
      
      // ===== HANDLE PERSONAL REVIEW (fetch_and_review_games) =====
      console.log('🔍 [Personal Review Check] Full result:', result);
      console.log('🔍 [Personal Review Check] result.tool_calls:', result.tool_calls);
      console.log('🔍 [Personal Review Check] result.tool_calls type:', typeof result.tool_calls);
      console.log('🔍 [Personal Review Check] result.tool_calls length:', result.tool_calls?.length);
      
      // Log each tool call structure
      if (result.tool_calls && Array.isArray(result.tool_calls)) {
        result.tool_calls.forEach((tc: any, idx: number) => {
          console.log(`🔍 [Personal Review Check] Tool call ${idx}:`, {
            tool: tc.tool,
            hasResult: !!tc.result,
            resultType: typeof tc.result,
            resultKeys: tc.result && typeof tc.result === 'object' ? Object.keys(tc.result) : [],
            fullToolCall: tc
          });
        });
      }
      
      const personalReviewTool = result.tool_calls?.find((tc: any) => tc.tool === 'fetch_and_review_games');
      const hasSelectGamesTool = Array.isArray(result.tool_calls) && result.tool_calls.some((tc: any) => tc?.tool === "select_games");
      // Check both detected_intent and orchestration mode for review detection
      const isGameReviewIntent = result.detected_intent === "game_review" || result.orchestration?.mode === "review";
      console.log('🔍 [Personal Review Check] personalReviewTool:', personalReviewTool);
      
      if (personalReviewTool) {
        console.log('🔍 [Personal Review Check] personalReviewTool keys:', Object.keys(personalReviewTool));
        console.log('🔍 [Personal Review Check] result object:', personalReviewTool.result);
        console.log('🔍 [Personal Review Check] result object type:', typeof personalReviewTool.result);
        
        // Check if result is truncated
        if (personalReviewTool.result?._truncated === true) {
          console.warn('⚠️ [Personal Review Check] Result is truncated! Size:', personalReviewTool.result._size);
          console.warn('⚠️ [Personal Review Check] This should have been merged with chunked data. Check chunked data merge logic.');
        }
        
        // Check if result is a string that needs parsing
        if (typeof personalReviewTool.result === 'string') {
          console.log('🔍 [Personal Review Check] Result is a string, attempting to parse...');
          try {
            const parsed = JSON.parse(personalReviewTool.result);
            console.log('🔍 [Personal Review Check] Parsed result:', parsed);
            console.log('🔍 [Personal Review Check] Parsed success:', parsed.success);
            console.log('🔍 [Personal Review Check] Parsed first_game:', parsed.first_game);
            console.log('🔍 [Personal Review Check] Parsed first_game_review:', parsed.first_game_review ? 'EXISTS' : 'NULL');
            // Update the tool call with parsed result
            personalReviewTool.result = parsed;
          } catch (e) {
            console.error('❌ [Personal Review Check] Failed to parse result string:', e);
          }
        }
        
        // Check if result exists and has expected structure
        if (personalReviewTool.result && typeof personalReviewTool.result === 'object') {
          console.log('🔍 [Personal Review Check] result keys:', Object.keys(personalReviewTool.result));
          console.log('🔍 [Personal Review Check] success:', personalReviewTool.result.success);
          console.log('🔍 [Personal Review Check] success type:', typeof personalReviewTool.result.success);
          console.log('🔍 [Personal Review Check] first_game:', personalReviewTool.result.first_game);
          console.log('🔍 [Personal Review Check] first_game type:', typeof personalReviewTool.result.first_game);
          console.log('🔍 [Personal Review Check] first_game_review:', personalReviewTool.result.first_game_review ? 'EXISTS' : 'NULL');
          console.log('🔍 [Personal Review Check] first_game_review type:', typeof personalReviewTool.result.first_game_review);
          
          // Also check nested structures
          if (personalReviewTool.result.first_game) {
            console.log('🔍 [Personal Review Check] first_game keys:', Object.keys(personalReviewTool.result.first_game));
            console.log('🔍 [Personal Review Check] first_game.pgn:', personalReviewTool.result.first_game.pgn);
          }
        } else {
          console.warn('⚠️ [Personal Review Check] No result object found or result is not an object');
        }
      } else {
        console.log('🔍 [Personal Review Check] No personalReviewTool found');
      }
      
      // Check for personal review result (allow for missing PGN gracefully)
      const hasPersonalReviewResult = personalReviewTool?.result?.success === true;
      const hasPgn = personalReviewTool?.result?.first_game?.pgn && personalReviewTool.result.first_game.pgn.length > 0;
      console.log('🔍 [Personal Review Check] hasPersonalReviewResult:', hasPersonalReviewResult, 'hasPgn:', hasPgn);
      
      // Check if we have review data - if so, show it regardless of intent detection
      const hasReviewData = hasPersonalReviewResult && 
                           (personalReviewTool?.result?.first_game_review || 
                            personalReviewTool?.result?.stats || 
                            personalReviewTool?.result?.charts);
      
      // Only auto-open review tabs when backend says we're actually doing a game review.
      // This prevents game LIST/SELECT requests from opening walkthrough tabs if the wrong tool was called.
      // Check orchestration mode as well as detected_intent
      const isReviewMode = isGameReviewIntent;
      
      if (hasReviewData && hasPgn && isReviewMode && !hasSelectGamesTool) {
        const reviewResult = personalReviewTool.result;
        console.log('🎯 [Personal Review] Loading game into tab');
        
        // Load game into new tab
        loadGameIntoTab({
          pgn: reviewResult.first_game.pgn,
          white: reviewResult.first_game.white,
          black: reviewResult.first_game.black,
          date: reviewResult.first_game.date,
          result: reviewResult.first_game.result,
          timeControl: reviewResult.first_game.time_control,
          opening: reviewResult.first_game.opening,
        }, { forceNewTab: true });
        
        // Trigger walkthrough if we have review data
        if (reviewResult.first_game_review?.ply_records) {
          console.log('🎬 [Personal Review] Triggering walkthrough');
          const plyRecords = reviewResult.first_game_review.ply_records;
          
          const transformedMoves = plyRecords.map((record: any, idx: number) => {
            const plyValue = typeof record.ply === 'number' ? record.ply : idx + 1;
            const engineInfo = record.engine || {};
            return {
              ...record,
              moveNumber: Math.floor(plyValue / 2) + 1,
              move: record.san || record.move || '',
              quality: record.category,
              color: record.side_moved === 'white' ? 'w' : 'b',
              evalBefore: engineInfo.eval_before_cp ?? 0,
              evalAfter: engineInfo.played_eval_after_cp ?? 0,
              cpLoss: record.cp_loss ?? 0,
              accuracy: record.accuracy_pct ?? 100,
              bestMove: engineInfo.best_move_san || '',
              fen: record.fen_after || '',
              fenBefore: record.fen_before || '',
            };
          });
          
          const whiteStats = reviewResult.first_game_review.stats?.white || {};
          const blackStats = reviewResult.first_game_review.stats?.black || {};
          
          // Keep the connected user's side at the bottom of the board.
          // Backend sets game_metadata.player_color to the connected account's color.
          const meta = (reviewResult.first_game_review.game_metadata || {}) as any;
          if (meta.player_color === 'black') setBoardOrientation('black');
          else if (meta.player_color === 'white') setBoardOrientation('white');

          const walkthroughData = {
            moves: transformedMoves,
            openingName: reviewResult.first_game.opening || '',
            avgWhiteAccuracy: whiteStats.overall_accuracy ?? 0,
            avgBlackAccuracy: blackStats.overall_accuracy ?? 0,
            gameTags: [],
            pgn: reviewResult.first_game.pgn,
            stats: reviewResult.first_game_review.stats,
            // Expose metadata at top-level for walkthrough (player/focus/review_subject)
            game_metadata: reviewResult.first_game_review.game_metadata || {},
            first_game_review: reviewResult.first_game_review,  // Include full review for walkthrough
            // NEW: Include LLM-selected key moments for query-aware walkthrough
            selectedKeyMoments: reviewResult.selected_key_moments || [],
            selectionRationale: reviewResult.selection_rationale || {},
            queryIntent: reviewResult.selection_rationale?.query_intent || 'general',
            // Batch pre-commentary generated on backend (ply -> text)
            preCommentaryByPly: reviewResult.pre_commentary_by_ply || {}
          };
          
          // Generate table data for button and narrative
          const tableData = generateReviewTableData(walkthroughData);
          
          // Show narrative with Review Table button (add it here where tableData is available)
          if (reviewResult.narrative) {
            addAssistantMessage(reviewResult.narrative, {
              gameReviewTable: tableData
            }, result.graphData);
          }
          
          // Automatically open PersonalReview component for profile reviews
          // Only open for multi-game reviews (profile reviews), not single game reviews
          const hasProfileData = reviewResult.stats || reviewResult.charts || reviewResult.phase_stats;
          const isMultiGameReview = (reviewResult.games_analyzed || 0) > 1;
          if (hasProfileData && isMultiGameReview) {
            console.log('🎯 [Personal Review] Opening PersonalReview component with profile data');
            setTimeout(() => {
              setShowPersonalReview(true);
            }, 500); // Small delay to let walkthrough initialize
          }
          
          setTimeout(() => {
            setWalkthroughData(walkthroughData);
            startWalkthroughWithData(walkthroughData);
          }, 500);
          
          // Add walkthrough button after narrative (if narrative exists)
          if (reviewResult.narrative) {
            // Button will be added after narrative message
            setTimeout(() => {
              setMessages(prev => [...prev, {
                role: 'button',
                content: '',
                buttonAction: 'START_WALKTHROUGH',
                buttonLabel: 'Start Guided Walkthrough',
                timestamp: new Date()
              }]);
            }, 100);
          }
        } else {
          // No walkthrough data, but still show narrative if available
          if (reviewResult.narrative) {
            addAssistantMessage(reviewResult.narrative, undefined, result.graphData);
          }
        }

        // Don't show result.content if we already showed the narrative (to avoid duplicates)
        // The narrative contains the same information as result.content
        if (!reviewResult.narrative && typeof result.content === "string" && result.content.trim()) {
          addAssistantMessage(result.content, undefined, result.graphData);
        } else if (!reviewResult.narrative) {
          addAssistantMessage("I fetched your game review data, but couldn't render the walkthrough. You can ask about specific moves or moments and I'll answer from the review.", undefined, result.graphData);
        }
        
        removeLoadingMessage(loaderId);
        setIsLLMProcessing(false);
        setLiveStatusMessages([]);
        return; // Exit early - don't show generic LLM response
      }
      // ===== END PERSONAL REVIEW HANDLING =====
      
      // ===== HANDLE FRONTEND COMMANDS =====
      if (result.frontend_commands && result.frontend_commands.length > 0) {
        for (const cmd of result.frontend_commands) {
          try {
            if (cmd.type === 'create_tab') {
              if (tabs.length < 5) {
                handleNewTab();
                console.log('✅ Created new tab via LLM command');
              } else {
                console.warn('⚠️ Cannot create tab: maximum tabs reached');
              }
            } else if (cmd.type === 'switch_tab') {
              const targetTabId = cmd.payload?.tab_id || cmd.payload?.tab_index !== undefined 
                ? tabs[cmd.payload.tab_index]?.id 
                : null;
              
              if (targetTabId && tabs.some(t => t.id === targetTabId)) {
                handleTabSelect(targetTabId);
                console.log(`✅ Switched to tab ${targetTabId} via LLM command`);
              } else if (cmd.payload?.tab_index !== undefined && tabs[cmd.payload.tab_index]) {
                handleTabSelect(tabs[cmd.payload.tab_index].id);
                console.log(`✅ Switched to tab at index ${cmd.payload.tab_index} via LLM command`);
              } else {
                console.warn('⚠️ Invalid tab ID or index for switch_tab command:', cmd.payload);
              }
            } else if (cmd.type === 'list_tabs') {
              // LLM can see tabs in context, but we can log for debugging
              console.log('📋 Tab list requested:', tabs.map(t => ({ id: t.id, name: t.name, pgn_length: t.pgn.length })));
            }
          } catch (err) {
            console.error('❌ Error executing frontend command:', cmd, err);
          }
        }
      }
      // ===== END FRONTEND COMMANDS =====
      
      const reply = result.content;
      
      // Store minimal meta for general chat with cached analysis
      const meta = {
        // NEW: Include final_pgn and show_board_link if available
        final_pgn: result.final_pgn,
        show_board_link: result.show_board_link,
        type: "general_chat",
        boardContext,
        fen,
        // Include buttons if present
        buttons: result.buttons,
        moveCount,
        rawEngineData: analysisCache[fen], // Include cached analysis for annotations
        backendAnnotations: result.annotations, // Backend-generated annotations
        // Chain-of-thought / status tracking
        statusMessages: result.status_messages || [],
        detectedIntent: result.detected_intent,
        toolsUsed: result.tools_used || [],
        orchestration: result.orchestration,
        narrativeDecision: result.narrative_decision
      };
      
      addAssistantMessage(reply, meta, result.graphData);
    } catch (err: any) {
      addSystemMessage(`Error: ${err.message}`);
    } finally {
      removeLoadingMessage(loaderId);
      setIsLLMProcessing(false);
      setLiveStatusMessages([]);
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
    console.log("🎙️ generatePlayModeCommentary called:", { userMove, userFenAfter });
    try {
      // Analyze position after user's move to get accurate eval and tags
      console.log("📊 Analyzing user position...");
      const userAnalysis = await analyzePosition(userFenAfter, 1, 12);
      console.log("✅ User analysis complete");
      
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
      console.log("📊 Analyzing engine position...");
      const engineAnalysis = await analyzePosition(engineResponse.new_fen, 3, 12);
      console.log("✅ Engine analysis complete");
      const engineCandidates = engineAnalysis.candidate_moves || [];
      const engineBestMove = engineCandidates[0];
      const engineThreats = engineAnalysis.threats || [];
      console.log("🎯 Engine best move:", engineBestMove?.move, "Threats:", engineThreats.length);
      
      // Extract relevant tags from both positions
      const userTags = userAnalysis.white_analysis?.chunk_1_immediate?.tags || userAnalysis.black_analysis?.chunk_1_immediate?.tags || [];
      const engineTags = engineAnalysis.white_analysis?.chunk_1_immediate?.tags || engineAnalysis.black_analysis?.chunk_1_immediate?.tags || [];
      
      // Format top 3-5 relevant tags for each position
      const userTagsStr = userTags.slice(0, 5).map((t: any) => t.name || t).join(', ');
      const engineTagsStr = engineTags.slice(0, 5).map((t: any) => t.name || t).join(', ');
      
      const prompt = `You're a chess coach commenting on moves.

USER MOVE: ${userMove}
QUALITY: ${moveQuality} (centipawn loss: ${evalChange})
EVAL: ${evalAfter}cp
POSITION TAGS AFTER USER MOVE: ${userTagsStr || 'none'}

ENGINE MOVE: ${engineResponse.engine_move_san}
ENGINE'S NEXT PLAN: ${engineBestMove ? engineBestMove.move : 'developing'}
ENGINE THREATS: ${engineThreats.length > 0 ? engineThreats[0].desc : 'none'}
POSITION TAGS AFTER ENGINE MOVE: ${engineTagsStr || 'none'}

Generate 2 sentences:
Sentence 1: Judge the user's move (${userMove}) - mention if it's ${moveQuality} and weave in relevant position tags naturally
Sentence 2: Explain your response (${engineResponse.engine_move_san}) - state its purpose and incorporate relevant tags

Use the position tags to add concrete details about piece activity, control, threats, or pawn structure.
Mention tags naturally as part of the explanation (e.g., "controlling the long diagonal" instead of just listing tag names).

IMPORTANT: Do NOT use quotation marks in your response. Write plain text only.

Examples:
- e4 is the best move, seizing central space and opening lines for your bishop. I responded with c5, challenging your center and preparing counterplay along the c-file.
- Nf3 is an excellent move that develops your knight while eyeing the central squares. I played Nc6 in response, developing my knight and supporting a future d5 break to contest the center.
- h4 is a mistake, weakening your kingside structure without creating real threats. I responded with d5, immediately seizing the center and exploiting your pawn's poor placement.
- Bc4 is a good move, putting pressure on f7 and developing with tempo. I played Nf6 to defend while also developing and preparing castling for king safety.`;

      console.log("🤖 Calling LLM for commentary...");
      const {content: commentary} = await callLLM([
        { role: "system", content: "You are a concise chess coach. Format: Sentence 1 judges user move. Sentence 2 explains engine's purpose. NEVER use quotation marks in your response." },
        { role: "user", content: prompt },
      ], 0.6);
      console.log("✅ LLM response received:", commentary);
      
      // Add meta with CP loss and best move for tooltip
      const commentaryMeta = {
        cpLoss: evalChange,
        bestMove: engineBestMove?.move || userMove,
        evalAfter: evalAfter,
        quality: moveQuality
      };
      
      console.log("💬 Adding assistant message with commentary");
      addAssistantMessage(commentary, commentaryMeta);
      console.log("✅ Assistant message added");
      
      // Check for advantage shifts
      await checkAdvantageShift(evalBefore, evalAfter, engineAnalysis, "engine", engineResponse.new_fen);
      
    } catch (err: any) {
      console.error('❌ Commentary generation error:', err);
      console.error('Error details:', err.message, err.stack);
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
        const mySide = whoHasAdvantage;
        reason = `${mySide}'s material advantage (up ${materialDiff} pawn${materialDiff > 1 ? 's' : ''})`;
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
                const mySide = whoHasAdvantage;
                reason = `${mySide}'s unstoppable threat: ${candidates[0].move} (threatens mate)`;
              } else if (hasFork && candidates.length >= 2) {
                // Compare first candidate vs second in original position
                const bestEval = candidates[0].eval_cp || 0;
                const secondEval = candidates[1].eval_cp || 0;
                const gap = Math.abs(bestEval - secondEval);
                
                if (gap >= 50) {
                  reasonType = "threat";
                  const mySide = whoHasAdvantage;
                  reason = `${mySide}'s current threat: ${candidates[0].move}`;
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
          const mySide = whoHasAdvantage;
          factors.push(`${mySide}'s active pieces (${myActive.slice(0, 2).join(", ")})`);
        }
        if (oppInactive.length >= 2) {
          const oppSide = whoHasAdvantage === "White" ? "Black" : "White";
          factors.push(`${oppSide}'s inactive ${oppInactive[0]}`);
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
          reason = `${factors.slice(0, 2).join(" and ")}`;
        } else {
          const mySide = whoHasAdvantage;
          reason = `${mySide}'s better position and control`;
        }
      }
      
      const advantageMessage = `${whoHasAdvantage} now has a ${afterLevel} advantage because of ${reason}`;
      
      // Use setTimeout to ensure this message appears after the move commentary
      setTimeout(() => {
        addSystemMessage(advantageMessage);
      }, 100);
    }
  }

  async function handleMove(from: string, to: string, promotion?: string) {
    console.log("🎯 handleMove called:", { from, to, promotion, mode, llmEnabled });
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
        // First, show the move on the board
        setGame(tempGame);
        setFen(tempGame.fen());
        
        const wasCorrect = await checkRetryMove(moveSan.san);
        if (wasCorrect) {
          // Correct move found - add to move tree
          const newTree = moveTree.clone();
          newTree.addMove(moveSan.san, tempGame.fen());
          setMoveTree(newTree);
          setPgn(newTree.toPGN());
        }
        // Wrong moves handled in checkRetryMove (board will be reset after delay)
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

      // Tree-first (DISCUSS/ANALYZE): extend backend D2/D16 tree from current node
      if (mode === "DISCUSS" || mode === "ANALYZE") {
        try {
          const tabId = activeTab?.id || activeTabId || sessionId;
          await ensureBackendTreeForTab(tabId, fenBeforeMove);
          const parentNodeId = backendTreeNodeByTabRef.current[tabId] || "root";
          const resp = await fetch(`${getBackendBase()}/board/tree/add_move`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              thread_id: tabId,
              parent_node_id: parentNodeId,
              move_san: moveSan.san,
            }),
          });
          if (resp.ok) {
            const data = await resp.json();
            if (data?.node_id) {
              backendTreeNodeByTabRef.current[tabId] = data.node_id;
            }
          }
        } catch (e) {
          console.warn("Backend tree add_move failed:", e);
        }
      }
      setPgn(newPgn);
      // Push a mini-board snapshot message into chat
      setMessages(prev => [...prev, {
        role: 'graph',
        content: '',
        meta: { miniBoard: { fen: newFen, pgn: newPgn, orientation: boardOrientation } }
      }]);

      if (lessonMode) {
        const moveCount = Math.ceil(tempGame.history().length / 2);
        const playedByWhite = moveSan.color === 'w';
        const userMoveLabel = playedByWhite ? `${moveCount}.${moveSan.san}` : `${moveCount}...${moveSan.san}`;
        addUserMessage(`I played ${userMoveLabel}`);
      }
      
      // Check if game is over after user's move
      if (tempGame.isCheckmate()) {
        const winner = tempGame.turn() === 'w' ? 'Black' : 'White';
        addSystemMessage(`Checkmate! ${winner} wins! Game ended.`);
        setAiGameActive(false);
        setMode("DISCUSS");
        return; // Don't continue with engine response
      } else if (tempGame.isStalemate()) {
        addSystemMessage(`Stalemate! The game is a draw. Game ended.`);
        setAiGameActive(false);
        setMode("DISCUSS");
        return; // Don't continue with engine response
      } else if (tempGame.isDraw()) {
        addSystemMessage(`Draw! The game ended in a draw. Game ended.`);
        setAiGameActive(false);
        setMode("DISCUSS");
        return; // Don't continue with engine response
      }

      // Auto-analyze (engine raw) only for PLAY/lesson loops.
      // For DISCUSS/ANALYZE, we prefetch baseline intuition instead (cheaper than redundant raw analysis).
      if (mode === "PLAY" || aiGameActive || lessonMode) {
      autoAnalyzePositionAndMove(newFen, moveSan.san, fenBeforeMove).catch(err => console.error('Auto-analysis failed:', err));
      } else {
        prefetchBaselineIntuition(newFen);
      }

      const shouldCallAi = llmEnabled && aiGameActive && !lessonMode;
      console.log("[LESSON DEBUG] handleMove state", {
        llmEnabled,
        aiGameActive,
        lessonMode,
        shouldCallAi,
        lessonNodeId,
        currentLessonPositionExists: Boolean(currentLessonPosition),
      });

      // If actively playing with AI (and not in lesson mode), announce move and get AI response
      if (shouldCallAi) {
        // Auto-switch to PLAY mode if not already there
        if (mode !== "PLAY") {
          setMode("PLAY");
          console.log("🎮 Auto-switched to PLAY mode");
        }
        
        // Get move number for display
        const moveNum = Math.floor(game.history().length / 2) + 1;
        const isWhiteMove = fen.split(' ')[1] === 'w';
        const userMoveMessage = isWhiteMove ? `I played ${moveNum}.${moveSan.san}` : `I played ${moveNum}...${moveSan.san}`;
        
        // Announce the user's move in chat
        console.log("💬 Sending user move message:", userMoveMessage);
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
            
            // Auto-analyze (engine raw) only for PLAY/lesson loops.
            // For DISCUSS/ANALYZE, we prefetch baseline intuition instead.
            if (mode === "PLAY" || aiGameActive || lessonMode) {
            autoAnalyzePositionAndMove(response.new_fen, response.engine_move_san, newFen).catch(err => console.error('Auto-analysis failed:', err));
            } else {
              prefetchBaselineIntuition(response.new_fen);
            }
            
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

            // Check if game is over after engine move
            if (gameAfterEngine.isCheckmate()) {
              const winner = gameAfterEngine.turn() === 'w' ? 'Black' : 'White';
              addSystemMessage(`Checkmate! ${winner} wins! Game ended.`);
              setAiGameActive(false);
              setMode("DISCUSS");
            } else if (gameAfterEngine.isStalemate()) {
              addSystemMessage(`Stalemate! The game is a draw. Game ended.`);
              setAiGameActive(false);
              setMode("DISCUSS");
            } else if (gameAfterEngine.isDraw()) {
              addSystemMessage(`Draw! The game ended in a draw. Game ended.`);
              setAiGameActive(false);
              setMode("DISCUSS");
            } else {
              // Generate AI commentary on user's move + engine response
              if (llmEnabled) {
                console.log("🎙️ Generating play mode commentary...");
                // Describe the move for AI commentary
                const moveDescription = describeMoveType(moveSan, tempGame);
                try {
                  await generatePlayModeCommentary(moveSan.san, moveDescription, response, newFen);
                  console.log("✅ Commentary generated successfully");
                } catch (err) {
                  console.error("❌ Commentary generation failed:", err);
                  addAssistantMessage(`I played ${response.engine_move_san}.`);
                }
              } else {
                // Simple response if LLM is disabled
                addAssistantMessage(
                  `I played ${response.engine_move_san}.`
                );
              }
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
        `${getBackendBase()}/analyze_move?fen=${encodeURIComponent(fenBeforeLastMove)}&move_san=${encodeURIComponent(lastMoveSan)}&depth=18`,
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
    // Generate the structured Chesster response format
    const evalCp = analysisData.eval_cp || 0;
    const verdict = `${evalCp >= 0 ? '+' : ''}${(evalCp / 100).toFixed(2)} pawns`;

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
    
    const candidates = analysisData.candidate_moves || [];
    const themes = analysisData.themes || [];
    const threats = analysisData.threats || [];
    const pieceQuality = analysisData.piece_quality || {};
    
    let card = `Eval: ${evalCp > 0 ? '+' : ''}${evalPawns} pawns\n\n`;
    
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
  
  // DEBUG: Test engine pool with sample game
  async function testEnginePool() {
    console.log('🧪 Testing engine pool...');
    addSystemMessage('Testing engine pool...');
    
    try {
      // First check status
      const statusRes = await fetch(`${getBackendBase()}/engine_pool/status`);
      const status = await statusRes.json();
      console.log('Engine pool status:', status);
      
      if (!status.available) {
        addSystemMessage(`Engine pool not available: ${status.error || 'Unknown error'}`);
        return;
      }
      
      addSystemMessage(`Engine pool ready: ${status.pool_size} engines, ${status.engines_available} available`);
      
      // Run full test
      addSystemMessage('Running test game review (20 moves)...');
      const testRes = await fetch(`${getBackendBase()}/engine_pool/test`, { method: 'POST' });
      const testResult = await testRes.json();
      console.log('Engine pool test result:', testResult);
      
      if (testResult.success) {
        addSystemMessage(`${testResult.message}`);
        addSystemMessage(`Speed: ${testResult.positions_per_second} positions/sec`);
      } else {
        addSystemMessage(`Test failed: ${testResult.error}`);
      }
    } catch (err: any) {
      console.error('Engine pool test error:', err);
      addSystemMessage(`Test error: ${err.message}`);
    }
  }
  
  // Expose for console testing (client-side only)
  useEffect(() => {
    if (typeof window !== 'undefined') {
      (window as any).testAnnotations = testAnnotations;
      (window as any).testEnginePool = testEnginePool;
    }
  }, []);

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
      
      // ONLY show arrows when LLM explicitly mentions moves
      const candidates = engineData.candidate_moves || [];
      const moveArrows = generateMoveArrows(parsed.moves, fen, candidates);
      console.log('   Move arrows generated (LLM-mentioned only):', moveArrows.length);
      
      // Generate theme-based annotations for tags mentioned
      let themeAnnotations = { arrows: [] as any[], highlights: [] as any[] };
      try {
        // Determine side from FEN
        const sideToMove = fen.includes(' w ') ? 'white' : 'black';
        themeAnnotations = generateThemeAnnotations(parsed.themes || [], parsed.tags || [], engineData, fen, sideToMove);
        console.log('   Theme annotations generated:', themeAnnotations.arrows.length, 'arrows,', themeAnnotations.highlights.length, 'highlights');
      } catch (e) {
        console.warn('   Theme annotation generation failed:', e);
      }
      
      // Combine move arrows with theme annotations
      const combinedArrows = [...moveArrows.slice(0, 5), ...themeAnnotations.arrows.slice(0, 3)];
      const combinedHighlights = themeAnnotations.highlights.slice(0, 6);  // Allow theme-based highlights
      
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

    // Show loading indicator
    console.log('🔄 [generateLLMResponse] Starting, setting isLLMProcessing=true');
    const loaderId = addLoadingMessage('llm', 'Generating response...');
    setIsLLMProcessing(true);
    setLiveStatusMessages([]);  // Clear previous status
    activeStatusRunIdRef.current = null;

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
      
      // CRITICAL: Verify the analysis FEN matches the current position
      // If they don't match, the LLM will talk about the wrong position!
      if (analysisToUse && analysisToUse.fen && analysisToUse.fen !== fen) {
        console.warn(`⚠️ FEN MISMATCH! Analysis FEN: ${analysisToUse.fen}, Current FEN: ${fen}`);
        console.warn('   Waiting for correct analysis...');
        // Don't use mismatched analysis - better to have no analysis than wrong analysis
        analysisToUse = null;
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

      // Filter messages to only include those from the CURRENT position
      // This prevents confusion from context of different board states
      const messagesFromCurrentPosition = messages.filter(m => m.fen === fen);
      const recentRelevantMessages = messagesFromCurrentPosition.slice(-3);
      
      console.log(`💬 Context filtering: ${messages.length} total messages, ${messagesFromCurrentPosition.length} from current FEN, using last ${recentRelevantMessages.length}`);

      const contextMessage = `
USER REQUEST: ${userMessage}

Current Position (FEN): ${fen}
Current PGN: ${pgn}
Mode: ${inferredMode} (${modeContext})
Chat History (from this position): ${recentRelevantMessages.map(m => `${m.role}: ${m.content}`).join("\n")}

${themeAnalysisSummary}

Instructions: Respond naturally and conversationally. Use themes to justify any positional claims. Keep your response concise (2-3 sentences). Focus on being helpful and engaging.
      `.trim();

      // Use streaming endpoint for real-time status updates
      const result = await callLLMStream(
        [
          { role: "system", content: systemPrompt },
          { role: "user", content: contextMessage },
        ], 
        0.7,
        "gpt-4o-mini",
        true,
        // Real-time status callback with replace support + throttling
        (status) => {
          const now = Date.now();
          const timeSinceLastUpdate = now - lastStatusUpdateRef.current;
          
          // If update is faster than 200ms, mark as instant (no animation)
          // Only animate if >1 second since last update
          const shouldAnimate = timeSinceLastUpdate > 1000;
          
          setLiveStatusMessages(prev => {
            // Ignore late events from previous runs; lock to first seen run id.
            const runId = (status as any)?._runId as (string | undefined);
            if (runId) {
              if (!activeStatusRunIdRef.current) activeStatusRunIdRef.current = runId;
              if (activeStatusRunIdRef.current && runId !== activeStatusRunIdRef.current) return prev;
            }
            lastStatusUpdateRef.current = now;
            const enrichedStatus = { ...status, instant: !shouldAnimate };
            
            if (status.replace && prev.length > 0) {
              // Replace the last message instead of adding
              return [...prev.slice(0, -1), enrichedStatus];
            }
            return [...prev, enrichedStatus];
          });
        },
        abortController?.signal
      );
      
      const meta = { 
        rawEngineData: toolOutput, 
        fen: fen,
        mode: inferredMode,
        structuredAnalysis: structuredAnalysis,
        // Chain-of-thought data
        statusMessages: result.status_messages || [],
        detectedIntent: result.detected_intent,
        toolsUsed: result.tools_used || [],
        orchestration: result.orchestration,
        backendAnnotations: result.annotations,
        baselineIntuition: result.baseline_intuition
      };
      
      // Add assistant message - ensure content is not empty
      const hasContent = result.content && result.content.trim();
      if (hasContent) {
        addAssistantMessage(result.content, meta);
      } else {
        console.warn("⚠️ [generateLLMResponse] Empty content received, not adding message. Result:", result);
      }
      
      // Add buttons after the message if present (always add buttons, even if no message)
      if (Array.isArray(result.buttons) && result.buttons.length > 0) {
        const buttonIdBase = Date.now();
        const buttonMessages = result.buttons.map((btn: any, idx: number) => {
          const buttonMsg: ChatMessage = {
            id: `btn-msg-${buttonIdBase}-${idx}`,  // Add unique ID for React key
            role: 'button' as const,
            content: btn.label || btn.action || 'Button',  // Ensure content is never empty
            buttonAction: btn.action,
            buttonLabel: btn.label,
            meta: { ...(btn.data || {}), buttonId: `btn-${buttonIdBase}-${idx}` },
            fen: fen,
            tabId: activeTabId
          };
          return buttonMsg;
        });
        // Add buttons immediately - React will batch the state updates
        setMessages((prev) => [...prev, ...buttonMessages]);
      } else {
      }
      
      // Don't hide - they'll be collapsed automatically when marked as complete
    } catch (err: any) {
      addSystemMessage(`LLM error: ${err.message}`);
      // Hide execution plan and thinking stage on error too
      setExecutionPlan(null);
      setThinkingStage(null);
    } finally {
      removeLoadingMessage(loaderId);
      setIsLLMProcessing(false);
      setLiveStatusMessages([]);
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
        const response = await fetch(`${getBackendBase()}/analyze_move?fen=${encodeURIComponent(fenBefore)}&move_san=${encodeURIComponent(moveToAnalyze)}&depth=18`, {
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
        const response = await fetch(`${getBackendBase()}/analyze_move?fen=${encodeURIComponent(fenToAnalyze)}&move_san=${encodeURIComponent(moveToAnalyze)}&depth=18`, {
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

  async function handleRunFullAnalysis(fenToAnalyze: string) {
    // Run full analysis (with Step 7 - piece profiles, NNUE, etc.)
    const loadingId = addLoadingMessage('stockfish', 'Running full analysis...');
    
    try {
      const response = await fetch(
        `${getBackendBase()}/analyze_position?fen=${encodeURIComponent(fenToAnalyze)}&lines=4&depth=18&light_mode=false`,
        { method: 'GET' }
      );
      
      if (!response.ok) {
        throw new Error(`Analysis failed: ${response.statusText}`);
      }
      
      const analysisData = await response.json();
      
      // Remove loading message
      setMessages((prev) => prev.filter((m) => m.id !== loadingId));
      
      // Cache the full analysis
      setAnalysisDataByFen(prev => {
        const newMap = new Map(prev);
        newMap.set(fenToAnalyze, analysisData);
        return newMap;
      });
      
      // Add assistant message with full analysis results
      addAssistantMessage(
        `**Full Analysis Complete**\n\nEval: ${analysisData.eval_cp}cp\nBest move: ${analysisData.best_move}\n\nFull analysis includes piece profiles, NNUE evaluation, square control, and piece trajectories.`,
        { 
          rawEngineData: analysisData,
          fen: fenToAnalyze,
          fen_before: fenToAnalyze
        }
      );
    } catch (error: any) {
      console.error('Full analysis error:', error);
      setMessages((prev) => prev.filter((m) => m.id !== loadingId));
      addSystemMessage(`Full analysis error: ${error.message}`);
    }
  }

  async function handleAnalyzeMoveRequest() {
    // Trigger a structured analysis of the current position/move
    // This forces the LLM to use headers and detailed breakdown
    if (!llmEnabled) {
      addSystemMessage("LLM is disabled. Enable it to get structured analysis.");
      return;
    }
    
    const loadingId = addLoadingMessage('llm', 'Generating structured analysis...');
    
    try {
      const structuredPrompt = "Analyze this position with full technical details.";
      
      // Use callLLM with force_structured context flag
      const result = await fetch(`${getBackendBase()}/llm_chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: [
            { role: 'system', content: 'You are Chesster.' },
            { role: 'user', content: structuredPrompt }
          ],
          context: {
            fen,
            board_state: fen,
            pgn,
            has_pgn: !!pgn,
            mode,
            force_structured: true  // Flag to force structured output
          },
          use_tools: true,
          model: 'gpt-4o-mini',
          temperature: 0.7,
          max_tool_iterations: 5
        })
      });
      
      const data = await result.json();
      
      // Remove loading message
      setMessages((prev) => prev.filter((m) => m.id !== loadingId));
      
      // Add assistant response
      addAssistantMessage(data.content, data.raw_data);
    } catch (error: any) {
      console.error('Structured analysis error:', error);
      setMessages((prev) => prev.filter((m) => m.id !== loadingId));
      addSystemMessage(`Analysis error: ${error.message}`);
    }
  }

  async function handleSendMessage(message: string) {
    // Check for pending confirmations or clarifying questions first
    if (pendingConfirmation) {
      const lower = message.toLowerCase().trim();
      
      if (pendingConfirmation.action === 'confirm') {
        // Handle yes/no confirmation
        if (lower === 'yes' || lower === 'y' || lower === 'no' || lower === 'n') {
          const executed = executeIntent(pendingConfirmation.intent, message, {
            aiGameActive,
            mode,
            walkthroughActive
          });
          if (executed) {
            addUserMessage(message);
            return;
          }
        }
      } else if (pendingConfirmation.action === 'clarify') {
        // Handle clarifying question response
        const possibleIntents: IntentDetection[] = JSON.parse(pendingConfirmation.intent);
        
        // Check if user responded with a number
        const numMatch = lower.match(/^(\d+)$/);
        if (numMatch) {
          const selectedIndex = parseInt(numMatch[1]) - 1;
          if (selectedIndex >= 0 && selectedIndex < possibleIntents.length) {
            const selectedIntent = possibleIntents[selectedIndex];
            const executed = executeIntent(selectedIntent.intent, message, {
              aiGameActive,
              mode,
              walkthroughActive
            });
            if (executed) {
              setPendingConfirmation(null);
              addUserMessage(message);
              return;
            }
          }
        }
        
        // Check if user's message matches one of the intent descriptions
        for (const intent of possibleIntents) {
          const intentKeywords = intent.keywords || [];
          if (intentKeywords.some(k => lower.includes(k)) || 
              lower.includes(intent.intent.toLowerCase()) ||
              lower.includes(intent.description.toLowerCase())) {
            const executed = executeIntent(intent.intent, message, {
              aiGameActive,
              mode,
              walkthroughActive
            });
            if (executed) {
              setPendingConfirmation(null);
              addUserMessage(message);
              return;
            }
          }
        }
        
        // If no match, clear confirmation and proceed normally
        setPendingConfirmation(null);
      }
    }

    // Check for button actions first (before adding user message)
    if (message.startsWith('__BUTTON_ACTION__')) {
      const action = message.replace('__BUTTON_ACTION__', '');
      if (action === 'START_WALKTHROUGH') {
        if (isProcessingStep) {
          console.log('🚫 [handleButtonAction] Already processing, ignoring START_WALKTHROUGH');
          return;
        }
        setIsProcessingStep(true);
        await startWalkthrough();
        setIsProcessingStep(false);
        return;
      } else if (action === 'NEXT_STEP') {
        if (isProcessingStep) {
          console.log('🚫 [handleButtonAction] Already processing, ignoring NEXT_STEP');
          return;
        }
        setIsProcessingStep(true);
        await continueWalkthrough();
        setIsProcessingStep(false);
        return;
      } else if (action === 'LESSON_SKIP') {
        await skipLessonPosition();
        return;
      } else if (action === 'LESSON_PREVIOUS') {
        await previousLessonPosition();
        return;
      } else if (action.startsWith('LESSON_MOVE::')) {
        const [, nodeId, moveKey] = action.split('::');
        if (nodeId && moveKey) {
          await executeLessonBranchMove(nodeId, moveKey);
        }
        return;
      } else if (action.startsWith('JUMP_TO_PLY_')) {
        const ply = parseInt(action.replace('JUMP_TO_PLY_', ''));
        await jumpToKeyPoint(ply);
        return;
      } else if (action === 'RETRY_MOVE') {
        // Disable the retry button that was clicked
        const buttonId = (event as CustomEvent)?.detail?.buttonId;
        if (buttonId) {
          setMessages(prev => prev.map(msg => 
            msg.buttonAction === 'RETRY_MOVE' && msg.meta?.buttonId === buttonId
              ? { ...msg, meta: { ...msg.meta, disabled: true } }
              : msg
          ));
        } else {
          // Fallback: disable all retry buttons if no buttonId
          setMessages(prev => prev.map(msg => 
            msg.buttonAction === 'RETRY_MOVE'
              ? { ...msg, meta: { ...msg.meta, disabled: true } }
              : msg
          ));
        }
        await startRetryMove();
        return;
      } else if (action === 'SHOW_HINT') {
        await showRetryHint();
        return;
      } else if (action === 'SHOW_SOLUTION') {
        await showRetrySolution();
        return;
      } else if (action === 'start_game_white') {
        // User wants to play as White (AI plays Black)
        setBoardOrientation('white');
        // Use the setAiGame from executeUICommands context
        const setAiGameFn = (async (active: boolean, aiSide: 'white' | 'black' | null = null, makeMoveNow: boolean = false) => {
          console.log(`[setAiGame] Setting AI game: active=${active}, aiSide=${aiSide}, makeMoveNow=${makeMoveNow}`);
          setAiGameActive(active);
          if (active) {
            setMode("PLAY");
            if (makeMoveNow) {
              const currentTurn = fen.split(' ')[1];
              const isAiTurn = aiSide === null || 
                              (aiSide === 'white' && currentTurn === 'w') || 
                              (aiSide === 'black' && currentTurn === 'b');
              if (isAiTurn) {
                try {
                  const response = await playMove(fen, "", undefined, 1500);
                  if (response.legal && response.engine_move_san && response.new_fen) {
                    const tempGame = new Chess(fen);
                    const move = tempGame.move(response.engine_move_san);
                    if (move) {
                      handleMove(move.from, move.to, move.promotion);
                    }
                  }
                } catch (err) {
                  console.error('[setAiGame] Error making AI move:', err);
                }
              }
            }
          }
        });
        await setAiGameFn(true, 'black', false);
        addSystemMessage('Starting game - you are playing as White. Make your first move!');
        return;
      } else if (action === 'start_game_black') {
        // User wants to play as Black (AI plays White)
        setBoardOrientation('black');
        // Determine if AI should make first move (if it's White's turn)
        const currentGame = new Chess(fen);
        const isWhiteTurn = currentGame.turn() === 'w';
        // Use the setAiGame from executeUICommands context
        const setAiGameFn = (async (active: boolean, aiSide: 'white' | 'black' | null = null, makeMoveNow: boolean = false) => {
          console.log(`[setAiGame] Setting AI game: active=${active}, aiSide=${aiSide}, makeMoveNow=${makeMoveNow}`);
          setAiGameActive(active);
          if (active) {
            setMode("PLAY");
            if (makeMoveNow) {
              const currentTurn = fen.split(' ')[1];
              const isAiTurn = aiSide === null || 
                              (aiSide === 'white' && currentTurn === 'w') || 
                              (aiSide === 'black' && currentTurn === 'b');
              if (isAiTurn) {
                try {
                  const response = await playMove(fen, "", undefined, 1500);
                  if (response.legal && response.engine_move_san && response.new_fen) {
                    const tempGame = new Chess(fen);
                    const move = tempGame.move(response.engine_move_san);
                    if (move) {
                      handleMove(move.from, move.to, move.promotion);
                    }
                  }
                } catch (err) {
                  console.error('[setAiGame] Error making AI move:', err);
                }
              }
            }
          }
        });
        await setAiGameFn(true, 'white', isWhiteTurn);
        if (isWhiteTurn) {
          addSystemMessage('Starting game - you are playing as Black. AI will make the first move...');
        } else {
          addSystemMessage('Starting game - you are playing as Black. Make your first move!');
        }
        return;
      }
    }
    
    // Tree search command (client-side UX): /search <query> or /tree-search <query>
    // Returns a ranked list by deviation depth (mainline first) and ply.
    if (message.startsWith('/search ') || message.startsWith('/tree-search ')) {
      const query = message.replace(/^\/(search|tree-search)\s+/i, '').trim();
      if (!query) {
        addSystemMessage('Usage: /search <query> (e.g., /search move:\"Nf3\")');
        return;
      }
      try {
        const tabId = activeTab?.id || activeTabId || sessionId;
        await ensureBackendTreeForTab(tabId, fen);
        const resp = await fetch(`${getBackendBase()}/board/tree/search`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ thread_id: tabId, query, limit: 25 }),
        });
        if (!resp.ok) {
          const txt = await resp.text();
          addSystemMessage(`Tree search failed: ${txt}`);
          return;
        }
        const data = await resp.json();
        const rows = Array.isArray(data?.results) ? data.results : [];
        const tableLines = [
          `Query: ${query}`,
          '',
          '| Rank | Move | VarDepth | Ply | Node |',
          '|---:|---|---:|---:|---|',
          ...rows.map((r: any, i: number) => {
            const mv = String(r?.move_san || '');
            const vd = String(r?.variation_depth ?? '');
            const ply = String(r?.ply ?? '');
            const nid = String(r?.node_id || '');
            return `| ${i + 1} | ${mv} | ${vd} | ${ply} | ${nid} |`;
          }),
        ].join('\n');

        setMessages(prev => [
          ...prev,
          { role: 'user', content: message },
          {
            role: 'expandable_table',
            content: '',
            tableTitle: `Tree search results (${rows.length})`,
            tableContent: tableLines,
          } as any,
        ]);
        return;
      } catch (e: any) {
        addSystemMessage(`Tree search error: ${e instanceof Error ? e.message : String(e)}`);
        return;
      }
    }

    // Check if there's a pending image to attach
    if (pendingImage) {
      // Update the existing image message to include the text content
      setMessages((prev) => prev.map((msg, idx) => {
        if (idx === prev.length - 1 && msg.image && msg.content === '') {
          return {
            ...msg,
            content: message,
            image: {
              ...msg.image,
              uploading: false,
              uploadProgress: 100,
            },
          };
        }
        return msg;
      }));
      
      // Also update tab messages
      setTabs(prevTabs => prevTabs.map(tab => {
        if (tab.id === activeTabId) {
          return {
            ...tab,
            messages: (tab.messages || []).map((msg, idx) => {
              const tabMessages = tab.messages || [];
              if (idx === tabMessages.length - 1 && msg.image && msg.content === '') {
                return {
                  ...msg,
                  content: message,
                  image: {
                    ...msg.image,
                    uploading: false,
                    uploadProgress: 100,
                  },
                };
              }
              return msg;
            }),
          };
        }
        return tab;
      }));
      
      setPendingImage(null); // Clear pending image after attaching
      // Don't add a new message, just update the existing one
      // The message was already added when image was selected
    } else {
      addUserMessage(message);
    }

    // Create abort controller for this request BEFORE processing
    const controller = new AbortController();
    setAbortController(controller);
    setIsAnalyzing(true);

    let lower = message.toLowerCase().trim();
    
    // Create context early for use throughout function
    const context = {
      aiGameActive,
      mode,
      walkthroughActive,
      fen,
      pgn
    };
    
    // ============================================================
    // ALL MESSAGES GO TO LLM INTERPRETER
    // The LLM interpreter handles all intent detection intelligently
    // No more frontend pattern matching
    // ============================================================
    try {
      console.log('🤖 Routing to LLM interpreter');
      await handleGeneralChat(message);
    } catch (err: any) {
      // Handle abort errors gracefully
      if (err.message === 'Request cancelled' || err.name === 'AbortError') {
        console.log('Request cancelled by user');
        addSystemMessage("Request cancelled.");
      } else {
        console.error('Error in handleGeneralChat:', err);
        addSystemMessage(`Error: ${err instanceof Error ? err.message : String(err)}`);
      }
    } finally {
      setIsAnalyzing(false);
      setAbortController(null);
    }
    return;
    
    // Old intent detection code has been completely removed
    // The LLM interpreter now handles all message routing
    
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
    setAiGameActive(false); // End AI game session when board is reset
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

  const findLessonNode = (id: string | null): LessonTreeNode | undefined => {
    if (!id) return undefined;
    return lessonTree.find((node) => node.id === id);
  };

  const getGamePhaseFromFen = (fenValue: string): "opening" | "middlegame" | "endgame" => {
    try {
      const board = new Chess(fenValue);
      const pieceCount = board.board().reduce((acc, row) => {
        return (
          acc +
          row.reduce((subAcc, square) => {
            return subAcc + (square ? 1 : 0);
          }, 0)
        );
      }, 0);
      if (pieceCount >= 28) return "opening";
      if (pieceCount >= 12) return "middlegame";
      return "endgame";
    } catch (err) {
      return "opening";
    }
  };

  const percentText = (value?: number | null, digits: number = 0) => {
    if (typeof value !== "number" || Number.isNaN(value)) return null;
    return `${(value * 100).toFixed(digits)}%`;
  };

  const describeMoveSource = (source?: string) => {
    if (!source) return null;
    switch (source) {
      case "mainline":
        return "theory main line";
      case "lichess":
        return "Lichess data";
      case "user_history":
        return "from your games";
      default:
        return source.replace(/_/g, " ");
    }
  };

  const describePersonalRecord = (record?: LessonMoveDescriptor["personal_record"]) => {
    if (!record || !record.games) return null;
    const wl = `${record.wins}-${record.losses}${record.draws ? `-${record.draws}` : ""}`;
    const score = record.games
      ? Math.round(((record.wins + 0.5 * record.draws) / record.games) * 100)
      : null;
    return score != null ? `your record ${wl} (${score}%)` : `your record ${wl}`;
  };

  const capitalizeWord = (word: string) => (word ? word.charAt(0).toUpperCase() + word.slice(1) : "");

  const formatLessonMoveOption = (label: string, descriptor?: LessonMoveDescriptor | null) => {
    if (!descriptor?.san) return null;
    const meta: string[] = [];
    const source = describeMoveSource(descriptor.source);
    if (source) meta.push(source);
    const pop = percentText(descriptor.popularity);
    if (pop) meta.push(`${pop} usage`);
    const win = percentText(descriptor.win_rate, 1);
    if (win) meta.push(`${win} score`);
    const record = describePersonalRecord(descriptor.personal_record);
    if (record) meta.push(record);
    if (descriptor.source === "user_history" && descriptor.platform) {
      meta.push(`${capitalizeWord(descriptor.platform)} games`);
    }
    return `• ${label}: ${descriptor.san}${meta.length ? ` — ${meta.join(" • ")}` : ""}`;
  };

  const humanizeTag = (tag: string) => {
    if (!tag) return null;
    const mobility = tag.match(/^tag\.activity\.mobility\.(\w+)/);
    if (mobility) {
      const piece = mobility[1];
      const pieceName = piece === "knight" ? "knight" : piece;
      return `${capitalizeWord(pieceName)} activity`;
    }
    const diagonal = tag.match(/^tag\.diagonal\.long\.([a-h]\d[a-h]\d)/);
    if (diagonal) {
      const diag = diagonal[1];
      const pretty =
        diag.length === 4 ? `${diag.slice(0, 2)}–${diag.slice(2)}`.toUpperCase() : diag.toUpperCase();
      return `pressure on ${pretty}`;
    }
    if (tag === "tag.bishop.pair") {
      return "bishop pair edge";
    }
    if (tag.startsWith("tag.activity.")) {
      return "piece activity";
    }
    const cleaned = tag.replace(/^tag\./, "").replace(/\./g, " ").replace(/_/g, " ");
    return cleaned ? cleaned.replace(/(^|\s)([a-z])/g, (_, space, ch) => `${space}${ch.toUpperCase()}`) : null;
  };

  const summarizeTagGroup = (tags?: string[], sideLabel?: string) => {
    if (!tags?.length) return null;
    const phrases = tags
      .map((tag) => humanizeTag(tag))
      .filter((val): val is string => Boolean(val))
      .slice(0, 2);
    if (!phrases.length) return null;
    return `${sideLabel || "Side"}: ${phrases.join(" & ")}`;
  };

  const describeTagFocus = (tags?: LessonTreeNode["tags"]) => {
    if (!tags) return null;
    const segments = [
      summarizeTagGroup(tags.white, "White"),
      summarizeTagGroup(tags.black, "Black"),
    ].filter(Boolean);
    if (!segments.length) return null;
    return segments.join(" ");
  };

  const announceLessonOptions = (node: LessonTreeNode, index: number, total: number) => {
    if (!node) return;
    const totalCount = total || lessonTree.length || 1;
    const moveLines: string[] = [];
    const mainLine = formatLessonMoveOption("Main line", node.main_move);
    if (mainLine) moveLines.push(mainLine);
    (node.alternate_moves || [])
      .slice(0, 3)
      .forEach((alt, idx) => {
        const altLine = formatLessonMoveOption(`Alternate ${idx + 1}`, alt);
        if (altLine) moveLines.push(altLine);
      });
    const focusText = describeTagFocus(node.tags);
    const sections = [
      node.objective || "Find the best continuation.",
      moveLines.length ? moveLines.join("\n") : null,
      focusText ? `_Focus_: ${focusText}` : null,
    ].filter(Boolean);
    addAssistantMessage(`**Lesson position ${index + 1}/${totalCount}**\n${sections.join("\n\n")}`);
  };

  const applyLessonVisuals = (node?: LessonTreeNode | null) => {
    if (!node) {
      setLessonArrows([]);
      return;
    }
    const arrows: AnnotationArrow[] = [];
    if (node.main_move?.from && node.main_move?.to) {
      arrows.push({
        from: node.main_move.from,
        to: node.main_move.to,
        color: LESSON_ARROW_COLORS.main,
      });
    }
    (node.alternate_moves || []).forEach((alt) => {
      if (alt.from && alt.to) {
        arrows.push({
          from: alt.from,
          to: alt.to,
          color: LESSON_ARROW_COLORS.alternate,
        });
      }
    });
    const threatMove = node.ai_responses?.[0];
    if (threatMove?.from && threatMove?.to) {
      arrows.push({
        from: threatMove.from,
        to: threatMove.to,
        color: LESSON_ARROW_COLORS.threat,
      });
    }
    setLessonArrows(arrows);
    const descriptionLines: string[] = [];
    const mainLineText = formatLessonMoveOption("Main line", node.main_move);
    if (mainLineText) {
      descriptionLines.push(mainLineText);
    }
    (node.alternate_moves || [])
      .slice(0, 3)
      .forEach((alt, idx) => {
        const altLine = formatLessonMoveOption(`Alternate ${idx + 1}`, alt);
        if (altLine) {
          descriptionLines.push(altLine);
        }
      });
    if (descriptionLines.length) {
      setLessonCueSnapshot({
        arrows,
        description: descriptionLines.join("\n"),
      });
      setLessonCueButtonActive(false);
    } else {
      setLessonCueSnapshot({ arrows, description: "" });
      setLessonCueButtonActive(false);
    }
  };

  const clearLessonVisualsForMove = () => {
    setLessonArrows([]);
    setAnnotations((prev) => ({
      ...prev,
      arrows: [],
      highlights: [],
    }));
    setLessonCueButtonActive(false);
  };

  const offerLessonCueButton = () => {
    if (!lessonCueSnapshot || lessonCueButtonActive) return;
    setLessonCueButtonActive(true);
    setMessages((prev) => [
      ...prev,
      {
        role: "button",
        content: "",
        buttonAction: "SHOW_LESSON_CUES",
        buttonLabel: "Show lesson cues",
      },
    ]);
  };

  const handleLessonCueRequest = () => {
    if (!lessonCueSnapshot) {
      addSystemMessage("No stored lesson cues for this position yet.");
      return;
    }
    setLessonArrows(lessonCueSnapshot.arrows);
    if (lessonCueSnapshot.description) {
      addAssistantMessage(`**Lines to know**\n${lessonCueSnapshot.description}`);
    }
  };
  const deriveNextNodeResponse = (
    currentNode: LessonTreeNode,
    nextNode: LessonTreeNode | undefined,
    playerMoveSan: string
  ): string | null => {
    if (!nextNode) return null;
    const currentHistory = currentNode.history || [];
    const nextHistory = nextNode.history || [];
    if (nextHistory.length <= currentHistory.length) return null;
    const diff = nextHistory.slice(currentHistory.length);
    if (!diff.length) return null;
    if (diff.length === 1) {
      return diff[0] === playerMoveSan ? null : diff[0];
    }
    const candidate = diff.find((san: string) => san !== playerMoveSan);
    return candidate || diff[diff.length - 1] || null;
  };
  const applyLessonAIMove = (startingFen: string, san: string) => {
    try {
      const tempGame = new Chess(startingFen);
      const move = tempGame.move(san);
      if (!move) {
        return null;
      }
      setGame(tempGame);
      setFen(tempGame.fen());
      let nextTreePgn = tempGame.pgn();
      setMoveTree((prev) => {
        const nextTree = prev.clone();
        nextTree.addMove(move.san, tempGame.fen());
        nextTreePgn = nextTree.toPGN();
        return nextTree;
      });
      setPgn(nextTreePgn);
      setTreeVersion((v) => v + 1);
      return tempGame.fen();
    } catch (err) {
      console.warn("Failed to apply lesson AI move:", err);
      return null;
    }
  };

  const handleLessonTreeMove = async (moveSan: string, postMoveFen: string, previousFen: string) => {
    if (!lessonNodeId) return;
    const node = findLessonNode(lessonNodeId);
    if (!node) return;
    const attemptNumber = getLessonAttemptNumber(node.id);
    const isMainMove = node.main_move?.san === moveSan;
    const matchedAlt = (node.alternate_moves || []).find((alt) => alt.san === moveSan);
    if (!isMainMove && !matchedAlt) {
      respondToLessonMove({
        moveSan,
        expectedMove: node.main_move?.san,
        attemptNumber,
        wasCorrect: false,
      });
      setIsOffMainLine(true);
      setMainLineFen(previousFen);
      return;
    }

    const nextNodeCandidate = node.next_node_id ? findLessonNode(node.next_node_id) : undefined;
    let responseSan: string | null = node.ai_responses?.[0]?.san ?? null;
    if (!responseSan) {
      responseSan = deriveNextNodeResponse(node, nextNodeCandidate, moveSan);
    }
    respondToLessonMove({
      moveSan,
      expectedMove: responseSan || node.main_move?.san,
      attemptNumber,
      wasCorrect: isMainMove,
    });

    let currentFenAfterMove = postMoveFen;
    if (responseSan) {
      const nextFen = applyLessonAIMove(postMoveFen, responseSan);
      if (nextFen) {
        currentFenAfterMove = nextFen;
        addAssistantMessage(`Opponent plays ${responseSan}.`);
      }
    }

    if (node.next_node_id) {
      const nextNode = nextNodeCandidate;
      if (nextNode) {
        const nextIndex = lessonTree.findIndex((n) => n.id === nextNode.id);
        presentLessonNode(nextNode, nextIndex >= 0 ? nextIndex : 0);
        return;
      }
    }

    setLessonNodeId(null);
    setCurrentLessonPosition(null);
    addAssistantMessage("Lesson branch finished. You can revisit earlier forks to explore alternates.");
  };


  const getLessonAttemptNumber = (positionId?: string | null) => {
    if (!positionId) return 1;
    const next = (lessonAttemptLog[positionId] ?? 0) + 1;
    setLessonAttemptLog((prev) => ({
      ...prev,
      [positionId]: next,
    }));
    return next;
  };

  const respondToLessonMove = ({
    moveSan,
    expectedMove,
    attemptNumber,
    wasCorrect,
  }: {
    moveSan: string;
    expectedMove?: string;
    attemptNumber: number;
    wasCorrect: boolean;
  }) => {
    const cleanAttempt = attemptNumber || 1;
    const correctTemplates = [
      `Nice touch with **${moveSan}**—you're following the headline idea.`,
      `Still sharp. **${moveSan}** keeps the structure you prepared.`,
      `Dialed in! **${moveSan}** is exactly what this plan needs.`,
    ];
    const retryTemplates = [
      `Let's steady the hand—**${moveSan}** gives up the thread.`,
      `Not yet. **${moveSan}** drifts from the game plan.`,
      `Re-center. **${moveSan}** doesn't hit the aim of the position.`,
    ];
    const pool = wasCorrect ? correctTemplates : retryTemplates;
    const variant = pool[(cleanAttempt - 1) % pool.length];
    const nextStep = expectedMove
      ? `Main line response to watch for: **${expectedMove}**.`
      : "Main line response is ready when you are.";
    addAssistantMessage(
      `${variant}\n${nextStep} Lesson cues refreshed below—tap **Show lesson cues** any time if you want them again later.`
    );
    handleLessonCueRequest();
    offerLessonCueButton();
  };


  const presentLessonNode = (
    node: LessonTreeNode,
    index: number,
    treeOverride?: LessonTreeNode[],
    orientationOverride?: "white" | "black",
  ) => {
    if (!node) return;
    const activeTree = treeOverride || lessonTree;
    const total = activeTree.length || lessonTree.length || 1;
    const newGame = new Chess(node.fen);
    setGame(newGame);
    setFen(node.fen);
    setLessonNodeId(node.id);
    setLessonProgress({ current: index + 1, total });
    enterLessonMode();
    const nextOrientation = orientationOverride || lessonOrientation;
    setBoardOrientation(nextOrientation);
    applyLessonVisuals(node);
    announceLessonOptions(node, index, total);
  };

  const initializeLessonTree = (nodes: LessonTreeNode[], orientation: "white" | "black") => {
    setLessonTree(nodes);
    setLessonOrientation(orientation);
    if (nodes.length) {
      presentLessonNode(nodes[0], 0, nodes, orientation);
    } else {
      setLessonNodeId(null);
    }
  };

  const executeLessonBranchMove = async (nodeId: string, key: string) => {
    const node = findLessonNode(nodeId);
    if (!node) return;
    let descriptor: LessonMoveDescriptor | undefined | null;
    if (key === "main") {
      descriptor = node.main_move;
    } else if (key.startsWith("alt")) {
      const altIndex = parseInt(key.replace("alt", ""), 10);
      descriptor = node.alternate_moves?.[altIndex];
    }
    if (!descriptor?.san) {
      addSystemMessage("Unable to interpret that lesson move.");
      return;
    }
    const learnerGame = new Chess(node.fen);
    try {
      learnerGame.move(descriptor.san);
    } catch (err) {
      addSystemMessage(`Move ${descriptor.san} is not legal in this position.`);
      return;
    }
    let narration = `You played ${descriptor.san} (${descriptor.source || "theory"})`;
    if (node.ai_responses && node.ai_responses.length > 0) {
      const reply = node.ai_responses[0];
      try {
        learnerGame.move(reply.san);
        narration += `\nAI replies ${reply.san}.`;
      } catch (err) {
        console.warn("Failed to apply AI reply", err);
      }
    }
    setGame(learnerGame);
    setFen(learnerGame.fen());
    addAssistantMessage(narration);
    if (node.next_node_id) {
      const nextNode = findLessonNode(node.next_node_id);
      if (nextNode) {
        const nextIndex = lessonTree.findIndex((n) => n.id === nextNode.id);
        presentLessonNode(nextNode, nextIndex >= 0 ? nextIndex : 0);
        return;
      }
    }
    addAssistantMessage("Lesson branch finished. You can revisit earlier forks to explore alternates.");
  };

  function aiSetPosition(newFen: string): boolean {
    try {
      const newGame = new Chess();
      const loadSuccess = newGame.load(newFen) as unknown as boolean;
      if (!loadSuccess) {
        throw new Error('Invalid FEN string');
      }
      setGame(newGame);
      setFen(newGame.fen());
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
    console.log('♟️ [handleLoadFen] Requested load:', newFen);
    if (!newFen || typeof newFen !== 'string') {
      console.error('❌ handleLoadFen received invalid FEN:', newFen);
      addSystemMessage('Cannot load position: engine did not provide a valid FEN.');
      return;
    }
    if (!/^([prnbqkPRNBQK1-8]+\/?){1,8}\s[wb]\s(-|K?Q?k?q?)\s(-|[a-h][36])\s\d+\s\d+$/.test(newFen.trim())) {
      console.warn('⚠️ handleLoadFen received non-standard FEN, attempting to load anyway:', newFen);
    }
    try {
      const newGame = new Chess(newFen);
      setGame(newGame);
      setFen(newFen);
      
      // Reset move tree when loading new FEN
      const cleanedFen = newGame.fen();
      const newTree = new MoveTree();
      newTree.root.fen = cleanedFen;
      newTree.currentNode = newTree.root;
      setMoveTree(newTree);
      setPgn("");
      // Add starting position snapshot into chat
      setMessages(prev => [...prev, {
        role: 'graph',
        content: '',
        meta: { miniBoard: { fen: cleanedFen, pgn: '', orientation: boardOrientation } }
      }]);
      
      addSystemMessage(`Position loaded from FEN`);
    } catch (err: any) {
      addSystemMessage(`Invalid FEN: ${err.message}`);
    }
  }

  function generateReviewTableData(data: any) {
    // Transform walkthrough data into GameReviewTable format
    const moves = (data.moves || []).map((m: any) => ({
      moveNumber: m.moveNumber,
      move: m.move,
      quality: m.quality,
      cpLoss: m.cpLoss,
      eval: m.evalAfter,
      comment: m.hint || ''
    }));
    
    const stats = {
      white_accuracy: data.avgWhiteAccuracy || 0,
      black_accuracy: data.avgBlackAccuracy || 0,
      overall_accuracy: ((data.avgWhiteAccuracy || 0) + (data.avgBlackAccuracy || 0)) / 2,
      excellent: moves.filter((m: any) => m.quality === 'excellent' || m.quality === 'best').length,
      good: moves.filter((m: any) => m.quality === 'good').length,
      inaccuracy: moves.filter((m: any) => m.quality === 'inaccuracy').length,
      mistake: moves.filter((m: any) => m.quality === 'mistake').length,
      blunder: moves.filter((m: any) => m.quality === 'blunder').length
    };
    
    const game_metadata = {
      opening: data.openingName || 'Unknown Opening',
      total_moves: data.moves?.length || 0,
      game_character: (data.gameTags || []).join(', '),
      result: '' // Not available in walkthrough data
    };
    
    const key_points = [];
    if (data.leftTheoryMove) {
      key_points.push({
        ply: data.leftTheoryMove.moveNumber,
        type: 'left_theory',
        description: `Left theory with ${data.leftTheoryMove.move}`,
        move: data.leftTheoryMove.move
      });
    }
    
    (data.criticalMovesList || []).forEach((m: any) => {
      key_points.push({
        ply: m.moveNumber,
        type: m.quality || 'critical',
        description: `${m.quality || 'Critical move'}: ${m.move}`,
        move: m.move
      });
    });
    
    return {
      moves,
      stats,
      game_metadata,
      key_points
    };
  }

  async function startWalkthroughWithData(data: any) {
    console.log('🎬 [startWalkthroughWithData] Called with data:', data ? 'EXISTS' : 'NULL');
    
    if (!data) {
      console.error('❌ [startWalkthroughWithData] No walkthrough data provided!');
      return;
    }
    
    // Generate table data for later use
    const tableData = generateReviewTableData(data);
    // Store table data globally for use in walkthrough messages
    (window as any).__walkthroughTableData = tableData;
    
    // Get first move to show position after move 1
    // Handle both data structures: new (first_game_review.ply_records) and old (moves)
    let plyRecords: any[] = [];
    if (data.first_game_review?.ply_records) {
      plyRecords = data.first_game_review.ply_records;
    } else if (data.moves && Array.isArray(data.moves)) {
      // Transform moves array to ply_records format
      plyRecords = data.moves.map((m: any, idx: number) => ({
        ply: m.ply || (idx + 1),
        san: m.move || m.san,
        fen_after: m.fen || m.fenAfter,
        fen_before: m.fenBefore || m.fen_before
      }));
    }
    
    const firstMove = plyRecords.find((r: any) => r.ply === 1);
    
    if (firstMove && firstMove.fen_after) {
      // Navigate to position after move 1 in the existing moveTree (don't overwrite it)
      setMoveTree(prevTree => {
        // Find the first move node in the tree
        if (prevTree.root.children.length > 0) {
          // Clone to avoid mutating state directly
          const tree = prevTree.clone();
          const firstNode = tree.root.children[0];
          tree.currentNode = firstNode;
          
          // Set board to position after move 1
          const game = new Chess();
          game.load(firstMove.fen_after);
          setFen(firstMove.fen_after);
          setGame(game);
          
          // Don't overwrite PGN - keep the full game PGN
          // The walkthrough will navigate through moves, but PGN should remain intact
          
          return tree;
        } else {
          // Fallback: if tree is empty, create minimal tree
          const newTree = new MoveTree();
          newTree.root.fen = INITIAL_FEN;
          newTree.currentNode = newTree.root;
          const firstNode = newTree.addMove(firstMove.san, firstMove.fen_after);
          newTree.currentNode = firstNode;
          
          const game = new Chess();
          game.load(firstMove.fen_after);
          setFen(firstMove.fen_after);
          setGame(game);
          
          return newTree;
        }
      });
    }
    
    // Store walkthrough data for button click
    setWalkthroughData(data);
    
    // DON'T add a message here - the narrative message will be added separately with the button
    // Just set up the board position and store the data
  }

  async function continueWalkthroughWithData(data: any, step: number) {
    try {
      console.log('🔄 [continueWalkthroughWithData] Called, step:', step, 'data:', data ? 'EXISTS' : 'NULL');
      
      if (!data) {
        console.error('❌ [continueWalkthroughWithData] No walkthrough data provided!');
        addSystemMessage("Walkthrough halted: no data available.");
        return;
      }
      
      // Extract queryIntent early so it's available throughout the function
      const queryIntent = data.queryIntent || 'general';
      
      // Use pre-built sequence if available (from batch commentary generation)
      let sequence: any[] = data.sequence || [];
      
      // If no pre-built sequence, build it now (fallback for old code paths)
      if (sequence.length === 0) {
        const moves = Array.isArray(data.moves) ? data.moves : [];
        const selectedKeyMoments = Array.isArray(data.selectedKeyMoments) ? data.selectedKeyMoments : [];
        const leftTheoryMove = data.leftTheoryMove || null;
        
        console.log('🔄 [continueWalkthroughWithData] Extracted data - moves count:', moves.length, 'selectedKeyMoments:', selectedKeyMoments.length, 'queryIntent:', queryIntent);
        if (moves.length === 0) {
          console.warn('⚠️ [continueWalkthroughWithData] No moves available in walkthrough data.');
          addSystemMessage("Unable to start walkthrough: review returned no moves.");
          setWalkthroughActive(false);
          return;
        }
        
        sequence = [];
        
        // ========== USE LLM-SELECTED MOMENTS IF AVAILABLE ==========
        if (selectedKeyMoments.length > 0) {
      console.log('🎯 [Walkthrough] Using LLM-selected key moments:', {
        count: selectedKeyMoments.length,
        queryIntent: queryIntent,
        plies: selectedKeyMoments.map((m: any) => m.ply)
      });
      
      // Build sequence from selected moments
      selectedKeyMoments.forEach((moment: any) => {
        const ply = moment.ply;
        const moveData = moves.find((m: any) => m.ply === ply);
        
        if (!moveData) {
          console.warn(`   ⚠️ Move at ply ${ply} not found in moves array`);
          return;
        }
        
        // Determine step type from moment labels or move category
        const labels = moment.labels || [];
        const primaryLabel = moment.primary_label || moveData.quality || '';
        const category = moveData.category || primaryLabel;
        
        // Classify step type - errors get retry, good moves get highlight
        let stepType = 'highlight'; // Default for non-errors
        
        if (category === 'blunder' || labels.includes('blunder')) {
          stepType = 'blunder';
        } else if (category === 'mistake' || labels.includes('mistake')) {
          stepType = 'mistake';
        } else if (category === 'inaccuracy' || labels.includes('inaccuracy')) {
          stepType = 'inaccuracy';
        } else if (labels.includes('advantage_shift')) {
          stepType = 'advantage_shift';
        } else if (labels.includes('missed_critical_win') || labels.includes('missed_win')) {
          stepType = 'missed_win';
        } else if (category === 'critical_best' || labels.includes('critical_best')) {
          stepType = 'critical';
        } else if (category === 'best' || labels.includes('best')) {
          stepType = 'best_move';
        } else if (labels.includes('tactical_opportunity')) {
          stepType = 'tactical';
        } else if (labels.includes('phase_transition')) {
          stepType = 'phase_transition';
        }
        
        sequence.push({ 
          type: stepType, 
          move: moveData,
          moment: moment,
          queryIntent: queryIntent
        });
        
        const moveLabel = `${moveData.moveNumber}${moveData.color === 'w' ? '.' : '...'} ${moveData.move}`;
        console.log(`   ✅ Adding ${stepType} at ply ${ply}: ${moveLabel} (labels: ${labels.join(', ') || 'none'})`);
      });
      
      // Always end with final position if not already included
      const lastMomentPly = selectedKeyMoments[selectedKeyMoments.length - 1]?.ply;
      const finalMove = moves[moves.length - 1];
      if (finalMove && lastMomentPly !== finalMove.ply) {
        sequence.push({ type: 'final', move: finalMove });
        console.log(`   ✅ Adding final position at ply ${finalMove.ply}`);
      }
      
          console.log('🎯 [Walkthrough] LLM-driven sequence built:', {
            steps: sequence.length,
            queryIntent: queryIntent,
            types: sequence.map((s: any) => s.type)
          });
          
        } else {
          // ========== FALLBACK: Original error-based selection ==========
          console.log('⚠️ [Walkthrough] No LLM-selected moments, using fallback error-based selection');
      
          const crossed200 = Array.isArray(data.crossed200) ? data.crossed200 : [];
          const crossed300 = Array.isArray(data.crossed300) ? data.crossed300 : [];
          
          // Collect error candidates
          const candidates: any[] = [];
          moves.forEach((m: any) => {
            if (m.quality === 'blunder') {
              candidates.push({ move: m, type: 'blunder', cpLoss: m.cpLoss || 0 });
            } else if (m.quality === 'mistake') {
              candidates.push({ move: m, type: 'mistake', cpLoss: m.cpLoss || 0 });
            } else if (m.quality === 'inaccuracy' && (m.cpLoss || 0) >= 50) {
              candidates.push({ move: m, type: 'inaccuracy', cpLoss: m.cpLoss || 0 });
            }
          });
          
          // Sort by CP loss, take top 10
          candidates.sort((a, b) => b.cpLoss - a.cpLoss);
          const selectedErrors = candidates.slice(0, 10);
          const errorPlies = new Set(selectedErrors.map(e => e.move.ply));
          
          // Add opening if exists
          const lastTheoryMoveFound = moves.filter((m: any) => m.isTheoryMove).pop();
          if (lastTheoryMoveFound) {
            sequence.push({ type: 'opening', move: lastTheoryMoveFound });
          }
          
          // Add left theory
          if (leftTheoryMove) {
            sequence.push({ type: 'left_theory', move: leftTheoryMove });
          }
          
          // Add errors chronologically
          selectedErrors.sort((a, b) => a.move.ply - b.move.ply);
          selectedErrors.forEach(err => {
            sequence.push({ type: err.type, move: err.move });
          });
          
          // Add advantage shifts not already in errors
          const allShifts = [
            ...crossed200.map((m: any) => ({ ...m, threshold: 200 })),
            ...crossed300.map((m: any) => ({ ...m, threshold: 300 }))
          ];
          allShifts.sort((a, b) => a.ply - b.ply);
          allShifts.slice(0, 5).forEach((shift: any) => {
            if (!errorPlies.has(shift.ply)) {
              sequence.push({ type: 'advantage_shift', move: shift });
            }
          });
          
          // Final position
          const finalMove = moves[moves.length - 1];
          if (finalMove) {
            sequence.push({ type: 'final', move: finalMove });
          }
          
          console.log('🎯 [Walkthrough] Fallback sequence built:', {
            steps: sequence.length,
            errors: selectedErrors.length,
            types: sequence.map((s: any) => s.type)
          });
        }
      }
    
    // Check if we're done
    if (step >= sequence.length) {
        console.log('✅ [continueWalkthroughWithData] All steps complete');
      setWalkthroughActive(false);
      setWalkthroughStep(0);
      
      // Generate query-aware completion message
      let completionMessage = "That completes the walkthrough! Feel free to ask any questions about the game.";
      if (queryIntent === 'loss_diagnosis') {
        completionMessage = "That covers the key moments that led to your loss. Would you like tips on how to avoid these patterns?";
      } else if (queryIntent === 'blunder_review') {
        completionMessage = "Those were the critical errors in this game. Would you like to practice similar positions?";
      } else if (queryIntent === 'time_analysis') {
        completionMessage = "Those were the moves where time was a factor. Would you like time management tips?";
      } else if (queryIntent === 'best_moves') {
        completionMessage = "Those were your strongest moves! Would you like to analyze the patterns that led to them?";
      } else if (queryIntent === 'tactical_moments') {
        completionMessage = "Those were the key tactical moments. Would you like to practice similar tactics?";
      }
      
      addAssistantMessage(completionMessage);
      return;
    }
    
      const current = sequence[step];
      console.log('▶️ [continueWalkthroughWithData] Executing step', step + 1, 'of', sequence.length, 'type:', current?.type);
      await executeWalkthroughStep(current, step + 1, sequence.length, data, step); // Pass step index for commentary lookup
    
    setWalkthroughStep(step + 1);
    } catch (err) {
      console.error('❌ [continueWalkthroughWithData] Error:', err);
      addSystemMessage(`Walkthrough error: ${err instanceof Error ? err.message : String(err)}`);
      setWalkthroughActive(false);
    }
  }

  async function continueWalkthrough() {
    console.log('🔄 [continueWalkthrough] Called, step:', walkthroughStep, 'data:', walkthroughData ? 'EXISTS' : 'NULL');
    
    if (!walkthroughData) {
      console.error('❌ [continueWalkthrough] No walkthrough data available!');
      return;
    }
    try {
      await continueWalkthroughWithData(walkthroughData, walkthroughStep);
    } catch (err) {
      console.error('❌ [continueWalkthrough] continueWalkthroughWithData threw:', err);
      addSystemMessage(`Walkthrough error: ${err instanceof Error ? err.message : String(err)}`);
      setWalkthroughActive(false);
    }
  }

  async function generateWalkthroughPreCommentary(
    stepType: string,
    move: any,
    walkData: any,
    allowRetry: boolean,
    skipLoadingIndicator: boolean = false,
    stepIndex?: number
  ): Promise<string> {
    const meta = (walkData?.game_metadata || walkData?.gameMetadata || {}) as any;
    const rationale = (walkData?.selectionRationale || walkData?.selection_rationale || {}) as any;
    const preByPly = (walkData?.preCommentaryByPly || walkData?.pre_commentary_by_ply || {}) as any;
    const playerColor: 'white' | 'black' | null = meta.player_color || null;
    const focusColor: 'white' | 'black' | 'both' | null = meta.focus_color || meta.focusColor || null;
    const reviewSubject: 'player' | 'opponent' | 'both' | null = meta.review_subject || meta.reviewSubject || null;
    const narrativeFocus: string | null =
      typeof rationale?.narrative_focus === 'string' ? rationale.narrative_focus : null;

    const moverColor: 'white' | 'black' = move?.color === 'w' ? 'white' : 'black';
    const moverLabel =
      reviewSubject === 'opponent'
        ? 'your opponent'
        : (playerColor && moverColor === playerColor ? 'you' : (moverColor === 'white' ? 'White' : 'Black'));

    const moveSan = move?.move || move?.san || '?';
    const moveNumber = typeof move?.moveNumber === 'number' ? move.moveNumber : null;
    const cpLoss = Math.round(move?.cpLoss || 0);
    const evalBefore = typeof move?.evalBefore === 'number' ? move.evalBefore : null;
    const evalAfter = typeof move?.evalAfter === 'number' ? move.evalAfter : null;

    // Check for pre-generated commentary first (from batch generation)
    // Use stepIndex if provided (most reliable), otherwise find by matching step
    if (walkData.preGeneratedCommentary) {
      let commentaryIndex: number | null = null;
      
      if (typeof stepIndex === 'number' && stepIndex >= 0) {
        // Use provided step index (most reliable)
        commentaryIndex = stepIndex;
      } else if (walkData.sequence) {
        // Fallback: find step in sequence
        commentaryIndex = walkData.sequence.findIndex((s: any) => 
          s.move?.ply === move?.ply || 
          (s.move?.moveNumber === move?.moveNumber && s.move?.color === move?.color)
        );
      }
      
      if (commentaryIndex !== null && commentaryIndex >= 0 && walkData.preGeneratedCommentary.has(commentaryIndex)) {
        return walkData.preGeneratedCommentary.get(commentaryIndex)!;
      }
    }
    
    // If backend provided pre-commentary, use it (no per-step LLM call).
    const plyKey =
      typeof move?.ply === 'number' ? String(move.ply) :
      (typeof move?.moveNumber === 'number' ? String((move.moveNumber - 1) * 2 + (move?.color === 'w' ? 1 : 2)) : null);
    if (plyKey && preByPly && typeof preByPly[plyKey] === 'string' && preByPly[plyKey].trim()) {
      return preByPly[plyKey].trim();
    }

    const prompt = `
We are in a guided chess walkthrough.

Context:
- Review subject: ${reviewSubject || 'unknown'} (focus_color=${focusColor || 'unknown'}, player_color=${playerColor || 'unknown'})
- Step type: ${stepType}
- Mover: ${moverLabel} (${moverColor})
- Move: ${moveNumber ? `Move ${moveNumber}: ${moveSan}` : moveSan}
- CP loss (if applicable): ${cpLoss}
- Eval before: ${evalBefore === null ? 'N/A' : (evalBefore / 100).toFixed(2)}
- Eval after: ${evalAfter === null ? 'N/A' : (evalAfter / 100).toFixed(2)}
- Retry allowed: ${allowRetry}

Write 1–2 sentences of pre-analysis coach commentary that:
- Explains why this moment matters / what to watch for
- Does NOT reveal the best move or suggest any specific move
- If Retry allowed, end with a short invitation like "Try to find a better continuation" (no move names)
- Avoid "10. Qb3" formatting; if you mention move number, use "Move 10: …"
`;

    try {
      // Show loading indicator while generating commentary (unless batch generation is handling it)
      const loadingId = skipLoadingIndicator ? null : addLoadingMessage('llm', 'Generating walkthrough commentary...');
      try {
        const { content } = await callLLM(
          [
            {
              role: "system",
              content:
                "You are a concise chess coach. Write 1–2 sentences. No move spoilers. Never name the best move. Never output SAN suggestions. Avoid lists."
            },
            { role: "user", content: prompt }
          ],
          0.6,
          "gpt-4o-mini",
          false
        );
        return (content || "").trim();
      } finally {
        if (loadingId) removeLoadingMessage(loadingId);
      }
    } catch (e) {
      if (allowRetry) return "This is a key turning point—see if you can find a cleaner continuation from here.";
      return "This is a key moment—let’s see what it changed in the position.";
    }
  }

  async function executeWalkthroughStep(step: any, stepNum: number, totalSteps: number, contextData?: any, stepIndex?: number) {
    console.log('🎬 [executeWalkthroughStep] Starting step:', stepNum, 'type:', step?.type);
    
    if (!step || !step.move) {
      console.error('❌ [executeWalkthroughStep] Invalid step data:', step);
      addSystemMessage("Error: Invalid walkthrough step. Skipping...");
      return;
    }
    
    const { type, move } = step;
  if (typeof move.moveNumber !== 'number') {
    console.error('❌ [executeWalkthroughStep] Missing moveNumber in move:', move);
    addSystemMessage("Error: Missing move number for walkthrough step. Skipping...");
    return;
  }
  const side = move.color === 'w' ? 'White' : 'Black';
  const walkData = contextData || walkthroughData || {};

  // Determine whether this walkthrough is focused on the player, opponent, or both.
  // When reviewing opponent performance, NEVER show "Retry Move" (that's only for the player's training flow).
  const meta = (walkData?.game_metadata || walkData?.gameMetadata || {}) as any;
  const playerColor: 'white' | 'black' | null = meta.player_color || null;
  const focusColor: 'white' | 'black' | 'both' | null = meta.focus_color || meta.focusColor || null;
  const reviewSubject: 'player' | 'opponent' | 'both' | null = meta.review_subject || meta.reviewSubject || null;
  const moveColor: 'white' | 'black' = move.color === 'w' ? 'white' : 'black';
  const allowRetry = !!playerColor && (focusColor ? focusColor === playerColor : reviewSubject !== 'opponent') && moveColor === playerColor;
    
    console.log('🎬 [executeWalkthroughStep] Move data:', {
      moveNumber: move.moveNumber,
      moveSan: move.move || move.san,
      hasColor: !!move.color,
      hasFen: !!move.fen
    });
    
    // Navigate to the move with animation when jumping between key moments
    await navigateToMove(move.moveNumber, true);
    
    let message = "";
    
    switch (type) {
      case 'opening':
        message = await generateOpeningAnalysis(move, walkData);
        break;
      case 'left_theory': {
        // First show the context message with review table
        const evalAtTheory = move.evalBefore ? `${move.evalBefore > 0 ? '+' : ''}${(move.evalBefore / 100).toFixed(2)}` : '0.00';
        const pre = await generateWalkthroughPreCommentary(type, move, walkData, allowRetry, false, stepIndex);
        // Use ":" (not ".") to avoid triggering PGN sequence parsing on messages like "10. Qb3"
        const theoryMessage = `**Move ${move.moveNumber}: ${move.move} - Left Opening Theory**\n\n${pre}\n\n${move.color === 'w' ? 'White' : 'Black'} played **${move.move}**, departing from known opening theory. The evaluation was ${evalAtTheory} before this move.`;
        
        const tableDataTheory = contextData ? generateReviewTableData(contextData) : ((window as any).__walkthroughTableData || null);
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: theoryMessage,
          meta: tableDataTheory ? { gameReviewTable: tableDataTheory } : undefined,
          timestamp: new Date()
        }]);
        
        // Analyze immediately
        await analyzeMoveAtPosition(move, true);
        
        // Return early to skip the normal message handling
        setMessages(prev => [...prev, {
          role: 'button',
          content: '',
          buttonAction: 'NEXT_STEP',
          buttonLabel: `Next Step (${stepNum}/${totalSteps})`
        }]);
        return;
      }
      case 'blunder':
      case 'mistake':
      case 'inaccuracy': {
        const cpLoss = Math.round(move.cpLoss || 0);
        const severity = move.quality === 'blunder' ? 'Blunder' : move.quality === 'mistake' ? 'Mistake' : 'Inaccuracy';
        const accuracyPct = typeof move.accuracy === 'number' ? (move.accuracy.toFixed ? move.accuracy.toFixed(1) : move.accuracy) : 'n/a';
        const pre = await generateWalkthroughPreCommentary(type, move, walkData, allowRetry, false, stepIndex);
        
        // Don't spoil the best move - just describe the position and loss
        // Use ":" (not ".") to avoid triggering PGN sequence parsing on messages like "10. Qb3"
        const errorMessage = `**Move ${move.moveNumber}: ${move.move} – ${severity}.**\n\n${pre}\n\n${move.color === 'w' ? 'White' : 'Black'} played **${move.move}**, allowing a swing of ${cpLoss}cp (accuracy ${accuracyPct}%).`;
        
        const tableDataError = contextData ? generateReviewTableData(contextData) : ((window as any).__walkthroughTableData || null);
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: errorMessage,
          meta: tableDataError ? { gameReviewTable: tableDataError } : undefined,
          timestamp: new Date()
        }]);
        
        // Analyze immediately
        await analyzeMoveAtPosition(move, true);
        
        if (allowRetry) {
          // Store retry data and add retry button
          setRetryMoveData(move);
          const retryButtonId = `retry_${move.moveNumber}_${Date.now()}`;
          setMessages(prev => [...prev, {
            role: 'button',
            content: '',
            buttonAction: 'RETRY_MOVE',
            buttonLabel: `Retry Move ${move.moveNumber}`,
            id: retryButtonId,
            meta: { buttonId: retryButtonId }
          }, {
            role: 'button',
            content: '',
            buttonAction: 'NEXT_STEP',
            buttonLabel: `Skip (${stepNum}/${totalSteps})`
          }]);
          return;
        }

        // Opponent/both-side review: no retry, just continue
        setMessages(prev => [...prev, {
          role: 'button',
          content: '',
          buttonAction: 'NEXT_STEP',
          buttonLabel: `Next Step (${stepNum}/${totalSteps})`
        }]);
        return;
      }
      case 'critical': {
        const actualMove = move.move || move.san;
        const gapToSecond = move.gapToSecondBest != null ? Math.round(move.gapToSecondBest) : null;
        const gapText = gapToSecond != null ? ` (only ${gapToSecond}cp better than the alternatives)` : '';
        const pre = await generateWalkthroughPreCommentary(type, move, walkData, allowRetry, false, stepIndex);
        const criticalMessage = `**Move ${move.moveNumber}: ${actualMove} – Critical Move!**\n\n${pre}\n\n${side} found **${actualMove}**, the lone move that held the evaluation${gapText}.`;
        
        const tableDataCritical = contextData ? generateReviewTableData(contextData) : ((window as any).__walkthroughTableData || null);
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: criticalMessage,
          meta: tableDataCritical ? { gameReviewTable: tableDataCritical } : undefined,
          timestamp: new Date()
        }]);
        
        // Analyze immediately
        await analyzeMoveAtPosition(move, true);
        setMessages(prev => [...prev, {
          role: 'button',
          content: '',
          buttonAction: 'NEXT_STEP',
          buttonLabel: `Next Step (${stepNum}/${totalSteps})`
        }]);
        return;
      }
      case 'missed_win': {
        const evalBefore = move.evalBefore || 0;
        const missedGap = move.gapToSecondBest || 0;
        const pre = await generateWalkthroughPreCommentary(type, move, walkData, allowRetry, false, stepIndex);
        // Use ":" (not ".") to avoid triggering PGN sequence parsing on messages like "10. Qb3"
        const missedWinMessage = `**Move ${move.moveNumber}: ${move.move} - Missed Win**\n\n${pre}\n\n${move.color === 'w' ? 'White' : 'Black'} played **${move.move}** in a winning position (${(evalBefore / 100).toFixed(2)}), but missed a stronger continuation.`;
        
        const tableDataMissed = contextData ? generateReviewTableData(contextData) : ((window as any).__walkthroughTableData || null);
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: missedWinMessage,
          meta: tableDataMissed ? { gameReviewTable: tableDataMissed } : undefined,
          timestamp: new Date()
        }]);
        
        // Analyze immediately
        await analyzeMoveAtPosition(move, true);
        setMessages(prev => [...prev, {
          role: 'button',
          content: '',
          buttonAction: 'NEXT_STEP',
          buttonLabel: `Next Step (${stepNum}/${totalSteps})`
        }]);
        return;
      }
      case 'advantage_shift':
        const evalChange = move.evalAfter - move.evalBefore;
        const crossedThreshold = 
          move.crossed300 ? '±300cp (decisive)' :
          move.crossed200 ? '±200cp (clear advantage)' :
          move.crossed100 ? '±100cp (slight advantage)' : 'significant';
        const pre = await generateWalkthroughPreCommentary(type, move, walkData, allowRetry, false, stepIndex);
        // Use ":" (not ".") to avoid triggering PGN sequence parsing on messages like "10. Qb3"
        const shiftSummary = `**Move ${move.moveNumber}: ${move.move} – Advantage Shift**\n\n${pre}\n\n${side} played **${move.move}**, crossing the ${crossedThreshold} threshold. The evaluation shifted from ${(move.evalBefore / 100).toFixed(2)} to ${(move.evalAfter / 100).toFixed(2)} (${evalChange > 0 ? '+' : ''}${(evalChange / 100).toFixed(2)}).`;
        
        // Add auto-generated message with review table
        const tableData = contextData ? generateReviewTableData(contextData) : ((window as any).__walkthroughTableData || null);
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: shiftSummary,
          meta: tableData ? { gameReviewTable: tableData } : undefined,
          timestamp: new Date()
        }]);
        
        // Analyze immediately
        await analyzeMoveAtPosition(move, true);
        
        // Add next button
        setMessages(prev => [...prev, {
          role: 'button',
          content: '',
          buttonAction: 'NEXT_STEP',
          buttonLabel: `Next Step (${stepNum}/${totalSteps})`
        }]);
        return;
      case 'best_move': {
        const actualMove = move.move || move.san;
        const evalBefore = move.evalBefore ? `${move.evalBefore > 0 ? '+' : ''}${(move.evalBefore / 100).toFixed(2)}` : '0.00';
        const pre = await generateWalkthroughPreCommentary(type, move, walkData, allowRetry, false, stepIndex);
        const bestMoveMessage = `**Move ${move.moveNumber}: ${actualMove} – Excellent Move!**\n\n${pre}\n\n${side} found **${actualMove}**, the best move in the position (eval ${evalBefore}).`;
        
        const tableDataBest = contextData ? generateReviewTableData(contextData) : ((window as any).__walkthroughTableData || null);
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: bestMoveMessage,
          meta: tableDataBest ? { gameReviewTable: tableDataBest } : undefined,
          timestamp: new Date()
        }]);
        
        await analyzeMoveAtPosition(move, true);
        setMessages(prev => [...prev, {
          role: 'button',
          content: '',
          buttonAction: 'NEXT_STEP',
          buttonLabel: `Next Step (${stepNum}/${totalSteps})`
        }]);
        return;
      }
      case 'tactical': {
        const actualMove = move.move || move.san;
        const cpLoss = Math.round(move.cpLoss || 0);
        const tacticalMessage = cpLoss > 0 
          ? `**Move ${move.moveNumber}. ${actualMove} – Missed Tactic!**\n\n${side} played **${actualMove}**, but there was a tactical opportunity here (${cpLoss}cp lost). Can you spot what was missed?`
          : `**Move ${move.moveNumber}. ${actualMove} – Tactical Moment!**\n\n${side} found **${actualMove}** in a tactical position. Let's analyze the key ideas.`;
        
        const tableDataTact = contextData ? generateReviewTableData(contextData) : ((window as any).__walkthroughTableData || null);
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: tacticalMessage,
          meta: tableDataTact ? { gameReviewTable: tableDataTact } : undefined,
          timestamp: new Date()
        }]);
        
        await analyzeMoveAtPosition(move, true);
        
        // If it's a missed tactic, offer retry
        if (cpLoss > 50) {
          setRetryMoveData(move);
          const retryButtonId = `retry_${move.moveNumber}_${Date.now()}`;
          setMessages(prev => [...prev, {
            role: 'button',
            content: '',
            buttonAction: 'RETRY_MOVE',
            buttonLabel: `Retry Move ${move.moveNumber}`,
            id: retryButtonId,
            meta: { buttonId: retryButtonId }
          }, {
            role: 'button',
            content: '',
            buttonAction: 'NEXT_STEP',
            buttonLabel: `Skip (${stepNum}/${totalSteps})`
          }]);
        } else {
          setMessages(prev => [...prev, {
            role: 'button',
            content: '',
            buttonAction: 'NEXT_STEP',
            buttonLabel: `Next Step (${stepNum}/${totalSteps})`
          }]);
        }
        return;
      }
      case 'phase_transition': {
        const actualMove = move.move || move.san;
        const phase = move.phase || 'middlegame';
        const transitionMessage = `**Move ${move.moveNumber}. ${actualMove} – Entering ${phase.charAt(0).toUpperCase() + phase.slice(1)}**\n\n${side} played **${actualMove}**, marking the transition to the ${phase}. The character of the position is changing.`;
        
        const tableDataPhase = contextData ? generateReviewTableData(contextData) : ((window as any).__walkthroughTableData || null);
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: transitionMessage,
          meta: tableDataPhase ? { gameReviewTable: tableDataPhase } : undefined,
          timestamp: new Date()
        }]);
        
        await analyzeMoveAtPosition(move, true);
        setMessages(prev => [...prev, {
          role: 'button',
          content: '',
          buttonAction: 'NEXT_STEP',
          buttonLabel: `Next Step (${stepNum}/${totalSteps})`
        }]);
        return;
      }
      case 'highlight': {
        // Generic highlight for LLM-selected moments that don't fit other categories
        const actualMove = move.move || move.san;
        const queryIntent = step.queryIntent || 'general';
        const cpLoss = Math.round(move.cpLoss || 0);
        const timeSpent = move.timeSpent ? `${move.timeSpent.toFixed(1)}s` : null;
        
        // Generate context-aware message based on query intent
        let highlightMessage = `**Move ${move.moveNumber}. ${actualMove}**\n\n`;
        if (queryIntent === 'time_analysis' && timeSpent) {
          highlightMessage += `${side} spent **${timeSpent}** on this move.`;
        } else if (queryIntent === 'blunder_review' && cpLoss > 0) {
          highlightMessage += `${side} played **${actualMove}**, losing ${cpLoss}cp.`;
        } else if (queryIntent === 'best_moves') {
          highlightMessage += `${side} found **${actualMove}**, one of the best moves in the game.`;
        } else {
          highlightMessage += `${side} played **${actualMove}**.`;
        }
        
        const tableDataHighlight = contextData ? generateReviewTableData(contextData) : ((window as any).__walkthroughTableData || null);
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: highlightMessage,
          meta: tableDataHighlight ? { gameReviewTable: tableDataHighlight } : undefined,
          timestamp: new Date()
        }]);
        
        await analyzeMoveAtPosition(move, true);
        
        // Offer retry if significant loss
        if (cpLoss > 100) {
          setRetryMoveData(move);
          const retryButtonId = `retry_${move.moveNumber}_${Date.now()}`;
          setMessages(prev => [...prev, {
            role: 'button',
            content: '',
            buttonAction: 'RETRY_MOVE',
            buttonLabel: `Retry Move ${move.moveNumber}`,
            id: retryButtonId,
            meta: { buttonId: retryButtonId }
          }, {
            role: 'button',
            content: '',
            buttonAction: 'NEXT_STEP',
            buttonLabel: `Skip (${stepNum}/${totalSteps})`
          }]);
        } else {
          setMessages(prev => [...prev, {
            role: 'button',
            content: '',
            buttonAction: 'NEXT_STEP',
            buttonLabel: `Next Step (${stepNum}/${totalSteps})`
          }]);
        }
        return;
      }
      case 'middlegame':
        message = await generateMiddlegameAnalysis(move, walkData);
        break;
      case 'final':
        message = await generateFinalAnalysis(move, walkData);
        break;
    }
    
    if (message && !message.includes("Let me analyze")) {
      // Add message with review table data
      const tableDataGeneral = contextData ? generateReviewTableData(contextData) : ((window as any).__walkthroughTableData || null);
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: message,
        meta: tableDataGeneral ? { gameReviewTable: tableDataGeneral } : undefined,
        timestamp: new Date()
      }]);
      
      // Add Next button
      setMessages(prev => [...prev, {
        role: 'button',
        content: '',
        buttonAction: 'NEXT_STEP',
        buttonLabel: `Next Step (${stepNum}/${totalSteps})`
      }]);
    } else if (message) {
      // Message already added by analysis function, no wait needed
      // Add Next button
      setMessages(prev => [...prev, {
        role: 'button',
        content: '',
        buttonAction: 'NEXT_STEP',
        buttonLabel: `Next Step (${stepNum}/${totalSteps})`
      }]);
    }
  }

  async function navigateToMove(moveNumber: number, animate: boolean = false) {
    const mainLine = moveTree.getMainLine();
    const targetNode = mainLine.find((n: any) => n.moveNumber === moveNumber);
    
    if (!targetNode) return;
    
    const targetIndex = mainLine.findIndex((n: any) => n.moveNumber === moveNumber);
    
    // Find current position in main line
    let currentIndex = -1;
    let currentNode = moveTree.currentNode;
    while (currentNode && currentIndex === -1) {
      currentIndex = mainLine.findIndex((n: any) => n === currentNode);
      if (currentIndex === -1 && currentNode.parent) {
        currentNode = currentNode.parent;
      } else {
        break;
      }
    }
    if (currentIndex === -1) currentIndex = 0; // Default to start if not found
    
    if (animate && targetIndex !== currentIndex && targetIndex > currentIndex) {
      // Animate through moves quickly from current position to target
      const newTree = moveTree.clone();
      
      // Navigate to current position first
      newTree.goToStart();
      for (let i = 0; i < currentIndex; i++) {
        newTree.goForward();
      }
      
      // Animate forward to target
      for (let i = currentIndex; i < targetIndex; i++) {
        newTree.goForward();
        const currentNode = mainLine[i + 1];
        if (currentNode) {
          setMoveTree(newTree.clone());
          setFen(currentNode.fen);
          const tempGame = new Chess(currentNode.fen);
          setGame(tempGame);
          // Small delay to show progression (50ms per move for quick animation)
          await new Promise(resolve => setTimeout(resolve, 50));
        }
      }
    } else {
      // Instant jump - no animation
      const newTree = moveTree.clone();
      newTree.goToStart();
      for (let i = 0; i < targetIndex; i++) {
        newTree.goForward();
      }
      
      setMoveTree(newTree);
      setFen(targetNode.fen);
      const tempGame = new Chess(targetNode.fen);
      setGame(tempGame);
    }
  }

  async function generateOpeningAnalysis(move: any, contextData?: any): Promise<string> {
    const context = contextData || walkthroughData || {};
    const openingName = context.openingName || 'Unknown opening';
    const accuracyStats = context.accuracyStats || {};
    const openingStats = accuracyStats.opening || { white: 0, black: 0 };
    const sideAccuracyRaw = move.color === 'w' ? openingStats.white : openingStats.black;
    const sideAccuracy = typeof sideAccuracyRaw === 'number' ? sideAccuracyRaw : 0;
    const accuracyDisplay = sideAccuracy.toFixed ? sideAccuracy.toFixed(1) : sideAccuracy;
    
    console.log('📖 [generateOpeningAnalysis] Using context:', {
      openingName,
      sideAccuracy,
      move_color: move.color,
      has_contextData: !!contextData
    });
    const safePrompt = `Analyze the opening phase of this chess game:

Opening: ${openingName}

Side to move accuracy: ${accuracyDisplay}%

Write 2-3 sentences about:
1. The opening choice and its key themes
2. How well the side to move handled the opening

Be conversational and educational. Avoid restating move lists; focus on ideas.`;

    try {
      const { content } = await callLLM([
        { role: "system", content: "You are a helpful chess coach." },
        { role: "user", content: safePrompt }
      ], 0.7, "gpt-4o-mini", false);  // NO TOOLS - just text response
      return `**Opening: ${openingName}**\n\n${content}`;
    } catch (err) {
      return `**Opening: ${openingName}**\n\nOpening accuracy: ${accuracyDisplay}%`;
    }
  }

  async function generateMiddlegameAnalysis(move: any, contextData?: any): Promise<string> {
    const context = contextData || walkthroughData || {};
    const accuracyStats = context.accuracyStats || {};
    const middlegameStats = accuracyStats.middlegame || { white: 0, black: 0 };
    const sideAccuracyRaw = move.color === 'w' ? middlegameStats.white : middlegameStats.black;
    const sideAccuracy = typeof sideAccuracyRaw === 'number' ? sideAccuracyRaw : 0;
    const accuracyDisplay = sideAccuracy.toFixed ? sideAccuracy.toFixed(1) : sideAccuracy;
    
    const tempGame = new Chess(move.fen);
    const board = tempGame.board();
    let material = { white: 0, black: 0 };
    const pieceValues: Record<string, number> = { p: 1, n: 3, b: 3, r: 5, q: 9, k: 0 };
    
    board.forEach((row: any) => {
      row.forEach((square: any) => {
        if (square) {
          const value = pieceValues[square.type] ?? 0;
          if (square.color === 'w') material.white += value;
          else material.black += value;
        }
      });
    });
    
    const materialDiff = material.white - material.black;
    const materialStr =
      materialDiff > 0 ? `White +${materialDiff}` :
      materialDiff < 0 ? `Black +${Math.abs(materialDiff)}` :
      'Equal';
    
    const evalStr = move.evalAfter ? `${move.evalAfter > 0 ? '+' : ''}${(move.evalAfter / 100).toFixed(2)}` : '0.00';
    
    return `**Middlegame Transition (Move ${move.moveNumber})**\n\nBy move ${move.moveNumber}, the game has entered the middlegame. The evaluation is ${evalStr}.\n\n**Material Balance:** ${materialStr}\n**Middlegame Accuracy:** ${accuracyDisplay}%\n\nLet's break down the critical themes of this middlegame position.`;
  }

  async function generateFinalAnalysis(move: any, contextData?: any): Promise<string> {
    const context = contextData || walkthroughData || {};
    const avgWhiteRaw = typeof context.avgWhiteAccuracy === 'number' ? context.avgWhiteAccuracy : 0;
    const avgBlackRaw = typeof context.avgBlackAccuracy === 'number' ? context.avgBlackAccuracy : 0;
    const averageDisplay = move.color === 'w' ? (avgWhiteRaw.toFixed ? avgWhiteRaw.toFixed(1) : avgWhiteRaw) : (avgBlackRaw.toFixed ? avgBlackRaw.toFixed(1) : avgBlackRaw);
    const accuracyStats = context.accuracyStats || {};
    const endgameStats = accuracyStats.endgame || { white: 0, black: 0 };
    const sideEndgameRaw = move.color === 'w' ? endgameStats.white : endgameStats.black;
    const sideEndgame = typeof sideEndgameRaw === 'number' ? sideEndgameRaw : 0;
    const endgameDisplay = sideEndgame.toFixed ? sideEndgame.toFixed(1) : sideEndgame;
    const gameTags = Array.isArray(context.gameTags) ? context.gameTags : [];
    
    const finalEval = move.evalAfter ?? 0;
    let result = "The game ended in a drawn position";
    if (finalEval > 300) result = "White won this game";
    else if (finalEval < -300) result = "Black won this game";
    
    const finalEvalStr = `${finalEval > 0 ? '+' : ''}${(finalEval / 100).toFixed(2)}`;
    const tags = gameTags.map((t: any) => t?.name || t).filter(Boolean).join(", ") || "Balanced game";
    
    return `**Final Position (Move ${move.moveNumber})**\n\n${result} with a final evaluation of ${finalEvalStr}.\n\n**Overall Accuracy (side to move):** ${averageDisplay}%\n**Endgame Accuracy:** ${endgameDisplay}%\n**Game Tags:** ${tags}\n\nLet me summarise the decisive elements of this endgame.`;
  }

  async function analyzeMoveAtPosition(move: any, skipLLMGeneration: boolean = false) {
    const fenBefore = move.fenBefore || move.fen_before || move._fullRecord?.fen_before;
    const fenAfter = move.fen;
    if (!fenBefore) {
      console.warn('[Walkthrough] Missing fenBefore for move, skipping analysis', move);
      addSystemMessage("Unable to analyze this move because the preceding position is unavailable.");
      return;
    }
    if (!fenAfter) {
      console.warn('[Walkthrough] Missing fen (after) for move, skipping analysis', move);
      addSystemMessage("Unable to analyze this move because the resulting position is unavailable.");
      return;
    }

    // Setup board and visuals (no analyze_move call; we already have review metadata for this move)
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
          arrows: [{ from: fromSquare, to: toSquare, color: 'rgba(34, 139, 34, 0.7)' }],
          highlights: []
        }));
      }
    } catch (error) {
      console.error("Failed to set board position:", error);
    }

    // SKIP LLM generation if explicitly told to (called from walkthrough) or if walkthrough is active
    // This prevents duplicate messages during game review walkthroughs
    if (skipLLMGeneration || walkthroughActive) {
      console.log('[Walkthrough] Skipping on-the-spot LLM commentary - using pre-generated commentary instead');
      return; // Exit early - board is set up, but no LLM call needed
    }

    // Route straight to LLM for a natural coach note (skip analyze_move + structured templates)
    // This only runs when NOT in walkthrough context
    try {
      const side = move.color === 'w' ? 'White' : move.color === 'b' ? 'Black' : 'Side';
      const moveSan = move.move || move.san || '?';
      const cpLoss = Math.round(move.cpLoss ?? move.cp_loss ?? 0);
      const accuracyRaw = move.accuracy ?? move.accuracy_pct ?? null;
      const accuracyPct = typeof accuracyRaw === 'number' ? accuracyRaw : null;
      const evalBefore = move.evalBefore ?? move.eval_before ?? null;
      const evalAfter = move.evalAfter ?? move.eval_after ?? null;

      const evalText =
        (typeof evalBefore === 'number' && typeof evalAfter === 'number')
          ? `Eval: ${(evalBefore / 100).toFixed(2)} → ${(evalAfter / 100).toFixed(2)}`
          : '';

      const detailParts: string[] = [];
      if (Number.isFinite(cpLoss) && cpLoss > 0) detailParts.push(`swing ${cpLoss}cp`);
      if (typeof accuracyPct === 'number') detailParts.push(`accuracy ${accuracyPct.toFixed(1)}%`);
      const detail = detailParts.length ? `(${detailParts.join(', ')})` : '';

      const chatContext = getRecentChatContext(3);
      const prompt = `Review this move: ${moveSan} (move ${move.moveNumber || '?'}, ${side} to move played it).\n\nPosition BEFORE the move (FEN): ${fenBefore}\nPosition AFTER the move (FEN): ${fenAfter}\n${evalText}\n${detail}\n\nWrite a short coach note (2–3 sentences): what was the idea, why it was passive/active, and what general improvement to look for next. Do NOT use rigid templates (no “Verdict:” / “Candidate Moves:” / “Critical Line:”). Do NOT reveal or name the engine’s best move in SAN.`;

      const llmResponse = await callLLM(
        [
          { role: "system", content: "You are a chess coach. Be concise, specific, and natural. No templates. No move spoilers." },
          ...chatContext,
          { role: "user", content: prompt },
        ],
        0.6,
        "gpt-4o-mini",
        false  // Disable tools to prevent setup_position error (we just need a coach note, not tool calls)
      );

      const llmContent = (llmResponse?.content || "").trim();
      if (!llmContent) {
        throw new Error("Empty LLM response for move review");
      }

      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: llmContent,
          meta: {
            reviewMove: {
              moveNumber: move.moveNumber,
              move: moveSan,
              fenBefore,
              fenAfter,
              cpLoss,
              accuracy: accuracyPct
            }
          }
        }
      ]);
    } catch (err: any) {
      console.error("Move analysis failed:", err);
      addSystemMessage(`Move review failed: ${err instanceof Error ? err.message : String(err)}`);
    }
  }

  async function analyzeCurrentPosition() {
    // Analyze the current position
    try {
      const response = await fetch(`${getBackendBase()}/analyze_position?fen=${encodeURIComponent(fen)}&lines=3&depth=12`);
      
      if (!response.ok) {
        throw new Error(`Backend returned ${response.status}`);
      }
      
      const data = await response.json();
      
      const evalCp = data.eval_cp || 0;
      const evalPawns = (evalCp / 100).toFixed(2);
      
      let message = `**Position Analysis**\n\nEval: ${evalCp > 0 ? '+' : ''}${evalPawns} pawns\n\n`;
      
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
    const evalRawValues: Array<number | null> = moves.map((m: any) => {
      const v = m?.evalAfter;
      return typeof v === "number" && Number.isFinite(v) ? v / 100 : null; // pawns
    });
    const evalNums = evalRawValues.filter((v): v is number => typeof v === "number" && Number.isFinite(v));
    const evalMin = evalNums.length ? Math.min(...evalNums) : 0;
    const evalMax = evalNums.length ? Math.max(...evalNums) : 0;
    const evalRange = evalMax - evalMin;
    const evalNormalizedValues: Array<number | null> = evalRawValues.map((v) => {
      if (v == null || !Number.isFinite(v)) return null;
      if (evalRange <= 1e-9) return 50;
      return ((v - evalMin) / evalRange) * 100;
    });

    const evalGraphData: ChatGraphData = {
      graph_id: "eval_graph",
      series: [
        {
          id: "eval_pawns",
          name: "Eval (pawns)",
          color: "#60a5fa",
          rawValues: evalRawValues,
          normalizedValues: evalNormalizedValues,
        },
      ],
      xLabels: moves.map((m: any, idx: number) => {
        const mn = m?.moveNumber;
        const mv = m?.move;
        return `${typeof mn === "number" ? mn : idx + 1}${m?.color === "b" ? "..." : "."} ${mv ?? ""}`.trim();
      }),
      grouping: "game",
    };

    setMessages(prev => [...prev, {
      role: 'graph',
      content: '',
      graphData: evalGraphData
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
      addAssistantMessage(`**Excellent!** You found the best move **${bestMove}**. That avoids the ${Math.round(retryMoveData.cpLoss || 0)}cp drop caused by **${retryMoveData.move}**.`);
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
      // Call analyze_move API to get analysis data
      try {
        const response = await fetch(
          `${getBackendBase()}/analyze_move?fen=${encodeURIComponent(retryMoveData.fenBefore)}&move_san=${encodeURIComponent(moveSan)}&depth=18`,
          { method: 'POST' }
        );
        
        if (response.ok) {
          const analyzeResult = await response.json();
          
          // Format the tool result manually (since we're not using tools)
          const playedDesc = analyzeResult.played_move_description || {};
          const uniqueTags = analyzeResult.unique_best_tag_descriptions || [];
          const neglectedTags = analyzeResult.neglected_tag_descriptions || [];
          
          // Build description of what played move did
          let playedWhat = "";
          if (typeof playedDesc === 'object' && playedDesc.tags_gained && playedDesc.tags_gained.length > 0) {
            playedWhat = playedDesc.tags_gained[0];
          } else if (typeof playedDesc === 'object' && playedDesc.tags_lost && playedDesc.tags_lost.length > 0) {
            playedWhat = `fixed ${playedDesc.tags_lost[0]}`;
          } else {
            playedWhat = "made a positional adjustment";
          }
          
          // Build what it neglected
          let neglectedWhat = "";
          if (neglectedTags.length > 0) {
            neglectedWhat = neglectedTags[0];
          } else if (uniqueTags.length > 0) {
            neglectedWhat = uniqueTags[0];
          } else {
            neglectedWhat = "a more important consideration";
          }
          
          // Call LLM to generate natural feedback based on the analysis
          const llmMessages: any[] = [
            {
              role: 'system',
              content: 'You are a chess coach providing feedback on move attempts. When a move is wrong, provide helpful, encouraging hints without revealing the best move. Be concise (1-2 sentences).'
            },
            {
              role: 'user',
              content: `I tried move ${moveSan} in this position. The move ${playedWhat}, but it neglects ${neglectedWhat}. Provide feedback on what this move accomplished and what it missed, without revealing the best move.`
            }
          ];
          
          // Call LLM to generate feedback (without tools)
          const llmResponse = await callLLM(llmMessages, 0.7, "gpt-4o-mini", false);
          
          if (llmResponse.content) {
            addAssistantMessage(llmResponse.content);
          } else {
            // Fallback if LLM fails
            addAssistantMessage(`**Not quite.** You played **${moveSan}**, but there's a better move. Try to spot the key idea and attempt again.`);
          }
          
          // After LLM response is shown, reset board to retry position
          // Reset board to retry position
          const newGame = new Chess(retryMoveData.fenBefore);
          setGame(newGame);
          setFen(retryMoveData.fenBefore);
          
          // Add buttons
          setMessages(prev => [...prev, {
            role: 'button',
            content: '',
            buttonAction: 'SHOW_HINT',
            buttonLabel: 'Show Hint'
          }, {
            role: 'button',
            content: '',
            buttonAction: 'SHOW_SOLUTION',
            buttonLabel: 'Show Solution'
          }]);
        } else {
          // Fallback if API call fails
          addAssistantMessage(`**Not quite.** You played **${moveSan}**, but there's a better move. Try to spot the key idea and attempt again.`);
          
          // Reset board after fallback message
          const newGame = new Chess(retryMoveData.fenBefore);
          setGame(newGame);
          setFen(retryMoveData.fenBefore);
          
          // Add buttons
          setMessages(prev => [...prev, {
            role: 'button',
            content: '',
            buttonAction: 'SHOW_HINT',
            buttonLabel: 'Show Hint'
          }, {
            role: 'button',
            content: '',
            buttonAction: 'SHOW_SOLUTION',
            buttonLabel: 'Show Solution'
          }]);
        }
      } catch (error) {
        console.error("Failed to get move analysis:", error);
        // Fallback if API call fails
        addAssistantMessage(`**Not quite.** You played **${moveSan}**, but there's a better move. Try to spot the key idea and attempt again.`);
        
        // Reset board after fallback message
        const newGame = new Chess(retryMoveData.fenBefore);
        setGame(newGame);
        setFen(retryMoveData.fenBefore);
        
        // Add buttons
        setMessages(prev => [...prev, {
          role: 'button',
          content: '',
          buttonAction: 'SHOW_HINT',
          buttonLabel: 'Show Hint'
        }, {
          role: 'button',
          content: '',
          buttonAction: 'SHOW_SOLUTION',
          buttonLabel: 'Show Solution'
        }]);
      }
      
      return false;
    }
  }
  
  async function showRetryHint() {
    if (!retryMoveData) return;
    
    // Update hint button to show loading state
    setMessages(prev => prev.map(msg => 
      msg.buttonAction === 'SHOW_HINT'
        ? { ...msg, buttonLabel: 'Loading...', meta: { ...msg.meta, disabled: true, loading: true } }
        : msg
    ));
    
    try {
      const fenBefore = retryMoveData.fenBefore;
      const bestMove = retryMoveData.bestMove; // provided by review pipeline; MUST NOT be revealed
      const side = retryMoveData.color === 'w' ? 'White' : 'Black';

      const llmMessages: any[] = [
        {
          role: 'system',
          content: "You are a chess coach providing hints. Write 1–2 sentences. Never output SAN/uci. Never name the best move. Avoid lists."
        },
        {
          role: 'user',
          content:
            `Give me a hint for the best move in this position.\n\n` +
            `Position FEN (before the best move): ${fenBefore}\n` +
            `Side to move: ${side}\n\n` +
            `Hidden (DO NOT REVEAL): the best move is ${bestMove}\n\n` +
            `Hint goal: describe the key idea/pattern (development, tactics, pressure, prophylaxis, etc.) without telling the move.`
        }
      ];

      const llmResponse = await callLLM(llmMessages, 0.7, "gpt-4o-mini", false);
      const hint = (llmResponse.content || "").trim();
      if (!hint) throw new Error("Empty hint from LLM");
      addAssistantMessage(`💡 **Hint:** ${hint}`);
    } catch (error) {
      console.error("Failed to get hint:", error);
      addSystemMessage(`Hint failed: ${error instanceof Error ? error.message : String(error)}`);
    }
    
    // Disable the hint button and restore original text
    setMessages(prev => prev.map(msg => 
      msg.buttonAction === 'SHOW_HINT'
        ? { ...msg, buttonLabel: 'Show Hint', meta: { ...msg.meta, disabled: true, loading: false } }
        : msg
    ));
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
        arrows: [{ from: bestMove.from, to: bestMove.to, color: 'rgba(34, 139, 34, 0.7)' }],
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
          arrows: [{ from: fromSquare, to: toSquare, color: 'rgba(34, 139, 34, 0.7)' }],
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
      const response = await fetch(`${getBackendBase()}/review_game?pgn_string=${encodeURIComponent(cleanPgn)}&side_focus=${reviewSideFocus}&include_timestamps=true`, {
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
          buttonLabel: 'Start Guided Walkthrough'
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
      const response = await fetch(`${getBackendBase()}/generate_lesson`, {
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
            const posResponse = await fetch(`${getBackendBase()}/generate_positions?topic_code=${topicCode}&count=${positionsPerTopic}`, {
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
      enterLessonMode();
      
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
      const response = await fetch(`${getBackendBase()}/generate_opening_lesson`, {
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
      
      enterLessonMode();
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
    setFen(fen);
    setGame(newGame);
    setBoardOrientation(newGame.turn() === 'w' ? 'white' : 'black');
    
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
          buttonLabel: 'Previous Position',
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
    
    let moveCheckSucceeded = false;
    let isNetworkError = false;
    
    try {
      const lessonId = currentLesson.plan.lesson_id;
      
      const response = await fetch(
        `${getBackendBase()}/check_opening_move?fen=${encodeURIComponent(currentFen)}&move_san=${moveSan}&lesson_id=${lessonId}`,
        { method: "POST" }
      );
      if (response.status === 404) {
        addSystemMessage("This lesson snapshot has expired. Please generate a fresh opening lesson and try again.");
        return;
      }
      if (!response.ok) {
        // Check if it's a network/server error
        if (response.status >= 500 || response.status === 0) {
          isNetworkError = true;
          throw new Error("Connection issue - server unavailable");
        }
        throw new Error("Failed to check opening move");
      }
      const result = await response.json();
      moveCheckSucceeded = true;
      
      if (result.is_popular) {
        addSystemMessage(`✅ ${result.feedback}`);

        if (lessonProgress.current === lessonProgress.total - 1) {
          addSystemMessage("🎉 Congratulations! You've completed the opening lesson!");
          setLessonMode(false);
        }
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
      if (isNetworkError || error.message?.includes("Connection") || error.message?.includes("network")) {
        addSystemMessage("⚠️ Connection issue detected. Continuing with lesson anyway...");
      } else {
        addSystemMessage(`⚠️ Could not verify move popularity: ${error.message}`);
      }
    }
    
    // Always try to continue with auto-play response, even if move check failed
    // This ensures the lesson flow continues smoothly even with connection issues
    if (lessonMode && currentLesson?.type === "opening" && !waitingForEngine) {
      try {
        await autoPlayOpeningResponse(currentFen, moveSan);
        // Note: restoreOpeningLessonVisuals is called inside autoPlayOpeningResponse
        // with the correct FEN, so we don't need to call it again here
      } catch (autoPlayError: any) {
        console.error("Auto-play response error:", autoPlayError);
        if (autoPlayError.message?.includes("Connection") || autoPlayError.message?.includes("network") || autoPlayError.message?.includes("fetch")) {
          addSystemMessage("⚠️ Connection issue - AI response delayed. Please try again in a moment.");
        } else {
          addSystemMessage(`⚠️ Could not generate AI response: ${autoPlayError.message}`);
        }
      }
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
  
  const parseLessonCandidate = (entry: any): SnapshotCandidate | null => {
    if (!entry) return null;
    if (typeof entry === "string") {
      return { san: entry };
    }
    if (typeof entry === "object" && entry.san) {
      return {
        san: entry.san,
        pop: entry.popularity ?? entry.pop,
        score: entry.score ?? entry.win_rate,
      };
    }
    return null;
  };

  const buildLessonCueSnapshot = (pos: any): LessonCueSnapshot | null => {
    if (!pos?.fen) return null;
    const rawCandidates =
      (pos.popular_replies && pos.popular_replies.length
        ? pos.popular_replies
        : pos.candidates) || [];
    const parsed: SnapshotCandidate[] = rawCandidates
      .map(parseLessonCandidate)
      .filter((val: SnapshotCandidate | null): val is SnapshotCandidate => Boolean(val));
    if (!parsed.length) return null;
    const arrows: AnnotationArrow[] = [];
    const main = parsed[0];
    const fmtPercent = (value?: number) => {
      if (typeof value !== "number" || Number.isNaN(value)) return null;
      return `${Math.round(value * 100)}%`;
    };
    const describe = (candidate: SnapshotCandidate) => {
      const usage = fmtPercent(candidate.pop);
      const winRate = typeof candidate.score === "number" ? `${Math.round(candidate.score * 100)}%` : null;
      const parts = [usage ? `${usage} usage` : null, winRate ? `${winRate} score` : null].filter(Boolean);
      return parts.length ? `${candidate.san} (${parts.join(" • ")})` : candidate.san;
    };
    parsed.slice(0, 4).forEach((candidate: SnapshotCandidate, idx: number) => {
      try {
        const tempBoard = new Chess(pos.fen);
        const move = tempBoard.move(candidate.san);
        if (move?.from && move?.to) {
          arrows.push({
            from: move.from,
            to: move.to,
            color: idx === 0 ? LESSON_ARROW_COLORS.main : LESSON_ARROW_COLORS.alternate,
          });
        }
      } catch (err) {
        // Ignore parsing failures; still allow description
      }
    });
    if (!arrows.length) {
      return {
        arrows: [],
        description: [
          `Main line: ${describe(main)}`,
        parsed.slice(1, 4).length ? `Alternates: ${parsed.slice(1, 4).map(describe).join(", ")}` : "",
        ]
          .filter(Boolean)
          .join("\n"),
      };
    }
    const description = [
      `Main line: ${describe(main)}`,
      parsed.slice(1, 4).length ? `Alternates: ${parsed.slice(1, 4).map(describe).join(", ")}` : "",
    ]
      .filter(Boolean)
      .join("\n");
    return { arrows, description };
  };

  async function loadLessonPosition(pos: any, index: number, total: number) {
    setCurrentLessonPosition(pos);
    
    // Set board to position FEN
    setFen(pos.fen);
    const newGame = new Chess(pos.fen);
    setGame(newGame);
    const lessonPerspective =
      typeof pos.side === "string"
        ? (pos.side === "black" ? "black" : "white")
        : newGame.turn() === "w"
          ? "white"
          : "black";
    setBoardOrientation(lessonPerspective);
    
    // Reset move tree
    const newTree = new MoveTree();
    setMoveTree(newTree);
    setTreeVersion(v => v + 1);
    
    // Reset lesson line tracking
    setLessonMoveIndex(0);
    setIsOffMainLine(false);
    setMainLineFen(pos.fen);
    setLessonCueButtonActive(false);
    const cueSnapshot = buildLessonCueSnapshot(pos);
    setLessonCueSnapshot(cueSnapshot);
    setLessonArrows(cueSnapshot?.arrows || []);
    if (cueSnapshot?.description && currentLesson?.type !== "opening") {
      addAssistantMessage(`**Lines to know**\n${cueSnapshot.description}`);
    }
    
    const safeObjective =
      typeof pos.objective === "string"
        ? pos.objective
        : pos.objective?.text ||
          pos.objective?.title ||
          "Find the best continuation";
    const hintsList = Array.isArray(pos.hints) ? pos.hints : [];
    const normalizedHints = hintsList.map((hint: any) => {
      if (typeof hint === "string") return hint;
      if (hint && typeof hint === "object") {
        return hint.text || hint.hint || hint.note || JSON.stringify(hint);
      }
      return String(hint);
    });

    // Generate LLM introduction to the position
    const introPrompt = `You are teaching a chess lesson. Introduce this position to the student:

Topic: ${pos.topic_name || "Critical position"}
Objective: ${safeObjective}
Position: ${pos.fen}

Write 2-3 sentences to introduce this training position. Be encouraging and explain what they should look for. Do NOT reveal the specific moves to play.`;

    try {
      const introResult = await callLLM([
        { role: "system", content: "You are an encouraging chess coach." },
        { role: "user", content: introPrompt }
      ]);
      const introText = introResult?.content?.trim?.() || safeObjective;
      addAssistantMessage(`**📚 Lesson Position ${index + 1}/${total}**\n\n${introText}`);
    } catch (err) {
      addAssistantMessage(`**📚 Lesson Position ${index + 1}/${total}**\n\n${safeObjective}`);
    }
    
    // Show objective card in chat
    setTimeout(() => {
      const hintsSection =
        normalizedHints.length > 0
          ? normalizedHints.map((h: string) => `• ${h}`).join('\n')
          : "• Focus on the plan described above.";
      addSystemMessage(`💡 **Objective:** ${safeObjective}\n\n**Hints:**\n${hintsSection}`);
    }, 1000);
    
    // Add navigation buttons after a short delay
    setTimeout(() => {
      if (index > 0) {
        // Add "Previous Position" button
        setMessages(prev => [...prev, {
          role: 'button',
          content: '',
          buttonLabel: 'Previous Position',
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
      const attemptNumber = getLessonAttemptNumber(currentLessonPosition.id);
      
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
        respondToLessonMove({
          moveSan,
          expectedMove: idealLine[newIndex],
          attemptNumber,
          wasCorrect: true,
        });
        
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
        respondToLessonMove({
          moveSan,
          expectedMove,
          attemptNumber,
          wasCorrect: false,
        });
        const response = await fetch(`${getBackendBase()}/check_lesson_move?fen=${encodeURIComponent(currentFen)}&move_san=${encodeURIComponent(moveSan)}`, {
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
          `${getBackendBase()}/analyze_move?fen=${encodeURIComponent(currentFen)}&move_san=${encodeURIComponent(moveSan)}&depth=18`,
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
              const engineResponse = await fetch(`${getBackendBase()}/analyze_position?fen=${encodeURIComponent(currentPosition)}&lines=1&depth=16`);
              
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
  
  // Apply theme to document (client-side only)
  useEffect(() => {
    if (typeof document !== 'undefined') {
      document.documentElement.setAttribute('data-theme', theme);
    }
  }, [theme]);
  
  // Keyboard shortcuts (client-side only)
  useEffect(() => {
    if (typeof window === 'undefined') return;
    
    const handleKeyboard = (e: KeyboardEvent) => {
      // Ctrl/Cmd+K: Focus composer
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        const composer = document.querySelector('.hero-input, .bottom-input') as HTMLTextAreaElement;
        composer?.focus();
      }
      
      // B: Toggle board
      if (e.key === 'b' && !e.metaKey && !e.ctrlKey && !e.altKey) {
        const target = e.target as HTMLElement;
        if (target.tagName !== 'INPUT' && target.tagName !== 'TEXTAREA') {
          setBoardDockOpen(prev => !prev);
        }
      }
      
      // Ctrl/Cmd+L: Load game
      if ((e.metaKey || e.ctrlKey) && e.key === 'l') {
        e.preventDefault();
        setShowLoadGame(prev => !prev);
      }
      
      // Esc: Close modals
      if (e.key === 'Escape') {
        setShowHistory(false);
        setShowLoadGame(false);
      }
    };
    
    window.addEventListener('keydown', handleKeyboard);
    return () => window.removeEventListener('keydown', handleKeyboard);
  }, []);

  // Wrap handleMove for board interaction (includes lesson mode check if needed)
  const wrappedHandleMove = (from: string, to: string, promotion?: string) => {
    if (lessonMode) {
      clearLessonVisualsForMove();
    }
    const currentFenBeforeMove = fen;
    const tempGame = new Chess(fen);
    const move = tempGame.move({ from, to, promotion });
    if (!move) {
      addSystemMessage("Illegal move!");
      return;
    }

    const postMoveFen = tempGame.fen();

    if (lessonMode && lessonNodeId) {
      handleMove(from, to, promotion)
        .then(() => handleLessonTreeMove(move.san, postMoveFen, currentFenBeforeMove))
        .catch((err) => {
          console.error("Lesson move failed:", err);
        });
      return;
    }

    if (lessonMode && currentLessonPosition) {
      handleMove(from, to, promotion)
        .then(() => checkLessonMove(move.san, currentFenBeforeMove))
        .catch((err) => console.error("Lesson move failed:", err));
      return;
    }

    handleMove(from, to, promotion).catch((err) => console.error("Move failed:", err));
  };

  const lessonQueryFromText = (text?: string | null) => {
    if (!text) return undefined;
    let cleaned = text.trim();
    cleaned = cleaned.replace(/[".]/g, "");
    cleaned = cleaned.replace(/^teach me\s*/i, "");
    cleaned = cleaned.replace(/^teach em\s*/i, "");
    cleaned = cleaned.replace(/^to\s+play\s+/i, "");
    cleaned = cleaned.replace(/^how to\s+/i, "");
    cleaned = cleaned.replace(/^learn\s+/i, "");
    cleaned = cleaned.replace(/^play\s+/i, "");
    cleaned = cleaned.replace(/^about\s+/i, "");
    cleaned = cleaned.trim();
    return cleaned.length > 0 ? cleaned : undefined;
  };

  const openingAnnouncementRef = useRef<Set<string>>(new Set());

  const getOpeningPlanHint = (name: string, perspective: "White" | "Black") => {
    const lower = name.toLowerCase();
    if (lower.includes("sicilian")) {
      return perspective === "White"
        ? "Aim for rapid development, clamp down on d5, and be ready for kingside pawn storms."
        : "Contest the center with ...d5 or ...b5 and keep pressure along the c-file.";
    }
    if (lower.includes("italian") || lower.includes("giuoco")) {
      return perspective === "White"
        ? "Point your pieces toward f7 and use c3/d4 to open the center when prepared."
        : "Challenge White’s center with ...d5 or ...Na5 plans while watching the f7 square.";
    }
    if (lower.includes("french")) {
      return perspective === "White"
        ? "Use your space advantage, support e5, and build a kingside attack."
        : "Break down White’s center with ...c5 and ...f6, then trade into favorable endgames.";
    }
    if (lower.includes("caro-kann")) {
      return perspective === "White"
        ? "Keep the lead in development and pressure d5 before Black finishes setup."
        : "Stay solid, challenge the center with ...c5 or ...e5, and aim for good minor-piece play.";
    }
    if (lower.includes("king's indian") || lower.includes("kings indian")) {
      return perspective === "White"
        ? "Restrict kingside counterplay with queenside expansion and timely c4 breaks."
        : "Prepare ...f5 pawn storms and look for kingside attacking chances.";
    }
    return perspective === "White"
      ? "Maintain active development and use your central space to dictate the pace."
      : "Complete development efficiently and craft counterplay against White’s center.";
  };

  const handleLegacyGameReview = async () => {
    setShowRequestOptions(false);
    if (isLegacyReviewing) return;
    if (!pgn || !pgn.trim()) {
      addSystemMessage("Legacy review requires a PGN. Load or play a game first.");
      return;
    }
    setIsLegacyReviewing(true);
    addSystemMessage("Running legacy game review (direct API call)...");
    try {
      const result = await legacyReviewGame(pgn.trim());
      const reviewPayload = result?.review || result;
      const opening = reviewPayload?.game_metadata?.opening || reviewPayload?.opening?.name_final || "Unknown opening";
      const totalMoves = reviewPayload?.game_metadata?.total_moves ?? Math.floor((reviewPayload?.ply_records?.length || 0) / 2);
      const character = reviewPayload?.game_metadata?.game_character || reviewPayload?.summary?.character || "n/a";
      addAssistantMessage(
        `Legacy review complete.\n\nOpening: ${opening}\nMoves analyzed: ${totalMoves}\nCharacter: ${character}`,
        {
          review: reviewPayload,
          legacy_review: result,
          source: 'legacy_review_manual'
        }
      );
    } catch (err: any) {
      addSystemMessage(`Legacy review failed: ${err?.message || String(err)}`);
    } finally {
      setIsLegacyReviewing(false);
    }
  };

  const handleOpeningLessonResult = (payload: OpeningLessonResponse) => {
    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent("startOpeningLesson", { detail: payload }));
    }
  };

  const handleGenerateOpeningLesson = async (source: "button" | "intent", explicitQuery?: string) => {
    pendingOpeningLessonQueryRef.current = undefined;
    if (!user?.id) {
      addSystemMessage("Sign in to generate personalized opening lessons.");
      return;
    }
    if (isGeneratingLesson) {
      addSystemMessage("An opening lesson is already being prepared.");
      return;
    }

    setShowRequestOptions(false);
    setIsGeneratingLesson(true);

    try {
      let inferredQuery = explicitQuery?.trim();
      let lookupName: string | undefined;
      let lookupEco: string | undefined;
      const sanitizedQuery = lessonQueryFromText(inferredQuery);
      if (sanitizedQuery) {
        inferredQuery = sanitizedQuery;
      }

      if (!inferredQuery && fen) {
        try {
          const lookup = await openingLookup(fen);
          lookupName = lookup?.name;
          lookupEco = lookup?.eco;
        } catch (err) {
          console.warn("Opening lookup failed:", err);
        }
      }

      const displayName = inferredQuery || lookupName || "this opening";
      const announcement = `Generating opening lesson for ${displayName}...`;
      addAutomatedMessage(announcement);

      const lessonResponse = await generateOpeningLesson({
        userId: user.id,
        chatId: currentThreadId,
        openingQuery: inferredQuery || lookupName,
        fen,
        eco: lookupEco,
        orientation: boardOrientation,
      });

      handleOpeningLessonResult(lessonResponse);
    } catch (err: any) {
      addSystemMessage(`Opening lesson failed: ${err?.message || String(err)}`);
    } finally {
      setIsGeneratingLesson(false);
    }
  };

  async function generateBatchWalkthroughCommentary(sequence: any[], walkData: any): Promise<Map<number, string>> {
    console.log('📝 [Batch Commentary] Generating commentary for', sequence.length, 'steps');
    const commentaryMap = new Map<number, string>();
    
    // Filter out steps that don't need commentary (opening has its own analysis, final doesn't need commentary)
    const stepsNeedingCommentary = sequence
      .map((step, index) => ({ step, index }))
      .filter(({ step }) => step.type !== 'opening' && step.type !== 'final');
    
    if (stepsNeedingCommentary.length === 0) {
      console.log('📝 [Batch Commentary] No steps need commentary');
      return commentaryMap;
    }
    
    addSystemMessage(`Generating commentary for ${stepsNeedingCommentary.length} key moments...`);
    
    // Generate all commentary in parallel with progress updates
    const commentaryPromises = stepsNeedingCommentary.map(async ({ step, index }) => {
      const move = step.move;
      const meta = (walkData?.game_metadata || walkData?.gameMetadata || {}) as any;
      const playerColor: 'white' | 'black' | null = meta.player_color || null;
      const focusColor: 'white' | 'black' | 'both' | null = meta.focus_color || meta.focusColor || null;
      const reviewSubject: 'player' | 'opponent' | 'both' | null = meta.review_subject || meta.reviewSubject || null;
      const moveColor: 'white' | 'black' = move?.color === 'w' ? 'white' : 'black';
      const allowRetry = !!playerColor && (focusColor ? focusColor === playerColor : reviewSubject !== 'opponent') && moveColor === playerColor;
      
      const moveNumber = move?.moveNumber || '?';
      const moveSan = move?.move || move?.san || '?';
      
      // Update status for this specific move
      addSystemMessage(`Generating commentary for Move ${moveNumber}: ${moveSan}...`);
      
      try {
        const commentary = await generateWalkthroughPreCommentary(
          step.type,
          move,
          walkData,
          allowRetry,
          true, // skipLoadingIndicator = true (we're showing batch progress instead)
          index // Pass step index for lookup
        );
        return { index, commentary };
      } catch (err) {
        console.error(`❌ [Batch Commentary] Failed for step ${index}:`, err);
        // Fallback commentary
        const fallback = allowRetry 
          ? "This is a key turning point—see if you can find a cleaner continuation from here."
          : "This is a key moment—let's see what it changed in the position.";
        return { index, commentary: fallback };
      }
    });
    
    // Wait for all to complete
    const results = await Promise.all(commentaryPromises);
    results.forEach(({ index, commentary }) => {
      commentaryMap.set(index, commentary);
    });
    
    addSystemMessage(`✅ Commentary generation complete for ${results.length} moves`);
    return commentaryMap;
  }

  async function startWalkthrough() {
    console.log('🎬 [startWalkthrough] Wrapper invoked');
    if (!walkthroughData) {
      console.error('❌ [startWalkthrough] No walkthrough data available!');
      addSystemMessage("Walkthrough cannot start yet: no review data.");
      return;
    }
    
    // Open board automatically (like lessons do)
    if (!boardDockOpen) {
      setBoardDockOpen(true);
    }
    
    // Show loading state
    setIsProcessingStep(true);
    
    try {
      // Build sequence first to determine what needs commentary
      const moves = Array.isArray(walkthroughData.moves) ? walkthroughData.moves : [];
      const selectedKeyMoments = Array.isArray(walkthroughData.selectedKeyMoments) ? walkthroughData.selectedKeyMoments : [];
      const queryIntent = walkthroughData.queryIntent || 'general';
      const leftTheoryMove = walkthroughData.leftTheoryMove || null;
      
      const sequence: any[] = [];
      
      // Build sequence (same logic as continueWalkthroughWithData)
      if (selectedKeyMoments.length > 0) {
        selectedKeyMoments.forEach((moment: any) => {
          const ply = moment.ply;
          const moveData = moves.find((m: any) => m.ply === ply);
          if (!moveData) return;
          
          const labels = moment.labels || [];
          const primaryLabel = moment.primary_label || moveData.quality || '';
          const category = moveData.category || primaryLabel;
          
          let stepType = 'highlight';
          if (category === 'blunder' || labels.includes('blunder')) stepType = 'blunder';
          else if (category === 'mistake' || labels.includes('mistake')) stepType = 'mistake';
          else if (category === 'inaccuracy' || labels.includes('inaccuracy')) stepType = 'inaccuracy';
          else if (labels.includes('advantage_shift')) stepType = 'advantage_shift';
          else if (labels.includes('missed_critical_win') || labels.includes('missed_win')) stepType = 'missed_win';
          else if (category === 'critical_best' || labels.includes('critical_best')) stepType = 'critical';
          else if (category === 'best' || labels.includes('best')) stepType = 'best_move';
          else if (labels.includes('tactical_opportunity')) stepType = 'tactical';
          else if (labels.includes('phase_transition')) stepType = 'phase_transition';
          
          sequence.push({ type: stepType, move: moveData, moment: moment, queryIntent: queryIntent });
        });
        
        const finalMove = moves[moves.length - 1];
        if (finalMove && selectedKeyMoments[selectedKeyMoments.length - 1]?.ply !== finalMove.ply) {
          sequence.push({ type: 'final', move: finalMove });
        }
      } else {
        // Fallback sequence building
        const lastTheoryMoveFound = moves.filter((m: any) => m.isTheoryMove).pop();
        if (lastTheoryMoveFound) sequence.push({ type: 'opening', move: lastTheoryMoveFound });
        if (leftTheoryMove) sequence.push({ type: 'left_theory', move: leftTheoryMove });
        
        const candidates: any[] = [];
        moves.forEach((m: any) => {
          if (m.quality === 'blunder') candidates.push({ move: m, type: 'blunder', cpLoss: m.cpLoss || 0 });
          else if (m.quality === 'mistake') candidates.push({ move: m, type: 'mistake', cpLoss: m.cpLoss || 0 });
          else if (m.quality === 'inaccuracy' && (m.cpLoss || 0) >= 50) {
            candidates.push({ move: m, type: 'inaccuracy', cpLoss: m.cpLoss || 0 });
          }
        });
        candidates.sort((a, b) => b.cpLoss - a.cpLoss);
        candidates.slice(0, 10).sort((a, b) => a.move.ply - b.move.ply).forEach(err => {
          sequence.push({ type: err.type, move: err.move });
        });
        
        const finalMove = moves[moves.length - 1];
        if (finalMove) sequence.push({ type: 'final', move: finalMove });
      }
      
      // Generate all commentary in parallel BEFORE starting walkthrough
      console.log('📝 [startWalkthrough] Generating batch commentary for', sequence.length, 'steps');
      const commentaryMap = await generateBatchWalkthroughCommentary(sequence, walkthroughData);
      
      // Store commentary map in walkthroughData for use during execution
      walkthroughData.preGeneratedCommentary = commentaryMap;
      walkthroughData.sequence = sequence; // Store sequence too
      
      // Now actually start the walkthrough
      console.log('🎬 [startWalkthrough] Setting active and step 0');
      setWalkthroughActive(true);
      setWalkthroughStep(0);
      
      // Start with first step immediately
      console.log('🎬 [startWalkthrough] Starting continueWalkthroughWithData immediately');
      await continueWalkthroughWithData(walkthroughData, 0);
    } catch (err) {
      console.error('❌ [startWalkthrough] Error:', err);
      addSystemMessage(`Walkthrough failed to start: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setIsProcessingStep(false);
    }
  }

  const handleButtonAction = async (action: string, buttonId?: string) => {
    // Handle play-against-AI side selection
    if (action === "start_game_white" || action === "start_game_black") {
      // Disable the clicked button
      if (buttonId) {
        setMessages((prev) => 
          prev.map((msg) => 
            msg.meta?.buttonId === buttonId 
              ? { ...msg, meta: { ...msg.meta, disabled: true } }
              : msg
          )
        );
      }
      
      // Disable all play buttons
      setMessages((prev) =>
        prev.map((msg) =>
          (msg.buttonAction === "start_game_white" || msg.buttonAction === "start_game_black")
            ? { ...msg, meta: { ...msg.meta, disabled: true } }
            : msg
        )
      );
      
      const aiSide = action === "start_game_white" ? "black" : "white";
      const userSide = action === "start_game_white" ? "white" : "black";
      
      // Set board orientation so playing side is at bottom
      setBoardOrientation(userSide);
      
      // Activate AI game mode and make first move if it's AI's turn
      setAiGameActive(true);
      setMode("PLAY");
      
      const currentTurn = fen.split(' ')[1]; // 'w' or 'b'
      const isAiTurn = (aiSide === 'white' && currentTurn === 'w') || 
                       (aiSide === 'black' && currentTurn === 'b');
      
      // Make first move if it's AI's turn
      if (isAiTurn) {
        try {
          // Call playMove with null user_move_san to indicate it's AI's turn
          const response = await playMove(fen, null, undefined, 1500);
          
          if (response.legal && response.engine_move_san && response.new_fen) {
            // Print "I played [best move]"
            addSystemMessage(`I played ${response.engine_move_san}`);
            
            // Apply the move to the board
            const tempGame = new Chess(fen);
            const move = tempGame.move(response.engine_move_san);
            if (move) {
              // Use handleMove to properly trigger all move handling logic
              // This will update the board, PGN, and trigger any LLM analysis if enabled
              handleMove(move.from, move.to, move.promotion);
            } else {
              addSystemMessage(`Error: Invalid move ${response.engine_move_san} from engine`);
            }
          } else {
            const errorMsg = response.error || 'Unknown error';
            addSystemMessage(`Error making AI move: ${errorMsg}`);
          }
        } catch (err: any) {
          const errorMsg = err?.message || 'Failed to get engine move';
          addSystemMessage(`Error: ${errorMsg}`);
        }
      }
      
      return;
    }
    
    if (action === "SHOW_LESSON_DATA") {
      setShowLessonDataPanel(true);
      return;
    }
    if (action === "SHOW_LESSON_CUES") {
      handleLessonCueRequest();
      setLessonCueButtonActive(false);
      return;
    }
    await handleSendMessage(`__BUTTON_ACTION__${action}`);
  };

  // Handler for starting game from setup modal
  const handleStartGame = useCallback(async (config: {
    userSide: "white" | "black";
    aiElo: number;
    startFromCurrent: boolean;
    newTab: boolean;
  }) => {
    const { userSide, aiElo, startFromCurrent, newTab } = config;
    
    // If new tab, create one and switch to it
    if (newTab) {
      handleNewTab();
      // Wait a bit for tab to be created, then reset to starting position
      setTimeout(() => {
        const newGame = new Chess();
        setFen(INITIAL_FEN);
        setPgn("");
        setGame(newGame);
        setMoveTree(new MoveTree());
      }, 100);
    }
    
    // Store game config
    setAiGameElo(aiElo);
    setAiGameUserSide(userSide);
    
    // Store game state in current tab
    setTabs(prevTabs => prevTabs.map(tab => 
      tab.id === activeTabId 
        ? { ...tab, aiGameActive: true, aiGameElo: aiElo, aiGameUserSide: userSide }
        : tab
    ));
    
    // Set board orientation
    setBoardOrientation(userSide);
    
    // Activate game mode
    setAiGameActive(true);
    setMode("PLAY");
    
    // Add system notification
    addSystemMessage(`Game started! You're playing as ${userSide === "white" ? "White" : "Black"} against Chesster (ELO ${aiElo}).`);
    
    // Get current position - use state directly since we're in a callback
    const currentFen = fen;
    const currentTurn = currentFen.split(' ')[1]; // 'w' or 'b'
    const aiSide = userSide === "white" ? "black" : "white";
    const isAiTurn = (aiSide === 'white' && currentTurn === 'w') || 
                     (aiSide === 'black' && currentTurn === 'b');
    
    // If it's AI's turn, make the best move first
    if (isAiTurn) {
      try {
        const response = await playMove(currentFen, undefined, aiElo, 1500);
        
        if (response.legal && response.engine_move_san && response.new_fen) {
          addSystemMessage(`I played ${response.engine_move_san}`);
          
          const tempGame = new Chess(currentFen);
          const move = tempGame.move(response.engine_move_san);
          if (move) {
            handleMove(move.from, move.to, move.promotion);
          } else {
            addSystemMessage(`Error: Invalid move ${response.engine_move_san} from engine`);
          }
        } else {
          const errorMsg = response.error || 'Unknown error';
          addSystemMessage(`Error making AI move: ${errorMsg}`);
        }
      } catch (err: any) {
        const errorMsg = err?.message || 'Failed to get engine move';
        addSystemMessage(`Error: ${errorMsg}`);
      }
    }
  }, [activeTabId, handleMove, handleNewTab]);

  // Handler for exiting game mode
  const handleExitGameMode = useCallback(() => {
    // Clear game state from current tab
    setTabs(prevTabs => prevTabs.map(tab => 
      tab.id === activeTabId 
        ? { ...tab, aiGameActive: false, aiGameElo: undefined, aiGameUserSide: undefined }
        : tab
    ));
    
    setAiGameActive(false);
    setAiGameUserSide(null);
    setMode("DISCUSS");
    addSystemMessage("Game mode left. You can resume back through the options menu.");
  }, [activeTabId]);

  const boardArrows = lessonMode ? lessonArrows : annotations.arrows;
  const boardHighlights = lessonMode ? [] : annotations.highlights;

  return (
    <div data-theme={theme} className="app-shell">
      <TopBar
        onToggleHistory={() => setShowHistory(!showHistory)}
        onSignIn={handleSignInClick}
        onSignOut={handleAuthSignOut}
        onSwitchAccount={handleSwitchAccount}
        userEmail={authUserEmail}
        userName={authUserName}
        authLoading={authLoading}
      />

      {showAuthModal && !user && (
        <AuthModal onClose={() => setShowAuthModal(false)} />
      )}
      
      {/* Limit Exceeded Popup */}
      {limitExceededInfo && (
        <div 
          className="limit-exceeded-overlay"
          onClick={(e) => {
            if (e.target === e.currentTarget) {
              setLimitExceededInfo(null);
            }
          }}
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0, 0, 0, 0.6)',
            zIndex: 1000,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '20px'
          }}
        >
          <div 
            className="limit-exceeded-modal"
            style={{
              background: 'var(--bg-primary)',
              border: '1px solid var(--border-color)',
              borderRadius: '12px',
              padding: '24px',
              maxWidth: '500px',
              width: '100%',
              boxShadow: '0 10px 40px rgba(0, 0, 0, 0.3)'
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <h2 style={{ margin: 0, fontSize: '20px', fontWeight: '600' }}>Limit Exceeded</h2>
              <button
                type="button"
                onClick={() => setLimitExceededInfo(null)}
                style={{
                  background: 'transparent',
                  border: 'none',
                  fontSize: '24px',
                  cursor: 'pointer',
                  color: 'var(--text-secondary)',
                  padding: '0',
                  width: '32px',
                  height: '32px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}
              >
                ×
              </button>
            </div>
            
            <p style={{ margin: '0 0 20px 0', color: 'var(--text-primary)', lineHeight: '1.6' }}>
              {limitExceededInfo.message}
            </p>
            
            <p style={{ margin: '0 0 20px 0', color: 'var(--text-secondary)', fontSize: '14px', lineHeight: '1.6' }}>
              Your conversation can continue, but AI responses are limited. You can still use available tools below.
            </p>
            
            {/* Available Tools */}
            {limitExceededInfo.available_tools && (
              <div style={{ marginBottom: '20px' }}>
                <h3 style={{ margin: '0 0 12px 0', fontSize: '16px', fontWeight: '600' }}>Available Tools</h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {limitExceededInfo.available_tools.game_reviews?.available && (
                    <button
                      type="button"
                      onClick={async () => {
                        // Call game review tool directly
                        setLimitExceededInfo(null);
                        // TODO: Implement direct tool call
                        alert('Game review tool will be called directly');
                      }}
                      style={{
                        padding: '10px 16px',
                        background: 'var(--accent-primary)',
                        color: 'var(--bg-primary)',
                        border: 'none',
                        borderRadius: '6px',
                        cursor: 'pointer',
                        fontSize: '14px',
                        fontWeight: '500'
                      }}
                    >
                      Review Game ({limitExceededInfo.available_tools.game_reviews.used || 0}/{limitExceededInfo.available_tools.game_reviews.limit === 'unlimited' ? '∞' : limitExceededInfo.available_tools.game_reviews.limit} remaining)
                    </button>
                  )}
                  {limitExceededInfo.available_tools.lessons?.available && (
                    <button
                      type="button"
                      onClick={async () => {
                        // Call lesson tool directly
                        setLimitExceededInfo(null);
                        // TODO: Implement direct tool call
                        alert('Lesson tool will be called directly');
                      }}
                      style={{
                        padding: '10px 16px',
                        background: 'var(--accent-primary)',
                        color: 'var(--bg-primary)',
                        border: 'none',
                        borderRadius: '6px',
                        cursor: 'pointer',
                        fontSize: '14px',
                        fontWeight: '500'
                      }}
                    >
                      Generate Lesson ({limitExceededInfo.available_tools.lessons.used || 0}/{limitExceededInfo.available_tools.lessons.limit === 'unlimited' ? '∞' : limitExceededInfo.available_tools.lessons.limit} remaining)
                    </button>
                  )}
                  {(!limitExceededInfo.available_tools.game_reviews?.available && !limitExceededInfo.available_tools.lessons?.available) && (
                    <p style={{ margin: 0, color: 'var(--text-secondary)', fontSize: '14px' }}>
                      No tools available. Upgrade your plan to access more features.
                    </p>
                  )}
                </div>
              </div>
            )}
            
            {/* Next Step Actions */}
            <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
              {limitExceededInfo.next_step === 'sign_in' && (
                <button
                  type="button"
                  onClick={() => {
                    setLimitExceededInfo(null);
                    setShowAuthModal(true);
                  }}
                  style={{
                    flex: 1,
                    padding: '12px',
                    background: 'var(--accent-primary)',
                    color: 'var(--bg-primary)',
                    border: 'none',
                    borderRadius: '6px',
                    cursor: 'pointer',
                    fontSize: '14px',
                    fontWeight: '600'
                  }}
                >
                  Sign In / Sign Up
                </button>
              )}
              {limitExceededInfo.next_step === 'upgrade_lite' && (
                <button
                  type="button"
                  onClick={() => {
                    setLimitExceededInfo(null);
                    setShowHistory(true);
                    setOpenSettingsNonce((n) => n + 1);
                  }}
                  style={{
                    flex: 1,
                    padding: '12px',
                    background: 'var(--accent-primary)',
                    color: 'var(--bg-primary)',
                    border: 'none',
                    borderRadius: '6px',
                    cursor: 'pointer',
                    fontSize: '14px',
                    fontWeight: '600'
                  }}
                >
                  Upgrade to Lite
                </button>
              )}
              {limitExceededInfo.next_step === 'upgrade' && (
                <button
                  type="button"
                  onClick={() => {
                    setLimitExceededInfo(null);
                    setShowHistory(true);
                    setOpenSettingsNonce((n) => n + 1);
                  }}
                  style={{
                    flex: 1,
                    padding: '12px',
                    background: 'var(--accent-primary)',
                    color: 'var(--bg-primary)',
                    border: 'none',
                    borderRadius: '6px',
                    cursor: 'pointer',
                    fontSize: '14px',
                    fontWeight: '600'
                  }}
                >
                  View Plans
                </button>
              )}
              <button
                type="button"
                onClick={() => setLimitExceededInfo(null)}
                style={{
                  flex: 1,
                  padding: '12px',
                  background: 'transparent',
                  color: 'var(--text-primary)',
                  border: '1px solid var(--border-color)',
                  borderRadius: '6px',
                  cursor: 'pointer',
                  fontSize: '14px',
                  fontWeight: '500'
                }}
              >
                Continue Conversation
              </button>
            </div>
          </div>
        </div>
      )}

      {showDevTools && (
            <button 
          className="dev-quick-graph"
          onClick={() => (typeof window !== 'undefined' && (window as any).CG_renderGraph && (window as any).CG_renderGraph())}
          title="Render mini-board in chat"
            >
          Render graph in chat
            </button>
          )}
          
      {isFirstMessage ? (
        // INITIAL STATE: Hero Composer
        <main className="initial-layout">
          <div className="hero-stage">
            <RotatingExamples />
            <HeroComposer
              onFirstSend={handleFirstSend}
              onToggleBoard={handleToggleBoard}
              onLoadGame={handleShowLoadGame}
              isBoardOpen={boardDockOpen}
              placeholder={rotatingPlaceholder}
              placeholderVisible={placeholderVisible}
            />
          </div>
          
          {boardDockOpen && (
            <div className="board-with-tabs">
              <TabBar
                tabs={tabs}
                activeTabId={activeTabId}
                onTabSelect={handleTabSelect}
                onTabClose={handleTabClose}
                onTabRename={handleTabRename}
                onTabDuplicate={handleTabDuplicate}
                onNewTab={handleNewTab}
              />
              <BoardDock
                fen={fen}
                pgn={pgn}
                arrows={boardArrows}
                highlights={boardHighlights}
                onMove={wrappedHandleMove}
                orientation={boardOrientation}
                onFlipBoard={() => setBoardOrientation(prev => (prev === "white" ? "black" : "white"))}
                rootNode={moveTree.root}
                currentNode={moveTree.currentNode}
                onMoveClick={handleMoveClick}
                onDeleteMove={handleDeleteMove}
                onDeleteVariation={handleDeleteVariation}
                onPromoteVariation={handlePromoteVariation}
                onAddComment={handleAddComment}
              />
            </div>
          )}
        </main>
      ) : (
        // CHAT STATE: Conversation with optional board
        <main
          ref={layoutRef}
          className={`chat-layout ${boardDockOpen ? 'with-board' : ''} ${isMobileMode ? 'mobile-mode' : ''}`}
          style={layoutStyle}
        >
          {boardDockOpen ? (
            <>
              <div className="layout-column board-column" style={boardColumnStyle}>
                <TabBar
                  tabs={tabs}
                  activeTabId={activeTabId}
                  onTabSelect={handleTabSelect}
                  onTabClose={handleTabClose}
                  onTabRename={handleTabRename}
                  onTabDuplicate={handleTabDuplicate}
                  onNewTab={handleNewTab}
                  onHideBoard={() => setBoardDockOpen(false)}
                />
                <BoardDock
                  fen={previewFEN || fen}
                  pgn={pgn}
                  arrows={boardArrows}
                  highlights={boardHighlights}
                  onMove={wrappedHandleMove}
                  orientation={boardOrientation}
                  onFlipBoard={() => setBoardOrientation(prev => (prev === "white" ? "black" : "white"))}
                  onLoadGame={() => setShowLoadGame(!showLoadGame)}
                  onHideBoard={() => setBoardDockOpen(false)}
                  rootNode={moveTree.root}
                  currentNode={moveTree.currentNode}
                  onMoveClick={handleMoveClick}
                  onDeleteMove={handleDeleteMove}
                  onDeleteVariation={handleDeleteVariation}
                  onPromoteVariation={handlePromoteVariation}
                  onAddComment={handleAddComment}
                />
              </div>
              {isMobileMode ? (
                <div
                  className="row-resizer"
                  onPointerDown={(e) => beginDrag("board-chat", "y", e)}
                  onMouseDown={(e) => beginDrag("board-chat", "y", e)}
                />
              ) : (
                <div
                  className="column-resizer"
                  onPointerDown={(e) => beginDrag("board-chat", "x", e)}
                  onMouseDown={(e) => beginDrag("board-chat", "x", e)}
                />
              )}
              <div className="layout-column chat-column" style={chatColumnStyle}>
              {activeTab?.tabType === 'training' && activeTab?.trainingSession ? (
                <TrainingSession
                  session={activeTab.trainingSession}
                  username={user?.id || ''}
                  onComplete={(results) => {
                    console.log("Training session complete:", results);
                    // Update tab to remove training session and switch to discuss mode
                    setTabs(prev => prev.map(t => 
                      t.id === activeTabId 
                        ? { ...t, trainingSession: undefined, tabType: 'discuss' }
                        : t
                    ));
                    addSystemMessage("Training session completed! Great work!");
                  }}
                  onClose={() => {
                    // Switch tab back to discuss mode
                    setTabs(prev => prev.map(t => 
                      t.id === activeTabId 
                        ? { ...t, trainingSession: undefined, tabType: 'discuss' }
                        : t
                    ));
                  }}
                  onSwitchToChat={() => {
                    // Switch tab to chat mode but keep training session
                    setTabs(prev => prev.map(t => 
                      t.id === activeTabId 
                        ? { ...t, tabType: 'discuss' }
                        : t
                    ));
                  }}
                />
              ) : (
                <Conversation 
                  messages={messages}
                  executionPlan={executionPlan}
                  thinkingStage={thinkingStage}
                  onToggleBoard={!boardDockOpen ? handleToggleBoard : undefined}
                  isBoardOpen={boardDockOpen}
                  onLoadGame={!boardDockOpen ? handleShowLoadGame : undefined}
                  currentFEN={fen}
                  onApplyPGN={handleApplyPGNSequence}
                  onPreviewFEN={handlePreviewFEN}
                  onButtonAction={handleButtonAction}
                  isProcessingButton={isProcessingStep}
                  loadingIndicators={activeLoaders}
                  isLLMProcessing={isLLMProcessing}
                  liveStatusMessages={liveStatusMessages}
                  onRunFullAnalysis={handleRunFullAnalysis}
                  factsCard={factsByTask[activeTab?.id || "default"]}
                  isMobileMode={isMobileMode}
                  fen={previewFEN || fen}
                  pgn={pgn}
                  arrows={boardArrows}
                  highlights={boardHighlights}
                  boardOrientation={boardOrientation}
                  moveTree={moveTree}
                  currentNode={moveTree.currentNode}
                  rootNode={moveTree.root}
                  onMoveClick={handleMoveClick}
                  onDeleteMove={handleDeleteMove}
                  onDeleteVariation={handleDeleteVariation}
                  onPromoteVariation={handlePromoteVariation}
                  onAddComment={handleAddComment}
                />
              )}
              </div>
            </>
          ) : (
            <>
              {activeTab?.tabType === 'training' && activeTab?.trainingSession ? (
                <TrainingSession
                  session={activeTab.trainingSession}
                  username={user?.id || ''}
                  onComplete={(results) => {
                    console.log("Training session complete:", results);
                    // Update tab to remove training session and switch to discuss mode
                    setTabs(prev => prev.map(t => 
                      t.id === activeTabId 
                        ? { ...t, trainingSession: undefined, tabType: 'discuss' }
                        : t
                    ));
                    addSystemMessage("Training session completed! Great work!");
                  }}
                  onClose={() => {
                    // Switch tab back to discuss mode
                    setTabs(prev => prev.map(t => 
                      t.id === activeTabId 
                        ? { ...t, trainingSession: undefined, tabType: 'discuss' }
                        : t
                    ));
                  }}
                />
              ) : (
                <Conversation 
                  messages={messages}
                  executionPlan={executionPlan}
                  thinkingStage={thinkingStage}
                  onToggleBoard={!boardDockOpen ? handleToggleBoard : undefined}
                  isBoardOpen={boardDockOpen}
                  onLoadGame={!boardDockOpen ? handleShowLoadGame : undefined}
                  currentFEN={fen}
                  onApplyPGN={handleApplyPGNSequence}
                  onPreviewFEN={handlePreviewFEN}
                  onButtonAction={handleButtonAction}
                  isProcessingButton={isProcessingStep}
                  loadingIndicators={activeLoaders}
                  isLLMProcessing={isLLMProcessing}
                  liveStatusMessages={liveStatusMessages}
                  onRunFullAnalysis={handleRunFullAnalysis}
                  onShowBoardTab={handleShowBoardFromMessage}
                  factsCard={factsByTask[activeTab?.id || "default"]}
                  isMobileMode={isMobileMode}
                  fen={previewFEN || fen}
                  pgn={pgn}
                  arrows={boardArrows}
                  highlights={boardHighlights}
                  boardOrientation={boardOrientation}
                  moveTree={moveTree}
                  currentNode={moveTree.currentNode}
                  rootNode={moveTree.root}
                  onMoveClick={handleMoveClick}
                  onDeleteMove={handleDeleteMove}
                  onDeleteVariation={handleDeleteVariation}
                  onPromoteVariation={handlePromoteVariation}
                  onAddComment={handleAddComment}
                />
              )}
            </>
          )}
          
          {!(activeTab?.tabType === 'training' && activeTab?.trainingSession) && (
            <BottomComposer
              onSend={handleSendMessage}
              disabled={isAnalyzing || isProcessingStep || isGeneratingLesson}
              isProcessing={isAnalyzing || isProcessingStep || isGeneratingLesson}
              onCancel={cancelProcessing}
              placeholder={isAnalyzing ? "Analyzing position..." : lightningMode ? "Ask or use @tool_name(args)..." : "Ask about the position..."}
              onOpenOptions={() => setShowRequestOptions(true)}
              optionsDisabled={isAnalyzing || isLegacyReviewing || isGeneratingLesson}
              lightningMode={lightningMode}
            />
          )}

          <GameSetupModal
            open={showGameSetup}
            onClose={() => setShowGameSetup(false)}
            currentFen={fen}
            onStartGame={handleStartGame}
          />

          <OpeningLessonModal
            open={showOpeningModal}
            onClose={() => setShowOpeningModal(false)}
            currentFen={fen}
            onStartLesson={async (config) => {
              if (!user?.id) {
                addSystemMessage("Sign in to generate personalized opening lessons.");
                return;
              }
              if (isGeneratingLesson) {
                addSystemMessage("An opening lesson is already being prepared.");
                return;
              }

              setShowOpeningModal(false);
              setIsGeneratingLesson(true);

              try {
                const lessonFen = config.startFromCurrent ? fen : undefined; // undefined = let backend resolve opening
                const displayName = config.openingQuery || "this opening";
                const announcement = `Generating opening lesson for ${displayName}...`;
                addAutomatedMessage(announcement);

                // Generate lesson - backend will resolve opening if fen is null
                const lessonResponse = await generateOpeningLesson({
                  userId: user.id,
                  chatId: currentThreadId,
                  openingQuery: config.openingQuery,
                  fen: lessonFen,
                  eco: undefined,
                  orientation: config.orientation,
                });

                // If starting from starting position, check if we need to push a move
                if (!config.startFromCurrent && lessonResponse.practice_positions && lessonResponse.practice_positions.length > 0) {
                  const firstPosition = lessonResponse.practice_positions[0];
                  const positionFen = firstPosition.fen || firstPosition.position?.fen;
                  
                  if (positionFen) {
                    const tempGame = new Chess(positionFen);
                    const sideToPlay = tempGame.turn() === "w" ? "white" : "black";
                    
                    // If chosen side doesn't match side to play, push best move
                    if (config.orientation !== sideToPlay) {
                      try {
                        const moveResult = await playMove(positionFen, null, 1500, 1500);
                        if (moveResult.legal && moveResult.best_move_san) {
                          tempGame.move(moveResult.best_move_san);
                          const adjustedFen = tempGame.fen();
                          
                          // Update the first practice position with adjusted FEN
                          lessonResponse.practice_positions[0].fen = adjustedFen;
                          if (lessonResponse.practice_positions[0].position) {
                            lessonResponse.practice_positions[0].position.fen = adjustedFen;
                          }
                          
                          addSystemMessage(`I played ${moveResult.best_move_san} to reach your chosen side.`);
                        }
                      } catch (moveErr) {
                        console.warn("Failed to push move for side adjustment:", moveErr);
                      }
                    }
                  }
                }

                handleOpeningLessonResult(lessonResponse);
              } catch (err: any) {
                addSystemMessage(`Opening lesson failed: ${err?.message || String(err)}`);
              } finally {
                setIsGeneratingLesson(false);
              }
            }}
          />

          {showRequestOptions && (
            <div className="request-options-overlay" role="dialog" aria-modal="true">
              <div className="request-options-modal">
                <h3>Manual Request</h3>
                <p>Select a request to run without the LLM.</p>
                <div className="request-options-buttons">
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/*"
                    style={{ display: 'none' }}
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (file) {
                        handleImageSelected(file);
                        setShowRequestOptions(false);
                      }
                      // Reset input
                      if (fileInputRef.current) {
                        fileInputRef.current.value = '';
                      }
                    }}
                  />
                  <button
                    type="button"
                    onClick={() => {
                      fileInputRef.current?.click();
                    }}
                  >
                    Add Photo
                  </button>
                  <button
                    type="button"
                    onClick={handleLegacyGameReview}
                    disabled={isLegacyReviewing}
                  >
                    {isLegacyReviewing ? 'Running Legacy Review...' : 'Legacy Game Review'}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setShowRequestOptions(false);
                      handleAnalyzeMoveRequest();
                    }}
                    disabled={!llmEnabled}
                    title={!llmEnabled ? "Enable LLM to use this feature" : "Get structured analysis"}
                    >
                      Analyze Move
                    </button>
                  {aiGameActive ? (
                    <button
                      type="button"
                      onClick={() => {
                        setShowRequestOptions(false);
                        handleExitGameMode();
                      }}
                      title="Exit game mode"
                    >
                      Exit Game Mode
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={() => {
                        setShowRequestOptions(false);
                        setShowGameSetup(true);
                      }}
                      disabled={!llmEnabled}
                      title={!llmEnabled ? "Enable LLM to play with AI" : "Start playing a game with the AI"}
                    >
                      Play with AI
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => {
                      setShowRequestOptions(false);
                      setShowOpeningModal(true);
                    }}
                    disabled={!user || isGeneratingLesson}
                    title={!user ? "Sign in to generate personalized lessons" : undefined}
                  >
                    {isGeneratingLesson ? 'Preparing Lesson...' : 'Opening Lesson'}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setLightningMode(!lightningMode);
                      setShowRequestOptions(false);
                    }}
                    style={{
                      background: lightningMode ? 'var(--accent-primary)' : 'transparent',
                      color: lightningMode ? 'var(--bg-primary)' : 'var(--text-primary)',
                      border: '1px solid var(--border-color)',
                    }}
                    title={lightningMode ? "Lightning Mode: Fast responses with gpt-4o-mini. Click to switch to Deep Thought mode." : "Lightning Mode: Fast responses but may forget tool calls. Use @tool_name(args) to mandate tools."}
                  >
                    {lightningMode ? '⚡ Lightning Mode ON' : '⚡ Lightning Mode'}
                  </button>
                  <button 
                    type="button"
                    onClick={() => setShowRequestOptions(false)}
                    className="cancel-button"
                  >
                    Cancel
                  </button>
            </div>
          </div>
        </div>
      )}
          
          {showLoadGame && (
            <LoadGamePanel
              onLoad={handleLoadedGame}
              onClose={() => setShowLoadGame(false)}
            />
          )}
    </main>
      )}

      <HistoryCurtain
        open={showHistory}
        onClose={() => setShowHistory(false)}
        onSelectThread={(threadId) => {
          setCurrentThreadId(threadId);
          // TODO: Load thread messages from Supabase
        }}
        currentThreadId={currentThreadId}
        profilePreferences={profilePreferences}
        profileStatus={profileStatus}
        profileHighlights={profileOverview?.highlights}
        profileGames={profileOverview?.games}
        profileStats={profileStats}
        onEditProfileSetup={() => setShowProfileSetupModal(true)}
        onRefreshProfile={refreshProfileData}
        onOpenProfileDashboard={() => setShowProfileDashboard(true)}
        onOpenPersonalReview={() => setShowPersonalReview(true)}
        userId={user?.id}
      />
      {showPersonalReview && (
        <PersonalReview onClose={() => setShowPersonalReview(false)} />
      )}
      {user && (
        <ProfileSetupModal
          open={showProfileSetupModal}
          onClose={() => setShowProfileSetupModal(false)}
          onSave={handleSaveProfilePreferences}
          initialData={profilePreferences}
        />
      )}
      {showProfileDashboard && (
        <ProfileDashboard
          onClose={() => setShowProfileDashboard(false)}
          onCreateNewTab={(params: any) => {
            setShowProfileDashboard(false);
            // Create new tab using the newTab handler from executeUICommands
            const newTabId =
              typeof crypto !== "undefined" && "randomUUID" in crypto
                ? `tab-${crypto.randomUUID()}`
                : `tab-${Date.now()}-${Math.random().toString(16).slice(2)}`;
            
            // Track if initial message has been sent (using a closure variable)
            let initialMessageSent = false;
            
            let newMoveTree = new MoveTree();
            const newTab: BoardTabState = {
              ...createDefaultTab(tabs.length + 1),
              id: newTabId,
              name: params.title || (params.type === 'training' ? 'Training' : params.type === 'lesson' ? 'Lesson' : 'Review'),
              tabType: params.type || 'review',
              fen: params.fen || INITIAL_FEN,
              pgn: params.pgn || '',
              game: new Chess(params.fen || INITIAL_FEN),
              moveTree: newMoveTree,
              isAnalyzing: false,
              hasUnread: false,
              isModified: false,
              messages: [], // Don't add initial message here - let handleSendMessage add it to prevent duplicates
              annotations: {
                fen: params.fen || INITIAL_FEN,
                pgn: params.pgn || '',
                arrows: [],
                highlights: [],
                comments: [],
                nags: []
              },
              analysisCache: {},
              moveHistory: [],
              trainingSession: params.trainingSession || undefined // Store training session if provided
            };
            
            if (params.pgn) {
              try {
                newMoveTree = MoveTree.fromPGN(params.pgn);
                newTab.moveTree = newMoveTree;
                const gameFromPgn = new Chess();
                gameFromPgn.loadPgn(params.pgn);
                newTab.game = gameFromPgn;
                newTab.fen = gameFromPgn.fen();
                newTab.annotations.fen = gameFromPgn.fen();
                newTab.annotations.pgn = params.pgn;
                newTab.pgn = params.pgn;
              } catch (e) {
                console.error("[newTab] Failed to load PGN:", e);
                newTab.pgn = params.pgn;
                newTab.annotations.pgn = params.pgn;
              }
            }
            
            // CRITICAL: Initialize messages as empty - handleSendMessage will add the initial message
            // This prevents duplicate messages
            setMessages([]);
            
            // Create and activate the new tab
            setTabs(prev => {
              const updated = prev.some(t => t.id === newTabId) ? prev : [...prev, newTab];
              return updated;
            });
            
            // Set active tab and global state
            setActiveTabId(newTabId);
            setFen(newTab.fen);
            setPgn(newTab.pgn);
            setGame(newTab.game);
            setMoveTree(newTab.moveTree);
            
            // If there's an initial message AND it's NOT a training session, send it after tab is created and active
            // Training sessions should render TrainingSession component directly, not send messages to LLM
            if (params.initialMessage && !params.trainingSession) {
              const messageToSend = params.initialMessage;
              const targetTabId = newTabId;
              setTimeout(async () => {
                // Use functional update to check current state
                setActiveTabId(currentId => {
                  if (currentId === targetTabId && !initialMessageSent) {
                    initialMessageSent = true; // Mark as sent (closure variable)
                    console.log('📤 Sending initial message to new tab:', messageToSend);
                    // Send the message asynchronously
                    handleSendMessage(messageToSend).catch(err => {
                      console.error('Failed to send initial message:', err);
                      initialMessageSent = false; // Reset on error so it can be retried
                    });
                  } else if (currentId !== targetTabId) {
                    console.warn('⚠️ Tab changed before initial message could be sent', { 
                      expectedTab: targetTabId,
                      actualTab: currentId
                    });
                  } else if (initialMessageSent) {
                    console.log('⚠️ Initial message already sent, skipping duplicate');
                  }
                  return currentId; // No change
                });
              }, 1000);
            }
          }}
        />
      )}
      {lessonDataSections && lessonDataSections.length > 0 && (
        <>
          <button
            type="button"
            className="lesson-data-button"
            onClick={() => setShowLessonDataPanel(true)}
          >
            Lesson Data
          </button>
          {showLessonDataPanel && (
            <div className="lesson-data-overlay" role="dialog" aria-modal="true">
              <div className="lesson-data-panel">
                <div className="lesson-data-panel__header">
                  <h3>Lesson Data</h3>
                  <button
                    type="button"
                    className="lesson-data-close"
                    onClick={() => setShowLessonDataPanel(false)}
                  >
                    Close
                  </button>
                </div>
                <div className="lesson-data-panel__body">
                  {lessonDataSections.map((section, idx) => (
                    <section key={`${section.title}-${idx}`} className="lesson-data-section">
                      <h4>{section.title}</h4>
                      <pre>{section.body}</pre>
                    </section>
                  ))}
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default function HomePage() {
  return (
    <Suspense fallback={<div>Loading...</div>}>
      <HomeInner />
    </Suspense>
  );
}
