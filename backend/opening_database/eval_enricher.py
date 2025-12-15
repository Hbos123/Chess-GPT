import json
import io
import zstandard as zstd
from pathlib import Path
from typing import Dict
import chess
import logging
from .config import normalize_fen, MIN_EVAL_DEPTH
from .openings_parser import PositionNode

logger = logging.getLogger(__name__)

class EvalEnricher:
    """Enrich positions with Stockfish evaluations from Lichess DB"""
    
    def __init__(self, eval_db_path: Path):
        self.eval_db_path = eval_db_path
        self.eval_index: Dict[str, dict] = {}
    
    def load_eval_index(self, positions: Dict[str, PositionNode]):
        """Load only the evals we need (selective loading)
        
        Lichess eval DB is huge. Only load FENs we actually have in our tree.
        """
        target_fens = set(positions.keys())
        logger.info(f"Loading evals for {len(target_fens)} positions...")
        
        found_count = 0
        
        with open(self.eval_db_path, 'rb') as f:
            dctx = zstd.ZstdDecompressor()
            with dctx.stream_reader(f) as reader:
                text_stream = io.TextIOWrapper(reader, encoding='utf-8')
                
                for line_num, line in enumerate(text_stream):
                    if line_num % 1_000_000 == 0:
                        logger.info(f"Scanned {line_num/1_000_000:.1f}M eval entries, found {found_count}...")
                    
                    try:
                        eval_data = json.loads(line)
                        fen = normalize_fen(eval_data['fen'])
                        
                        if fen in target_fens:
                            self.eval_index[fen] = eval_data
                            found_count += 1
                            
                            # Early exit if we found everything
                            if found_count >= len(target_fens):
                                logger.info("Found all target positions, stopping scan")
                                break
                                
                    except Exception as e:
                        continue
        
        logger.info(f"Loaded {len(self.eval_index)} evals ({found_count}/{len(target_fens)} positions matched)")
    
    def enrich_positions(self, positions: Dict[str, PositionNode]):
        """Add evaluation data to position nodes"""
        enriched = 0
        
        for fen, node in positions.items():
            if fen not in self.eval_index:
                continue
            
            eval_data = self.eval_index[fen]
            
            # Quality check
            if eval_data.get('depth', 0) < MIN_EVAL_DEPTH:
                continue
            
            pvs = eval_data.get('pvs', [])
            if len(pvs) == 0:
                continue
            
            # Best move
            best_pv = pvs[0]
            node.eval_cp = best_pv.get('cp')
            node.eval_depth = eval_data['depth']
            
            # Extract best move
            best_moves = best_pv.get('moves', '').split()
            if best_moves:
                node.best_move_uci = best_moves[0]
                
                # Convert UCI to SAN
                try:
                    board = chess.Board(fen)
                    move = chess.Move.from_uci(best_moves[0])
                    node.best_move_san = board.san(move)
                except:
                    pass
            
            # Second best for critical detection
            if len(pvs) > 1:
                node.second_best_cp = pvs[1].get('cp')
            
            enriched += 1
        
        logger.info(f"Enriched {enriched}/{len(positions)} positions with evaluations")



