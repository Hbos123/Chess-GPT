"""
Interpreter Output Validator
Validates and sanitizes LLM outputs from the interpreter loop
"""

from typing import Dict, Any, List, Tuple, Optional
import json
import re


# Valid action types
VALID_ACTION_TYPES = {"fetch", "analyze", "search", "compute"}

# Required parameters per action type
ACTION_REQUIRED_PARAMS = {
    "fetch": [],  # platforms will default to connected accounts
    "analyze": [],  # fen or pgn required
    "search": ["query"],
    "compute": ["type"]
}

# Valid compute types
VALID_COMPUTE_TYPES = {"baseline", "correlation", "anomaly", "complexity", "critical_moments"}

# Valid modes
VALID_MODES = {"play", "analyze", "review", "training", "chat", "fetch"}


def validate_interpreter_output(raw: dict) -> Tuple[bool, List[str]]:
    """
    Validate interpreter LLM output structure.
    
    Args:
        raw: Raw parsed JSON from LLM
    
    Returns:
        (is_valid, list_of_errors)
    """
    errors = []
    
    # Must have is_ready field
    if "is_ready" not in raw:
        errors.append("Missing 'is_ready' field")
        return False, errors
    
    is_ready = raw.get("is_ready")
    
    if is_ready:
        # Ready state validation
        if not raw.get("final_plan"):
            errors.append("is_ready=true but no 'final_plan' provided")
        else:
            plan = raw["final_plan"]
            plan_errors = _validate_final_plan(plan)
            errors.extend(plan_errors)
    else:
        # Not ready - needs actions
        if not raw.get("actions"):
            errors.append("Not ready but no 'actions' specified")
        else:
            for i, action in enumerate(raw.get("actions", [])):
                action_errors = _validate_action(action, i)
                errors.extend(action_errors)
        
        # Insights are optional but should be a list
        if "insights" in raw and not isinstance(raw["insights"], list):
            errors.append("'insights' should be a list")
    
    return len(errors) == 0, errors


def _validate_final_plan(plan: dict) -> List[str]:
    """Validate final_plan structure"""
    errors = []
    
    if not isinstance(plan, dict):
        return ["final_plan should be an object"]
    
    # Required fields
    if "mode" not in plan:
        errors.append("final_plan missing 'mode'")
    elif plan["mode"] not in VALID_MODES:
        errors.append(f"Invalid mode: {plan['mode']}")
    
    # Optional but validated fields
    if "mode_confidence" in plan:
        conf = plan["mode_confidence"]
        if not isinstance(conf, (int, float)) or not (0 <= conf <= 1):
            errors.append("mode_confidence should be 0-1")
    
    if "response_guidelines" in plan:
        guidelines = plan["response_guidelines"]
        if not isinstance(guidelines, dict):
            errors.append("response_guidelines should be an object")
    
    return errors


def _validate_action(action: dict, index: int) -> List[str]:
    """Validate a single action"""
    errors = []
    prefix = f"Action {index}"
    
    if not isinstance(action, dict):
        return [f"{prefix}: should be an object"]
    
    # Required fields
    if "action_type" not in action:
        errors.append(f"{prefix}: missing 'action_type'")
    else:
        action_type = action["action_type"]
        if action_type not in VALID_ACTION_TYPES:
            errors.append(f"{prefix}: invalid action_type '{action_type}'")
        else:
            # Validate params for this action type
            params = action.get("params", {})
            param_errors = _validate_action_params(action_type, params, prefix)
            errors.extend(param_errors)
    
    if "reasoning" not in action:
        errors.append(f"{prefix}: missing 'reasoning'")
    elif not isinstance(action["reasoning"], str):
        errors.append(f"{prefix}: 'reasoning' should be a string")
    
    return errors


def _validate_action_params(action_type: str, params: dict, prefix: str) -> List[str]:
    """Validate parameters for a specific action type"""
    errors = []
    
    if not isinstance(params, dict):
        return [f"{prefix}: 'params' should be an object"]
    
    # Check required params
    required = ACTION_REQUIRED_PARAMS.get(action_type, [])
    for param in required:
        if param not in params:
            errors.append(f"{prefix}: missing required param '{param}'")
    
    # Type-specific validation
    if action_type == "fetch":
        if "platforms" in params:
            platforms = params["platforms"]
            if not isinstance(platforms, list):
                errors.append(f"{prefix}: 'platforms' should be a list")
            else:
                valid_platforms = {"chess.com", "lichess"}
                for p in platforms:
                    if p not in valid_platforms:
                        errors.append(f"{prefix}: invalid platform '{p}'")
        
        if "count" in params:
            count = params["count"]
            if not isinstance(count, int) or count < 1 or count > 100:
                errors.append(f"{prefix}: 'count' should be 1-100")
    
    elif action_type == "analyze":
        # Need either fen or pgn
        if "fen" not in params and "pgn" not in params:
            # Will use context FEN, which is okay
            pass
        
        if "depth" in params:
            depth = params["depth"]
            if not isinstance(depth, int) or depth < 1 or depth > 30:
                errors.append(f"{prefix}: 'depth' should be 1-30")
    
    elif action_type == "search":
        query = params.get("query", "")
        if not query or not isinstance(query, str):
            errors.append(f"{prefix}: 'query' should be a non-empty string")
        elif len(query) > 500:
            errors.append(f"{prefix}: 'query' too long (max 500 chars)")
    
    elif action_type == "compute":
        compute_type = params.get("type", "")
        if compute_type not in VALID_COMPUTE_TYPES:
            errors.append(f"{prefix}: invalid compute type '{compute_type}'")
    
    return errors


def sanitize_output(raw: Any) -> dict:
    """
    Sanitize and fix common LLM output mistakes.
    
    Args:
        raw: Raw output (could be dict, string, or other)
    
    Returns:
        Sanitized dictionary
    """
    # If already a dict, work with it
    if isinstance(raw, dict):
        return _sanitize_dict(raw)
    
    # If string, try to parse as JSON
    if isinstance(raw, str):
        # Try to extract JSON from markdown code blocks
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', raw)
        if json_match:
            raw = json_match.group(1)
        
        # Try to parse
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return _sanitize_dict(parsed)
        except json.JSONDecodeError:
            pass
    
    # Return empty dict as fallback
    return {"is_ready": False, "actions": [], "insights": []}


def _sanitize_dict(d: dict) -> dict:
    """Sanitize a dictionary output"""
    result = {}
    
    # Handle is_ready
    is_ready = d.get("is_ready", d.get("isReady", d.get("ready", False)))
    result["is_ready"] = bool(is_ready)
    
    if result["is_ready"]:
        # Get final plan
        plan = d.get("final_plan", d.get("finalPlan", d.get("plan", {})))
        result["final_plan"] = _sanitize_plan(plan)
    else:
        # Get actions
        actions = d.get("actions", [])
        result["actions"] = [_sanitize_action(a) for a in actions if isinstance(a, dict)]
        
        # Get insights
        insights = d.get("insights", [])
        if isinstance(insights, list):
            result["insights"] = [str(i) for i in insights]
        elif isinstance(insights, str):
            result["insights"] = [insights]
        else:
            result["insights"] = []
    
    return result


def _sanitize_plan(plan: Any) -> dict:
    """Sanitize a final plan"""
    if not isinstance(plan, dict):
        return {"mode": "chat"}
    
    result = {}
    
    # Mode
    mode = plan.get("mode", "chat")
    if mode in VALID_MODES:
        result["mode"] = mode
    else:
        result["mode"] = "chat"
    
    # Mode confidence
    conf = plan.get("mode_confidence", plan.get("modeConfidence", 0.8))
    try:
        result["mode_confidence"] = max(0, min(1, float(conf)))
    except (ValueError, TypeError):
        result["mode_confidence"] = 0.8
    
    # Intent summary
    intent = plan.get("user_intent_summary", plan.get("intent", plan.get("userIntent", "")))
    result["user_intent_summary"] = str(intent) if intent else ""
    
    # Response guidelines
    guidelines = plan.get("response_guidelines", plan.get("responseGuidelines", {}))
    if isinstance(guidelines, dict):
        result["response_guidelines"] = guidelines
    
    # Tool sequence
    tools = plan.get("tool_sequence", plan.get("tools", []))
    if isinstance(tools, list):
        result["tool_sequence"] = tools
    
    # Extracted data
    extracted = plan.get("extracted_data", plan.get("extractedData", {}))
    if isinstance(extracted, dict):
        result["extracted_data"] = extracted
    
    return result


def _sanitize_action(action: dict) -> dict:
    """Sanitize a single action"""
    result = {}
    
    # Action type
    action_type = action.get("action_type", action.get("actionType", action.get("type", "")))
    if action_type in VALID_ACTION_TYPES:
        result["action_type"] = action_type
    else:
        result["action_type"] = "analyze"  # Safe default
    
    # Params
    params = action.get("params", action.get("parameters", {}))
    if isinstance(params, dict):
        result["params"] = params
    else:
        result["params"] = {}
    
    # Reasoning
    reasoning = action.get("reasoning", action.get("reason", ""))
    result["reasoning"] = str(reasoning) if reasoning else "No reasoning provided"
    
    # Dependencies
    depends = action.get("depends_on", action.get("dependsOn"))
    if depends:
        result["depends_on"] = str(depends)
    
    return result


def validate_action_params_strict(action_type: str, params: dict) -> Tuple[bool, List[str]]:
    """
    Strict validation of action parameters.
    Returns (is_valid, errors) tuple.
    """
    errors = _validate_action_params(action_type, params, "Action")
    return len(errors) == 0, errors

