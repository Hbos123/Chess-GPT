"""
Board Simulator for Interpreter
Allows interpreter to test moves and play out sequences on its own board
"""

import chess
from typing import Dict, Any, List, Optional
from dataclasses import dataclass


@dataclass
class MoveTestResult:
    """Result of testing a move"""
    move_san: str
    is_legal: bool
    resulting_fen: str
    opponent_responses: List[str]  # Legal moves for opponent
    pv_after_move: List[str]  # PV from engine after this move
    consequences: Dict[str, Any]  # Specific consequences (doubled pawns, pins, etc.)
    light_eval: Optional[float] = None  # Quick evaluation
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "move_san": self.move_san,
            "is_legal": self.is_legal,
            "resulting_fen": self.resulting_fen,
            "opponent_responses": self.opponent_responses[:5],  # Limit to top 5
            "pv_after_move": self.pv_after_move[:10],  # First 10 moves of PV
            "consequences": self.consequences,
            "light_eval": self.light_eval
        }


class BoardSimulator:
    """
    Simulates chess positions for the interpreter.
    Can test moves, play out sequences, and analyze consequences.
    """
    
    def __init__(self, engine_queue):
        self.engine_queue = engine_queue
    
    async def test_move(
        self,
        fen: str,
        move_san: str,
        follow_pv: bool = True,
        depth: int = 12
    ) -> MoveTestResult:
        """
        Test a move and see what happens.
        
        Args:
            fen: Starting position
            move_san: Move to test (e.g., "Nf3")
            follow_pv: If True, follow PV to see consequences
            depth: Depth for light analysis
        
        Returns:
            MoveTestResult with consequences
        """
        board = chess.Board(fen)
        
        # Check if move is legal
        try:
            move = board.parse_san(move_san)
            if move not in board.legal_moves:
                return MoveTestResult(
                    move_san=move_san,
                    is_legal=False,
                    resulting_fen=fen,
                    opponent_responses=[],
                    pv_after_move=[],
                    consequences={"error": "Move is not legal"}
                )
        except Exception as e:
            return MoveTestResult(
                move_san=move_san,
                is_legal=False,
                resulting_fen=fen,
                opponent_responses=[],
                pv_after_move=[],
                consequences={"error": f"Invalid move: {str(e)}"}
            )
        
        # Make the move
        board.push(move)
        resulting_fen = board.fen()
        
        # Get opponent's legal moves
        opponent_responses = [board.san(m) for m in board.legal_moves]
        
        # Light analysis of resulting position
        pv = []
        light_eval = None
        try:
            info = await self.engine_queue.enqueue(
                self.engine_queue.engine.analyse,
                board,
                chess.engine.Limit(depth=depth)
            )
            
            pv = [board.san(m) for m in info.get("pv", [])]
            score = info.get("score")
            if score:
                if score.is_mate():
                    light_eval = 10000 if score.mate() > 0 else -10000
                else:
                    light_eval = score.relative.score(mate_score=10000)
        except Exception as e:
            # Engine analysis failed, continue without PV
            pass
        
        # Analyze consequences (board is now after the move)
        consequences = await self._analyze_consequences(
            fen, move_san, board, move, pv if follow_pv else []
        )
        
        return MoveTestResult(
            move_san=move_san,
            is_legal=True,
            resulting_fen=resulting_fen,
            opponent_responses=opponent_responses,
            pv_after_move=pv,
            consequences=consequences,
            light_eval=light_eval
        )
    
    async def _analyze_consequences(
        self,
        original_fen: str,
        move_san: str,
        board_after: chess.Board,
        move_obj: chess.Move,
        pv: List[str]
    ) -> Dict[str, Any]:
        """Analyze specific consequences of a move, including tactics"""
        consequences = {}
        
        # Check for doubled pawns
        doubled_pawns = self._check_doubled_pawns(board_after)
        if doubled_pawns:
            consequences["doubled_pawns"] = doubled_pawns
        
        # Detect tactics using threat_analyzer
        tactics = self._detect_tactics(board_after, move_obj)
        if tactics:
            consequences["tactics"] = tactics
        
        # Check for pins (using threat_analyzer)
        pins = self._check_pins(board_after)
        if pins:
            consequences["pins"] = pins
        
        # Check if move allows opponent captures
        opponent_captures = []
        for move in board_after.legal_moves:
            if board_after.is_capture(move):
                opponent_captures.append(board_after.san(move))
        if opponent_captures:
            consequences["allows_captures"] = opponent_captures[:3]
        
        # Follow PV to see what happens
        if pv:
            pv_consequences = await self._follow_pv_consequences(board_after.copy(), pv[:5])
            if pv_consequences:
                consequences["pv_shows"] = pv_consequences
        
        return consequences
    
    def _detect_tactics(self, board: chess.Board, move_obj: chess.Move) -> Dict[str, Any]:
        """Detect tactical patterns: forks, skewers, discovered attacks, etc.
        
        Args:
            board: Board AFTER the move has been made
            move_obj: The move that was just made
        """
        tactics = {}
        
        try:
            from threat_analyzer import is_fork, is_skewer, _get_fork_details, _get_skewer_details, _get_pin_details
            
            if not move_obj:
                return tactics
            
            # Temporarily undo move to check tactics (need position before move)
            board.pop()
            
            # Check for forks (attacking two pieces)
            if is_fork(board, move_obj):
                fork_details = _get_fork_details(board, move_obj)
                tactics["fork"] = {
                    "description": f"{fork_details.get('attacker_name', 'Piece')} forks {', '.join(fork_details.get('targets', []))}",
                    "targets": fork_details.get("targets", []),
                    "attacker": fork_details.get("attacker_name", "")
                }
            
            # Check for skewers
            if is_skewer(board, move_obj):
                skewer_details = _get_skewer_details(board, move_obj)
                tactics["skewer"] = {
                    "description": f"{skewer_details.get('attacker_name', 'Piece')} skewers {skewer_details.get('front_piece', '')} and {skewer_details.get('back_piece', '')}",
                    "front_piece": skewer_details.get("front_piece", ""),
                    "back_piece": skewer_details.get("back_piece", "")
                }
            
            # Check for discovered attacks (move reveals attack from behind)
            discovered = self._check_discovered_attacks(board, move_obj)
            if discovered:
                tactics["discovered_attack"] = discovered
            
            # Restore move
            board.push(move_obj)
            
            # Check for pins in current position (after move)
            pin_details = _get_pin_details(board, move_obj)
            if pin_details:
                tactics["pin"] = {
                    "description": f"{pin_details.get('pinned_piece', 'Piece')} is pinned to {pin_details.get('target', 'target')}",
                    "pinned_piece": pin_details.get("pinned_piece", ""),
                    "target": pin_details.get("target", "")
                }
            
        except ImportError:
            # Fallback if threat_analyzer not available
            pass
        except Exception as e:
            # Don't fail on tactic detection errors - restore board if needed
            try:
                if board.move_stack and len(board.move_stack) == 0:
                    board.push(move_obj)
            except:
                pass
        
        return tactics
    
    def _check_discovered_attacks(self, board: chess.Board, move: Optional[chess.Move] = None) -> Optional[Dict[str, Any]]:
        """Check if a move creates a discovered attack"""
        if not move:
            return None
        
        # Temporarily undo move to check what was behind
        board.pop()
        
        # Check what piece is now attacking after the move
        from_sq = move.from_square
        to_sq = move.to_square
        
        # Find sliding pieces that could attack through the from_square
        discovered = []
        for sq in chess.SQUARES:
            piece = board.piece_at(sq)
            if piece and piece.color == board.turn and piece.piece_type in [chess.BISHOP, chess.ROOK, chess.QUEEN]:
                # Check if this piece can attack through from_sq to target
                if board.is_attacked_by(piece.color, to_sq):
                    # Check if from_sq was blocking
                    if self._square_blocks_attack(board, sq, to_sq, from_sq):
                        target_piece = board.piece_at(to_sq)
                        if target_piece and target_piece.color != piece.color:
                            discovered.append({
                                "attacker": chess.square_name(sq),
                                "target": chess.square_name(to_sq),
                                "piece": piece.symbol()
                            })
        
        board.push(move)  # Restore move
        
        if discovered:
            return {
                "description": f"Discovered attack: {discovered[0]['piece']} on {discovered[0]['attacker']} attacks {chess.square_name(discovered[0]['target'])}",
                "attacks": discovered
            }
        return None
    
    def _square_blocks_attack(self, board: chess.Board, attacker_sq: int, target_sq: int, blocker_sq: int) -> bool:
        """Check if blocker_sq is between attacker_sq and target_sq"""
        # Check if squares are aligned
        attacker_file, attacker_rank = chess.square_file(attacker_sq), chess.square_rank(attacker_sq)
        target_file, target_rank = chess.square_file(target_sq), chess.square_rank(target_sq)
        blocker_file, blocker_rank = chess.square_file(blocker_sq), chess.square_rank(blocker_sq)
        
        # Same file
        if attacker_file == target_file == blocker_file:
            return (attacker_rank < blocker_rank < target_rank) or (target_rank < blocker_rank < attacker_rank)
        
        # Same rank
        if attacker_rank == target_rank == blocker_rank:
            return (attacker_file < blocker_file < target_file) or (target_file < blocker_file < attacker_file)
        
        # Same diagonal
        if abs(attacker_file - target_file) == abs(attacker_rank - target_rank):
            if abs(attacker_file - blocker_file) == abs(attacker_rank - blocker_rank):
                # Check if blocker is between
                file_dir = 1 if target_file > attacker_file else -1
                rank_dir = 1 if target_rank > attacker_rank else -1
                blocker_file_dir = 1 if blocker_file > attacker_file else -1
                blocker_rank_dir = 1 if blocker_rank > attacker_rank else -1
                if blocker_file_dir == file_dir and blocker_rank_dir == rank_dir:
                    dist_to_blocker = abs(blocker_file - attacker_file)
                    dist_to_target = abs(target_file - attacker_file)
                    return dist_to_blocker < dist_to_target
        
        return False
    
    def _check_doubled_pawns(self, board: chess.Board) -> List[str]:
        """Check for doubled pawns on any file"""
        doubled = []
        for file in range(8):
            file_pawns = []
            for rank in range(8):
                square = chess.square(file, rank)
                piece = board.piece_at(square)
                if piece and piece.piece_type == chess.PAWN:
                    file_pawns.append(chess.square_name(square))
            if len(file_pawns) > 1:
                # Check if same color
                colors = [board.color_at(chess.parse_square(sq)) for sq in file_pawns]
                if len(set(colors)) == 1:  # All same color
                    file_name = chr(ord('a') + file)
                    doubled.append(f"file_{file_name}")
        return doubled
    
    def _check_pins(self, board: chess.Board) -> List[Dict[str, str]]:
        """Check for pinned pieces"""
        pins = []
        try:
            from threat_analyzer import _get_pin_details
            
            # Check all legal moves to see if any create pins
            for move in board.legal_moves:
                board.push(move)
                pin_details = _get_pin_details(board, move)
                if pin_details:
                    pins.append({
                        "move": board.san(move),
                        "pinned_piece": pin_details.get("pinned_piece", ""),
                        "target": pin_details.get("target", "")
                    })
                board.pop()
        except ImportError:
            pass
        except Exception:
            pass
        
        return pins
    
    async def _follow_pv_consequences(
        self,
        board: chess.Board,
        pv: List[str]
    ) -> Dict[str, Any]:
        """Follow PV and see what happens"""
        results = {
            "moves_played": [],
            "doubled_pawns_created": [],
            "material_changes": []
        }
        
        test_board = board.copy()
        for move_san in pv:
            try:
                move = test_board.parse_san(move_san)
                test_board.push(move)
                results["moves_played"].append(move_san)
                
                # Check for doubled pawns after each move
                doubled = self._check_doubled_pawns(test_board)
                if doubled:
                    for d in doubled:
                        if d not in results["doubled_pawns_created"]:
                            results["doubled_pawns_created"].append(d)
                
            except Exception:
                break
        
        return results
    
    async def test_move_sequence(
        self,
        fen: str,
        moves: List[str],
        depth: int = 12
    ) -> Dict[str, Any]:
        """
        Test a sequence of moves.
        
        Returns:
            {
                "success": bool,
                "final_fen": str,
                "moves_played": List[str],
                "consequences": Dict
            }
        """
        board = chess.Board(fen)
        moves_played = []
        
        for move_san in moves:
            try:
                move = board.parse_san(move_san)
                if move not in board.legal_moves:
                    return {
                        "success": False,
                        "error": f"{move_san} is not legal",
                        "moves_played": moves_played,
                        "final_fen": board.fen()
                    }
                board.push(move)
                moves_played.append(move_san)
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Invalid move {move_san}: {str(e)}",
                    "moves_played": moves_played,
                    "final_fen": board.fen()
                }
        
        # Analyze final position
        eval_cp = None
        try:
            info = await self.engine_queue.enqueue(
                self.engine_queue.engine.analyse,
                board,
                chess.engine.Limit(depth=depth)
            )
            score = info.get("score")
            if score:
                if score.is_mate():
                    eval_cp = 10000 if score.mate() > 0 else -10000
                else:
                    eval_cp = score.relative.score(mate_score=10000)
        except:
            pass
        
        # Get the first move object if available
        first_move_obj = None
        if moves:
            test_board = chess.Board(fen)
            try:
                first_move_obj = test_board.parse_san(moves[0])
            except:
                pass
        
        consequences = await self._analyze_consequences(fen, moves[0] if moves else "", board, first_move_obj, [])
        
        return {
            "success": True,
            "final_fen": board.fen(),
            "moves_played": moves_played,
            "consequences": consequences,
            "eval_cp": eval_cp
        }

