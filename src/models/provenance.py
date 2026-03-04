from typing import List
from pydantic import BaseModel
from .base import BoundingBox

class ProvenanceEntry(BaseModel):
    """A single citation in a provenance chain."""
    document_name: str
    page_number: int
    bbox: BoundingBox
    content_hash: str

class ProvenanceChain(BaseModel):
    """Collection of source citations for query verification."""
    entries: List[ProvenanceEntry]
