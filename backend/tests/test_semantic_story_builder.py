import os
import sys
import unittest

import chess

# Ensure backend/ is on sys.path when tests are run from repo root
HERE = os.path.dirname(__file__)
BACKEND_DIR = os.path.abspath(os.path.join(HERE, ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from investigator import InvestigationResult
from evidence_semantic_story import build_semantic_story


class TestSemanticStoryBuilder(unittest.TestCase):
    def test_problem_tag_lost_is_positive_and_clutter_tags_are_omitted_from_story(self):
        inv = InvestigationResult(
            evidence_starting_fen=chess.STARTING_FEN,
            evidence_pgn_line="Nf3 d5",
            evidence_main_line_moves=["Nf3", "d5"],
            evidence_per_move_deltas=[
                {
                    "move": "Nf3",
                    "tags_gained": ["tag.diagonal.open.e5-h2", "tag.key.d4", "tag.color.hole.dark.f1"],
                    "tags_lost": ["tag.piece.trapped", "tag.undeveloped.knight"],
                    "roles_gained": [],
                    "roles_lost": [],
                },
                {
                    "move": "d5",
                    "tags_gained": ["tag.castling.available.kingside"],
                    "tags_lost": ["tag.bishop.pair", "tag.castling.rights.kingside"],
                    "roles_gained": [],
                    "roles_lost": [],
                },
            ],
            evidence_eval_start=1.23,
            evidence_eval_end=0.56,
            evidence_eval_delta=-0.67,
            evidence_material_start=0.0,
            evidence_material_end=0.0,
            evidence_positional_start=1.23,
            evidence_positional_end=0.56,
            # Public net lists (already filtered by pipeline); raw keeps full
            evidence_tags_gained_net=["tag.castling.available.kingside"],
            evidence_tags_lost_net=["tag.piece.trapped", "tag.undeveloped.knight", "tag.bishop.pair", "tag.castling.rights.kingside"],
            evidence_tags_gained_net_raw=["tag.diagonal.open.e5-h2", "tag.key.d4", "tag.castling.available.kingside"],
            evidence_tags_lost_net_raw=["tag.piece.trapped", "tag.undeveloped.knight", "tag.bishop.pair", "tag.castling.rights.kingside"],
        )

        story = build_semantic_story(
            investigation_result=inv,
            evidence_eval={
                "eval_start": inv.evidence_eval_start,
                "eval_end": inv.evidence_eval_end,
                "eval_delta": inv.evidence_eval_delta,
                "material_start": inv.evidence_material_start,
                "material_end": inv.evidence_material_end,
                "positional_start": inv.evidence_positional_start,
                "positional_end": inv.evidence_positional_end,
                "pgn_line": inv.evidence_pgn_line,
            },
        )

        # Clutter tags should be omitted from semantic story events
        all_tag_event_names = []
        for mv in story.get("moves", []):
            for ev in mv.get("events", []):
                if ev.get("type") == "tag":
                    all_tag_event_names.append(ev.get("name"))
        self.assertNotIn("tag.diagonal.open.e5-h2", all_tag_event_names)
        self.assertNotIn("tag.key.d4", all_tag_event_names)
        self.assertNotIn("tag.color.hole.dark.f1", all_tag_event_names)

        # Losing a problem tag should be marked positive
        trapped_events = []
        for mv in story.get("moves", []):
            for ev in mv.get("events", []):
                if ev.get("type") == "tag" and ev.get("name") == "tag.piece.trapped":
                    trapped_events.append(ev)
        self.assertTrue(len(trapped_events) >= 1)
        self.assertEqual(trapped_events[0].get("change"), "lost")
        self.assertEqual(trapped_events[0].get("polarity"), "positive")

        # Castling availability should have specific phrasing
        castling_events = []
        for mv in story.get("moves", []):
            for ev in mv.get("events", []):
                if ev.get("type") == "tag" and ev.get("name") == "tag.castling.available.kingside":
                    castling_events.append(ev)
        self.assertTrue(len(castling_events) >= 1)
        self.assertIn("castling became legal", (castling_events[0].get("meaning") or "").lower())

    def test_to_dict_includes_semantic_story_and_raw_fields(self):
        inv = InvestigationResult(
            evidence_starting_fen=chess.STARTING_FEN,
            evidence_pgn_line="Nf3 d5",
            evidence_main_line_moves=["Nf3", "d5"],
            evidence_per_move_deltas=[
                {"move": "Nf3", "tags_gained": [], "tags_lost": ["tag.undeveloped.knight"], "roles_gained": [], "roles_lost": []}
            ],
            evidence_tags_gained_net=[],
            evidence_tags_lost_net=["tag.undeveloped.knight"],
            evidence_tags_gained_net_raw=[],
            evidence_tags_lost_net_raw=["tag.undeveloped.knight"],
            evidence_eval_start=0.0,
            evidence_eval_end=0.1,
            evidence_eval_delta=0.1,
        )
        payload = inv.to_dict(include_semantic_story=True)
        self.assertIn("semantic_story", payload)
        self.assertIsNotNone(payload["semantic_story"])
        self.assertIn("evidence_tags_gained_net_raw", payload)
        self.assertIn("evidence_tags_lost_net_raw", payload)


if __name__ == "__main__":
    unittest.main()


