"""
Drill Card data structures and management
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import json


class DrillCard:
    """Represents a single training drill"""
    
    def __init__(
        self,
        card_id: str,
        fen: str,
        side_to_move: str,
        best_move_san: str,
        best_move_uci: str,
        tags: List,
        themes: Dict,
        difficulty: Dict,
        source: Dict,
        ground_truth: Optional[Dict] = None
    ):
        self.card_id = card_id
        self.fen = fen
        self.side_to_move = side_to_move
        self.best_move_san = best_move_san
        self.best_move_uci = best_move_uci
        self.tags = tags
        self.themes = themes
        self.difficulty = difficulty
        self.source = source
        self.ground_truth = ground_truth or {}
        
        # SRS state
        self.srs_state = {
            "stage": "new",  # new, learning, review
            "due_date": datetime.now().isoformat(),
            "interval_days": 0,
            "ease_factor": 2.5,
            "lapses": 0
        }
        
        # Statistics
        self.stats = {
            "attempts": 0,
            "correct_attempts": 0,
            "total_time_s": 0,
            "hints_used": 0,
            "last_attempt": None
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "card_id": self.card_id,
            "fen": self.fen,
            "side_to_move": self.side_to_move,
            "best_move_san": self.best_move_san,
            "best_move_uci": self.best_move_uci,
            "tags": self.tags,
            "themes": self.themes,
            "difficulty": self.difficulty,
            "source": self.source,
            "ground_truth": self.ground_truth,
            "srs_state": self.srs_state,
            "stats": self.stats
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'DrillCard':
        """Create DrillCard from dictionary"""
        card = cls(
            card_id=data["card_id"],
            fen=data["fen"],
            side_to_move=data["side_to_move"],
            best_move_san=data["best_move_san"],
            best_move_uci=data["best_move_uci"],
            tags=data["tags"],
            themes=data["themes"],
            difficulty=data["difficulty"],
            source=data["source"],
            ground_truth=data.get("ground_truth", {})
        )
        card.srs_state = data.get("srs_state", card.srs_state)
        card.stats = data.get("stats", card.stats)
        return card
    
    def update_srs(self, correct: bool, time_s: float):
        """Update SRS state after attempt"""
        self.stats["attempts"] += 1
        self.stats["total_time_s"] += time_s
        self.stats["last_attempt"] = datetime.now().isoformat()
        
        if correct:
            self.stats["correct_attempts"] += 1
            
            # Successful recall - increase interval
            if self.srs_state["stage"] == "new":
                self.srs_state["stage"] = "learning"
                self.srs_state["interval_days"] = 1
            elif self.srs_state["stage"] == "learning":
                if self.srs_state["interval_days"] < 7:
                    self.srs_state["interval_days"] = min(7, self.srs_state["interval_days"] * 2)
                else:
                    self.srs_state["stage"] = "review"
                    self.srs_state["interval_days"] = 21
            else:  # review
                self.srs_state["interval_days"] = int(self.srs_state["interval_days"] * self.srs_state["ease_factor"])
                self.srs_state["ease_factor"] = min(2.8, self.srs_state["ease_factor"] + 0.1)
        else:
            # Failed recall - reset or reduce interval
            self.srs_state["lapses"] += 1
            
            if self.srs_state["stage"] == "review":
                self.srs_state["stage"] = "learning"
                self.srs_state["interval_days"] = 1
            else:
                self.srs_state["interval_days"] = max(1, self.srs_state["interval_days"] // 2)
            
            self.srs_state["ease_factor"] = max(1.3, self.srs_state["ease_factor"] - 0.2)
        
        # Calculate due date
        due = datetime.now() + timedelta(days=self.srs_state["interval_days"])
        self.srs_state["due_date"] = due.isoformat()
    
    def is_due(self) -> bool:
        """Check if card is due for review"""
        due_date = datetime.fromisoformat(self.srs_state["due_date"])
        return datetime.now() >= due_date


class CardDatabase:
    """Manages collection of drill cards"""
    
    def __init__(self, storage_path: str = "backend/cache/training_cards"):
        self.storage_path = storage_path
        self.cards: Dict[str, DrillCard] = {}
        
        import os
        os.makedirs(storage_path, exist_ok=True)
    
    def add_card(self, card: DrillCard):
        """Add card to database"""
        self.cards[card.card_id] = card
    
    def get_due_cards(self, max_cards: int = 20) -> List[DrillCard]:
        """Get cards due for review"""
        due = [card for card in self.cards.values() if card.is_due()]
        due.sort(key=lambda c: c.srs_state["due_date"])
        return due[:max_cards]
    
    def get_cards_by_stage(self, stage: str) -> List[DrillCard]:
        """Get cards in specific SRS stage"""
        return [card for card in self.cards.values() if card.srs_state["stage"] == stage]
    
    def save(self, username: str):
        """Save cards to file"""
        import os
        filepath = os.path.join(self.storage_path, f"{username}_cards.jsonl")
        
        with open(filepath, "w") as f:
            for card in self.cards.values():
                f.write(json.dumps(card.to_dict()) + "\n")
    
    def load(self, username: str):
        """Load cards from file"""
        import os
        filepath = os.path.join(self.storage_path, f"{username}_cards.jsonl")
        
        if not os.path.exists(filepath):
            return
        
        self.cards = {}
        with open(filepath, "r") as f:
            for line in f:
                if line.strip():
                    card_data = json.loads(line)
                    card = DrillCard.from_dict(card_data)
                    self.cards[card.card_id] = card

