/**
 * Tag-Based Visual Annotations
 * Maps chess theme tags to board visual elements (arrows, highlights, markers)
 */

import { Chess } from 'chess.js';

export interface TagAnnotation {
  arrows?: Array<{from: string, to: string, color: string, style?: 'solid' | 'dashed' | 'double'}>;
  highlights?: Array<{sq: string, color: string, style?: 'fill' | 'ring'}>;
  markers?: Array<{sq: string, icon: string}>;
  labels?: Array<{sq: string, text: string, color?: string}>;
  fileHighlights?: Array<{file: string, color: string, intensity?: number}>;
  rays?: Array<{squares: string[], color: string, style: 'dashed'}>;
}

// Color constants
export const ANNOTATION_COLORS = {
  // Friendly (our side)
  friendly_primary: 'rgba(34, 197, 94, 0.65)',    // Green
  friendly_secondary: 'rgba(34, 197, 94, 0.3)',
  friendly_highlight: 'rgba(0, 255, 0, 0.3)',
  
  // Opponent
  opponent_primary: 'rgba(239, 68, 68, 0.65)',    // Red
  opponent_secondary: 'rgba(239, 68, 68, 0.3)',
  
  // Neutral
  neutral_warning: 'rgba(251, 191, 36, 0.5)',     // Yellow
  neutral_info: 'rgba(59, 130, 246, 0.4)',        // Blue
  
  // Special
  hole: 'rgba(255, 100, 100, 0.3)',
  exposed_king: 'rgba(255, 0, 0, 0.5)',
  shield: 'rgba(100, 200, 100, 0.4)',
  trap: 'rgba(200, 50, 50, 0.5)',
  file_stripe: 'rgba(34, 197, 94, 0.15)',
  diagonal_band: 'rgba(59, 130, 246, 0.2)'
};

// Icon constants
export const ANNOTATION_ICONS = {
  shield: '🛡',
  hole: '⭕',
  weak_pawn: '⚠',
  fork: '🍴',
  pin: '📌',
  skewer: '➖▶',
  lightning: '⚡',
  lock: '🔒',
  battery: '⚡⚡',
  anvil: '⚓',
  crown: '👑',
  target: '🎯',
  infinity: '∞',
  break: '💥',
  link: '🔗',
  exposed: '!',
  check: '✓',
  warning: '⚠'
};

/**
 * Main function: Generate visual annotations for a tag
 */
export function getAnnotationsForTag(
  tag: any,
  board: Chess,
  sideToMove: 'w' | 'b'
): TagAnnotation {
  const tagName = tag.tag_name || '';
  const side = tag.side;
  const isOurSide = (side === 'white' && sideToMove === 'w') || (side === 'black' && sideToMove === 'b');
  const color = isOurSide ? ANNOTATION_COLORS.friendly_primary : ANNOTATION_COLORS.opponent_primary;
  
  // ============ FILE TAGS ============
  
  if (tagName.startsWith('tag.file.open.')) {
    const file = tagName.split('.')[3];  // Extract 'a' from 'tag.file.open.a'
    return {
      fileHighlights: [{file, color: ANNOTATION_COLORS.file_stripe, intensity: 1}]
    };
  }
  
  if (tagName === 'tag.file.semi') {
    const file = tag.files?.[0];
    if (file) {
      return {
        fileHighlights: [{file, color: isOurSide ? ANNOTATION_COLORS.friendly_secondary : ANNOTATION_COLORS.opponent_secondary, intensity: 0.5}]
      };
    }
  }
  
  if (tagName === 'tag.rook.open_file') {
    const rook_sq = tag.pieces?.[0]?.substring(1);  // 'Ra1' -> 'a1'
    const file = tag.files?.[0];
    if (rook_sq && file) {
      const target_rank = sideToMove === 'w' ? '7' : '2';
      return {
        highlights: [{sq: rook_sq, color: ANNOTATION_COLORS.friendly_highlight, style: 'ring'}],
        arrows: [{from: rook_sq, to: `${file}${target_rank}`, color: color, style: 'solid'}]
      };
    }
  }
  
  if (tagName === 'tag.rook.semi_open') {
    const rook_sq = tag.pieces?.[0]?.substring(1);
    if (rook_sq) {
      return {
        highlights: [{sq: rook_sq, color: ANNOTATION_COLORS.friendly_secondary, style: 'ring'}]
      };
    }
  }
  
  if (tagName === 'tag.rook.connected') {
    const pieces = tag.pieces || [];
    if (pieces.length === 2) {
      const r1 = pieces[0].substring(1);
      const r2 = pieces[1].substring(1);
      return {
        highlights: [
          {sq: r1, color: ANNOTATION_COLORS.friendly_highlight, style: 'ring'},
          {sq: r2, color: ANNOTATION_COLORS.friendly_highlight, style: 'ring'}
        ],
        arrows: [{from: r1, to: r2, color: ANNOTATION_COLORS.friendly_secondary, style: 'solid'}]
      };
    }
  }
  
  if (tagName === 'tag.rook.rank7') {
    const rook_sq = tag.pieces?.[0]?.substring(1);
    if (rook_sq) {
      return {
        highlights: [{sq: rook_sq, color: ANNOTATION_COLORS.friendly_primary, style: 'ring'}]
      };
    }
  }
  
  // ============ PAWN TAGS ============
  
  if (tagName.startsWith('tag.pawn.passed.')) {
    const pawn_sq = tag.squares?.[0];
    if (pawn_sq) {
      const file = pawn_sq[0];
      const target_rank = sideToMove === 'w' ? '8' : '1';
      return {
        highlights: [{sq: pawn_sq, color: ANNOTATION_COLORS.friendly_highlight, style: 'ring'}],
        arrows: [{from: pawn_sq, to: `${file}${target_rank}`, color: ANNOTATION_COLORS.friendly_secondary, style: 'dashed'}]
      };
    }
  }
  
  if (tagName === 'tag.pawn.passed.protected') {
    const pawn_sq = tag.squares?.[0];
    if (pawn_sq) {
      return {
        markers: [{sq: pawn_sq, icon: ANNOTATION_ICONS.shield}]
      };
    }
  }
  
  if (tagName === 'tag.pawn.passed.connected') {
    const pieces = tag.pieces || [];
    if (pieces.length >= 2) {
      const p1 = pieces[0].substring(1);
      const p2 = pieces[1].substring(1);
      return {
        highlights: [
          {sq: p1, color: ANNOTATION_COLORS.friendly_highlight, style: 'ring'},
          {sq: p2, color: ANNOTATION_COLORS.friendly_highlight, style: 'ring'}
        ]
      };
    }
  }
  
  if (tagName.startsWith('tag.lever.')) {
    const push_sq = tag.squares?.[0];
    const pawn = tag.pieces?.[0]?.substring(1);
    if (pawn && push_sq) {
      return {
        arrows: [{from: pawn, to: push_sq, color: ANNOTATION_COLORS.friendly_primary, style: 'solid'}],
        markers: [{sq: push_sq, icon: ANNOTATION_ICONS.break}]
      };
    }
  }
  
  // ============ DIAGONAL TAGS ============
  
  if (tagName.startsWith('tag.diagonal.long.')) {
    const piece_sq = tag.pieces?.[0]?.substring(1);
    if (piece_sq) {
      return {
        highlights: [{sq: piece_sq, color: ANNOTATION_COLORS.diagonal_band, style: 'ring'}]
      };
    }
  }
  
  if (tagName === 'tag.battery.qb.diagonal') {
    const pieces = tag.pieces || [];
    if (pieces.length === 2) {
      const q_sq = pieces[0].substring(1);
      const b_sq = pieces[1].substring(1);
      return {
        highlights: [
          {sq: q_sq, color: ANNOTATION_COLORS.friendly_highlight, style: 'ring'},
          {sq: b_sq, color: ANNOTATION_COLORS.friendly_highlight, style: 'ring'}
        ],
        markers: [{sq: q_sq, icon: ANNOTATION_ICONS.battery}]
      };
    }
  }
  
  // ============ OUTPOST & HOLE TAGS ============
  
  if (tagName.startsWith('tag.square.outpost.knight.')) {
    const outpost_sq = tag.squares?.[0];
    const knight_sq = tag.pieces?.[0]?.substring(1);
    if (outpost_sq) {
      return {
        highlights: [{sq: outpost_sq, color: ANNOTATION_COLORS.friendly_highlight, style: 'fill'}],
        markers: [{sq: outpost_sq, icon: ANNOTATION_ICONS.anvil}]
      };
    }
  }
  
  if (tagName.startsWith('tag.color.hole.')) {
    const hole_sq = tag.squares?.[0];
    if (hole_sq) {
      return {
        highlights: [{sq: hole_sq, color: ANNOTATION_COLORS.hole, style: 'ring'}],
        markers: [{sq: hole_sq, icon: ANNOTATION_ICONS.hole}]
      };
    }
  }
  
  // ============ CENTER & KEY SQUARE TAGS ============
  
  if (tagName === 'tag.center.control.core') {
    const squares = tag.squares || [];
    return {
      highlights: squares.map((sq: string) => ({
        sq,
        color: isOurSide ? ANNOTATION_COLORS.friendly_highlight : ANNOTATION_COLORS.opponent_secondary,
        style: 'ring' as const
      }))
    };
  }
  
  if (tagName === 'tag.center.control.near') {
    const squares = tag.squares || [];
    return {
      highlights: squares.map((sq: string) => ({
        sq,
        color: ANNOTATION_COLORS.friendly_secondary,
        style: 'ring' as const
      }))
    };
  }
  
  if (tagName.startsWith('tag.key.')) {
    const key_sq = tagName.split('.')[2];  // 'e4' from 'tag.key.e4'
    return {
      highlights: [{sq: key_sq, color: ANNOTATION_COLORS.friendly_highlight, style: 'ring'}],
      markers: [{sq: key_sq, icon: ANNOTATION_ICONS.crown}]
    };
  }
  
  if (tagName === 'tag.space.advantage') {
    // Show space advantage as subtle highlights in opponent half
    // (implementation simplified - could highlight controlled squares)
    return {};
  }
  
  // ============ KING SAFETY TAGS ============
  
  if (tagName === 'tag.king.shield.intact') {
    const king_sq = tag.squares?.[0];
    if (king_sq) {
      return {
        highlights: [{sq: king_sq, color: ANNOTATION_COLORS.shield, style: 'ring'}],
        markers: [{sq: king_sq, icon: ANNOTATION_ICONS.shield}]
      };
    }
  }
  
  if (tagName.startsWith('tag.king.shield.missing.')) {
    const king_sq = tag.squares?.[0];
    if (king_sq) {
      return {
        highlights: [{sq: king_sq, color: ANNOTATION_COLORS.neutral_warning, style: 'ring'}],
        markers: [{sq: king_sq, icon: ANNOTATION_ICONS.warning}]
      };
    }
  }
  
  if (tagName === 'tag.king.file.open') {
    const file = tag.files?.[0];
    const king_sq = tag.squares?.[0];
    if (file && king_sq) {
      return {
        fileHighlights: [{file, color: ANNOTATION_COLORS.opponent_secondary, intensity: 0.6}],
        highlights: [{sq: king_sq, color: ANNOTATION_COLORS.neutral_warning, style: 'ring'}]
      };
    }
  }
  
  if (tagName === 'tag.king.file.semi') {
    const file = tag.files?.[0];
    if (file) {
      return {
        fileHighlights: [{file, color: ANNOTATION_COLORS.opponent_secondary, intensity: 0.3}]
      };
    }
  }
  
  if (tagName === 'tag.king.center.exposed') {
    const king_sq = tag.squares?.[0];
    if (king_sq) {
      return {
        highlights: [{sq: king_sq, color: ANNOTATION_COLORS.exposed_king, style: 'ring'}],
        markers: [{sq: king_sq, icon: ANNOTATION_ICONS.exposed}],
        labels: [{sq: king_sq, text: 'EXPOSED', color: 'red'}]
      };
    }
  }
  
  if (tagName === 'tag.king.castled.safe') {
    const king_sq = tag.squares?.[0];
    if (king_sq) {
      return {
        highlights: [{sq: king_sq, color: ANNOTATION_COLORS.shield, style: 'fill'}]
      };
    }
  }
  
  if (tagName === 'tag.king.attackers.count') {
    const king_sq = tag.squares?.[0];
    const count = tag.details?.count || 0;
    if (king_sq && count > 0) {
      return {
        highlights: [{sq: king_sq, color: ANNOTATION_COLORS.opponent_secondary, style: 'ring'}],
        labels: [{sq: king_sq, text: `${count} ATK`, color: 'red'}]
      };
    }
  }
  
  // ============ ACTIVITY TAGS ============
  
  if (tagName.startsWith('tag.activity.mobility.')) {
    // Simplified: just highlight active pieces
    return {};
  }
  
  if (tagName === 'tag.piece.trapped') {
    const piece_sq = tag.squares?.[0];
    if (piece_sq) {
      return {
        highlights: [{sq: piece_sq, color: ANNOTATION_COLORS.trap, style: 'ring'}],
        markers: [{sq: piece_sq, icon: ANNOTATION_ICONS.lock}]
      };
    }
  }
  
  if (tagName === 'tag.bishop.bad') {
    const bishop_sq = tag.squares?.[0];
    if (bishop_sq) {
      return {
        highlights: [{sq: bishop_sq, color: ANNOTATION_COLORS.neutral_warning, style: 'ring'}]
      };
    }
  }
  
  if (tagName === 'tag.bishop.pair') {
    const pieces = tag.pieces || [];
    if (pieces.length === 2) {
      const b1 = pieces[0].substring(1);
      const b2 = pieces[1].substring(1);
      return {
        highlights: [
          {sq: b1, color: ANNOTATION_COLORS.friendly_highlight, style: 'ring'},
          {sq: b2, color: ANNOTATION_COLORS.friendly_highlight, style: 'ring'}
        ],
        markers: [{sq: b1, icon: ANNOTATION_ICONS.infinity}]
      };
    }
  }
  
  // ============ TACTICAL TAGS ============
  
  if (tagName === 'tag.tactic.fork') {
    // Would need PV or move data from tag details
    return {
      markers: [{sq: tag.squares?.[0] || 'e4', icon: ANNOTATION_ICONS.fork}]
    };
  }
  
  if (tagName === 'tag.tactic.pin') {
    const pinned_sq = tag.squares?.[0];
    if (pinned_sq) {
      return {
        highlights: [{sq: pinned_sq, color: ANNOTATION_COLORS.opponent_secondary, style: 'ring'}],
        markers: [{sq: pinned_sq, icon: ANNOTATION_ICONS.pin}]
      };
    }
  }
  
  if (tagName === 'tag.tactic.discovered' || tagName === 'tag.tactic.discovered_check') {
    return {
      markers: [{sq: tag.squares?.[0] || 'e4', icon: ANNOTATION_ICONS.lightning}]
    };
  }
  
  if (tagName === 'tag.tactic.backrank') {
    const back_rank = sideToMove === 'w' ? '8' : '1';
    return {
      highlights: [
        {sq: `a${back_rank}`, color: ANNOTATION_COLORS.opponent_secondary, style: 'fill'},
        {sq: `b${back_rank}`, color: ANNOTATION_COLORS.opponent_secondary, style: 'fill'},
        {sq: `c${back_rank}`, color: ANNOTATION_COLORS.opponent_secondary, style: 'fill'},
        {sq: `d${back_rank}`, color: ANNOTATION_COLORS.opponent_secondary, style: 'fill'},
        {sq: `e${back_rank}`, color: ANNOTATION_COLORS.opponent_secondary, style: 'fill'},
        {sq: `f${back_rank}`, color: ANNOTATION_COLORS.opponent_secondary, style: 'fill'},
        {sq: `g${back_rank}`, color: ANNOTATION_COLORS.opponent_secondary, style: 'fill'},
        {sq: `h${back_rank}`, color: ANNOTATION_COLORS.opponent_secondary, style: 'fill'}
      ]
    };
  }
  
  // ============ ENDGAME TAGS ============
  
  if (tagName === 'tag.rook.behind.passed') {
    const rook_sq = tag.pieces?.[0]?.substring(1);
    const passer_sq = tag.squares?.[0];
    if (rook_sq && passer_sq) {
      return {
        highlights: [
          {sq: rook_sq, color: ANNOTATION_COLORS.friendly_highlight, style: 'ring'},
          {sq: passer_sq, color: ANNOTATION_COLORS.friendly_highlight, style: 'ring'}
        ]
      };
    }
  }
  
  if (tagName === 'tag.king.proximity.passed') {
    const king_sq = tag.squares?.[0];
    if (king_sq) {
      return {
        highlights: [{sq: king_sq, color: ANNOTATION_COLORS.friendly_secondary, style: 'ring'}]
      };
    }
  }
  
  // Default: no annotation for unknown/unimplemented tags
  return {};
}

/**
 * Generate all annotations from a list of tags
 */
export function generateAnnotationsFromTags(
  tags: any[],
  fen: string,
  sideToMove: 'w' | 'b'
): { arrows: any[], highlights: any[] } {
  const board = new Chess(fen);
  const allArrows: any[] = [];
  const allHighlights: any[] = [];
  const allMarkers: any[] = [];
  const allLabels: any[] = [];
  const fileHighlightMap: Map<string, {color: string, intensity: number}> = new Map();
  
  // Process each tag
  tags.forEach(tag => {
    const annotation = getAnnotationsForTag(tag, board, sideToMove);
    
    if (annotation.arrows) {
      allArrows.push(...annotation.arrows);
    }
    
    if (annotation.highlights) {
      allHighlights.push(...annotation.highlights);
    }
    
    if (annotation.markers) {
      allMarkers.push(...annotation.markers);
    }
    
    if (annotation.labels) {
      allLabels.push(...annotation.labels);
    }
    
    if (annotation.fileHighlights) {
      annotation.fileHighlights.forEach(fh => {
        // Merge file highlights by taking max intensity
        const existing = fileHighlightMap.get(fh.file);
        if (!existing || (fh.intensity || 1) > existing.intensity) {
          fileHighlightMap.set(fh.file, {color: fh.color, intensity: fh.intensity || 1});
        }
      });
    }
  });
  
  // Convert file highlights to square highlights
  fileHighlightMap.forEach((fh, file) => {
    for (let rank = 1; rank <= 8; rank++) {
      allHighlights.push({
        sq: `${file}${rank}`,
        color: fh.color,
        style: 'fill'
      });
    }
  });
  
  // Apply priority and merge overlapping annotations
  const {arrows, highlights} = mergeAnnotations(allArrows, allHighlights);
  
  // Note: markers and labels not yet supported by react-chessboard
  // They would be rendered as overlays in a future enhancement
  
  return {arrows, highlights};
}

/**
 * Merge and prioritize annotations to prevent clutter
 */
function mergeAnnotations(
  arrows: any[],
  highlights: any[]
): { arrows: any[], highlights: any[] } {
  // Deduplicate arrows by from-to pair
  const arrowMap = new Map<string, any>();
  arrows.forEach(arrow => {
    const key = `${arrow.from}-${arrow.to}`;
    if (!arrowMap.has(key)) {
      arrowMap.set(key, arrow);
    }
  });
  
  // Deduplicate highlights by square (keep strongest color)
  const highlightMap = new Map<string, any>();
  highlights.forEach(hl => {
    const existing = highlightMap.get(hl.sq);
    if (!existing) {
      highlightMap.set(hl.sq, hl);
    } else {
      // Keep ring style over fill if both present
      if (hl.style === 'ring' && existing.style === 'fill') {
        highlightMap.set(hl.sq, hl);
      }
    }
  });
  
  // Limit to prevent clutter
  const finalArrows = Array.from(arrowMap.values()).slice(0, 15);
  const finalHighlights = Array.from(highlightMap.values()).slice(0, 25);
  
  return {
    arrows: finalArrows,
    highlights: finalHighlights
  };
}

/**
 * Tag priority for sorting (higher = more important)
 */
export function getTagPriority(tagName: string): number {
  // Tactical tags - highest priority
  if (tagName.startsWith('tag.tactic.')) return 100;
  
  // King safety - high priority
  if (tagName.startsWith('tag.king.')) return 90;
  
  // Passed pawns - high priority
  if (tagName.startsWith('tag.pawn.passed')) return 80;
  
  // Outposts - medium-high
  if (tagName.includes('outpost')) return 70;
  
  // Holes - medium
  if (tagName.includes('hole')) return 60;
  
  // Activity (trapped, bishop pair) - medium
  if (tagName.startsWith('tag.piece.trapped') || tagName === 'tag.bishop.pair') return 50;
  
  // Files, diagonals - medium-low
  if (tagName.startsWith('tag.file.') || tagName.startsWith('tag.diagonal.')) return 40;
  
  // Center control - low
  if (tagName.startsWith('tag.center.') || tagName.startsWith('tag.key.')) return 30;
  
  // Default
  return 10;
}

/**
 * Generate plan-based arrows showing example moves for the actions in the plan
 */
export function generatePlanArrows(
  planExplanation: string,
  board: Chess,
  sideToMove: 'w' | 'b'
): any[] {
  const arrows: any[] = [];
  
  if (!planExplanation) return arrows;
  
  const lowerPlan = planExplanation.toLowerCase();
  
  // Parse out actions from plan explanation
  // Format: "Build advantage by: action1, then action2, then action3"
  
  // DEVELOPMENT - show knight/bishop development moves
  if (lowerPlan.includes('develop your knight') || lowerPlan.includes('develop knight')) {
    const knights = findPieces(board, 'n', sideToMove);
    knights.forEach(sq => {
      const moves = board.moves({square: sq as any, verbose: true});
      // Find development moves (off back rank)
      const backRank = sideToMove === 'w' ? 1 : 8;
      const devMoves = moves.filter((m: any) => {
        const toRank = parseInt(m.to[1]);
        return toRank !== backRank;
      });
      if (devMoves.length > 0) {
        const move = devMoves[0];
        arrows.push({from: move.from, to: move.to, color: ANNOTATION_COLORS.friendly_primary, style: 'solid'});
      }
    });
  }
  
  if (lowerPlan.includes('develop your bishop') || lowerPlan.includes('develop bishop')) {
    const bishops = findPieces(board, 'b', sideToMove);
    bishops.forEach(sq => {
      const moves = board.moves({square: sq as any, verbose: true});
      const backRank = sideToMove === 'w' ? 1 : 8;
      const devMoves = moves.filter((m: any) => {
        const toRank = parseInt(m.to[1]);
        return toRank !== backRank;
      });
      if (devMoves.length > 0) {
        const move = devMoves[0];
        arrows.push({from: move.from, to: move.to, color: ANNOTATION_COLORS.friendly_primary, style: 'solid'});
      }
    });
  }
  
  // CENTER CONTROL - show pawn pushes to center
  if (lowerPlan.includes('control the center') || lowerPlan.includes('expand in the center') || lowerPlan.includes('push pawns for space')) {
    const pawns = findPieces(board, 'p', sideToMove);
    const centralFiles = ['d', 'e'];
    pawns.forEach(sq => {
      const file = sq[0];
      if (centralFiles.includes(file)) {
        const moves = board.moves({square: sq as any, verbose: true});
        if (moves.length > 0) {
          const move = moves[0];
          arrows.push({from: move.from, to: move.to, color: ANNOTATION_COLORS.friendly_primary, style: 'solid'});
        }
      }
    });
  }
  
  // CONTROL KEY SQUARES - show moves to d4, e4, d5, e5
  const keySquareMatch = lowerPlan.match(/control ([a-h][1-8])/);
  if (keySquareMatch) {
    const targetSq = keySquareMatch[1];
    // Find pieces that can move to this square
    const allMoves = board.moves({verbose: true});
    const movesToTarget = allMoves.filter((m: any) => m.to === targetSq);
    if (movesToTarget.length > 0) {
      const move = movesToTarget[0];
      arrows.push({from: move.from, to: move.to, color: ANNOTATION_COLORS.friendly_primary, style: 'solid'});
    }
  }
  
  // CASTLE - show castling move
  if (lowerPlan.includes('castle') && !lowerPlan.includes('castled')) {
    const king_sq = board.turn() === sideToMove ? 'e1' : (sideToMove === 'w' ? 'e1' : 'e8');
    const moves = board.moves({square: king_sq as any, verbose: true});
    const castleMoves = moves.filter((m: any) => m.flags.includes('k') || m.flags.includes('q'));
    if (castleMoves.length > 0) {
      const move = castleMoves[0];
      arrows.push({from: move.from, to: move.to, color: ANNOTATION_COLORS.shield, style: 'solid'});
    }
  }
  
  // ROOK TO OPEN FILE
  if (lowerPlan.includes('place rook on open file') || lowerPlan.includes('control the') && lowerPlan.includes('-file')) {
    const rooks = findPieces(board, 'r', sideToMove);
    if (rooks.length > 0) {
      const rook_sq = rooks[0];
      const moves = board.moves({square: rook_sq as any, verbose: true});
      if (moves.length > 0) {
        const move = moves[0];
        arrows.push({from: move.from, to: move.to, color: ANNOTATION_COLORS.friendly_primary, style: 'dashed'});
      }
    }
  }
  
  return arrows.slice(0, 5);  // Limit to top 5 plan arrows
}

/**
 * Helper: Find all pieces of a type for a side
 */
function findPieces(board: Chess, pieceType: string, sideToMove: 'w' | 'b'): string[] {
  const pieces: string[] = [];
  const boardArray = board.board();
  
  boardArray.forEach((row, rankIdx) => {
    row.forEach((square, fileIdx) => {
      if (square && square.type === pieceType && square.color === sideToMove) {
        const sq = String.fromCharCode(97 + fileIdx) + (8 - rankIdx);
        pieces.push(sq);
      }
    });
  });
  
  return pieces;
}

