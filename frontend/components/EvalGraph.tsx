"use client";

import { useEffect, useRef } from 'react';

interface EvalGraphProps {
  moves: Array<{
    moveNumber: number;
    move: string;
    evalAfter: number;
    color: string;
  }>;
}

export default function EvalGraph({ moves }: EvalGraphProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    if (!canvasRef.current || moves.length === 0) return;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Set canvas size
    const width = canvas.width;
    const height = canvas.height;

    // Clear canvas
    ctx.fillStyle = '#1a1a1a';
    ctx.fillRect(0, 0, width, height);

    // Calculate bounds
    const maxEval = 500; // Cap at +/- 500cp for better visualization
    const padding = 40;
    const graphWidth = width - 2 * padding;
    const graphHeight = height - 2 * padding;

    // Draw grid lines
    ctx.strokeStyle = '#333';
    ctx.lineWidth = 1;
    
    // Horizontal lines (eval thresholds)
    const evalLines = [-300, -200, -100, 0, 100, 200, 300];
    evalLines.forEach(evalCp => {
      const y = padding + graphHeight / 2 - (evalCp / maxEval) * (graphHeight / 2);
      ctx.beginPath();
      ctx.moveTo(padding, y);
      ctx.lineTo(width - padding, y);
      ctx.stroke();
      
      // Draw eval labels
      ctx.fillStyle = evalCp === 0 ? '#888' : '#555';
      ctx.font = '11px monospace';
      ctx.textAlign = 'right';
      ctx.fillText(evalCp > 0 ? `+${evalCp}` : `${evalCp}`, padding - 5, y + 4);
    });

    // Draw center line (0.00)
    ctx.strokeStyle = '#666';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(padding, padding + graphHeight / 2);
    ctx.lineTo(width - padding, padding + graphHeight / 2);
    ctx.stroke();

    // Prepare data points
    const dataPoints = moves.map((move, index) => {
      const x = padding + (index / (moves.length - 1 || 1)) * graphWidth;
      const clampedEval = Math.max(-maxEval, Math.min(maxEval, move.evalAfter));
      const y = padding + graphHeight / 2 - (clampedEval / maxEval) * (graphHeight / 2);
      return { x, y, move, index };
    });

    // Draw eval line
    ctx.strokeStyle = '#4a9eff';
    ctx.lineWidth = 2;
    ctx.beginPath();
    dataPoints.forEach((point, i) => {
      if (i === 0) {
        ctx.moveTo(point.x, point.y);
      } else {
        ctx.lineTo(point.x, point.y);
      }
    });
    ctx.stroke();

    // Draw points
    dataPoints.forEach(point => {
      ctx.fillStyle = point.move.evalAfter > 0 ? '#22c55e' : point.move.evalAfter < 0 ? '#ef4444' : '#888';
      ctx.beginPath();
      ctx.arc(point.x, point.y, 3, 0, 2 * Math.PI);
      ctx.fill();
    });

    // Draw move numbers on x-axis
    ctx.fillStyle = '#666';
    ctx.font = '10px monospace';
    ctx.textAlign = 'center';
    const step = Math.max(1, Math.floor(moves.length / 10));
    moves.forEach((move, index) => {
      if (index % step === 0 || index === moves.length - 1) {
        const x = padding + (index / (moves.length - 1 || 1)) * graphWidth;
        ctx.fillText(`${move.moveNumber}`, x, height - padding + 15);
      }
    });

    // Draw labels
    ctx.fillStyle = '#aaa';
    ctx.font = 'bold 12px sans-serif';
    ctx.textAlign = 'left';
    ctx.fillText('Evaluation Over Time', padding, 20);
    
    ctx.font = '11px sans-serif';
    ctx.fillText(`${moves.length} moves analyzed`, padding, 35);

  }, [moves]);

  return (
    <div className="eval-graph-container">
      <canvas 
        ref={canvasRef} 
        width={700} 
        height={250}
        className="eval-graph-canvas"
      />
    </div>
  );
}

