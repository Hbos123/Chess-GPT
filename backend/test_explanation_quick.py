#!/usr/bin/env python3
"""
Quick test script to verify explanation generator works.

Run with: python3 test_explanation_quick.py
"""

import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from explanation_generator import (
    MoveIntentClassifier, TagDeltaAnalyzer, generate_move_explanation
)

def test_basic_functionality():
    """Test basic functionality of explanation components."""
    print("Testing Move Intent Classifier...")
    classifier = MoveIntentClassifier()
    
    tags_before = [
        {"tag_name": "king.center.exposed", "side": "white", "strength": 0.8},
        {"tag_name": "threat.mate", "side": "white", "strength": 0.9}
    ]
    result = classifier.classify(tags_before, {}, "white")
    print(f"  ✓ Intent classification: {result['primary_type']} (confidence: {result['confidence']:.2f})")
    assert result["primary_type"] == "defensive"
    
    print("\nTesting Tag Delta Analyzer...")
    analyzer = TagDeltaAnalyzer()
    
    tags_before = [{"tag_name": "center.control", "side": "white"}]
    tags_after = [{"tag_name": "center.control", "side": "white"}, {"tag_name": "piece.activity", "side": "white"}]
    best_tags = [{"tag_name": "center.control", "side": "white"}, {"tag_name": "piece.activity", "side": "white"}]
    
    result = analyzer.analyze(tags_before, tags_after, best_tags, "white")
    print(f"  ✓ Tag deltas: gained={len(result['gained'])}, lost={len(result['lost'])}, missed={len(result['missed'])}")
    assert len(result["gained"]) > 0
    
    print("\nTesting Complete Explanation Generation...")
    ply_record = {
        "ply": 10,
        "side_moved": "white",
        "san": "Nf3",
        "uci": "g1f3",
        "fen_before": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
        "fen_after": "rnbqkb1r/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
        "cp_loss": 150,
        "category": "mistake"
    }
    raw_before = {
        "tags": [
            {"tag_name": "center.control", "side": "white"},
            {"tag_name": "piece.activity", "side": "white"}
        ],
        "themes": {},
        "eval_cp": 50
    }
    raw_after = {
        "tags": [{"tag_name": "center.control", "side": "white"}],
        "eval_cp": -100
    }
    best_move_tags = [
        {"tag_name": "center.control", "side": "white"},
        {"tag_name": "piece.activity", "side": "white"},
        {"tag_name": "threat.attack", "side": "white"}
    ]
    engine_info = [{"eval_cp": 50, "pv": ["g1f3", "d8h4"]}]
    
    result = generate_move_explanation(
        ply_record=ply_record,
        raw_before=raw_before,
        raw_after=raw_after,
        best_move_tags=best_move_tags,
        engine_info=engine_info,
        phase="opening"
    )
    
    print(f"  ✓ Generated explanation structure")
    print(f"    - Move intent: {result['move_intent']['primary_type']}")
    print(f"    - Mistake type: {result['mistake_classification']['primary_type']}")
    print(f"    - Narrative: {result['narrative']['primary_reason']}")
    print(f"    - Explanation: {result['narrative']['explanation'][:100]}...")
    
    assert "tag_analysis" in result
    assert "move_intent" in result
    assert "mistake_classification" in result
    assert "narrative" in result
    assert "explanation" in result["narrative"]
    
    print("\n✅ All basic tests passed!")
    return True

if __name__ == "__main__":
    try:
        test_basic_functionality()
        print("\n🎉 Explanation generator is working correctly!")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


















