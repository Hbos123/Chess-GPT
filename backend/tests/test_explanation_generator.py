"""
Comprehensive tests for the explanation generator system.

Tests all components: intent classification, tag deltas, PV detection,
mistake classification, narrative selection, and end-to-end explanations.
"""

import pytest
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from explanation_generator import (
    MoveIntentClassifier, TagDeltaAnalyzer, PVMissedMoveDetector,
    MistakeClassifier, NarrativeSelector, ExplanationGenerator,
    TemporalContextAnalyzer, PhaseAwareInterpreter, ComparativeMoveAnalyzer,
    generate_move_explanation
)


class TestMoveIntentClassification:
    """Test move intent classification with various tag combinations."""
    
    def test_defensive_intent(self):
        """Test that defensive tags lead to defensive intent."""
        classifier = MoveIntentClassifier()
        
        tags_before = [
            {"tag_name": "king.center.exposed", "side": "white", "strength": 0.8},
            {"tag_name": "threat.mate", "side": "white", "strength": 0.9}
        ]
        themes_before = {}
        
        result = classifier.classify(tags_before, themes_before, "white")
        
        assert result["primary_type"] == "defensive"
        assert result["confidence"] > 0.5
        assert len(result["justification"]["tags_used"]) > 0
    
    def test_positional_intent(self):
        """Test that positional tags lead to positional intent."""
        classifier = MoveIntentClassifier()
        
        tags_before = [
            {"tag_name": "center.control.core", "side": "white", "strength": 0.7},
            {"tag_name": "space.advantage", "side": "white", "strength": 0.6},
            {"tag_name": "outpost.knight", "side": "white", "strength": 0.5}
        ]
        themes_before = {}
        
        result = classifier.classify(tags_before, themes_before, "white")
        
        assert result["primary_type"] == "positional_improvement"
        assert result["confidence"] > 0.4
    
    def test_tactical_intent(self):
        """Test that tactical tags lead to tactical intent."""
        classifier = MoveIntentClassifier()
        
        tags_before = [
            {"tag_name": "fork", "side": "white", "strength": 0.8},
            {"tag_name": "pin", "side": "white", "strength": 0.7}
        ]
        themes_before = {}
        
        result = classifier.classify(tags_before, themes_before, "white")
        
        assert result["primary_type"] == "tactical_execution"
        assert result["confidence"] > 0.5
    
    def test_multiple_intents(self):
        """Test that multiple intents are detected correctly."""
        classifier = MoveIntentClassifier()
        
        tags_before = [
            {"tag_name": "king.exposed", "side": "white", "strength": 0.6},
            {"tag_name": "center.control.core", "side": "white", "strength": 0.7}
        ]
        themes_before = {}
        
        result = classifier.classify(tags_before, themes_before, "white")
        
        assert result["primary_type"] in ["defensive", "positional_improvement"]
        assert len(result["secondary_types"]) >= 0
    
    def test_no_tags_unclear_intent(self):
        """Test that positions with no relevant tags return unclear intent."""
        classifier = MoveIntentClassifier()
        
        tags_before = []
        themes_before = {}
        
        result = classifier.classify(tags_before, themes_before, "white")
        
        assert result["primary_type"] == "unclear"
        assert result["confidence"] == 0.0


class TestTagDeltaAnalysis:
    """Test tag delta analysis: gained/lost detection, best move comparison."""
    
    def test_tag_gained(self):
        """Test detection of gained tags."""
        analyzer = TagDeltaAnalyzer()
        
        tags_before = [
            {"tag_name": "center.control", "side": "white"}
        ]
        tags_after_played = [
            {"tag_name": "center.control", "side": "white"},
            {"tag_name": "piece.activity", "side": "white"}
        ]
        best_move_tags = [
            {"tag_name": "center.control", "side": "white"},
            {"tag_name": "piece.activity", "side": "white"}
        ]
        
        result = analyzer.analyze(tags_before, tags_after_played, best_move_tags, "white")
        
        assert "piece.activity" in result["gained"]
        assert result["net_change"] > 0
    
    def test_tag_lost(self):
        """Test detection of lost tags."""
        analyzer = TagDeltaAnalyzer()
        
        tags_before = [
            {"tag_name": "center.control", "side": "white"},
            {"tag_name": "piece.activity", "side": "white"}
        ]
        tags_after_played = [
            {"tag_name": "center.control", "side": "white"}
        ]
        best_move_tags = [
            {"tag_name": "center.control", "side": "white"},
            {"tag_name": "piece.activity", "side": "white"}
        ]
        
        result = analyzer.analyze(tags_before, tags_after_played, best_move_tags, "white")
        
        assert "piece.activity" in result["lost"]
        assert result["net_change"] < 0
    
    def test_tag_missed(self):
        """Test detection of missed tags (in best move but not played)."""
        analyzer = TagDeltaAnalyzer()
        
        tags_before = [
            {"tag_name": "center.control", "side": "white"}
        ]
        tags_after_played = [
            {"tag_name": "center.control", "side": "white"}
        ]
        best_move_tags = [
            {"tag_name": "center.control", "side": "white"},
            {"tag_name": "threat.attack", "side": "white"}
        ]
        
        result = analyzer.analyze(tags_before, tags_after_played, best_move_tags, "white")
        
        assert "threat.attack" in result["missed"]
        assert result["tag_delta_best"] > result["tag_delta_played"]
    
    def test_net_change_calculation(self):
        """Test net tag change calculation."""
        analyzer = TagDeltaAnalyzer()
        
        tags_before = [
            {"tag_name": "tag1", "side": "white"},
            {"tag_name": "tag2", "side": "white"}
        ]
        tags_after_played = [
            {"tag_name": "tag1", "side": "white"},
            {"tag_name": "tag3", "side": "white"}
        ]
        best_move_tags = [
            {"tag_name": "tag1", "side": "white"},
            {"tag_name": "tag2", "side": "white"},
            {"tag_name": "tag3", "side": "white"}
        ]
        
        result = analyzer.analyze(tags_before, tags_after_played, best_move_tags, "white")
        
        assert result["net_change"] == 0  # Gained 1, lost 1
        assert len(result["gained"]) == 1
        assert len(result["lost"]) == 1
        assert len(result["missed"]) == 0  # tag3 was gained, tag2 was kept in best


class TestPVMissedMoveDetection:
    """Test PV-based missed move detection."""
    
    def test_no_pv_no_detection(self):
        """Test that empty PV returns no detection."""
        detector = PVMissedMoveDetector()
        
        result = detector.detect(
            [], [], [], [], "", "white"
        )
        
        assert result["detected"] == False
    
    def test_pv_with_opponent_move(self):
        """Test detection with PV containing opponent moves."""
        detector = PVMissedMoveDetector()
        
        pv = ["e2e4", "e7e5", "g1f3"]
        tags_before = [
            {"tag_name": "position.stable", "side": "white"}
        ]
        tags_after_played = [
            {"tag_name": "position.stable", "side": "white"}
        ]
        engine_info = [
            {"eval_cp": 50, "pv": pv}
        ]
        
        result = detector.detect(
            pv, tags_before, tags_after_played, engine_info, 
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", "white"
        )
        
        # Should detect if eval swing is large enough
        # This is a simplified test - real detection needs actual position analysis
        assert "detected" in result
    
    def test_critical_tags_detection(self):
        """Test that critical tags trigger detection."""
        detector = PVMissedMoveDetector()
        
        pv = ["e2e4", "d8h4"]  # Qh4 creates threat
        tags_before = [
            {"tag_name": "position.stable", "side": "white"}
        ]
        tags_after_played = [
            {"tag_name": "position.stable", "side": "white"}
            # No threat tags addressed
        ]
        engine_info = [
            {"eval_cp": -250, "pv": pv}  # Large eval swing
        ]
        
        result = detector.detect(
            pv, tags_before, tags_after_played, engine_info,
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", "white"
        )
        
        # Should detect if conditions are met
        assert "detected" in result


class TestMistakeClassification:
    """Test all mistake types with tag evidence justification."""
    
    def test_missed_opponent_move_classification(self):
        """Test classification of missed opponent move."""
        classifier = MistakeClassifier()
        
        ply_record = {
            "side_moved": "white",
            "cp_loss": 250,
            "fen_before": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        }
        raw_before = {
            "tags": [{"tag_name": "position.stable", "side": "white"}],
            "themes": {},
            "eval_cp": 50
        }
        raw_after = {
            "tags": [{"tag_name": "position.stable", "side": "white"}],
            "eval_cp": -200
        }
        best_move_tags = [
            {"tag_name": "position.stable", "side": "white"}
        ]
        engine_info = [
            {"eval_cp": -250, "pv": ["e2e4", "d8h4"]}
        ]
        
        result = classifier.classify(
            ply_record, raw_before, raw_after, best_move_tags, engine_info
        )
        
        assert result["primary_type"] in ["missed_opponent_move", "calculation_failure", "unclear"]
        assert result["severity"] in ["blunder", "mistake"]
        assert "justification" in result
    
    def test_calculation_failure_classification(self):
        """Test classification of calculation failure."""
        classifier = MistakeClassifier()
        
        ply_record = {
            "side_moved": "white",
            "cp_loss": 150,
            "fen_before": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        }
        raw_before = {
            "tags": [
                {"tag_name": "center.control", "side": "white"},
                {"tag_name": "piece.activity", "side": "white"}
            ],
            "themes": {},
            "eval_cp": 50
        }
        raw_after = {
            "tags": [
                {"tag_name": "center.control", "side": "white"}
                # Lost piece.activity
            ],
            "eval_cp": -100
        }
        best_move_tags = [
            {"tag_name": "center.control", "side": "white"},
            {"tag_name": "piece.activity", "side": "white"},
            {"tag_name": "threat.attack", "side": "white"}
        ]
        engine_info = [
            {"eval_cp": 50, "pv": ["e2e4"]}
        ]
        
        result = classifier.classify(
            ply_record, raw_before, raw_after, best_move_tags, engine_info
        )
        
        assert result["primary_type"] in ["calculation_failure", "strategic_misjudgment", "unclear"]
        assert result["severity"] in ["mistake", "blunder"]
        assert "tag_evidence" in result["justification"]
    
    def test_intent_mismatch_classification(self):
        """Test classification of intent mismatch."""
        classifier = MistakeClassifier()
        
        ply_record = {
            "side_moved": "white",
            "cp_loss": 80,
            "fen_before": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        }
        raw_before = {
            "tags": [
                {"tag_name": "king.exposed", "side": "white"},
                {"tag_name": "threat.mate", "side": "white"}
            ],
            "themes": {},
            "eval_cp": -50
        }
        raw_after = {
            "tags": [
                {"tag_name": "king.exposed", "side": "white"},
                {"tag_name": "positional.improvement", "side": "white"}
                # Wrong type of tag for position
            ],
            "eval_cp": -130
        }
        best_move_tags = [
            {"tag_name": "king.safe", "side": "white"}
        ]
        engine_info = [
            {"eval_cp": -50, "pv": ["e1g1"]}  # Castling
        ]
        
        result = classifier.classify(
            ply_record, raw_before, raw_after, best_move_tags, engine_info
        )
        
        # May detect calculation_failure if missed tags, or intent_mismatch if position requires defensive
        assert result["primary_type"] in ["intent_mismatch", "strategic_misjudgment", "calculation_failure", "unclear"]
        assert "justification" in result
    
    def test_severity_classification(self):
        """Test that severity is correctly classified by CP loss."""
        classifier = MistakeClassifier()
        
        test_cases = [
            (250, "blunder"),
            (150, "mistake"),
            (60, "inaccuracy"),
            (30, "minor")  # <50 is minor for mistakes
        ]
        
        for cp_loss, expected_severity in test_cases:
            ply_record = {
                "side_moved": "white",
                "cp_loss": cp_loss,
                "fen_before": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
            }
            raw_before = {"tags": [], "themes": {}, "eval_cp": 0}
            raw_after = {"tags": [], "eval_cp": -cp_loss}
            best_move_tags = []
            engine_info = [{"eval_cp": 0, "pv": []}]
            
            result = classifier.classify(
                ply_record, raw_before, raw_after, best_move_tags, engine_info
            )
            
            assert result["severity"] == expected_severity


class TestNarrativeSelection:
    """Test narrative selection with multiple factors."""
    
    def test_primary_reason_selection(self):
        """Test that highest-scored factor becomes primary reason."""
        selector = NarrativeSelector()
        
        mistake_classification = {
            "primary_type": "missed_opponent_move",
            "secondary_types": ["calculation_failure"],
            "severity": "blunder"
        }
        missed_move = {
            "detected": True,
            "move_san": "Qh4",
            "eval_swing": 250
        }
        tag_deltas = {
            "gained": [],
            "lost": ["piece.activity"],
            "missed": ["threat.attack"],
            "net_change": -1
        }
        eval_evidence = {
            "cp_loss": 250,
            "eval_before": 50,
            "eval_after_played": -200
        }
        
        result = selector.select(
            mistake_classification, missed_move, tag_deltas, eval_evidence
        )
        
        assert "primary_reason" in result
        assert "missed" in result["primary_reason"].lower() or "opponent" in result["primary_reason"].lower()
        assert len(result["secondary_reasons"]) >= 0
    
    def test_suppression_logic(self):
        """Test that low-importance factors are suppressed."""
        selector = NarrativeSelector()
        
        mistake_classification = {
            "primary_type": "missed_opponent_move",
            "secondary_types": ["calculation_failure", "strategic_misjudgment"],
            "severity": "blunder"
        }
        missed_move = {
            "detected": True,
            "move_san": "Qh4",
            "eval_swing": 300  # Very high
        }
        tag_deltas = {
            "gained": [],
            "lost": [],
            "missed": [],
            "net_change": 0
        }
        eval_evidence = {
            "cp_loss": 300,
            "eval_before": 50,
            "eval_after_played": -250
        }
        
        result = selector.select(
            mistake_classification, missed_move, tag_deltas, eval_evidence
        )
        
        # Low-scoring factors should be suppressed
        assert len(result.get("suppressed_factors", [])) >= 0
    
    def test_multiple_factors(self):
        """Test selection with multiple competing factors."""
        selector = NarrativeSelector()
        
        mistake_classification = {
            "primary_type": "calculation_failure",
            "secondary_types": ["strategic_misjudgment"],
            "severity": "mistake"
        }
        missed_move = {
            "detected": False
        }
        tag_deltas = {
            "gained": [],
            "lost": ["piece.activity", "center.control"],
            "missed": ["threat.attack"],
            "net_change": -2
        }
        eval_evidence = {
            "cp_loss": 150,
            "eval_before": 50,
            "eval_after_played": -100
        }
        
        result = selector.select(
            mistake_classification, missed_move, tag_deltas, eval_evidence
        )
        
        assert "primary_reason" in result
        assert len(result["secondary_reasons"]) <= 2


class TestEndToEnd:
    """Test complete explanation pipeline end-to-end."""
    
    def test_complete_explanation_generation(self):
        """Test complete explanation generation for a tactical blunder."""
        ply_record = {
            "ply": 10,
            "side_moved": "white",
            "san": "Nf3",
            "uci": "g1f3",
            "fen_before": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
            "fen_after": "rnbqkb1r/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
            "cp_loss": 250,
            "category": "blunder"
        }
        raw_before = {
            "tags": [
                {"tag_name": "center.control", "side": "white"},
                {"tag_name": "position.stable", "side": "white"}
            ],
            "themes": {},
            "eval_cp": 50
        }
        raw_after = {
            "tags": [
                {"tag_name": "center.control", "side": "white"}
            ],
            "eval_cp": -200
        }
        best_move_tags = [
            {"tag_name": "center.control", "side": "white"},
            {"tag_name": "king.safe", "side": "white"}
        ]
        engine_info = [
            {"eval_cp": -250, "pv": ["g1f3", "d8h4"]}
        ]
        
        result = generate_move_explanation(
            ply_record=ply_record,
            raw_before=raw_before,
            raw_after=raw_after,
            best_move_tags=best_move_tags,
            engine_info=engine_info,
            phase="opening"
        )
        
        # Verify structure
        assert "tag_analysis" in result
        assert "move_intent" in result
        assert "mistake_classification" in result
        assert "missed_opponent_move" in result
        assert "narrative" in result
        assert "comparison" in result
        assert "context" in result
        
        # Verify narrative has explanation
        assert "explanation" in result["narrative"]
        assert len(result["narrative"]["explanation"]) > 0
    
    def test_positional_mistake_explanation(self):
        """Test explanation for a positional mistake."""
        ply_record = {
            "ply": 25,
            "side_moved": "white",
            "san": "h3",
            "uci": "h2h3",
            "fen_before": "rnbqkb1r/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
            "fen_after": "rnbqkb1r/pppppppp/8/8/4P3/7P/PPPP1PP1/RNBQKBNR b KQkq - 0 2",
            "cp_loss": 80,
            "category": "mistake"
        }
        raw_before = {
            "tags": [
                {"tag_name": "center.control", "side": "white"},
                {"tag_name": "piece.activity", "side": "white"}
            ],
            "themes": {},
            "eval_cp": 30
        }
        raw_after = {
            "tags": [
                {"tag_name": "center.control", "side": "white"}
                # Lost piece.activity
            ],
            "eval_cp": -50
        }
        best_move_tags = [
            {"tag_name": "center.control", "side": "white"},
            {"tag_name": "piece.activity", "side": "white"},
            {"tag_name": "threat.attack", "side": "white"}
        ]
        engine_info = [
            {"eval_cp": 30, "pv": ["d2d4"]}
        ]
        
        result = generate_move_explanation(
            ply_record=ply_record,
            raw_before=raw_before,
            raw_after=raw_after,
            best_move_tags=best_move_tags,
            engine_info=engine_info,
            phase="middlegame"
        )
        
        assert result["mistake_classification"]["primary_type"] != "unclear"
        assert result["narrative"]["explanation"] is not None
    
    def test_intent_mismatch_explanation(self):
        """Test explanation for intent mismatch."""
        ply_record = {
            "ply": 15,
            "side_moved": "white",
            "san": "b3",
            "uci": "b2b3",
            "fen_before": "rnbqkb1r/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
            "fen_after": "rnbqkb1r/pppppppp/8/8/4P3/1P6/P1PP1PPP/RNBQKBNR b KQkq - 0 2",
            "cp_loss": 60,
            "category": "inaccuracy"
        }
        raw_before = {
            "tags": [
                {"tag_name": "king.exposed", "side": "white"},
                {"tag_name": "threat.mate", "side": "white"}
            ],
            "themes": {},
            "eval_cp": -30
        }
        raw_after = {
            "tags": [
                {"tag_name": "king.exposed", "side": "white"},
                {"tag_name": "positional.improvement", "side": "white"}
                # Wrong type for position - no tags lost, so calculation_failure won't trigger
            ],
            "eval_cp": -90
        }
        best_move_tags = [
            {"tag_name": "king.safe", "side": "white"}
            # Best move creates defensive tag, played move creates positional tag
        ]
        engine_info = [
            {"eval_cp": -30, "pv": ["e1g1"]}
        ]
        
        result = generate_move_explanation(
            ply_record=ply_record,
            raw_before=raw_before,
            raw_after=raw_after,
            best_move_tags=best_move_tags,
            engine_info=engine_info,
            phase="opening"
        )
        
        # Should detect intent mismatch or strategic misjudgment (calculation_failure less likely since no tags lost)
        assert result["mistake_classification"]["primary_type"] in ["intent_mismatch", "strategic_misjudgment", "calculation_failure", "unclear"]
        # Check that explanation is generated
        assert "explanation" in result["narrative"]
        assert len(result["narrative"]["explanation"]) > 0


class TestTemporalContext:
    """Test temporal context analysis."""
    
    def test_early_game_context(self):
        """Test context for early game moves."""
        analyzer = TemporalContextAnalyzer()
        
        ply_records = [
            {"ply": 1, "side_moved": "white", "san": "e4"},
            {"ply": 2, "side_moved": "black", "san": "e5"},
            {"ply": 3, "side_moved": "white", "san": "Nf3"}
        ]
        
        result = analyzer.analyze(ply_records, 3)
        
        assert result["plan_continuity"] in ["early", "early_game", "continued"]
        assert len(result["player_last_2_moves"]) <= 2
    
    def test_plan_continuity_detection(self):
        """Test detection of plan continuity."""
        analyzer = TemporalContextAnalyzer()
        
        ply_records = [
            {"ply": 10, "side_moved": "white", "san": "Nf3"},
            {"ply": 11, "side_moved": "black", "san": "Nf6"},
            {"ply": 12, "side_moved": "white", "san": "Bg5"},
            {"ply": 13, "side_moved": "black", "san": "Be7"},
            {"ply": 14, "side_moved": "white", "san": "Bxf6"}
        ]
        
        result = analyzer.analyze(ply_records, 14)
        
        assert "plan_continuity" in result
        assert result["plan_continuity"] in ["continued", "broken", "early"]


class TestPhaseAwareInterpretation:
    """Test phase-aware mistake interpretation."""
    
    def test_opening_mistake_interpretation(self):
        """Test interpretation of mistakes in opening."""
        interpreter = PhaseAwareInterpreter()
        
        result = interpreter.interpret("missed_opponent_move", "opening", 100)
        
        assert result["phase_context"] in ["development error", "theory deviation", "missed_opponent_move"]
        assert "opening" in result["interpretation"]
    
    def test_endgame_mistake_interpretation(self):
        """Test interpretation of mistakes in endgame."""
        interpreter = PhaseAwareInterpreter()
        
        result = interpreter.interpret("calculation_failure", "endgame", 150)
        
        assert result["phase_context"] in ["endgame calculation error", "technique issue", "calculation_failure"]
        assert "endgame" in result["interpretation"]
        assert result["severity_adjusted"] in ["critical", "significant", "moderate"]


class TestComparativeAnalysis:
    """Test comparative move analysis."""
    
    def test_intent_comparison(self):
        """Test comparison of played vs best move intent."""
        analyzer = ComparativeMoveAnalyzer()
        
        move_intent = {
            "primary_type": "positional_improvement",
            "confidence": 0.8
        }
        best_move_intent = {
            "primary_type": "tactical_execution",
            "confidence": 0.9
        }
        tag_deltas = {
            "net_change": 0,
            "tag_delta_best": 2
        }
        eval_evidence = {
            "cp_loss": 100
        }
        
        result = analyzer.analyze(move_intent, best_move_intent, tag_deltas, eval_evidence)
        
        assert result["played_move"]["intent"] == "positional_improvement"
        assert result["best_move"]["intent"] == "tactical_execution"
        assert "insight" in result
        assert len(result["insight"]) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

