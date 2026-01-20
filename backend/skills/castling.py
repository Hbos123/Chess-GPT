from __future__ import annotations

from typing import Any, Dict

import chess


def check_castling(*, fen: str) -> Dict[str, Any]:
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






