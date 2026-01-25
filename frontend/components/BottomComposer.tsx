import { useState, useEffect, useRef } from 'react';

interface BottomComposerProps {
  onSend: (message: string) => void;
  disabled?: boolean;
  placeholder?: string;
  onOpenOptions?: () => void;
  optionsDisabled?: boolean;
}

export default function BottomComposer({ 
  onSend, 
  disabled = false,
  placeholder = "Ask about the position...",
  onOpenOptions,
  optionsDisabled,
}: BottomComposerProps) {
  const [input, setInput] = useState('');
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

  const handleSend = () => {
    if (input.trim() && !disabled) {
      onSend(input);
      setInput('');
      hasWarmedUpRef.current = false; // Reset for next message
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const isOptionsDisabled = optionsDisabled ?? disabled;

  return (
    <div className="bottom-composer">
      <div className="composer-inner">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
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
            onClick={handleSend}
            disabled={!input.trim() || disabled}
          >
            {disabled ? 'Analyzing...' : 'Send'}
          </button>
        </div>
      </div>
    </div>
  );
}

