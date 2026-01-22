import { useMemo } from 'react';

interface TagInstance {
  tag_name: string;
  ply: number;
  node_id: string;
  squares: string[];
  confidence: number;
  branch_path: string[];
  aggressors?: string[];
  victims?: string[];
  side?: string;
}

interface Node {
  id: string;
  role: string;
  ply_index: number;
  ConfidencePercent?: number;
  frozen_confidence?: number;
  metadata?: {
    tags?: Array<{
      tag_name: string;
      squares?: string[];
      aggressors?: string[];
      victims?: string[];
      side?: string;
    }>;
  };
  parent_id?: string;
}

interface TagConfidenceViewProps {
  nodes: Node[];
  baseline: number;
}

export default function TagConfidenceView({ nodes, baseline }: TagConfidenceViewProps) {
  // Group tags by type
  const tagGroups = useMemo(() => {
    const groups: Record<string, TagInstance[]> = {};
    
    // Build node lookup
    const nodeById = new Map(nodes.map(n => [n.id, n]));
    
    // Extract all tag instances
    for (const node of nodes) {
      const tags = node.metadata?.tags || [];
      const confidence = node.frozen_confidence ?? node.ConfidencePercent ?? 0;
      
      // Build branch path
      const branchPath: string[] = [];
      let current: Node | undefined = node;
      while (current && current.parent_id) {
        branchPath.unshift(current.id);
        current = nodeById.get(current.parent_id);
        if (current?.role === 'pv' || current?.id.startsWith('pv-')) {
          break;
        }
      }
      
      for (const tag of tags) {
        const tagName = tag.tag_name;
        if (!tagName) continue;
        
        if (!groups[tagName]) {
          groups[tagName] = [];
        }
        
        groups[tagName].push({
          tag_name: tagName,
          ply: node.ply_index,
          node_id: node.id,
          squares: tag.squares || [],
          confidence,
          branch_path: branchPath,
          aggressors: tag.aggressors,
          victims: tag.victims,
          side: tag.side
        });
      }
    }
    
    // Sort tags by frequency and relevance
    return Object.entries(groups).sort((a, b) => b[1].length - a[1].length);
  }, [nodes]);
  
  // Get PV nodes for main line
  const pvNodes = useMemo(() => {
    return nodes
      .filter(n => n.role === 'pv' || n.id.startsWith('pv-'))
      .sort((a, b) => a.ply_index - b.ply_index);
  }, [nodes]);
  
  // Calculate tag confidence changes
  const tagConfidenceMap = useMemo(() => {
    const map: Record<string, { ply: number; confidence: number }[]> = {};
    
    for (const [tagName, instances] of tagGroups) {
      map[tagName] = instances.map(i => ({
        ply: i.ply,
        confidence: i.confidence
      })).sort((a, b) => a.ply - b.ply);
    }
    
    return map;
  }, [tagGroups]);
  
  return (
    <div className="tag-confidence-view">
      <div className="tag-view-header">
        <h3>Tag Confidence Analysis</h3>
        <p>PV line with tag-based branches showing confidence changes</p>
      </div>
      
      {/* PV Main Line */}
      <div className="pv-main-line">
        <div className="pv-line-label">Principal Variation</div>
        <div className="pv-nodes-container">
          {pvNodes.map((node, idx) => {
            const conf = node.frozen_confidence ?? node.ConfidencePercent ?? 0;
            const isGreen = conf >= baseline;
            return (
              <div
                key={node.id}
                className={`pv-node ${isGreen ? 'green' : 'red'}`}
                style={{ left: `${idx * 80}px` }}
              >
                <div className="pv-node-label">Ply {node.ply_index}</div>
                <div className="pv-node-confidence">{Math.round(conf)}%</div>
              </div>
            );
          })}
        </div>
      </div>
      
      {/* Tag Branches */}
      <div className="tag-branches">
        {tagGroups.slice(0, 10).map(([tagName, instances]) => {
          const confMap = tagConfidenceMap[tagName];
          if (!confMap || confMap.length === 0) return null;
          
          // Calculate confidence trend
          const firstConf = confMap[0].confidence;
          const lastConf = confMap[confMap.length - 1].confidence;
          const trend = lastConf - firstConf;
          const trendColor = trend > 10 ? 'green' : trend < -10 ? 'red' : 'gray';
          
          // Group by branch path
          const branchGroups = new Map<string, TagInstance[]>();
          for (const instance of instances) {
            const branchKey = instance.branch_path.join('-') || 'pv';
            if (!branchGroups.has(branchKey)) {
              branchGroups.set(branchKey, []);
            }
            branchGroups.get(branchKey)!.push(instance);
          }
          
          return (
            <div key={tagName} className="tag-branch-group">
              <div className="tag-branch-header">
                <span className="tag-name">{tagName}</span>
                <span className={`tag-trend ${trendColor}`}>
                  {trend > 0 ? '↑' : trend < 0 ? '↓' : '→'} {Math.abs(trend).toFixed(0)}%
                </span>
              </div>
              
              <div className="tag-branch-instances">
                {Array.from(branchGroups.entries()).map(([branchKey, branchInstances]) => {
                  const avgConf = branchInstances.reduce((sum, i) => sum + i.confidence, 0) / branchInstances.length;
                  const isHighConf = avgConf >= baseline;
                  
                  return (
                    <div
                      key={branchKey}
                      className={`tag-branch ${isHighConf ? 'high-conf' : 'low-conf'}`}
                      title={`${branchInstances.length} instance(s), avg confidence: ${Math.round(avgConf)}%`}
                    >
                      <div className="tag-branch-info">
                        <span className="tag-branch-label">
                          {branchKey === 'pv' ? 'PV' : `Branch ${branchKey.slice(0, 8)}`}
                        </span>
                        <span className="tag-branch-confidence">{Math.round(avgConf)}%</span>
                      </div>
                      {branchInstances.length > 0 && (
                        <div className="tag-branch-squares">
                          Squares: {branchInstances[0].squares.slice(0, 3).join(', ')}
                          {branchInstances[0].squares.length > 3 && '...'}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
      
      {/* Tag Summary */}
      <div className="tag-summary">
        <h4>Tag Summary</h4>
        <div className="tag-summary-stats">
          <div>Total Tags: {tagGroups.length}</div>
          <div>PV Nodes: {pvNodes.length}</div>
          <div>Baseline: {baseline}%</div>
        </div>
      </div>
    </div>
  );
}

