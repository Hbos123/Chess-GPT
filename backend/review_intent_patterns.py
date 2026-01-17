"""
Pattern dictionary for detecting "review my game" intent.
Used to short-circuit the main message pathway and trigger game review directly.
"""
import re
from typing import Dict, Optional, Tuple

# Patterns for "review my game [game_id] from [platform]"
# Order matters: more specific patterns first, then general ones
REVIEW_INTENT_PATTERNS: list[Tuple[str, float]] = [
    # Most specific: explicit platform names
    (r"\breview\s+my\s+game\s+(\d+)\s+from\s+(chess\.?com|lichess)", 1.0),
    (r"\breview\s+game\s+(\d+)\s+from\s+(chess\.?com|lichess)", 1.0),
    (r"\banalyze\s+my\s+game\s+(\d+)\s+from\s+(chess\.?com|lichess)", 0.95),
    (r"\banalyze\s+game\s+(\d+)\s+from\s+(chess\.?com|lichess)", 0.95),
    # General patterns that match any word (will match "chesscom", "chess.com", etc.)
    (r"\breview\s+my\s+game\s+(\d+)\s+from\s+(\w+)", 1.0),  # "review my game 123 from chesscom"
    (r"\breview\s+my\s+game\s+(\d+)\s+on\s+(\w+)", 1.0),  # "review my game 123 on chesscom"
    (r"\breview\s+game\s+(\d+)\s+from\s+(\w+)", 1.0),  # "review game 123 from chesscom"
    (r"\breview\s+game\s+(\d+)\s+on\s+(\w+)", 1.0),  # "review game 123 on chesscom"
    (r"\banalyze\s+my\s+game\s+(\d+)\s+from\s+(\w+)", 0.95),  # "analyze my game 123 from chesscom"
    (r"\banalyze\s+game\s+(\d+)\s+from\s+(\w+)", 0.95),  # "analyze game 123 from chesscom"
]


def detect_review_intent(user_message: str) -> Dict[str, any]:
    """
    Detect if the user wants to review a specific game.
    
    Returns:
        {
            "is_review_intent": bool,
            "confidence": float (0.0-1.0),
            "matched_pattern": str or None,
            "game_id": str or None,
            "platform": str or None
        }
    """
    if not user_message:
        return {
            "is_review_intent": False,
            "confidence": 0.0,
            "matched_pattern": None,
            "game_id": None,
            "platform": None
        }
    
    msg_lower = user_message.lower().strip()
    
    # Check review intent patterns
    best_match = None
    best_confidence = 0.0
    game_id = None
    platform = None
    
    for pattern, confidence in REVIEW_INTENT_PATTERNS:
        match = re.search(pattern, msg_lower)
        if match:
            if confidence > best_confidence:
                best_confidence = confidence
                best_match = pattern
                # Extract game ID and platform from match groups
                groups = match.groups()
                if len(groups) >= 2:
                    game_id = groups[0]
                    platform_raw = groups[1]
                    # Normalize platform name - handle "chesscom", "chess.com", "chess_com", etc.
                    platform_lower = platform_raw.lower().replace("_", "").replace(".", "").replace("-", "")
                    if "chess" in platform_lower or platform_lower == "chesscom":
                        platform = "chess.com"
                    elif "lichess" in platform_lower:
                        platform = "lichess"
                    else:
                        # Try to normalize common variations
                        if platform_lower in ["chesscom", "chess", "com"]:
                            platform = "chess.com"
                        else:
                            platform = platform_raw
    
    # Require high confidence (>= 0.9) to short-circuit
    is_review_intent = best_confidence >= 0.9
    
    return {
        "is_review_intent": is_review_intent,
        "confidence": best_confidence,
        "matched_pattern": best_match,
        "game_id": game_id,
        "platform": platform
    }

