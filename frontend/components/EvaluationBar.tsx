"use client";

import { useMemo, useEffect, useRef, useState } from "react";

interface EvaluationBarProps {
  evalCp: number; // Centipawns evaluation (positive = white advantage, negative = black advantage)
  orientation: "white" | "black";
  mate?: number; // Mate in N moves (positive = white mates, negative = black mates)
}

export default function EvaluationBar({ evalCp, orientation, mate }: EvaluationBarProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [height, setHeight] = useState<number>(600);
  const [computedStyles, setComputedStyles] = useState<{
    bgPrimary: string;
    bgSecondary: string;
  } | null>(null);

  // Get computed CSS variable values
  useEffect(() => {
    const updateStyles = () => {
      const root = document.documentElement;
      const bgPrimary = getComputedStyle(root).getPropertyValue('--bg-primary').trim() || '#0c111a';
      const bgSecondary = getComputedStyle(root).getPropertyValue('--bg-secondary').trim() || '#111827';
      setComputedStyles({ bgPrimary, bgSecondary });
    };

    updateStyles();
    // Watch for theme changes
    const observer = new MutationObserver(updateStyles);
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['data-theme', 'style']
    });

    return () => observer.disconnect();
  }, []);

  // Match board container height
  useEffect(() => {
    const updateHeight = () => {
      const boardContainer = containerRef.current?.parentElement?.querySelector('.board-container');
      if (boardContainer) {
        const boardHeight = boardContainer.getBoundingClientRect().height;
        if (boardHeight > 0) {
          setHeight(boardHeight);
        }
      }
    };

    updateHeight();
    const resizeObserver = new ResizeObserver(updateHeight);
    const boardContainer = containerRef.current?.parentElement?.querySelector('.board-container');
    if (boardContainer) {
      resizeObserver.observe(boardContainer);
    }
    window.addEventListener('resize', updateHeight);

    return () => {
      resizeObserver.disconnect();
      window.removeEventListener('resize', updateHeight);
    };
  }, []);

  // Normalize eval to 0-100 scale for bar display
  const normalizedEval = useMemo(() => {
    if (mate !== undefined) {
      return mate > 0 ? 100 : 0;
    }
    const maxCp = 1000;
    const clampedCp = Math.max(-maxCp, Math.min(maxCp, evalCp));
    const normalized = 50 + (clampedCp / maxCp) * 50;
    return Math.max(0, Math.min(100, normalized));
  }, [evalCp, mate]);

  // Format eval text
  const evalText = useMemo(() => {
    if (mate !== undefined) {
      return mate > 0 ? `M${mate}` : `M${Math.abs(mate)}`;
    }
    const pawns = (evalCp / 100).toFixed(1);
    return evalCp >= 0 ? `+${pawns}` : pawns;
  }, [evalCp, mate]);

  // White section should be on the same side as white pieces
  // When orientation is "white", white pieces are at bottom → white section at bottom
  // When orientation is "black", white pieces are at top → white section at top
  const whiteAtTop = orientation === "black";
  
  const whiteHeight = normalizedEval;
  const blackHeight = 100 - normalizedEval;

  // Helper functions to darken/lighten colors
  const hexToRgb = (hex: string): [number, number, number] | null => {
    const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
    return result ? [
      parseInt(result[1], 16),
      parseInt(result[2], 16),
      parseInt(result[3], 16)
    ] : null;
  };

  const darkenColor = (color: string, percent: number): string => {
    const rgb = hexToRgb(color);
    if (!rgb) return color;
    const [r, g, b] = rgb;
    const factor = 1 - (percent / 100);
    return `rgb(${Math.max(0, Math.floor(r * factor))}, ${Math.max(0, Math.floor(g * factor))}, ${Math.max(0, Math.floor(b * factor))})`;
  };

  const lightenColor = (color: string, percent: number): string => {
    const rgb = hexToRgb(color);
    if (!rgb) return color;
    const [r, g, b] = rgb;
    const factor = 1 + (percent / 100);
    return `rgb(${Math.min(255, Math.floor(r * factor))}, ${Math.min(255, Math.floor(g * factor))}, ${Math.min(255, Math.floor(b * factor))})`;
  };

  const bgPrimary = computedStyles?.bgPrimary || '#0c111a';
  const bgSecondary = computedStyles?.bgSecondary || '#111827';
  
  // Both sections use dark background, but different shades
  // White section: white background
  const whiteBgColor = 'rgba(255, 255, 255, 1)';
  // Black section: darker background
  const blackBgColor = darkenColor(bgPrimary, 15);
  
  // Text colors: lighter for both (since both backgrounds are dark)
  const whiteTextColor = lightenColor(bgPrimary, 50);
  const blackTextColor = lightenColor(bgPrimary, 40);

  // Create style objects for white and black sections
  const whiteSectionStyle: React.CSSProperties = {
    height: `${whiteHeight}%`,
    backgroundColor: whiteBgColor,
    transition: 'height 0.3s ease',
    position: 'absolute',
    ...(whiteAtTop ? { top: 0 } : { bottom: 0 }),
    left: 0,
    right: 0,
    display: 'flex',
    alignItems: whiteAtTop ? 'flex-start' : 'flex-end',
    justifyContent: 'center',
    padding: '2px 4px',
    fontWeight: '600',
    color: whiteTextColor,
    fontSize: '15px',
    lineHeight: '1.2',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  };

  const blackSectionStyle: React.CSSProperties = {
    height: `${blackHeight}%`,
    backgroundColor: 'rgba(16, 23, 36, 1)',
    transition: 'height 0.3s ease',
    position: 'absolute',
    ...(whiteAtTop ? { bottom: 0 } : { top: 0 }),
    left: 0,
    right: 0,
    display: 'flex',
    alignItems: whiteAtTop ? 'flex-end' : 'flex-start',
    justifyContent: 'center',
    padding: '2px 4px',
    fontWeight: '600',
    color: 'rgba(255, 255, 255, 1)',
    fontSize: '15px',
    lineHeight: '1.2',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  };

  return (
    <div 
      ref={containerRef}
      className="evaluation-bar-container"
      style={{ height: `${height}px` }}
    >
      <div className="evaluation-bar" style={{ height: '100%', position: 'relative' }}>
        {/* White section - matches white pieces side */}
        <div 
          className="evaluation-bar-white"
          style={whiteSectionStyle}
        >
          {whiteHeight > 8 && evalText}
        </div>
        
        {/* Black section - opposite side */}
        <div 
          className="evaluation-bar-black"
          style={blackSectionStyle}
        >
          {blackHeight > 8 && evalText}
        </div>
      </div>
    </div>
  );
}

