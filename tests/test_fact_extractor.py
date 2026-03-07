import os
import sys
import json
from dotenv import load_dotenv

# Ensure project root is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.agents.fact_extractor import FactExtractor
from src.models.chunking import LDU, ChunkType
from src.models.base import BoundingBox

def test_fact_extraction():
    load_dotenv()
    print("--- Testing Fact Extractor ---")
    
    extractor = FactExtractor()
    
    # Create a sample chunk representing a budget table row
    sample_chunk = LDU(
        id="ldu_test_1",
        content="Commercial Bank of Ethiopia (CBE) - Capital Adequacy Ratio: 12.5% as of Dec 2023. Total Assets: 1.2 Trillion ETB.",
        chunk_type=ChunkType.TEXT,
        page_refs=[1],
        bbox=BoundingBox(x0=50.0, y0=100.0, x1=400.0, y1=150.0),
        content_hash="test_hash_1",
        token_count=25
    )
    
    print(f"Feeding chunk: '{sample_chunk.content}'")
    
    try:
        facts = extractor.extract_facts("test_doc_ext", [sample_chunk])
        
        print(f"\nExtracted {len(facts)} facts:")
        for i, fact in enumerate(facts):
            print(f"Fact {i+1}:")
            print(f"  Entity: {fact.entity}")
            print(f"  Attribute: {fact.attribute}")
            print(f"  Value: {fact.value}")
            print(f"  Unit: {fact.unit}")
            print(f"  Page: {fact.page_number}")
            print("-" * 20)
            
        if len(facts) > 0:
            print("\n✓ Fact Extraction Logic Verified!")
        else:
            print("\n✗ No facts extracted. Check LLM prompt or connectivity.")
            
    except Exception as e:
        print(f"\n✗ Error during extraction: {str(e)}")

if __name__ == "__main__":
    test_fact_extraction()
