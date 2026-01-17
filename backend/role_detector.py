"""
Deterministic Piece Role Detector

Purpose:
- Provide a fast, deterministic mapping of piece → roles for LightRawAnalysis.
- Must not call the engine or any LLMs.
- Used for role deltas (roles gained/lost) across lines in Investigator + Summariser.

Output format:
    {
      "white_knight_f3": ["role.control.outpost", "role.activity.high_mobility"],
      ...
    }

Downstream code will serialize as "piece_id:role.name".
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import chess


def detect_all_piece_roles(
    fen: str,
    *,
    previous_fen: Optional[str] = None,
    pgn_exploration: Optional[str] = None,
    investigation_result: Optional[Any] = None,
) -> Dict[str, List[str]]:
    """
    Compute deterministic piece roles for all pieces in the given FEN.

    Notes:
    - previous_fen/pgn_exploration/investigation_result are accepted for API compatibility
      (call sites pass them), but this function remains deterministic and board-only.
    """
    try:
        board = chess.Board(fen)
    except Exception:
        return {}

    roles: Dict[str, List[str]] = {}

    # Cache king squares for "defending king" heuristics
    wk = board.king(chess.WHITE)
    bk = board.king(chess.BLACK)
    king_sq = {chess.WHITE: wk, chess.BLACK: bk}

    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if not piece:
            continue
        color = piece.color
        side = "white" if color == chess.WHITE else "black"
        piece_name = chess.piece_name(piece.piece_type)  # "knight", ...
        square_name = chess.square_name(sq)
        piece_id = f"{side}_{piece_name}_{square_name}"

        rlist: List[str] = []

        # --- Status roles (tactical-ish, deterministic) ---
        # Hanging: attacked by opponent and not defended by own side.
        attacked_by_opp = board.is_attacked_by(not color, sq)
        defended_by_self = board.is_attacked_by(color, sq)
        if attacked_by_opp and not defended_by_self:
            rlist.append("role.status.hanging")

        # Trapped-ish: very low mobility and most destinations are unsafe.
        legal_dests = list(board.attacks(sq))
        if piece.piece_type in (chess.KNIGHT, chess.BISHOP, chess.ROOK) and legal_dests:
            safe_dests = [d for d in legal_dests if not board.is_attacked_by(not color, d)]
            if len(safe_dests) <= 1 and len(legal_dests) >= 2:
                rlist.append("role.status.trapped")

        # --- Positional roles ---
        # Knight on the rim (a/h-file) — positional disadvantage.
        if piece.piece_type == chess.KNIGHT:
            file_idx = chess.square_file(sq)
            if file_idx in (0, 7):
                rlist.append("role.position.edge")

        # Outpost (knight only): advanced square not attackable by enemy pawns.
        if piece.piece_type == chess.KNIGHT:
            rank_idx = chess.square_rank(sq)
            advanced = (rank_idx >= 3) if color == chess.WHITE else (rank_idx <= 4)
            if advanced and not _is_attacked_by_enemy_pawn(board, sq, color):
                rlist.append("role.control.outpost")

        # Mobility roles (general activity signal)
        mobility = len(legal_dests)
        if mobility >= 9:
            rlist.append("role.activity.high_mobility")
        elif mobility >= 6:
            rlist.append("role.activity.moderate_mobility")
        elif mobility <= 2:
            rlist.append("role.activity.low_mobility")

        # Defending king: piece attacks squares adjacent to own king.
        ksq = king_sq.get(color)
        if ksq is not None:
            king_neighbors = _king_neighbor_squares(ksq)
            if any(n in board.attacks(sq) for n in king_neighbors):
                rlist.append("role.defending.king")

        # De-duplicate, keep stable ordering
        if rlist:
            seen = set()
            deduped: List[str] = []
            for r in rlist:
                if r not in seen:
                    seen.add(r)
                    deduped.append(r)
            roles[piece_id] = deduped

    return roles


def _king_neighbor_squares(king_sq: int) -> List[int]:
    """All board-valid squares adjacent to king_sq (8-neighborhood)."""
    out: List[int] = []
    f0 = chess.square_file(king_sq)
    r0 = chess.square_rank(king_sq)
    for df in (-1, 0, 1):
        for dr in (-1, 0, 1):
            if df == 0 and dr == 0:
                continue
            f = f0 + df
            r = r0 + dr
            if 0 <= f <= 7 and 0 <= r <= 7:
                out.append(chess.square(f, r))
    return out


def _is_attacked_by_enemy_pawn(board: chess.Board, target_sq: int, color: chess.Color) -> bool:
    """
    True if target_sq is attackable by an enemy pawn in the current position.
    For an outpost check we only care about pawn attack geometry, not pinned legality.
    """
    tf = chess.square_file(target_sq)
    tr = chess.square_rank(target_sq)
    enemy = not color

    # Squares where an enemy pawn would sit to attack target_sq.
    # If enemy is BLACK, its pawns attack "down" (toward decreasing ranks),
    # so they would be on rank+1 relative to the target.
    # If enemy is WHITE, its pawns attack "up" (toward increasing ranks),
    # so they would be on rank-1 relative to the target.
    pawn_rank = tr + 1 if enemy == chess.BLACK else tr - 1
    if not (0 <= pawn_rank <= 7):
        return False

    for pawn_file in (tf - 1, tf + 1):
        if 0 <= pawn_file <= 7:
            sq = chess.square(pawn_file, pawn_rank)
            if board.piece_at(sq) == chess.Piece(chess.PAWN, enemy):
                return True
    return False

