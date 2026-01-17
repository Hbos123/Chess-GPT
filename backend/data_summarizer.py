"""
Data Summarizer
Compresses accumulated data to fit within LLM context limits
"""

from typing import Dict, Any, List, Optional
import json


# Approximate tokens per character (conservative estimate)
CHARS_PER_TOKEN = 4

# Maximum characters for summaries
MAX_SUMMARY_CHARS = 6000  # ~1500 tokens


def summarize_accumulated(data: Dict[str, Any], max_chars: int = MAX_SUMMARY_CHARS) -> str:
    """
    Summarize all accumulated data into a context-sized string.
    
    Args:
        data: Accumulated data from interpreter passes
        max_chars: Maximum characters for the summary
    
    Returns:
        Human-readable summary of the data
    """
    if not data:
        return "No data accumulated yet."
    
    parts = []
    remaining_chars = max_chars
    
    # Group by data type
    games_data = {}
    analysis_data = {}
    search_data = {}
    compute_data = {}
    other_data = {}
    
    for key, value in data.items():
        if "fetch" in key.lower() or "game" in key.lower():
            games_data[key] = value
        elif "analyze" in key.lower() or "analysis" in key.lower():
            analysis_data[key] = value
        elif "search" in key.lower():
            search_data[key] = value
        elif "compute" in key.lower() or "baseline" in key.lower():
            compute_data[key] = value
        else:
            other_data[key] = value
    
    # Summarize games (highest priority for review requests)
    if games_data:
        games_summary = summarize_games_data(games_data, remaining_chars // 2)
        if games_summary:
            parts.append(games_summary)
            remaining_chars -= len(games_summary)
    
    # Summarize analysis
    if analysis_data and remaining_chars > 500:
        analysis_summary = summarize_analysis_data(analysis_data, remaining_chars // 3)
        if analysis_summary:
            parts.append(analysis_summary)
            remaining_chars -= len(analysis_summary)
    
    # Summarize compute results
    if compute_data and remaining_chars > 300:
        compute_summary = summarize_compute_data(compute_data, remaining_chars // 3)
        if compute_summary:
            parts.append(compute_summary)
            remaining_chars -= len(compute_summary)
    
    # Summarize search results
    if search_data and remaining_chars > 300:
        search_summary = summarize_search_data(search_data, remaining_chars // 3)
        if search_summary:
            parts.append(search_summary)
            remaining_chars -= len(search_summary)
    
    return "\n\n".join(parts) if parts else "Data accumulated but could not be summarized."


def summarize_games_data(data: Dict[str, Any], max_chars: int) -> str:
    """Summarize fetched games data"""
    parts = ["## Fetched Games"]
    
    all_games = []
    for key, value in data.items():
        if isinstance(value, dict) and "games" in value:
            all_games.extend(value["games"])
        elif isinstance(value, list):
            all_games.extend(value)
    
    if not all_games:
        return ""
    
    parts.append(f"Total games fetched: {len(all_games)}")
    
    # Calculate stats
    wins = losses = draws = 0
    time_controls = {}
    openings = {}
    
    for game in all_games:
        result = game.get("result", "").lower()
        if "1-0" in result or "win" in result:
            wins += 1
        elif "0-1" in result or "loss" in result:
            losses += 1
        elif "1/2" in result or "draw" in result:
            draws += 1
        
        tc = game.get("time_control", "unknown")
        time_controls[tc] = time_controls.get(tc, 0) + 1
        
        opening = game.get("opening", game.get("eco", "unknown"))
        if opening and opening != "unknown":
            openings[opening] = openings.get(opening, 0) + 1
    
    if wins + losses + draws > 0:
        parts.append(f"Results: {wins}W / {draws}D / {losses}L")
    
    if time_controls:
        tc_str = ", ".join(f"{tc}: {count}" for tc, count in sorted(time_controls.items(), key=lambda x: -x[1])[:3])
        parts.append(f"Time controls: {tc_str}")
    
    if openings:
        op_str = ", ".join(f"{op}: {count}" for op, count in sorted(openings.items(), key=lambda x: -x[1])[:5])
        parts.append(f"Common openings: {op_str}")
    
    # Show sample games
    parts.append("\nSample games:")
    for game in all_games[:5]:
        game_line = _format_game_line(game)
        parts.append(f"  - {game_line}")
    
    if len(all_games) > 5:
        parts.append(f"  ... and {len(all_games) - 5} more games")
    
    summary = "\n".join(parts)
    
    # Truncate if needed
    if len(summary) > max_chars:
        summary = summary[:max_chars-20] + "\n...[truncated]"
    
    return summary


def _format_game_line(game: Dict[str, Any]) -> str:
    """Format a single game as a brief line"""
    white = game.get("white", game.get("white_player", "?"))
    black = game.get("black", game.get("black_player", "?"))
    result = game.get("result", "?")
    date = game.get("date", game.get("end_time", ""))[:10] if game.get("date") or game.get("end_time") else ""
    tc = game.get("time_control", "")
    
    line = f"{white} vs {black}: {result}"
    if tc:
        line += f" ({tc})"
    if date:
        line += f" [{date}]"
    
    return line[:100]  # Limit line length


def summarize_analysis_data(data: Dict[str, Any], max_chars: int) -> str:
    """Summarize analysis data"""
    parts = ["## Analysis Results"]
    
    for key, value in data.items():
        if not isinstance(value, dict):
            continue
        
        analysis_parts = []
        
        if "eval" in value:
            eval_val = value["eval"]
            if isinstance(eval_val, (int, float)):
                eval_str = f"+{eval_val/100:.2f}" if eval_val >= 0 else f"{eval_val/100:.2f}"
                analysis_parts.append(f"eval: {eval_str}")
        
        # CRITICAL: Extract candidate moves for move testing
        candidate_moves = []
        if "candidate_moves" in value:
            candidate_moves = value["candidate_moves"]
        elif "endpoint_response" in value and isinstance(value["endpoint_response"], dict):
            candidate_moves = value["endpoint_response"].get("candidate_moves", [])
        
        if candidate_moves:
            # Extract top 5 candidate moves with their evals
            moves_list = []
            for i, cand in enumerate(candidate_moves[:5]):
                move = cand.get("move", cand.get("move_san", "?"))
                eval_cp = cand.get("eval_cp", 0)
                eval_str = f"+{eval_cp/100:.2f}" if eval_cp >= 0 else f"{eval_cp/100:.2f}"
                moves_list.append(f"{move} ({eval_str})")
            if moves_list:
                analysis_parts.append(f"CANDIDATE MOVES: {', '.join(moves_list)}")
        
        if "best_move" in value:
            analysis_parts.append(f"best: {value['best_move']}")
        
        if "pv" in value:
            pv = value["pv"]
            if isinstance(pv, list):
                pv_str = " ".join(pv[:5])
                analysis_parts.append(f"PV: {pv_str}")
            elif isinstance(pv, str):
                analysis_parts.append(f"PV: {pv[:50]}")
        
        if "cp_loss" in value:
            analysis_parts.append(f"CP loss: {value['cp_loss']}")
        
        if "quality" in value:
            analysis_parts.append(f"quality: {value['quality']}")
        
        if analysis_parts:
            parts.append(f"  {key}: {', '.join(analysis_parts)}")
    
    summary = "\n".join(parts)
    
    if len(summary) > max_chars:
        summary = summary[:max_chars-20] + "\n...[truncated]"
    
    return summary if len(parts) > 1 else ""


def summarize_compute_data(data: Dict[str, Any], max_chars: int) -> str:
    """Summarize compute/statistics data"""
    parts = ["## Computed Statistics"]
    
    for key, value in data.items():
        if not isinstance(value, dict):
            continue
        
        if "baseline" in key.lower():
            parts.append(_summarize_baseline(value))
        elif "correlation" in key.lower():
            parts.append(_summarize_correlation(value))
        elif "anomaly" in key.lower() or "anomalies" in key.lower():
            parts.append(_summarize_anomalies(value))
        elif "complexity" in key.lower():
            parts.append(_summarize_complexity(value))
        else:
            # Generic summary
            parts.append(f"  {key}: {_truncate_dict(value, 200)}")
    
    summary = "\n".join(parts)
    
    if len(summary) > max_chars:
        summary = summary[:max_chars-20] + "\n...[truncated]"
    
    return summary if len(parts) > 1 else ""


def _summarize_baseline(data: Dict[str, Any]) -> str:
    """Summarize player baseline data"""
    lines = ["  Player Baseline:"]
    
    if "average_accuracy" in data:
        lines.append(f"    Avg accuracy: {data['average_accuracy']:.1f}%")
    if "average_cp_loss" in data:
        lines.append(f"    Avg CP loss: {data['average_cp_loss']:.1f}")
    if "games_analyzed" in data:
        lines.append(f"    Games analyzed: {data['games_analyzed']}")
    if "strength_estimate" in data:
        lines.append(f"    Estimated strength: {data['strength_estimate']}")
    
    return "\n".join(lines)


def _summarize_correlation(data: Dict[str, Any]) -> str:
    """Summarize engine correlation data"""
    lines = ["  Engine Correlation:"]
    
    if "correlation_score" in data:
        lines.append(f"    Score: {data['correlation_score']:.1f}%")
    if "top1_match_rate" in data:
        lines.append(f"    Top-1 match: {data['top1_match_rate']:.1f}%")
    if "top3_match_rate" in data:
        lines.append(f"    Top-3 match: {data['top3_match_rate']:.1f}%")
    
    return "\n".join(lines)


def _summarize_anomalies(data: Dict[str, Any]) -> str:
    """Summarize anomaly detection data"""
    lines = ["  Anomaly Detection:"]
    
    if "anomalies_found" in data:
        lines.append(f"    Anomalies found: {data['anomalies_found']}")
    if "suspicion_score" in data:
        lines.append(f"    Suspicion score: {data['suspicion_score']:.2f}")
    if "flagged_games" in data:
        count = len(data["flagged_games"]) if isinstance(data["flagged_games"], list) else data["flagged_games"]
        lines.append(f"    Flagged games: {count}")
    
    return "\n".join(lines)


def _summarize_complexity(data: Dict[str, Any]) -> str:
    """Summarize move complexity data"""
    lines = ["  Move Complexity:"]
    
    if "average_complexity" in data:
        lines.append(f"    Avg complexity: {data['average_complexity']:.2f}")
    if "complex_moves" in data:
        lines.append(f"    Complex moves: {data['complex_moves']}")
    if "simple_moves" in data:
        lines.append(f"    Simple moves: {data['simple_moves']}")
    
    return "\n".join(lines)


def summarize_search_data(data: Dict[str, Any], max_chars: int) -> str:
    """Summarize web search data"""
    parts = ["## Web Search Results"]
    
    for key, value in data.items():
        if not isinstance(value, dict):
            continue
        
        query = value.get("query", "unknown query")
        results = value.get("results", [])
        
        parts.append(f"  Query: {query[:50]}")
        
        if results:
            for r in results[:3]:
                title = r.get("title", "")[:60]
                snippet = r.get("snippet", r.get("content", ""))[:100]
                parts.append(f"    - {title}")
                if snippet:
                    parts.append(f"      {snippet}...")
    
    summary = "\n".join(parts)
    
    if len(summary) > max_chars:
        summary = summary[:max_chars-20] + "\n...[truncated]"
    
    return summary if len(parts) > 1 else ""


def _truncate_dict(d: Dict[str, Any], max_chars: int) -> str:
    """Convert dict to string and truncate"""
    try:
        s = json.dumps(d, default=str)
        if len(s) > max_chars:
            return s[:max_chars-3] + "..."
        return s
    except:
        return str(d)[:max_chars]


def estimate_tokens(text: str) -> int:
    """Estimate token count for a string"""
    return len(text) // CHARS_PER_TOKEN


def truncate_to_tokens(text: str, max_tokens: int) -> str:
    """Truncate text to approximately max_tokens"""
    max_chars = max_tokens * CHARS_PER_TOKEN
    if len(text) <= max_chars:
        return text
    return text[:max_chars-20] + "\n...[truncated]"

