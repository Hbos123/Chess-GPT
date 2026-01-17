"""
Pydantic models for Personal Review System
Type definitions for all data structures
"""

from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field, validator
from datetime import datetime


class GameMetadata(BaseModel):
    """Game metadata structure"""
    game_id: Optional[str] = None
    platform: Literal["chess.com", "lichess", "chesscom", "manual"] = "chess.com"
    player_rating: int = Field(ge=0, le=4000)
    opponent_rating: int = Field(ge=0, le=4000)
    result: Literal["win", "loss", "draw", "unknown"] = "unknown"
    player_color: Literal["white", "black"] = "white"
    time_category: Optional[str] = None
    date: Optional[str] = None
    pgn: Optional[str] = None
    has_clock: bool = False
    opening: Optional[str] = None


class FilterSpec(BaseModel):
    """Filter specification for game selection"""
    rating_min: Optional[int] = Field(None, ge=0, le=4000)
    rating_max: Optional[int] = Field(None, ge=0, le=4000)
    result: Optional[Literal["win", "loss", "draw"]] = None
    player_color: Optional[Literal["white", "black"]] = None
    time_category: Optional[Literal["bullet", "blitz", "rapid", "classical"]] = None
    opening_eco: Optional[str] = None
    date_range: Optional[Literal["older", "recent"]] = None


class CohortSpec(BaseModel):
    """Cohort definition for comparison"""
    label: str
    filters: FilterSpec


class AnalysisPlan(BaseModel):
    """LLM planner output structure"""
    intent: Literal["diagnostic", "comparison", "trend", "focus"] = "diagnostic"
    filters: FilterSpec = Field(default_factory=FilterSpec)
    metrics: List[str] = Field(default_factory=lambda: ["overall_stats", "phase_breakdown"])
    games_to_analyze: int = Field(default=50, ge=1, le=100)
    analysis_depth: int = Field(default=15, ge=10, le=25)
    cohorts: Optional[List[CohortSpec]] = None
    exemplars: Optional[Dict[str, Any]] = None
    focus_phase: Optional[Literal["opening", "middlegame", "endgame"]] = None
    
    @validator('metrics')
    def validate_metrics(cls, v):
        valid_metrics = [
            "overall_stats", "phase_breakdown", "opening_performance",
            "theme_analysis", "time_management", "mistake_patterns"
        ]
        for metric in v:
            if metric not in valid_metrics:
                raise ValueError(f"Invalid metric: {metric}. Must be one of {valid_metrics}")
        return v


class PhaseStats(BaseModel):
    """Statistics for a game phase"""
    accuracy: Optional[float] = None
    avg_cp_loss: Optional[float] = None
    move_count: int = 0


class SummaryStats(BaseModel):
    """Overall summary statistics"""
    total_games: int = 0
    wins: int = 0
    losses: int = 0
    draws: int = 0
    win_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    overall_accuracy: float = Field(default=0.0, ge=0.0, le=100.0)
    avg_accuracy: float = Field(default=0.0, ge=0.0, le=100.0)
    avg_cp_loss: float = 0.0
    blunder_rate: float = Field(default=0.0, ge=0.0, le=100.0)
    mistake_rate: float = Field(default=0.0, ge=0.0, le=100.0)
    total_moves: int = 0
    blunders_per_game: float = 0.0
    mistakes_per_game: float = 0.0


class AccuracyByRating(BaseModel):
    """Accuracy grouped by rating band"""
    rating_range: str
    accuracy: float
    game_count: int


class OpeningPerformance(BaseModel):
    """Performance statistics for an opening"""
    name: str
    count: int
    wins: int
    losses: int
    draws: int
    win_rate: float
    avg_accuracy: float
    avg_cp_loss: float


class ThemeFrequency(BaseModel):
    """Theme frequency statistics"""
    name: str
    frequency: int
    error_count: int
    error_rate: float
    weakness_level: Literal["critical", "moderate", "minor"]


class AggregatedStats(BaseModel):
    """Complete aggregated statistics output"""
    summary: SummaryStats
    accuracy_by_rating: List[AccuracyByRating] = Field(default_factory=list)
    opening_performance: List[OpeningPerformance] = Field(default_factory=list)
    theme_frequency: List[ThemeFrequency] = Field(default_factory=list)
    phase_stats: Dict[str, PhaseStats] = Field(default_factory=dict)
    win_rate_by_phase: Dict[str, float] = Field(default_factory=dict)
    mistake_patterns: Dict[str, Any] = Field(default_factory=dict)
    time_management: Dict[str, Any] = Field(default_factory=dict)
    advanced_metrics: Dict[str, Any] = Field(default_factory=dict)
    accuracy_by_color: Dict[str, Any] = Field(default_factory=dict)
    performance_by_time_control: List[Dict[str, Any]] = Field(default_factory=list)
    accuracy_by_time_spent: List[Dict[str, Any]] = Field(default_factory=list)
    performance_by_tags: Dict[str, Any] = Field(default_factory=dict)
    critical_moments: Dict[str, Any] = Field(default_factory=dict)
    advantage_conversion: Dict[str, Any] = Field(default_factory=dict)
    blunder_triggers: Dict[str, Any] = Field(default_factory=dict)
    piece_activity: List[Dict[str, Any]] = Field(default_factory=list)
    tilt_points: List[Dict[str, Any]] = Field(default_factory=list)
    diagnostic_insights: List[Dict[str, Any]] = Field(default_factory=list)
    total_games_analyzed: int = 0
    error: Optional[str] = None
    action_plan: Optional[List[str]] = None
    analyzed_game_ids: Optional[List[str]] = None  # Changed from analyzed_games


class PlanReviewRequest(BaseModel):
    """Request model for planning review"""
    query: str = Field(..., min_length=1)
    games: List[Dict[str, Any]]


class AggregateReviewRequest(BaseModel):
    """Request model for aggregating review"""
    plan: Dict[str, Any]  # Will be validated as AnalysisPlan
    games: List[Dict[str, Any]]


class GenerateReportRequest(BaseModel):
    """Request model for generating report"""
    query: str
    plan: Dict[str, Any]
    data: Dict[str, Any]


class ProgressUpdate(BaseModel):
    """Progress update for SSE"""
    current: int
    total: int
    message: str
    percentage: float = Field(default=0.0, ge=0.0, le=100.0)

