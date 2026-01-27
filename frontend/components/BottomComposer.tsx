import { useState, useEffect, useRef } from 'react';
import { AVAILABLE_TOOLS, type ToolDefinition } from '@/lib/toolDefinitions';

interface BottomComposerProps {
  onSend: (message: string) => void;
  disabled?: boolean;
  placeholder?: string;
  onOpenOptions?: () => void;
  optionsDisabled?: boolean;
  lightningMode?: boolean;
  isProcessing?: boolean;
  onCancel?: () => void;
}

export default function BottomComposer({ 
  onSend, 
  disabled = false,
  placeholder = "Ask about the position...",
  onOpenOptions,
  optionsDisabled,
  lightningMode = false,
  isProcessing = false,
  onCancel,
}: BottomComposerProps) {
  const [input, setInput] = useState('');
  const [showToolSuggestions, setShowToolSuggestions] = useState(false);
  const [toolSuggestions, setToolSuggestions] = useState<ToolDefinition[]>([]);
  const [suggestionPosition, setSuggestionPosition] = useState({ top: 0, left: 0 });
  const [cursorPosition, setCursorPosition] = useState(0);
  const [showArgHints, setShowArgHints] = useState(false);
  const [currentTool, setCurrentTool] = useState<ToolDefinition | null>(null);
  const [argHintsPosition, setArgHintsPosition] = useState({ top: 0, left: 0 });
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const warmUpTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const hasWarmedUpRef = useRef(false);

  // Warm up interpreter API when user starts typing
  useEffect(() => {
    if (input.trim().length > 0 && !hasWarmedUpRef.current) {
      // Clear existing timeout
      if (warmUpTimeoutRef.current) {
        clearTimeout(warmUpTimeoutRef.current);
      }
      
      // Debounce: warm up after 300ms of typing
      warmUpTimeoutRef.current = setTimeout(() => {
        const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
        // Fire-and-forget warm-up request
        fetch(`${backendUrl}/warmup/interpreter`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({}),
        }).catch(() => {
          // Ignore errors - this is just a warm-up
        });
        hasWarmedUpRef.current = true;
      }, 300);
    }
    
    return () => {
      if (warmUpTimeoutRef.current) {
        clearTimeout(warmUpTimeoutRef.current);
      }
    };
  }, [input]);

  // Check if cursor is inside parentheses and show argument hints
  const checkForArgHints = (value: string, cursorPos: number) => {
    const textBeforeCursor = value.substring(0, cursorPos);
    const lastAtIndex = textBeforeCursor.lastIndexOf('@');
    
    if (lastAtIndex === -1) {
      setShowArgHints(false);
      setCurrentTool(null);
      return;
    }
    
    const textAfterAt = textBeforeCursor.substring(lastAtIndex + 1);
    const openParenIndex = textAfterAt.indexOf('(');
    const closeParenIndex = textAfterAt.indexOf(')');
    
    // Check if cursor is inside parentheses
    if (openParenIndex !== -1 && (closeParenIndex === -1 || closeParenIndex > openParenIndex)) {
      // Cursor is inside parentheses - find the tool
      const toolName = textAfterAt.substring(0, openParenIndex).trim();
      const tool = AVAILABLE_TOOLS.find(t => t.name === toolName);
      
      if (tool) {
        setCurrentTool(tool);
        setShowArgHints(true);
        
        // Position arg hints popup above cursor
        if (textareaRef.current) {
          const rect = textareaRef.current.getBoundingClientRect();
          const lineHeight = 24;
          const lines = textBeforeCursor.split('\n').length;
          setArgHintsPosition({
            top: rect.top + (lines * lineHeight) - 200,
            left: rect.left + 10
          });
        }
      } else {
        setShowArgHints(false);
        setCurrentTool(null);
      }
    } else {
      setShowArgHints(false);
      setCurrentTool(null);
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const value = e.target.value;
    const cursorPos = e.target.selectionStart;
    setInput(value);
    setCursorPosition(cursorPos);
    
    // Check for argument hints first
    checkForArgHints(value, cursorPos);
    
    // Check for @ symbol for tool suggestions
    const textBeforeCursor = value.substring(0, cursorPos);
    const lastAtIndex = textBeforeCursor.lastIndexOf('@');
    
    if (lastAtIndex !== -1) {
      const textAfterAt = textBeforeCursor.substring(lastAtIndex + 1);
      // Check if we're still in a tool call (no closing parenthesis yet, or inside parentheses)
      const openParenIndex = textAfterAt.indexOf('(');
      const closeParenIndex = textAfterAt.indexOf(')');
      
      // Only show tool suggestions if we're NOT inside parentheses
      if (openParenIndex === -1 || (openParenIndex !== -1 && closeParenIndex !== -1 && closeParenIndex < openParenIndex)) {
        // Show suggestions
        const searchTerm = textAfterAt.split('(')[0].trim();
        const filtered = AVAILABLE_TOOLS.filter(tool => 
          tool.name.toLowerCase().includes(searchTerm.toLowerCase())
        );
        setToolSuggestions(filtered);
        setShowToolSuggestions(filtered.length > 0);
        
        // Position popup above cursor
        if (textareaRef.current) {
          const rect = textareaRef.current.getBoundingClientRect();
          const lineHeight = 24;
          const lines = textBeforeCursor.split('\n').length;
          setSuggestionPosition({
            top: rect.top + (lines * lineHeight) - 250,
            left: rect.left + 10
          });
        }
      } else {
        setShowToolSuggestions(false);
      }
    } else {
      setShowToolSuggestions(false);
    }
  };

  // Auto-complete tool call when Enter is pressed
  const autoCompleteToolCall = (): boolean => {
    const textBeforeCursor = input.substring(0, cursorPosition);
    const textAfterCursor = input.substring(cursorPosition);
    const lastAtIndex = textBeforeCursor.lastIndexOf('@');
    
    if (lastAtIndex === -1) return false;
    
    const textAfterAt = textBeforeCursor.substring(lastAtIndex + 1);
    const openParenIndex = textAfterAt.indexOf('(');
    
    // If we're typing a tool name (before opening paren or no paren yet)
    if (openParenIndex === -1) {
      const searchTerm = textAfterAt.trim();
      if (searchTerm.length === 0) return false;
      
      // Find exact match or best match
      const exactMatch = AVAILABLE_TOOLS.find(t => t.name.toLowerCase() === searchTerm.toLowerCase());
      const bestMatch = AVAILABLE_TOOLS.find(t => 
        t.name.toLowerCase().startsWith(searchTerm.toLowerCase())
      );
      
      const tool = exactMatch || bestMatch;
      if (tool) {
        // Complete the tool call
        const argTemplate = tool.args
          .map(arg => arg.required ? `-` : `-`)
          .join(',');
        
        const toolCall = `@${tool.name}(${argTemplate})`;
        const newText = 
          input.substring(0, lastAtIndex + 1) + 
          toolCall + 
          textAfterCursor;
        
        setInput(newText);
        setShowToolSuggestions(false);
        
        // Position cursor after @tool_name(
        setTimeout(() => {
          const newCursorPos = lastAtIndex + 1 + tool.name.length + 2;
          textareaRef.current?.setSelectionRange(newCursorPos, newCursorPos);
          textareaRef.current?.focus();
        }, 0);
        
        return true; // Indicate we handled the Enter key
      }
    }
    
    return false;
  };

  const handleSend = () => {
    if (input.trim() && !disabled) {
      onSend(input);
      setInput('');
      setShowToolSuggestions(false);
      setShowArgHints(false);
      setCurrentTool(null);
      hasWarmedUpRef.current = false; // Reset for next message
    }
  };

  const handleCancel = () => {
    if (onCancel) {
      onCancel();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      // Try to auto-complete tool call first
      if (autoCompleteToolCall()) {
        e.preventDefault();
        return;
      }
      
      // Otherwise, send message
      e.preventDefault();
      handleSend();
    } else if (e.key === 'Escape') {
      setShowToolSuggestions(false);
      setShowArgHints(false);
    } else if (e.key === 'ArrowDown' && showToolSuggestions && toolSuggestions.length > 0) {
      e.preventDefault();
      // Could implement keyboard navigation here
    }
  };

  const insertToolCall = (tool: ToolDefinition) => {
    const textBeforeCursor = input.substring(0, cursorPosition);
    const textAfterCursor = input.substring(cursorPosition);
    const lastAtIndex = textBeforeCursor.lastIndexOf('@');
    
    if (lastAtIndex === -1) {
      // No @ found, just insert at cursor
      const argTemplate = tool.args
        .map(arg => arg.required ? `-` : `-`)
        .join(',');
      
      const toolCall = `@${tool.name}(${argTemplate})`;
      const newText = textBeforeCursor + toolCall + textAfterCursor;
      
      setInput(newText);
      setShowToolSuggestions(false);
      
      setTimeout(() => {
        const newCursorPos = textBeforeCursor.length + tool.name.length + 3; // After @tool_name(
        textareaRef.current?.setSelectionRange(newCursorPos, newCursorPos);
        textareaRef.current?.focus();
      }, 0);
      return;
    }
    
    // Replace the partial tool call
    const textAfterAt = textBeforeCursor.substring(lastAtIndex + 1);
    const openParenIndex = textAfterAt.indexOf('(');
    
    let replacementStart: number;
    let replacementEnd: number;
    
    if (openParenIndex === -1) {
      // No opening paren yet - replace from @ to cursor
      replacementStart = lastAtIndex;
      replacementEnd = cursorPosition;
    } else {
      // Opening paren exists - replace from @ to cursor
      replacementStart = lastAtIndex;
      replacementEnd = cursorPosition;
    }
    
    // Build argument template with placeholders
    const argTemplate = tool.args
      .map(arg => arg.required ? `-` : `-`)
      .join(',');
    
    const toolCall = `@${tool.name}(${argTemplate})`;
    const newText = 
      input.substring(0, replacementStart) + 
      toolCall + 
      input.substring(replacementEnd);
    
    setInput(newText);
    setShowToolSuggestions(false);
    
    // Focus back on textarea and position cursor after @tool_name(
    setTimeout(() => {
      const newCursorPos = replacementStart + tool.name.length + 3; // After @tool_name(
      textareaRef.current?.setSelectionRange(newCursorPos, newCursorPos);
      textareaRef.current?.focus();
    }, 0);
  };

  const isOptionsDisabled = optionsDisabled ?? disabled;

  return (
    <div className="bottom-composer">
      <div className="composer-inner">
        <textarea
          ref={textareaRef}
          value={input}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          className="bottom-input"
          rows={1}
          disabled={disabled}
        />
        <div className="composer-side">
          {onOpenOptions && (
            <button
              type="button"
              className="options-button"
              onClick={onOpenOptions}
              disabled={isOptionsDisabled}
              title="Open manual request options"
            >
              Options
            </button>
          )}
          <button 
            className="send-button"
            onClick={isProcessing ? handleCancel : handleSend}
            disabled={!isProcessing && (!input.trim() || disabled)}
            style={isProcessing ? { backgroundColor: 'var(--error-color)', color: 'white' } : {}}
          >
            {isProcessing ? 'Stop' : (disabled ? 'Analyzing...' : 'Send')}
          </button>
        </div>
      </div>
      
      {/* Tool Suggestions Popup */}
      {showToolSuggestions && toolSuggestions.length > 0 && (
        <div 
          className="tool-suggestions-popup"
          style={{
            position: 'fixed',
            top: suggestionPosition.top,
            left: suggestionPosition.left,
            background: 'var(--bg-primary)',
            border: '1px solid var(--border-color)',
            borderRadius: '8px',
            padding: '8px',
            maxHeight: '200px',
            overflowY: 'auto',
            zIndex: 1000,
            boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
            minWidth: '280px',
            maxWidth: '400px'
          }}
          onClick={(e) => e.stopPropagation()}
        >
          {toolSuggestions.map((tool, idx) => (
            <div
              key={idx}
              onClick={() => insertToolCall(tool)}
              style={{
                padding: '10px 12px',
                cursor: 'pointer',
                borderRadius: '4px',
                marginBottom: '4px',
                background: 'transparent',
                transition: 'background 0.2s',
                border: '1px solid transparent'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'var(--bg-secondary)';
                e.currentTarget.style.borderColor = 'var(--accent-primary)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'transparent';
                e.currentTarget.style.borderColor = 'transparent';
              }}
            >
              <div style={{ fontWeight: '600', fontSize: '14px', color: 'var(--accent-primary)', marginBottom: '4px' }}>
                @{tool.name}
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '6px', lineHeight: '1.4' }}>
                {tool.description}
              </div>
              <div style={{ fontSize: '11px', color: 'var(--text-secondary)', fontFamily: 'monospace', opacity: '0.8' }}>
                ({tool.args.map(a => `${a.name}${a.required ? '' : '?'}`).join(', ')})
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Argument Hints Popup - shows when cursor is inside parentheses */}
      {showArgHints && currentTool && (
        <div 
          className="arg-hints-popup"
          style={{
            position: 'fixed',
            top: argHintsPosition.top,
            left: argHintsPosition.left,
            background: 'var(--bg-primary)',
            border: '1px solid var(--border-color)',
            borderRadius: '8px',
            padding: '12px',
            maxWidth: '350px',
            zIndex: 1001,
            boxShadow: '0 4px 12px rgba(0,0,0,0.15)'
          }}
          onClick={(e) => e.stopPropagation()}
        >
          <div style={{ fontWeight: '600', fontSize: '13px', color: 'var(--accent-primary)', marginBottom: '8px' }}>
            @{currentTool.name} Arguments:
          </div>
          <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
            {currentTool.args.map((arg, idx) => (
              <div 
                key={idx}
                style={{ 
                  marginBottom: '6px',
                  paddingLeft: '8px',
                  borderLeft: `2px solid ${arg.required ? 'var(--error-color)' : 'var(--border-color)'}`
                }}
              >
                <div style={{ fontWeight: '500', color: 'var(--text-primary)', marginBottom: '2px' }}>
                  {arg.name}
                  {arg.required && <span style={{ color: 'var(--error-color)', marginLeft: '4px' }}>*</span>}
                  <span style={{ fontSize: '11px', color: 'var(--text-secondary)', marginLeft: '6px', fontFamily: 'monospace' }}>
                    ({arg.type})
                  </span>
                </div>
                <div style={{ fontSize: '11px', color: 'var(--text-secondary)', lineHeight: '1.4' }}>
                  {arg.description}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
