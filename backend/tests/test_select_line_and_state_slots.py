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


class TestSelectLineAndStateSlots(unittest.TestCase):
    def _make_executor(self) -> Executor:
        # Minimal fake engine pool (won't be used in this test)
        class FakeEnginePool:
            async def analyze_single(self, fen: str, depth: int = 1, multipv: int = 1):
                return {"success": True, "engine_id": 0, "result": [{"pv": [], "score": chess.engine.PovScore(chess.engine.Cp(0), chess.WHITE)}]}

        return Executor(engine_pool=FakeEnginePool())

    def test_select_line_then_apply_and_save_state(self):
        ex = self._make_executor()
        root_fen = "r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1"
        intent = IntentPlan(intent="discuss_position")

        # Step 1 simulates an investigate_target result by directly setting results via a prior step.
        # We'll model it as a dict payload with witness candidates.
        # Then select_line chooses shortest (both length 1, tie-break stable) and apply_line uses it.
        plan = ExecutionPlan(
            plan_id="plan_select",
            original_intent=intent,
            steps=[
                ExecutionStep(
                    step_number=1,
                    action_type="apply_line",
                    parameters={"fen": root_fen, "line_san": [], "max_plies": 0},
                    purpose="No-op to establish step numbering",
                ),
                ExecutionStep(
                    step_number=2,
                    action_type="select_line",
                    parameters={
                        "witnesses": [{"line_san": ["O-O-O"]}, {"line_san": ["O-O"]}],
                        "strategy": "by_index",
                        "index": 1
                    },
                    purpose="Pick second witness",
                ),
                ExecutionStep(
                    step_number=3,
                    action_type="apply_line",
                    parameters={"fen": root_fen, "line_ref": "step:2.selected_line_san", "max_plies": 2},
                    purpose="Apply selected line",
                ),
                ExecutionStep(
                    step_number=4,
                    action_type="save_state",
                    parameters={"name": "after_castle", "fen_ref": "step:3.end_fen"},
                    purpose="Save state slot",
                ),
                ExecutionStep(
                    step_number=5,
                    action_type="apply_line",
                    parameters={"fen_ref": "state:after_castle", "line_san": [], "max_plies": 0},
                    purpose="Resolve state: slot",
                ),
            ],
        )

        import asyncio
        res = asyncio.run(ex.execute_plan(plan, context={"fen": root_fen}))
        self.assertEqual(res["results"][2]["selected_line_san"], ["O-O"])
        self.assertIn("end_fen", res["results"][3])
        self.assertEqual(res["results"][4]["name"], "after_castle")
        self.assertIn("end_fen", res["results"][5])


if __name__ == "__main__":
    unittest.main()








