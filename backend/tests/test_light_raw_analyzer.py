"""
Unit tests for Light Raw Analysis
Tests theme/tag computation and output verification
"""

import unittest
from light_raw_analyzer import compute_light_raw_analysis, LightRawAnalysis


class TestLightRawAnalyzer(unittest.TestCase):
    """Test cases for Light Raw Analysis"""
    
    def test_compute_light_raw_analysis(self):
        """Test light raw analysis computation"""
        # Starting position
        fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        
        result = compute_light_raw_analysis(fen)
        
        self.assertIsInstance(result, LightRawAnalysis)
        self.assertIsInstance(result.themes, dict)
        self.assertIsInstance(result.tags, list)
        self.assertIsInstance(result.material_balance_cp, int)
        self.assertIn(result.material_advantage, ["white", "black", "equal"])
        self.assertIsInstance(result.theme_scores, dict)
        self.assertIsInstance(result.top_themes, list)
    
    def test_themes_present(self):
        """Test that all 11 themes are present"""
        fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        
        result = compute_light_raw_analysis(fen)
        
        expected_themes = [
            "center_space", "pawn_structure", "king_safety",
            "piece_activity", "color_complex", "lanes",
            "local_imbalances", "development", "promotion",
            "breaks", "prophylaxis"
        ]
        
        for theme in expected_themes:
            self.assertIn(theme, result.themes, f"Missing theme: {theme}")
    
    def test_theme_scores_structure(self):
        """Test theme scores structure"""
        fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        
        result = compute_light_raw_analysis(fen)
        
        self.assertIn("white", result.theme_scores)
        self.assertIn("black", result.theme_scores)
        
        # Check that theme scores have totals
        self.assertIn("total", result.theme_scores["white"])
        self.assertIn("total", result.theme_scores["black"])
    
    def test_top_themes(self):
        """Test top themes extraction"""
        fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        
        result = compute_light_raw_analysis(fen)
        
        self.assertIsInstance(result.top_themes, list)
        self.assertLessEqual(len(result.top_themes), 5)  # Should be top 5 or fewer
    
    def test_material_balance(self):
        """Test material balance calculation"""
        # Starting position should be equal
        fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        
        result = compute_light_raw_analysis(fen)
        
        # Starting position should have equal material
        self.assertEqual(result.material_balance_cp, 0)
        self.assertEqual(result.material_advantage, "equal")
    
    def test_to_dict(self):
        """Test serialization to dict"""
        fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        
        result = compute_light_raw_analysis(fen)
        result_dict = result.to_dict()
        
        self.assertIsInstance(result_dict, dict)
        self.assertIn("themes", result_dict)
        self.assertIn("tags", result_dict)
        self.assertIn("material_balance_cp", result_dict)
        self.assertIn("material_advantage", result_dict)
        self.assertIn("theme_scores", result_dict)
        self.assertIn("top_themes", result_dict)
    
    def test_performance(self):
        """Test that analysis is fast (<150ms target)"""
        import time
        fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        
        start = time.time()
        result = compute_light_raw_analysis(fen)
        elapsed = (time.time() - start) * 1000  # Convert to ms
        
        # Should be fast (target <150ms, but allow some margin for CI)
        self.assertLess(elapsed, 500, f"Analysis took {elapsed}ms, should be <500ms")


if __name__ == "__main__":
    unittest.main()












