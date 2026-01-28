"use client";

import { useState, useRef, useEffect } from "react";
import type { ChatMessage, Mode, Annotation } from "@/types";
import OpenAI from "openai";
import ChatGraph from "./ChatGraph";
import MarkdownTable from "./MarkdownTable";
import ExpandableTable from "./ExpandableTable";

interface ChatProps {
  messages: ChatMessage[];
  onSendMessage: (message: string) => void;
  mode: Mode;
  fen: string;
  pgn: string;
  annotations: Annotation;
  systemPrompt: string;
  llmEnabled: boolean;
  onToggleLLM: () => void;
  isReviewing?: boolean;
  reviewProgress?: number;
  totalMoves?: number;
  lessonMode?: boolean;
  isOffMainLine?: boolean;
  onReturnToMainLine?: () => void;
  isAnalyzing?: boolean;  // Block input while analyzing
}

export default function Chat({
  messages,
  onSendMessage,
  mode,
  fen,
  pgn,
  annotations,
  systemPrompt,
  llmEnabled,
  onToggleLLM,
  isReviewing,
  reviewProgress,
  totalMoves,
  lessonMode,
  isOffMainLine,
  onReturnToMainLine,
  isAnalyzing,
}: ChatProps) {
  const [input, setInput] = useState("");
  const [showMetaModal, setShowMetaModal] = useState(false);
  const [selectedMeta, setSelectedMeta] = useState<any>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = () => {
    if (!input.trim()) return;
    onSendMessage(input);
    setInput("");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleShowMeta = (meta: any) => {
    setSelectedMeta(meta);
    setShowMetaModal(true);
  };

  const formatSystemMessage = (content: string) => {
    // Convert **text** to bold
    const boldRegex = /\*\*(.+?)\*\*/g;
    const parts: (string | JSX.Element)[] = [];
    let lastIndex = 0;
    let match;
    let key = 0;

    while ((match = boldRegex.exec(content)) !== null) {
      // Add text before the match
      if (match.index > lastIndex) {
        parts.push(content.substring(lastIndex, match.index));
      }
      // Add bold text
      parts.push(<strong key={key++}>{match[1]}</strong>);
      lastIndex = match.index + match[0].length;
    }

    // Add remaining text
    if (lastIndex < content.length) {
      parts.push(content.substring(lastIndex));
    }

    return parts.length > 0 ? parts : content;
  };

  // Parse message content and extract markdown tables
  const parseMessageContent = (content: string): Array<{type: 'text' | 'table', content: string}> => {
    const lines = content.split('\n');
    const blocks: Array<{type: 'text' | 'table', content: string}> = [];
    let currentBlock: string[] = [];
    let inTable = false;
    
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      const isTableLine = line.trim().startsWith('|') && line.trim().endsWith('|');
      
      if (isTableLine) {
        if (!inTable) {
          // Start of table - save any previous text block
          if (currentBlock.length > 0) {
            blocks.push({ type: 'text', content: currentBlock.join('\n') });
            currentBlock = [];
          }
          inTable = true;
        }
        currentBlock.push(line);
      } else {
        if (inTable) {
          // End of table - save table block
          if (currentBlock.length > 0) {
            blocks.push({ type: 'table', content: currentBlock.join('\n') });
            currentBlock = [];
          }
          inTable = false;
        }
        currentBlock.push(line);
      }
    }
    
    // Save remaining block
    if (currentBlock.length > 0) {
      blocks.push({ 
        type: inTable ? 'table' : 'text', 
        content: currentBlock.join('\n') 
      });
    }
    
    return blocks;
  };

  const formatMessageWithColors = (content: string, meta?: any) => {
    // Remove surrounding quotes if present
    let cleaned = content.trim();
    if (cleaned.startsWith('"') && cleaned.endsWith('"')) {
      cleaned = cleaned.slice(1, -1);
    }
    
    // Convert ### headers to bold text with proper spacing
    // Match any ### header and replace with bold, ensuring line break before
    cleaned = cleaned.replace(/([^\n])###\s+(.+?)$/gm, '$1\n\n**$2**\n');
    cleaned = cleaned.replace(/^###\s+(.+?)$/gm, '**$1**\n');
    
    // Normalize whitespace around bold text to prevent unwanted line breaks
    // CRITICAL FIX: Remove ALL line breaks immediately before bold text
    // The backend often sends \n\n**bold** or text\n**bold**, which causes unwanted line breaks
    // We need to catch ALL cases, not just those with preceding non-whitespace characters
    
    // Step 1: Remove double newlines before bold (most common from backend like "\n\n**Time Management**")
    cleaned = cleaned.replace(/\n\s*\n\s*\*\*/g, ' **');
    
    // Step 2: Remove single newline before bold when preceded by any character (including spaces)
    // This catches: "text\n**bold**" and "text \n**bold**"
    cleaned = cleaned.replace(/([^\n])\s*\n\s*\*\*/g, '$1 **');
    
    // Step 3: Handle newline at the very start of string/line before bold
    cleaned = cleaned.replace(/^\s*\n\s*\*\*/gm, '**');
    
    // Step 4: Handle newline before bold when bold is on its own line with spaces
    cleaned = cleaned.replace(/\n\s+\*\*([^*]+?)\*\*\s*\n/g, ' **$1** ');
    
    // Step 5: Handle newline before bold when followed by text on same line
    cleaned = cleaned.replace(/\n\s*\*\*([^*]+?)\*\*\s+([^\n])/g, ' **$1** $2');
    
    // Step 6: Final catch-all - remove any remaining newlines before bold
    // This ensures we catch any edge cases we missed
    cleaned = cleaned.replace(/\n\s*\*\*/g, ' **');
    
    // Process markdown bold text first (**text** or *text*)
    const processBoldText = (text: string): (string | JSX.Element)[] => {
      const parts: (string | JSX.Element)[] = [];
      let remainingText = text;
      let keyIndex = 0;
      
      // Match **text** (double asterisks) or *text* (single asterisks) but not at start of line for bullet points
      const boldRegex = /(\*\*(.+?)\*\*|\*(?!\s)(.+?)(?<!\s)\*)/g;
      let match;
      let lastIndex = 0;
      
      while ((match = boldRegex.exec(remainingText)) !== null) {
        // Add text before the bold section
        if (match.index > lastIndex) {
          parts.push(remainingText.substring(lastIndex, match.index));
        }
        
        // Add bold text (group 2 for **, group 3 for *)
        const boldContent = match[2] || match[3];
        parts.push(
          <strong key={`bold-${keyIndex++}`}>{boldContent}</strong>
        );
        
        lastIndex = match.index + match[0].length;
      }
      
      // Add remaining text
      if (lastIndex < remainingText.length) {
        parts.push(remainingText.substring(lastIndex));
      }
      
      return parts.length > 0 ? parts : [text];
    };
    
    // First pass: convert bold markdown
    const boldProcessedParts = processBoldText(cleaned);
    
    // Define quality words and their colors with tooltips
    // Only color the operator word itself (best, excellent, good, etc.)
    const qualityPatterns = [
      { 
        pattern: /\b(best)\b/gi, 
        color: '#15803d', // dark green
        label: 'best',
        cpRange: '0cp'
      },
      { 
        pattern: /\b(excellent)\b/gi, 
        color: '#16a34a', // green
        label: 'excellent',
        cpRange: '<30cp'
      },
      { 
        pattern: /\b(good)\b/gi, 
        color: '#22c55e', // light green
        label: 'good',
        cpRange: '30-50cp'
      },
      { 
        pattern: /\b(inaccuracy)\b/gi, 
        color: '#eab308', // yellow
        label: 'inaccuracy',
        cpRange: '50-80cp'
      },
      { 
        pattern: /\b(mistake)\b/gi, 
        color: '#f97316', // orange
        label: 'mistake',
        cpRange: '80-200cp'
      },
      { 
        pattern: /\b(blunder)\b/gi, 
        color: '#dc2626', // red
        label: 'blunder',
        cpRange: '200cp+'
      }
    ];

    // Second pass: apply quality word coloring to text parts
    const processQualityWords = (textPart: string | JSX.Element, partKey: number): JSX.Element[] => {
      // If it's already a JSX element (bold text), return it as-is
      if (typeof textPart !== 'string') {
        return [textPart];
      }
      
      const results: JSX.Element[] = [];
      let text = textPart;
      let lastIndex = 0;
      let subIndex = 0;
      
      // Find all quality words in this text segment
      const matches: Array<{ index: number; length: number; pattern: any }> = [];
      
      qualityPatterns.forEach((patternObj) => {
        const regex = new RegExp(patternObj.pattern);
        let match;
        while ((match = regex.exec(text)) !== null) {
          matches.push({
            index: match.index,
            length: match[0].length,
            pattern: patternObj
          });
        }
      });
      
      // Sort matches by position
      matches.sort((a, b) => a.index - b.index);
      
      // Process matches
      matches.forEach((match) => {
        const { index, length, pattern } = match;
        const { color, label, cpRange } = pattern;
        
        // Add text before match
        if (index > lastIndex) {
          results.push(
            <span key={`${partKey}-text-${subIndex++}`}>
              {text.substring(lastIndex, index)}
            </span>
          );
        }
        
        // Add colored quality word
        const tooltip = meta?.cpLoss !== undefined 
          ? `${label.toUpperCase()} | CP Loss: ${meta.cpLoss}cp | Best: ${meta.bestMove || 'N/A'}`
          : `${label.toUpperCase()} (${cpRange})`;
        
        results.push(
          <span 
            key={`${partKey}-quality-${subIndex++}`}
            className="quality-word"
            style={{ 
              color,
              fontWeight: 700
            }}
            data-tooltip={tooltip}
          >
            {text.substring(index, index + length)}
          </span>
        );
        
        lastIndex = index + length;
      });
      
      // Add remaining text
      if (lastIndex < text.length) {
        results.push(
          <span key={`${partKey}-text-${subIndex++}`}>
            {text.substring(lastIndex)}
          </span>
        );
      }
      
      return results.length > 0 ? results : [<span key={`${partKey}-default`}>{text}</span>];
    };
    
    // Apply quality word processing to all parts
    const finalParts: JSX.Element[] = [];
    boldProcessedParts.forEach((part, idx) => {
      const processed = processQualityWords(part, idx);
      finalParts.push(...processed);
    });

    return finalParts.length > 0 ? <>{finalParts}</> : <>{cleaned}</>;
  };

  return (
    <div className="chat-container">
      <div className="chat-header">
        <h2>Chat</h2>
        <button onClick={onToggleLLM} className="toggle-llm">
          LLM: {llmEnabled ? "ON" : "OFF"}
        </button>
      </div>

      <div className="chat-messages">
        {messages.length === 0 && !isReviewing && (
          <div className="empty-state">
            <p>No messages yet. Start a conversation!</p>
            <p className="hint">
              {mode === "PLAY" && "Make a move to start playing."}
              {mode === "ANALYZE" && 'Click "Analyze Position" to get insights.'}
              {mode === "TACTICS" && 'Click "Next Tactic" to solve puzzles.'}
              {mode === "DISCUSS" && "Ask me anything about chess!"}
            </p>
          </div>
        )}

        {messages.map((msg, idx) => (
          <div key={idx}>
            {msg.role === 'graph' ? (
              <div className="message message-graph">
                {msg.graphData ? <ChatGraph graphData={msg.graphData} /> : null}
              </div>
            ) : msg.role === 'button' ? (
              <div className="message message-button">
                <button 
                  className="walkthrough-button"
                  onClick={() => onSendMessage(`__BUTTON_ACTION__${msg.buttonAction}`)}
                >
                  {msg.buttonLabel || 'Start Walkthrough'}
                </button>
              </div>
            ) : msg.role === 'expandable_table' ? (
              <div className="message message-expandable">
                <ExpandableTable 
                  title={msg.tableTitle || 'Details'} 
                  content={msg.tableContent || ''} 
                  defaultOpen={false}
                />
              </div>
            ) : (
              <div className={`message message-${msg.role}`}>
                <div className="message-role">
                  {msg.role === "user"
                    ? "You"
                    : msg.role === "assistant"
                    ? "Chesster"
                    : "System"}
                  {msg.meta && (
                    <button 
                      onClick={() => handleShowMeta(msg.meta)}
                      className="meta-button"
                      title="View raw analysis data"
                    >
                      📊
                    </button>
                  )}
                </div>
                <div className="message-content">
                  {typeof msg.content === "string" ? (
                    <>
                      {parseMessageContent(msg.content).map((block, blockIndex) => {
                        if (block.type === 'table') {
                          return <MarkdownTable key={blockIndex} content={block.content} />;
                        } else {
                          return (
                            <pre key={blockIndex} className="message-text">
                              <span style={{ display: 'inline' }}>
                                {msg.role === "assistant" 
                                  ? formatMessageWithColors(block.content, msg.meta) 
                                  : msg.role === "system"
                                    ? formatSystemMessage(block.content)
                                    : block.content}
                              </span>
                            </pre>
                          );
                        }
                      })}
                    </>
                  ) : (
                    <div>{JSON.stringify(msg.content, null, 2)}</div>
                  )}
                </div>
              </div>
            )}
          </div>
        ))}
        
        {isReviewing && (
          <div className="review-progress-container">
            <div className="progress-text">Analyzing {totalMoves} moves with Stockfish depth 18...</div>
            <div className="progress-bar-wrapper">
              <div className="progress-bar-fill" style={{ width: `${reviewProgress}%` }}></div>
            </div>
            <div className="progress-percentage">{reviewProgress}%</div>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>

      {lessonMode && isOffMainLine && onReturnToMainLine && (
        <div style={{
          padding: '12px',
          borderTop: '1px solid rgba(255,255,255,0.1)',
          display: 'flex',
          justifyContent: 'center'
        }}>
          <button 
            className="return-to-main-line-chat-button"
            onClick={onReturnToMainLine}
          >
            ♻️ Return to Main Line
          </button>
        </div>
      )}

      <div className="chat-input-area">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={isAnalyzing ? "⏳ Analyzing position..." : `Ask about the position (${mode} mode)...`}
          className="chat-input"
          rows={3}
          disabled={isAnalyzing}
        />
        <button onClick={handleSend} className="send-button" disabled={!input.trim() || isAnalyzing}>
          {isAnalyzing ? "⏳ Analyzing..." : "Send"}
        </button>
      </div>

      <div className="chat-context-info">
        <small>
          Current FEN: {fen.substring(0, 30)}...
          {" | "}
          Mode: {mode}
          {" | "}
          Comments: {annotations.comments.length}
          {" | "}
          Arrows: {annotations.arrows.length}
        </small>
      </div>

      {showMetaModal && selectedMeta && (
        <div className="modal-overlay" onClick={() => setShowMetaModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>📊 Chesster Analysis</h3>
              <button onClick={() => setShowMetaModal(false)} className="modal-close">×</button>
            </div>
            <div className="modal-body">
              {selectedMeta.mode && (
                <div className="meta-section">
                  <strong>Mode:</strong>
                  <p className="meta-text">{selectedMeta.mode}</p>
                </div>
              )}
              
              {selectedMeta.fen && (
                <div className="meta-section">
                  <strong>Position (FEN):</strong>
                  <pre className="meta-data">{selectedMeta.fen}</pre>
                </div>
              )}
              
              {selectedMeta.structuredAnalysis && (
                <div className="meta-section">
                  <strong>Chesster Structured Analysis:</strong>
                  <pre className="meta-data">{selectedMeta.structuredAnalysis}</pre>
                </div>
              )}
              
              {selectedMeta.rawEngineData && (
                <>
                  {selectedMeta.rawEngineData.move_analysis && (
                    <div className="meta-section">
                      <strong>📍 Move Analysis (Quality & Alternatives):</strong>
                      <pre className="meta-data">{JSON.stringify(selectedMeta.rawEngineData.move_analysis, null, 2)}</pre>
                    </div>
                  )}
                  <div className="meta-section">
                    <strong>📊 Position Analysis (Full Engine Output):</strong>
                    <pre className="meta-data">{JSON.stringify(
                      // Exclude move_analysis to avoid duplication
                      Object.fromEntries(
                        Object.entries(selectedMeta.rawEngineData).filter(([k]) => k !== 'move_analysis')
                      ), 
                      null, 
                      2
                    )}</pre>
                  </div>
                </>
              )}
              
              {selectedMeta.tool_context && (
                <div className="meta-section">
                  <strong>🔧 Context Sent to LLM:</strong>
                  <pre className="meta-data">{JSON.stringify(selectedMeta.tool_context, null, 2)}</pre>
                </div>
              )}
              
              {selectedMeta.tool_raw_data && (
                <div className="meta-section">
                  <strong>🔧 Tool Calls Made:</strong>
                  <pre className="meta-data">{JSON.stringify(selectedMeta.tool_raw_data, null, 2)}</pre>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

