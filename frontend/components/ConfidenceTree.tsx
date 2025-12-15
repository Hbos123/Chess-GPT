"use client";

import { useMemo, useState } from "react";

interface NodeRec {
  id: string;
  parent_id: string | null;
  ply_from_S0?: number;
  ConfidencePercent?: number;
  move_from_parent?: string | null;
  terminal_confidence?: number | null;
  initial_confidence?: number | null;
  transferred_confidence?: number | null;
  preference_number?: number | null;
  insufficient_confidence?: boolean;
  extended_moves?: Record<string, number>;
  fen?: string;
  shape?: "circle" | "triangle" | "square";
  color?: "red" | "green" | "grey";
  role?: string;
  tags?: string[];
  metadata?: Record<string, any>;
}

interface ConfidenceTreeProps {
  nodes: NodeRec[];
  title?: string;
  baseline?: number;
  viewMode?: "nodes" | "tags";
  onIncreaseConfidence?: () => void;
  isIncreasingConfidence?: boolean;
}

const COLOR_MAP: Record<string, string> = {
  red: "#b05555",
  green: "#55aa55",
  grey: "#888888",
};

export default function ConfidenceTree({ 
  nodes = [], 
  title, 
  baseline,
  onIncreaseConfidence,
  isIncreasingConfidence = false
}: ConfidenceTreeProps) {
  const [hoverId, setHoverId] = useState<string | null>(null);

  const { positions, contentWidth, contentHeight, offsetX, offsetY } = useMemo(() => {
    const positions = new Map<string, { x: number; y: number }>();
    const nodeById = new Map(nodes.map((n) => [n.id, n]));

    // New structure: start node, best move, played move, alternatives
    const startNode = nodes.find((n) => n.id === "start");
    const bestMoveNode = nodes.find((n) => n.id === "best-move");
    const playedMoveNode = nodes.find((n) => n.id === "played-move");
    const altNodes = nodes.filter((n) => n.id.startsWith("alt-"));
    
    // For layout, treat start as root, then arrange children
    const pvNodes = [startNode, bestMoveNode, playedMoveNode].filter(Boolean) as NodeRec[];

    const pvY = 200;
    const dx = 90;
    const branchDxPrimary = 70;
    const branchDxSecondary = 55;
    const branchDy = 80;
    const nodeRadius = 12; // Approximate node size for collision detection
    const minDistance = nodeRadius * 2.5; // Minimum distance between nodes

    // Collision detection helper
    const hasCollision = (x: number, y: number, excludeId?: string): boolean => {
      for (const [id, pos] of positions.entries()) {
        if (excludeId && id === excludeId) continue;
        const dx = pos.x - x;
        const dy = pos.y - y;
        const distance = Math.sqrt(dx * dx + dy * dy);
        if (distance < minDistance) {
          return true;
        }
      }
      return false;
    };

    // Find non-overlapping position
    const findNonOverlappingPosition = (
      baseX: number,
      baseY: number,
      excludeId?: string
    ): { x: number; y: number } => {
      if (!hasCollision(baseX, baseY, excludeId)) {
        return { x: baseX, y: baseY };
      }

      // Try spiral search pattern
      const maxAttempts = 20;
      for (let attempt = 1; attempt <= maxAttempts; attempt++) {
        const angle = (attempt * 0.5) * Math.PI;
        const radius = minDistance * attempt * 0.3;
        const testX = baseX + Math.cos(angle) * radius;
        const testY = baseY + Math.sin(angle) * radius;
        
        if (!hasCollision(testX, testY, excludeId)) {
          return { x: testX, y: testY };
        }
      }

      // Fallback: just offset vertically
      return { x: baseX, y: baseY + minDistance * 2 };
    };

    // Position start node
    if (startNode) {
      positions.set(startNode.id, { x: 100, y: pvY });
    }
    
    // Position best move to the right of start
    if (bestMoveNode) {
      positions.set(bestMoveNode.id, { x: 100 + dx, y: pvY });
    }
    
    // Position played move below start (if exists)
    if (playedMoveNode) {
      positions.set(playedMoveNode.id, { x: 100, y: pvY + branchDy });
    }
    
    // Position alternatives around start
    altNodes.forEach((node, idx) => {
      const angle = (idx * 2 * Math.PI) / Math.max(altNodes.length, 1);
      const radius = branchDy * 1.5;
      const x = 100 + Math.cos(angle) * radius;
      const y = pvY + Math.sin(angle) * radius;
      positions.set(node.id, { x, y });
    });

    const branchCountByPv = new Map<string, number>();
    const pending = nodes.filter((n) => !positions.has(n.id));
    const maxIterations = Math.max(2, pending.length * 4);
    let iterations = 0;

    while (iterations < maxIterations) {
      let placedInPass = false;
      for (const node of pending) {
        if (positions.has(node.id)) {
          continue;
        }
        if (!node.parent_id) {
          continue;
        }
        const parentPos = positions.get(node.parent_id);
        if (!parentPos) {
          continue;
        }
        const parentNode = nodeById.get(node.parent_id);
        if (!parentNode) {
          continue;
        }

        // New structure: all children of start are positioned relative to start
        const isParentStart = parentNode.id === "start";
        let candidatePos: { x: number; y: number };
        
        if (isParentStart) {
          // Children of start are already positioned above
          // This handles any additional nodes that might be added later
          const count = branchCountByPv.get(parentNode.id) ?? 0;
          branchCountByPv.set(parentNode.id, count + 1);
          const angle = (count * 2 * Math.PI) / 8; // Space around start
          const radius = branchDy * (1 + count * 0.3);
          candidatePos = {
            x: parentPos.x + Math.cos(angle) * radius,
            y: parentPos.y + Math.sin(angle) * radius,
          };
        } else {
          // For other parents, position to the right
          candidatePos = {
            x: parentPos.x + branchDxSecondary,
            y: parentPos.y,
          };
        }

        // Check for collision and adjust if needed
        const finalPos = findNonOverlappingPosition(candidatePos.x, candidatePos.y);
        positions.set(node.id, finalPos);
        placedInPass = true;
      }
      if (!placedInPass) {
        break;
      }
      iterations += 1;
    }

    if (positions.size === 0) {
      return {
        positions,
        contentWidth: 400,
        contentHeight: 240,
        offsetX: 0,
        offsetY: 0,
      };
    }

    let minX = Infinity;
    let maxX = -Infinity;
    let minY = Infinity;
    let maxY = -Infinity;

    positions.forEach((pos) => {
      minX = Math.min(minX, pos.x);
      maxX = Math.max(maxX, pos.x);
      minY = Math.min(minY, pos.y);
      maxY = Math.max(maxY, pos.y);
    });

    const padding = 100;
    const contentWidth = maxX - minX + padding * 2;
    const contentHeight = maxY - minY + padding * 2;
    const offsetX = -minX + padding;
    const offsetY = -minY + padding;

    return { positions, contentWidth, contentHeight, offsetX, offsetY };
  }, [nodes]);

  const width = Math.max(420, contentWidth);
  const height = Math.max(220, contentHeight);

  const nodeById = useMemo(() => {
    const map = new Map<string, NodeRec>();
    nodes.forEach((n) => map.set(n.id, n));
    return map;
  }, [nodes]);

  const baselineThreshold = baseline ?? 80;

  // Function to calculate color based on current baseline
  const getNodeColor = (node: NodeRec): string => {
    const conf =
      (typeof node.terminal_confidence === "number" && !Number.isNaN(node.terminal_confidence)
        ? node.terminal_confidence
        : undefined) ??
      (typeof node.ConfidencePercent === "number" && !Number.isNaN(node.ConfidencePercent)
        ? node.ConfidencePercent
        : 0);
    // Simple threshold check: green if >= baseline, red otherwise
    return conf >= baselineThreshold ? "green" : "red";
  };

  const startNode = nodes.find((n) => n.id === "start");
  const startConfidence = startNode?.ConfidencePercent ?? 0;

  return (
    <div className="conf-tree-wrapper">
      {title && <div className="conf-tree-title">{title}</div>}
      {onIncreaseConfidence && (
        <div style={{ marginBottom: "10px", textAlign: "center" }}>
          <button
            onClick={() => {
              if (!isIncreasingConfidence) {
                onIncreaseConfidence();
              }
            }}
            disabled={isIncreasingConfidence}
            style={{
              padding: "8px 16px",
              backgroundColor: "#4a5568",
              color: "#fff",
              border: "1px solid #718096",
              borderRadius: "4px",
              cursor: isIncreasingConfidence ? "not-allowed" : "pointer",
              fontSize: "14px",
              fontWeight: "500",
            }}
          >
            {isIncreasingConfidence ? "Increasing Confidence..." : `Increase Confidence (${startConfidence}%)`}
          </button>
        </div>
      )}
      <div className="conf-tree-canvas">
        <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
          <g transform={`translate(${offsetX}, ${offsetY})`}>
            {nodes.map((node) => {
              if (!node.parent_id) {
                return null;
              }
              const parent = nodeById.get(node.parent_id);
              if (!parent) {
                return null;
              }
              const a = positions.get(parent.id);
              const b = positions.get(node.id);
              if (!a || !b) {
                return null;
              }
              const isPvEdge = parent.id === "start" && (node.id === "best-move" || node.id === "played-move");
              return (
                <line
                  key={`edge-${parent.id}-${node.id}`}
                  x1={a.x}
                  y1={a.y}
                  x2={b.x}
                  y2={b.y}
                  stroke={isPvEdge ? "#666" : "#444"}
                  strokeWidth={isPvEdge ? 2 : 1}
                  opacity={isPvEdge ? 0.9 : 0.6}
                />
              );
            })}

            {nodes
              .filter((node) => positions.has(node.id))
              .map((node) => {
                const pos = positions.get(node.id)!;
                const shape = node.shape || "circle";
                // Recalculate color based on current baseline
                const colorKey = getNodeColor(node);
                const fill = COLOR_MAP[colorKey] ?? "#888";
                const confidenceValue =
                  node.terminal_confidence ??
                  node.ConfidencePercent ??
                  (typeof (node as any).confidence === "number" ? (node as any).confidence : 0);
                const moveLabel =
                  node.id === "start"
                    ? "Start"
                    : (node.move_from_parent && node.move_from_parent !== "null"
                        ? node.move_from_parent
                        : "•"
                      ).substring(0, 6);

                return (
                  <g
                    key={`node-${node.id}`}
                    onMouseEnter={() => setHoverId(node.id)}
                    onMouseLeave={() => setHoverId((prev) => (prev === node.id ? null : prev))}
                  >
                    {shape === "triangle" ? (
                      <path
                        d={`M ${pos.x} ${pos.y - 12} L ${pos.x + 11} ${pos.y + 9} L ${pos.x - 11} ${pos.y + 9} Z`}
                        fill={fill}
                        stroke="#2d2d2d"
                        strokeWidth={1}
                      />
                    ) : shape === "square" ? (
                      <rect
                        x={pos.x - 11}
                        y={pos.y - 11}
                        width={22}
                        height={22}
                        fill={fill}
                        stroke="#2d2d2d"
                        strokeWidth={1}
                        rx={3}
                      />
                    ) : (
                      <circle cx={pos.x} cy={pos.y} r={11} fill={fill} stroke="#2d2d2d" strokeWidth={1} />
                    )}

                    <text
                      x={pos.x + 15}
                      y={pos.y + 5}
                      fontSize={moveLabel.length > 4 ? 9 : 11}
                      fill="#d0d0d0"
                      fontWeight="500"
                    >
                      {moveLabel}
                    </text>

                    {hoverId === node.id && (
                      <g>
                        <rect
                          x={pos.x + 20}
                          y={pos.y - 58}
                          width={260}
                          height={
                            (node.initial_confidence != null ? 16 : 0) +
                            (node.preference_number != null ? 16 : 0) +
                            (node.terminal_confidence != null ? 16 : 0) +
                            (node.transferred_confidence != null ? 16 : 0) +
                            (node.insufficient_confidence ? 16 : 0) +
                            60
                          }
                          fill="#0a0a0a"
                          fillOpacity={0.95}
                          stroke="#666"
                          strokeWidth={1.5}
                          rx={6}
                        />
                        <text x={pos.x + 28} y={pos.y - 40} fontSize={11} fill="#e0e0e0">
                          Confidence: {confidenceValue}%
                        </text>
                        {node.initial_confidence != null && (
                          <text x={pos.x + 28} y={pos.y - 24} fontSize={11} fill="#ffaa00">
                            Initial: {node.initial_confidence}%
                          </text>
                        )}
                        {node.preference_number != null && (
                          <text x={pos.x + 28} y={pos.y - (node.initial_confidence != null ? 8 : 24)} fontSize={11} fill="#88ccff">
                            Depth 2 Rank: #{node.preference_number}
                          </text>
                        )}
                        {node.terminal_confidence != null && (
                          <text x={pos.x + 28} y={pos.y - (node.initial_confidence != null ? (node.preference_number != null ? -8 : 8) : (node.preference_number != null ? 8 : 24))} fontSize={11} fill="#aaaaaa">
                            Terminal: {node.terminal_confidence}%
                          </text>
                        )}
                        {node.transferred_confidence != null && (
                          <text x={pos.x + 28} y={pos.y + (node.initial_confidence != null ? (node.preference_number != null ? 8 : 24) : (node.preference_number != null ? 24 : 40))} fontSize={11} fill="#88ff88">
                            Transferred: {node.transferred_confidence}%
                          </text>
                        )}
                        {node.insufficient_confidence && (
                          <text x={pos.x + 28} y={pos.y + (node.transferred_confidence != null ? (node.initial_confidence != null ? (node.preference_number != null ? 24 : 40) : (node.preference_number != null ? 40 : 56)) : (node.preference_number != null ? 24 : 40))} fontSize={11} fill="#ff6666" fontWeight="bold">
                            ⚠ Below baseline
                          </text>
                        )}
                        <text x={pos.x + 28} y={pos.y + (node.transferred_confidence != null ? (node.insufficient_confidence ? 40 : 56) : (node.insufficient_confidence ? 40 : 56))} fontSize={9} fill="#888888">
                          {node.fen ? node.fen.substring(0, 48) + (node.fen.length > 48 ? "…" : "") : ""}
                        </text>
                      </g>
                    )}
                  </g>
                );
              })}
          </g>
        </svg>
      </div>
    </div>
  );
}


