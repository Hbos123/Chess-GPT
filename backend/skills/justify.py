from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional, Tuple

from command_protocol import render_command
from minimal_prompts import MIN_SYSTEM_PROMPT_V1, JUSTIFY_FROM_EVIDENCE_CONTRACT_V1


def _extract_user_goals(user_message: str) -> List[str]:
    m = (user_message or "").lower()
    goals: List[str] = []
    if "castle" in m:
        goals.append("castle your king safely")
    if "knight" in m and ("develop" in m or "get" in m or "out" in m):
        goals.append("get your knight developed")
    if "develop" in m or "development" in m:
        goals.append("develop your pieces")
    return goals[:3]


def _extract_recommended_line(facts: Dict[str, Any]) -> str:
    """
    Prefer the PV for the recommended move from facts_card.top_moves, otherwise first PV available.
    """
    fc = facts.get("facts_card") if isinstance(facts, dict) else None
    top = fc.get("top_moves") if isinstance(fc, dict) else None
    if not isinstance(top, list):
        top = facts.get("top_moves") if isinstance(facts.get("top_moves"), list) else None
    rec = facts.get("recommended_move") if isinstance(facts.get("recommended_move"), str) else None
    if isinstance(top, list):
        for tm in top[:3]:
            if not isinstance(tm, dict):
                continue
            san = tm.get("san") or tm.get("move_san")
            pv = tm.get("pv_san")
            if rec and isinstance(san, str) and san.strip() != rec.strip():
                continue
            if isinstance(pv, list):
                moves = [str(x).strip() for x in pv[:10] if isinstance(x, str) and str(x).strip()]
                if moves:
                    return " ".join(moves)
        for tm in top[:3]:
            if not isinstance(tm, dict):
                continue
            pv = tm.get("pv_san")
            if isinstance(pv, list):
                moves = [str(x).strip() for x in pv[:10] if isinstance(x, str) and str(x).strip()]
                if moves:
                    return " ".join(moves)
    return ""


def _sanitize_story(s: str) -> str:
    t = (s or "").strip()
    # strip any accidental bullets/headings
    t = re.sub(r"^\s*[-*]\s+", "", t)
    t = t.replace("tag.", "")  # last-ditch; contract should prevent this
    return t.strip()


def _looks_like_square_influence_sentence(s: str) -> bool:
    m = (s or "").lower()
    return ("influence over squares" in m) or bool(re.search(r"\bsquares\s+[a-h][1-8]", m))


def _pv_moves_4plies(line: str) -> List[str]:
    toks = [t for t in (line or "").split() if t]
    return toks[:4]


def _sanitize_worded_pv(worded: Any, pv_moves: List[str]) -> List[Dict[str, str]]:
    """
    Enforce: 4 plies max, moves must match pv_moves exactly, preserve order.
    """
    pv_set = set(pv_moves or [])
    out: List[Dict[str, str]] = []
    if not isinstance(worded, list):
        return out
    for item in worded:
        if not isinstance(item, dict):
            continue
        mv = item.get("move")
        why = item.get("why")
        if not (isinstance(mv, str) and mv.strip() and mv.strip() in pv_set):
            continue
        if not (isinstance(why, str) and why.strip()):
            continue
        out.append({"move": mv.strip(), "why": _sanitize_story(why)})
    # Reorder to match pv_moves, keep only first 4.
    ordered: List[Dict[str, str]] = []
    for mv in pv_moves:
        for it in out:
            if it["move"] == mv:
                ordered.append(it)
                break
    return ordered[: len(pv_moves)]


async def justify_from_evidence(
    *,
    llm_router,
    task_id: str,
    user_message: str,
    facts: Dict[str, Any],
    model: str,
    temperature: float,
) -> Dict[str, Any]:
    goals = _extract_user_goals(user_message)
    line = _extract_recommended_line(facts)
    pv_moves = _pv_moves_4plies(line)

    ev = facts.get("evidence") if isinstance(facts, dict) else None
    tag_examples = []
    dev_examples = []
    pv_deltas = []
    if isinstance(ev, dict):
        te = ev.get("tag_examples")
        if isinstance(te, list):
            for x in te[:2]:
                if isinstance(x, dict) and isinstance(x.get("sentence"), str) and x.get("sentence").strip():
                    tag_examples.append(x.get("sentence").strip())
        dc = ev.get("development_counterfactuals")
        if isinstance(dc, list):
            for d in dc[:2]:
                if not isinstance(d, dict):
                    continue
                mv = d.get("move")
                delta = d.get("delta_cp_vs_best")
                ln = d.get("line_san")
                if isinstance(mv, str) and mv.strip() and isinstance(ln, str) and ln.strip():
                    if isinstance(delta, (int, float)):
                        dev_examples.append(f"For example, if you try {mv.strip()} immediately, it scores worse by {int(delta)}cp: {ln.strip()}")
                    else:
                        dev_examples.append(f"For example, if you try {mv.strip()} immediately, it leads to a worse position: {ln.strip()}")
        # Extract per-ply deltas (deterministic, move-by-move evidence)
        pv_deltas_raw = ev.get("pv_move_deltas")
        if isinstance(pv_deltas_raw, list):
            for delta_entry in pv_deltas_raw:
                if not isinstance(delta_entry, dict):
                    continue
                move = delta_entry.get("move")
                tags_gained = delta_entry.get("tags_gained", [])
                tags_lost = delta_entry.get("tags_lost", [])
                theme_changes = delta_entry.get("theme_changes", {})
                geometry = delta_entry.get("geometry", {})
                if isinstance(move, str) and move.strip():
                    # Format for LLM: human-readable summary
                    delta_summary = {
                        "move": move.strip(),
                        "tags_gained": tags_gained[:5],  # Limit to avoid bloat
                        "tags_lost": tags_lost[:5],
                        "theme_changes": theme_changes,
                        "geometry": geometry,
                    }
                    pv_deltas.append(delta_summary)

    cmd = render_command(
        command="JUSTIFY_FROM_EVIDENCE",
        input={
            "user_goals": goals,
            "recommended_move": facts.get("recommended_move"),
            "recommended_line_san": line,
            "pv_moves": pv_moves,
            "material_summary": (facts.get("facts_card") or {}).get("material_summary") if isinstance(facts.get("facts_card"), dict) else None,
            "positional_summary": (facts.get("facts_card") or {}).get("positional_summary") if isinstance(facts.get("facts_card"), dict) else None,
            "positional_factors": (facts.get("facts_card") or {}).get("positional_factors") if isinstance(facts.get("facts_card"), dict) else None,
            "tag_example_sentences": tag_examples,
            "dev_counterfactual_sentences": dev_examples,
            "pv_move_deltas": pv_deltas,  # Per-ply deltas: what changed on each move
        },
        constraints={"json_only": True},
    )

    try:
        out = llm_router.complete_json(
            session_id=task_id,
            stage="justify_from_evidence",
            subsession="justify",
            system_prompt=MIN_SYSTEM_PROMPT_V1,
            task_seed=JUSTIFY_FROM_EVIDENCE_CONTRACT_V1,
            user_text=cmd,
            model=model,
            temperature=temperature,
        )
    except Exception:
        # Single repair retry: ask for corrected JSON only (keeps pipeline resilient).
        try:
            repair = render_command(
                command="REPAIR_JSON",
                input={"instruction": "Return ONLY valid JSON for JUSTIFY_FROM_EVIDENCE.", "bad_output": "non_json_or_invalid_json"},
                constraints={"json_only": True},
            )
            out = llm_router.complete_json(
                session_id=task_id,
                stage="justify_from_evidence",
                subsession="justify_repair",
                system_prompt=MIN_SYSTEM_PROMPT_V1,
                task_seed=JUSTIFY_FROM_EVIDENCE_CONTRACT_V1,
                user_text=repair,
                model=model,
                temperature=0.0,
            )
        except Exception:
            out = {}

    # sanitize
    if isinstance(out, dict):
        ss = out.get("story_sentences")
        if isinstance(ss, list):
            out["story_sentences"] = [_sanitize_story(x) for x in ss if isinstance(x, str) and _sanitize_story(x)]
        out["worded_pv"] = _sanitize_worded_pv(out.get("worded_pv"), pv_moves=pv_moves)
    return out if isinstance(out, dict) else {}


