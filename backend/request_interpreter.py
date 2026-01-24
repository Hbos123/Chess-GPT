"""
Request Interpreter
Preprocesses user requests to create orchestration plans for the main LLM
"""

from typing import Dict, Any, Optional, List
from openai import OpenAI
import json
import re
import os

import chess

from orchestration_plan import (
    OrchestrationPlan,
    IntentPlan,
    Mode,
    ResponseStyle,
    ResponseGuidelines,
    ToolCall,
    AnalysisRequest,
    FrontendCommand,
    FrontendCommandType,
    StatusMessage,
    InvestigationRequest,
    build_play_mode_plan,
    build_analyze_plan,
    build_review_plan,
    build_training_plan,
    build_chat_plan,
    build_move_impact_plan,
    build_compare_moves_plan,
    build_pv_analysis_plan,
    build_direct_question_plan
)
from interpreter_prompt import (
    INTERPRETER_SYSTEM_PROMPT,
    INTERPRETER_SYSTEM_PROMPT_COMPACT,
    MULTI_PASS_PROMPT_ADDITION,
    INTENT_INTERPRETER_PROMPT,
    CONNECTED_IDEAS_EXTRACTOR_PROMPT,
)
from minimal_prompts import MIN_SYSTEM_PROMPT_V1, INTERPRETER_CONTRACT_V1
from command_protocol import render_command
from action_schema import validate_interpreter_intent

def _looks_like_quota_or_rate_limit_error(e: Exception) -> bool:
    s = str(e).lower()
    return ("insufficient_quota" in s) or ("exceeded your current quota" in s) or ("rate limit" in s) or ("error code: 429" in s)


class RequestInterpreter:
    """
    Preprocesses user requests to create orchestration plans.
    Uses LLM as the PRIMARY interpreter for understanding user intent.
    Supports multi-pass mode for complex requests requiring external data.
    """
    
    def __init__(
        self, 
        openai_client: OpenAI, 
        use_compact_prompt: bool = True,
        use_llm_primary: bool = True,  # LLM-first by default
        enable_multi_pass: bool = False,  # Multi-pass interpreter loop
        game_fetcher = None,
        engine_queue = None,
        llm_router = None,
    ):
        self.client = openai_client
        self.llm_router = llm_router
        self.use_compact_prompt = use_compact_prompt
        self.use_llm_primary = use_llm_primary
        self.enable_multi_pass = enable_multi_pass
        
        # Model configuration - can override via INTERPRETER_MODEL environment variable
        # Default to gpt-5-mini for speed; higher layers can stay on gpt-5.
        self.model = os.getenv("INTERPRETER_MODEL", "gpt-5-mini")
        # Logs should be provider-agnostic; vLLM model id is logged by LLMRouter per-call.
        print(f"   🤖 Interpreter initialized (LLM provider=vllm)")
        # Debug/audit: last LLM I/O (prompts + raw response texts + parsed JSON)
        self._audit_llm_io: Dict[str, Any] = {}
        # Small in-memory cache for connected_ideas pass (avoid repeat LLM calls for same position+query)
        self._connected_ideas_cache: Dict[str, Any] = {}
        
        # Initialize interpreter loop if multi-pass enabled
        self._interpreter_loop = None
        if enable_multi_pass:
            self._init_interpreter_loop(game_fetcher, engine_queue)
    
    def _init_interpreter_loop(self, game_fetcher, engine_queue):
        """Initialize the interpreter loop for multi-pass mode"""
        try:
            from interpreter_loop import InterpreterLoop
            from interpreter_action_executor import InterpreterActionExecutor
            from interpreter_budget import ResourceBudget
            from board_simulator import BoardSimulator
            
            # Create board simulator for chess-specific actions
            board_simulator = BoardSimulator(engine_queue) if engine_queue else None
            
            action_executor = InterpreterActionExecutor(
                game_fetcher=game_fetcher,
                engine_queue=engine_queue,
                openai_client=self.client,
                board_simulator=board_simulator
            )
            
            self._interpreter_loop = InterpreterLoop(
                interpreter=self,
                action_executor=action_executor,
                budget=ResourceBudget.default()
            )
            print("   🔄 Multi-pass interpreter loop initialized with board simulator")
        except Exception as e:
            print(f"   ⚠️ Failed to initialize interpreter loop: {e}")
            import traceback
            traceback.print_exc()
            self._interpreter_loop = None
    
    def _extract_moves_from_message(self, message: str) -> tuple[list[str], str]:
        """
        Extract chess moves from a message like "rate my position after e4 e5 Nf3".
        
        Handles patterns like:
        - "after e4 e5 Nf3"
        - "after 1.e4 e5 2.Nf3"
        - "position after e4, e5, Nf3"
        - "what about after e4 e5"
        
        Returns:
            Tuple of (list of moves, cleaned message without move sequence)
        """
        import re
        
        # Pattern to detect "after [moves]" 
        after_patterns = [
            r'\bafter\s+(.+?)(?:\?|$|\.(?![a-h]\d))',  # "after e4 e5 Nf3?" or end of string
            r'\bposition\s+after\s+(.+?)(?:\?|$)',
            r'\bfollowing\s+(.+?)(?:\?|$)',
            r'\bwhat\s+about\s+after\s+(.+?)(?:\?|$)',
        ]
        
        moves_text = None
        for pattern in after_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                moves_text = match.group(1).strip()
                break
        
        if not moves_text:
            return [], message
        
        # Parse the moves from the extracted text
        # Handle formats: "e4 e5 Nf3", "1.e4 e5 2.Nf3", "e4, e5, Nf3"
        
        # Remove move numbers (1., 2., etc.)
        moves_text = re.sub(r'\d+\.+', ' ', moves_text)
        
        # Split by whitespace or commas
        parts = re.split(r'[\s,]+', moves_text)
        
        # Filter to valid SAN moves
        san_pattern = r'^[KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]?$|^O-O(?:-O)?$'
        moves = []
        for part in parts:
            part = part.strip()
            if part and re.match(san_pattern, part, re.IGNORECASE):
                moves.append(part)
        
        # Create cleaned message (remove the move sequence)
        cleaned_message = message
        for pattern in after_patterns:
            cleaned_message = re.sub(pattern, '', cleaned_message, flags=re.IGNORECASE)
        cleaned_message = cleaned_message.strip()
        
        if moves:
            print(f"   🎯 Extracted moves from message: {moves}")
        
        return moves, cleaned_message

    def _normalize_fen_for_cache(self, fen: Optional[str]) -> str:
        """Normalize FEN for cache keys (strip move counters)."""
        if not fen or not isinstance(fen, str):
            return ""
        try:
            return " ".join(fen.split()[:4])
        except Exception:
            return str(fen)

    def _connected_ideas_cache_key(self, fen: Optional[str], message: str) -> str:
        fen_norm = self._normalize_fen_for_cache(fen)
        msg = (message or "").strip().lower()
        return f"{fen_norm}|{msg}"

    def _should_run_connected_ideas(
        self,
        intent_plan: IntentPlan,
        *,
        message: str,
        fen_for_rel: Optional[str],
        piece_instances: List[Dict[str, Any]],
    ) -> bool:
        """
        Heuristic gate for connected-ideas pass (saves an LLM call when it won’t help).

        Policy is configurable via CONNECTED_IDEAS_POLICY:
        - ambiguity_only (default): only run when piece identity is ambiguous
        - dependency_or_ambiguity: also run on dependency-language markers
        """
        try:
            if getattr(intent_plan, "intent", None) != "discuss_position":
                return False
        except Exception:
            return False

        msg = (message or "").lower()
        policy = (os.getenv("CONNECTED_IDEAS_POLICY", "ambiguity_only") or "ambiguity_only").strip().lower()

        # Piece identity ambiguity (multiple candidates of a type on the relevant side)
        def _count_instances(piece_name: str, color: str) -> int:
            n = 0
            for p in piece_instances or []:
                if not isinstance(p, dict):
                    continue
                if p.get("piece") == piece_name and p.get("color") == color:
                    n += 1
            return n

        side = "white"
        try:
            if fen_for_rel:
                b = chess.Board(fen_for_rel)
                side = "white" if b.turn == chess.WHITE else "black"
        except Exception:
            pass

        for pt in ("knight", "rook", "bishop"):
            if pt in msg and _count_instances(pt, side) >= 2:
                return True

        # Optional: dependency-language marker policy
        if policy == "dependency_or_ambiguity":
            dependency_markers = (
                "to enable", "so i can", "so that", "before", "after", "if ", "then", "unless",
                "tradeoff", "alternative", "sequence", "prerequisite", "blocks", "enables",
                "either", " or ",
            )
            if any(m in msg for m in dependency_markers):
                return True

        return False
    
    def _apply_moves_to_fen(self, starting_fen: str, moves: list[str]) -> tuple[str, bool]:
        """
        Apply a sequence of moves to a FEN position.
        
        Args:
            starting_fen: Starting FEN (or None for starting position)
            moves: List of SAN moves to apply
            
        Returns:
            Tuple of (resulting FEN, success boolean)
        """
        if not moves:
            return starting_fen, True
        
        try:
            # Use starting position if no FEN provided
            if not starting_fen or starting_fen == "startpos":
                board = chess.Board()
            else:
                board = chess.Board(starting_fen)
            
            for move_san in moves:
                try:
                    move = board.parse_san(move_san)
                    if move in board.legal_moves:
                        board.push(move)
                    else:
                        print(f"   ⚠️ Move {move_san} is not legal in current position")
                        return starting_fen, False
                except Exception as e:
                    print(f"   ⚠️ Failed to parse move {move_san}: {e}")
                    return starting_fen, False
            
            resulting_fen = board.fen()
            print(f"   ✅ Applied {len(moves)} moves, resulting FEN: {resulting_fen[:50]}...")
            return resulting_fen, True
            
        except Exception as e:
            print(f"   ❌ Failed to apply moves: {e}")
            return starting_fen, False
    
    async def interpret(
        self,
        message: str,
        context: Dict[str, Any],
        conversation_history: Optional[List[Dict[str, str]]] = None,
        status_callback: Optional[callable] = None
    ) -> OrchestrationPlan:
        """
        Analyze user request and produce an orchestration plan.
        
        Uses LLM as PRIMARY interpreter for true natural language understanding.
        Only uses pattern matching as a fast-path for trivially obvious cases.
        
        Args:
            message: The user's message
            context: Current context (fen, pgn, mode, etc.)
            conversation_history: Recent messages for context
            status_callback: Optional callback for status updates (phase, message, **kwargs)
            
        Returns:
            OrchestrationPlan guiding the main LLM's response
        """
        import time
        
        # Emit initial status
        if status_callback:
            status_callback(
                phase="interpreting",
                message="Understanding your request...",
                timestamp=time.time()
            )
        
        # ✅ All requests go through prompt-based LLM interpretation
        # No phrase/pattern detection - everything handled by prompts
        
        # Use multi-pass interpreter loop if enabled, otherwise single-pass LLM interpretation
        if self.enable_multi_pass and self._interpreter_loop:
            print(f"   🔄 Using multi-pass interpreter loop (rigorous investigation)...")
            if status_callback:
                status_callback(
                    phase="interpreting",
                    message="Decomposing request and planning investigation...",
                    timestamp=time.time()
                )
            
            # Use the interpreter loop for multi-pass investigation
            plan = await self._interpreter_loop.run(
                message=message,
                context=context,
                status_callback=status_callback
            )
        else:
            # Use LLM as PRIMARY interpreter for everything else (single-pass)
            print(f"   🤖 Using LLM interpreter (single-pass)...")
            if status_callback:
                status_callback(
                    phase="interpreting",
                    message="Analyzing intent...",
                    timestamp=time.time()
                )
            
            plan = await self._llm_interpret(message, context, conversation_history)
        
        # POST-PROCESSING: Inject username from connected_accounts if needed
        if plan and plan.tool_sequence:
            connected_accounts = context.get("connected_accounts", [])
            print(f"   📋 Context connected_accounts: {connected_accounts}")
            
            if connected_accounts:
                for tool in plan.tool_sequence:
                    if tool.name == "fetch_and_review_games":
                        # Auto-inject username/platform if not already set
                        if not tool.arguments.get("username"):
                            # Use first connected account
                            account = connected_accounts[0]
                            tool.arguments["username"] = account.get("username")
                            tool.arguments["platform"] = account.get("platform", "chess.com")
                            print(f"   📎 Auto-injected credentials: {account.get('username')} on {account.get('platform')}")
                        else:
                            print(f"   ℹ️ Tool already has username: {tool.arguments.get('username')}")
            else:
                print(f"   ⚠️ No connected_accounts found in context - tool will need username from user")
        
        # Emit detected intent
        if status_callback and plan:
            intent_msg = plan.user_intent_summary or f"{plan.mode.value} mode"
            status_callback(
                phase="planning",
                message=f"Detected: {intent_msg}",
                timestamp=time.time()
            )
            
            # If there are tools planned, emit that too
            if plan.tool_sequence:
                tool_names = [t.name for t in plan.tool_sequence]
                status_callback(
                    phase="planning",
                    message=f"Planning to use: {', '.join(tool_names)}",
                    timestamp=time.time()
                )
        
        return plan
    
    async def interpret_intent(
        self,
        message: str,
        context: Dict[str, Any],
        status_callback: Optional[callable] = None,
        session_id: Optional[str] = None,
    ) -> IntentPlan:
        """
        NEW: Intent-only interpretation for 4-layer pipeline.
        Returns IntentPlan with no chess reasoning.
        
        Args:
            message: The user's message
            context: Current context (fen, pgn, mode, etc.)
            status_callback: Optional callback for status updates
            
        Returns:
            IntentPlan with intent classification only
        """
        import time
        from contextlib import nullcontext
        from pipeline_timer import get_pipeline_timer
        _timer = get_pipeline_timer()
        
        # Emit initial status
        if status_callback:
            status_callback(
                phase="interpreting",
                message="Understanding your request...",
                timestamp=time.time()
            )
        
        try:
            # PRE-PROCESS: Extract moves from "after [moves]" patterns
            with (_timer.span("interpreter:extract_moves") if _timer else nullcontext()):
                extracted_moves, cleaned_message = self._extract_moves_from_message(message)
            
            # Apply moves to get correct FEN if moves were extracted
            original_fen = context.get("fen") or context.get("board_state")
            computed_fen = None
            moves_applied = False
            
            if extracted_moves:
                # Start from provided FEN or starting position
                starting_fen = original_fen if original_fen else None
                with (_timer.span("interpreter:apply_moves_to_fen", {"moves": len(extracted_moves)}) if _timer else nullcontext()):
                    computed_fen, moves_applied = self._apply_moves_to_fen(starting_fen, extracted_moves)
                
                if moves_applied:
                    print(f"   🎯 Updated context FEN after applying {len(extracted_moves)} moves")
                    # Update context with computed FEN
                    context = {**context, "fen": computed_fen, "board_state": computed_fen}
                    context["moves_applied"] = extracted_moves  # Track for downstream use
            
            # Build context summary (with updated FEN if moves were applied)
            with (_timer.span("interpreter:build_context_summary") if _timer else nullcontext()):
                context_summary = self._build_context_summary(context)
            
            # LOG INPUT
            print(f"\n{'='*80}")
            print(f"🔍 [INTERPRETER] INPUT:")
            print(f"   Original Message: {message}")
            if extracted_moves:
                print(f"   Extracted Moves: {extracted_moves}")
                print(f"   Cleaned Message: {cleaned_message}")
            print(f"   Context keys: {list(context.keys())}")
            if context.get("fen"):
                print(f"   FEN: {context.get('fen')[:50]}...")
            if context.get("mode"):
                print(f"   Mode: {context.get('mode')}")
            print(f"{'='*80}\n")
            
            # Build user prompt - include move application info
            moves_context = ""
            if extracted_moves and moves_applied:
                moves_context = f"""
MOVES APPLIED: The user mentioned moves "{' '.join(extracted_moves)}" which have been applied.
The FEN below is the position AFTER these moves have been played.
Original message was: "{message}"
The user is asking about this resulting position.
"""
            
            # Build user prompt
            with (_timer.span("interpreter:build_user_prompt") if _timer else nullcontext()):
                user_prompt = render_command(
                    command="FAST_CLASSIFY",
                    input={
                        "user_message": (cleaned_message if extracted_moves else message),
                        "moves_context": (moves_context or "").strip(),
                        "context_summary": (context_summary or "").strip(),
                    },
                    constraints={
                        "json_only": True,
                        "max_investigation_requests": 4,
                    },
                )

            # Use intent-only prompt
            # gpt-5 models don't support custom temperature, only default (1.0)
            llm_kwargs = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": INTENT_INTERPRETER_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                "response_format": {"type": "json_object"},
            }
            if not self.model.startswith("gpt-5"):
                llm_kwargs["temperature"] = 0.1
            
            with (_timer.span("interpreter:llm_call", {"model": self.model}) if _timer else nullcontext()):
                import time as _time
                _t0 = _time.perf_counter()
                response = None
                if self.llm_router:
                    try:
                        result_json = self.llm_router.complete_json(
                            session_id=session_id or "default",
                            stage="interpreter",
                            subsession="interpreter",
                            system_prompt=MIN_SYSTEM_PROMPT_V1,
                            task_seed=INTERPRETER_CONTRACT_V1,
                            user_text=user_prompt,
                            temperature=(0.1 if not self.model.startswith("gpt-5") else None),
                            model=self.model,
                            max_tokens=int(os.getenv("INTERPRETER_MAX_TOKENS", "450")),
                        )
                    except Exception as e:
                        # Generic repair retry: ask for the *minimal* valid intent JSON.
                        # This handles cases where the model output was truncated or non-JSON.
                        print(f"   ❌ Intent interpretation error: {e}")
                        try:
                            minimal_prompt = render_command(
                                command="FAST_CLASSIFY_RETRY_MINIMAL_JSON",
                                input={
                                    "user_message": (cleaned_message if extracted_moves else message),
                                    "context_summary": (context_summary or "").strip(),
                                    "notes": "Previous attempt failed to parse. Return ONLY minimal valid JSON with required keys. Do NOT include long arrays. For game_select, put selectors in game_select_params/game_select_requests and keep requests <= 8.",
                                },
                                constraints={"json_only": True, "max_investigation_requests": 0},
                            )
                            result_json = self.llm_router.complete_json(
                                session_id=session_id or "default",
                                stage="interpreter",
                                subsession="interpreter_repair",
                                system_prompt=MIN_SYSTEM_PROMPT_V1,
                                task_seed=INTERPRETER_CONTRACT_V1,
                                user_text=minimal_prompt,
                                temperature=(0.0 if not self.model.startswith("gpt-5") else None),
                                model=self.model,
                                max_tokens=int(os.getenv("INTERPRETER_REPAIR_MAX_TOKENS", "260")),
                            )
                        except Exception:
                            raise
                    ok, errs = validate_interpreter_intent(result_json)
                    if not ok:
                        # Single repair retry: ask the model to output a corrected JSON object.
                        try:
                            repair_prompt = render_command(
                                command="REPAIR_JSON",
                                input={"errors": errs, "bad_json": result_json},
                                constraints={"json_only": True},
                            )
                            result_json = self.llm_router.complete_json(
                                session_id=session_id or "default",
                                stage="interpreter",
                                subsession="interpreter",
                                system_prompt=MIN_SYSTEM_PROMPT_V1,
                                task_seed=INTERPRETER_CONTRACT_V1,
                                user_text=repair_prompt,
                                temperature=(0.0 if not self.model.startswith("gpt-5") else None),
                                model=self.model,
                                max_tokens=int(os.getenv("INTERPRETER_MAX_TOKENS", "450")),
                            )
                        except Exception:
                            pass
                else:
                    response = self.client.chat.completions.create(**llm_kwargs)
                    result_json = None
                _dt_intent = _time.perf_counter() - _t0
            # Record token usage for cost audits
            try:
                usage = getattr(response, "usage", None) if response is not None else None
                prompt_tokens = getattr(usage, "prompt_tokens", None) if usage is not None else None
                completion_tokens = getattr(usage, "completion_tokens", None) if usage is not None else None
            except Exception:
                prompt_tokens = None
                completion_tokens = None
            try:
                if _timer:
                    _timer.record_llm("interpreter_intent", float(locals().get("_dt_intent", 0.0)), tokens_in=prompt_tokens, tokens_out=completion_tokens, model=self.model)
            except Exception:
                pass
            try:
                self._audit_llm_io = {
                    "model": self.model,
                    "passes": [
                        {
                            "pass": "intent",
                            "messages": [
                                {"role": "system", "content": INTENT_INTERPRETER_PROMPT},
                                {"role": "user", "content": user_prompt},
                            ],
                            "raw_response_text": (
                                response.choices[0].message.content
                                if response is not None
                                else json.dumps(result_json)
                            ),
                        }
                    ],
                }
            except Exception:
                self._audit_llm_io = {}
            
            # Parse response
            with (_timer.span("interpreter:parse_json") if _timer else nullcontext()):
                if result_json is None:
                    result_json = json.loads(response.choices[0].message.content)
            try:
                if isinstance(self._audit_llm_io.get("passes"), list) and self._audit_llm_io["passes"]:
                    self._audit_llm_io["passes"][0]["parsed_json"] = result_json
            except Exception:
                pass
            
            # Create IntentPlan
            with (_timer.span("interpreter:build_intent_plan") if _timer else nullcontext()):
                intent_plan = IntentPlan.from_dict(result_json)

            # Hardening: vLLM sometimes returns schema-valid JSON that is semantically wrong for our pipeline
            # (e.g., sets investigation_type="fetch_and_review_games" for a position discussion).
            # For DISCUSS/ANALYZE with a concrete FEN, force position-style investigations and ensure FEN is attached.
            try:
                ctx_mode_norm = str((context or {}).get("mode") or "").upper().strip()
                ctx_fen_norm = (context or {}).get("fen") or (context or {}).get("board_state")
                has_fen = isinstance(ctx_fen_norm, str) and bool(str(ctx_fen_norm).strip())
            except Exception:
                ctx_mode_norm = ""
                ctx_fen_norm = None
                has_fen = False

            if (
                intent_plan
                and getattr(intent_plan, "intent", None) == "discuss_position"
                and has_fen
                and ctx_mode_norm in ("DISCUSS", "ANALYZE")
            ):
                try:
                    intent_plan.investigation_required = True
                except Exception:
                    pass
                try:
                    # Keep deprecated field consistent for downstream branches that still read it.
                    intent_plan.investigation_type = "position"
                except Exception:
                    pass
                try:
                    if not isinstance(getattr(intent_plan, "investigation_requests", None), list) or not intent_plan.investigation_requests:
                        intent_plan.investigation_requests = [
                            InvestigationRequest(
                                investigation_type="position",
                                focus=None,
                                parameters={"fen": str(ctx_fen_norm)},
                                purpose="Analyze current position",
                            )
                        ]
                except Exception:
                    pass
                try:
                    for req in (intent_plan.investigation_requests or []):
                        it = str(getattr(req, "investigation_type", "") or "").lower().strip()
                        if it not in ("position", "move", "game"):
                            req.investigation_type = "position"
                        if not isinstance(getattr(req, "parameters", None), dict):
                            req.parameters = {}
                        if "fen" not in req.parameters:
                            req.parameters["fen"] = str(ctx_fen_norm)
                except Exception:
                    pass

            # NEW: LLM pass to extract connected ideas / relationships (domain-agnostic)
            # This helps the Planner expand implied prerequisites, sequences, and verification checks.
            try:
                # Only run for position-discussion / planning-like intents where structure matters.
                if intent_plan.intent == "discuss_position":
                    # Provide FEN + piece instance inventory to preserve piece identity (e.g., distinguishing multiple knights).
                    fen_for_rel = None
                    try:
                        fen_for_rel = (
                            context.get("fen")
                            or context.get("context_fen")
                            or (intent_plan.investigation_requests[0].parameters.get("fen") if intent_plan.investigation_requests else None)
                            or computed_fen
                        )
                    except Exception:
                        fen_for_rel = None

                    piece_instances = []
                    try:
                        if isinstance(fen_for_rel, str) and fen_for_rel:
                            b = chess.Board(fen_for_rel)
                            for sq in chess.SQUARES:
                                p = b.piece_at(sq)
                                if not p:
                                    continue
                                color = "white" if p.color == chess.WHITE else "black"
                                piece_name = chess.piece_name(p.piece_type)
                                sqn = chess.square_name(sq)
                                piece_instances.append({
                                    "id": f"{color}_{piece_name}_{sqn}",
                                    "color": color,
                                    "piece": piece_name,
                                    "square": sqn
                                })
                    except Exception:
                        piece_instances = []

                    # Conditional second pass: only run when it adds value (ambiguity or dependency language).
                    with (_timer.span("interpreter:connected_ideas:should_run") if _timer else nullcontext()):
                        should_run = self._should_run_connected_ideas(
                            intent_plan,
                            message=(cleaned_message if extracted_moves else message),
                            fen_for_rel=fen_for_rel,
                            piece_instances=piece_instances,
                        )
                    if not should_run:
                        intent_plan.connected_ideas = None
                        try:
                            # Record in audit for transparency
                            if not isinstance(self._audit_llm_io.get("passes"), list):
                                self._audit_llm_io["passes"] = []
                            self._audit_llm_io["passes"].append({"pass": "connected_ideas", "skipped": True})
                        except Exception:
                            pass
                    else:
                        # Cache by (normalized FEN + cleaned message) to avoid repeated second-pass calls.
                        cache_key = self._connected_ideas_cache_key(
                            fen_for_rel,
                            (cleaned_message if extracted_moves else message),
                        )
                        cached_ci = None
                        try:
                            cached_ci = self._connected_ideas_cache.get(cache_key)
                        except Exception:
                            cached_ci = None

                        if isinstance(cached_ci, dict):
                            intent_plan.connected_ideas = cached_ci
                            try:
                                if not isinstance(self._audit_llm_io.get("passes"), list):
                                    self._audit_llm_io["passes"] = []
                                self._audit_llm_io["passes"].append(
                                    {"pass": "connected_ideas", "cache_hit": True, "parsed_json": cached_ci}
                                )
                            except Exception:
                                pass
                        else:
                            rel_user_prompt = f"""Extract connected ideas from the user request.

USER MESSAGE: {cleaned_message if extracted_moves else message}

CONTEXT FEN (if available): {fen_for_rel}

PIECE INSTANCES (for identity resolution only; do not analyze):
{json.dumps(piece_instances, indent=2)}

USER INTENT SUMMARY (from prior intent pass): {intent_plan.user_intent_summary}
GOAL LABEL: {intent_plan.goal}

INVESTIGATION REQUESTS (from prior pass):
{json.dumps([ir.to_dict() for ir in intent_plan.investigation_requests], indent=2)}
"""
                            # Default to the same model as the primary interpreter pass (vLLM model name),
                            # not an OpenAI-hosted model name (which will 404 on vLLM).
                            connected_model = os.getenv("CONNECTED_IDEAS_MODEL", self.model)
                            # Keep this very fast; fallback to None on timeout.
                            try:
                                connected_timeout_s = float(os.getenv("CONNECTED_IDEAS_TIMEOUT_S", "2.0"))
                            except Exception:
                                connected_timeout_s = 2.0

                            rel_resp = None
                            with (_timer.span("interpreter:connected_ideas:llm_call", {"model": connected_model, "timeout_s": connected_timeout_s}) if _timer else nullcontext()):
                                try:
                                    import asyncio as _asyncio
                                    async def _run_connected_router():
                                        import time as _time
                                        _t0 = _time.perf_counter()
                                        out = self.llm_router.complete_json(
                                            session_id=session_id or "default",
                                            stage="interpreter_connected_ideas",
                                            subsession="interpreter_connected_ideas",
                                            system_prompt=MIN_SYSTEM_PROMPT_V1,
                                            user_text=rel_user_prompt,
                                            task_seed=None,
                                            temperature=0.0,
                                            model=connected_model,
                                            max_tokens=int(os.getenv("CONNECTED_IDEAS_MAX_TOKENS", "450")),
                                        )
                                        return out, (_time.perf_counter() - _t0)
                                    rel_json, _dt_connected = await _asyncio.wait_for(_run_connected_router(), timeout=connected_timeout_s)
                                    rel_resp = rel_json
                                except Exception as e:
                                    # Timeout or request failure: non-fatal, just skip.
                                    print(f"   ⚠️ [INTERPRETER] connected_ideas LLM call skipped (non-fatal): {e}")
                                    rel_resp = None

                            if rel_resp is not None:
                                # Record token usage for cost audits
                                try:
                                    usage = getattr(rel_resp, "usage", None)
                                    prompt_tokens = getattr(usage, "prompt_tokens", None)
                                    completion_tokens = getattr(usage, "completion_tokens", None)
                                except Exception:
                                    prompt_tokens = None
                                    completion_tokens = None
                                try:
                                    if _timer:
                                        _timer.record_llm("interpreter_connected_ideas", float(locals().get("_dt_connected", 0.0)), tokens_in=prompt_tokens, tokens_out=completion_tokens, model=connected_model)
                                except Exception:
                                    pass

                                intent_plan.connected_ideas = rel_resp if isinstance(rel_resp, dict) else None
                            else:
                                intent_plan.connected_ideas = None
                            try:
                                if isinstance(intent_plan.connected_ideas, dict):
                                    self._connected_ideas_cache[cache_key] = intent_plan.connected_ideas
                            except Exception:
                                pass
                            try:
                                if not isinstance(self._audit_llm_io.get("passes"), list):
                                    self._audit_llm_io["passes"] = []
                                self._audit_llm_io["passes"].append(
                                    {
                                        "pass": "connected_ideas",
                                        "messages": [
                                            {"role": "system", "content": CONNECTED_IDEAS_EXTRACTOR_PROMPT},
                                            {"role": "user", "content": rel_user_prompt},
                                        ],
                                        "raw_response_text": json.dumps(rel_resp) if rel_resp is not None else None,
                                        "parsed_json": intent_plan.connected_ideas,
                                    }
                                )
                            except Exception:
                                pass
            except Exception as e:
                print(f"   ⚠️ [INTERPRETER] connected_ideas extraction failed (non-fatal): {e}")
                intent_plan.connected_ideas = None
            
            # POST-PROCESS: Inject computed FEN into investigation requests if moves were applied
            if extracted_moves and moves_applied and computed_fen:
                for req in intent_plan.investigation_requests:
                    # Add the computed FEN to parameters if not already set
                    if "fen" not in req.parameters:
                        req.parameters["fen"] = computed_fen
                    if "moves_applied" not in req.parameters:
                        req.parameters["moves_applied"] = extracted_moves
                print(f"   ✅ Injected computed FEN into {len(intent_plan.investigation_requests)} investigation request(s)")
            
            # POST-PROCESS: Handle game_review intent - populate game_review_params from connected_accounts
            if intent_plan.intent == "game_review" and intent_plan.needs_game_fetch:
                connected_accounts = context.get("connected_accounts", [])
                if not intent_plan.game_review_params:
                    intent_plan.game_review_params = {}
                
                if connected_accounts:
                    # Use first connected account
                    account = connected_accounts[0]
                    if "username" not in intent_plan.game_review_params:
                        intent_plan.game_review_params["username"] = account.get("username")
                    if "platform" not in intent_plan.game_review_params:
                        # Normalize platform name
                        platform = account.get("platform", "chess.com")
                        if platform in ("chesscom", "chess_com"):
                            platform = "chess.com"
                        elif platform == "lichess":
                            platform = "lichess"
                        intent_plan.game_review_params["platform"] = platform
                    print(f"   ✅ Injected game_review_params from connected_accounts: {intent_plan.game_review_params}")
                else:
                    print(f"   ⚠️ No connected_accounts found - game_review will need username from user")
            
            # LOG OUTPUT
            import sys
            print(f"\n{'='*80}")
            print(f"✅ [INTERPRETER] OUTPUT:")
            print(f"   Intent: {intent_plan.intent}")
            print(f"   Scope: {intent_plan.scope}")
            print(f"   Goal: {intent_plan.goal}")
            print(f"   Investigation Required: {intent_plan.investigation_required}")
            print(f"   Investigation Type: {intent_plan.investigation_type}")
            print(f"   Investigation Requests: {len(intent_plan.investigation_requests)}")
            for i, req in enumerate(intent_plan.investigation_requests):
                print(f"      [{i+1}] Type: {req.investigation_type}, Focus: {req.focus}, Purpose: {req.purpose}")
            print(f"   Mode: {intent_plan.mode.value}")
            print(f"   Mode Confidence: {intent_plan.mode_confidence}")
            print(f"   User Intent Summary: {intent_plan.user_intent_summary}")
            print(f"{'='*80}\n")
            sys.stdout.flush()
            
            # VALIDATION: Ensure investigation_required matches investigation_requests
            if intent_plan.investigation_required:
                if not intent_plan.investigation_requests:
                    print(f"   ⚠️ WARNING: investigation_required=True but no investigation_requests! Setting to False.")
                    intent_plan.investigation_required = False
                else:
                    # Validate investigation_type consistency (if provided)
                    if intent_plan.investigation_type:
                        for req in intent_plan.investigation_requests:
                            if req.investigation_type != intent_plan.investigation_type:
                                print(f"   ⚠️ WARNING: investigation_type mismatch! Plan says '{intent_plan.investigation_type}' but request has '{req.investigation_type}'")
            else:
                # If investigation_required=False, clear investigation_requests
                if intent_plan.investigation_requests:
                    print(f"   ⚠️ WARNING: investigation_required=False but investigation_requests exist! Clearing requests.")
                    intent_plan.investigation_requests = []
            
            if status_callback:
                status_callback(
                    phase="interpreting",
                    message=f"Detected: {intent_plan.user_intent_summary or intent_plan.intent}",
                    timestamp=time.time()
                )
            
            return intent_plan
            
        except Exception as e:
            print(f"   ❌ Intent interpretation error: {e}")
            import traceback
            traceback.print_exc()

            # If we hit quota/rate limits, degrade gracefully for position discussion:
            # keep the pipeline moving (Planner fallback + Investigator can still run), and
            # surface a clear hint in the summary.
            try:
                fen_hint = context.get("fen") or context.get("board_state")
                msg_lower = (message or "").lower()
                # Generic: Detect position analysis requests (not specific keywords)
                # Pattern: mentions position-related concepts OR asks for move suggestions
                position_indicators = [
                    "best move", "what do i do", "what should", "how do i", "how can i",
                    "progress", "suggest", "recommend", "advice", "help",
                    "position", "situation", "here", "this position"
                ]
                has_position_request = any(indicator in msg_lower for indicator in position_indicators)
                
                if fen_hint and has_position_request:
                    # Generic: Extract piece type if mentioned (any piece, not just specific ones)
                    piece_types = ["knight", "bishop", "rook", "queen", "pawn", "king"]
                    focus = None
                    for piece in piece_types:
                        if piece in msg_lower:
                            focus = piece
                            break
                    # Generic: Detect strategic goals
                    if not focus and ("castle" in msg_lower or "castling" in msg_lower or "king" in msg_lower):
                        focus = "king_safety"
                    # Minimal, deterministic investigation request
                    reqs = [
                        InvestigationRequest(
                            investigation_type="position",
                            focus=focus,
                            parameters={"fen": fen_hint},
                            purpose="Analyze current position and suggest practical moves (LLM quota fallback)",
                        )
                    ]
                    return IntentPlan(
                        intent="discuss_position",
                        scope="current_position",
                        goal="suggest moves",
                        constraints={"depth": "standard", "tone": "coach", "verbosity": "medium"},
                        investigation_required=True,
                        investigation_requests=reqs,
                        investigation_type="position",
                        mode=Mode.ANALYZE,
                        mode_confidence=0.6,
                        user_intent_summary=(
                            "LLM quota/rate-limit hit in interpreter; using deterministic fallback intent to continue analysis"
                            if _looks_like_quota_or_rate_limit_error(e)
                            else "Using deterministic fallback intent to continue analysis"
                        ),
                        needs_game_fetch=False,
                        connected_ideas=None,
                    )
            except Exception:
                pass

            # Default fallback to general chat
            return IntentPlan(
                intent="general_chat",
                scope=None,
                goal="answer question",
                constraints={},
                investigation_required=False,
                investigation_type=None,
                mode=Mode.CHAT,
                mode_confidence=0.5,
                user_intent_summary=(
                    "LLM quota/rate-limit hit in intent classification"
                    if _looks_like_quota_or_rate_limit_error(e)
                    else "Error in intent classification"
                ),
            )
    
    def _trivial_detect(
        self,
        message: str,
        context: Dict[str, Any]
    ) -> Optional[OrchestrationPlan]:
        """
        Only catch TRIVIALLY obvious cases to save API calls.
        If there's ANY ambiguity, return None and let LLM handle it.
        """
        msg_lower = message.lower().strip()
        
        # IMPORTANT: Even if the message is long (multi-intent), we still want to catch
        # obvious "rate the last move" requests. Users often append this to other text.
        # Everything else stays strict to avoid mis-routing.
        
        # PLAY MODE - only ultra-obvious triggers
        if msg_lower in ["let's play", "play a game", "your move", "your turn"]:
            plan = build_play_mode_plan()
            plan.user_intent_summary = "Start/continue a game"
            return plan
        
        # RATE LAST MOVE - detect anywhere in message (can be appended to other requests)
        move_quality_triggers = [
            "rate that move",
            "rate the move",
            "rate last move",
            "rate the last move",
            "how was that move",
            "how was that last move",
            "how good was that",
            "how good was that move",
            "how good was that last move",
            "how good was the last move",
            "was that a good move",
            "was that good",
            "good move?",
        ]
        if any(t in msg_lower for t in move_quality_triggers):
            fen = context.get("board_state") or context.get("fen")
            last_move = context.get("last_move", {})
            if fen and last_move.get("move"):
                return build_move_impact_plan(
                    fen_before=last_move.get("fen_before", fen),
                    fen_after=fen,
                    move_san=last_move.get("move")
                )

        # Skip trivial detection for anything longer than a simple phrase
        if len(msg_lower) > 50:
            return None
        
        # Everything else → LLM
        return None
    
    def _legacy_pattern_detect(
        self,
        message: str,
        context: Dict[str, Any]
    ) -> Optional[OrchestrationPlan]:
        """
        LEGACY: Pattern-based detection (NOT USED by default).
        Kept for reference. LLM interpreter is now the primary method.
        
        To re-enable pattern matching, set use_llm_primary=False in __init__.
        """
        msg_lower = message.lower().strip()
        
        # ================================================================
        # PLAY MODE
        # ================================================================
        if context.get("mode") == "play":
            # User is in play mode
            if any(phrase in msg_lower for phrase in ["i played", "my move", "your turn"]):
                return build_play_mode_plan()
        
        if any(phrase in msg_lower for phrase in ["let's play", "play a game", "play with me", "play you"]):
            plan = build_play_mode_plan()
            plan.system_prompt_additions = (
                "User wants to play. Assume they're White and go first. "
                "Respond conversationally, make it clear whose turn it is."
            )
            plan.user_intent_summary = "Start a game"
            return plan
        
        # ================================================================
        # ANALYZE MODE - Move analysis
        # ================================================================
        # ================================================================
        # COMPARE MOVES - "Is e4 better than d4?" / "Compare Nf3 and Nc3"
        # ================================================================
        compare_patterns = [
            r"is\s+([KQRBNP]?[a-h]?[1-8]?x?[a-h][1-8])\s+better\s+than\s+([KQRBNP]?[a-h]?[1-8]?x?[a-h][1-8])",
            r"compare\s+([KQRBNP]?[a-h]?[1-8]?x?[a-h][1-8])\s+(?:and|vs|versus|to|with)\s+([KQRBNP]?[a-h]?[1-8]?x?[a-h][1-8])",
            r"([KQRBNP]?[a-h]?[1-8]?x?[a-h][1-8])\s+or\s+([KQRBNP]?[a-h]?[1-8]?x?[a-h][1-8])\s*\?",
            r"which\s+is\s+better[,:]?\s*([KQRBNP]?[a-h]?[1-8]?x?[a-h][1-8])\s+or\s+([KQRBNP]?[a-h]?[1-8]?x?[a-h][1-8])",
        ]
        
        for pattern in compare_patterns:
            match = re.search(pattern, msg_lower, re.IGNORECASE)
            if match:
                move1 = match.group(1)
                move2 = match.group(2)
                fen = context.get("board_state") or context.get("fen")
                if fen:
                    return build_compare_moves_plan(fen=fen, move1=move1, move2=move2)
        
        # "Is Nf3 good?" / "Rate e4" / "What about Bc4?"
        move_patterns = [
            r"is\s+([KQRBNP]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]?)\s+(?:a\s+)?good",
            r"rate\s+([KQRBNP]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]?)",
            r"what\s+about\s+([KQRBNP]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]?)",
            r"how\s+is\s+([KQRBNP]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]?)",
        ]
        
        for pattern in move_patterns:
            match = re.search(pattern, msg_lower, re.IGNORECASE)
            if match:
                move = match.group(1)
                fen = context.get("board_state") or context.get("fen")
                if fen:
                    return build_analyze_plan(fen=fen, move=move)
        
        # "Rate that move" / "How was that move?" / "How good was that?"
        move_quality_triggers = [
            "rate that", "rate the move", "how was that", "rate last",
            "how good", "was that good", "is that good", "good move",
            "bad move", "what do you think of"
        ]
        if any(phrase in msg_lower for phrase in move_quality_triggers):
            last_move = context.get("last_move", {})
            if last_move:
                fen_before = last_move.get("fen_before")
                fen_after = context.get("board_state") or context.get("fen")
                move = last_move.get("move")
                if fen_before and move:
                    # Use full impact analysis if we have before and after
                    if fen_after:
                        plan = build_move_impact_plan(
                            fen_before=fen_before,
                            move=move,
                            fen_after=fen_after
                        )
                    else:
                        plan = build_analyze_plan(
                            fen=fen_before, 
                            move=move,
                            include_piece_profiles=True,
                            compare_before_after=True
                        )
                    plan.user_intent_summary = f"Rate the last move ({move})"
                    return plan
        
        # ================================================================
        # ANALYZE MODE - PV/Sequence analysis
        # ================================================================
        pv_triggers = ["explain the pv", "explain the line", "why is this the best", 
                       "why this sequence", "explain this continuation", "what's the idea",
                       "why these moves"]
        
        if any(trigger in msg_lower for trigger in pv_triggers):
            fen = context.get("board_state") or context.get("fen")
            cached = context.get("cached_analysis", {})
            pv_moves = cached.get("pv", [])
            
            if fen:
                if pv_moves and len(pv_moves) > 0:
                    plan = build_pv_analysis_plan(fen=fen, pv_moves=pv_moves)
                else:
                    # Need to get PV first
                    plan = build_analyze_plan(fen=fen)
                    plan.analysis_requests[0].include_pv_analysis = True
                    plan.system_prompt_additions = (
                        "User wants to understand WHY this is the best line. "
                        "Explain the strategic purpose of the PV sequence, "
                        "how pieces improve through the moves."
                    )
                plan.user_intent_summary = "Explain the PV/best line"
                return plan
        
        # ================================================================
        # ANALYZE MODE - Position analysis
        # ================================================================
        analyze_triggers = ["analyze this", "analyze the position", "evaluate this", 
                          "what's best", "best move", "what should i play"]
        
        if any(trigger in msg_lower for trigger in analyze_triggers):
            fen = context.get("board_state") or context.get("fen")
            if fen:
                plan = build_analyze_plan(fen=fen)
                plan.user_intent_summary = "Analyze current position"
                return plan
        
        # ================================================================
        # REVIEW MODE
        # ================================================================
        
        # Personal review triggers (fetch from Chess.com/Lichess, NOT the current board)
        personal_game_triggers = ["my last game", "my game", "my recent game", "review my last",
                                  "pull up my", "fetch my", "get my game"]
        
        is_personal_game_request = any(trigger in msg_lower for trigger in personal_game_triggers)
        
        review_triggers = ["review my", "my profile", "my games", "why am i stuck",
                         "help me improve", "what am i doing wrong", "analyze me",
                         "check my profile", "look at my"]
        
        if is_personal_game_request or any(trigger in msg_lower for trigger in review_triggers):
            # Try to extract username and platform
            username, platform = self._extract_username_platform(message, context)
            
            if username:
                plan = build_review_plan(username=username, platform=platform)
                plan.user_intent_summary = f"Review profile for {username}"
                return plan
            else:
                # Need to ask for username
                plan = build_review_plan()
                plan.skip_tools = True
                plan.system_prompt_additions = (
                    "User wants profile review but didn't provide username. "
                    "Ask for their username and platform (chess.com or lichess)."
                )
                plan.user_intent_summary = "Profile review - needs username"
                return plan
        
        # Check for username + platform pattern: "HKB03 on chess.com"
        username, platform = self._extract_username_platform(message, context)
        if username and platform:
            plan = build_review_plan(username=username, platform=platform)
            plan.user_intent_summary = f"Review {username} on {platform}"
            return plan
        
        # "Review this game" / "Review the game" with PGN in context (NOT personal - reviewing current board)
        if "review" in msg_lower and "game" in msg_lower and "my" not in msg_lower:
            pgn = context.get("pgn")
            if pgn:
                plan = build_review_plan(pgn=pgn)
                plan.user_intent_summary = "Review the current game"
                return plan
        
        # ================================================================
        # TRAINING MODE
        # ================================================================
        training_triggers = ["train", "drill", "practice", "exercises", "work on my"]
        
        if any(trigger in msg_lower for trigger in training_triggers):
            # Extract training focus
            training_focus = self._extract_training_focus(message)
            plan = build_training_plan(training_query=training_focus)
            plan.user_intent_summary = f"Training on {training_focus}"
            return plan
        
        # ================================================================
        # DIRECT QUESTIONS - Concise answers needed
        # ================================================================
        fen = context.get("board_state") or context.get("fen")
        
        # "What is the most active piece?" / "Which piece is most active?"
        if re.search(r"(what|which).*(most|least).*(active|developed|important|dangerous|weak)", msg_lower):
            if "most active" in msg_lower or "most developed" in msg_lower:
                return build_direct_question_plan("most_active", fen=fen, focus="most active piece")
            elif "least active" in msg_lower or "worst" in msg_lower or "weakest" in msg_lower:
                return build_direct_question_plan("weakest_piece", fen=fen, focus="weakest piece")
            elif "most important" in msg_lower or "most dangerous" in msg_lower:
                return build_direct_question_plan("most_active", fen=fen, focus="key piece")
        
        # "What's the threat?" / "Any threats?"
        if re.search(r"(what|any|where).*(threat|danger|attack)", msg_lower):
            return build_direct_question_plan("threat", fen=fen, focus="threats")
        
        # "Best square for the knight?" / "Where should my bishop go?"
        if re.search(r"(best|good|ideal).*(square|place|post)", msg_lower):
            return build_direct_question_plan("best_square", fen=fen, focus="best squares")
        
        # "Who's better?" / "Who's winning?"
        if re.search(r"who.*(better|winning|ahead|advantage)", msg_lower):
            return build_direct_question_plan("evaluation", fen=fen, focus="who's better")
        
        # "What's the plan?" / "What should I do?"
        if re.search(r"(what.*(plan|do|play)|how.*proceed|what.*idea)", msg_lower) and not "what is a" in msg_lower:
            return build_direct_question_plan("plan", fen=fen, focus="strategic plan")
        
        # "What's wrong with my position?" / "What are the weaknesses?"
        if re.search(r"(what.*(wrong|weak|problem)|where.*weak|any.*(weakness|hole))", msg_lower):
            return build_direct_question_plan("weaknesses", fen=fen, focus="weaknesses")
        
        # "Is there a tactic?" / "Any tricks?" / "Did I miss something?"
        if re.search(r"(any|is there).*(tactic|trick|combo|combination)|miss.*(something|tactic|anything)", msg_lower):
            return build_direct_question_plan("tactics", fen=fen, focus="tactics")
        
        # "Can I checkmate?" / "Is there a mate?"
        if re.search(r"(can.*mate|is there.*mate|any.*mate|checkmate)", msg_lower):
            return build_direct_question_plan("mate", fen=fen, focus="checkmate")
        
        # "What opening is this?" / "What's this called?"
        if re.search(r"(what|which).*(opening|this called|name of)", msg_lower):
            return build_direct_question_plan("opening_name", fen=fen, focus="opening name")
        
        # "How are my pawns?" / "Is my structure ok?"
        if re.search(r"(how.*(pawn|structure)|is.*(structure|pawn).*(ok|good|bad))", msg_lower):
            return build_direct_question_plan("pawn_structure", fen=fen, focus="pawn structure")
        
        # "Should I trade?" / "Is this a good exchange?" / "Take or not?"
        if re.search(r"(should.*trade|should.*take|should.*exchange|good.*trade|good.*exchange|take.*not)", msg_lower):
            return build_direct_question_plan("trade", fen=fen, focus="trade decision")
        
        # "Is my king safe?" / "How is my king?"
        if re.search(r"(is.*king.*(safe|ok|danger)|how.*king|king.*safe)", msg_lower):
            return build_direct_question_plan("king_safety", fen=fen, focus="king safety")
        
        # "Can I win this?" / "Is this drawn?" / "Winning or drawn?"
        if re.search(r"(can.*win|is.*(drawn|draw|won|lost)|winning.*draw|draw.*win)", msg_lower):
            return build_direct_question_plan("outcome", fen=fen, focus="position outcome")
        
        # "Why was that bad?" / "What was wrong with that?"
        if re.search(r"why.*(bad|wrong|mistake|blunder)|what.*(wrong|bad).*that", msg_lower):
            last_move = context.get("last_move", {})
            move = last_move.get("move", "that move")
            return build_direct_question_plan("explain_mistake", fen=fen, focus=f"why {move} was wrong")
        
        # "Is there a fork/pin/skewer?" / "Any forks?"
        if re.search(r"(any|is there).*(fork|pin|skewer|discovered|double attack)", msg_lower):
            return build_direct_question_plan("tactics", fen=fen, focus="tactical motifs")
        
        # "Any checks?" / "Can I give check?"
        if re.search(r"(any|can.*give).*(check)", msg_lower):
            return build_direct_question_plan("checks", fen=fen, focus="checks")
        
        # "What's the evaluation?" / "What's the eval?"
        if re.search(r"what.*(eval|evaluation|assessment|score)", msg_lower):
            return build_direct_question_plan("evaluation", fen=fen, focus="evaluation")
        
        # "Am I in trouble?" / "Am I losing?" / "Am I slightly worse?"
        if re.search(r"am i.*(trouble|losing|lost|danger|bad|worse|better|winning|ahead|behind|equal)", msg_lower):
            return build_direct_question_plan("evaluation", fen=fen, focus="position assessment")
        
        # "Is this position complicated/complex/sharp?"
        if re.search(r"is.*(position|this).*(complicated|complex|sharp|tactical|quiet|calm)", msg_lower):
            return build_direct_question_plan("position_type", fen=fen, focus="position character")
        
        # "Is this endgame winning/drawn?" / "Is this won?"
        if re.search(r"is.*(endgame|this).*(winning|won|drawn|lost|holdable)", msg_lower):
            return build_direct_question_plan("outcome", fen=fen, focus="endgame assessment")
        
        # "How's my development?" / "Am I developed?"
        if re.search(r"(how.*develop|am i.*develop|is.*develop.*(ok|good|bad|behind))", msg_lower):
            return build_direct_question_plan("development", fen=fen, focus="development")
        
        # "What are my candidate moves?" / "What are my options?"
        if re.search(r"what.*(candidate|option|choice|move.*consider|possibilit)", msg_lower):
            return build_direct_question_plan("candidates", fen=fen, focus="candidate moves")
        
        # "Is the center open or closed?"
        if re.search(r"is.*(center|centre).*(open|closed)", msg_lower):
            return build_direct_question_plan("center_type", fen=fen, focus="center structure")
        
        # "Who controls more space?"
        if re.search(r"who.*(control|has).*(space|more)", msg_lower):
            return build_direct_question_plan("space", fen=fen, focus="space control")
        
        # "Can I castle?" / "Is castling possible/safe?"
        if re.search(r"(can i|is|should i).*castl", msg_lower):
            return build_direct_question_plan("castling", fen=fen, focus="castling")
        
        # "What happens if I take/play X?" / "If I go X?"
        if re.search(r"(what happen|what if|if i).*(take|play|go|push|move)", msg_lower):
            return build_direct_question_plan("what_if", fen=fen, focus="move consequences")
        
        # "Is my bishop/knight/rook good/bad/active/passive?"
        if re.search(r"is my.*(bishop|knight|rook|queen).*(good|bad|active|passive|doing|useful)", msg_lower):
            return build_direct_question_plan("piece_assessment", fen=fen, focus="piece assessment")
        
        # "Where is my knight/bishop strongest?" / "Best square for knight?"
        if re.search(r"where.*(knight|bishop|rook).*(strong|best|go)|best.*(square|place).*for.*(knight|bishop|rook)", msg_lower):
            return build_direct_question_plan("best_square", fen=fen, focus="best square for piece")
        
        # "Can I trap the piece?"
        if re.search(r"can i.*(trap|win|catch)", msg_lower):
            return build_direct_question_plan("trap", fen=fen, focus="trapping")
        
        # "How do I break through/improve?"
        if re.search(r"how.*(break|improve|make progress|breakthrough)", msg_lower):
            return build_direct_question_plan("plan", fen=fen, focus="improvement plan")
        
        # "What's the critical move?" / "Key move here?"
        if re.search(r"(what|which).*(critical|key|important|crucial).*(move|play)", msg_lower):
            return build_direct_question_plan("key_move", fen=fen, focus="critical move")
        
        # "Why is engine recommending this?"
        if re.search(r"why.*(engine|stockfish|computer).*(recommend|suggest|play|say)", msg_lower):
            return build_direct_question_plan("explain_engine", fen=fen, focus="engine recommendation")
        
        # "Should I push my pawns?"
        if re.search(r"should i.*(push|advance|move).*(pawn|a-pawn|b-pawn|c-pawn|d-pawn|e-pawn|f-pawn|g-pawn|h-pawn)", msg_lower):
            return build_direct_question_plan("pawn_push", fen=fen, focus="pawn advance")
        
        # "Where should I put my queen/knight/etc?" / "Where should my queen go?"
        if re.search(r"where.*(put|place|move|go|should).*(queen|knight|bishop|rook|king)|where.*(queen|knight|bishop|rook).*(go|belong|be)", msg_lower):
            return build_direct_question_plan("best_square", fen=fen, focus="piece placement")
        
        # "What piece should I move?" / "Which piece to develop?"
        if re.search(r"(what|which).*(piece|move).*(next|first|now|should)", msg_lower):
            return build_direct_question_plan("next_move", fen=fen, focus="which piece to move")
        
        # "Is there a back rank threat?" / "Is X a threat?"
        if re.search(r"is.*(back rank|Qh5|Qh4|Ng5|Bxh7|Nf6).*(threat|coming|dangerous)", msg_lower):
            return build_direct_question_plan("threat", fen=fen, focus="specific threat")
        
        # "Is X coming?" / "Is f5 coming?"
        if re.search(r"is\s+[a-h][1-8]?\s*(coming|planned|imminent)", msg_lower):
            return build_direct_question_plan("threat", fen=fen, focus="incoming move")
        
        # "Can I sacrifice?" / "Can I sac on X?"
        if re.search(r"can i.*(sac|sacrifice)", msg_lower):
            return build_direct_question_plan("sacrifice", fen=fen, focus="sacrifice possibility")
        
        # "Should I keep/exchange queens?" / "Keep pieces on?"
        if re.search(r"should i.*(keep|exchange|trade).*(queen|piece|rook|bishop|knight)", msg_lower):
            return build_direct_question_plan("trade", fen=fen, focus="piece exchange")
        
        # "Is X necessary?" / "Is h3 necessary?"
        if re.search(r"is\s+[A-Za-z0-9]+\s*(necessary|needed|required|important)", msg_lower):
            return build_direct_question_plan("move_necessity", fen=fen, focus="move necessity")
        
        # "Is X playable?" / "Is e5 playable?"
        if re.search(r"is\s+[A-Za-z0-9]+\s*(playable|possible|an option|viable)", msg_lower):
            return build_direct_question_plan("move_viability", fen=fen, focus="move viability")
        
        # "What's the computer/engine line?"
        if re.search(r"(what|show).*(computer|engine|stockfish).*(line|move|say|think|recommend)", msg_lower):
            return build_direct_question_plan("engine_line", fen=fen, focus="engine recommendation")
        
        # "Do I have compensation?"
        if re.search(r"(do i|is there).*(compensation|enough|activity for)", msg_lower):
            return build_direct_question_plan("compensation", fen=fen, focus="compensation assessment")
        
        # "Is this a typical X structure?" / "Is this theoretical?"
        if re.search(r"is.*(typical|theoretical|theory|standard|normal|book)", msg_lower):
            return build_direct_question_plan("theory", fen=fen, focus="theory/typical position")
        
        # "Can X equalize?" / "Can I hold?"
        if re.search(r"can.*(equalize|hold|defend|survive|draw)", msg_lower):
            return build_direct_question_plan("holdability", fen=fen, focus="defensive chances")
        
        # "Is this a fortress?"
        if re.search(r"is.*(fortress|impregnable|unbreakable)", msg_lower):
            return build_direct_question_plan("fortress", fen=fen, focus="fortress assessment")
        
        # "What are the imbalances?"
        if re.search(r"what.*(imbalance|difference|asymmetr)", msg_lower):
            return build_direct_question_plan("imbalances", fen=fen, focus="imbalances")
        
        # "Who has the initiative?" / "Is there counterplay?"
        if re.search(r"(who|is there).*(initiative|counterplay|pressure|momentum)", msg_lower):
            return build_direct_question_plan("initiative", fen=fen, focus="initiative/counterplay")
        
        # "How should I recapture?"
        if re.search(r"(how|which way|should i).*(recapture|take back|retake)", msg_lower):
            return build_direct_question_plan("recapture", fen=fen, focus="recapture direction")
        
        # "Is the X-file important?"
        if re.search(r"is.*(file|rank|diagonal).*(important|key|useful|open)", msg_lower):
            return build_direct_question_plan("file_importance", fen=fen, focus="file/rank importance")
        
        # "Should I accept the gambit/sacrifice?"
        if re.search(r"should i.*(accept|decline|take).*(gambit|sacrifice|pawn)", msg_lower):
            return build_direct_question_plan("gambit", fen=fen, focus="gambit decision")
        
        # "Is my X better than his Y?" / "Knight or bishop?"
        if re.search(r"(is my|which is better|knight or bishop|bishop or knight).*(better|stronger|prefer)", msg_lower):
            return build_direct_question_plan("piece_comparison", fen=fen, focus="piece comparison")
        
        # "Is my position worse/better now?"
        if re.search(r"is my.*(position).*(worse|better|improved|deteriorated)", msg_lower):
            return build_direct_question_plan("position_change", fen=fen, focus="position change")
        
        # "Is this pawn weak?"
        if re.search(r"is.*(this|the|my).*(pawn|square).*(weak|strong|good|bad)", msg_lower):
            return build_direct_question_plan("pawn_assessment", fen=fen, focus="pawn/square assessment")
        
        # "Should I blockade?"
        if re.search(r"should i.*(blockade|stop|block)", msg_lower):
            return build_direct_question_plan("blockade", fen=fen, focus="blockade decision")
        
        # "Where does theory end?"
        if re.search(r"where.*(theory|book).*(end|stop|finish)", msg_lower):
            return build_direct_question_plan("theory_end", fen=fen, focus="theory boundary")
        
        # "Which minor piece is stronger?" / "Which piece is better?"
        if re.search(r"which.*(piece|minor piece|major piece).*(strong|better|prefer)", msg_lower):
            return build_direct_question_plan("piece_comparison", fen=fen, focus="piece comparison")
        
        # "Should I activate my king/rook/etc?"
        if re.search(r"should i.*(activate|bring|get).*(king|rook|bishop|knight|queen|piece)", msg_lower):
            return build_direct_question_plan("activation", fen=fen, focus="piece activation")
        
        # "Is the queen/piece exposed/safe/vulnerable?"
        if re.search(r"is.*(queen|king|rook|piece).*(exposed|safe|vulnerable|secure|danger)", msg_lower):
            return build_direct_question_plan("piece_safety", fen=fen, focus="piece safety")
        
        # "Is Bb5/Nd5/c4 worth considering?" / "Should I play X?"
        if re.search(r"(is|would|should).*(worth|consider|right idea|good idea|sensible)|should i play\s+\w+", msg_lower):
            return build_direct_question_plan("move_consideration", fen=fen, focus="move consideration")
        
        # "Would X be a mistake?"
        if re.search(r"would.*(be a|be).*(mistake|error|blunder|bad)", msg_lower):
            return build_direct_question_plan("move_mistake", fen=fen, focus="move assessment")
        
        # "Is taking with the knight better?"
        if re.search(r"is.*(taking|capturing).*(with|by).*(better|worse|right)", msg_lower):
            return build_direct_question_plan("capture_choice", fen=fen, focus="capture decision")
        
        # "Is this a good pawn structure?" (handles both word orders)
        if re.search(r"(good|bad|ok|solid|weak).*(pawn structure|structure)|is.*(pawn structure).*(good|bad|ok|solid|weak)", msg_lower):
            return build_direct_question_plan("pawn_structure", fen=fen, focus="pawn structure quality")
        
        # "Do I have weak squares?"
        if re.search(r"(do i|are there|any).*(weak|strong).*(square)", msg_lower):
            return build_direct_question_plan("weak_squares", fen=fen, focus="square weaknesses")
        
        # "Is my king position solid/safe/secure?" / "Is my king solid?"
        if re.search(r"is my.*(king).*(position|placement)?.*(solid|safe|secure|ok|good)", msg_lower):
            return build_direct_question_plan("king_safety", fen=fen, focus="king position")
        
        # "Is my king too open/exposed?"
        if re.search(r"is my.*(king).*(too|very).*(open|exposed|unsafe)", msg_lower):
            return build_direct_question_plan("king_safety", fen=fen, focus="king exposure")
        
        # "Is this equal?" / "Is the position equal?"
        if re.search(r"is.*(this|position|it).*(equal|balanced|level|even)", msg_lower):
            return build_direct_question_plan("equality", fen=fen, focus="position equality")
        
        # "Is white/black much better?" / "Does white have advantage?"
        if re.search(r"is.*(white|black).*(much|slightly|clearly).*(better|worse|winning|losing)|does.*(white|black).*(have|has).*(advantage|edge)", msg_lower):
            return build_direct_question_plan("side_evaluation", fen=fen, focus="side advantage")
        
        # "How bad/good is my position?"
        if re.search(r"how.*(bad|good|terrible|great).*(is|my).*(position|situation)", msg_lower):
            return build_direct_question_plan("position_assessment", fen=fen, focus="position quality")
        
        # "What variation is this?" / "Is this the main line?"
        if re.search(r"(what|which).*(variation|line).*(is this|are we)|is this.*(main|side|popular).*(line|variation)", msg_lower):
            return build_direct_question_plan("variation", fen=fen, focus="opening variation")
        
        # "Am I out of book?" / "Is this still theory?"
        if re.search(r"(am i|are we).*(out of|still in).*(book|theory)|is this.*(still).*(book|theory)", msg_lower):
            return build_direct_question_plan("book_status", fen=fen, focus="book/theory status")
        
        # "Can I convert this?"
        if re.search(r"can i.*(convert|win from here|finish|close out)", msg_lower):
            return build_direct_question_plan("conversion", fen=fen, focus="conversion")
        
        # "Should I simplify/complicate/attack/defend/wait?"
        if re.search(r"should i.*(simplify|complicate|attack|defend|wait|be patient|go aggressive|stay solid)", msg_lower):
            return build_direct_question_plan("strategy_choice", fen=fen, focus="strategic decision")
        
        # "Is it time to attack/defend?"
        if re.search(r"is it.*(time|right).*(to|for).*(attack|defend|push|wait|strike)", msg_lower):
            return build_direct_question_plan("timing", fen=fen, focus="timing")
        
        # "Is X a strong square?" / "Is e5 an outpost?"
        if re.search(r"is\s+[a-h][1-8]\s*(a|an)?.*(strong|weak|good|outpost|key)", msg_lower):
            return build_direct_question_plan("square_quality", fen=fen, focus="square quality")
        
        # "Is f7/h7/etc vulnerable?"
        if re.search(r"is\s+[a-h][1-8]\s*(vulnerable|weak|target|attackable)", msg_lower):
            return build_direct_question_plan("square_vulnerability", fen=fen, focus="square vulnerability")
        
        # "Should I create a passed pawn?"
        if re.search(r"should i.*(create|make|get|push for).*(passed|passer)", msg_lower):
            return build_direct_question_plan("passed_pawn", fen=fen, focus="passed pawn creation")
        
        # "Is my pawn majority useful?"
        if re.search(r"is.*(my|the).*(pawn majority|majority|queenside|kingside).*(useful|relevant|winning|important)", msg_lower):
            return build_direct_question_plan("pawn_majority", fen=fen, focus="pawn majority")
        
        # "Are my pawns overextended?"
        if re.search(r"are.*(my|the)?.*(pawn).*(overextended|too far|weak|exposed)", msg_lower):
            return build_direct_question_plan("pawn_extension", fen=fen, focus="pawn extension")
        
        # "Is this pawn push committal?"
        if re.search(r"is.*(this|the).*(pawn|push|move).*(committal|permanent|irreversible)", msg_lower):
            return build_direct_question_plan("move_committal", fen=fen, focus="move permanence")
        
        # "Can I advance my pawns safely?"
        if re.search(r"can i.*(advance|push|move).*(pawn|my).*(safely|without)", msg_lower):
            return build_direct_question_plan("pawn_safety", fen=fen, focus="pawn advance safety")
        
        # "Should I keep my king in the center?"
        if re.search(r"should.*(keep|leave).*(king|my).*(center|centre|middle)", msg_lower):
            return build_direct_question_plan("king_placement", fen=fen, focus="king placement")
        
        # "Is this the top/best engine move?"
        if re.search(r"is.*(this|that).*(top|best|first|number one).*(engine|computer|stockfish).*(move|choice)", msg_lower):
            return build_direct_question_plan("engine_top", fen=fen, focus="engine top choice")
        
        # "Why does stockfish like this?"
        if re.search(r"why.*(does|is).*(stockfish|engine|computer).*(like|prefer|choose|recommend|play)", msg_lower):
            return build_direct_question_plan("explain_engine", fen=fen, focus="engine preference")
        
        # "Is there a better alternative?" / "Is there another option?"
        if re.search(r"is there.*(better|another|alternative|different)", msg_lower):
            return build_direct_question_plan("alternatives", fen=fen, focus="alternatives")
        
        # "Can my opponent save/hold this?"
        if re.search(r"can.*(my opponent|opponent|they|he|she).*(save|hold|defend|survive|escape)", msg_lower):
            return build_direct_question_plan("opponent_chances", fen=fen, focus="opponent chances")
        
        # "Is my opponent in trouble?"
        if re.search(r"is.*(my opponent|opponent|black|white).*(in trouble|losing|worse|struggling)", msg_lower):
            return build_direct_question_plan("opponent_assessment", fen=fen, focus="opponent situation")
        
        # "Is this a tempo move?"
        if re.search(r"is.*(this|that).*(tempo|developing|useful).*(move|gain)", msg_lower):
            return build_direct_question_plan("tempo", fen=fen, focus="tempo")
        
        # "Is there zugzwang?"
        if re.search(r"is.*(there|this).*(zugzwang|zug)", msg_lower):
            return build_direct_question_plan("zugzwang", fen=fen, focus="zugzwang")
        
        # "Is this a critical position?"
        if re.search(r"is.*(this|the).*(critical|crucial|key|important|decisive).*(position|moment|point)", msg_lower):
            return build_direct_question_plan("critical_moment", fen=fen, focus="critical moment")
        
        # "What are the key factors?"
        if re.search(r"what.*(are|is).*(key|main|important|critical).*(factor|element|consideration|thing)", msg_lower):
            return build_direct_question_plan("key_factors", fen=fen, focus="key factors")
        
        # "Is time a factor?" / "Does time matter?"
        if re.search(r"(is|does).*(time|clock|tempo).*(factor|matter|important|relevant)", msg_lower):
            return build_direct_question_plan("time_factor", fen=fen, focus="time factor")
        
        # ================================================================
        # GENERAL FLEXIBLE PATTERNS (catch-all for common question forms)
        # ================================================================
        
        # "Any X?" - hanging pieces, checks, tactics, threats, etc.
        if re.search(r"^any\s+\w+", msg_lower):
            return build_direct_question_plan("general_any", fen=fen, focus="any question")
        
        # "Is my X trapped/stuck/blocked/bad/restricted?"
        if re.search(r"is.*(my|the).*(trapped|stuck|blocked|restricted|bad|useless|passive)", msg_lower):
            return build_direct_question_plan("piece_problem", fen=fen, focus="piece problem")
        
        # "Can I X?" where X is a chess action
        if re.search(r"can i\s+(infiltrate|exploit|coordinate|target|break|create|force|simplify|overload|grab|prevent|double|occupy|open|close)", msg_lower):
            return build_direct_question_plan("can_i_action", fen=fen, focus="action possibility")
        
        # "Should I X?" where X is a chess action  
        if re.search(r"should i\s+(double|occupy|centralize|open|close|grab|prevent|keep|release|maintain)", msg_lower):
            return build_direct_question_plan("should_i_action", fen=fen, focus="action decision")
        
        # "Is the X important/useful/relevant/good?" - general feature questions
        if re.search(r"is.*(the|this|my).*(important|useful|relevant|good|necessary|worth)", msg_lower):
            return build_direct_question_plan("feature_importance", fen=fen, focus="feature importance")
        
        # "Is the position X?" - locked, open, closed, dynamic, etc.
        if re.search(r"is.*(the\s+)?position\s+(locked|open|closed|dynamic|static|fluid|solid|loose)", msg_lower):
            return build_direct_question_plan("position_type", fen=fen, focus="position character")
        
        # "Is there a X?" - perpetual, breakthrough, resource, etc.
        if re.search(r"is there\s+(a\s+)?(perpetual|breakthrough|resource|zwischenzug|intermezzo|in-between)", msg_lower):
            return build_direct_question_plan("tactical_resource", fen=fen, focus="tactical resource")
        
        # "Is this/that/the move X?" - forcing, strong, best, etc.
        if re.search(r"is\s+(this|that|the)\s+(move\s+)?(forcing|strong|best|correct|right|winning|losing|good|bad)", msg_lower):
            return build_direct_question_plan("move_quality", fen=fen, focus="move quality")
        
        # "Is X weak/strong?" for squares, colors, pawns
        if re.search(r"is.*(the\s+)?(light|dark)\s+squares?\s+(weak|strong)|are.*(squares?|colors?)\s+(weak|strong)", msg_lower):
            return build_direct_question_plan("color_complex", fen=fen, focus="color complex")
        
        # "Can I improve X?"
        if re.search(r"can i\s+(improve|activate|develop|reposition)", msg_lower):
            return build_direct_question_plan("improvement", fen=fen, focus="improvement")
        
        # "Is my X active/good/fast enough?"
        if re.search(r"is.*(my|the).*(active|fast|quick|good|strong)\s+enough", msg_lower):
            return build_direct_question_plan("sufficiency", fen=fen, focus="sufficiency")
        
        # General "Is X the move?" pattern for specific moves (e.g., "Is Rc1 the move?")
        if re.search(r"is\s+\w{2,5}\s+the\s+(move|right|best|correct)", msg_lower):
            return build_direct_question_plan("specific_move", fen=fen, focus="specific move")
        
        # "Is there pressure/tension?"
        if re.search(r"is there\s+(pressure|tension|danger|stress)", msg_lower):
            return build_direct_question_plan("position_pressure", fen=fen, focus="pressure")
        
        # "Do I need to X?" - defend, attack, react, etc.
        if re.search(r"do i\s+(need|have)\s+to", msg_lower):
            return build_direct_question_plan("necessity", fen=fen, focus="necessity")
        
        # "Is this/the X forced/forcing?"
        if re.search(r"is.*(this|the|a).*(forced|forcing|only move|necessary move)", msg_lower):
            return build_direct_question_plan("forcing", fen=fen, focus="forcing nature")
        
        # "Is X contestable/accessible?"
        if re.search(r"is.*(contestable|accessible|available|usable|reachable)", msg_lower):
            return build_direct_question_plan("accessibility", fen=fen, focus="accessibility")
        
        # "Is there a defensive X?"
        if re.search(r"is there\s+(a\s+)?defensive", msg_lower):
            return build_direct_question_plan("defensive_resource", fen=fen, focus="defense")
        
        # "Is the X stronger here?" for pieces
        if re.search(r"is.*(the|my).*(knight|bishop|rook|queen|king).*(stronger|better|more useful|more active)", msg_lower):
            return build_direct_question_plan("piece_comparison", fen=fen, focus="piece comparison")
        
        # "Should I play X-ly?" for adverbs (prophylactically, aggressively, etc.)
        if re.search(r"should i\s+play\s+\w+(ly|ically)", msg_lower):
            return build_direct_question_plan("play_style", fen=fen, focus="play style")
        
        # "Is the position holdable/tenable?"
        if re.search(r"is.*(position|this).*(holdable|tenable|defensible|drawable|saveable)", msg_lower):
            return build_direct_question_plan("holdability", fen=fen, focus="holdability")
        
        # "Is there a back rank threat?" / "Is X a threat?"
        if re.search(r"is.*(there\s+)?a?\s*(back rank|discovered|mate|serious|immediate)?\s*threat", msg_lower):
            return build_direct_question_plan("threat", fen=fen, focus="threat")
        
        # "Is X coming?" - asking about imminent moves
        if re.search(r"is\s+\w+\s+(coming|imminent|threatened|planned)", msg_lower):
            return build_direct_question_plan("imminent_move", fen=fen, focus="imminent move")
        
        # "Is Qh5/Nf3/etc a threat?" - specific move as threat
        if re.search(r"is\s+[kqrbnpKQRBNP]?[a-h][1-8]\s+a\s+threat", msg_lower, re.IGNORECASE):
            return build_direct_question_plan("move_threat", fen=fen, focus="move threat")
        
        # ================================================================
        # SIMPLE CHAT - Theory questions
        # ================================================================
        simple_chat_patterns = [
            r"what is a?\s+",
            r"explain\s+",
            r"how does\s+",
            r"why is\s+",
            r"tell me about\s+",
        ]
        
        for pattern in simple_chat_patterns:
            if re.match(pattern, msg_lower):
                plan = build_chat_plan(simple=True)
                plan.user_intent_summary = "Chess concept explanation"
                return plan
        
        # ================================================================
        # No quick match - return None for LLM interpretation
        # ================================================================
        return None
    
    async def _llm_interpret(
        self,
        message: str,
        context: Dict[str, Any],
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> OrchestrationPlan:
        """
        Use LLM as PRIMARY interpreter for natural language understanding.
        This handles ALL request interpretation - no pattern matching needed.
        """
        try:
            # Build rich context summary
            context_summary = self._build_context_summary(context)
            print(f"   📋 Context summary:\n{context_summary}")
            
            # Build conversation context (expanded window)
            history_summary = ""
            if conversation_history and len(conversation_history) > 0:
                recent = conversation_history[-10:]  # Last 10 messages for better context
                history_summary = "\n".join([
                    f"{m['role'].upper()}: {m['content'][:500]}..." if len(m.get('content', '')) > 500 else f"{m['role'].upper()}: {m['content']}"
                    for m in recent if m.get('content')
                ])
            
            # Enhanced user prompt with more context
            user_prompt = f"""Analyze this chess assistant request:

USER MESSAGE: "{message}"

CURRENT CONTEXT:
{context_summary}

CONVERSATION HISTORY:
{history_summary if history_summary else "No prior messages"}

Interpret the user's intent and generate the orchestration plan JSON.
Consider:
1. What is the user REALLY asking for? (not just keywords)
2. What analysis/tools would best answer their question?
3. How should the response be structured and styled?
4. Should the answer be direct (yes/no) or detailed?

Output ONLY valid JSON:"""
            
            system_prompt = (
                INTERPRETER_SYSTEM_PROMPT_COMPACT 
                if self.use_compact_prompt 
                else INTERPRETER_SYSTEM_PROMPT
            )
            
            # gpt-5 models don't support custom temperature, only default (1.0)
            llm_kwargs = {
                "model": self.model,  # Configurable model (default: gpt-4o for reliability)
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
            }
            # GPT-5 models require max_completion_tokens instead of max_tokens
            if self.model.startswith("gpt-5"):
                llm_kwargs["max_completion_tokens"] = 1500
            else:
                llm_kwargs["max_tokens"] = 1500
                llm_kwargs["temperature"] = 0.3  # Slightly higher for more natural understanding
            
            response = self.client.chat.completions.create(**llm_kwargs)
            
            plan_text = response.choices[0].message.content.strip()
            
            # Parse JSON
            plan_json = self._extract_json(plan_text)
            
            if plan_json:
                try:
                    plan = OrchestrationPlan.from_dict(plan_json)
                except Exception as parse_error:
                    print(f"   ⚠️ Failed to parse plan structure: {parse_error}")
                    return self._build_clarification_plan(message, "Had trouble understanding that request")
                
                # Validate understanding confidence - force clarification if low but not set
                plan = self._validate_confidence(plan, message, context)
                
                # Log the interpretation with full tool details
                guidelines_summary = ""
                if plan.response_guidelines:
                    rg = plan.response_guidelines
                    flags = []
                    if rg.direct_answer:
                        flags.append("direct")
                    if rg.skip_advice:
                        flags.append("no-advice")
                    if plan.needs_clarification:
                        flags.append("needs-clarification")
                    guidelines_summary = f" [{', '.join(flags)}]" if flags else ""
                
                confidence_str = f" (confidence: {plan.understanding_confidence:.1%})"
                print(f"   🤖 LLM: {plan.mode.value} mode, {len(plan.tool_sequence)} tools{guidelines_summary}{confidence_str}")
                print(f"      Intent: {plan.user_intent_summary or 'Not specified'}")
                
                if plan.needs_clarification:
                    print(f"      ❓ Clarification: {plan.clarification_question[:100]}...")
                
                # Log tool sequence details
                if plan.tool_sequence:
                    for t in plan.tool_sequence:
                        print(f"      Tool: {t.name} args={t.arguments}")
                
                return plan
            else:
                print(f"   ⚠️ Failed to parse interpreter response:")
                print(f"      Raw: {plan_text[:500]}...")
                # Ask for clarification instead of guessing
                return self._build_clarification_plan(message, "I couldn't parse the request properly")
        
        except Exception as e:
            print(f"   ❌ Interpreter error: {e}")
            import traceback
            traceback.print_exc()
            # Ask for clarification instead of guessing
            return self._build_clarification_plan(message, f"Error during interpretation: {e}")
    
    async def interpret_single_pass(
        self,
        message: str,
        context: Dict[str, Any],
        data_summary: str = "",
        is_multi_pass: bool = False
    ):
        """
        Run a single interpreter pass for multi-pass mode.
        Returns an InterpreterOutput that either has actions to execute or is_ready with final_plan.
        
        This method is called by InterpreterLoop.
        """
        from dataclasses import dataclass
        from typing import Any
        
        @dataclass
        class SinglePassResponse:
            raw_json: dict
            tokens_used: dict
        
        try:
            # Build context summary
            context_summary = self._build_context_summary(context)
            
            # Build user prompt with multi-pass awareness
            investigation_status = ""
            if context.get('investigation_plan'):
                plan = context['investigation_plan']
                completed = len(context.get('completed_steps', []))
                total = len(plan.get('steps', []))
                investigation_status = f"""
INVESTIGATION PLAN STATUS:
- Plan ID: {plan.get('plan_id', 'N/A')}
- Question: {plan.get('question', 'N/A')}
- Steps completed: {completed}/{total}
- Completed step IDs: {context.get('completed_steps', [])}
"""
            
            # Extract FEN from context for move testing
            accumulated_data = context.get("accumulated_data") or {}
            current_fen = context.get('fen') or context.get('board_state')
            if not current_fen and accumulated_data:
                # Try to get FEN from accumulated analysis results
                for key, value in accumulated_data.items():
                    if isinstance(value, dict) and value.get('fen'):
                        current_fen = value['fen']
                        break
            
            fen_info = f"\nCURRENT FEN: {current_fen}" if current_fen else "\nCURRENT FEN: Not available (check context)"
            
            user_prompt = f"""Analyze this chess assistant request (MULTI-PASS MODE):

USER MESSAGE: "{message}"

CURRENT CONTEXT:
{context_summary}

ACCUMULATED DATA FROM PREVIOUS PASSES:
{data_summary if data_summary else "No data accumulated yet"}

PREVIOUS PASSES INFO:
Pass count: {context.get('pass_count', 0)}
Insights so far: {context.get('insights_so_far', [])}
{investigation_status}

CRITICAL INSTRUCTIONS FOR POSITION QUESTIONS:

If you have analysis results with candidate moves but NO test_move actions yet:
1. Extract top 3-5 candidate moves from the analysis results
2. Create test_move actions for EACH candidate move:
   {{
     "action_type": "test_move",
     "params": {{
       "fen": "{current_fen or '<get_from_context_or_accumulated_data>'}",
       "move_san": "<candidate_move>",
       "follow_pv": true,
       "depth": 12
     }},
     "reasoning": "Test if <move> works, check consequences like doubled pawns, pins, material changes"
   }}
3. DO NOT set is_ready: true until move tests are complete

For "what should I do" / "how should I progress" questions:
- Pass 1: analyze → get candidates
- Pass 2: test_move for each candidate → verify consequences  
- Pass 3: synthesize → set is_ready: true

Available Actions:
- ANALYZE: Get position analysis with candidate moves
- TEST_MOVE: Test a specific move and check consequences (REQUIRED after analyze for position questions)
- EXAMINE_PV: See what the engine's PV suggests
- CHECK_CONSEQUENCE: Check specific consequence (doubled_pawns, pins, captures)
- FETCH: Get games from platforms
- SEARCH: Web search
- COMPUTE: Statistics

If you need more data (is_ready: false):
- Request actions above

If ready (after move testing is complete):
- Provide complete final_plan with mode, tools, guidelines
- Include investigation_summary linking tested moves to recommendations

Output ONLY valid JSON:"""
            
            # Use multi-pass prompt addition
            system_prompt = (
                INTERPRETER_SYSTEM_PROMPT_COMPACT 
                if self.use_compact_prompt 
                else INTERPRETER_SYSTEM_PROMPT
            )
            system_prompt += MULTI_PASS_PROMPT_ADDITION
            
            # Add message decomposition section for complex questions
            from interpreter_prompt import MESSAGE_DECOMPOSITION_SECTION
            system_prompt += MESSAGE_DECOMPOSITION_SECTION
            
            # gpt-5 models don't support custom temperature, only default (1.0)
            llm_kwargs = {
                "model": self.model,  # Configurable model (default: gpt-4o for reliability)
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "max_tokens": 1200
            }
            if not self.model.startswith("gpt-5"):
                llm_kwargs["temperature"] = 0.3
            
            response = self.client.chat.completions.create(**llm_kwargs)
            
            plan_text = response.choices[0].message.content.strip()
            plan_json = self._extract_json(plan_text)
            
            tokens_used = {
                "input": response.usage.prompt_tokens if response.usage else 0,
                "output": response.usage.completion_tokens if response.usage else 0
            }
            
            if not plan_json:
                plan_json = {"is_ready": False, "actions": [], "insights": []}
            
            # Parse message_decomposition and investigation_plan if present
            if "message_decomposition" in plan_json and plan_json["message_decomposition"]:
                from orchestration_plan import MessageDecomposition
                try:
                    plan_json["message_decomposition"] = MessageDecomposition.from_dict(
                        plan_json["message_decomposition"]
                    ).to_dict()  # Convert back to dict for JSON serialization
                except Exception as e:
                    print(f"   ⚠️ Failed to parse message_decomposition: {e}")
            
            if "investigation_plan" in plan_json and plan_json["investigation_plan"]:
                from orchestration_plan import InvestigationPlan
                try:
                    plan_json["investigation_plan"] = InvestigationPlan.from_dict(
                        plan_json["investigation_plan"]
                    ).to_dict()  # Convert back to dict for JSON serialization
                except Exception as e:
                    print(f"   ⚠️ Failed to parse investigation_plan: {e}")
            
            return SinglePassResponse(raw_json=plan_json, tokens_used=tokens_used)
            
        except Exception as e:
            print(f"   ❌ Single pass error: {e}")
            import traceback
            traceback.print_exc()
            # Return ready with fallback plan on error
            return SinglePassResponse(
                raw_json={
                    "is_ready": True,
                    "final_plan": {
                        "mode": "chat",
                        "mode_confidence": 0.5,
                        "user_intent_summary": message,
                        "system_prompt_additions": f"Error during interpretation: {e}"
                    }
                },
                tokens_used={"input": 0, "output": 0}
            )
    
    async def interpret_with_loop(
        self,
        message: str,
        context: Dict[str, Any],
        status_callback = None,
        cancel_token = None
    ) -> OrchestrationPlan:
        """
        Interpret using multi-pass loop if enabled.
        Falls back to single-pass if loop not available.
        """
        if self._interpreter_loop:
            try:
                return await self._interpreter_loop.run(
                    message=message,
                    context=context,
                    status_callback=status_callback,
                    cancel_token=cancel_token
                )
            except Exception as e:
                print(f"   ⚠️ Interpreter loop failed, falling back: {e}")
        
        # Fall back to standard interpretation
        return await self._llm_interpret(message, context)
    
    def _build_context_summary(self, context: Dict[str, Any]) -> str:
        """Build a rich context summary for the interpreter"""
        parts = []
        
        # Connected accounts (Chess.com/Lichess) - IMPORTANT for game fetching
        connected_accounts = context.get("connected_accounts", [])
        if connected_accounts:
            accounts_str = ", ".join([f"{a['platform']}: {a['username']}" for a in connected_accounts])
            parts.append(f"Connected accounts: {accounts_str}")
        else:
            parts.append("No connected accounts (user needs to provide username or connect via Personal tab)")
        
        if context.get("fen") or context.get("board_state"):
            fen = context.get("board_state") or context.get("fen")
            # Check if it's the starting position
            starting_fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
            if fen == starting_fen or (fen and fen.startswith("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR")):
                parts.append("Board: Starting position (no game in progress)")
            else:
                parts.append(f"Current FEN: {fen}")
        
        if context.get("mode"):
            parts.append(f"Current mode: {context['mode']}")
        
        # AI Game mode context
        if context.get("aiGameActive"):
            parts.append("AI Game: ACTIVE (user is playing against AI)")
        
        if context.get("pgn"):
            pgn_preview = context["pgn"][:200] + "..." if len(context["pgn"]) > 200 else context["pgn"]
            parts.append(f"PGN loaded: {pgn_preview}")
        elif not context.get("pgn") or context.get("pgn") == "":
            parts.append("No PGN loaded")
        
        if context.get("last_move"):
            lm = context["last_move"]
            parts.append(f"Last move: {lm.get('move')} (fen_before available: {bool(lm.get('fen_before'))})")
        
        if context.get("cached_analysis"):
            parts.append("Cached analysis available from previous queries")
        
        if context.get("username"):
            parts.append(f"Saved username: {context['username']}")
        
        if context.get("platform"):
            parts.append(f"Saved platform: {context['platform']}")
        
        # Add game review tab info if present
        if context.get("gameReviewTabOpen"):
            parts.append("Game Review tab is open (user may be viewing a game)")
        
        # Add recent tool results if available
        if context.get("last_tool_result"):
            parts.append(f"Last tool used: {context.get('last_tool_result', {}).get('tool_name', 'unknown')}")
        
        return "\n".join(parts) if parts else "No context available"
    
    def _validate_confidence(self, plan: OrchestrationPlan, message: str, context: Dict[str, Any]) -> OrchestrationPlan:
        """
        Validate that the interpreter's confidence matches its actions.
        If confidence is low but no clarification was requested, force it.
        """
        CONFIDENCE_THRESHOLD = 0.7
        
        # If interpreter said low confidence but didn't ask for clarification, fix that
        if plan.understanding_confidence < CONFIDENCE_THRESHOLD and not plan.needs_clarification:
            print(f"   ⚠️ Low confidence ({plan.understanding_confidence:.1%}) but no clarification - forcing clarification")
            
            # Build a clarification question based on the intent summary
            best_guess = plan.user_intent_summary or "what you're looking for"
            
            # Check if connected accounts might be relevant
            connected_accounts = context.get("connected_accounts", [])
            account_hint = ""
            if connected_accounts:
                acc = connected_accounts[0]
                account_hint = f" (I see you have {acc.get('username')} connected on {acc.get('platform', 'chess.com')})"
            
            plan.needs_clarification = True
            plan.clarification_question = (
                f"I want to make sure I understand correctly. "
                f"I think you might want: {best_guess}{account_hint}. "
                f"Is that right? Just say 'yes' to confirm, or tell me what you'd actually like to do."
            )
            plan.skip_tools = True
            plan.tool_sequence = []
        
        # If confidence is high and has tools, we're good
        # If confidence is high but no tools and not a simple chat, might be a miss
        # (But we trust high confidence for now)
        
        return plan
    
    def _build_clarification_plan(self, original_message: str, reason: str = "") -> OrchestrationPlan:
        """Build a plan that asks for clarification instead of guessing"""
        # Generate helpful examples based on common intents
        examples = []
        msg_lower = original_message.lower()
        
        if "review" in msg_lower or "game" in msg_lower:
            examples.append("'review my last Chess.com game'")
            examples.append("'analyze this position'")
        elif "analyze" in msg_lower or "position" in msg_lower:
            examples.append("'what's the best move here?'")
            examples.append("'explain this position'")
        elif "play" in msg_lower or "move" in msg_lower:
            examples.append("'let's play a game'")
            examples.append("'what should I play?'")
        else:
            examples.append("'analyze my last game'")
            examples.append("'explain the Sicilian Defense'")
        
        clarification = (
            f"I want to make sure I help you with the right thing! "
            f"Could you clarify what you'd like? For example, you could say {examples[0]} or {examples[1]}."
        )
        
        plan = build_chat_plan(simple=True)
        plan.needs_clarification = True
        plan.clarification_question = clarification
        plan.user_intent_summary = f"Needs clarification ({reason})" if reason else "Needs clarification"
        plan.skip_tools = True
        
        return plan
    
    def _extract_json(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Extract JSON from LLM response.

        The interpreter prompt requests "ONLY valid JSON", but models sometimes return:
        - Markdown fences (```json ... ```)
        - Leading/trailing commentary
        - Multiple JSON objects
        - Trailing commas

        This function is intentionally defensive to avoid unnecessary clarification fallbacks.
        """
        if not text:
            return None

        def _strip_code_fences(s: str) -> str:
            s = s.strip()
            if "```" not in s:
                return s
            # Prefer ```json fenced block if present
            if "```json" in s:
                try:
                    return s.split("```json", 1)[1].split("```", 1)[0].strip()
                except Exception:
                    return s.strip()
            # Otherwise take the first fenced block content
            try:
                return s.split("```", 1)[1].split("```", 1)[0].strip()
            except Exception:
                return s.strip()

        def _find_first_json_span(s: str) -> Optional[str]:
            # Find first '{' or '[' and return the smallest balanced JSON substring.
            start_obj = s.find("{")
            start_arr = s.find("[")
            if start_obj == -1 and start_arr == -1:
                return None
            if start_obj == -1:
                start = start_arr
                open_ch, close_ch = "[", "]"
            elif start_arr == -1:
                start = start_obj
                open_ch, close_ch = "{", "}"
            else:
                start = min(start_obj, start_arr)
                open_ch, close_ch = ("{", "}") if start == start_obj else ("[", "]")

            depth = 0
            in_str = False
            esc = False
            for i in range(start, len(s)):
                ch = s[i]
                if in_str:
                    if esc:
                        esc = False
                        continue
                    if ch == "\\":
                        esc = True
                        continue
                    if ch == "\"":
                        in_str = False
                        continue
                    continue
                else:
                    if ch == "\"":
                        in_str = True
                        continue
                    if ch == open_ch:
                        depth += 1
                    elif ch == close_ch:
                        depth -= 1
                        if depth == 0:
                            return s[start : i + 1]
            return None

        def _try_load(s: str) -> Optional[Dict[str, Any]]:
            try:
                loaded = json.loads(s)
                return loaded if isinstance(loaded, dict) else None
            except Exception:
                return None

        # 1) Direct parse
        direct = _try_load(text.strip())
        if direct is not None:
            return direct

        # 2) Strip fences and retry
        stripped = _strip_code_fences(text)
        direct2 = _try_load(stripped)
        if direct2 is not None:
            return direct2

        # 3) Extract balanced JSON substring and retry (from stripped + original)
        for candidate_source in (stripped, text):
            span = _find_first_json_span(candidate_source)
            if not span:
                continue
            parsed = _try_load(span)
            if parsed is not None:
                return parsed

            # 4) Common cleanup: trailing commas before } or ]
            try:
                cleaned = re.sub(r",\s*([}\]])", r"\1", span)
                parsed2 = _try_load(cleaned)
                if parsed2 is not None:
                    return parsed2
            except Exception:
                pass

        return None
    
    def _extract_username_platform(
        self,
        message: str,
        context: Dict[str, Any]
    ) -> tuple[Optional[str], Optional[str]]:
        """Extract username and platform from message or context"""
        
        # Check context first
        username = context.get("username")
        platform = context.get("platform")
        
        msg_lower = message.lower()
        
        # Platform detection
        if not platform:
            if any(p in msg_lower for p in ["chess.com", "chess com", "chesscom"]):
                platform = "chess.com"
            elif any(p in msg_lower for p in ["lichess", "lichess.org"]):
                platform = "lichess"
        
        # Username patterns
        if not username:
            # "username on platform" pattern
            patterns = [
                r"(\w+)\s+on\s+(?:chess\.?com|lichess)",
                r"username\s+(?:is\s+)?(\w+)",
                r"(?:my|the)\s+(?:username|profile)\s+(?:is\s+)?(\w+)",
                r"check\s+(\w+)\s+(?:on\s+)?(?:chess\.?com|lichess)?",
            ]
            
            for pattern in patterns:
                match = re.search(pattern, message, re.IGNORECASE)
                if match:
                    potential_username = match.group(1)
                    # Filter out common words
                    if potential_username.lower() not in ["my", "the", "is", "on", "at", "profile"]:
                        username = potential_username
                        break
        
        return username, platform
    
    def _extract_training_focus(self, message: str) -> str:
        """Extract training focus area from message"""
        msg_lower = message.lower()
        
        focus_keywords = {
            "tactics": ["tactics", "tactical", "combinations", "calculation"],
            "endgames": ["endgame", "endgames", "endings"],
            "openings": ["opening", "openings"],
            "middlegame": ["middlegame", "middle game"],
            "positional": ["positional", "strategic", "strategy"],
            "attacking": ["attacking", "attack", "kingside attack"],
            "defending": ["defending", "defense", "defensive"],
            "pawn structure": ["pawn structure", "pawns"],
        }
        
        for focus, keywords in focus_keywords.items():
            if any(kw in msg_lower for kw in keywords):
                return focus
        
        # Default
        return "general improvement"


# ============================================================================
# Pre-analysis execution
# ============================================================================

async def execute_analysis_requests(
    analysis_requests: List[AnalysisRequest],
    engine_queue,
    status_callback=None
) -> Dict[str, Any]:
    """
    Pre-execute analysis requests before the main LLM call.
    Returns results keyed by FEN.
    
    Args:
        analysis_requests: List of AnalysisRequest objects
        engine_queue: Stockfish queue
        status_callback: Optional callback for status updates
    """
    results = {}
    
    for request in analysis_requests:
        try:
            import chess
            import chess.engine
            
            board = chess.Board(request.fen)
            result_key = f"{request.fen}:{request.move}" if request.move else request.fen
            
            if request.move:
                # Analyze specific move
                if status_callback:
                    status_callback("analyzing", f"Calculating move quality for {request.move}")
                
                move = board.parse_san(request.move)
                
                # Get analysis before move (multi-PV for alternates)
                lines_count = max(request.lines, 5) if request.include_alternates else request.lines
                info_before = await engine_queue.enqueue(
                    engine_queue.engine.analyse,
                    board,
                    chess.engine.Limit(depth=request.depth),
                    multipv=lines_count
                )
                
                # Get best move and alternatives
                best_move = info_before[0]["pv"][0]
                best_san = board.san(best_move)
                
                # Get eval before
                score = info_before[0]["score"].white()
                eval_before = score.score(mate_score=10000) if not score.is_mate() else (
                    10000 if score.mate() > 0 else -10000
                )
                
                # Build alternates list with rankings
                alternates = []
                for rank, line in enumerate(info_before, 1):
                    if line.get("pv"):
                        try:
                            pv_move = line["pv"][0]
                            # Validate move is legal before converting to SAN
                            if pv_move in board.legal_moves:
                                alt_san = board.san(pv_move)
                                alt_score = line["score"].white()
                                alt_eval = alt_score.score(mate_score=10000) if not alt_score.is_mate() else (
                                    10000 if alt_score.mate() > 0 else -10000
                                )
                                
                                # Build PV if requested
                                pv_san = None
                                if request.include_pv_analysis:
                                    pv_san = []
                                    temp_board = board.copy()
                                    for pv_m in line["pv"][:5]:
                                        if pv_m in temp_board.legal_moves:
                                            pv_san.append(temp_board.san(pv_m))
                                            temp_board.push(pv_m)
                                        else:
                                            break
                                
                                alternates.append({
                                    "move": alt_san,
                                    "eval_cp": alt_eval,
                                    "preference_rank": rank,
                                    "pv": pv_san
                                })
                        except Exception as e:
                            print(f"      ⚠️ Error parsing alternate move: {e}")
                
                # Find rank of played move
                played_rank = next(
                    (a["preference_rank"] for a in alternates if a["move"] == request.move),
                    len(alternates) + 1
                )
                
                # Calculate CP loss
                played_eval = next(
                    (a["eval_cp"] for a in alternates if a["move"] == request.move),
                    None
                )
                if played_eval is None:
                    # Move not in top candidates, analyze it directly
                    board_copy = board.copy()
                    board_copy.push(move)
                    info_after = await engine_queue.enqueue(
                        engine_queue.engine.analyse,
                        board_copy,
                        chess.engine.Limit(depth=request.depth)
                    )
                    after_score = info_after["score"].white()
                    played_eval = after_score.score(mate_score=10000) if not after_score.is_mate() else (
                        10000 if after_score.mate() > 0 else -10000
                    )
                    played_rank = lines_count + 1
                
                cp_loss = abs(eval_before - played_eval) if board.turn else abs(played_eval - eval_before)
                
                # Determine word rating
                if cp_loss < 10:
                    word_rating = "excellent"
                elif cp_loss < 25:
                    word_rating = "good"
                elif cp_loss < 50:
                    word_rating = "inaccuracy"
                elif cp_loss < 100:
                    word_rating = "mistake"
                elif cp_loss < 200:
                    word_rating = "blunder"
                else:
                    word_rating = "severe_blunder"
                
                results[result_key] = {
                    "move_analyzed": request.move,
                    "best_move": best_san,
                    "is_best": request.move == best_san,
                    "eval_before": eval_before,
                    "eval_after": played_eval,
                    "cp_loss": cp_loss,
                    "preference_rank": played_rank,
                    "word_rating": word_rating,
                    "depth": request.depth,
                    "alternates": alternates if request.include_alternates else alternates[:3]
                }
                
                # Add piece profiles if requested
                if request.include_piece_profiles:
                    if status_callback:
                        status_callback("profiling", "Building piece profiles")
                    try:
                        from piece_profiler import build_piece_profiles, get_profile_summary
                        
                        # Build profiles using existing tags from analysis (no separate tag call needed)
                        # Pass None for nnue_dump and tags - profiler will handle it
                        profiles_before = await build_piece_profiles(request.fen, nnue_dump=None, tags=None)
                        
                        results[result_key]["piece_profiles_before"] = profiles_before
                        results[result_key]["profile_summary_before"] = get_profile_summary(profiles_before)
                        
                        # If compare before/after, also get profiles after
                        if request.compare_before_after:
                            if status_callback:
                                status_callback("comparing", "Comparing before/after profiles")
                            board_after = board.copy()
                            board_after.push(move)
                            fen_after = board_after.fen()
                            
                            profiles_after = await build_piece_profiles(fen_after, nnue_dump=None, tags=None)
                            
                            results[result_key]["piece_profiles_after"] = profiles_after
                            results[result_key]["profile_summary_after"] = get_profile_summary(profiles_after)
                            
                            # Compute profile changes
                            results[result_key]["profile_changes"] = _compute_profile_changes(
                                profiles_before, profiles_after, request.move
                            )
                    except Exception as e:
                        print(f"      ⚠️ Piece profiling failed: {e}")
                        import traceback
                        traceback.print_exc()
                
            else:
                # Position analysis
                if status_callback:
                    status_callback("analyzing", "Analyzing position")
                
                info = await engine_queue.enqueue(
                    engine_queue.engine.analyse,
                    board,
                    chess.engine.Limit(depth=request.depth),
                    multipv=request.lines
                )
                
                # Extract results
                candidates = []
                for rank, line in enumerate(info, 1):
                    if line.get("pv"):
                        try:
                            pv_move = line["pv"][0]
                            if pv_move in board.legal_moves:
                                move_san = board.san(pv_move)
                                score = line["score"].white()
                                eval_cp = score.score(mate_score=10000) if not score.is_mate() else (
                                    10000 if score.mate() > 0 else -10000
                                )
                                candidate = {
                                    "move": move_san,
                                    "eval_cp": eval_cp,
                                    "preference_rank": rank
                                }
                                if request.include_pv_analysis:
                                    pv_san = []
                                    temp_board = board.copy()
                                    for pv_m in line["pv"][:5]:
                                        if pv_m in temp_board.legal_moves:
                                            pv_san.append(temp_board.san(pv_m))
                                            temp_board.push(pv_m)
                                        else:
                                            break
                                    candidate["pv"] = pv_san
                                candidates.append(candidate)
                        except Exception as e:
                            print(f"      ⚠️ Error parsing candidate: {e}")
                
                results[result_key] = {
                    "eval_cp": candidates[0]["eval_cp"] if candidates else 0,
                    "candidates": candidates,
                    "depth": request.depth
                }
                
                # Add PV trajectory analysis if requested
                if request.include_pv_analysis and candidates and candidates[0].get("pv"):
                    if status_callback:
                        status_callback("tracking", "Analyzing PV trajectory")
                    try:
                        pv_trajectory = await analyze_pv_trajectory(
                            request.fen,
                            candidates[0]["pv"],
                            engine_queue,
                            max_moves=5
                        )
                        results[result_key]["pv_trajectory"] = pv_trajectory
                    except Exception as e:
                        print(f"      ⚠️ PV trajectory analysis failed: {e}")
                
                # Add piece profiles if requested
                if request.include_piece_profiles:
                    if status_callback:
                        status_callback("profiling", "Building piece profiles")
                    try:
                        from piece_profiler import build_piece_profiles, get_profile_summary
                        
                        profiles = await build_piece_profiles(request.fen, nnue_dump=None, tags=None)
                        
                        results[result_key]["piece_profiles"] = profiles
                        results[result_key]["profile_summary"] = get_profile_summary(profiles)
                    except Exception as e:
                        print(f"      ⚠️ Piece profiling failed: {e}")
                        import traceback
                        traceback.print_exc()
        
        except Exception as e:
            print(f"   ⚠️ Pre-analysis failed for {request.fen[:30]}: {e}")
            result_key = f"{request.fen}:{request.move}" if request.move else request.fen
            results[result_key] = {"error": str(e)}
    
    return results


async def analyze_pv_trajectory(
    fen: str,
    pv_moves: List[str],
    engine_queue,
    max_moves: int = 5
) -> Dict[str, Any]:
    """
    Analyze how piece profiles change through a PV sequence.
    This creates a qualitative understanding of WHY the PV is best.
    """
    import chess
    
    trajectory = {
        "moves": [],
        "piece_journeys": {},  # Track each piece through the PV
        "key_transformations": [],
        "strategic_summary": []
    }
    
    board = chess.Board(fen)
    current_fen = fen
    
    try:
        from piece_profiler import build_piece_profiles
        
        # Get initial profiles
        prev_profiles = await build_piece_profiles(current_fen, nnue_dump=None, tags=None)
        
        for i, move_san in enumerate(pv_moves[:max_moves]):
            try:
                move = board.parse_san(move_san)
                board.push(move)
                current_fen = board.fen()
                
                # Get profiles after this move
                curr_profiles = await build_piece_profiles(current_fen, nnue_dump=None, tags=None)
                
                # Compute changes for this step
                step_changes = _compute_profile_changes(prev_profiles, curr_profiles, move_san)
                
                trajectory["moves"].append({
                    "move": move_san,
                    "ply": i + 1,
                    "fen_after": current_fen,
                    "changes": step_changes
                })
                
                # Track piece journeys
                if step_changes.get("moved_piece"):
                    mp = step_changes["moved_piece"]
                    piece_key = mp["piece"]
                    if piece_key not in trajectory["piece_journeys"]:
                        trajectory["piece_journeys"][piece_key] = []
                    trajectory["piece_journeys"][piece_key].append({
                        "ply": i + 1,
                        "from": mp["from"],
                        "to": mp["to"],
                        "role_change": mp.get("old_role") != mp.get("new_role"),
                        "activity_delta": mp.get("new_activity", 0) - mp.get("old_activity", 0)
                    })
                
                # Identify key transformations
                if step_changes.get("captured_piece"):
                    trajectory["key_transformations"].append(
                        f"Move {i+1} ({move_san}): Captures {step_changes['captured_piece']['piece']}"
                    )
                
                for rc in step_changes.get("role_changes", []):
                    if rc["from_role"] != rc["to_role"]:
                        trajectory["key_transformations"].append(
                            f"Move {i+1} ({move_san}): {rc['piece']} becomes {rc['to_role']}"
                        )
                
                for ac in step_changes.get("activity_changes", []):
                    if abs(ac["delta"]) > 20:
                        trajectory["key_transformations"].append(
                            f"Move {i+1} ({move_san}): {ac['piece']} {ac['direction']} significantly"
                        )
                
                prev_profiles = curr_profiles
                
            except Exception as e:
                print(f"      ⚠️ Error analyzing PV move {move_san}: {e}")
                break
        
        # Generate strategic summary
        for piece, journey in trajectory["piece_journeys"].items():
            if len(journey) > 1:
                total_activity = sum(j.get("activity_delta", 0) for j in journey)
                trajectory["strategic_summary"].append(
                    f"{piece}: Moves {len(journey)} times, net activity change {total_activity:+.0f}cp"
                )
        
    except Exception as e:
        print(f"   ⚠️ PV trajectory analysis failed: {e}")
        trajectory["error"] = str(e)
    
    return trajectory


def _compute_profile_changes(
    profiles_before: Dict,
    profiles_after: Dict,
    move: str
) -> Dict[str, Any]:
    """
    Compare piece profiles before and after a move to describe impact.
    Now includes significance scoring for all changes.
    """
    from significance_scorer import SignificanceScorer
    
    changes = {
        "moved_piece": None,
        "captured_piece": None,
        "activity_changes": [],
        "role_changes": [],
        "tag_changes": [],
        "summary": [],
        "scored_changes": []  # NEW: Changes with significance scores
    }
    
    # Find pieces that changed position or were captured
    squares_before = set(profiles_before.keys())
    squares_after = set(profiles_after.keys())
    
    # Pieces that disappeared (captured)
    disappeared = squares_before - squares_after
    appeared = squares_after - squares_before
    
    # Try to identify moved piece vs captured
    for sq in disappeared:
        profile = profiles_before[sq]
        # Check if this piece appeared on a new square (moved)
        found_new_sq = False
        for new_sq in appeared:
            new_profile = profiles_after[new_sq]
            if (new_profile.get("piece_type") == profile.get("piece_type") and
                new_profile.get("color") == profile.get("color")):
                old_activity = profile.get("nnue_contribution_cp", profile.get("nnue_contribution", 0))
                new_activity = new_profile.get("nnue_contribution_cp", new_profile.get("nnue_contribution", 0))
                activity_delta = new_activity - old_activity
                
                # Score the improvement
                piece_type = profile.get("piece_type", "unknown")
                tags_before = profile.get("tags", [])
                tags_after = new_profile.get("tags", [])
                
                improvement_score = SignificanceScorer.score_piece_improvement(
                    nnue_delta=activity_delta,
                    piece_type=piece_type,
                    tags_before=tags_before,
                    tags_after=tags_after
                )
                
                changes["moved_piece"] = {
                    "piece": profile.get("piece_symbol"),
                    "from": sq,
                    "to": new_sq,
                    "old_role": profile.get("role"),
                    "new_role": new_profile.get("role"),
                    "old_activity": old_activity,
                    "new_activity": new_activity,
                    "activity_delta": activity_delta,
                    "improvement_score": improvement_score
                }
                
                # Add to scored changes if significant
                if improvement_score["significance_score"] > 20:
                    changes["scored_changes"].append({
                        "type": "piece_improvement",
                        "piece": profile.get("piece_symbol"),
                        "from": sq,
                        "to": new_sq,
                        "score": improvement_score,
                        "description": f"{profile.get('piece_symbol')} improved by {activity_delta:.1f}cp"
                    })
                
                found_new_sq = True
                break
        
        if not found_new_sq:
            # This piece was captured
            changes["captured_piece"] = {
                "piece": profile.get("piece_symbol"),
                "square": sq,
                "was_role": profile.get("role")
            }
    
    # Compare profiles for pieces that stayed
    for sq in squares_before & squares_after:
        before = profiles_before[sq]
        after = profiles_after[sq]
        
        # Check activity change
        activity_before = before.get("nnue_contribution_cp", before.get("nnue_contribution", 0))
        activity_after = after.get("nnue_contribution_cp", after.get("nnue_contribution", 0))
        activity_delta = activity_after - activity_before
        
        if abs(activity_delta) > 2:  # Lower threshold to catch more changes
            piece_type = before.get("piece_type", "unknown")
            tags_before = before.get("tags", [])
            tags_after = after.get("tags", [])
            
            improvement_score = SignificanceScorer.score_piece_improvement(
                nnue_delta=activity_delta,
                piece_type=piece_type,
                tags_before=tags_before,
                tags_after=tags_after
            )
            
            changes["activity_changes"].append({
                "piece": before.get("piece_symbol"),
                "square": sq,
                "delta": activity_delta,
                "direction": "improved" if activity_delta > 0 else "worsened",
                "improvement_score": improvement_score
            })
            
            # Add to scored changes if significant
            if improvement_score["significance_score"] > 20:
                changes["scored_changes"].append({
                    "type": "piece_activity_change",
                    "piece": before.get("piece_symbol"),
                    "square": sq,
                    "score": improvement_score,
                    "description": f"{before.get('piece_symbol')} on {sq} {improvement_score['magnitude']}ly {'improved' if activity_delta > 0 else 'worsened'}"
                })
        
        # Check role change
        role_before = before.get("role")
        role_after = after.get("role")
        if role_before != role_after:
            changes["role_changes"].append({
                "piece": before.get("piece_symbol"),
                "square": sq,
                "from_role": role_before,
                "to_role": role_after
            })
        
        # Check tag changes
        tags_before = set(before.get("tags", []))
        tags_after = set(after.get("tags", []))
        new_tags = tags_after - tags_before
        lost_tags = tags_before - tags_after
        
        if new_tags or lost_tags:
            changes["tag_changes"].append({
                "piece": before.get("piece_symbol"),
                "square": sq,
                "gained": list(new_tags),
                "lost": list(lost_tags)
            })
    
    # Generate summary
    summaries = []
    
    if changes["moved_piece"]:
        mp = changes["moved_piece"]
        summaries.append(f"{mp['piece']} moved from {mp['from']} to {mp['to']}")
        if mp["old_role"] != mp["new_role"]:
            summaries.append(f"Role changed from {mp['old_role']} to {mp['new_role']}")
        activity_change = mp.get("activity_delta", mp["new_activity"] - mp["old_activity"])
        if abs(activity_change) > 2:
            improvement_score = mp.get("improvement_score", {})
            magnitude = improvement_score.get("magnitude", "")
            summaries.append(f"Activity {magnitude}ly {'improved' if activity_change > 0 else 'decreased'} by {abs(activity_change):.1f}cp (significance: {improvement_score.get('significance_score', 0):.1f})")
    
    if changes["captured_piece"]:
        cp = changes["captured_piece"]
        summaries.append(f"Captured {cp['piece']} on {cp['square']}")
    
    for ac in changes["activity_changes"][:3]:  # Top 3
        summaries.append(f"{ac['piece']} on {ac['square']} {ac['direction']} ({ac['delta']:+.0f} cp)")
    
    for rc in changes["role_changes"][:2]:  # Top 2
        summaries.append(f"{rc['piece']} on {rc['square']}: {rc['from_role']} → {rc['to_role']}")
    
    changes["summary"] = summaries
    
    return changes

