"""
Multi-Pass Interpreter Loop
Orchestrates multiple interpreter passes, executing actions and accumulating context
until ready to generate a final plan for the main LLM.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Callable, Tuple
from enum import Enum
import json
import time
import hashlib
import asyncio

from interpreter_budget import (
    ResourceBudget,
    ResourceUsage,
    CancellationToken,
    CancellationError,
    BudgetExceededError,
    ContextChangedError
)


class ActionType(str, Enum):
    """Types of actions the interpreter can request"""
    FETCH = "fetch"         # Fetch games from chess platforms
    ANALYZE = "analyze"     # Run position/game analysis
    SEARCH = "search"       # Web search for information
    COMPUTE = "compute"     # Run calculations (baseline, correlation, etc.)


@dataclass
class InterpreterAction:
    """A single action requested by the interpreter"""
    action_type: ActionType
    params: Dict[str, Any]
    reasoning: str
    depends_on: Optional[str] = None  # ID of action this depends on
    
    @property
    def id(self) -> str:
        """Generate unique ID for this action"""
        content = f"{self.action_type.value}:{json.dumps(self.params, sort_keys=True)}"
        return hashlib.md5(content.encode()).hexdigest()[:8]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_type": self.action_type.value,
            "params": self.params,
            "reasoning": self.reasoning,
            "depends_on": self.depends_on
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'InterpreterAction':
        return cls(
            action_type=ActionType(data["action_type"]),
            params=data.get("params", {}),
            reasoning=data.get("reasoning", ""),
            depends_on=data.get("depends_on")
        )


@dataclass
class ActionResult:
    """Result of executing an action"""
    action_id: str
    success: bool
    data: Any = None
    error: Optional[str] = None
    duration_ms: int = 0
    retries: int = 0
    from_cache: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "action_id": self.action_id,
            "success": self.success,
            "duration_ms": self.duration_ms
        }
        if self.error:
            result["error"] = self.error
        if self.from_cache:
            result["from_cache"] = True
        return result


@dataclass
class PassRecord:
    """Record of a single interpreter pass"""
    pass_number: int
    actions_requested: List[InterpreterAction]
    action_results: Dict[str, ActionResult]
    insights: List[str]
    duration_ms: int
    llm_tokens_used: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "pass": self.pass_number,
            "actions": [a.action_type.value for a in self.actions_requested],
            "results_summary": {
                aid: {"success": r.success, "cached": r.from_cache}
                for aid, r in self.action_results.items()
            },
            "insights": self.insights,
            "duration_ms": self.duration_ms
        }


@dataclass
class InterpreterOutput:
    """Output from a single interpreter pass"""
    is_ready: bool
    actions: List[InterpreterAction] = field(default_factory=list)
    insights: List[str] = field(default_factory=list)
    final_plan: Optional[Any] = None  # OrchestrationPlan when is_ready=True
    raw_response: Optional[str] = None
    tokens_used: int = 0
    
    @classmethod
    def ready(cls, plan: Any) -> 'InterpreterOutput':
        """Create a ready output with final plan"""
        return cls(is_ready=True, final_plan=plan)
    
    @classmethod
    def needs_actions(cls, actions: List[InterpreterAction], insights: List[str] = None) -> 'InterpreterOutput':
        """Create an output requesting actions"""
        return cls(is_ready=False, actions=actions, insights=insights or [])


@dataclass
class InterpreterState:
    """
    Accumulated state across interpreter passes.
    Tracks context, executed actions, and insights.
    """
    original_message: str
    original_context: Dict[str, Any]
    context_hash: str
    passes: List[PassRecord] = field(default_factory=list)
    accumulated_data: Dict[str, Any] = field(default_factory=dict)
    insights: List[str] = field(default_factory=list)
    usage: ResourceUsage = field(default_factory=ResourceUsage)
    
    @classmethod
    def create(cls, message: str, context: Dict[str, Any]) -> 'InterpreterState':
        """Create initial state from message and context"""
        # Hash critical context fields for staleness detection
        critical = {
            "fen": context.get("fen"),
            "pgn": context.get("pgn"),
            "mode": context.get("mode")
        }
        context_hash = hashlib.md5(
            json.dumps(critical, sort_keys=True).encode()
        ).hexdigest()
        
        return cls(
            original_message=message,
            original_context=context,
            context_hash=context_hash
        )
    
    def add_pass(
        self, 
        actions: List[InterpreterAction], 
        results: Dict[str, ActionResult],
        insights: List[str],
        duration_ms: int,
        tokens: int = 0
    ):
        """Record a completed pass"""
        self.usage.passes += 1
        
        record = PassRecord(
            pass_number=len(self.passes) + 1,
            actions_requested=actions,
            action_results=results,
            insights=insights,
            duration_ms=duration_ms,
            llm_tokens_used=tokens
        )
        self.passes.append(record)
        
        # Accumulate insights
        self.insights.extend(insights)
        
        # Store action results in accumulated data
        for action in actions:
            if action.id in results and results[action.id].success:
                key = f"{action.action_type.value}_{len(self.passes)}_{action.id}"
                self.accumulated_data[key] = results[action.id].data
    
    def get_context_for_llm(self) -> Dict[str, Any]:
        """Build context for the next LLM pass"""
        return {
            **self.original_context,
            "previous_passes": [p.to_dict() for p in self.passes],
            "accumulated_data_keys": list(self.accumulated_data.keys()),
            "insights_so_far": self.insights,
            "pass_count": len(self.passes)
        }
    
    def get_data_summary(self) -> str:
        """Get a summarized view of accumulated data for LLM context"""
        from data_summarizer import summarize_accumulated
        return summarize_accumulated(self.accumulated_data)
    
    def check_context_staleness(self, current_context: Dict[str, Any]) -> bool:
        """Check if context has changed since start"""
        critical = {
            "fen": current_context.get("fen"),
            "pgn": current_context.get("pgn"),
            "mode": current_context.get("mode")
        }
        current_hash = hashlib.md5(
            json.dumps(critical, sort_keys=True).encode()
        ).hexdigest()
        return current_hash != self.context_hash


class InterpreterLoop:
    """
    Orchestrates multiple interpreter passes until ready.
    Executes actions, accumulates context, and handles safety controls.
    """
    
    def __init__(
        self,
        interpreter,  # RequestInterpreter instance
        action_executor,  # ActionExecutor instance
        budget: ResourceBudget = None
    ):
        self.interpreter = interpreter
        self.executor = action_executor
        self.budget = budget or ResourceBudget.default()
    
    async def run(
        self,
        message: str,
        context: Dict[str, Any],
        status_callback: Optional[Callable] = None,
        cancel_token: Optional[CancellationToken] = None,
        get_current_context: Optional[Callable] = None
    ) -> Any:  # Returns OrchestrationPlan
        """
        Run the interpreter loop until ready or budget exhausted.
        
        Args:
            message: User message
            context: Current context (fen, pgn, mode, etc.)
            status_callback: Optional callback for status updates
            cancel_token: Optional token for cancellation
            get_current_context: Optional callback to get current context for staleness check
        
        Returns:
            OrchestrationPlan for the main LLM
        """
        state = InterpreterState.create(message, context)
        
        while True:
            # Check cancellation
            if cancel_token and cancel_token.is_cancelled:
                return self._build_cancelled_plan(state, cancel_token.reason)
            
            # Check budget
            can_continue, reason = state.usage.can_continue(self.budget)
            if not can_continue:
                return self._build_fallback_plan(state, reason)
            
            # Check context staleness
            if get_current_context:
                if state.check_context_staleness(get_current_context()):
                    raise ContextChangedError(state.context_hash, "new")
            
            # Emit status
            pass_num = len(state.passes) + 1
            if status_callback:
                status_callback(
                    phase="thinking",
                    message=f"Pass {pass_num}/{self.budget.max_passes}...",
                    pass_number=pass_num,
                    timestamp=time.time()
                )
            
            # Run interpreter pass
            start_time = time.time()
            try:
                output = await self._run_pass(state, status_callback)
            except Exception as e:
                print(f"   ❌ Interpreter pass failed: {e}")
                state.usage.record_validation_error()
                
                # Check if we should fallback
                can_continue, reason = state.usage.can_continue(self.budget)
                if not can_continue:
                    return self._build_fallback_plan(state, reason)
                continue
            
            # Check if ready
            if output.is_ready:
                if status_callback:
                    status_callback(
                        phase="ready",
                        message="Interpretation complete",
                        timestamp=time.time()
                    )
                return output.final_plan
            
            # Execute requested actions
            if output.actions:
                if status_callback:
                    status_callback(
                        phase="executing",
                        message=f"Executing {len(output.actions)} actions...",
                        timestamp=time.time()
                    )
                
                results = await self._execute_actions(
                    output.actions, 
                    state, 
                    status_callback,
                    cancel_token
                )
                
                # Record pass
                duration_ms = int((time.time() - start_time) * 1000)
                state.add_pass(
                    output.actions, 
                    results, 
                    output.insights,
                    duration_ms,
                    output.tokens_used
                )
            else:
                # No actions but not ready - LLM is confused
                state.usage.record_validation_error()
    
    async def _run_pass(
        self, 
        state: InterpreterState,
        status_callback: Optional[Callable] = None
    ) -> InterpreterOutput:
        """Run a single interpreter pass"""
        from interpreter_validator import validate_interpreter_output, sanitize_output
        
        # Build context for LLM
        context_for_llm = state.get_context_for_llm()
        data_summary = state.get_data_summary()
        
        # Call interpreter LLM
        response = await self.interpreter.interpret_single_pass(
            state.original_message,
            context_for_llm,
            data_summary,
            is_multi_pass=True
        )
        
        # Track token usage
        if hasattr(response, 'tokens_used'):
            state.usage.record_llm_call(
                response.tokens_used.get('input', 0),
                response.tokens_used.get('output', 0)
            )
        
        # Validate response
        raw_json = response.raw_json if hasattr(response, 'raw_json') else response
        sanitized = sanitize_output(raw_json)
        is_valid, errors = validate_interpreter_output(sanitized)
        
        if not is_valid:
            print(f"   ⚠️ Validation errors: {errors}")
            state.usage.record_validation_error()
            # Return empty actions to trigger retry
            return InterpreterOutput(is_ready=False, actions=[], insights=[])
        
        # Parse output
        if sanitized.get("is_ready"):
            from orchestration_plan import OrchestrationPlan
            plan = OrchestrationPlan.from_dict(sanitized["final_plan"])
            return InterpreterOutput.ready(plan)
        else:
            actions = [
                InterpreterAction.from_dict(a) 
                for a in sanitized.get("actions", [])
            ]
            insights = sanitized.get("insights", [])
            return InterpreterOutput.needs_actions(actions, insights)
    
    async def _execute_actions(
        self,
        actions: List[InterpreterAction],
        state: InterpreterState,
        status_callback: Optional[Callable] = None,
        cancel_token: Optional[CancellationToken] = None
    ) -> Dict[str, ActionResult]:
        """Execute actions, handling parallelism and dependencies"""
        results: Dict[str, ActionResult] = {}
        
        # Separate independent and dependent actions
        independent = [a for a in actions if not a.depends_on]
        dependent = [a for a in actions if a.depends_on]
        
        # Execute independent actions in parallel
        if independent:
            # Check budget before executing
            for action in independent:
                if not self._can_execute_action(action, state):
                    results[action.id] = ActionResult(
                        action_id=action.id,
                        success=False,
                        error="budget_exceeded"
                    )
                    continue
            
            # Filter to only executable actions
            executable = [a for a in independent if a.id not in results]
            
            if executable:
                parallel_results = await asyncio.gather(
                    *[self._execute_single_action(a, state, status_callback, cancel_token) 
                      for a in executable],
                    return_exceptions=True
                )
                
                for action, result in zip(executable, parallel_results):
                    if isinstance(result, Exception):
                        results[action.id] = ActionResult(
                            action_id=action.id,
                            success=False,
                            error=str(result)
                        )
                    else:
                        results[action.id] = result
        
        # Execute dependent actions sequentially
        for action in dependent:
            if cancel_token and cancel_token.is_cancelled:
                results[action.id] = ActionResult(
                    action_id=action.id,
                    success=False,
                    error="cancelled"
                )
                continue
            
            # Check if dependency succeeded
            if action.depends_on and action.depends_on not in results:
                results[action.id] = ActionResult(
                    action_id=action.id,
                    success=False,
                    error="dependency_not_found"
                )
                continue
            
            if action.depends_on and not results[action.depends_on].success:
                results[action.id] = ActionResult(
                    action_id=action.id,
                    success=False,
                    error="dependency_failed"
                )
                continue
            
            if not self._can_execute_action(action, state):
                results[action.id] = ActionResult(
                    action_id=action.id,
                    success=False,
                    error="budget_exceeded"
                )
                continue
            
            result = await self._execute_single_action(
                action, state, status_callback, cancel_token
            )
            results[action.id] = result
        
        return results
    
    async def _execute_single_action(
        self,
        action: InterpreterAction,
        state: InterpreterState,
        status_callback: Optional[Callable] = None,
        cancel_token: Optional[CancellationToken] = None
    ) -> ActionResult:
        """Execute a single action with retry logic"""
        start_time = time.time()
        retries = 0
        
        while retries <= self.budget.max_retries_per_action:
            if cancel_token and cancel_token.is_cancelled:
                return ActionResult(
                    action_id=action.id,
                    success=False,
                    error="cancelled"
                )
            
            try:
                if status_callback:
                    status_callback(
                        phase="executing",
                        message=f"{action.action_type.value}: {action.reasoning[:50]}...",
                        tool=action.action_type.value,
                        timestamp=time.time()
                    )
                
                result = await self.executor.execute(action, state.accumulated_data)
                
                # Track usage
                self._record_action_usage(action, state, result)
                
                duration_ms = int((time.time() - start_time) * 1000)
                return ActionResult(
                    action_id=action.id,
                    success=True,
                    data=result,
                    duration_ms=duration_ms,
                    retries=retries,
                    from_cache=getattr(result, 'from_cache', False)
                )
                
            except Exception as e:
                retries += 1
                state.usage.record_retry()
                
                if retries > self.budget.max_retries_per_action:
                    duration_ms = int((time.time() - start_time) * 1000)
                    return ActionResult(
                        action_id=action.id,
                        success=False,
                        error=str(e),
                        duration_ms=duration_ms,
                        retries=retries
                    )
                
                # Exponential backoff
                await asyncio.sleep(2 ** retries * 0.5)
    
    def _can_execute_action(self, action: InterpreterAction, state: InterpreterState) -> bool:
        """Check if we can execute an action within budget"""
        if action.action_type == ActionType.FETCH:
            return state.usage.can_fetch(self.budget)
        elif action.action_type == ActionType.ANALYZE:
            return state.usage.can_analyze(self.budget)
        elif action.action_type == ActionType.SEARCH:
            return state.usage.can_search(self.budget)
        elif action.action_type == ActionType.COMPUTE:
            return state.usage.can_compute(self.budget)
        return True
    
    def _record_action_usage(
        self, 
        action: InterpreterAction, 
        state: InterpreterState,
        result: Any
    ):
        """Record action usage in state"""
        if action.action_type == ActionType.FETCH:
            games_count = len(result.get('games', [])) if isinstance(result, dict) else 0
            state.usage.record_fetch(games_count)
        elif action.action_type == ActionType.ANALYZE:
            state.usage.record_analysis()
        elif action.action_type == ActionType.SEARCH:
            state.usage.record_search()
        elif action.action_type == ActionType.COMPUTE:
            state.usage.record_compute()
    
    def _build_fallback_plan(self, state: InterpreterState, reason: str) -> Any:
        """Build a fallback plan when we can't continue"""
        from orchestration_plan import (
            OrchestrationPlan, 
            Mode, 
            ResponseStyle,
            ResponseGuidelines
        )
        
        # Determine best mode from accumulated data
        if any("fetch" in k for k in state.accumulated_data.keys()):
            mode = Mode.REVIEW
        elif any("analyze" in k for k in state.accumulated_data.keys()):
            mode = Mode.ANALYZE
        else:
            mode = Mode.CHAT
        
        # Build summary of what we learned
        summary_parts = [
            f"Original request: {state.original_message}",
            f"Completed {len(state.passes)} processing passes.",
            f"Stopped due to: {reason}"
        ]
        
        if state.insights:
            summary_parts.append("Insights gathered:")
            for insight in state.insights[:5]:
                summary_parts.append(f"  - {insight}")
        
        return OrchestrationPlan(
            mode=mode,
            user_intent_summary=state.original_message,
            mode_confidence=0.6,  # Lower confidence for fallback
            pre_computed_analysis=state.accumulated_data,
            system_prompt_additions="\n".join(summary_parts),
            response_guidelines=ResponseGuidelines(
                style=ResponseStyle.CONVERSATIONAL,
                focus_aspects=["Use available data to help user"]
            )
        )
    
    def _build_cancelled_plan(self, state: InterpreterState, reason: str) -> Any:
        """Build a plan for cancelled requests"""
        from orchestration_plan import (
            OrchestrationPlan, 
            Mode, 
            ResponseGuidelines,
            ResponseStyle
        )
        
        return OrchestrationPlan(
            mode=Mode.CHAT,
            user_intent_summary=f"Cancelled: {state.original_message}",
            mode_confidence=0.5,
            system_prompt_additions=f"Request was cancelled ({reason}). Acknowledge this briefly.",
            response_guidelines=ResponseGuidelines(
                style=ResponseStyle.BRIEF,
                max_length="short"
            )
        )

