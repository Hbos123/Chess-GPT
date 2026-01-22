"""
Advanced Intelligence Tools
Tools for complex multi-step reasoning, cheating investigations, and player analysis
"""

from .web_search import web_search, TOOL_WEB_SEARCH
from .multi_depth_analysis import multi_depth_analyze, TOOL_MULTI_DEPTH_ANALYZE
from .engine_correlation import engine_correlation, TOOL_ENGINE_CORRELATION
from .anomaly_detection import detect_anomalies, TOOL_ANOMALY_DETECT
from .player_baseline import calculate_baseline, TOOL_PLAYER_BASELINE
from .critical_moments import find_critical_moments, TOOL_CRITICAL_MOMENTS
from .complexity_scorer import score_move_complexity, TOOL_COMPLEXITY_SCORER
from .game_filters import fetch_games_filtered, TOOL_FETCH_GAMES_FILTERED
from .peer_comparison import compare_to_peers, TOOL_PEER_COMPARISON

__all__ = [
    # Functions
    'web_search',
    'multi_depth_analyze', 
    'engine_correlation',
    'detect_anomalies',
    'calculate_baseline',
    'find_critical_moments',
    'score_move_complexity',
    'fetch_games_filtered',
    'compare_to_peers',
    
    # Tool schemas
    'TOOL_WEB_SEARCH',
    'TOOL_MULTI_DEPTH_ANALYZE',
    'TOOL_ENGINE_CORRELATION',
    'TOOL_ANOMALY_DETECT',
    'TOOL_PLAYER_BASELINE',
    'TOOL_CRITICAL_MOMENTS',
    'TOOL_COMPLEXITY_SCORER',
    'TOOL_FETCH_GAMES_FILTERED',
    'TOOL_PEER_COMPARISON',
]

# All tool schemas for easy registration
ALL_TOOL_SCHEMAS = [
    TOOL_WEB_SEARCH,
    TOOL_MULTI_DEPTH_ANALYZE,
    TOOL_ENGINE_CORRELATION,
    TOOL_ANOMALY_DETECT,
    TOOL_PLAYER_BASELINE,
    TOOL_CRITICAL_MOMENTS,
    TOOL_COMPLEXITY_SCORER,
    TOOL_FETCH_GAMES_FILTERED,
    TOOL_PEER_COMPARISON,
]
