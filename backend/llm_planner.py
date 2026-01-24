"""
LLM Planner for Personal Review
Converts natural language queries into structured analysis plans
"""

from typing import List, Dict, Any
from openai import OpenAI
import os
import json
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models.personal_review import AnalysisPlan, FilterSpec


class LLMPlanner:
    """Converts natural queries to structured analysis plans using LLM"""
    
    def __init__(self, openai_client: OpenAI, llm_router=None):
        self.client = openai_client
        self.llm_router = llm_router
        # This is the "planner" for personal review queries (not the 4-layer executor Planner).
        # Default to a cheaper model; can be overridden via PERSONAL_REVIEW_PLANNER_MODEL.
        self.model = os.getenv("PERSONAL_REVIEW_PLANNER_MODEL", "gpt-5-mini")
    
    def plan_analysis(self, query: str, games: List[Dict]) -> Dict[str, Any]:
        """
        Convert natural language query into structured analysis plan
        
        Args:
            query: User's natural language question
            games: List of available games with metadata
            
        Returns:
            Structured plan dictionary
        """
        # Build context about available games
        game_context = self._build_game_context(games)
        
        # System prompt for planning
        system_prompt = """You are a chess analysis planner. Your job is to convert natural language questions about chess performance into structured analysis plans.

Given a player's question and their available games, create a JSON plan with:

1. "intent" - The type of analysis:
   - "diagnostic": Why am I stuck / what are my weaknesses
   - "comparison": How have I improved / changed over time
   - "trend": Pattern analysis over time periods
   - "focus": Specific area analysis (opening, endgame, etc.)

2. "filters" - What games to analyze:
   - rating_min/max: Rating range
   - result: "win", "loss", "draw"
   - player_color: "white", "black"
   - time_category: "bullet", "blitz", "rapid", "classical"
   - opening_eco: ECO code prefix

3. "cohorts" (optional) - For comparisons:
   - label: Description
   - filters: Same structure as above

4. "metrics" - What to calculate:
   - "overall_stats": Win rate, accuracy, blunders
   - "phase_breakdown": Opening/middlegame/endgame analysis
   - "opening_performance": Performance by opening
   - "theme_analysis": Common tactical/positional themes
   - "time_management": Time usage patterns
   - "mistake_patterns": When and where mistakes happen

5. "games_to_analyze" - How many games (default: all matching)

6. "exemplars" (optional):
   - count: Number of example games
   - selection: "best_games", "worst_games", "critical_saves", "missed_wins"

Examples:

Q: "Why am I stuck at 800?"
A: {
  "intent": "diagnostic",
  "filters": {"rating_min": 750, "rating_max": 850},
  "metrics": ["overall_stats", "phase_breakdown", "mistake_patterns", "opening_performance"],
  "exemplars": {"count": 3, "selection": "worst_games"}
}

Q: "How has my middlegame improved?"
A: {
  "intent": "comparison",
  "cohorts": [
    {"label": "3 months ago", "filters": {"date_range": "older"}},
    {"label": "Recent", "filters": {"date_range": "recent"}}
  ],
  "metrics": ["phase_breakdown", "theme_analysis"],
  "focus_phase": "middlegame"
}

Q: "Which openings should I avoid?"
A: {
  "intent": "focus",
  "filters": {},
  "metrics": ["opening_performance"],
  "exemplars": {"count": 2, "selection": "worst_games"}
}

Respond ONLY with valid JSON. No explanations."""

        user_message = f"""Player's question: "{query}"

Available games context:
{game_context}

Create the analysis plan:"""

        try:
            import time as _time
            from pipeline_timer import get_pipeline_timer
            _timer = get_pipeline_timer()
            _t0 = _time.perf_counter()
            response = None
            if self.llm_router:
                plan = self.llm_router.complete_json(
                    session_id="default",
                    stage="personal_review_planner",
                    system_prompt=system_prompt,
                    user_text=user_message,
                    temperature=0.3,
                    model=self.model,
                )
                plan_text = json.dumps(plan, ensure_ascii=False)
            else:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message}
                    ],
                    temperature=0.3,
                )
            _dt = _time.perf_counter() - _t0
            try:
                usage = getattr(response, "usage", None) if response is not None else None
                prompt_tokens = getattr(usage, "prompt_tokens", None)
                completion_tokens = getattr(usage, "completion_tokens", None)
            except Exception:
                prompt_tokens = None
                completion_tokens = None
            if _timer:
                _timer.record_llm(
                    "personal_review_planner",
                    _dt,
                    tokens_in=prompt_tokens,
                    tokens_out=completion_tokens,
                    model=self.model
                )
            if response is not None:
                plan_text = response.choices[0].message.content.strip()
            
            # Parse JSON
            # Remove markdown code blocks if present
            if "```json" in plan_text:
                plan_text = plan_text.split("```json")[1].split("```")[0].strip()
            elif "```" in plan_text:
                plan_text = plan_text.split("```")[1].split("```")[0].strip()
            if response is not None:
                plan_dict = json.loads(plan_text)
            else:
                plan_dict = plan_text if isinstance(plan_text, dict) else json.loads(plan_text)
            
            # Validate using Pydantic model
            try:
                plan = AnalysisPlan(**plan_dict)
                # Override games_to_analyze if needed
                if plan.games_to_analyze > len(games):
                    plan.games_to_analyze = min(len(games), 50)
            except Exception as e:
                print(f"⚠️ Plan validation failed, using defaults: {e}")
                # Fall back to manual validation
                plan = self._validate_plan(plan_dict, len(games))
                # Convert to dict for return
                if isinstance(plan, AnalysisPlan):
                    plan = plan.dict()
            
            # Return as dict for compatibility
            if isinstance(plan, AnalysisPlan):
                return plan.dict()
            return plan
        
        except Exception as e:
            print(f"Error planning analysis: {e}")
            # Return default diagnostic plan
            return {
                "intent": "diagnostic",
                "filters": {},
                "metrics": ["overall_stats", "phase_breakdown", "opening_performance"],
                "games_to_analyze": min(len(games), 50),
                "error": f"Plan generation failed, using default plan: {str(e)}"
            }
    
    def _build_game_context(self, games: List[Dict]) -> str:
        """Build summary context of available games"""
        if not games:
            return "No games available"
        
        # Count games by rating range
        rating_ranges = {}
        for game in games:
            rating = game.get("player_rating", 0)
            if rating > 0:
                band = (rating // 100) * 100
                rating_ranges[band] = rating_ranges.get(band, 0) + 1
        
        # Count by result
        results = {"win": 0, "loss": 0, "draw": 0}
        for game in games:
            result = game.get("result", "unknown")
            if result in results:
                results[result] += 1
        
        # Count by time control
        time_controls = {}
        for game in games:
            tc = game.get("time_category", "unknown")
            time_controls[tc] = time_controls.get(tc, 0) + 1
        
        context = f"""Total games: {len(games)}
Results: {results['win']} wins, {results['loss']} losses, {results['draw']} draws
Rating ranges: {', '.join(f'{k}-{k+99}: {v} games' for k, v in sorted(rating_ranges.items()))}
Time controls: {', '.join(f'{k}: {v}' for k, v in time_controls.items())}"""
        
        return context
    
    def _validate_plan(self, plan: Dict, total_games: int) -> Dict:
        """Validate and set defaults for plan (fallback if Pydantic validation fails)"""
        # Ensure required fields
        if "intent" not in plan or plan["intent"] not in ["diagnostic", "comparison", "trend", "focus"]:
            plan["intent"] = "diagnostic"
        
        if "filters" not in plan or not isinstance(plan["filters"], dict):
            plan["filters"] = {}
        
        if "metrics" not in plan or not isinstance(plan["metrics"], list):
            plan["metrics"] = ["overall_stats", "phase_breakdown"]
        
        # Validate metrics
        valid_metrics = [
            "overall_stats", "phase_breakdown", "opening_performance",
            "theme_analysis", "time_management", "mistake_patterns"
        ]
        plan["metrics"] = [m for m in plan["metrics"] if m in valid_metrics]
        if not plan["metrics"]:
            plan["metrics"] = ["overall_stats", "phase_breakdown"]
        
        if "games_to_analyze" not in plan or not isinstance(plan["games_to_analyze"], int):
            plan["games_to_analyze"] = min(total_games, 50)
        else:
            plan["games_to_analyze"] = max(1, min(plan["games_to_analyze"], 100, total_games))
        
        if "analysis_depth" not in plan or not isinstance(plan["analysis_depth"], int):
            plan["analysis_depth"] = 15
        else:
            plan["analysis_depth"] = max(10, min(plan["analysis_depth"], 25))
        
        return plan

