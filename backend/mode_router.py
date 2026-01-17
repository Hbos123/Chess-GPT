from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class ModePolicy:
    name: str
    max_time_s: float

    light_depth: int
    light_lines: int

    # Candidate selection / compare-jump
    cursor_loop_enabled: bool
    cursor_topn: int
    compare_enabled: bool
    compare_topn: int
    compare_depth: int

    # Optional escalation
    deep_on_high_confidence_required: bool
    deep_depth: int
    deep_lines: int


class ModeRouter:
    """
    Deterministic router for per-mode budgets and investigation behavior.
    Keep this mostly deterministic and driven by:
    - frontend mode (PLAY/ANALYZE/TACTICS/DISCUSS)
    - interpreter mode if present
    - user message shape (wants suggestions vs pure question)
    """

    def __init__(self) -> None:
        pass

    @staticmethod
    def _norm_mode(mode: Any) -> str:
        m = str(mode or "").strip().upper()
        if m in {"PLAY", "ANALYZE", "TACTICS", "DISCUSS"}:
            return m
        return ""

    @staticmethod
    def _wants_move_suggestions(msg: str) -> bool:
        m = (msg or "").lower()
        return bool(
            re.search(
                r"\b(best move|what should i|what do i|how do i|how can i|next move|progress|plan|idea|recommend|suggest)\b",
                m,
            )
        )

    def policy_for(self, *, context: Dict[str, Any], intent_plan: Any, user_message: str) -> ModePolicy:
        context_mode = self._norm_mode((context or {}).get("mode"))
        intent_mode = self._norm_mode(getattr(intent_plan, "mode", None))
        mode = context_mode or intent_mode or "ANALYZE"

        # Global time budget (cap by env, then allow per-mode baselines).
        try:
            max_time_s = float(os.getenv("TASK_MAX_TIME_S", "18"))
        except Exception:
            max_time_s = 18.0

        # Per-mode defaults (env still wins if explicitly set).
        if mode == "PLAY":
            base = dict(light_depth=8, light_lines=2, compare_depth=10, deep_depth=14, deep_lines=3)
        elif mode == "TACTICS":
            base = dict(light_depth=12, light_lines=3, compare_depth=12, deep_depth=18, deep_lines=4)
        elif mode == "DISCUSS":
            base = dict(light_depth=8, light_lines=2, compare_depth=10, deep_depth=14, deep_lines=3)
        else:  # ANALYZE
            base = dict(light_depth=10, light_lines=3, compare_depth=12, deep_depth=16, deep_lines=4)

        # Allow env overrides (kept for ops tuning).
        light_depth = int(os.getenv("ENGINE_LIGHT_DEPTH", str(base["light_depth"])))
        light_lines = int(os.getenv("ENGINE_LIGHT_LINES", str(base["light_lines"])))
        deep_depth = int(os.getenv("ENGINE_DEEP_DEPTH", str(base["deep_depth"])))
        deep_lines = int(os.getenv("ENGINE_DEEP_LINES", str(base["deep_lines"])))

        cursor_loop_enabled = str(os.getenv("ENABLE_CURSOR_LOOP", "true")).lower().strip() == "true"
        compare_enabled = str(os.getenv("ENABLE_CURSOR_LOOP_COMPARE", "true")).lower().strip() == "true"

        cursor_topn = max(1, min(int(os.getenv("CURSOR_LOOP_TOPN", "5")), 8))
        compare_topn = max(2, min(int(os.getenv("CURSOR_LOOP_COMPARE_TOPN", "3")), 8))
        compare_depth = int(os.getenv("CURSOR_LOOP_COMPARE_DEPTH", str(base["compare_depth"])))

        # DISCUSS: if user isn't asking for move suggestions, we still allow an engine-light fact pass,
        # but the cursor-loop selection (choose a move) can be disabled to avoid over-prescribing.
        wants_suggestions = self._wants_move_suggestions(user_message or "")
        if mode == "DISCUSS" and not wants_suggestions:
            # Still compute eval/top moves, but don't "pick" a move unless requested.
            cursor_loop_enabled = False

        deep_on_high = True
        return ModePolicy(
            name=mode,
            max_time_s=max_time_s,
            light_depth=light_depth,
            light_lines=light_lines,
            cursor_loop_enabled=cursor_loop_enabled,
            cursor_topn=cursor_topn,
            compare_enabled=compare_enabled,
            compare_topn=compare_topn,
            compare_depth=compare_depth,
            deep_on_high_confidence_required=deep_on_high,
            deep_depth=deep_depth,
            deep_lines=deep_lines,
        )

    async def run_investigation(
        self,
        *,
        policy: ModePolicy,
        fen: str,
        context: Dict[str, Any],
        user_message: str,
        evaluate_position_fn,
        compare_moves_fn,
        judge_compare_moves_fn,
        send_event,
        engine_queue=None,
        engine_pool_instance=None,
        tool_executor=None,
        enable_facts_ready_event: bool = True,
        t0: float,
    ) -> Dict[str, Any]:
        """
        Runs the engine-first investigation phase under a deterministic policy.

        Returns:
          {
            "events": [<sse_event_str>...],
            "result": {light_result, chosen_move, chosen_reason, compare_out, judge_out}
          }
        """
        events = []
        # Light eval:
        # Prefer reusing baseline D2/D16 if present (so we don't spend an extra Stockfish call
        # after baseline has already computed best move/eval).
        reuse_baseline = str(os.getenv("CONTROLLER_REUSE_BASELINE_FOR_LIGHT", "true")).lower().strip() == "true"
        light_result: Dict[str, Any] = {}
        if reuse_baseline and isinstance(context, dict):
            try:
                bi = context.get("baseline_intuition")
                scan_root = (bi or {}).get("scan_root") if isinstance(bi, dict) else None
                root = (scan_root or {}).get("root") if isinstance(scan_root, dict) else None
                evidence = (scan_root or {}).get("evidence") if isinstance(scan_root, dict) else None
                best = (root or {}).get("best_move_d16_san") if isinstance(root, dict) else None
                ev16 = (root or {}).get("eval_d16") if isinstance(root, dict) else None
                pv = (evidence or {}).get("evidence_main_line_moves") if isinstance(evidence, dict) else None
                if isinstance(best, str) and best.strip() and isinstance(ev16, (int, float)):
                    eval_cp = int(round(float(ev16) * 100.0))
                    pv_san = [m for m in (pv or []) if isinstance(m, str) and m.strip()][:10] if isinstance(pv, list) else []
                    light_result = {
                        "eval_cp": eval_cp,
                        "top_moves": [{"move_san": best.strip(), "eval_cp": eval_cp, "pv_san": pv_san}],
                        "pv_san": pv_san,
                        "from_cache": True,
                    }
            except Exception:
                light_result = {}

        if not light_result:
            light_result = await evaluate_position_fn(
                tool_executor=tool_executor,
                context=context,
                engine_queue=engine_queue,
                engine_pool_instance=engine_pool_instance,
                depth=policy.light_depth,
                lines=policy.light_lines,
                light_mode=True,
            )
        events.append(send_event("milestone", {"name": "engine_light_done", "timestamp": time.time()}))

        chosen_move: Optional[str] = None
        chosen_reason: str = ""
        compare_out: Optional[Dict[str, Any]] = None
        judge_out: Optional[Dict[str, Any]] = None

        # Candidate selection + optional compare/judge
        if policy.cursor_loop_enabled and isinstance(light_result, dict) and self._wants_move_suggestions(user_message or ""):
            top_moves = light_result.get("top_moves") or []
            candidates: list[str] = []
            if isinstance(top_moves, list):
                for tm in top_moves:
                    if not isinstance(tm, dict):
                        continue
                    ms = tm.get("move_san")
                    if isinstance(ms, str) and ms.strip():
                        candidates.append(ms.strip())
            candidates = candidates[: policy.cursor_topn]

            if candidates:
                if policy.compare_enabled and len(candidates) >= 2:
                    # Respect time budget before expensive compares
                    if (time.time() - t0) >= policy.max_time_s:
                        return {
                            "events": events,
                            "result": {
                                "light_result": light_result,
                                "chosen_move": None,
                                "chosen_reason": "budget_time_exceeded_before_compare",
                                "compare_out": None,
                                "judge_out": None,
                            },
                        }
                    compare_candidates = candidates[: min(policy.compare_topn, len(candidates))]
                    comp = await compare_moves_fn(
                        tool_executor=tool_executor,
                        context=context,
                        fen=fen,
                        moves_san=compare_candidates,
                        depth=policy.compare_depth,
                    )
                    judged = judge_compare_moves_fn(comp)
                    compare_out = comp if isinstance(comp, dict) else None
                    judge_out = judged if isinstance(judged, dict) else None
                    winner = (judged or {}).get("winner") if isinstance(judged, dict) else None
                    if isinstance(winner, str) and winner.strip():
                        chosen_move = winner.strip()
                        chosen_reason = "compare_judge"
                    else:
                        chosen_move = compare_candidates[0]
                        chosen_reason = "engine_top1_fallback"
                else:
                    chosen_move = candidates[0]
                    chosen_reason = "engine_top1"

                if enable_facts_ready_event:
                    brief_top = []
                    if isinstance(top_moves, list):
                        for tm in top_moves[: min(len(top_moves), 5)]:
                            if not isinstance(tm, dict):
                                continue
                            brief_top.append({"move": tm.get("move_san"), "eval_cp": tm.get("eval_cp")})
                    events.append(
                        send_event(
                        "facts_ready",
                        {
                            "eval_cp": light_result.get("eval_cp") if isinstance(light_result, dict) else None,
                            "recommended_move": chosen_move,
                            "recommended_reason": chosen_reason,
                            "top_moves": brief_top,
                        },
                        )
                    )

        return {
            "events": events,
            "result": {
                "light_result": light_result,
                "chosen_move": chosen_move,
                "chosen_reason": chosen_reason,
                "compare_out": compare_out,
                "judge_out": judge_out,
            },
        }


