import { useEffect, useMemo, useState } from 'react';
import { stripEmojis } from '@/utils/emojiFilter';
import Board from '@/components/Board';
import ConfidenceTree from './ConfidenceTree';
import TagConfidenceView from './TagConfidenceView';
import LoadingMessage from './LoadingMessage';
import InteractivePGN from './InteractivePGN';
import GameReviewTable from './GameReviewTable';
import PersonalReviewCharts from './PersonalReviewCharts';
import ExpandableTable from './ExpandableTable';
import { getBackendBase } from '@/lib/backendBase';

interface ShowBoardLaunchPayload {
  finalPgn?: string;
  fen?: string;
  showBoardLink?: string;
}

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
  tableTitle?: string;
  tableContent?: string;
  onButtonAction?: (action: string) => void;
  isButtonDisabled?: boolean;
  onRunFullAnalysis?: (fen: string) => void;
  onShowBoard?: (payload: ShowBoardLaunchPayload) => void;
}

export default function MessageBubble({ role, content, rawData, timestamp, currentFEN, onApplyPGN, onPreviewFEN, buttonAction, buttonLabel, tableTitle, tableContent, onButtonAction, isButtonDisabled, onRunFullAnalysis, onShowBoard }: MessageBubbleProps) {
  const [showRawData, setShowRawData] = useState(false);
  const [showEvidence, setShowEvidence] = useState(false);
  const [showLogs, setShowLogs] = useState(false);
  const [prevLogs, setPrevLogs] = useState<string[]>([]);

  const backendBase = getBackendBase();
  const [liveLogs, setLiveLogs] = useState<string[]>([]);
  const [logStream, setLogStream] = useState<EventSource | null>(null);
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
  const [baselineTab, setBaselineTab] = useState<"root" | "after_best">("root");

  const DEFAULT_BASELINE = 80;

  // Initialize miniFen when miniBoard data is available
  useEffect(() => {
    if (rawData?.miniBoard?.fen) {
      setMiniFen(rawData.miniBoard.fen);
    }
  }, [rawData?.miniBoard?.fen]);

  // backendBase already resolved above via getBackendBase() (LAN-safe).
  const engineData = (rawData?.rawEngineData ?? rawData) || {};
  const moveConfidence = localMoveConfidence || engineData?.confidence;
  const positionConfidence = localPositionConfidence || engineData?.position_confidence || rawData?.position_confidence;
  const baselineIntuition = rawData?.baselineIntuition;

  // Fetch previous logs when panel opens
  useEffect(() => {
    if (showLogs && prevLogs.length === 0) {
      fetch(`${backendBase}/debug/backend_log_tail?lines=80`)
        .then(res => res.json())
        .then(data => {
          if (data.lines) {
            setPrevLogs(data.lines);
          }
        })
        .catch(err => {
          setPrevLogs([`[Error fetching logs: ${err.message}]`]);
        });
    }
  }, [showLogs, backendBase]);

  // Start/stop live log stream
  useEffect(() => {
    if (!showLogs) {
      if (logStream) {
        logStream.close();
        setLogStream(null);
      }
      setLiveLogs([]);
      return;
    }

    const es = new EventSource(`${backendBase}/debug/backend_log_stream`);
    es.addEventListener('log', (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data);
        if (data.line) {
          setLiveLogs(prev => {
            const updated = [...prev, data.line];
            return updated.slice(-80); // Keep last 80 lines
          });
        }
      } catch (err) {
        console.warn('Failed to parse log event:', err);
      }
    });

    es.addEventListener('error', () => {
      es.close();
    });

    setLogStream(es);

    return () => {
      es.close();
    };
  }, [showLogs, backendBase]);


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
      const isDisabled = isButtonDisabled || rawData?.disabled;
      const handleClick = () => {
        if (isDisabled) return;
        if (onButtonAction) {
          onButtonAction(buttonAction, rawData?.buttonId);
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
        <div className="message-bubble message-button" style={{ background: 'transparent', border: 'none', padding: 0 }}>
          <button 
            className="inline-button" 
            onClick={handleClick}
            disabled={isDisabled}
            style={{ 
              opacity: isDisabled ? 0.4 : 1, 
              cursor: isDisabled ? 'not-allowed' : 'pointer',
              backgroundColor: isDisabled ? 'rgba(255, 255, 255, 0.02)' : undefined
            }}
          >
            {label}
          </button>
        </div>
      );
    }

    if (role === 'expandable_table') {
      const title = tableTitle || (rawData?.tableTitle as string) || (content?.trim() || 'Details');
      const body = tableContent || (rawData?.tableContent as string) || '';
      return (
        <div className="message-bubble message-expandable" style={{ background: 'transparent', border: 'none', padding: 0 }}>
          <ExpandableTable title={String(title)} content={String(body)} defaultOpen={false} />
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
          <div className="message-header-actions">
            {/* Evidence toggle (per-claim, evidence-locked) */}
            <button
              className="raw-data-toggle"
              onClick={() => setShowEvidence(!showEvidence)}
              title="View evidence attached to each claim"
            >
              Evidence
            </button>

            <button 
              className="raw-data-toggle"
              onClick={() => setShowLogs(!showLogs)}
              title="View backend logs (previous + live)"
            >
              Logs
            </button>

            <button 
              className="raw-data-toggle"
              onClick={() => setShowRawData(!showRawData)}
              title="View raw analysis data"
            >
              Raw Data
            </button>

            {/* NEW: Show Board button when investigation lines are available */}
            {(() => {
              const rawMeta = rawData as any;
              const showBoardLink = rawMeta?.show_board_link;
              const finalPgn = rawMeta?.final_pgn;
              if (!showBoardLink && !finalPgn) return null;
              
              const handleShowBoard = () => {
                if (onShowBoard) {
                  const fallbackFen = rawMeta?.fen || rawMeta?.boardContext?.fen || currentFEN;
                  onShowBoard({
                    finalPgn,
                    fen: fallbackFen || undefined,
                    showBoardLink,
                  });
                  return;
                }
                
                if (showBoardLink) {
                  window.open(showBoardLink, '_blank');
                }
              };
              
              return (
                <button
                  className="raw-data-toggle"
                  onClick={handleShowBoard}
                  title="Add board tab with all investigated lines"
                >
                  Show Board
                </button>
              );
            })()}
          </div>
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

        {role === "assistant" && baselineIntuition && (
          <div style={{ marginTop: 12, padding: 10, border: "1px solid rgba(255,255,255,0.12)", borderRadius: 8 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8, marginBottom: 8 }}>
              <div style={{ fontWeight: 700 }}>Baseline D2/D16 Intuition</div>
              <div style={{ display: "flex", gap: 8 }}>
                <button
                  type="button"
                  className="raw-data-toggle"
                  onClick={() => setBaselineTab("root")}
                  style={{ opacity: baselineTab === "root" ? 1 : 0.7 }}
                >
                  Scan A (root)
                </button>
                {(() => {
                  const bi = baselineIntuition || {};
                  const hasScanB = Boolean(bi.scan_after_best && !bi.scan_after_best?.error);
                  if (!hasScanB) return null;
                  return (
                    <button
                      type="button"
                      className="raw-data-toggle"
                      onClick={() => setBaselineTab("after_best")}
                      style={{ opacity: baselineTab === "after_best" ? 1 : 0.7 }}
                    >
                      Scan B (after best)
                    </button>
                  );
                })()}
              </div>
            </div>

            {(() => {
              const bi = baselineIntuition || {};
              const scan = baselineTab === "after_best" && bi.scan_after_best ? bi.scan_after_best : bi.scan_root;
              const root = scan?.root || {};
              const pgn = scan?.pgn_exploration || "";
              const motifs = Array.isArray(scan?.motifs) ? scan.motifs : [];
              const claims = Array.isArray(scan?.claims) ? scan.claims : [];
              return (
                <div>
                  <div style={{ fontSize: 13, opacity: 0.9, marginBottom: 8 }}>
                    D16 eval: {String(root.eval_d16)} | D2 eval: {String(root.eval_d2)} | Best D16:{" "}
                    {String(root.best_move_d16_san)}
                  </div>
                  <details open>
                    <summary style={{ cursor: "pointer", fontWeight: 600 }}>PGN (verbose)</summary>
                    <pre style={{ whiteSpace: "pre-wrap", marginTop: 8, maxHeight: 260, overflow: "auto" }}>{String(pgn || "")}</pre>
                  </details>
                  <details>
                    <summary style={{ cursor: "pointer", fontWeight: 600 }}>Claims</summary>
                    <pre style={{ whiteSpace: "pre-wrap", marginTop: 8, maxHeight: 200, overflow: "auto" }}>
                      {JSON.stringify(claims.slice(0, 12), null, 2)}
                    </pre>
                  </details>
                  <details>
                    <summary style={{ cursor: "pointer", fontWeight: 600 }}>Motifs</summary>
                    <pre style={{ whiteSpace: "pre-wrap", marginTop: 8, maxHeight: 200, overflow: "auto" }}>
                      {JSON.stringify(motifs.slice(0, 25), null, 2)}
                    </pre>
                  </details>
                </div>
              );
            })()}
          </div>
        )}
      </div>
      
      {showLogs && role === 'assistant' && (
        <div className="logs-panel">
          <div className="logs-header">
            <span>Backend Logs</span>
            <button onClick={() => setShowLogs(false)} className="copy-button">
              Close
            </button>
          </div>
          
          <div className="logs-content">
            <div className="logs-section">
              <div className="logs-section-title">Previous (last 80 lines)</div>
              <pre className="logs-previous">
                {prevLogs.length > 0 ? prevLogs.join('\n') : 'Loading...'}
              </pre>
            </div>
            
            <div className="logs-section">
              <div className="logs-section-title">Live (upcoming)</div>
              <pre className="logs-live">
                {liveLogs.length > 0 ? liveLogs.join('\n') : 'Waiting for new logs...'}
              </pre>
            </div>
          </div>
        </div>
      )}

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

      {showEvidence && role === 'assistant' && rawData && (
        <div className="evidence-panel">
          <div className="evidence-header">
            <span>Evidence (by clause)</span>
            <button onClick={() => setShowEvidence(false)} className="copy-button">
              Close
            </button>
          </div>
          {(() => {
            const narrativeDecision = (rawData as any)?.narrativeDecision || (rawData as any)?.narrative_decision || null;
            const claims: any[] = Array.isArray(narrativeDecision?.claims) ? narrativeDecision.claims : [];
            const patternClaims: any[] = Array.isArray(narrativeDecision?.pattern_claims)
              ? narrativeDecision.pattern_claims
              : (Array.isArray(narrativeDecision?.patternClaims) ? narrativeDecision.patternClaims : []);
            const patternSummary: string | null =
              typeof narrativeDecision?.pattern_summary === 'string'
                ? narrativeDecision.pattern_summary
                : (typeof narrativeDecision?.patternSummary === 'string' ? narrativeDecision.patternSummary : null);
            // Motifs/patterns live under baseline_intuition; surface them here as well
            // so "Evidence" includes both clause-locked claims + recurring motifs.
            const bi = (rawData as any)?.baseline_intuition || (rawData as any)?.baselineIntuition || null;
            const scanRoot = bi?.scan_root || bi?.scanRoot || bi?.scan_root_result || null;
            const motifs: any[] = Array.isArray(scanRoot?.motifs) ? scanRoot.motifs : [];

            return (
              <div className="evidence-claims">
                {patternSummary && (
                  <div className="evidence-motifs" style={{ marginBottom: 12 }}>
                    <div className="evidence-row">
                      <div className="evidence-label">Pattern summary</div>
                      <div className="evidence-value">
                        <pre className="evidence-json">{patternSummary}</pre>
                      </div>
                    </div>
                  </div>
                )}
                {motifs.length > 0 && (
                  <div className="evidence-motifs" style={{ marginBottom: 12 }}>
                    <div className="evidence-row">
                      <div className="evidence-label">Patterns (motifs)</div>
                      <div className="evidence-value">
                        {(motifs.slice(0, 10) as any[]).map((m, i) => {
                          const sig = m?.pattern?.signature || m?.signature || "";
                          const count = m?.location?.count_total ?? m?.count_total ?? null;
                          const cls = m?.classification || m?.class || null;
                          return (
                            <div key={`motif-${i}`} className="evidence-tag-row">
                              <span className="evidence-tags mono">
                                {sig || "(motif)"}{count !== null ? `  (count=${count})` : ""}{cls ? `  [${cls}]` : ""}
                              </span>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  </div>
                )}

                {!claims.length && (
                  <div className="evidence-empty">No evidence-locked claims available for this message.</div>
                )}
                {patternClaims.length > 0 && (
                  <div className="evidence-motifs" style={{ marginBottom: 12 }}>
                    <div className="evidence-row">
                      <div className="evidence-label">Patterns (claim format)</div>
                      <div className="evidence-value">
                        {patternClaims.slice(0, 10).map((pc: any, i: number) => {
                          const payload = pc?.evidence_payload || pc?.evidencePayload || {};
                          const evidenceMoves = Array.isArray(pc?.evidence_moves) ? pc.evidence_moves : [];
                          const pgnMoves = Array.isArray(payload?.pgn_moves) ? payload.pgn_moves : [];
                          const pgnLine = typeof payload?.pgn_line === 'string' ? payload.pgn_line : null;
                          const tagsGainedNet = Array.isArray(payload?.tags_gained_net) ? payload.tags_gained_net : [];
                          const tagsLostNet = Array.isArray(payload?.tags_lost_net) ? payload.tags_lost_net : [];
                          const rolesGainedNet = Array.isArray(payload?.roles_gained_net) ? payload.roles_gained_net : [];
                          const rolesLostNet = Array.isArray(payload?.roles_lost_net) ? payload.roles_lost_net : [];
                          const toNum = (v: any): number | null => {
                            if (typeof v === 'number' && Number.isFinite(v)) return v;
                            if (typeof v === 'string') {
                              const n = Number(v);
                              if (Number.isFinite(n)) return n;
                            }
                            return null;
                          };
                          const evidenceEvalStart = toNum(payload?.evidence_eval_start);
                          const evidenceEvalEnd = toNum(payload?.evidence_eval_end);
                          const evidenceEvalDelta = toNum(payload?.evidence_eval_delta);
                          const evidenceMaterialStart = toNum(payload?.evidence_material_start);
                          const evidenceMaterialEnd = toNum(payload?.evidence_material_end);
                          const evidencePositionalStart = toNum(payload?.evidence_positional_start);
                          const evidencePositionalEnd = toNum(payload?.evidence_positional_end);
                          const keyEvalBreakdown = payload?.key_eval_breakdown && typeof payload.key_eval_breakdown === 'object' ? payload.key_eval_breakdown : null;
                          const displayMoves = (pgnMoves.length > 0 ? pgnMoves : evidenceMoves);
                          const fmt = (n: number) => `${n >= 0 ? '+' : ''}${n.toFixed(2)}`;
                          
                          return (
                            <details key={`pattern-claim-${i}`} className="evidence-clause">
                              <summary className="evidence-summary">
                                <span className="evidence-title">Pattern {i + 1}</span>
                                <span className="evidence-badge evidence-badge-pattern">pattern</span>
                                <span className="evidence-priority">P2</span>
                              </summary>
                              <div className="evidence-body">
                                {typeof pc?.summary === 'string' && pc.summary && (
                                  <div className="evidence-row">
                                    <div className="evidence-label">Summary</div>
                                    <div className="evidence-value">{pc.summary}</div>
                                  </div>
                                )}
                                {displayMoves.length > 0 && (
                                  <div className="evidence-row">
                                    <div className="evidence-label">Evidence moves</div>
                                    <div className="evidence-value mono">{displayMoves.join(' ')}</div>
                                  </div>
                                )}
                                {pgnLine && (
                                  <div className="evidence-row">
                                    <div className="evidence-label">PGN line</div>
                                    <div className="evidence-value mono">{pgnLine}</div>
                                  </div>
                                )}
                                {(evidenceEvalStart !== null || evidenceEvalEnd !== null || evidenceEvalDelta !== null || evidenceMaterialStart !== null || evidenceMaterialEnd !== null || evidencePositionalStart !== null || evidencePositionalEnd !== null) && (
                                  <div className="evidence-row">
                                    <div className="evidence-label">Eval (evidence line)</div>
                                    <div className="evidence-value">
                                      <div className="evidence-tag-row">
                                        <span className="evidence-tag-label">Start → End:</span>
                                        <span className="evidence-tags mono">
                                          {evidenceEvalStart !== null ? fmt(evidenceEvalStart) : 'n/a'} → {evidenceEvalEnd !== null ? fmt(evidenceEvalEnd) : 'n/a'}
                                          {evidenceEvalDelta !== null ? ` (Δ ${fmt(evidenceEvalDelta)})` : ''}
                                        </span>
                                      </div>
                                      {(evidenceMaterialStart !== null || evidencePositionalStart !== null || evidenceMaterialEnd !== null || evidencePositionalEnd !== null) && (
                                        <div className="evidence-tag-row">
                                          <span className="evidence-tag-label">Decomp:</span>
                                          <span className="evidence-tags mono">
                                            start mat {evidenceMaterialStart !== null ? fmt(evidenceMaterialStart) : 'n/a'} + pos {evidencePositionalStart !== null ? fmt(evidencePositionalStart) : 'n/a'}; end mat {evidenceMaterialEnd !== null ? fmt(evidenceMaterialEnd) : 'n/a'} + pos {evidencePositionalEnd !== null ? fmt(evidencePositionalEnd) : 'n/a'}
                                          </span>
                                        </div>
                                      )}
                                    </div>
                                  </div>
                                )}
                                {(tagsGainedNet.length > 0 || tagsLostNet.length > 0 || rolesGainedNet.length > 0 || rolesLostNet.length > 0) && (
                                  <div className="evidence-row">
                                    <div className="evidence-label">Tags</div>
                                    <div className="evidence-value">
                                      {tagsGainedNet.length > 0 && (
                                        <div className="evidence-tag-row">
                                          <span className="evidence-tag-label">Tags gained:</span>
                                          <span className="evidence-tags">{tagsGainedNet.join(', ')}</span>
                                        </div>
                                      )}
                                      {tagsLostNet.length > 0 && (
                                        <div className="evidence-tag-row">
                                          <span className="evidence-tag-label">Tags lost:</span>
                                          <span className="evidence-tags">{tagsLostNet.join(', ')}</span>
                                        </div>
                                      )}
                                      {rolesGainedNet.length > 0 && (
                                        <div className="evidence-tag-row">
                                          <span className="evidence-tag-label">Roles gained:</span>
                                          <span className="evidence-tags">{rolesGainedNet.join(', ')}</span>
                                        </div>
                                      )}
                                      {rolesLostNet.length > 0 && (
                                        <div className="evidence-tag-row">
                                          <span className="evidence-tag-label">Roles lost:</span>
                                          <span className="evidence-tags">{rolesLostNet.join(', ')}</span>
                                        </div>
                                      )}
                                    </div>
                                  </div>
                                )}
                              </div>
                            </details>
                          );
                        })}
                      </div>
                    </div>
                  </div>
                )}
                {claims.map((c, idx) => {
                  const hints = c?.hints || {};
                  const payload = c?.evidence_payload || c?.evidencePayload || {};
                  const roleLabel = hints?.role || 'detail';
                  const priority = hints?.priority ?? 2;
                  const connector = c?.connector || null;
                  const source = c?.evidence_source || null;
                  const evidenceMoves = Array.isArray(c?.evidence_moves) ? c.evidence_moves : [];

                  const themeTags = Array.isArray(payload?.theme_tags) ? payload.theme_tags : [];
                  const rawTags = Array.isArray(payload?.raw_tags) ? payload.raw_tags : [];
                  const pgnLine = typeof payload?.pgn_line === 'string' ? payload.pgn_line : null;
                  const pgnMoves = Array.isArray(payload?.pgn_moves) ? payload.pgn_moves : [];
                  const twoMove = payload?.two_move && typeof payload.two_move === 'object' ? payload.two_move : null;
                  const tagsGainedNet = Array.isArray(payload?.tags_gained_net) ? payload.tags_gained_net : [];
                  const tagsLostNet = Array.isArray(payload?.tags_lost_net) ? payload.tags_lost_net : [];
                  const rolesGainedNet = Array.isArray(payload?.roles_gained_net) ? payload.roles_gained_net : [];  // NEW
                  const rolesLostNet = Array.isArray(payload?.roles_lost_net) ? payload.roles_lost_net : [];  // NEW
                  const materialChangeNet = typeof payload?.material_change_net === 'number' ? payload.material_change_net : null;
                  const toNum = (v: any): number | null => {
                    if (typeof v === 'number' && Number.isFinite(v)) return v;
                    if (typeof v === 'string') {
                      const n = Number(v);
                      if (Number.isFinite(n)) return n;
                    }
                    return null;
                  };
                  const evidenceEvalStart = toNum(payload?.evidence_eval_start);
                  const evidenceEvalEnd = toNum(payload?.evidence_eval_end);
                  const evidenceEvalDelta = toNum(payload?.evidence_eval_delta);
                  const evidenceMaterialStart = toNum(payload?.evidence_material_start);
                  const evidenceMaterialEnd = toNum(payload?.evidence_material_end);
                  const evidencePositionalStart = toNum(payload?.evidence_positional_start);
                  const evidencePositionalEnd = toNum(payload?.evidence_positional_end);
                  const keyEvalBreakdown = payload?.key_eval_breakdown && typeof payload.key_eval_breakdown === 'object' ? payload.key_eval_breakdown : null;

                  const displayMoves = (pgnMoves.length > 0 ? pgnMoves : evidenceMoves);
                  const fmt = (n: number) => `${n >= 0 ? '+' : ''}${n.toFixed(2)}`;

                  return (
                    <details key={`${idx}-${c?.summary || ''}`} className="evidence-clause">
                      <summary className="evidence-summary">
                        <span className="evidence-title">Claim {idx + 1}</span>
                        <span className={`evidence-badge evidence-badge-${roleLabel}`}>{roleLabel}</span>
                        <span className="evidence-priority">P{priority}</span>
                      </summary>

                      <div className="evidence-body">
                        {typeof c?.summary === 'string' && c.summary && (
                          <div className="evidence-row">
                            <div className="evidence-label">Summary</div>
                            <div className="evidence-value">{c.summary}</div>
                          </div>
                        )}

                        {connector && (
                          <div className="evidence-row">
                            <div className="evidence-label">Connector</div>
                            <div className="evidence-value">{String(connector)}</div>
                          </div>
                        )}

                        {source && (
                          <div className="evidence-row">
                            <div className="evidence-label">Evidence source</div>
                            <div className="evidence-value">{String(source)}</div>
                          </div>
                        )}

                        {displayMoves.length > 0 && (
                          <div className="evidence-row">
                            <div className="evidence-label">Evidence moves</div>
                            <div className="evidence-value mono">{displayMoves.join(' ')}</div>
                          </div>
                        )}

                        {pgnLine && (
                          <div className="evidence-row">
                            <div className="evidence-label">PGN line</div>
                            <div className="evidence-value mono">{pgnLine}</div>
                          </div>
                        )}

                        {(evidenceEvalStart !== null || evidenceEvalEnd !== null || evidenceEvalDelta !== null || evidenceMaterialStart !== null || evidenceMaterialEnd !== null || evidencePositionalStart !== null || evidencePositionalEnd !== null) && (
                          <div className="evidence-row">
                            <div className="evidence-label">Eval (evidence line)</div>
                            <div className="evidence-value">
                              <div className="evidence-tag-row">
                                <span className="evidence-tag-label">Start → End:</span>
                                <span className="evidence-tags mono">
                                  {evidenceEvalStart !== null ? fmt(evidenceEvalStart) : 'n/a'} → {evidenceEvalEnd !== null ? fmt(evidenceEvalEnd) : 'n/a'}
                                  {evidenceEvalDelta !== null ? ` (Δ ${fmt(evidenceEvalDelta)})` : ''}
                                </span>
                              </div>
                              {(evidenceMaterialStart !== null || evidencePositionalStart !== null || evidenceMaterialEnd !== null || evidencePositionalEnd !== null) && (
                                <div className="evidence-tag-row">
                                  <span className="evidence-tag-label">Decomp:</span>
                                  <span className="evidence-tags mono">
                                    start mat {evidenceMaterialStart !== null ? fmt(evidenceMaterialStart) : 'n/a'} + pos {evidencePositionalStart !== null ? fmt(evidencePositionalStart) : 'n/a'}; end mat {evidenceMaterialEnd !== null ? fmt(evidenceMaterialEnd) : 'n/a'} + pos {evidencePositionalEnd !== null ? fmt(evidencePositionalEnd) : 'n/a'}
                                  </span>
                                </div>
                              )}
                            </div>
                          </div>
                        )}

                        {(themeTags.length > 0 || rawTags.length > 0) && (
                          <div className="evidence-row">
                            <div className="evidence-label">Tags</div>
                            <div className="evidence-value">
                              {themeTags.length > 0 && (
                                <div className="evidence-tag-row">
                                  <span className="evidence-tag-label">Themes:</span>
                                  <span className="evidence-tags">{themeTags.join(', ')}</span>
                                </div>
                              )}
                              {rawTags.length > 0 && (
                                <div className="evidence-tag-row">
                                  <span className="evidence-tag-label">Raw tags:</span>
                                  <span className="evidence-tags">{rawTags.join(', ')}</span>
                                </div>
                              )}
                            </div>
                          </div>
                        )}

                        {twoMove && (
                          <div className="evidence-row">
                            <div className="evidence-label">Two-move snippet</div>
                            <div className="evidence-value">
                              <pre className="evidence-json">{JSON.stringify(twoMove, null, 2)}</pre>
                            </div>
                          </div>
                        )}

                        {/* NEW: Eval Breakdown (fundamentally informs the claim) */}
                        {keyEvalBreakdown && (
                          <div className="evidence-row">
                            <div className="evidence-label">Eval breakdown (key evidence)</div>
                            <div className="evidence-value">
                              {keyEvalBreakdown.material_balance_before !== null && keyEvalBreakdown.material_balance_before !== undefined && 
                               keyEvalBreakdown.material_balance_after !== null && keyEvalBreakdown.material_balance_after !== undefined && (
                                <div className="evidence-tag-row">
                                  <span className="evidence-tag-label">Material balance:</span>
                                  <span className="evidence-tags mono" style={{ fontWeight: 'bold' }}>
                                    {fmt(keyEvalBreakdown.material_balance_before)} → {fmt(keyEvalBreakdown.material_balance_after)}
                                    {keyEvalBreakdown.material_balance_delta !== null && keyEvalBreakdown.material_balance_delta !== undefined 
                                      ? ` (Δ ${fmt(keyEvalBreakdown.material_balance_delta)})` 
                                      : ''}
                                  </span>
                                </div>
                              )}
                              {keyEvalBreakdown.positional_balance_before !== null && keyEvalBreakdown.positional_balance_before !== undefined && 
                               keyEvalBreakdown.positional_balance_after !== null && keyEvalBreakdown.positional_balance_after !== undefined && (
                                <div className="evidence-tag-row">
                                  <span className="evidence-tag-label">Positional balance:</span>
                                  <span className="evidence-tags mono" style={{ fontWeight: 'bold' }}>
                                    {fmt(keyEvalBreakdown.positional_balance_before)} → {fmt(keyEvalBreakdown.positional_balance_after)}
                                    {keyEvalBreakdown.positional_balance_delta !== null && keyEvalBreakdown.positional_balance_delta !== undefined 
                                      ? ` (Δ ${fmt(keyEvalBreakdown.positional_balance_delta)})` 
                                      : ''}
                                  </span>
                                </div>
                              )}
                              {keyEvalBreakdown.eval_before !== null && keyEvalBreakdown.eval_after !== null && (
                                <div className="evidence-tag-row">
                                  <span className="evidence-tag-label">Total eval:</span>
                                  <span className="evidence-tags mono">
                                    {fmt(keyEvalBreakdown.eval_before)} → {fmt(keyEvalBreakdown.eval_after)}
                                    {keyEvalBreakdown.eval_delta !== null && keyEvalBreakdown.eval_delta !== undefined 
                                      ? ` (Δ ${fmt(keyEvalBreakdown.eval_delta)})` 
                                      : ''}
                                  </span>
                                </div>
                              )}
                            </div>
                          </div>
                        )}

                        {(tagsGainedNet.length > 0 || tagsLostNet.length > 0 || rolesGainedNet.length > 0 || rolesLostNet.length > 0 || materialChangeNet !== null) && (
                          <div className="evidence-row">
                            <div className="evidence-label">Net changes (sequence)</div>
                            <div className="evidence-value">
                              {tagsGainedNet.length > 0 && (
                                <div className="evidence-tag-row">
                                  <span className="evidence-tag-label">Tags gained:</span>
                                  <span className="evidence-tags">{tagsGainedNet.join(', ')}</span>
                                </div>
                              )}
                              {tagsLostNet.length > 0 && (
                                <div className="evidence-tag-row">
                                  <span className="evidence-tag-label">Tags lost:</span>
                                  <span className="evidence-tags">{tagsLostNet.join(', ')}</span>
                                </div>
                              )}
                              {rolesGainedNet.length > 0 && (
                                <div className="evidence-tag-row">
                                  <span className="evidence-tag-label">Roles gained:</span>
                                  <span className="evidence-tags">{rolesGainedNet.join(', ')}</span>
                                </div>
                              )}
                              {rolesLostNet.length > 0 && (
                                <div className="evidence-tag-row">
                                  <span className="evidence-tag-label">Roles lost:</span>
                                  <span className="evidence-tags">{rolesLostNet.join(', ')}</span>
                                </div>
                              )}
                              {materialChangeNet !== null && (
                                <div className="evidence-tag-row">
                                  <span className="evidence-tag-label">Material change:</span>
                                  <span className="evidence-tags">
                                    {materialChangeNet > 0 ? '+' : ''}{materialChangeNet.toFixed(2)} pawns
                                    {materialChangeNet > 0 ? ' (better for White)' : materialChangeNet < 0 ? ' (better for Black)' : ''}
                                  </span>
                                </div>
                              )}
                            </div>
                          </div>
                        )}
                      </div>
                    </details>
                  );
                })}
              </div>
            );
          })()}
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

