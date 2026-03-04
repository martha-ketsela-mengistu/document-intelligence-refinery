import time
import pdfplumber
import hashlib
from typing import Optional, List
from .base import BaseExtractor, ExtractionResult
from ..models.extraction import ExtractedDocument, TextBlock, Table, Figure

class FastTextExtractor(BaseExtractor):
    def __init__(self, rules: Optional[dict] = None):
        self.rules = rules or {
            "min_char_density": 0.001,
            "accept_confidence_threshold": 0.6
        }

    def extract_page(self, file_path: str, page_number: int, document_id: Optional[str] = None) -> ExtractionResult:
        start_time = time.time()
        doc_id = document_id or hashlib.md5(file_path.encode()).hexdigest()
        
        try:
            with pdfplumber.open(file_path) as pdf:
                if page_number > len(pdf.pages):
                    raise ValueError(f"Page {page_number} out of range (max {len(pdf.pages)})")
                
                page = pdf.pages[page_number - 1]
                
                # Extract Text Blocks (simplistic grouping by lines)
                text_blocks = []
                words = page.extract_words()
                # Group words into blocks if they share same top (rough line detection)
                current_block = []
                last_top = -1
                for w in words:
                    if abs(w['top'] - last_top) > 2: # New line
                        if current_block:
                            text_blocks.append(self._create_text_block(current_block, doc_id, page_number))
                        current_block = [w]
                        last_top = w['top']
                    else:
                        current_block.append(w)
                if current_block:
                    text_blocks.append(self._create_text_block(current_block, doc_id, page_number))

                # Extract Tables
                tables = []
                found_tables = page.find_tables()
                for i, t in enumerate(found_tables):
                    table_data = t.extract()
                    if table_data and len(table_data) > 0:
                        headers = table_data[0]
                        rows = table_data[1:] if len(table_data) > 1 else []
                        bbox = (t.bbox[0], t.bbox[1], t.bbox[2], t.bbox[3])
                        content = f"{headers}\n{rows}"
                        h = hashlib.md5(content.encode()).hexdigest()
                        
                        tables.append(Table(
                            document_id=doc_id,
                            page_number=page_number,
                            bbox=bbox,
                            content_hash=f"table_{h}",
                            headers=[str(h) for h in headers],
                            rows=[[str(c) for c in r] for r in rows]
                        ))

                # Extract Figures (images)
                figures = []
                for i, img in enumerate(page.images):
                    bbox = (img['x0'], img['top'], img['x1'], img['bottom'])
                    figures.append(Figure(
                        document_id=doc_id,
                        page_number=page_number,
                        bbox=bbox,
                        content_hash=f"fig_{doc_id}_{page_number}_{i}",
                        caption=None
                    ))

                # Build ExtractedDocument
                content = ExtractedDocument(
                    document_id=doc_id,
                    text_blocks=text_blocks,
                    tables=tables,
                    figures=figures,
                    reading_order=[b.content_hash for b in text_blocks] + [t.content_hash for t in tables]
                )

                # Confidence Scoring
                confidence = self._calculate_confidence(page, content)
                
                processing_time = time.time() - start_time
                return ExtractionResult(
                    extraction_id=f"fast_{doc_id}_{page_number}",
                    document_id=doc_id,
                    page_number=page_number,
                    strategy_used="fast_text",
                    content=content,
                    confidence_score=confidence,
                    processing_time=processing_time,
                    cost_estimate=0.0
                )

        except Exception as e:
            return ExtractionResult(
                extraction_id=f"fast_{doc_id}_{page_number}",
                document_id=doc_id,
                page_number=page_number,
                strategy_used="fast_text",
                content=ExtractedDocument(document_id=doc_id),
                confidence_score=0.0,
                processing_time=time.time() - start_time,
                error=str(e)
            )

    def _create_text_block(self, words: List[dict], doc_id: str, page_number: int) -> TextBlock:
        text = " ".join([w['text'] for w in words])
        x0 = min([w['x0'] for w in words])
        top = min([w['top'] for w in words])
        x1 = max([w['x1'] for w in words])
        bottom = max([w['bottom'] for w in words])
        bbox = (x0, top, x1, bottom)
        h = hashlib.md5(text.encode()).hexdigest()
        return TextBlock(
            document_id=doc_id,
            page_number=page_number,
            bbox=bbox,
            content_hash=f"text_{h}",
            text=text
        )

    def _calculate_confidence(self, page, content: ExtractedDocument) -> float:
        # Simplistic confidence: based on character density and successful table extraction
        text = page.extract_text() or ""
        char_count = len(text)
        page_area = page.width * page.height
        density = char_count / page_area if page_area > 0 else 0
        
        # If density is extremely low, confidence is low
        if density < self.rules["min_char_density"]:
            return 0.2
        
        # If there are many rects but no tables found, confidence might be lower
        if len(page.rects) > 10 and not content.tables:
            return 0.5
            
        return 0.95 # Base confidence for healthy digital text
