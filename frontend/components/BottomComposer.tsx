import { useState } from 'react';

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

  const handleSend = () => {
    if (input.trim() && !disabled) {
      onSend(input);
      setInput('');
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

