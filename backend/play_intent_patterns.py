"""
Pattern dictionary for detecting "play against AI" intent.
Used to short-circuit the main message pathway and offer side selection.
"""
import re
from typing import Dict, List, Tuple

# Direct questions with the sole intent of playing against the AI
PLAY_INTENT_PATTERNS: List[Tuple[str, float]] = [
    # Direct play requests
    (r"\b(let'?s|lets)\s+play\b", 1.0),
    (r"\b(let'?s|lets)\s+continue\s+playing\b", 1.0),  # "let's continue playing"
    (r"\bplay\s+(together|a\s+game|with\s+you|against\s+you)\b", 1.0),
    (r"\bplay\s+(from\s+)?(this\s+)?(position|here)\b", 1.0),
    (r"\bstart\s+a\s+game\b", 1.0),
    (r"\bwanna\s+play\b", 1.0),
    (r"\bwant\s+to\s+play\b", 1.0),
    (r"\bcan\s+we\s+play\b", 1.0),
    (r"\bshall\s+we\s+play\b", 1.0),
    (r"\bready\s+to\s+play\b", 1.0),
    (r"\bplay\s+chess\s+(with|against)\s+(you|ai|the\s+ai)\b", 1.0),
    (r"\b(you|ai)\s+(play|vs|against)\s+(me|you)\b", 1.0),
    (r"\bchallenge\s+(you|the\s+ai)\b", 0.9),
    (r"\bgame\s+on\b", 0.9),
    (r"\bcontinue\s+playing\b", 0.9),  # "continue playing" - high confidence for play intent
    (r"\bplay\s+now\b", 0.8),
]

# Patterns that should NOT trigger play intent (exclude these)
EXCLUDE_PATTERNS: List[str] = [
    r"\b(analyze|review|explain|show|tell|what|how|why|when|where)\s+.*\bplay\b",  # Questions about playing
    r"\bplay\s+(book|opening|theory|line|variation)\b",  # Chess theory
    r"\bplay\s+(better|well|correctly|right)\b",  # Improvement questions
    r"\bhow\s+to\s+play\b",  # Learning questions
    r"\bwhat\s+to\s+play\b",  # Move suggestions
    r"\bshould\s+(i|we)\s+play\b",  # Move advice
]


def detect_play_intent(user_message: str) -> Dict[str, any]:
    """
    Detect if the user wants to play against the AI.
    
    Returns:
        {
            "is_play_intent": bool,
            "confidence": float (0.0-1.0),
            "matched_pattern": str or None
        }
    """
    if not user_message:
        return {"is_play_intent": False, "confidence": 0.0, "matched_pattern": None}
    
    msg_lower = user_message.lower().strip()
    
    # Check exclude patterns first
    for exclude_pattern in EXCLUDE_PATTERNS:
        if re.search(exclude_pattern, msg_lower):
            return {"is_play_intent": False, "confidence": 0.0, "matched_pattern": None}
    
    # Check play intent patterns
    best_match = None
    best_confidence = 0.0
    
    for pattern, confidence in PLAY_INTENT_PATTERNS:
        if re.search(pattern, msg_lower):
            if confidence > best_confidence:
                best_confidence = confidence
                best_match = pattern
    
    # Require high confidence (>= 0.8) to short-circuit
    is_play_intent = best_confidence >= 0.8
    
    return {
        "is_play_intent": is_play_intent,
        "confidence": best_confidence,
        "matched_pattern": best_match
    }

