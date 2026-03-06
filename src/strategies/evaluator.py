from abc import ABC, abstractmethod
import re
from typing import List
from ..models.extraction import ExtractedDocument

class ConfidenceEvaluator(ABC):
    @abstractmethod
    def evaluate(self, document: ExtractedDocument) -> float:
        """Evaluate the quality of extracted text and return a confidence score (0.0 to 1.0)."""
        pass

class HeuristicConfidenceEvaluator(ConfidenceEvaluator):
    def __init__(self, rules: dict = None):
        self.rules = rules or {
            "min_words": 5,
            "garbage_char_ratio": 0.15,
            "max_whitespace_ratio": 0.5
        }

    def evaluate(self, document: ExtractedDocument) -> float:
        all_text = " ".join([b.text for b in document.text_blocks])
        
        if not all_text.strip():
            # If there are tables but no text, it might still be okay, but usually text blocks exist
            if document.tables:
                return 0.5
            return 0.0

        # 1. Word Count Check
        words = all_text.split()
        if len(words) < self.rules["min_words"]:
            return 0.3

        # 2. Garbage Character Ratio (e.g., non-alphanumeric/non-sentence punctuation)
        # We allow common Amharic characters too in the regex if needed
        # For a simple heuristic, let's look for suspicious repeating symbols
        garbage_pattern = r'[^a-zA-Z0-9\s.,!?;:\u1200-\u137F]'
        garbage_chars = re.findall(garbage_pattern, all_text)
        garbage_ratio = len(garbage_chars) / len(all_text) if all_text else 0
        
        if garbage_ratio > self.rules["garbage_char_ratio"]:
            return max(0.1, 0.9 - (garbage_ratio * 4)) # Scale down heavily

        # 3. Whitespace Ratio (indicator of broken layout/OCR)
        whitespace_count = len(re.findall(r'\s{3,}', all_text))
        whitespace_ratio = (whitespace_count * 10) / len(all_text) if all_text else 0
        
        if whitespace_ratio > self.rules["max_whitespace_ratio"]:
            return 0.4

        # 4. Language Coherence (Very simple check for repeated characters/gibberish)
        if re.search(r'(.)\1{5,}', all_text): # e.g. "aaaaaa" or "......"
            return 0.2

        return 0.95 # Base high confidence for passed heuristics
