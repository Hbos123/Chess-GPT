"""
Integration tests for investigate_target goal DSL.
Skips if engine queue is not available.
"""

import os
import sys
import unittest
import chess

# Ensure backend/ is on sys.path when tests are run from repo root
HERE = os.path.dirname(__file__)
BACKEND_DIR = os.path.abspath(os.path.join(HERE, ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from investigator import Investigator


class TestInvestigateTarget(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        class FakeEnginePool:
            async def analyze_single(self, fen: str, depth: int = 1, multipv: int = 1):
                board = chess.Board(fen)
                moves = list(board.legal_moves)

                def score_move(m: chess.Move) -> int:
                    # Prefer castling and common opening move e4 to make tests deterministic.
                    if board.is_castling(m):
                        return 100
                    try:
                        p = board.piece_at(m.from_square)
                        if p and p.piece_type == chess.PAWN and chess.square_name(m.from_square) == "e2" and chess.square_name(m.to_square) == "e4":
                            return 90
                    except Exception:
                        pass
                    return 0

                moves.sort(key=score_move, reverse=True)

                # Return python-chess-like info dicts
                info_list = []
                for m in moves[:max(1, multipv)]:
                    info_list.append({
                        "pv": [m],
                        "score": chess.engine.PovScore(chess.engine.Cp(0), chess.WHITE)
                    })
                return {"success": True, "engine_id": 0, "result": info_list}

        cls.engine_pool = FakeEnginePool()

    def setUp(self):
        self.investigator = Investigator(engine_pool=self.engine_pool)

    def test_castle_immediate_success(self):
        # Kings+rooks only, both sides can castle
        fen = "r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1"
        goal = {
            "op": "predicate",
            "predicate": {"type": "castle", "params": {"side": "white", "mode": "already_castled"}},
        }
        policy = {
            "query_type": "existence",
            "max_depth": 1,
            "beam_width": 4,
            "branching_limit": 6,
            "opponent_model": "best",
            "engine_depth_propose": 1,
            "engine_depth_reply": 1,
            "top_k_witnesses": 2
        }

        import asyncio
        res = asyncio.run(self.investigator.investigate_target(fen=fen, goal=goal, policy=policy))
        self.assertEqual(res.goal_search_results.get("goal_status"), "success")
        witness = res.goal_search_results.get("witness_line_san") or []
        self.assertTrue(len(witness) >= 1)
        self.assertIn(witness[0], ["O-O", "O-O-O"])
        witnesses = res.goal_search_results.get("witnesses") or []
        self.assertGreaterEqual(len(witnesses), 1)
        # In this position, both castling sides should be discoverable with top_k_witnesses=2.
        if len(witnesses) >= 2:
            all_first_moves = [w.get("line_san", [None])[0] for w in witnesses if isinstance(w, dict)]
            self.assertTrue("O-O" in all_first_moves or "O-O-O" in all_first_moves)

    def test_play_move_success_in_one_ply(self):
        fen = chess.STARTING_FEN
        goal = {
            "op": "predicate",
            "predicate": {"type": "play_move", "params": {"move_san": "e4", "by": "side_to_move"}},
        }
        policy = {
            "query_type": "existence",
            "max_depth": 1,
            "beam_width": 6,
            "branching_limit": 8,
            "opponent_model": "best",
            "engine_depth_propose": 1,
            "engine_depth_reply": 1
        }

        import asyncio
        res = asyncio.run(self.investigator.investigate_target(fen=fen, goal=goal, policy=policy))
        self.assertEqual(res.goal_search_results.get("goal_status"), "success")
        witness = res.goal_search_results.get("witness_line_san") or []
        self.assertTrue("e4" in witness)

    def test_piece_on_square_root_success(self):
        fen = "4k3/8/8/8/4Q3/8/8/4K3 w - - 0 1"
        goal = {
            "op": "predicate",
            "predicate": {"type": "piece_on_square", "params": {"piece": "Q", "side": "white", "square": "e4"}},
        }
        policy = {"query_type": "existence", "max_depth": 0, "beam_width": 2, "branching_limit": 2, "opponent_model": "best"}

        import asyncio
        res = asyncio.run(self.investigator.investigate_target(fen=fen, goal=goal, policy=policy))
        self.assertEqual(res.goal_search_results.get("goal_status"), "success")
        self.assertEqual(res.goal_search_results.get("witness_line_san") or [], [])

    def test_goal_composition_and_not(self):
        fen = "4k3/8/8/8/4Q3/8/8/4K3 w - - 0 1"
        goal = {
            "op": "and",
            "args": [
                {"op": "predicate", "predicate": {"type": "piece_on_square", "params": {"piece": "Q", "side": "white", "square": "e4"}}},
                {"op": "not", "args": [{"op": "predicate", "predicate": {"type": "fen_contains", "params": {"pattern": " b "}}}]},
            ],
        }
        policy = {"query_type": "existence", "max_depth": 0, "beam_width": 2, "branching_limit": 2, "opponent_model": "best"}

        import asyncio
        res = asyncio.run(self.investigator.investigate_target(fen=fen, goal=goal, policy=policy))
        self.assertEqual(res.goal_search_results.get("goal_status"), "success")


if __name__ == "__main__":
    unittest.main()


