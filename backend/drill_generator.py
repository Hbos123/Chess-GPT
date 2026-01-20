"""
Drill Generator - Creates training drills from mined positions
"""

from typing import List, Dict, Any, Optional, Tuple
import chess
import chess.engine
import hashlib


class DrillGenerator:
    """Generates drills from positions"""
    
    def __init__(self):
        pass
    
    async def generate_drills(
        self,
        positions: List[Dict],
        drill_types: List[str],
        engine: Optional[chess.engine.SimpleEngine] = None,
        verify_depth: int = 18
    ) -> List[Dict]:
        """
        Generate drills from mined positions
        
        Args:
            positions: List of mined positions
            drill_types: Types of drills to generate
            engine: Stockfish engine for verification
            verify_depth: Depth to verify ground truth
            
        Returns:
            List of drill dictionaries
        """
        print(f"\n🎯 DRILL GENERATOR: Creating drills from {len(positions)} positions")
        print(f"   Drill types: {drill_types}")
        
        drills = []
        
        for idx, pos in enumerate(positions):
            drill_type = self._classify_drill_type(pos, drill_types)
            
            # Verify ground truth if engine available
            if engine:
                verified = await self._verify_ground_truth(pos, engine, verify_depth)
                pos.update(verified)
            
            # Generate drill card
            drill = self._create_drill_card(pos, drill_type)
            
            if drill:
                drills.append(drill)
                if idx < 3:  # Log first few for debugging
                    print(f"   Drill {idx+1}: {drill_type}, tags={pos.get('tags', [])[:2]}")
        
        print(f"   ✅ Generated {len(drills)} drills")
        
        return drills
    
    def _classify_drill_type(self, position: Dict, allowed_types: List[str]) -> str:
        """Determine drill type based on position characteristics"""
        tags = position.get("tags", [])
        category = position.get("category", "")
        cp_loss = position.get("cp_loss", 0)
        phase = position.get("phase", "middlegame")
        
        # Extract tag names
        tag_names = []
        for tag in tags:
            if isinstance(tag, dict):
                tag_names.append(tag.get("name", ""))
            else:
                tag_names.append(str(tag))
        
        tag_str = " ".join(tag_names).lower()
        
        # Classification logic
        if "tactics" in allowed_types:
            if any(t in tag_str for t in ["fork", "pin", "skewer", "discovered", "deflection"]):
                return "tactics"
        
        if "defense" in allowed_types:
            if any(t in tag_str for t in ["threat", "mate", "backrank"]) and cp_loss > 100:
                return "defense"
        
        if "critical_choice" in allowed_types:
            if category == "critical_best":
                return "critical_choice"
        
        if "conversion" in allowed_types:
            if phase == "endgame" and "advantage" in tag_str:
                return "conversion"
        
        if "opening" in allowed_types:
            if phase == "opening" or "theory_exit" in position.get("key_point_labels", []):
                return "opening"
        
        # Default
        return "tactics" if "tactics" in allowed_types else allowed_types[0]
    
    async def _verify_ground_truth(
        self,
        position: Dict,
        engine: chess.engine.SimpleEngine,
        depth: int
    ) -> Dict:
        """Verify best move and alternatives at specified depth"""
        try:
            board = chess.Board(position["fen"])
            
            info = await engine.analyse(
                board,
                chess.engine.Limit(depth=depth),
                multipv=3
            )
            
            # Extract best move
            best_pv = info[0]["pv"]
            best_move = best_pv[0]
            best_san = board.san(best_move)
            
            # Extract eval
            score = info[0]["score"].white()
            eval_cp = score.score(mate_score=10000) if not score.is_mate() else (10000 if score.mate() > 0 else -10000)
            
            # Extract alternatives
            alternatives = []
            for i in range(1, min(3, len(info))):
                alt_move = info[i]["pv"][0]
                alt_san = board.san(alt_move)
                alt_score = info[i]["score"].white()
                alt_cp = alt_score.score(mate_score=10000) if not alt_score.is_mate() else (10000 if alt_score.mate() > 0 else -10000)
                
                alternatives.append({
                    "san": alt_san,
                    "uci": alt_move.uci(),
                    "eval_cp": alt_cp,
                    "cp_loss": abs(eval_cp - alt_cp)
                })
            
            return {
                "verified_best_san": best_san,
                "verified_best_uci": best_move.uci(),
                "verified_eval_cp": eval_cp,
                "verified_pv": " ".join(board.san(m) for m in best_pv[:5]),
                "alternatives": alternatives
            }
        
        except Exception as e:
            print(f"      Warning: Could not verify ground truth: {e}")
            return {}
    
    def _create_drill_card(self, position: Dict, drill_type: str) -> Dict:
        """Create drill card from position with tag transition context"""
        # Generate unique card ID
        card_id = hashlib.md5(
            f"{position['fen']}{position['best_move_san']}".encode()
        ).hexdigest()[:12]
        
        # Extract tags for hints
        tags = position.get("tags", []) or position.get("tags_start", [])
        tag_names = []
        for tag in tags:
            if isinstance(tag, dict):
                tag_names.append(tag.get("name", tag.get("tag_name", "")))
            else:
                tag_names.append(str(tag))
        
        # Extract tag transition data
        tags_gained = position.get("tags_gained", [])
        tags_lost = position.get("tags_lost", [])
        tags_after_best = position.get("tags_after_best", [])
        tags_after_played = position.get("tags_after_played", [])
        
        # Extract piece information
        piece_blundered = position.get("piece_blundered")
        piece_best_move = position.get("piece_best_move")
        move_san = position.get("move_san") or position.get("player_move_san")
        
        # Generate contextual question and hint based on tag transitions
        question, hint = self._generate_contextual_prompt(
            drill_type, 
            position["side_to_move"],
            tags_lost,
            tags_gained,
            tags_after_best,
            tags_after_played,
            move_san,
            piece_blundered,
            piece_best_move
        )
        
        # Fallback to default if no contextual prompt generated
        if not question:
            question = self._generate_question(drill_type, position["side_to_move"])
        if not hint:
            hint = self._generate_hint(tag_names, drill_type)
        
        # Build drill card
        drill = {
            "card_id": card_id,
            "type": drill_type,
            "fen": position["fen"],
            "side_to_move": position["side_to_move"],
            "question": question,
            "best_move_san": position.get("verified_best_san", position.get("best_move_san")),
            "best_move_uci": position.get("verified_best_uci", position.get("best_move_uci")),
            "alternatives": position.get("alternatives", []),
            "eval_cp": position.get("verified_eval_cp", position.get("eval_before_cp", 0)),
            "tags": tag_names,
            "phase": position.get("phase"),
            "opening": position.get("opening"),
            "hint": hint,
            "difficulty": {
                "rating_est": self._estimate_difficulty(position),
                "cp_loss_if_wrong": position.get("cp_loss", 0)
            },
            "source": {
                "type": "own_game",
                "game_id": position.get("source_game_id") or position.get("from_game_id"),
                "ply": position.get("ply") or position.get("source_ply")
            },
            "explanation": "",  # Filled after user attempts
            # Tag transition metadata
            "tag_transitions": {
                "gained": tags_gained,
                "lost": tags_lost,
                "missed": list(set(tags_after_best) - set(tags_after_played)) if tags_after_best and tags_after_played else []
            },
            "piece_context": {
                "blundered": piece_blundered,
                "best_move": piece_best_move
            }
        }
        
        return drill
    
    def _generate_contextual_prompt(
        self,
        drill_type: str,
        side: str,
        tags_lost: List[str],
        tags_gained: List[str],
        tags_after_best: List[str],
        tags_after_played: List[str],
        move_san: Optional[str],
        piece_blundered: Optional[str],
        piece_best_move: Optional[str]
    ) -> Tuple[str, str]:
        """
        Generate contextual question and hint based on tag transitions.
        Returns (question, hint) tuple.
        """
        color = "White" if side == "white" else "Black"
        question = ""
        hint = ""
        
        # Check for missed opportunities (tag in best_move but not in played)
        missed_tags = []
        if tags_after_best and tags_after_played:
            missed_tags = list(set(tags_after_best) - set(tags_after_played))
        
        # Priority 1: Lost tags (most common case for mistakes/blunders)
        if tags_lost:
            primary_tag = tags_lost[0]  # Use first lost tag
            tag_display = primary_tag.replace("_", " ").title()
            
            if move_san:
                question = f"{color} to move — You mistakenly played {move_san}, losing {tag_display}. Find the better move that maintains this advantage."
            else:
                question = f"{color} to move — Find the move that maintains {tag_display} (your move lost this advantage)."
            
            if piece_blundered and piece_best_move and piece_blundered != piece_best_move:
                hint = f"💡 Consider moving your {piece_best_move} instead of your {piece_blundered}. The best move maintains {tag_display}."
            else:
                hint = f"💡 The best move maintains {tag_display} that your move lost."
        
        # Priority 2: Missed opportunities
        elif missed_tags:
            primary_tag = missed_tags[0]
            tag_display = primary_tag.replace("_", " ").title()
            
            question = f"{color} to move — The best move would gain {tag_display}, but your move missed this opportunity. Find the move that secures this advantage."
            
            if piece_best_move:
                hint = f"💡 Consider moving your {piece_best_move} to gain {tag_display}."
            else:
                hint = f"💡 The best move gains {tag_display}."
        
        # Priority 3: Gained tags (less common for errors, but still useful context)
        elif tags_gained:
            primary_tag = tags_gained[0]
            tag_display = primary_tag.replace("_", " ").title()
            
            question = f"{color} to move — Find the best move (your move gained {tag_display}, but there may be a better option)."
            hint = f"💡 Consider if there's a better way to gain {tag_display}."
        
        return (question, hint)
    
    def _generate_question(self, drill_type: str, side: str) -> str:
        """Generate question text for drill"""
        color = "White" if side == "white" else "Black"
        
        questions = {
            "tactics": f"{color} to move — find the best move",
            "defense": f"{color} to move — find the only move to survive",
            "critical_choice": f"{color} to move — this is a critical moment",
            "conversion": f"{color} to move — convert the advantage",
            "opening": f"{color} to move — what does theory recommend?",
            "strategic": f"{color} to move — choose the best plan"
        }
        
        return questions.get(drill_type, f"{color} to move — find the best move")
    
    def _generate_hint(self, tag_names: List[str], drill_type: str) -> str:
        """Generate hint from tags"""
        tag_str = " ".join(tag_names).lower()
        
        if "fork" in tag_str:
            return "💡 Look for a fork (attacking two pieces simultaneously)"
        elif "pin" in tag_str:
            return "💡 Look for a pin (immobilizing a piece)"
        elif "skewer" in tag_str:
            return "💡 Look for a skewer (forcing a valuable piece to move)"
        elif "mate" in tag_str or "checkmate" in tag_str:
            return "💡 Look for checkmate!"
        elif "threat" in tag_str:
            return "💡 Identify and neutralize the threat"
        elif "file" in tag_str and "open" in tag_str:
            return "💡 Consider the open file"
        elif "diagonal" in tag_str:
            return "💡 Look at the diagonal"
        elif "pawn" in tag_str:
            return "💡 Pawn structure is key here"
        else:
            return "💡 Think carefully about all forcing moves"
    
    def _estimate_difficulty(self, position: Dict) -> int:
        """Estimate difficulty rating"""
        base_rating = 1200
        
        cp_loss = position.get("cp_loss", 0)
        
        # Higher CP loss = easier to see it was wrong = easier drill
        if cp_loss >= 200:
            return base_rating + 200  # Obvious blunder
        elif cp_loss >= 100:
            return base_rating + 400  # Clear mistake
        elif cp_loss >= 50:
            return base_rating + 600  # Subtle error
        else:
            return base_rating + 800  # Critical choice

