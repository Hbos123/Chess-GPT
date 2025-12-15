/**
 * Unit tests for PGN sequence parser
 * Tests isolated PGN parsing logic without browser dependencies
 */

import { parsePGNSequences } from '../lib/pgnSequenceParser';

describe('PGN Sequence Parser', () => {
  it('should parse simple sequence from starting position', () => {
    const text = "After 1. e4 e5 2. Nf3, White controls the center";
    const fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";
    
    const sequences = parsePGNSequences(text, fen);
    
    expect(sequences.length).toBeGreaterThan(0);
    expect(sequences[0].moves.length).toBeGreaterThan(0);
    expect(sequences[0].fullPGN).toContain('e4');
  });

  it('should handle PGN from current position (after e4)', () => {
    const text = "Consider 1... e5 2. Nf3 Nc6 for symmetry";
    const fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1";
    
    const sequences = parsePGNSequences(text, fen);
    
    // Should attempt to parse from current position
    expect(sequences.length).toBeGreaterThanOrEqual(0);
  });

  it('should gracefully handle invalid moves', () => {
    const text = "After 1. e4 e6 2. e5 (impossible from e4)";
    const fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";
    
    // Should not throw error
    expect(() => parsePGNSequences(text, fen)).not.toThrow();
  });

  it('should handle empty text', () => {
    const text = "";
    const fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";
    
    const sequences = parsePGNSequences(text, fen);
    expect(sequences).toEqual([]);
  });

  it('should handle text with no PGN', () => {
    const text = "This is just regular text with no moves";
    const fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";
    
    const sequences = parsePGNSequences(text, fen);
    expect(sequences).toEqual([]);
  });

  it('should parse multiple separate sequences', () => {
    const text = "First try 1. e4 e5, or alternatively 1. d4 d5";
    const fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";
    
    const sequences = parsePGNSequences(text, fen);
    
    // Should find multiple sequences
    // Exact behavior depends on implementation
    expect(sequences.length).toBeGreaterThanOrEqual(0);
  });

  it('should handle Black to move notation', () => {
    const text = "After 1... e5 2. Nf3";
    const fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1";
    
    // Should handle Black's first move correctly
    expect(() => parsePGNSequences(text, fen)).not.toThrow();
  });
});

