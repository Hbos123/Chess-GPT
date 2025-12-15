"""
Spaced Repetition System (SRS) Scheduler
Manages drill scheduling and session composition
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from drill_card import DrillCard, CardDatabase
import random
import chess
import chess.engine


class SRSScheduler:
    """Manages spaced repetition scheduling for drill cards"""
    
    def __init__(self):
        self.intervals = [1, 3, 7, 21, 45]  # Days
    
    def create_session(
        self,
        card_db: CardDatabase,
        session_length: int = 20,
        mode: str = "quick"
    ) -> Dict[str, Any]:
        """
        Create a training session from card database
        
        Args:
            card_db: Card database
            session_length: Number of drills
            mode: Session mode (quick/focused/opening/endgame)
            
        Returns:
            Session dictionary with cards and metadata
        """
        print(f"\n📚 SRS SCHEDULER: Creating {mode} session with {session_length} drills")
        
        # Get cards by stage
        new_cards = card_db.get_cards_by_stage("new")
        learning_cards = card_db.get_cards_by_stage("learning")
        review_cards = card_db.get_cards_by_stage("review")
        
        # Get due cards
        due_cards = card_db.get_due_cards(max_cards=session_length)
        
        print(f"   Card inventory: {len(new_cards)} new, {len(learning_cards)} learning, {len(review_cards)} review")
        print(f"   Due cards: {len(due_cards)}")
        
        # Composition percentages
        if mode == "quick":
            new_pct, learning_pct, review_pct = 0.30, 0.30, 0.40
        elif mode == "focused":
            new_pct, learning_pct, review_pct = 0.40, 0.30, 0.30
        else:
            new_pct, learning_pct, review_pct = 0.35, 0.30, 0.35
        
        # Calculate counts
        new_count = int(session_length * new_pct)
        learning_count = int(session_length * learning_pct)
        review_count = session_length - new_count - learning_count
        
        # Select cards
        session_cards = []
        
        # New cards
        selected_new = random.sample(new_cards, min(new_count, len(new_cards)))
        session_cards.extend(selected_new)
        
        # Learning cards (prioritize due)
        learning_due = [c for c in learning_cards if c.is_due()]
        learning_not_due = [c for c in learning_cards if not c.is_due()]
        selected_learning = learning_due[:learning_count]
        if len(selected_learning) < learning_count:
            selected_learning.extend(random.sample(learning_not_due, min(learning_count - len(selected_learning), len(learning_not_due))))
        session_cards.extend(selected_learning)
        
        # Review cards (prioritize due)
        review_due = [c for c in review_cards if c.is_due()]
        review_not_due = [c for c in review_cards if not c.is_due()]
        selected_review = review_due[:review_count]
        if len(selected_review) < review_count:
            selected_review.extend(random.sample(review_not_due, min(review_count - len(selected_review), len(review_not_due))))
        session_cards.extend(selected_review)
        
        # Shuffle
        random.shuffle(session_cards)
        
        print(f"   ✅ Session: {len(selected_new)} new, {len(selected_learning)} learning, {len(selected_review)} review")
        
        return {
            "session_id": self._generate_session_id(),
            "mode": mode,
            "cards": [card.to_dict() for card in session_cards],
            "total_cards": len(session_cards),
            "composition": {
                "new": len(selected_new),
                "learning": len(selected_learning),
                "review": len(selected_review)
            },
            "created_at": datetime.now().isoformat()
        }
    
    async def _verify_ground_truth(
        self,
        position: Dict,
        engine: Optional[chess.engine.SimpleEngine],
        depth: int
    ) -> Dict:
        """Verify best move at specified depth"""
        try:
            board = chess.Board(position["fen"])
            
            info = await engine.analyse(
                board,
                chess.engine.Limit(depth=depth),
                multipv=3
            )
            
            best_move = info[0]["pv"][0]
            best_san = board.san(best_move)
            
            score = info[0]["score"].white()
            eval_cp = score.score(mate_score=10000) if not score.is_mate() else (10000 if score.mate() > 0 else -10000)
            
            # Get PV
            pv = " ".join(board.san(m) for m in info[0]["pv"][:5])
            
            return {
                "verified_best_san": best_san,
                "verified_best_uci": best_move.uci(),
                "verified_eval_cp": eval_cp,
                "verified_pv": pv
            }
        
        except Exception as e:
            print(f"      Warning: Verification failed: {e}")
            return {}
    
    def _generate_session_id(self) -> str:
        """Generate unique session ID"""
        return datetime.now().strftime("%Y%m%d_%H%M%S")

