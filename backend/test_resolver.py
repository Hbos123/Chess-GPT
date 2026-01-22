#!/usr/bin/env python3
"""Smoke test for opening resolver"""
import asyncio
import sys
from opening_resolver import resolve_opening
from opening_explorer import LichessExplorerClient

async def test_resolver():
    """Test that resolver can handle opening names"""
    explorer = LichessExplorerClient()
    
    test_cases = [
        "Russian Game",
        "London System",
        "Sicilian Najdorf",
        "B90",
        "e4 e5 Nf3 Nf6"
    ]
    
    print("Testing opening resolver...")
    for query in test_cases:
        try:
            result = await resolve_opening(query, explorer)
            print(f"✅ '{query}' -> {result.get('name')} (FEN: {result.get('seed_fen')[:30]}...)")
        except Exception as e:
            print(f"❌ '{query}' failed: {e}")
            return False
    
    print("\n✅ All tests passed!")
    return True

if __name__ == "__main__":
    success = asyncio.run(test_resolver())
    sys.exit(0 if success else 1)

