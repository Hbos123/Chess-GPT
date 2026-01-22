interface LoadingMessageProps {
  type: 'stockfish' | 'llm' | 'game_review' | 'training' | 'general';
  message?: string;
}

export default function LoadingMessage({ type, message }: LoadingMessageProps) {
  const getLoadingText = () => {
    if (message) return message;
    
    switch (type) {
      case 'stockfish':
        return 'Analyzing position with Stockfish...';
      case 'llm':
        return 'Generating response...';
      case 'game_review':
        return 'Reviewing game...';
      case 'training':
        return 'Generating training...';
      default:
        return 'Processing...';
    }
  };

  const getIcon = () => {
    switch (type) {
      case 'stockfish':
        return '⚙️';
      case 'llm':
        return '💭';
      case 'game_review':
        return '📊';
      case 'training':
        return '🎯';
      default:
        return '⏳';
    }
  };

  return (
    <div className="loading-message">
      <div className="loading-content">
        <span className="loading-icon">{getIcon()}</span>
        <span className="loading-text">{getLoadingText()}</span>
        <span className="loading-dots">
          <span className="dot">.</span>
          <span className="dot">.</span>
          <span className="dot">.</span>
        </span>
      </div>
    </div>
  );
}




