import os
import argparse
from src.agents.triage import TriageAgent
from src.agents.extractor import ExtractionRouter
from src.agents.chunker import ChunkingEngine
from src.agents.indexer import NavigationAgent
from src.utils.db_utils import init_db, insert_facts
from src.utils.vector_utils import VectorStoreIngestor
from src.utils.logging_utils import get_logger

# Load environment variables if needed
import dotenv
dotenv.load_dotenv()

logger = get_logger("refinery_main")

def run_pipeline(file_path: str):
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        return

    doc_id = os.path.basename(file_path)
    logger.info(f"--- Starting Refinery Pipeline for {doc_id} ---")

    # 0. Initialize DB
    init_db()

    # 1. Triage
    triage_agent = TriageAgent()
    profile = triage_agent.triage_document(file_path)
    logger.info(f"Triage Complete. Profile: {profile.overall_origin_type} | {profile.overall_layout_complexity}")
    
    # Save profile to artifact directory
    profile_dir = ".refinery/profiles"
    os.makedirs(profile_dir, exist_ok=True)
    profile_path = os.path.join(profile_dir, f"{doc_id}.json")
    with open(profile_path, "w") as f:
        f.write(profile.model_dump_json(indent=2))
    logger.info(f"Document profile saved to {profile_path}")

    # 2. Extraction
    router = ExtractionRouter()
    # For speed in verification, limit to first 5 pages
    extraction_results = router.extract_document(file_path, profile, page_range=(1, 5))
    logger.info(f"Extraction Complete. Extracted {len(extraction_results)} pages.")

    # 3. Chunking
    chunker = ChunkingEngine()
    # ExtractionRouter returns List[ExtractionResult], ChunkingEngine expects List[ExtractedDocument]
    extracted_docs = [res.content for res in extraction_results if not res.error]
    chunks = chunker.chunk_document(doc_id, extracted_docs)
    logger.info(f"Chunking Complete. Generated {len(chunks)} LDUs.")

    # 4. Indexing (PageIndex)
    indexer = NavigationAgent()
    page_index = indexer.build_tree(doc_id, chunks)
    logger.info(f"Indexing Complete. PageIndex built for {doc_id}.")

    # 5. Ingestion
    if chunks:
        ingestor = VectorStoreIngestor()
        ingestor.ingest_chunks(chunks)
        logger.info(f"Ingestion Complete.")
    else:
        logger.warning(f"No chunks generated for {doc_id}. Skipping ingestion.")

    logger.info(f"--- Pipeline Finished for {doc_id} ---")
    return profile, chunks, page_index

def main():
    parser = argparse.ArgumentParser(description="Document Intelligence Refinery Pipeline")
    parser.add_argument("--file", type=str, help="Path to the PDF file to process")
    args = parser.parse_args()

    if args.file:
        run_pipeline(args.file)
    else:
        # Default test file for verification
        test_file = "data/2021_Audited_Financial_Statement_Report.pdf"
        if os.path.exists(test_file):
            run_pipeline(test_file)
        else:
            logger.error("No file provided and default test file missing.")

if __name__ == "__main__":
    main()
