"""
Deterministic Semantic Story Builder

Purpose:
Turn structured per-move deltas (tags/roles gained/lost) + eval breakdown into a
grounded, polarity-correct, human-readable story scaffold.

Rules:
- Deterministic only (no engine calls, no LLM calls).
- Must not introduce new moves/tags/roles/evals.
- Treat "tag lost" as "property no longer exists" and interpret polarity via heuristics.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import chess


# These are intentionally broad heuristics to avoid test-case overfitting.
# They should be refined incrementally with small, audited additions.
_PROBLEM_TAG_SUBSTRINGS: Tuple[str, ...] = (
    "trapped",
    "undeveloped",
    "hanging",
    "overloaded",
    "exposed",
    "weak",
    "isolated",
    "backward",
    ".bad",  # e.g. tag.bishop.bad
    "shield.missing",
    "king.center.exposed",
)

_BENEFIT_TAG_SUBSTRINGS: Tuple[str, ...] = (
    "bishop.pair",
    "shield.intact",
    "passed",  # conservative: many passed pawn tags should be positive
    "outpost",  # can be context-dependent, but usually beneficial
    "castling.available.",
)

# Low-signal / geometry tags: default to neutral to reduce narrative mistakes.
_NEUTRAL_TAG_PREFIXES: Tuple[str, ...] = (
    "tag.diagonal.",
    "tag.file.",
    "tag.key.",
    "tag.center.",
    "tag.activity.",
    "tag.lever.",
    "tag.color.hole.",
)


_PROBLEM_ROLE_SUBSTRINGS: Tuple[str, ...] = (
    "role.status.trapped",
    "role.status.hanging",
    "role.attacking.overloaded_piece",
)

_BENEFIT_ROLE_SUBSTRINGS: Tuple[str, ...] = (
    "role.develop",
    "role.activity",
    "role.control",
    "role.attacking",  # depends on side, but generally means activity
    "role.defending",
)


def _castling_rights_str(board: chess.Board) -> str:
    parts: List[str] = []
    if board.has_kingside_castling_rights(chess.WHITE):
        parts.append("K")
    if board.has_queenside_castling_rights(chess.WHITE):
        parts.append("Q")
    if board.has_kingside_castling_rights(chess.BLACK):
        parts.append("k")
    if board.has_queenside_castling_rights(chess.BLACK):
        parts.append("q")
    return "".join(parts) if parts else "-"


def _classify_tag(tag_name: str) -> str:
    """
    Returns: "problem" | "benefit" | "neutral"
    """
    if not tag_name:
        return "neutral"
    t = tag_name.lower()

    if any(t.startswith(p) for p in _NEUTRAL_TAG_PREFIXES):
        return "neutral"

    if any(s in t for s in _PROBLEM_TAG_SUBSTRINGS):
        return "problem"
    if any(s in t for s in _BENEFIT_TAG_SUBSTRINGS):
        return "benefit"
    return "neutral"


def _classify_role(role_name: str) -> str:
    """
    Returns: "problem" | "benefit" | "neutral"
    """
    if not role_name:
        return "neutral"
    r = role_name.lower()
    if any(s in r for s in _PROBLEM_ROLE_SUBSTRINGS):
        return "problem"
    if any(s in r for s in _BENEFIT_ROLE_SUBSTRINGS):
        return "benefit"
    return "neutral"


def _polarity_from_classification(kind: str, change: str) -> str:
    """
    kind: "problem"|"benefit"|"neutral"
    change: "gained"|"lost"
    Returns: "positive"|"negative"|"neutral"
    """
    if kind == "neutral":
        return "neutral"
    if kind == "problem":
        # A problem appearing is bad; a problem disappearing is good.
        return "negative" if change == "gained" else "positive"
    if kind == "benefit":
        # A benefit appearing is good; a benefit disappearing is bad.
        return "positive" if change == "gained" else "negative"
    return "neutral"


def _meaning_for_castling_tag(tag_name: str, change: str) -> Optional[str]:
    # Availability tags
    if tag_name.startswith("tag.castling.available."):
        side = "kingside" if tag_name.endswith(".kingside") else "queenside" if tag_name.endswith(".queenside") else "castling"
        return (
            f"{side} castling became legal"
            if change == "gained"
            else f"{side} castling is no longer legal"
        )

    # Rights-lost tags (typically only gained)
    if tag_name.startswith("tag.castling.rights.lost"):
        if tag_name.endswith(".kingside"):
            return "kingside castling rights were lost"
        if tag_name.endswith(".queenside"):
            return "queenside castling rights were lost"
        return "castling rights were lost"

    # Rights-present-but-not-legal tags
    if tag_name.startswith("tag.castling.rights."):
        if tag_name.endswith(".kingside"):
            return "kingside castling rights exist (castling not currently legal)"
        if tag_name.endswith(".queenside"):
            return "queenside castling rights exist (castling not currently legal)"
        return None

    return None


def _meaning_for_generic(name: str, kind: str, change: str, item_type: str) -> str:
    # Keep these intentionally generic; the summariser can paraphrase.
    if kind == "problem":
        if change == "lost":
            return f"{item_type} problem was resolved"
        return f"{item_type} problem appeared"
    if kind == "benefit":
        if change == "gained":
            return f"{item_type} benefit appeared"
        return f"{item_type} benefit was removed"
    return f"{item_type} property changed"


def build_semantic_story(
    investigation_result: Any,
    evidence_eval: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Build a semantic story from an InvestigationResult-like object.

    Expects (if present):
    - evidence_starting_fen
    - evidence_pgn_line
    - evidence_main_line_moves
    - evidence_per_move_deltas: [{move, tags_gained, tags_lost, roles_gained, roles_lost}]
    - evidence_tags_gained_net / evidence_tags_lost_net
    - evidence_roles_gained_net / evidence_roles_lost_net
    """
    evidence_eval = evidence_eval or {}

    starting_fen = getattr(investigation_result, "evidence_starting_fen", None)
    board: Optional[chess.Board] = None
    if starting_fen:
        try:
            board = chess.Board(starting_fen)
        except Exception:
            board = None

    story: Dict[str, Any] = {
        "starting": {
            "fen": starting_fen,
            "side_to_move": ("white" if (board and board.turn == chess.WHITE) else "black" if board else None),
            "castling_rights": _castling_rights_str(board) if board else None,
            "eval": {
                "total": evidence_eval.get("eval_start"),
                "material": evidence_eval.get("material_start"),
                "positional": evidence_eval.get("positional_start"),
            },
        },
        "pgn_line": getattr(investigation_result, "evidence_pgn_line", None),
        "moves": [],
        "net": {
            "positive": [],
            "negative": [],
            "neutral": [],
            "net_eval_delta_total": evidence_eval.get("eval_delta"),
        },
        "guards": {
            "no_new_analysis": True,
            "grounding": "Meanings are derived from tag/role names + delta direction only.",
        },
    }

    net_pos: List[str] = []
    net_neg: List[str] = []
    net_neu: List[str] = []

    per_move = list(getattr(investigation_result, "evidence_per_move_deltas", []) or [])
    for idx, move_data in enumerate(per_move, start=1):
        move_san = move_data.get("move") or ""
        events: List[Dict[str, Any]] = []

        # Tags gained/lost
        for change_key, change in (("tags_gained", "gained"), ("tags_lost", "lost")):
            for tag in (move_data.get(change_key) or []):
                tag_name = tag if isinstance(tag, str) else str(tag)
                kind = _classify_tag(tag_name)
                # Drop clutter/geometry tags entirely from the semantic story.
                # They remain available in raw/structured evidence, but they add noise here.
                if kind == "neutral" and any(tag_name.lower().startswith(p) for p in _NEUTRAL_TAG_PREFIXES):
                    continue
                polarity = _polarity_from_classification(kind, change)
                meaning = _meaning_for_castling_tag(tag_name, change) or _meaning_for_generic(tag_name, kind, change, "tag")
                ev = {
                    "type": "tag",
                    "change": change,
                    "name": tag_name,
                    "meaning": meaning,
                    "polarity": polarity,
                    "classification": kind,
                }
                events.append(ev)
                if polarity == "positive":
                    net_pos.append(meaning)
                elif polarity == "negative":
                    net_neg.append(meaning)
                else:
                    net_neu.append(meaning)

        # Roles gained/lost
        for change_key, change in (("roles_gained", "gained"), ("roles_lost", "lost")):
            for role in (move_data.get(change_key) or []):
                role_name = role if isinstance(role, str) else str(role)
                kind = _classify_role(role_name)
                polarity = _polarity_from_classification(kind, change)
                meaning = _meaning_for_generic(role_name, kind, change, "role")
                ev = {
                    "type": "role",
                    "change": change,
                    "name": role_name,
                    "meaning": meaning,
                    "polarity": polarity,
                    "classification": kind,
                }
                events.append(ev)
                if polarity == "positive":
                    net_pos.append(meaning)
                elif polarity == "negative":
                    net_neg.append(meaning)
                else:
                    net_neu.append(meaning)

        story["moves"].append(
            {
                "ply": idx,
                "move_san": move_san,
                "events": events,
                # Per-move eval not currently available in evidence_eval; keep explicit None fields.
                "eval_note": {
                    "delta_total": None,
                    "delta_material": None,
                    "delta_positional": None,
                },
            }
        )

    # Deduplicate net buckets while preserving order.
    def _dedupe(seq: List[str]) -> List[str]:
        seen = set()
        out: List[str] = []
        for x in seq:
            if x in seen:
                continue
            seen.add(x)
            out.append(x)
        return out

    story["net"]["positive"] = _dedupe(net_pos)
    story["net"]["negative"] = _dedupe(net_neg)
    story["net"]["neutral"] = _dedupe(net_neu)

    return story


