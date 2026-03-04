from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field

class OriginType(str, Enum):
    NATIVE_DIGITAL = "native_digital"
    SCANNED_IMAGE = "scanned_image"
    MIXED = "mixed"
    FORM_FILLABLE = "form_fillable"

class LayoutComplexity(str, Enum):
    SINGLE_COLUMN = "single_column"
    MULTI_COLUMN = "multi_column"
    TABLE_HEAVY = "table_heavy"
    FIGURE_HEAVY = "figure_heavy"
    MIXED = "mixed"

class DomainHint(str, Enum):
    FINANCIAL = "financial"
    LEGAL = "legal"
    TECHNICAL = "technical"
    MEDICAL = "medical"
    GENERAL = "general"

class ExtractionCostTier(str, Enum):
    FAST_TEXT_SUFFICIENT = "fast_text_sufficient"
    NEEDS_LAYOUT_MODEL = "needs_layout_model"
    NEEDS_VISION_MODEL = "needs_vision_model"

class LanguageInfo(BaseModel):
    code: str
    confidence: float = Field(ge=0.0, le=1.0)

class PageProfile(BaseModel):
    """Classification metadata for a single page."""
    page_number: int
    origin_type: OriginType
    layout_complexity: LayoutComplexity
    character_density: float = Field(description="Characters per page area")
    image_area_ratio: float = Field(ge=0.0, le=1.0)
    has_font_metadata: bool
    estimated_extraction_cost: ExtractionCostTier
    metadata: Optional[dict] = Field(default_factory=dict)

class DocumentProfile(BaseModel):
    """Classification metadata for a document, produced by the Triage Agent."""
    document_id: str
    overall_origin_type: OriginType
    overall_layout_complexity: LayoutComplexity
    overall_estimated_cost: ExtractionCostTier
    domain_hint: DomainHint
    language: LanguageInfo
    pages: List[PageProfile] = Field(default_factory=list)
    metadata: Optional[dict] = Field(default_factory=dict)
