import { useState } from 'react';

interface HeroComposerProps {
  onFirstSend: (message: string) => void;
  onToggleBoard: () => void;
  onLoadGame: () => void;
  isBoardOpen: boolean;
  placeholder?: string;
  placeholderVisible?: boolean;
}

export default function HeroComposer({ 
  onFirstSend, 
  onToggleBoard, 
  onLoadGame,
  isBoardOpen,
  placeholder = "Ask about chess positions, analyze games, get training...",
  placeholderVisible = true
}: HeroComposerProps) {
  const [input, setInput] = useState('');

  const handleSend = () => {
    if (input.trim()) {
      onFirstSend(input);
      setInput('');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="hero-composer-container">
      <div className="hero-composer">
        <div className="hero-input-wrapper">
          {/* Custom animated placeholder overlay */}
          {!input && (
            <div className={`custom-placeholder ${placeholderVisible ? 'visible' : 'hidden'}`}>
              {placeholder}
            </div>
          )}
          
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder=""
            className="hero-input"
            autoFocus
          />
        </div>
        
        <button 
          className="send-button"
          onClick={handleSend}
          disabled={!input.trim()}
        >
          Send
        </button>
      </div>

      {/* Inline links snug under the composer */}
      <div className="hero-links">
        <button 
          className="board-toggle-link"
          onClick={onToggleBoard}
        >
          {isBoardOpen ? 'Hide' : 'Show'} chessboard
        </button>
        <button className="load-game-link-external" onClick={onLoadGame}>
          Load game
        </button>
      </div>
    </div>
  );
}

