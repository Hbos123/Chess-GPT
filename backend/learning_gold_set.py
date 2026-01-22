"""
Gold set evaluation for regression testing.

Loads frozen positions from JSON and evaluates model responses
against known-good engine lines.
"""

from __future__ import annotations

from typing import Dict, List, Any, Optional
import json
import os
import chess
from supabase_client import SupabaseClient


class GoldSetEvaluator:
    """Evaluates model responses against gold set positions."""
    
    def __init__(self, supabase_client: Optional[SupabaseClient] = None):
        self.supabase_client = supabase_client
        self.positions: List[Dict[str, Any]] = []
    
    def load_positions(self, json_path: str = "data/gold_set_positions.json") -> bool:
        """
        Load gold set positions from JSON file.
        
        Returns:
            True if loaded successfully, False otherwise
        """
        try:
            if not os.path.exists(json_path):
                print(f"⚠️  [GOLD_SET] File not found: {json_path}")
                return False
            
            with open(json_path, "r") as f:
                self.positions = json.load(f)
            
            print(f"✅ [GOLD_SET] Loaded {len(self.positions)} positions from {json_path}")
            return True
        except Exception as e:
            print(f"⚠️  [GOLD_SET] Failed to load positions: {e}")
            return False
    
    def load_from_supabase(self) -> bool:
        """
        Load gold set positions from Supabase table.
        
        Returns:
            True if loaded successfully, False otherwise
        """
        if not self.supabase_client:
            return False
        
        try:
            result = self.supabase_client.client.table("learning_gold_set").select("*").execute()
            if result.data:
                self.positions = result.data
                print(f"✅ [GOLD_SET] Loaded {len(self.positions)} positions from Supabase")
                return True
            return False
        except Exception as e:
            print(f"⚠️  [GOLD_SET] Failed to load from Supabase: {e}")
            return False
    
    def evaluate_response(
        self,
        position_id: str,
        model_response_move_san: str,
        model_response_eval_cp: Optional[float] = None,
        base_model: Optional[str] = None,
        prompt_bundle_version: Optional[str] = None,
        router_version: Optional[str] = None,
        interaction_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate a model response against a gold set position.
        
        Returns:
            Dict with evaluation results (matched_best_move_bool, eval_error_cp, etc.)
        """
        # Find position
        position = None
        for p in self.positions:
            if p.get("position_id") == position_id:
                position = p
                break
        
        if not position:
            return {"error": f"Position {position_id} not found in gold set"}
        
        known_best_move = position.get("known_best_move_san")
        known_best_eval = position.get("known_best_eval_cp")
        
        # Check if move matches best move
        matched_best_move = (model_response_move_san.lower().strip() == known_best_move.lower().strip())
        
        # Calculate eval error
        eval_error = None
        if model_response_eval_cp is not None and known_best_eval is not None:
            eval_error = abs(model_response_eval_cp - known_best_eval)
        
        result = {
            "position_id": position_id,
            "matched_best_move_bool": matched_best_move,
            "eval_error_cp": eval_error,
            "model_response_move_san": model_response_move_san,
            "model_response_eval_cp": model_response_eval_cp,
            "known_best_move_san": known_best_move,
            "known_best_eval_cp": known_best_eval,
        }
        
        # Save to Supabase if available
        if self.supabase_client and interaction_id:
            try:
                self.supabase_client.client.table("learning_gold_set_results").insert({
                    "position_id": position_id,
                    "interaction_id": interaction_id,
                    "model_response_move_san": model_response_move_san,
                    "model_response_eval_cp": model_response_eval_cp,
                    "matched_best_move_bool": matched_best_move,
                    "eval_error_cp": eval_error,
                    "base_model": base_model,
                    "prompt_bundle_version": prompt_bundle_version,
                    "router_version": router_version,
                }).execute()
            except Exception as e:
                print(f"⚠️  [GOLD_SET] Failed to save result: {e}")
        
        return result
    
    def get_all_positions(self) -> List[Dict[str, Any]]:
        """Get all loaded positions."""
        return self.positions


# Global instance
_gold_set_evaluator: Optional[GoldSetEvaluator] = None


def get_gold_set_evaluator() -> GoldSetEvaluator:
    """Get the global gold set evaluator instance."""
    global _gold_set_evaluator
    if _gold_set_evaluator is None:
        _gold_set_evaluator = GoldSetEvaluator()
    return _gold_set_evaluator


def init_gold_set_evaluator(supabase_client: Optional[SupabaseClient] = None) -> GoldSetEvaluator:
    """Initialize gold set evaluator with Supabase client."""
    global _gold_set_evaluator
    _gold_set_evaluator = GoldSetEvaluator(supabase_client)
    # Try to load from file first, then Supabase
    if not _gold_set_evaluator.load_positions():
        _gold_set_evaluator.load_from_supabase()
    return _gold_set_evaluator

