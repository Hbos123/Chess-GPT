#!/usr/bin/env python3
"""
Test script for D2/D16 branching pathway.
Tests the complete branching system on starting position and outputs results to a temporary file.
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import chess

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from investigator import Investigator
from engine_pool import EnginePool
from engine_queue import StockfishQueue


async def test_d2_d16_branching():
    """Test D2/D16 branching pathway on starting position."""
    
    # Starting position FEN
    start_fen = chess.STARTING_FEN
    
    print("=" * 80)
    print("D2/D16 BRANCHING PATHWAY TEST")
    print("=" * 80)
    print(f"Starting FEN: {start_fen}")
    print(f"Test started at: {datetime.now().isoformat()}")
    print("=" * 80)
    print()
    
    # Initialize engine
    print("🔧 Initializing engine...")
    engine_queue = None
    engine_pool = None
    try:
        engine_queue = StockfishQueue()
        await engine_queue.initialize()
        print("✅ Engine initialized")
    except Exception as e:
        print(f"❌ Engine initialization failed: {e}")
        print("   Trying to use engine pool instead...")
        try:
            from engine_pool import get_engine_pool
            engine_pool = await get_engine_pool()
            if engine_pool:
                print("✅ Engine pool initialized")
            else:
                print("❌ Could not initialize engine pool either")
                return
        except Exception as e2:
            print(f"❌ Engine pool initialization also failed: {e2}")
            return
    
    # Initialize investigator
    print("🔧 Initializing investigator...")
    try:
        if engine_queue:
            investigator = Investigator(engine_queue=engine_queue)
        elif engine_pool:
            investigator = Investigator(engine_pool=engine_pool)
        else:
            print("❌ No engine available")
            return
        print("✅ Investigator initialized")
        print()
    except Exception as e:
        print(f"❌ Investigator initialization failed: {e}")
        return
    
    # Run investigation
    print("🔍 Running investigate_with_dual_depth...")
    print("-" * 80)
    
    try:
        result = await investigator.investigate_with_dual_depth(
            fen=start_fen,
            scope="general_position",
            depth_16=16,
            depth_2=2,
            original_fen=start_fen,
            branching_limit=4,  # Limit branches for testing
            max_pv_plies=16,  # Limit PV length
            include_pgn=True,
            pgn_max_chars=20000,
            branch_depth_limit=3  # Limit recursion depth
        )
        print("-" * 80)
        print("✅ Investigation complete")
        print()
    except Exception as e:
        print(f"❌ Investigation failed: {e}")
        import traceback
        traceback.print_exc()
        return
    finally:
        # Cleanup
        try:
            if engine_queue:
                await engine_queue.cleanup()
        except Exception:
            pass
    
    # Convert result to dict
    result_dict = result.to_dict(include_semantic_story=False)
    
    # Build claims
    print("🔍 Building claims from investigation...")
    from skills.claims import build_claims_from_investigation
    claims = build_claims_from_investigation(result_dict)
    print(f"✅ Built {len(claims)} claims")
    print()
    
    # Prepare output
    output = {
        "test_info": {
            "fen": start_fen,
            "test_time": datetime.now().isoformat(),
            "test_type": "d2_d16_branching_pathway"
        },
        "root_analysis": {
            "eval_d16": result.eval_d16,
            "eval_d2": result.eval_d2,
            "best_move_d16": result.best_move_d16,
            "best_move_d16_eval_cp": result.best_move_d16_eval_cp,
            "second_best_move_d16": result.second_best_move_d16,
            "second_best_move_d16_eval_cp": result.second_best_move_d16_eval_cp,
            "is_critical": result.is_critical,
            "is_winning": result.is_winning,
            "overestimated_moves": result.overestimated_moves,
        },
        "exploration_tree": {
            "root_eval_d16": result_dict.get("exploration_tree", {}).get("eval_d16"),
            "best_move_d16": result_dict.get("exploration_tree", {}).get("best_move_d16"),
            "pv_full": result_dict.get("exploration_tree", {}).get("pv_full", []),
            "threat_claim": result_dict.get("exploration_tree", {}).get("threat_claim"),
            "pv_threat_claims_count": len(result_dict.get("exploration_tree", {}).get("pv_threat_claims", [])),
            "pv_branches_count": len(result_dict.get("exploration_tree", {}).get("pv_branches", [])),
            "root_branches_count": len(result_dict.get("exploration_tree", {}).get("branches", [])),
        },
        "threats": {
            "root_threat": result_dict.get("exploration_tree", {}).get("threat_claim"),
            "pv_threats": result_dict.get("exploration_tree", {}).get("pv_threat_claims", []),
        },
        "claims": claims,
        "evidence_line": {
            "evidence_pgn_line": result.evidence_pgn_line,
            "evidence_moves": result.evidence_main_line_moves,
            "eval_start": result.evidence_eval_start,
            "eval_end": result.evidence_eval_end,
            "eval_delta": result.evidence_eval_delta,
            "material_start": result.evidence_material_start,
            "material_end": result.evidence_material_end,
            "positional_start": result.evidence_positional_start,
            "positional_end": result.evidence_positional_end,
        },
        "pgn_exploration": result.pgn_exploration[:5000] if result.pgn_exploration else "",  # First 5000 chars
        "pgn_length": len(result.pgn_exploration) if result.pgn_exploration else 0,
    }
    
    # Write to temporary file
    temp_dir = Path("/tmp")
    temp_file = temp_dir / f"d2_d16_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    print(f"📝 Writing results to: {temp_file}")
    with open(temp_file, 'w') as f:
        json.dump(output, f, indent=2, default=str)
    
    print(f"✅ Results written to: {temp_file}")
    print()
    
    # Print summary
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Root Eval D16: {result.eval_d16}")
    print(f"Root Eval D2: {result.eval_d2}")
    print(f"Best Move D16: {result.best_move_d16}")
    print(f"Overestimated Moves: {len(result.overestimated_moves)}")
    print(f"Root Threat: {'Yes' if output['threats']['root_threat'] else 'No'}")
    if output['threats']['root_threat']:
        print(f"  - Significance: {output['threats']['root_threat'].get('threat_significance_cp')}cp")
    print(f"PV Threats: {len(output['threats']['pv_threats'])}")
    print(f"PV Branches: {output['exploration_tree']['pv_branches_count']}")
    print(f"Root Branches: {output['exploration_tree']['root_branches_count']}")
    print(f"Total Claims: {len(claims)}")
    print(f"PGN Length: {output['pgn_length']} chars")
    print("=" * 80)
    print()
    
    # Print claim types
    claim_types = {}
    for claim in claims:
        claim_type = claim.get("claim_type", "unknown")
        claim_types[claim_type] = claim_types.get(claim_type, 0) + 1
    
    print("Claim Types:")
    for claim_type, count in sorted(claim_types.items()):
        print(f"  - {claim_type}: {count}")
    print()
    
    print(f"✅ Test complete! Full results in: {temp_file}")


if __name__ == "__main__":
    asyncio.run(test_d2_d16_branching())

