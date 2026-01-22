"""
Explainer - Language Engine Only
Purpose: Turn investigation facts into fluent, human explanation.
FORBIDDEN: Reanalysis, contradictions, new ideas
"""

import sys
import re
import os
import json
from typing import Dict, Any, Optional, List
from investigator import InvestigationResult
from openai import OpenAI
from minimal_prompts import MIN_SYSTEM_PROMPT_V1, EXPLAINER_CONTRACT_V1
from command_protocol import render_command


class Explainer:
    """
    Language Engine - NOT allowed to think.
    Only converts investigation facts to prose.
    """
    
    def __init__(self, openai_client: OpenAI, llm_router=None):
        """
        Initialize Explainer with OpenAI client.
        
        Args:
            openai_client: OpenAI client instance
            llm_router: Optional LLM router for vLLM
        """
        self.client = openai_client
        self.llm_router = llm_router
        self.model = os.getenv("EXPLAINER_MODEL", "gpt-5-mini")
        self._last_prompt_audit: Optional[Dict[str, Any]] = None

    async def explain(
        self,
        investigation_facts: Any,  # Can be InvestigationResult, dict with multiple results, or None
        user_message: str,
        context_fen: Optional[str] = None,  # FEN from context for piece/square grounding
        context: Optional[Dict[str, Any]] = None,  # Full request context (baseline_intuition significance)
        session_id: Optional[str] = None,
        reduced_data: Optional[Dict[str, Any]] = None,  # Optional reduced/interpreted data from InvestigationReducer
    ) -> str:
        """
        Generate fluent explanation from investigation facts.
        NO new analysis - only language generation.
        
        Args:
            investigation_facts: Structured facts from Investigator, or dict with multiple_results for comparisons
            user_message: Original user message
            context_fen: FEN from context for piece/square grounding (optional)
            
        Returns:
            Natural language explanation
        """
        from contextlib import nullcontext
        try:
            from pipeline_timer import get_pipeline_timer
            _timer = get_pipeline_timer()
        except Exception:
            _timer = None

        # Validate inputs
        if not investigation_facts:
            raise ValueError("investigation_facts is required")

        # LOG INPUT
        print(f"\n{'='*80}")
        print(f"🔍 [EXPLAINER] INPUT:")
        print(f"   User Message: {user_message}")
        print(f"   Investigation Facts Type: {type(investigation_facts).__name__}")
        if isinstance(investigation_facts, InvestigationResult):
            print(f"      Eval Before: {investigation_facts.eval_before}")
            print(f"      Best Move: {investigation_facts.best_move}")
        print(f"{'='*80}\n")
        sys.stdout.flush()
        
        # Check if this is a comparison (multiple results)
        is_comparison = isinstance(investigation_facts, dict) and investigation_facts.get("comparison_mode", False)
        
        with (_timer.span("explainer:build_facts_card", {"comparison": bool(is_comparison)}) if _timer else nullcontext()):
            if is_comparison:
                multiple_results = investigation_facts.get("multiple_results", []) if investigation_facts else []
                facts_card = self._build_comparison_facts_card(multiple_results)
            else:
                if isinstance(investigation_facts, InvestigationResult):
                    facts_card = self._build_facts_card(investigation_facts, reduced_data=reduced_data)
                else:
                    raise ValueError("investigation_facts must be InvestigationResult or comparison dict")
        
        comparison_instruction = ""
        if is_comparison:
            comparison_instruction = """
COMPARISON MODE:
- Multiple investigation results are present.
- Keep it clear which points belong to which candidate (e.g., "Option A: Nf3 … / Option B: Bc4 …").
- Summarize the key tradeoff(s) and conclude with a clear answer to the user's question."""
        
        # Gate PGN by default: only include when user explicitly asks for a line/variation
        user_asks_for_line = False
        try:
            _m = (user_message or "").lower()
            user_asks_for_line = any(
                x in _m
                for x in [
                    "line",
                    "variation",
                    "pgn",
                    "sequence",
                    "moves",
                    "main line",
                    "show me",
                    "what's the line",
                    "what is the line",
                ]
            )
        except Exception:
            user_asks_for_line = False

        include_pgn = False
        pgn_section = ""
        if user_asks_for_line and isinstance(investigation_facts, InvestigationResult):
            pgn_to_use = investigation_facts.pgn_exploration or ""
            if pgn_to_use:
                include_pgn = True
                pgn_preview_limit = 500
                pgn_preview = pgn_to_use[:pgn_preview_limit] + ("..." if len(pgn_to_use) > pgn_preview_limit else "")
                pgn_section = f"""
PGN ANALYSIS:
{pgn_preview}
"""
        
        # Extract user goal from message
        user_goal = None
        if user_message:
            msg_lower = user_message.lower()
            if "castle" in msg_lower or "castling" in msg_lower:
                user_goal = "castling"
            elif "attack" in msg_lower or "aggressive" in msg_lower or "strike" in msg_lower:
                user_goal = "attack"
            elif "simplify" in msg_lower or "trade" in msg_lower or "exchange" in msg_lower:
                user_goal = "simplify"
            elif "defend" in msg_lower or "defense" in msg_lower or "safe" in msg_lower:
                user_goal = "defend"
            elif "develop" in msg_lower or "development" in msg_lower:
                user_goal = "develop"
        
        goal_anchoring = ""
        if user_goal:
            goal_mappings = {
                "castling": "Connect every explanation to king safety and development. Explicitly state how the mechanism relates to castling.",
                "attack": "Connect every explanation to creating threats and opening lines. Explicitly state how the mechanism relates to attacking.",
                "simplify": "Connect every explanation to trades and risk reduction. Explicitly state how the mechanism relates to simplification.",
                "defend": "Connect every explanation to safety and threat removal. Explicitly state how the mechanism relates to defense.",
                "develop": "Connect every explanation to piece activity and coordination. Explicitly state how the mechanism relates to development."
            }
            goal_anchoring = goal_mappings.get(user_goal, "")

        # Build delta guidance if material/tag changes are available
        delta_guidance = ""
        try:
            if isinstance(investigation_facts, InvestigationResult):
                material_change = getattr(investigation_facts, "material_change", None)
                evidence_tags_gained = getattr(investigation_facts, "evidence_tags_gained_net", None)
                evidence_tags_lost = getattr(investigation_facts, "evidence_tags_lost_net", None)
                
                if material_change or evidence_tags_gained or evidence_tags_lost:
                    delta_guidance = "\n\nCHANGES (use these to make explanations concrete):"
                    if material_change is not None and abs(material_change) > 0.01:
                        delta_guidance += f"\n- Material: {material_change:+.2f} pawns → Use phrases like 'loses/gains {abs(material_change):.1f} pawns' or 'material change of {material_change:+.2f} pawns'"
                    if evidence_tags_gained:
                        tag_names = []
                        for tag in evidence_tags_gained[:3]:
                            if isinstance(tag, dict):
                                tag_name = tag.get("tag_name") or tag.get("tag") or str(tag)
                            else:
                                tag_name = str(tag)
                            if tag_name.startswith("tag."):
                                tag_name = tag_name[4:].replace(".", "_")
                            tag_names.append(tag_name)
                        if tag_names:
                            delta_guidance += f"\n- Tags gained: {', '.join(tag_names)} → Reference naturally (e.g., 'gains center control', 'enables castling')"
                    if evidence_tags_lost:
                        tag_names = []
                        for tag in evidence_tags_lost[:3]:
                            if isinstance(tag, dict):
                                tag_name = tag.get("tag_name") or tag.get("tag") or str(tag)
                            else:
                                tag_name = str(tag)
                            if tag_name.startswith("tag."):
                                tag_name = tag_name[4:].replace(".", "_")
                            tag_names.append(tag_name)
                        if tag_names:
                            delta_guidance += f"\n- Tags lost: {', '.join(tag_names)} → Reference naturally (e.g., 'loses castling rights', 'weakens pawn structure')"
                    delta_guidance += "\n- Combine changes: When both material and tags change, mention both (e.g., 'gains center control but loses a pawn')"
        except Exception:
            delta_guidance = ""

        # Pattern summary (motifs) from baseline intuition
        pattern_summary = None
        try:
            baseline = (context or {}).get("baseline_intuition") if isinstance(context, dict) else None
            scan_root = baseline.get("scan_root") if isinstance(baseline, dict) else None
            motifs = scan_root.get("motifs") if isinstance(scan_root, dict) else None
            if isinstance(motifs, list) and motifs:
                import re as _re
                def _extract_san(sig: str) -> str:
                    toks = _re.findall(r"SAN:([A-Za-z0-9O+=#\\-]+)", str(sig or ""))[:6]
                    return " → ".join(toks) if toks else ""
                def _rank(m):
                    loc = m.get("location") if isinstance(m, dict) else None
                    ct = (loc or {}).get("count_total") if isinstance(loc, dict) else m.get("count_total")
                    try:
                        ct_i = int(ct or 0)
                    except Exception:
                        ct_i = 0
                    try:
                        sigv = float(m.get("significance") or 0.0)
                    except Exception:
                        sigv = 0.0
                    return (ct_i, sigv)
                ms = [m for m in motifs if isinstance(m, dict)]
                ms.sort(key=_rank, reverse=True)
                ms = ms[:6]
                lines = []
                for m in ms:
                    sig = ((m.get("pattern") or {}) if isinstance(m.get("pattern"), dict) else {}).get("signature") or m.get("signature") or ""
                    phrase = _extract_san(sig) or "(pattern)"
                    loc = m.get("location") if isinstance(m, dict) else None
                    ct = (loc or {}).get("count_total") if isinstance(loc, dict) else m.get("count_total")
                    cls = m.get("classification") or m.get("class")
                    try:
                        ct_i = int(ct or 0)
                    except Exception:
                        ct_i = 0
                    lines.append(f"- {phrase} (seen {ct_i}×){f' [{cls}]' if cls else ''}")
                if lines:
                    pattern_summary = "Patterns (recurring motifs across branches):\n" + "\n".join(lines)
        except Exception:
            pattern_summary = None

        rules_contract = """GUIDELINES (minimal):
- Be free in tone and structure.
- Any concrete chess claim must be backed by the provided evidence SAN sequence / PV / facts. If not, say it's unclear.
- Do NOT output internal identifiers (no `tag.*`, `role.*`, no debug labels like 'Line:', 'Eval Δ', etc.)."""

        # Add reduced data insights if available
        reduced_insights = ""
        if reduced_data and isinstance(reduced_data, dict):
            narrative_summary = reduced_data.get("narrative_summary")
            if narrative_summary:
                reduced_insights = f"\nINVESTIGATION SUMMARY:\n{narrative_summary}\n"
        
        prompt = f"""You are a chess coach explaining investigation results.

USER QUESTION: {user_message}
{f"USER GOAL (heuristic): {user_goal}" if user_goal else ""}

PATTERN SUMMARY (motifs; optional):
These are recurring ideas found across branches. Use them if they help answer the user's question.
Do NOT output raw identifiers like tag.* or role.*. Prefer describing the move sequence in words.
{pattern_summary if isinstance(pattern_summary, str) and pattern_summary.strip() else "None"}
{reduced_insights}
FACTS CARD (compact, high-signal):
{facts_card}
{pgn_section}
{comparison_instruction}

TASK:
Answer the user's question directly and naturally. If a user goal is present, connect to it once.

{rules_contract}
{delta_guidance}
GOAL ANCHOR (optional): {goal_anchoring if goal_anchoring else "Connect to the user's goal once if it helps."}
"""

        # In relaxed mode, reduce further constraints
        relaxed = os.getenv("STRICT_LLM_MODE", "").lower().strip() != "true"
        if relaxed:
            prompt = prompt.replace("MUST", "should").replace("must", "should")

        # Prompt size audit
        def _approx_tokens(s: str) -> int:
            return int(len(s) / 4) if isinstance(s, str) else 0

        section_sizes = {
            "rules_contract_chars": len(rules_contract or ""),
            "facts_card_chars": len(facts_card or ""),
            "pgn_section_chars": len(pgn_section or ""),
            "total_prompt_chars": len(prompt),
        }
        print("   📏 [EXPLAINER_PROMPT_AUDIT] section_sizes:", section_sizes)
        print("   📏 [EXPLAINER_PROMPT_AUDIT] approx_total_tokens:", _approx_tokens(prompt))

        try:
            self._last_prompt_audit = {
                "section_sizes": section_sizes,
                "approx_total_tokens": _approx_tokens(prompt),
                "include_pgn": bool(include_pgn),
            }
        except Exception:
            self._last_prompt_audit = None
        
        try:
            # Generate explanation
            model_params = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
            }
            if "gpt-5" not in self.model.lower():
                model_params["temperature"] = 0.7
            
            import time as _time
            from pipeline_timer import get_pipeline_timer
            _pipeline_timer = get_pipeline_timer()
            _t0 = _time.perf_counter()
            response = None
            if self.llm_router:
                cmd = render_command(
                    command="WRITE_EXPLANATION",
                    input={"prompt": prompt},
                    constraints={"json_only": False},
                )
                explanation_text = self.llm_router.complete(
                    session_id=session_id or "default",
                    stage="explainer",
                    system_prompt=MIN_SYSTEM_PROMPT_V1,
                    task_seed=EXPLAINER_CONTRACT_V1,
                    user_text=cmd,
                    temperature=(0.7 if "gpt-5" not in self.model.lower() else None),
                    model=self.model,
                    max_tokens=int(os.getenv("EXPLAINER_MAX_TOKENS", "1600")),
                )
            else:
                response = self.client.chat.completions.create(**model_params)
            _dt = _time.perf_counter() - _t0
            try:
                usage = getattr(response, "usage", None) if response is not None else None
                prompt_tokens = getattr(usage, "prompt_tokens", None) if usage is not None else None
                completion_tokens = getattr(usage, "completion_tokens", None) if usage is not None else None
            except Exception:
                prompt_tokens = None
                completion_tokens = None
            if _pipeline_timer:
                _pipeline_timer.record_llm("explainer", _dt, tokens_in=prompt_tokens, tokens_out=completion_tokens, model=self.model)
            
            # Extract content
            raw_content = None
            finish_reason = None
            if response is not None:
                choice = response.choices[0]
                raw_content = choice.message.content
                finish_reason = getattr(choice, "finish_reason", None)
            else:
                raw_content = explanation_text
            
            if raw_content is None:
                raise ValueError(f"Response content is None! Finish reason: {finish_reason}")
            
            explanation = raw_content.strip()
            
            if not explanation:
                raise ValueError("Generated explanation is empty")
            
            # LOG OUTPUT
            print(f"\n{'='*80}")
            print(f"✅ [EXPLAINER] OUTPUT:")
            print(f"   Explanation Length: {len(explanation)} chars")
            print(f"   Preview (first 200 chars): {explanation[:200]}...")
            print(f"{'='*80}\n")
            sys.stdout.flush()
            
            return explanation
            
        except Exception as e:
            import traceback
            print(f"\n{'='*80}")
            print(f"❌ [EXPLAINER] ERROR:")
            print(f"   Error: {e}")
            print(f"   Traceback:")
            traceback.print_exc()
            print(f"{'='*80}\n")
            raise

    async def explain_simple(
        self,
        user_message: str,
        context: Dict[str, Any],
        session_id: Optional[str] = None,
    ) -> str:
        """
        Simple explanation for non-investigation requests (general chat).
        
        Args:
            user_message: User's message
            context: Context data
            
        Returns:
            Natural language explanation
        """
        # This method remains unchanged for general chat
        # Implementation would go here if needed
        raise NotImplementedError("explain_simple not implemented")

    def _build_facts_card(self, facts: InvestigationResult, reduced_data: Optional[Dict[str, Any]] = None) -> str:
        """
        Build a compact, high-signal facts card for the Explainer prompt.
        
        Args:
            facts: InvestigationResult
            reduced_data: Optional reduced/interpreted data from InvestigationReducer
        """
        # If reduced data is available, use the structured facts from reducer
        if reduced_data and isinstance(reduced_data, dict):
            structured_facts = reduced_data.get("structured_facts")
            if structured_facts:
                return structured_facts
        
        # Fallback to original minimal format
        parts: List[str] = []

        if facts.eval_before is not None:
            parts.append(f"Eval before: {facts.eval_before:+.2f} pawns")
        if facts.best_move_d16:
            parts.append(f"Best move (D16): {facts.best_move_d16}")
        if facts.eval_d16 is not None:
            parts.append(f"D16 eval: {facts.eval_d16:+.2f} pawns")
        if facts.eval_d2 is not None:
            parts.append(f"D2 eval: {facts.eval_d2:+.2f} pawns")
        if facts.is_critical:
            parts.append("Critical decision")
        if facts.is_winning:
            parts.append("Winning position")
        if facts.themes_identified:
            parts.append(f"Themes: {', '.join(facts.themes_identified[:5])}")

        return "\n".join(parts) if parts else "No facts available."

    def _build_comparison_facts_card(self, multiple_results: List[Dict[str, Any]]) -> str:
        """
        Build facts card for comparison mode.
        """
        parts = []
        for i, item in enumerate(multiple_results[:3]):
            result = item.get("result")
            if isinstance(result, InvestigationResult):
                move = result.best_move_d16 or "unknown"
                eval_val = result.eval_d16 if result.eval_d16 is not None else "unknown"
                parts.append(f"Option {i+1} ({move}): eval {eval_val}")
        return "\n".join(parts) if parts else "No comparison data available."
