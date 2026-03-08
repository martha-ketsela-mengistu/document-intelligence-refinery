import os
import sys
from pydantic import ValidationError
from src.models.base import BoundingBox, ProvenanceBase
from src.agents.triage import TriageAgent
from src.strategies.classifier import KeywordDomainClassifier, DomainClassifier
from src.models.triage import DomainHint

def test_bounding_box_validation():
    print("Testing BoundingBox validation...")
    # Valid
    box = BoundingBox(x0=10, y0=20, x1=30, y1=40)
    print(f"✓ Valid box: {box}")
    assert box.to_tuple() == (10, 20, 30, 40)

    # Invalid: x1 < x0
    try:
        BoundingBox(x0=30, y0=20, x1=10, y1=40)
    except ValidationError as e:
        print(f"✓ Caught invalid x1: {e.errors()[0]['msg']}")

    # Invalid: negative
    try:
        BoundingBox(x0=-1, y0=20, x1=10, y1=40)
    except ValidationError as e:
        print(f"✓ Caught negative x0: {e.errors()[0]['msg']}")

def test_domain_classifier():
    print("\nTesting KeywordDomainClassifier...")
    classifier = KeywordDomainClassifier()
    
    financial_text = "The bank's audit report showed significant revenue growth."
    legal_text = "According to article 5 of the compliance law, this section is mandatory."
    
    assert classifier.classify(financial_text) == DomainHint.FINANCIAL
    assert classifier.classify(legal_text) == DomainHint.LEGAL
    print("✓ Domain classification works as expected")

def test_triage_with_custom_classifier():
    print("\nTesting TriageAgent with custom classifier...")
    class MockClassifier(DomainClassifier):
        def classify(self, text: str) -> DomainHint:
            return DomainHint.MEDICAL
    
    mock_classifier = MockClassifier()
    triage_agent = TriageAgent(domain_classifier=mock_classifier)
    
    # We can't easily run a full triage without a real PDF, but we can verify the classifier is assigned
    assert triage_agent.classifier == mock_classifier
    print("✓ TriageAgent accepts custom classifier")

if __name__ == "__main__":
    sys.path.append(os.getcwd())
    try:
        test_bounding_box_validation()
        test_domain_classifier()
        test_triage_with_custom_classifier()
        print("\nAll model and classifier tests passed!")
    except Exception as e:
        print(f"\nVerification failed: {e}")
        sys.exit(1)
