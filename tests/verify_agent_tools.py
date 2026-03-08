import os
import sys
import yaml
from dotenv import load_dotenv
from typing import List

# Ensure project root is in path
sys.path.append(os.getcwd())

from src.agents.triage import TriageAgent
from src.agents.extractor import ExtractionRouter
from src.agents.chunking import ChunkingEngine
from src.agents.navigation import NavigationAgent
from src.agents.retrieval import RetrievalAgent
from src.agents.fact_extractor import FactExtractor
from src.agents.assistant import RefineryAssistant
from src.agents.audit_mode import AuditMode
from src.utils.db_utils import init_db

def verify_agent_pipeline():
    # 0. Setup
    load_dotenv()
    init_db()
    
    rules_path = "g:/projects/document-intelligence-refinery/rubric/extraction_rules.yaml"
    with open(rules_path, "r") as f:
        rules = yaml.safe_load(f)

    file_path = "g:/projects/document-intelligence-refinery/data/2021_Audited_Financial_Statement_Report.pdf"
    document_id = "2021_Audited_Financial_Statement_Report"
    
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return

    print(f"=== Running Agentic Pipeline for: {document_id} ===")

    # --- Step 1: Standard Pipeline (Triage -> Extraction -> Chunking -> Navigation) ---
    print("\n[1] Running Base Pipeline...")
    triage_agent = TriageAgent(extraction_rules=rules.get("strategy_a"))
    doc_profile = triage_agent.triage_document(file_path, document_id)
    
    print("\n--- Output: Triage ---")
    print(doc_profile.model_dump_json(indent=2))
    
    extractor_router = ExtractionRouter(rules=rules.get("escalation", {}))
    # For speed in testing, we'll only process the first 3 pages
    extraction_results = extractor_router.extract_document(file_path, doc_profile, page_range=(1, 3))
    successful_docs = [res.content for res in extraction_results if not res.error]
    print("\n--- Output: Extraction ---")
    for res in successful_docs:
        print(f"Page {res.page_number}: {len(res.text_blocks)} text blocks, {len(res.tables)} tables, {len(res.figures)} figures")
    
    chunk_engine = ChunkingEngine()
    chunks = chunk_engine.chunk_document(document_id, successful_docs)
    print("\n--- Output: Chunking ---")
    print(f"Total LDUs: {len(chunks)}")
    for i, c in enumerate(chunks[:2]):
        print(f"LDU {i+1}: {c.chunk_type.value} - '{c.content[:100]}...'")
    
    nav_agent = NavigationAgent(model="qwen3-vl:235b-instruct")
    page_index = nav_agent.build_tree(document_id, chunks)
    # output page index
    print("\n--- Output: Navigation ---")
    print(page_index.model_dump_json(indent=2))
    
    ret_agent = RetrievalAgent()
    ret_agent.ingest_ldus(chunks)

    # --- Step 2: Fact Extraction ---
    print("\n[2] Extracting Structured Facts...")
    fact_extractor = FactExtractor(model="qwen3-vl:235b-instruct")
    facts = fact_extractor.extract_facts(document_id, chunks)
    print(f"Extracted {len(facts)} structured facts to SQLite.")
    print("\n--- Output: Fact Extraction ---")
    for f in facts:
        print(f"Entity: {f.entity}, Attribute: {f.attribute}, Value: {f.value} {f.unit} (Page {f.page_number})")

    # --- Step 3: Agentic Interface ---
    print("\n[3] Testing Assistant Agent...")
    assistant = RefineryAssistant(nav_agent, ret_agent, page_index, model="qwen3-vl:235b-instruct")
    
    query = "What is the cash and cash equivalents in 30 June 2021?"
    print(f"Query: {query}")
    answer = assistant.run(query)
    print(f"Assistant Answer:\n{answer}")

    # --- Step 4: Audit Mode ---
    print("\n[4] Testing Audit Mode...")
    auditor = AuditMode(assistant)
    claim = "Cash and cash equivalents were 15,194,080 thousand Birr."
    print(f"Claim to Verify: {claim}")
    verification = auditor.verify_claim(claim)
    print("\nAudit Result:")
    print(f"Status: {verification['status']}")
    print(f"Reasoning: {verification['reasoning']}")
    for cit in verification.get('citations', []):
        print(f" - Citation: Page {cit['page']}, BBox {cit['bbox']}")

    print("\n=== Agentic Verification Completed ===")

if __name__ == "__main__":
    verify_agent_pipeline()
