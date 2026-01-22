"""
Integration tests for dual-depth investigation flow and PGN generation
Tests the full investigate_with_dual_depth() flow
"""

import unittest
import chess
from investigator import Investigator, InvestigationResult
from engine_queue import StockfishQueue


class TestDualDepthInvestigation(unittest.TestCase):
    """Integration tests for dual-depth investigation"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test fixtures once for all tests"""
        try:
            cls.engine_queue = StockfishQueue(num_engines=1)
        except Exception as e:
            cls.engine_queue = None
            print(f"Warning: Could not initialize engine queue: {e}")
    
    def setUp(self):
        """Set up for each test"""
        if self.engine_queue is None:
            self.skipTest("Engine queue not available")
        self.investigator = Investigator(self.engine_queue)
    
    def test_investigate_with_dual_depth(self):
        """Test full dual-depth investigation"""
        # Starting position
        fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        
        import asyncio
        result = asyncio.run(
            self.investigator.investigate_with_dual_depth(fen, scope="general_position")
        )
        
        self.assertIsInstance(result, InvestigationResult)
        self.assertIsNotNone(result.eval_d16)
        self.assertIsNotNone(result.eval_d2)
        self.assertIsNotNone(result.best_move_d16)
        self.assertIsInstance(result.top_moves_d2, list)
        self.assertIsInstance(result.overestimated_moves, list)
        self.assertIsNotNone(result.two_move_tactics)
        self.assertIsNotNone(result.light_raw_analysis)
        self.assertIsInstance(result.exploration_tree, dict)
        self.assertIsInstance(result.pgn_exploration, str)
        self.assertIsInstance(result.themes_identified, list)
        self.assertIsInstance(result.commentary, dict)
    
    def test_exploration_tree_structure(self):
        """Test exploration tree structure"""
        fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        
        import asyncio
        result = asyncio.run(
            self.investigator.investigate_with_dual_depth(fen, scope="general_position")
        )
        
        tree = result.exploration_tree
        self.assertIn("position", tree)
        self.assertIn("eval_d16", tree)
        self.assertIn("best_move_d16", tree)
        self.assertIn("tactics", tree)
        self.assertIn("light_raw", tree)
        self.assertIn("branches", tree)
        self.assertIsInstance(tree["branches"], list)
    
    def test_pgn_generation(self):
        """Test PGN generation with annotations"""
        fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        
        import asyncio
        result = asyncio.run(
            self.investigator.investigate_with_dual_depth(fen, scope="general_position")
        )
        
        pgn = result.pgn_exploration
        self.assertIsInstance(pgn, str)
        self.assertGreater(len(pgn), 0)
        
        # PGN should contain FEN header
        self.assertIn("FEN", pgn)
    
    def test_commentary_generation(self):
        """Test commentary generation"""
        fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        
        import asyncio
        result = asyncio.run(
            self.investigator.investigate_with_dual_depth(fen, scope="general_position")
        )
        
        commentary = result.commentary
        self.assertIsInstance(commentary, dict)
        
        # Should have commentary for best move if available
        if result.best_move_d16:
            self.assertIn(result.best_move_d16, commentary)
    
    def test_investigate_position_with_scope(self):
        """Test investigate_position() routing to dual-depth when scope is general_position"""
        fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        
        import asyncio
        result = asyncio.run(
            self.investigator.investigate_position(fen, scope="general_position")
        )
        
        # Should have dual-depth fields populated
        self.assertIsNotNone(result.eval_d16)
        self.assertIsNotNone(result.eval_d2)
        self.assertIsNotNone(result.two_move_tactics)
        self.assertIsNotNone(result.light_raw_analysis)


if __name__ == "__main__":
    unittest.main()











