from __future__ import annotations

import os
import time
from typing import Any, AsyncGenerator, Dict, Optional, Tuple

import chess

from command_protocol import render_command
from minimal_prompts import MIN_SYSTEM_PROMPT_V1, CHAT_CONTRACT_V1
from task_models import GoalObject, EvidenceRegistry, CompressedTaskMemory
from fast_router import FastHeuristicsRouter
from skills.evaluate import evaluate_position
from skills.explain import explain_with_facts
from self_check import self_check
from skills.compare import compare_moves
from judges.move_compare_judge import judge_compare_moves
from memory_compressor import compress_memory
from pipeline_timer import get_pipeline_timer
from scan_service import ScanPolicy
from skills.scan import scan_d2_d16_from_fen
from skills.scan import scan_d2_d16_after_san
from skills.baseline_intuition import run_baseline_intuition, BaselineIntuitionPolicy, format_baseline_intuition_for_chat
from skills.motifs import MotifPolicy
from mode_router import ModeRouter
from facts_assembler import FactsAssembler
from facts_models import AnswerEnvelope
from verifier import Verifier
from confidence_signals import compute_confidence_signals
from light_raw_analyzer import compute_light_raw_analysis
from evidence_builder import build_evidence_pack
from skills.justify import justify_from_evidence


def _validate_and_filter_ui_commands(ui_commands: list) -> list:
    """
    Validate and filter UI commands to ensure only valid actions are included.
    Returns a filtered list of valid commands.
    """
    if not isinstance(ui_commands, list):
        return []
    
    valid_actions = {
        "load_position", "new_tab", "navigate", "annotate", "push_move",
        "set_fen", "set_pgn", "delete_move", "delete_variation", "promote_variation", "set_ai_game"
    }
    
    filtered = []
    for i, cmd in enumerate(ui_commands):
        if not isinstance(cmd, dict):
            print(f"      [CHAIN] WARNING: UI command {i} is not a dict, skipping: {cmd}")
            continue
        action = cmd.get("action")
        if action not in valid_actions:
            print(f"      [CHAIN] WARNING: Invalid UI command action '{action}' at index {i}, skipping. Valid actions: {valid_actions}")
            continue
        filtered.append(cmd)
    
    return filtered


class TaskController:
    """
    Cursor-like control plane.

    Initially minimal: wraps existing building blocks (RequestInterpreter + ToolExecutor + Summariser + Explainer)
    while adding:
    - deterministic fast paths
    - goal object stub
    - explicit stop reason
    - milestones

    Later phases can expand this into a full skill/judge/memory loop.
    """

    def __init__(
        self,
        *,
        llm_router,
        request_interpreter,
        tool_executor,
        engine_queue,
        engine_pool_instance=None,
        openai_client,
    ):
        self.llm_router = llm_router
        self.request_interpreter = request_interpreter
        self.tool_executor = tool_executor
        self.engine_queue = engine_queue
        self.engine_pool_instance = engine_pool_instance
        self.openai_client = openai_client
        self.fast_router = FastHeuristicsRouter()
        self.mode_router = ModeRouter()
        self.facts_assembler = FactsAssembler()
        self.verifier = Verifier()

    async def _answer_general_chat(
        self,
        *,
        task_id: str,
        user_message: str,
        context: Dict[str, Any],
        messages: list | None = None,
        model: str,
        temperature: float,
    ) -> Dict[str, Any]:
        # Keep this minimal: a single command-based prompt.
        history = []
        try:
            if isinstance(messages, list):
                for m in messages[-10:]:
                    if isinstance(m, dict) and m.get("role") in ("user", "assistant"):
                        history.append({"role": m.get("role"), "content": (m.get("content") or "")[:600]})
        except Exception:
            history = []
        cmd = render_command(
            command="CHAT",
            input={
                "user_message": user_message,
                "history": history,
                "context": {k: context.get(k) for k in ["mode", "fen", "pgn", "last_move"] if k in context},
            },
            constraints={"style": "helpful", "json_only": True},
        )
        try:
            res = self.llm_router.complete_json(
                session_id=task_id,
                stage="chat",
                subsession="chat",
                system_prompt=MIN_SYSTEM_PROMPT_V1,
                task_seed=CHAT_CONTRACT_V1,
                user_text=cmd,
                model=model,
                temperature=temperature,
                max_tokens=int(os.getenv("CHAT_MAX_TOKENS", "1200")),
            )
            # Handle both 'response' and 'explanation' keys from LLM
            if isinstance(res, dict):
                if "explanation" in res:
                    # Ensure ui_commands is always an array and validate
                    ui_commands = _validate_and_filter_ui_commands(res.get("ui_commands", []))
                    return {"explanation": res["explanation"], "ui_commands": ui_commands}
                elif "response" in res:
                    ui_commands = _validate_and_filter_ui_commands(res.get("ui_commands", []))
                    return {"explanation": res["response"], "ui_commands": ui_commands}
                else:
                    # Try to find any text field
                    for key in ["content", "text", "message", "answer"]:
                        if key in res:
                            ui_commands = _validate_and_filter_ui_commands(res.get("ui_commands", []))
                            return {"explanation": res[key], "ui_commands": ui_commands}
                    # If no explanation found, create one from the response
                    ui_commands = _validate_and_filter_ui_commands(res.get("ui_commands", []))
                    return {"explanation": "I've processed your request.", "ui_commands": ui_commands}
            # If res is a string, it might be a Python dict string - try to extract JSON
            if isinstance(res, str):
                # Check if it looks like a Python dict string
                if res.strip().startswith("{") and ("'" in res or "True" in res or "False" in res):
                    import json
                    import ast
                    try:
                        # Try to parse as Python literal and convert to JSON
                        parsed = ast.literal_eval(res)
                        if isinstance(parsed, dict):
                            explanation = parsed.get("explanation") or parsed.get("response") or "I've processed your request."
                            ui_commands = _validate_and_filter_ui_commands(parsed.get("ui_commands", []))
                            return {"explanation": str(explanation), "ui_commands": ui_commands}
                    except Exception:
                        pass
                # If it's just a string, wrap it as explanation
                return {"explanation": res, "ui_commands": []}
            return {"explanation": "I've processed your request.", "ui_commands": []}
        except Exception as e:
            # Fallback for simple chat if JSON fails
            import traceback
            print(f"❌ [CHAT] JSON completion failed: {type(e).__name__}: {e}", flush=True)
            try:
                text = self.llm_router.complete(
                    session_id=task_id,
                    stage="chat",
                    subsession="chat",
                    system_prompt=MIN_SYSTEM_PROMPT_V1,
                    task_seed=CHAT_CONTRACT_V1,
                    user_text=cmd,
                    model=model,
                    temperature=temperature,
                )
                return {"explanation": text, "ui_commands": []}
            except Exception:
                return {"explanation": "I encountered an error processing your request.", "ui_commands": []}

    async def run(
        self,
        *,
        request,
        send_event,
    ) -> AsyncGenerator[str, None]:
        """
        Main streaming entrypoint.

        Yields SSE event strings via send_event helper.
        """
        t0 = time.time()
        # Budget should apply to the *interactive controller work* (investigation/justify/explain),
        # not to the baseline D2/D16 precomputation which we want to "already be done".
        # We therefore track a separate budget start time that we can reset after baseline completes.
        t_budget_start = t0
        # max_time_s is now primarily driven by ModeRouter policy (still env-overridable).
        max_time_s = float(os.getenv("TASK_MAX_TIME_S", "18"))
        engine_calls = 0
        llm_calls = 0
        context = request.context or {}
        task_id = request.task_id or request.session_id or "default"
        model = getattr(request, "model", "gpt-5")
        temperature = getattr(request, "temperature", 0.7)

        user_messages = [m for m in (request.messages or []) if m.get("role") == "user"]
        last_user_message = user_messages[-1].get("content", "") if user_messages else ""
        
        # CRITICAL: Ensure we're checking the USER's message, not assistant/LLM response
        # Verify we have a user message
        if not last_user_message or not isinstance(last_user_message, str):
            print(f"   ⚠️ [TASK_CONTROLLER] No valid user message found. user_messages count: {len(user_messages)}, last_user_message type: {type(last_user_message)}")
            last_user_message = ""
        
        # Turn-scoped LLM session id to prevent prefix/context bloat across user turns.
        # Using the count of user messages makes this deterministic for a given request.
        turn_n = max(1, len(user_messages))
        llm_session_id = f"{task_id}__t{turn_n}"
        fen = context.get("fen") or context.get("board_state") or chess.STARTING_FEN

        # Conversational context comes from the request payload (messages), not server-side transcript.
        chat_history = []
        try:
            for m in (request.messages or [])[-10:]:
                if isinstance(m, dict) and m.get("role") in ("user", "assistant"):
                    chat_history.append({"role": m.get("role"), "content": (m.get("content") or "")[:800]})
        except Exception:
            chat_history = []

        evidence = EvidenceRegistry()
        memory = CompressedTaskMemory()
        goal = GoalObject(objective=(last_user_message or "").strip()[:200] or "Answer the user")

        yield send_event("milestone", {"name": "task_started", "timestamp": time.time()})
        await _sleep0()

        _pt = get_pipeline_timer()

        def _should_stop(extra_reason: str = "") -> Optional[str]:
            dt = time.time() - t_budget_start
            if dt >= max_time_s:
                return f"budget_time_exceeded:{round(dt,2)}s"
            if extra_reason:
                return extra_reason
            return None

        # Check for game review intent (short-circuit main pathway)
        # IMPORTANT: This checks the USER's message, not any LLM response
        # Check for play-against-AI intent (short-circuit main pathway)
        if last_user_message and isinstance(last_user_message, str):
            try:
                from play_intent_patterns import detect_play_intent
                play_detection = detect_play_intent(last_user_message)
                print(f"   [TASK_CONTROLLER] ✅ Play intent check on USER message: '{last_user_message[:80]}...' -> {play_detection}")
                if play_detection.get("is_play_intent", False):
                    print(f"   [TASK_CONTROLLER] ✅ Detected play-against-AI intent (confidence: {play_detection.get('confidence', 0):.2f})")
                    # Return response with system message directing user to options menu
                    yield send_event(
                        "complete",
                        {
                            "content": "You can play directly against Chesster through the options menu! Click the 'Options' button to start a game.",
                            "stop_reason": "play_intent_detected",
                            "ui_commands": [
                                {
                                    "action": "system_message",
                                    "content": "💡 Tip: You can play directly against Chesster through the options menu!"
                                }
                            ],
                            "buttons": []
                        }
                    )
                    try:
                        if _pt:
                            _pt.record_stop_reason("play_intent_detected")
                    except Exception:
                        pass
                    return
            except Exception as e:
                print(f"   ⚠️ [TASK_CONTROLLER] Play intent detection failed: {e}")
                import traceback
                traceback.print_exc()

        # Fast router (deterministic, zero-token routing for simple requests)
        fr = self.fast_router.try_route(user_message=last_user_message, context=context)
        if getattr(fr, "handled", False):
            if getattr(fr, "milestone_kind", None):
                yield send_event("milestone", {"name": "fast_path_taken", "kind": fr.milestone_kind, "timestamp": time.time()})
                await _sleep0()
            yield send_event("complete", {"content": fr.content, "stop_reason": fr.stop_reason})
            try:
                if _pt:
                    _pt.record_stop_reason(fr.stop_reason)
            except Exception:
                pass
            return

        # Build intent/goal via existing interpreter (LLM but cheap)
        print(f"   [CHAIN] [TASK_CONTROLLER] Step 1: Interpreting user intent...")
        print(f"      [CHAIN] User message: {last_user_message[:100]}...")
        print(f"      [CHAIN] Context keys: {list(context.keys()) if context else []}")
        yield send_event("milestone", {"name": "goal_built", "timestamp": time.time()})
        await _sleep0()
        llm_calls += 1

        # If no investigation required, do a single chat completion and return
        try:
            # Give the interpreter short conversation context so follow-ups like
            # "can you fetch it for me" can still resolve to game_review without
            # backend phrase matching.
            interp_context = dict(context) if isinstance(context, dict) else {}
            interp_context["chat_history"] = chat_history
            intent_plan = await self.request_interpreter.interpret_intent(
                message=last_user_message,
                context=interp_context,
                status_callback=None,
                session_id=llm_session_id,
            )
            print(f"   [CHAIN] [TASK_CONTROLLER] Intent classified:")
            print(f"      [CHAIN] Investigation required: {getattr(intent_plan, 'investigation_required', False)}")
            print(f"      [CHAIN] Mode: {getattr(intent_plan, 'mode', 'unknown')}")
            print(f"      [CHAIN] Goal: {getattr(intent_plan, 'goal', '')[:80]}...")

            # -----------------------------------------------------------------
            # Generic coercion: if the interpreter produced game_review but its
            # structured goal/requests indicate "list/select multiple games",
            # convert to game_select to avoid review tabs/walkthrough/explainer.
            # -----------------------------------------------------------------
            try:
                if getattr(intent_plan, "intent", "") == "game_review":
                    goal_txt = (getattr(intent_plan, "goal", "") or "")
                    summary_txt = (getattr(intent_plan, "user_intent_summary", "") or "")
                    g = (goal_txt + " " + summary_txt).lower()
                    irs = getattr(intent_plan, "investigation_requests", None) or []
                    if (("list" in g) or ("select" in g) or ("retrieve and list" in g)) and isinstance(irs, list) and len(irs) >= 2:
                        reqs = []
                        # Reserve a 5-unique budget by default.
                        reqs.append({"name": "five_unique", "count": 5, "sort": "date_desc", "require_unique": True})

                        purpose_to_req = {
                            "last_game": {"name": "last_game", "offset": 0, "sort": "date_desc", "allow_reuse": True},
                            "second_last_game": {"name": "second_last_game", "offset": 1, "sort": "date_desc", "allow_reuse": True},
                            "won_game": {"name": "won_game", "filters": {"result": "win"}, "allow_reuse": True},
                            "rapid_game": {"name": "rapid_game", "filters": {"time_control": "rapid"}, "allow_reuse": True},
                            "bullet_game": {"name": "bullet_game", "filters": {"time_control": "bullet"}, "allow_reuse": True},
                            "played_as_black": {"name": "played_as_black", "filters": {"color": "black"}, "allow_reuse": True},
                            "black_as_player": {"name": "played_as_black", "filters": {"color": "black"}, "allow_reuse": True},
                        }
                        for ir in irs[:12]:
                            try:
                                purpose = (getattr(ir, "purpose", "") or "").strip().lower()
                                if purpose in purpose_to_req:
                                    base = dict(purpose_to_req[purpose])
                                    base.setdefault("count", 1)
                                    base.setdefault("require_unique", False)
                                    reqs.append(base)
                            except Exception:
                                continue

                        setattr(intent_plan, "intent", "game_select")
                        setattr(
                            intent_plan,
                            "game_select_params",
                            {
                                # Fetch a larger pool so we can actually satisfy time-control slices (rapid/bullet/etc).
                                "candidate_fetch_count": 160,
                                "months_back": 12,
                                "global_unique": True,
                                # Allow more than 5 uniques if needed to satisfy requested categories.
                                # (The response can still *present* 5 uniques as the primary list.)
                                "global_limit": 12,
                            },
                        )
                        setattr(intent_plan, "game_select_requests", reqs)
                        setattr(intent_plan, "investigation_required", False)
                        print("   ✅ Coerced intent_plan to game_select (list/select games)")
            except Exception as _coerce_e:
                try:
                    print(f"   ⚠️ game_select coercion skipped: {_coerce_e}")
                except Exception:
                    pass
        except Exception as e:
            print(f"   ❌ [CHAIN] [TASK_CONTROLLER] Interpreter failed: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            # Safe fallback: chat answer
            res = await self._answer_general_chat(
                task_id=llm_session_id,
                user_message=last_user_message,
                context=context,
                messages=(request.messages or []),
                model=model,
                temperature=temperature,
            )
            content = res.get("explanation", "")
            ui_commands = res.get("ui_commands", [])
            yield send_event("complete", {"content": content, "ui_commands": ui_commands, "stop_reason": f"interpreter_failed:{str(e)[:80]}"})
            return

        evidence.llm["intent_plan"] = getattr(intent_plan, "to_dict", lambda: {})()
        yield send_event("milestone", {"name": "fast_classify_done", "timestamp": time.time()})
        await _sleep0()
        
        # Check if interpreter wants to call set_ai_game tool
        ui_commands_from_tools = []
        try:
            tool_sequence = getattr(intent_plan, "tool_sequence", None) or []
            for tool_call in tool_sequence:
                if isinstance(tool_call, dict) and tool_call.get("name") == "set_ai_game":
                    tool_args = tool_call.get("arguments", {})
                    print(f"   [TASK_CONTROLLER] Executing set_ai_game tool: {tool_args}")
                    tool_result = await self.tool_executor.execute_tool("set_ai_game", tool_args, context=context)
                    # Extract UI command from tool result
                    if isinstance(tool_result, dict) and "ui_command" in tool_result:
                        ui_commands_from_tools.append(tool_result["ui_command"])
                        print(f"   [TASK_CONTROLLER] Extracted UI command from set_ai_game tool")
        except Exception as e:
            print(f"   ⚠️ [TASK_CONTROLLER] Error executing set_ai_game tool: {type(e).__name__}: {e}")

        # ---------------------------------------------------------------------
        # Personal game review hook (fetch + analyze last game)
        # Uses existing ToolExecutor.fetch_and_review_games / review_full_game infra.
        # ---------------------------------------------------------------------
        # NOTE: routing is LLM-dependent (intent_plan). Avoid phrase matching here.
        if getattr(intent_plan, "intent", "") == "game_select":
            yield send_event("status", {"phase": "fetch", "message": "Selecting games…", "timestamp": time.time()})
            await _sleep0()

            params = getattr(intent_plan, "game_select_params", None) or {}
            requests = getattr(intent_plan, "game_select_requests", None) or []
            
            # If requests is empty, try to infer from the user message
            if not requests and last_user_message:
                msg_l = last_user_message.lower()
                inferred_requests = []
                
                # Infer "last blitz game" -> {name: "last_blitz_game", filters: {time_control: "blitz"}}
                if "last" in msg_l:
                    if "blitz" in msg_l:
                        inferred_requests.append({"name": "last_blitz_game", "filters": {"time_control": "blitz"}})
                    elif "rapid" in msg_l:
                        inferred_requests.append({"name": "last_rapid_game", "filters": {"time_control": "rapid"}})
                    elif "bullet" in msg_l:
                        inferred_requests.append({"name": "last_bullet_game", "filters": {"time_control": "bullet"}})
                    elif "classical" in msg_l:
                        inferred_requests.append({"name": "last_classical_game", "filters": {"time_control": "classical"}})
                    else:
                        # Just "last game"
                        inferred_requests.append({"name": "last_game", "filters": {}})
                
                if inferred_requests:
                    print(f"[TASK_CONTROLLER] Inferred {len(inferred_requests)} selection requests from user message")
                    requests = inferred_requests

            # Resolve username/platform from params or connected_accounts
            username = params.get("username")
            platform = params.get("platform")
            try:
                if not (username and platform):
                    accounts = context.get("connected_accounts") if isinstance(context, dict) else None
                    if isinstance(accounts, list) and accounts:
                        a0 = accounts[0] if isinstance(accounts[0], dict) else None
                        if isinstance(a0, dict):
                            username = username or a0.get("username")
                            platform = platform or a0.get("platform")
                if isinstance(platform, str):
                    p = platform.lower().strip()
                    if p in ("chesscom", "chess.com", "chess"):
                        platform = "chess.com"
                    elif p in ("lichess", "lichess.org"):
                        platform = "lichess"
            except Exception:
                pass

            tool_args = {
                "username": username,
                "platform": platform,
                # Guard against tiny candidate pools from the interpreter; selectors need breadth.
                "candidate_fetch_count": max(60, int(params.get("candidate_fetch_count", 80) or 80)),
                "months_back": int(params.get("months_back", 6) or 6),
                "date_from": params.get("date_from"),
                "date_to": params.get("date_to"),
                "global_unique": bool(params.get("global_unique", True)),
                "global_limit": params.get("global_limit"),
                # Always include PGN for selected refs so they can be opened in tabs later.
                "include_pgn": True,
                "requests": requests if isinstance(requests, list) else [],
            }

            tool_failed = False
            try:
                tool_result = await self.tool_executor.execute_tool("select_games", tool_args, context=context)
            except Exception as e:
                tool_failed = True
                tool_result = {"success": False, "error": "select_games_exception", "message": str(e)}
            tool_calls = [{"tool": "select_games", "args": tool_args, "result": tool_result}]

            if isinstance(tool_result, dict) and tool_result.get("error") == "info_required":
                yield send_event(
                    "complete",
                    {
                        "content": tool_result.get("message") or "I need your username and platform (chess.com or lichess) to select games.",
                        "stop_reason": "game_select_info_required",
                        "ui_commands": [],
                        "tool_calls": tool_calls,
                        "baseline_intuition": None,
                        "explain_error": None,
                        "narrative_decision": {"core_message": "Game selection needs account info.", "claims": [], "pattern_claims": [], "pattern_summary": None},
                        "detected_intent": "game_select",
                        "envelope": None,
                    },
                )
                return

            # Always use LLM to generate natural prose (never deterministic formatting)
            selected = (tool_result.get("selected") if isinstance(tool_result, dict) else None) or {}
            unmet = (tool_result.get("unmet") if isinstance(tool_result, dict) else None) or []
            if isinstance(tool_result, dict) and tool_result.get("success") is False:
                tool_failed = True

            print(f"[TASK_CONTROLLER] game_select: selected keys={list(selected.keys())}, unmet count={len(unmet)}")
            
            # Format selected games for LLM context
            selected_summary = {}
            for k, arr in selected.items():
                if isinstance(arr, list) and arr:
                    games_list = []
                    for g in arr[:3]:  # Limit to first 3 per label
                        if isinstance(g, dict):
                            games_list.append({
                                "date": g.get("date"),
                                "time_category": g.get("time_category"),
                                "opponent": g.get("opponent_name"),
                                "result": g.get("result"),
                                "color": g.get("player_color"),
                                "eco": g.get("eco"),
                                "url": g.get("url"),
                            })
                    if games_list:
                        selected_summary[k] = games_list
            
            unmet_summary = []
            for u in unmet[:5]:
                if isinstance(u, dict):
                    unmet_summary.append({
                        "name": u.get("name"),
                        "found": u.get("found_count", 0),
                        "requested": u.get("requested_count", 1),
                    })
            
            print(f"[TASK_CONTROLLER] game_select: selected_summary keys={list(selected_summary.keys())}, unmet_summary={unmet_summary}")

            # Generate LLM response with selected games and unmet selections
            # ALWAYS use LLM - never fall back to deterministic formatting
            content = None
            try:
                prompt_msg = (
                    f"The user asked: '{last_user_message}'. "
                    f"Here are the selected games: {selected_summary}. "
                    f"Here are unmet selections (couldn't find matching games): {unmet_summary}. "
                    f"Write a natural, conversational response that: "
                    f"1. Lists the games that were found (include date, opponent, result, time control if available), "
                    f"2. Mentions any selections that couldn't be found and why (e.g., 'I couldn't find a rapid game in your recent history'), "
                    f"3. Uses natural language, not bullet points, 'Details:', or technical formatting. "
                    f"4. Be concise but helpful. "
                    f"5. If no games were found, explain why and what the user can do next."
                )
                print(f"[TASK_CONTROLLER] Calling LLM for game_select prose. selected_summary={bool(selected_summary)}, unmet_summary={bool(unmet_summary)}")
                llm = await self._answer_general_chat(
                    task_id=llm_session_id,
                    user_message=prompt_msg,
                    context={
                        "mode": context.get("mode"),
                        "connected_accounts": context.get("connected_accounts"),
                        "game_select": {"selected": selected_summary, "unmet": unmet_summary},
                    },
                    messages=(request.messages or []),
                    model=model,
                    temperature=temperature,
                )
                print(f"[TASK_CONTROLLER] LLM response type: {type(llm)}, keys: {list(llm.keys()) if isinstance(llm, dict) else 'not dict'}")
                if isinstance(llm, dict) and isinstance(llm.get("explanation"), str) and llm["explanation"].strip():
                    content = llm["explanation"].strip()
                    print(f"[TASK_CONTROLLER] LLM generated content (length: {len(content)})")
                else:
                    print(f"[TASK_CONTROLLER] LLM response missing explanation field or empty")
            except Exception as e:
                import traceback
                print(f"[TASK_CONTROLLER] Error generating LLM response for game_select: {e}")
                traceback.print_exc()
            
            # If LLM failed, generate a minimal fallback (still natural language, not "Details:")
            if not content or not content.strip():
                print(f"[TASK_CONTROLLER] LLM failed or returned empty, using fallback. selected_summary={bool(selected_summary)}, unmet_summary={bool(unmet_summary)}")
                if selected_summary:
                    content = f"I found {sum(len(v) for v in selected_summary.values())} game(s) from your history."
                elif unmet_summary:
                    names = [u.get("name", "game") for u in unmet_summary]
                    content = f"I couldn't find the requested games ({', '.join(names)}). They might not be in your recent history or the filters might be too specific."
                else:
                    content = "I couldn't find any games matching your request."

            # Automatically open selected game in a new tab if PGN is available.
            # This handles "pull up", "show", "get", "open", etc. - any game selection should open it.
            ui_commands = []
            try:
                if isinstance(selected, dict) and selected:
                    chosen_ref = None
                    # Prefer a "last_*" selection if present (e.g. last_rapid_game).
                    for k in selected.keys():
                        if isinstance(k, str) and k.startswith("last_"):
                            arr = selected.get(k)
                            if isinstance(arr, list) and arr and isinstance(arr[0], dict):
                                chosen_ref = arr[0]
                                break
                    if chosen_ref is None:
                        # Fallback to first available game
                        for arr in selected.values():
                            if isinstance(arr, list) and arr and isinstance(arr[0], dict):
                                chosen_ref = arr[0]
                                break
                    if isinstance(chosen_ref, dict):
                        pgn = chosen_ref.get("pgn")
                        if isinstance(pgn, str) and pgn.strip():
                            date = chosen_ref.get("date") or ""
                            tc = chosen_ref.get("time_category") or ""
                            opp = chosen_ref.get("opponent_name") or ""
                            title = f"{date} {tc} vs {opp}".strip() or "Selected game"
                            ui_cmd = {"action": "new_tab", "params": {"type": "review", "pgn": pgn, "title": title}}
                            ui_commands.append(ui_cmd)
                            # Only append "Opened it in a new tab" if user explicitly asked for it
                            msg_l = (last_user_message or "").lower()
                            if any(w in msg_l for w in ["tab", "open", "load", "bring", "put", "pull", "show", "get"]):
                                content = (content + "\n\nOpened it in a new tab.").strip()
                            print(f"[TASK_CONTROLLER] Emitting new_tab UI command with PGN (length: {len(pgn)}), title: {title}")
                            print(f"[TASK_CONTROLLER] UI command preview: action={ui_cmd['action']}, pgn_preview={pgn[:100] if len(pgn) > 100 else pgn}...")
                        else:
                            print(f"[TASK_CONTROLLER] WARNING: chosen_ref has no PGN. Keys: {list(chosen_ref.keys())}, chosen_ref={chosen_ref}")
            except Exception as e:
                import traceback
                print(f"[TASK_CONTROLLER] Error emitting new_tab UI command: {e}")
                traceback.print_exc()
                ui_commands = []

            stop_reason = "game_select_done"
            if tool_failed:
                stop_reason = "game_select_failed"
                # Always return an LLM-written message even if selection failed.
                try:
                    llm = await self._answer_general_chat(
                        task_id=llm_session_id,
                        user_message=(
                            "The user asked to list/select specific games from their history, but the game selector tool failed. "
                            "Write a short, helpful response explaining the failure, what info is missing (if any), and what you can still do next. "
                            "Do NOT fabricate game details."
                        ),
                        context={
                            "mode": context.get("mode"),
                            "connected_accounts": context.get("connected_accounts"),
                            "game_select": {"args": tool_args, "tool_result": tool_result},
                        },
                        messages=(request.messages or []),
                        model=model,
                        temperature=temperature,
                    )
                    if isinstance(llm, dict) and isinstance(llm.get("explanation"), str) and llm["explanation"].strip():
                        content = llm["explanation"].strip()
                except Exception:
                    pass
            
            # Merge UI commands from tools (e.g., set_ai_game)
            if ui_commands_from_tools:
                if not isinstance(ui_commands, list):
                    ui_commands = []
                ui_commands.extend(ui_commands_from_tools)
                ui_commands = _validate_and_filter_ui_commands(ui_commands)

            yield send_event(
                "complete",
                {
                    "content": content,
                    "stop_reason": stop_reason,
                    "duration_s": round(time.time() - t0, 4),
                    "budgets": {"engine_calls": engine_calls, "llm_calls": llm_calls, "max_time_s": max_time_s},
                    "ui_commands": ui_commands,
                    "tool_calls": tool_calls,
                    "baseline_intuition": None,
                    "explain_error": None,
                    "narrative_decision": {"core_message": "Games selected.", "claims": [], "pattern_claims": [], "pattern_summary": None},
                    "detected_intent": "game_select",
                    "envelope": None,
                },
            )
            return

        if getattr(intent_plan, "intent", "") == "game_review":
            yield send_event("status", {"phase": "review", "message": "Reviewing your last game…", "timestamp": time.time()})
            await _sleep0()

            # Prefer reviewing a PGN already loaded in context.
            ctx_pgn = context.get("pgn") if isinstance(context, dict) else None

            # Resolve username/platform (interpreter may inject game_review_params from connected_accounts)
            params = getattr(intent_plan, "game_review_params", None) or {}
            username = params.get("username")
            platform = params.get("platform")
            try:
                if not (username and platform):
                    accounts = context.get("connected_accounts") if isinstance(context, dict) else None
                    if isinstance(accounts, list) and accounts:
                        a0 = accounts[0] if isinstance(accounts[0], dict) else None
                        if isinstance(a0, dict):
                            username = username or a0.get("username")
                            platform = platform or a0.get("platform")
                if isinstance(platform, str):
                    p = platform.lower().strip()
                    if p in ("chesscom", "chess.com", "chess"):
                        platform = "chess.com"
                    elif p in ("lichess", "lichess.org"):
                        platform = "lichess"
            except Exception:
                pass

            # Run tool(s)
            tool_result: Dict[str, Any] = {}
            tool_calls = []
            try:
                if isinstance(ctx_pgn, str) and ctx_pgn.strip():
                    tool_args = {"pgn": ctx_pgn, "side_focus": "both", "depth": int(os.getenv("REVIEW_GAME_DEPTH", "15"))}
                    tool_result = await self.tool_executor.execute_tool(
                        "review_full_game",
                        tool_args,
                        context=context,
                    )
                    tool_calls = [{"tool": "review_full_game", "args": tool_args, "result": tool_result}]
                else:
                    tool_args = {
                        "username": username,
                        "platform": platform,
                        "count": 1,
                        "games_to_analyze": 1,
                        "depth": int(os.getenv("REVIEW_GAME_DEPTH", "14")),
                        "query": last_user_message,
                        "review_subject": "player",
                        "user_id": (context.get("user_id") if isinstance(context, dict) else None),
                    }
                    tool_result = await self.tool_executor.execute_tool(
                        "fetch_and_review_games",
                        tool_args,
                        context=context,
                    )
                    tool_calls = [{"tool": "fetch_and_review_games", "args": tool_args, "result": tool_result}]
            except Exception as ge:
                tool_result = {"success": False, "error": f"{type(ge).__name__}: {ge}"}
                tool_calls = [{"tool": "fetch_and_review_games", "args": {"username": username, "platform": platform}, "result": tool_result}]

            # Handle "need username/platform" (tool returns info_required)
            if isinstance(tool_result, dict) and tool_result.get("error") == "info_required":
                yield send_event(
                    "complete",
                    {
                        "content": tool_result.get("message") or "I need your username and platform (chess.com or lichess) to fetch your last game.",
                        "stop_reason": "game_review_info_required",
                        "ui_commands": [],
                        "tool_calls": tool_calls,
                        "baseline_intuition": None,
                        "explain_error": None,
                        "narrative_decision": {"core_message": "Game review needs account info.", "claims": [], "pattern_claims": [], "pattern_summary": None},
                        "envelope": None,
                    },
                )
                return

            # Pull key artifacts
            first_game = tool_result.get("first_game") if isinstance(tool_result, dict) else None
            first_game_review = tool_result.get("first_game_review") if isinstance(tool_result, dict) else None
            if not first_game_review and isinstance(tool_result, dict):
                first_game_review = tool_result.get("review")
            narrative = tool_result.get("narrative") if isinstance(tool_result, dict) else None

            game_pgn = ""
            if isinstance(first_game, dict) and isinstance(first_game.get("pgn"), str):
                game_pgn = first_game.get("pgn") or ""
            elif isinstance(first_game_review, dict) and isinstance(first_game_review.get("pgn"), str):
                game_pgn = first_game_review.get("pgn") or ""
            elif isinstance(ctx_pgn, str):
                game_pgn = ctx_pgn

            # Explain with facts (LLM)
            facts = {
                "chat_history": chat_history,
                "game_review": {
                    "source_tool": ("review_full_game" if (isinstance(ctx_pgn, str) and ctx_pgn.strip()) else "fetch_and_review_games"),
                    "narrative": narrative,
                    "stats": (tool_result.get("stats") if isinstance(tool_result, dict) else None),
                    "phase_stats": (tool_result.get("phase_stats") if isinstance(tool_result, dict) else None),
                    "opening_performance": (tool_result.get("opening_performance") if isinstance(tool_result, dict) else None),
                    "first_game_ref": (
                        {
                            "game_id": (first_game.get("game_id") if isinstance(first_game, dict) else None),
                            "platform": (first_game.get("platform") if isinstance(first_game, dict) else None),
                            "url": (first_game.get("url") if isinstance(first_game, dict) else None),
                            "date": (first_game.get("date") if isinstance(first_game, dict) else None),
                            "time_category": (first_game.get("time_category") if isinstance(first_game, dict) else None),
                            "time_control": (first_game.get("time_control") if isinstance(first_game, dict) else None),
                            "player_color": (first_game.get("player_color") if isinstance(first_game, dict) else None),
                            "result": (first_game.get("result") if isinstance(first_game, dict) else None),
                            "opponent_name": (first_game.get("opponent_name") if isinstance(first_game, dict) else None),
                            "opponent_rating": (first_game.get("opponent_rating") if isinstance(first_game, dict) else None),
                            "eco": (first_game.get("eco") if isinstance(first_game, dict) else None),
                            "opening": (first_game.get("opening") if isinstance(first_game, dict) else None),
                        }
                        if isinstance(first_game, dict)
                        else None
                    ),
                    "selected_key_moments": (tool_result.get("selected_key_moments") if isinstance(tool_result, dict) else None),
                    "selection_rationale": (tool_result.get("selection_rationale") if isinstance(tool_result, dict) else None),
                    # Keep PGN out of the explainer prompt to avoid 8k context overflows.
                    # The UI can still open the PGN in a new tab via ui_commands.
                },
            }

            res = await explain_with_facts(
                llm_router=self.llm_router,
                task_id=llm_session_id,
                user_message=last_user_message,
                context=context,
                facts=facts,
                model=model,
                temperature=temperature,
            )

            content = (res.get("explanation") if isinstance(res, dict) else "") or ""
            ui_commands = res.get("ui_commands", []) if isinstance(res, dict) else []

            # Default: open a review tab with the fetched PGN (non-destructive).
            try:
                if isinstance(game_pgn, str) and game_pgn.strip():
                    title = None
                    if isinstance(first_game, dict):
                        w = first_game.get("white")
                        b = first_game.get("black")
                        if w or b:
                            title = f"Last game: {w or 'White'} vs {b or 'Black'}"
                    if not isinstance(ui_commands, list):
                        ui_commands = []
                    ui_commands.append({"action": "new_tab", "params": {"type": "review", "pgn": game_pgn, "title": title or "Last game review"}})
            except Exception:
                pass
            
            # Merge UI commands from tools (e.g., set_ai_game)
            if ui_commands_from_tools:
                if not isinstance(ui_commands, list):
                    ui_commands = []
                ui_commands.extend(ui_commands_from_tools)
                ui_commands = _validate_and_filter_ui_commands(ui_commands)

            yield send_event(
                "complete",
                {
                    "content": content.strip(),
                    "stop_reason": "game_review_done",
                    "duration_s": round(time.time() - t0, 4),
                    "budgets": {"engine_calls": engine_calls, "llm_calls": llm_calls, "max_time_s": max_time_s},
                    "ui_commands": ui_commands,
                    "tool_calls": tool_calls,
                    "baseline_intuition": None,
                    "explain_error": (res.get("error") if isinstance(res, dict) else None),
                    "narrative_decision": {
                        "core_message": "Game review (last game).",
                        "claims": [
                            {
                                "summary": "Last game fetched + reviewed",
                                "claim_type": "game_review",
                                "connector": None,
                                "evidence_moves": [],
                                "evidence_source": "fetch_and_review_games",
                                "evidence_payload": {
                                    "first_game": first_game,
                                    "stats": (tool_result.get("stats") if isinstance(tool_result, dict) else None),
                                    "phase_stats": (tool_result.get("phase_stats") if isinstance(tool_result, dict) else None),
                                    "selected_key_moments": (tool_result.get("selected_key_moments") if isinstance(tool_result, dict) else None),
                                },
                            }
                        ],
                        "pattern_claims": [],
                        "pattern_summary": None,
                    },
                    "detected_intent": "game_review",
                    "envelope": None,
                },
            )
            return

        investigation_required = getattr(intent_plan, "investigation_required", False)
        print(f"   [CHAIN] [TASK_CONTROLLER] Step 2: Checking investigation requirement...")
        print(f"      [CHAIN] Investigation required: {investigation_required}")

        # Guardrail: if we have a concrete position (FEN) and the user is asking for
        # move advice / development / castling plans, we must go through engine-first
        # investigation even if the interpreter said "no investigation".
        # Only force engine investigation if the request actually includes a concrete position.
        # (Starting position counts as a valid position.)
        try:
            ctx_fen = (context or {}).get("fen") or (context or {}).get("board_state")
            has_fen = isinstance(ctx_fen, str) and bool(ctx_fen.strip())
        except Exception:
            has_fen = False

        # Baseline D2/D16 intuition is the default for DISCUSS/ANALYZE when a FEN is present.
        # IMPORTANT: This should be considered "already done" before the interactive controller work.
        # If main.py prefetched it into context, reuse it. Otherwise compute it here and then reset budget.
        baseline_intuition: Optional[Dict[str, Any]] = None
        try:
            ctx_mode = str((context or {}).get("mode") or "").upper().strip()
        except Exception:
            ctx_mode = ""
        if has_fen and ctx_mode in ("DISCUSS", "ANALYZE"):
            try:
                # Reuse prefetched baseline if present (main may attach it).
                try:
                    bi_prefetch = (context or {}).get("baseline_intuition") if isinstance(context, dict) else None
                except Exception:
                    bi_prefetch = None
                if isinstance(bi_prefetch, dict) and bi_prefetch:
                    baseline_intuition = bi_prefetch
                else:
                    baseline_intuition = None

                yield send_event(
                    "status",
                    {
                        "phase": "investigating",
                        "message": "Running baseline D2/D16 scans (two-pass)...",
                        "timestamp": time.time(),
                    },
                )
                await _sleep0()

                if baseline_intuition is None:
                    scan_pol = ScanPolicy(
                        d2_depth=int(os.getenv("SCAN_D2_DEPTH", "2")),
                        d16_depth=int(os.getenv("SCAN_D16_DEPTH", "16")),
                        branching_limit=int(os.getenv("SCAN_BRANCHING_LIMIT", "4")),
                        max_pv_plies=int(os.getenv("SCAN_MAX_PV_PLIES", "16")),
                        include_pgn=(str(os.getenv("SCAN_INCLUDE_PGN", "true")).lower().strip() == "true"),
                        pgn_max_chars=int(os.getenv("SCAN_PGN_MAX_CHARS", "12000")),
                        timeout_s=float(os.getenv("SCAN_TIMEOUT_S", "18")),
                    )
                    motif_pol = MotifPolicy(
                        max_pattern_plies=int(os.getenv("MOTIFS_MAX_PATTERN_PLIES", "4")),
                        motifs_top=int(os.getenv("MOTIFS_TOP", "25")),
                        max_line_plies=int(os.getenv("MOTIFS_MAX_LINE_PLIES", "10")),
                        max_branch_lines=int(os.getenv("MOTIFS_MAX_BRANCH_LINES", "12")),
                    )
                    baseline_pol = BaselineIntuitionPolicy(scan=scan_pol, motifs=motif_pol)
                    baseline_intuition = await run_baseline_intuition(
                        engine_pool_instance=self.engine_pool_instance,
                        engine_queue=self.engine_queue,
                        start_fen=fen,
                        policy=baseline_pol,
                    )
                yield send_event("milestone", {"name": "engine_deep_done", "timestamp": time.time()})
                await _sleep0()

                # Make baseline available to downstream steps (ModeRouter and prompt grounding).
                try:
                    if isinstance(context, dict) and isinstance(baseline_intuition, dict):
                        context["baseline_intuition"] = baseline_intuition
                except Exception:
                    pass

                # Reset budget timer AFTER baseline completes (or is reused), so we don't abort immediately.
                t_budget_start = time.time()
            except Exception as _bi_e:
                baseline_intuition = {"error": f"baseline_intuition_failed:{type(_bi_e).__name__}"}
                # Even on baseline failure, reset budget so we don't chain-abort for budget right after.
                t_budget_start = time.time()
        try:
            msg_l = (last_user_message or "").lower()
            wants_plan = bool(
                __import__("re").search(
                    r"\b(best move|what should i|what do i|how do i|how can i|next move|progress|plan|recommend|suggest|develop|development|castle|castling)\b",
                    msg_l,
                )
            )
        except Exception:
            wants_plan = False
        if (not investigation_required) and bool(has_fen) and bool(wants_plan):
            print("   [CHAIN] [TASK_CONTROLLER] Overriding interpreter: forcing engine investigation (position+plan request).")
            investigation_required = True

        if not investigation_required:
            # Fallback: Check if user is asking to open a previously selected game in a tab.
            # This handles cases where the interpreter didn't route to game_select (e.g., "bring it into a new tab").
            msg_l = (last_user_message or "").lower()
            wants_tab = any(w in msg_l for w in ["tab", "open", "load", "bring", "put"])
            if wants_tab:
                # Scan chat history for previous game_select tool calls.
                # Check both message.tool_calls and message.meta.tool_calls, and also check result payloads.
                selected_game_pgn = None
                selected_game_title = None
                try:
                    for m in reversed(request.messages or []):
                        if not isinstance(m, dict):
                            continue
                        # Check direct tool_calls field
                        tool_calls = m.get("tool_calls") or []
                        # Also check meta.tool_calls
                        meta = m.get("meta") or {}
                        if isinstance(meta, dict):
                            tool_calls.extend(meta.get("tool_calls") or [])
                        # Also check raw_data.tool_calls (frontend stores it there)
                        raw_data = m.get("raw_data") or {}
                        if isinstance(raw_data, dict):
                            tool_calls.extend(raw_data.get("tool_calls") or [])
                        # Also check if the message content itself contains a tool_calls reference
                        if not tool_calls and isinstance(m.get("content"), str):
                            # Try to extract from content if it's JSON
                            try:
                                import json
                                content_json = json.loads(m.get("content", ""))
                                if isinstance(content_json, dict):
                                    tool_calls.extend(content_json.get("tool_calls") or [])
                            except Exception:
                                pass
                        for tc in tool_calls:
                            if isinstance(tc, dict) and tc.get("tool") == "select_games":
                                result = tc.get("result")
                                if isinstance(result, dict):
                                    selected = result.get("selected") or {}
                                    # Find the first available game with PGN.
                                    for arr in selected.values():
                                        if isinstance(arr, list) and arr:
                                            g = arr[0] if isinstance(arr[0], dict) else None
                                            if isinstance(g, dict):
                                                pgn = g.get("pgn")
                                                if isinstance(pgn, str) and pgn.strip():
                                                    selected_game_pgn = pgn.strip()
                                                    date = g.get("date") or ""
                                                    tc_cat = g.get("time_category") or ""
                                                    opp = g.get("opponent_name") or ""
                                                    selected_game_title = f"{date} {tc_cat} vs {opp}".strip() or "Selected game"
                                                    break
                                if selected_game_pgn:
                                    break
                        if selected_game_pgn:
                            break
                except Exception as e:
                    import traceback
                    print(f"[TASK_CONTROLLER] Error scanning chat history for game_select: {e}")
                    traceback.print_exc()
                if selected_game_pgn:
                    ui_commands = [{"action": "new_tab", "params": {"type": "review", "pgn": selected_game_pgn, "title": selected_game_title}}]
                    yield send_event(
                        "complete",
                        {"content": "Opened it in a new tab.", "ui_commands": ui_commands, "stop_reason": "open_game_tab", "baseline_intuition": baseline_intuition},
                    )
                    return
            
            _t_skill = time.time()
            res = await self._answer_general_chat(
                task_id=task_id,
                user_message=last_user_message,
                context=context,
                model=model,
                temperature=temperature,
            )
            content = res.get("explanation", "")
            ui_commands = res.get("ui_commands", [])
            # Baseline intuition is included in response_data for UI display (tabs), not prepended to text.
            try:
                if _pt:
                    _pt.record_skill("chat_answer", time.time() - _t_skill)
                    _pt.record_stop_reason("no_investigation_required")
            except Exception:
                pass
            yield send_event(
                "complete",
                {"content": content, "ui_commands": ui_commands, "stop_reason": "no_investigation_required", "baseline_intuition": baseline_intuition},
            )
            return

        # Judge-loop: compare moves (cheap) when explicitly requested.
        try:
            goal_str = str(getattr(intent_plan, "goal", "") or "").lower()
        except Exception:
            goal_str = ""
        if "compare" in goal_str and "move" in goal_str:
            try:
                # Try to extract moves from investigation_requests focus fields (preferred)
                reqs = getattr(intent_plan, "investigation_requests", None)
                focuses = []
                if isinstance(reqs, list):
                    for r in reqs:
                        f = getattr(r, "focus", None)
                        if isinstance(f, str) and f.strip():
                            focuses.append(f.strip())
                focuses = focuses[:2]

                # Fallback: use first two SAN-like tokens from message
                if len(focuses) < 2:
                    import re
                    toks = re.findall(r"\b(O-O-O|O-O|[KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]?)\b", last_user_message)
                    for t in toks:
                        if t not in focuses:
                            focuses.append(t)
                        if len(focuses) >= 2:
                            break

                if len(focuses) >= 2:
                    stop_now = _should_stop()
                    if stop_now:
                        yield send_event("complete", {"content": "Time budget exceeded.", "stop_reason": stop_now})
                        return
                    comp = await compare_moves(
                        tool_executor=self.tool_executor,
                        context=context,
                        fen=fen,
                        moves_san=focuses[:2],
                        depth=int(os.getenv("COMPARE_DEPTH", "10")),
                    )
                    engine_calls += 2
                    judged = judge_compare_moves(comp)
                    facts = {
                        "compare": comp,
                        "judgment": judged,
                    }
                    yield send_event("milestone", {"name": "engine_light_done", "timestamp": time.time()})
                    await _sleep0()
                    llm_calls += 1
                    res = await explain_with_facts(
                        llm_router=self.llm_router,
                        task_id=task_id,
                        user_message=last_user_message,
                        context=context,
                        facts=facts,
                        model=model,
                        temperature=temperature,
                    )
                    content = res.get("explanation", "")
                    ui_commands = res.get("ui_commands", [])
                    yield send_event("milestone", {"name": "final_ready", "timestamp": time.time()})
                    await _sleep0()
                    yield send_event(
                        "complete",
                        {
                            "content": (content or "").strip(),
                            "stop_reason": "judge_compare_moves",
                            "ui_commands": ui_commands,
                            "envelope": AnswerEnvelope(
                                facts_card=self.facts_assembler.from_light_result(fen=fen, light_result={}),
                                explanation=(content or "").strip(),
                                ui_commands=ui_commands,
                                stop_reason="judge_compare_moves",
                            ).model_dump(),
                        },
                    )
                    try:
                        if _pt:
                            _pt.record_stop_reason("judge_compare_moves")
                    except Exception:
                        pass
                    return
            except Exception:
                pass

        # Investigation required: run deterministic per-mode investigation policy.
        print(f"   [CHAIN] [TASK_CONTROLLER] Step 3: Starting investigation phase...")
        try:
            # If user explicitly names moves to investigate (e.g., "what if Nf3?"),
            # run D2/D16 scans from the resulting positions (tool-like behavior).
            move_scans = []
            try:
                import re
                toks = re.findall(r"\b(O-O-O|O-O|[KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]?)\b", last_user_message or "")
                # De-dupe and cap.
                cand_moves = []
                for t in toks:
                    if t not in cand_moves:
                        cand_moves.append(t)
                    if len(cand_moves) >= 2:
                        break
                # Heuristic trigger: "what if"/"instead"/"compare"/"investigate" in message.
                trigger = any(x in (last_user_message or "").lower() for x in ["what if", "instead", "compare", "investigat", "line for", "variation for"])
                if trigger and cand_moves:
                    pol = ScanPolicy(
                        d2_depth=int(os.getenv("SCAN_D2_DEPTH", "2")),
                        d16_depth=int(os.getenv("SCAN_D16_DEPTH", "16")),
                        branching_limit=int(os.getenv("SCAN_BRANCHING_LIMIT", "2")),
                        max_pv_plies=int(os.getenv("SCAN_MAX_PV_PLIES", "10")),
                        include_pgn=False,  # keep this lightweight for per-move investigations
                        pgn_max_chars=0,
                        timeout_s=float(os.getenv("SCAN_TIMEOUT_S", "18")),
                    )
                    for mv in cand_moves:
                        try:
                            s = await scan_d2_d16_after_san(
                                engine_pool_instance=self.engine_pool_instance,
                                engine_queue=self.engine_queue,
                                start_fen=fen,
                                move_san=mv,
                                policy=pol,
                            )
                            move_scans.append(s)
                        except Exception:
                            continue
            except Exception:
                move_scans = []

            # Optional explicit scan trigger (Cursor-like "run a scan" behavior).
            scan_enabled = str(os.getenv("ENABLE_CONTROLLER_SCAN", "false")).lower().strip() == "true"
            scan_mentioned = "scan" in (last_user_message or "").lower()
            print(f"      [CHAIN] Scan mode check: enabled={scan_enabled}, mentioned={scan_mentioned}")
            if scan_enabled and scan_mentioned:
                pol = ScanPolicy(
                    d2_depth=int(os.getenv("SCAN_D2_DEPTH", "2")),
                    d16_depth=int(os.getenv("SCAN_D16_DEPTH", "16")),
                    branching_limit=int(os.getenv("SCAN_BRANCHING_LIMIT", "4")),
                    max_pv_plies=int(os.getenv("SCAN_MAX_PV_PLIES", "16")),
                    include_pgn=(str(os.getenv("SCAN_INCLUDE_PGN", "true")).lower().strip() == "true"),
                    pgn_max_chars=int(os.getenv("SCAN_PGN_MAX_CHARS", "8000")),
                    timeout_s=float(os.getenv("SCAN_TIMEOUT_S", "18")),
                )
                scan_out = await scan_d2_d16_from_fen(
                    engine_pool_instance=self.engine_pool_instance,
                    engine_queue=self.engine_queue,
                    start_fen=fen,
                    policy=pol,
                )
                yield send_event("milestone", {"name": "engine_deep_done", "timestamp": time.time()})
                await _sleep0()
                res = await explain_with_facts(
                    llm_router=self.llm_router,
                    task_id=task_id,
                    user_message=last_user_message,
                    context=context,
                    facts={"scan": scan_out},
                    model=model,
                    temperature=temperature,
                )
                content = res.get("explanation", "")
                ui_commands = res.get("ui_commands", [])
                # Baseline intuition is included in response_data for UI display (tabs), not prepended to text.
                yield send_event(
                    "complete",
                    {
                        "content": (content or "").strip(),
                        "stop_reason": "controller_scan",
                        "ui_commands": ui_commands,
                        "baseline_intuition": baseline_intuition,
                        "envelope": AnswerEnvelope(
                            facts_card=self.facts_assembler.from_light_result(fen=fen, light_result={}),
                            explanation=(content or "").strip(),
                            ui_commands=ui_commands,
                            stop_reason="controller_scan",
                        ).model_dump(),
                    },
                )
                return

            policy = self.mode_router.policy_for(context=context, intent_plan=intent_plan, user_message=last_user_message)
            # Align controller budget helper with policy.
            max_time_s = policy.max_time_s

            stop_now = _should_stop()
            if stop_now:
                print(f"   ⚠️ [CHAIN] [TASK_CONTROLLER] Time budget exceeded before engine eval")
                yield send_event("complete", {"content": "Time budget exceeded.", "stop_reason": stop_now})
                return

            print(f"   [CHAIN] [TASK_CONTROLLER] Step 4: Running engine investigation under policy...")
            print(
                f"      [CHAIN] Mode={policy.name} depth={policy.light_depth} lines={policy.light_lines} "
                f"compare={policy.compare_enabled} compare_depth={policy.compare_depth}"
            )

            inv = await self.mode_router.run_investigation(
                policy=policy,
                fen=fen,
                context=context,
                user_message=last_user_message,
                evaluate_position_fn=evaluate_position,
                compare_moves_fn=compare_moves,
                judge_compare_moves_fn=judge_compare_moves,
                send_event=send_event,
                engine_queue=self.engine_queue,
                engine_pool_instance=self.engine_pool_instance,
                tool_executor=self.tool_executor,
                enable_facts_ready_event=(str(os.getenv("ENABLE_FACTS_READY_EVENT", "true")).lower().strip() == "true"),
                # Align ModeRouter's compare budget checks with controller budget (post-baseline).
                t0=t_budget_start,
            )

            for ev in (inv.get("events") or []):
                try:
                    yield ev
                    await _sleep0()
                except Exception:
                    pass

            res = inv.get("result") if isinstance(inv, dict) else None
            res = res if isinstance(res, dict) else {}
            light_result = res.get("light_result")
            chosen_move = res.get("chosen_move")
            chosen_reason = res.get("chosen_reason") or ""
            compare_out = res.get("compare_out")
            judge_out = res.get("judge_out")

            engine_calls += 1
            evidence.engine["analysis"] = light_result
            if compare_out and judge_out:
                evidence.engine["move_compare"] = {"compare": compare_out, "judgment": judge_out}
        except Exception as e:
            print(f"   ❌ [CHAIN] [TASK_CONTROLLER] Engine evaluation failed: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            # If engine evaluation fails, fall back to chat response.
            res = await self._answer_general_chat(
                task_id=task_id,
                user_message=last_user_message,
                context=context,
                model=model,
                temperature=temperature,
            )
            content = res.get("explanation", "")
            ui_commands = res.get("ui_commands", [])
            yield send_event("complete", {"content": content, "ui_commands": ui_commands, "stop_reason": f"engine_eval_failed:{str(e)[:80]}"})
            return

        # Canonical recommendation: if baseline D16 best move exists, it wins.
        # This prevents mismatches like "best_move=h3" but claim says "play d4".
        try:
            bi = baseline_intuition if isinstance(baseline_intuition, dict) else None
            root = ((bi or {}).get("scan_root") or {}).get("root") if isinstance(bi, dict) else None
            best_d16 = (root or {}).get("best_move_d16_san") if isinstance(root, dict) else None
            if isinstance(best_d16, str) and best_d16.strip():
                if not chosen_move or str(chosen_move).strip() != best_d16.strip():
                    chosen_move = best_d16.strip()
                    chosen_reason = "baseline_best_move_d16"
        except Exception:
            pass

        # ModeRouter already handled candidate selection + optional compare + facts_ready emission.

        # Self-check: decide if we should stop or escalate.
        print(f"   [CHAIN] [TASK_CONTROLLER] Step 5: Running self-check...")
        try:
            llm_calls += 1
            sc = await self_check(
                llm_router=self.llm_router,
                task_id=task_id,
                goal={
                    "objective": goal.objective,
                    "confidence_required": goal.confidence_required,
                },
                evidence={"engine": evidence.engine, "chess": evidence.chess, "llm": evidence.llm},
                model=model,
            )
            print(f"      [CHAIN] Self-check result: {sc}")
        except Exception as sc_e:
            print(f"      ⚠️ [CHAIN] Self-check failed: {type(sc_e).__name__}: {sc_e}")
            sc = {}

        confidence = sc.get("confidence") if isinstance(sc, dict) else None
        missing = sc.get("missing_artifacts") if isinstance(sc, dict) else None
        stop = bool(sc.get("stop")) if isinstance(sc, dict) and "stop" in sc else False
        stop_reason = sc.get("stop_reason") if isinstance(sc, dict) else None
        print(f"      [CHAIN] Confidence: {confidence}, Stop: {stop}, Reason: {stop_reason}")
        if missing:
            print(f"      [CHAIN] Missing artifacts: {missing}")

        # Stop rule: if self-check is sufficiently confident, avoid extra work.
        try:
            conf_th = float(os.getenv("STOP_CONFIDENCE_THRESHOLD", "0.72"))
        except Exception:
            conf_th = 0.72
        if isinstance(confidence, (int, float)) and confidence >= conf_th and not stop:
            stop = True
            stop_reason = stop_reason or "high_confidence"

        # Simple escalation: if not stopping and confidence_required is high, run deeper engine eval
        # (ModeRouter policy controls whether we do this).
        if not stop and goal.confidence_required == "high":
            print(f"   [CHAIN] [TASK_CONTROLLER] Step 6: Escalating to deep engine eval (high confidence required)...")
            try:
                stop_now = _should_stop()
                if stop_now:
                    print(f"      ⚠️ [CHAIN] Time budget exceeded before deep eval")
                    yield send_event("complete", {"content": "Time budget exceeded.", "stop_reason": stop_now})
                    return
                # Keep env overrides, but ModeRouter chooses the per-mode defaults.
                try:
                    policy2 = self.mode_router.policy_for(context=context, intent_plan=intent_plan, user_message=last_user_message)
                    depth2 = int(getattr(policy2, "deep_depth", 16))
                    lines2 = int(getattr(policy2, "deep_lines", 3))
                except Exception:
                    depth2 = int(os.getenv("ENGINE_DEEP_DEPTH", "16"))
                    lines2 = int(os.getenv("ENGINE_DEEP_LINES", "3"))
                print(f"      [CHAIN] Deep eval params: depth={depth2}, lines={lines2}")
                deep_result = await evaluate_position(
                    tool_executor=self.tool_executor,
                    context=context,
                    engine_queue=self.engine_queue,
                    engine_pool_instance=self.engine_pool_instance,
                    depth=depth2,
                    lines=lines2,
                    light_mode=False,
                )
                engine_calls += 1
                print(f"      [CHAIN] Deep eval complete: eval_cp={deep_result.get('eval_cp') if isinstance(deep_result, dict) else 'N/A'}")
                evidence.engine["analysis_deep"] = deep_result
                yield send_event("milestone", {"name": "engine_deep_done", "timestamp": time.time()})
                await _sleep0()
            except Exception as deep_e:
                print(f"      ⚠️ [CHAIN] Deep eval failed: {type(deep_e).__name__}: {deep_e}")
                pass

        # Minimal "facts card" (keep small)
        print(f"   [CHAIN] [TASK_CONTROLLER] Step 7: Building facts card for explanation...")
        top_moves = None
        try:
            if isinstance(light_result, dict):
                top_moves = light_result.get("top_moves")
        except Exception:
            top_moves = None
        # Canonical FactsCard (engine-first artifact)
        facts_card = None
        try:
            if isinstance(light_result, dict):
                # Fast tag/theme analysis for justification (50-150ms target).
                light_raw = None
                try:
                    lra = compute_light_raw_analysis(fen)
                    light_raw = lra.to_dict() if hasattr(lra, "to_dict") else None
                except Exception:
                    light_raw = None
                facts_card = self.facts_assembler.from_light_result(
                    fen=fen,
                    light_result=light_result,
                    light_raw=light_raw,
                )
                try:
                    facts_card.confidence_signals = compute_confidence_signals(facts_light=light_result, facts_deep=(deep_result if isinstance(deep_result, dict) else None))
                except Exception:
                    pass
        except Exception:
            facts_card = None

        # Back-compat facts dict for existing explain_with_facts prompt shape.
        facts = {
            "eval_cp": (light_result.get("eval_cp") if isinstance(light_result, dict) else None),
            "candidate_moves": (light_result.get("candidate_moves") if isinstance(light_result, dict) else None),
            "top_moves": (top_moves if isinstance(top_moves, list) else None),
            "from_cache": bool(light_result.get("from_cache")) if isinstance(light_result, dict) else False,
            "self_check": {"confidence": confidence, "missing_artifacts": missing, "stop_reason": stop_reason},
            "facts_card": (facts_card.model_dump() if facts_card else None),
            "chat_history": chat_history,
        }
        # Attach any explicit per-move D2/D16 scans requested by the user.
        try:
            if isinstance(move_scans, list) and move_scans:
                facts["move_scans"] = move_scans[:2]
        except Exception:
            pass
        # Add a compact baseline bundle for grounding (D2/D16 + PGN + claims + patterns),
        # while keeping the full baseline_intuition only in the response payload for UI tabs.
        try:
            bi = baseline_intuition if isinstance(baseline_intuition, dict) else None
            scan_root = (bi or {}).get("scan_root") if isinstance(bi, dict) else None
            if isinstance(scan_root, dict):
                facts["baseline"] = {
                    "root": scan_root.get("root") or {},
                    "evidence": (scan_root.get("evidence") or {}) if isinstance(scan_root.get("evidence"), dict) else {},
                    # Keep PGN available to the LLM, but bounded.
                    "pgn_exploration": (scan_root.get("pgn_exploration") or "")[: int(os.getenv("BASELINE_PGN_PROMPT_MAX_CHARS", "1200"))],
                    "claims": (scan_root.get("claims") or [])[:12] if isinstance(scan_root.get("claims"), list) else [],
                    "pattern_claims": (scan_root.get("pattern_claims") or [])[:12] if isinstance(scan_root.get("pattern_claims"), list) else [],
                    "motifs": (scan_root.get("motifs") or [])[:8] if isinstance(scan_root.get("motifs"), list) else [],
                }
        except Exception:
            pass
        if chosen_move:
            facts["recommended_move"] = chosen_move
            facts["recommended_reason"] = chosen_reason
        if compare_out and judge_out:
            facts["move_compare"] = {"compare": compare_out, "judgment": judge_out}
        print(f"      [CHAIN] Facts card: eval_cp={facts.get('eval_cp')}, top_moves_count={len(facts.get('top_moves', []))}")

        # Evidence pack: concrete citeable examples for any claims/tags (deterministic, engine-first).
        try:
            ev = await build_evidence_pack(
                fen=fen,
                facts_card=(facts_card.model_dump() if facts_card else None),
                light_raw=(light_raw if isinstance(light_raw, dict) else None),
                user_message=last_user_message,
                engine_queue=self.engine_queue,
                engine_pool_instance=self.engine_pool_instance,
                dev_depth=int(os.getenv("DEV_COUNTERFACTUAL_DEPTH", "10")),
            )
            if isinstance(ev, dict):
                facts["evidence"] = ev
        except Exception as e:
            print(f"   ⚠️ [CHAIN] [TASK_CONTROLLER] Evidence builder failed: {type(e).__name__}: {e}")

        # Attach compressed memory (if any) for continuity.
        try:
            prior_mem = self.llm_router.get_task_memory(task_id=task_id, subsession="main")
            if prior_mem:
                facts["memory"] = prior_mem
                print(f"      [CHAIN] Attached prior memory (compressed)")
        except Exception as mem_e:
            print(f"      [CHAIN] Could not retrieve prior memory: {mem_e}")

        print(f"   [CHAIN] [TASK_CONTROLLER] Step 8: Generating explanation from facts...")
        # Always run a short justification writer (LLM) to turn evidence into a human story.
        # This stays evidence-locked: it must only use provided facts/lines/examples.
        try:
            just = await justify_from_evidence(
                llm_router=self.llm_router,
                task_id=llm_session_id,
                user_message=last_user_message,
                facts=facts,
                model=model,
                temperature=temperature,
            )
            if isinstance(just, dict) and just:
                facts["justification"] = just
        except Exception as je:
            print(f"   ⚠️ [CHAIN] [TASK_CONTROLLER] Justify step failed: {type(je).__name__}: {je}")

        res = await explain_with_facts(
            llm_router=self.llm_router,
            task_id=llm_session_id,
            user_message=last_user_message,
            context=context,
            facts=facts,
            model=model,
            temperature=temperature,
        )
        explain_error = res.get("error") if isinstance(res, dict) else None
        content = res.get("explanation", "")
        # Aggregate commands from justification and final explanation
        ui_commands = []
        just_commands = facts.get("justification", {}).get("ui_commands", [])
        if isinstance(just_commands, list):
            ui_commands.extend(just_commands)
        
        expl_commands = res.get("ui_commands", [])
        if isinstance(expl_commands, list):
            ui_commands.extend(expl_commands)
            
        print(f"      [CHAIN] Explanation generated: {len(content or '')} chars, {len(ui_commands)} commands")

        # Validate and filter UI commands before passing to AnswerEnvelope
        ui_commands = _validate_and_filter_ui_commands(ui_commands)
        if len(ui_commands) < len(just_commands) + len(expl_commands if isinstance(expl_commands, list) else []):
            print(f"      [CHAIN] Filtered UI commands: {len(ui_commands)} valid commands (some were invalid)")

        # IMPORTANT: Board mutation commands are powerful.
        # Policy: controlled by mode or explicit context flag (no phrase matching).
        try:
            mode = (context.get("mode") or "").upper()
            allow_mutations = bool(mode == "PLAY" or context.get("allow_ui_mutations") is True)
            mutating = {"push_move", "set_fen", "set_pgn", "load_position", "delete_move", "delete_variation", "promote_variation"}
            if not allow_mutations and isinstance(ui_commands, list):
                ui_commands = [
                    c
                    for c in ui_commands
                    if not (isinstance(c, dict) and (c.get("action") in mutating))
                ]
        except Exception:
            pass

        # NOTE: No post-processing that forces a PV/line into the text.
        # If the LLM includes a line, it should be because it's needed for a specific claim.

        # Baseline intuition is included in response_data for UI display (tabs), not prepended to text.

        # Deterministic grounding verification (best-effort).
        try:
            ok, issues = self.verifier.verify(
                fen=fen,
                facts={"top_moves": (top_moves if isinstance(top_moves, list) else [])},
                recommended_move=(chosen_move if isinstance(chosen_move, str) else None),
                explanation=(content or ""),
            )
            if not ok:
                print(f"   ⚠️ [CHAIN] [TASK_CONTROLLER] Verification issues: {issues}")
                # Hard rule: if recommended move is ungrounded, remove it from envelope.
                if "recommended_move_not_in_candidates" in issues:
                    chosen_move = None
                    chosen_reason = "verifier_removed_ungrounded_recommendation"
        except Exception as ve:
            print(f"   ⚠️ [CHAIN] [TASK_CONTROLLER] Verifier failed: {type(ve).__name__}: {ve}")

        yield send_event("milestone", {"name": "final_ready", "timestamp": time.time()})
        await _sleep0()

        # Merge UI commands from tools (e.g., set_ai_game) with commands from LLM
        final_ui_commands = list(ui_commands) if isinstance(ui_commands, list) else []
        if ui_commands_from_tools:
            final_ui_commands.extend(ui_commands_from_tools)
        final_ui_commands = _validate_and_filter_ui_commands(final_ui_commands)
        
        yield send_event(
            "complete",
            {
                "content": (content or "").strip(),
                "stop_reason": stop_reason or ("engine_light_then_explain" if stop else "engine_light_then_explain_no_stop"),
                "duration_s": round(time.time() - t0, 4),
                "budgets": {"engine_calls": engine_calls, "llm_calls": llm_calls, "max_time_s": max_time_s},
                "ui_commands": final_ui_commands,
                "baseline_intuition": baseline_intuition,
                "explain_error": explain_error,
                # Populate a minimal narrative_decision-like object for the existing Evidence UI
                # (claims + pattern_claims), without using the legacy 4-layer summariser/explainer.
                "narrative_decision": (lambda _bi: (
                    (lambda _sr: (
                        (lambda _raw_claims, _pattern_claims: (
                            (lambda _ui_claims: (
                                {
                                    "core_message": ("Engine baseline (D2/D16) + evidence-locked claims and patterns." if _bi else "Engine baseline."),
                                    "mechanism": "",
                                    # Normalize baseline claims into the UI claim schema expected by MessageBubble:
                                    # {summary, claim_type, connector, evidence_moves, evidence_source, evidence_payload}
                                    "claims": _ui_claims,
                                    "pattern_claims": _pattern_claims,
                                    "pattern_summary": None,
                                    "emphasis": [],
                                    "psychological_frame": "",
                                    "verbosity": "medium",
                                    "suppress": [],
                                }
                            ))([
                                (lambda c: (
                                    {
                                        "summary": (
                                            (c.get("statement") or c.get("summary"))
                                            if isinstance((c.get("statement") or c.get("summary")), str)
                                            else str(c.get("claim_type") or c.get("type") or "claim")
                                        ),
                                        "claim_type": (c.get("claim_type") or c.get("type") or "claim"),
                                        "connector": None,
                                        "evidence_moves": (
                                            (c.get("support") or {}).get("moves")
                                            if isinstance(c.get("support"), dict) and isinstance((c.get("support") or {}).get("moves"), list)
                                            else []
                                        ),
                                        "evidence_source": (
                                            (c.get("evidence_ref") or {}).get("source")
                                            if isinstance(c.get("evidence_ref"), dict)
                                            else None
                                        ),
                                        "evidence_payload": (c.get("support") if isinstance(c.get("support"), dict) else {}),
                                    }
                                ))(c) for c in (_raw_claims if isinstance(_raw_claims, list) else []) if isinstance(c, dict)
                            ])
                        ))(
                            (_sr.get("claims") if isinstance(_sr, dict) else []),
                            (_sr.get("pattern_claims") if isinstance(_sr, dict) else []),
                        )
                    ))((( _bi or {}).get("scan_root") if isinstance(_bi, dict) else None))
                ))(baseline_intuition if isinstance(baseline_intuition, dict) else None),
                "envelope": (
                    AnswerEnvelope(
                        facts_card=(facts_card or self.facts_assembler.from_light_result(fen=fen, light_result=light_result if isinstance(light_result, dict) else {})),
                        recommended_move=(chosen_move if isinstance(chosen_move, str) else None),
                        alternatives=[],
                        explanation=(content or "").strip(),
                        ui_commands=_validate_and_filter_ui_commands(ui_commands),
                        confidence=(float(confidence) if isinstance(confidence, (int, float)) else None),
                        stop_reason=str(stop_reason or ""),
                        budgets={"engine_calls": engine_calls, "llm_calls": llm_calls, "max_time_s": max_time_s},
                        artifacts_used=["engine:light", "llm:explain_with_facts"],
                    ).model_dump()
                    if facts_card or isinstance(light_result, dict)
                    else None
                ),
            },
        )
        try:
            if _pt:
                _pt.record_stop_reason(stop_reason or ("engine_light_then_explain" if stop else "engine_light_then_explain_no_stop"))
        except Exception:
            pass

        # Compress and persist task memory after completion (best-effort).
        try:
            current_memory = self.llm_router.get_task_memory(task_id=task_id, subsession="main")
            mem = await compress_memory(
                llm_router=self.llm_router,
                task_id=task_id,
                subsession="memory",
                current_memory=current_memory,
                evidence={"engine": evidence.engine, "chess": evidence.chess, "llm": evidence.llm},
                stop_reason=str(stop_reason or ""),
                model=model,
            )
            if isinstance(mem, dict):
                self.llm_router.set_task_memory(task_id=task_id, subsession="main", memory=mem)
        except Exception:
            pass
        return


async def _sleep0():
    # micro-yield helper to flush SSE
    import asyncio
    await asyncio.sleep(0)


def _ensure_example_present(text: str, *, facts: Dict[str, Any]) -> str:
    t = (text or "").strip()
    if not t:
        return t
    if "For example" in t or "Example:" in t:
        return t

    ev = facts.get("evidence") if isinstance(facts, dict) else None
    if isinstance(ev, dict):
        te = ev.get("tag_examples")
        if isinstance(te, list) and te:
            first = te[0]
            if isinstance(first, dict):
                sent = first.get("sentence")
                if isinstance(sent, str) and sent.strip():
                    return t + "\n" + sent.strip()
        dc = ev.get("development_counterfactuals")
        if isinstance(dc, list) and dc:
            d0 = dc[0]
            if isinstance(d0, dict):
                mv = d0.get("move")
                delta = d0.get("delta_cp_vs_best")
                line = d0.get("line_san")
                if isinstance(mv, str) and mv.strip() and isinstance(line, str) and line.strip():
                    if isinstance(delta, (int, float)):
                        return t + f"\nFor example, if you try {mv.strip()} immediately, it scores worse by {int(delta)}cp: {line.strip()}"
                    return t + f"\nFor example, if you try {mv.strip()} immediately, it leads to a worse position: {line.strip()}"

    return t + "\nExample: (not available in facts)"


def _extract_recommended_line_from_facts(facts: Dict[str, Any]) -> str:
    """
    Deterministically extract a recommended PV line from FactsCard/top_moves, without any LLM.
    """
    fc = facts.get("facts_card") if isinstance(facts.get("facts_card"), dict) else None
    top = None
    if isinstance(fc, dict) and isinstance(fc.get("top_moves"), list):
        top = fc.get("top_moves")
    elif isinstance(facts.get("top_moves"), list):
        top = facts.get("top_moves")
    rec = facts.get("recommended_move") if isinstance(facts.get("recommended_move"), str) else None

    def _join(pv_san):
        if not isinstance(pv_san, list):
            return ""
        moves = [m.strip() for m in pv_san[:10] if isinstance(m, str) and m.strip()]
        return " ".join(moves).strip()

    if isinstance(top, list):
        if rec:
            for tm in top[:4]:
                if not isinstance(tm, dict):
                    continue
                san = tm.get("san") or tm.get("move_san")
                if isinstance(san, str) and san.strip() == rec.strip():
                    line = _join(tm.get("pv_san"))
                    if line:
                        return line
        for tm in top[:2]:
            if not isinstance(tm, dict):
                continue
            line = _join(tm.get("pv_san"))
            if line:
                return line
    return ""


def _ensure_line_is_natural(text: str, *, facts: Dict[str, Any]) -> str:
    """
    Ensure any required PV line is included and phrased naturally (no standalone 'Line:' label).
    """
    t = (text or "").strip()
    if not t:
        return t

    low = t.lower()
    # If there's already a natural line sentence, keep it.
    if ("a clean line is" in low) or ("one concrete continuation is" in low):
        return t

    # If model used legacy "Line:", rewrite it.
    if "Line:" in t:
        t = t.replace("Line:", "A clean line is:")
        return t.strip()

    # Otherwise append one deterministically if we have it.
    line = _extract_recommended_line_from_facts(facts)
    if line:
        return (t + "\nA clean line is: " + line).strip()
    return (t + "\nA clean line is not available in the facts.").strip()


def _ensure_worded_pv_present(text: str, *, facts: Dict[str, Any]) -> str:
    """
    Ensure the response includes the worded PV (move — why) when available.
    Does NOT enforce any fixed prefix strings.
    """
    t = (text or "").strip()
    if not t:
        return t
    just = facts.get("justification") if isinstance(facts, dict) else None
    wpv = just.get("worded_pv") if isinstance(just, dict) else None
    if not isinstance(wpv, list) or not wpv:
        return t

    # If at least one PV move token already appears, assume it's included.
    try:
        first_mv = wpv[0].get("move") if isinstance(wpv[0], dict) else None
        if isinstance(first_mv, str) and first_mv.strip() and first_mv.strip() in t:
            return t
    except Exception:
        pass

    lines = []
    for it in wpv[:4]:
        if not isinstance(it, dict):
            continue
        mv = it.get("move")
        why = it.get("why")
        if isinstance(mv, str) and mv.strip() and isinstance(why, str) and why.strip():
            lines.append(f"{mv.strip()} — {why.strip()}")
    if not lines:
        return t
    return (t + "\n" + "\n".join(lines)).strip()


