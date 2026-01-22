#!/usr/bin/env python3
"""
Extract PGN from the most recent investigation result.

This script connects to the backend or reads from logs to extract
the most recent investigation PGN and create documentation.
"""

import sys
import os
from pathlib import Path
import asyncio
from datetime import datetime

# Add parent directory to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "backend"))

# Change to project root for imports
os.chdir(project_root)

# Import required modules
try:
    from dotenv import load_dotenv
    load_dotenv()
    
    from investigator import Investigator
    from engine_pool import EnginePool
    from scripts.extract_pgn_documentation import create_documentation_from_pgn
    
    import chess
    import chess.engine
except ImportError as e:
    print(f"Error importing modules: {e}")
    print("Make sure you're running from the project root and dependencies are installed.")
    import traceback
    traceback.print_exc()
    sys.exit(1)


async def get_recent_investigation_pgn(fen: str = None) -> str:
    """
    Get PGN from a recent investigation.
    
    Args:
        fen: Optional FEN string to investigate. If None, uses starting position.
    
    Returns:
        PGN string from investigation
    """
    if fen is None:
        # Default to starting position
        fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    
    print(f"Starting investigation for position: {fen[:50]}...")
    print()
    
    # Initialize engine pool
    print("Initializing engine pool...")
    # Use the same path as main.py, but try to find stockfish
    stockfish_path = os.getenv("STOCKFISH_PATH", "./stockfish")
    
    # If the path from env doesn't exist, try to find it
    if stockfish_path == "./stockfish" and not os.path.exists(stockfish_path):
        import shutil
        # Try common locations
        possible_paths = [
            "/opt/homebrew/bin/stockfish",
            "/usr/local/bin/stockfish"
        ]
        for path in possible_paths:
            if os.path.exists(path):
                stockfish_path = path
                break
        else:
            # Try PATH
            found = shutil.which("stockfish")
            if found:
                stockfish_path = found
            else:
                stockfish_path = "stockfish"  # Final fallback
    
    print(f"   Using Stockfish: {stockfish_path}")
    engine_pool = EnginePool(
        pool_size=2,
        stockfish_path=stockfish_path
    )
    init_result = await engine_pool.initialize()
    if not init_result:
        print("❌ Engine pool failed to initialize. Cannot continue.")
        print("   Make sure Stockfish is installed and accessible.")
        return ""
    print("✅ Engine pool initialized")
    print()
    
    # Initialize investigator
    print("Initializing investigator...")
    investigator = Investigator(
        engine_pool=engine_pool,
        engine_queue=None  # Use pool, not queue
    )
    print("✅ Investigator initialized")
    print()
    
    # Run investigation with dual-depth analysis
    print("Running dual-depth investigation (D16/D2)...")
    print("This may take a minute...")
    print()
    
    try:
        result = await investigator.investigate_position(
            fen=fen,
            scope="general_position"  # This triggers dual-depth analysis
        )
        
        pgn = result.pgn_exploration
        
        if not pgn or len(pgn.strip()) < 100:
            print("⚠️ Warning: PGN is empty or very short")
            print(f"   PGN length: {len(pgn) if pgn else 0} chars")
            return ""
        
        print(f"✅ Investigation complete!")
        print(f"   PGN length: {len(pgn)} chars")
        print(f"   Overestimated moves: {len(result.overestimated_moves)}")
        print(f"   Themes: {', '.join(result.themes_identified[:5]) if result.themes_identified else 'None'}")
        print()
        
        return pgn
        
    except Exception as e:
        print(f"❌ Error during investigation: {e}")
        import traceback
        traceback.print_exc()
        return ""
    finally:
        # Cleanup
        await engine_pool.shutdown()


async def main():
    """Main function."""
    print("=" * 70)
    print("PGN Extraction from Recent Investigation")
    print("=" * 70)
    print()
    
    # Check if FEN provided as argument
    fen = None
    if len(sys.argv) > 1:
        fen = sys.argv[1]
        print(f"Using provided FEN: {fen}")
        print()
    
    # Get PGN from investigation
    pgn = await get_recent_investigation_pgn(fen)
    
    if not pgn:
        print("❌ No PGN extracted. Exiting.")
        return
    
    # Create documentation
    output_file = f"INVESTIGATION_PGN_EXTRACTED_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    print(f"Creating documentation file: {output_file}")
    print()
    
    try:
        output_path = create_documentation_from_pgn(pgn, output_file)
        print()
        print("=" * 70)
        print("✅ Documentation created successfully!")
        print(f"   File: {output_path}")
        print("=" * 70)
    except Exception as e:
        print(f"❌ Error creating documentation: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

