import os
import yaml
import json
from src.agents.triage import TriageAgent

def generate_sample_profile():
    # Load rules
    rules_path = "rubric/extraction_rules.yaml"
    with open(rules_path, "r") as f:
        rules = yaml.safe_load(f)
    
    agent = TriageAgent(extraction_rules=rules)
    
    # Target PDF
    pdf_path = "data/Consumer Price Index June 2025.pdf"
    if not os.path.exists(pdf_path):
        print(f"Error: {pdf_path} not found.")
        return

    print(f"Triaging {pdf_path}...")
    profile = agent.triage_document(pdf_path)
    
    # Save to .refinery/profiles/
    output_dir = ".refinery/profiles"
    os.makedirs(output_dir, exist_ok=True)
    
    doc_id = profile.document_id
    output_path = os.path.join(output_dir, f"{doc_id}.json")
    
    with open(output_path, "w") as f:
        f.write(profile.model_dump_json(indent=2))
        
    print(f"✓ Profile saved to {output_path}")

if __name__ == "__main__":
    generate_sample_profile()
