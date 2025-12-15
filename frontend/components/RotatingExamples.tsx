import { useState, useEffect } from 'react';

const EXAMPLES = [
  "Analyze my position after 1. e4 e5 2. Nf3",
  "Review my last 5 games from Chess.com",
  "What's the best move in this position?",
  "Create training on my tactical mistakes",
  "Teach me the Italian Game opening",
  "Is Nf3 a good move here?",
  "How can I improve my endgame play?",
  "Explain the Sicilian Defense",
  "What are my weak squares?",
  "Should I trade my bishop for their knight?"
];

// Hook to get rotating placeholder text with fade animation state
export function useRotatingPlaceholder() {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isVisible, setIsVisible] = useState(true);

  useEffect(() => {
    const interval = setInterval(() => {
      // Fade out
      setIsVisible(false);
      
      // Change text after fade completes
      setTimeout(() => {
        setCurrentIndex((prev) => (prev + 1) % EXAMPLES.length);
        setIsVisible(true);
      }, 300);
    }, 4000);

    return () => clearInterval(interval);
  }, []);

  return { text: EXAMPLES[currentIndex], isVisible };
}

// Default export (no longer renders anything visible)
export default function RotatingExamples() {
  return null;
}

