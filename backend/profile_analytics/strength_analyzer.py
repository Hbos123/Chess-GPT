"""
Strength Analyzer
Assesses tactical vs positional skills, piece coordination, and phase proficiency.
"""

from typing import Dict, List, Any
import statistics

class StrengthAnalyzer:
    def __init__(self, supabase_client):
        self.supabase = supabase_client

    async def get_profile(self, user_id: str, games: List[Dict] = None) -> Dict[str, Any]:
        """Calculate advanced strength/weakness profile for a user."""
        if games is None:
            games = self.supabase.get_active_reviewed_games(user_id, limit=50)
        
        if not games:
            return {"status": "no_data"}

        return {
            "phase_proficiency": self._analyze_phases(games),
            "tactical_vs_positional": self._analyze_skill_types(games),
            "piece_performance": self._analyze_piece_accuracy(games),
            "calculation_depth_proxy": self._analyze_complexity_handling(games)
        }

    def _analyze_phases(self, games: List[Dict]) -> Dict[str, Any]:
        phases = {"opening": [], "middlegame": [], "endgame": []}
        for game in games:
            review = game.get("game_review", {})
            stats = review.get("stats", {})
            by_phase = stats.get("by_phase", {})
            for p in phases:
                acc = by_phase.get(p, {}).get("accuracy")
                if acc is not None:
                    phases[p].append(acc)
        
        return {
            k: round(statistics.mean(v), 1) if v else 0 
            for k, v in phases.items()
        }

    def _analyze_skill_types(self, games: List[Dict]) -> Dict[str, Any]:
        # Proxy: Tactics = moves with high eval swings (blunders/brilliant)
        # Positional = steady accuracy in complex but non-tactical positions
        tactical_acc = []
        positional_acc = []
        
        for game in games:
            review = game.get("game_review", {})
            ply_records = review.get("ply_records", [])
            for ply in ply_records:
                is_tactical = abs(ply.get("eval_delta", 0)) > 150
                acc = ply.get("accuracy_pct", 0)
                if is_tactical:
                    tactical_acc.append(acc)
                else:
                    positional_acc.append(acc)
        
        return {
            "tactical_accuracy": round(statistics.mean(tactical_acc), 1) if tactical_acc else 0,
            "positional_accuracy": round(statistics.mean(positional_acc), 1) if positional_acc else 0
        }

    def _analyze_piece_accuracy(self, games: List[Dict]) -> Dict[str, Any]:
        pieces = {"Pawn": [], "Knight": [], "Bishop": [], "Rook": [], "Queen": [], "King": []}
        for game in games:
            review = game.get("game_review", {})
            ply_records = review.get("ply_records", [])
            for ply in ply_records:
                san = ply.get("san", "")
                acc = ply.get("accuracy_pct")
                if not san or acc is None: continue
                
                # Simple SAN parsing
                p_type = "Pawn"
                if san[0] in "KQRBN":
                    mapping = {"K": "King", "Q": "Queen", "R": "Rook", "B": "Bishop", "N": "Knight"}
                    p_type = mapping[san[0]]
                
                if p_type in pieces:
                    pieces[p_type].append(acc)
        
        return {
            k: round(statistics.mean(v), 1) if v else 0 
            for k, v in pieces.items()
        }

    def _analyze_complexity_handling(self, games: List[Dict]) -> Dict[str, Any]:
        # Proxy: complexity = number of legal moves / piece interactions
        # Handling = accuracy in high-complexity positions
        complex_acc = []
        simple_acc = []
        
        for game in games:
            review = game.get("game_review", {})
            ply_records = review.get("ply_records", [])
            for ply in ply_records:
                # This is a very rough proxy for now
                # In a full impl, we'd use 'light_raw' data from Step 7
                complexity = len(ply.get("top_moves", []))
                acc = ply.get("accuracy_pct", 0)
                if complexity > 15:
                    complex_acc.append(acc)
                else:
                    simple_acc.append(acc)
        
        return {
            "complex_position_accuracy": round(statistics.mean(complex_acc), 1) if complex_acc else 0,
            "simple_position_accuracy": round(statistics.mean(simple_acc), 1) if simple_acc else 0
        }

