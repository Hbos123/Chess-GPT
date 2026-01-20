import os
import sys
import unittest

# Ensure backend/ is on sys.path when tests are run from repo root
HERE = os.path.dirname(__file__)
BACKEND_DIR = os.path.abspath(os.path.join(HERE, ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from planner import ExecutionPlan, ExecutionStep
from orchestration_plan import IntentPlan
from executor import Executor
import chess
import chess.engine


class TestApplyLineStep(unittest.TestCase):
    def _make_executor(self) -> Executor:
        # Provide a minimal fake engine pool so Investigator construction succeeds,
        # but our plan only uses apply_line (no engine calls).
        class FakeEnginePool:
            async def analyze_single(self, fen: str, depth: int = 1, multipv: int = 1):
                return {"success": True, "engine_id": 0, "result": [{"pv": [], "score": chess.engine.PovScore(chess.engine.Cp(0), chess.WHITE)}]}

        return Executor(engine_pool=FakeEnginePool())

    def test_apply_line_produces_end_fen(self):
        ex = self._make_executor()
        root_fen = chess.STARTING_FEN

        intent = IntentPlan(intent="discuss_position")
        plan = ExecutionPlan(
            plan_id="plan_test",
            original_intent=intent,
            steps=[
                ExecutionStep(
                    step_number=1,
                    action_type="apply_line",
                    parameters={"fen": root_fen, "line_san": ["e4", "e5"], "max_plies": 4},
                    purpose="Apply simple line",
                ),
                ExecutionStep(
                    step_number=2,
                    action_type="apply_line",
                    parameters={"fen_ref": "step:1.end_fen", "line_san": ["Nf3"], "max_plies": 4},
                    purpose="Chain from previous end_fen",
                ),
            ],
        )

        import asyncio
        result = asyncio.run(ex.execute_plan(plan, context={"fen": root_fen}))

        r1 = result["results"][1]
        r2 = result["results"][2]
        self.assertIn("end_fen", r1)
        self.assertIn("end_fen", r2)
        self.assertTrue(isinstance(r2.get("fens"), list))
        self.assertGreaterEqual(len(r2.get("fens")), 2)


if __name__ == "__main__":
    unittest.main()








