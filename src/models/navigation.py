from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel, Field

class PageIndexNode(BaseModel):
    """A node in the hierarchical PageIndex tree."""
    title: str
    page_start: int
    page_end: int
    summary: str
    data_types_present: List[str] = Field(default_factory=list, description="e.g. ['tables', 'figures', 'equations']")
    key_entities: List[str] = Field(default_factory=list)
    child_sections: List[PageIndexNode] = Field(default_factory=list)

class PageIndex(BaseModel):
    """The full PageIndex navigation structure for a document."""
    document_id: str
    root: PageIndexNode
