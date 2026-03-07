from typing import List, Optional
from pydantic import BaseModel, Field
from .base import BoundingBox, ProvenanceBase

class TextBlock(ProvenanceBase):
    text: str

class Table(ProvenanceBase):
    headers: List[str]
    rows: List[List[str]]
    # Optional field for cell-level bboxes if needed, but spec says "tables as structured objects"
    # and "Every extracted item must include: document_id, page_number, bbox"

class Figure(ProvenanceBase):
    caption: Optional[str] = None
    alt_text: Optional[str] = None

class ExtractedDocument(BaseModel):
    """Normalized extraction output from various strategies."""
    document_id: str
    page_number: int = Field(ge=1)
    text_blocks: List[TextBlock] = Field(default_factory=list)
    tables: List[Table] = Field(default_factory=list)
    figures: List[Figure] = Field(default_factory=list)
    reading_order: List[str] = Field(default_factory=list, description="Ordered list of item IDs or content hashes")

class FactEntry(BaseModel):
    """A structured fact extracted from the document."""
    doc_id: str
    entity: str
    attribute: str
    value: str
    unit: Optional[str] = None
    page_number: int
    bbox: BoundingBox
    content_hash: str
