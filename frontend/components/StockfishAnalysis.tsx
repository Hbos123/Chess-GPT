"use client";

import { useState, useEffect, useRef, useMemo } from "react";
import { Chess } from "chess.js";

interface StockfishLine {
  multipv: number;
  eval_cp: number;
  mate?: number;
  depth: number;
  pv_san: string;
  move: string;
}

interface StockfishAnalysisProps {
  fen: string;
  depth?: number;
  maxLines?: number;
  onEvalUpdate?: (evalCp: number, mate?: number) => void;
}

export default function StockfishAnalysis({ 
  fen, 
  depth = 15, 
  maxLines = 3,
  onEvalUpdate 
}: StockfishAnalysisProps) {
  // Ensure depth is always defined and stable to prevent dependency array size changes
  const targetDepth = useMemo(() => depth ?? 15, [depth]);
  const [lines, setLines] = useState<StockfishLine[]>([]);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [showAllLines, setShowAllLines] = useState(false);
  const [expandedPgn, setExpandedPgn] = useState<Set<number>>(new Set());
  const [currentDepth, setCurrentDepth] = useState(1);
  const currentDepthRef = useRef<number>(1);
  const engineRef = useRef<any>(null);
  const currentFenRef = useRef<string>(fen);
  const infosRef = useRef<Map<number, StockfishLine>>(new Map());
  const depthTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Initialize Stockfish engine - only once on mount
  useEffect(() => {
    let isReady = false;
    const readyQueue: string[] = [];
    
    const initEngine = () => {
      try {
        // Use stockfish via Web Worker from public folder
        // The stockfish-lite.js file expects to find stockfish.wasm in the same directory
        const worker = new Worker('/stockfish-lite.js', { type: 'classic' });
        
        // Wrap worker to match expected interface
        const engine = {
          postMessage: (msg: string) => {
            try {
              if (!isReady && (msg === 'uci' || msg === 'isready')) {
                worker.postMessage(msg);
              } else if (!isReady) {
                readyQueue.push(msg);
              } else {
                worker.postMessage(msg);
              }
            } catch (e) {
              console.error('Error posting message to Stockfish:', e);
            }
          },
          onmessage: null as ((line: any) => void) | null,
          terminate: () => {
            try {
              worker.terminate();
            } catch (e) {
              // Ignore termination errors
            }
          },
        };
        
        worker.onmessage = (e: MessageEvent) => {
          const text = typeof e.data === 'string' ? e.data : String(e.data || '');
          if (!text || text.trim() === '') return;
          
          // Handle ready response
          if (text.trim() === 'readyok') {
            isReady = true;
            // Process queued messages
            readyQueue.forEach(msg => engine.postMessage(msg));
            readyQueue.length = 0;
          }
          
          if (engine.onmessage) {
            engine.onmessage({ data: text });
          }
        };
        
        worker.onerror = (e: ErrorEvent) => {
          console.error('Stockfish worker error:', e);
          console.error('Error details:', {
            message: e.message,
            filename: e.filename,
            lineno: e.lineno,
            colno: e.colno,
            error: e.error,
          });
          setIsAnalyzing(false);
        };
        
        // Set up message handler
        engine.onmessage = (line: any) => {
          const text = typeof line === 'string' ? line : line?.data || '';
          if (!text || text.trim() === '') return;

          if (text.startsWith('info')) {
            const tokens = text.split(/\s+/);
            const info: Partial<StockfishLine> = {};
            
            for (let i = 0; i < tokens.length; i++) {
              const t = tokens[i];
              if (t === 'depth') {
                const newDepth = parseInt(tokens[++i], 10);
                if (!isNaN(newDepth)) {
                  info.depth = newDepth;
                  currentDepthRef.current = newDepth;
                  setCurrentDepth(newDepth);
                }
              }
              if (t === 'multipv') info.multipv = parseInt(tokens[++i], 10);
              if (t === 'score') {
                const type = tokens[++i];
                const val = parseInt(tokens[++i], 10);
                if (type === 'cp') {
                  info.eval_cp = val;
                } else if (type === 'mate') {
                  info.mate = val;
                  info.eval_cp = val > 0 ? 10000 : -10000;
                }
              }
              if (t === 'pv') {
                const pvUci = tokens.slice(i + 1);
                // Convert UCI to SAN
                try {
                  const board = new Chess(currentFenRef.current);
                  const moves: string[] = [];
                  for (const uci of pvUci) {
                    try {
                      const from = uci.substring(0, 2);
                      const to = uci.substring(2, 4);
                      const promo = uci.length > 4 ? uci.substring(4, 5) : undefined;
                      const move = board.move({ from, to, promotion: promo as any });
                      if (!move) break;
                      moves.push(move.san);
                    } catch {
                      break;
                    }
                  }
                  info.pv_san = moves.join(' ');
                  info.move = moves[0] || '';
                } catch {
                  info.pv_san = '';
                  info.move = '';
                }
                break;
              }
            }

            if (info.multipv && info.eval_cp !== undefined && info.pv_san) {
              const line: StockfishLine = {
                multipv: info.multipv,
                eval_cp: info.eval_cp,
                mate: info.mate,
                depth: info.depth || currentDepthRef.current,
                pv_san: info.pv_san,
                move: info.move || '',
              };
              
              infosRef.current.set(info.multipv, line);
              
              // Update state with all lines, sorted by eval
              const sortedLines = Array.from(infosRef.current.values())
                .sort((a, b) => {
                  // Sort by eval (higher is better for white)
                  return b.eval_cp - a.eval_cp;
                })
                .slice(0, maxLines);
              
              setLines(sortedLines);
              
              // Notify parent of best eval
              if (info.multipv === 1 && onEvalUpdate) {
                onEvalUpdate(line.eval_cp, line.mate);
              }
            }
          } else if (text.startsWith('bestmove')) {
            // When bestmove is received, continue to next depth if not at max
            const currentDepthValue = currentDepthRef.current;
            if (currentDepthValue < targetDepth && engineRef.current) {
              // Continue analysis at next depth
              const nextDepth = currentDepthValue + 1;
              currentDepthRef.current = nextDepth;
              setCurrentDepth(nextDepth);
              engineRef.current.postMessage(`go depth ${nextDepth}`);
            } else {
              setIsAnalyzing(false);
              if (depthTimeoutRef.current) {
                clearTimeout(depthTimeoutRef.current);
                depthTimeoutRef.current = null;
              }
            }
          }
        };
        
        // Initialize the engine
        engine.postMessage('uci');
        engine.postMessage('isready');
        
        engineRef.current = engine;
        
        console.log('Stockfish engine initialized successfully');
      } catch (error) {
        console.error('Failed to initialize Stockfish:', error);
        console.error('Error details:', {
          message: (error as Error)?.message,
          stack: (error as Error)?.stack,
          name: (error as Error)?.name,
        });
        setIsAnalyzing(false);
      }
    };

    initEngine();

    return () => {
      if (engineRef.current) {
        try {
          engineRef.current.postMessage('stop');
          engineRef.current.postMessage('quit');
          if (engineRef.current.terminate) {
            engineRef.current.terminate();
          }
        } catch (e) {
          // Ignore errors on cleanup
        }
        engineRef.current = null;
      }
      if (depthTimeoutRef.current) {
        clearTimeout(depthTimeoutRef.current);
        depthTimeoutRef.current = null;
      }
    };
  }, []); // Only initialize once on mount

  // Analyze position when FEN changes - progressive depth
  useEffect(() => {
    if (!engineRef.current) return;
    
    // Stop any ongoing analysis
    engineRef.current.postMessage('stop');
    
    // Clear previous timeout
    if (depthTimeoutRef.current) {
      clearTimeout(depthTimeoutRef.current);
      depthTimeoutRef.current = null;
    }
    
    currentFenRef.current = fen;
    setIsAnalyzing(true);
    setLines([]);
    currentDepthRef.current = 1;
    setCurrentDepth(1);
    infosRef.current.clear();

    const engine = engineRef.current;

    // Small delay to ensure previous stop command is processed
    setTimeout(() => {
      // Start analysis at depth 1, will progress to target depth
      engine.postMessage('ucinewgame');
      engine.postMessage(`setoption name MultiPV value ${maxLines}`);
      engine.postMessage(`position fen ${fen}`);
      engine.postMessage('go depth 1');

      // Set a longer timeout for depth progression (allow more time for deeper analysis)
      const timeout = setTimeout(() => {
        engine.postMessage('stop');
        setIsAnalyzing(false);
        depthTimeoutRef.current = null;
      }, Math.max(30000, targetDepth * 2000)); // At least 30s, or 2s per depth

      depthTimeoutRef.current = timeout;
    }, 100);

    return () => {
      if (depthTimeoutRef.current) {
        clearTimeout(depthTimeoutRef.current);
        depthTimeoutRef.current = null;
      }
      if (engineRef.current) {
        engineRef.current.postMessage('stop');
      }
    };
  }, [fen, maxLines, targetDepth]);

  const formatEval = (evalCp: number, mate?: number) => {
    if (mate !== undefined) {
      return mate > 0 ? `M${mate}` : `M${Math.abs(mate)}`;
    }
    const pawns = (evalCp / 100).toFixed(1);
    return evalCp >= 0 ? `+${pawns}` : pawns;
  };

  // Truncate PGN to one line with ellipsis
  const truncatePgn = (pgn: string, maxLength: number = 50): string => {
    if (pgn.length <= maxLength) return pgn;
    return pgn.substring(0, maxLength) + '...';
  };

  // Show minimal loading state when analyzing
  if (lines.length === 0 && isAnalyzing) {
    return (
      <div className="stockfish-analysis">
        {isAnalyzing && <span className="stockfish-analyzing-indicator">Analyzing depth {currentDepth}...</span>}
      </div>
    );
  }

  if (lines.length === 0 && !isAnalyzing) {
    return null;
  }

  const visibleLines = showAllLines ? lines.slice(0, 3) : lines.slice(0, 1);

  return (
    <div className="stockfish-analysis">
      {visibleLines.map((line, idx) => {
        const isPgnExpanded = expandedPgn.has(line.multipv);
        const displayPgn = isPgnExpanded ? line.pv_san : truncatePgn(line.pv_san);
        const shouldShowExpand = !isPgnExpanded && line.pv_san.length > 50;

        return (
          <div key={line.multipv} className="stockfish-line">
            <div className="stockfish-line-header">
              <div className="stockfish-line-info">
                <span className="stockfish-line-number">{line.multipv}.</span>
                <span className="stockfish-line-eval">
                  {formatEval(line.eval_cp, line.mate)}
                </span>
                <span className="stockfish-line-depth">depth {line.depth}</span>
              </div>
              <div className="stockfish-line-move">{line.move}</div>
              <div 
                className="stockfish-line-pv-inline"
                onClick={() => {
                  if (shouldShowExpand || isPgnExpanded) {
                    setExpandedPgn(prev => {
                      const next = new Set(prev);
                      if (next.has(line.multipv)) {
                        next.delete(line.multipv);
                      } else {
                        next.add(line.multipv);
                      }
                      return next;
                    });
                  }
                }}
                style={{ 
                  cursor: shouldShowExpand || isPgnExpanded ? 'pointer' : 'default' 
                }}
              >
                {displayPgn}
              </div>
              {idx === 0 && lines.length > 1 && (
                <span 
                  className="stockfish-expand-arrow"
                  onClick={(e) => {
                    e.stopPropagation();
                    setShowAllLines(!showAllLines);
                  }}
                  style={{ cursor: 'pointer' }}
                >
                  {showAllLines ? '▼' : '▶'}
                </span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

