"""
Offline position generation script.
Generates completed theme positions, deduplicates, then backtracks to create puzzles.
Run: python3 backend/generate_lesson_positions.py
"""

import asyncio
import chess
import chess.engine
import json
import sys
import random
import time
from typing import List, Dict, Set, Any
from predicates import score_topic
from retrograde_builder import backtrack_from_position


STOCKFISH_PATH = "./stockfish"


async def generate_finished_positions(
    topic_code: str,
    engine: chess.engine.SimpleEngine,
    target_count: int = 20,
    max_attempts: int = 100
) -> List[str]:
    """
    Generate positions that ALREADY HAVE the theme present.
    These will be backtracked later to create starting positions.
    """
    finished_fens = []
    attempts = 0
    
    print(f"\n🎯 Generating finished positions for {topic_code}...")
    print(f"Target: {target_count} positions")
    
    while len(finished_fens) < target_count and attempts < max_attempts:
        attempts += 1
        
        # Rollout from start
        board = chess.Board()
        rng = random.Random(int(time.time() * 1000) + attempts)
        
        # Random rollout 10-20 moves
        plies = rng.randint(10, 20)
        
        for _ in range(plies):
            # Get engine moves
            try:
                analysis = await engine.analyse(board, chess.engine.Limit(time=0.05), multipv=5)
                
                if not analysis:
                    break
                
                if not isinstance(analysis, list):
                    analysis = [analysis]
                
                # Sample from top moves
                moves = []
                for info in analysis[:5]:
                    pv = info.get("pv", [])
                    if pv:
                        moves.append(pv[0])
                
                if not moves:
                    break
                
                # Random choice from top moves
                move = rng.choice(moves)
                board.push(move)
                
            except:
                break
        
        # Check if position has the theme
        pred_result = score_topic(topic_code, board)
        
        if pred_result.score >= 0.85:
            fen = board.fen()
            finished_fens.append(fen)
            print(f"  ✓ Found position {len(finished_fens)}/{target_count} (score: {pred_result.score:.2f})")
        
        if attempts % 10 == 0:
            print(f"  ... {attempts} attempts, {len(finished_fens)} found")
    
    print(f"\n✅ Generated {len(finished_fens)} finished positions in {attempts} attempts")
    return finished_fens


def deduplicate_positions(fens: List[str]) -> List[str]:
    """Remove duplicate FENs."""
    seen: Set[str] = set()
    unique = []
    
    for fen in fens:
        # Use board FEN (without move counters) for dedup
        board = chess.Board(fen)
        board_fen = board.board_fen()
        
        if board_fen not in seen:
            seen.add(board_fen)
            unique.append(fen)
    
    duplicates_removed = len(fens) - len(unique)
    if duplicates_removed > 0:
        print(f"🔧 Removed {duplicates_removed} duplicate positions")
    
    return unique


async def process_positions_for_topic(
    topic_code: str,
    engine: chess.engine.SimpleEngine,
    target_positions: int = 10,
    backtrack_plies: int = 6
) -> List[Dict[str, Any]]:
    """
    Full pipeline: generate finished → deduplicate → backtrack → package.
    """
    print(f"\n{'='*60}")
    print(f"Processing Topic: {topic_code}")
    print(f"{'='*60}")
    
    # Step 1: Generate finished positions with theme present
    finished_fens = await generate_finished_positions(
        topic_code, 
        engine, 
        target_count=target_positions * 2  # Generate 2x for dedup margin
    )
    
    if not finished_fens:
        print(f"❌ Failed to generate any positions for {topic_code}")
        return []
    
    # Step 2: Deduplicate
    unique_fens = deduplicate_positions(finished_fens)
    
    # Step 3: Backtrack to create puzzles
    print(f"\n🔙 Backtracking {len(unique_fens)} positions...")
    
    processed_positions = []
    
    for i, end_fen in enumerate(unique_fens[:target_positions]):
        try:
            print(f"  Processing {i+1}/{min(len(unique_fens), target_positions)}... ", end="", flush=True)
            
            starting_fen, mainline_san = await backtrack_from_position(
                end_fen,
                backtrack_plies,
                engine
            )
            
            processed_positions.append({
                "fen": starting_fen,
                "ideal_line": mainline_san,
                "end_fen": end_fen,
                "topic": topic_code
            })
            
            print(f"✓ ({len(mainline_san)} moves backtracked)")
            
        except Exception as e:
            print(f"✗ Failed: {e}")
            continue
    
    print(f"\n✅ Successfully backtracked {len(processed_positions)} positions")
    
    return processed_positions


async def main():
    """Generate positions for all topics and save to JSON file."""
    
    # Initialize engine
    print("🚀 Initializing Stockfish engine...")
    engine = await chess.engine.popen_uci(STOCKFISH_PATH)
    
    print("✓ Engine initialized")
    
    # Topics to generate
    topics = [
        "PS.IQP",
        "PS.CARLSBAD",
        "ST.OUTPOST",
        "ST.SEVENTH_RANK",
        "ST.OPEN_FILE",
        "TM.PIN",
        "TM.FORK",
    ]
    
    all_positions = {}
    
    for topic in topics:
        positions = await process_positions_for_topic(
            topic,
            engine,
            target_positions=5,  # 5 unique positions per topic
            backtrack_plies=6
        )
        
        all_positions[topic] = positions
    
    # Save to JSON
    output_file = "backend/generated_positions.json"
    with open(output_file, "w") as f:
        json.dump(all_positions, f, indent=2)
    
    print(f"\n{'='*60}")
    print(f"✅ Generation Complete!")
    print(f"{'='*60}")
    print(f"Saved to: {output_file}")
    print(f"Total topics: {len(all_positions)}")
    print(f"Total positions: {sum(len(v) for v in all_positions.values())}")
    
    # Cleanup
    await engine.quit()


if __name__ == "__main__":
    asyncio.run(main())




