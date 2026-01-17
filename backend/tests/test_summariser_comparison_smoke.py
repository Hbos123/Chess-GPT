import os
import sys
import unittest

HERE = os.path.dirname(__file__)
BACKEND_DIR = os.path.abspath(os.path.join(HERE, ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from summariser import Summariser
from investigator import InvestigationResult


class _FakeChoice:
    def __init__(self, content: str):
        self.message = type("M", (), {"content": content})


class _FakeResp:
    def __init__(self, content: str):
        self.choices = [_FakeChoice(content)]


class _FakeChatCompletions:
    def create(self, *args, **kwargs):
        # If this is the worded-PGN call, return a minimal valid worded-PGN JSON.
        try:
            msgs = kwargs.get("messages") or []
            if isinstance(msgs, list) and msgs and isinstance(msgs[0], dict):
                sys_msg = msgs[0].get("content") if isinstance(msgs[0].get("content"), str) else ""
                if "You convert SAN PGN into a grounded English narration" in (sys_msg or ""):
                    return _FakeResp(
                        """{
                          "mainline": {"header_summary": "Main line: (mock)", "worded_pgn": "Main line narration.", "moves": []},
                          "alternate_lines": [],
                          "notes": []
                        }"""
                    )
        except Exception:
            pass

        # Otherwise, treat as the main Summariser decision call.
        return _FakeResp(
            """{
              "core_message": "Recommended line selected from investigated candidates.",
              "psychological_frame": "clear plan",
              "mechanism": "prioritizes a stable improvement while avoiding immediate concessions",
              "mechanism_key_evidence": {"key_tags_gained": [], "key_tags_lost": [], "key_roles_gained": [], "key_roles_lost": [], "key_material_change": null},
              "selected_tags": [],
              "selected_roles": [],
              "suppressed_tags": [],
              "suppressed_roles": [],
              "claims": [
                {"summary":"The move a3 is a stable candidate.","claim_type":"general","connector":null,"evidence_moves":["a3","a6"],"reason":"candidate A","key_evidence":{"key_tags_gained":[],"key_tags_lost":[],"key_roles_gained":[],"key_roles_lost":[],"key_material_change":null}}
              ],
              "emphasis": ["primary_narrative"],
              "takeaway": "Prefer improving moves that keep the position stable under best reply.",
              "verbosity": "brief",
              "pgn_sequences_to_extract": []
            }"""
        )


class _FakeOpenAI:
    def __init__(self):
        self.chat = type("Chat", (), {"completions": _FakeChatCompletions()})


class TestSummariserComparisonSmoke(unittest.TestCase):
    def test_comparison_mode_does_not_require_worded_pgn_assignment(self):
        s = Summariser(openai_client=_FakeOpenAI())

        inv1 = InvestigationResult(
            player_move="a3",
            pv_after_move=["a6"],
            evidence_pgn_line="a3 a6",
            evidence_main_line_moves=["a3", "a6"],
            evidence_tags_gained_net=[],
            evidence_tags_lost_net=[],
            evidence_roles_gained_net=[],
            evidence_roles_lost_net=[],
            evidence_eval_start=0.1,
            evidence_eval_end=0.2,
            evidence_eval_delta=0.1,
        )
        inv2 = InvestigationResult(
            player_move="h3",
            pv_after_move=["h6"],
            evidence_pgn_line="h3 h6",
            evidence_main_line_moves=["h3", "h6"],
            evidence_tags_gained_net=[],
            evidence_tags_lost_net=[],
            evidence_roles_gained_net=[],
            evidence_roles_lost_net=[],
            evidence_eval_start=0.1,
            evidence_eval_end=0.0,
            evidence_eval_delta=-0.1,
        )

        comparison_bundle = {
            "comparison_mode": True,
            "multiple_results": [
                {"request": {"focus": "a3"}, "result": inv1},
                {"request": {"focus": "h3"}, "result": inv2},
            ],
        }

        # Provide a minimal execution_plan stub with discussion_agenda so agenda-coverage fallback runs.
        exec_plan = type("EP", (), {"discussion_agenda": [{"topic": "topic", "questions_to_answer": ["Q1", "Q2", "Q3"]}]})()

        # Should not raise UnboundLocalError for worded_pgn/original_pgn_context.
        out = self._run_async(s.summarise(comparison_bundle, execution_plan=exec_plan, user_message="What should I do?"))
        self.assertIsNotNone(out)
        self.assertTrue(hasattr(out, "claims"))
        # With agenda-coverage fallback, should produce at least 2 claims in suggestion-style prompts.
        self.assertGreaterEqual(len(out.claims), 2)
        pgn_lines = []
        for c in out.claims[:2]:
            payload = getattr(c, "evidence_payload", None)
            pgn_lines.append(getattr(payload, "pgn_line", None) if payload else None)
        self.assertIn("a3 a6", pgn_lines)
        self.assertIn("h3 h6", pgn_lines)

    def _run_async(self, coro):
        import asyncio
        # Robust across test suites: other tests may have used asyncio.run(), which
        # closes and clears the default loop, leaving no current event loop.
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)


if __name__ == "__main__":
    unittest.main()


