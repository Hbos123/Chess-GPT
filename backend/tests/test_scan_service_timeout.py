import unittest

import chess

from investigator import Investigator
from scan_service import scan_d2_d16, ScanPolicy


class TestScanServiceTimeout(unittest.TestCase):
    def test_scan_timeout_returns_error(self):
        # Create a dummy investigator-like object that never returns.
        class DummyInv:
            async def investigate_with_dual_depth(self, *args, **kwargs):
                import asyncio
                await asyncio.sleep(10)

        import asyncio

        async def run():
            return await scan_d2_d16(
                investigator=DummyInv(),  # type: ignore
                start_fen=chess.STARTING_FEN,
                policy=ScanPolicy(timeout_s=0.01, include_pgn=False),
            )

        out = asyncio.run(run())
        self.assertTrue(isinstance(out, dict))
        self.assertIn("error", out)


if __name__ == "__main__":
    unittest.main()


