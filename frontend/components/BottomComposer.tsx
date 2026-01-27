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

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const value = e.target.value;
    const cursorPos = e.target.selectionStart;
    setInput(value);
    setCursorPosition(cursorPos);
    
    // Check for @ symbol for tool suggestions
    const textBeforeCursor = value.substring(0, cursorPos);
    const lastAtIndex = textBeforeCursor.lastIndexOf('@');
    
    if (lastAtIndex !== -1) {
      const textAfterAt = textBeforeCursor.substring(lastAtIndex + 1);
      // Check if we're still in a tool call (no closing parenthesis yet, or inside parentheses)
      const openParenIndex = textAfterAt.indexOf('(');
      const closeParenIndex = textAfterAt.indexOf(')');
      
      if (openParenIndex === -1 || (openParenIndex !== -1 && (closeParenIndex === -1 || closeParenIndex > openParenIndex))) {
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

  const handleSend = () => {
    if (input.trim() && !disabled) {
      onSend(input);
      setInput('');
      setShowToolSuggestions(false);
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
      e.preventDefault();
      handleSend();
    } else if (e.key === 'Escape') {
      setShowToolSuggestions(false);
    } else if (e.key === 'ArrowDown' && showToolSuggestions && toolSuggestions.length > 0) {
      e.preventDefault();
      // Could implement keyboard navigation here
    }
  };

  const insertToolCall = (tool: ToolDefinition) => {
    const textBeforeCursor = input.substring(0, cursorPosition);
    const textAfterCursor = input.substring(cursorPosition);
    const lastAtIndex = textBeforeCursor.lastIndexOf('@');
    
    // Build argument template with placeholders
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
    
    // Focus back on textarea and position cursor after @tool_name(
    setTimeout(() => {
      const newCursorPos = lastAtIndex + 1 + tool.name.length + 2; // After @tool_name(
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
              <div style={{ fontSize: '11px', color: 'var(--text-secondary)', fontFamily: 'monospace', opacity: 0.8 }}>
                ({tool.args.map(a => `${a.name}${a.required ? '' : '?'}`).join(', ')})
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

