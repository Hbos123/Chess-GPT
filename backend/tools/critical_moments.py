"""
Critical Moments Finder Tool
Identifies key turning points in chess games
"""

import chess
import chess.pgn
from io import StringIO
from typing import Dict, List, Optional, Literal


async def find_critical_moments(
    pgn: str,
    threshold_cp: int = 100,
    engine_queue = None,
    depth: int = 20,
    include_missed_wins: bool = True,
    include_blunders: bool = True,
    include_turning_points: bool = True
) -> Dict:
    """
    Identify critical moments in a game.
    
    Args:
        pgn: PGN string of the game
        threshold_cp: Minimum CP swing to consider critical (default 100)
        engine_queue: Stockfish engine queue
        depth: Analysis depth
        include_missed_wins: Include missed winning chances
        include_blunders: Include major blunders
        include_turning_points: Include evaluation turning points
        
    Returns:
        {
            "critical_moments": [
                {
                    "move_num": 23,
                    "fen": "r1bqk...",
                    "played": "Rxf7",
                    "best_move": "Qxd5",
                    "eval_before": 150,
                    "eval_after": -200,
                    "swing": 350,
                    "type": "blunder",
                    "description": "Loses material with Rxf7, Qxd5 maintains advantage"
                }
            ],
            "game_phases": {
                "opening_end_move": 12,
                "critical_phase": {"start": 20, "end": 35},
                "result_decided_move": 32
            },
            "total_swings": 5,
            "biggest_swing": {"move_num": 23, "swing": 350}
        }
    """
    # Parse PGN
    try:
        game = chess.pgn.read_game(StringIO(pgn))
        if not game:
            return {"error": "Could not parse PGN"}
    except Exception as e:
        return {"error": f"PGN parse error: {str(e)}"}
    
    # Collect all positions
    board = game.board()
    positions = []
    moves = []
    
    for move in game.mainline_moves():
        positions.append(board.fen())
        moves.append(move)
        board.push(move)
    
    positions.append(board.fen())  # Final position
    
    if not positions:
        return {"error": "No moves in game"}
    
    # Analyze each position
    evaluations = []
    for fen in positions:
        if engine_queue:
            try:
                result = await engine_queue.analyze(fen, depth=depth, num_lines=3)
                if result and "lines" in result and result["lines"]:
                    best_line = result["lines"][0]
                    eval_cp = best_line.get("cp", 0)
                    best_move = best_line.get("pv", [""])[0] if best_line.get("pv") else ""
                    top_moves = [
                        {"move": l.get("pv", [""])[0], "eval": l.get("cp", 0)}
                        for l in result["lines"][:3]
                    ]
                    evaluations.append({
                        "eval": eval_cp,
                        "best_move": best_move,
                        "top_moves": top_moves
                    })
                else:
                    evaluations.append({"eval": 0, "best_move": "", "top_moves": []})
            except:
                evaluations.append({"eval": 0, "best_move": "", "top_moves": []})
        else:
            evaluations.append({"eval": 0, "best_move": "", "top_moves": []})
    
    # Find critical moments
    critical_moments = []
    
    for i in range(len(moves)):
        fen_before = positions[i]
        fen_after = positions[i + 1]
        eval_before = evaluations[i]["eval"]
        eval_after = evaluations[i + 1]["eval"]
        best_move = evaluations[i]["best_move"]
        played_move = moves[i]
        
        # Normalize for side to move
        board_temp = chess.Board(fen_before)
        if board_temp.turn == chess.BLACK:
            eval_before = -eval_before
            eval_after = -eval_after
        
        # Calculate swing
        swing = eval_after - eval_before
        abs_swing = abs(swing)
        
        if abs_swing >= threshold_cp:
            # Classify moment type
            moment_type = _classify_moment(
                swing, eval_before, eval_after, threshold_cp
            )
            
            # Filter by type
            if moment_type == "blunder" and not include_blunders:
                continue
            if moment_type == "missed_win" and not include_missed_wins:
                continue
            if moment_type == "turning_point" and not include_turning_points:
                continue
            
            # Get SAN notation
            played_san = board_temp.san(played_move)
            best_san = ""
            if best_move:
                try:
                    best_san = board_temp.san(chess.Move.from_uci(best_move))
                except:
                    best_san = best_move
            
            description = _generate_description(
                moment_type, played_san, best_san, swing, eval_before
            )
            
            critical_moments.append({
                "move_num": i + 1,
                "fen": fen_before,
                "played": played_san,
                "best_move": best_san,
                "eval_before": eval_before,
                "eval_after": eval_after,
                "swing": swing,
                "type": moment_type,
                "description": description
            })
    
    # Sort by swing magnitude
    critical_moments.sort(key=lambda x: abs(x["swing"]), reverse=True)
    
    # Analyze game phases
    game_phases = _analyze_game_phases(evaluations, critical_moments)
    
    # Find biggest swing
    biggest_swing = None
    if critical_moments:
        biggest = critical_moments[0]
        biggest_swing = {"move_num": biggest["move_num"], "swing": biggest["swing"]}
    
    return {
        "critical_moments": critical_moments[:15],  # Top 15
        "game_phases": game_phases,
        "total_swings": len(critical_moments),
        "biggest_swing": biggest_swing,
        "analysis_depth": depth,
        "threshold_cp": threshold_cp
    }


def _classify_moment(swing: int, eval_before: int, eval_after: int, threshold: int) -> str:
    """Classify the type of critical moment"""
    if swing < -threshold:
        # Player worsened their position
        if eval_before > 100:
            return "blunder"
        else:
            return "mistake"
    elif swing > threshold:
        # Opponent blundered (or player made great move)
        if eval_before < -100:
            return "great_defense"
        else:
            return "opponent_blunder"
    
    # Turning point based on sign change
    if eval_before * eval_after < 0:
        return "turning_point"
    
    # Missed win
    if eval_before > 200 and eval_after < 100:
        return "missed_win"
    
    return "critical_moment"


def _generate_description(
    moment_type: str, 
    played: str, 
    best: str, 
    swing: int,
    eval_before: int
) -> str:
    """Generate human-readable description"""
    descriptions = {
        "blunder": f"Serious error with {played}. {best} was much better ({swing:+d} cp).",
        "mistake": f"Inaccuracy with {played}. {best} maintains the position ({swing:+d} cp).",
        "missed_win": f"{played} lets the advantage slip. {best} kept the win ({swing:+d} cp).",
        "opponent_blunder": f"Opponent's error gives {swing:+d} cp. Position now winning.",
        "great_defense": f"Strong defensive move {played} saves the position ({swing:+d} cp).",
        "turning_point": f"Evaluation flips with {played}. Game dynamics change ({swing:+d} cp).",
        "critical_moment": f"Important moment with {played}. {swing:+d} cp swing."
    }
    return descriptions.get(moment_type, f"{played} causes {swing:+d} cp swing.")


def _analyze_game_phases(evaluations: List[Dict], critical_moments: List[Dict]) -> Dict:
    """Analyze game phases based on evaluations"""
    phases = {
        "opening_end_move": None,
        "critical_phase": None,
        "result_decided_move": None
    }
    
    evals = [e["eval"] for e in evaluations]
    
    # Opening ends when first significant eval swing (>50 cp from 0)
    for i, ev in enumerate(evals):
        if abs(ev) > 50 and i >= 5:
            phases["opening_end_move"] = i
            break
    
    if not phases["opening_end_move"] and len(evals) > 10:
        phases["opening_end_move"] = 12  # Default
    
    # Critical phase: where most critical moments occur
    if critical_moments:
        move_nums = [m["move_num"] for m in critical_moments]
        if move_nums:
            phases["critical_phase"] = {
                "start": min(move_nums),
                "end": max(move_nums)
            }
    
    # Result decided: when eval becomes decisive (>300 cp)
    for i, ev in enumerate(evals):
        if abs(ev) > 300:
            phases["result_decided_move"] = i
            break
    
    return phases


# Tool schema for LLM
TOOL_CRITICAL_MOMENTS = {
    "type": "function",
    "function": {
        "name": "find_critical_moments",
        "description": "Identify key turning points in a chess game including blunders, missed wins, and evaluation swings. Returns detailed analysis of each critical moment.",
        "parameters": {
            "type": "object",
            "properties": {
                "pgn": {
                    "type": "string",
                    "description": "PGN string of the game to analyze"
                },
                "threshold_cp": {
                    "type": "integer",
                    "description": "Minimum CP swing to consider critical (default 100)",
                    "default": 100
                },
                "include_missed_wins": {
                    "type": "boolean",
                    "description": "Include missed winning opportunities",
                    "default": True
                },
                "include_blunders": {
                    "type": "boolean", 
                    "description": "Include major blunders",
                    "default": True
                }
            },
            "required": ["pgn"]
        }
    }
}

