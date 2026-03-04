from typing import Annotated, List, Tuple
from pydantic import BaseModel, Field

# Bounding Box: [x0, y0, x1, y1] in PDF points
BoundingBox = Annotated[Tuple[float, float, float, float], Field(min_length=4, max_length=4)]

class ProvenanceBase(BaseModel):
    """Base provenance information for extracted content."""
    document_id: str
    page_number: int
    bbox: BoundingBox
    content_hash: str
