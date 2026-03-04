from unittest.mock import MagicMock, patch
from src.agents.triage import TriageAgent
from src.models.triage import OriginType, LayoutComplexity, ExtractionCostTier

def test_triage_logic():
    agent = TriageAgent()
    
    # Test Origin Detection
    # Case 1: Digital
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "A" * 150 # Exceeds min_chars_for_digital (100)
    origin = agent.detect_origin_type(density=0.05, image_ratio=0.1, has_fonts=True, page=mock_page)
    assert origin == OriginType.NATIVE_DIGITAL
    
    # Case 2: Scanned
    origin = agent.detect_origin_type(density=0.001, image_ratio=0.8, has_fonts=False, page=MagicMock())
    assert origin == OriginType.SCANNED_IMAGE
    
    # Test Cost Calculation
    cost = agent.calculate_estimated_cost_per_page(OriginType.NATIVE_DIGITAL, LayoutComplexity.SINGLE_COLUMN, 0.05)
    assert cost == ExtractionCostTier.FAST_TEXT_SUFFICIENT
    
    cost = agent.calculate_estimated_cost_per_page(OriginType.SCANNED_IMAGE, LayoutComplexity.SINGLE_COLUMN, 0.001)
    assert cost == ExtractionCostTier.NEEDS_VISION_MODEL
    
    # Test Domain Hint
    hint = agent.classify_domain_hint("This is a financial report about banking revenue.")
    assert hint.value == "financial"
    
    print("✓ Triage logic tests passed")

if __name__ == "__main__":
    try:
        test_triage_logic()
    except Exception as e:
        import traceback
        print(f"Tests failed: {e}")
        traceback.print_exc()
        exit(1)
