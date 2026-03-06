import os
import time
import json
from typing import List, Optional, Dict, Any
from ..models.triage import DocumentProfile, ExtractionCostTier
from ..models.extraction import ExtractedDocument
from ..strategies.base import BaseExtractor, ExtractionResult
from ..strategies.fast_text import FastTextExtractor
from ..strategies.layout_extractor import LayoutExtractor
from ..strategies.vision_extractor import VisionExtractor
from ..strategies.evaluator import HeuristicConfidenceEvaluator

class ExtractionRouter:
    def __init__(self, rules: Optional[dict] = None):
        self.rules = {
            "max_retries": 3,
            "min_confidence_threshold": 0.6,
            "ledger_path": ".refinery/extraction_ledger.jsonl",
            "strategy_a": {},
            "strategy_b": {},
            "strategy_c": {}
        }
        if rules:
            self.rules.update(rules)
        
        self.strategies: Dict[str, BaseExtractor] = {
            "fast_text": FastTextExtractor(self.rules.get("strategy_a")),
            "layout_aware": LayoutExtractor(self.rules.get("strategy_b")),
            "vision_augmented": VisionExtractor(self.rules.get("strategy_c"))
        }
        self.evaluator = HeuristicConfidenceEvaluator()

        os.makedirs(os.path.dirname(self.rules["ledger_path"]), exist_ok=True)

    def extract_document(self, file_path: str, profile: DocumentProfile) -> List[ExtractionResult]:
        results = []
        for page_prof in profile.pages:
            result = self.extract_page_with_escalation(file_path, page_prof.page_number, profile.document_id, page_prof.estimated_extraction_cost)
            results.append(result)
        return results

    def extract_page_with_escalation(self, file_path: str, page_number: int, document_id: str, preferred_tier: ExtractionCostTier) -> ExtractionResult:
        # Determine initial strategy based on tier
        strategy_chain = ["fast_text", "layout_aware", "vision_augmented"]
        
        start_index = 0
        if preferred_tier == ExtractionCostTier.NEEDS_LAYOUT_MODEL:
            start_index = 1
        elif preferred_tier == ExtractionCostTier.NEEDS_VISION_MODEL:
            start_index = 2

        current_attempt = 0
        last_result = None

        for i in range(start_index, len(strategy_chain)):
            strategy_name = strategy_chain[i]
            extractor = self.strategies[strategy_name]
            
            while current_attempt < self.rules["max_retries"]:
                result = extractor.extract_page(file_path, page_number, document_id)
                
                # Post-extraction confidence evaluation (Text Quality)
                eval_score = self.evaluator.evaluate(result.content)
                # Combine extractor's internal confidence with heuristic evaluation
                # We take the minimum to be conservative
                final_confidence = min(result.confidence_score, eval_score)
                result.confidence_score = final_confidence
                
                self._log_to_ledger(result)
                
                if result.confidence_score >= self.rules["min_confidence_threshold"] and not result.error:
                    return result
                
                current_attempt += 1
                last_result = result
            
            # If we reach here, this strategy failed or low confidence, move to next in chain
            current_attempt = 0 # Reset retries for next strategy

        return last_result or ExtractionResult(
            extraction_id=f"failed_{document_id}_{page_number}",
            document_id=document_id,
            page_number=page_number,
            strategy_used="none",
            content=ExtractedDocument(document_id=document_id),
            confidence_score=0.0,
            processing_time=0.0,
            error="All strategies failed to reach confidence threshold"
        )

    def _log_to_ledger(self, result: ExtractionResult):
        entry = {
            "doc_id": result.document_id,
            "page_number": result.page_number,
            "strategy_used": result.strategy_used,
            "confidence": result.confidence_score,
            "processing_time": result.processing_time,
            "cost_estimate": result.cost_estimate,
            "error": result.error
        }
        with open(self.rules["ledger_path"], "a") as f:
            f.write(json.dumps(entry) + "\n")
