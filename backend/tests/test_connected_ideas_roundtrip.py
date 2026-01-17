import os
import sys
import unittest

HERE = os.path.dirname(__file__)
BACKEND_DIR = os.path.abspath(os.path.join(HERE, ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from orchestration_plan import IntentPlan


class TestConnectedIdeasRoundtrip(unittest.TestCase):
    def test_intent_plan_connected_ideas_roundtrip(self):
        payload = {
            "intent": "discuss_position",
            "scope": "current_position",
            "goal": "suggest moves",
            "constraints": {"depth": "standard", "tone": "coach", "verbosity": "medium"},
            "investigation_required": True,
            "investigation_requests": [
                {"investigation_type": "position", "focus": None, "parameters": {}, "purpose": "Progress toward goal"}
            ],
            "mode": "analyze",
            "mode_confidence": 0.9,
            "user_intent_summary": "Progress toward a goal with connected prerequisites",
            "connected_ideas": {
                "goals": [{"id": "G1", "type": "capability", "label": "goal_x"}],
                "entities": [{"id": "E1", "type": "concept", "label": "prereq_y"}],
                "relations": [{"type": "prerequisite", "from": "prereq_y", "to": "goal_x", "strength": "high", "notes": ""}],
                "questions_to_answer": ["What blocks goal_x?"],
            },
        }

        ip = IntentPlan.from_dict(payload)
        self.assertIsInstance(ip.connected_ideas, dict)
        out = ip.to_dict()
        self.assertIn("connected_ideas", out)
        self.assertEqual(out["connected_ideas"]["relations"][0]["type"], "prerequisite")


if __name__ == "__main__":
    unittest.main()







