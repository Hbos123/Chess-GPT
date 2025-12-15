"""
Training Planner - Converts training queries to structured training blueprints
"""

from typing import Dict, List, Any, Optional
from openai import OpenAI
import json


class TrainingPlanner:
    """Generates training blueprints from natural language queries"""
    
    def __init__(self, openai_client: OpenAI):
        self.client = openai_client
    
    def plan_training(
        self,
        query: str,
        analyzed_games: Optional[List[Dict]] = None,
        user_stats: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Convert training query to structured blueprint
        
        Args:
            query: User's training goal/question
            analyzed_games: Optional analyzed games for context
            user_stats: Optional user statistics
            
        Returns:
            Training blueprint dictionary
        """
        context = self._build_context(analyzed_games, user_stats)
        
        system_prompt = """You are a chess training planner. Convert training requests into structured blueprints.

Create JSON with:

1. "focus_tags": Priority tags to train (e.g., ["tactic.fork", "tactic.pin", "endgame.pawn"])
2. "context_filters": 
   - phases: ["opening", "middlegame", "endgame"]
   - sides: ["white", "black"] or both
   - openings: ECO codes or names (if specific)
3. "source_mix": {"own_games": 0.7, "opening_explorer": 0.2, "bank": 0.1}
4. "difficulty": {"start_rating": 1200, "target_rating": 1400}
5. "session_config": {"length": 20, "time_box_minutes": 15, "mode": "quick|focused|opening|endgame"}
6. "drill_types": ["tactics", "defense", "critical_choice", "conversion"]
7. "lesson_goals": ["Explain fork patterns", "Practice pin recognition"]

Examples:

Q: "I keep missing forks"
A: {
  "focus_tags": ["tactic.fork"],
  "context_filters": {"phases": ["middlegame", "endgame"], "sides": ["white", "black"]},
  "source_mix": {"own_games": 0.8, "opening_explorer": 0.1, "bank": 0.1},
  "difficulty": {"start_rating": "user_rating", "target_rating": "user_rating+100"},
  "session_config": {"length": 15, "mode": "focused"},
  "drill_types": ["tactics", "defense"],
  "lesson_goals": ["Recognize fork patterns", "Calculate fork sequences"]
}

Q: "Practice my Sicilian"
A: {
  "focus_tags": ["opening"],
  "context_filters": {"phases": ["opening"], "openings": ["B20-B99"], "sides": ["black"]},
  "source_mix": {"own_games": 0.5, "opening_explorer": 0.5, "bank": 0},
  "session_config": {"length": 20, "mode": "opening"},
  "drill_types": ["opening"],
  "lesson_goals": ["Recall main lines", "Handle anti-Sicilian"]
}

Respond ONLY with valid JSON."""

        user_message = f"""Training request: "{query}"

Context:
{context}

Create the training blueprint:"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.3,
                max_tokens=800
            )
            
            plan_text = response.choices[0].message.content.strip()
            
            # Parse JSON
            if "```json" in plan_text:
                plan_text = plan_text.split("```json")[1].split("```")[0].strip()
            elif "```" in plan_text:
                plan_text = plan_text.split("```")[1].split("```")[0].strip()
            
            blueprint = json.loads(plan_text)
            
            # Validate and set defaults
            blueprint = self._validate_blueprint(blueprint)
            
            # Generate human-readable search criteria
            blueprint["search_criteria"] = self._generate_search_criteria(blueprint, query)
            
            print(f"\n📋 TRAINING SEARCH CRITERIA:")
            print(f"   User asked: '{query}'")
            print(f"   Looking for:")
            for criteria in blueprint["search_criteria"]:
                print(f"     • {criteria}")
            print()
            
            return blueprint
        
        except Exception as e:
            print(f"Error planning training: {e}")
            # Return default blueprint
            return {
                "focus_tags": ["tactic"],
                "context_filters": {"phases": ["middlegame"], "sides": ["white", "black"]},
                "source_mix": {"own_games": 0.7, "opening_explorer": 0.2, "bank": 0.1},
                "session_config": {"length": 15, "mode": "quick"},
                "drill_types": ["tactics"],
                "lesson_goals": ["General tactical improvement"],
                "error": f"Planning failed, using default: {str(e)}"
            }
    
    def _build_context(
        self,
        analyzed_games: Optional[List[Dict]],
        user_stats: Optional[Dict]
    ) -> str:
        """Build context for training planner"""
        parts = []
        
        if user_stats:
            parts.append(f"User rating: {user_stats.get('rating', 'unknown')}")
            parts.append(f"Blunder rate: {user_stats.get('blunder_rate', 0):.1f}%")
            parts.append(f"Weak phases: {user_stats.get('weak_phases', [])}")
        
        if analyzed_games:
            parts.append(f"Analyzed games: {len(analyzed_games)}")
            
            # Game metadata summary
            from collections import Counter
            openings = []
            game_chars = []
            endgame_types = []
            results = {"win": 0, "loss": 0, "draw": 0}
            
            for game in analyzed_games:
                game_meta = game.get("game_metadata", {})
                openings.append(game_meta.get("opening", "Unknown"))
                game_chars.append(game_meta.get("game_character", "unknown"))
                if game_meta.get("endgame_type"):
                    endgame_types.append(game_meta.get("endgame_type"))
                
                result = game.get("metadata", {}).get("result", "unknown")
                if result in results:
                    results[result] += 1
            
            parts.append(f"Results: {results['win']}W-{results['loss']}L-{results['draw']}D")
            opening_freq = Counter(openings).most_common(3)
            parts.append(f"Top openings: {', '.join(f'{o[0][:25]}' for o in opening_freq)}")
            char_freq = Counter(game_chars).most_common(3)
            parts.append(f"Game types: {', '.join(f'{c[0]}' for c in char_freq)}")
            if endgame_types:
                parts.append(f"Endgame types: {', '.join(set(endgame_types))}")
            
            # Common mistake tags with phase breakdown
            tag_freq = {}
            error_count_by_phase = {"opening": 0, "middlegame": 0, "endgame": 0}
            critical_count = 0
            
            for game in analyzed_games:
                for record in game.get("ply_records", []):
                    category = record.get("category", "")
                    phase = record.get("phase", "middlegame")
                    
                    if record.get("is_critical"):
                        critical_count += 1
                    
                    if category in ["inaccuracy", "mistake", "blunder"]:
                        error_count_by_phase[phase] += 1
                        
                        for tag in record.get("analyse", {}).get("tags", []):
                            if isinstance(tag, dict):
                                tag_name = tag.get("name", "")
                            else:
                                tag_name = str(tag)
                            if tag_name:
                                tag_freq[tag_name] = tag_freq.get(tag_name, 0) + 1
            
            if tag_freq:
                top_mistakes = sorted(tag_freq.items(), key=lambda x: x[1], reverse=True)[:8]
                parts.append(f"Common mistake tags: {', '.join(t[0] for t in top_mistakes)}")
            
            parts.append(f"Errors by phase: opening={error_count_by_phase['opening']}, mid={error_count_by_phase['middlegame']}, end={error_count_by_phase['endgame']}")
            parts.append(f"Critical positions identified: {critical_count}")
        
        return "\n".join(parts) if parts else "No context available"
    
    def _validate_blueprint(self, blueprint: Dict) -> Dict:
        """Validate and set defaults"""
        if "focus_tags" not in blueprint or not blueprint["focus_tags"]:
            blueprint["focus_tags"] = ["tactic"]
        
        if "context_filters" not in blueprint:
            blueprint["context_filters"] = {}
        
        if "source_mix" not in blueprint:
            blueprint["source_mix"] = {"own_games": 0.7, "opening_explorer": 0.2, "bank": 0.1}
        
        if "session_config" not in blueprint:
            blueprint["session_config"] = {"length": 15, "mode": "quick"}
        
        if "drill_types" not in blueprint:
            blueprint["drill_types"] = ["tactics"]
        
        return blueprint
    
    def _generate_search_criteria(self, blueprint: Dict, query: str) -> List[str]:
        """Generate human-readable search criteria"""
        criteria = []
        
        # Focus tags
        focus_tags = blueprint.get("focus_tags", [])
        if focus_tags:
            tag_desc = ", ".join(focus_tags)
            criteria.append(f"Positions with tags: {tag_desc}")
        
        # Phases
        phases = blueprint.get("context_filters", {}).get("phases", [])
        if phases:
            criteria.append(f"From game phases: {', '.join(phases)}")
        
        # Sides
        sides = blueprint.get("context_filters", {}).get("sides", [])
        if sides and len(sides) == 1:
            criteria.append(f"Playing as {sides[0]}")
        
        # Openings
        openings = blueprint.get("context_filters", {}).get("openings", [])
        if openings:
            criteria.append(f"From openings: {', '.join(str(o) for o in openings)}")
        
        # Drill types
        drill_types = blueprint.get("drill_types", [])
        if drill_types:
            criteria.append(f"Drill types: {', '.join(drill_types)}")
        
        # Mistakes vs critical choices
        if "tactics" in drill_types or "defense" in drill_types:
            criteria.append("Mistakes and tactical opportunities")
        if "critical_choice" in drill_types:
            criteria.append("Critical decision points (even if played correctly)")
        
        # Session length
        length = blueprint.get("session_config", {}).get("length", 15)
        criteria.append(f"Target: {length} drills")
        
        if not criteria:
            criteria.append("General tactical improvement from all games")
        
        return criteria

