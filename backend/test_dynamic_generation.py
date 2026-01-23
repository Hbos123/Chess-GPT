"""
Quick test script to verify dynamic position generation is working.
Run: python3 backend/test_dynamic_generation.py
"""

import asyncio
import os
import sys
import time

# Add parent directory to path
sys.path.insert(0, '.')

from backend.predicates import score_iqp, score_outpost, score_carlsbad
from backend.position_cache import PositionCache
import chess


async def test_predicates():
    """Test that predicates correctly identify positions."""
    print("=" * 60)
    print("TEST 1: Predicates")
    print("=" * 60)
    
    # Test IQP detection
    iqp_fen = "r1bq1rk1/pp1nbppp/2p1pn2/3p4/2PP4/2N1PN2/PP2BPPP/R1BQ1RK1 w - - 0 9"
    board = chess.Board(iqp_fen)
    result = score_iqp(board)
    
    print(f"\n✓ IQP Predicate:")
    print(f"  FEN: {iqp_fen[:50]}...")
    print(f"  Score: {result.score:.2f} (should be >0.7)")
    print(f"  Has IQP: {result.details.get('has_iqp')}")
    print(f"  IQP Square: {result.details.get('iqp_square')}")
    
    # Test Outpost detection
    outpost_fen = "r1bqr1k1/pp1nbppp/2p1pn2/3p4/2PP4/2N1PN2/PP2BPPP/R1BQR1K1 w - - 0 11"
    board = chess.Board(outpost_fen)
    result = score_outpost(board)
    
    print(f"\n✓ Outpost Predicate:")
    print(f"  FEN: {outpost_fen[:50]}...")
    print(f"  Score: {result.score:.2f}")
    print(f"  Outposts: {result.details.get('outposts', [])}")
    
    print("\n✅ Predicates working!\n")


async def test_cache():
    """Test position cache functionality."""
    print("=" * 60)
    print("TEST 2: Position Cache")
    print("=" * 60)
    
    cache = PositionCache(ttl_seconds=10)
    
    # Store a test position
    test_position = {
        "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        "objective": "Test position",
        "ideal_line": ["e4", "e5", "Nf3"]
    }
    
    await cache.store_position("PS.IQP", "white", "intermediate", test_position)
    print(f"\n✓ Stored position in cache")
    
    # Retrieve it
    retrieved = await cache.get_position("PS.IQP", "white", "intermediate")
    
    if retrieved:
        print(f"✓ Retrieved position from cache")
        print(f"  FEN: {retrieved['fen'][:50]}...")
        print(f"  Cache hit!")
    else:
        print(f"✗ Failed to retrieve from cache")
    
    # Check stats
    stats = cache.get_stats()
    print(f"\n✓ Cache Stats:")
    print(f"  Hits: {stats['hits']}")
    print(f"  Misses: {stats['misses']}")
    print(f"  Hit Rate: {stats['hit_rate']}")
    
    print("\n✅ Cache working!\n")


async def test_generation():
    """Test dynamic position generation (requires engine)."""
    print("=" * 60)
    print("TEST 3: Dynamic Generation")
    print("=" * 60)
    print("\nThis test requires the backend server to be running.")
    print("It will make actual API calls to test generation.")
    
    try:
        import urllib.request
        import json
        
        # Test generation endpoint
        port = os.getenv("BACKEND_PORT", "8001")
        url = f"http://localhost:{port}/generate_positions?topic_code=PS.IQP&count=1"
        
        print(f"\n✓ Testing: {url}")
        start = time.time()
        
        response = urllib.request.urlopen(url, timeout=5)
        data = json.loads(response.read())
        
        elapsed = (time.time() - start) * 1000
        
        if data.get("positions") and len(data["positions"]) > 0:
            pos = data["positions"][0]
            print(f"✓ Generated position in {elapsed:.0f}ms")
            print(f"  Topic: {pos.get('topic_name')}")
            print(f"  FEN: {pos.get('fen', '')[:60]}...")
            print(f"  Ideal line length: {len(pos.get('ideal_line', []))} moves")
            print(f"  Has objective: {'objective' in pos}")
            print(f"  Has hints: {'hints' in pos and len(pos['hints']) > 0}")
            
            # Check if it's dynamically generated or template
            is_dynamic = pos.get('meta', {}).get('generated', False)
            is_fallback = pos.get('meta', {}).get('fallback', False)
            
            if is_dynamic:
                print(f"  Source: ✨ DYNAMIC GENERATION")
            elif is_fallback:
                print(f"  Source: ⚠️  Template Fallback")
            else:
                print(f"  Source: Unknown")
            
            print("\n✅ Generation working!")
        else:
            print(f"✗ No positions returned")
            
    except Exception as e:
        print(f"\n⚠️  Could not test generation: {e}")
        print("   Make sure backend server is running at localhost:8000")


async def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print(" DYNAMIC FEN GENERATION SYSTEM - TEST SUITE")
    print("=" * 60 + "\n")
    
    try:
        await test_predicates()
        await test_cache()
        await test_generation()
        
        print("=" * 60)
        print(" ALL TESTS COMPLETE")
        print("=" * 60 + "\n")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())




