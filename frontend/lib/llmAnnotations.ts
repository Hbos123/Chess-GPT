/**
 * LLM Response → Board Annotations
 * 
 * Parses LLM chat responses to extract:
 * 1. Suggested moves → Draw arrows
 * 2. Referenced themes/tags → Apply visual annotations
 */

import { Chess } from 'chess.js';

export interface ParsedLLMAnnotations {
  moves: string[];              // e.g., ["Nf3", "d4", "Nc3"]
  themes: string[];             // e.g., ["S_CENTER_SPACE", "S_KING"]
  tags: string[];               // e.g., ["threat.capture.more_value", "outpost.knight.d5"]
  arrows: Array<{ from: string; to: string; color?: string }>;
  highlights: Array<{ sq: string; color?: string }>;  // Use 'sq' not 'square'
  labels?: Array<{ sq: string; text: string }>;
}

/**
 * Parse LLM response to extract moves and themes/tags
 */
export function parseLLMResponse(
  llmText: string,
  analysisData: any,
  currentFen: string
): ParsedLLMAnnotations {
  const result: ParsedLLMAnnotations = {
    moves: [],
    themes: [],
    tags: [],
    arrows: [],
    highlights: [],
    labels: []
  };

  // Extract move suggestions
  result.moves = extractMoves(llmText, currentFen);
  
  // Extract theme references (e.g., "S_CENTER_SPACE: -1.2" or "central space")
  result.themes = extractThemes(llmText, analysisData);
  
  // Extract tag references (e.g., "knight attacking queen", "semi-open e-file")
  result.tags = extractTags(llmText, analysisData);
  
  // Extract specific squares and pieces mentioned
  const specificAnnotations = extractSpecificMentions(llmText, currentFen);
  result.arrows.push(...specificAnnotations.arrows);
  result.highlights.push(...specificAnnotations.highlights);

  return result;
}

/**
 * Extract specific squares and pieces mentioned by LLM
 * e.g., "Bc4 targets f7" → arrow c4→f7, highlight f7
 * e.g., "controls d4 and e5" → highlight d4, e5
 */
function extractSpecificMentions(text: string, fen: string): {
  arrows: Array<{ from: string; to: string; color: string }>;
  highlights: Array<{ sq: string; color: string }>;
} {
  const result = { arrows: [], highlights: [] as any[] };
  const chess = new Chess(fen);
  
  // Extract all chess squares mentioned (e.g., "f7", "d4", "c3")
  const squarePattern = /\b([a-h][1-8])\b/g;
  const squares = [...new Set([...text.matchAll(squarePattern)].map(m => m[1]))];
  
  // Highlight mentioned squares (max 5 to avoid clutter)
  squares.slice(0, 5).forEach(sq => {
    result.highlights.push({ sq, color: 'rgba(76, 175, 80, 0.6)' });
  });
  
  // Extract piece + square mentions (e.g., "Bc4", "Nf3", "bishop to c4")
  const pieceMovePattern = /\b([NBRQK]?[a-h]?[1-8]?x?[a-h][1-8][\+#]?)\b/g;
  const pieceMoves = [...text.matchAll(pieceMovePattern)].map(m => m[1]);
  
  // Extract targeting/attacking patterns (e.g., "targets f7", "attacking c6")
  const targetPattern = /(target|attack|pressure|aim|threat|menace)[^.]*?([a-h][1-8])/gi;
  const targets = [...text.matchAll(targetPattern)];
  
  targets.forEach(match => {
    const targetSq = match[2];
    result.highlights.push({ sq: targetSq, color: 'rgba(244, 67, 54, 0.6)' }); // Red for targets
  });
  
  return result;
}

/**
 * Extract move suggestions from LLM text
 * Looks for patterns like:
 * - "Best is Nf3"
 * - "Play d4"
 * - "Consider Nc3"
 * - "Nf3 (-0.5cp)"
 */
function extractMoves(text: string, fen: string): string[] {
  const moves: string[] = [];
  const chess = new Chess(fen);
  
  // Common move suggestion patterns - including pawn moves (lowercase)
  const patterns = [
    /(?:best|top|play|consider|try|suggest)\s+(?:is|move)?\s*([A-Z][a-z]?[1-8](?:[xX\-=][a-z][1-8])?[+#]?)/gi,
    /(?:best|top|play|consider|try|suggest)\s+(?:is|move)?\s*([a-h][1-8](?:[xX\-=][a-z][1-8])?[+#]?)/gi, // Pawn moves
    /\b([A-Z][a-z]?[1-8](?:[xX\-=][a-z][1-8])?[+#]?)\s*\([^)]*cp\)/gi,  // "Nf3 (-20cp)"
    /\b([a-h][1-8](?:[xX\-=][a-z][1-8])?[+#]?)\s*\([^)]*cp\)/gi,  // "e6 (-39cp)"
    /\b([A-Z][a-z]?[1-8](?:[xX\-=][a-z][1-8])?[+#]?)\s+(?:is|would|maintains)/gi,
    /\b([a-h][1-8])\s+\((?:Black|White)\s+(?:aims|can|prepares)/gi  // "e6 (An option...)"
  ];
  
  for (const pattern of patterns) {
    const matches = text.matchAll(pattern);
    for (const match of matches) {
      const moveStr = match[1];
      try {
        // Validate move is legal
        const move = chess.move(moveStr);
        if (move) {
          moves.push(moveStr);
          chess.undo();
        }
      } catch (e) {
        // Invalid move, skip
      }
    }
  }
  
  return [...new Set(moves)]; // Deduplicate
}

/**
 * Extract theme references from text using comprehensive dictionary
 */
function extractThemes(text: string, analysisData: any): string[] {
  const { extractMentionedThemes } = require('@/lib/themeDictionary');
  return extractMentionedThemes(text);
}

/**
 * Extract tag references from text using smart matching
 */
function extractTags(text: string, analysisData: any): string[] {
  const { isTagMentioned } = require('@/lib/themeDictionary');
  const tags: string[] = [];
  
  // Get all tags from analysis data
  const allTags = getAllTagsFromAnalysis(analysisData);
  
  // Filter to only tags that are actually mentioned
  for (const tag of allTags) {
    if (isTagMentioned(tag, text)) {
      tags.push(tag.tag_name);
    }
  }
  
  return tags;
}

/**
 * Get all tags from analysis data structure
 */
function getAllTagsFromAnalysis(analysisData: any): any[] {
  const tags: any[] = [];
  
  if (analysisData?.white_analysis?.chunk_1_immediate?.tags) {
    tags.push(...analysisData.white_analysis.chunk_1_immediate.tags);
  }
  if (analysisData?.black_analysis?.chunk_1_immediate?.tags) {
    tags.push(...analysisData.black_analysis.chunk_1_immediate.tags);
  }
  
  return tags;
}

/**
 * Generate move arrows from suggested moves, checking against candidates
 * RULE: Only draw if move is in candidate list, use default semi-transparent green
 */
export function generateMoveArrows(
  moves: string[],
  fen: string,
  candidateMoves?: any[]
): Array<{ from: string; to: string; color: string }> {
  const arrows: Array<{ from: string; to: string; color: string }> = [];
  const chess = new Chess(fen);
  
  // Default semi-transparent green for all candidate moves
  const defaultGreen = 'rgba(76, 175, 80, 0.6)';
  
  moves.forEach((moveStr) => {
    try {
      const move = chess.move(moveStr);
      if (move) {
        // CHECK: Is this move in the candidate list?
        const candidateMatch = candidateMoves?.find(c => 
          c.move === moveStr || c.move === move.san
        );
        
        // ONLY draw if it's in the candidate list
        if (candidateMatch) {
          arrows.push({
            from: move.from,
            to: move.to,
            color: defaultGreen  // Use default semi-transparent green
          });
        }
        
        chess.undo();
      }
    } catch (e) {
      // Invalid move, skip
    }
  });
  
  return arrows;
}

