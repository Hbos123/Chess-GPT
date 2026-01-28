import { useState, useEffect, useRef, useCallback } from 'react';
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
  const argHintsDebounceRef = useRef<NodeJS.Timeout | null>(null);

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

  // Enhanced function to update argument hints position based on cursor
  const updateArgHintsPosition = useCallback((cursorPos: number) => {
    if (!textareaRef.current) return;
    
    const textBeforeCursor = input.substring(0, cursorPos);
    const rect = textareaRef.current.getBoundingClientRect();
    const style = window.getComputedStyle(textareaRef.current);
    const lineHeight = parseInt(style.lineHeight) || 24;
    const paddingLeft = parseInt(style.paddingLeft) || 8;
    const paddingTop = parseInt(style.paddingTop) || 8;
    
    // Calculate line and column
    const lines = textBeforeCursor.split('\n');
    const currentLine = lines.length - 1;
    const currentColumn = lines[currentLine].length;
    
    // Estimate character width (approximate for monospace-like fonts)
    const charWidth = 7.5;
    const x = paddingLeft + (currentColumn * charWidth);
    const y = paddingTop + (currentLine * lineHeight);
    
    // Position popup above and to the right of cursor
    setArgHintsPosition({
      top: rect.top + y - 220, // Position above cursor
      left: Math.min(rect.left + x + 20, window.innerWidth - 370) // Keep within viewport
    });
  }, [input]);

  // Enhanced check if cursor is inside parentheses and show argument hints
  const checkForArgHints = useCallback((value: string, cursorPos: number) => {
    // Clear any existing debounce
    if (argHintsDebounceRef.current) {
      clearTimeout(argHintsDebounceRef.current);
    }
    
    // Debounce to prevent flickering on rapid cursor movement
    argHintsDebounceRef.current = setTimeout(() => {
      const textBeforeCursor = value.substring(0, cursorPos);
      const textAfterCursor = value.substring(cursorPos);
      
      // Find the most recent @ symbol before cursor
      const lastAtIndex = textBeforeCursor.lastIndexOf('@');
      
      if (lastAtIndex === -1) {
        setShowArgHints(false);
        setCurrentTool(null);
        return;
      }
      
      const textAfterAt = textBeforeCursor.substring(lastAtIndex + 1);
      const openParenIndex = textAfterAt.indexOf('(');
      
      // No opening paren yet - don't show hints
      if (openParenIndex === -1) {
        setShowArgHints(false);
        setCurrentTool(null);
        return;
      }
      
      // Extract tool name (everything between @ and opening paren)
      const toolName = textAfterAt.substring(0, openParenIndex).trim();
      
      // Find matching tool (case-insensitive)
      const tool = AVAILABLE_TOOLS.find(t => 
        t.name.toLowerCase() === toolName.toLowerCase()
      );
      
      if (!tool) {
        setShowArgHints(false);
        setCurrentTool(null);
        return;
      }
      
      // Now check if cursor is actually inside the parentheses
      // Get text from opening paren to cursor
      const textInParens = textAfterAt.substring(openParenIndex + 1);
      
      // Count parentheses depth to handle nested cases
      let parenDepth = 1;
      let foundClosingParen = false;
      
      // Check text before cursor (within the parentheses)
      for (let i = 0; i < textInParens.length; i++) {
        if (textInParens[i] === '(') {
          parenDepth++;
        } else if (textInParens[i] === ')') {
          parenDepth--;
          if (parenDepth === 0) {
            foundClosingParen = true;
            // Cursor is at or after closing paren - not inside
            if (i < textInParens.length - 1 || textAfterCursor.trim().length > 0) {
              setShowArgHints(false);
              setCurrentTool(null);
              return;
            }
            break;
          }
        }
      }
      
      // If we haven't found a closing paren or depth > 0, cursor is inside
      const isInsideParens = !foundClosingParen || parenDepth > 0;
      
      if (isInsideParens) {
        setCurrentTool(tool);
        setShowArgHints(true);
        updateArgHintsPosition(cursorPos);
      } else {
        setShowArgHints(false);
        setCurrentTool(null);
      }
    }, 50); // 50ms debounce
  }, [updateArgHintsPosition]);

  // Handler for cursor position changes (used by onClick and arrow keys)
  const handleCursorChange = useCallback(() => {
    if (!textareaRef.current) return;
    const cursorPos = textareaRef.current.selectionStart;
    setCursorPosition(cursorPos);
    checkForArgHints(input, cursorPos);
  }, [input, checkForArgHints]);

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const value = e.target.value;
    const cursorPos = e.target.selectionStart;
    setInput(value);
    setCursorPosition(cursorPos);
    
    // Check for argument hints
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
      
      // Clear debounce timeout
      if (argHintsDebounceRef.current) {
        clearTimeout(argHintsDebounceRef.current);
        argHintsDebounceRef.current = null;
      }
    }
  };
  
  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (argHintsDebounceRef.current) {
        clearTimeout(argHintsDebounceRef.current);
      }
    };
  }, []);

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
      setCurrentTool(null);
    } else if (e.key === 'ArrowDown' && showToolSuggestions && toolSuggestions.length > 0) {
      e.preventDefault();
      // Could implement keyboard navigation here
    } else if (['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(e.key)) {
      // Check cursor position after arrow key movement
      setTimeout(() => {
        handleCursorChange();
      }, 0);
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
          onClick={handleCursorChange}
          onKeyDown={handleKeyDown}
          onBlur={() => {
            // Optionally hide hints on blur, or keep them visible
            // Uncomment the next line if you want hints to disappear when clicking away
            // setShowArgHints(false);
          }}
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
