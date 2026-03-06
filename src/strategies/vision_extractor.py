import os
import time
import hashlib
import json
import base64
import fitz
from typing import Optional
from ollama import Client
from .base import BaseExtractor, ExtractionResult
from ..models.base import BoundingBox
from .base import BaseExtractor, ExtractionResult
from ..models.base import BoundingBox
from ..models.extraction import ExtractedDocument, TextBlock, Table, Figure
from ..utils.logging_utils import get_logger

logger = get_logger(__name__)

class VisionExtractor(BaseExtractor):
    def __init__(self, rules: Optional[dict] = None):
        defaults = {
            "ollama_host": os.getenv("OLLAMA_HOST", "https://ollama.com"),
            "model": "qwen3-vl:235b-instruct",
            "page_limit": 10,
            "cost_per_second": 0.01 # VLMs are expensive in compute time
        }
        self.rules = {**defaults, **(rules or {})}
        self.client = Client(host=self.rules["ollama_host"])
        self.pages_processed = 0

    def extract_page(self, file_path: str, page_number: int, document_id: Optional[str] = None) -> ExtractionResult:
        start_time = time.time()
        doc_id = document_id or hashlib.md5(file_path.encode()).hexdigest()
        
        # Budget Guard
        if self.pages_processed >= self.rules["page_limit"]:
            logger.warning(f"[{doc_id}] Vision: Page limit reached ({self.rules['page_limit']}). Skipping page {page_number}.")
            return ExtractionResult(
                extraction_id=f"vision_{doc_id}_{page_number}",
                document_id=doc_id,
                page_number=page_number,
                strategy_used="vision_augmented",
                content=ExtractedDocument(document_id=doc_id),
                confidence_score=0.0,
                processing_time=0.0,
                error="Budget guard: page limit exceeded"
            )

        try:
            # For OLLAMA, we need to convert PDF page to image
            # Since we don't have a specific tool for this here, we'll assume a helper or use a library
            # In a real environment, we'd use fitz (PyMuPDF) or similar
            # For the mock/impl, we'll placeholder the image conversion
            image_data = self._get_page_image_base64(file_path, page_number)
            
            prompt = """
            Extract the content of this document page into a structured JSON format.
            Identify text blocks (with approximate bounding boxes [x0, y0, x1, y1]), 
            tables (with headers and rows), and figures.
            Format the output strictly as JSON following this schema:
            {
                "text_blocks": [{"text": "...", "bbox": [x0, y0, x1, y1]}],
                "tables": [{"headers": ["..."], "rows": [["..."]], "bbox": [x0, y0, x1, y1]}],
                "figures": [{"caption": "...", "bbox": [x0, y0, x1, y1]}]
            }
            """
            
            logger.info(f"[{doc_id}] Vision: Sending page {page_number} to VLM ({self.rules['model']})...")
            response = self.client.generate(
                model=self.rules["model"],
                prompt=prompt,
                images=[image_data],
                stream=False
            )
            raw_output = response.get("response", "")
            
            # Parse JSON from response
            extracted_data = self._parse_json(raw_output)
            
            text_blocks = [
                TextBlock(
                    document_id=doc_id,
                    page_number=page_number,
                    bbox=BoundingBox(
                        x0=min(b.get("bbox", [0,0,0,0])[0], b.get("bbox", [0,0,0,0])[2]),
                        y0=min(b.get("bbox", [0,0,0,0])[1], b.get("bbox", [0,0,0,0])[3]),
                        x1=max(b.get("bbox", [0,0,0,0])[0], b.get("bbox", [0,0,0,0])[2]),
                        y1=max(b.get("bbox", [0,0,0,0])[1], b.get("bbox", [0,0,0,0])[3])
                    ),
                    content_hash=hashlib.md5(b.get("text", "").encode()).hexdigest(),
                    text=b.get("text", "")
                ) for b in extracted_data.get("text_blocks", [])
            ]
            
            tables = [
                Table(
                    document_id=doc_id,
                    page_number=page_number,
                    bbox=BoundingBox(
                        x0=min(t.get("bbox", [0,0,0,0])[0], t.get("bbox", [0,0,0,0])[2]),
                        y0=min(t.get("bbox", [0,0,0,0])[1], t.get("bbox", [0,0,0,0])[3]),
                        x1=max(t.get("bbox", [0,0,0,0])[0], t.get("bbox", [0,0,0,0])[2]),
                        y1=max(t.get("bbox", [0,0,0,0])[1], t.get("bbox", [0,0,0,0])[3])
                    ),
                    content_hash=hashlib.md5(str(t).encode()).hexdigest(),
                    headers=t.get("headers", []),
                    rows=t.get("rows", [])
                ) for t in extracted_data.get("tables", [])
            ]
            
            figures = [
                Figure(
                    document_id=doc_id,
                    page_number=page_number,
                    bbox=BoundingBox(
                        x0=min(f.get("bbox", [0,0,0,0])[0], f.get("bbox", [0,0,0,0])[2]),
                        y0=min(f.get("bbox", [0,0,0,0])[1], f.get("bbox", [0,0,0,0])[3]),
                        x1=max(f.get("bbox", [0,0,0,0])[0], f.get("bbox", [0,0,0,0])[2]),
                        y1=max(f.get("bbox", [0,0,0,0])[1], f.get("bbox", [0,0,0,0])[3])
                    ),
                    content_hash=hashlib.md5(str(f).encode()).hexdigest(),
                    caption=f.get("caption")
                ) for f in extracted_data.get("figures", [])
            ]

            content = ExtractedDocument(
                document_id=doc_id,
                text_blocks=text_blocks,
                tables=tables,
                figures=figures,
                reading_order=[b.content_hash for b in text_blocks] + [t.content_hash for t in tables]
            )

            self.pages_processed += 1
            processing_time = time.time() - start_time
            
            logger.info(f"[{doc_id}] Vision Page {page_number}: Extracted {len(text_blocks)} text blocks, {len(tables)} tables, {len(figures)} figures. Confidence: 0.80")
            
            return ExtractionResult(
                extraction_id=f"vision_{doc_id}_{page_number}",
                document_id=doc_id,
                page_number=page_number,
                strategy_used="vision_augmented",
                content=content,
                confidence_score=0.8, # VLM confidence
                processing_time=processing_time,
                cost_estimate=processing_time * self.rules.get("cost_per_second", 0.01)
            )

        except Exception as e:
            return ExtractionResult(
                extraction_id=f"vision_{doc_id}_{page_number}",
                document_id=doc_id,
                page_number=page_number,
                strategy_used="vision_augmented",
                content=ExtractedDocument(document_id=doc_id),
                confidence_score=0.0,
                processing_time=time.time() - start_time,
                error=f"Vision strategy failed: {str(e)}"
            )

    def _get_page_image_base64(self, file_path, page_number):
        """Convert a PDF page to a base64 encoded PNG image."""
        doc = fitz.open(file_path)
        try:
            page = doc.load_page(page_number - 1)
            # Use a higher matrix for better quality extraction if needed
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            img_bytes = pix.tobytes("png")
            return base64.b64encode(img_bytes).decode("utf-8")
        finally:
            doc.close()

    def _parse_json(self, text):
        try:
            # Find JSON block in markdown-like output
            start = text.find("{")
            end = text.rfind("}") + 1
            if start != -1 and end != -1:
                return json.loads(text[start:end])
            return {}
        except:
            return {}
