import json
import os
import sys
import yaml
from typing import List

# Ensure project root is in path
sys.path.append(os.getcwd())

from src.agents.triage import TriageAgent
from src.agents.extractor import ExtractionRouter
from src.agents.chunker import ChunkingEngine
from src.agents.indexer import NavigationAgent
from src.agents.retrieval import RetrievalAgent
from src.models.extraction import ExtractedDocument

def verify_full_pipeline():
    # Configuration
    rules_path = "rubric/extraction_rules.yaml"
    if not os.path.exists(rules_path):
        # Try parent dir if running from tests/
        rules_path = os.path.join("..", rules_path)
        
    with open(rules_path, "r") as f:
        rules = yaml.safe_load(f)

    file_path = "data/2021_Audited_Financial_Statement_Report.pdf"
    document_id = "2021_Audited_Financial_Statement_Report"
    
    if not os.path.exists(file_path):
        file_path = os.path.join("..", file_path)

    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return

    print(f"=== Starting Full Pipeline for: {document_id} ===")

    # --- Stage 1: Triage ---
    print("\n--- Stage 1: Triage ---")
    triage_agent = TriageAgent(extraction_rules=rules.get("strategy_a"))
    doc_profile = triage_agent.triage_document(file_path, document_id)
    print(f"Origin: {doc_profile.overall_origin_type.value}")
    print(f"Complexity: {doc_profile.overall_layout_complexity.value}")
    print(f"Estimated Cost Tier: {doc_profile.overall_estimated_cost.value}")

    # --- Stage 2: Extraction ---
    print("\n--- Stage 2: Extraction ---")
    # Note: ExtractionRouter expects 'escalation' rules which contain strategy-specific overrides
    extractor_router = ExtractionRouter(rules=rules.get("escalation", {}))
    # extract_document handles the page loop and escalation logic, limiting to 3 pages for speed
    extraction_results = extractor_router.extract_document(file_path, doc_profile, page_range=(1, 3))
    
    successful_docs = []
    for res in extraction_results:
        if not res.error:
            successful_docs.append(res.content)
        else:
            print(f"Warning: Page {res.page_number} failed extraction: {res.error}")

    print(f"Successfully extracted {len(successful_docs)} pages.")

    # --- Stage 3: Chunking ---
    print("\n--- Stage 3: Chunking ---")
    chunk_engine = ChunkingEngine()
    chunks = chunk_engine.chunk_document(document_id, successful_docs)
    print(f"Generated {len(chunks)} LDUs (semantically coherent chunks).")

    # --- Stage 4: Page Index & NER ---
    print("\n--- Stage 4: Page Index & NER ---")
    # NavigationAgent uses Ollama for summaries and NER
    ollama_host = os.getenv("OLLAMA_HOST", "http://ollama.com")
    nav_agent = NavigationAgent(ollama_host=ollama_host, model="qwen3-vl:235b-instruct")
    page_index = nav_agent.build_tree(document_id, chunks)
    
    # Print tree structure
    def print_node(node, indent=0):
        print("  " * indent + f"• {node.title} (Pages {node.page_start}-{node.page_end})")
        print("  " * indent + f"  Summary: {node.summary}")
        if node.key_entities:
            print("  " * indent + f"  Entities: {', '.join(node.key_entities)}")
        for child in node.child_sections:
            print_node(child, indent + 1)

    print_node(page_index.root)

    # --- Stage 5: Vector Ingestion & Hybrid Search ---
    print("\n--- Stage 5: Vector Ingestion & Hybrid Search ---")
    retrieval_agent = RetrievalAgent()
    # Reset collection for clean test
    try:
        retrieval_agent.client.delete_collection("document_chunks")
    except:
        pass
    retrieval_agent.collection = retrieval_agent.client.create_collection("document_chunks", metadata={"hnsw:space": "cosine"})
    
    retrieval_agent.ingest_ldus(chunks)
    print(f"Ingested {len(chunks)} unique LDUs into ChromaDB.")

    # Test Hybrid Query
    query = "What is the net profit for the year 2021?"
    print(f"\nSearching for: \"{query}\"")
    
    # Step A: Page Index Query (Narrow down sections)
    relevant_sections = nav_agent.query_index(page_index, query)
    section_titles = [n.title for n in relevant_sections]
    print(f"Top 3 sections from PageIndex: {section_titles}")

    # Step B: Filtered Vector Search
    results = retrieval_agent.search(query, top_k=3, section_filter=section_titles)
    
    print("\n--- Top Search Results (Augmented by PageIndex) ---")
    for i, doc in enumerate(results['documents'][0]):
        meta = results['metadatas'][0][i]
        print(f"[{i+1}] Section: {meta['section']} | Page: {meta['pages']}")
        print(f"    Content: {doc[:200]}...")
        print("-" * 40)

    print("\n=== Full Pipeline Verification Completed Successfully ===")

if __name__ == "__main__":
    verify_full_pipeline()
