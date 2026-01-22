import logging
from typing import Dict, List
from .config import CRITICAL_CP_LOSS_THRESHOLD
from .openings_parser import PositionNode

logger = logging.getLogger(__name__)

class CriticalDetector:
    """Identify critical positions"""
    
    def detect_critical_positions(self, positions: Dict[str, PositionNode]) -> List[str]:
        """Find positions where 2nd best move loses significantly"""
        critical_fens = []
        
        for fen, node in positions.items():
            if node.eval_cp is None or node.second_best_cp is None:
                continue
            
            cp_loss = abs(node.eval_cp - node.second_best_cp)
            
            if cp_loss >= CRITICAL_CP_LOSS_THRESHOLD:
                critical_fens.append(fen)
                logger.debug(
                    f"Critical: {node.opening_name or fen[:30]}... "
                    f"({cp_loss}cp loss if not playing {node.best_move_san})"
                )
        
        logger.info(f"Found {len(critical_fens)} critical positions")
        return critical_fens
    
    def generate_note(self, node: PositionNode) -> dict:
        """Generate note for critical position"""
        cp_loss = abs(node.eval_cp - node.second_best_cp)
        
        title = f"Critical: {cp_loss}cp swing"
        if node.opening_name:
            title = f"{node.opening_name} - {title}"
        
        return {
            'note_type': 'auto',
            'title': title,
            'body': f'Only {node.best_move_san} maintains the evaluation. Other moves lose {cp_loss}+ centipawns.',
            'motifs': ['critical_choice', 'accuracy_required'],
            'license': 'CC0'  # Derived from CC0 source
        }



