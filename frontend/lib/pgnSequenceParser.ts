import { Chess } from 'chess.js';
import { detectSmartFEN } from './pgnContextDetector';

export interface PGNMove {
  moveNumber: number;
  white?: string;
  black?: string;
  whiteUCI?: string;
  blackUCI?: string;
  fenAfterWhite?: string;
  fenAfterBlack?: string;
}

export interface PGNSequence {
  moves: PGNMove[];
  startFEN: string;
  endFEN: string;
  fullPGN: string;
}

/**
 * Parse PGN sequences from text like "1. e4 e5 2. Nf3 Nc6 3. Bc4"
 * Also handles: "After 1...c5, the position might progress with 2. Nf3 Nc6 3. d4"
 * Returns sequences with FEN at each move for hover preview
 */
export function parsePGNSequences(text: string, currentFEN: string): PGNSequence[] {
  const sequences: PGNSequence[] = [];
  
  // Strategy: Find ALL individual move notations, then group consecutive ones
  // Match patterns like "1. e4", "1... e5", "2. Nf3"
  const allMoveMatches: Array<{
    index: number;
    moveNumber: number;
    isBlackMove: boolean;
    moveText: string;
    fullMatch: string;
  }> = [];
  
  // Pattern: number + dot + optional ellipsis + move
  const singleMovePattern = /(\d+)\.\s*(\.\.\.?\s*)?([NBRQK]?[a-h]?[1-8]?x?[a-h][1-8](?:=[NBRQ])?[+#]?|O-O(?:-O)?)/g;
  
  let match;
  while ((match = singleMovePattern.exec(text)) !== null) {
    const moveNumber = parseInt(match[1]);
    const hasEllipsis = !!match[2];
    const moveText = match[3];
    
    allMoveMatches.push({
      index: match.index,
      moveNumber,
      isBlackMove: hasEllipsis,
      moveText,
      fullMatch: match[0]
    });
  }
  
  if (allMoveMatches.length === 0) return sequences;
  
  // Group consecutive moves into sequences
  // Consecutive means: indices are close together (within 100 chars)
  const groups: typeof allMoveMatches[] = [];
  let currentGroup: typeof allMoveMatches = [allMoveMatches[0]];
  
  for (let i = 1; i < allMoveMatches.length; i++) {
    const prev = allMoveMatches[i - 1];
    const curr = allMoveMatches[i];
    
    // If moves are close together and move numbers make sense, group them
    const closeEnough = curr.index - (prev.index + prev.fullMatch.length) < 100;
    const numbersConsecutive = curr.moveNumber <= prev.moveNumber + 1;
    
    if (closeEnough && numbersConsecutive) {
      currentGroup.push(curr);
    } else {
      groups.push(currentGroup);
      currentGroup = [curr];
    }
  }
  groups.push(currentGroup);
  
  // Parse each group
  for (const group of groups) {
    if (group.length === 0) continue;
    
    try {
      // Extract the PGN text first to help with context detection
      const firstIndex = group[0].index;
      const lastMatch = group[group.length - 1];
      const lastIndex = lastMatch.index + lastMatch.fullMatch.length;
      const fullPGN = text.substring(firstIndex, lastIndex);
      
      // Use smart FEN detection to avoid "Invalid move" errors
      const startingFEN = detectSmartFEN(fullPGN, currentFEN, text);
      
      const chess = new Chess(startingFEN);
      const parsedMoves: PGNMove[] = [];
      const startFEN = chess.fen();
      
      for (const moveMatch of group) {
        const { moveNumber, moveText, isBlackMove } = moveMatch;
        
        // Find or create the move data for this number
        let moveData = parsedMoves.find(m => m.moveNumber === moveNumber);
        if (!moveData) {
          moveData = { moveNumber };
          parsedMoves.push(moveData);
        }
        
        // Apply the move
        const move = chess.move(moveText);
        if (!move) {
          // Invalid move, abort this sequence
          break;
        }
        
        if (isBlackMove || chess.turn() === 'w') {
          // This was black's move (we just played it, now it's white's turn)
          moveData.black = moveText;
          moveData.blackUCI = move.from + move.to + (move.promotion || '');
          moveData.fenAfterBlack = chess.fen();
        } else {
          // This was white's move (we just played it, now it's black's turn)
          moveData.white = moveText;
          moveData.whiteUCI = move.from + move.to + (move.promotion || '');
          moveData.fenAfterWhite = chess.fen();
        }
      }
      
      if (parsedMoves.length > 0) {
        const seq = {
          moves: parsedMoves,
          startFEN,
          endFEN: chess.fen(),
          fullPGN
        };
        console.log('[PGN Parser] Found sequence:', fullPGN, '→', seq.endFEN);
        sequences.push(seq);
      }
    } catch (e) {
      console.warn('Failed to parse PGN sequence:', group, e);
    }
  }
  
  return sequences;
}

/**
 * Find PGN sequences in text and return their positions for underlining
 * This uses the same grouping logic as parsePGNSequences
 */
export function findPGNRanges(text: string): Array<{ start: number; end: number; sequence: string }> {
  const ranges: Array<{ start: number; end: number; sequence: string }> = [];
  
  // Find ALL individual move notations
  const allMoveMatches: Array<{
    index: number;
    moveNumber: number;
    fullMatch: string;
  }> = [];
  
  const singleMovePattern = /(\d+)\.\s*(\.\.\.?\s*)?([NBRQK]?[a-h]?[1-8]?x?[a-h][1-8](?:=[NBRQ])?[+#]?|O-O(?:-O)?)/g;
  
  let match;
  while ((match = singleMovePattern.exec(text)) !== null) {
    allMoveMatches.push({
      index: match.index,
      moveNumber: parseInt(match[1]),
      fullMatch: match[0]
    });
  }
  
  if (allMoveMatches.length === 0) return ranges;
  
  // Group consecutive moves
  const groups: typeof allMoveMatches[] = [];
  let currentGroup: typeof allMoveMatches = [allMoveMatches[0]];
  
  for (let i = 1; i < allMoveMatches.length; i++) {
    const prev = allMoveMatches[i - 1];
    const curr = allMoveMatches[i];
    
    const closeEnough = curr.index - (prev.index + prev.fullMatch.length) < 100;
    const numbersConsecutive = curr.moveNumber <= prev.moveNumber + 1;
    
    if (closeEnough && numbersConsecutive) {
      currentGroup.push(curr);
    } else {
      groups.push(currentGroup);
      currentGroup = [curr];
    }
  }
  groups.push(currentGroup);
  
  // Convert groups to ranges
  for (const group of groups) {
    if (group.length === 0) continue;
    
    const firstIndex = group[0].index;
    const lastMatch = group[group.length - 1];
    const lastIndex = lastMatch.index + lastMatch.fullMatch.length;
    
    ranges.push({
      start: firstIndex,
      end: lastIndex,
      sequence: text.substring(firstIndex, lastIndex)
    });
  }
  
  return ranges;
}

