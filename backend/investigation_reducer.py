"""
Investigation Reducer - Interpreter Layer
Purpose: Transform raw InvestigationResult + Claims into structured, LLM-friendly summaries.
Reduces complexity, extracts insights, and creates narrative flow.
"""

from typing import Dict, Any, List, Optional, Tuple
from investigator import InvestigationResult


class InvestigationReducer:
    """
    Interprets and reduces investigation results into structured summaries.
    Bridges the gap between raw analysis data and LLM explanation.
    """
    
    def __init__(self):
        """Initialize the reducer."""
        pass
    
    def reduce(
        self,
        investigation: InvestigationResult,
        claims: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Reduce investigation result and claims into structured summary.
        
        Args:
            investigation: InvestigationResult from Investigator
            claims: List of claims from build_claims_from_investigation
            
        Returns:
            Dict with structured sections:
            - primary_claim: Root claim with eval trajectory
            - rejected_alternatives: Overestimated moves with why they fail
            - threats: Significant threats with context
            - key_insights: Extracted patterns
            - narrative_summary: Human-readable flow
            - structured_facts: Formatted facts for LLM
        """
        # Extract primary claim (baseline)
        primary_claim = self._extract_primary_claim(investigation, claims)
        
        # Extract rejected alternatives (overestimated moves)
        rejected_alternatives = self._extract_rejected_alternatives(investigation, claims)
        
        # Extract threats (significant threats >= 60cp)
        threats = self._extract_threats(investigation, claims)
        
        # Extract key insights from exploration tree
        key_insights = self._extract_key_insights(investigation)
        
        # Build narrative summary
        narrative_summary = self._build_narrative_summary(
            primary_claim, rejected_alternatives, threats, key_insights
        )
        
        # Build structured facts for LLM
        structured_facts = self._build_structured_facts(
            investigation, primary_claim, rejected_alternatives, threats
        )
        
        return {
            "primary_claim": primary_claim,
            "rejected_alternatives": rejected_alternatives,
            "threats": threats,
            "key_insights": key_insights,
            "narrative_summary": narrative_summary,
            "structured_facts": structured_facts,
        }
    
    def _extract_primary_claim(
        self, investigation: InvestigationResult, claims: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Extract the primary (baseline) claim."""
        baseline_claim = None
        evidence_claim = None
        
        for claim in claims:
            if claim.get("claim_type") == "baseline":
                baseline_claim = claim
            elif claim.get("claim_type") == "evidence_line":
                evidence_claim = claim
        
        eval_start = investigation.eval_d16
        eval_end = None
        eval_delta = None
        
        if evidence_claim:
            support = evidence_claim.get("support", {})
            eval_start = support.get("eval_start") or eval_start
            eval_end = support.get("eval_end")
            eval_delta = support.get("eval_delta")
        
        return {
            "best_move": investigation.best_move_d16,
            "eval_start": eval_start,
            "eval_end": eval_end,
            "eval_delta": eval_delta,
            "eval_d16": investigation.eval_d16,
            "eval_d2": investigation.eval_d2,
            "is_critical": investigation.is_critical,
            "is_winning": investigation.is_winning,
            "evidence_line": evidence_claim.get("support", {}).get("pgn_line") if evidence_claim else None,
            "evidence_moves": evidence_claim.get("support", {}).get("moves", [])[:8] if evidence_claim else [],
        }
    
    def _extract_rejected_alternatives(
        self, investigation: InvestigationResult, claims: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Extract rejected alternatives (overestimated moves) with reasons."""
        alternatives = []
        
        # Get overestimated moves from claims
        overestimated_claims = [
            c for c in claims if c.get("claim_type") == "overestimated_move"
        ]
        
        # Get branch data from exploration tree
        exploration_tree = investigation.exploration_tree or {}
        branches = exploration_tree.get("branches", [])
        
        # Match claims with branch data
        for claim in overestimated_claims[:5]:  # Limit to top 5
            move = claim.get("support", {}).get("move")
            if not move:
                continue
            
            # Find corresponding branch
            branch_data = None
            for branch in branches:
                if branch.get("move_played") == move:
                    branch_data = branch
                    break
            
            alternative = {
                "move": move,
                "reason": "Overestimated at shallow depth (D2) but worse at deep analysis (D16)",
                "eval_d16": investigation.eval_d16,
                "eval_d2": investigation.eval_d2,
            }
            
            if branch_data:
                branch_eval = branch_data.get("eval_d16")
                branch_stopped = branch_data.get("stopped", False)
                branch_stop_reason = branch_data.get("stop_reason", "")
                
                alternative.update({
                    "branch_eval": branch_eval,
                    "stopped": branch_stopped,
                    "stop_reason": branch_stop_reason,
                    "branch_pv": branch_data.get("pv_full", [])[:6],  # First 6 moves
                })
                
                # Refine reason based on branch data
                if branch_stopped:
                    if "eval_below_threshold" in branch_stop_reason:
                        alternative["reason"] = f"Branch evaluation ({branch_eval:+.2f}) falls below threshold (15cp drop from root)"
                    elif "d2_eval_below_original" in branch_stop_reason:
                        alternative["reason"] = "Position after this move is worse than original position"
            
            alternatives.append(alternative)
        
        return alternatives
    
    def _extract_threats(
        self, investigation: InvestigationResult, claims: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Extract significant threats (>= 60cp) with context."""
        threats = []
        
        # Get threat claims
        threat_claims = [c for c in claims if c.get("claim_type") == "threat"]
        
        for claim in threat_claims[:5]:  # Limit to top 5
            support = claim.get("support", {})
            significance = support.get("threat_significance_cp", 0)
            
            if significance < 60:  # Only significant threats
                continue
            
            threat = {
                "significance_cp": significance,
                "best_move": support.get("threat_move_san") or support.get("best_opponent_move_san"),
                "second_best_move": support.get("second_best_opponent_move_san"),
                "threat_pv": support.get("threat_pv_san") or support.get("best_opponent_pv_san", [])[:6],
                "eval_after_threat": support.get("eval_after_best_threat"),
                "location": "root",
            }
            
            # Check if it's a PV threat
            if support.get("pv_move_index") is not None:
                threat["location"] = f"PV move {support.get('pv_move_index', 0) + 1} ({support.get('pv_move_san', '?')})"
            
            # Check if it's a branch threat
            if support.get("branch_move"):
                threat["location"] = f"Branch ({support.get('branch_move')})"
            
            threat["explanation"] = (
                f"Opponent has narrow options: best move ({threat['best_move']}) is significantly "
                f"better than second-best ({threat['second_best_move']}), gap: {significance}cp"
            )
            
            threats.append(threat)
        
        return threats
    
    def _extract_key_insights(self, investigation: InvestigationResult) -> List[str]:
        """Extract key insights from exploration tree."""
        insights = []
        exploration_tree = investigation.exploration_tree or {}
        
        # Insight: Critical decision point
        if investigation.is_critical:
            best = investigation.best_move_d16
            second = investigation.second_best_move_d16
            gap = (investigation.best_move_d16_eval_cp or 0) - (investigation.second_best_move_d16_eval_cp or 0)
            if gap > 0:
                insights.append(
                    f"Critical decision: {best} is significantly better than {second} "
                    f"(gap: {gap}cp)"
                )
        
        # Insight: Winning position
        if investigation.is_winning:
            insights.append("Position is winning for the side to move")
        
        # Insight: Overestimated moves found
        overestimated = investigation.overestimated_moves or []
        if overestimated:
            insights.append(
                f"Found {len(overestimated)} move(s) that appear good at shallow depth "
                f"but are worse at deep analysis"
            )
        
        # Insight: Branch exploration depth
        branches = exploration_tree.get("branches", [])
        if branches:
            stopped_branches = [b for b in branches if b.get("stopped", False)]
            if stopped_branches:
                insights.append(
                    f"Explored {len(branches)} alternate lines, "
                    f"{len(stopped_branches)} stopped due to evaluation drop"
                )
        
        # Insight: PV length
        pv_full = exploration_tree.get("pv_full", [])
        if pv_full and len(pv_full) > 10:
            insights.append(f"Principal variation extends {len(pv_full)} moves ahead")
        
        return insights
    
    def _build_narrative_summary(
        self,
        primary_claim: Dict[str, Any],
        rejected_alternatives: List[Dict[str, Any]],
        threats: List[Dict[str, Any]],
        key_insights: List[str],
    ) -> str:
        """Build a human-readable narrative summary."""
        parts = []
        
        # Opening: Position evaluation
        eval_start = primary_claim.get("eval_start") or primary_claim.get("eval_d16")
        best_move = primary_claim.get("best_move")
        
        parts.append(f"Position evaluation: {eval_start:+.2f} pawns")
        if best_move:
            parts.append(f"Best move: {best_move}")
        
        # Primary claim trajectory
        eval_end = primary_claim.get("eval_end")
        eval_delta = primary_claim.get("eval_delta")
        if eval_end is not None and eval_delta is not None:
            direction = "improves" if eval_delta > 0 else "worsens" if eval_delta < 0 else "maintains"
            parts.append(
                f"After best line, evaluation {direction} to {eval_end:+.2f} "
                f"({eval_delta:+.2f} change)"
            )
        
        # Rejected alternatives
        if rejected_alternatives:
            parts.append(f"\nRejected alternatives ({len(rejected_alternatives)}):")
            for alt in rejected_alternatives[:3]:  # Top 3
                move = alt.get("move")
                reason = alt.get("reason", "Worse than best move")
                parts.append(f"  - {move}: {reason}")
        
        # Threats
        if threats:
            parts.append(f"\nSignificant threats detected ({len(threats)}):")
            for threat in threats[:3]:  # Top 3
                location = threat.get("location", "position")
                significance = threat.get("significance_cp", 0)
                parts.append(f"  - At {location}: {significance}cp gap between best and second-best")
        
        # Key insights
        if key_insights:
            parts.append(f"\nKey insights:")
            for insight in key_insights[:5]:  # Top 5
                parts.append(f"  - {insight}")
        
        return "\n".join(parts)
    
    def _build_structured_facts(
        self,
        investigation: InvestigationResult,
        primary_claim: Dict[str, Any],
        rejected_alternatives: List[Dict[str, Any]],
        threats: List[Dict[str, Any]],
    ) -> str:
        """Build structured facts card for LLM consumption."""
        parts = []
        
        # Primary evaluation
        parts.append("=== PRIMARY CLAIM ===")
        parts.append(f"Best move: {primary_claim.get('best_move', 'N/A')}")
        parts.append(f"Eval (D16): {primary_claim.get('eval_d16', 0):+.2f} pawns")
        parts.append(f"Eval (D2): {primary_claim.get('eval_d2', 0):+.2f} pawns")
        
        if primary_claim.get("eval_start") is not None:
            parts.append(f"Eval start: {primary_claim['eval_start']:+.2f} pawns")
        if primary_claim.get("eval_end") is not None:
            parts.append(f"Eval end: {primary_claim['eval_end']:+.2f} pawns")
        if primary_claim.get("eval_delta") is not None:
            parts.append(f"Eval delta: {primary_claim['eval_delta']:+.2f} pawns")
        
        if primary_claim.get("is_critical"):
            parts.append("⚠️ CRITICAL: Significant gap between best and second-best moves")
        if primary_claim.get("is_winning"):
            parts.append("✅ WINNING: Position is winning")
        
        # Evidence line
        evidence_moves = primary_claim.get("evidence_moves", [])
        if evidence_moves:
            parts.append(f"\nEvidence line: {' '.join(evidence_moves[:8])}")
        
        # Rejected alternatives
        if rejected_alternatives:
            parts.append(f"\n=== REJECTED ALTERNATIVES ({len(rejected_alternatives)}) ===")
            for i, alt in enumerate(rejected_alternatives[:3], 1):
                move = alt.get("move", "?")
                reason = alt.get("reason", "Worse evaluation")
                branch_eval = alt.get("branch_eval")
                parts.append(f"{i}. {move}: {reason}")
                if branch_eval is not None:
                    parts.append(f"   Branch eval: {branch_eval:+.2f} pawns")
                branch_pv = alt.get("branch_pv", [])
                if branch_pv:
                    parts.append(f"   Branch PV: {' '.join(branch_pv[:4])}")
        
        # Threats
        if threats:
            parts.append(f"\n=== THREATS ({len(threats)}) ===")
            for i, threat in enumerate(threats[:3], 1):
                location = threat.get("location", "position")
                significance = threat.get("significance_cp", 0)
                best_move = threat.get("best_move", "?")
                parts.append(f"{i}. At {location}: {significance}cp gap")
                parts.append(f"   Best threat: {best_move}")
                threat_pv = threat.get("threat_pv", [])
                if threat_pv:
                    parts.append(f"   Threat PV: {' '.join(threat_pv[:4])}")
        
        return "\n".join(parts)


