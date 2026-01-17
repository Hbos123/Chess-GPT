"""
LLM Reporter for Personal Review
Generates narrative reports from aggregated data
"""

from typing import Dict, Any, Union
from openai import OpenAI
import json
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models.personal_review import AggregatedStats, AnalysisPlan


class LLMReporter:
    """Generates natural language reports from analysis data"""
    
    def __init__(self, openai_client: OpenAI, llm_router=None):
        self.client = openai_client
        self.llm_router = llm_router
        self.model = os.getenv("PERSONAL_REVIEW_REPORTER_MODEL", "gpt-5")
    
    def generate_report(
        self, 
        query: str, 
        plan: Union[Dict[str, Any], AnalysisPlan], 
        data: Union[Dict[str, Any], AggregatedStats]
    ) -> str:
        """
        Generate natural language report from aggregated data
        
        Args:
            query: Original user question
            plan: Analysis plan that was executed
            data: Aggregated analysis data
            
        Returns:
            Formatted narrative report
        """
        # Build data summary for LLM
        data_summary = self._build_data_summary(data)
        
        system_prompt = """You are a professional chess coach providing personalized feedback. 

You receive:
1. A player's question
2. Statistical analysis of their games
3. Aggregated performance metrics

Generate a comprehensive, encouraging, and actionable report in this structure:

## Overview
- Direct answer to their question (2-3 sentences)
- Key finding that stands out most

## Quantitative Insights
- Present the most relevant numbers from the data
- Use tables or bullet points for clarity
- Compare to typical player performance when helpful

## Qualitative Analysis
- Interpret what the numbers mean
- Identify patterns and trends
- Point out strengths and weaknesses

## Specific Examples
- Reference specific situations from the data
- Connect patterns to concrete scenarios

## Action Plan
- 3-5 specific, actionable recommendations
- Prioritize by impact
- Make them concrete and measurable

Tone: Professional but warm, encouraging but honest, specific not generic.
Use chess terminology appropriately for the player's level.
Avoid vague advice like "study more" - be specific about what and how."""

        user_message = f"""Player's question: "{query}"

Analysis data:
{data_summary}

Generate the personalized report:"""

        try:
            response = None
            if self.llm_router:
                return self.llm_router.complete(
                    session_id="default",
                    stage="personal_review_reporter",
                    system_prompt=system_prompt,
                    user_text=user_message,
                    temperature=0.7,
                    model=self.model,
                )

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.7,
                max_tokens=2000
            )
            
            report = response.choices[0].message.content.strip()
            return report
        
        except Exception as e:
            print(f"Error generating report: {e}")
            # Return fallback report
            return self._generate_fallback_report(data)
    
    def _build_data_summary(self, data: Dict) -> str:
        """Build concise summary of data for LLM"""
        summary_parts = []
        
        # Summary stats
        if "summary" in data:
            summary = data["summary"]
            summary_parts.append(f"""Overall Performance:
- Total games: {summary.get('total_games', 0)}
- Win rate: {summary.get('win_rate', 0):.1f}%
- Overall accuracy: {summary.get('overall_accuracy', 0):.1f}%
- Avg CP loss: {summary.get('avg_cp_loss', 0):.0f}
- Blunders per game: {summary.get('blunders_per_game', 0):.1f}
- Mistakes per game: {summary.get('mistakes_per_game', 0):.1f}""")
        
        # Phase stats
        if "phase_stats" in data:
            phase_lines = ["Performance by Phase:"]
            for phase, stats in data["phase_stats"].items():
                phase_lines.append(f"- {phase.capitalize()}: {stats.get('accuracy', 0):.1f}% accuracy, {stats.get('avg_cp_loss', 0):.0f} avg CP loss")
            summary_parts.append("\n".join(phase_lines))
        
        # Opening performance
        if "opening_performance" in data:
            openings = data["opening_performance"][:5]  # Top 5
            if openings:
                opening_lines = ["Top Openings:"]
                for opening in openings:
                    opening_lines.append(
                        f"- {opening['name']}: {opening['win_rate']:.1f}% win rate, "
                        f"{opening['avg_accuracy']:.1f}% accuracy ({opening['count']} games)"
                    )
                summary_parts.append("\n".join(opening_lines))
        
        # Theme frequency
        if "theme_frequency" in data:
            themes = data["theme_frequency"][:10]  # Top 10
            if themes:
                theme_lines = ["Most Common Themes:"]
                for theme in themes:
                    theme_lines.append(f"- {theme['name']}: {theme['frequency']} occurrences")
                summary_parts.append("\n".join(theme_lines))
        
        # Time management
        if "time_management" in data:
            tm = data["time_management"]
            summary_parts.append(f"""Time Management:
- Avg time per move: {tm.get('avg_time_per_move', 0):.1f}s
- Fast moves (<5s) accuracy: {tm.get('fast_move_accuracy', 0):.1f}%
- Slow moves (>30s) accuracy: {tm.get('slow_move_accuracy', 0):.1f}%""")
        
        # Advanced metrics
        if "advanced_metrics" in data:
            am = data["advanced_metrics"]
            summary_parts.append(f"""Advanced Metrics:
- Tactical Complexity Index: {am.get('tactical_complexity_index', 0):.2f}
- Conversion Rate: {am.get('conversion_rate', 0):.1f}%""")
        
        return "\n\n".join(summary_parts)
    
    def _generate_fallback_report(self, data: Dict) -> str:
        """Generate basic report if LLM fails"""
        summary = data.get("summary", {})
        
        report = f"""# Chess Performance Report

## Overview
Based on analysis of {summary.get('total_games', 0)} games:
- Win Rate: {summary.get('win_rate', 0):.1f}%
- Overall Accuracy: {summary.get('overall_accuracy', 0):.1f}%
- Average CP Loss: {summary.get('avg_cp_loss', 0):.0f}

## Key Statistics
- Blunders per game: {summary.get('blunders_per_game', 0):.1f}
- Mistakes per game: {summary.get('mistakes_per_game', 0):.1f}

## Next Steps
1. Review your most common mistakes
2. Practice tactical puzzles
3. Analyze your opening repertoire
4. Work on time management
"""
        
        return report

