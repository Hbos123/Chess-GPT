from supabase import create_client, Client
from typing import Dict, List
import logging
from .config import SUPABASE_URL, SUPABASE_KEY, BATCH_SIZE
from .openings_parser import PositionNode, EcoEntry

logger = logging.getLogger(__name__)

class SupabaseImporter:
    """Bulk import to Supabase"""
    
    def __init__(self):
        self.client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    def import_eco_codes(self, eco_entries: List[EcoEntry]):
        """Import canonical ECO entries to openings table"""
        logger.info(f"Importing {len(eco_entries)} ECO codes...")
        
        batch = []
        for entry in eco_entries:
            batch.append({
                'eco': entry.eco,
                'name': entry.name,
                'epd': entry.epd,
                'canonical_pgn': entry.pgn_moves,
                'source': 'CC0:lichess-openings'
            })
            
            if len(batch) >= BATCH_SIZE:
                self._upsert('openings', batch, 'eco')
                batch = []
        
        if batch:
            self._upsert('openings', batch, 'eco')
        
        logger.info("ECO codes imported")
    
    def import_position_nodes(self, positions: Dict[str, PositionNode]):
        """Import opening_nodes table"""
        logger.info(f"Importing {len(positions)} position nodes...")
        
        batch = []
        for fen, node in positions.items():
            batch.append({
                'fen': fen,
                'parent_fen': node.parent_fen,
                'eco': node.eco,
                'ply_from_start': node.ply_from_start,
                'is_named': node.is_named,
                'aliases': [node.opening_name] if node.opening_name else [],
                'source': 'CC0:lichess-openings'
            })
            
            if len(batch) >= BATCH_SIZE:
                self._upsert('opening_nodes', batch, 'fen')
                batch = []
        
        if batch:
            self._upsert('opening_nodes', batch, 'fen')
        
        logger.info("Position nodes imported")
    
    def import_critical_notes(self, positions: Dict[str, PositionNode], 
                            critical_fens: List[str], detector):
        """Import opening_notes for critical positions"""
        logger.info(f"Importing {len(critical_fens)} critical notes...")
        
        batch = []
        for fen in critical_fens:
            node = positions[fen]
            note = detector.generate_note(node)
            
            batch.append({
                'fen': fen,
                **note
            })
            
            if len(batch) >= BATCH_SIZE:
                self._upsert('opening_notes', batch, 'fen')
                batch = []
        
        if batch:
            self._upsert('opening_notes', batch, 'fen')
        
        logger.info("Critical notes imported")
    
    def _upsert(self, table: str, rows: List[dict], conflict_column: str):
        """Upsert batch with conflict handling"""
        try:
            self.client.table(table).upsert(rows, on_conflict=conflict_column).execute()
            logger.debug(f"Upserted {len(rows)} rows to {table}")
        except Exception as e:
            logger.error(f"Failed to upsert to {table}: {e}")



