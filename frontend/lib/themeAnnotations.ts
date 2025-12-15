/**
 * Theme-Based Board Annotations
 * Complete visual dictionary for chess themes and tags
 * 
 * Primitives:
 * - HL(sq) = highlight square
 * - ARROW(a→b) = directional arrow
 * - LABEL(sq, text) = text near square
 */

import { Chess } from 'chess.js';

export interface AnnotationSet {
  arrows: Array<{ from: string; to: string; color?: string }>;
  highlights: Array<{ sq: string; color?: string }>;  // Use 'sq' not 'square'
  labels?: Array<{ sq: string; text: string }>;
}

// Semi-transparent dark green as default, red only for threats
const COLORS = {
  default: 'rgba(76, 175, 80, 0.6)',    // DEFAULT - semi-transparent dark green
  red: 'rgba(244, 67, 54, 0.6)'         // ONLY for threats/dangers
};

/**
 * Generate annotations for referenced themes
 * NOTE: Only annotates tags, NOT themes. Theme mentions in text are often
 * negative ("fails to control center", "king safety concerns") and shouldn't
 * trigger positive highlights.
 */
export function generateThemeAnnotations(
  themes: string[],
  tags: any[],
  analysisData: any,
  fen: string,
  side: 'white' | 'black'
): AnnotationSet {
  const result: AnnotationSet = {
    arrows: [],
    highlights: []
  };
  
  const chess = new Chess(fen);
  
  // DISABLED: Theme-based annotations often fire incorrectly when LLM mentions
  // themes in negative context (e.g., "fails to control center", "king safety concerns")
  // Only process specific tags which have more precise semantics
  
  // for (const theme of themes) {
  //   const themeAnnotations = getThemeAnnotations(theme, analysisData, chess, side);
  //   result.arrows.push(...themeAnnotations.arrows);
  //   result.highlights.push(...themeAnnotations.highlights);
  // }
  
  for (const tag of tags) {
    const tagAnnotations = getTagAnnotations(tag, chess, side);
    result.arrows.push(...tagAnnotations.arrows);
    result.highlights.push(...tagAnnotations.highlights);
  }
  
  // Limit to prevent clutter (max 10 arrows, 6 highlights)
  result.arrows = result.arrows.slice(0, 10);
  result.highlights = result.highlights.slice(0, 6);
  
  return result;
}

/**
 * Get annotations for a specific theme
 */
function getThemeAnnotations(
  theme: string,
  analysisData: any,
  chess: Chess,
  side: 'white' | 'black'
): AnnotationSet {
  const result: AnnotationSet = { arrows: [], highlights: [] };
  
  switch (theme) {
    case 'S_CENTER_SPACE':
    case 'S_CENTER':
      return annotateCenterControl(chess, side);
      
    // DISABLED: S_SPACE adds too many highlights (16 squares)
    // case 'S_SPACE':
    //   return annotateSpaceAdvantage(chess, side);
      
    case 'S_KING':
      return annotateKingSafety(chess, side);
      
    case 'S_PAWN':
      return annotatePawnStructure(chess, side, analysisData);
      
    case 'S_ACTIVITY':
      return annotatePieceActivity(chess, side);
      
    case 'S_THREATS':
      return annotateThreats(chess, side, analysisData);
      
    case 'S_DEV':
      return annotateDevelopment(chess, side);
  }
  
  return result;
}

/**
 * Get annotations for a specific tag
 */
function getTagAnnotations(
  tag: any,
  chess: Chess,
  side: 'white' | 'black'
): AnnotationSet {
  const result: AnnotationSet = { arrows: [], highlights: [] };
  
  // Handle both object tags and string tags
  const tagName = typeof tag === 'string' ? tag : (tag.tag_name || tag.name || '');
  
  // Extract squares from tag name (e.g., "tag.diagonal.f8-a3" -> ["f8", "a3"])
  const squarePattern = /([a-h][1-8])/g;
  const extractedSquares = tagName.match(squarePattern) || [];
  
  // Diagonal tags - PRIORITY: draw arrow along diagonal
  if (tagName.includes('diagonal')) {
    // Try to get squares from tag data first, then from tag name
    const pieces = tag.pieces || [];
    const squares = tag.squares || extractedSquares;
    
    if (squares.length >= 2) {
      // Draw arrow from first to last square of diagonal
      result.arrows.push({
        from: squares[0],
        to: squares[squares.length - 1],
        color: COLORS.default
      });
    } else if (pieces.length > 0 && squares.length > 0) {
      const pieceSquare = extractSquareFromPiece(pieces[0]);
      if (pieceSquare) {
        result.arrows.push({
          from: pieceSquare,
          to: squares[squares.length - 1],
          color: COLORS.default
        });
      }
    }
    return result;  // Return early - don't add other highlights
  }
  
  // Key square tags - highlight the key square
  if (tagName.includes('key.')) {
    if (extractedSquares.length > 0) {
      result.highlights.push({
        sq: extractedSquares[0],
        color: COLORS.default
      });
    }
    return result;
  }
  
  // Center control - only highlight if we actually HAVE pieces there
  // Don't highlight empty center squares (that would be misleading when LLM says "fails to control center")
  if (tagName.includes('center.control')) {
    const color = side === 'white' ? 'w' : 'b';
    ['d4', 'd5', 'e4', 'e5'].forEach(sq => {
      const piece = chess.get(sq as any);
      // Only highlight if OUR piece occupies the square
      if (piece && piece.color === color) {
        result.highlights.push({ sq, color: COLORS.default });
      }
    });
    return result;
  }
  
  // Threat tags
  if (tagName.includes('threat.capture') || tagName.includes('threat.hanging')) {
    if (tag.from_square && tag.to_square) {
      result.arrows.push({
        from: tag.from_square,
        to: tag.to_square,
        color: COLORS.red
      });
      result.highlights.push({
        sq: tag.to_square,
        color: COLORS.red
      });
    }
  }
  
  // Outpost tags
  if (tagName.includes('outpost')) {
    const outpostSquares = extractSquaresFromTag(tag);
    outpostSquares.forEach(square => {
      result.highlights.push({ sq: square, color: COLORS.default });
    });
  }
  
  // File tags (open/semi-open)
  if (tagName.includes('file.open') || tagName.includes('file.semi')) {
    const files = tag.files || [];
    files.forEach((file: string) => {
      // Highlight key squares on the file
      const entrySquare = side === 'white' ? `${file}7` : `${file}2`;
      result.highlights.push({ sq: entrySquare, color: COLORS.default });
    });
  }
  
  // Diagonal tags
  if (tagName.includes('diagonal')) {
    const pieces = tag.pieces || [];
    const squares = tag.squares || [];
    
    // Draw ray from piece along diagonal
    if (pieces.length > 0 && squares.length > 0) {
      const pieceSquare = extractSquareFromPiece(pieces[0]);
      if (pieceSquare && squares.length > 0) {
        result.arrows.push({
          from: pieceSquare,
          to: squares[squares.length - 1],
          color: COLORS.default
        });
      }
    }
  }
  
  // Tactical tags
  if (tagName.includes('tactic.fork')) {
    // Ring the forking piece, arrows to targets
    const forkerSq = tag.from_square || tag.square;
    const targets = tag.targets || [];
    
    if (forkerSq) {
      result.highlights.push({ sq: forkerSq, color: COLORS.default });
      targets.forEach((target: string) => {
        result.arrows.push({
          from: forkerSq,
          to: target,
          color: COLORS.default
        });
      });
    }
  }
  
  if (tagName.includes('tactic.pin')) {
    // Ray through pinned piece
    if (tag.from_square && tag.to_square) {
      result.arrows.push({
        from: tag.from_square,
        to: tag.to_square,
        color: COLORS.red
      });
      if (tag.pinned_square) {
        result.highlights.push({ sq: tag.pinned_square, color: COLORS.default });
      }
    }
  }
  
  // Bishop pair
  if (tagName.includes('bishop.pair')) {
    const pieces = tag.pieces || [];
    pieces.forEach((piece: string) => {
      const square = extractSquareFromPiece(piece);
      if (square) {
        result.highlights.push({ sq: square, color: COLORS.default });
      }
    });
  }
  
  // Passed pawns
  if (tagName.includes('pawn.passed')) {
    const squares = extractSquaresFromTag(tag);
    squares.forEach(square => {
      result.highlights.push({ sq: square, color: COLORS.default });
      // Arrow to promotion square
      const file = square[0];
      const promSq = side === 'white' ? `${file}8` : `${file}1`;
      result.arrows.push({
        from: square,
        to: promSq,
        color: COLORS.default
      });
    });
  }
  
  // King safety tags
  if (tagName.includes('king.exposed') || tagName.includes('king.attackers')) {
    const kingSq = tag.squares?.[0];
    if (kingSq) {
      result.highlights.push({ sq: kingSq, color: COLORS.red });
    }
  }
  
  return result;
}

// ============================================================================
// THEME-SPECIFIC ANNOTATION FUNCTIONS
// ============================================================================

function annotateCenterControl(chess: Chess, side: 'white' | 'black'): AnnotationSet {
  const result: AnnotationSet = { arrows: [], highlights: [] };
  const coreSquares = ['d4', 'e4', 'd5', 'e5'];
  const color = side === 'white' ? 'w' : 'b';
  
  // Highlight controlled/occupied central squares
  coreSquares.forEach(square => {
    const piece = chess.get(square as any);
    
    // If occupied by our piece
    if (piece && piece.color === color) {
      result.highlights.push({ sq: square, color: COLORS.default });
    } else {
      // Check if we control this square (any of our pieces attack it)
      const board = chess.board();
      let controlled = false;
      
      for (let rank = 0; rank < 8; rank++) {
        for (let file = 0; file < 8; file++) {
          const p = board[rank][file];
          if (p && p.color === color) {
            const from = String.fromCharCode(97 + file) + (8 - rank);
            const attacks = chess.moves({ square: from as any, verbose: true });
            if (attacks.some((m: any) => m.to === square)) {
              controlled = true;
              break;
            }
          }
        }
        if (controlled) break;
      }
      
      if (controlled) {
        result.highlights.push({ sq: square, color: COLORS.default });
      }
    }
  });
  
  return result;
}

function annotateSpaceAdvantage(chess: Chess, side: 'white' | 'black'): AnnotationSet {
  const result: AnnotationSet = { arrows: [], highlights: [] };
  
  // Highlight squares in your half that you control
  const ranks = side === 'white' ? ['4', '5'] : ['5', '4'];
  const files = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'];
  
  files.forEach(file => {
    ranks.forEach(rank => {
      const square = `${file}${rank}`;
      result.highlights.push({ sq: square, color: COLORS.default });
    });
  });
  
  return result;
}

function annotateKingSafety(chess: Chess, side: 'white' | 'black'): AnnotationSet {
  const result: AnnotationSet = { arrows: [], highlights: [] };
  
  // Find king
  const board = chess.board();
  let kingSq: string | null = null;
  
  for (let rank = 0; rank < 8; rank++) {
    for (let file = 0; file < 8; file++) {
      const piece = board[rank][file];
      if (piece && piece.type === 'k' && 
          ((side === 'white' && piece.color === 'w') || (side === 'black' && piece.color === 'b'))) {
        kingSq = String.fromCharCode(97 + file) + (8 - rank);
        break;
      }
    }
    if (kingSq) break;
  }
  
  if (!kingSq) return result;
  
  // Highlight king
  result.highlights.push({ sq: kingSq, color: COLORS.default });
  
  // Highlight pawn shield (if castled)
  const file = kingSq[0];
  const rank = kingSq[1];
  const shieldRank = side === 'white' ? '2' : '7';
  
  if (file === 'g' || file === 'h') {
    // Kingside castled
    ['f', 'g', 'h'].forEach(f => {
      result.highlights.push({ sq: `${f}${shieldRank}`, color: COLORS.default });
    });
  } else if (file === 'b' || file === 'c') {
    // Queenside castled
    ['a', 'b', 'c'].forEach(f => {
      result.highlights.push({ sq: `${f}${shieldRank}`, color: COLORS.default });
    });
  }
  
  return result;
}

function annotatePawnStructure(chess: Chess, side: 'white' | 'black', analysisData: any): AnnotationSet {
  const result: AnnotationSet = { arrows: [], highlights: [] };
  
  // Highlight weak pawns (isolated, backward, doubled)
  const board = chess.board();
  const color = side === 'white' ? 'w' : 'b';
  
  for (let rank = 0; rank < 8; rank++) {
    for (let file = 0; file < 8; file++) {
      const piece = board[rank][file];
      if (piece && piece.type === 'p' && piece.color === color) {
        const sq = String.fromCharCode(97 + file) + (8 - rank);
        
        // Check if isolated (no friendly pawns on adjacent files)
        const hasNeighbor = hasAdjacentPawn(chess, file, color);
        if (!hasNeighbor) {
          result.highlights.push({ sq: sq, color: COLORS.default });
        }
      }
    }
  }
  
  return result;
}

function annotatePieceActivity(chess: Chess, side: 'white' | 'black'): AnnotationSet {
  const result: AnnotationSet = { arrows: [], highlights: [] };
  
  // Highlight active pieces (knights, bishops on good squares)
  const board = chess.board();
  const color = side === 'white' ? 'w' : 'b';
  
  for (let rank = 0; rank < 8; rank++) {
    for (let file = 0; file < 8; file++) {
      const piece = board[rank][file];
      if (piece && piece.color === color && (piece.type === 'n' || piece.type === 'b')) {
        const square = String.fromCharCode(97 + file) + (8 - rank);
        result.highlights.push({ sq: square, color: COLORS.default });
      }
    }
  }
  
  return result;
}

function annotateThreats(chess: Chess, side: 'white' | 'black', analysisData: any): AnnotationSet {
  const result: AnnotationSet = { arrows: [], highlights: [] };
  
  // Get threat tags from analysis
  const sideAnalysis = side === 'white' ? 
    analysisData?.white_analysis : 
    analysisData?.black_analysis;
  
  const tags = sideAnalysis?.chunk_1_immediate?.tags || [];
  
  tags.forEach((tag: any) => {
    if (tag.tag_name?.includes('threat')) {
      if (tag.from_square && tag.to_square) {
        result.arrows.push({
          from: tag.from_square,
          to: tag.to_square,
          color: COLORS.red
        });
      }
    }
  });
  
  return result;
}

function annotateDevelopment(chess: Chess, side: 'white' | 'black'): AnnotationSet {
  const result: AnnotationSet = { arrows: [], highlights: [] };
  
  // Highlight DEVELOPED pieces (not undeveloped ones!)
  // Show pieces that have moved from starting squares
  const board = chess.board();
  const color = side === 'white' ? 'w' : 'b';
  const startRank = side === 'white' ? '1' : '8';
  
  // Find developed minor pieces (knights and bishops not on back rank)
  for (let rank = 0; rank < 8; rank++) {
    for (let file = 0; file < 8; file++) {
      const piece = board[rank][file];
      if (piece && piece.color === color && (piece.type === 'n' || piece.type === 'b')) {
        const square = String.fromCharCode(97 + file) + (8 - rank);
        const pieceRank = square[1];
        
        // If not on back rank, it's developed
        if (pieceRank !== startRank) {
          result.highlights.push({ sq: square, color: COLORS.default });
          
          // Show control/scope arrows for bishops
          if (piece.type === 'b') {
            const moves = getAttackingSquares(chess, square);
            moves.slice(0, 3).forEach(targetSq => {
              result.arrows.push({
                from: square,
                to: targetSq,
                color: COLORS.default
              });
            });
          }
        }
      }
    }
  }
  
  return result;
}

// Helper: Get squares a piece attacks
function getAttackingSquares(chess: Chess, square: string): string[] {
  const attacks: string[] = [];
  const piece = chess.get(square as any);
  if (!piece) return attacks;
  
  // Get all legal moves from this square
  const moves = chess.moves({ square: square as any, verbose: true });
  
  // Return unique target squares
  return [...new Set(moves.map((m: any) => m.to))].slice(0, 4);
}

// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

function extractSquaresFromTag(tag: any): string[] {
  const squares: string[] = [];
  
  if (tag.squares) {
    squares.push(...tag.squares);
  }
  if (tag.square) {
    squares.push(tag.square);
  }
  if (tag.target_square) {
    squares.push(tag.target_square);
  }
  
  // Extract from tag name (e.g., "tag.square.outpost.knight.d5" → "d5")
  const squareMatch = (tag.tag_name || '').match(/\b([a-h][1-8])\b/);
  if (squareMatch) {
    squares.push(squareMatch[1]);
  }
  
  return [...new Set(squares)];
}

function extractSquareFromPiece(pieceStr: string): string | null {
  // "Nd5" → "d5", "Bc4" → "c4"
  const match = pieceStr.match(/[A-Z]?([a-h][1-8])/);
  return match ? match[1] : null;
}

function hasAdjacentPawn(chess: Chess, file: number, color: string): boolean {
  const board = chess.board();
  
  for (let rank = 0; rank < 8; rank++) {
    // Check left file
    if (file > 0) {
      const piece = board[rank][file - 1];
      if (piece && piece.type === 'p' && piece.color === color) return true;
    }
    // Check right file
    if (file < 7) {
      const piece = board[rank][file + 1];
      if (piece && piece.type === 'p' && piece.color === color) return true;
    }
  }
  
  return false;
}

