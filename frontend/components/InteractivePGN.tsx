import { useState } from 'react';
import { parsePGNSequences, PGNSequence } from '@/lib/pgnSequenceParser';

interface InteractivePGNProps {
  text: string;
  currentFEN: string;
  onApplySequence?: (fen: string, pgn: string) => void;
  onHoverMove?: (fen: string | null) => void;
}

function renderMarkdown(text: string) {
  let html = text;
  
  // 1. Escape HTML entities for security (do this first)
  html = html
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
  
  // 2. Replace ## with double line break (simple - just insert <br/><br/> and remove ##)
  html = html.replace(/##\s*/g, '<br /><br />');
  
  // 3. Replace **text** with <strong>text</strong> (toggle bold on/off)
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  
  // 4. Convert newlines to breaks
  html = html.replace(/\n/g, '<br />');
  
  // 5. Clean up multiple consecutive line breaks
  html = html.replace(/(<br \/>){3,}/g, '<br /><br />');
  
  return html;
}

export default function InteractivePGN({ text, currentFEN, onApplySequence, onHoverMove }: InteractivePGNProps) {
  const [sequences] = useState(() => parsePGNSequences(text, currentFEN));
  
  if (sequences.length === 0) {
    // No PGN sequences found, return markdown-rendered text
    return <span dangerouslySetInnerHTML={{ __html: renderMarkdown(text) }} />;
  }
  
  // Split text into parts: plain text and PGN sequences
  const parts: Array<{ type: 'text' | 'pgn'; content: string; sequence?: PGNSequence }> = [];
  let lastIndex = 0;
  
  sequences.forEach((seq) => {
    const seqIndex = text.indexOf(seq.fullPGN, lastIndex);
    if (seqIndex >= lastIndex) {
      // Add plain text before this sequence
      if (seqIndex > lastIndex) {
        parts.push({ type: 'text', content: text.substring(lastIndex, seqIndex) });
      }
      // Add PGN sequence
      parts.push({ type: 'pgn', content: seq.fullPGN, sequence: seq });
      lastIndex = seqIndex + seq.fullPGN.length;
    }
  });
  
  // Add remaining text
  if (lastIndex < text.length) {
    parts.push({ type: 'text', content: text.substring(lastIndex) });
  }
  
  return (
    <>
      {parts.map((part, idx) => {
        if (part.type === 'text') {
          return <span key={idx} dangerouslySetInnerHTML={{ __html: renderMarkdown(part.content) }} />;
        } else if (part.type === 'pgn' && part.sequence) {
          return (
            <PGNSequenceSpan
              key={idx}
              sequence={part.sequence}
              onApply={onApplySequence}
              onHover={onHoverMove}
            />
          );
        }
        return null;
      })}
    </>
  );
}

interface PGNSequenceSpanProps {
  sequence: PGNSequence;
  onApply?: (fen: string, pgn: string) => void;
  onHover?: (fen: string | null) => void;
}

function PGNSequenceSpan({ sequence, onApply, onHover }: PGNSequenceSpanProps) {
  const [hoveredFEN, setHoveredFEN] = useState<string | null>(null);
  
  const handleClick = () => {
    if (onApply) {
      onApply(sequence.endFEN, sequence.fullPGN);
    }
  };
  
  const handleMouseEnter = () => {
    if (onHover) {
      onHover(sequence.endFEN);
    }
  };
  
  const handleMouseLeave = () => {
    if (onHover) {
      onHover(null);
    }
  };
  
  return (
    <span
      className="pgn-sequence"
      onClick={handleClick}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      title={`Click to apply this sequence\nHover to preview`}
    >
      {sequence.fullPGN}
    </span>
  );
}

