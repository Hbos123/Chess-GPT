"use client";

import { useSearchParams } from 'next/navigation';
import { Suspense, useState, useEffect } from 'react';
import { Chess } from 'chess.js';
import Board from '@/components/Board';

function ChessBoardInner() {
  const searchParams = useSearchParams();
  const pgnParam = searchParams.get('pgn') || '';
  const fenParam = searchParams.get('fen') || '';
  
  const [game, setGame] = useState<Chess | null>(null);
  const [currentFen, setCurrentFen] = useState(fenParam || 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1');
  const [pgn, setPgn] = useState(pgnParam);
  const [error, setError] = useState<string | null>(null);
  
  useEffect(() => {
    if (pgnParam) {
      try {
        const newGame = new Chess();
        newGame.loadPgn(pgnParam);
        setGame(newGame);
        setCurrentFen(newGame.fen());
        setPgn(pgnParam);
      } catch (err: any) {
        console.error('Error loading PGN:', err);
        setError(`Failed to load PGN: ${err.message}`);
        // Fallback to FEN if available
        if (fenParam) {
          try {
            const newGame = new Chess(fenParam);
            setGame(newGame);
            setCurrentFen(fenParam);
          } catch (fenErr) {
            setError('Failed to load both PGN and FEN');
          }
        }
      }
    } else if (fenParam) {
      try {
        const newGame = new Chess(fenParam);
        setGame(newGame);
        setCurrentFen(fenParam);
      } catch (err: any) {
        setError(`Failed to load FEN: ${err.message}`);
      }
    }
  }, [pgnParam, fenParam]);
  
  const handleMove = (from: string, to: string, promotion?: string) => {
    if (!game) return;
    try {
      const move = game.move({ from, to, promotion });
      if (move) {
        setCurrentFen(game.fen());
        setPgn(game.pgn());
      }
    } catch (err) {
      console.error('Invalid move:', err);
    }
  };
  
  return (
    <div className="container mx-auto p-4 max-w-6xl">
      <div className="mb-4">
        <h1 className="text-2xl font-bold mb-2">Investigation Lines</h1>
        {error && (
          <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
            {error}
          </div>
        )}
        {!error && pgn && (
          <p className="text-sm text-gray-600 mb-2">
            This board shows all moves that were investigated during analysis. 
            Use the board to navigate through variations.
          </p>
        )}
      </div>
      
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div>
          {game && (
            <Board
              fen={currentFen}
              onMove={handleMove}
              arrows={[]}
              highlights={[]}
              orientation="white"
              disabled={false}
            />
          )}
        </div>
        
        <div>
          <div className="bg-gray-50 p-4 rounded-lg">
            <h2 className="text-lg font-semibold mb-2">PGN</h2>
            {pgn ? (
              <pre className="bg-white p-3 rounded border text-xs overflow-auto max-h-96 font-mono whitespace-pre-wrap">
                {pgn}
              </pre>
            ) : (
              <p className="text-gray-500 text-sm">No PGN available</p>
            )}
          </div>
          
          {game && (
            <div className="mt-4 bg-gray-50 p-4 rounded-lg">
              <h2 className="text-lg font-semibold mb-2">Current Position</h2>
              <p className="text-sm font-mono bg-white p-2 rounded border">
                {currentFen}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function ChessBoardPage() {
  // Next.js requires a Suspense boundary when using useSearchParams() in app router pages.
  return (
    <Suspense fallback={<div className="container mx-auto p-4 max-w-6xl">Loading…</div>}>
      <ChessBoardInner />
    </Suspense>
  );
}


