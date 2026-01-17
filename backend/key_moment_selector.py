"""
Key Moment Selector - Statistics-first selection of key moments for game reviews.

This module selects the most relevant key moments based on:
1. Significant statistics (low accuracy tags, phase weaknesses, preferences)
2. Query context (general review vs "how did I lose?" vs "every mistake")
3. Player focus (own moves only unless explicitly requested)
"""

from typing import List, Dict, Any, Tuple, Optional, Set
from collections import defaultdict
import re
import asyncio
import json
import concurrent.futures


def determine_moment_count(query_type: str, total_moments: int) -> int:
    """Determine target number of key moments based on query type."""
    if query_type == "comprehensive":
        return total_moments  # Show all
    elif query_type == "loss_diagnosis":
        return min(5, total_moments)  # Just the relevant ending part
    elif query_type == "specific":
        return min(10, total_moments)
    else:  # general
        return min(12, max(8, total_moments // 2))  # 8-12 optimal


# ============================================================================
# LOSS TYPE DIAGNOSIS
# ============================================================================

def diagnose_loss_type(
    game_result: str,
    ply_records: List[Dict],
    player_color: str,
    statistics: Dict,
    game_metadata: Dict = None
) -> Optional[Dict]:
    """
    Diagnose how the player lost (if they lost).
    
    Returns None if not a loss, otherwise a dict with:
        - loss_type: timeout, single_critical_blunder, multiple_blunders, 
                     time_pressure, tag_blindspot, gradual_decline
        - detail: Human-readable explanation
        - key_moves: List of relevant move plys
    """
    # Check if it's a loss
    if not game_result:
        return None
    
    result_lower = game_result.lower()
    is_loss = any([
        result_lower == "loss",
        (result_lower == "0-1" and player_color == "white"),
        (result_lower == "1-0" and player_color == "black"),
        "resign" in result_lower and player_color in result_lower,
    ])
    
    if not is_loss:
        return None
    
    # Get player's records only
    player_records = [r for r in ply_records if r.get("side_moved") == player_color]
    
    if not player_records:
        return {"loss_type": "unknown", "detail": "No player moves found", "key_moves": []}
    
    blunders = [r for r in player_records if r.get("category") == "blunder"]
    mistakes = [r for r in player_records if r.get("category") == "mistake"]
    
    # Check termination field FIRST (most reliable)
    termination = ""
    time_control = ""
    if game_metadata:
        termination = game_metadata.get("termination", "").lower()
        time_control = game_metadata.get("time_control", "").lower()
    
    # Determine time thresholds based on time control
    is_blitz = "blitz" in time_control or "+" in time_control  # e.g., "3+2"
    slow_threshold = 15 if is_blitz else 30  # Blitz: 15s is slow, Rapid/Classical: 30s
    time_pressure_threshold = 3 if is_blitz else 5  # Blitz: <3s is pressure, Rapid: <5s
    
    # Check for timeout (check termination field first)
    if "time" in termination or "timeout" in termination:
        # Find slow moves that contributed to time trouble
        slow_moves = [r for r in player_records if (r.get("time_spent_s") or 0) > slow_threshold]
        # Find time pressure errors
        time_pressure_errors = [
            r for r in (blunders + mistakes)
            if (r.get("time_spent_s") or 999) < time_pressure_threshold
            and r.get("accuracy_pct", 100) < 70
        ]
        
        return {
            "loss_type": "timeout",
            "detail": f"Lost on time. {'You spent significant time on ' + str(len(slow_moves)) + ' moves' if slow_moves else ''}",
            "key_moves": [r["ply"] for r in slow_moves[:3]] + [r["ply"] for r in time_pressure_errors[:2]],
            "time_analysis": {
                "slow_moves": [{"ply": r["ply"], "time_spent": r.get("time_spent_s", 0)} for r in slow_moves[:5]],
                "time_pressure_moves": [{"ply": r["ply"], "time_spent": r.get("time_spent_s", 0), "cp_loss": r.get("cp_loss", 0)} for r in time_pressure_errors[:5]],
                "total_time_spent": sum(r.get("time_spent_s", 0) for r in player_records)
            }
        }
    
    # Check for timeout (very fast moves at end) - fallback if termination not available
    last_5 = player_records[-5:] if len(player_records) >= 5 else player_records
    fast_final_moves = [r for r in last_5 if (r.get("time_spent_s") or 999) < 1]
    if len(fast_final_moves) >= 3:
        return {
            "loss_type": "timeout",
            "detail": "Lost on time - multiple moves under 1 second at the end",
            "key_moves": [r["ply"] for r in fast_final_moves],
            "time_analysis": {
                "slow_moves": [],
                "time_pressure_moves": [{"ply": r["ply"], "time_spent": r.get("time_spent_s", 0)} for r in fast_final_moves],
                "total_time_spent": sum(r.get("time_spent_s", 0) for r in player_records)
            }
        }
    
    # Single critical blunder
    if len(blunders) == 1 and blunders[0].get("cp_loss", 0) > 200:
        return {
            "loss_type": "single_critical_blunder",
            "detail": f"Single critical blunder on move {(blunders[0]['ply'] + 1) // 2} lost the game",
            "key_moves": [blunders[0]["ply"]],
            "blunder_ply": blunders[0]["ply"]
        }
    
    # Multiple blunders
    if len(blunders) >= 2:
        return {
            "loss_type": "multiple_blunders",
            "detail": f"{len(blunders)} blunders throughout the game",
            "key_moves": [b["ply"] for b in blunders]
        }
    
    # Time pressure errors (using time-control-aware thresholds)
    time_pressure_errors = [
        r for r in (blunders + mistakes)
        if (r.get("time_spent_s") or 999) < time_pressure_threshold
        and r.get("accuracy_pct", 100) < 70
    ]
    if len(time_pressure_errors) >= 2:
        return {
            "loss_type": "time_pressure",
            "detail": f"{len(time_pressure_errors)} errors made under time pressure (< {time_pressure_threshold} seconds)",
            "key_moves": [r["ply"] for r in time_pressure_errors],
            "time_analysis": {
                "slow_moves": [],
                "time_pressure_moves": [{"ply": r["ply"], "time_spent": r.get("time_spent_s", 0), "cp_loss": r.get("cp_loss", 0)} for r in time_pressure_errors[:5]],
                "total_time_spent": sum(r.get("time_spent_s", 0) for r in player_records)
            }
        }
    
    # Tag-based blindspot
    tag_stats = statistics.get("performance_by_tags", {})
    worst_tags = tag_stats.get("bottom_performing", [])
    if worst_tags:
        try:
            worst_acc = worst_tags[0].get("accuracy")
            worst_acc_f = float(worst_acc) if worst_acc is not None else 100.0
        except Exception:
            worst_acc_f = 100.0
    else:
        worst_acc_f = 100.0
    if worst_tags and worst_acc_f < 60:
        worst_tag = worst_tags[0]
        try:
            acc_f = float(worst_tag.get("accuracy")) if worst_tag.get("accuracy") is not None else 0.0
        except Exception:
            acc_f = 0.0
        return {
            "loss_type": "tag_blindspot",
            "detail": f"Low accuracy ({acc_f:.0f}%) in {worst_tag.get('tag', 'unknown')} positions",
            "tag": worst_tag.get("tag", "unknown"),
            "key_moves": []  # Will be filled by selector
        }
    
    # Gradual decline (accumulation of small errors)
    inaccuracies = [r for r in player_records if r.get("category") == "inaccuracy"]
    if len(inaccuracies) + len(mistakes) >= 5:
        return {
            "loss_type": "gradual_decline",
            "detail": f"Accumulated {len(inaccuracies)} inaccuracies and {len(mistakes)} mistakes throughout",
            "key_moves": [r["ply"] for r in (inaccuracies + mistakes)[:5]]
        }
    
    return {
        "loss_type": "gradual_decline",
        "detail": "Accumulated small errors throughout the game",
        "key_moves": []
    }


# ============================================================================
# STATISTICS ANALYSIS
# ============================================================================

def calculate_tag_performance_score(accuracy: float, count: int, avg_accuracy: float) -> float:
    """
    Calculate a performance score that combines accuracy deficit with frequency.
    
    Higher score = more important to report.
    
    Formula: (accuracy_deficit * frequency_weight)
    - accuracy_deficit: How much below average (0-100 scale)
    - frequency_weight: log(count) to give diminishing returns but still reward frequency
    
    Example:
    - Tag with 60% accuracy, 20 occurrences, 80% avg: (20 * log(20)) = 20 * 3.0 = 60
    - Tag with 40% accuracy, 1 occurrence, 80% avg: (40 * log(1)) = 40 * 0 = 0
    """
    import math
    
    accuracy_deficit = max(0, avg_accuracy - accuracy)
    
    # Frequency weight: log(count + 1) to avoid log(0)
    # This gives diminishing returns but still rewards frequency
    frequency_weight = math.log(count + 1)
    
    # Normalize frequency weight (log(50) ≈ 3.9, so scale to 0-1 range)
    frequency_weight_normalized = min(1.0, frequency_weight / 3.9)
    
    # Combine: deficit * (0.5 + 0.5 * frequency_weight)
    # This ensures even low-frequency tags with very bad accuracy get some weight
    # But high-frequency tags get more weight
    performance_score = accuracy_deficit * (0.5 + 0.5 * frequency_weight_normalized)
    
    return performance_score


def identify_significant_statistics(statistics: Dict) -> List[Dict]:
    """
    Find statistics that are outliers and warrant highlighting.
    
    Returns list of significant stats with type, tag/phase, and severity.
    Uses performance score to prioritize tags by both accuracy deficit and frequency.
    """
    significant = []
    avg_accuracy = statistics.get("avg_accuracy", 80)
    
    # Check tag accuracy
    tag_stats = statistics.get("performance_by_tags", {})
    all_tags = tag_stats.get("all_tags", [])
    
    for tag_stat in all_tags:
        accuracy = tag_stat.get("accuracy", 100)
        count = tag_stat.get("move_count", 0)
        
        # Only consider tags with sufficient frequency (at least 3 occurrences)
        if count < 3:
            continue
        
        # Check for unusually LOW performance (significantly below average)
        accuracy_deficit = avg_accuracy - accuracy
        if accuracy_deficit > 10:  # At least 10% below average
            performance_score = calculate_tag_performance_score(accuracy, count, avg_accuracy)
            if performance_score > 5:  # Minimum performance score threshold
                significant.append({
                    "type": "tag_accuracy",
                    "tag": tag_stat.get("tag", ""),
                    "accuracy": accuracy,
                    "count": count,
                    "performance_score": performance_score,
                    "severity": "critical" if accuracy < 50 else "moderate",
                    "direction": "low"  # Unusually low performance
                })
        
        # Check for unusually HIGH performance (significantly above average)
        accuracy_surplus = accuracy - avg_accuracy
        if accuracy_surplus > 15 and accuracy > 85:  # At least 15% above average and >85% accuracy
            significant.append({
                "type": "tag_accuracy",
                "tag": tag_stat.get("tag", ""),
                "accuracy": accuracy,
                "count": count,
                "performance_score": 0,  # Not a weakness, so no performance score
                "severity": "positive",
                "direction": "high"  # Unusually high performance
            })
    
    # Check tag preferences - only include if they're unusual (significant)
    tag_preferences = tag_stats.get("tag_preferences", {})
    for tag_name, pref_data in tag_preferences.items():
        if not pref_data.get("significant", False):
            continue
        
        signal = pref_data.get("preference_signal", "neutral")
        if signal == "neutral":
            continue
        
        strength = pref_data.get("preference_strength", 0)
        # Only include if preference strength is significant (>0.3)
        # AND the accuracy when creating/removing is unusually low
        if strength > 0.3:
            created_acc = pref_data.get("created_accuracy", 100)
            removed_acc = pref_data.get("removed_accuracy", 100)
            created_count = pref_data.get("created_count", 0)
            removed_count = pref_data.get("removed_count", 0)
            
            # Check if the accuracy when creating/removing is unusually low
            if signal == "seeks" and created_acc < avg_accuracy - 10 and created_count >= 3:
                significant.append({
                    "type": "tag_preference",
                    "tag": tag_name,
                    "pattern": signal,  # "seeks"
                    "created_accuracy": created_acc,
                    "removed_accuracy": removed_acc,
                    "strength": strength,
                    "count": created_count,
                    "severity": "moderate",
                    "direction": "negative"  # Unusual negative preference
                })
            elif signal == "avoids" and removed_acc < avg_accuracy - 10 and removed_count >= 3:
                significant.append({
                    "type": "tag_preference",
                    "tag": tag_name,
                    "pattern": signal,  # "avoids"
                    "created_accuracy": created_acc,
                    "removed_accuracy": removed_acc,
                    "strength": strength,
                    "count": removed_count,
                    "severity": "moderate",
                    "direction": "negative"  # Unusual negative preference
                })
    
    # Check phase weaknesses
    phase_stats = statistics.get("phase_stats", {})
    if phase_stats:
        phase_accuracies = []
        for phase, data in phase_stats.items():
            if data.get("move_count", 0) > 0:
                phase_accuracies.append((phase, data.get("accuracy", 100)))
        
        if len(phase_accuracies) >= 2:
            sorted_phases = sorted(phase_accuracies, key=lambda x: x[1])
            weakest = sorted_phases[0]
            strongest = sorted_phases[-1]
            gap = strongest[1] - weakest[1]
            
            # > 15% gap between phases is significant
            if gap > 15 and weakest[1] < 80:
                significant.append({
                    "type": "phase_weakness",
                    "phase": weakest[0],
                    "accuracy": weakest[1],
                    "gap": gap,
                    "strongest_phase": strongest[0],
                    "severity": "critical" if gap > 25 else "moderate"
                })
    
    # Sort by performance_score (highest first), then by severity, then by accuracy
    severity_order = {"critical": 0, "moderate": 1, "minor": 2}
    significant.sort(key=lambda x: (
        -x.get("performance_score", 0) if x.get("type") == "tag_accuracy" else 0,  # Negative for descending
        severity_order.get(x.get("severity", "minor"), 2),
        x.get("accuracy", 100)
    ))
    
    return significant


# ============================================================================
# MOMENT FINDING HELPERS
# ============================================================================

def _extract_tag_names(tags: List) -> Set[str]:
    """Extract tag names from tag list (handles both dict and string formats)."""
    names = set()
    for tag in tags:
        if isinstance(tag, dict):
            name = tag.get("tag_name", tag.get("name", tag.get("tag", "")))
        elif isinstance(tag, str):
            name = tag
        else:
            continue
        if name:
            names.add(name)
    return names


def find_errors_in_positions_with_tag(
    all_key_moments: List[Dict],
    tag_name: str
) -> List[Dict]:
    """Find error moves where the position had the specified tag."""
    matches = []
    
    for moment in all_key_moments:
        # Only consider errors
        if moment.get("primary_label") not in ["blunder", "mistake", "inaccuracy"]:
            continue
        
        # Check if tag was present in position before move
        tags_before = moment.get("tags_before", [])
        tag_names = _extract_tag_names(tags_before)
        
        if tag_name in tag_names or any(tag_name in t for t in tag_names):
            matches.append(moment)
    
    return matches


def find_missed_best_moves_with_tag(
    all_key_moments: List[Dict],
    tag_name: str
) -> List[Dict]:
    """Find moves where best move would have created the tag but wasn't played."""
    matches = []
    
    for moment in all_key_moments:
        # Check if best move had the tag
        best_move_tags = moment.get("best_move_tags", [])
        best_tag_names = _extract_tag_names(best_move_tags)
        
        # Check if played move didn't have it
        tags_after = moment.get("tags_after", [])
        played_tag_names = _extract_tag_names(tags_after)
        
        # Best move had tag but played move doesn't
        if (tag_name in best_tag_names or any(tag_name in t for t in best_tag_names)):
            if tag_name not in played_tag_names and not any(tag_name in t for t in played_tag_names):
                matches.append(moment)
    
    return matches


def find_preference_pattern_moves(
    all_key_moments: List[Dict],
    tag_name: str,
    pattern: str  # "seeks" or "avoids"
) -> List[Dict]:
    """Find moves matching a tag preference pattern."""
    matches = []
    
    for moment in all_key_moments:
        tags_before = _extract_tag_names(moment.get("tags_before", []))
        tags_after = _extract_tag_names(moment.get("tags_after", []))
        
        tag_in_before = tag_name in tags_before or any(tag_name in t for t in tags_before)
        tag_in_after = tag_name in tags_after or any(tag_name in t for t in tags_after)
        
        if pattern == "seeks":
            # Player seeks this tag: created it (not before, is after)
            if not tag_in_before and tag_in_after:
                matches.append(moment)
        elif pattern == "avoids":
            # Player avoids this tag: removed it (was before, not after)
            if tag_in_before and not tag_in_after:
                matches.append(moment)
    
    return matches


def find_errors_in_phase(
    all_key_moments: List[Dict],
    phase: str
) -> List[Dict]:
    """Find error moves in a specific game phase."""
    matches = []
    
    for moment in all_key_moments:
        record = moment.get("record", {})
        if record.get("phase") != phase:
            continue
        
        if moment.get("primary_label") in ["blunder", "mistake", "inaccuracy"]:
            matches.append(moment)
    
    return matches


def select_general_moments(
    all_key_moments: List[Dict],
    player_color: str,
    include_opponent_moves: bool
) -> List[Dict]:
    """Select general key moments for a balanced review."""
    selected = []
    
    for moment in all_key_moments:
        side = moment.get("side")
        labels = moment.get("labels", [])
        primary = moment.get("primary_label", "")
        
        # If we're reviewing both sides, treat both as eligible
        is_focus_side = (player_color == "both") or (side == player_color)

        # Always include focus side's significant moments
        if is_focus_side:
            if primary in ["blunder", "mistake", "critical_good_move", "advantage_shift"]:
                selected.append(moment)
            elif "phase_transition" in labels:
                selected.append(moment)
        
        # Include non-focus side's major blunders if requested or if they're game-changing
        elif include_opponent_moves or primary == "blunder":
            if primary == "blunder" and moment.get("advantage_swing", 0) > 200:
                selected.append(moment)
    
    return selected


def select_loss_explanation_moments(
    all_key_moments: List[Dict],
    game_result: str,
    player_color: str
) -> List[Dict]:
    """Select moments that explain the loss."""
    selected = []
    
    # Focus on player's errors and opponent's decisive moves
    for moment in all_key_moments:
        side = moment.get("side")
        primary = moment.get("primary_label", "")
        labels = moment.get("labels", [])
        
        if side == player_color:
            # Player's errors
            if primary in ["blunder", "mistake"]:
                selected.append(moment)
            # Missed wins
            elif "missed_critical_win" in labels:
                selected.append(moment)
        else:
            # Opponent's winning moves
            if "advantage_shift" in labels and moment.get("advantage_swing", 0) > 150:
                selected.append(moment)
    
    # Sort by ply to show chronological order of the collapse
    selected.sort(key=lambda x: x.get("ply", 0))
    
    return selected


# ============================================================================
# LLM-BASED MOMENT SELECTION
# ============================================================================

def _build_ply_summary(ply_records: List[Dict], player_color: str) -> List[Dict]:
    """
    Build a condensed summary of ply records for LLM consumption.
    
    Returns list of dicts with key info about each move.
    """
    summary = []
    for record in ply_records:
        ply = record.get("ply", 0)
        san = record.get("san", "?")
        side = record.get("side_moved", "")
        category = record.get("category", "")
        cp_loss = record.get("cp_loss", 0)
        time_spent = record.get("time_spent_s", 0)
        phase = record.get("phase", "")
        accuracy = record.get("accuracy_pct", 100)
        
        # Get key tags (simplified)
        raw_before = record.get("raw_before", {})
        tags = raw_before.get("tags", [])
        key_tags = []
        for t in tags[:5]:  # Limit to 5 tags
            if isinstance(t, dict):
                tag_name = t.get("tag_name", "")
                # Simplify tag names
                if "fork" in tag_name: key_tags.append("fork")
                elif "pin" in tag_name: key_tags.append("pin")
                elif "check" in tag_name: key_tags.append("check")
                elif "threat" in tag_name: key_tags.append("threat")
                elif "pawn" in tag_name and "passed" in tag_name: key_tags.append("passed_pawn")
                elif "center" in tag_name: key_tags.append("center")
                elif "king" in tag_name and "safety" in tag_name: key_tags.append("king_safety")
        
        # Get eval
        engine = record.get("engine", {})
        eval_before = engine.get("eval_before_cp", 0)
        eval_after = engine.get("played_eval_after_cp", 0)
        eval_change = abs(eval_after - eval_before) if eval_before and eval_after else 0
        
        is_player = (player_color == "both") or (side == player_color)

        summary.append({
            "ply": ply,
            "move": san,
            "side": side,
            "is_player": is_player,
            "category": category,
            "cp_loss": round(cp_loss),
            "time_s": round(time_spent, 1) if time_spent else 0,
            "phase": phase,
            "accuracy": round(accuracy),
            "eval_change": round(eval_change),
            "tags": key_tags
        })
    
    return summary


async def select_moments_with_llm(
    interpreter_intent: str,
    user_query: str,
    ply_records: List[Dict],
    player_color: str,
    game_metadata: Dict,
    openai_client,
    llm_router=None,
) -> Dict:
    """
    Use LLM to select which moments to include based on ANY query.
    
    Returns:
        {
            "selected_plies": [19, 33, 47],  # Specific plies to show
            "narrative_focus": "Brief opening sentence",
            "query_intent": "loss_diagnosis" | "time_analysis" | "custom" | etc.,
            "selection_rationale": "Why these moves were selected"
        }
    """
    if not openai_client and not llm_router:
        # Fallback to default selection
        return {
            "selected_plies": [],
            "narrative_focus": "General game review",
            "query_intent": "general",
            "selection_rationale": "No LLM available"
        }
    
    # Build condensed ply summary
    ply_summary = _build_ply_summary(ply_records, player_color)
    
    # Build summary table as text
    summary_lines = ["| Ply | Move | Side | Player? | Category | CP Loss | Time | Phase | Accuracy | Eval Δ | Tags |"]
    summary_lines.append("|-----|------|------|---------|----------|---------|------|-------|----------|--------|------|")
    
    for p in ply_summary:
        tags_str = ",".join(p["tags"][:3]) if p["tags"] else "-"
        is_player = "✓" if p["is_player"] else ""
        summary_lines.append(
            f"| {p['ply']} | {p['move']} | {p['side']} | {is_player} | {p['category']} | {p['cp_loss']} | {p['time_s']}s | {p['phase']} | {p['accuracy']}% | {p['eval_change']} | {tags_str} |"
        )
    
    summary_table = "\n".join(summary_lines)
    
    # Game metadata
    result = game_metadata.get("result", "")
    termination = game_metadata.get("termination", "")
    time_control = game_metadata.get("time_control", "")
    
    prompt = f"""You are selecting key moments from a chess game to show the user based on their query.

**User's Intent (from interpreter):** {interpreter_intent}
**Original Query:** {user_query}

**Game Info:**
- Result: {result}
- Termination: {termination}
- Time Control: {time_control}
- Player Color: {player_color}
- Total Moves: {len(ply_records)}

**Available Moves:**
{summary_table}

**Your Task:**
Select the most relevant moves to show the user. Consider:
1. What the user is asking about
2. Which moves best answer their question
3. Typically 3-12 moves is appropriate (fewer for specific questions, more for general reviews)
4. Decide whether to include opponent moves based on the user's query and the interpreter intent

**Return JSON:**
```json
{{
    "selected_plies": [list of ply numbers to show],
    "narrative_focus": "One sentence describing what to emphasize in the response",
    "query_intent": "loss_diagnosis|time_analysis|blunder_review|best_moves|tactical_moments|advantage_shifts|custom|general",
    "include_opponent_moves": true,
    "target_count": 10,
    "moment_mix": {{"highlights": 0.4, "errors": 0.4, "shifts": 0.2}},
    "selection_rationale": "Brief explanation of why these moves were selected"
}}
```

Examples:
- "why did I lose?" → Select the key errors that led to the loss (3-5 moves)
- "what moves took the longest?" → Select moves sorted by time_s (5-10 moves)
- "show all my blunders" → Select all moves with category="blunder"
- "where did I have a passed pawn?" → Select moves with "passed_pawn" in tags
- "general review" → Select a balanced mix of key moments (8-12 moves)
"""
    
    try:
        if llm_router:
            result = llm_router.complete_json(
                session_id="default",
                stage="key_moment_selector",
                system_prompt="You are a chess game analyzer. Select the most relevant moves to show based on the user's query. Return only valid JSON.",
                user_text=prompt,
                temperature=0.3,
                model="gpt-5",
            )
        else:
            loop = asyncio.get_event_loop()
            
            def call_openai():
                return openai_client.chat.completions.create(
                    model="gpt-5",
                    messages=[
                        {"role": "system", "content": "You are a chess game analyzer. Select the most relevant moves to show based on the user's query. Return only valid JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3
                )
            
            with concurrent.futures.ThreadPoolExecutor() as pool:
                response = await asyncio.wait_for(
                    loop.run_in_executor(pool, call_openai),
                    timeout=8.0
                )
            
            content = response.choices[0].message.content
            
            # Extract JSON from response (handle markdown code blocks)
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            result = json.loads(content.strip())
        
        # Validate result
        if "selected_plies" not in result:
            result["selected_plies"] = []
        if "narrative_focus" not in result:
            result["narrative_focus"] = interpreter_intent or "Game review"
        if "query_intent" not in result:
            result["query_intent"] = "custom"
        if "include_opponent_moves" not in result:
            result["include_opponent_moves"] = False
        if "target_count" not in result:
            result["target_count"] = len(result.get("selected_plies", [])) or 10
        if "moment_mix" not in result:
            result["moment_mix"] = {"highlights": 0.4, "errors": 0.4, "shifts": 0.2}
        if "selection_rationale" not in result:
            result["selection_rationale"] = ""
        
        print(f"   🎯 LLM selected {len(result['selected_plies'])} moments: {result['selected_plies'][:10]}...")
        print(f"      Intent: {result['query_intent']}, Focus: {result['narrative_focus'][:50]}...")
        
        return result
        
    except Exception as e:
        print(f"⚠️ LLM moment selection failed: {e}")
        # Return empty selection, will fallback to statistics-based
        return {
            "selected_plies": [],
            "narrative_focus": interpreter_intent or "Game review",
            "query_intent": "general",
            "selection_rationale": f"LLM selection failed: {e}"
        }


# ============================================================================
# MAIN SELECTION FUNCTION
# ============================================================================

async def select_key_moments_by_statistics(
    all_key_moments: List[Dict],
    statistics: Dict,
    user_query: str,
    game_result: str,
    player_color: str,
    total_games: int,
    ply_records: List[Dict] = None,
    game_metadata: Dict = None,
    interpreter_intent: str = "",
    openai_client = None
) -> Tuple[List[Dict], Dict]:
    """
    Select key moments based on LLM interpretation and statistics.
    
    Args:
        all_key_moments: All detected key moments (both sides)
        statistics: Aggregated statistics from the game(s)
        user_query: Original user query for context
        game_result: Game result (win/loss/draw)
        player_color: Player's color
        total_games: Number of games being reviewed
        ply_records: Full ply records for filtering (optional)
        game_metadata: Game metadata including termination, time_control (optional)
        interpreter_intent: Intent determined by the main interpreter
        openai_client: OpenAI client for LLM-based selection
    
    Returns:
        Tuple of:
            - selected_moments: List of key moments to include
            - selection_rationale: Dict explaining selections
    """
    # Default ply_records if not provided
    if ply_records is None:
        ply_records = []
    
    # 1. Try LLM-based moment selection first (handles ANY query flexibly)
    llm_selection = None
    if openai_client and ply_records and (interpreter_intent or user_query):
        llm_selection = await select_moments_with_llm(
            interpreter_intent=interpreter_intent,
            user_query=user_query,
            ply_records=ply_records,
            player_color=player_color,
            game_metadata=game_metadata or {},
            openai_client=openai_client
        )
    
    # 2. If LLM returned specific plies, use those
    if llm_selection and llm_selection.get("selected_plies"):
        selected_plies = llm_selection["selected_plies"]
        query_intent = llm_selection.get("query_intent", "custom")
        narrative_focus = llm_selection.get("narrative_focus", interpreter_intent or "Game review")
        include_opponent_moves = bool(llm_selection.get("include_opponent_moves", False))
        target_count = llm_selection.get("target_count", len(selected_plies))
        moment_mix = llm_selection.get("moment_mix") or {"highlights": 0.4, "errors": 0.4, "shifts": 0.2}
        
        # Build moments from selected plies
        selected_moments = []
        for ply in selected_plies:
            # Find moment in all_key_moments
            moment = next((m for m in all_key_moments if m.get("ply") == ply), None)
            if moment:
                selected_moments.append(moment)
            else:
                # Create moment from ply_record if not in key moments
                record = next((r for r in ply_records if r.get("ply") == ply), None)
                if record:
                    selected_moments.append({
                        "ply": ply,
                        "side": record.get("side_moved"),
                        "labels": [record.get("category", "")],
                        "primary_label": record.get("category", ""),
                        "cp_loss": record.get("cp_loss", 0),
                        "record": record
                    })

        # Enforce include_opponent_moves policy deterministically
        if player_color != "both" and not include_opponent_moves:
            selected_moments = [m for m in selected_moments if m.get("side") == player_color]
        
        # Get loss diagnosis only if the selector explicitly chose loss_diagnosis
        loss_diagnosis = None
        if query_intent == "loss_diagnosis" and game_result:
            loss_diagnosis = diagnose_loss_type(
                game_result, ply_records, player_color, statistics, game_metadata
            )
        
        selection_rationale = {
            "query_intent": query_intent,
            "interpreter_intent": interpreter_intent,
            "narrative_focus": narrative_focus,
            "interpretation_method": "llm",
            "target_count": target_count,
            "include_opponent_moves": include_opponent_moves,
            "moment_mix": moment_mix,
            "moments_selected": len(selected_moments),
            "moments_available": len(all_key_moments),
            "loss_diagnosis": loss_diagnosis,
            "llm_rationale": llm_selection.get("selection_rationale", "")
        }
        
        return selected_moments, selection_rationale
    
    # 3. Fallback: Statistics-based selection (original logic)
    print("   ⚠️ LLM selection unavailable, using statistics-based fallback")
    
    query_intent = "general"
    filter_criteria = {}
    narrative_focus = interpreter_intent or "General game review"
    interpretation_method = "statistics"
    include_opponent_moves = (player_color == "both")
    moment_mix = {"highlights": 0.4, "errors": 0.4, "shifts": 0.2}
    
    # Determine parameters (no query heuristics here)
    target_count = determine_moment_count(query_intent, len(all_key_moments))
    loss_diagnosis = None
    
    # 4. Deterministic stats-based selection (no query heuristics)
    eligible_key_moments = (
        all_key_moments if player_color == "both"
        else [m for m in all_key_moments if m.get("side") == player_color]
    )
    
    # 2. Identify significant statistics
    significant_stats = identify_significant_statistics(statistics)
    
    # 3. Build candidate moments linked to statistics
    stat_linked_moments: List[Tuple[Dict, Optional[Dict]]] = []  # (moment, stat_that_linked_it)
    
    for stat in significant_stats:
        if stat["type"] == "tag_accuracy":
            # Find errors in positions with this tag
            tag_errors = find_errors_in_positions_with_tag(eligible_key_moments, stat["tag"])
            for moment in tag_errors:
                stat_linked_moments.append((moment, stat))
            
            # Find missed best moves that would have this tag
            missed = find_missed_best_moves_with_tag(eligible_key_moments, stat["tag"])
            for moment in missed:
                stat_linked_moments.append((moment, stat))
        
        elif stat["type"] == "tag_preference":
            pref_moves = find_preference_pattern_moves(
                eligible_key_moments, stat["tag"], stat["pattern"]
            )
            for moment in pref_moves:
                stat_linked_moments.append((moment, stat))
        
        elif stat["type"] == "phase_weakness":
            phase_errors = find_errors_in_phase(eligible_key_moments, stat["phase"])
            for moment in phase_errors:
                stat_linked_moments.append((moment, stat))
    
    # 4. Add general key moments
    general_moments = select_general_moments(eligible_key_moments, player_color, include_opponent_moves)
    for moment in general_moments:
        # Only add if not already linked to a stat
        if not any(m[0].get("ply") == moment.get("ply") for m in stat_linked_moments):
            stat_linked_moments.append((moment, None))
    
    # 5. Deduplicate by ply
    seen_plys = set()
    deduplicated: List[Tuple[Dict, Optional[Dict]]] = []
    
    for moment, stat in stat_linked_moments:
        ply = moment.get("ply")
        if ply not in seen_plys:
            deduplicated.append((moment, stat))
            seen_plys.add(ply)
    
    # 6. Sort by priority: stat-linked first, then by severity, then by ply
    def priority_key(item: Tuple[Dict, Optional[Dict]]) -> Tuple[int, int, int]:
        moment, stat = item
        # Has stat link = higher priority (lower number)
        stat_priority = 0 if stat else 1
        # Severity: blunder > mistake > others
        primary = moment.get("primary_label", "")
        severity_map = {"blunder": 0, "mistake": 1, "missed_critical_win": 2, "advantage_shift": 3}
        severity = severity_map.get(primary, 5)
        # Ply for chronological tiebreaker
        ply = moment.get("ply", 9999)
        return (stat_priority, severity, ply)
    
    deduplicated.sort(key=priority_key)
    
    # 7. Limit to target count
    final_selection = deduplicated[:target_count]
    
    # 8. Sort final selection chronologically
    final_selection.sort(key=lambda x: x[0].get("ply", 0))
    
    # 9. Build rationale
    selection_rationale = {
        "query_intent": query_intent,
        "interpreter_intent": interpreter_intent,  # Original interpreter text
        "filter_criteria": filter_criteria if filter_criteria else {},
        "narrative_focus": narrative_focus,
        "interpretation_method": interpretation_method,
        "target_count": target_count,
        "include_opponent_moves": include_opponent_moves,
        "moment_mix": moment_mix,
        "significant_stats": significant_stats,
        "moments_selected": len(final_selection),
        "moments_available": len(all_key_moments),
        "stat_linked_count": sum(1 for _, s in final_selection if s is not None),
        "loss_diagnosis": loss_diagnosis,
        "moment_rationales": []
    }
    
    for moment, stat in final_selection:
        rationale = {
            "ply": moment.get("ply"),
            "primary_label": moment.get("primary_label"),
            "side": moment.get("side"),
        }
        if stat:
            rationale["linked_to_stat"] = {
                "type": stat.get("type"),
                "tag": stat.get("tag"),
                "phase": stat.get("phase"),
            }
        selection_rationale["moment_rationales"].append(rationale)
    
    # Extract just the moments for return
    selected_moments = [m for m, _ in final_selection]
    
    return selected_moments, selection_rationale


# ============================================================================
# ENHANCED KEY MOMENT DETECTION
# ============================================================================

def detect_all_key_moments(
    ply_records: List[Dict],
    player_color: str = None
) -> List[Dict]:
    """
    Detect ALL key moments for both sides.
    
    This is called during game analysis to build the full list of key moments
    before the selection phase filters them based on query/statistics.
    
    Returns list of key moment dicts with:
        - ply, side, labels, primary_label
        - cp_loss, advantage_swing
        - tags_before, tags_after, best_move_tags
        - record (full ply record reference)
    """
    key_moments = []
    
    for i, record in enumerate(ply_records):
        labels = []
        side = record.get("side_moved")
        
        eval_cp = record.get("engine", {}).get("played_eval_after_cp", 0)
        eval_before = record.get("engine", {}).get("eval_before_cp", 0)
        prev_eval = ply_records[i-1].get("engine", {}).get("played_eval_after_cp", 0) if i > 0 else 0
        
        category = record.get("category", "")
        cp_loss = record.get("cp_loss", 0)
        
        # === Move Quality Labels ===
        if category == "blunder":
            labels.append("blunder")
        elif category == "mistake":
            labels.append("mistake")
        elif category == "inaccuracy":
            labels.append("inaccuracy")
        elif category == "critical_best":
            labels.append("critical_good_move")
        
        # === Advantage Shift Detection ===
        eval_swing = abs(eval_cp - prev_eval)
        if eval_swing > 100:
            labels.append("advantage_shift")
        
        # === Missed Critical Win ===
        # Dropped from winning (>300cp) to not winning (<100cp)
        if eval_before > 300 and eval_cp < 100:
            labels.append("missed_critical_win")
        elif eval_before < -300 and eval_cp > -100:
            labels.append("missed_critical_win")
        
        # === Tactical Opportunity ===
        tags_before = record.get("raw_before", {}).get("tags", [])
        tag_names_before = _extract_tag_names(tags_before)
        tactical_tags = {"fork", "pin", "skewer", "discovered_attack", "tactic"}
        if tag_names_before & tactical_tags or any(t in name for name in tag_names_before for t in tactical_tags):
            if category in ["mistake", "blunder"]:
                labels.append("tactical_opportunity")
        
        # === Phase Transition ===
        if i > 0:
            prev_phase = ply_records[i-1].get("phase", "")
            curr_phase = record.get("phase", "")
            if prev_phase != curr_phase and curr_phase:
                labels.append("phase_transition")
        
        # === Theory Exit ===
        if record.get("is_theory") == False and i > 0:
            if ply_records[i-1].get("is_theory") == True:
                labels.append("theory_exit")
        
        # === Threshold Crossings ===
        for threshold in [100, 200, 300]:
            if prev_eval < threshold <= eval_cp:
                labels.append(f"threshold_{threshold}_white")
            if prev_eval > -threshold >= eval_cp:
                labels.append(f"threshold_{threshold}_black")
        
        # Only create key moment if there are labels
        if labels:
            # Determine primary label (most severe)
            primary_priority = [
                "blunder", "missed_critical_win", "mistake", "advantage_shift",
                "critical_good_move", "inaccuracy", "tactical_opportunity",
                "phase_transition", "theory_exit"
            ]
            primary = next((l for l in primary_priority if l in labels), labels[0])
            
            key_moment = {
                "ply": record.get("ply"),
                "side": side,
                "labels": labels,
                "primary_label": primary,
                "cp_loss": cp_loss,
                "advantage_swing": eval_swing,
                "tags_before": list(_extract_tag_names(tags_before)),
                "tags_after": list(_extract_tag_names(record.get("raw_after", {}).get("tags", []))),
                "best_move_tags": list(_extract_tag_names(record.get("best_move_tags", []))),
                "record": record,
            }
            key_moments.append(key_moment)
    
    return key_moments

