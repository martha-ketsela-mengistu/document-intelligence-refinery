import os
import json
from dotenv import load_dotenv
from src.strategies.vision_extractor import VisionExtractor

def test_vision_extraction():
    load_dotenv()
    
    # We'll use a placeholder image if the one in VisionExtractor works
    # Actually, let's just use the extractor directly on a page
    extractor = VisionExtractor()
    
    print(f"Testing Vision Extraction with Cloud Ollama...")
    print(f"URL: {extractor.rules['ollama_url']}")
    print(f"API Key present: {'Yes' if extractor.api_key else 'No'}")
    
    pdf_path = "data/Security_Vulnerability_Disclosure_Standard_Procedure_1.pdf"
    if not os.path.exists(pdf_path):
        print(f"Error: {pdf_path} not found.")
        return

    # Extract page 1 using Vision directly
    print("Extracting page 1 using Vision strategy...")
    result = extractor.extract_page(pdf_path, 1)
    
    if result.error:
        print(f"Error during extraction: {result.error}")
        return

    print("\n✓ Extraction successful!")
    print(f"Strategy: {result.strategy_used}")
    print(f"Confidence: {result.confidence_score}")
    
    print("\n--- Extracted JSON Content ---")
    print(result.content.model_dump_json(indent=2))
    print("------------------------------\n")

if __name__ == "__main__":
    import sys
    sys.path.append(os.getcwd())
    test_vision_extraction()
