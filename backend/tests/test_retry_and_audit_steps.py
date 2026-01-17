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


class TestRetryAndAuditSteps(unittest.TestCase):
    def _make_executor(self) -> Executor:
        # Fake engine pool with deterministic eval and "top2" style info
        class FakeEnginePool:
            async def analyze_single(self, fen: str, depth: int = 8, multipv: int = 1):
                b = chess.Board(fen)
                # eval: +50cp if side to move is white else -50cp, to make cp stable
                cp = 50 if b.turn == chess.WHITE else -50
                info = {"pv": [], "score": chess.engine.PovScore(chess.engine.Cp(cp), chess.WHITE)}
                return {"success": True, "engine_id": 0, "result": [info]}

        return Executor(engine_pool=FakeEnginePool())

    def test_retry_investigate_target_runs_and_returns_result(self):
        ex = self._make_executor()
        intent = IntentPlan(intent="discuss_position")
        fen = "4k3/8/8/8/4Q3/8/8/4K3 w - - 0 1"
        goal = {"op": "predicate", "predicate": {"type": "piece_on_square", "params": {"piece": "Q", "side": "white", "square": "e4"}}}

        plan = ExecutionPlan(
            plan_id="plan_retry",
            original_intent=intent,
            steps=[
                ExecutionStep(
                    step_number=1,
                    action_type="retry_investigate_target",
                    parameters={"fen": fen, "goal": goal, "policy": {"max_depth": 0, "top_k_witnesses": 2}, "retries": 2},
                    purpose="Retry target",
                )
            ],
        )

        import asyncio
        res = asyncio.run(ex.execute_plan(plan, context={"fen": fen}))
        step1 = res["results"][1]
        # retry step returns InvestigationResult
        self.assertTrue(hasattr(step1, "goal_search_results"))
        self.assertEqual((step1.goal_search_results or {}).get("goal_status"), "success")
        self.assertTrue(isinstance((step1.goal_search_results or {}).get("retry_attempts"), list))

    def test_audit_line_runs(self):
        ex = self._make_executor()
        intent = IntentPlan(intent="discuss_position")
        fen = "r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1"

        plan = ExecutionPlan(
            plan_id="plan_audit",
            original_intent=intent,
            steps=[
                ExecutionStep(step_number=1, action_type="audit_line", parameters={"fen": fen, "line_san": ["O-O"], "depth": 6, "side": "white"}, purpose="Audit"),
            ],
        )

        import asyncio
        res = asyncio.run(ex.execute_plan(plan, context={"fen": fen}))
        out = res["results"][1]
        self.assertEqual(out.get("side"), "white")
        self.assertIn("end_fen", out)
        self.assertIn("eval_cp_white", out)


if __name__ == "__main__":
    unittest.main()


