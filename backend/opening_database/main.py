import logging
from .downloader import LichessDownloader
from .openings_parser import OpeningsParser
from .eval_enricher import EvalEnricher
from .critical_detector import CriticalDetector
from .supabase_importer import SupabaseImporter

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Pipeline: Download → Parse → Enrich → Detect → Import"""
    
    # Step 1: Download source data
    logger.info("="*60)
    logger.info("STEP 1: Downloading source data")
    logger.info("="*60)
    
    downloader = LichessDownloader()
    tsv_path = downloader.download_openings_data()
    eval_path = downloader.download_eval_database()
    
    # Step 2: Parse openings into tree
    logger.info("="*60)
    logger.info("STEP 2: Parsing openings into FEN tree")
    logger.info("="*60)
    
    parser = OpeningsParser()
    parser.parse_tsv(tsv_path)
    
    # Step 3: Enrich with evaluations
    logger.info("="*60)
    logger.info("STEP 3: Enriching with Stockfish evaluations")
    logger.info("="*60)
    
    enricher = EvalEnricher(eval_path)
    enricher.load_eval_index(parser.position_nodes)
    enricher.enrich_positions(parser.position_nodes)
    
    # Step 4: Detect critical positions
    logger.info("="*60)
    logger.info("STEP 4: Detecting critical positions")
    logger.info("="*60)
    
    detector = CriticalDetector()
    critical_fens = detector.detect_critical_positions(parser.position_nodes)
    
    # Step 5: Import to Supabase
    logger.info("="*60)
    logger.info("STEP 5: Importing to Supabase")
    logger.info("="*60)
    
    importer = SupabaseImporter()
    importer.import_eco_codes(parser.eco_entries)
    importer.import_position_nodes(parser.position_nodes)
    importer.import_critical_notes(parser.position_nodes, critical_fens, detector)
    
    # Summary
    logger.info("="*60)
    logger.info("PIPELINE COMPLETE")
    logger.info(f"  ECO codes: {len(parser.eco_entries)}")
    logger.info(f"  Position nodes: {len(parser.position_nodes)}")
    logger.info(f"  Critical positions: {len(critical_fens)}")
    logger.info(f"  Source: CC0 Lichess chess-openings")
    logger.info("="*60)

if __name__ == '__main__':
    main()



