"""
Tag analysis system for confidence trees.
Tracks tag instances across branches and analyzes their relevance.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import json


@dataclass
class TagInstance:
    """Represents a single tag instance with full context."""
    tag_name: str
    ply: int
    node_id: str
    squares: List[str]
    aggressors: List[str] = field(default_factory=list)
    victims: List[str] = field(default_factory=list)
    side: Optional[str] = None
    confidence: int = 0
    branch_path: List[str] = field(default_factory=list)  # Path from PV to this node
    details: Dict[str, Any] = field(default_factory=dict)


class TagTracker:
    """Tracks tag instances across confidence tree branches."""
    
    def __init__(self):
        self.tag_instances: Dict[str, List[TagInstance]] = {}  # tag_name -> List[TagInstance]
        self.node_to_tags: Dict[str, List[str]] = {}  # node_id -> List[tag_name]
    
    def add_tag_instance(
        self,
        tag_name: str,
        node_id: str,
        ply: int,
        confidence: int,
        squares: List[str],
        branch_path: List[str],
        aggressors: List[str] = None,
        victims: List[str] = None,
        side: Optional[str] = None,
        details: Dict[str, Any] = None
    ) -> None:
        """Add a tag instance to the tracker."""
        if tag_name not in self.tag_instances:
            self.tag_instances[tag_name] = []
        
        instance = TagInstance(
            tag_name=tag_name,
            ply=ply,
            node_id=node_id,
            squares=squares or [],
            aggressors=aggressors or [],
            victims=victims or [],
            side=side,
            confidence=confidence,
            branch_path=branch_path.copy(),
            details=details or {}
        )
        
        self.tag_instances[tag_name].append(instance)
        
        # Track reverse mapping
        if node_id not in self.node_to_tags:
            self.node_to_tags[node_id] = []
        if tag_name not in self.node_to_tags[node_id]:
            self.node_to_tags[node_id].append(tag_name)
    
    def track_tag_across_branches(self, nodes: List[Any]) -> Dict[str, List[TagInstance]]:
        """
        Track all tag instances from nodes and return mapping.
        
        Args:
            nodes: List of NodeState objects with tags in metadata
            
        Returns:
            Dictionary mapping tag_name -> List[TagInstance]
        """
        # Build node lookup for branch path construction
        node_by_id = {node.id: node for node in nodes}
        
        for node in nodes:
            tags = node.metadata.get("tags", [])
            if not tags:
                continue
            
            # Determine branch path (path from PV to this node)
            branch_path = self._get_branch_path(node, node_by_id)
            
            for tag_data in tags:
                tag_name = tag_data.get("tag_name")
                if not tag_name:
                    continue
                
                self.add_tag_instance(
                    tag_name=tag_name,
                    node_id=node.id,
                    ply=node.ply_index,
                    confidence=node.frozen_confidence if node.has_branches and node.frozen_confidence is not None else node.confidence,
                    squares=tag_data.get("squares", []),
                    branch_path=branch_path,
                    aggressors=tag_data.get("aggressors", []),
                    victims=tag_data.get("victims", []),
                    side=tag_data.get("side"),
                    details=tag_data.get("details", {})
                )
        
        return self.tag_instances
    
    def _get_branch_path(self, node: Any, node_by_id: Dict[str, Any]) -> List[str]:
        """Get the path from PV to this node."""
        path = []
        current = node
        
        while current and current.parent_id:
            path.insert(0, current.id)
            current = node_by_id.get(current.parent_id)
            # Stop if we reach a PV node
            if current and (current.role == "pv" or current.id.startswith("pv-")):
                break
        
        return path
    
    def analyze_tag_relevance(self, baseline: int) -> Dict[str, Any]:
        """
        Analyze tag relevance across branches.
        
        Args:
            baseline: Confidence baseline threshold
            
        Returns:
            Dictionary with critical_tags, branching_tags, confidence_correlated_tags
        """
        critical_tags = []
        branching_tags = []
        confidence_correlated_tags = []
        
        for tag_name, instances in self.tag_instances.items():
            if not instances:
                continue
            
            # Analyze tag behavior
            high_conf_instances = [i for i in instances if i.confidence >= baseline]
            low_conf_instances = [i for i in instances if i.confidence < baseline]
            
            # Tags that appear in high-confidence nodes
            if high_conf_instances:
                critical_tags.append({
                    "tag_name": tag_name,
                    "high_conf_count": len(high_conf_instances),
                    "low_conf_count": len(low_conf_instances),
                    "instances": len(instances)
                })
            
            # Tags that appear in multiple branches (branching points)
            branch_paths = set(tuple(i.branch_path) for i in instances)
            if len(branch_paths) > 1:
                branching_tags.append({
                    "tag_name": tag_name,
                    "branch_count": len(branch_paths),
                    "instances": len(instances)
                })
            
            # Tags that correlate with confidence changes
            if len(instances) > 1:
                confs = [i.confidence for i in instances]
                conf_range = max(confs) - min(confs)
                if conf_range > 20:  # Significant confidence variation
                    confidence_correlated_tags.append({
                        "tag_name": tag_name,
                        "confidence_range": conf_range,
                        "min_confidence": min(confs),
                        "max_confidence": max(confs),
                        "instances": len(instances)
                    })
        
        return {
            "critical_tags": sorted(critical_tags, key=lambda x: x["high_conf_count"], reverse=True),
            "branching_tags": sorted(branching_tags, key=lambda x: x["branch_count"], reverse=True),
            "confidence_correlated_tags": sorted(confidence_correlated_tags, key=lambda x: x["confidence_range"], reverse=True)
        }
    
    def map_tag_confidence_changes(self, nodes: List[Any]) -> Dict[str, Dict[int, int]]:
        """
        Map tag confidence changes with depth and across branches.
        
        Args:
            nodes: List of NodeState objects
            
        Returns:
            Dictionary mapping tag_name -> {ply: confidence, ...}
        """
        tag_confidence_map: Dict[str, Dict[int, int]] = {}
        
        for tag_name, instances in self.tag_instances.items():
            tag_confidence_map[tag_name] = {}
            for instance in instances:
                ply = instance.ply
                # If multiple instances at same ply, take average
                if ply in tag_confidence_map[tag_name]:
                    tag_confidence_map[tag_name][ply] = (
                        tag_confidence_map[tag_name][ply] + instance.confidence
                    ) // 2
                else:
                    tag_confidence_map[tag_name][ply] = instance.confidence
        
        return tag_confidence_map


def track_tag_across_branches(nodes: List[Any]) -> TagTracker:
    """
    Convenience function to track tags across branches.
    
    Args:
        nodes: List of NodeState objects
        
    Returns:
        TagTracker instance with all tags tracked
    """
    tracker = TagTracker()
    tracker.track_tag_across_branches(nodes)
    return tracker

