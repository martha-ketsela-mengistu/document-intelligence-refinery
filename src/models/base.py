from typing import Annotated, List, Tuple
from pydantic import BaseModel, Field, field_validator

class BoundingBox(BaseModel):
    """Bounding Box: [x0, y0, x1, y1] in PDF points."""
    x0: float = Field(ge=0.0)
    y0: float = Field(ge=0.0)
    x1: float = Field(ge=0.0)
    y1: float = Field(ge=0.0)

    @field_validator('x1')
    @classmethod
    def x1_greater_than_x0(cls, v: float, info):
        if 'x0' in info.data and v < info.data['x0'] - 1e-5:
            raise ValueError('x1 must be greater than or equal to x0')
        return max(v, info.data.get('x0', v))

    @field_validator('y1')
    @classmethod
    def y1_greater_than_y0(cls, v: float, info):
        if 'y0' in info.data and v < info.data['y0'] - 1e-5:
            raise ValueError('y1 must be greater than or equal to y0')
        return max(v, info.data.get('y0', v))

    def to_tuple(self) -> Tuple[float, float, float, float]:
        return (self.x0, self.y0, self.x1, self.y1)

class ProvenanceBase(BaseModel):
    """Base provenance information for extracted content."""
    document_id: str
    page_number: int = Field(ge=1)
    bbox: BoundingBox
    content_hash: str
