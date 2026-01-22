"""
Configuration for Personal Review System
Centralized configuration with environment variable support
"""

import os
from typing import Optional


class PersonalReviewConfig:
    """Configuration for personal review system"""
    
    # Default analysis depth
    DEFAULT_ANALYSIS_DEPTH: int = int(os.getenv("PERSONAL_REVIEW_DEFAULT_DEPTH", "15"))
    
    # Maximum games per analysis
    MAX_GAMES_PER_ANALYSIS: int = int(os.getenv("PERSONAL_REVIEW_MAX_GAMES", "50"))
    
    # Cache TTL in seconds (24 hours)
    CACHE_TTL_SECONDS: int = int(os.getenv("PERSONAL_REVIEW_CACHE_TTL", str(24 * 60 * 60)))
    
    # Parallel analysis workers
    MAX_PARALLEL_ANALYSES: int = int(os.getenv("PERSONAL_REVIEW_MAX_PARALLEL", "4"))
    
    # Depth validation range
    MIN_DEPTH: int = 10
    MAX_DEPTH: int = 25
    
    # Analysis quality thresholds
    MIN_MOVE_COUNT: int = 10
    MIN_EVAL_CP: int = -1000
    MAX_EVAL_CP: int = 1000
    
    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = int(os.getenv("PERSONAL_REVIEW_RATE_LIMIT", "10"))
    
    @classmethod
    def validate_depth(cls, depth: int) -> int:
        """Validate and clamp depth to valid range"""
        return max(cls.MIN_DEPTH, min(cls.MAX_DEPTH, depth))
    
    @classmethod
    def get_depth(cls, user_override: Optional[int] = None, plan_depth: Optional[int] = None) -> int:
        """Get analysis depth with priority: user_override > plan_depth > default"""
        if user_override is not None:
            return cls.validate_depth(user_override)
        if plan_depth is not None:
            return cls.validate_depth(plan_depth)
        return cls.DEFAULT_ANALYSIS_DEPTH


# Global config instance
config = PersonalReviewConfig()


