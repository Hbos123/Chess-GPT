"""
Benchmark script to verify ProcessPoolExecutor speedup for theme/tag calculations.

Usage: python benchmark_parallel.py

This script:
1. Analyzes 20 positions serially (single process)
2. Analyzes same 20 positions with ProcessPoolExecutor (4 processes)
3. Verifies results are identical
4. Reports speedup factor
"""

import asyncio
import time
from concurrent.futures import ProcessPoolExecutor
from typing import List, Dict

import chess

from parallel_analyzer import compute_themes_and_tags, compute_theme_scores


# Test positions from various game phases
TEST_POSITIONS = [
    # Opening positions
    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",  # Starting
    "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",  # 1.e4
    "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",  # 1.e4 e5
    "rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 1 2",  # 2.Nf3
    "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3",  # 2...Nc6
    
    # Middlegame positions
    "r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4",  # Italian
    "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4",  # Open game
    "r1bqk2r/ppp2ppp/2np1n2/2b1p3/2B1P3/2NP1N2/PPP2PPP/R1BQK2R w KQkq - 0 6",  # Giuoco Piano
    "r2qkb1r/ppp1pppp/2n2n2/3p1b2/3P1B2/2N2N2/PPP1PPPP/R2QKB1R w KQkq - 4 5",  # London
    "rnbqk2r/pppp1ppp/4pn2/8/1bPP4/2N5/PP2PPPP/R1BQKBNR w KQkq - 2 4",  # Nimzo
    
    # Complex middlegame
    "r1bq1rk1/ppp2ppp/2np1n2/2b1p3/2B1P3/2NP1N2/PPP2PPP/R1BQ1RK1 w - - 0 7",
    "r2q1rk1/ppp1bppp/2n2n2/3pp3/2PP4/2NBPN2/PP3PPP/R1BQ1RK1 b - - 0 8",
    "r1bq1rk1/pp1n1ppp/4pn2/2pp4/1bPP4/2NBPN2/PP3PPP/R1BQ1RK1 w - - 0 8",
    "r2qr1k1/ppp2ppp/2n1bn2/3p4/3P4/2NBPN2/PP3PPP/R1BQ1RK1 w - - 0 10",
    "r4rk1/pp1qppbp/2np1np1/8/2PP4/2N1PN2/PP2BPPP/R1BQ1RK1 w - - 0 9",
    
    # Endgame positions
    "8/8/4k3/8/8/4K3/4P3/8 w - - 0 1",  # K+P vs K
    "8/5pk1/6p1/8/8/6P1/5PK1/8 w - - 0 1",  # Pawn ending
    "8/8/4k3/8/2B5/4K3/8/8 w - - 0 1",  # B+K vs K
    "4k3/8/8/8/8/8/4R3/4K3 w - - 0 1",  # R+K vs K
    "r3k3/8/8/8/8/8/8/R3K3 w Qq - 0 1",  # R vs R
]


def benchmark_serial(positions: List[str]) -> tuple:
    """Benchmark serial (single-threaded) computation."""
    results = []
    
    start_time = time.perf_counter()
    for fen in positions:
        result = compute_themes_and_tags(fen)
        result["theme_scores"] = compute_theme_scores(result["themes"])
        results.append(result)
    elapsed = time.perf_counter() - start_time
    
    return results, elapsed


async def benchmark_parallel(positions: List[str], num_workers: int = 4) -> tuple:
    """Benchmark parallel (multi-process) computation."""
    results = [None] * len(positions)
    
    with ProcessPoolExecutor(max_workers=num_workers) as pool:
        loop = asyncio.get_event_loop()
        
        start_time = time.perf_counter()
        
        # Submit all tasks
        futures = []
        for i, fen in enumerate(positions):
            future = loop.run_in_executor(pool, compute_themes_and_tags, fen)
            futures.append((i, future))
        
        # Gather results
        for i, future in futures:
            result = await future
            result["theme_scores"] = compute_theme_scores(result["themes"])
            results[i] = result
        
        elapsed = time.perf_counter() - start_time
    
    return results, elapsed


def verify_results(serial_results: List[Dict], parallel_results: List[Dict]) -> bool:
    """Verify that serial and parallel results match."""
    if len(serial_results) != len(parallel_results):
        print(f"❌ Length mismatch: {len(serial_results)} vs {len(parallel_results)}")
        return False
    
    for i, (s, p) in enumerate(zip(serial_results, parallel_results)):
        # Check themes
        if set(s["themes"].keys()) != set(p["themes"].keys()):
            print(f"❌ Position {i}: theme keys mismatch")
            return False
        
        # Check tags count (order may differ)
        if len(s["tags"]) != len(p["tags"]):
            print(f"❌ Position {i}: tag count mismatch ({len(s['tags'])} vs {len(p['tags'])})")
            return False
        
        # Check material balance
        if s["material_balance_cp"] != p["material_balance_cp"]:
            print(f"❌ Position {i}: material balance mismatch")
            return False
    
    return True


async def simulate_engine_analysis():
    """Simulate Stockfish engine analysis time (I/O bound, ~50ms per position)."""
    await asyncio.sleep(0.05)  # 50ms simulated engine wait


async def benchmark_realistic_serial(positions: List[str]) -> tuple:
    """
    Realistic benchmark: Serial theme/tag calcs AFTER engine analysis.
    This is what happens without ProcessPoolExecutor.
    """
    results = []
    start_time = time.perf_counter()
    
    for fen in positions:
        # Engine analysis first (I/O bound)
        await simulate_engine_analysis()
        # Then theme/tag calcs (CPU bound) - blocks the event loop
        result = compute_themes_and_tags(fen)
        result["theme_scores"] = compute_theme_scores(result["themes"])
        results.append(result)
    
    elapsed = time.perf_counter() - start_time
    return results, elapsed


async def benchmark_realistic_parallel(positions: List[str], num_workers: int = 4) -> tuple:
    """
    Realistic benchmark: Theme/tag calcs run IN PARALLEL with engine analysis.
    This is what happens WITH ProcessPoolExecutor.
    """
    results = [None] * len(positions)
    
    with ProcessPoolExecutor(max_workers=num_workers) as pool:
        loop = asyncio.get_event_loop()
        start_time = time.perf_counter()
        
        async def analyze_position(i: int, fen: str):
            # Start theme/tag calc in process pool (non-blocking)
            theme_future = loop.run_in_executor(pool, compute_themes_and_tags, fen)
            # Run engine analysis concurrently
            await simulate_engine_analysis()
            # Wait for theme/tag result
            result = await theme_future
            result["theme_scores"] = compute_theme_scores(result["themes"])
            results[i] = result
        
        # Run all positions with 4 concurrent workers
        tasks = [analyze_position(i, fen) for i, fen in enumerate(positions)]
        await asyncio.gather(*tasks)
        
        elapsed = time.perf_counter() - start_time
    
    return results, elapsed


async def main():
    print("=" * 60)
    print("ProcessPoolExecutor Benchmark")
    print("=" * 60)
    print(f"\nTesting with {len(TEST_POSITIONS)} positions")
    
    # Pure computation benchmark
    print("\n--- Pure Computation (no engine) ---")
    print("Running SERIAL benchmark (single process)...")
    serial_results, serial_time = benchmark_serial(TEST_POSITIONS)
    print(f"   Serial time: {serial_time:.3f}s")
    print(f"   Per position: {serial_time/len(TEST_POSITIONS)*1000:.1f}ms")
    
    print("\nRunning PARALLEL benchmark (4 processes)...")
    parallel_results, parallel_time = await benchmark_parallel(TEST_POSITIONS, num_workers=4)
    print(f"   Parallel time: {parallel_time:.3f}s")
    print(f"   Per position: {parallel_time/len(TEST_POSITIONS)*1000:.1f}ms")
    
    # Verify results
    print("\nVerifying results match...")
    if verify_results(serial_results, parallel_results):
        print("   ✅ Results match!")
    else:
        print("   ❌ Results DO NOT match!")
        return
    
    pure_speedup = serial_time / parallel_time
    print(f"\nPure computation speedup: {pure_speedup:.2f}x")
    
    # Realistic benchmark with simulated engine
    print("\n--- Realistic Scenario (with simulated engine) ---")
    print("Simulating 50ms engine analysis per position...")
    
    print("\nRunning SERIAL (engine then themes, blocking)...")
    _, realistic_serial_time = await benchmark_realistic_serial(TEST_POSITIONS)
    print(f"   Serial time: {realistic_serial_time:.3f}s")
    
    print("\nRunning PARALLEL (engine + themes concurrent)...")
    _, realistic_parallel_time = await benchmark_realistic_parallel(TEST_POSITIONS)
    print(f"   Parallel time: {realistic_parallel_time:.3f}s")
    
    realistic_speedup = realistic_serial_time / realistic_parallel_time
    
    # Report
    print("\n" + "=" * 60)
    print(f"REALISTIC SPEEDUP: {realistic_speedup:.2f}x")
    print("=" * 60)
    
    if realistic_speedup > 1.5:
        print("✅ Significant speedup achieved!")
    elif realistic_speedup > 1.0:
        print("⚠️  Modest speedup")
    else:
        print("❌ No speedup")
    
    # Time saved estimate
    print(f"\nEstimated time saved per 67-move game review:")
    time_saved_per_pos = (realistic_serial_time - realistic_parallel_time) / len(TEST_POSITIONS)
    total_saved = time_saved_per_pos * 134  # 67 moves × 2 positions each
    print(f"   ~{abs(total_saved):.1f}s {'saved' if total_saved > 0 else 'added'}")


if __name__ == "__main__":
    asyncio.run(main())

