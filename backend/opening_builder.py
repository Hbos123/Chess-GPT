"""
Opening lesson builder - selects variations and creates lesson plans.
"""

import chess
import hashlib
import time
from typing import Dict, List, Optional, Tuple
from opening_explorer import LichessExplorerClient
from opening_resolver import resolve_opening


# Popularity thresholds
THETA_POP_MAIN = 0.12  # 12% - main line threshold
THETA_POP_ALT = 0.06   # 6% - alternate line threshold
THETA_POP_FORK = 0.08  # 8% - checkpoint creation threshold
THETA_POP_MIN = 0.04   # 4% - minimum to continue branch

# Depth limits
MAIN_LINE_DEPTH = 20
ALT_LINE_DEPTH = 8
OVERVIEW_DEPTH = 6

WHITE_MINOR_START = [chess.B1, chess.G1, chess.C1, chess.F1]
BLACK_MINOR_START = [chess.B8, chess.G8, chess.C8, chess.F8]


def _rooks_connected(board: chess.Board, color: bool) -> bool:
    back_rank = 0 if color == chess.WHITE else 7
    rooks = [
        sq
        for sq, piece in board.piece_map().items()
        if piece.piece_type == chess.ROOK and piece.color == color and chess.square_rank(sq) == back_rank
    ]
    if len(rooks) < 2:
        return False
    rooks.sort()
    left, right = rooks[0], rooks[-1]
    for file_idx in range(chess.square_file(left) + 1, chess.square_file(right)):
        sq = chess.square(file_idx, back_rank)
        if board.piece_at(sq):
            return False
    return True


def _minor_pieces_developed(board: chess.Board, color: bool) -> bool:
    start_squares = WHITE_MINOR_START if color == chess.WHITE else BLACK_MINOR_START
    for sq in start_squares:
        piece = board.piece_at(sq)
        if piece and piece.color == color and piece.piece_type in {chess.BISHOP, chess.KNIGHT}:
            return False
    return True


def _opening_phase_complete(board: chess.Board, orientation: str) -> bool:
    color = chess.WHITE if orientation == "white" else chess.BLACK
    return _rooks_connected(board, color) and _minor_pieces_developed(board, color)


class VariationBuilder:
    """Builds opening variations from explorer data."""
    
    def __init__(self, explorer: LichessExplorerClient):
        self.explorer = explorer
        self.visited_fens = set()
    
    def _rank_moves(self, moves: List[Dict], total_games: int, for_white: bool) -> List[Tuple[Dict, float]]:
        """
        Rank moves by composite score.
        
        Returns: List of (move_data, composite_score) tuples, sorted descending
        """
        if total_games == 0:
            return []
        
        ranked = []
        for move in moves:
            games = move.get("white", 0) + move.get("draws", 0) + move.get("black", 0)
            popularity = games / total_games
            
            # Calculate win rate from teaching side's perspective
            if for_white:
                win_rate = (move.get("white", 0) + 0.5 * move.get("draws", 0)) / games if games > 0 else 0.5
            else:
                win_rate = (move.get("black", 0) + 0.5 * move.get("draws", 0)) / games if games > 0 else 0.5
            
            # Composite score: 70% popularity, 30% win rate
            composite_score = 0.7 * popularity + 0.3 * win_rate
            
            ranked.append((move, composite_score, popularity, win_rate))
        
        # Sort by composite score descending
        ranked.sort(key=lambda x: x[1], reverse=True)
        return ranked
    
    async def _walk_branch(
        self,
        start_fen: str,
        start_moves: List[str],
        max_depth: int,
        min_popularity: float,
        orientation: str
    ) -> Dict:
        """
        Walk a variation branch until popularity drops or depth limit.
        
        Returns:
            {
                "moves_san": List[str],
                "fens": List[str],
                "checkpoints": List[Dict],  # Positions where significant forks occur
                "total_depth": int
            }
        """
        current_fen = start_fen
        moves_san = list(start_moves)
        fens = [current_fen]
        checkpoints = []
        
        board = chess.Board(current_fen)
        for_white = orientation == "white"
        
        for ply in range(max_depth):
            # Query current position
            try:
                explorer_data = await self.explorer.query_position(current_fen)
            except Exception as e:
                print(f"Explorer query failed: {e}")
                break
            
            total_games = explorer_data.get("white", 0) + explorer_data.get("draws", 0) + explorer_data.get("black", 0)
            if total_games == 0:
                break
            
            moves = explorer_data.get("moves", [])
            if not moves:
                break
            
            # Rank moves
            ranked = self._rank_moves(moves, total_games, for_white)
            if not ranked:
                break
            
            # Check if this is a fork point (multiple popular moves)
            popular_moves = [r for r in ranked if r[2] >= THETA_POP_FORK]  # r[2] is popularity
            if len(popular_moves) >= 2:
                # This is a checkpoint!
                popular_replies = [
                    {"san": r[0]["san"], "pop": r[2], "score": r[3]}
                    for r in popular_moves[:4]  # Top 4 popular replies
                ]
                
                checkpoints.append({
                    "fen": current_fen,
                    "moves_san": list(moves_san),
                    "objective": f"Find the best continuation ({popular_moves[0][0]['san']} is most popular)",
                    "popular_replies": popular_replies
                })
            
            # Continue with most popular/best move
            best_move_data, best_score, best_pop, best_wr = ranked[0]
            
            # Check if popularity is too low
            if best_pop < min_popularity:
                break
            
            # Make the move
            try:
                move_san = best_move_data["san"]
                move = board.parse_san(move_san)
                board.push(move)
                moves_san.append(move_san)
                current_fen = board.fen()
                fens.append(current_fen)
            except Exception as e:
                print(f"Failed to parse move: {e}")
                break

            if _opening_phase_complete(board, orientation):
                break
        
        return {
            "moves_san": moves_san,
            "fens": fens,
            "checkpoints": checkpoints,
            "total_depth": len(moves_san)
        }
    
    async def _select_alternates(
        self,
        fen: str,
        orientation: str,
        main_move_san: str
    ) -> List[Dict]:
        """Select 2-3 alternate moves at a position."""
        try:
            explorer_data = await self.explorer.query_position(fen)
        except:
            return []
        
        total_games = explorer_data.get("white", 0) + explorer_data.get("draws", 0) + explorer_data.get("black", 0)
        if total_games == 0:
            return []
        
        moves = explorer_data.get("moves", [])
        for_white = orientation == "white"
        
        ranked = self._rank_moves(moves, total_games, for_white)
        
        # Get alternates (excluding main move, with pop >= THETA_POP_ALT)
        alternates = []
        for move_data, score, pop, wr in ranked:
            if move_data["san"] == main_move_san:
                continue
            if pop >= THETA_POP_ALT:
                opening_data = move_data.get("opening") or {}
                alternates.append({
                    "san": move_data["san"],
                    "popularity": pop,
                    "win_rate": wr,
                    "eco": opening_data.get("eco"),
                    "name": opening_data.get("name")
                })
            if len(alternates) >= 3:
                break
        
        return alternates


async def build_opening_lesson(
    opening_query: str,
    explorer: LichessExplorerClient,
    db: str = "lichess",
    rating_range: Tuple[int, int] = (1600, 2000)
) -> Dict:
    """
    Build a complete opening lesson from a query.
    
    Args:
        opening_query: User's opening query
        explorer: Lichess explorer client
        db: "lichess" or "masters"
        rating_range: (min_rating, max_rating)
    
    Returns:
        Complete lesson plan dictionary
    """
    # Step 1: Resolve opening
    resolved = await resolve_opening(opening_query, explorer)
    
    # Step 2: Build variation tree
    builder = VariationBuilder(explorer)
    
    # Walk main line
    main_branch = await builder._walk_branch(
        start_fen=resolved["seed_fen"],
        start_moves=resolved["seed_moves_san"],
        max_depth=MAIN_LINE_DEPTH,
        min_popularity=THETA_POP_MIN,
        orientation=resolved["orientation"]
    )
    
    # Select alternates at key decision points
    alternate_branches = []
    
    # Look for alternates at the first few moves
    if len(main_branch["fens"]) > 0:
        check_fens = main_branch["fens"][:min(3, len(main_branch["fens"]))]
        
        for i, fen in enumerate(check_fens):
            main_move = main_branch["moves_san"][i] if i < len(main_branch["moves_san"]) else None
            if main_move:
                alternates = await builder._select_alternates(fen, resolved["orientation"], main_move)
                
                for alt in alternates[:2]:  # Max 2 alternates per position
                    # Walk this alternate
                    board_at_fork = chess.Board(fen)
                    try:
                        alt_move = board_at_fork.parse_san(alt["san"])
                        board_at_fork.push(alt_move)
                        alt_fen = board_at_fork.fen()
                        
                        alt_branch = await builder._walk_branch(
                            start_fen=alt_fen,
                            start_moves=main_branch["moves_san"][:i] + [alt["san"]],
                            max_depth=ALT_LINE_DEPTH,
                            min_popularity=THETA_POP_MIN,
                            orientation=resolved["orientation"]
                        )
                        
                        alternate_branches.append({
                            "id": f"alt_{i}_{alt['san']}",
                            "name": alt.get("name", f"Alternate: {alt['san']}"),
                            "fork_move": alt["san"],
                            "popularity": alt["popularity"],
                            "branch": alt_branch
                        })
                    except:
                        pass
    
    # Step 3: Compose lesson plan
    lesson_id = hashlib.md5(f"{opening_query}_{time.time()}".encode()).hexdigest()[:12]
    
    # Collect all checkpoint FENs
    all_checkpoints = []
    
    # Add main line checkpoints (these already start from the seed position)
    all_checkpoints.extend(main_branch["checkpoints"])
    
    # Add alternate branch checkpoints
    for alt in alternate_branches[:2]:  # Max 2 alternate branches
        if alt["branch"]["checkpoints"]:
            all_checkpoints.extend(alt["branch"]["checkpoints"][:2])  # Max 2 checkpoints per alternate
    
    # Build sections
    sections = [
        {
            "type": "overview",
            "main_branch_id": "main",
            "key_ideas": [
                f"Main line involves: {', '.join(main_branch['moves_san'][:6])}",
                f"Teaching from {resolved['orientation']}'s perspective",
                f"Based on {db} database, ratings {rating_range[0]}-{rating_range[1]}"
            ],
            "structure": resolved["name"]
        },
        {
            "type": "walkthrough",
            "branch_id": "main",
            "checkpoints": main_branch["checkpoints"]
        }
    ]
    
    if alternate_branches:
        sections.append({
            "type": "alternates",
            "branches": [
                {
                    "id": alt["id"],
                    "name": alt["name"],
                    "checkpoints": alt["branch"]["checkpoints"][:2]
                }
                for alt in alternate_branches[:2]
            ]
        })
    
    # Add drill section
    drill_fens = [cp["fen"] for cp in all_checkpoints]
    sections.append({
        "type": "drill",
        "fens": drill_fens
    })
    
    lesson_plan = {
        "lesson_id": lesson_id,
        "query": opening_query,
        "title": f"{resolved['name']} - Opening Lesson",
        "description": f"Learn the {resolved['name']} with main line and popular alternatives",
        "meta": {
            "db": db,
            "rating_range": list(rating_range),
            "speeds": ["rapid", "classical"],
            "orientation": resolved["orientation"],
            "eco": resolved.get("eco")
        },
        "sections": sections,
        "practice_count": len(all_checkpoints),
        "main_line_moves": main_branch["moves_san"],
        "alternates_count": len(alternate_branches)
    }
    
    return lesson_plan

