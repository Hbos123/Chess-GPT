"""
Position Miner for Training & Drill System
Extracts training positions from analyzed games based on priority and diversity rules
"""

from typing import List, Dict, Any, Optional
from collections import defaultdict
import random
import json


class PositionMiner:
    """Mines training positions from analyzed games"""
    
    def __init__(self, openai_client=None, llm_router=None):
        self.max_duplicates_per_motif = 3
        self.max_same_opening = 5
        self.openai_client = openai_client
        self.llm_router = llm_router
    
    def mine_positions(
        self,
        analyzed_games: List[Dict],
        focus_tags: Optional[List[str]] = None,
        max_positions: int = 20,
        phase_filter: Optional[str] = None,
        side_filter: Optional[str] = None,
        include_critical_choices: bool = True
    ) -> List[Dict]:
        """
        Extract training positions from analyzed games
        
        Args:
            analyzed_games: List of game review results
            focus_tags: Prioritize positions matching these tags
            max_positions: Maximum positions to return
            phase_filter: Only extract from this phase (opening/middlegame/endgame)
            side_filter: Only extract for this side (white/black)
            include_critical_choices: Include correct critical moves as drills
            
        Returns:
            List of drill-ready positions
        """
        print(f"\n🔍 POSITION MINER: Mining {max_positions} positions from {len(analyzed_games)} games")
        print(f"   Focus tags: {focus_tags or 'all'}")
        print(f"   Filters: phase={phase_filter or 'all'}, side={side_filter or 'both'}")
        
        # Build game context for better selection
        game_summaries = []
        for game in analyzed_games:
            game_meta = game.get("game_metadata", {})
            result = game.get("metadata", {}).get("result", "unknown")
            game_summaries.append({
                "opening": game_meta.get("opening", "Unknown"),
                "character": game_meta.get("game_character", "unknown"),
                "result": result,
                "endgame_type": game_meta.get("endgame_type"),
                "total_moves": game_meta.get("total_moves", 0)
            })
        
        print(f"   Game types: {[g['character'] for g in game_summaries]}")
        print(f"   Openings: {[g['opening'][:30] for g in game_summaries[:3]]}")
        
        # Log search criteria
        print(f"\n   🔍 SEARCHING FOR:")
        if focus_tags:
            print(f"      Tags matching: {', '.join(focus_tags)}")
        if phase_filter:
            print(f"      Phase: {phase_filter}")
        if side_filter:
            print(f"      Side: {side_filter}")
        print(f"      Include critical choices: {include_critical_choices}")
        print(f"      Priority: Blunders > Mistakes > Critical > Threshold events")
        print()
        
        candidates = []
        moves_checked = 0
        
        # Extract candidates with priority scoring
        for game_idx, game in enumerate(analyzed_games):
            print(f"   Searching game {game_idx + 1}/{len(analyzed_games)}...")
            ply_records = game.get("ply_records", [])
            player_color = game.get("metadata", {}).get("player_color", "white")
            opening_name = game.get("opening", {}).get("name_final", "") or game.get("metadata", {}).get("opening", "")
            
            for record in ply_records:
                moves_checked += 1
                
                # Apply filters
                if phase_filter and record.get("phase") != phase_filter:
                    continue
                
                if side_filter and record.get("side_moved") != side_filter:
                    continue
                
                # Calculate priority score
                priority = self._calculate_priority(record, focus_tags, include_critical_choices)
                
                if priority > 0:
                    position = {
                        "fen": record.get("fen_before"),
                        "side_to_move": record.get("side_moved"),
                        "best_move_san": record.get("engine", {}).get("best_move_san"),
                        "best_move_uci": record.get("engine", {}).get("best_move_uci"),
                        "player_move_san": record.get("san"),
                        "player_move_uci": record.get("uci"),
                        "eval_before_cp": record.get("engine", {}).get("eval_before_cp", 0),
                        "eval_after_cp": record.get("engine", {}).get("played_eval_after_cp", 0),
                        "cp_loss": record.get("cp_loss", 0),
                        "category": record.get("category"),
                        "phase": record.get("phase"),
                        "tags": record.get("analyse", {}).get("tags", []),
                        "themes": record.get("analyse", {}).get("themes", {}),
                        "opening": opening_name,
                        "source_game_id": game.get("metadata", {}).get("game_id"),
                        "ply": record.get("ply"),
                        "time_spent_s": record.get("time_spent_s"),
                        "priority": priority,
                        "key_point_labels": record.get("key_point_labels", []),
                        "error_note": record.get("error_note", ""),
                        "critical_note": record.get("critical_note", ""),
                        "is_critical": record.get("is_critical", False),
                        "game_character": game.get("game_metadata", {}).get("game_character", "unknown"),
                        "game_result": game.get("metadata", {}).get("result", "unknown")
                    }
                    candidates.append(position)
        
        print(f"\n   📊 SEARCH RESULTS:")
        print(f"      Moves checked: {moves_checked}")
        print(f"      Candidates found: {len(candidates)}")
        
        if len(candidates) == 0:
            print(f"      ⚠️ NO RELEVANT POSITIONS FOUND")
            print(f"      Criteria may be too specific or games don't contain matching positions")
            return []  # Return empty list - frontend will handle
        
        # Show candidate breakdown
        by_category = {}
        for c in candidates:
            cat = c.get("category", "unknown")
            by_category[cat] = by_category.get(cat, 0) + 1
        print(f"      By category: {dict(by_category)}")
        
        # Sort by priority
        candidates.sort(key=lambda x: x["priority"], reverse=True)
        
        # Show top priorities
        top_3 = candidates[:3]
        print(f"      Top 3 priorities:")
        for i, c in enumerate(top_3):
            tags_str = ", ".join(self._extract_motifs(c["tags"]))[:40]
            print(f"        {i+1}. {c['category']} (priority={c['priority']:.1f}): {c['best_move_san']} - tags: {tags_str}")
        
        # Apply diversity rules
        selected = self._apply_diversity(candidates, max_positions)
        
        print(f"\n   ✅ FINAL SELECTION: {len(selected)} positions")
        if len(selected) == 0:
            print(f"      ⚠️ Diversity filtering removed all candidates")
            print(f"      Try broadening search criteria or increasing max_positions")
        
        return selected
    
    def _calculate_priority(
        self,
        record: Dict,
        focus_tags: Optional[List[str]],
        include_critical_choices: bool
    ) -> float:
        """Calculate priority score for a position"""
        priority = 0.0
        
        category = record.get("category", "")
        cp_loss = record.get("cp_loss", 0)
        key_labels = record.get("key_point_labels", [])
        
        # Priority Tier 1: Blunders matching focus tags (10 points)
        if category == "blunder":
            priority += 10.0
            if focus_tags and self._has_matching_tag(record, focus_tags):
                priority += 5.0  # Bonus for matching focus
        
        # Priority Tier 2: Mistakes matching focus tags (7 points)
        elif category == "mistake":
            priority += 7.0
            if focus_tags and self._has_matching_tag(record, focus_tags):
                priority += 3.0
        
        # Priority Tier 3: Critical choices (5 points)
        elif category == "critical_best" and include_critical_choices:
            priority += 5.0
        
        # Priority Tier 4: Threshold crossings (3 points)
        if any("threshold" in label for label in key_labels):
            priority += 3.0
        
        # Priority Tier 5: Theory exits (2 points)
        if "theory_exit" in key_labels:
            priority += 2.0
        
        # Bonus for high CP loss (learning opportunity)
        if cp_loss >= 100:
            priority += 2.0
        elif cp_loss >= 200:
            priority += 4.0
        
        # Bonus for time trouble (if available)
        time_spent = record.get("time_spent_s")
        if time_spent is not None and time_spent < 5 and cp_loss > 50:
            priority += 2.0  # Fast mistakes
        
        return priority
    
    def _has_matching_tag(self, record: Dict, focus_tags: List[str]) -> bool:
        """Check if record has any of the focus tags"""
        record_tags = record.get("analyse", {}).get("tags", [])
        
        for tag in record_tags:
            # Handle both dict and string tags
            if isinstance(tag, dict):
                tag_name = tag.get("name", tag.get("tag", ""))
            elif isinstance(tag, str):
                tag_name = tag
            else:
                continue
            
            # Check if any focus tag matches (partial match OK)
            for focus in focus_tags:
                if focus.lower() in tag_name.lower() or tag_name.lower() in focus.lower():
                    return True
        
        return False
    
    def _apply_diversity(self, candidates: List[Dict], max_positions: int) -> List[Dict]:
        """Apply diversity rules to candidate positions"""
        selected = []
        motif_count = defaultdict(int)
        opening_count = defaultdict(int)
        used_fens = set()
        
        for candidate in candidates:
            if len(selected) >= max_positions:
                break
            
            fen = candidate["fen"]
            opening = candidate["opening"]
            
            # Skip exact duplicates
            if fen in used_fens:
                continue
            
            # Check opening diversity
            if opening and opening_count[opening] >= self.max_same_opening:
                continue
            
            # Extract main motif from tags
            motifs = self._extract_motifs(candidate["tags"])
            
            # Check motif diversity
            skip = False
            for motif in motifs:
                if motif_count[motif] >= self.max_duplicates_per_motif:
                    skip = True
                    break
            
            if skip:
                continue
            
            # Accept position
            selected.append(candidate)
            used_fens.add(fen)
            
            if opening:
                opening_count[opening] += 1
            
            for motif in motifs:
                motif_count[motif] += 1
        
        return selected
    
    def _extract_motifs(self, tags: List) -> List[str]:
        """Extract main motifs from tags"""
        motifs = []
        
        for tag in tags:
            if isinstance(tag, dict):
                tag_name = tag.get("name", tag.get("tag", ""))
            elif isinstance(tag, str):
                tag_name = tag
            else:
                continue
            
            # Extract last part as motif (e.g., "tactic.fork" → "fork")
            if "." in tag_name:
                motif = tag_name.split(".")[-1]
                motifs.append(motif)
        
        return motifs

