from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

import chess


class VerificationError(Exception):
    pass


def _extract_san_like_tokens(text: str) -> List[str]:
    # Very conservative: only tokens with at least one digit (rank) or castling.
    toks = re.findall(r"\b(O-O-O|O-O|[KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]?)\b", text or "")
    return [t.strip() for t in toks if isinstance(t, str) and t.strip()]


class Verifier:
    """
    Deterministic grounding verifier.

    Checks:
    - recommended move must be present in facts candidates
    - move must be legal in provided FEN
    - explanation must not introduce SAN tokens not in candidates (best-effort heuristic)
    """

    def verify(
        self,
        *,
        fen: str,
        facts: Dict[str, Any],
        recommended_move: Optional[str],
        explanation: str,
    ) -> Tuple[bool, List[str]]:
        issues: List[str] = []

        candidates: List[str] = []
        allowed: set[str] = set()
        try:
            top_moves = facts.get("top_moves")
            if isinstance(top_moves, list):
                for tm in top_moves:
                    if isinstance(tm, dict):
                        ms = tm.get("move_san")
                    else:
                        ms = None
                    if isinstance(ms, str) and ms.strip():
                        s = ms.strip()
                        candidates.append(s)
                        allowed.add(s)
                    # Allow PV moves mentioned as a line continuation (still grounded in engine facts).
                    if isinstance(tm, dict):
                        pv = tm.get("pv_san")
                        if isinstance(pv, list):
                            for p in pv[:24]:
                                if isinstance(p, str) and p.strip():
                                    allowed.add(p.strip())
        except Exception:
            pass

        # 1) recommended must be grounded
        if recommended_move and candidates and recommended_move not in candidates:
            issues.append("recommended_move_not_in_candidates")

        # 2) legality check (if provided)
        if recommended_move:
            try:
                board = chess.Board(fen)
                mv = board.parse_san(recommended_move)
                if mv not in board.legal_moves:
                    issues.append("recommended_move_illegal_for_fen")
            except Exception:
                # parse_san can fail even for valid SAN if context mismatch; still treat as issue.
                issues.append("recommended_move_could_not_be_parsed")

        # 3) explanation introduces unknown SAN (heuristic)
        try:
            mentioned = _extract_san_like_tokens(explanation or "")
            if candidates:
                for tok in mentioned[:25]:
                    # allow common generic tokens that are not move suggestions
                    if tok in {"O-O", "O-O-O"} and (tok in candidates):
                        continue
                    if tok not in allowed:
                        # Only flag if it looks like a move (contains file+rank)
                        if re.search(r"[a-h][1-8]", tok):
                            issues.append("explanation_mentions_move_not_in_candidates")
                            break
        except Exception:
            pass

        return (len(issues) == 0), issues


