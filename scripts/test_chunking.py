import json
import os
import sys

# Ensure project root is in path
sys.path.append(os.getcwd())

from src.models.extraction import ExtractedDocument
from src.agents.chunking import ChunkingEngine, ChunkValidator

def test_chunking():
    # Load extracted data
    jsonl_path = "g:/projects/document-intelligence-refinery/docs/extracted/Security_Vulnerability_Disclosure_Standard_Procedure_1.pdf.jsonl"
    if not os.path.exists(jsonl_path):
        print(f"File not found: {jsonl_path}")
        return

    pages = []
    with open(jsonl_path, "r") as f:
        # Based on verify_extraction: f.write(json.dumps(result.content.model_dump_json()) + "\n")
        # Line is a JSON string of a JSON string?
        # Let's try simple deserialization
        for i, line in enumerate(f):
            try:
                # The file has: "{\"document_id\":...}"
                # So json.loads(line) will give the actual json string
                # and json.loads that will give the dict.
                data_str = json.loads(line)
                data_dict = json.loads(data_str)
                pages.append(ExtractedDocument(**data_dict))
            except Exception as e:
                print(f"Error parsing line {i+1}: {e}")

    engine = ChunkingEngine()
    chunks = engine.chunk_document("Security_PD_1", pages)
    
    print(f"Total LDUs generated: {len(chunks)}\n")
    
    # Check for List LDU
    list_ldus = [c for c in chunks if c.chunk_type == "list"]
    print(f"Grouped List LDUs: {len(list_ldus)}")
    
    # Check for Tables
    table_ldus = [c for c in chunks if c.chunk_type == "table"]
    print(f"Table LDUs: {len(table_ldus)}")

    # Check for Section Headers tracked
    sections = set([c.parent_section for c in chunks if c.parent_section])
    print(f"Sections detected: {sections}")

    # Inspect a few chunks
    for i, ldu in enumerate(chunks[:15]):
        print(f"LDU {i} | Type: {ldu.chunk_type:8} | Section: {str(ldu.parent_section):15} | Snippet: {ldu.content[:60]}...")

    # Run Validator
    validator = ChunkValidator()
    errors = validator.validate(chunks)
    if errors:
        print("\n--- Validation Errors ---")
        for e in errors:
            print(f"[-] {e}")
    else:
        print("\n[+] All chunking rules validated successfully!")

if __name__ == "__main__":
    test_chunking()
