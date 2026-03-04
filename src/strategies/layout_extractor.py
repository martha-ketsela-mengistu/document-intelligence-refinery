import time
import hashlib
from typing import Optional
from docling.datamodel.base_models import InputFormat
from docling.document_converter import DocumentConverter
from .base import BaseExtractor, ExtractionResult
from ..models.base import BoundingBox
from ..models.extraction import ExtractedDocument, TextBlock, Table, Figure

class LayoutExtractor(BaseExtractor):
    def __init__(self, rules: Optional[dict] = None):
        self.rules = rules or {}
        self.converter = DocumentConverter()

    def extract_page(self, file_path: str, page_number: int, document_id: Optional[str] = None) -> ExtractionResult:
        start_time = time.time()
        doc_id = document_id or hashlib.md5(file_path.encode()).hexdigest()
        
        try:
            # Docling typically converts the whole document
            # But for our pipeline, we might want to convert specific pages or use its internal representation
            # For this MVP, we'll convert and then filter for the page
            result = self.converter.convert(file_path)
            doc = result.document
            
            text_blocks = []
            tables = []
            figures = []
            
            # Docling's doc structure contains elements with page information
            for element, level in doc.iterate_items():
                # Check if element is on the requested page
                # Docling 2.x structure might vary, adapting to common pattern
                prov = getattr(element, 'prov', [])
                if prov and any(p.page_no == page_number for p in prov):
                    if hasattr(element, 'text'):
                        # Text or Table?
                        if hasattr(element, 'rows'): # Table
                            bbox = self._get_bbox(element)
                            tables.append(Table(
                                document_id=doc_id,
                                page_number=page_number,
                                bbox=bbox,
                                content_hash=f"table_{hashlib.md5(element.text.encode()).hexdigest()}",
                                headers=[str(c.text) for c in element.rows[0].cells] if element.rows else [],
                                rows=[[str(c.text) for c in r.cells] for r in element.rows[1:]] if len(element.rows) > 1 else []
                            ))
                        else:
                            bbox = self._get_bbox(element)
                            text_blocks.append(TextBlock(
                                document_id=doc_id,
                                page_number=page_number,
                                bbox=bbox,
                                content_hash=f"text_{hashlib.md5(element.text.encode()).hexdigest()}",
                                text=element.text
                            ))
            
            content = ExtractedDocument(
                document_id=doc_id,
                text_blocks=text_blocks,
                tables=tables,
                figures=figures,
                reading_order=[b.content_hash for b in text_blocks] + [t.content_hash for t in tables]
            )
            
            processing_time = time.time() - start_time
            return ExtractionResult(
                extraction_id=f"layout_{doc_id}_{page_number}",
                document_id=doc_id,
                page_number=page_number,
                strategy_used="layout_aware",
                content=content,
                confidence_score=0.9, # Docling is generally high confidence for layout
                processing_time=processing_time
            )

        except Exception as e:
            return ExtractionResult(
                extraction_id=f"layout_{doc_id}_{page_number}",
                document_id=doc_id,
                page_number=page_number,
                strategy_used="layout_aware",
                content=ExtractedDocument(document_id=doc_id),
                confidence_score=0.0,
                processing_time=time.time() - start_time,
                error=str(e)
            )

    def _get_bbox(self, element) -> BoundingBox:
        # Docling prov contains location info
        if hasattr(element, 'prov') and element.prov:
            p = element.prov[0]
            if hasattr(p, 'bbox'):
                return BoundingBox(x0=p.bbox.l, y0=p.bbox.t, x1=p.bbox.r, y1=p.bbox.b)
        return BoundingBox(x0=0.0, y0=0.0, x1=0.0, y1=0.0)
