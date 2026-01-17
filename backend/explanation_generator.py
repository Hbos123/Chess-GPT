"""
Explanation Generator - Transforms raw analysis into coach-quality explanations.

This module provides tag-based explanation generation that justifies all
higher-order explanations with tag changes and existing tags.
"""

from typing import Dict, List, Optional, Tuple, Any
import chess


# Intent tag mappings - maps existing tags to move intent categories
INTENT_TAG_MAPPINGS = {
    "defensive": {
        "tags_indicating": [
            "king.exposed", "king.center.exposed", "king.shield.missing",
            "threat.mate", "threat.check", "piece.under_attack",
            "backrank.weak", "king.file.open"
        ],
        "weight": 1.0
    },
    "positional_improvement": {
        "tags_indicating": [
            "center.control.core", "center.control.near", "space.advantage",
            "outpost.knight", "outpost.bishop", "file.open", "file.semi",
            "diagonal.open", "diagonal.long", "piece.activity",
            "activity.mobility"
        ],
        "weight": 1.0
    },
    "tactical_execution": {
        "tags_indicating": [
            "fork", "pin", "skewer", "discovered_attack", "tactic",
            "check", "mate_threat", "piece.hanging", "capture.opportunity"
        ],
        "weight": 1.2
    },
    "structural_manipulation": {
        "tags_indicating": [
            "pawn.lever", "pawn.break", "pawn.passed", "pawn.isolated",
            "pawn.backward", "color.hole", "pawn.chain", "pawn.doubled"
        ],
        "weight": 0.9
    },
    "piece_economy": {
        "tags_indicating": [
            "trade.opportunity", "exchange", "simplification",
            "piece.coordination", "bishop.pair", "rook.connected"
        ],
        "weight": 0.8
    },
    "prophylactic": {
        "tags_indicating": [
            "prevent", "block", "overprotect", "defend"
        ],
        "weight": 0.9
    }
}

# Mistake tag patterns - maps tag deltas to mistake indicators
MISTAKE_TAG_PATTERNS = {
    "missed_opponent_move": {
        "critical_tags": ["threat.mate", "king.exposed", "piece.hanging", "fork", "pin"],
        "eval_threshold": 100,
        "description": "Opponent move in PV creates threatening tags that weren't addressed"
    },
    "calculation_failure": {
        "pattern": "lost_tags_present_in_best",
        "eval_threshold": 50,
        "description": "Played move loses tags that best move would have kept"
    },
    "strategic_misjudgment": {
        "pattern": "wrong_tag_type_for_position",
        "eval_threshold": 80,
        "description": "Played move creates wrong type of tags for position"
    },
    "intent_mismatch": {
        "pattern": "intent_vs_required_tags",
        "eval_threshold": 50,
        "description": "Move intent doesn't match game state requirements"
    },
    "evaluation_blindness": {
        "pattern": "tags_same_but_eval_changed",
        "eval_threshold": 100,
        "description": "Played move maintains tags but loses evaluation"
    }
}

# Explanation templates
EXPLANATION_TEMPLATES = {
    "missed_opponent_move": "Your move fails because of {opponent_move}, which {threat_description}. {context}",
    "calculation_failure": "You saw {what_player_saw}, but missed {critical_line}. {tag_evidence}",
    "strategic_misjudgment": "You focused on {player_focus}, but {what_mattered} was more important. {tag_evidence}",
    "intent_mismatch": "The idea of {move_intent} is good, but {game_state_requirement} is needed here. {tag_evidence}",
    "evaluation_blindness": "The position looks similar, but {eval_change_description}. {tag_evidence}",
    "defensive": "You needed to address {threats}, but instead {what_played_did}. {tag_evidence}",
    "positional_improvement": "You tried to improve {aspect}, but {why_failed}. {tag_evidence}"
}


class MoveIntentClassifier:
    """Classifies move intent based on existing tags in the position."""
    
    def classify(self, tags_before: List[Dict], themes_before: Dict, side: str) -> Dict:
        """
        Classify move intent from existing tags.
        
        Args:
            tags_before: Tags from position before move
            themes_before: Theme scores from position before move
            side: "white" or "black"
            
        Returns:
            {
                "primary_type": str,
                "secondary_types": List[str],
                "confidence": float,
                "justification": {
                    "tags_used": List[str],
                    "tag_strengths": Dict[str, float]
                }
            }
        """
        # Extract tag names for side
        side_tags = [
            t for t in tags_before
            if t.get("side") == side or t.get("side") == "both"
        ]
        tag_names = {t.get("tag_name", "") for t in side_tags}
        
        # Score each intent category
        intent_scores = {}
        tag_evidence = {}
        
        for intent_type, mapping in INTENT_TAG_MAPPINGS.items():
            score = 0.0
            matched_tags = []
            tag_strengths = {}
            
            for indicator_tag in mapping["tags_indicating"]:
                # Check if any tag contains this indicator
                for tag_name in tag_names:
                    if indicator_tag in tag_name.lower():
                        # Find the tag object to get strength
                        tag_obj = next((t for t in side_tags if t.get("tag_name") == tag_name), None)
                        strength = tag_obj.get("strength", 0.5) if tag_obj else 0.5
                        
                        score += strength * mapping["weight"]
                        matched_tags.append(tag_name)
                        tag_strengths[tag_name] = strength
            
            if score > 0:
                intent_scores[intent_type] = score
                tag_evidence[intent_type] = {
                    "tags": matched_tags,
                    "strengths": tag_strengths
                }
        
        # Select primary and secondary intents
        if not intent_scores:
            return {
                "primary_type": "unclear",
                "secondary_types": [],
                "confidence": 0.0,
                "justification": {"tags_used": [], "tag_strengths": {}}
            }
        
        sorted_intents = sorted(intent_scores.items(), key=lambda x: x[1], reverse=True)
        primary_type = sorted_intents[0][0]
        primary_score = sorted_intents[0][1]
        
        # Calculate confidence (normalize to 0-1)
        total_score = sum(intent_scores.values())
        confidence = min(primary_score / max(total_score, 1.0), 1.0)
        
        # Secondary types (score > 50% of primary)
        secondary_types = [
            intent for intent, score in sorted_intents[1:]
            if score > primary_score * 0.5
        ][:2]
        
        justification = tag_evidence.get(primary_type, {})
        if "tags" in justification:
            # Convert to expected format
            justification = {
                "tags_used": justification.get("tags", []),
                "tag_strengths": justification.get("strengths", {})
            }
        else:
            justification = {"tags_used": [], "tag_strengths": {}}
        
        return {
            "primary_type": primary_type,
            "secondary_types": secondary_types,
            "confidence": confidence,
            "justification": justification
        }


class TagDeltaAnalyzer:
    """Analyzes tag changes between positions."""
    
    def analyze(self, tags_before: List[Dict], tags_after_played: List[Dict], 
                best_move_tags: List[Dict], side: str) -> Dict:
        """
        Analyze tag deltas for a move.
        
        Args:
            tags_before: Tags before move
            tags_after_played: Tags after played move
            best_move_tags: Tags after best move
            side: "white" or "black"
            
        Returns:
            {
                "gained": List[str],
                "lost": List[str],
                "missed": List[str],
                "net_change": int,
                "tag_delta_played": int,
                "tag_delta_best": int
            }
        """
        # Filter tags by side
        before_names = {t.get("tag_name") for t in tags_before 
                       if t.get("side") == side or t.get("side") == "both"}
        after_played_names = {t.get("tag_name") for t in tags_after_played
                             if t.get("side") == side or t.get("side") == "both"}
        best_names = {t.get("tag_name") for t in best_move_tags
                     if t.get("side") == side or t.get("side") == "both"}
        
        # Calculate deltas
        gained = list(after_played_names - before_names)
        lost = list(before_names - after_played_names)
        missed = list(best_names - before_names - after_played_names)
        
        # Net changes
        tag_delta_played = len(gained) - len(lost)
        tag_delta_best = len(missed) + len(best_names & before_names) - len(lost)
        net_change = tag_delta_played
        
        return {
            "gained": gained,
            "lost": lost,
            "missed": missed,
            "net_change": net_change,
            "tag_delta_played": tag_delta_played,
            "tag_delta_best": tag_delta_best
        }


class PVMissedMoveDetector:
    """Detects missed opponent moves via PV analysis."""
    
    def detect(self, pv: List[str], tags_before: List[Dict], 
               tags_after_played: List[Dict], engine_info: List[Dict],
               fen_before: str, side_moved: str) -> Dict:
        """
        Detect if player missed a critical opponent move in PV.
        
        Args:
            pv: Principal variation (list of UCI moves)
            tags_before: Tags before move
            tags_after_played: Tags after played move
            engine_info: Engine analysis info
            fen_before: FEN before move
            side_moved: "white" or "black"
            
        Returns:
            {
                "detected": bool,
                "critical_move": Optional[str],
                "move_san": Optional[str],
                "threat_tags": List[Dict],
                "threat_description": Optional[str],
                "pv_position": Optional[int],
                "eval_swing": Optional[int]
            }
        """
        if not pv or len(pv) < 2:
            return {"detected": False}
        
        # Extract opponent moves (every other move starting from index 1)
        opponent_moves = [pv[i] for i in range(1, min(len(pv), 7), 2)]  # Check first 3 opponent moves
        
        tags_before_names = {t.get("tag_name") for t in tags_before}
        tags_after_played_names = {t.get("tag_name") for t in tags_after_played}
        
        critical_tags = [
            "threat.mate", "king.exposed", "king.center.exposed",
            "piece.hanging", "fork", "pin", "skewer", "discovered_attack",
            "check", "mate_threat"
        ]
        
        board = chess.Board(fen_before)
        opponent_side = "black" if side_moved == "white" else "white"
        
        for idx, opp_move_uci in enumerate(opponent_moves):
            try:
                # Play move sequence up to opponent move
                temp_board = chess.Board(fen_before)
                for i in range((idx * 2) + 1):
                    if i < len(pv):
                        temp_board.push(chess.Move.from_uci(pv[i]))
                
                # Get eval swing
                if idx == 0 and len(engine_info) > 0:
                    eval_before = engine_info[0].get("eval_cp", 0)
                    # Estimate eval after opponent move (would need actual analysis)
                    # For now, use PV eval if available
                    eval_swing = abs(engine_info[0].get("eval_cp", 0)) if engine_info else 0
                else:
                    eval_swing = 0
                
                # Check if this move would create critical tags
                # We simulate by checking if played move addressed these tags
                # In reality, we'd need to analyze the position after opponent move
                # For now, we check if played move didn't address known threats
                
                # Check if played move addressed any critical tags
                addressed_critical = any(
                    tag in tags_after_played_names for tag in critical_tags
                    if any(ct in tag for ct in critical_tags)
                )
                
                # If eval swing is large and critical tags weren't addressed, likely missed
                if eval_swing > 100 and not addressed_critical:
                    # Check if position before had indicators of this threat
                    threat_indicators = [
                        t for t in tags_before
                        if any(ct in t.get("tag_name", "").lower() for ct in ["threat", "attack", "check"])
                    ]
                    
                    if threat_indicators or eval_swing > 200:
                        move_obj = chess.Move.from_uci(opp_move_uci)
                        move_san = board.san(move_obj) if board.is_legal(move_obj) else opp_move_uci
                        
                        return {
                            "detected": True,
                            "critical_move": opp_move_uci,
                            "move_san": move_san,
                            "threat_tags": [{"tag_name": "threat.detected"}],
                            "threat_description": f"creates a critical threat (eval swing: {eval_swing}cp)",
                            "pv_position": idx + 1,
                            "eval_swing": eval_swing
                        }
            except Exception as e:
                continue
        
        return {"detected": False}


class MistakeClassifier:
    """Classifies mistake types using tag evidence."""
    
    def __init__(self):
        self.intent_classifier = MoveIntentClassifier()
        self.tag_delta_analyzer = TagDeltaAnalyzer()
        self.pv_detector = PVMissedMoveDetector()
    
    def classify(self, ply_record: Dict, raw_before: Dict, raw_after: Dict,
                 best_move_tags: List[Dict], engine_info: List[Dict]) -> Dict:
        """
        Classify mistake type.
        
        Args:
            ply_record: Complete ply record
            raw_before: Raw analysis before move
            raw_after: Raw analysis after move
            best_move_tags: Tags from best move
            engine_info: Engine analysis info
            
        Returns:
            {
                "primary_type": str,
                "secondary_types": List[str],
                "severity": str,
                "confidence": float,
                "justification": {...}
            }
        """
        side_moved = ply_record.get("side_moved", "white")
        cp_loss = ply_record.get("cp_loss", 0)
        tags_before = raw_before.get("tags", [])
        tags_after_played = raw_after.get("tags", [])
        
        # Get move intent
        move_intent = self.intent_classifier.classify(
            tags_before, raw_before.get("themes", {}), side_moved
        )
        
        # Analyze tag deltas
        tag_deltas = self.tag_delta_analyzer.analyze(
            tags_before, tags_after_played, best_move_tags, side_moved
        )
        
        # Check for missed opponent move
        pv = engine_info[0].get("pv", []) if engine_info else []
        missed_move = self.pv_detector.detect(
            pv, tags_before, tags_after_played, engine_info,
            ply_record.get("fen_before", ""), side_moved
        )
        
        # Score mistake types
        mistake_scores = {}
        mistake_evidence = {}
        
        # 1. Missed opponent move
        if missed_move.get("detected"):
            score = min(abs(missed_move.get("eval_swing", 0)) / 500.0, 1.0) * 0.9
            mistake_scores["missed_opponent_move"] = score
            mistake_evidence["missed_opponent_move"] = {
                "threat_tags": missed_move.get("threat_tags", []),
                "eval_swing": missed_move.get("eval_swing", 0),
                "pv_position": missed_move.get("pv_position")
            }
        
        # 2. Calculation failure (lost tags that best move keeps)
        best_tag_names = {bt.get("tag_name") for bt in best_move_tags}
        lost_tags_in_best = [tag for tag in tag_deltas["lost"] if tag in best_tag_names]
        
        if lost_tags_in_best or (tag_deltas["missed"] and not missed_move.get("detected")):
            # Strong indicator of calculation failure
            score = min((len(lost_tags_in_best) + len(tag_deltas["missed"])) / 5.0, 1.0) * 0.85
            if cp_loss > 50:
                score += 0.15
            # Boost if significant tag loss
            if len(tag_deltas["lost"]) >= 2:
                score += 0.1
            mistake_scores["calculation_failure"] = min(score, 1.0)
            mistake_evidence["calculation_failure"] = {
                "tags_lost": tag_deltas["lost"],
                "tags_missed": tag_deltas["missed"]
            }
        
        # 3. Intent mismatch (only if calculation_failure not detected)
        if "calculation_failure" not in mistake_scores:
            position_required_tags = self._get_required_tags(tags_before, cp_loss)
            move_created_tags = [t.get("tag_name") for t in tags_after_played]
            mismatch = len(set(position_required_tags) - set(move_created_tags))
            if mismatch > 0 and move_intent["primary_type"] != "defensive" and position_required_tags:
                score = min(mismatch / 3.0, 1.0) * 0.6
                mistake_scores["intent_mismatch"] = score
                mistake_evidence["intent_mismatch"] = {
                    "position_required_tags": position_required_tags,
                    "move_created_tags": move_created_tags[:5]
                }
        
        # 4. Strategic misjudgment
        if tag_deltas["missed"] and len(tag_deltas["missed"]) > len(tag_deltas["gained"]):
            score = min(len(tag_deltas["missed"]) / 3.0, 1.0) * 0.5
            if cp_loss > 80:
                score += 0.2
            mistake_scores["strategic_misjudgment"] = score
            mistake_evidence["strategic_misjudgment"] = {
                "tags_missed": tag_deltas["missed"],
                "tags_gained": tag_deltas["gained"]
            }
        
        # Determine severity first (based on cp_loss, matching engine_pool.py)
        # >=200=blunder, >=80=mistake, >=50=inaccuracy, <50=minor
        if cp_loss >= 200:
            severity = "blunder"
        elif cp_loss >= 80:
            severity = "mistake"
        elif cp_loss >= 50:  # 50-79 is inaccuracy
            severity = "inaccuracy"
        else:
            severity = "minor"  # <50 is minor for mistakes
        
        # Select primary mistake type
        if not mistake_scores:
            return {
                "primary_type": "unclear",
                "secondary_types": [],
                "severity": severity,  # Use calculated severity
                "confidence": 0.0,
                "justification": {}
            }
        
        sorted_mistakes = sorted(mistake_scores.items(), key=lambda x: x[1], reverse=True)
        primary_type = sorted_mistakes[0][0]
        primary_score = sorted_mistakes[0][1]
        
        # Secondary types
        secondary_types = [
            mistake for mistake, score in sorted_mistakes[1:]
            if score > primary_score * 0.6
        ][:2]
        
        return {
            "primary_type": primary_type,
            "secondary_types": secondary_types,
            "severity": severity,
            "confidence": min(primary_score, 1.0),
            "justification": {
                "tag_evidence": mistake_evidence.get(primary_type, {}),
                "eval_evidence": {
                    "cp_loss": cp_loss,
                    "eval_before": raw_before.get("eval_cp", 0),
                    "eval_after_played": raw_after.get("eval_cp", 0)
                }
            }
        }
    
    def _get_required_tags(self, tags_before: List[Dict], cp_loss: int) -> List[str]:
        """Determine what tags the position requires based on existing tags."""
        required = []
        tag_names = [t.get("tag_name", "") for t in tags_before]
        
        # If king is exposed, defensive tags required
        if any("king.exposed" in name or "king.center.exposed" in name for name in tag_names):
            required.extend(["king.safe", "defensive", "castle"])
        
        # If threats present, defensive tags required
        if any("threat" in name or "attack" in name for name in tag_names):
            required.extend(["defensive", "block", "prevent"])
        
        # If large cp loss, likely tactical issue
        if cp_loss > 100:
            required.extend(["tactical", "calculation"])
        
        return required


class NarrativeSelector:
    """Selects primary narrative from detected factors."""
    
    def select(self, mistake_classification: Dict, missed_move: Dict,
               tag_deltas: Dict, eval_evidence: Dict) -> Dict:
        """
        Select primary narrative reason.
        
        Args:
            mistake_classification: Mistake classification result
            missed_move: Missed move detection result
            tag_deltas: Tag delta analysis
            eval_evidence: Evaluation evidence
            
        Returns:
            {
                "primary_reason": str,
                "secondary_reasons": List[str],
                "suppressed_factors": List[str],
                "justification": {...}
            }
        """
        factors = []
        
        # Add missed opponent move factor
        if missed_move.get("detected"):
            score = self._score_factor("missed_opponent_move", missed_move, tag_deltas, eval_evidence)
            factors.append({
                "type": "missed_opponent_move",
                "score": score,
                "description": f"Missed opponent tactical resource ({missed_move.get('move_san', 'move')})"
            })
        
        # Add mistake type factors
        primary_mistake = mistake_classification.get("primary_type")
        if primary_mistake and primary_mistake != "unclear":
            score = self._score_factor(primary_mistake, {}, tag_deltas, eval_evidence)
            factors.append({
                "type": primary_mistake,
                "score": score,
                "description": self._get_mistake_description(primary_mistake)
            })
        
        # Add secondary mistake types
        for sec_type in mistake_classification.get("secondary_types", []):
            score = self._score_factor(sec_type, {}, tag_deltas, eval_evidence) * 0.7
            factors.append({
                "type": sec_type,
                "score": score,
                "description": self._get_mistake_description(sec_type)
            })
        
        if not factors:
            return {
                "primary_reason": "Minor inaccuracy",
                "secondary_reasons": [],
                "suppressed_factors": [],
                "justification": {}
            }
        
        # Sort by score
        factors.sort(key=lambda x: x["score"], reverse=True)
        
        primary = factors[0]
        secondary = [f["description"] for f in factors[1:3] if f["score"] > primary["score"] * 0.5]
        suppressed = [f["description"] for f in factors[3:] if f["score"] < primary["score"] * 0.3]
        
        return {
            "primary_reason": primary["description"],
            "secondary_reasons": secondary,
            "suppressed_factors": suppressed,
            "justification": {
                "primary_evidence": {
                    "type": primary["type"],
                    "score": primary["score"]
                },
                "tag_weight": 0.9 if tag_deltas.get("net_change", 0) != 0 else 0.5,
                "eval_weight": min(abs(eval_evidence.get("cp_loss", 0)) / 500.0, 1.0)
            }
        }
    
    def _score_factor(self, factor_type: str, factor_data: Dict,
                     tag_deltas: Dict, eval_evidence: Dict) -> float:
        """Score a narrative factor."""
        base_score = 0.0
        
        # Evaluation delta magnitude (0-1 scale)
        cp_loss = abs(eval_evidence.get("cp_loss", 0))
        eval_weight = min(cp_loss / 500.0, 1.0) * 0.4
        
        # Tag criticality
        tag_criticality = 0.0
        if factor_type == "missed_opponent_move":
            critical_tags = ["threat.mate", "king.exposed", "piece.hanging"]
            threat_tags = factor_data.get("threat_tags", [])
            if threat_tags:
                tag_criticality = 0.3
        elif factor_type == "calculation_failure":
            tags_lost = len(tag_deltas.get("tags_lost", []))
            tags_missed = len(tag_deltas.get("tags_missed", []))
            tag_criticality = min((tags_lost + tags_missed) / 5.0, 1.0) * 0.3
        elif factor_type == "intent_mismatch":
            mismatch = len(tag_deltas.get("position_required_tags", [])) - len(tag_deltas.get("move_created_tags", []))
            tag_criticality = min(mismatch / 3.0, 1.0) * 0.3
        
        # Material impact
        material_weight = 0.0
        if abs(eval_evidence.get("material_delta", 0)) > 100:
            material_weight = 0.2
        
        # Temporal proximity
        temporal_weight = 0.1
        
        total_score = eval_weight + tag_criticality + material_weight + temporal_weight
        return min(total_score, 1.0)
    
    def _get_mistake_description(self, mistake_type: str) -> str:
        """Get human-readable description of mistake type."""
        descriptions = {
            "missed_opponent_move": "Missed opponent tactical resource",
            "calculation_failure": "Calculation oversight",
            "strategic_misjudgment": "Strategic misjudgment",
            "intent_mismatch": "Wrong move type for position",
            "evaluation_blindness": "Evaluation misjudgment"
        }
        return descriptions.get(mistake_type, "Mistake")


class ExplanationGenerator:
    """Generates human-readable explanations from structured analysis."""
    
    def __init__(self):
        self.templates = EXPLANATION_TEMPLATES
    
    def generate(self, narrative: Dict, mistake_classification: Dict,
                missed_move: Dict, move_intent: Dict, tag_deltas: Dict) -> str:
        """
        Generate human-readable explanation.
        
        Args:
            narrative: Narrative selection result
            mistake_classification: Mistake classification
            missed_move: Missed move detection
            move_intent: Move intent classification
            tag_deltas: Tag delta analysis
            
        Returns:
            Human-readable explanation string
        """
        primary_mistake = mistake_classification.get("primary_type", "unclear")
        
        if primary_mistake == "missed_opponent_move" and missed_move.get("detected"):
            template = self.templates.get("missed_opponent_move", "{opponent_move} {threat_description}")
            context = f"You were trying to {move_intent.get('primary_type', 'improve your position')}, but this was not the moment for that type of move."
            return template.format(
                opponent_move=missed_move.get("move_san", "a move"),
                threat_description=missed_move.get("threat_description", "creates a threat"),
                context=context
            )
        
        elif primary_mistake == "intent_mismatch":
            template = self.templates.get("intent_mismatch", "The idea of {move_intent} is good, but {game_state_requirement} is needed here. {tag_evidence}")
            tag_evidence = self._format_tag_evidence(tag_deltas)
            required_action = self._get_required_action(tag_deltas)
            move_intent_str = move_intent.get("primary_type", "improving your position").replace("_", " ")
            explanation = template.format(
                move_intent=move_intent_str,
                game_state_requirement=required_action,
                tag_evidence=tag_evidence
            )
            # Ensure explanation mentions intent or wrong
            if "intent" not in explanation.lower() and "wrong" not in explanation.lower() and "idea" not in explanation.lower():
                explanation = f"The idea of {move_intent_str} is good, but {required_action} is needed here. {tag_evidence}"
            return explanation
        
        elif primary_mistake == "calculation_failure":
            template = self.templates.get("calculation_failure", "{what_player_saw} {critical_line}")
            tag_evidence = self._format_tag_evidence(tag_deltas)
            return template.format(
                what_player_saw="the position",
                critical_line="a critical line",
                tag_evidence=tag_evidence
            )
        
        else:
            # Generic explanation - use primary reason from narrative
            primary_reason = narrative.get('primary_reason', 'Mistake')
            tag_evidence = self._format_tag_evidence(tag_deltas)
            
            # If primary reason doesn't contain explanation, add tag evidence
            if tag_evidence:
                return f"{primary_reason}. {tag_evidence}"
            else:
                return primary_reason
    
    def _format_tag_evidence(self, tag_deltas: Dict) -> str:
        """Format tag evidence for explanation."""
        if tag_deltas.get("lost"):
            return f"You lost {len(tag_deltas['lost'])} positional advantage(s)."
        elif tag_deltas.get("missed"):
            return f"You missed {len(tag_deltas['missed'])} opportunity(s)."
        return ""
    
    def _get_required_action(self, tag_deltas: Dict) -> str:
        """Get required action from tag deltas."""
        required_tags = tag_deltas.get("position_required_tags", [])
        if "defensive" in required_tags or "king.safe" in required_tags:
            return "defensive moves"
        elif "tactical" in required_tags:
            return "tactical calculation"
        return "a different approach"


class TemporalContextAnalyzer:
    """Analyzes temporal context (move sequences)."""
    
    def analyze(self, ply_records: List[Dict], current_ply: int) -> Dict:
        """
        Analyze temporal context for a move.
        
        Args:
            ply_records: All ply records (for context)
            current_ply: Current ply number
            
        Returns:
            {
                "player_last_2_moves": List[str],
                "opponent_last_move": Optional[str],
                "plan_continuity": str,
                "ignored_threats": List[str]
            }
        """
        if current_ply < 2:
            return {
                "player_last_2_moves": [],
                "opponent_last_move": None,
                "plan_continuity": "early_game",
                "ignored_threats": []
            }
        
        # Get last 2 player moves
        player_moves = []
        if current_ply > 0 and current_ply <= len(ply_records):
            current_record = ply_records[current_ply - 1]
            current_side = current_record.get("side_moved")
            
            for i in range(max(0, current_ply - 4), current_ply):
                if i < len(ply_records):
                    record = ply_records[i]
                    if record.get("side_moved") == current_side:
                        player_moves.append(record.get("san", ""))
        
        # Get opponent's last move
        opponent_move = None
        if current_ply > 1 and current_ply <= len(ply_records):
            current_record = ply_records[current_ply - 1]
            current_side = current_record.get("side_moved")
            
            if current_ply - 2 >= 0 and current_ply - 2 < len(ply_records):
                opp_record = ply_records[current_ply - 2]
                if opp_record.get("side_moved") != current_side:
                    opponent_move = opp_record.get("san")
        
        # Detect plan continuity
        if len(player_moves) >= 2:
            # Check if moves have similar intent (simplified)
            plan_continuity = "continued" if len(player_moves) == 2 else "broken"
        else:
            plan_continuity = "early"
        
        return {
            "player_last_2_moves": player_moves[:2],
            "opponent_last_move": opponent_move,
            "plan_continuity": plan_continuity,
            "ignored_threats": []  # Would need threat analysis
        }


class PhaseAwareInterpreter:
    """Contextualizes mistakes by game phase."""
    
    def interpret(self, mistake_type: str, phase: str, cp_loss: int) -> Dict:
        """
        Interpret mistake in phase-appropriate context.
        
        Args:
            mistake_type: Type of mistake
            phase: "opening", "middlegame", or "endgame"
            cp_loss: Centipawn loss
            
        Returns:
            {
                "phase_context": str,
                "interpretation": str,
                "severity_adjusted": str
            }
        """
        phase_contexts = {
            "opening": {
                "missed_opponent_move": "development error",
                "calculation_failure": "theory deviation",
                "strategic_misjudgment": "opening principle violation"
            },
            "middlegame": {
                "missed_opponent_move": "tactical oversight",
                "calculation_failure": "calculation error",
                "strategic_misjudgment": "strategic misjudgment"
            },
            "endgame": {
                "missed_opponent_move": "technique issue",
                "calculation_failure": "endgame calculation error",
                "strategic_misjudgment": "technique issue"
            }
        }
        
        phase_context = phase_contexts.get(phase, {}).get(mistake_type, mistake_type)
        
        # Adjust severity by phase
        if phase == "endgame" and cp_loss > 100:
            severity_adjusted = "critical"
        elif phase == "opening" and cp_loss > 50:
            severity_adjusted = "significant"
        else:
            severity_adjusted = "moderate"
        
        return {
            "phase_context": phase_context,
            "interpretation": f"{phase_context} in the {phase}",
            "severity_adjusted": severity_adjusted
        }


class ComparativeMoveAnalyzer:
    """Compares played move vs best move."""
    
    def analyze(self, move_intent: Dict, best_move_intent: Dict,
               tag_deltas: Dict, eval_evidence: Dict) -> Dict:
        """
        Compare played move vs best move.
        
        Args:
            move_intent: Intent of played move
            best_move_intent: Intent of best move
            tag_deltas: Tag delta analysis
            eval_evidence: Evaluation evidence
            
        Returns:
            {
                "played_move": {...},
                "best_move": {...},
                "comparison": str,
                "insight": str
            }
        """
        played_outcome = "+" if tag_deltas.get("net_change", 0) > 0 else "-"
        played_outcome += f"{abs(tag_deltas.get('net_change', 0))} tags"
        
        best_outcome = "+" if tag_deltas.get("tag_delta_best", 0) > 0 else "-"
        best_outcome += f"{abs(tag_deltas.get('tag_delta_best', 0))} tags"
        
        # Determine risk levels (simplified)
        played_risk = "low" if abs(eval_evidence.get("cp_loss", 0)) < 50 else "medium"
        best_risk = "low" if tag_deltas.get("tag_delta_best", 0) > 0 else "medium"
        
        # Generate insight
        if move_intent.get("primary_type") == "defensive" and best_move_intent.get("primary_type") != "defensive":
            insight = "You chose safety over opportunity"
        elif move_intent.get("primary_type") == "positional_improvement" and best_move_intent.get("primary_type") == "tactical_execution":
            insight = "You chose position over tactics"
        else:
            insight = "Different strategic approach"
        
        return {
            "played_move": {
                "intent": move_intent.get("primary_type", "unclear"),
                "outcome": played_outcome,
                "risk": played_risk
            },
            "best_move": {
                "intent": best_move_intent.get("primary_type", "unclear"),
                "outcome": best_outcome,
                "risk": best_risk
            },
            "comparison": f"Played: {played_outcome}, Best: {best_outcome}",
            "insight": insight
        }


def generate_move_explanation(ply_record: Dict, raw_before: Dict, raw_after: Dict,
                             best_move_tags: List[Dict], engine_info: List[Dict],
                             ply_records: Optional[List[Dict]] = None,
                             phase: Optional[str] = None) -> Dict:
    """
    Generate complete structured explanation for a move.
    
    Args:
        ply_record: Complete ply record
        raw_before: Raw analysis before move
        raw_after: Raw analysis after move
        best_move_tags: Tags from best move
        engine_info: Engine analysis info
        ply_records: All ply records (for temporal context)
        phase: Game phase ("opening", "middlegame", "endgame")
        
    Returns:
        Complete structured analysis dictionary
    """
    side_moved = ply_record.get("side_moved", "white")
    
    # Initialize analyzers
    intent_classifier = MoveIntentClassifier()
    tag_delta_analyzer = TagDeltaAnalyzer()
    pv_detector = PVMissedMoveDetector()
    mistake_classifier = MistakeClassifier()
    narrative_selector = NarrativeSelector()
    explanation_generator = ExplanationGenerator()
    temporal_analyzer = TemporalContextAnalyzer()
    phase_interpreter = PhaseAwareInterpreter()
    comparative_analyzer = ComparativeMoveAnalyzer()
    
    # 1. Tag analysis
    tags_before = raw_before.get("tags", [])
    tags_after_played = raw_after.get("tags", [])
    tag_deltas = tag_delta_analyzer.analyze(
        tags_before, tags_after_played, best_move_tags, side_moved
    )
    
    # 2. Move intent classification
    move_intent = intent_classifier.classify(
        tags_before, raw_before.get("themes", {}), side_moved
    )
    
    # 3. Best move intent (if available)
    best_move_intent = intent_classifier.classify(
        tags_before, raw_before.get("themes", {}), side_moved
    )  # Simplified - would need actual best move analysis
    
    # 4. PV missed move detection
    pv = engine_info[0].get("pv", []) if engine_info else []
    missed_move = pv_detector.detect(
        pv, tags_before, tags_after_played, engine_info,
        ply_record.get("fen_before", ""), side_moved
    )
    
    # 5. Mistake classification
    mistake_classification = mistake_classifier.classify(
        ply_record, raw_before, raw_after, best_move_tags, engine_info
    )
    
    # 6. Narrative selection
    eval_evidence = {
        "cp_loss": ply_record.get("cp_loss", 0),
        "eval_before": raw_before.get("eval_cp", 0),
        "eval_after_played": raw_after.get("eval_cp", 0),
        "material_delta": 0  # Would need to calculate
    }
    narrative = narrative_selector.select(
        mistake_classification, missed_move, tag_deltas, eval_evidence
    )
    
    # 7. Generate explanation
    explanation = explanation_generator.generate(
        narrative, mistake_classification, missed_move, move_intent, tag_deltas
    )
    
    # 8. Temporal context
    temporal_context = {}
    if ply_records:
        current_ply = ply_record.get("ply", 1)
        temporal_context = temporal_analyzer.analyze(ply_records, current_ply)
    
    # 9. Phase-aware interpretation
    phase_context = {}
    if phase:
        phase_context = phase_interpreter.interpret(
            mistake_classification.get("primary_type", "unclear"),
            phase, ply_record.get("cp_loss", 0)
        )
    
    # 10. Comparative analysis
    comparison = comparative_analyzer.analyze(
        move_intent, best_move_intent, tag_deltas, eval_evidence
    )
    
    return {
        "tag_analysis": tag_deltas,
        "move_intent": move_intent,
        "mistake_classification": mistake_classification,
        "missed_opponent_move": missed_move,
        "narrative": {
            **narrative,
            "explanation": explanation
        },
        "comparison": comparison,
        "context": {
            **temporal_context,
            "phase": phase,
            **phase_context
        }
    }

