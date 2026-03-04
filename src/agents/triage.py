import os
import pdfplumber
from typing import List, Dict, Any, Optional
from collections import Counter
from ..models.triage import (
    DocumentProfile, PageProfile, OriginType, LayoutComplexity, 
    DomainHint, ExtractionCostTier, LanguageInfo
)
from ..strategies.classifier import DomainClassifier, KeywordDomainClassifier

class TriageAgent:
    def __init__(self, extraction_rules: Optional[Dict[str, Any]] = None, domain_classifier: Optional[DomainClassifier] = None):
        self.rules = {
            "density_threshold": 0.001,
            "image_ratio_threshold": 0.5,
            "min_chars_for_digital": 100,
            "multi_column_gap_threshold": 30,
            "table_line_threshold": 5,
        }
        self.classifier = domain_classifier or KeywordDomainClassifier()
        if extraction_rules:
            # Map specific YAML structure to internal keys
            if "strategy_a" in extraction_rules:
                s_a = extraction_rules["strategy_a"]
                self.rules["min_chars_for_digital"] = s_a.get("min_char_count_per_page", 100)
                self.rules["density_threshold"] = s_a.get("min_char_density", 0.001)
                self.rules["image_ratio_threshold"] = s_a.get("max_image_area_pct", 0.5)
            
            # Allow direct overrides from top-level keys if they match
            for k, v in extraction_rules.items():
                if k in self.rules:
                    self.rules[k] = v

    def triage_document(self, file_path: str, document_id: Optional[str] = None) -> DocumentProfile:
        if not document_id:
            document_id = os.path.basename(file_path)

        page_profiles = []
        all_text = ""
        with pdfplumber.open(file_path) as pdf:
            for i, page in enumerate(pdf.pages):
                page_text = page.extract_text() or ""
                all_text += page_text + "\n"
                
                page_profile = self.triage_page(page, i + 1)
                page_profiles.append(page_profile)

        # Aggregate document-level summary
        doc_profile = self._summarize_document(document_id, page_profiles)
        
        # Determine domain hint from aggregated text
        doc_profile.domain_hint = self.classifier.classify(all_text)
        
        return doc_profile

    def triage_page(self, page: pdfplumber.page.Page, page_number: int) -> PageProfile:
        density = self.analyze_character_density(page)
        image_ratio = self.calculate_image_area_ratio(page)
        has_fonts = self.extract_font_metadata(page)
        
        origin = self.detect_origin_type(density, image_ratio, has_fonts, page)
        complexity = self.detect_layout_complexity(page)
        cost = self.calculate_estimated_cost_per_page(origin, complexity, density)

        return PageProfile(
            page_number=page_number,
            origin_type=origin,
            layout_complexity=complexity,
            character_density=density,
            image_area_ratio=image_ratio,
            has_font_metadata=has_fonts,
            estimated_extraction_cost=cost,
            metadata={
                "char_count": len(page.extract_text() or ""),
                "image_count": len(page.images),
                "rect_count": len(page.rects)
            }
        )

    def analyze_character_density(self, page: pdfplumber.page.Page) -> float:
        text = page.extract_text() or ""
        char_count = len(text)
        page_area = page.width * page.height
        if page_area == 0:
            return 0.0
        return char_count / page_area

    def calculate_image_area_ratio(self, page: pdfplumber.page.Page) -> float:
        total_image_area = 0
        for img in page.images:
            img_width = img.get("width", 0)
            img_height = img.get("height", 0)
            total_image_area += (img_width * img_height)
        
        page_area = page.width * page.height
        if page_area == 0:
            return 0.0
        return min(1.0, total_image_area / page_area)

    def extract_font_metadata(self, page: pdfplumber.page.Page) -> bool:
        # Check if the page has embedded fonts in its objects
        return len(page.chars) > 0 and any(c.get("fontname") for c in page.chars[:100])

    def detect_origin_type(self, density: float, image_ratio: float, has_fonts: bool, page: pdfplumber.page.Page) -> OriginType:
        text = page.extract_text() or ""
        char_count = len(text)

        if has_fonts and char_count > self.rules["min_chars_for_digital"]:
            return OriginType.NATIVE_DIGITAL
        
        if image_ratio > self.rules["image_ratio_threshold"] and char_count < self.rules["min_chars_for_digital"]:
            return OriginType.SCANNED_IMAGE
        
        if char_count > 0:
            return OriginType.MIXED
            
        return OriginType.SCANNED_IMAGE

    def detect_layout_complexity(self, page: pdfplumber.page.Page) -> LayoutComplexity:
        # Check for tables (pdfplumber has built-in table detection)
        tables = page.find_tables()
        if len(tables) > 1 or (len(tables) == 1 and len(page.rects) > self.rules["table_line_threshold"]):
            return LayoutComplexity.TABLE_HEAVY

        # Check for multiple columns
        # Simplistic approach: look for vertical whitespace gaps in text
        # Real implementation would be more complex, here we use a heuristic
        if self._has_multiple_columns(page):
            return LayoutComplexity.MULTI_COLUMN

        # Check for images
        if len(page.images) > 2:
            return LayoutComplexity.FIGURE_HEAVY

        return LayoutComplexity.SINGLE_COLUMN

    def _has_multiple_columns(self, page: pdfplumber.page.Page) -> bool:
        # A very basic heuristic: check if there's a significant vertical gap in the middle
        mid = page.width / 2
        margin = self.rules["multi_column_gap_threshold"]
        
        # Check if any characters fall in the middle vertical strip
        chars_in_middle = [c for c in page.chars if mid - margin < c["x0"] < mid + margin]
        
        # If there are few characters in the middle but many on both sides, it might be multi-column
        if not chars_in_middle and len(page.chars) > 100:
            return True
        return False


    def calculate_estimated_cost_per_page(self, origin: OriginType, complexity: LayoutComplexity, density: float) -> ExtractionCostTier:
        # Scanned images might be extractable with layout models (Strategy B) first.
        # Escalation to Vision (Strategy C) will happen at the extraction stage if needed.
        if origin == OriginType.SCANNED_IMAGE:
            return ExtractionCostTier.NEEDS_LAYOUT_MODEL
        
        if complexity in [LayoutComplexity.TABLE_HEAVY, LayoutComplexity.MULTI_COLUMN]:
            return ExtractionCostTier.NEEDS_LAYOUT_MODEL
            
        # if density < self.rules["density_threshold"] / 10:
        #     return ExtractionCostTier.NEEDS_VISION_MODEL
            
        return ExtractionCostTier.FAST_TEXT_SUFFICIENT

    def _summarize_document(self, document_id: str, page_profiles: List[PageProfile]) -> DocumentProfile:
        if not page_profiles:
            # Fallback for empty docs
            return DocumentProfile(
                document_id=document_id,
                overall_origin_type=OriginType.SCANNED_IMAGE,
                overall_layout_complexity=LayoutComplexity.SINGLE_COLUMN,
                overall_estimated_cost=ExtractionCostTier.FAST_TEXT_SUFFICIENT,
                domain_hint=DomainHint.GENERAL,
                language=LanguageInfo(code="en", confidence=0.0),
                pages=[]
            )

        # Dominant types
        origins = [p.origin_type for p in page_profiles]
        complexities = [p.layout_complexity for p in page_profiles]
        costs = [p.estimated_extraction_cost for p in page_profiles]
        
        origin_counts = Counter(origins)
        complexity_counts = Counter(complexities)
        cost_counts = Counter(costs)

        # Decide overall status
        # If any page is scanned, the doc might be mixed
        overall_origin = OriginType.MIXED if len(set(origins)) > 1 else origins[0]
        if origin_counts[OriginType.SCANNED_IMAGE] == len(page_profiles):
            overall_origin = OriginType.SCANNED_IMAGE
        elif origin_counts[OriginType.NATIVE_DIGITAL] == len(page_profiles):
            overall_origin = OriginType.NATIVE_DIGITAL

        # Dominant complexity
        overall_complexity = complexity_counts.most_common(1)[0][0]
        
        # Max cost is safer for estimation
        overall_cost = ExtractionCostTier.FAST_TEXT_SUFFICIENT
        if ExtractionCostTier.NEEDS_VISION_MODEL in costs:
            overall_cost = ExtractionCostTier.NEEDS_VISION_MODEL
        elif ExtractionCostTier.NEEDS_LAYOUT_MODEL in costs:
            overall_cost = ExtractionCostTier.NEEDS_LAYOUT_MODEL

        # Domain hint from first few pages
        # (Assuming first page or first 5 pages give the context)
        # We need text for this, let's just use a dummy text for now or re-extract
        # In a real scenario, we'd pass the aggregated text to the classifier.
        # For now, let's assume we have it or use metadata.
        
        return DocumentProfile(
            document_id=document_id,
            overall_origin_type=overall_origin,
            overall_layout_complexity=overall_complexity,
            overall_estimated_cost=overall_cost,
            domain_hint=DomainHint.GENERAL, # Placeholder, should be updated with text
            language=LanguageInfo(code="en", confidence=0.9), # Placeholder
            pages=page_profiles
        )
