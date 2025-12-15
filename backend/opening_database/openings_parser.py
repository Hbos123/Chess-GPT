import csv
import chess
from pathlib import Path
from typing import Dict, List, Optional
import logging
from .config import normalize_fen, MAX_PLY_DEPTH

logger = logging.getLogger(__name__)

class OpeningsParser:
    """Parse Lichess openings.tsv into FEN-based tree"""
    
    def __init__(self):
        self.eco_entries: List[EcoEntry] = []
        self.position_nodes: Dict[str, PositionNode] = {}
        
    def parse_tsv(self, tsv_path: Path):
        """Parse openings.tsv file
        
        TSV columns: eco, name, pgn, uci, epd
        """
        logger.info(f"Parsing {tsv_path}...")
        
        with open(tsv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter='\t')
            
            for row in reader:
                eco = row['eco']
                name = row['name']
                pgn_moves = row['pgn']
                epd = row['epd']
                
                entry = EcoEntry(eco, name, pgn_moves, epd)
                self.eco_entries.append(entry)
                
                # Build position tree from this opening line
                self._build_tree_from_line(entry)
        
        logger.info(f"Parsed {len(self.eco_entries)} ECO entries")
        logger.info(f"Created {len(self.position_nodes)} unique position nodes")
    
    def _build_tree_from_line(self, entry: 'EcoEntry'):
        """Walk through opening moves and create/update position nodes"""
        board = chess.Board()
        parent_fen = None
        
        # Parse PGN moves (e.g., "1. e4 e5 2. Nf3")
        try:
            # Remove move numbers
            moves_str = entry.pgn_moves.replace('.', ' ')
            move_tokens = moves_str.split()
            
            for ply, san in enumerate(move_tokens):
                if ply >= MAX_PLY_DEPTH:
                    break
                
                # Skip if it's just whitespace or move number
                if not san or san.isdigit():
                    continue
                
                # Get current FEN before making move
                fen = normalize_fen(board.fen())
                
                # Create or get position node
                if fen not in self.position_nodes:
                    self.position_nodes[fen] = PositionNode(
                        fen=fen,
                        parent_fen=parent_fen,
                        ply_from_start=ply
                    )
                
                node = self.position_nodes[fen]
                
                # Track move from parent
                try:
                    move = board.parse_san(san)
                    uci = move.uci()
                    
                    if parent_fen and parent_fen in self.position_nodes:
                        parent = self.position_nodes[parent_fen]
                        parent.add_child_move(san, uci, fen)
                    
                    board.push(move)
                    parent_fen = fen
                    
                except Exception as e:
                    logger.warning(f"Failed to parse move '{san}' in {entry.name}: {e}")
                    break
            
            # Mark final position with ECO code and opening name
            final_fen = normalize_fen(board.fen())
            if final_fen in self.position_nodes:
                node = self.position_nodes[final_fen]
                node.eco = entry.eco
                node.opening_name = entry.name
                node.is_named = True
                node.canonical_pgn = entry.pgn_moves
                
        except Exception as e:
            logger.error(f"Failed to build tree for {entry.name}: {e}")

class EcoEntry:
    """Single ECO opening entry from TSV"""
    def __init__(self, eco: str, name: str, pgn_moves: str, epd: str):
        self.eco = eco
        self.name = name
        self.pgn_moves = pgn_moves
        self.epd = epd

class PositionNode:
    """Position in the opening tree"""
    def __init__(self, fen: str, parent_fen: Optional[str], ply_from_start: int):
        self.fen = fen
        self.parent_fen = parent_fen
        self.ply_from_start = ply_from_start
        
        # Opening data
        self.eco: Optional[str] = None
        self.opening_name: Optional[str] = None
        self.is_named = False
        self.canonical_pgn: Optional[str] = None
        
        # Child moves from this position
        self.child_moves: List['ChildMove'] = []
        
        # Evaluation data (populated by enricher)
        self.eval_cp: Optional[float] = None
        self.eval_depth: Optional[int] = None
        self.best_move_san: Optional[str] = None
        self.best_move_uci: Optional[str] = None
        self.second_best_cp: Optional[float] = None
        
    def add_child_move(self, san: str, uci: str, child_fen: str):
        """Track a known continuation from this position"""
        # Check if already exists
        for move in self.child_moves:
            if move.uci == uci:
                return
        
        self.child_moves.append(ChildMove(san, uci, child_fen))

class ChildMove:
    """A move leading to a child position"""
    def __init__(self, san: str, uci: str, child_fen: str):
        self.san = san
        self.uci = uci
        self.child_fen = child_fen



