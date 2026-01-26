"""
Planner - Thinking/Planning Layer
Converts abstract intent into a simple, sequential execution plan.
Outputs a list of steps that will be worked through one by one.
"""

import json
import uuid
import re
import os
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import chess
from planner_helpers import prepare_planner_context
from orchestration_plan import IntentPlan
from planner_prompt import PLANNER_SYSTEM_PROMPT
from minimal_prompts import MIN_SYSTEM_PROMPT_V1, PLANNER_CONTRACT_V1
from command_protocol import render_command
from action_schema import validate_planner_plan


@dataclass
class ExecutionStep:
    """
    A single step in the execution plan.
    Simple, ordered list that gets worked through sequentially.
    """
    step_number: int  # Order in the plan (1, 2, 3, ...)
    action_type: str  # "ask_clarification" | "investigate_move" | "investigate_position" | "investigate_target" | "apply_line" | "select_line" | "save_state" | "investigate_game" | "synthesize" | "answer"
    parameters: Dict[str, Any] = field(default_factory=dict)
    # {
    #   "move_san": "Nf3" (if action_type == "investigate_move"),
    #   "fen": "..." (if needed),
    #   "question": "Which piece?" (if action_type == "ask_clarification"),
    #   "focus": "knight" (if action_type == "investigate_position")
    # }
    purpose: str = ""  # Why this step is needed
    tool_to_call: Optional[str] = None  # "investigator.investigate_move" | "investigator.investigate_position" | null
    expected_output: str = ""  # What we expect to learn from this step
    status: str = "pending"  # "pending" | "in_progress" | "completed" | "failed"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "step_number": self.step_number,
            "action_type": self.action_type,
            "parameters": self.parameters,
            "purpose": self.purpose,
            "tool_to_call": self.tool_to_call,
            "expected_output": self.expected_output,
            "status": self.status
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ExecutionStep':
        """Create from dictionary"""
        return cls(
            step_number=data["step_number"],
            action_type=data["action_type"],
            parameters=data.get("parameters", {}),
            purpose=data.get("purpose", ""),
            tool_to_call=data.get("tool_to_call"),
            expected_output=data.get("expected_output", ""),
            status=data.get("status", "pending")
        )


@dataclass
class ExecutionPlan:
    """
    Simple, sequential execution plan.
    A list of steps that will be worked through one by one.
    """
    plan_id: str
    original_intent: IntentPlan
    steps: List[ExecutionStep] = field(default_factory=list)
    # NEW: High-level discussion agenda (planner-produced) to guide summarisation coverage.
    discussion_agenda: List[Dict[str, Any]] = field(default_factory=list)
    # NEW: Execution metadata/flags (planner-controlled behavior switches)
    metadata: Dict[str, Any] = field(default_factory=dict)
    # Simple ordered list - work through step 1, then 2, then 3, etc.
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "plan_id": self.plan_id,
            "steps": [step.to_dict() for step in self.steps],
            "total_steps": len(self.steps),
            "discussion_agenda": self.discussion_agenda,
            "metadata": self.metadata or {},
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], original_intent: IntentPlan) -> 'ExecutionPlan':
        """Create from dictionary"""
        steps = [ExecutionStep.from_dict(step_data) for step_data in data.get("steps", [])]
        return cls(
            plan_id=data.get("plan_id", f"plan_{uuid.uuid4().hex[:8]}"),
            original_intent=original_intent,
            steps=steps,
            discussion_agenda=data.get("discussion_agenda", []) or [],
            metadata=data.get("metadata", {}) or {},
        )


class Planner:
    """
    Thinking/Planning layer.
    Converts abstract intent into a simple, sequential execution plan.
    """
    
    def __init__(self, openai_client, engine_queue=None, llm_router=None):
        self.client = openai_client
        self.engine_queue = engine_queue
        self.llm_router = llm_router
        # Default to a cheaper/faster model; can be overridden via PLANNER_MODEL.
        # "gpt-4 mini" in OpenAI model naming is typically "gpt-5-mini".
        self.model = os.getenv("PLANNER_MODEL", "gpt-5-mini")
        self.engine_move_drop_threshold_cp = 120  # cp gap allowed between best and alternative candidates
        # Speed: depth used only for *candidate selection* (not the main investigations).
        # Keep this lower to reduce latency without impacting final quality (the Investigator does deeper work).
        self.engine_probe_depth = int(os.getenv("PLANNER_ENGINE_PROBE_DEPTH", "12"))
        # Speed: cap how many candidate moves we will investigate when the user didn't explicitly request moves.
        self.max_candidate_investigations = int(os.getenv("PLANNER_MAX_CANDIDATE_INVESTIGATIONS", "4"))
        # Debug/audit: last LLM I/O
        self._audit_llm_io: Dict[str, Any] = {}
    
    async def create_execution_plan(
        self,
        intent_plan: IntentPlan,
        fen: Optional[str],
        context: Dict[str, Any],
        session_id: Optional[str] = None,
    ) -> ExecutionPlan:
        """
        Create a simple, sequential execution plan.
        
        This is the "thinking" stage - it plans how to answer the question
        by creating a list of steps that will be worked through.
        """
        # VALIDATION: Check if FEN was computed from moves
        # If investigation requests have a computed FEN, use that instead
        computed_fen = None
        for req in intent_plan.investigation_requests:
            if req.parameters.get("fen"):
                computed_fen = req.parameters.get("fen")
                break
        
        if computed_fen:
            fen = computed_fen
            print(f"   ✅ Using computed FEN from investigation request")
        
        # VALIDATION: Detect starting position mismatch
        warning = self._validate_position_relevance(fen, intent_plan)
        if warning:
            print(f"   ⚠️ POSITION WARNING: {warning}")
        
        # Prepare context with legal moves and tags
        planner_context = None
        if fen:
            try:
                # Timing: context building can be expensive if tags are computed.
                from pipeline_timer import get_pipeline_timer
                _timer = get_pipeline_timer()
                _ctx_entry = _timer.start("planner:context", {"has_fen": True}) if _timer else None
                planner_context = prepare_planner_context(fen, intent_plan, context)
                if _timer and _ctx_entry:
                    _timer.finish(_ctx_entry, {"context_keys": list(planner_context.keys()) if isinstance(planner_context, dict) else None})
            except Exception as e:
                print(f"   ⚠️ Error preparing planner context: {e}")
                planner_context = None
        
        # LOG INPUT
        print(f"\n{'='*80}")
        print(f"🔍 [PLANNER] INPUT:")
        print(f"   Intent: {intent_plan.intent}")
        print(f"   Investigation Required: {intent_plan.investigation_required}")
        print(f"   Investigation Requests: {len(intent_plan.investigation_requests)}")
        for i, req in enumerate(intent_plan.investigation_requests):
            print(f"      [{i+1}] {req.investigation_type} (focus: {req.focus})")
            if req.parameters.get("moves_applied"):
                print(f"         Moves Applied: {req.parameters.get('moves_applied')}")
        print(f"   FEN: {fen[:50] if fen else 'None'}...")
        if warning:
            print(f"   ⚠️ Warning: {warning}")
        print(f"{'='*80}\n")
        
        # Build prompt for thinking/planning (command protocol)
        base_prompt = self._build_planning_prompt(intent_plan, planner_context, context, fen)
        prompt = render_command(
            command="PLAN_STEPS",
            input={
                "intent_plan": intent_plan.to_dict() if hasattr(intent_plan, "to_dict") else {},
                "fen": fen,
                "mode": (context or {}).get("mode"),
                "planner_context": planner_context,
                "prompt": base_prompt,
            },
            constraints={
                "json_only": True,
                "max_steps": 12,
            },
        )
        try:
            self._audit_llm_io = {
                "model": self.model,
                "temperature": 0.2,
                "messages": [
                    {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
            }
        except Exception:
            self._audit_llm_io = {}
        
        # Call LLM to create execution plan
        try:
            # gpt-5 only supports the default temperature; omit it to avoid 400s.
            create_kwargs = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                "response_format": {"type": "json_object"},
            }
            if not str(self.model).startswith("gpt-5"):
                create_kwargs["temperature"] = 0.2
            import time as _time
            from pipeline_timer import get_pipeline_timer
            _timer = get_pipeline_timer()
            _llm_entry = _timer.start("planner:llm", {"model": self.model}) if _timer else None
            _t0 = _time.perf_counter()
            response = None
            if self.llm_router:
                # Session-aware router (vLLM-first). Per-stage subsession keys are derived inside the router.
                result = self.llm_router.complete_json(
                    session_id=session_id or "default",
                    stage="planner",
                    system_prompt=MIN_SYSTEM_PROMPT_V1,
                    task_seed=PLANNER_CONTRACT_V1,
                    user_text=prompt,
                    temperature=(0.2 if not str(self.model).startswith("gpt-5") else None),
                    model=self.model,
                )
                ok, errs = validate_planner_plan(result)
                if not ok:
                    # Single repair retry.
                    try:
                        repair_prompt = render_command(
                            command="REPAIR_PLAN_JSON",
                            input={"errors": errs, "bad_json": result},
                            constraints={"json_only": True, "max_steps": 12},
                        )
                        result = self.llm_router.complete_json(
                            session_id=session_id or "default",
                            stage="planner",
                            system_prompt=MIN_SYSTEM_PROMPT_V1,
                            task_seed=PLANNER_CONTRACT_V1,
                            user_text=repair_prompt,
                            temperature=(0.0 if not str(self.model).startswith("gpt-5") else None),
                            model=self.model,
                            max_tokens=int(os.getenv("PLANNER_MAX_TOKENS", "900")),
                        )
                    except Exception:
                        pass
            else:
                response = self.client.chat.completions.create(**create_kwargs)
            _dt = _time.perf_counter() - _t0
            # Record LLM stats (for pipeline_timer.print_summary()).
            try:
                usage = getattr(response, "usage", None) if response is not None else None
                prompt_tokens = getattr(usage, "prompt_tokens", None) if usage is not None else None
                completion_tokens = getattr(usage, "completion_tokens", None) if usage is not None else None
            except Exception:
                prompt_tokens = None
                completion_tokens = None
            if _timer:
                _timer.record_llm("planner", _dt, tokens_in=prompt_tokens, tokens_out=completion_tokens, model=self.model)
                if _llm_entry:
                    _timer.finish(_llm_entry, {"duration_s": round(_dt, 4), "tokens_in": prompt_tokens, "tokens_out": completion_tokens})
            try:
                if response is not None:
                    self._audit_llm_io["raw_response_text"] = response.choices[0].message.content
                else:
                    self._audit_llm_io["raw_response_text"] = json.dumps(result)
            except Exception:
                pass
            if response is not None:
                result = json.loads(response.choices[0].message.content)
            try:
                self._audit_llm_io["parsed_json"] = result
            except Exception:
                pass
            
            # Convert LLM output to ExecutionPlan
            steps = []
            for step_data in result.get("steps", []):
                steps.append(ExecutionStep(
                    step_number=step_data["step_number"],
                    action_type=step_data["action_type"],
                    parameters=step_data.get("parameters", {}),
                    purpose=step_data.get("purpose", ""),
                    tool_to_call=step_data.get("tool_to_call"),
                    expected_output=step_data.get("expected_output", "")
                ))
            
            plan_id = result.get("plan_id", f"plan_{uuid.uuid4().hex[:8]}")
            
            execution_plan = ExecutionPlan(
                plan_id=plan_id,
                original_intent=intent_plan,
                steps=steps,
                discussion_agenda=result.get("discussion_agenda", []) or [],
            )
            # Planner is the primary source of candidate-move selection; avoid executor adding extra candidates.
            try:
                execution_plan.metadata["disable_executor_candidate_injection"] = True
            except Exception:
                execution_plan.metadata = {"disable_executor_candidate_injection": True}
            
            # Enforce move-selection policy so we only investigate relevant moves
            execution_plan = await self._auto_add_candidate_moves(
                execution_plan=execution_plan,
                planner_context=planner_context,
                fen=fen,
                intent_plan=intent_plan,
                context=context
            )

            # Repair common reference mistakes in LLM-produced plans (deterministic, additive safety).
            execution_plan = self._repair_step_references(execution_plan)
            
            # Filter out unnecessary clarification steps when intent is clear enough to proceed
            execution_plan = self._filter_unnecessary_clarifications(execution_plan, intent_plan, fen)
            
            # LOG OUTPUT
            import sys
            print(f"\n{'='*80}")
            print(f"✅ [PLANNER] OUTPUT:")
            print(f"   Plan ID: {execution_plan.plan_id}")
            print(f"   Total Steps: {len(execution_plan.steps)}")
            for step in execution_plan.steps:
                print(f"      Step {step.step_number}: {step.action_type}")
                print(f"         Purpose: {step.purpose}")
                if step.parameters:
                    print(f"         Parameters: {list(step.parameters.keys())}")
                print(f"         Expected Output: {step.expected_output}")
            print(f"{'='*80}\n")
            sys.stdout.flush()
            
            return execution_plan
        except Exception as e:
            print(f"   ❌ Planner error: {e}")
            import traceback
            traceback.print_exc()
            # Fallback: create simple plan
            return self._create_fallback_plan(intent_plan, fen)

    def _intent_mentions_piece_and_goal(self, intent_plan: IntentPlan, context: Dict[str, Any]) -> bool:
        """
        Generic heuristic: user mentions a specific piece type AND a strategic goal.
        When true, we should investigate moves by that piece type in addition to engine top moves.
        This ensures we test user-relevant moves, not just engine suggestions.
        """
        try:
            intent_blob = json.dumps(getattr(intent_plan, "to_dict")(), ensure_ascii=False).lower()  # type: ignore
        except Exception:
            try:
                intent_blob = str(intent_plan).lower()
            except Exception:
                intent_blob = ""
        user_msg = (context.get("user_message") or context.get("message") or "").lower()
        combined = f"{intent_blob}\n{user_msg}"
        
        # Generic piece types (not just knight)
        piece_types = ["knight", "bishop", "rook", "queen", "pawn", "king"]
        mentions_piece = any(piece in combined for piece in piece_types)
        
        # Generic strategic goals (not just castling)
        strategic_goals = [
            "castle", "castling", "o-o", "0-0",
            "develop", "development", "activate", "mobilize",
            "control", "occupy", "attack", "defend",
            "centralize", "coordinate", "connect"
        ]
        mentions_goal = any(goal in combined for goal in strategic_goals)
        
        return mentions_piece and mentions_goal

    def _extract_mentioned_piece_type(self, intent_plan: IntentPlan, context: Dict[str, Any]) -> Optional[str]:
        """
        Generic: Extract which piece type the user mentioned (any piece, not just knight).
        Returns piece type string (e.g., "knight", "bishop") or None.
        """
        try:
            intent_blob = json.dumps(getattr(intent_plan, "to_dict")(), ensure_ascii=False).lower()  # type: ignore
        except Exception:
            try:
                intent_blob = str(intent_plan).lower()
            except Exception:
                intent_blob = ""
        user_msg = (context.get("user_message") or context.get("message") or "").lower()
        combined = f"{intent_blob}\n{user_msg}"
        
        # Generic piece types (in order of commonality for development questions)
        piece_types = ["knight", "bishop", "rook", "queen", "pawn", "king"]
        for piece in piece_types:
            if piece in combined:
                return piece
        return None

    def _extract_piece_instance_id(
        self,
        intent_plan: IntentPlan,
        *,
        piece_type: str,
        side_to_move: Optional[str],
    ) -> Optional[str]:
        """
        Extract a specific piece-instance id (e.g. 'white_knight_g1') from connected_ideas entities if present.
        """
        try:
            ci = getattr(intent_plan, "connected_ideas", None)
        except Exception:
            ci = None
        if not isinstance(ci, dict):
            return None
        ents = ci.get("entities") or []
        if not isinstance(ents, list):
            return None

        rx = re.compile(r"^(white|black)_([a-z]+)_([a-h][1-8])$")
        side = (side_to_move or "").lower().strip()
        for e in ents:
            if not isinstance(e, dict):
                continue
            label = e.get("label")
            if not isinstance(label, str) or not label:
                continue
            m = rx.match(label.strip())
            if not m:
                continue
            color, ptype, _sq = m.group(1), m.group(2), m.group(3)
            if ptype != piece_type:
                continue
            if side and color != side:
                continue
            return label.strip()
        return None

    def _extract_needs_clarification_options(
        self,
        intent_plan: IntentPlan,
        *,
        piece_type: str,
        side_to_move: Optional[str],
    ) -> List[str]:
        """
        Extract ambiguity options from connected_ideas entities of the form:
        'needs_clarification:<piece_type>:<opt1>,<opt2>,...'
        """
        try:
            ci = getattr(intent_plan, "connected_ideas", None)
        except Exception:
            ci = None
        if not isinstance(ci, dict):
            return []
        ents = ci.get("entities") or []
        if not isinstance(ents, list):
            return []

        side = (side_to_move or "").lower().strip()
        prefix = f"needs_clarification:{piece_type}:"
        options: List[str] = []
        for e in ents:
            if not isinstance(e, dict):
                continue
            label = e.get("label")
            if not isinstance(label, str) or not label:
                continue
            s = label.strip()
            if not s.startswith(prefix):
                continue
            raw = s[len(prefix):].strip()
            if not raw:
                continue
            for opt in [x.strip() for x in raw.split(",") if x.strip()]:
                if side and opt.startswith(("white_", "black_")):
                    if not opt.startswith(f"{side}_"):
                        continue
                options.append(opt)
        # Preserve order, dedupe
        deduped: List[str] = []
        seen = set()
        for o in options:
            if o not in seen:
                seen.add(o)
                deduped.append(o)
        return deduped

    def _repair_step_references(self, execution_plan: ExecutionPlan) -> ExecutionPlan:
        """
        Repair common invalid references produced by the Planner LLM.
        Example: apply_line line_ref = step:3.witness_line_san but step 3 is investigate_move.
        """
        if not execution_plan or not execution_plan.steps:
            return execution_plan

        step_by_num: Dict[int, ExecutionStep] = {s.step_number: s for s in execution_plan.steps}
        first_target_step_num: Optional[int] = None
        for s in execution_plan.steps:
            if s.action_type == "investigate_target":
                first_target_step_num = s.step_number
                break

        for s in execution_plan.steps:
            if s.action_type != "apply_line":
                continue
            params = s.parameters if isinstance(s.parameters, dict) else {}
            line_ref = params.get("line_ref")
            if not isinstance(line_ref, str):
                continue

            # If this apply_line step is intended to apply a target witness line, force it to use the first
            # investigate_target witness. This prevents accidentally applying pv_after_move (which is often a suffix).
            try:
                purpose = (s.purpose or "").lower()
                if first_target_step_num is not None and ("witness" in purpose or "target" in purpose):
                    desired = f"step:{first_target_step_num}.goal_search_results.witness_line_san"
                    if line_ref != desired:
                        params["line_ref"] = desired
                        s.parameters = params
                        continue
            except Exception:
                pass

            # Additional safety: if line_ref points at goal_search_results from a step that is NOT investigate_target,
            # rewrite it to the first investigate_target step's witness line.
            # This fixes the common LLM error: "step:7.goal_search_results.witness_line_san" where step 7 is investigate_move.
            if first_target_step_num is not None and ".goal_search_results." in line_ref and line_ref.startswith("step:"):
                try:
                    after = line_ref.split("step:", 1)[1]
                    n_str = after.split(".", 1)[0]
                    n = int(n_str)
                    producer = step_by_num.get(n)
                    if producer and producer.action_type != "investigate_target":
                        params["line_ref"] = f"step:{first_target_step_num}.goal_search_results.witness_line_san"
                        s.parameters = params
                        continue
                except Exception:
                    pass

            # Handle only the simplest/common pattern: step:N.witness_line_san
            if ".witness_line_san" not in line_ref:
                continue
            if not line_ref.startswith("step:"):
                continue
            try:
                # "step:3.witness_line_san" -> 3
                after = line_ref.split("step:", 1)[1]
                n_str = after.split(".", 1)[0]
                n = int(n_str)
            except Exception:
                continue

            producer = step_by_num.get(n)
            if not producer:
                continue
            if producer.action_type == "investigate_target":
                # Fine; but prefer the canonical nested path for investigate_target
                params["line_ref"] = f"step:{n}.goal_search_results.witness_line_san"
                s.parameters = params
                continue
            if producer.action_type == "investigate_move":
                # investigate_move doesn't have witness_line_san; use pv_after_move instead
                params["line_ref"] = f"step:{n}.pv_after_move"
                s.parameters = params
                continue

            # Fallback: if we have an investigate_target in the plan, point to that witness line.
            if first_target_step_num is not None:
                params["line_ref"] = f"step:{first_target_step_num}.goal_search_results.witness_line_san"
                s.parameters = params

        return execution_plan

    def _filter_unnecessary_clarifications(
        self,
        execution_plan: ExecutionPlan,
        intent_plan: IntentPlan,
        fen: Optional[str]
    ) -> ExecutionPlan:
        """
        Remove unnecessary clarification steps when the intent is clear enough to proceed.
        Only keep clarification steps if:
        1. The intent is genuinely ambiguous (e.g., multiple pieces could be meant AND no context identifies which)
        2. Critical information is missing (e.g., no FEN when position analysis is needed)
        """
        if not execution_plan or not execution_plan.steps:
            return execution_plan
        
        # Check if we have sufficient context to proceed
        has_fen = bool(fen)
        has_investigation_requests = bool(intent_plan.investigation_requests)
        intent_is_clear = bool(intent_plan.goal and intent_plan.user_intent_summary)
        
        filtered_steps = []
        for step in execution_plan.steps:
            if step.action_type == "ask_clarification":
                # Check if this clarification is necessary
                question = step.parameters.get("question", "").lower()
                
                # Remove if:
                # 1. We have FEN and investigation requests (sufficient context)
                # 2. Intent is clear (goal and summary provided)
                # 3. Question is about preferences/style (not critical ambiguity)
                if has_fen and has_investigation_requests and intent_is_clear:
                    # Check if question is about preferences/style (not critical)
                    preference_keywords = ["preference", "style", "detail", "level", "how would you like", "kingside castling"]
                    if any(kw in question for kw in preference_keywords):
                        print(f"   ⚠️ [PLANNER] Removing unnecessary clarification step: {question[:50]}...")
                        continue  # Skip this clarification step
                
                # Keep if question is about critical ambiguity (which piece, which move, etc.)
                critical_keywords = ["which piece", "which move", "which knight", "which bishop"]
                if any(kw in question for kw in critical_keywords):
                    # Only keep if we genuinely don't have enough context
                    if not has_fen or not has_investigation_requests:
                        filtered_steps.append(step)
                    else:
                        print(f"   ⚠️ [PLANNER] Removing unnecessary clarification step: {question[:50]}...")
                        continue
                else:
                    # For other clarification questions, remove if we have sufficient context
                    if has_fen and has_investigation_requests:
                        print(f"   ⚠️ [PLANNER] Removing unnecessary clarification step: {question[:50]}...")
                        continue
            
            filtered_steps.append(step)
        
        # Renumber steps
        for idx, step in enumerate(filtered_steps):
            step.step_number = idx + 1
        
        execution_plan.steps = filtered_steps
        return execution_plan
    
    def _build_planning_prompt(
        self,
        intent_plan: IntentPlan,
        planner_context: Optional[Dict[str, Any]],
        context: Dict[str, Any],
        fen: Optional[str]
    ) -> str:
        """Build prompt for thinking/planning"""
        
        def _cap(s: str, max_chars: int) -> str:
            if not isinstance(s, str):
                return ""
            if max_chars <= 0:
                return ""
            if len(s) <= max_chars:
                return s
            return s[:max_chars] + f"\n... <truncated {len(s) - max_chars} chars>"
        
        # Format legal moves if available
        moves_text = ""
        if planner_context:
            moves_text = "\nLEGAL MOVES BY PIECE:\n"
            for piece_type, moves in planner_context["legal_moves_by_piece"].items():
                if moves:
                    moves_text += f"\n{piece_type.upper()} ({len(moves)} moves):\n"
                    for move in moves[:8]:  # Limit to top 8 per piece
                        move_desc = f"  {move['move_san']}"
                        if move["is_capture"]:
                            move_desc += " (capture)"
                        if move["is_check"]:
                            move_desc += " (check)"
                        moves_text += move_desc + "\n"
        moves_text = _cap(moves_text, int(os.getenv("PLANNER_MOVES_TEXT_MAX_CHARS", "2500")))
        
        # Format tags if available
        tags_text = ""
        if planner_context:
            tags_info = planner_context.get("tags", {})
            tags_text = f"\nPOSITION TAGS:\n"
            tags_text += f"Summary: {tags_info.get('tag_summary', 'No summary')}\n"
            if tags_info.get("tactical_tags"):
                tags_text += f"Tactical: {len(tags_info['tactical_tags'])} tags\n"
            threats = tags_info.get("threats", {})
            if isinstance(threats, dict) and (threats.get("white") or threats.get("black")):
                tags_text += f"Threats: {len(threats.get('white', []))} white, {len(threats.get('black', []))} black\n"
        tags_text = _cap(tags_text, int(os.getenv("PLANNER_TAGS_TEXT_MAX_CHARS", "800")))

        analysis_text = ""
        if planner_context:
            analysis_summary = planner_context.get("analysis_summary")
            if analysis_summary:
                analysis_lines = []
                eval_cp = analysis_summary.get("eval_cp")
                if eval_cp is not None:
                    analysis_lines.append(f"Eval (white perspective): {eval_cp:+.0f} cp")
                if analysis_summary.get("best_move"):
                    analysis_lines.append(f"Best move: {analysis_summary['best_move']}")
                candidate_moves = analysis_summary.get("candidate_moves") or []
                if candidate_moves:
                    analysis_lines.append("Top candidates:")
                    for cand in candidate_moves:
                        move = cand.get("move")
                        eval_text = f" ({cand.get('eval_cp'):+.0f} cp)" if cand.get("eval_cp") is not None else ""
                        pv = cand.get("pv")
                        pv_text = ""
                        if isinstance(pv, str) and pv:
                            pv_short = pv[:90] + ("…" if len(pv) > 90 else "")
                            pv_text = f" → {pv_short}"
                        analysis_lines.append(f"  • {move}{eval_text}{pv_text}")
                insights = analysis_summary.get("top_insights") or []
                if insights:
                    analysis_lines.append("Key insights:")
                    for insight in insights:
                        prefix = "white" if insight.get("side") == "white" else "black"
                        analysis_lines.append(f"  • ({prefix}) {insight.get('insight')}")
                sample_threats = analysis_summary.get("sample_threats") or {}
                threat_counts = analysis_summary.get("threat_counts") or {}
                if threat_counts:
                    analysis_lines.append(f"Threat overview: {threat_counts.get('white', 0)} white / {threat_counts.get('black', 0)} black")
                if sample_threats:
                    for side, entries in sample_threats.items():
                        if entries:
                            analysis_lines.append(f"  • {side} threat: {entries[0].get('threat')} (Δ{entries[0].get('delta_cp', 0)} cp)")

                if analysis_lines:
                    analysis_text = "\nANALYSIS SNAPSHOT:\n" + "\n".join(analysis_lines) + "\n"
        analysis_text = _cap(analysis_text, int(os.getenv("PLANNER_ANALYSIS_TEXT_MAX_CHARS", "1200")))
        
        # Format investigation requests
        inv_requests_text = "\nINVESTIGATION REQUESTS:\n"
        for req in intent_plan.investigation_requests:
            inv_requests_text += f"  - {req.investigation_type}: focus={req.focus}, purpose={req.purpose}\n"

        connected_text = ""
        if getattr(intent_plan, "connected_ideas", None):
            try:
                connected_text = "\nCONNECTED IDEAS (relation graph from Interpreter; expand this into investigations + a discussion agenda):\n"
                connected_text += json.dumps(intent_plan.connected_ideas, indent=2) + "\n"
            except Exception:
                connected_text = ""
        connected_text = _cap(connected_text, int(os.getenv("PLANNER_CONNECTED_TEXT_MAX_CHARS", "1200")))
        
        fen_str = fen or "<from_context>"
        
        prompt = f"""Think through how to answer this question. Create a simple, ordered list of steps.

USER QUESTION: {intent_plan.user_intent_summary or intent_plan.goal}
INTENT: {intent_plan.intent}
GOAL: {intent_plan.goal}

{inv_requests_text}

{moves_text}

{tags_text}

{analysis_text}

{connected_text}

Think through the process:
1. Do we need clarification? (if intent is unclear)
2. What investigations are needed? (which moves/positions to test)
3. What tools to call? (investigator methods)
4. When to synthesize? (after all investigations)
5. When to answer? (after synthesis)

Create a simple, ordered list of steps that will be worked through sequentially.

Output JSON:
{{
  "plan_id": "plan_123",
  "discussion_agenda": [
    {{
      "topic": "short_topic_label",
      "questions_to_answer": ["q1", "q2"],
      "must_surface": {{"tags": [], "roles": [], "themes": []}}
    }}
  ],
  "steps": [
    {{
      "step_number": 1,
      "action_type": "investigate_position",
      "parameters": {{
        "fen": "{fen_str}",
        "focus": "knight"
      }},
      "purpose": "Get position analysis focusing on knight",
      "tool_to_call": "investigator.investigate_position",
      "expected_output": "Position analysis with knight-focused insights"
    }},
    {{
      "step_number": 2,
      "action_type": "investigate_move",
      "parameters": {{
        "fen": "{fen_str}",
        "move_san": "Nf3"
      }},
      "purpose": "Test if Nf3 works and check consequences",
      "tool_to_call": "investigator.investigate_move",
      "expected_output": "PGN with branches showing Nf3 consequences"
    }},
    {{
      "step_number": 3,
      "action_type": "investigate_target",
      "parameters": {{
        "fen_ref": "root",
        "goal": {{
          "op": "predicate",
          "predicate": {{"type": "castle", "params": {{"side": "white", "mode": "can_castle_next"}}}}
        }},
        "policy": {{"query_type": "existence", "max_depth": 8, "beam_width": 4, "branching_limit": 8, "opponent_model": "best"}}
      }},
      "purpose": "Check if the position has a reachable goal state (example: can castle next)",
      "tool_to_call": "investigator.investigate_target",
      "expected_output": "Witness line reaching the goal, or uncertain/failure with limits"
    }},
    {{
      "step_number": 4,
      "action_type": "apply_line",
      "parameters": {{
        "fen_ref": "root",
        "line_ref": "step:3.witness_line_san",
        "max_plies": 12
      }},
      "purpose": "Apply the witness line to reach the target position for follow-up analysis",
      "tool_to_call": null,
      "expected_output": "end_fen + intermediate fens"
    }},
    {{
      "step_number": 5,
      "action_type": "synthesize",
      "parameters": {{}},
      "purpose": "Combine all investigation results",
      "tool_to_call": null,
      "expected_output": "Synthesized findings ready for explanation"
    }},
    {{
      "step_number": 6,
      "action_type": "answer",
      "parameters": {{}},
      "purpose": "Generate final answer",
      "tool_to_call": null,
      "expected_output": "Natural language response"
    }}
  ]
}}"""
        
        return prompt
    
    def _create_fallback_plan(
        self,
        intent_plan: IntentPlan,
        fen: Optional[str]
    ) -> ExecutionPlan:
        """Create a simple fallback plan if LLM fails"""
        steps = []
        
        # Add investigation steps based on investigation_requests
        for idx, req in enumerate(intent_plan.investigation_requests):
            if req.investigation_type == "position":
                steps.append(ExecutionStep(
                    step_number=len(steps) + 1,
                    action_type="investigate_position",
                    parameters={"fen": fen or "", "focus": req.focus},
                    purpose=req.purpose or "Investigate position",
                    tool_to_call="investigator.investigate_position",
                    expected_output="Position analysis"
                ))
            elif req.investigation_type == "move":
                steps.append(ExecutionStep(
                    step_number=len(steps) + 1,
                    action_type="investigate_move",
                    parameters={"fen": fen or "", "move_san": req.focus or ""},
                    purpose=req.purpose or "Investigate move",
                    tool_to_call="investigator.investigate_move",
                    expected_output="Move analysis"
                ))
            elif req.investigation_type == "game":
                steps.append(ExecutionStep(
                    step_number=len(steps) + 1,
                    action_type="investigate_game",
                    parameters={"pgn": "", "focus": req.focus},
                    purpose=req.purpose or "Investigate game",
                    tool_to_call="investigator.investigate_game",
                    expected_output="Game analysis"
                ))
        
        # Add synthesis and answer steps
        if steps:
            steps.append(ExecutionStep(
                step_number=len(steps) + 1,
                action_type="synthesize",
                parameters={},
                purpose="Combine all investigation results",
                tool_to_call=None,
                expected_output="Synthesized findings"
            ))
        
        steps.append(ExecutionStep(
            step_number=len(steps) + 1,
            action_type="answer",
            parameters={},
            purpose="Generate final answer",
            tool_to_call=None,
            expected_output="Natural language response"
        ))
        
        return ExecutionPlan(
            plan_id=f"plan_{uuid.uuid4().hex[:8]}",
            original_intent=intent_plan,
            steps=steps
        )
    
    def _validate_position_relevance(
        self,
        fen: Optional[str],
        intent_plan: IntentPlan
    ) -> Optional[str]:
        """
        Validate that the position is relevant to the user's intent.
        Returns a warning message if there's a potential issue, None otherwise.
        """
        import chess
        
        if not fen:
            return None
        
        # Check if this is the starting position
        STARTING_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        is_starting_position = fen.startswith("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR")
        
        # Check intent for patterns that suggest the user wanted a different position
        intent_summary = intent_plan.user_intent_summary or ""
        goal = intent_plan.goal or ""
        combined_text = f"{intent_summary} {goal}".lower()
        
        # Patterns that suggest specific moves were expected
        move_expected_patterns = [
            "after",
            "following",
            "position after",
            "e4 e5",  # Common opening moves
            "d4 d5",
            "nf3",
        ]
        
        if is_starting_position:
            # Check if user mentioned moves in their intent
            for pattern in move_expected_patterns:
                if pattern in combined_text:
                    return f"Position is starting FEN but intent mentions '{pattern}' - moves may not have been applied"
            
            # Check if investigation requests mention moves_applied
            for req in intent_plan.investigation_requests:
                if req.parameters.get("moves_applied"):
                    expected_moves = req.parameters.get("moves_applied")
                    return f"Moves {expected_moves} were extracted but position is still starting FEN - move application may have failed"
        
        # Check if the position makes sense (basic validation)
        try:
            board = chess.Board(fen)
            if not board.is_valid():
                return "Position FEN is invalid"
        except Exception as e:
            return f"Failed to parse FEN: {e}"
        
        return None
    
    async def _auto_add_candidate_moves(
        self,
        execution_plan: ExecutionPlan,
        planner_context: Optional[Dict[str, Any]],
        fen: Optional[str],
        intent_plan: IntentPlan,
        context: Dict[str, Any]
    ) -> ExecutionPlan:
        """
        Enforce the move selection policy:
        - If the user explicitly mentioned moves, investigate ONLY those.
        - Otherwise, investigate the engine's top candidate move(s) (from cached_analysis).
        - If baseline_intuition is already present (prefetched), do NOT inject extra engine-driven
          candidate investigations for generic DISCUSS/ANALYZE; baseline is the default evidence.
        - If we can't find either, leave the plan as-is.
        """
        if not execution_plan.steps:
            return execution_plan
        
        # Determine which moves should be investigated
        user_moves = self._extract_moves_from_intent(intent_plan)
        normalized_user_moves = self._dedupe_moves(user_moves)
        
        # Baseline-first policy: if baseline intuition exists, don't inject candidate move investigations.
        # The executor should only run extra investigations if they are explicitly planned (or user-requested moves).
        try:
            baseline = context.get("baseline_intuition") if isinstance(context, dict) else None
            has_baseline = isinstance(baseline, dict) and isinstance(baseline.get("scan_root"), dict)
        except Exception:
            has_baseline = False
        
        if normalized_user_moves:
            # User explicitly asked for moves: investigate ONLY those.
            target_moves = [{"move": move, "reason": "user_request"} for move in normalized_user_moves]
        else:
            if has_baseline:
                return execution_plan
            # If user mentions a specific piece type and strategic goal,
            # include moves by that piece type (from legal-moves context) in addition to engine candidates.
            wants_piece_specific = self._intent_mentions_piece_and_goal(intent_plan, context)

            extra_moves: List[Dict[str, Any]] = []
            if wants_piece_specific and planner_context and isinstance(planner_context, dict):
                # Generic: Detect which piece type user mentioned and get moves for that piece type
                lm = planner_context.get("legal_moves_by_piece", {}) or {}
                # NOTE: planner_helpers.get_legal_moves_by_piece uses plural keys ("knights", "bishops", ...)
                
                # Generic: Extract mentioned piece type from intent (any piece, not just knight)
                mentioned_piece_type = self._extract_mentioned_piece_type(intent_plan, context)
                if mentioned_piece_type:
                    piece_plural = f"{mentioned_piece_type}s"  # "knight" -> "knights"
                    piece_moves = lm.get(piece_plural, []) or []
                    
                    side = (planner_context.get("side_to_move") or "white").lower()
                    target_piece_id = self._extract_piece_instance_id(
                        intent_plan,
                        piece_type=mentioned_piece_type,
                        side_to_move=side,
                    )
                    clarify_options = self._extract_needs_clarification_options(
                        intent_plan,
                        piece_type=mentioned_piece_type,
                        side_to_move=side,
                    )

                    # If the interpreter flagged ambiguity, ask a clarifying question instead of mixing identities.
                    if (not target_piece_id) and clarify_options:
                        # Render options as squares if possible: white_knight_g1 -> g1
                        squares: List[str] = []
                        for opt in clarify_options[:4]:
                            try:
                                squares.append(opt.split("_")[-1])
                            except Exception:
                                squares.append(opt)
                        sq_text = " or ".join(squares) if squares else "the relevant one"
                        question = f"Which {side} {mentioned_piece_type} do you mean ({sq_text})?"
                        ask = ExecutionStep(
                            step_number=0,
                            action_type="ask_clarification",
                            parameters={
                                "question": question,
                                "piece_type": mentioned_piece_type,
                                "options": clarify_options[:6],
                                "fen": fen or (planner_context.get("fen") if planner_context else None),
                            },
                            purpose="Clarify which piece the user is referring to (avoid mixing piece identities)",
                            tool_to_call=None,
                            expected_output=f"User specifies which {mentioned_piece_type} to discuss/test"
                        )
                        # Prepend to plan; executor will return early with needs_clarification.
                        execution_plan.steps = [ask] + list(execution_plan.steps or [])
                        for idx, st in enumerate(execution_plan.steps):
                            st.step_number = idx + 1
                        return execution_plan

                    # If a specific piece instance was identified, focus on its from-square.
                    if isinstance(target_piece_id, str) and target_piece_id:
                        preferred_from = target_piece_id.split("_")[-1]
                    else:
                        # Generic fallback: use default starting square for piece type if available
                        preferred_from = None
                    preferred: List[Dict[str, Any]] = []
                    others: List[Dict[str, Any]] = []
                    for m in piece_moves:
                        if not isinstance(m, dict):
                            continue
                        san = m.get("move_san")
                        frm = m.get("from_square")
                        if not san:
                            continue
                        if preferred_from and frm == preferred_from:
                            preferred.append({"move": san, "reason": f"{mentioned_piece_type}_development"})
                        else:
                            others.append({"move": san, "reason": f"{mentioned_piece_type}_development"})

                    for item in (preferred + others)[:3]:
                        extra_moves.append(item)

            engine_moves = await self._get_engine_candidate_moves(
                context=context,
                fen=fen or (planner_context.get("fen") if planner_context else None),
                max_moves=2 if wants_piece_specific else 1
            )
            if not engine_moves and not extra_moves:
                print("   ⚠️ [PLANNER] No candidates available; keeping original move plan")
                return execution_plan

            # Order: intent-relevant moves first, then engine
            target_moves = []
            target_moves.extend(extra_moves)
            engine_list = [m for m in (engine_moves or []) if isinstance(m, dict) and m.get("move")]
            for idx, move_info in enumerate(engine_list):
                # Mark the first engine suggestion explicitly as the primary recommendation candidate.
                reason = move_info.get("reason", "engine_candidate")
                if idx == 0:
                    reason = "engine_best"
                target_moves.append({"move": move_info["move"], "reason": reason})
        
        if not target_moves:
            return execution_plan
        
        fen_for_steps = fen or (planner_context.get("fen") if planner_context else "")

        # Safety filter: only keep candidate moves that are legal for the side-to-move at the root FEN.
        # This prevents injecting nonsense candidates (e.g., opponent-to-move moves) from shallow lists.
        try:
            import chess  # local import to avoid hard dependency at module import time
            if isinstance(fen_for_steps, str) and fen_for_steps.strip():
                board = chess.Board(fen_for_steps.strip())
                filtered_target_moves: List[Dict[str, Any]] = []
                for m in target_moves:
                    san = m.get("move") if isinstance(m, dict) else None
                    if not isinstance(san, str) or not san.strip():
                        continue
                    try:
                        board.parse_san(san.strip())
                        filtered_target_moves.append(m)
                    except Exception:
                        continue
                target_moves = filtered_target_moves
        except Exception:
            # If anything goes wrong (bad FEN, missing chess module), do not block planning.
            pass

        # Re-assign primary recommendation if the originally selected primary was filtered out.
        # Rule: the first engine-sourced move remaining becomes "engine_best".
        engine_first_idx = None
        for idx, m in enumerate(target_moves):
            if isinstance(m, dict) and m.get("reason") in ("engine_best", "engine_candidate", "engine"):
                engine_first_idx = idx
                break
        if engine_first_idx is not None:
            for idx, m in enumerate(target_moves):
                if not isinstance(m, dict):
                    continue
                if idx == engine_first_idx:
                    m["reason"] = "engine_best"
                else:
                    # Keep other reasons as-is; don't clobber intent-relevant labels.
                    pass

        # Speed: hard-cap the number of candidate investigations (keep primary + top others in order).
        # This only applies when the user did NOT explicitly request a list of specific moves.
        if not normalized_user_moves and isinstance(self.max_candidate_investigations, int) and self.max_candidate_investigations > 0:
            try:
                # Deduplicate by normalized SAN while preserving order.
                deduped: List[Dict[str, Any]] = []
                seen_norm = set()
                for m in target_moves:
                    if not isinstance(m, dict):
                        continue
                    san = m.get("move")
                    if not isinstance(san, str) or not san.strip():
                        continue
                    norm = self._normalize_move_key(san)
                    if not norm or norm in seen_norm:
                        continue
                    seen_norm.add(norm)
                    deduped.append(m)

                # Ensure primary (engine_best) is kept first if present.
                primary_idx = next((i for i, m in enumerate(deduped) if isinstance(m, dict) and m.get("reason") == "engine_best"), None)
                capped: List[Dict[str, Any]] = []
                if primary_idx is not None:
                    capped.append(deduped[primary_idx])
                for i, m in enumerate(deduped):
                    if primary_idx is not None and i == primary_idx:
                        continue
                    capped.append(m)
                    if len(capped) >= self.max_candidate_investigations:
                        break

                # If primary existed but got pushed out somehow, re-add it.
                if primary_idx is not None and capped and capped[0].get("reason") != "engine_best":
                    capped[0]["reason"] = "engine_best"

                target_moves = capped
            except Exception:
                pass
        
        # Build new investigate_move steps matching target moves
        new_move_steps: List[ExecutionStep] = []
        for move_info in target_moves:
            move_label = move_info["move"]
            reason_label = move_info["reason"]
            is_primary = reason_label == "engine_best"
            new_move_steps.append(ExecutionStep(
                step_number=0,  # placeholder, will be renumbered
                action_type="investigate_move",
                parameters={
                    "fen": fen_for_steps,
                    "move_san": move_label,
                    # Hint for downstream consumers (Summariser) about which move is the primary recommendation candidate.
                    "is_primary_recommendation": bool(is_primary),
                },
                purpose=f"{'PRIMARY RECOMMENDATION: ' if is_primary else ''}Test {move_label} ({reason_label.replace('_', ' ')})",
                tool_to_call="investigator.investigate_move",
                expected_output=f"PGN showing {move_label} consequences"
            ))
        
        # No need to change plan if we somehow failed to build steps
        if not new_move_steps:
            return execution_plan
        
        # Rebuild plan: remove existing move investigations and insert our curated list
        updated_steps: List[ExecutionStep] = []
        inserted_moves = False
        
        for step in execution_plan.steps:
            if step.action_type == "investigate_move":
                # Skip legacy move steps; we'll replace them with curated ones
                continue
            
            updated_steps.append(step)
            
            if not inserted_moves and step.action_type == "investigate_position":
                updated_steps.extend(new_move_steps)
                inserted_moves = True
        
        if not inserted_moves:
            # If there's no investigate_position step, insert before synth/answer (or at end)
            insert_index = next(
                (idx for idx, step in enumerate(updated_steps) if step.action_type in ("synthesize", "answer")),
                len(updated_steps)
            )
            updated_steps[insert_index:insert_index] = new_move_steps
        
        # Renumber all steps to maintain sequential ordering
        for idx, step in enumerate(updated_steps):
            step.step_number = idx + 1
        
        execution_plan.steps = updated_steps
        enforced_moves = [move_info["move"] for move_info in target_moves]
        source_label = "user" if normalized_user_moves else "engine"
        if self._intent_mentions_knight_castle(intent_plan, context):
            source_label = "intent+engine"
        print(f"   ✅ [PLANNER] Enforcing {source_label} move policy: {enforced_moves}")
        return execution_plan
    
    def _dedupe_moves(self, moves: Optional[List[str]]) -> List[str]:
        """Deduplicate SAN strings while preserving order."""
        if not moves:
            return []
        deduped: List[str] = []
        seen = set()
        for move in moves:
            if not move:
                continue
            normalized = self._normalize_move_key(move)
            if normalized and normalized not in seen:
                seen.add(normalized)
                deduped.append(move.strip())
        return deduped
    
    def _normalize_move_key(self, move: str) -> str:
        """Normalize SAN for deduplication."""
        return move.strip().replace(" ", "").lower()

    def _normalize_fen_key(self, fen: Optional[str]) -> Optional[str]:
        """Use only the stable parts of a FEN when comparing cached analysis."""
        if not fen:
            return None
        try:
            parts = fen.split()
            if len(parts) >= 4:
                return " ".join(parts[:4])
        except Exception:
            pass
        return fen

    def _normalize_candidate_list(self, candidate_list: Any, source: str) -> List[Dict[str, Any]]:
        normalized: List[Dict[str, Any]] = []
        if not isinstance(candidate_list, list):
            return normalized
        for candidate in candidate_list:
            move_label = None
            eval_cp = None
            pv_san = None
            if isinstance(candidate, dict):
                move_label = candidate.get("move") or candidate.get("san")
                eval_cp = candidate.get("eval_cp")
                pv_san = candidate.get("pv_san")
            elif isinstance(candidate, str):
                move_label = candidate
            if not move_label:
                continue
            normalized.append({
                "move": move_label.strip(),
                "eval_cp": eval_cp,
                "pv_san": pv_san,
                "reason": source
            })
        return normalized

    def _collect_cached_candidates(
        self,
        context: Optional[Dict[str, Any]],
        normalized_fen: Optional[str]
    ) -> List[Dict[str, Any]]:
        if not isinstance(context, dict):
            return []
        analyses: List[Dict[str, Any]] = []
        primary = context.get("cached_analysis")
        if isinstance(primary, dict):
            analyses.append(primary)
        for inline in context.get("inline_boards", []) or []:
            cached = inline.get("cached_analysis") if isinstance(inline, dict) else None
            if isinstance(cached, dict):
                analyses.append(cached)

        candidates: List[Dict[str, Any]] = []
        for analysis in analyses:
            analysis_fen = self._normalize_fen_key(analysis.get("fen"))
            if normalized_fen and analysis_fen and analysis_fen != normalized_fen:
                continue
            candidate_list = analysis.get("candidate_moves")
            normalized_candidates = self._normalize_candidate_list(candidate_list, source="cached_analysis")
            candidates.extend(normalized_candidates)
        return candidates

    def _dedupe_candidate_dicts(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        deduped: List[Dict[str, Any]] = []
        seen = set()
        for candidate in candidates:
            move = candidate.get("move")
            if not move:
                continue
            key = self._normalize_move_key(move)
            if key and key not in seen:
                seen.add(key)
                deduped.append(candidate)
        return deduped

    def _select_candidate_subset(
        self,
        candidates: List[Dict[str, Any]],
        fen_for_scoring: Optional[str],
        max_moves: int
    ) -> List[Dict[str, Any]]:
        deduped = self._dedupe_candidate_dicts(candidates)
        if not deduped:
            return []

        side_multiplier = 1
        board = None
        if fen_for_scoring:
            try:
                board = chess.Board(fen_for_scoring)
            except Exception:
                board = None

        if board and board.turn == chess.BLACK:
            side_multiplier = -1

        def effective_score(candidate: Dict[str, Any]) -> Optional[int]:
            eval_cp = candidate.get("eval_cp")
            if eval_cp is None:
                return None
            return eval_cp * side_multiplier

        deduped.sort(
            key=lambda c: effective_score(c) if effective_score(c) is not None else float("-inf"),
            reverse=True
        )

        best_score = next((effective_score(c) for c in deduped if effective_score(c) is not None), None)
        selected: List[Dict[str, Any]] = []

        for candidate in deduped:
            current_score = effective_score(candidate)
            if best_score is not None and current_score is not None:
                drop = best_score - current_score
                if drop > self.engine_move_drop_threshold_cp:
                    print(f"   ⚠️ [PLANNER] Dropping {candidate['move']} (Δ{drop:.0f}cp vs best)")
                    continue
            selected.append(candidate)
            if len(selected) >= max_moves:
                break

        if not selected and deduped:
            selected = [deduped[0]]
        return selected

    async def _probe_engine_for_candidates(self, fen: str, max_moves: int) -> List[Dict[str, Any]]:
        if not self.engine_queue:
            return []
        try:
            board = chess.Board(fen)
        except Exception as e:
            print(f"   ⚠️ [PLANNER] Invalid FEN for engine probe: {e}")
            return []

        try:
            info = await self.engine_queue.enqueue(
                self.engine_queue.engine.analyse,
                board,
                chess.engine.Limit(depth=self.engine_probe_depth),
                multipv=max(1, max_moves)
            )
        except Exception as e:
            print(f"   ⚠️ [PLANNER] Engine probe failed: {e}")
            return []

        infos = info if isinstance(info, list) else [info]
        candidates: List[Dict[str, Any]] = []
        for item in infos:
            pv = item.get("pv")
            score = item.get("score")
            if not pv or not score:
                continue
            move = pv[0]
            try:
                move_san = board.san(move)
            except Exception:
                continue
            eval_cp = self._score_to_white_cp(score)
            pv_san_list = []
            board_copy = board.copy()
            for mv in pv[:6]:
                try:
                    pv_san_list.append(board_copy.san(mv))
                    board_copy.push(mv)
                except Exception:
                    break
            candidates.append({
                "move": move_san,
                "eval_cp": eval_cp,
                "pv_san": " ".join(pv_san_list),
                "reason": "engine_probe"
            })
        return candidates

    def _score_to_white_cp(self, score: Any) -> Optional[int]:
        if score is None:
            return None
        pov = score.white()
        if pov.is_mate():
            mate = pov.mate()
            if mate is None:
                return None
            return 10000 if mate > 0 else -10000
        return pov.score(mate_score=10000)
    
    async def _get_engine_candidate_moves(
        self,
        context: Optional[Dict[str, Any]],
        fen: Optional[str],
        max_moves: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Extract high-quality engine candidate moves.
        Priority:
          1. Cached analysis matching the current FEN
          2. Inline board caches matching FEN
          3. Fresh engine probe (depth ~16) as fallback
        """
        normalized_fen = self._normalize_fen_key(fen)
        candidate_sources = self._collect_cached_candidates(context, normalized_fen)
        
        if not candidate_sources and fen:
            fallback = await self._probe_engine_for_candidates(fen, max_moves=max_moves)
            candidate_sources.extend(fallback)
        
        if not candidate_sources:
            return []
        
        filtered = self._select_candidate_subset(candidate_sources, fen, max_moves)
        return filtered
    
    def _extract_moves_from_intent(self, intent_plan: IntentPlan) -> List[str]:
        """
        Extract chess moves mentioned in user message or intent plan.
        Returns list of move SANs (e.g., ["Qd3", "Qe2", "Bxf7+"]).
        """
        moves = []
        
        # Check investigation_requests for move focuses
        for req in intent_plan.investigation_requests:
            if req.focus:
                # Check if focus looks like a move (SAN pattern)
                import re
                san_pattern = r'\b([NBRQK]?[a-h]?[1-8]?x?[a-h][1-8](?:=[NBRQ])?[+#]?|O-O(?:-O)?)\b'
                if re.match(san_pattern, req.focus, re.IGNORECASE):
                    moves.append(req.focus)
        
        # Check user_intent_summary for moves
        if intent_plan.user_intent_summary:
            import re
            san_pattern = r'\b([NBRQK]?[a-h]?[1-8]?x?[a-h][1-8](?:=[NBRQ])?[+#]?|O-O(?:-O)?)\b'
            found_moves = re.findall(san_pattern, intent_plan.user_intent_summary, re.IGNORECASE)
            moves.extend(found_moves)
        
        # Deduplicate and return
        return list(dict.fromkeys(moves))  # Preserves order while removing duplicates


