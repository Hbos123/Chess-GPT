/**
 * PGN Context Detector
 * 
 * Intelligently detects the starting FEN for PGN sequences based on:
 * - Move numbers in the sequence
 * - Current board position
 * - Context clues in the text
 * 
 * This fixes the bug where PGN parser tries to replay moves that
 * have already been played on the current board.
 */

import { Chess } from 'chess.js';

export interface PGNContext {
  startFEN: string;
  reason: 'starting_position' | 'current_position' | 'detected_earlier';
}

/**
 * Detect the appropriate starting FEN for parsing a PGN sequence.
 * 
 * @param pgnText The PGN sequence text (e.g., "1. e4 e5 2. Nf3")
 * @param currentFEN The current board FEN
 * @returns The FEN to use as starting point for parsing
 */
export function detectPGNStartingFEN(pgnText: string, currentFEN: string): PGNContext {
  const STARTING_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";
  
  // Extract move numbers from the PGN text
  const moveNumbers = extractMoveNumbers(pgnText);
  
  if (moveNumbers.length === 0) {
    // No move numbers found, use current position
    return {
      startFEN: currentFEN,
      reason: 'current_position'
    };
  }
  
  const firstMoveNum = Math.min(...moveNumbers);
  const currentMoveNum = getCurrentMoveNumber(currentFEN);
  
  // Strategy 1: If sequence starts with move 1, use starting position
  if (firstMoveNum === 1 && currentMoveNum > 1) {
    return {
      startFEN: STARTING_FEN,
      reason: 'starting_position'
    };
  }
  
  // Strategy 2: If sequence starts with current or future move, use current position
  if (firstMoveNum >= currentMoveNum) {
    return {
      startFEN: currentFEN,
      reason: 'current_position'
    };
  }
  
  // Strategy 3: Sequence references earlier moves than current position
  // Try to detect if we should use starting position
  if (firstMoveNum === 1 || (currentMoveNum - firstMoveNum) > 3) {
    return {
      startFEN: STARTING_FEN,
      reason: 'detected_earlier'
    };
  }
  
  // Default: use current position
  return {
    startFEN: currentFEN,
    reason: 'current_position'
  };
}

/**
 * Extract all move numbers from PGN text.
 * E.g., "1. e4 e5 2. Nf3" → [1, 2]
 */
function extractMoveNumbers(pgnText: string): number[] {
  const numbers: number[] = [];
  
  // Match patterns like "1.", "2.", "10."
  const pattern = /(\d+)\./g;
  let match;
  
  while ((match = pattern.exec(pgnText)) !== null) {
    const num = parseInt(match[1]);
    if (!isNaN(num) && num > 0) {
      numbers.push(num);
    }
  }
  
  return numbers;
}

/**
 * Get the current full move number from a FEN string.
 * E.g., "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1" → 1
 */
function getCurrentMoveNumber(fen: string): number {
  const parts = fen.split(' ');
  
  if (parts.length < 6) {
    return 1; // Invalid FEN, assume starting position
  }
  
  const moveNum = parseInt(parts[5]);
  return isNaN(moveNum) ? 1 : moveNum;
}

/**
 * Check if a PGN sequence likely starts from the starting position
 * based on contextual clues in the text.
 */
export function sequenceStartsFromBeginning(pgnText: string, surroundingText: string): boolean {
  const lowerText = surroundingText.toLowerCase();
  const lowerPGN = pgnText.toLowerCase();
  
  // Contextual clues that indicate starting position
  const startingClues = [
    'from the beginning',
    'from the start',
    'opening moves',
    'main line',
    '1. e4',
    '1. d4',
    'game starts',
    'initial position'
  ];
  
  for (const clue of startingClues) {
    if (lowerText.includes(clue) || lowerPGN.includes(clue)) {
      return true;
    }
  }
  
  // If PGN starts with "1. " it likely wants starting position
  if (pgnText.trim().match(/^1\.\s/)) {
    return true;
  }
  
  return false;
}

/**
 * Smart FEN detection for PGN parsing.
 * 
 * @param pgnText The PGN sequence
 * @param currentFEN Current board FEN
 * @param fullMessageText Full message text for context
 * @returns FEN to use for parsing
 */
export function detectSmartFEN(
  pgnText: string, 
  currentFEN: string,
  fullMessageText?: string
): string {
  const STARTING_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";
  
  // Use context detector
  const context = detectPGNStartingFEN(pgnText, currentFEN);
  
  // If we have surrounding text, check for additional clues
  if (fullMessageText && sequenceStartsFromBeginning(pgnText, fullMessageText)) {
    return STARTING_FEN;
  }
  
  return context.startFEN;
}

