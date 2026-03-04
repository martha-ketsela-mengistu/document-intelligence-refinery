from abc import ABC, abstractmethod
from typing import Optional, List
from ..models.triage import DomainHint

class DomainClassifier(ABC):
    @abstractmethod
    def classify(self, text: str) -> DomainHint:
        """Classify the domain of the given text."""
        pass

class KeywordDomainClassifier(DomainClassifier):
    def classify(self, text: str) -> DomainHint:
        text_lower = text.lower()
        if any(w in text_lower for w in ["revenue", "financial", "bank", "audit", "tax", "fiscal"]):
            return DomainHint.FINANCIAL
        if any(w in text_lower for w in ["legal", "court", "compliance", "law", "article", "section"]):
            return DomainHint.LEGAL
        if any(w in text_lower for w in ["technical", "specification", "architecture", "engineering", "manual"]):
            return DomainHint.TECHNICAL
        if any(w in text_lower for w in ["medical", "health", "patient", "clinical", "hospital"]):
            return DomainHint.MEDICAL
        return DomainHint.GENERAL
