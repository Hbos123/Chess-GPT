"""
Interpreter Budget and Resource Controls
Manages resource limits, usage tracking, and cancellation for the interpreter loop
"""

from dataclasses import dataclass, field
from typing import Optional, Tuple
import time
import threading


@dataclass
class ResourceBudget:
    """
    Defines resource limits for the interpreter loop.
    Prevents runaway costs, infinite loops, and excessive API usage.
    """
    max_passes: int = 5              # Maximum interpreter passes
    max_fetches: int = 3             # Maximum fetch operations
    max_analyses: int = 5            # Maximum analysis operations
    max_searches: int = 2            # Maximum web searches
    max_computes: int = 3            # Maximum compute operations
    max_games_total: int = 100       # Maximum games to fetch total
    timeout_seconds: float = 60.0    # Total timeout for interpreter loop
    max_cost_usd: float = 0.10       # Maximum estimated API cost
    max_context_tokens: int = 8000   # Maximum tokens for LLM context
    max_retries_per_action: int = 2  # Retries per failed action
    max_validation_errors: int = 3   # Max invalid LLM outputs before fallback
    
    @classmethod
    def default(cls) -> 'ResourceBudget':
        """Standard budget for most requests"""
        return cls()
    
    @classmethod
    def generous(cls) -> 'ResourceBudget':
        """Extended budget for complex investigations"""
        return cls(
            max_passes=8,
            max_fetches=5,
            max_analyses=10,
            max_searches=5,
            max_games_total=200,
            timeout_seconds=120.0,
            max_cost_usd=0.25
        )
    
    @classmethod
    def minimal(cls) -> 'ResourceBudget':
        """Minimal budget for simple requests"""
        return cls(
            max_passes=2,
            max_fetches=1,
            max_analyses=2,
            max_searches=1,
            timeout_seconds=30.0,
            max_cost_usd=0.05
        )
    
    @classmethod
    def single_pass(cls) -> 'ResourceBudget':
        """Budget that forces single-pass behavior"""
        return cls(
            max_passes=1,
            max_fetches=1,
            max_analyses=1,
            timeout_seconds=15.0
        )


@dataclass
class ResourceUsage:
    """
    Tracks actual resource usage during interpreter execution.
    Updated after each action and LLM call.
    """
    passes: int = 0
    fetches: int = 0
    analyses: int = 0
    searches: int = 0
    computes: int = 0
    games_fetched: int = 0
    llm_calls: int = 0
    llm_tokens_input: int = 0
    llm_tokens_output: int = 0
    api_calls: int = 0
    retries: int = 0
    validation_errors: int = 0
    start_time: float = field(default_factory=time.time)
    
    @property
    def elapsed_seconds(self) -> float:
        """Time since usage tracking started"""
        return time.time() - self.start_time
    
    @property
    def estimated_cost_usd(self) -> float:
        """
        Estimate API cost based on token usage.
        Using approximate GPT-4o-mini pricing: $0.15/1M input, $0.60/1M output
        """
        input_cost = (self.llm_tokens_input / 1_000_000) * 0.15
        output_cost = (self.llm_tokens_output / 1_000_000) * 0.60
        return input_cost + output_cost
    
    def record_llm_call(self, input_tokens: int, output_tokens: int):
        """Record an LLM call"""
        self.llm_calls += 1
        self.llm_tokens_input += input_tokens
        self.llm_tokens_output += output_tokens
    
    def record_fetch(self, games_count: int = 0):
        """Record a fetch operation"""
        self.fetches += 1
        self.games_fetched += games_count
        self.api_calls += 1
    
    def record_analysis(self):
        """Record an analysis operation"""
        self.analyses += 1
        self.api_calls += 1
    
    def record_search(self):
        """Record a web search"""
        self.searches += 1
        self.api_calls += 1
    
    def record_compute(self):
        """Record a compute operation"""
        self.computes += 1
    
    def record_retry(self):
        """Record a retry attempt"""
        self.retries += 1
    
    def record_validation_error(self):
        """Record an LLM output validation error"""
        self.validation_errors += 1
    
    def can_continue(self, budget: ResourceBudget) -> Tuple[bool, str]:
        """
        Check if we can continue based on budget constraints.
        Returns (can_continue, reason_if_not)
        """
        if self.passes >= budget.max_passes:
            return False, "max_passes_reached"
        
        if self.elapsed_seconds > budget.timeout_seconds:
            return False, "timeout"
        
        if self.estimated_cost_usd > budget.max_cost_usd:
            return False, "cost_limit"
        
        if self.validation_errors >= budget.max_validation_errors:
            return False, "too_many_validation_errors"
        
        return True, ""
    
    def can_fetch(self, budget: ResourceBudget) -> bool:
        """Check if we can perform another fetch"""
        return self.fetches < budget.max_fetches
    
    def can_analyze(self, budget: ResourceBudget) -> bool:
        """Check if we can perform another analysis"""
        return self.analyses < budget.max_analyses
    
    def can_search(self, budget: ResourceBudget) -> bool:
        """Check if we can perform another web search"""
        return self.searches < budget.max_searches
    
    def can_compute(self, budget: ResourceBudget) -> bool:
        """Check if we can perform another compute"""
        return self.computes < budget.max_computes
    
    def can_fetch_games(self, count: int, budget: ResourceBudget) -> bool:
        """Check if we can fetch the specified number of games"""
        return (self.games_fetched + count) <= budget.max_games_total
    
    def to_dict(self) -> dict:
        """Convert to dictionary for logging/debugging"""
        return {
            "passes": self.passes,
            "fetches": self.fetches,
            "analyses": self.analyses,
            "searches": self.searches,
            "computes": self.computes,
            "games_fetched": self.games_fetched,
            "llm_calls": self.llm_calls,
            "llm_tokens": self.llm_tokens_input + self.llm_tokens_output,
            "api_calls": self.api_calls,
            "retries": self.retries,
            "validation_errors": self.validation_errors,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "estimated_cost_usd": round(self.estimated_cost_usd, 4)
        }


class CancellationToken:
    """
    Thread-safe cancellation token for aborting long-running operations.
    Used when user navigates away or sends a new message.
    """
    
    def __init__(self):
        self._cancelled = False
        self._lock = threading.Lock()
        self._reason: Optional[str] = None
    
    def cancel(self, reason: str = "user_cancelled"):
        """Request cancellation"""
        with self._lock:
            self._cancelled = True
            self._reason = reason
    
    @property
    def is_cancelled(self) -> bool:
        """Check if cancellation was requested"""
        with self._lock:
            return self._cancelled
    
    @property
    def reason(self) -> Optional[str]:
        """Get the cancellation reason"""
        with self._lock:
            return self._reason
    
    def check(self) -> None:
        """
        Check for cancellation and raise if cancelled.
        Use in long-running loops.
        """
        if self.is_cancelled:
            raise CancellationError(self.reason or "cancelled")
    
    def reset(self):
        """Reset the cancellation token for reuse"""
        with self._lock:
            self._cancelled = False
            self._reason = None


class CancellationError(Exception):
    """Raised when an operation is cancelled"""
    pass


class BudgetExceededError(Exception):
    """Raised when resource budget is exceeded"""
    
    def __init__(self, reason: str, usage: ResourceUsage):
        self.reason = reason
        self.usage = usage
        super().__init__(f"Budget exceeded: {reason}")


class ContextChangedError(Exception):
    """Raised when the chess context changes during processing"""
    
    def __init__(self, old_hash: str, new_hash: str):
        self.old_hash = old_hash
        self.new_hash = new_hash
        super().__init__("Context changed during processing")

