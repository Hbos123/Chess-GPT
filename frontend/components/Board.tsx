"use client";

import { useState, useEffect, useMemo, useRef } from "react";
import { Chessboard } from "react-chessboard";
import { Chess } from "chess.js";
import type { Square } from "chess.js";
import type { AnnotationArrow, AnnotationHighlight } from "@/types";

interface BoardProps {
  fen: string;
  onMove: (from: string, to: string, promotion?: string) => void;
  arrows?: AnnotationArrow[];
  highlights?: AnnotationHighlight[];
  orientation?: "white" | "black";
  disabled?: boolean;
}

export default function Board({
  fen,
  onMove,
  arrows = [],
  highlights = [],
  orientation = "white",
  disabled = false,
}: BoardProps) {
  // INFINITE LOOP PREVENTION:
  // - Use refs to track previous values and only update when they actually change
  // - Memoize array/object dependencies to prevent new references on every render
  // - Check for actual value changes before calling setState in useEffect
  
  const [game, setGame] = useState(() => new Chess(fen));
  const [customSquareStyles, setCustomSquareStyles] = useState<{
    [square: string]: React.CSSProperties;
  }>({});
  
  // Use ref to track previous FEN to prevent unnecessary updates
  const prevFenRef = useRef<string>(fen);

  // Update game when FEN changes - only if FEN actually changed
  useEffect(() => {
    if (prevFenRef.current !== fen) {
      prevFenRef.current = fen;
      try {
        const newGame = new Chess(fen);
        setGame(newGame);
      } catch (e) {
        console.error("Invalid FEN:", e);
      }
    }
  }, [fen]);

  // react-chessboard handles its own responsive sizing via ResizeObserver

  // Memoize highlights to prevent infinite loops from new array references
  // Arrays/objects passed as props create new references on every render
  const highlightsKey = useMemo(() => {
    return highlights.map(h => `${h.sq}-${h.color || ''}`).join(',');
  }, [highlights]);

  // Update square styles for highlights - only when highlights actually change
  // Use the memoized key instead of the array itself to prevent infinite loops
  useEffect(() => {
    const styles: { [square: string]: React.CSSProperties } = {};
    highlights.forEach((h) => {
      styles[h.sq] = {
        backgroundColor: h.color || "#ffee99",
        transition: "background-color 0.3s ease",
      };
    });
    setCustomSquareStyles(styles);
  }, [highlightsKey]);

  function onDrop(sourceSquare: string, targetSquare: string, piece: string) {
    if (disabled) return false;

    try {
      // Check if it's a pawn promotion
      const move = game.move({
        from: sourceSquare as Square,
        to: targetSquare as Square,
        promotion: piece[1].toLowerCase() === "p" && (targetSquare[1] === "8" || targetSquare[1] === "1") ? "q" : undefined,
      });

      if (move === null) return false;

      // Undo the move since parent handles state
      game.undo();

      // Notify parent
      onMove(sourceSquare, targetSquare, move.promotion);
      return true;
    } catch (e) {
      return false;
    }
  }

  // Convert arrows to compatible format
  const boardArrows = arrows.map((a) => [a.from, a.to, a.color || "#00aa00"]);

  return (
    <div className="board-container">
      <Chessboard
        position={fen}
        onPieceDrop={onDrop}
        boardOrientation={orientation}
        customSquareStyles={customSquareStyles}
        customArrowColor="rgb(0,170,0)"
        customArrows={boardArrows as any}
        arePiecesDraggable={!disabled}
      />
    </div>
  );
}

