"""
Investigation Planner
LLM-based agent that creates multi-step execution plans for complex queries
"""

import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum


class InvestigationType(Enum):
    CHEATING_ANALYSIS = "cheating_analysis"
    PLAYER_RESEARCH = "player_research"
    GAME_COMPARISON = "game_comparison"
    PERFORMANCE_TREND = "performance_trend"
    OPENING_ANALYSIS = "opening_analysis"
    TOURNAMENT_REVIEW = "tournament_review"
    GENERAL_INVESTIGATION = "general_investigation"


@dataclass
class Step:
    """A single step in an investigation plan"""
    id: str
    tool: str
    args: Dict[str, Any]
    depends_on: List[str] = field(default_factory=list)
    description: str = ""
    optional: bool = False
    retry_on_fail: bool = True
    timeout_seconds: int = 60


@dataclass
class InvestigationPlan:
    """Complete investigation plan"""
    investigation_type: InvestigationType
    steps: List[Step]
    synthesis_prompt: str
    context: Dict[str, Any] = field(default_factory=dict)
    parallel_groups: List[List[str]] = field(default_factory=list)  # Steps that can run in parallel
    max_duration_seconds: int = 300
    
    def to_dict(self) -> Dict:
        return {
            "investigation_type": self.investigation_type.value,
            "steps": [
                {
                    "id": s.id,
                    "tool": s.tool,
                    "args": s.args,
                    "depends_on": s.depends_on,
                    "description": s.description,
                    "optional": s.optional
                }
                for s in self.steps
            ],
            "synthesis_prompt": self.synthesis_prompt,
            "parallel_groups": self.parallel_groups,
            "max_duration_seconds": self.max_duration_seconds
        }


PLANNER_SYSTEM_PROMPT = """You are an investigation planner for chess analysis. Given a user query, create a detailed execution plan.

## Available Tools

### External Data
- web_search(query, max_results, filter): Search web for chess news/info
- fetch_games_filtered(username, platform, date_from, date_to, ...): Get player games
- fetch_tournament_games(player_name, tournament_name, year, source): Get tournament games

### Analysis
- multi_depth_analyze(pgn, depths, focus_side): Analyze game at multiple depths
- engine_correlation(pgn, depth, top_n, exclude_book_moves): Check engine correlation
- find_critical_moments(pgn, threshold_cp): Find turning points
- score_move_complexity(fen, move, depth): Assess move difficulty

### Statistics
- calculate_baseline(games, exclude_outliers): Calculate player baseline
- detect_anomalies(test_games, baseline, metrics): Detect statistical anomalies

## Output Format
Return JSON:
```json
{
    "investigation_type": "cheating_analysis|player_research|...",
    "steps": [
        {
            "id": "step_1",
            "tool": "tool_name",
            "args": {"param": "value"},
            "depends_on": [],
            "description": "What this step does"
        }
    ],
    "parallel_groups": [["step_1", "step_2"], ["step_4"]],
    "synthesis_prompt": "How to combine results..."
}
```

## Dependency References
Use $step_id.field to reference previous results:
- $step_1.games -> games from step 1
- $step_2.baseline -> baseline from step 2

## Guidelines
1. Start with data gathering (web search, game fetching)
2. Then analyze (engine correlation, multi-depth)
3. Then statistical comparison (baseline, anomaly detection)
4. Group independent steps for parallel execution
5. Include clear synthesis prompt for final summary"""


class InvestigationPlanner:
    """Creates multi-step plans for complex investigations"""
    
    def __init__(self, openai_client=None, llm_router=None):
        self.client = openai_client
        self.llm_router = llm_router
        self._templates = self._load_templates()
    
    async def create_plan(
        self,
        query: str,
        context: Dict[str, Any] = None
    ) -> InvestigationPlan:
        """
        Create an investigation plan from a natural language query.
        
        Args:
            query: User's investigation request
            context: Additional context (player info, games, etc.)
            
        Returns:
            InvestigationPlan ready for execution
        """
        context = context or {}
        
        # Try to detect investigation type from query
        inv_type = self._detect_investigation_type(query)
        
        # Check for template match
        template_plan = self._try_template_match(query, inv_type, context)
        if template_plan:
            return template_plan
        
        # Use LLM for complex planning
        if self.client:
            return await self._llm_plan(query, context)
        
        # Fallback: basic plan
        return self._create_basic_plan(query, inv_type, context)
    
    def _detect_investigation_type(self, query: str) -> InvestigationType:
        """Detect the type of investigation from the query"""
        query_lower = query.lower()
        
        if any(word in query_lower for word in ["cheat", "cheating", "engine", "computer assistance", "suspicious"]):
            return InvestigationType.CHEATING_ANALYSIS
        
        if any(word in query_lower for word in ["tournament", "event", "competition"]):
            return InvestigationType.TOURNAMENT_REVIEW
        
        if any(word in query_lower for word in ["opening", "repertoire", "theory"]):
            return InvestigationType.OPENING_ANALYSIS
        
        if any(word in query_lower for word in ["trend", "progress", "improvement", "rating"]):
            return InvestigationType.PERFORMANCE_TREND
        
        if any(word in query_lower for word in ["compare", "vs", "versus", "against"]):
            return InvestigationType.GAME_COMPARISON
        
        if any(word in query_lower for word in ["who is", "tell me about", "profile"]):
            return InvestigationType.PLAYER_RESEARCH
        
        return InvestigationType.GENERAL_INVESTIGATION
    
    def _load_templates(self) -> Dict[InvestigationType, Dict]:
        """Load investigation templates"""
        return {
            InvestigationType.CHEATING_ANALYSIS: {
                "steps": [
                    Step(
                        id="web_context",
                        tool="web_search",
                        args={"query": "$PLAYER $EVENT cheating allegations"},
                        description="Get news context about allegations"
                    ),
                    Step(
                        id="fetch_suspect_games",
                        tool="fetch_tournament_games",
                        args={
                            "player_name": "$PLAYER",
                            "tournament_name": "$EVENT",
                            "year": "$YEAR"
                        },
                        description="Get games from suspicious event"
                    ),
                    Step(
                        id="fetch_baseline_games",
                        tool="fetch_games_filtered",
                        args={
                            "username": "$USERNAME",
                            "platform": "$PLATFORM",
                            "date_to": "$EVENT_DATE"
                        },
                        depends_on=["fetch_suspect_games"],
                        description="Get historical games for baseline"
                    ),
                    Step(
                        id="calculate_baseline",
                        tool="calculate_baseline",
                        args={"games": "$fetch_baseline_games.games"},
                        depends_on=["fetch_baseline_games"],
                        description="Calculate historical baseline"
                    ),
                    Step(
                        id="multi_depth",
                        tool="multi_depth_analyze",
                        args={
                            "pgn": "$fetch_suspect_games.games",
                            "depths": [15, 25, 40]
                        },
                        depends_on=["fetch_suspect_games"],
                        description="Multi-depth analysis of suspect games"
                    ),
                    Step(
                        id="engine_correlation",
                        tool="engine_correlation",
                        args={
                            "pgn": "$fetch_suspect_games.games",
                            "depth": 30
                        },
                        depends_on=["fetch_suspect_games"],
                        description="Check engine move correlation"
                    ),
                    Step(
                        id="anomaly_detection",
                        tool="detect_anomalies",
                        args={
                            "test_games": "$fetch_suspect_games.games",
                            "baseline": "$calculate_baseline"
                        },
                        depends_on=["calculate_baseline", "fetch_suspect_games"],
                        description="Detect statistical anomalies"
                    )
                ],
                "parallel_groups": [
                    ["web_context", "fetch_suspect_games"],
                    ["multi_depth", "engine_correlation"],
                ],
                "synthesis_prompt": """Analyze all findings for potential cheating:
1. Summarize news context and allegations
2. Compare tournament performance to baseline
3. Evaluate multi-depth analysis (suspicious if high deep accuracy)
4. Assess engine correlation (>85% top-3 match is unusual)
5. Review anomaly detection flags
6. Provide balanced conclusion with confidence level

Be objective and note limitations in the analysis."""
            },
            
            InvestigationType.PLAYER_RESEARCH: {
                "steps": [
                    Step(
                        id="web_search",
                        tool="web_search",
                        args={"query": "$PLAYER chess player profile"},
                        description="Search for player information"
                    ),
                    Step(
                        id="fetch_games",
                        tool="fetch_games_filtered",
                        args={
                            "username": "$USERNAME",
                            "platform": "$PLATFORM"
                        },
                        description="Get recent games"
                    ),
                    Step(
                        id="calculate_baseline",
                        tool="calculate_baseline",
                        args={"games": "$fetch_games.games"},
                        depends_on=["fetch_games"],
                        description="Calculate performance metrics"
                    )
                ],
                "parallel_groups": [["web_search", "fetch_games"]],
                "synthesis_prompt": """Create player profile:
1. Background information from web search
2. Performance statistics from games
3. Playing style observations
4. Strengths and areas for improvement"""
            }
        }
    
    def _try_template_match(
        self,
        query: str,
        inv_type: InvestigationType,
        context: Dict
    ) -> Optional[InvestigationPlan]:
        """Try to match query to a template"""
        if inv_type not in self._templates:
            return None
        
        template = self._templates[inv_type]
        
        # Extract variables from query/context
        variables = self._extract_variables(query, context)
        
        # Substitute variables in template
        steps = []
        for step_template in template["steps"]:
            args = {}
            for key, value in step_template.args.items():
                if isinstance(value, str) and value.startswith("$"):
                    # Variable reference
                    var_name = value[1:]
                    if var_name in variables:
                        args[key] = variables[var_name]
                    else:
                        args[key] = value  # Keep reference for step executor
                else:
                    args[key] = value
            
            steps.append(Step(
                id=step_template.id,
                tool=step_template.tool,
                args=args,
                depends_on=step_template.depends_on,
                description=step_template.description
            ))
        
        return InvestigationPlan(
            investigation_type=inv_type,
            steps=steps,
            synthesis_prompt=template["synthesis_prompt"],
            context=context,
            parallel_groups=template.get("parallel_groups", [])
        )
    
    def _extract_variables(self, query: str, context: Dict) -> Dict[str, Any]:
        """Extract variables from query and context"""
        variables = {}
        
        # From context
        if "player" in context:
            variables["PLAYER"] = context["player"]
        if "username" in context:
            variables["USERNAME"] = context["username"]
        if "platform" in context:
            variables["PLATFORM"] = context["platform"]
        if "event" in context:
            variables["EVENT"] = context["event"]
        if "year" in context:
            variables["YEAR"] = context["year"]
        
        # Simple extraction from query (could be enhanced with NLP)
        import re
        
        # Year patterns
        year_match = re.search(r'\b(20\d{2})\b', query)
        if year_match and "YEAR" not in variables:
            variables["YEAR"] = int(year_match.group(1))
        
        return variables
    
    async def _llm_plan(
        self,
        query: str,
        context: Dict
    ) -> InvestigationPlan:
        """Use LLM to create a plan"""
        try:
            user_prompt = f"""Create an investigation plan for:
Query: {query}

Context: {json.dumps(context, indent=2) if context else "None provided"}

Return the plan as JSON."""

            if self.llm_router:
                plan_json = self.llm_router.complete_json(
                    session_id="default",
                    stage="investigation_planner",
                    system_prompt=PLANNER_SYSTEM_PROMPT,
                    user_text=user_prompt,
                    temperature=0.3,
                    model="gpt-5",
                )
            else:
                response = self.client.chat.completions.create(
                    model="gpt-5",
                    messages=[
                        {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.3,
                    max_tokens=2000
                )
                
                content = response.choices[0].message.content.strip()
                
                # Extract JSON
                plan_json = self._extract_json(content)
            
            if plan_json:
                return self._parse_plan_json(plan_json)
            
        except Exception as e:
            print(f"LLM planning error: {e}")
        
        # Fallback
        return self._create_basic_plan(query, InvestigationType.GENERAL_INVESTIGATION, context)
    
    def _extract_json(self, text: str) -> Optional[Dict]:
        """Extract JSON from LLM response"""
        import re
        
        # Try to find JSON block
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except:
                pass
        
        # Try parsing entire response
        try:
            return json.loads(text)
        except:
            pass
        
        return None
    
    def _parse_plan_json(self, plan_json: Dict) -> InvestigationPlan:
        """Parse JSON into InvestigationPlan"""
        steps = []
        for step_data in plan_json.get("steps", []):
            steps.append(Step(
                id=step_data.get("id", f"step_{len(steps)}"),
                tool=step_data.get("tool", ""),
                args=step_data.get("args", {}),
                depends_on=step_data.get("depends_on", []),
                description=step_data.get("description", "")
            ))
        
        inv_type_str = plan_json.get("investigation_type", "general_investigation")
        try:
            inv_type = InvestigationType(inv_type_str)
        except:
            inv_type = InvestigationType.GENERAL_INVESTIGATION
        
        return InvestigationPlan(
            investigation_type=inv_type,
            steps=steps,
            synthesis_prompt=plan_json.get("synthesis_prompt", "Summarize findings."),
            parallel_groups=plan_json.get("parallel_groups", [])
        )
    
    def _create_basic_plan(
        self,
        query: str,
        inv_type: InvestigationType,
        context: Dict
    ) -> InvestigationPlan:
        """Create a basic plan without LLM"""
        steps = [
            Step(
                id="search",
                tool="web_search",
                args={"query": query, "max_results": 5},
                description="Search for relevant information"
            )
        ]
        
        return InvestigationPlan(
            investigation_type=inv_type,
            steps=steps,
            synthesis_prompt="Summarize the search findings and provide analysis.",
            context=context
        )

