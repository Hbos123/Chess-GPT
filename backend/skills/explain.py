from __future__ import annotations

import os
import json
from typing import Any, Dict, List

from command_protocol import render_command
from minimal_prompts import MIN_SYSTEM_PROMPT_V1, EXPLAIN_WITH_FACTS_CONTRACT_V1


def _compact_for_prompt(
    obj: Any,
    *,
    max_depth: int = 8,
    max_str_len: int = 800,
    max_list_len: int = 30,
    max_dict_items: int = 60,
) -> Any:
    """
    Deterministically shrink large nested artifacts (PGNs, trees, evidence blobs) so
    the explain_with_facts prompt stays under the model context window.
    """
    if max_depth <= 0:
        return "…<max_depth>"
    if obj is None:
        return None
    if isinstance(obj, (bool, int, float)):
        return obj
    if isinstance(obj, str):
        return (obj[:max_str_len] + "…<truncated>") if len(obj) > max_str_len else obj
    if isinstance(obj, list):
        out: List[Any] = []
        for it in obj[:max_list_len]:
            out.append(
                _compact_for_prompt(
                    it,
                    max_depth=max_depth - 1,
                    max_str_len=max_str_len,
                    max_list_len=max_list_len,
                    max_dict_items=max_dict_items,
                )
            )
        if len(obj) > max_list_len:
            out.append(f"…<+{len(obj) - max_list_len} more>")
        return out
    if isinstance(obj, dict):
        out2: Dict[str, Any] = {}
        keys = list(obj.keys())
        keys.sort(key=lambda x: str(x))
        for k in keys[:max_dict_items]:
            kk = str(k)
            out2[kk] = _compact_for_prompt(
                obj.get(k),
                max_depth=max_depth - 1,
                max_str_len=max_str_len,
                max_list_len=max_list_len,
                max_dict_items=max_dict_items,
            )
        if len(keys) > max_dict_items:
            out2["…<truncated_keys>"] = f"+{len(keys) - max_dict_items} keys"
        return out2
    try:
        return _compact_for_prompt(
            repr(obj),
            max_depth=max_depth - 1,
            max_str_len=max_str_len,
            max_list_len=max_list_len,
            max_dict_items=max_dict_items,
        )
    except Exception:
        return "<unrepr>"


def _cmd_len_for_facts(facts: Dict[str, Any]) -> int:
    try:
        payload = {"command": "EXPLAIN_WITH_FACTS", "input": {"facts": (facts or {})}}
        return len("COMMAND\n" + json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    except Exception:
        return 10**9


def _select_facts_for_prompt(facts: Dict[str, Any]) -> Dict[str, Any]:
    """
    Keep the explainer input small and stable.
    The UI still receives full baseline artifacts separately (baseline_intuition).
    """
    if not isinstance(facts, dict):
        return {}
    out: Dict[str, Any] = {}

    # Core small fields
    for k in [
        "eval_cp",
        "recommended_move",
        "recommended_reason",
        "self_check",
        "pgn_citations",
        "user_goals",
        "move_compare",
        "chat_history",
        # Personal review / game review artifacts (kept compact by the compactor)
        "game_review",
    ]:
        if k in facts:
            out[k] = facts.get(k)

    # Extra-cautious shaping for game_review: keep only small, decision-useful fields.
    # Tool results can include huge nested structures (key moments, full PGNs, move tables).
    gr = out.get("game_review")
    if isinstance(gr, dict):
        out_gr: Dict[str, Any] = {}
        for kk in [
            "source_tool",
            "narrative",
            "stats",
            "phase_stats",
            "opening_performance",
            "first_game_ref",
            "selection_rationale",
        ]:
            if kk in gr:
                out_gr[kk] = gr.get(kk)
        # Keep only a few key moments if present
        skm = gr.get("selected_key_moments")
        if isinstance(skm, list):
            out_gr["selected_key_moments"] = skm[:5]
        out["game_review"] = out_gr

    # Compact baseline grounding only
    b = facts.get("baseline")
    if isinstance(b, dict):
        out_b: Dict[str, Any] = {}
        if isinstance(b.get("root"), dict):
            out_b["root"] = b.get("root")
        if isinstance(b.get("evidence"), dict):
            # Prefer the short, citeable line + moves list.
            ev = b.get("evidence") or {}
            out_b["evidence"] = {
                "evidence_pgn_line": ev.get("evidence_pgn_line"),
                "evidence_main_line_moves": ev.get("evidence_main_line_moves") or [],
            }
        # Claims/patterns are helpful but can get large; keep only a few.
        if isinstance(b.get("claims"), list):
            out_b["claims"] = b.get("claims")[:6]
        if isinstance(b.get("pattern_claims"), list):
            out_b["pattern_claims"] = b.get("pattern_claims")[:6]
        # Keep any PGN context very small (full PGN is available to the UI separately).
        if isinstance(b.get("pgn_exploration"), str):
            out_b["pgn_exploration"] = b.get("pgn_exploration")
        out["baseline"] = out_b

    return out


def _shrink_facts_until_fit(*, facts: Dict[str, Any], max_cmd_chars: int) -> Dict[str, Any]:
    """
    If the final command envelope is still too large, drop the heaviest keys first.
    Keeps baseline root + recommended move info intact.
    """
    if not isinstance(facts, dict):
        return {}
    f = dict(facts)
    # Drop heaviest keys first (deterministic order)
    heavy_keys = [
        "memory",
        "evidence",
        "facts_card",
        "candidate_moves",
        "top_moves",
        # conversation can bloat quickly across turns
        "chat_history",
        # game review can be large; _select_facts_for_prompt should already shrink it,
        # but keep this as a last-resort drop.
        "game_review",
    ]
    for hk in heavy_keys:
        if _cmd_len_for_facts(f) <= max_cmd_chars:
            break
        if hk in f:
            f.pop(hk, None)
    return f


def _join_san_line(pv_san: Any, *, max_plies: int = 10, max_chars: int = 140) -> str:
    if not isinstance(pv_san, list):
        return ""
    moves = []
    for m in pv_san[: max_plies]:
        if isinstance(m, str) and m.strip():
            moves.append(m.strip())
    s = " ".join(moves).strip()
    if not s:
        return ""
    return (s[:max_chars] + "…") if len(s) > max_chars else s


def _wants_alternatives(user_message: str) -> bool:
    m = (user_message or "").lower()
    import re
    return bool(
        re.search(
            r"\b(alternatives?|other options?|another option|what else|instead|compare|vs)\b",
            m,
        )
    )


def _extract_user_goals(user_message: str) -> list[str]:
    m = (user_message or "").lower()
    goals: list[str] = []
    if "castle" in m:
        goals.append("castle your king safely")
    if "knight" in m and ("develop" in m or "get" in m or "out" in m):
        goals.append("get your knight developed")
    if "develop" in m or "development" in m:
        goals.append("develop your pieces")
    if "king safety" in m:
        goals.append("improve king safety")
    # keep small + generic
    return goals[:3]


def _extract_pv_citations(*, facts: Dict[str, Any], include_alternatives: bool) -> Dict[str, Any]:
    """
    Build small, grounded SAN line citations from facts.
    We prefer facts.facts_card.top_moves[].pv_san, but fall back to facts.top_moves.
    """
    fc = facts.get("facts_card") if isinstance(facts, dict) else None
    top = None
    if isinstance(fc, dict) and isinstance(fc.get("top_moves"), list):
        top = fc.get("top_moves")
    elif isinstance(facts.get("top_moves"), list):
        top = facts.get("top_moves")

    recommended = None
    if isinstance(facts.get("recommended_move"), str) and facts.get("recommended_move").strip():
        recommended = facts.get("recommended_move").strip()

    # Determine PV for recommended move.
    rec_line = ""
    alt_lines = []
    if isinstance(top, list):
        # If no explicit recommended move, default to top1.
        if not recommended:
            try:
                m0 = top[0]
                if isinstance(m0, dict) and isinstance(m0.get("san"), str):
                    recommended = m0.get("san")
            except Exception:
                pass

        for i, tm in enumerate(top[:3]):
            if not isinstance(tm, dict):
                continue
            san = tm.get("san") or tm.get("move_san")
            pv = tm.get("pv_san")
            line = _join_san_line(pv, max_plies=(10 if i == 0 else 6), max_chars=140)
            if not line:
                continue
            if recommended and isinstance(san, str) and san.strip() == recommended and not rec_line:
                rec_line = line
            elif include_alternatives and len(alt_lines) < 1:
                alt_lines.append({"move": (san if isinstance(san, str) else None), "line": line})

    out: Dict[str, Any] = {}
    if rec_line:
        out["recommended_line_san"] = rec_line
    if alt_lines:
        out["alternative_lines_san"] = alt_lines
    return out


async def explain_with_facts(
    *,
    llm_router,
    task_id: str,
    user_message: str,
    context: Dict[str, Any],
    facts: Dict[str, Any],
    model: str,
    temperature: float,
) -> Dict[str, Any]:
    """
    Single-pass explanation skill: feed compact facts and request a helpful answer + UI commands.
    """
    include_alts = _wants_alternatives(user_message)
    citations = _extract_pv_citations(facts=facts if isinstance(facts, dict) else {}, include_alternatives=include_alts)
    facts_for_prompt = facts if isinstance(facts, dict) else {}
    if citations:
        # Keep this small and explicitly grounded.
        facts_for_prompt = {**facts_for_prompt, "pgn_citations": citations}
    goals = _extract_user_goals(user_message)
    if goals:
        facts_for_prompt = {**facts_for_prompt, "user_goals": goals}

    # Hard cap prompt size to avoid vLLM 8k context errors.
    max_cmd_chars = int(os.getenv("EXPLAIN_WITH_FACTS_MAX_INPUT_CHARS", "9000"))
    facts_for_prompt = _select_facts_for_prompt(facts_for_prompt)
    facts_for_prompt = _compact_for_prompt(
        facts_for_prompt,
        max_depth=int(os.getenv("EXPLAIN_WITH_FACTS_COMPACT_MAX_DEPTH", "8")),
        max_str_len=int(os.getenv("EXPLAIN_WITH_FACTS_COMPACT_MAX_STR", "500")),
        max_list_len=int(os.getenv("EXPLAIN_WITH_FACTS_COMPACT_MAX_LIST", "30")),
        max_dict_items=int(os.getenv("EXPLAIN_WITH_FACTS_COMPACT_MAX_DICT", "60")),
    )
    facts_for_prompt = _shrink_facts_until_fit(facts=facts_for_prompt, max_cmd_chars=max_cmd_chars)

    cmd = render_command(
        command="EXPLAIN_WITH_FACTS",
        input={
            "user_message": user_message,
            "facts": facts_for_prompt,
            "context": {k: context.get(k) for k in ["mode", "fen", "pgn", "last_move"] if k in context},
        },
        constraints={"json_only": True, "style": "conversational"},
    )
    # Keep user-visible reasoning in the 'main' subsession only.
    try:
        res = llm_router.complete_json(
            session_id=task_id,
            stage="explain_with_facts",
            subsession="explain",
            system_prompt=MIN_SYSTEM_PROMPT_V1,
            task_seed=EXPLAIN_WITH_FACTS_CONTRACT_V1,
            user_text=cmd,
            model=model,
            temperature=temperature,
            max_tokens=int(os.getenv("EXPLAIN_WITH_FACTS_MAX_TOKENS", "1200")),
        )
        return res if isinstance(res, dict) else {"explanation": str(res), "ui_commands": []}
    except Exception as e:
        import traceback
        print(f"❌ [EXPLAIN_WITH_FACTS] JSON completion failed: {type(e).__name__}: {e}", flush=True)
        tb = traceback.format_exc()
        try:
            print(tb, flush=True)
        except Exception:
            pass
        # Return structured error details so the frontend "Raw Data" panel can show the cause
        # even if log streaming is unavailable.
        return {
            "explanation": "I encountered an error generating the explanation.",
            "ui_commands": [],
            "error": {
                "stage": "explain_with_facts",
                "type": type(e).__name__,
                "message": str(e),
                "traceback": (tb[:2000] + ("…<truncated>" if len(tb) > 2000 else "")) if isinstance(tb, str) else None,
            },
        }


