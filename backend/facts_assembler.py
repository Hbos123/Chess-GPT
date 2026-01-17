from __future__ import annotations

import chess
from typing import Any, Dict, List, Optional

from facts_models import CandidateMove, FactsCard
from material_calculator import calculate_material_balance, get_material_count


def _side_to_move_from_fen(fen: str) -> str:
    try:
        b = chess.Board(fen)
        return "white" if b.turn == chess.WHITE else "black"
    except Exception:
        # Default: assume white to move (safe-ish)
        return "white"


def _human_piece_name(key: str, n: int) -> str:
    base = {
        "pawns": "pawn",
        "knights": "knight",
        "bishops": "bishop",
        "rooks": "rook",
        "queens": "queen",
    }.get(key, key)
    if n == 1:
        return base
    return base + "s"


def _material_summary_from_counts(counts: Dict[str, Any]) -> str:
    """
    Produce a compact human summary of material imbalance.
    Prefers chess-native phrasing for common patterns (minor-for-pawns, exchange).
    """
    if not isinstance(counts, dict):
        return ""
    w = counts.get("white") if isinstance(counts.get("white"), dict) else {}
    b = counts.get("black") if isinstance(counts.get("black"), dict) else {}
    diffs = {}
    for k in ["pawns", "knights", "bishops", "rooks", "queens"]:
        try:
            diffs[k] = int(w.get(k, 0)) - int(b.get(k, 0))
        except Exception:
            diffs[k] = 0

    if all(v == 0 for v in diffs.values()):
        return "Material is equal."

    side = "White" if sum(diffs.values()) >= 0 else "Black"
    # Determine which side is ahead in material cp-like terms (prefer pawns first)
    # We'll use the diffs signs to express trade-offs.

    pawns = diffs["pawns"]
    minors = diffs["knights"] + diffs["bishops"]
    rooks = diffs["rooks"]
    queens = diffs["queens"]

    # Common: minor for 2+ pawns
    if abs(minors) == 1 and pawns != 0 and (minors > 0) != (pawns > 0):
        if minors > 0:
            return f"White has a minor piece for {abs(pawns)} pawn{'' if abs(pawns)==1 else 's'}."
        else:
            return f"Black has a minor piece for {abs(pawns)} pawn{'' if abs(pawns)==1 else 's'}."

    # Exchange up (rook for minor)
    if rooks != 0 and minors != 0 and (rooks > 0) != (minors > 0) and abs(rooks) == 1 and abs(minors) == 1:
        if rooks > 0:
            extra = f" and {abs(pawns)} pawn{'' if abs(pawns)==1 else 's'}" if pawns > 0 else ""
            return f"White is up the exchange{extra}."
        else:
            extra = f" and {abs(pawns)} pawn{'' if abs(pawns)==1 else 's'}" if pawns < 0 else ""
            return f"Black is up the exchange{extra}."

    # Otherwise, list net extras by side.
    ahead = "white" if (pawns * 1 + minors * 3 + rooks * 5 + queens * 9) > 0 else "black"
    parts = []
    for k in ["queens", "rooks", "bishops", "knights", "pawns"]:
        d = diffs[k]
        if d == 0:
            continue
        if (d > 0 and ahead == "white") or (d < 0 and ahead == "black"):
            parts.append(f"{abs(d)} {_human_piece_name(k, abs(d))}")
    if not parts:
        # Fallback
        return f"{side} has a material edge."
    who = "White" if ahead == "white" else "Black"
    return f"{who} is up " + ", ".join(parts) + "."


def _positional_summary(positional_cp: int) -> str:
    a = abs(int(positional_cp))
    if a < 40:
        return "The position itself is roughly equal."
    side = "White" if positional_cp > 0 else "Black"
    if a < 120:
        return f"{side} has a slightly better position."
    if a < 250:
        return f"{side} has the better position."
    return f"{side} has a clearly better position."


def _theme_to_phrase(theme: str) -> Optional[str]:
    t = (theme or "").lower().strip()
    mapping = {
        "king_safety": "king safety",
        "piece_activity": "piece activity",
        "pawn_structure": "pawn structure",
        "center_space": "space/center control",
        "center_control": "center control",
        "square_control": "square control",
        "initiative": "initiative",
        "coordination": "piece coordination",
    }
    return mapping.get(t, t.replace("_", " ") if t else None)


class FactsAssembler:
    """
    Normalize various engine result shapes into canonical FactsCard.
    """

    def from_light_result(
        self,
        *,
        fen: str,
        light_result: Dict[str, Any],
        light_raw: Optional[Dict[str, Any]] = None,
        depth: Optional[int] = None,
        multipv: Optional[int] = None,
    ) -> FactsCard:
        eval_cp = 0
        try:
            ev = light_result.get("eval_cp")
            if isinstance(ev, (int, float)):
                eval_cp = int(ev)
        except Exception:
            eval_cp = 0

        top_moves_in = light_result.get("top_moves")
        top_moves: List[CandidateMove] = []
        if isinstance(top_moves_in, list):
            rank = 1
            for tm in top_moves_in:
                if not isinstance(tm, dict):
                    continue
                san = tm.get("move_san") or tm.get("move") or tm.get("san")
                if not isinstance(san, str) or not san.strip():
                    continue
                top_moves.append(
                    CandidateMove(
                        rank=rank,
                        san=san.strip(),
                        uci=(tm.get("move_uci") if isinstance(tm.get("move_uci"), str) else None),
                        eval_cp=(int(tm.get("eval_cp")) if isinstance(tm.get("eval_cp"), (int, float)) else None),
                        pv_san=(tm.get("pv_san") if isinstance(tm.get("pv_san"), list) else []),
                    )
                )
                rank += 1

        # Material + positional breakdown from FEN + engine eval.
        material_balance_cp = 0
        material_summary = ""
        positional_cp = int(eval_cp)
        positional_summary = ""
        positional_factors: List[str] = []
        try:
            b = chess.Board(fen)
            material_balance_cp = int(calculate_material_balance(b))
            counts = get_material_count(b)
            material_summary = _material_summary_from_counts(counts)
            positional_cp = int(eval_cp) - int(material_balance_cp)
            positional_summary = _positional_summary(positional_cp)
        except Exception:
            material_balance_cp = 0
            positional_cp = int(eval_cp)

        # Themes/tags (optional): used as justification phrases, kept compact.
        try:
            if isinstance(light_raw, dict):
                top_themes = light_raw.get("top_themes")
                if isinstance(top_themes, list):
                    for th in top_themes[:3]:
                        if isinstance(th, str) and th.strip():
                            p = _theme_to_phrase(th.strip())
                            if p:
                                positional_factors.append(p)
        except Exception:
            pass

        return FactsCard(
            fen=fen,
            side_to_move=_side_to_move_from_fen(fen),
            eval_cp=eval_cp,
            material_balance_cp=material_balance_cp,
            material_summary=material_summary,
            positional_cp=positional_cp,
            positional_summary=positional_summary,
            positional_factors=positional_factors,
            top_moves=top_moves,
            pv=(light_result.get("pv_san") if isinstance(light_result.get("pv_san"), list) else []),
            tags=(light_result.get("tags") if isinstance(light_result.get("tags"), list) else []),
            roles=(light_result.get("roles") if isinstance(light_result.get("roles"), dict) else {}),
            deltas=(light_result.get("deltas") if isinstance(light_result.get("deltas"), dict) else {}),
            source="stockfish",
            depth=depth,
            multipv=multipv,
        )


