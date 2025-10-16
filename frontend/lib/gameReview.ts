// Comprehensive Game Review Engine
// Analyzes every move in a game and provides detailed insights

import { Chess } from "chess.js";

export interface MoveAnalysis {
  moveNumber: number;
  move: string;
  fen: string;
  fenBefore: string;
  color: 'w' | 'b';
  evalBefore: number;
  evalAfter: number;
  evalChange: number;
  cpLoss: number;
  quality: 'best' | 'excellent' | 'good' | 'inaccuracy' | 'mistake' | 'blunder';
  isCritical: boolean; // Gap to 2nd best > 50cp
  isMissedWin: boolean; // Non-best move where best was winning (>50cp gap, eval>50cp)
  isTheoryMove: boolean;
  bestMove: string;
  secondBestMove?: string;
  gapToSecondBest?: number;
  openingName?: string;
  phase: 'opening' | 'middlegame' | 'endgame';
  advantageLevel: 'equal' | 'slight' | 'clear' | 'strong';
  advantageFor: 'white' | 'black' | 'equal';
}

export interface GamePhaseTransition {
  moveNumber: number;
  fromPhase: string;
  toPhase: string;
  reason: string;
}

export interface AdvantageShift {
  moveNumber: number;
  move: string;
  fromLevel: string;
  toLevel: string;
  reason: string;
}

export interface GameReviewReport {
  moves: MoveAnalysis[];
  openingName: string;
  gameType: 'consistent' | 'reversal' | 'volatile';
  phaseTransitions: GamePhaseTransition[];
  advantageShifts: AdvantageShift[];
  whiteAccuracy: number;
  blackAccuracy: number;
  criticalMoves: MoveAnalysis[];
  missedWins: MoveAnalysis[];
  brilliantMoves: MoveAnalysis[]; // Extra: Moves better than engine's top choice
  dubious: MoveAnalysis[]; // Extra: Questionable but playable
  blunders: number;
  mistakes: number;
  inaccuracies: number;
}

// Helper: Calculate move quality from CP loss
export function getMoveQuality(cpLoss: number): MoveAnalysis['quality'] {
  if (cpLoss === 0) return 'best';
  if (cpLoss < 30) return 'excellent';
  if (cpLoss < 50) return 'good';
  if (cpLoss < 80) return 'inaccuracy';
  if (cpLoss < 200) return 'mistake';
  return 'blunder';
}

// Helper: Get advantage level from eval
export function getAdvantageLevel(cp: number): { level: string; for: string } {
  const absCp = Math.abs(cp);
  let level = 'equal';
  
  if (absCp < 50) level = 'equal';
  else if (absCp < 100) level = 'slight';
  else if (absCp < 200) level = 'clear';
  else level = 'strong';
  
  const advantageFor = cp > 50 ? 'white' : cp < -50 ? 'black' : 'equal';
  
  return { level, for: advantageFor };
}

// Helper: Determine game phase
export function getGamePhase(pieceCount: number, queens: number): string {
  if (pieceCount >= 28) return 'opening';
  if (queens === 0 || pieceCount <= 12) return 'endgame';
  return 'middlegame';
}

// Helper: Classify game type
export function classifyGameType(advantageShifts: AdvantageShift[]): 'consistent' | 'reversal' | 'volatile' {
  if (advantageShifts.length === 0) return 'consistent';
  
  // Count how many times advantage switched sides
  let sideChanges = 0;
  for (let i = 1; i < advantageShifts.length; i++) {
    const prev = advantageShifts[i - 1].toLevel;
    const curr = advantageShifts[i].toLevel;
    
    if ((prev.includes('white') && curr.includes('black')) ||
        (prev.includes('black') && curr.includes('white'))) {
      sideChanges++;
    }
  }
  
  if (sideChanges === 0) return 'consistent';
  if (sideChanges === 1) return 'reversal';
  return 'volatile';
}

// Calculate accuracy percentage
export function calculateAccuracy(moves: MoveAnalysis[], color: 'w' | 'b'): number {
  const playerMoves = moves.filter(m => m.color === color);
  if (playerMoves.length === 0) return 100;
  
  // Accuracy formula: 100 - (average CP loss)
  const totalCpLoss = playerMoves.reduce((sum, m) => sum + m.cpLoss, 0);
  const avgCpLoss = totalCpLoss / playerMoves.length;
  
  // Cap at 100% and floor at 0%
  return Math.max(0, Math.min(100, 100 - avgCpLoss));
}

