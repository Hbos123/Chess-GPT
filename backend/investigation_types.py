"""
Investigation Types and Schemas
Defines investigation types, tool schemas, and response formats
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum


class InvestigationType(Enum):
    """Types of investigations the system can perform"""
    CHEATING_ANALYSIS = "cheating_analysis"
    PLAYER_RESEARCH = "player_research"
    GAME_COMPARISON = "game_comparison"
    PERFORMANCE_TREND = "performance_trend"
    OPENING_ANALYSIS = "opening_analysis"
    TOURNAMENT_REVIEW = "tournament_review"
    STYLE_ANALYSIS = "style_analysis"
    PREPARATION_CHECK = "preparation_check"
    GENERAL_INVESTIGATION = "general_investigation"


@dataclass
class InvestigationRequest:
    """Request for an investigation"""
    query: str
    investigation_type: Optional[InvestigationType] = None
    target_player: Optional[str] = None
    target_event: Optional[str] = None
    target_games: Optional[List[str]] = None
    date_range: Optional[Dict[str, str]] = None
    comparison_player: Optional[str] = None
    additional_context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class InvestigationConfig:
    """Configuration for an investigation type"""
    required_tools: List[str]
    optional_tools: List[str]
    min_games: int = 5
    max_games: int = 100
    default_depth: int = 20
    synthesis_format: str = "structured"
    confidence_thresholds: Dict[str, float] = field(default_factory=lambda: {
        "high": 0.8,
        "medium": 0.5,
        "low": 0.3
    })


# Investigation configurations
INVESTIGATION_CONFIGS: Dict[InvestigationType, InvestigationConfig] = {
    InvestigationType.CHEATING_ANALYSIS: InvestigationConfig(
        required_tools=["multi_depth_analyze", "engine_correlation", "detect_anomalies"],
        optional_tools=["web_search", "calculate_baseline", "score_move_complexity"],
        min_games=3,
        max_games=50,
        default_depth=30,
        synthesis_format="structured",
        confidence_thresholds={"high": 0.9, "medium": 0.7, "low": 0.5}
    ),
    
    InvestigationType.PLAYER_RESEARCH: InvestigationConfig(
        required_tools=["web_search", "calculate_baseline"],
        optional_tools=["find_critical_moments", "engine_correlation"],
        min_games=10,
        max_games=100,
        default_depth=15
    ),
    
    InvestigationType.PERFORMANCE_TREND: InvestigationConfig(
        required_tools=["calculate_baseline"],
        optional_tools=["detect_anomalies", "engine_correlation"],
        min_games=20,
        max_games=200,
        default_depth=15
    ),
    
    InvestigationType.TOURNAMENT_REVIEW: InvestigationConfig(
        required_tools=["find_critical_moments"],
        optional_tools=["engine_correlation", "score_move_complexity"],
        min_games=1,
        max_games=15,
        default_depth=25
    ),
    
    InvestigationType.OPENING_ANALYSIS: InvestigationConfig(
        required_tools=["web_search"],
        optional_tools=["engine_correlation"],
        min_games=5,
        max_games=50,
        default_depth=20
    ),
    
    InvestigationType.STYLE_ANALYSIS: InvestigationConfig(
        required_tools=["calculate_baseline", "find_critical_moments"],
        optional_tools=["score_move_complexity"],
        min_games=15,
        max_games=100,
        default_depth=15
    ),
    
    InvestigationType.GENERAL_INVESTIGATION: InvestigationConfig(
        required_tools=["web_search"],
        optional_tools=["calculate_baseline", "find_critical_moments"],
        min_games=1,
        max_games=50,
        default_depth=20
    )
}


# Tool definitions for function calling
INVESTIGATION_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "investigate",
            "description": "Run a complex multi-step investigation. Use for cheating analysis, player research, performance trends, tournament reviews, and other analytical tasks that require multiple data sources and analysis steps.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The investigation query (e.g., 'Did Hans Niemann cheat at Sinquefield Cup 2022?', 'Analyze Magnus Carlsen's performance trend in 2023')"
                    },
                    "investigation_type": {
                        "type": "string",
                        "enum": [t.value for t in InvestigationType],
                        "description": "Type of investigation to run"
                    },
                    "target_player": {
                        "type": "string",
                        "description": "Primary player to investigate"
                    },
                    "target_event": {
                        "type": "string",
                        "description": "Specific tournament or event (optional)"
                    },
                    "context": {
                        "type": "object",
                        "description": "Additional context (usernames, platforms, date ranges)"
                    }
                },
                "required": ["query"]
            }
        }
    }
]


# Suspicion level definitions for cheating analysis
SUSPICION_LEVELS = {
    "normal": {
        "score_range": (0, 0.3),
        "description": "Performance within expected parameters",
        "action": "No concerns"
    },
    "elevated": {
        "score_range": (0.3, 0.5),
        "description": "Some metrics above average, may warrant review",
        "action": "Monitor if pattern continues"
    },
    "high": {
        "score_range": (0.5, 0.7),
        "description": "Multiple significant anomalies detected",
        "action": "Detailed review recommended"
    },
    "extreme": {
        "score_range": (0.7, 1.0),
        "description": "Strong statistical evidence of irregularities",
        "action": "Formal review warranted"
    }
}


# Performance benchmarks by rating
RATING_BENCHMARKS = {
    "2700+": {
        "top1_match": (65, 75),  # (min, max) normal range
        "top3_match": (85, 92),
        "avg_cp_loss": (15, 30),
        "blunder_rate": (0.01, 0.04)
    },
    "2500-2700": {
        "top1_match": (55, 68),
        "top3_match": (78, 88),
        "avg_cp_loss": (25, 45),
        "blunder_rate": (0.03, 0.07)
    },
    "2200-2500": {
        "top1_match": (45, 60),
        "top3_match": (70, 82),
        "avg_cp_loss": (35, 60),
        "blunder_rate": (0.05, 0.10)
    },
    "2000-2200": {
        "top1_match": (38, 52),
        "top3_match": (62, 75),
        "avg_cp_loss": (45, 75),
        "blunder_rate": (0.07, 0.14)
    },
    "1800-2000": {
        "top1_match": (32, 45),
        "top3_match": (55, 68),
        "avg_cp_loss": (55, 90),
        "blunder_rate": (0.10, 0.18)
    },
    "<1800": {
        "top1_match": (25, 40),
        "top3_match": (45, 62),
        "avg_cp_loss": (70, 120),
        "blunder_rate": (0.12, 0.25)
    }
}


def get_rating_benchmark(rating: int) -> Dict:
    """Get benchmark values for a specific rating"""
    if rating >= 2700:
        return RATING_BENCHMARKS["2700+"]
    elif rating >= 2500:
        return RATING_BENCHMARKS["2500-2700"]
    elif rating >= 2200:
        return RATING_BENCHMARKS["2200-2500"]
    elif rating >= 2000:
        return RATING_BENCHMARKS["2000-2200"]
    elif rating >= 1800:
        return RATING_BENCHMARKS["1800-2000"]
    else:
        return RATING_BENCHMARKS["<1800"]


def is_metric_suspicious(metric: str, value: float, rating: int) -> bool:
    """Check if a metric value is suspicious for the rating level"""
    benchmark = get_rating_benchmark(rating)
    
    if metric not in benchmark:
        return False
    
    min_val, max_val = benchmark[metric]
    
    # For "good" metrics (accuracy, match rate), suspicious if too high
    if metric in ["top1_match", "top3_match"]:
        return value > max_val * 1.15  # 15% above max is suspicious
    
    # For "bad" metrics (cp_loss, blunder_rate), suspicious if too low
    if metric in ["avg_cp_loss", "blunder_rate"]:
        return value < min_val * 0.5  # 50% below min is suspicious
    
    return False

