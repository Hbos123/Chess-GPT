import { useEffect, useRef, useState, useCallback } from 'react';
import MessageBubble from './MessageBubble';
import IntentBox from './IntentBox';
import StatusIndicator from './StatusIndicator';
import ExecutionPlan from './ExecutionPlan';
import ThinkingStage from './ThinkingStage';
import FactsCard from './FactsCard';
import Board from './Board';
import PGNViewer from './PGNViewer';
import StockfishAnalysis from './StockfishAnalysis';
import EvaluationBar from './EvaluationBar';
import type { AnnotationArrow, AnnotationHighlight, ChatGraphData } from '@/types';
import type { MoveNode } from '@/lib/moveTree';

interface Message {
  id?: string;
  role: 'user' | 'assistant' | 'system' | 'graph' | 'button' | 'expandable_table' | 'board';
  content: string;
  meta?: any;
  timestamp?: Date;
  buttonAction?: string;
  buttonLabel?: string;
  tableTitle?: string;
  tableContent?: string;
  graphData?: ChatGraphData;
  image?: {
    data: string;
    filename?: string;
    mimeType?: string;
    uploading?: boolean;
    uploadProgress?: number;
  };
}

interface LoadingIndicator {
  id: string;
  type: 'stockfish' | 'llm' | 'game_review' | 'training' | 'general';
  message: string;
}

interface StatusMessage {
  phase: string;
  message: string;
  tool?: string;
  progress?: number;
  timestamp: number;
}

interface ShowBoardLaunchPayload {
  finalPgn?: string;
  fen?: string;
  showBoardLink?: string;
}

interface ConversationProps {
  messages: Message[];
  onToggleBoard?: () => void;
  isBoardOpen?: boolean;
  onLoadGame?: () => void;
  currentFEN?: string;
  onApplyPGN?: (fen: string, pgn: string) => void;
  onPreviewFEN?: (fen: string | null) => void;
  onButtonAction?: (action: string, buttonId?: string) => void;
  isProcessingButton?: boolean;
  loadingIndicators?: LoadingIndicator[];
  // New: Live status tracking
  isLLMProcessing?: boolean;
  liveStatusMessages?: StatusMessage[];
  onRunFullAnalysis?: (fen: string) => void;
  // Execution plan and thinking stage
  executionPlan?: any;
  thinkingStage?: any;
  onShowBoardTab?: (payload: ShowBoardLaunchPayload) => void;
  factsCard?: any;
  // Props for inline mobile board
  isMobileMode?: boolean;
  fen?: string;
  pgn?: string;
  arrows?: AnnotationArrow[];
  highlights?: AnnotationHighlight[];
  boardOrientation?: 'white' | 'black';
  moveTree?: any;
  currentNode?: MoveNode;
  rootNode?: MoveNode;
  onMoveClick?: (node: MoveNode) => void;
  onDeleteMove?: (node: MoveNode) => void;
  onDeleteVariation?: (node: MoveNode) => void;
  onPromoteVariation?: (node: MoveNode) => void;
  onAddComment?: (node: MoveNode, comment: string) => void;
  tokenUsage?: {
    messages?: { used: number; limit: number };
    tokens?: { used: number; limit: number };
  };
}

export default function Conversation({ 
  messages, 
  onToggleBoard, 
  isBoardOpen, 
  onLoadGame, 
  currentFEN, 
  onApplyPGN, 
  onPreviewFEN, 
  onButtonAction, 
  isProcessingButton, 
  loadingIndicators,
  isLLMProcessing,
  liveStatusMessages,
  onRunFullAnalysis,
  executionPlan,
  thinkingStage,
  onShowBoardTab,
  factsCard,
  isMobileMode = false,
  fen,
  pgn,
  arrows = [],
  highlights = [],
  boardOrientation = 'white',
  moveTree,
  currentNode,
  rootNode,
  onMoveClick,
  onDeleteMove,
  onDeleteVariation,
  onPromoteVariation,
  onAddComment,
  tokenUsage,
}: ConversationProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const [boardKey, setBoardKey] = useState(0);
  const [isExpanded, setIsExpanded] = useState(false);
  const [currentEval, setCurrentEval] = useState(0);
  const [currentMate, setCurrentMate] = useState<number | undefined>(undefined);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, liveStatusMessages]);

  // Update board when FEN, PGN, or annotations change
  useEffect(() => {
    if (fen || pgn || arrows.length > 0 || highlights.length > 0) {
      setBoardKey(prev => prev + 1);
    }
  }, [fen, pgn, arrows, highlights]);

  const handleEvalUpdate = useCallback((evalCp: number, mate?: number) => {
    setCurrentEval(evalCp);
    setCurrentMate(mate);
  }, []);

  const handleGoBack = () => {
    if (currentNode?.parent && onMoveClick) {
      onMoveClick(currentNode.parent);
    }
  };

  const handleGoForward = () => {
    if (currentNode?.children && currentNode.children.length > 0 && onMoveClick) {
      onMoveClick(currentNode.children[0]);
    }
  };

  const canGoBack = currentNode?.parent !== null;
  const canGoForward = currentNode?.children && currentNode.children.length > 0;
  // Only show board if there's a board message in the messages array
  const hasBoardMessage = messages.some(msg => msg.role === 'board');
  const shouldShowInlineBoard = !isBoardOpen && fen && hasBoardMessage;

  return (
    <div className="conversation-container">
      {/* Toolbar with buttons in flow */}
      {(onToggleBoard || onLoadGame || tokenUsage) && (
        <div className="conversation-toolbar" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {tokenUsage && (
            <TokenUsageBar 
              messages={tokenUsage.messages}
              tokens={tokenUsage.tokens}
            />
          )}
          {onLoadGame && (
            <button className="toolbar-button" onClick={onLoadGame}>
              Load game
            </button>
          )}
          {onToggleBoard && (
            <button className="toolbar-button" onClick={onToggleBoard}>
              {isBoardOpen ? 'Hide' : 'Show'} chessboard
            </button>
          )}
        </div>
      )}
      
      <div className="conversation-stream">
        {/* Facts-first: show most recent grounded facts for this task/thread */}
        {factsCard && (
          <FactsCard
            title="Facts"
            eval_cp={typeof factsCard.eval_cp === "number" ? factsCard.eval_cp : undefined}
            recommended_move={typeof factsCard.recommended_move === "string" ? factsCard.recommended_move : undefined}
            recommended_reason={typeof factsCard.recommended_reason === "string" ? factsCard.recommended_reason : undefined}
            top_moves={Array.isArray(factsCard.top_moves) ? factsCard.top_moves : []}
            source={typeof factsCard.source === "string" ? factsCard.source : undefined}
          />
        )}
        
        {messages.map((msg, index) => {
          // Filter out: inline graphs when board open, empty/null messages
          // Board messages are handled separately - don't filter them out
          const isEmpty = !msg.content || msg.content.trim() === '';
          const hasButtons = msg.role === 'button' || (msg.role === 'assistant' && msg.meta?.buttons?.length > 0);
          const isBoardMessage = msg.role === 'board';
          const shouldHide = (isBoardOpen && msg.role === 'graph') || (isEmpty && msg.role !== 'button' && !hasButtons && !isBoardMessage);
          
          if (isEmpty && msg.role === 'assistant' && !hasButtons) {
            return null;
          }
          
          // Handle board messages separately - render the board component
          if (isBoardMessage) {
            return (
              <div key={msg.id || index}>
                {/* Inline board - appears after board message */}
                {shouldShowInlineBoard && (
                  <div className="inline-board-message" key={boardKey}>
                    <div className="inline-board-container">
                      <div className="inline-board-with-eval">
                        <EvaluationBar 
                          evalCp={currentEval}
                          orientation={boardOrientation}
                          mate={currentMate}
                        />
                        <div className="inline-board-wrapper">
                          <Board
                            fen={fen}
                            onMove={() => {}} // Read-only in conversation
                            arrows={arrows}
                            highlights={highlights}
                            orientation={boardOrientation}
                            disabled={true}
                          />
                        </div>
                      </div>
                      
                      {/* Navigation controls */}
                      <div className="inline-board-controls">
                        <button
                          type="button"
                          className="nav-button nav-back"
                          onClick={handleGoBack}
                          disabled={!canGoBack}
                          title="Previous move"
                        >
                          ←
                        </button>
                        <button
                          type="button"
                          className="nav-button nav-expand"
                          onClick={() => setIsExpanded(!isExpanded)}
                          title={isExpanded ? "Collapse" : "Expand PGN & Analysis"}
                        >
                          {isExpanded ? 'Collapse' : 'Expand'}
                        </button>
                        <button
                          type="button"
                          className="nav-button nav-forward"
                          onClick={handleGoForward}
                          disabled={!canGoForward}
                          title="Next move"
                        >
                          →
                        </button>
                      </div>

                      {/* Expandable PGN and Analysis */}
                      {isExpanded && (
                        <div className="inline-board-expanded">
                          {pgn && rootNode && currentNode && (
                            <div className="inline-pgn-viewer">
                              <PGNViewer
                                rootNode={rootNode}
                                currentNode={currentNode}
                                onMoveClick={onMoveClick || (() => {})}
                                onDeleteMove={onDeleteMove || (() => {})}
                                onDeleteVariation={onDeleteVariation || (() => {})}
                                onPromoteVariation={onPromoteVariation || (() => {})}
                                onAddComment={onAddComment || (() => {})}
                              />
                            </div>
                          )}
                          {fen && (
                            <div className="inline-stockfish-analysis">
                              <StockfishAnalysis 
                                fen={fen}
                                onRunFullAnalysis={onRunFullAnalysis}
                              />
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            );
          }
          
          if (shouldHide) {
            return null;
          }
          
          // Group consecutive button messages together
          const isButton = msg.role === 'button';
          const prevMsg = index > 0 ? messages[index - 1] : null;
          const nextMsg = index < messages.length - 1 ? messages[index + 1] : null;
          const isFirstButton = isButton && (prevMsg?.role !== 'button');
          const isLastButton = isButton && (nextMsg?.role !== 'button');
          
          // Show IntentBox for assistant messages with detected intent
          const showIntentBox = msg.role === 'assistant' && 
            (msg.meta?.detectedIntent || msg.meta?.toolsUsed?.length > 0);
          
          // Skip rendering if this is the second button (it will be rendered with the first)
          if (isButton && !isFirstButton) {
            return null;
          }
          
          return (
            <div key={msg.id || index}>
              {showIntentBox && (
                <IntentBox
                  intent={msg.meta.detectedIntent || ''}
                  toolsUsed={msg.meta.toolsUsed || []}
                  statusHistory={msg.meta.statusMessages}
                  mode={msg.meta.orchestration?.mode}
                />
              )}
              {isButton && isFirstButton ? (
                <div className="button-group-container">
                  <MessageBubble
                    role={msg.role}
                    content={msg.content}
                    rawData={msg.meta}
                    timestamp={msg.timestamp}
                    currentFEN={currentFEN}
                    onApplyPGN={onApplyPGN}
                    onPreviewFEN={onPreviewFEN}
                    buttonAction={msg.buttonAction}
                    buttonLabel={msg.buttonLabel}
                    onButtonAction={onButtonAction}
                    isButtonDisabled={isProcessingButton || msg.meta?.disabled || msg.meta?.loading}
                    onRunFullAnalysis={onRunFullAnalysis}
                    onShowBoard={onShowBoardTab}
                    graphData={msg.graphData}
                  />
                  {nextMsg?.role === 'button' && (
                    <MessageBubble
                      role={nextMsg.role}
                      content={nextMsg.content}
                      rawData={nextMsg.meta}
                      timestamp={nextMsg.timestamp}
                      currentFEN={currentFEN}
                      onApplyPGN={onApplyPGN}
                      onPreviewFEN={onPreviewFEN}
                      buttonAction={nextMsg.buttonAction}
                      buttonLabel={nextMsg.buttonLabel}
                      onButtonAction={onButtonAction}
                      isButtonDisabled={isProcessingButton || nextMsg.meta?.disabled || nextMsg.meta?.loading}
                      onRunFullAnalysis={onRunFullAnalysis}
                      onShowBoard={onShowBoardTab}
                      graphData={nextMsg.graphData}
                    />
                  )}
                </div>
              ) : (
                <MessageBubble
                  role={msg.role}
                  content={msg.content}
                  rawData={msg.meta}
                  timestamp={msg.timestamp}
                  currentFEN={currentFEN}
                  onApplyPGN={onApplyPGN}
                  onPreviewFEN={onPreviewFEN}
                  buttonAction={msg.buttonAction}
                  buttonLabel={msg.buttonLabel}
                  tableTitle={msg.tableTitle}
                  tableContent={msg.tableContent}
                  onButtonAction={onButtonAction}
                  isButtonDisabled={msg.role === 'button' ? (isProcessingButton || msg.meta?.disabled || msg.meta?.loading) : undefined}
                  onRunFullAnalysis={onRunFullAnalysis}
                  onShowBoard={onShowBoardTab}
                  image={msg.image}
                  graphData={msg.graphData}
                />
              )}
            </div>
          );
        })}
        
        {/* Show execution plan if available */}
        {executionPlan && (
          <ExecutionPlan
            plan_id={executionPlan.plan_id}
            steps={executionPlan.steps || []}
            total_steps={executionPlan.total_steps || 0}
            isComplete={executionPlan.isComplete || false}
            thinkingTimeSeconds={executionPlan.thinkingTimeSeconds}
          />
        )}
        
        {/* Show thinking stage if available */}
        {thinkingStage && (
          <ThinkingStage
            phase={thinkingStage.phase}
            message={thinkingStage.message}
            plan_id={thinkingStage.plan_id}
            step_number={thinkingStage.step_number}
            isComplete={thinkingStage.isComplete || false}
            thinkingTimeSeconds={thinkingStage.thinkingTimeSeconds}
          />
        )}
        
        {/* Show live status messages while LLM is processing */}
        {isLLMProcessing && liveStatusMessages && liveStatusMessages.length > 0 && (
          <StatusIndicator
            messages={liveStatusMessages}
            isComplete={false}
            isVisible={true}
          />
        )}
        
        {/* Show loading indicator for other processing types */}
        {!isLLMProcessing && loadingIndicators && loadingIndicators.length > 0 && (
          <div className="inline-loader">
            <span className="loader-dot-pulse" />
            <span>{loadingIndicators[0]?.message}</span>
          </div>
        )}
        
        <div ref={bottomRef} />
      </div>
    </div>
  );
}

