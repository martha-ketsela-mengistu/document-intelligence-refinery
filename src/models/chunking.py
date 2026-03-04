from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field
from .base import BoundingBox

class ChunkType(str, Enum):
    TEXT = "text"
    TABLE = "table"
    FIGURE = "figure"
    LIST = "list"
    HEADING = "heading"

class LDU(BaseModel):
    """Logical Document Unit: a semantically coherent, self-contained unit."""
    id: str
    content: str
    chunk_type: ChunkType
    page_refs: List[int]
    bbox: BoundingBox
    parent_section: Optional[str] = None
    token_count: int
    content_hash: str
    metadata: Optional[dict] = Field(default_factory=dict)
