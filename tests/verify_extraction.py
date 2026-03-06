import os
import yaml
import json
from src.agents.triage import TriageAgent
from src.agents.extractor import ExtractionRouter
from src.models.triage import DocumentProfile

def verify_extraction_pipeline():
    # Load rules
    rules_path = "rubric/extraction_rules.yaml"
    with open(rules_path, "r") as f:
        rules = yaml.safe_load(f)
    
    triage_agent = TriageAgent(extraction_rules=rules)
    extractor_router = ExtractionRouter(rules=rules.get("escalation", {}))
    
    # Sample PDF (from data folder as per previous step)
    # pdf_path = "data/Security_Vulnerability_Disclosure_Standard_Procedure_1.pdf"
    pdf_path = "data/2013-E.C-Assigned-regular-budget-and-expense.pdf"
    if not os.path.exists(pdf_path):
        print(f"Error: {pdf_path} not found.")
        return

    print(f"Step 1: Triaging {pdf_path}...")
    profile = triage_agent.triage_document(pdf_path)
    print(f"✓ Document profiled: {profile.overall_origin_type}")
    
    # Extract all pages for verification
    for page_prof in profile.pages:
        print(f"Step 2: Extracting page {page_prof.page_number}...")
        result = extractor_router.extract_page_with_escalation(
            pdf_path, 
            page_prof.page_number, 
            profile.document_id, 
            page_prof.estimated_extraction_cost
        )
    
        print(f"✓ Extraction result: strategy={result.strategy_used}, confidence={result.confidence_score}")
        if result.error:
            print(f"⚠ Extraction error: {result.error}")
        
        print("\n--- Extracted JSON Content ---")
        print(result.content.model_dump_json(indent=2))
        print("------------------------------\n")

        # output the extracted content to a file jsonl
        with open(f"extracted/{profile.document_id}.jsonl", "a") as f:
            f.write(json.dumps(result.content.model_dump_json()) + "\n")

        print(f"✓ Text blocks extracted: {len(result.content.text_blocks)}")
        print(f"✓ Tables extracted: {len(result.content.tables)}")
        
        # Check ledger
        if os.path.exists(".refinery/extraction_ledger.jsonl"):
            print("✓ Extraction ledger updated")

if __name__ == "__main__":
    try:
        # Load .env
        from dotenv import load_dotenv
        load_dotenv()
        
        # Set PYTHONPATH to current dir
        import sys
        sys.path.append(os.getcwd())
        verify_extraction_pipeline()
    except Exception as e:
        import traceback
        print(f"Verification failed: {e}")
        traceback.print_exc()
