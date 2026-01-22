"""
Multi-Depth Analysis Tool
Analyzes games at multiple Stockfish depths to detect suspiciously accurate play
"""

import chess
import chess.pgn
from io import StringIO
from typing import Dict, List, Optional, Literal
import asyncio


async def multi_depth_analyze(
    pgn: str,
    depths: List[int] = None,
    focus_side: Literal["white", "black", "both"] = "both",
    engine_queue = None,
    skip_book_moves: int = 8
) -> Dict:
    """
    Analyze a game at multiple depths and compare results.
    Useful for detecting suspiciously accurate play where accuracy
    increases abnormally with depth.
    
    Args:
        pgn: PGN string of the game
        depths: List of depths to analyze at (default: [10, 20, 30])
        focus_side: Which side to analyze
        engine_queue: Stockfish engine queue
        skip_book_moves: Number of opening moves to skip
        
    Returns:
        {
            "depth_comparison": [
                {"depth": 10, "accuracy": 78.5, "avg_cp_loss": 42, "moves_analyzed": 30},
                {"depth": 20, "accuracy": 82.1, "avg_cp_loss": 35, "moves_analyzed": 30},
                ...
            ],
            "convergence_rate": 0.95,
            "critical_moves": [
                {"move_num": 23, "move": "Rxf7", "depth_10_eval": -150, "depth_30_eval": 350, "diff": 500}
            ],
            "suspicion_indicators": {
                "rapid_convergence": bool,
                "high_deep_accuracy": bool,
                "unusual_depth_pattern": bool
            }
        }
    """
    if depths is None:
        depths = [10, 20, 30]
    
    # Sort depths
    depths = sorted(depths)
    
    # Parse PGN
    try:
        game = chess.pgn.read_game(StringIO(pgn))
        if not game:
            return {"error": "Could not parse PGN"}
    except Exception as e:
        return {"error": f"PGN parse error: {str(e)}"}
    
    # Get all positions and moves
    board = game.board()
    positions = []
    moves_played = []
    
    for move in game.mainline_moves():
        positions.append(board.fen())
        moves_played.append(move)
        board.push(move)
    
    # Filter by side
    analysis_indices = []
    for i, pos in enumerate(positions):
        fen_parts = pos.split()
        side_to_move = fen_parts[1]
        
        if focus_side == "both":
            if i >= skip_book_moves:
                analysis_indices.append(i)
        elif focus_side == "white" and side_to_move == "w":
            if i >= skip_book_moves:
                analysis_indices.append(i)
        elif focus_side == "black" and side_to_move == "b":
            if i >= skip_book_moves:
                analysis_indices.append(i)
    
    if not analysis_indices:
        return {"error": "No positions to analyze after filtering"}
    
    # Analyze at each depth
    depth_results = {}
    move_evaluations = {}  # {move_idx: {depth: {"eval": cp, "best_move": str}}}
    
    for depth in depths:
        depth_results[depth] = {
            "cp_losses": [],
            "matches_top1": 0,
            "matches_top3": 0,
            "total": 0
        }
    
    # Run analysis for each position at each depth
    for idx in analysis_indices:
        fen = positions[idx]
        played_move = moves_played[idx]
        
        move_evaluations[idx] = {}
        
        for depth in depths:
            try:
                if engine_queue:
                    # Use engine queue for analysis
                    result = await _analyze_position_at_depth(
                        engine_queue, fen, depth, num_lines=3
                    )
                else:
                    # Placeholder if no engine
                    result = {
                        "eval": 0,
                        "best_move": None,
                        "top_moves": []
                    }
                
                move_evaluations[idx][depth] = result
                
                # Calculate if played move matches engine recommendation
                played_uci = played_move.uci()
                best_move = result.get("best_move")
                top_moves = result.get("top_moves", [])
                
                if best_move == played_uci:
                    depth_results[depth]["matches_top1"] += 1
                    depth_results[depth]["matches_top3"] += 1
                elif played_uci in [m.get("move") for m in top_moves[:3]]:
                    depth_results[depth]["matches_top3"] += 1
                
                # Calculate CP loss
                # Find eval of played move vs best move
                played_eval = None
                for m in top_moves:
                    if m.get("move") == played_uci:
                        played_eval = m.get("eval", 0)
                        break
                
                if played_eval is not None:
                    best_eval = result.get("eval", 0)
                    # Normalize for side to move
                    cp_loss = abs(best_eval - played_eval)
                    depth_results[depth]["cp_losses"].append(cp_loss)
                
                depth_results[depth]["total"] += 1
                
            except Exception as e:
                print(f"Analysis error at depth {depth}, move {idx}: {e}")
                continue
    
    # Compile depth comparison
    depth_comparison = []
    for depth in depths:
        dr = depth_results[depth]
        total = dr["total"] or 1
        
        avg_cp_loss = sum(dr["cp_losses"]) / len(dr["cp_losses"]) if dr["cp_losses"] else 0
        accuracy = (dr["matches_top3"] / total * 100) if total > 0 else 0
        
        depth_comparison.append({
            "depth": depth,
            "accuracy": round(accuracy, 1),
            "avg_cp_loss": round(avg_cp_loss, 1),
            "top1_match": round(dr["matches_top1"] / total * 100, 1) if total > 0 else 0,
            "moves_analyzed": total
        })
    
    # Find critical moves (where eval changes significantly between depths)
    critical_moves = []
    for idx in analysis_indices:
        if idx not in move_evaluations:
            continue
        
        evals = move_evaluations[idx]
        if len(depths) >= 2:
            low_depth = depths[0]
            high_depth = depths[-1]
            
            if low_depth in evals and high_depth in evals:
                low_eval = evals[low_depth].get("eval", 0)
                high_eval = evals[high_depth].get("eval", 0)
                diff = abs(high_eval - low_eval)
                
                if diff > 100:  # Significant evaluation swing
                    move_num = idx + 1
                    move_san = _move_to_san(positions[idx], moves_played[idx])
                    
                    critical_moves.append({
                        "move_num": move_num,
                        "move": move_san,
                        f"depth_{low_depth}_eval": low_eval,
                        f"depth_{high_depth}_eval": high_eval,
                        "diff": diff
                    })
    
    # Sort by eval difference
    critical_moves.sort(key=lambda x: x.get("diff", 0), reverse=True)
    critical_moves = critical_moves[:10]  # Top 10
    
    # Calculate convergence rate (how quickly accuracy stabilizes)
    convergence_rate = _calculate_convergence(depth_comparison)
    
    # Suspicion indicators
    suspicion_indicators = {
        "rapid_convergence": convergence_rate > 0.95,
        "high_deep_accuracy": (
            depth_comparison[-1]["accuracy"] > 90 if depth_comparison else False
        ),
        "unusual_depth_pattern": _detect_unusual_pattern(depth_comparison)
    }
    
    return {
        "depth_comparison": depth_comparison,
        "convergence_rate": round(convergence_rate, 3),
        "critical_moves": critical_moves,
        "suspicion_indicators": suspicion_indicators,
        "moves_analyzed": len(analysis_indices),
        "focus_side": focus_side
    }


async def _analyze_position_at_depth(
    engine_queue,
    fen: str,
    depth: int,
    num_lines: int = 3
) -> Dict:
    """Analyze a position at a specific depth using engine queue"""
    try:
        # Put analysis request
        result = await engine_queue.analyze(fen, depth=depth, num_lines=num_lines)
        
        if result and "lines" in result:
            lines = result["lines"]
            best_line = lines[0] if lines else {}
            
            return {
                "eval": best_line.get("cp", 0),
                "best_move": best_line.get("pv", [""])[0] if best_line.get("pv") else None,
                "top_moves": [
                    {"move": line.get("pv", [""])[0], "eval": line.get("cp", 0)}
                    for line in lines[:num_lines]
                ]
            }
        
        return {"eval": 0, "best_move": None, "top_moves": []}
    
    except Exception as e:
        print(f"Engine analysis error: {e}")
        return {"eval": 0, "best_move": None, "top_moves": []}


def _move_to_san(fen: str, move: chess.Move) -> str:
    """Convert a move to SAN notation"""
    try:
        board = chess.Board(fen)
        return board.san(move)
    except:
        return move.uci()


def _calculate_convergence(depth_comparison: List[Dict]) -> float:
    """
    Calculate how quickly accuracy converges with depth.
    High convergence (>0.95) means accuracy barely changes at deeper depths.
    """
    if len(depth_comparison) < 2:
        return 0.5
    
    accuracies = [d["accuracy"] for d in depth_comparison]
    
    # Calculate how much accuracy changes between consecutive depths
    changes = []
    for i in range(1, len(accuracies)):
        change = abs(accuracies[i] - accuracies[i-1])
        changes.append(change)
    
    if not changes:
        return 0.5
    
    # Convergence is inverse of total change
    # Small changes = high convergence
    total_change = sum(changes)
    max_possible_change = len(changes) * 100  # Each could change by 100%
    
    convergence = 1 - (total_change / max_possible_change) if max_possible_change > 0 else 0.5
    
    return max(0, min(1, convergence))


def _detect_unusual_pattern(depth_comparison: List[Dict]) -> bool:
    """
    Detect unusual patterns in depth-accuracy relationship.
    Normal: accuracy increases slightly with depth
    Unusual: accuracy jumps dramatically or decreases
    """
    if len(depth_comparison) < 2:
        return False
    
    accuracies = [d["accuracy"] for d in depth_comparison]
    
    # Check for dramatic jumps (>15% between depths)
    for i in range(1, len(accuracies)):
        if abs(accuracies[i] - accuracies[i-1]) > 15:
            return True
    
    # Check if very high accuracy at deep depth but not at shallow
    if len(accuracies) >= 2:
        shallow = accuracies[0]
        deep = accuracies[-1]
        
        # Suspicious if deep is very high (>90) but shallow is moderate (<75)
        if deep > 90 and shallow < 75:
            return True
    
    return False


# Tool schema for LLM
TOOL_MULTI_DEPTH_ANALYZE = {
    "type": "function",
    "function": {
        "name": "multi_depth_analyze",
        "description": "Analyze a game at multiple Stockfish depths and compare results. Useful for detecting suspiciously accurate play where performance increases abnormally with deeper analysis.",
        "parameters": {
            "type": "object",
            "properties": {
                "pgn": {
                    "type": "string",
                    "description": "PGN string of the game to analyze"
                },
                "depths": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Depths to analyze at (default: [10, 20, 30])",
                    "default": [10, 20, 30]
                },
                "focus_side": {
                    "type": "string",
                    "enum": ["white", "black", "both"],
                    "description": "Which side to focus analysis on",
                    "default": "both"
                }
            },
            "required": ["pgn"]
        }
    }
}

