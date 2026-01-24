"""
Result Synthesizer
Combines investigation results into coherent reports
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass


@dataclass
class SynthesisSection:
    """A section in the synthesis report"""
    title: str
    content: str
    confidence: str = "medium"  # low/medium/high
    sources: List[str] = None


@dataclass
class SynthesisReport:
    """Complete synthesis report"""
    title: str
    summary: str
    sections: List[SynthesisSection]
    conclusion: str
    confidence_overall: str
    recommendations: List[str] = None
    caveats: List[str] = None


class ResultSynthesizer:
    """Synthesizes investigation results into reports"""
    
    def __init__(self, openai_client=None, llm_router=None):
        self.client = openai_client
        self.llm_router = llm_router
    
    async def synthesize(
        self,
        results: Dict[str, Any],
        synthesis_prompt: str,
        format: str = "structured",
        investigation_type: str = "general"
    ) -> SynthesisReport:
        """
        Synthesize investigation results into a report.
        
        Args:
            results: Dictionary of step_id -> result data
            synthesis_prompt: Instructions for synthesis
            format: "structured", "narrative", or "brief"
            investigation_type: Type of investigation for specialized formatting
            
        Returns:
            SynthesisReport
        """
        if self.llm_router or self.client:
            return await self._llm_synthesize(results, synthesis_prompt, format, investigation_type)
        else:
            return self._basic_synthesize(results, synthesis_prompt, investigation_type)
    
    async def _llm_synthesize(
        self,
        results: Dict[str, Any],
        synthesis_prompt: str,
        format: str,
        investigation_type: str
    ) -> SynthesisReport:
        """Use LLM for sophisticated synthesis"""
        
        # Build results context
        results_text = self._format_results(results)
        
        # Get format-specific instructions
        format_instructions = self._get_format_instructions(format)
        
        # Get investigation-specific guidance
        investigation_guidance = self._get_investigation_guidance(investigation_type)
        
        system_prompt = f"""You are an expert chess analyst creating a synthesis report.

{format_instructions}

{investigation_guidance}

Output your response as a structured report with clear sections."""

        user_prompt = f"""## Investigation Results

{results_text}

---

## Synthesis Instructions

{synthesis_prompt}

Create a comprehensive synthesis report."""

        try:
            if self.llm_router:
                content = self.llm_router.complete(
                    session_id="default",
                    stage="result_synthesizer",
                    system_prompt=system_prompt,
                    user_text=user_prompt,
                    temperature=0.4,
                    model="gpt-5",
                ).strip()
            else:
                response = self.client.chat.completions.create(
                    model="gpt-5",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.4,
                )
                
                content = response.choices[0].message.content.strip()
            return self._parse_llm_report(content, investigation_type)
            
        except Exception as e:
            return SynthesisReport(
                title="Synthesis Error",
                summary=f"Error generating synthesis: {str(e)}",
                sections=[],
                conclusion="Unable to complete synthesis.",
                confidence_overall="low"
            )
    
    def _format_results(self, results: Dict[str, Any]) -> str:
        """Format results for LLM context"""
        sections = []
        
        for step_id, data in results.items():
            if isinstance(data, dict):
                # Format dict nicely
                content = self._format_dict(data)
            else:
                content = str(data)
            
            # Truncate very long content
            if len(content) > 3000:
                content = content[:3000] + "\n... (truncated)"
            
            sections.append(f"### {step_id}\n\n{content}")
        
        return "\n\n".join(sections)
    
    def _format_dict(self, d: Dict, indent: int = 0) -> str:
        """Format a dictionary for readable output"""
        lines = []
        prefix = "  " * indent
        
        for key, value in d.items():
            if isinstance(value, dict):
                lines.append(f"{prefix}**{key}:**")
                lines.append(self._format_dict(value, indent + 1))
            elif isinstance(value, list):
                lines.append(f"{prefix}**{key}:** [{len(value)} items]")
                for i, item in enumerate(value[:5]):  # Show first 5
                    if isinstance(item, dict):
                        lines.append(f"{prefix}  - {self._format_dict(item, indent + 2)}")
                    else:
                        lines.append(f"{prefix}  - {item}")
                if len(value) > 5:
                    lines.append(f"{prefix}  ... and {len(value) - 5} more")
            else:
                lines.append(f"{prefix}**{key}:** {value}")
        
        return "\n".join(lines)
    
    def _get_format_instructions(self, format: str) -> str:
        """Get instructions based on format"""
        if format == "structured":
            return """Structure your report with:
1. Executive Summary (2-3 sentences)
2. Key Findings (bullet points)
3. Detailed Analysis (sections with evidence)
4. Conclusion
5. Recommendations (if applicable)
6. Caveats and Limitations"""
        
        elif format == "narrative":
            return """Write a flowing narrative that:
1. Opens with context and key question
2. Walks through the evidence
3. Builds to a logical conclusion
4. Addresses counterarguments"""
        
        else:  # brief
            return """Be concise:
1. One paragraph summary
2. Key bullet points
3. Bottom line conclusion"""
    
    def _get_investigation_guidance(self, investigation_type: str) -> str:
        """Get guidance specific to investigation type"""
        guidance = {
            "cheating_analysis": """For cheating investigations:
- Be extremely careful with conclusions
- Present evidence objectively
- Consider alternative explanations
- Note statistical vs definitive evidence
- Avoid defamatory statements
- Include confidence levels for each claim""",
            
            "player_research": """For player research:
- Balance strengths and weaknesses
- Use specific examples from games
- Compare to rating-appropriate peers
- Focus on actionable insights""",
            
            "tournament_review": """For tournament reviews:
- Highlight key games and moments
- Note performance relative to expectations
- Identify patterns across games
- Suggest areas for improvement""",
            
            "performance_trend": """For performance analysis:
- Show clear before/after comparisons
- Use specific metrics
- Identify turning points
- Note external factors if known"""
        }
        
        return guidance.get(investigation_type, "Analyze the results thoroughly and objectively.")
    
    def _parse_llm_report(self, content: str, investigation_type: str) -> SynthesisReport:
        """Parse LLM output into structured report"""
        # Simple parsing - look for common headers
        import re
        
        lines = content.split("\n")
        
        # Extract title (first heading)
        title = "Investigation Report"
        for line in lines:
            if line.startswith("#") and not line.startswith("##"):
                title = line.lstrip("#").strip()
                break
        
        # Extract summary (first paragraph or executive summary section)
        summary = ""
        in_summary = False
        for i, line in enumerate(lines):
            if "summary" in line.lower() or "overview" in line.lower():
                in_summary = True
                continue
            if in_summary and line.strip() and not line.startswith("#"):
                summary = line.strip()
                break
        
        if not summary and len(lines) > 2:
            # Use first non-heading paragraph
            for line in lines:
                if line.strip() and not line.startswith("#"):
                    summary = line.strip()
                    break
        
        # Extract sections (## headers)
        sections = []
        current_section = None
        current_content = []
        
        for line in lines:
            if line.startswith("## "):
                if current_section:
                    sections.append(SynthesisSection(
                        title=current_section,
                        content="\n".join(current_content).strip()
                    ))
                current_section = line[3:].strip()
                current_content = []
            elif current_section:
                current_content.append(line)
        
        if current_section:
            sections.append(SynthesisSection(
                title=current_section,
                content="\n".join(current_content).strip()
            ))
        
        # Find conclusion
        conclusion = ""
        for section in sections:
            if "conclusion" in section.title.lower():
                conclusion = section.content
                break
        
        if not conclusion:
            conclusion = summary
        
        # Determine overall confidence
        confidence = self._assess_confidence(content, investigation_type)
        
        # Extract recommendations
        recommendations = []
        for section in sections:
            if "recommend" in section.title.lower():
                # Parse bullet points
                for line in section.content.split("\n"):
                    if line.strip().startswith("-") or line.strip().startswith("•"):
                        recommendations.append(line.strip()[1:].strip())
        
        # Extract caveats
        caveats = []
        for section in sections:
            if "caveat" in section.title.lower() or "limitation" in section.title.lower():
                for line in section.content.split("\n"):
                    if line.strip().startswith("-") or line.strip().startswith("•"):
                        caveats.append(line.strip()[1:].strip())
        
        return SynthesisReport(
            title=title,
            summary=summary[:500],
            sections=sections,
            conclusion=conclusion[:1000],
            confidence_overall=confidence,
            recommendations=recommendations if recommendations else None,
            caveats=caveats if caveats else None
        )
    
    def _assess_confidence(self, content: str, investigation_type: str) -> str:
        """Assess overall confidence level from content"""
        content_lower = content.lower()
        
        # Look for explicit confidence statements
        if "high confidence" in content_lower or "strong evidence" in content_lower:
            return "high"
        if "low confidence" in content_lower or "insufficient evidence" in content_lower:
            return "low"
        if "moderate confidence" in content_lower or "some evidence" in content_lower:
            return "medium"
        
        # Look for hedging language
        hedge_words = ["possibly", "might", "unclear", "uncertain", "inconclusive"]
        hedge_count = sum(1 for word in hedge_words if word in content_lower)
        
        if hedge_count >= 3:
            return "low"
        elif hedge_count >= 1:
            return "medium"
        
        return "medium"
    
    def _basic_synthesize(
        self,
        results: Dict[str, Any],
        synthesis_prompt: str,
        investigation_type: str
    ) -> SynthesisReport:
        """Basic synthesis without LLM"""
        
        # Build simple sections from results
        sections = []
        for step_id, data in results.items():
            if isinstance(data, dict):
                content = "\n".join(f"- **{k}**: {v}" for k, v in list(data.items())[:10])
            else:
                content = str(data)[:500]
            
            sections.append(SynthesisSection(
                title=step_id.replace("_", " ").title(),
                content=content
            ))
        
        return SynthesisReport(
            title=f"{investigation_type.replace('_', ' ').title()} Report",
            summary="Analysis completed. See sections below for details.",
            sections=sections,
            conclusion="See individual sections for findings.",
            confidence_overall="medium"
        )

