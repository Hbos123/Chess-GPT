import { useEffect, useRef } from 'react';
import MessageBubble from './MessageBubble';
import IntentBox from './IntentBox';
import StatusIndicator from './StatusIndicator';

interface Message {
  id?: string;
  role: 'user' | 'assistant' | 'system' | 'graph' | 'button' | 'expandable_table';
  content: string;
  meta?: any;
  timestamp?: Date;
  buttonAction?: string;
  buttonLabel?: string;
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

interface ConversationProps {
  messages: Message[];
  onToggleBoard?: () => void;
  isBoardOpen?: boolean;
  onLoadGame?: () => void;
  currentFEN?: string;
  onApplyPGN?: (fen: string, pgn: string) => void;
  onPreviewFEN?: (fen: string | null) => void;
  onButtonAction?: (action: string) => void;
  isProcessingButton?: boolean;
  loadingIndicators?: LoadingIndicator[];
  // New: Live status tracking
  isLLMProcessing?: boolean;
  liveStatusMessages?: StatusMessage[];
  onRunFullAnalysis?: (fen: string) => void;
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
  onRunFullAnalysis
}: ConversationProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, liveStatusMessages]);

  return (
    <div className="conversation-container">
      {onToggleBoard && (
        <button className="board-toggle-chat" onClick={onToggleBoard}>
          {isBoardOpen ? 'Hide' : 'Show'} chessboard
        </button>
      )}
      
      <div className="conversation-stream">
        {messages.map((msg, index) => {
          // Filter out: inline graphs when board open, empty/null messages
          const isEmpty = !msg.content || msg.content.trim() === '';
          const shouldHide = (isBoardOpen && msg.role === 'graph') || (isEmpty && msg.role !== 'button');
          
          if (isEmpty && msg.role === 'assistant') {
            console.log('🚫 [Conversation] Suppressing empty assistant message at index', index);
          }
          
          if (shouldHide) return null;
          
          // Show IntentBox for assistant messages with detected intent
          const showIntentBox = msg.role === 'assistant' && 
            (msg.meta?.detectedIntent || msg.meta?.toolsUsed?.length > 0);
          
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
                isButtonDisabled={msg.role === 'button' ? (isProcessingButton || msg.meta?.disabled || msg.meta?.loading) : undefined}
                onRunFullAnalysis={onRunFullAnalysis}
              />
            </div>
          );
        })}
        
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
      
      {onLoadGame && (
        <button className="load-game-chat" onClick={onLoadGame}>
          Load game
        </button>
      )}
    </div>
  );
}

