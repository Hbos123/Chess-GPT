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
    
    Args:
        analyses: Dictionary of analysis results keyed by tool name
        
    Returns:
        Formatted string for prompt
    """
    if not analyses:
        return "No analyses selected."
    
    parts = []
    for tool_name, result in analyses.items():
        if isinstance(result, dict) and "error" in result:
            parts.append(f"### {tool_name} (FAILED)\nError: {result['error']}")
        else:
            # Format the result - try to make it readable
            if isinstance(result, dict):
                # For large dicts, summarize key fields
                summary_fields = ["success", "narrative", "summary", "stats", "games_analyzed"]
                summary = {}
                for field in summary_fields:
                    if field in result:
                        summary[field] = result[field]
                
                if summary:
                    parts.append(f"### {tool_name} Results\n{json.dumps(summary, indent=2)}")
                else:
                    # Fallback: just show keys
                    parts.append(f"### {tool_name} Results\n{json.dumps(result, indent=2)[:1000]}...")
            else:
                parts.append(f"### {tool_name} Results\n{str(result)[:500]}")
    
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
    # Format selected data
    context_str = json.dumps(filtered_context, indent=2) if filtered_context else "No context selected."
    analyses_str = format_analyses_for_prompt(filtered_analyses) if filtered_analyses else "No analyses selected."
    
    # Build response instructions
    exclusions_str = "\n".join([f"- Do NOT mention: {item}" for item in orchestration_plan.exclude_from_response]) if orchestration_plan.exclude_from_response else "No exclusions specified."
    
    # Response strategy or fallback to system_prompt_additions
    response_instructions = orchestration_plan.response_strategy if orchestration_plan.response_strategy else (
        orchestration_plan.system_prompt_additions if orchestration_plan.system_prompt_additions else "Follow the interpreter's plan above."
    )
    
    prompt = f"""You are Chess GPT, a chess assistant.

## Interpreter's Plan

{response_instructions}

## Selected Context (only what's relevant)
{context_str}

## Selected Analyses (only what's relevant)
{analyses_str}

## Exclusions
{exclusions_str}

## Base Capabilities (for reference only)
{base_capabilities}

CRITICAL: Follow the interpreter's plan exactly. The selected data above is all you need to respond. Do not reference information that wasn't included in the selected context or analyses.
"""
    return prompt

