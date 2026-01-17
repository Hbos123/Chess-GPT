"""
Unit tests for Two-Move Win Engine
Tests each tactic type detection: forks, skewers, discovered attacks, captures, promotions, checkmates
"""

import unittest
import chess
from two_move_win_engine import TwoMoveWinEngine, TwoMoveWinResult


class TestTwoMoveWinEngine(unittest.TestCase):
    """Test cases for Two-Move Win Engine"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.engine = TwoMoveWinEngine()

    def _assert_san_legal(self, fen: str, side: chess.Color, san: str):
        """Assert SAN is parseable and legal for side to move in fen."""
        board = chess.Board(fen)
        board.turn = side
        move = board.parse_san(san)
        self.assertIn(move, board.legal_moves, f"SAN not legal: {san} for fen={fen}")

    def _assert_sequence_legal(self, fen: str, side: chess.Color, seq):
        """Apply SAN moves sequentially and ensure each is legal."""
        board = chess.Board(fen)
        board.turn = side
        for san in seq:
            move = board.parse_san(san)
            self.assertIn(move, board.legal_moves, f"Illegal SAN in sequence: {san} for fen={board.fen()}")
            board.push(move)
        return board
    
    def test_fork_detection(self):
        """Test fork detection"""
        # Position with knight fork opportunity
        fen = "rnbqkb1r/pppppppp/5n2/8/8/5N2/PPPPPPPP/RNBQKB1R w KQkq - 0 1"
        board = chess.Board(fen)
        
        # This is a simple starting position - test that engine doesn't crash
        # and returns a result
        import asyncio
        result = asyncio.run(self.engine.scan_two_move_tactics(fen, chess.WHITE))
        
        self.assertIsInstance(result, TwoMoveWinResult)
        self.assertIsInstance(result.open_tactics, list)
        self.assertIsInstance(result.blocked_tactics, list)
        # If any tactics are returned, their moves must be legal SAN in the original position
        for t in result.open_tactics:
            if t.get("move"):
                self._assert_san_legal(fen, chess.WHITE, t["move"])
    
    def test_capture_detection(self):
        """Test capture detection"""
        # Position with capture opportunity
        fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        
        import asyncio
        result = asyncio.run(self.engine.scan_two_move_tactics(fen, chess.WHITE))
        
        self.assertIsInstance(result, TwoMoveWinResult)
        self.assertIsInstance(result.open_captures, list)
        self.assertIsInstance(result.closed_captures, list)
        for c in result.open_captures:
            if c.get("move"):
                self._assert_san_legal(fen, chess.WHITE, c["move"])
    
    def test_promotion_detection(self):
        """Test promotion detection"""
        # Position with pawn on 7th rank
        fen = "rnbqkbnr/pppppppP/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        
        import asyncio
        result = asyncio.run(self.engine.scan_two_move_tactics(fen, chess.WHITE))
        
        self.assertIsInstance(result, TwoMoveWinResult)
        self.assertIsInstance(result.promotions, list)
    
    def test_checkmate_detection(self):
        """Test checkmate detection"""
        # Simple forced mate in 1 for White: Qg7#
        fen = "7k/5Q2/7K/8/8/8/8/8 w - - 0 1"
        
        import asyncio
        result = asyncio.run(self.engine.scan_two_move_tactics(fen, chess.WHITE))
        
        self.assertIsInstance(result, TwoMoveWinResult)
        self.assertIsInstance(result.checkmates, list)
        # Should find a mate in 1
        self.assertTrue(any(m.get("type") == "mate_in_1" for m in result.checkmates), "Expected mate_in_1 not found")
        # Any returned mate sequence should be legal and end in checkmate
        for m in result.checkmates:
            seq = m.get("sequence") or []
            if not seq:
                continue
            end_board = self._assert_sequence_legal(fen, chess.WHITE, seq)
            self.assertTrue(end_board.is_checkmate(), f"Mate sequence did not end in checkmate: {seq}")
    
    def test_summary_flags(self):
        """Test summary flags are set correctly"""
        fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        
        import asyncio
        result = asyncio.run(self.engine.scan_two_move_tactics(fen, chess.WHITE))
        
        self.assertIsInstance(result.has_winning_tactic, bool)
        self.assertIsInstance(result.has_losing_tactic, bool)
        self.assertIsInstance(result.has_immediate_threat, bool)
        self.assertIsInstance(result.has_promotion_threat, bool)
        self.assertIsInstance(result.has_mate_threat, bool)
    
    def test_to_dict(self):
        """Test serialization to dict"""
        fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        
        import asyncio
        result = asyncio.run(self.engine.scan_two_move_tactics(fen, chess.WHITE))
        result_dict = result.to_dict()
        
        self.assertIsInstance(result_dict, dict)
        self.assertIn("open_tactics", result_dict)
        self.assertIn("blocked_tactics", result_dict)
        self.assertIn("open_captures", result_dict)
        self.assertIn("closed_captures", result_dict)
        self.assertIn("promotions", result_dict)
        self.assertIn("checkmates", result_dict)
        self.assertIn("mate_patterns", result_dict)
        self.assertIn("has_winning_tactic", result_dict)
        self.assertIn("has_losing_tactic", result_dict)

    def test_side_to_move_mismatch_does_not_crash(self):
        """Engine should be robust if fen turn differs from requested side_to_move."""
        fen = "7k/5Q2/7K/8/8/8/8/8 w - - 0 1"
        import asyncio
        result = asyncio.run(self.engine.scan_two_move_tactics(fen, chess.BLACK))
        self.assertIsInstance(result, TwoMoveWinResult)

    def test_fork_flag_refuted_by_simple_recapture(self):
        """
        Regression: don't treat a "fork" as winning if the forking piece can be simply recaptured for net loss.
        Example: Nxe5+ (forking king+queen) is met by ...fxe5 (knight for pawn).
        """
        fen = "8/3k1q2/5p2/4p3/8/5N2/8/4K3 w - - 0 1"
        import asyncio
        result = asyncio.run(self.engine.scan_two_move_tactics(fen, chess.WHITE))
        forks = [t for t in result.open_tactics if t.get("type") == "fork"]
        self.assertTrue(len(forks) > 0, "Expected at least one fork candidate")
        # At least one fork candidate should be marked as refuted by SEE
        self.assertTrue(
            any((t.get("verification") or {}).get("refuted") is True for t in forks),
            "Expected a fork candidate to be refuted by simple recapture (SEE)"
        )

    def test_best_defense_prefers_counter_threat_over_recapture(self):
        """
        Regression for zwischenzug-style selection:
        If the defender can win the attacker's queen immediately, it should be preferred over
        merely capturing the 'attacking piece' square.
        """
        engine = TwoMoveWinEngine()
        # Crafted so "recapture the attacker piece" is a blunder (queen gets taken),
        # while the zwischenzug/counter-threat wins the queen.
        # If Black plays Qxe3?? then Bxe3 wins the queen.
        # So best is Qxd1+ (wins queen with check).
        fen = "4k3/8/8/8/8/4N3/3q1B2/3Q3K b - - 0 1"
        board = chess.Board(fen)
        # Pretend the attacker just moved a piece to e3 (the knight is on e3).
        attacking_move = chess.Move.from_uci("f1e3")  # only the destination matters for defense scoring
        best = engine._find_best_defense(board, chess.BLACK, attacking_move)
        self.assertIsNotNone(best)
        best_san = board.san(best)
        # Best defense should win the queen: Qxd1+
        self.assertEqual(best_san, "Qxd1+", f"Expected Qxd1+ but got {best_san}")

    def test_discovered_attack_targets_are_enemy_pieces_not_destination_square(self):
        """
        Regression: discovered_attack must report real enemy piece targets (e.g., queen on e7),
        not the moved-to square (previous bug produced targets like ["a3"]).
        """
        engine = TwoMoveWinEngine()
        fen = "6k1/4q3/8/8/8/8/4B3/4R1K1 w - - 0 1"
        board = chess.Board(fen)
        move = board.parse_san("Bf3")  # vacates e2, revealing rook attack on e7
        info = engine._check_discovered_attack(board, move)
        self.assertIsNotNone(info, "Expected discovered attack to be detected")
        self.assertEqual(info.get("type"), "discovered_attack")
        targets = info.get("targets") or []
        self.assertIn("e7", targets, f"Expected e7 as target, got {targets}")
        # Ensure none of the targets is the move destination square (f3)
        self.assertNotIn("f3", targets, f"Discovered attack targets should not include moved-to square: {targets}")


if __name__ == "__main__":
    unittest.main()


