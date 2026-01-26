"""
Prompt Builder for Interpreter-Driven Prompts
Builds main LLM prompts based on interpreter's data selection and response strategy
"""

from typing import Dict, Any, Tuple
from orchestration_plan import OrchestrationPlan
import json


# System-level context that should always be included
ALWAYS_INCLUDE = ["user_id", "authenticated", "mode"]


def validate_interpreter_selections(
    plan: OrchestrationPlan,
    available_data: Dict[str, Any],
    pre_executed_results: Dict[str, Any]
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Validate and filter data based on interpreter's selections.
    
    Args:
        plan: OrchestrationPlan with include_context and relevant_analyses
        available_data: Full context dictionary
        pre_executed_results: Results from pre-executed tools
        
    Returns:
        Tuple of (filtered_context, filtered_analyses)
    """
    # Always include system-level context
    filtered_context = {k: v for k, v in available_data.items() if k in ALWAYS_INCLUDE}
    
    # Add interpreter-selected context
    for key, should_include in plan.include_context.items():
        if should_include:
            if key in available_data:
                filtered_context[key] = available_data[key]
            else:
                print(f"   ⚠️ Interpreter requested context '{key}' but it's not available - ignoring")
    
    # Filter analyses based on relevant_analyses
    filtered_analyses = {}
    for analysis_key in plan.relevant_analyses:
        if analysis_key in pre_executed_results:
            filtered_analyses[analysis_key] = pre_executed_results[analysis_key]
        else:
            print(f"   ⚠️ Interpreter requested analysis '{analysis_key}' but it wasn't executed - ignoring")
    
    # Merge with interpreter's custom selected_data
    filtered_context.update(plan.selected_data)
    
    return filtered_context, filtered_analyses


def format_analyses_for_prompt(analyses: Dict[str, Any]) -> str:
    """
    Format tool execution results for inclusion in prompt.
    Extracts only relevant/key fields to avoid token bloat.
    
    Args:
        analyses: Dictionary of analysis results keyed by tool name
        
    Returns:
        Formatted string for prompt
    """
    if not analyses:
        return "No analyses selected."
    
    parts = []
    MAX_RESULT_SIZE = 2000  # Limit each result to 2k chars
    
    for tool_name, result in analyses.items():
        if isinstance(result, dict) and "error" in result:
            parts.append(f"### {tool_name} (FAILED)\nError: {result['error']}")
        elif tool_name == "analyze_position" and isinstance(result, dict):
            # Special handling for analyze_position - extract only key fields
            # This endpoint returns HUGE nested structures, we need only essentials
            summary = {
                "fen": result.get("fen", "")[:50],  # Just first 50 chars
                "eval_cp": result.get("eval_cp"),
                "best_move": result.get("best_move"),
                "phase": result.get("phase"),
                "candidate_moves": [
                    {
                        "move": c.get("move"),
                        "eval_cp": c.get("eval_cp"),
                        "pv_san": " ".join(c.get("pv_san", [])[:5]) if isinstance(c.get("pv_san"), list) else c.get("pv_san", "")[:50]
                    }
                    for c in result.get("candidate_moves", [])[:3]  # Only top 3 candidates
                ],
                # Top insights from chunk_3_most_significant (most important!)
                "top_insights_white": [
                    {
                        "insight": ins.get("insight", "")[:200],  # Truncate long insights
                        "significance_score": ins.get("significance_score")
                    }
                    for ins in result.get("white_analysis", {}).get("chunk_3_most_significant", {}).get("insights", [])[:3]  # Top 3
                ],
                "top_insights_black": [
                    {
                        "insight": ins.get("insight", "")[:200],
                        "significance_score": ins.get("significance_score")
                    }
                    for ins in result.get("black_analysis", {}).get("chunk_3_most_significant", {}).get("insights", [])[:3]  # Top 3
                ],
                # Key threats (if available)
                "threats": {
                    "white": [
                        {
                            "threat": t.get("threat", "")[:100],
                            "delta_cp": t.get("delta_cp")
                        }
                        for t in result.get("threats", {}).get("white", [])[:3]  # Top 3 threats
                    ],
                    "black": [
                        {
                            "threat": t.get("threat", "")[:100],
                            "delta_cp": t.get("delta_cp")
                        }
                        for t in result.get("threats", {}).get("black", [])[:3]  # Top 3 threats
                    ]
                } if result.get("threats") else None
            }
            # Remove None values
            summary = {k: v for k, v in summary.items() if v is not None}
            parts.append(f"### {tool_name} Results\n{json.dumps(summary, separators=(',', ':'), ensure_ascii=False)}")
        elif isinstance(result, dict):
            # For other large dicts, summarize key fields
            summary_fields = ["success", "narrative", "summary", "stats", "games_analyzed"]
            summary = {}
            for field in summary_fields:
                if field in result:
                    val = result[field]
                    # Truncate strings
                    if isinstance(val, str) and len(val) > 500:
                        val = val[:500] + "..."
                    summary[field] = val
            
            if summary:
                parts.append(f"### {tool_name} Results\n{json.dumps(summary, separators=(',', ':'), ensure_ascii=False)}")
            else:
                # Fallback: just show keys and truncate
                result_str = json.dumps(result, separators=(",", ":"), ensure_ascii=False)
                if len(result_str) > MAX_RESULT_SIZE:
                    result_str = result_str[:MAX_RESULT_SIZE] + "..."
                parts.append(f"### {tool_name} Results\n{result_str}")
        else:
            result_str = str(result)
            if len(result_str) > MAX_RESULT_SIZE:
                result_str = result_str[:MAX_RESULT_SIZE] + "..."
            parts.append(f"### {tool_name} Results\n{result_str}")
    
    return "\n\n".join(parts)


def build_interpreter_driven_prompt(
    orchestration_plan: OrchestrationPlan,
    filtered_context: Dict[str, Any],
    filtered_analyses: Dict[str, Any],
    base_capabilities: str
) -> str:
    """
    Build prompt where interpreter controls everything.
    
    Args:
        orchestration_plan: The interpreter's orchestration plan
        filtered_context: Context data selected by interpreter
        filtered_analyses: Analysis results selected by interpreter
        base_capabilities: Base system prompt with tool descriptions
        
    Returns:
        Complete system prompt string
    """
    # Format selected data with size limits
    context_str = json.dumps(filtered_context, separators=(",", ":"), ensure_ascii=False) if filtered_context else "No context selected."
    # Truncate context if too large (max 5000 chars)
    MAX_CONTEXT_SIZE = 5000
    if len(context_str) > MAX_CONTEXT_SIZE:
        context_str = context_str[:MAX_CONTEXT_SIZE] + "\n... [truncated - context too large]"
    
    analyses_str = format_analyses_for_prompt(filtered_analyses) if filtered_analyses else "No analyses selected."
    
    # Build response instructions
    exclusions_str = "\n".join([f"- Do NOT mention: {item}" for item in orchestration_plan.exclude_from_response]) if orchestration_plan.exclude_from_response else "No exclusions specified."
    
    # Response strategy or fallback to system_prompt_additions
    response_instructions = orchestration_plan.response_strategy if orchestration_plan.response_strategy else (
        orchestration_plan.system_prompt_additions if orchestration_plan.system_prompt_additions else "Follow the interpreter's plan above."
    )
    
    # Build investigation summary if investigation plan exists
    investigation_summary = ""
    if orchestration_plan.investigation_plan:
        investigation_summary = "\n## Investigation Summary\n\n"
        investigation_summary += f"**Question:** {orchestration_plan.investigation_plan.question}\n\n"
        
        if orchestration_plan.message_decomposition:
            investigation_summary += "### Message Components Investigated:\n\n"
            for component in orchestration_plan.message_decomposition.components:
                if component.requires_investigation:
                    investigation_summary += f"**{component.component_type}:** {component.text}\n"
                    investigation_summary += f"  Intent: {component.intent}\n"
                    
                    # Get evidence for this component
                    evidence = orchestration_plan.get_evidence_for_component(component.investigation_id or "")
                    if evidence:
                        investigation_summary += f"  Evidence from investigation steps:\n"
                        for ev in evidence:
                            investigation_summary += f"    - Step {ev['step_id']} ({ev['action']}):\n"
                            if ev.get('insights'):
                                for insight in ev['insights']:
                                    investigation_summary += f"      • {insight}\n"
                            if ev.get('board_state_before'):
                                investigation_summary += f"      Board before: {ev['board_state_before'][:50]}...\n"
                            if ev.get('board_state_after'):
                                investigation_summary += f"      Board after: {ev['board_state_after'][:50]}...\n"
                    investigation_summary += "\n"
        
        if orchestration_plan.investigation_summary:
            investigation_summary += f"### Investigation Findings:\n{orchestration_plan.investigation_summary}\n\n"
        
        investigation_summary += "**CRITICAL:** All claims in your response must reference specific investigation steps. "
        investigation_summary += "Use phrases like 'Step X found that...' or 'Investigation showed...'. "
        investigation_summary += "No hallucinations - all facts must be backed by investigation evidence.\n\n"
    
    prompt = f"""You are Chesster, a chess assistant.

## Interpreter's Plan

{response_instructions}
{investigation_summary}
## Selected Context (only what's relevant)
{context_str}

## Selected Analyses (only what's relevant)
{analyses_str}

## Exclusions
{exclusions_str}

## Base Capabilities (for reference only)
{base_capabilities}

## Writing Style

**CRITICAL: Write in a prose, conversational manner.** 

- Write in flowing, natural paragraphs as if you're having a conversation with the user
- Avoid bullet points and lists unless absolutely necessary for clarity
- Weave technical details (evaluations, themes, moves) naturally into your narrative
- Use transitions and connecting phrases to create smooth flow between ideas
- Make it feel like you're explaining chess to a friend, not writing a technical report
- Even when presenting analysis, frame it conversationally rather than as a structured report

CRITICAL: Follow the interpreter's plan exactly. The selected data above is all you need to respond. Do not reference information that wasn't included in the selected context or analyses.
"""
    return prompt

