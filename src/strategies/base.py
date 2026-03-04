from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from ..models.extraction import ExtractedDocument

class ExtractionResult(BaseModel):
    extraction_id: str
    document_id: str
    page_number: int
    strategy_used: str
    content: ExtractedDocument
    confidence_score: float = Field(ge=0.0, le=1.0)
    processing_time: float
    cost_estimate: float = 0.0
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class BaseExtractor(ABC):
    @abstractmethod
    def extract_page(self, file_path: str, page_number: int, document_id: Optional[str] = None) -> ExtractionResult:
        """Extract content from a specific page of a document."""
        pass
