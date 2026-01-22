"""
Two-Move Win Engine - Fast Tactical Scanner
Purpose: Identify when wins/advantages or losses/disadvantages can materialize in 1-2 moves.
Scans for open tactics, blocked tactics, captures, promotions, checkmates, and mate patterns.
"""

import chess
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class TwoMoveWinResult:
    """Results from 2-move tactical scanner"""
    
    # Open tactics (immediately available)
    open_tactics: List[Dict[str, Any]] = field(default_factory=list)
    # [
    #   {
    #     "type": "fork" | "skewer" | "discovered_attack" | "double_attack" | "pin_win" | "deflection" | "overloading",
    #     "move": "Nf3",
    #     "sequence": ["Nf3", "Nxd4", "Nxf4"],  # 2-move sequence
    #     "targets": ["d4", "f4"],  # What's being attacked
    #     "material_gain": 1.0,  # In pawns
    #     "threat_level": "winning" | "equal" | "losing"
    #   }
    # ]
    
    # Blocked tactics (available after clearing)
    blocked_tactics: List[Dict[str, Any]] = field(default_factory=list)
    # [
    #   {
    #     "type": "blocked_fork" | "blocked_skewer" | "blocked_discovered" | "blocked_pin",
    #     "blocking_piece": "e2",  # Square of blocking piece
    #     "required_move": "e2-e4",  # Move needed to unblock
    #     "tactic_after": {...},  # What tactic becomes available
    #     "material_gain": 1.0
    #   }
    # ]
    
    # Open trades/captures
    open_captures: List[Dict[str, Any]] = field(default_factory=list)
    # [
    #   {
    #     "move": "Bxf7",
    #     "captures": "f7",  # Square being captured
    #     "material_gain": 3.0,  # Positive = winning, 0 = equal, negative = losing
    #     "forced_recapture": "Kxf7",  # If forced
    #     "type": "winning" | "equal" | "losing"
    #   }
    # ]
    
    # Closed trades/captures
    closed_captures: List[Dict[str, Any]] = field(default_factory=list)
    # [
    #   {
    #     "move": "Bxf7",
    #     "blocked_by": "e6",  # What's blocking it
    #     "material_gain": 3.0,  # If it were available
    #     "type": "potential_winning" | "potential_equal" | "blocked"
    #   }
    # ]
    
    # Promotions
    promotions: List[Dict[str, Any]] = field(default_factory=list)
    # [
    #   {
    #     "type": "immediate" | "threat" | "blocked",
    #     "pawn_square": "e7",
    #     "promotion_square": "e8",
    #     "moves_to_promote": 1,  # 1 = immediate, 2 = threat
    #     "blocking_piece": "e8"  # If blocked
    #   }
    # ]
    
    # Checkmates
    checkmates: List[Dict[str, Any]] = field(default_factory=list)
    # [
    #   {
    #     "type": "mate_in_1" | "mate_in_2" | "mate_pattern",
    #     "sequence": ["Qh7#"],  # Mate sequence
    #     "pattern": "back_rank" | "smothered" | "anastasia" | "boden" | "other",
    #     "moves": 1  # Moves to mate
    #   }
    # ]
    
    # Checkmating patterns
    mate_patterns: List[Dict[str, Any]] = field(default_factory=list)
    # [
    #   {
    #     "pattern": "back_rank_weakness" | "smothered_setup" | "anastasia_setup" | "boden_setup",
    #     "setup_moves": ["Qh7", "Nf7"],  # Moves to set up pattern
    #     "moves_to_mate": 2,  # Moves needed
    #     "weak_square": "h7"  # Key square
    #   }
    # ]
    
    # Summary flags
    has_winning_tactic: bool = False
    has_losing_tactic: bool = False  # Opponent has winning tactic
    has_immediate_threat: bool = False
    has_promotion_threat: bool = False
    has_mate_threat: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "open_tactics": self.open_tactics,
            "blocked_tactics": self.blocked_tactics,
            "open_captures": self.open_captures,
            "closed_captures": self.closed_captures,
            "promotions": self.promotions,
            "checkmates": self.checkmates,
            "mate_patterns": self.mate_patterns,
            "has_winning_tactic": self.has_winning_tactic,
            "has_losing_tactic": self.has_losing_tactic,
            "has_immediate_threat": self.has_immediate_threat,
            "has_promotion_threat": self.has_promotion_threat,
            "has_mate_threat": self.has_mate_threat
        }


class TwoMoveWinEngine:
    """
    Fast tactical scanner for 2-move deep tactics.
    Identifies when wins/advantages or losses/disadvantages can materialize.
    """
    
    def __init__(self):
        """Initialize the Two-Move Win Engine"""
        self.piece_values = {
            chess.PAWN: 1,
            chess.KNIGHT: 3,
            chess.BISHOP: 3,
            chess.ROOK: 5,
            chess.QUEEN: 9,
            chess.KING: 0
        }
        self.piece_names = {
            chess.PAWN: 'Pawn',
            chess.KNIGHT: 'Knight',
            chess.BISHOP: 'Bishop',
            chess.ROOK: 'Rook',
            chess.QUEEN: 'Queen',
            chess.KING: 'King'
        }

        # SEE-style capture/recapture proof depth (plies). This intentionally ignores non-capture zwischenzug lines.
        self._see_max_plies = 8
    
    async def scan_two_move_tactics(
        self,
        fen: str,
        side_to_move: chess.Color
    ) -> TwoMoveWinResult:
        """
        Scan for all 2-move deep tactics.
        Fast, shallow tactical analysis.
        
        Args:
            fen: FEN string of position
            side_to_move: Which side to analyze for
            
        Returns:
            TwoMoveWinResult with all tactical findings
        """
        board = chess.Board(fen)
        # Important: many detectors rely on board.turn; honor caller's side_to_move explicitly.
        # This allows safe scanning even if fen turn mismatches the requested side.
        board.turn = side_to_move
        result = TwoMoveWinResult()
        
        # 1. Scan for open tactics (1-move deep)
        result.open_tactics = self._scan_open_tactics(board, side_to_move)
        
        # 2. Scan for blocked tactics (2-move deep: clear + tactic)
        result.blocked_tactics = self._scan_blocked_tactics(board, side_to_move)
        
        # 3. Scan for open captures
        result.open_captures = self._scan_open_captures(board, side_to_move)
        
        # 4. Scan for closed captures
        result.closed_captures = self._scan_closed_captures(board, side_to_move)
        
        # 5. Scan for promotions
        result.promotions = self._scan_promotions(board, side_to_move)
        
        # 6. Scan for checkmates
        result.checkmates = self._scan_checkmates(board, side_to_move)
        
        # 7. Scan for mate patterns
        result.mate_patterns = self._scan_mate_patterns(board, side_to_move)
        
        # Set summary flags
        result.has_winning_tactic = any(
            t.get("threat_level") == "winning" for t in result.open_tactics
        )
        
        # Check opponent's tactics (threats if the opponent were to move next).
        # We scan on a copy with turn flipped to avoid parse_san / legality mismatches.
        opponent_board = chess.Board(fen)
        opponent_board.turn = (not side_to_move)
        opponent_tactics = self._scan_open_tactics(opponent_board, not side_to_move)
        result.has_losing_tactic = any(
            t.get("threat_level") == "winning" for t in opponent_tactics
        )
        
        result.has_immediate_threat = (
            len(result.open_tactics) > 0 or 
            len(result.open_captures) > 0 or
            len(result.checkmates) > 0
        )
        result.has_promotion_threat = any(
            p["type"] in ["immediate", "threat"] for p in result.promotions
        )
        result.has_mate_threat = (
            len(result.checkmates) > 0 or 
            len(result.mate_patterns) > 0
        )
        
        return result
    
    def _scan_open_tactics(
        self,
        board: chess.Board,
        side: chess.Color
    ) -> List[Dict[str, Any]]:
        """Scan for immediately available tactics - VALIDATED"""
        tactics = []
        
        try:
            from threat_analyzer import is_fork, is_skewer, _get_fork_details, _get_skewer_details
            from threat_detector import detect_fork_threats, detect_pin_threats, detect_skewer_threats
            
            # Use existing threat detectors
            # Ensure the board is on the right turn for SAN parsing / legal move generation.
            board.turn = side

            fork_threats = detect_fork_threats(board, side)
            for threat in fork_threats:
                move_token = threat.get("move", "")
                try:
                    # threat_detector may provide SAN or UCI; accept either
                    try:
                        move = board.parse_san(move_token)
                        move_san = move_token
                    except Exception:
                        move = chess.Move.from_uci(move_token)
                        if move not in board.legal_moves:
                            raise
                        move_san = board.san(move)

                    # Validate the fork
                    validation = self._validate_tactic(board, move, "fork", side)

                    # SEE gate: refute "fork" claims that lose immediately to a simple recapture
                    see = self._see_refute_by_recapture(board, move, side)
                    
                    if validation["is_valid_tactic"] and not see.get("refuted", False):
                        # Check if fork attacks unequal-value pieces
                        targets = [t.get("square", "") for t in threat.get("targets", [])]
                        if self._fork_attacks_unequal_targets(board, move, targets):
                            tactics.append({
                                "type": "fork",
                                "move": move_san,
                                "sequence": [move_san],
                                "targets": targets,
                                "material_gain": validation["net_material_change"],
                                "threat_level": "winning" if validation["outcome"] == "win" else "equal",
                                "is_valid_tactic": True,
                                "forced_sequence_exists": validation["forced_sequence_exists"],
                                "best_opponent_defense": validation["best_opponent_defense"],
                                "verification": {
                                    "method": "see",
                                    "refuted": False,
                                    "net_if_recaptured": see.get("net_if_recaptured"),
                                    "refutation_line": see.get("refutation_line"),
                                },
                            })
                    elif see.get("refuted", False):
                        # Keep as a non-winning flag for debugging/UI, but never treat as valid/winning.
                        targets = [t.get("square", "") for t in threat.get("targets", [])]
                        tactics.append({
                            "type": "fork",
                            "move": move_san,
                            "sequence": [move_san],
                            "targets": targets,
                            "material_gain": 0.0,
                            "threat_level": "equal",
                            "is_valid_tactic": False,
                            "forced_sequence_exists": False,
                            "best_opponent_defense": (see.get("refutation_line") or [None])[0],
                            "verification": {
                                "method": "see",
                                "refuted": True,
                                "net_if_recaptured": see.get("net_if_recaptured"),
                                "refutation_line": see.get("refutation_line"),
                                "reason": "refuted_by_simple_recapture",
                            },
                        })
                except Exception:
                    pass  # Skip invalid moves
            
            # Check for skewers
            skewer_threats = detect_skewer_threats(board, side)
            for threat in skewer_threats:
                move_san = threat.get("move", "")
                try:
                    move = board.parse_san(move_san)
                    # Validate the skewer
                    validation = self._validate_tactic(board, move, "skewer", side)
                    
                    if validation["is_valid_tactic"]:
                        tactics.append({
                            "type": "skewer",
                            "move": move_san,
                            "sequence": [move_san],
                            "targets": [threat.get("front_piece", ""), threat.get("back_piece", "")],
                            "material_gain": validation["net_material_change"],
                            "threat_level": "winning" if validation["outcome"] == "win" else "equal",
                            "is_valid_tactic": True,
                            "forced_sequence_exists": validation["forced_sequence_exists"],
                            "best_opponent_defense": validation["best_opponent_defense"]
                        })
                except Exception:
                    pass
            
            # Check for discovered attacks (check each move)
            for move in board.legal_moves:
                if board.turn == side:
                    move_san = board.san(move)
                    discovered = self._check_discovered_attack(board, move)
                    if discovered:
                        # Validate discovered attack
                        validation = self._validate_tactic(board, move, "discovered_attack", side)
                        if validation["is_valid_tactic"]:
                            discovered.update({
                                "material_gain": validation["net_material_change"],
                                "threat_level": "winning" if validation["outcome"] == "win" else "equal",
                                "is_valid_tactic": True,
                                "forced_sequence_exists": validation["forced_sequence_exists"],
                                "best_opponent_defense": validation["best_opponent_defense"]
                            })
                            # Ensure move string is present and correct
                            discovered["move"] = discovered.get("move") or move_san
                            tactics.append(discovered)
            
            # Check for double attacks
            double_attacks = self._scan_double_attacks(board, side)
            for attack in double_attacks:
                move_san = attack.get("move", "")
                try:
                    move = board.parse_san(move_san)
                    validation = self._validate_tactic(board, move, "double_attack", side)
                    if validation["is_valid_tactic"]:
                        attack.update({
                            "material_gain": validation["net_material_change"],
                            "threat_level": "winning" if validation["outcome"] == "win" else "equal",
                            "is_valid_tactic": True,
                            "forced_sequence_exists": validation["forced_sequence_exists"],
                            "best_opponent_defense": validation["best_opponent_defense"]
                        })
                        tactics.append(attack)
                except Exception:
                    pass
            
            # Check for pins that win material
            pin_threats = detect_pin_threats(board, side)
            for threat in pin_threats:
                # Check if pinned piece can be captured
                if self._can_capture_pinned_piece(board, threat):
                    move_san = threat.get("move", "")
                    try:
                        move = board.parse_san(move_san)
                        validation = self._validate_tactic(board, move, "pin_win", side)
                        if validation["is_valid_tactic"]:
                            tactics.append({
                                "type": "pin_win",
                                "move": move_san,
                                "sequence": [move_san],
                                "targets": [threat.get("pinned_piece", "")],
                                "material_gain": validation["net_material_change"],
                                "threat_level": "winning" if validation["outcome"] == "win" else "equal",
                                "is_valid_tactic": True,
                                "forced_sequence_exists": validation["forced_sequence_exists"],
                                "best_opponent_defense": validation["best_opponent_defense"]
                            })
                    except Exception:
                        pass
            
            # Check for deflection and overloading (simplified - already return empty)
            deflection = self._scan_deflection(board, side)
            tactics.extend(deflection)
            overloading = self._scan_overloading(board, side)
            tactics.extend(overloading)
            
        except ImportError:
            # Fallback if threat_analyzer not available
            pass
        except Exception as e:
            pass
        
        return tactics
    
    def _fork_attacks_unequal_targets(
        self,
        board: chess.Board,
        fork_move: chess.Move,
        target_squares: List[str]
    ) -> bool:
        """Check if fork attacks targets of unequal value"""
        if len(target_squares) < 2:
            return False
        
        target_values = []
        for sq_str in target_squares:
            try:
                sq = chess.parse_square(sq_str)
                piece = board.piece_at(sq)
                if piece:
                    target_values.append(self.piece_values.get(piece.piece_type, 0))
            except:
                pass
        
        # If targets have different values, fork is more valuable
        if len(set(target_values)) > 1:
            return True
        
        # Even if equal value, check if fork move itself wins material
        if board.is_capture(fork_move):
            attacker = board.piece_at(fork_move.from_square)
            victim = board.piece_at(fork_move.to_square)
            if attacker and victim:
                if self.piece_values.get(victim.piece_type, 0) > self.piece_values.get(attacker.piece_type, 0):
                    return True
        
        return False
    
    def _scan_blocked_tactics(
        self,
        board: chess.Board,
        side: chess.Color
    ) -> List[Dict[str, Any]]:
        """Scan for tactics available after clearing blocking pieces (2-move deep) - VALIDATED"""
        blocked_tactics = []
        
        # For each legal move, check if it unblocks a tactic
        # Ensure scan is for the right side
        board.turn = side
        for move in board.legal_moves:
            if board.turn != side:
                continue
            required_move_san = board.san(move)
            # Play move temporarily
            board.push(move)
            
            # Check if tactic is now available
            try:
                from threat_analyzer import is_fork, is_skewer
                
                # Check for fork after clearing
                for follow_move in board.legal_moves:
                    if board.turn == side:
                        if is_fork(board, follow_move):
                            # Validate the fork after clearing
                            validation = self._validate_tactic(board, follow_move, "blocked_fork", side)
                            if validation["is_valid_tactic"]:
                                blocked_tactics.append({
                                    "type": "blocked_fork",
                                    "blocking_piece": chess.square_name(move.from_square),
                                    "required_move": required_move_san,
                                    "tactic_after": {
                                        "type": "fork",
                                        "move": board.san(follow_move)
                                    },
                                    "material_gain": validation["net_material_change"],
                                    "is_valid_tactic": True,
                                    "forced_sequence_exists": validation["forced_sequence_exists"],
                                    "best_opponent_defense": validation["best_opponent_defense"]
                                })
                            break
                
                # Check for skewer after clearing
                for follow_move in board.legal_moves:
                    if board.turn == side:
                        if is_skewer(board, follow_move):
                            # Validate the skewer after clearing
                            validation = self._validate_tactic(board, follow_move, "blocked_skewer", side)
                            if validation["is_valid_tactic"]:
                                blocked_tactics.append({
                                    "type": "blocked_skewer",
                                    "blocking_piece": chess.square_name(move.from_square),
                                    "required_move": required_move_san,
                                    "tactic_after": {
                                        "type": "skewer",
                                        "move": board.san(follow_move)
                                    },
                                    "material_gain": validation["net_material_change"],
                                    "is_valid_tactic": True,
                                    "forced_sequence_exists": validation["forced_sequence_exists"],
                                    "best_opponent_defense": validation["best_opponent_defense"]
                                })
                            break
            except ImportError:
                pass
            except Exception:
                pass
            finally:
                board.pop()
        
        return blocked_tactics
    
    def _scan_open_captures(
        self,
        board: chess.Board,
        side: chess.Color
    ) -> List[Dict[str, Any]]:
        """Scan for immediately available captures - VALIDATED with full capture chain resolution"""
        captures = []
        
        board.turn = side
        for move in board.legal_moves:
            if board.turn != side:
                continue
            
            if board.is_capture(move):
                # Validate capture with full chain resolution
                validation = self._validate_tactic(board, move, "capture", side)
                
                # Only accept if net material gain after opponent's best reply
                if validation["is_valid_tactic"] and validation["net_material_change"] > 0:
                    attacker = board.piece_at(move.from_square)
                    victim = board.piece_at(move.to_square)
                    
                    if attacker and victim:
                        captures.append({
                            "move": board.san(move),
                            "captures": chess.square_name(move.to_square),
                            "material_gain": validation["net_material_change"],
                            "forced_recapture": validation["best_opponent_defense"],
                            "type": "winning",
                            "is_valid_tactic": True,
                            "forced_sequence_exists": validation["forced_sequence_exists"]
                        })
                # Also accept equal trades if they lead to checkmate
                elif validation["is_valid_tactic"] and validation["outcome"] == "win":
                    captures.append({
                        "move": board.san(move),
                        "captures": chess.square_name(move.to_square),
                        "material_gain": 0.0,
                        "forced_recapture": validation["best_opponent_defense"],
                        "type": "winning",  # Winning due to mate
                        "is_valid_tactic": True,
                        "forced_sequence_exists": validation["forced_sequence_exists"]
                    })
        
        return captures
    
    def _scan_closed_captures(
        self,
        board: chess.Board,
        side: chess.Color
    ) -> List[Dict[str, Any]]:
        """Scan for blocked/potential captures - Only flag as potential, never winning"""
        closed_captures = []
        
        # Check for captures that would be available if blocking piece moved
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if piece and piece.color != side:
                # Check if we could capture this piece if something moved
                attackers = board.attackers(side, square)
                defenders = board.attackers(not side, square)
                
                if len(attackers) > 0:
                    # Potential capture exists
                    # Check what's blocking it
                    blocking_pieces = []
                    for atk_sq in attackers:
                        atk_piece = board.piece_at(atk_sq)
                        if atk_piece:
                            # Check if there's a clear path
                            move = chess.Move(atk_sq, square)
                            if move not in board.legal_moves:
                                # Blocked - find what's blocking
                                blocking_pieces.append(chess.square_name(atk_sq))
                    
                    if blocking_pieces:
                        attacker_value = self.piece_values.get(atk_piece.piece_type, 0) if atk_piece else 0
                        victim_value = self.piece_values.get(piece.piece_type, 0)
                        material_gain = victim_value - attacker_value
                        
                        # Only flag as potential if material gain is positive
                        # Never mark as "winning" since it's blocked
                        if material_gain > 0:
                            closed_captures.append({
                                "move": f"{chess.square_name(atk_sq)}x{chess.square_name(square)}",
                                "blocked_by": blocking_pieces[0] if blocking_pieces else None,
                                "material_gain": material_gain,
                                "type": "potential_winning",  # Potential only
                                "is_valid_tactic": False  # Not valid until unblocked
                            })
        
        return closed_captures
    
    def _scan_promotions(
        self,
        board: chess.Board,
        side: chess.Color
    ) -> List[Dict[str, Any]]:
        """Scan for promotion opportunities - VALIDATED (only unstoppable promotions)"""
        promotions = []
        
        # Check pawns on 7th rank (for white) or 2nd rank (for black)
        promotion_rank = 6 if side == chess.WHITE else 1
        
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if piece and piece.piece_type == chess.PAWN and piece.color == side:
                rank = chess.square_rank(square)
                
                if rank == promotion_rank:
                    # On promotion rank - check if promotion is unstoppable
                    file = chess.square_file(square)
                    promotion_square = chess.square(file, 7 if side == chess.WHITE else 0)
                    
                    # Check if promotion square is blocked
                    blocking_piece = board.piece_at(promotion_square)
                    
                    if blocking_piece is None:
                        # Immediate promotion - validate it can't be stopped
                        promotion_move = chess.Move(square, promotion_square, promotion=chess.QUEEN)
                        if promotion_move in board.legal_moves:
                            # Check if opponent can stop it
                            if self._is_promotion_unstoppable(board, promotion_move, side):
                                promotions.append({
                                    "type": "immediate",
                                    "pawn_square": chess.square_name(square),
                                    "promotion_square": chess.square_name(promotion_square),
                                    "moves_to_promote": 1,
                                    "blocking_piece": None,
                                    "is_valid_tactic": True
                                })
                    else:
                        # Blocked - check if blocking costs material
                        if self._blocking_promotion_costs_material(board, square, promotion_square, side):
                            promotions.append({
                                "type": "blocked",
                                "pawn_square": chess.square_name(square),
                                "promotion_square": chess.square_name(promotion_square),
                                "moves_to_promote": 1,
                                "blocking_piece": chess.square_name(promotion_square),
                                "is_valid_tactic": True
                            })
                elif rank == (promotion_rank - 1):
                    # One move away - check if path is clear and unstoppable
                    file = chess.square_file(square)
                    promotion_square = chess.square(file, 7 if side == chess.WHITE else 0)
                    
                    # Check if path is clear
                    blocking_piece = board.piece_at(promotion_square)
                    
                    if blocking_piece is None:
                        # Check if promotion threat is forcing
                        advance_move = chess.Move(square, promotion_square - (8 if side == chess.WHITE else -8))
                        if advance_move in board.legal_moves:
                            # Simulate advance and check if promotion becomes unstoppable
                            board.push(advance_move)
                            next_promotion_sq = chess.square(file, 7 if side == chess.WHITE else 0)
                            next_promotion_move = chess.Move(advance_move.to_square, next_promotion_sq, promotion=chess.QUEEN)
                            if next_promotion_move in board.legal_moves and self._is_promotion_unstoppable(board, next_promotion_move, side):
                                promotions.append({
                                    "type": "threat",
                                    "pawn_square": chess.square_name(square),
                                    "promotion_square": chess.square_name(promotion_square),
                                    "moves_to_promote": 2,
                                    "blocking_piece": None,
                                    "is_valid_tactic": True
                                })
                            board.pop()
        
        return promotions
    
    def _is_promotion_unstoppable(
        self,
        board: chess.Board,
        promotion_move: chess.Move,
        side: chess.Color
    ) -> bool:
        """Check if promotion cannot be stopped without material loss"""
        # If it's check, harder to stop
        board.push(promotion_move)
        is_check = board.is_check()
        board.pop()
        
        if is_check:
            # Check-promotion is usually unstoppable
            return True
        
        # Check if opponent can capture the promoting pawn
        opponent = not side
        attackers = board.attackers(opponent, promotion_move.from_square)
        
        if not attackers:
            # No attackers - promotion is unstoppable
            return True
        
        # If attacker exists, check if capturing costs material
        for attacker_sq in attackers:
            capture_move = chess.Move(attacker_sq, promotion_move.from_square)
            if capture_move in board.legal_moves:
                attacker = board.piece_at(attacker_sq)
                if attacker:
                    # Pawn is worth 1, attacker might be worth more
                    if self.piece_values.get(attacker.piece_type, 0) > 1:
                        # Capturing costs material - promotion is effectively unstoppable
                        return True
        
        return False
    
    def _blocking_promotion_costs_material(
        self,
        board: chess.Board,
        pawn_square: int,
        promotion_square: int,
        side: chess.Color
    ) -> bool:
        """Check if blocking the promotion costs material"""
        blocking_piece = board.piece_at(promotion_square)
        if blocking_piece and blocking_piece.color != side:
            # Opponent piece blocking - check if we can capture it favorably
            attackers = board.attackers(side, promotion_square)
            defenders = board.attackers(not side, promotion_square)
            
            if len(attackers) > len(defenders):
                # More attackers than defenders - can win material
                return True
        
        return False
    
    def _scan_checkmates(
        self,
        board: chess.Board,
        side: chess.Color
    ) -> List[Dict[str, Any]]:
        """Scan for checkmate opportunities - VALIDATED (only forcing sequences)"""
        checkmates = []
        
        # Check for mate in 1
        board.turn = side
        for move in board.legal_moves:
            if board.turn != side:
                continue
            move_san = board.san(move)
            board.push(move)
            if board.is_checkmate():
                # Mate in 1 is always valid
                checkmates.append({
                    "type": "mate_in_1",
                    "sequence": [move_san],
                    "pattern": "other",
                    "moves": 1,
                    "is_valid_tactic": True,
                    "forced_sequence_exists": True
                })
            board.pop()
        
        # Check for mate in 2 (only if forcing)
        for move in board.legal_moves:
            if board.turn != side:
                continue
            first_san = board.san(move)
            board.push(move)
            if board.is_check():
                # Check if opponent has very limited responses
                responses = list(board.legal_moves)
                if len(responses) <= 2:
                    # Check if ALL defenses allow a mate-in-1 reply (forcing mate in 2)
                    all_defenses_lose = True
                    chosen_line = None  # [first, defense, mate]

                    for defense in responses:
                        defense_san = board.san(defense)
                        board.push(defense)

                        mate_reply = None
                        for reply in board.legal_moves:
                            reply_san = board.san(reply)
                            board.push(reply)
                            is_mate = board.is_checkmate()
                            board.pop()
                            if is_mate:
                                mate_reply = reply_san
                                break

                        board.pop()

                        if mate_reply is None:
                            all_defenses_lose = False
                            break
                        if chosen_line is None:
                            chosen_line = [first_san, defense_san, mate_reply]

                    if all_defenses_lose and chosen_line:
                        checkmates.append({
                            "type": "mate_in_2",
                            "sequence": chosen_line,  # 3 plies: move, defense, mate
                            "pattern": "other",
                            "moves": 2,
                            "is_valid_tactic": True,
                            "forced_sequence_exists": True
                        })
            board.pop()
        
        return checkmates
    
    def _scan_mate_patterns(
        self,
        board: chess.Board,
        side: chess.Color
    ) -> List[Dict[str, Any]]:
        """Scan for checkmating patterns"""
        patterns = []
        
        # Check for back rank weakness
        back_rank_weakness = self._check_back_rank_weakness(board, side)
        if back_rank_weakness:
            patterns.append(back_rank_weakness)
        
        # Check for smothered mate setup
        smothered = self._check_smothered_mate_setup(board, side)
        if smothered:
            patterns.append(smothered)
        
        # Check for other patterns (simplified)
        # Can be extended with more pattern detection
        
        return patterns
    
    def _check_discovered_attack(
        self,
        board: chess.Board,
        move: chess.Move
    ) -> Optional[Dict[str, Any]]:
        """
        Check if a move creates a discovered attack.
        
        IMPORTANT: "targets" must be enemy piece squares newly attacked by an unblocked
        sliding piece (rook/bishop/queen). Never return the moved-to square as a "target".
        """
        mover_piece = board.piece_at(move.from_square)
        if mover_piece is None:
            return None
        mover_side = mover_piece.color

        # Compute SAN on the pre-move board (safe; caller also does this, but keep local).
        try:
            move_san = board.san(move)
        except Exception:
            return None

        from_sq = move.from_square

        # Helper: ray iteration
        def _ray(start_sq: chess.Square, df: int, dr: int):
            f = chess.square_file(start_sq) + df
            r = chess.square_rank(start_sq) + dr
            while 0 <= f < 8 and 0 <= r < 8:
                yield chess.square(f, r)
                f += df
                r += dr

        # Directions for sliders
        rook_dirs = [(1, 0), (-1, 0), (0, 1), (0, -1)]
        bishop_dirs = [(1, 1), (1, -1), (-1, 1), (-1, -1)]

        # Find discovered targets: slider is blocked FIRST by from_sq, and beyond is an enemy piece.
        candidates: List[tuple[chess.Square, chess.Square]] = []  # (slider_sq, target_sq)

        for slider_sq in chess.SQUARES:
            p = board.piece_at(slider_sq)
            if not p or p.color != mover_side:
                continue
            if p.piece_type not in (chess.ROOK, chess.BISHOP, chess.QUEEN):
                continue

            dirs = []
            if p.piece_type in (chess.ROOK, chess.QUEEN):
                dirs.extend(rook_dirs)
            if p.piece_type in (chess.BISHOP, chess.QUEEN):
                dirs.extend(bishop_dirs)

            for df, dr in dirs:
                first_blocker_sq = None
                for sq in _ray(slider_sq, df, dr):
                    if board.piece_at(sq) is not None:
                        first_blocker_sq = sq
                        break
                if first_blocker_sq != from_sq:
                    continue

                # The moved piece was the first blocker; look beyond for the next blocker.
                for sq in _ray(from_sq, df, dr):
                    piece_beyond = board.piece_at(sq)
                    if piece_beyond is None:
                        continue
                    # Only care about enemy pieces (and ignore pawns for low-signal noise).
                    if piece_beyond.color != mover_side and piece_beyond.piece_type != chess.PAWN:
                        # Ensure the slider wasn't already attacking this target pre-move.
                        try:
                            if sq in board.attacks(slider_sq):
                                break
                        except Exception:
                            pass
                        candidates.append((slider_sq, sq))
                    break  # Stop at first blocker beyond from_sq

        if not candidates:
            return None

        # Validate on the post-move position: the slider must actually attack the target.
        post = board.copy(stack=False)
        try:
            post.turn = mover_side
            if move not in post.legal_moves:
                return None
            post.push(move)
        except Exception:
            return None

        targets: List[str] = []
        for slider_sq, target_sq in candidates:
            try:
                # Slider piece must still exist and attack the target square.
                slider_piece_post = post.piece_at(slider_sq)
                target_piece_post = post.piece_at(target_sq)
                if not slider_piece_post or slider_piece_post.color != mover_side:
                    continue
                if not target_piece_post or target_piece_post.color == mover_side:
                    continue
                if target_sq in post.attacks(slider_sq):
                    targets.append(chess.square_name(target_sq))
            except Exception:
                continue

        # Sanity gate: if we don't have real enemy targets, don't emit.
        targets = list(dict.fromkeys([t for t in targets if isinstance(t, str) and t]))
        if not targets:
            return None

        return {
            "type": "discovered_attack",
            "move": move_san,
            "sequence": [move_san],
            "targets": targets,
            "material_gain": 0.0,  # Filled by validation
            "threat_level": "equal"
        }
    
    def _scan_double_attacks(
        self,
        board: chess.Board,
        side: chess.Color
    ) -> List[Dict[str, Any]]:
        """Scan for double attacks (attacking two targets)"""
        double_attacks = []
        
        board.turn = side
        for move in board.legal_moves:
            if board.turn != side:
                continue
            move_san = board.san(move)
            board.push(move)
            # Count how many enemy pieces are attacked
            attacked_count = 0
            targets = []
            for square in chess.SQUARES:
                piece = board.piece_at(square)
                if piece and piece.color != side:
                    if board.is_attacked_by(side, square):
                        attacked_count += 1
                        targets.append(chess.square_name(square))
            
            if attacked_count >= 2:
                double_attacks.append({
                    "type": "double_attack",
                    "move": move_san,
                    "sequence": [move_san],
                    "targets": targets,
                    "material_gain": 0.0,  # Unknown without deeper analysis
                    "threat_level": "equal"
                })
            
            board.pop()
        
        return double_attacks
    
    def _can_capture_pinned_piece(
        self,
        board: chess.Board,
        threat: Dict[str, Any]
    ) -> bool:
        """Check if a pinned piece can be captured"""
        # Simplified check - if piece is pinned and has fewer defenders
        pinned_square = threat.get("pinned_square")
        if pinned_square:
            square = chess.parse_square(pinned_square)
            attackers = board.attackers(board.turn, square)
            defenders = board.attackers(not board.turn, square)
            return len(attackers) > len(defenders)
        return False
    
    def _scan_deflection(
        self,
        board: chess.Board,
        side: chess.Color
    ) -> List[Dict[str, Any]]:
        """Scan for deflection tactics"""
        deflections = []
        # Simplified - check if moving a piece away from defense creates a threat
        # Can be extended with more sophisticated detection
        return deflections
    
    def _scan_overloading(
        self,
        board: chess.Board,
        side: chess.Color
    ) -> List[Dict[str, Any]]:
        """Scan for overloading tactics"""
        overloadings = []
        # Simplified - check if a piece is defending multiple things
        # Can be extended with more sophisticated detection
        return overloadings
    
    def _check_back_rank_weakness(
        self,
        board: chess.Board,
        side: chess.Color
    ) -> Optional[Dict[str, Any]]:
        """Check for back rank weakness (mate pattern)"""
        enemy_side = not side
        back_rank = 0 if enemy_side == chess.WHITE else 7
        
        # Check if enemy king is on back rank with limited escape squares
        king_square = board.king(enemy_side)
        if king_square is None:
            return None
        
        king_rank = chess.square_rank(king_square)
        if king_rank == back_rank:
            # Check if back rank is blocked by own pieces
            file = chess.square_file(king_square)
            escape_squares = []
            for f in [file - 1, file, file + 1]:
                if 0 <= f <= 7:
                    escape_sq = chess.square(f, back_rank + (1 if enemy_side == chess.WHITE else -1))
                    if board.piece_at(escape_sq) is None:
                        escape_squares.append(chess.square_name(escape_sq))
            
            if len(escape_squares) == 0:
                # Back rank is weak
                return {
                    "pattern": "back_rank_weakness",
                    "setup_moves": [],  # Would need to calculate
                    "moves_to_mate": 2,
                    "weak_square": chess.square_name(king_square)
                }
        
        return None
    
    def _check_smothered_mate_setup(
        self,
        board: chess.Board,
        side: chess.Color
    ) -> Optional[Dict[str, Any]]:
        """Check for smothered mate setup"""
        # Simplified - check if knight can deliver checkmate with king surrounded
        # Can be extended with more sophisticated detection
        return None
    
    def _validate_tactic(
        self,
        board: chess.Board,
        tactic_move: chess.Move,
        tactic_type: str,
        side: chess.Color
    ) -> Dict[str, Any]:
        """
        Core validation: Check if tactic survives opponent's best reply within 2 moves.
        
        Returns:
            {
                "is_valid_tactic": bool,
                "forced_sequence_exists": bool,
                "best_opponent_defense": str or None,
                "net_material_change": float,
                "outcome": "win" | "neutral" | "reject",
                "rejection_reason": str or None
            }
        """
        # Work on a copy so we never corrupt the caller's board state.
        sim = board.copy(stack=False)
        result = {
            "is_valid_tactic": False,
            "forced_sequence_exists": False,
            "best_opponent_defense": None,
            "net_material_change": 0.0,
            "outcome": "reject",
            "rejection_reason": None
        }
        
        try:
            # Step 1: Simulate the tactic move
            sim.turn = side
            if tactic_move not in sim.legal_moves:
                result["rejection_reason"] = "illegal_move"
                return result
            
            # Get material before
            material_before = self._calculate_material(sim, side)
            
            sim.push(tactic_move)
            
            # Step 2: Enumerate opponent's best replies
            opponent = not side
            best_defense = self._find_best_defense(sim, opponent, tactic_move)
            
            if best_defense is None:
                # No legal moves - checkmate!
                result["is_valid_tactic"] = True
                result["forced_sequence_exists"] = True
                result["outcome"] = "win"
                result["net_material_change"] = 999.0  # Checkmate value
                return result

            # Capture SAN for defense in the correct position (before pushing it)
            try:
                best_defense_san = sim.san(best_defense)
            except Exception:
                best_defense_san = None
            
            # Step 3: Resolve capture chain completely
            sim.push(best_defense)
            
            # Resolve capture chain (modifies board, returns moves pushed)
            material_after, chain_moves_pushed = self._resolve_capture_chain(sim, side, max_plies=2)
            
            # Step 4: Evaluate outcome
            net_material = material_after - material_before
            
            result["best_opponent_defense"] = best_defense_san
            result["net_material_change"] = net_material
            
            # Check for checkmate after capture chain
            is_mate = sim.is_checkmate()
            
            # Strict acceptance rules
            if net_material > 0:
                # Wins material
                result["is_valid_tactic"] = True
                result["outcome"] = "win"
                result["forced_sequence_exists"] = True
            elif net_material == 0:
                # Equal trade - reject unless forcing mate
                if is_mate:
                    result["is_valid_tactic"] = True
                    result["outcome"] = "win"
                    result["forced_sequence_exists"] = True
                else:
                    result["rejection_reason"] = "equal_trade"
            else:
                # Loses material - reject
                result["rejection_reason"] = "loses_material"
            
        except Exception as e:
            # On any error, reject conservatively
            result["rejection_reason"] = f"validation_error: {str(e)}"
        
        return result

    # =========================================================================
    # SEE-style proof helpers (capture/recapture only)
    # =========================================================================
    def _see_refute_by_recapture(
        self,
        board: chess.Board,
        tactic_move: chess.Move,
        side: chess.Color
    ) -> Dict[str, Any]:
        """
        Check whether opponent can refute the tactic by immediately capturing the moved piece on its destination square,
        using capture-only minimax (SEE-style) on that square.
        """
        try:
            sim = board.copy(stack=False)
            sim.turn = side
            if tactic_move not in sim.legal_moves:
                return {"refuted": False, "net_if_recaptured": None, "refutation_line": None}

            sim.push(tactic_move)
            dest_sq = tactic_move.to_square

            # If opponent has no capture on destination square, no simple recapture refutation exists.
            opp_caps = [m for m in sim.legal_moves if sim.is_capture(m) and m.to_square == dest_sq]
            if not opp_caps:
                return {"refuted": False, "net_if_recaptured": 0.0, "refutation_line": None}

            net, line = self._see_best_line(
                sim,
                target_sq=dest_sq,
                perspective_side=side,
                plies=0,
                max_plies=self._see_max_plies
            )
            return {"refuted": net < 0, "net_if_recaptured": net, "refutation_line": line}
        except Exception:
            return {"refuted": False, "net_if_recaptured": None, "refutation_line": None}

    def _see_best_line(
        self,
        board: chess.Board,
        target_sq: int,
        perspective_side: chess.Color,
        plies: int,
        max_plies: int
    ) -> Tuple[float, List[str]]:
        """
        Capture-only minimax exchange evaluator on one square.
        Returns (net material for perspective_side, SAN line).
        """
        if plies >= max_plies:
            return 0.0, []

        victim_piece = board.piece_at(target_sq)
        if victim_piece is None:
            return 0.0, []

        legal_caps = [m for m in board.legal_moves if board.is_capture(m) and m.to_square == target_sq]
        if not legal_caps:
            return 0.0, []

        side_to_move = board.turn
        best_val = -1e9 if side_to_move == perspective_side else 1e9
        best_line: List[str] = []

        for move in legal_caps:
            victim = board.piece_at(target_sq)
            if victim is None:
                continue
            cap_val = float(self.piece_values.get(victim.piece_type, 0))
            signed = cap_val if side_to_move == perspective_side else -cap_val

            try:
                san = board.san(move)
            except Exception:
                san = move.uci()

            board.push(move)
            cont_val, cont_line = self._see_best_line(board, target_sq, perspective_side, plies + 1, max_plies)
            board.pop()

            total = signed + cont_val
            if side_to_move == perspective_side:
                if total > best_val:
                    best_val = total
                    best_line = [san] + cont_line
            else:
                if total < best_val:
                    best_val = total
                    best_line = [san] + cont_line

        if best_val == 1e9 or best_val == -1e9:
            return 0.0, []
        return best_val, best_line
    
    def _find_best_defense(
        self,
        board: chess.Board,
        defending_side: chess.Color,
        attacking_move: chess.Move
    ) -> Optional[chess.Move]:
        """
        Find opponent's best defensive reply.
        Prioritizes (danger-scored): captures of attacking piece, zwischenzug checks/counter-threats,
        and high-value captures. This is still heuristic (no engine), but it explicitly models
        intermediate moves instead of assuming recapture is best.
        """
        if board.turn != defending_side:
            return None
        
        legal_moves = list(board.legal_moves)
        if not legal_moves:
            return None

        # Score each defense move with a shallow minimax material component (capture/recapture + checks),
        # then tie-break using danger features. This makes between-move counter-threats (e.g., winning the queen)
        # outrank trivial recaptures.
        best_move = None
        best_score = -1e18
        for move in legal_moves:
            score = self._defense_score_with_shallow_reply(board, move, defending_side, attacking_move)
            if score > best_score:
                best_score = score
                best_move = move

        return best_move

    def _defense_score_with_shallow_reply(
        self,
        board: chess.Board,
        defense_move: chess.Move,
        defending_side: chess.Color,
        attacking_move: chess.Move
    ) -> float:
        """
        Combine:
        - how much the defense reduces the attacker's best immediate gain (captures/checks),
        - plus danger heuristics (checks, multi-attacks, etc.).
        Higher is better for the defender.
        """
        try:
            attacker_side = not defending_side
            material_before = self._calculate_material(board, attacker_side)
            # Danger tie-breaker must be computed on the pre-move board (where defense_move is legal).
            danger_component = self._danger_score_defense_move(board, defense_move, defending_side, attacking_move)

            # Apply defense
            board.push(defense_move)

            # Attacker best reply (bounded): captures + checks + promotions
            replies = []
            for m in board.legal_moves:
                if board.is_capture(m):
                    replies.append(m)
                    continue
                # check moves
                board.push(m)
                gives_check = board.is_check()
                board.pop()
                if gives_check or m.promotion:
                    replies.append(m)

            # If nothing interesting, still consider a small sample of legal moves
            if not replies:
                replies = list(board.legal_moves)[:8]

            # Rank replies by MVV-LVA-ish (captures) and checks
            def _reply_rank(m: chess.Move) -> float:
                r = 0.0
                if board.is_capture(m):
                    vic = board.piece_at(m.to_square)
                    att = board.piece_at(m.from_square)
                    if vic:
                        r += 100.0 * float(self.piece_values.get(vic.piece_type, 0))
                    if vic and att:
                        r += 20.0 * float(self.piece_values.get(vic.piece_type, 0) - self.piece_values.get(att.piece_type, 0))
                # checks
                board.push(m)
                if board.is_checkmate():
                    r += 10000.0
                elif board.is_check():
                    r += 500.0
                board.pop()
                return r

            replies.sort(key=_reply_rank, reverse=True)
            replies = replies[:12]

            best_gain = -1e18
            for rmove in replies:
                board.push(rmove)
                material_after = self._calculate_material(board, attacker_side)
                gain = material_after - material_before
                if gain > best_gain:
                    best_gain = gain
                board.pop()

            # Defender wants to minimize attacker's gain
            material_component = -1000.0 * best_gain

            board.pop()
            return material_component + danger_component
        except Exception:
            try:
                # best effort restore
                board.pop()
            except Exception:
                pass
            return self._danger_score_defense_move(board, defense_move, defending_side, attacking_move)

    def _danger_score_defense_move(
        self,
        board: chess.Board,
        move: chess.Move,
        defending_side: chess.Color,
        attacking_move: chess.Move
    ) -> float:
        """
        Heuristic "zwischenzug-aware" scoring for a defense move.
        Higher score = more dangerous for the attacker (better defense).
        Designed to surface intermediate checks, queen/rook wins, and multi-attacks.
        """
        # Only score moves that are legal in the provided position.
        if move not in board.legal_moves:
            return -1e9

        score = 0.0

        # 1) Capturing the attacker piece on its destination is usually strongest.
        try:
            if board.is_capture(move) and move.to_square == attacking_move.to_square:
                score += 5000.0
        except Exception:
            pass

        # 2) Captures: prefer winning big material (MVV)
        if board.is_capture(move):
            victim = board.piece_at(move.to_square)
            attacker = board.piece_at(move.from_square)
            if victim:
                score += 200.0 * float(self.piece_values.get(victim.piece_type, 0))
            if attacker and victim:
                # Prefer favorable trades (victim > attacker)
                score += 100.0 * float(self.piece_values.get(victim.piece_type, 0) - self.piece_values.get(attacker.piece_type, 0))

        # 3) Zwischenzug checks / mates: huge
        pushed = False
        try:
            board.push(move)
            pushed = True
            if board.is_checkmate():
                score += 10000.0
            elif board.is_check():
                score += 2000.0

            # 4) Multi-attack: after this defense, does the defender attack multiple valuable enemy pieces?
            # (Cheap fork-like signal without full tactic search.)
            mover_side = not board.turn  # side that played `move`
            attacked_valuable = 0
            attacked_value_sum = 0.0
            for sq in chess.SQUARES:
                p = board.piece_at(sq)
                if p and p.color != mover_side:
                    v = float(self.piece_values.get(p.piece_type, 0))
                    if v >= 3 and board.is_attacked_by(mover_side, sq):
                        attacked_valuable += 1
                        attacked_value_sum += v
            if attacked_valuable >= 2:
                score += 300.0 + 75.0 * attacked_value_sum
            elif attacked_valuable == 1:
                score += 50.0 + 25.0 * attacked_value_sum
        finally:
            if pushed:
                try:
                    board.pop()
                except Exception:
                    pass

        return score
    
    def _resolve_capture_chain(
        self,
        board: chess.Board,
        side: chess.Color,
        max_plies: int = 2
    ) -> Tuple[float, int]:
        """
        Resolve forced capture sequences completely.
        Returns (final material balance, number of moves pushed).
        Caller must pop the returned number of moves to restore board state.
        """
        material = self._calculate_material(board, side)
        plies_played = 0
        
        while plies_played < max_plies:
            # Check if there's a forced capture
            forced_capture = self._find_forced_capture(board)
            
            if forced_capture is None:
                break
            
            # Play forced capture
            board.push(forced_capture)
            plies_played += 1
            
            # Update material
            material = self._calculate_material(board, side)
            
            # Check if opponent has forced recapture
            if plies_played < max_plies:
                opponent_forced = self._find_forced_capture(board)
                if opponent_forced:
                    board.push(opponent_forced)
                    plies_played += 1
                    material = self._calculate_material(board, side)
                else:
                    break
        
        return material, plies_played
    
    def _find_forced_capture(
        self,
        board: chess.Board
    ) -> Optional[chess.Move]:
        """
        Find if there's a forced capture (check or only capture available).
        """
        legal_moves = list(board.legal_moves)
        if not legal_moves:
            return None
        
        # If in check, captures are more likely to be forced
        in_check = board.is_check()
        
        captures = [m for m in legal_moves if board.is_capture(m)]
        
        if in_check:
            # In check - prioritize captures
            if captures:
                return captures[0]
            return legal_moves[0]  # Any legal move
        
        # Not in check - only return capture if it's clearly favorable
        if len(captures) == 1 and len(legal_moves) <= 3:
            # Only one capture and few moves - likely forced
            return captures[0]
        
        # Check for captures that win material
        for move in captures:
            attacker = board.piece_at(move.from_square)
            victim = board.piece_at(move.to_square)
            if attacker and victim:
                if self.piece_values.get(victim.piece_type, 0) > self.piece_values.get(attacker.piece_type, 0):
                    return move
        
        return None
    
    def _calculate_material(
        self,
        board: chess.Board,
        side: chess.Color
    ) -> float:
        """Calculate material balance for given side (in pawns)"""
        material = 0.0
        
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if piece and piece.color == side:
                material += self.piece_values.get(piece.piece_type, 0)
            elif piece and piece.color != side:
                material -= self.piece_values.get(piece.piece_type, 0)
        
        return material
    
    def _estimate_material_gain(
        self,
        board: chess.Board,
        move_san: str
    ) -> float:
        """Estimate material gain from a move (simplified)"""
        try:
            move = board.parse_san(move_san)
            if board.is_capture(move):
                attacker = board.piece_at(move.from_square)
                victim = board.piece_at(move.to_square)
                if attacker and victim:
                    return self.piece_values.get(victim.piece_type, 0) - self.piece_values.get(attacker.piece_type, 0)
        except:
            pass
        return 0.0


