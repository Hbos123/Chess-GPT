import os
import sys
import unittest

HERE = os.path.dirname(__file__)
BACKEND_DIR = os.path.abspath(os.path.join(HERE, ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from summariser import Summariser, Claim
from investigator import InvestigationResult


class TestSummariserEvidenceBinding(unittest.TestCase):
    def test_attach_rich_evidence_overrides_llm_moves_and_source(self):
        # Minimal InvestigationResult with canonical evidence line that starts with player move.
        inv = InvestigationResult(
            player_move="Nf3",
            pv_after_move=["e5"],
            evidence_pgn_line="Nf3 e5",
            evidence_main_line_moves=["Nf3", "e5"],
            evidence_tags_gained_net=["tag.development.knight"],
            evidence_tags_lost_net=[],
            evidence_roles_gained_net=["white_knight_f3:role.structural.pawn_break_support"],
            evidence_roles_lost_net=[],
            evidence_eval_start=0.1,
            evidence_eval_end=0.2,
            evidence_eval_delta=0.1,
        )

        claim = Claim(
            summary="Developing your knight doesn't work because ...",
            claim_type="development_issue",
            connector="because",
            evidence_moves=["Bxe2", "Qxe2"],
            evidence_source="llm_generated",
        )

        s = Summariser(openai_client=None)  # client not used by _attach_rich_evidence
        s._attach_rich_evidence(claim, inv, want_pgn_line=True, want_tags=True, want_two_move=False)

        self.assertEqual(claim.evidence_moves[0], "Nf3")
        self.assertNotEqual(claim.evidence_source, "llm_generated")
        self.assertIn(claim.evidence_source, ("pv", "pgn", "validated"))


if __name__ == "__main__":
    unittest.main()







