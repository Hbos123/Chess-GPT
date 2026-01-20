import os
import sys
import unittest
import chess
import chess.engine

# Ensure backend/ is on sys.path when tests are run from repo root
HERE = os.path.dirname(__file__)
BACKEND_DIR = os.path.abspath(os.path.join(HERE, ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from investigator import Investigator


class TestInvestigateMovePvEvidence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        class FakeEnginePool:
            async def analyze_single(self, fen: str, depth: int = 8, multipv: int = 1):
                b = chess.Board(fen)
                moves = list(b.legal_moves)
                pv = [moves[0]] if moves else []
                info = {"pv": pv, "score": chess.engine.PovScore(chess.engine.Cp(0), chess.WHITE)}
                return {"success": True, "engine_id": 0, "result": [info]}

        cls.engine_pool = FakeEnginePool()

    def setUp(self):
        self.inv = Investigator(engine_pool=self.engine_pool)

    def test_pv_after_move_is_from_post_move_position_and_evidence_includes_player_move(self):
        fen = chess.STARTING_FEN
        move_san = "Nf3"
        import asyncio
        res = asyncio.run(self.inv.investigate_move(fen=fen, move_san=move_san, follow_pv=True))

        # PV after move should be SAN from the position AFTER Nf3 (i.e., black to move),
        # so it must be non-empty with our fake engine.
        self.assertTrue(isinstance(res.pv_after_move, list))
        self.assertGreaterEqual(len(res.pv_after_move), 1)

        # Canonical evidence line should start with the player's move (fixes "omitted first move" bug).
        self.assertTrue(isinstance(res.evidence_pgn_line, str))
        self.assertTrue(res.evidence_pgn_line.startswith("Nf3"))
        self.assertTrue(isinstance(res.evidence_main_line_moves, list))
        self.assertGreaterEqual(len(res.evidence_main_line_moves), 1)
        self.assertEqual(res.evidence_main_line_moves[0], "Nf3")


if __name__ == "__main__":
    unittest.main()








