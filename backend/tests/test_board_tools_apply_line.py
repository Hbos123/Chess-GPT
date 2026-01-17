import unittest

import chess

from board_tools import apply_line


class TestBoardToolsApplyLine(unittest.TestCase):
    def test_apply_line_san_success(self):
        out = apply_line(start_fen=chess.STARTING_FEN, moves=["e4", "e5", "Nf3"], fmt="san", max_plies=10)
        self.assertTrue(out["success"])
        self.assertTrue(isinstance(out["end_fen"], str) and len(out["end_fen"]) > 10)
        self.assertEqual(len(out["applied"]), 3)

    def test_apply_line_illegal_move(self):
        out = apply_line(start_fen=chess.STARTING_FEN, moves=["e5"], fmt="san", max_plies=10)
        self.assertFalse(out["success"])
        self.assertIsNotNone(out["error"])
        self.assertEqual(out["error"]["at_index"], 0)


if __name__ == "__main__":
    unittest.main()





