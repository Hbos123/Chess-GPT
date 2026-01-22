from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Optional

import chess


@dataclass
class FastRouteResult:
    handled: bool
    content: str = ""
    stop_reason: str = ""
    milestone_kind: Optional[str] = None
    data: Dict[str, Any] = None


class FastHeuristicsRouter:
    """
    Deterministic, zero-token fast path router.
    Intentionally conservative: only handles cases we can answer safely.
    """

    _RE_THEORY = re.compile(r"\b(what is|explain|define|how does|why do)\b", re.I)

    def detect_castling_question(self, msg: str) -> bool:
        """
        Only handle simple legality checks about current state.
        Generic detection: questions asking "can I do X?" or "is X legal?" about current position.
        Excludes questions asking "how to do X?" or "what move to do X?" which need full pipeline.
        """
        m = (msg or "").lower()
        has_castle_word = ("castle" in m) or ("castling" in m) or ("o-o" in m) or ("0-0" in m)
        if not has_castle_word:
            return False
        
        # Generic: Questions asking HOW/WHAT to do something need full pipeline (move suggestions)
        # Pattern: "how to", "what move", "what should", "how can I", "how do I"
        how_what_patterns = [
            r"\bhow\s+(to|can|do|should)",
            r"\bwhat\s+(move|should|can|do)",
            r"\bwhich\s+(move|way)",
        ]
        for pattern in how_what_patterns:
            if re.search(pattern, m):
                return False
        
        # Generic: Questions asking about future/planning need full pipeline
        # Pattern: future tense, planning words, goal-oriented language
        future_planning_patterns = [
            r"\b(want|need|should|plan|goal|eventually|later|next|after)",
        ]
        # Only exclude if combined with action verbs (not just "I want" alone)
        if re.search(r"\b(want|need|should)\s+\w+\s+(to\s+)?(castle|castling)", m):
            return False
        
        # Generic: Only handle simple present-state legality checks
        # Pattern: "can I", "is X legal", "can X", "is it legal"
        legality_patterns = [
            r"\bcan\s+(i|you|we|white|black)\s+(castle|castling)",
            r"\bis\s+(castling|castle|it)\s+(legal|possible|allowed)",
            r"\bcan\s+(white|black)\s+castle",
        ]
        return any(re.search(pattern, m) for pattern in legality_patterns)

    def castling_check(self, fen: str) -> Dict[str, Any]:
        b = chess.Board(fen)
        side = "white" if b.turn else "black"
        can_k = b.has_kingside_castling_rights(b.turn) and any(
            b.is_castling(m) and chess.square_file(m.to_square) == 6 for m in b.legal_moves
        )
        can_q = b.has_queenside_castling_rights(b.turn) and any(
            b.is_castling(m) and chess.square_file(m.to_square) == 2 for m in b.legal_moves
        )
        return {
            "side_to_move": side,
            "can_castle_now": bool(can_k or can_q),
            "kingside": bool(can_k),
            "queenside": bool(can_q),
        }

    def try_route(
        self,
        *,
        user_message: str,
        context: Dict[str, Any],
    ) -> FastRouteResult:
        fen = (context or {}).get("fen") or (context or {}).get("board_state") or chess.STARTING_FEN

        # Fast path 1: “can I castle?” legality check
        if fen and self.detect_castling_question(user_message):
            try:
                c = self.castling_check(fen)
                msg = (
                    f"{c['side_to_move'].capitalize()} to move. "
                    f"Castling now: {'yes' if c['can_castle_now'] else 'no'}. "
                    f"Kingside: {'yes' if c['kingside'] else 'no'}, queenside: {'yes' if c['queenside'] else 'no'}.\n"
                )
                return FastRouteResult(
                    handled=True,
                    content=msg,
                    stop_reason="deterministic_castling_check",
                    milestone_kind="castling_check",
                    data={"castling": c},
                )
            except Exception:
                pass

        # Fast path 2: pure theory (no board dependency required)
        # Only take this if the user is clearly asking a definition/explanation and not referencing “here/this position”.
        um = (user_message or "").strip()
        if self._RE_THEORY.search(um) and not any(x in um.lower() for x in ["here", "this position", "in this", "move", "best move"]):
            return FastRouteResult(
                handled=False,  # handled by controller via single LLM chat; keep this as a routing hint later
            )

        return FastRouteResult(handled=False)


