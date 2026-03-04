import os
import time
import hashlib
import json
import requests
from typing import Optional
from .base import BaseExtractor, ExtractionResult
from ..models.base import BoundingBox
from ..models.extraction import ExtractedDocument, TextBlock, Table, Figure

class VisionExtractor(BaseExtractor):
    def __init__(self, rules: Optional[dict] = None):
        self.rules = rules or {
            "ollama_url": os.getenv("OLLAMA_API_URL", "https://api.ollama.com/v1/chat/completions"),
            "model": "llama3.2-vision",
            "page_limit": 10,
            "cost_per_page": 0.01
        }
        self.api_key = os.getenv("OLLAMA_API_KEY")
        self.pages_processed = 0

    def extract_page(self, file_path: str, page_number: int, document_id: Optional[str] = None) -> ExtractionResult:
        start_time = time.time()
        doc_id = document_id or hashlib.md5(file_path.encode()).hexdigest()
        
        # Budget Guard
        if self.pages_processed >= self.rules["page_limit"]:
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
            
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            response = requests.post(
                self.rules["ollama_url"],
                headers=headers,
                json={
                    "model": self.rules["model"],
                    "prompt": prompt,
                    "stream": False,
                    "images": [image_data]
                }
            )
            response.raise_for_status()
            raw_output = response.json().get("response", "")
            
            # Parse JSON from response
            extracted_data = self._parse_json(raw_output)
            
            text_blocks = [
                TextBlock(
                    document_id=doc_id,
                    page_number=page_number,
                    bbox=BoundingBox(
                        x0=b.get("bbox", [0,0,0,0])[0],
                        y0=b.get("bbox", [0,0,0,0])[1],
                        x1=b.get("bbox", [0,0,0,0])[2],
                        y1=b.get("bbox", [0,0,0,0])[3]
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
                        x0=t.get("bbox", [0,0,0,0])[0],
                        y0=t.get("bbox", [0,0,0,0])[1],
                        x1=t.get("bbox", [0,0,0,0])[2],
                        y1=t.get("bbox", [0,0,0,0])[3]
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
                        x0=f.get("bbox", [0,0,0,0])[0],
                        y0=f.get("bbox", [0,0,0,0])[1],
                        x1=f.get("bbox", [0,0,0,0])[2],
                        y1=f.get("bbox", [0,0,0,0])[3]
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
            
            return ExtractionResult(
                extraction_id=f"vision_{doc_id}_{page_number}",
                document_id=doc_id,
                page_number=page_number,
                strategy_used="vision_augmented",
                content=content,
                confidence_score=0.8, # VLM confidence
                processing_time=processing_time,
                cost_estimate=self.rules["cost_per_page"]
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
        # Placeholder for PDF to Image conversion
        return "BASE64_IMAGE_DATA"

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
