#!/usr/bin/env python3
"""
Test script for InvestigationReducer.
Tests the reducer with the D2/D16 test output.
"""

import asyncio
import json
import sys
import os
from pathlib import Path

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from investigation_reducer import InvestigationReducer
from skills.claims import build_claims_from_investigation
from investigator import InvestigationResult


async def test_reducer():
    """Test the reducer with the D2/D16 test output."""
    
    # Load the test output
    test_file = Path("/tmp/d2_d16_test_20260106_181850.json")
    if not test_file.exists():
        print(f"❌ Test file not found: {test_file}")
        print("   Run test_d2_d16_branching.py first to generate test data")
        return
    
    print("=" * 80)
    print("INVESTIGATION REDUCER TEST")
    print("=" * 80)
    print(f"Loading test data from: {test_file}")
    print()
    
    with open(test_file, 'r') as f:
        test_data = json.load(f)
    
    # Reconstruct InvestigationResult from test data
    # (simplified - just enough to test the reducer)
    investigation = InvestigationResult(
        eval_before=None,
        eval_after=None,
        eval_drop=None,
        player_move=None,
        best_move=None,
        missed_move=None,
        intent_mismatch=None,
        game_phase=None,
        urgency=None,
        pgn_branches=None,
        tactics_found=None,
        threats=None,
        material_change=None,
        positional_change=None,
        theme_changes=None,
        candidate_moves=None,
        pv_after_move=None,
        user_proposed_move=None,
        candidate_move=None,
        is_awkward_development=None,
        light_raw_analysis=None,
        eval_d16=test_data["root_analysis"]["eval_d16"],
        best_move_d16=test_data["root_analysis"]["best_move_d16"],
        best_move_d16_eval_cp=test_data["root_analysis"]["best_move_d16_eval_cp"],
        second_best_move_d16=test_data["root_analysis"]["second_best_move_d16"],
        second_best_move_d16_eval_cp=test_data["root_analysis"]["second_best_move_d16_eval_cp"],
        is_critical=test_data["root_analysis"]["is_critical"],
        is_winning=test_data["root_analysis"]["is_winning"],
        eval_d2=test_data["root_analysis"]["eval_d2"],
        top_moves_d2=None,
        overestimated_moves=test_data["root_analysis"]["overestimated_moves"],
        exploration_tree=test_data["exploration_tree"],
        pgn_exploration=test_data.get("pgn_exploration", ""),
        themes_identified=None,
        evidence_pgn_line=test_data["evidence_line"].get("evidence_pgn_line"),
        evidence_main_line_moves=test_data["evidence_line"].get("evidence_moves", []),
        evidence_eval_start=test_data["evidence_line"].get("eval_start"),
        evidence_eval_end=test_data["evidence_line"].get("eval_end"),
        evidence_eval_delta=test_data["evidence_line"].get("eval_delta"),
        evidence_material_start=test_data["evidence_line"].get("material_start"),
        evidence_material_end=test_data["evidence_line"].get("material_end"),
        evidence_positional_start=test_data["evidence_line"].get("positional_start"),
        evidence_positional_end=test_data["evidence_line"].get("positional_end"),
    )
    
    # Build claims
    print("🔍 Building claims from investigation...")
    inv_dict = investigation.to_dict(include_semantic_story=False)
    claims = build_claims_from_investigation(inv_dict)
    print(f"✅ Built {len(claims)} claims")
    print()
    
    # Reduce investigation
    print("🔍 Reducing investigation data...")
    reducer = InvestigationReducer()
    reduced_data = reducer.reduce(investigation, claims)
    print("✅ Reduction complete")
    print()
    
    # Print summary
    print("=" * 80)
    print("REDUCED DATA SUMMARY")
    print("=" * 80)
    print()
    
    print("PRIMARY CLAIM:")
    pc = reduced_data["primary_claim"]
    print(f"  Best move: {pc.get('best_move')}")
    print(f"  Eval start: {pc.get('eval_start')}")
    print(f"  Eval end: {pc.get('eval_end')}")
    print(f"  Eval delta: {pc.get('eval_delta')}")
    print()
    
    print(f"REJECTED ALTERNATIVES ({len(reduced_data['rejected_alternatives'])}):")
    for i, alt in enumerate(reduced_data["rejected_alternatives"][:3], 1):
        print(f"  {i}. {alt.get('move')}: {alt.get('reason')}")
        if alt.get('branch_eval') is not None:
            print(f"     Branch eval: {alt.get('branch_eval'):+.2f}")
    print()
    
    print(f"THREATS ({len(reduced_data['threats'])}):")
    for i, threat in enumerate(reduced_data["threats"][:3], 1):
        print(f"  {i}. At {threat.get('location')}: {threat.get('significance_cp')}cp gap")
        print(f"     {threat.get('explanation')}")
    print()
    
    print(f"KEY INSIGHTS ({len(reduced_data['key_insights'])}):")
    for insight in reduced_data["key_insights"][:5]:
        print(f"  - {insight}")
    print()
    
    print("NARRATIVE SUMMARY:")
    print(reduced_data["narrative_summary"])
    print()
    
    print("STRUCTURED FACTS (for LLM):")
    print(reduced_data["structured_facts"])
    print()
    
    # Save reduced data
    output_file = Path("/tmp/reducer_test_output.json")
    with open(output_file, 'w') as f:
        json.dump(reduced_data, f, indent=2, default=str)
    
    print(f"✅ Reduced data saved to: {output_file}")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_reducer())

