"""
Executor - Works through ExecutionPlan steps sequentially.
Simple executor that processes steps one by one and emits SSE events.
"""

import time
import asyncio
import sys
from typing import Dict, Any, Optional, Callable, List
import re
import chess
from planner import ExecutionPlan, ExecutionStep
from investigator import Investigator, InvestigationResult


class Executor:
    """
    Executes ExecutionPlan steps sequentially.
    Works through the simple ordered list one by one.
    """
    
    def __init__(self, engine_queue=None, engine_pool=None, openai_client=None, sse_callback: Optional[Callable] = None):
        self.engine_queue = engine_queue
        self.engine_pool = engine_pool
        self.openai_client = openai_client
        # Use engine_pool if available, otherwise fall back to engine_queue
        self.investigator = Investigator(engine_queue=engine_queue, engine_pool=engine_pool)
        self.results: Dict[int, Any] = {}  # step_number -> result
        self.sse_callback = sse_callback  # Callback to emit SSE events
    
    def _emit_event(self, event_type: str, data: Dict[str, Any]):
        """Emit SSE event via callback"""
        if self.sse_callback:
            try:
                self.sse_callback(event_type, data)
            except Exception as e:
                print(f"   ⚠️ Error emitting SSE event {event_type}: {e}")

    def _get_step_result(self, step_number: int) -> Any:
        return self.results.get(step_number)

    def _resolve_fen(self, params: Dict[str, Any], context_fen: Optional[str]) -> Optional[str]:
        """
        Resolve a FEN from either direct `fen` or `fen_ref`.
        Supported refs:
        - "root" -> context_fen
        - "step:N.end_fen" -> prior step dict key or InvestigationResult.evidence_end_fen or InvestigationResult.goal_search_results.get("end_fen")
        - "step:N.<key>" -> dict key
        """
        if not isinstance(params, dict):
            return context_fen
        if params.get("fen"):
            return params.get("fen")
        fen_ref = params.get("fen_ref")
        if not fen_ref:
            return context_fen
        if fen_ref == "root":
            return context_fen
        if isinstance(fen_ref, str) and fen_ref.startswith("state:"):
            name = fen_ref.split(":", 1)[1]
            return getattr(self, "_state_slots", {}).get(name) or context_fen
        m = re.match(r"^step:(\d+)\.(.+)$", str(fen_ref))
        if not m:
            return context_fen
        step_num = int(m.group(1))
        key = m.group(2)
        prev = self._get_step_result(step_num)
        if isinstance(prev, InvestigationResult):
            if key == "end_fen":
                return getattr(prev, "evidence_end_fen", None) or (getattr(prev, "goal_search_results", {}) or {}).get("end_fen")
            # fallback: try goal_search_results or other fields
            return (getattr(prev, "goal_search_results", {}) or {}).get(key) or getattr(prev, key, None)
        if isinstance(prev, dict):
            return prev.get(key)
        return context_fen

    def _resolve_ref_value(self, ref: str) -> Any:
        """
        Resolve references:
        - state:NAME -> stored fen
        - step:N.key -> dict key or InvestigationResult attribute/consequence
        - step:N.goal_search_results.key -> InvestigationResult.goal_search_results[key]
        """
        if not ref or not isinstance(ref, str):
            return None
        if ref.startswith("state:"):
            name = ref.split(":", 1)[1]
            return getattr(self, "_state_slots", {}).get(name)
        m = re.match(r"^step:(\d+)\.(.+)$", ref)
        if not m:
            return None
        step_num = int(m.group(1))
        path = m.group(2)
        prev = self._get_step_result(step_num)
        if isinstance(prev, InvestigationResult):
            if path.startswith("goal_search_results."):
                ck = path.split(".", 1)[1]
                return (getattr(prev, "goal_search_results", {}) or {}).get(ck)
            if hasattr(prev, path):
                return getattr(prev, path)
            return (getattr(prev, "goal_search_results", {}) or {}).get(path)
        if isinstance(prev, dict):
            # One-level nested support: a.b
            if "." in path:
                head, tail = path.split(".", 1)
                base = prev.get(head)
                if isinstance(base, dict):
                    return base.get(tail)
                return None
            return prev.get(path)
        return None

    def _resolve_line_san(self, params: Dict[str, Any]) -> List[str]:
        """
        Resolve a SAN line from either direct `line_san` or `line_ref`.
        Supported refs:
        - "step:N.witness_line_san"
        - "step:N.pv_after_move"
        - "step:N.goal_search_results.witness_line_san"
        """
        if not isinstance(params, dict):
            return []
        if isinstance(params.get("line_san"), list):
            return [m for m in params.get("line_san") if isinstance(m, str)]
        line_ref = params.get("line_ref")
        if not line_ref:
            return []
        m = re.match(r"^step:(\d+)\.(.+)$", str(line_ref))
        if not m:
            return []
        step_num = int(m.group(1))
        key = m.group(2)
        prev = self._get_step_result(step_num)
        if isinstance(prev, InvestigationResult):
            if key == "witness_line_san":
                return list((getattr(prev, "goal_search_results", {}) or {}).get("witness_line_san") or [])
            if key == "pv_after_move":
                return list(prev.pv_after_move or [])
            if key.startswith("goal_search_results."):
                ck = key.split(".", 1)[1]
                val = (getattr(prev, "goal_search_results", {}) or {}).get(ck)
                return list(val or []) if isinstance(val, list) else []
        if isinstance(prev, dict):
            val = prev.get(key)
            return list(val or []) if isinstance(val, list) else []
        return []

    def _apply_san_line(self, start_fen: str, line_san: List[str], max_plies: int = 12) -> Dict[str, Any]:
        """
        Apply up to max_plies SAN moves and return end_fen + intermediate fens.
        Deterministic; no engine required.
        """
        out: Dict[str, Any] = {"start_fen": start_fen, "moves_san": [], "fens": [start_fen]}
        if not start_fen or not isinstance(start_fen, str):
            out["error"] = "Missing start_fen"
            return out
        try:
            b = chess.Board(start_fen)
        except Exception as e:
            out["error"] = f"Invalid start_fen: {e}"
            return out
        plies = 0
        for san in (line_san or []):
            if plies >= max_plies:
                break
            if not isinstance(san, str) or not san:
                continue
            try:
                mv = b.parse_san(san)
                b.push(mv)
                out["moves_san"].append(san)
                out["fens"].append(b.fen())
                plies += 1
            except Exception as e:
                out["error"] = f"Failed to apply SAN '{san}': {e}"
                break
        out["end_fen"] = out["fens"][-1] if out["fens"] else start_fen
        out["plies_applied"] = len(out["moves_san"])
        return out

    def _select_line_from_witnesses(
        self,
        witnesses: Any,
        *,
        strategy: str = "first",
        index: int = 0
    ) -> List[str]:
        """
        Deterministically select a line from witnesses.
        Accepts:
        - List[{"line_san":[...], ...}]
        - List[List[str]]
        """
        if not witnesses:
            return []
        lines: List[List[str]] = []
        if isinstance(witnesses, list):
            for w in witnesses:
                if isinstance(w, dict) and isinstance(w.get("line_san"), list):
                    lines.append([m for m in w.get("line_san") if isinstance(m, str)])
                elif isinstance(w, list):
                    lines.append([m for m in w if isinstance(m, str)])
        if not lines:
            return []
        strategy = (strategy or "first").lower()
        if strategy == "by_index":
            idx = max(0, min(int(index), len(lines) - 1))
            return lines[idx]
        if strategy == "shortest":
            return sorted(lines, key=lambda l: (len(l), " ".join(l)))[0]
        return lines[0]
    
    async def execute_plan(
        self,
        plan: ExecutionPlan,
        context: Dict[str, Any],
        status_callback: Optional[Callable] = None,
        live_pgn_streams: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute plan steps sequentially.
        
        Args:
            plan: ExecutionPlan to execute
            context: Context with FEN, PGN, etc.
            status_callback: Optional callback for status updates
            live_pgn_streams: Optional dict for live PGN streaming
            session_id: Optional session ID for tracking
            
        Returns:
            {
                "completed_steps": [...],
                "results": {step_number: result, ...},
                "final_result": ... (from last step),
                "investigated_lines": [...],  # NEW: All investigated moves and PVs
                "final_pgn": "...",  # NEW: PGN with all tested lines
                "needs_clarification": bool,
                "clarification_question": str (if needs_clarification)
            }
        """
        completed_steps = []
        fen = context.get("fen") or context.get("board_state")
        pgn = context.get("pgn")
        original_fen = fen  # Store original FEN for reverting
        processed_steps = set()  # step_number values already executed (for batched parallel investigations)

        # Named state slots for planner orchestration (state:NAME)
        self._state_slots = {}
        
        # NEW: Track all investigated lines for final PGN
        all_investigated_lines: List[Dict[str, Any]] = []
        
        print(f"\n{'='*80}")
        print(f"🔍 [EXECUTOR] INPUT:")
        print(f"   Plan ID: {plan.plan_id}")
        print(f"   Total Steps: {len(plan.steps)}")
        print(f"   Context FEN: {fen[:50] if fen else 'None'}...")
        print(f"{'='*80}\n")
        sys.stdout.flush()
        
        executor_start = time.time()
        print(f"   🔍 [EXECUTOR] Starting execution of plan with {len(plan.steps)} steps")
        # NOTE: plan_created is emitted by the orchestrator (backend/main.py) to avoid duplicates.
        
        for step in plan.steps:
            if step.step_number in processed_steps:
                continue
            step_start = time.time()
            print(f"   🔍 [EXECUTOR] Processing step {step.step_number}/{len(plan.steps)}: {step.action_type} - {step.purpose}")
            # Update step status to in_progress
            step.status = "in_progress"
            self._emit_event("step_update", {
                "step_number": step.step_number,
                "status": "in_progress",
                "purpose": step.purpose,
                "action_type": step.action_type
            })
            
            # Update status callback
            if status_callback:
                status_callback(
                    phase="executing",
                    message=f"Step {step.step_number}: {step.purpose}",
                    timestamp=time.time()
                )
            
            try:
                # Execute step based on action_type
                if step.action_type == "ask_clarification":
                    # Return early - need user input
                    return {
                        "needs_clarification": True,
                        "question": step.parameters.get("question", ""),
                        "completed_steps": completed_steps,
                        "plan_id": plan.plan_id
                    }
                
                elif step.action_type == "investigate_move":
                    # Opportunistic speedup: if we have a run of consecutive independent investigate_move steps
                    # from the same root FEN, execute them in parallel using separate Investigator instances
                    # (Investigator is not concurrency-safe due to shared mutable board state).
                    group = [step]
                    # Only consider a batch if this step resolves to the current context fen (no dependencies).
                    base_fen = self._resolve_fen(step.parameters, fen)
                    if base_fen and base_fen == fen:
                        try:
                            step_index = next((i for i, s in enumerate(plan.steps) if s.step_number == step.step_number), None)
                        except Exception:
                            step_index = None
                        if isinstance(step_index, int):
                            j = step_index + 1
                            while j < len(plan.steps):
                                nxt = plan.steps[j]
                                if nxt.action_type != "investigate_move":
                                    break
                                if nxt.step_number in processed_steps:
                                    j += 1
                                    continue
                                nxt_fen = self._resolve_fen(nxt.parameters, fen)
                                if not nxt_fen or nxt_fen != base_fen:
                                    break
                                group.append(nxt)
                                j += 1

                    if len(group) > 1:
                        print(f"   ⚡ [EXECUTOR] Parallelizing {len(group)} investigate_move step(s) from shared root FEN")
                        sys.stdout.flush()

                        async def _run_investigation(s: ExecutionStep):
                            mv_san = s.parameters.get("move_san")
                            if not mv_san:
                                return {"error": "Missing move_san"}
                            is_primary = bool(s.parameters.get("is_primary_recommendation"))
                            depth_light = int(s.parameters.get("depth", 12))
                            # Speed policy: primary uses D16; non-primary uses D2 (as requested).
                            depth_16 = 16 if is_primary else 2
                            depth_2 = 2
                            # Speed: evidence extension is cosmetic; keep full extension only for primary.
                            evidence_base_plies = 4
                            evidence_max_plies = 8 if is_primary else 4
                            inv = Investigator(engine_queue=self.engine_queue, engine_pool=self.engine_pool)
                            return await inv.investigate_move(
                                fen=base_fen,
                                move_san=mv_san,
                                follow_pv=True,
                                depth=depth_light,
                                depth_16=depth_16,
                                depth_2=depth_2,
                                evidence_base_plies=evidence_base_plies,
                                evidence_max_plies=evidence_max_plies,
                                focus=s.parameters.get("focus"),
                                pgn_callback=None,
                                fen_callback=None,
                                original_fen=original_fen
                            )

                        # Mark all grouped steps as processed up-front (we'll handle their events/results here).
                        for s in group[1:]:
                            processed_steps.add(s.step_number)

                        # Emit "thinking_started" + in_progress for all steps in the group (the loop only did the first one).
                        for s in group:
                            # Ensure in-progress state/event exists for steps that won't be visited by the main loop
                            if s is not step:
                                s.status = "in_progress"
                                self._emit_event("step_update", {
                                    "step_number": s.step_number,
                                    "status": "in_progress",
                                    "purpose": s.purpose,
                                    "action_type": s.action_type
                                })
                                if status_callback:
                                    status_callback(
                                        phase="executing",
                                        message=f"Step {s.step_number}: {s.purpose}",
                                        timestamp=time.time()
                                    )
                            self._emit_event("thinking_started", {
                                "phase": "investigating",
                                "message": f"Analyzing move {s.parameters.get('move_san', '')}...",
                                "plan_id": plan.plan_id,
                                "step_number": s.step_number
                            })

                        tasks = [asyncio.create_task(_run_investigation(s)) for s in group]
                        results = await asyncio.gather(*tasks, return_exceptions=True)

                        for s, res in zip(group, results):
                            if isinstance(res, Exception):
                                print(f"   ❌ Investigation error in step {s.step_number}: {res}")
                                s.status = "failed"
                                self.results[s.step_number] = {"error": f"Investigation failed: {str(res)}"}
                            else:
                                s.status = "completed"
                                self.results[s.step_number] = res
                                completed_steps.append(s.step_number)
                                if isinstance(res, InvestigationResult):
                                    all_investigated_lines.append({
                                        "move_san": s.parameters.get("move_san"),
                                        "fen_before": base_fen,
                                        "fen_after": res.pv_after_move[0] if res.pv_after_move else None,
                                        "pv": res.pv_after_move,
                                        "eval_after": res.eval_after,
                                        "eval_drop": res.eval_drop,
                                        "pgn_branch": res.pgn_branches.get("main_line") if res.pgn_branches else None
                                    })

                            # Emit completion/failure event + progress update
                            self._emit_event("step_update", {
                                "step_number": s.step_number,
                                "status": s.status,
                                "purpose": s.purpose,
                                "action_type": s.action_type,
                                **({"error": self.results.get(s.step_number, {}).get("error", "Unknown error")} if s.status == "failed" else {})
                            })
                            self._emit_event("plan_progress", {
                                "plan_id": plan.plan_id,
                                "completed": len(completed_steps),
                                "total": len(plan.steps),
                                "percentage": int((len(completed_steps) / len(plan.steps)) * 100) if plan.steps else 0
                            })

                        # Done with this batch; skip normal single-step path.
                        continue

                    # Emit thinking_started event
                    self._emit_event("thinking_started", {
                        "phase": "investigating",
                        "message": f"Analyzing move {step.parameters.get('move_san', '')}...",
                        "plan_id": plan.plan_id,
                        "step_number": step.step_number
                    })
                    
                    move_san = step.parameters.get("move_san")
                    step_fen = self._resolve_fen(step.parameters, fen)
                    
                    if step_fen and move_san:
                        print(f"\n   🔍 [EXECUTOR] Step {step.step_number}: Calling investigate_move...")
                        print(f"      Input FEN: {step_fen[:50]}...")
                        print(f"      Move SAN: {move_san}")
                        print(f"      Depth: {step.parameters.get('depth', 12)}")
                        print(f"      Focus: {step.parameters.get('focus')}")
                        
                        # Create PGN callback for live updates
                        pgn_updates = []
                        def pgn_callback(update_data: Dict[str, Any]):
                            pgn_updates.append(update_data)
                            # Emit to main SSE stream
                            self._emit_event("pgn_update", {
                                "plan_id": plan.plan_id,
                                "step_number": step.step_number,
                                **update_data
                            })
                            # Also send to live board stream if available
                            if session_id and live_pgn_streams and session_id in live_pgn_streams:
                                try:
                                    live_pgn_streams[session_id].put_nowait(("pgn_update", {
                                        "plan_id": plan.plan_id,
                                        "step_number": step.step_number,
                                        **update_data
                                    }))
                                except asyncio.QueueFull:
                                    pass  # Queue full, skip
                                except Exception as e:
                                    print(f"   ⚠️ Error sending to live board: {e}")
                        
                        # NEW: FEN callback for board updates
                        def fen_callback(update_data: Dict[str, Any]):
                            """Emit FEN updates to frontend"""
                            # Emit to main SSE stream
                            self._emit_event("board_state", {
                                "plan_id": plan.plan_id,
                                "step_number": step.step_number,
                                **update_data
                            })
                            # Also send to live board stream if available
                            if session_id and live_pgn_streams and session_id in live_pgn_streams:
                                try:
                                    live_pgn_streams[session_id].put_nowait(("board_state", {
                                        "plan_id": plan.plan_id,
                                        "step_number": step.step_number,
                                        **update_data
                                    }))
                                except asyncio.QueueFull:
                                    pass
                                except Exception as e:
                                    print(f"   ⚠️ Error sending FEN update to live board: {e}")
                        
                        try:
                            is_primary = bool(step.parameters.get("is_primary_recommendation"))
                            # Speed policy: primary uses D16; non-primary uses D2 (as requested).
                            depth_16 = 16 if is_primary else 2
                            depth_2 = 2
                            evidence_base_plies = 4
                            evidence_max_plies = 8 if is_primary else 4
                            result = await self.investigator.investigate_move(
                                fen=step_fen,
                                move_san=move_san,
                                follow_pv=True,
                                depth=step.parameters.get("depth", 12),
                                depth_16=depth_16,
                                depth_2=depth_2,
                                evidence_base_plies=evidence_base_plies,
                                evidence_max_plies=evidence_max_plies,
                                focus=step.parameters.get("focus"),
                                pgn_callback=pgn_callback,
                                fen_callback=fen_callback,  # NEW
                                original_fen=original_fen  # NEW
                            )
                            
                            # NEW: Track investigated line
                            if isinstance(result, InvestigationResult):
                                all_investigated_lines.append({
                                    "move_san": move_san,
                                    "fen_before": step_fen,
                                    "fen_after": result.pv_after_move[0] if result.pv_after_move else None,
                                    "pv": result.pv_after_move,
                                    "eval_after": result.eval_after,
                                    "eval_drop": result.eval_drop,
                                    "pgn_branch": result.pgn_branches.get("main_line") if result.pgn_branches else None
                                })
                            
                            print(f"\n   ✅ [EXECUTOR] Step {step.step_number}: investigate_move OUTPUT:")
                            print(f"      Type: {type(result).__name__}")
                            if isinstance(result, InvestigationResult):
                                print(f"      Player Move: {result.player_move}")
                                print(f"      Eval Before: {result.eval_before}")
                                print(f"      Eval After: {result.eval_after}")
                                print(f"      Eval Drop: {result.eval_drop}")
                                print(f"      Tactics Found: {len(result.tactics_found)}")
                                print(f"      Goal Search Results: {list(result.goal_search_results.keys()) if result.goal_search_results else []}")
                            print(f"   ✅ [EXECUTOR] Step {step.step_number}: investigate_move completed\n")
                            
                            self.results[step.step_number] = result
                            completed_steps.append(step.step_number)
                            step.status = "completed"
                        except Exception as inv_e:
                            print(f"   ❌ Investigation error in step {step.step_number}: {inv_e}")
                            import traceback
                            traceback.print_exc()
                            step.status = "failed"
                            self.results[step.step_number] = {"error": f"Investigation failed: {str(inv_e)}"}
                            # For critical investigation steps, fail the plan
                            if step.action_type in ["investigate_position", "investigate_move"]:
                                print(f"   ⚠️ Critical investigation step failed - plan may be incomplete")
                                # Continue but mark plan as potentially incomplete
                    else:
                        step.status = "failed"
                        self.results[step.step_number] = {"error": "Missing FEN or move_san"}
                
                elif step.action_type == "investigate_position":
                    print(f"   🔍 [EXECUTOR] Step {step.step_number}: Starting investigate_position")
                    # Emit thinking_started event
                    focus_val = step.parameters.get('focus', '')
                    focus_suffix = f' (focus: {focus_val})' if focus_val else ''
                    self._emit_event("thinking_started", {
                        "phase": "investigating",
                        "message": f"Analyzing position{focus_suffix}...",
                        "plan_id": plan.plan_id,
                        "step_number": step.step_number
                    })
                    
                    step_fen = self._resolve_fen(step.parameters, fen)
                    print(f"   🔍 [EXECUTOR] Step {step.step_number}: FEN={bool(step_fen)}, scope=general_position")
                    if step_fen:
                        # Create PGN callback for live updates
                        pgn_updates = []
                        def pgn_callback(update_data: Dict[str, Any]):
                            pgn_updates.append(update_data)
                            # Emit to main SSE stream
                            self._emit_event("pgn_update", {
                                "plan_id": plan.plan_id,
                                "step_number": step.step_number,
                                **update_data
                            })
                            # Also send to live board stream if available
                            if session_id and live_pgn_streams and session_id in live_pgn_streams:
                                try:
                                    live_pgn_streams[session_id].put_nowait(("pgn_update", {
                                        "plan_id": plan.plan_id,
                                        "step_number": step.step_number,
                                        **update_data
                                    }))
                                except asyncio.QueueFull:
                                    pass  # Queue full, skip
                                except Exception as e:
                                    print(f"   ⚠️ Error sending to live board: {e}")
                        
                        try:
                            print(f"\n   🔍 [EXECUTOR] Step {step.step_number}: Calling investigate_position...")
                            print(f"      Input FEN: {step_fen[:50]}...")
                            print(f"      Depth: {step.parameters.get('depth', 18)}")
                            print(f"      Focus: {step.parameters.get('focus')}")
                            print(f"      Scope: general_position")
                            
                            result = await self.investigator.investigate_position(
                                fen=step_fen,
                                depth=step.parameters.get("depth", 18),
                                focus=step.parameters.get("focus"),
                                scope="general_position",  # Use dual-depth
                                pgn_callback=pgn_callback
                            )
                            
                            print(f"\n   ✅ [EXECUTOR] Step {step.step_number}: investigate_position OUTPUT:")
                            print(f"      Type: {type(result).__name__}")
                            if isinstance(result, InvestigationResult):
                                print(f"      Eval Before: {result.eval_before}")
                                print(f"      Best Move: {result.best_move}")
                                print(f"      Game Phase: {result.game_phase}")
                                print(f"      Eval D16: {result.eval_d16}")
                                print(f"      Best Move D16: {result.best_move_d16}")
                                print(f"      Overestimated Moves: {len(result.overestimated_moves)}")
                                print(f"      PGN Exploration Length: {len(result.pgn_exploration) if result.pgn_exploration else 0} chars")
                                print(f"      Themes: {result.themes_identified[:5] if result.themes_identified else []}")
                            print(f"   ✅ [EXECUTOR] Step {step.step_number}: investigate_position completed\n")
                            
                            self.results[step.step_number] = result
                            completed_steps.append(step.step_number)
                            step.status = "completed"
                            
                            # ENHANCEMENT: Extract Stockfish candidate moves and add investigate_move steps
                            if isinstance(result, InvestigationResult):
                                # Planner is the primary place for candidate-move expansion.
                                # Only fall back to executor-side injection if the plan contains no investigate_move steps.
                                try:
                                    disable_injection = bool(
                                        getattr(plan, "metadata", {}).get("disable_executor_candidate_injection")
                                    )
                                except Exception:
                                    disable_injection = False

                                has_any_move_steps = any(
                                    getattr(s, "action_type", None) == "investigate_move" for s in (plan.steps or [])
                                )
                                if (not disable_injection) and (not has_any_move_steps):
                                    self._add_stockfish_candidate_moves(plan, result, step_fen, step.step_number, context)
                        except Exception as inv_e:
                            print(f"   ❌ [EXECUTOR] Investigation error in step {step.step_number}: {inv_e}")
                            import traceback
                            traceback.print_exc()
                            step.status = "failed"
                            self.results[step.step_number] = {"error": f"Investigation failed: {str(inv_e)}"}
                            # For critical investigation steps, fail the plan
                            if step.action_type in ["investigate_position", "investigate_move"]:
                                print(f"   ⚠️ Critical investigation step failed - plan may be incomplete")
                                # Continue but mark plan as potentially incomplete
                    else:
                        step.status = "failed"
                        self.results[step.step_number] = {"error": "Missing FEN"}
                
                elif step.action_type == "investigate_target":
                    print(f"   🔍 [EXECUTOR] Step {step.step_number}: Starting investigate_target")
                    self._emit_event("thinking_started", {
                        "phase": "investigating",
                        "message": "Searching for a target goal state...",
                        "plan_id": plan.plan_id,
                        "step_number": step.step_number
                    })

                    step_fen = self._resolve_fen(step.parameters, fen)
                    goal = step.parameters.get("goal") or {}
                    policy = step.parameters.get("policy") or {}

                    if step_fen:
                        # Create PGN callback for live updates (reuse pattern)
                        pgn_updates = []
                        def pgn_callback(update_data: Dict[str, Any]):
                            pgn_updates.append(update_data)
                            self._emit_event("pgn_update", {
                                "plan_id": plan.plan_id,
                                "step_number": step.step_number,
                                **update_data
                            })
                            if session_id and live_pgn_streams and session_id in live_pgn_streams:
                                try:
                                    live_pgn_streams[session_id].put_nowait(("pgn_update", {
                                        "plan_id": plan.plan_id,
                                        "step_number": step.step_number,
                                        **update_data
                                    }))
                                except asyncio.QueueFull:
                                    pass
                                except Exception as e:
                                    print(f"   ⚠️ Error sending to live board: {e}")

                        try:
                            print(f"\n   🔍 [EXECUTOR] Step {step.step_number}: Calling investigate_target...")
                            print(f"      Input FEN: {step_fen[:50]}...")
                            print(f"      Goal keys: {list(goal.keys()) if isinstance(goal, dict) else type(goal).__name__}")
                            print(f"      Policy keys: {list(policy.keys()) if isinstance(policy, dict) else type(policy).__name__}")

                            result = await self.investigator.investigate_target(
                                fen=step_fen,
                                goal=goal,
                                policy=policy,
                                pgn_callback=pgn_callback
                            )

                            # Convenience: compute end_fen for chaining (based on witness_line_san + witnesses)
                            try:
                                if isinstance(result, InvestigationResult):
                                    if not result.goal_search_results:
                                        result.goal_search_results = {}
                                    witness = (result.goal_search_results or {}).get("witness_line_san") or []
                                    if isinstance(witness, list) and witness:
                                        applied = self._apply_san_line(step_fen, witness, max_plies=len(witness))
                                        result.goal_search_results["end_fen"] = applied.get("end_fen")
                                        result.goal_search_results["fens"] = applied.get("fens")

                                    ws = (result.goal_search_results or {}).get("witnesses") or []
                                    if isinstance(ws, list) and ws:
                                        enriched = []
                                        for w in ws:
                                            if not isinstance(w, dict):
                                                continue
                                            line = w.get("line_san") if isinstance(w.get("line_san"), list) else []
                                            applied_w = self._apply_san_line(step_fen, line, max_plies=len(line)) if line else {"end_fen": step_fen, "fens": [step_fen]}
                                            w2 = dict(w)
                                            w2["end_fen"] = applied_w.get("end_fen")
                                            w2["fens"] = applied_w.get("fens")
                                            enriched.append(w2)
                                        result.goal_search_results["witnesses"] = enriched
                            except Exception:
                                pass

                            # Compute evidence deltas for investigate_target (like investigate_move does)
                            try:
                                if isinstance(result, InvestigationResult):
                                    witness = (result.goal_search_results or {}).get("witness_line_san") or []
                                    if isinstance(witness, list) and witness and len(witness) >= 1:
                                        # Compute evidence deltas for the witness line
                                        per_move, tg, tl, rg, rl, tg_struct, tl_struct = self.investigator._compute_per_move_deltas_for_line(step_fen, witness)
                                        result.evidence_starting_fen = step_fen
                                        result.evidence_main_line_moves = witness
                                        result.evidence_pgn_line = " ".join(witness)
                                        result.evidence_per_move_deltas = per_move
                                        # Preserve full/raw tags (for deep analysis)
                                        result.evidence_tags_gained_net_raw = list(tg or [])
                                        result.evidence_tags_lost_net_raw = list(tl or [])
                                        # Filter clutter from public net lists
                                        _clutter_prefixes = ("tag.diagonal.", "tag.key.", "tag.color.hole.")
                                        result.evidence_tags_gained_net = [t for t in (tg or []) if not any(str(t).startswith(p) for p in _clutter_prefixes)]
                                        result.evidence_tags_lost_net = [t for t in (tl or []) if not any(str(t).startswith(p) for p in _clutter_prefixes)]
                                        result.evidence_tags_gained_net_structured = tg_struct
                                        result.evidence_tags_lost_net_structured = tl_struct
                                        result.evidence_roles_gained_net = rg
                                        result.evidence_roles_lost_net = rl
                                        
                                        # Compute eval breakdown
                                        breakdown = await self.investigator._compute_evidence_eval_breakdown(
                                            starting_fen=step_fen,
                                            evidence_moves=witness,
                                            eval_start_pawns=None,  # investigate_target doesn't have eval_before
                                            end_eval_depth=6
                                        )
                                        result.evidence_end_fen = breakdown.get("end_fen")
                                        result.evidence_eval_start = breakdown.get("eval_start")
                                        result.evidence_eval_end = breakdown.get("eval_end")
                                        result.evidence_eval_delta = breakdown.get("eval_delta")
                                        result.evidence_material_start = breakdown.get("material_start")
                                        result.evidence_material_end = breakdown.get("material_end")
                                        result.evidence_positional_start = breakdown.get("positional_start")
                                        result.evidence_positional_end = breakdown.get("positional_end")

                                        # NEW: per-move FEN + eval/material/positional series for SAN->words narration
                                        try:
                                            result.evidence_per_move_stats = await self.investigator._compute_evidence_per_move_stats(
                                                starting_fen=step_fen,
                                                evidence_per_move_deltas=result.evidence_per_move_deltas,
                                                eval_start_pawns=result.evidence_eval_start,
                                                depth=6,
                                                max_plies=16,
                                            )
                                        except Exception:
                                            result.evidence_per_move_stats = []
                                        
                                        # Ensure pgn_exploration is set if missing
                                        if not result.pgn_exploration and witness:
                                            try:
                                                game = chess.pgn.Game()
                                                game.headers["FEN"] = step_fen
                                                game.headers["SetUp"] = "1"
                                                game.headers["Event"] = "Investigation (Target)"
                                                board = chess.Board(step_fen)
                                                node = game
                                                for san in witness:
                                                    mv = board.parse_san(san)
                                                    node = node.add_variation(mv)
                                                    board.push(mv)
                                                exporter = chess.pgn.StringExporter(headers=True, variations=False, comments=False)
                                                result.pgn_exploration = game.accept(exporter)
                                            except Exception:
                                                pass
                            except Exception as e:
                                print(f"   ⚠️ [EXECUTOR] Failed to compute evidence deltas for investigate_target: {e}")

                            self.results[step.step_number] = result
                            completed_steps.append(step.step_number)
                            step.status = "completed"
                        except Exception as inv_e:
                            print(f"   ❌ [EXECUTOR] Investigation error in step {step.step_number}: {inv_e}")
                            import traceback
                            traceback.print_exc()
                            step.status = "failed"
                            self.results[step.step_number] = {"error": f"Investigation failed: {str(inv_e)}"}
                            if step.action_type in ["investigate_position", "investigate_move", "investigate_target"]:
                                print(f"   ⚠️ Critical investigation step failed - plan may be incomplete")
                    else:
                        step.status = "failed"
                        self.results[step.step_number] = {"error": "Missing FEN"}
                
                elif step.action_type == "apply_line":
                    step_fen = self._resolve_fen(step.parameters, fen)
                    if not step_fen:
                        step.status = "failed"
                        self.results[step.step_number] = {"error": "Missing FEN for apply_line"}
                    else:
                        line_san = self._resolve_line_san(step.parameters)
                        # SAFETY: If we are applying a pv_after_move line from an investigate_move step,
                        # prepend that step's player_move so the applied SAN sequence is complete from the root FEN.
                        # (pv_after_move typically starts AFTER the player move, so it may begin with an opponent reply like "Bxe2".)
                        try:
                            line_ref = (step.parameters or {}).get("line_ref")
                            if isinstance(line_ref, str) and line_ref.endswith(".pv_after_move"):
                                import re
                                m = re.match(r"^step:(\d+)\.", line_ref)
                                if m:
                                    src_step_num = int(m.group(1))
                                    prev = self._get_step_result(src_step_num)
                                    if isinstance(prev, InvestigationResult):
                                        pm = getattr(prev, "player_move", None)
                                        if isinstance(pm, str) and pm:
                                            if not line_san or (isinstance(line_san[0], str) and line_san[0] != pm):
                                                line_san = [pm] + list(line_san or [])
                        except Exception:
                            pass
                        max_plies = int((step.parameters or {}).get("max_plies", 12))
                        max_plies = max(0, min(max_plies, 60))
                        result = self._apply_san_line(step_fen, line_san, max_plies=max_plies)
                        self.results[step.step_number] = result
                        completed_steps.append(step.step_number)
                        step.status = "completed"

                elif step.action_type == "select_line":
                    src = (step.parameters or {}).get("source_ref")
                    strategy = (step.parameters or {}).get("strategy", "first")
                    index = (step.parameters or {}).get("index", 0)
                    witnesses = self._resolve_ref_value(src) if isinstance(src, str) else (step.parameters or {}).get("witnesses")
                    selected = self._select_line_from_witnesses(witnesses, strategy=strategy, index=index)
                    out = {
                        "source_ref": src,
                        "strategy": strategy,
                        "index": index,
                        "selected_line_san": selected
                    }
                    self.results[step.step_number] = out
                    completed_steps.append(step.step_number)
                    step.status = "completed"

                elif step.action_type == "save_state":
                    name = (step.parameters or {}).get("name")
                    step_fen = self._resolve_fen(step.parameters, fen)
                    if not name or not isinstance(name, str):
                        step.status = "failed"
                        self.results[step.step_number] = {"error": "Missing state name"}
                    elif not step_fen:
                        step.status = "failed"
                        self.results[step.step_number] = {"error": "Missing FEN for save_state"}
                    else:
                        self._state_slots[name] = step_fen
                        self.results[step.step_number] = {"name": name, "fen": step_fen}
                        completed_steps.append(step.step_number)
                        step.status = "completed"

                elif step.action_type == "score_state":
                    step_fen = self._resolve_fen(step.parameters, fen)
                    if not step_fen:
                        step.status = "failed"
                        self.results[step.step_number] = {"error": "Missing FEN for score_state"}
                    else:
                        depth = int((step.parameters or {}).get("depth", 8))
                        depth = max(1, min(depth, 18))
                        side = ((step.parameters or {}).get("side") or "white").lower()
                        side_color = chess.WHITE if side == "white" else chess.BLACK
                        try:
                            analysis = await self.investigator._cached_analyze_depth(step_fen, depth=depth, get_top_2=False)
                            eval_pawns = analysis.get("eval")
                            eval_cp = int(round(eval_pawns * 100)) if isinstance(eval_pawns, (int, float)) else None
                        except Exception as e:
                            analysis = {"error": str(e)}
                            eval_cp = None

                        # Normalize score for chosen side
                        score_side_cp = None
                        if isinstance(eval_cp, int):
                            score_side_cp = eval_cp if side_color == chess.WHITE else -eval_cp

                        # Add cheap explainable breakdown from light raw (tags/themes/material)
                        try:
                            lr = self.investigator._cached_light_raw(step_fen)
                            material_cp = int(getattr(lr, "material_balance_cp", 0))
                            top_themes = list(getattr(lr, "top_themes", []) or [])[:5]
                            tag_sample = []
                            for t in (getattr(lr, "tags", []) or [])[:8]:
                                if isinstance(t, dict):
                                    tag_sample.append(t.get("tag") or t.get("name"))
                            breakdown = {
                                "material_balance_cp": material_cp,
                                "top_themes": top_themes,
                                "tag_sample": tag_sample,
                            }
                        except Exception:
                            breakdown = {}

                        out = {
                            "fen": step_fen,
                            "depth": depth,
                            "side": side,
                            "eval_cp_white": eval_cp,
                            "score_side_cp": score_side_cp,
                            "best_move_san": analysis.get("best_move_san") if isinstance(analysis, dict) else None,
                            "breakdown": breakdown,
                        }
                        save_as = (step.parameters or {}).get("save_as")
                        if save_as and isinstance(save_as, str):
                            out["saved_as"] = save_as
                        self.results[step.step_number] = out
                        completed_steps.append(step.step_number)
                        step.status = "completed"

                elif step.action_type == "select_state":
                    candidates = (step.parameters or {}).get("candidates") or []
                    strategy = ((step.parameters or {}).get("strategy") or "max").lower()
                    save_as = (step.parameters or {}).get("save_as") or "best"

                    rows = []
                    for c in candidates:
                        if not isinstance(c, dict):
                            continue
                        state_name = c.get("state")
                        score_ref = c.get("score_ref")
                        if not state_name or not isinstance(state_name, str):
                            continue
                        fen_c = getattr(self, "_state_slots", {}).get(state_name)
                        score_val = None
                        if isinstance(score_ref, str):
                            score_val = self._resolve_ref_value(score_ref)
                        else:
                            score_val = c.get("score")
                        # Support score_state output field name too
                        if isinstance(score_val, dict) and "score_side_cp" in score_val:
                            score_val = score_val.get("score_side_cp")
                        if isinstance(score_val, (int, float)):
                            score_val = float(score_val)
                        else:
                            score_val = None
                        rows.append({"state": state_name, "fen": fen_c, "score": score_val, "score_ref": score_ref})

                    rows_valid = [r for r in rows if isinstance(r.get("score"), (int, float))]
                    selected = None
                    if rows_valid:
                        if strategy == "min":
                            selected = sorted(rows_valid, key=lambda r: (r["score"], r["state"]))[0]
                        else:
                            selected = sorted(rows_valid, key=lambda r: (-r["score"], r["state"]))[0]

                    if not selected or not selected.get("fen"):
                        step.status = "failed"
                        self.results[step.step_number] = {"error": "No selectable candidate states", "candidates": rows}
                    else:
                        # Save chosen fen into a new slot for continued planning
                        if save_as and isinstance(save_as, str):
                            self._state_slots[save_as] = selected["fen"]
                        self.results[step.step_number] = {
                            "strategy": strategy,
                            "selected_state": selected["state"],
                            "selected_fen": selected["fen"],
                            "saved_as": save_as,
                            "candidates": rows,
                        }
                        completed_steps.append(step.step_number)
                        step.status = "completed"

                elif step.action_type == "audit_line":
                    # Counterfactual check: apply a line, then re-score end_fen at higher depth
                    step_fen = self._resolve_fen(step.parameters, fen)
                    if not step_fen:
                        step.status = "failed"
                        self.results[step.step_number] = {"error": "Missing FEN for audit_line"}
                    else:
                        line_san = self._resolve_line_san(step.parameters)
                        max_plies = int((step.parameters or {}).get("max_plies", 12))
                        max_plies = max(0, min(max_plies, 60))
                        applied = self._apply_san_line(step_fen, line_san, max_plies=max_plies)
                        end_fen = applied.get("end_fen")
                        depth = int((step.parameters or {}).get("depth", 12))
                        depth = max(1, min(depth, 18))
                        side = ((step.parameters or {}).get("side") or "white").lower()
                        side_color = chess.WHITE if side == "white" else chess.BLACK
                        eval_cp = None
                        try:
                            analysis = await self.investigator._analyze_depth(end_fen, depth=depth, get_top_2=True)
                            eval_pawns = analysis.get("eval")
                            eval_cp = int(round(eval_pawns * 100)) if isinstance(eval_pawns, (int, float)) else None
                            best = analysis.get("best_move_san")
                            second = analysis.get("second_best_move_san")
                            best_cp = analysis.get("best_move_eval_cp")
                            second_cp = analysis.get("second_best_move_eval_cp")
                            cp_gap = None
                            if isinstance(best_cp, int) and isinstance(second_cp, int):
                                cp_gap = abs(best_cp - second_cp)
                        except Exception as e:
                            analysis = {"error": str(e)}
                            best = None
                            second = None
                            cp_gap = None
                        score_side_cp = None
                        if isinstance(eval_cp, int):
                            score_side_cp = eval_cp if side_color == chess.WHITE else -eval_cp
                        out = {
                            "start_fen": step_fen,
                            "end_fen": end_fen,
                            "applied": applied,
                            "depth": depth,
                            "side": side,
                            "eval_cp_white": eval_cp,
                            "score_side_cp": score_side_cp,
                            "best_reply": best,
                            "second_reply": second,
                            "cp_gap": cp_gap,
                            "analysis": analysis,
                        }
                        self.results[step.step_number] = out
                        completed_steps.append(step.step_number)
                        step.status = "completed"

                elif step.action_type == "retry_investigate_target":
                    # Policy escalation loop for investigate_target
                    step_fen = self._resolve_fen(step.parameters, fen)
                    goal = (step.parameters or {}).get("goal") or {}
                    base_policy = (step.parameters or {}).get("policy") or {}
                    retries = int((step.parameters or {}).get("retries", 2))
                    retries = max(0, min(retries, 6))
                    if not step_fen:
                        step.status = "failed"
                        self.results[step.step_number] = {"error": "Missing FEN for retry_investigate_target"}
                    else:
                        attempts = []
                        best = None

                        def _rank(res: InvestigationResult):
                            st = (res.goal_search_results or {}).get("goal_status")
                            if st == "success":
                                return 3
                            if st == "uncertain":
                                return 2
                            return 1

                        for i in range(retries + 1):
                            pol = dict(base_policy)
                            # Escalate compute gradually
                            pol["max_depth"] = int(pol.get("max_depth", 8)) + i * 2
                            pol["beam_width"] = int(pol.get("beam_width", 4)) + i
                            pol["branching_limit"] = int(pol.get("branching_limit", 8)) + i * 2
                            try:
                                res = await self.investigator.investigate_target(fen=step_fen, goal=goal, policy=pol)
                                attempts.append({
                                    "attempt": i,
                                    "policy": pol,
                                    "goal_status": (res.goal_search_results or {}).get("goal_status"),
                                    "witness_line_san": (res.goal_search_results or {}).get("witness_line_san"),
                                    "witnesses": (res.goal_search_results or {}).get("witnesses"),
                                    "limits": (res.goal_search_results or {}).get("limits"),
                                })
                                if best is None or _rank(res) > _rank(best):
                                    best = res
                                if (res.goal_search_results or {}).get("goal_status") == "success":
                                    break
                            except Exception as e:
                                attempts.append({"attempt": i, "policy": pol, "error": str(e)})
                        if best is None:
                            step.status = "failed"
                            self.results[step.step_number] = {"error": "All attempts failed", "attempts": attempts}
                        else:
                            if not best.goal_search_results:
                                best.goal_search_results = {}
                            best.goal_search_results["retry_attempts"] = attempts
                            self.results[step.step_number] = best
                            completed_steps.append(step.step_number)
                            step.status = "completed"

                elif step.action_type == "investigate_game":
                    step_pgn = step.parameters.get("pgn") or pgn
                    if step_pgn:
                        result = await self.investigator.investigate_game(
                            pgn=step_pgn,
                            focus=step.parameters.get("focus")
                        )
                        self.results[step.step_number] = result
                        completed_steps.append(step.step_number)
                        step.status = "completed"
                    else:
                        step.status = "failed"
                        self.results[step.step_number] = {"error": "Missing PGN"}
                
                elif step.action_type == "synthesize":
                    # Collect all investigation results
                    investigation_results = [
                        self.results[step_num]
                        for step_num in completed_steps
                        if step_num in self.results and step_num != step.step_number
                    ]
                    # Pass to Summariser (handled in main pipeline)
                    self.results[step.step_number] = {
                        "synthesis_ready": True,
                        "results": investigation_results
                    }
                    completed_steps.append(step.step_number)
                    step.status = "completed"
                
                elif step.action_type == "answer":
                    # Mark as ready for Explainer
                    self.results[step.step_number] = {"answer_ready": True}
                    completed_steps.append(step.step_number)
                    step.status = "completed"
                
                else:
                    step.status = "failed"
                    self.results[step.step_number] = {"error": f"Unknown action_type: {step.action_type}"}
                
                # Emit step completion event
                if step.status == "completed":
                    self._emit_event("step_update", {
                        "step_number": step.step_number,
                        "status": "completed",
                        "purpose": step.purpose,
                        "action_type": step.action_type
                    })
                elif step.status == "failed":
                    self._emit_event("step_update", {
                        "step_number": step.step_number,
                        "status": "failed",
                        "purpose": step.purpose,
                        "action_type": step.action_type,
                        "error": self.results.get(step.step_number, {}).get("error", "Unknown error")
                    })
                
                # Emit progress update
                self._emit_event("plan_progress", {
                    "plan_id": plan.plan_id,
                    "completed": len(completed_steps),
                    "total": len(plan.steps),
                    "percentage": int((len(completed_steps) / len(plan.steps)) * 100) if plan.steps else 0
                })
                
            except Exception as e:
                print(f"   ❌ [EXECUTOR] Error in step {step.step_number}: {e}")
                import traceback
                traceback.print_exc()
                step.status = "failed"
                self.results[step.step_number] = {"error": str(e)}
                self._emit_event("step_update", {
                    "step_number": step.step_number,
                    "status": "failed",
                    "purpose": step.purpose,
                    "action_type": step.action_type,
                    "error": str(e)
                })
        
        # Build final PGN with all investigated lines
        final_pgn = self._build_final_pgn(all_investigated_lines, original_fen) if all_investigated_lines else ""
        
        print(f"\n{'='*80}")
        print(f"✅ [EXECUTOR] OUTPUT:")
        print(f"   Investigated Lines: {len(all_investigated_lines)}")
        print(f"   Final PGN Length: {len(final_pgn)} chars")
        print(f"   Completed Steps: {len(completed_steps)}/{len(plan.steps)}")
        print(f"   Results Keys: {list(self.results.keys())}")
        for step_num in completed_steps:
            result = self.results.get(step_num)
            if isinstance(result, InvestigationResult):
                print(f"      Step {step_num}: InvestigationResult")
                print(f"         Eval Before: {result.eval_before}")
                print(f"         Best Move: {result.best_move}")
            elif isinstance(result, dict):
                print(f"      Step {step_num}: dict with keys {list(result.keys())}")
                if "error" in result:
                    print(f"         Error: {result['error']}")
            else:
                print(f"      Step {step_num}: {type(result).__name__}")
        print(f"{'='*80}\n")
        sys.stdout.flush()
        
        executor_duration = time.time() - executor_start
        print(f"   ✅ [EXECUTOR] Execution complete: {len(completed_steps)}/{len(plan.steps)} steps completed")
        print(f"   ⏱️  [EXECUTOR] Total execution time: {executor_duration:.2f}s")
        return {
            "completed_steps": completed_steps,
            "results": self.results,
            "final_result": self.results.get(completed_steps[-1] if completed_steps else None),
            "plan_id": plan.plan_id,
            "investigated_lines": all_investigated_lines,  # NEW
            "final_pgn": final_pgn  # NEW
        }
    
    def _build_final_pgn(self, investigated_lines: List[Dict[str, Any]], original_fen: str) -> str:
        """
        Build a PGN with all investigated lines as variations.
        
        Args:
            investigated_lines: List of dicts with move_san, fen_before, pv, etc.
            original_fen: Original FEN position
            
        Returns:
            PGN string with all variations
        """
        if not investigated_lines:
            return ""
        
        try:
            game = chess.pgn.Game()
            game.headers["FEN"] = original_fen
            game.headers["SetUp"] = "1"
            game.headers["Event"] = "Investigation Lines"
            
            board = chess.Board(original_fen)
            node = game
            
            # Add each investigated line as a variation
            for line in investigated_lines:
                move_san = line.get("move_san")
                pv = line.get("pv", [])
                fen_before = line.get("fen_before", original_fen)  # Use line-specific FEN if available
                
                if not move_san:
                    continue
                
                try:
                    # Use line-specific FEN if available, otherwise fall back to original
                    line_board = chess.Board(fen_before)
                    # Only add if this move is legal in the original position (for consistency)
                    # But use line_board for parsing to handle different positions correctly
                    original_board = chess.Board(original_fen)
                    move_obj = original_board.parse_san(move_san)
                    if move_obj not in original_board.legal_moves:
                        # Skip moves that aren't legal in the original position
                        continue
                    
                    var_node = node.add_variation(move_obj)
                    
                    # Add PV moves to variation using the board state after the move
                    temp_board = original_board.copy()
                    temp_board.push(move_obj)
                    for pv_move_san in pv[:8]:  # Limit PV length
                        try:
                            pv_move = temp_board.parse_san(pv_move_san)
                            if pv_move in temp_board.legal_moves:
                                var_node = var_node.add_variation(pv_move)
                                temp_board.push(pv_move)
                            else:
                                break
                        except Exception:
                            break
                except Exception as e:
                    # Validate move before logging error
                    try:
                        test_board = chess.Board(original_fen)
                        parsed_move = test_board.parse_san(move_san)
                        if parsed_move not in test_board.legal_moves:
                            # Silently skip moves that aren't legal in original position
                            continue
                        else:
                            print(f"   ⚠️ [EXECUTOR] Error adding variation for {move_san}: {e}")
                    except Exception:
                        # Silently skip parse errors for moves not legal in original position
                        continue
            
            # Export PGN
            exporter = chess.pgn.StringExporter(headers=True, variations=True, comments=False)
            return str(game.accept(exporter))
        except Exception as e:
            print(f"   ⚠️ Error building final PGN: {e}")
            import traceback
            traceback.print_exc()
            return ""
    
    def _add_stockfish_candidate_moves(
        self,
        plan: ExecutionPlan,
        result: InvestigationResult,
        fen: str,
        position_step_number: int,
        context: Dict[str, Any]
    ):
        """
        Extract Stockfish candidate moves from investigate_position result and add investigate_move steps.
        Priority: User-mentioned moves > LLM-suggested moves > Stockfish recommendations.
        """
        # Get moves already being investigated
        existing_moves = set()
        for step in plan.steps:
            if step.action_type == "investigate_move":
                move_san = step.parameters.get("move_san")
                if move_san:
                    existing_moves.add(move_san)
        
        # Extract user-mentioned moves from intent_plan (if available)
        user_mentioned_moves = []
        intent_plan = context.get("intent_plan")
        if intent_plan:
            user_mentioned_moves = self._extract_moves_from_intent(intent_plan)
            # Heuristic: if user mentions knight development + castling without specifying moves,
            # add a few legal knight moves so we test the thing the user is actually asking about.
            try:
                summary = (getattr(intent_plan, "user_intent_summary", "") or "").lower()
                if ("knight" in summary) and ("castle" in summary) and (not user_mentioned_moves):
                    user_mentioned_moves = self._suggest_knight_development_moves(fen, limit=4)
            except Exception:
                pass
        
        # Collect Stockfish candidate moves
        stockfish_moves = []
        
        # Helper: accept either SAN or UCI and normalize to SAN
        def _normalize_to_san(move_str: Optional[str]) -> Optional[str]:
            if not move_str or not isinstance(move_str, str):
                return None
            try:
                import chess
                b = chess.Board(fen)
                # Try SAN first
                try:
                    m = b.parse_san(move_str)
                    if m in b.legal_moves:
                        return b.san(m)
                except Exception:
                    pass
                # Fallback to UCI
                try:
                    m = chess.Move.from_uci(move_str)
                    if m in b.legal_moves:
                        return b.san(m)
                except Exception:
                    pass
            except Exception:
                return None
            return None

        # Priority 1: Best moves from dual-depth analysis (most reliable)
        best_san = _normalize_to_san(result.best_move_d16)
        if best_san and best_san not in existing_moves:
            stockfish_moves.append({
                "move_san": best_san,
                "priority": 1,
                "source": "best_move_d16",
                "eval": result.best_move_d16_eval_cp
            })

        second_san = _normalize_to_san(result.second_best_move_d16)
        if second_san and second_san not in existing_moves and not any(m["move_san"] == second_san for m in stockfish_moves):
            stockfish_moves.append({
                "move_san": second_san,
                "priority": 1,
                "source": "second_best_move_d16",
                "eval": result.second_best_move_d16_eval_cp
            })
        
        # Priority 2: Top moves from D2 analysis
        if result.top_moves_d2:
            for move_data in result.top_moves_d2[:5]:  # Top 5 from D2
                move_san = move_data.get("move")
                if move_san and move_san not in existing_moves:
                    if not any(m["move_san"] == move_san for m in stockfish_moves):
                        stockfish_moves.append({
                            "move_san": move_san,
                            "priority": 2,
                            "source": "top_moves_d2",
                            "eval": move_data.get("eval_cp")
                        })
        
        # Priority 3: Candidate moves from standard analysis
        if result.candidate_moves:
            for move_data in result.candidate_moves[:3]:  # Top 3 candidates
                move_san = move_data.get("move")
                if move_san and move_san not in existing_moves:
                    if not any(m["move_san"] == move_san for m in stockfish_moves):
                        stockfish_moves.append({
                            "move_san": move_san,
                            "priority": 3,
                            "source": "candidate_moves",
                            "eval": move_data.get("eval")
                        })
        
        # Sort by priority and limit to top 5 Stockfish moves
        stockfish_moves.sort(key=lambda x: x["priority"])
        stockfish_moves = stockfish_moves[:5]
        
        # Add user-mentioned moves FIRST (highest priority, even if not in Stockfish list)
        new_steps = []
        # Find the position step index in the plan
        position_step_idx = None
        for idx, s in enumerate(plan.steps):
            if s.step_number == position_step_number:
                position_step_idx = idx
                break
        
        if position_step_idx is None:
            print(f"   ⚠️ [EXECUTOR] Could not find position step {position_step_number} in plan")
            return
        
        current_step_num = position_step_number + 1
        
        for move_san in user_mentioned_moves:
            if move_san not in existing_moves:
                new_steps.append(ExecutionStep(
                    step_number=current_step_num + len(new_steps),
                    action_type="investigate_move",
                    parameters={
                        "fen": fen,
                        "move_san": move_san
                    },
                    purpose=f"Test {move_san} (user-requested) and check consequences",
                    tool_to_call="investigator.investigate_move",
                    expected_output=f"Move analysis showing consequences of {move_san}"
                ))
                existing_moves.add(move_san)  # Prevent duplicates
        
        # Then add Stockfish moves
        for move_info in stockfish_moves:
            move_san = move_info["move_san"]
            if move_san not in existing_moves:
                new_steps.append(ExecutionStep(
                    step_number=current_step_num + len(new_steps),
                    action_type="investigate_move",
                    parameters={
                        "fen": fen,
                        "move_san": move_san
                    },
                    purpose=f"Test {move_san} (Stockfish: {move_info['source']}) and check consequences",
                    tool_to_call="investigator.investigate_move",
                    expected_output=f"Move analysis showing consequences of {move_san}"
                ))
                existing_moves.add(move_san)  # Prevent duplicates
        
        # Insert new steps after position investigation
        if new_steps:
            # Insert after the position step
            insert_idx = position_step_idx + 1
            plan.steps[insert_idx:insert_idx] = new_steps
            # Renumber all subsequent steps
            for idx in range(insert_idx + len(new_steps), len(plan.steps)):
                plan.steps[idx].step_number = idx + 1
            
            user_count = len([s for s in new_steps if "user-requested" in s.purpose])
            stockfish_count = len(new_steps) - user_count
            print(f"   ✅ [EXECUTOR] Auto-added {len(new_steps)} move investigations:")
            print(f"      - {user_count} user-requested moves")
            print(f"      - {stockfish_count} Stockfish recommendations: {[s.parameters.get('move_san') for s in new_steps[user_count:]]}")
    
    def _extract_moves_from_intent(self, intent_plan) -> List[str]:
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

    def _suggest_knight_development_moves(self, fen: str, limit: int = 4) -> List[str]:
        """
        Heuristic: if user asks about knight development/castling but doesn't name moves,
        propose a few legal knight moves (SAN) from the current position.
        """
        try:
            b = chess.Board(fen)
            out: List[str] = []
            for mv in b.legal_moves:
                p = b.piece_at(mv.from_square)
                if not p or p.piece_type != chess.KNIGHT:
                    continue
                try:
                    san = b.san(mv)
                except Exception:
                    continue
                if san and san not in out:
                    out.append(san)
                if len(out) >= limit:
                    break
            return out
        except Exception:
            return []

