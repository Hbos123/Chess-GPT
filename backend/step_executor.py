"""
Step Executor
Executes investigation plans step-by-step, handling dependencies and failures
"""

import asyncio
import re
import time
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
from datetime import datetime

from planning_agent import InvestigationPlan, Step


# Human-friendly tool messages
TOOL_MESSAGES = {
    "web_search": "Searching the web...",
    "fetch_games_filtered": "Fetching games...",
    "fetch_tournament_games": "Fetching tournament games...",
    "multi_depth_analyze": "Running multi-depth analysis...",
    "engine_correlation": "Checking engine correlation...",
    "calculate_baseline": "Calculating player baseline...",
    "detect_anomalies": "Detecting anomalies...",
    "find_critical_moments": "Finding critical moments...",
    "score_move_complexity": "Scoring move complexity...",
    "analyze_position": "Analyzing position...",
    "analyze_move": "Analyzing move...",
    "review_full_game": "Reviewing game...",
    "compare_to_peers": "Comparing to peers...",
}


@dataclass
class StepResult:
    """Result of executing a single step"""
    step_id: str
    success: bool
    data: Any = None
    error: str = None
    duration_ms: int = 0
    retries: int = 0


@dataclass
class ExecutionResult:
    """Result of executing an entire plan"""
    success: bool
    step_results: Dict[str, StepResult]
    synthesis: str = None
    total_duration_ms: int = 0
    failed_steps: List[str] = None
    
    def get_step_data(self, step_id: str) -> Any:
        """Get data from a specific step"""
        if step_id in self.step_results:
            return self.step_results[step_id].data
        return None


class StepExecutor:
    """Executes investigation plans step-by-step"""
    
    def __init__(
        self,
        tool_executor = None,
        openai_client = None,
        engine_queue = None,
        status_callback: Callable[[str, str], None] = None
    ):
        """
        Initialize step executor.
        
        Args:
            tool_executor: ToolExecutor instance for running tools
            openai_client: OpenAI client for synthesis
            engine_queue: Stockfish engine queue
            status_callback: Optional callback for status updates (step_id, message)
        """
        self.tool_executor = tool_executor
        self.client = openai_client
        self.engine_queue = engine_queue
        self.status_callback = status_callback
        
        # Tool function registry
        self._tools = self._register_tools()
    
    def _register_tools(self) -> Dict[str, Callable]:
        """Register available tool functions"""
        from tools.web_search import web_search
        from tools.multi_depth_analysis import multi_depth_analyze
        from tools.engine_correlation import engine_correlation
        from tools.anomaly_detection import detect_anomalies
        from tools.player_baseline import calculate_baseline
        from tools.critical_moments import find_critical_moments
        from tools.complexity_scorer import score_move_complexity
        
        return {
            "web_search": web_search,
            "multi_depth_analyze": multi_depth_analyze,
            "engine_correlation": engine_correlation,
            "detect_anomalies": detect_anomalies,
            "calculate_baseline": calculate_baseline,
            "find_critical_moments": find_critical_moments,
            "score_move_complexity": score_move_complexity,
        }
    
    async def execute_plan(
        self,
        plan: InvestigationPlan,
        context: Dict[str, Any] = None,
        status_callback: Optional[Callable] = None
    ) -> ExecutionResult:
        """
        Execute an investigation plan.
        
        Args:
            plan: The investigation plan to execute
            context: Additional context (can override plan.context)
            status_callback: Optional callback for status updates
            
        Returns:
            ExecutionResult with all step results and synthesis
        """
        # Use provided callback or fall back to instance callback
        if status_callback:
            self.status_callback = status_callback
            
        start_time = datetime.now()
        context = {**plan.context, **(context or {})}
        
        step_results: Dict[str, StepResult] = {}
        failed_steps: List[str] = []
        
        # Build dependency graph
        remaining_steps = {s.id: s for s in plan.steps}
        completed = set()
        total_steps = len(plan.steps)
        
        # Execute steps respecting dependencies
        while remaining_steps:
            # Find steps ready to execute (all dependencies met)
            ready_steps = []
            for step_id, step in remaining_steps.items():
                if all(dep in completed for dep in step.depends_on):
                    ready_steps.append(step)
            
            if not ready_steps:
                # No steps ready but steps remaining = circular dependency or failed deps
                for step_id in remaining_steps:
                    failed_steps.append(step_id)
                    step_results[step_id] = StepResult(
                        step_id=step_id,
                        success=False,
                        error="Dependencies not met"
                    )
                break
            
            # Calculate progress
            progress = len(completed) / total_steps if total_steps > 0 else 0
            
            # Check which can run in parallel
            parallel_group = self._find_parallel_group(ready_steps, plan.parallel_groups)
            
            if len(parallel_group) > 1:
                # Execute in parallel
                tool_names = [s.tool for s in parallel_group]
                self._update_status(
                    "parallel", 
                    f"Running {len(parallel_group)} tools in parallel: {', '.join(tool_names)}",
                    phase="executing",
                    progress=progress
                )
                
                tasks = [
                    self._execute_step(step, step_results, context)
                    for step in parallel_group
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for step, result in zip(parallel_group, results):
                    if isinstance(result, Exception):
                        step_results[step.id] = StepResult(
                            step_id=step.id,
                            success=False,
                            error=str(result)
                        )
                        failed_steps.append(step.id)
                    else:
                        step_results[step.id] = result
                        if not result.success:
                            failed_steps.append(step.id)
                    
                    completed.add(step.id)
                    del remaining_steps[step.id]
            else:
                # Execute sequentially
                step = ready_steps[0]
                progress = len(completed) / total_steps if total_steps > 0 else 0
                
                # Emit status for this step
                self._update_status(
                    step.id,
                    self._get_tool_message(step.tool, step.description if hasattr(step, 'description') else None),
                    phase="executing",
                    tool=step.tool,
                    progress=progress
                )
                
                result = await self._execute_step(step, step_results, context)
                step_results[step.id] = result
                
                if not result.success:
                    failed_steps.append(step.id)
                
                completed.add(step.id)
                del remaining_steps[step.id]
        
        # Calculate total duration
        total_duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        
        # Synthesize results
        synthesis = None
        if plan.synthesis_prompt and self.client:
            self._update_status(
                "synthesize",
                "Combining findings...",
                phase="synthesizing",
                progress=0.95
            )
            synthesis = await self._synthesize_results(
                step_results, plan.synthesis_prompt
            )
            self._update_status(
                "complete",
                "Analysis complete",
                phase="complete",
                progress=1.0
            )
        
        return ExecutionResult(
            success=len(failed_steps) == 0,
            step_results=step_results,
            synthesis=synthesis,
            total_duration_ms=total_duration_ms,
            failed_steps=failed_steps if failed_steps else None
        )
    
    async def _execute_step(
        self,
        step: Step,
        previous_results: Dict[str, StepResult],
        context: Dict[str, Any]
    ) -> StepResult:
        """Execute a single step"""
        start_time = datetime.now()
        self._update_status(step.id, f"Executing: {step.description or step.tool}")
        
        try:
            # Resolve argument references
            resolved_args = self._resolve_references(step.args, previous_results, context)
            
            # Get tool function
            tool_func = self._tools.get(step.tool)
            
            if not tool_func:
                # Try tool executor for other tools
                if self.tool_executor:
                    result = await self.tool_executor.execute(step.tool, resolved_args)
                else:
                    return StepResult(
                        step_id=step.id,
                        success=False,
                        error=f"Unknown tool: {step.tool}"
                    )
            else:
                # Add engine queue if needed
                if "engine_queue" in tool_func.__code__.co_varnames:
                    resolved_args["engine_queue"] = self.engine_queue
                
                # Execute tool
                result = await tool_func(**resolved_args)
            
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            
            # Check for error in result
            if isinstance(result, dict) and "error" in result:
                return StepResult(
                    step_id=step.id,
                    success=False,
                    data=result,
                    error=result["error"],
                    duration_ms=duration_ms
                )
            
            self._update_status(step.id, f"Completed in {duration_ms}ms")
            
            return StepResult(
                step_id=step.id,
                success=True,
                data=result,
                duration_ms=duration_ms
            )
            
        except Exception as e:
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            self._update_status(step.id, f"Failed: {str(e)}")
            
            return StepResult(
                step_id=step.id,
                success=False,
                error=str(e),
                duration_ms=duration_ms
            )
    
    def _resolve_references(
        self,
        args: Dict[str, Any],
        previous_results: Dict[str, StepResult],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Resolve $step_id.field references in arguments.
        
        Examples:
            $step_1.games -> previous_results["step_1"].data["games"]
            $PLAYER -> context["PLAYER"]
        """
        resolved = {}
        
        for key, value in args.items():
            if isinstance(value, str):
                resolved[key] = self._resolve_string(value, previous_results, context)
            elif isinstance(value, list):
                resolved[key] = [
                    self._resolve_string(v, previous_results, context) if isinstance(v, str) else v
                    for v in value
                ]
            elif isinstance(value, dict):
                resolved[key] = self._resolve_references(value, previous_results, context)
            else:
                resolved[key] = value
        
        return resolved
    
    def _resolve_string(
        self,
        value: str,
        previous_results: Dict[str, StepResult],
        context: Dict[str, Any]
    ) -> Any:
        """Resolve a single string value"""
        if not value.startswith("$"):
            return value
        
        # $step_id.field pattern
        match = re.match(r'\$(\w+)\.(\w+)', value)
        if match:
            step_id = match.group(1)
            field = match.group(2)
            
            if step_id in previous_results:
                data = previous_results[step_id].data
                if isinstance(data, dict) and field in data:
                    return data[field]
                return data
            return value
        
        # $VARIABLE pattern (context)
        var_name = value[1:]
        if var_name in context:
            return context[var_name]
        
        return value
    
    def _find_parallel_group(
        self,
        ready_steps: List[Step],
        parallel_groups: List[List[str]]
    ) -> List[Step]:
        """Find steps that can run in parallel"""
        if not parallel_groups:
            return [ready_steps[0]] if ready_steps else []
        
        ready_ids = {s.id for s in ready_steps}
        
        # Find a parallel group where all members are ready
        for group in parallel_groups:
            group_set = set(group)
            if group_set.issubset(ready_ids):
                return [s for s in ready_steps if s.id in group_set]
        
        # No full group ready, return first step
        return [ready_steps[0]] if ready_steps else []
    
    async def _synthesize_results(
        self,
        step_results: Dict[str, StepResult],
        synthesis_prompt: str
    ) -> str:
        """Use LLM to synthesize all results"""
        if not self.client:
            return None
        
        try:
            # Build results summary
            results_summary = []
            for step_id, result in step_results.items():
                if result.success:
                    # Truncate large data
                    data_str = str(result.data)
                    if len(data_str) > 2000:
                        data_str = data_str[:2000] + "... (truncated)"
                    results_summary.append(f"## {step_id}\n{data_str}")
                else:
                    results_summary.append(f"## {step_id}\nFailed: {result.error}")
            
            user_prompt = f"""Based on these investigation results, provide a synthesis:

{chr(10).join(results_summary)}

---

{synthesis_prompt}"""

            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert chess analyst synthesizing investigation findings. Be thorough, balanced, and cite specific evidence from the results."
                    },
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.5,
                max_tokens=2000
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            return f"Synthesis error: {str(e)}"
    
    def _update_status(
        self, 
        step_id: str, 
        message: str, 
        phase: str = "executing",
        tool: Optional[str] = None,
        progress: Optional[float] = None
    ):
        """Send status update via callback"""
        print(f"   [{step_id}] {message}")
        if self.status_callback:
            self.status_callback(
                phase=phase,
                message=message,
                tool=tool,
                progress=progress,
                timestamp=time.time()
            )
    
    def _get_tool_message(self, tool_name: str, target: str = None) -> str:
        """Get human-friendly message for a tool"""
        base_msg = TOOL_MESSAGES.get(tool_name, f"Running {tool_name}...")
        if target:
            return f"{base_msg} ({target})"
        return base_msg


async def run_investigation(
    query: str,
    context: Dict[str, Any] = None,
    openai_client = None,
    engine_queue = None,
    tool_executor = None,
    status_callback: Callable = None
) -> ExecutionResult:
    """
    Convenience function to run a complete investigation.
    
    Args:
        query: Investigation query
        context: Additional context
        openai_client: OpenAI client
        engine_queue: Stockfish engine queue
        tool_executor: ToolExecutor instance
        status_callback: Status update callback
        
    Returns:
        ExecutionResult
    """
    from planning_agent import InvestigationPlanner
    
    # Create plan
    planner = InvestigationPlanner(openai_client)
    plan = await planner.create_plan(query, context)
    
    # Execute plan
    executor = StepExecutor(
        tool_executor=tool_executor,
        openai_client=openai_client,
        engine_queue=engine_queue,
        status_callback=status_callback
    )
    
    return await executor.execute_plan(plan, context)

