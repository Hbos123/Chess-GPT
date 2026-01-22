"""
Position Search Tool
Allows searching user's historical positions by tags, themes, and other criteria.
"""

from typing import List, Dict, Any, Optional
from supabase_client import SupabaseClient

def search_user_positions(
    supabase_client: SupabaseClient,
    user_id: str,
    tags: Optional[List[str]] = None,
    themes: Optional[List[str]] = None,
    error_categories: Optional[List[str]] = None,
    phases: Optional[List[str]] = None,
    mover_name: Optional[str] = None,
    limit: int = 5
) -> List[Dict[str, Any]]:
    """
    Search user's saved positions with various filters.
    
    Returns a list of positions with FEN, move_played, and best_move.
    """
    if not supabase_client:
        return []
        
    results = supabase_client.search_user_positions(
        user_id=user_id,
        tags=tags,
        error_categories=error_categories,
        phases=phases,
        themes=themes,
        mover_name=mover_name,
        limit=limit
    )
    
    # Format results to include key fields
    formatted_results = []
    for pos in results:
        formatted_results.append({
            "fen": pos.get("fen"),
            "move_played": pos.get("move_played"),
            "best_move": pos.get("best_move"),
            "tags": pos.get("tags_start", []),
            "error_category": pos.get("error_category"),
            "phase": pos.get("phase"),
            "id": pos.get("id")
        })
        
    return formatted_results
