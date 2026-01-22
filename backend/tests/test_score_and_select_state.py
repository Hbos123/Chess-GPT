import os
import sys
import unittest

HERE = os.path.dirname(__file__)
BACKEND_DIR = os.path.abspath(os.path.join(HERE, ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from planner import ExecutionPlan, ExecutionStep
from orchestration_plan import IntentPlan
from executor import Executor
import chess
import chess.engine


class TestScoreAndSelectState(unittest.TestCase):
    def _make_executor(self) -> Executor:
        # Fake engine pool: returns eval based on material (white - black) so scoring is deterministic.
        class FakeEnginePool:
            async def analyze_single(self, fen: str, depth: int = 8, multipv: int = 1):
                b = chess.Board(fen)
                vals = {
                    chess.PAWN: 1,
                    chess.KNIGHT: 3,
                    chess.BISHOP: 3,
                    chess.ROOK: 5,
                    chess.QUEEN: 9,
                    chess.KING: 0,
                }
                white = 0
                black = 0
                for _, p in b.piece_map().items():
                    v = vals.get(p.piece_type, 0)
                    if p.color == chess.WHITE:
                        white += v
                    else:
                        black += v
                cp = int((white - black) * 100)
                info = {"pv": [], "score": chess.engine.PovScore(chess.engine.Cp(cp), chess.WHITE)}
                return {"success": True, "engine_id": 0, "result": [info]}

        return Executor(engine_pool=FakeEnginePool())

    def test_score_then_select_state(self):
        ex = self._make_executor()
        intent = IntentPlan(intent="discuss_position")

        # State A: white has a queen; State B: black has a queen (so score for white should prefer A).
        fen_a = "4k3/8/8/8/8/8/4Q3/4K3 w - - 0 1"
        fen_b = "4k3/4q3/8/8/8/8/8/4K3 w - - 0 1"

        plan = ExecutionPlan(
            plan_id="plan_score_select",
            original_intent=intent,
            steps=[
                ExecutionStep(step_number=1, action_type="save_state", parameters={"name": "A", "fen": fen_a}, purpose="Save A"),
                ExecutionStep(step_number=2, action_type="save_state", parameters={"name": "B", "fen": fen_b}, purpose="Save B"),
                ExecutionStep(step_number=3, action_type="score_state", parameters={"fen_ref": "state:A", "depth": 6, "side": "white"}, purpose="Score A"),
                ExecutionStep(step_number=4, action_type="score_state", parameters={"fen_ref": "state:B", "depth": 6, "side": "white"}, purpose="Score B"),
                ExecutionStep(
                    step_number=5,
                    action_type="select_state",
                    parameters={
                        "candidates": [
                            {"state": "A", "score_ref": "step:3.score_side_cp"},
                            {"state": "B", "score_ref": "step:4.score_side_cp"},
                        ],
                        "strategy": "max",
                        "save_as": "best",
                    },
                    purpose="Pick best",
                ),
                ExecutionStep(step_number=6, action_type="apply_line", parameters={"fen_ref": "state:best", "line_san": [], "max_plies": 0}, purpose="Use best"),
            ],
        )

        import asyncio
        res = asyncio.run(ex.execute_plan(plan, context={"fen": fen_a}))
        self.assertEqual(res["results"][5]["selected_state"], "A")
        self.assertTrue(res["results"][6]["end_fen"].startswith("4k3/"))


if __name__ == "__main__":
    unittest.main()








