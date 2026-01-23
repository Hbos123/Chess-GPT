import os
import unittest

from session_store import InMemorySessionStore


class TestSessionStoreSeedPrefix(unittest.TestCase):
    def test_seed_prefix_is_immutable_and_sets_initial_working_context(self):
        # Temporarily disable seed reset to test ValueError
        original_value = os.getenv("ALLOW_SEED_PREFIX_RESET")
        try:
            os.environ["ALLOW_SEED_PREFIX_RESET"] = "false"
            
            store = InMemorySessionStore(ttl_seconds=60)
            s = store.get_or_create("k1", "sys")
            self.assertEqual(s.working_context, "")

            store.seed_once("k1", "SEED_V1")
            s2 = store.get("k1")
            self.assertIsNotNone(s2)
            assert s2 is not None
            self.assertEqual(s2.seed_prefix, "SEED_V1")
            self.assertEqual(s2.working_context, "SEED_V1")

            # Second call with same seed is ok
            store.seed_once("k1", "SEED_V1")

            # Different seed should raise
            with self.assertRaises(ValueError):
                store.seed_once("k1", "SEED_V2")
        finally:
            # Restore original value
            if original_value is None:
                os.environ.pop("ALLOW_SEED_PREFIX_RESET", None)
            else:
                os.environ["ALLOW_SEED_PREFIX_RESET"] = original_value


if __name__ == "__main__":
    unittest.main()


