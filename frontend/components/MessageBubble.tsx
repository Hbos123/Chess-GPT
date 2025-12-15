import { useEffect, useMemo, useState } from 'react';
import { stripEmojis } from '@/utils/emojiFilter';
import Board from '@/components/Board';
import ConfidenceTree from './ConfidenceTree';
import TagConfidenceView from './TagConfidenceView';
import LoadingMessage from './LoadingMessage';
import InteractivePGN from './InteractivePGN';
import GameReviewTable from './GameReviewTable';
import PersonalReviewCharts from './PersonalReviewCharts';

interface MessageBubbleProps {
  role: 'user' | 'assistant' | 'system' | 'graph' | 'button' | 'expandable_table';
  content: string;
  rawData?: any;
  timestamp?: Date;
  currentFEN?: string;
  onApplyPGN?: (fen: string, pgn: string) => void;
  onPreviewFEN?: (fen: string | null) => void;
  buttonAction?: string;
  buttonLabel?: string;
  onButtonAction?: (action: string) => void;
  isButtonDisabled?: boolean;
  onRunFullAnalysis?: (fen: string) => void;
}

export default function MessageBubble({ role, content, rawData, timestamp, currentFEN, onApplyPGN, onPreviewFEN, buttonAction, buttonLabel, onButtonAction, isButtonDisabled, onRunFullAnalysis }: MessageBubbleProps) {
  const [showRawData, setShowRawData] = useState(false);
  const [showConfidence, setShowConfidence] = useState(false);
  const [showReviewTable, setShowReviewTable] = useState(false);
  const [localMoveConfidence, setLocalMoveConfidence] = useState<any>(null);
  const [localPositionConfidence, setLocalPositionConfidence] = useState<any>(null);
  const [showConfHelp, setShowConfHelp] = useState(false);
  const [showTree, setShowTree] = useState(false);
  const [baselineTarget, setBaselineTarget] = useState<number>(80);
  const [isRaising, setIsRaising] = useState(false);
  const [miniFen, setMiniFen] = useState<string | null>(null);
  const [targetLineConf, setTargetLineConf] = useState<number>(80);
  const [targetEndConf, setTargetEndConf] = useState<number>(80);
  const [maxDepth, setMaxDepth] = useState<number>(18);
  const [treeViewMode, setTreeViewMode] = useState<"nodes" | "tags">("nodes");

  const DEFAULT_BASELINE = 80;

  // Initialize miniFen when miniBoard data is available
  useEffect(() => {
    if (rawData?.miniBoard?.fen) {
      setMiniFen(rawData.miniBoard.fen);
    }
  }, [rawData?.miniBoard?.fen]);

  const backendBase = (process.env.NEXT_PUBLIC_BACKEND_URL as string) || 'http://localhost:8000';
  const engineData = (rawData?.rawEngineData ?? rawData) || {};
  const moveConfidence = localMoveConfidence || engineData?.confidence;
  const positionConfidence = localPositionConfidence || engineData?.position_confidence || rawData?.position_confidence;


  const getConfidenceNodes = (conf: any): any[] => {
    if (!conf) return [];
    // Direct nodes array
    if (Array.isArray(conf.nodes)) return conf.nodes;
    // Structure: {played_move: {nodes: [...]}, best_move: {nodes: [...]}}
    if (conf.played_move && Array.isArray(conf.played_move.nodes)) return conf.played_move.nodes;
    if (conf.best_move && Array.isArray(conf.best_move.nodes)) return conf.best_move.nodes;
    return [];
  };

  const getSnapshotFrames = (conf: any): any[][] => {
    if (!conf) return [];
    if (Array.isArray(conf.snapshots) && conf.snapshots.length > 0) {
      return conf.snapshots.map((snap: any) => (Array.isArray(snap.nodes) ? snap.nodes : []));
    }
    if (Array.isArray(conf.steps) && conf.steps.length > 0) {
      return conf.steps;
    }
    return [];
  };

  const mergeNodeArrays = (existingNodes: any[], incomingNodes: any[]): any[] => {
    if (!existingNodes.length) return incomingNodes;
    const existingMap = new Map(existingNodes.map((node: any) => [node.id, node]));
    const mergedIds = new Set<string>();

    const merged = incomingNodes.map((node: any) => {
      const prev = existingMap.get(node.id);
      mergedIds.add(node.id);
      if (!prev) {
        return node;
      }
      // CRITICAL: Preserve initial_confidence if it was already set (never overwrite)
      // Also preserve branches and extended_moves to maintain tree structure
      const preserveInitialConf = prev.initial_confidence != null ? prev.initial_confidence : (node.initial_confidence ?? null);
      const preserveBranches = prev.has_branches || prev.shape === "triangle" || node.has_branches || node.shape === "triangle";
      const preserveExtendedMoves = { ...(prev.extended_moves || {}), ...(node.extended_moves || {}) };
      
      return {
        ...prev,
        ...node,
        // Preserve shape if it was a triangle (don't let it become a circle)
        shape: prev.shape === "triangle" || prev.shape === "square" ? prev.shape : (node.shape ?? prev.shape),
        // Update color based on current baseline, but preserve branch status
        color: node.color ?? prev.color ?? (prev.insufficient_confidence ? "red" : prev.color),
        has_branches: preserveBranches,
        // CRITICAL: Never overwrite initial_confidence once it's set
        initial_confidence: preserveInitialConf,
        // Update frozen_confidence with new value if provided, but don't lose it
        frozen_confidence: node.frozen_confidence != null ? node.frozen_confidence : (prev.frozen_confidence ?? null),
        insufficient_confidence: node.insufficient_confidence ?? prev.insufficient_confidence ?? false,
        // Merge extended_moves to preserve all branches
        extended_moves: preserveExtendedMoves,
        // Merge metadata to preserve branch_summary
        metadata: { ...(prev.metadata || {}), ...(node.metadata || {}) },
        fen: node.fen || prev.fen || null,
      };
    });

    existingNodes.forEach((node: any) => {
      if (!mergedIds.has(node.id)) {
        merged.push(node);
      }
    });

    return merged;
  };

  const withMergedNodes = (base: any, nodesList: any[]): any => {
    if (!base) {
      return { nodes: nodesList };
    }
    if (Array.isArray(base.nodes)) {
      return { ...base, nodes: nodesList };
    }
    const result = { ...base };
    if (result.played_move?.nodes) {
      result.played_move = { ...result.played_move, nodes: nodesList };
    }
    if (result.best_move?.nodes) {
      result.best_move = { ...result.best_move, nodes: nodesList };
    }
    return result;
  };

  const resolveOverall = (conf: any): number | null => {
    if (!conf) return null;
    if (typeof conf.overall_confidence === 'number') return conf.overall_confidence;
    if (typeof conf.played_move?.overall_confidence === 'number') return conf.played_move.overall_confidence;
    return null;
  };

  const resolveBestOverall = (conf: any): number | null => {
    if (!conf) return null;
    if (typeof conf.best_move?.overall_confidence === 'number') return conf.best_move.overall_confidence;
    if (typeof conf.best_alternative?.overall_confidence === 'number') return conf.best_alternative.overall_confidence;
    return null;
  };

  const resolveLineConfidence = (conf: any): number | null => {
    if (!conf) return null;
    if (typeof conf.line_confidence === 'number') return conf.line_confidence;
    if (typeof conf.played_move?.line_confidence === 'number') return conf.played_move.line_confidence;
    return null;
  };

  const resolveBestLineConfidence = (conf: any): number | null => {
    if (!conf) return null;
    if (typeof conf.best_move?.line_confidence === 'number') return conf.best_move.line_confidence;
    if (typeof conf.best_alternative?.line_confidence === 'number') return conf.best_alternative.line_confidence;
    return null;
  };
  
  // Strip all emoji from content
  const filteredContent = stripEmojis(content);

  const escapeHtml = (text: string) =>
    text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");

  const formatSystemContent = (text: string) => {
    const escaped = escapeHtml(text);
    const withBold = escaped.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    return withBold.replace(/\n/g, "<br />");
  };

  const formattedSystemHtml = useMemo(() => formatSystemContent(filteredContent), [filteredContent]);

  const copyRawData = () => {
    if (rawData) {
      navigator.clipboard.writeText(JSON.stringify(rawData, null, 2));
    }
  };

  // If this is a loading message, render LoadingMessage component
  if (role === 'system' && rawData?.loading) {
    return <LoadingMessage type={rawData.loadingType} message={content} />;
  }

  const treeNodes = useMemo(() => {
    const moveNodes = getConfidenceNodes(moveConfidence);
    if (moveNodes.length) {
      return moveNodes;
    }
    const positionNodes = getConfidenceNodes(positionConfidence);
    if (positionNodes.length) {
      return positionNodes;
    }
    return [];
  }, [moveConfidence, positionConfidence]);

  if (role === 'system') {
    return (
      <div className="system-whisper" dangerouslySetInnerHTML={{ __html: formattedSystemHtml }} />
    );
  }

  // Special message types (legacy support)
  if (role === 'graph' || role === 'button' || role === 'expandable_table') {
    // Render a bare, interactive mini-board (no card) - independent instance per message
    if (rawData?.miniBoard?.fen && miniFen) {
      const orientation: 'white' | 'black' = rawData.miniBoard.orientation || 'white';
      const boardId: string = rawData?.miniBoard?.id || `${Date.now()}-${Math.random().toString(36).slice(2)}`;

      const handleMiniMove = (from: string, to: string, promotion?: string) => {
        try {
          // Use chess.js at runtime to keep bundle small; guard for SSR
          const { Chess } = require('chess.js');
          const temp = new Chess(miniFen);
          const mv = temp.move({ from, to, promotion });
          if (mv) {
            const newFen = temp.fen();
            setMiniFen(newFen);
            // Notify app about inline board change so it can analyze and add to context
            if (typeof window !== 'undefined') {
              const detail = { id: boardId, fen: newFen, pgn: temp.pgn(), orientation };
              window.dispatchEvent(new CustomEvent('inlineBoardChanged', { detail }));
            }
          }
        } catch {
          // ignore invalid moves
        }
      };

      return (
        <div className="inline-mini-board">
          <div style={{ width: 480, margin: '0 auto' }}>
            <Board
              fen={miniFen}
              onMove={handleMiniMove}
              orientation={orientation}
            />
          </div>
        </div>
      );
    }
    
    if (role === 'button') {
      if (!buttonAction) {
        console.warn('[Button] Missing buttonAction for button message', { content, rawData });
        return null;
      }
      const label = buttonLabel || (content?.trim() || 'Continue');
      const handleClick = () => {
        if (onButtonAction) {
          onButtonAction(buttonAction);
        } else if (typeof window !== 'undefined') {
          window.dispatchEvent(new CustomEvent('chatButtonAction', { 
            detail: { 
              action: buttonAction,
              buttonId: rawData?.buttonId 
            } 
          }));
        }
      };
      return (
        <div className="message-bubble message-button">
          <button 
            className="inline-button" 
            onClick={handleClick}
            disabled={isButtonDisabled}
            style={{ opacity: isButtonDisabled ? 0.5 : 1, cursor: isButtonDisabled ? 'not-allowed' : 'pointer' }}
          >
            {label}
          </button>
        </div>
      );
    }

    // Suppress empty graph messages when no mini-board metadata exists (with a console hint)
    if (role === 'graph') {
      if (typeof window !== 'undefined') {
        console.warn('[Graph] Suppressed graph message without miniBoard meta', { rawData, content });
      }
      return null;
    }
    return (
      <div className={`message-bubble message-${role}`}>
        <div className="message-content">
          <pre className="message-text">{filteredContent}</pre>
        </div>
      </div>
    );
  }

  // Show confidence affordance whenever we have analysis FEN (position) even if confidence not yet computed
  const hasConfidence = !!(moveConfidence || positionConfidence || engineData?.fen || engineData?.fen_before);
  
  // Check if this message has game review data
  const hasReviewData = !!(rawData?.gameReviewTable);

  const renderPercent = (value: number | null | undefined) => (value == null ? '--' : Math.round(value).toString());

  const playedOverallValue = resolveOverall(moveConfidence);
  const playedLineValue = resolveLineConfidence(moveConfidence);
  const bestOverallValue = resolveBestOverall(moveConfidence);
  const bestLineValue = resolveBestLineConfidence(moveConfidence);
  const positionOverallValue = resolveOverall(positionConfidence);
  const positionLineValue = resolveLineConfidence(positionConfidence);

  function nextStep(current: number) {
    const step = Math.min(95, Math.ceil(Math.max(0, current) / 10) * 10 + 10);
    return step;
  }

  function getCurrentLineConfidence(): number {
    // Try to get from direct confidence data first
    if (moveConfidence?.line_confidence != null) return moveConfidence.line_confidence;
    if (positionConfidence?.line_confidence != null) return positionConfidence.line_confidence;
    
    const playedLine = resolveLineConfidence(moveConfidence);
    const bestLine = resolveBestLineConfidence(moveConfidence);
    if (playedLine != null && bestLine != null) {
      return Math.min(playedLine, bestLine);
    }
    if (playedLine != null) return playedLine;
    const positionLine = resolveLineConfidence(positionConfidence);
    return positionLine ?? 0;
  }

  function getCurrentEndConfidence(): number {
    if (moveConfidence?.end_confidence != null) return moveConfidence.end_confidence;
    if (positionConfidence?.end_confidence != null) return positionConfidence.end_confidence;
    // Fallback to overall confidence
    return getCurrentLineConfidence();
  }

  async function raiseConfidence(mode: 'line' | 'end' | 'depth', target?: number) {
    if (isRaising) {
      return;
    }
    
    setIsRaising(true);
    
    // Log initial tree state
    const baselineForCounts = baselineTarget ?? DEFAULT_BASELINE;
    const colorForNode = (node: any) => {
      if (!node) return 'red';
      const hasBranches = node.has_branches ?? node.shape === 'triangle';
      const frozen =
        typeof node.frozen_confidence === 'number' ? node.frozen_confidence : null;
      const confidenceValue =
        typeof node.ConfidencePercent === 'number'
          ? node.ConfidencePercent
          : typeof node.confidence === 'number'
          ? node.confidence
          : 0;

      if (hasBranches) {
        // Preserve blue triangles (still pending exploration)
        if ((node.color === 'blue' || node.shape === 'triangle') && frozen == null) {
          return node.color === 'blue' ? 'blue' : confidenceValue >= baselineForCounts ? 'green' : 'red';
        }
        const effective = frozen != null ? frozen : confidenceValue;
        return effective >= baselineForCounts ? 'green' : 'red';
      }

      return confidenceValue >= baselineForCounts ? 'green' : 'red';
    };

    const summarizeNodes = (list: any[]) => {
      const pv = list.filter((node: any) => (node.id || '').startsWith('pv-')).length;
      const triangles = list.filter((node: any) => node.shape === 'triangle' || node.has_branches).length;
      const redCount = list.filter((node: any) => colorForNode(node) === 'red').length;
      const greenCount = list.filter((node: any) => colorForNode(node) === 'green').length;
      const blueCount = list.filter((node: any) => colorForNode(node) === 'blue').length;
      
      // Detailed breakdown for debugging
      const pvNodes = list.filter((node: any) => (node.id || '').startsWith('pv-'));
      const redPvNodes = pvNodes.filter((node: any) => colorForNode(node) === 'red');
      const lastPvNode = pvNodes.length > 0 ? pvNodes[pvNodes.length - 1] : null;
      
      return {
        total: list.length,
        pv,
        triangles,
        red_circles: redCount,
        green_circles: greenCount,
        blue_circles: blueCount,
        red_pv_nodes: redPvNodes.length,
        last_pv_is_red: lastPvNode ? colorForNode(lastPvNode) === 'red' : false,
        last_pv_id: lastPvNode?.id,
      };
    };

    const initialPool = getConfidenceNodes(moveConfidence);
    const initialNodes = initialPool.length ? initialPool : getConfidenceNodes(positionConfidence);

    console.log('🌳 BEFORE RAISE:', {
      ...summarizeNodes(initialNodes),
      line_conf: getCurrentLineConfidence(),
    });
    
    try {
      // Determine target based on mode
      let targetValue: number | undefined;
      let targetLineConfValue: number | undefined;
      let targetEndConfValue: number | undefined;
      let maxDepthValue: number | undefined;
      
      if (mode === 'line') {
        targetValue = target ?? targetLineConf ?? nextStep(getCurrentLineConfidence());
        targetLineConfValue = targetValue;
      } else if (mode === 'end') {
        targetValue = target ?? targetEndConf ?? nextStep(getCurrentEndConfidence());
        targetEndConfValue = targetValue;
      } else if (mode === 'depth') {
        maxDepthValue = maxDepth;
      }
      
      if ((moveConfidence || engineData?.fen_before) && engineData?.fen_before && engineData?.move_played) {
        // Send existing nodes for incremental update instead of rebuild
        const existingNodes = getConfidenceNodes(moveConfidence);
        const res = await fetch(`${backendBase}/confidence/raise_move`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ 
            fen: engineData.fen_before, 
            move_san: engineData.move_played, 
            target: targetValue ?? baselineTarget, 
            mode,
            target_line_conf: targetLineConfValue,
            target_end_conf: targetEndConfValue,
            max_depth: maxDepthValue,
            existing_nodes: existingNodes.length > 0 ? existingNodes : undefined
          })
        });

        if (!res.ok) {
          console.error('[Confidence] HTTP error:', res.status, res.statusText);
          setIsRaising(false);
          return;
        }

        const json = await res.json();

        if (json?.confidence) {
          const conf = json.confidence;
          const frames = getSnapshotFrames(conf);
          
          // Log phase information if available
          const phaseInfo = conf.stats?.phase_info;
          if (phaseInfo) {
            console.log('\n' + '='.repeat(80));
            console.log('🌳 CONFIDENCE RAISE PHASES');
            console.log('='.repeat(80));
            console.log('📊 Phase 1: Converted', phaseInfo.phase1_nodes_converted, 'red node(s) to blue triangles');
            console.log('🌿 Phase 2: Added', phaseInfo.phase2_nodes_added, 'new node(s) from branch extensions');
            console.log('❄️  Phase 3: Frozen and recolored', phaseInfo.phase3_nodes_frozen, 'blue triangle(s)');
            console.log('='.repeat(80) + '\n');
          }

          const logFinalState = () => {
            const finalNodes = getConfidenceNodes(conf);
            console.log('🌳 AFTER RAISE:', {
              ...summarizeNodes(finalNodes),
              iterations: conf.stats?.iteration ?? conf.debug?.iteration_count,
              line_conf: resolveLineConfidence(conf) ?? conf.line_confidence ?? getCurrentLineConfidence(),
              phases: phaseInfo ? phaseInfo.phases_executed : undefined,
            });
          };

          if (frames.length > 0) {
            let idx = 0;
            const animate = () => {
              const frameNodes = frames[idx] || [];
              setLocalMoveConfidence((prev: any) => {
                const existingNodes = getConfidenceNodes(prev);
                const mergedNodes = mergeNodeArrays(existingNodes, frameNodes);
                return withMergedNodes({ ...conf, snapshots: conf.snapshots }, mergedNodes);
              });
              idx += 1;
              if (idx < frames.length) {
                setTimeout(animate, 300);
              } else {
                // Final frame - merge with existing to preserve all state
                setLocalMoveConfidence((prev: any) => {
                  const existingNodes = getConfidenceNodes(prev);
                  const finalNodes = getConfidenceNodes(conf);
                  const mergedNodes = mergeNodeArrays(existingNodes, finalNodes);
                  return withMergedNodes(conf, mergedNodes);
                });
                setIsRaising(false);
                logFinalState();
              }
            };
            animate();
          } else {
            // No snapshots - still merge with existing nodes to preserve state
            setLocalMoveConfidence((prev: any) => {
              const existingNodes = getConfidenceNodes(prev);
              const newNodes = getConfidenceNodes(conf);
              const mergedNodes = mergeNodeArrays(existingNodes, newNodes);
              return withMergedNodes(conf, mergedNodes);
            });
            setIsRaising(false);
            logFinalState();
          }
        } else {
          setIsRaising(false);
        }
      } else if ((positionConfidence || engineData?.fen) && engineData?.fen) {
        const res = await fetch(`${backendBase}/confidence/raise_position`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ 
            fen: engineData.fen, 
            target: targetValue ?? baselineTarget,
            mode,
            target_line_conf: targetLineConfValue,
            target_end_conf: targetEndConfValue,
            max_depth: maxDepthValue
          })
        });
        
        if (!res.ok) {
          console.error('[Confidence] HTTP error:', res.status, res.statusText);
          setIsRaising(false);
          return;
        }
        
        const json = await res.json();

        if (json?.position_confidence) {
          const conf = json.position_confidence;
          const frames = getSnapshotFrames(conf);
          
          // Log phase information if available
          const phaseInfo = conf.stats?.phase_info;
          if (phaseInfo) {
            console.log('\n' + '='.repeat(80));
            console.log('🌳 CONFIDENCE RAISE PHASES');
            console.log('='.repeat(80));
            console.log('📊 Phase 1: Converted', phaseInfo.phase1_nodes_converted, 'red node(s) to blue triangles');
            console.log('🌿 Phase 2: Added', phaseInfo.phase2_nodes_added, 'new node(s) from branch extensions');
            console.log('❄️  Phase 3: Frozen and recolored', phaseInfo.phase3_nodes_frozen, 'blue triangle(s)');
            console.log('='.repeat(80) + '\n');
          }

          const logFinalState = () => {
            const finalNodes = getConfidenceNodes(conf);
            console.log('🌳 AFTER RAISE:', {
              ...summarizeNodes(finalNodes),
              iterations: conf.stats?.iteration ?? conf.debug?.iteration_count,
              line_conf: resolveLineConfidence(conf) ?? conf.line_confidence ?? getCurrentLineConfidence(),
              phases: phaseInfo ? phaseInfo.phases_executed : undefined,
            });
          };

          if (frames.length > 0) {
            let idx = 0;
            const animate = () => {
              const frameNodes = frames[idx] || [];
              setLocalPositionConfidence((prev: any) => {
                const existingNodes = getConfidenceNodes(prev);
                const mergedNodes = mergeNodeArrays(existingNodes, frameNodes);
                return withMergedNodes({ ...conf, snapshots: conf.snapshots }, mergedNodes);
              });
              idx += 1;
              if (idx < frames.length) {
                setTimeout(animate, 300);
              } else {
                // Final frame - merge with existing to preserve all state
                setLocalPositionConfidence((prev: any) => {
                  const existingNodes = getConfidenceNodes(prev);
                  const finalNodes = getConfidenceNodes(conf);
                  const mergedNodes = mergeNodeArrays(existingNodes, finalNodes);
                  return withMergedNodes(conf, mergedNodes);
                });
                setIsRaising(false);
                logFinalState();
              }
            };
            animate();
          } else {
            // No snapshots - still merge with existing nodes to preserve state
            setLocalPositionConfidence((prev: any) => {
              const existingNodes = getConfidenceNodes(prev);
              const newNodes = getConfidenceNodes(conf);
              const mergedNodes = mergeNodeArrays(existingNodes, newNodes);
              return withMergedNodes(conf, mergedNodes);
            });
            setIsRaising(false);
            logFinalState();
          }
        } else {
          setIsRaising(false);
        }
      } else {
        setIsRaising(false);
      }
    } catch (e) {
      console.error('[Confidence] Raise failed:', e);
      setIsRaising(false);
    }
  }

  // Minimal markdown for display: **bold**, *italic*, keep line breaks
  function toMinimalHtml(text: string) {
    // Process markdown in correct order to avoid interference
    let html = text;
    
    // 1. Escape HTML entities for security (do this first)
    const esc = (s: string) => s
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
    html = esc(html);
    
    // 2. Replace ## with double line break (simple - just insert <br/><br/> and remove ##)
    html = html.replace(/##\s*/g, '<br/><br/>');
    
    // 3. Replace **text** with <strong>text</strong> (toggle bold on/off)
    html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    
    // 4. Convert newlines to breaks
    html = html.replace(/\n/g, '<br/>');
    
    // 5. Clean up multiple consecutive line breaks
    html = html.replace(/(<br\/>){3,}/g, '<br/><br/>');
    
    return { __html: html };
  }

  return (
    <div className={`message-bubble message-${role}`}>
      <div className="message-header">
        <span className="message-role">
          {role === 'user' ? 'You' : role === 'assistant' ? 'Chesster' : 'System'}
        </span>
        
        {role === 'assistant' && rawData && (
          <button 
            className="raw-data-toggle"
            onClick={() => setShowRawData(!showRawData)}
            title="View raw analysis data"
          >
            Raw Data
          </button>
        )}

        {/* Confidence badge is shown at bottom-right below */}
      </div>
      
      <div className="message-content">
        <div className="message-text">
          {currentFEN ? (
            <InteractivePGN
              text={filteredContent}
              currentFEN={currentFEN}
              onApplySequence={onApplyPGN}
              onHoverMove={onPreviewFEN}
            />
          ) : (
            <div dangerouslySetInnerHTML={toMinimalHtml(filteredContent)} />
          )}
        </div>
      </div>
      
      {showRawData && rawData && (
        <div className="raw-data-panel">
          <div className="raw-data-header">
            <span>Raw Analysis Data</span>
            <button onClick={copyRawData} className="copy-button">
              Copy
            </button>
          </div>
          <pre className="raw-data-content">
            {JSON.stringify(rawData, null, 2)}
          </pre>
        </div>
      )}

      {showReviewTable && rawData?.gameReviewTable && (
        <div className="game-review-panel">
          <div className="review-header">Game Review Summary</div>
          <GameReviewTable data={rawData.gameReviewTable} />
        </div>
      )}

      {(rawData?.review || rawData?.tool_raw_data?.review) && (
        <div className="game-review-panel">
          <div className="review-header">Game Review Summary</div>
          <GameReviewTable data={rawData?.review || rawData?.tool_raw_data?.review} />
        </div>
      )}
      
      {rawData?.personalReviewChart && (
        <div className="personal-review-chart-panel">
          <PersonalReviewCharts data={rawData.personalReviewChart.data} />
        </div>
      )}

      {showConfidence && hasConfidence && (
        <div className="confidence-panel">
          {isRaising && (
            <div className="conf-loading">
              <span className="conf-spinner">⏳</span>
              <span>Analyzing and raising confidence...</span>
            </div>
          )}
          {moveConfidence ? (
            <div className="conf-grid">
              <div>
                <div className="conf-label">Played move (overall)</div>
                <div className="conf-value">{`${renderPercent(playedOverallValue)}%`}</div>
                <div className="conf-sub">Line confidence: {`${renderPercent(playedLineValue)}%`}</div>
              </div>
              {(bestOverallValue != null || bestLineValue != null) && (
                <div>
                  <div className="conf-label">Best move (overall)</div>
                  <div className="conf-value">{`${renderPercent(bestOverallValue)}%`}</div>
                  <div className="conf-sub">Line confidence: {`${renderPercent(bestLineValue)}%`}</div>
                </div>
              )}
            </div>
          ) : (
            <div>
              <div className="conf-label">Position confidence</div>
              <div className="conf-value">{`${renderPercent(positionOverallValue)}%`}</div>
              <div className="conf-sub">Line confidence: {`${renderPercent(positionLineValue)}%`}</div>
            </div>
          )}

          <div className="conf-actions">
            {/* Current Values Display */}
            <div className="conf-current-values">
              <div className="conf-value-display">
                <span className="conf-label">Line Confidence:</span>
                <span className="conf-value-text">{renderPercent(getCurrentLineConfidence())}%</span>
              </div>
              <div className="conf-value-display">
                <span className="conf-label">End Confidence:</span>
                <span className="conf-value-text">{renderPercent(getCurrentEndConfidence())}%</span>
              </div>
              <div className="conf-value-display">
                <span className="conf-label">Max Depth:</span>
                <span className="conf-value-text">{maxDepth} ply</span>
              </div>
            </div>

            <div className="conf-actions-row">
              <button onClick={() => setShowTree((v) => !v)}>{showTree ? 'Hide tree' : 'Show tree'}</button>
              {showTree && (
                <div className="view-mode-toggle">
                  <button
                    className={treeViewMode === "nodes" ? "active" : ""}
                    onClick={() => setTreeViewMode("nodes")}
                  >
                    Node View
                  </button>
                  <button
                    className={treeViewMode === "tags" ? "active" : ""}
                    onClick={() => setTreeViewMode("tags")}
                  >
                    Tag View
                  </button>
                </div>
              )}
              <button 
                onClick={async () => {
                  try {
                    const nodes = getConfidenceNodes(moveConfidence || positionConfidence);
                    const res = await fetch(`${backendBase}/generate_confidence_lesson`, {
                      method: 'POST',
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify({
                        nodes: nodes,
                        baseline: baselineTarget
                      })
                    });
                    if (res.ok) {
                      const lesson = await res.json();
                      // Trigger lesson start event
                      if (typeof window !== 'undefined') {
                        window.dispatchEvent(new CustomEvent('startConfidenceLesson', { detail: lesson }));
                      }
                    }
                  } catch (e) {
                    console.error('Failed to generate confidence lesson:', e);
                  }
                }}
                title="Generate mini lesson from low-confidence lines"
              >
                Generate Lesson
              </button>
              <button className="conf-help" onClick={() => setShowConfHelp(true)} title="What does confidence mean?">?</button>
            </div>
          </div>

          {showTree && (
            <div className="conf-tree-box">
              {treeViewMode === "nodes" ? (
                <ConfidenceTree
                  nodes={treeNodes}
                  title={moveConfidence ? 'Line confidence (played/best)' : 'Position line confidence'}
                  baseline={baselineTarget}
                  viewMode="nodes"
                  onIncreaseConfidence={() => raiseConfidence('line')}
                  isIncreasingConfidence={isRaising}
                />
              ) : (
                <TagConfidenceView
                  nodes={treeNodes}
                  baseline={baselineTarget}
                />
              )}
            </div>
          )}

          
        </div>
      )}

      {showConfHelp && (
        <div className="modal-overlay" onClick={() => setShowConfHelp(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-title">Explainer: Confidence</div>
              <button className="modal-close" onClick={() => setShowConfHelp(false)}>Close</button>
            </div>
            <div className="modal-body">
              <p>
                The confidence score is an estimation of how well the system can understand this position.
                It is divided into two categories:
              </p>
              <p>
                <strong>Position confidence</strong> measures how well the justification data explains Stockfish’s evaluation.
              </p>
              <p>
                <strong>Line confidence</strong> measures how well the system can justify how the position transpires along the principal variation.
                A low Position Confidence suggests the explanations do not properly account for the selected evaluations.
                A low Line Confidence (while not affecting the engine’s accuracy) indicates the presence of confounding or alternate lines with
                non‑obvious refutations; the LLM should call these out to ensure full understanding of the position.
              </p>
            </div>
          </div>
        </div>
      )}

      <div className="message-badges">
        {role === 'assistant' && hasConfidence && (
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <button
              className="confidence-badge"
              onClick={() => setShowConfidence(!showConfidence)}
              aria-expanded={showConfidence}
              title="Show confidence details"
            >
              Confidence = {renderPercent(playedOverallValue)}
            </button>
            {onRunFullAnalysis && (engineData?.fen || engineData?.fen_before) && engineData?.light_mode === true && (
              <button
                className="full-analysis-badge"
                onClick={() => {
                  const fenToAnalyze = engineData?.fen || engineData?.fen_before || currentFEN;
                  if (fenToAnalyze) {
                    onRunFullAnalysis(fenToAnalyze);
                  }
                }}
                title="Run full analysis (includes piece profiles, NNUE, trajectories)"
                style={{
                  padding: '4px 8px',
                  fontSize: '12px',
                  backgroundColor: '#4a5568',
                  color: '#fff',
                  border: '1px solid #718096',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  fontWeight: '500'
                }}
              >
                Run Full Analysis
              </button>
            )}
          </div>
        )}
        
        {role === 'assistant' && hasReviewData && (
          <button
            className="review-table-badge"
            onClick={() => setShowReviewTable(!showReviewTable)}
            aria-expanded={showReviewTable}
            title="Show game review summary table"
          >
            📊 Review Table
          </button>
        )}
      </div>
    </div>
  );
}

