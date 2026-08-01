from pydantic import BaseModel, Field
from typing import List, Optional

class NormalizedOCRWord(BaseModel):
    text: str
    bbox: List[float] = Field(..., min_length=4, max_length=4, description="[x, y, w, h] in pixels")
    line_id: Optional[str] = None
    confidence: float = Field(..., ge=0.0, le=1.0)

class NormalizedOCRResponse(BaseModel):
    words: List[NormalizedOCRWord]
    reading_order: Optional[List[str]] = Field(None, description="Ordered list of line_ids or word_ids")

class UploadResponse(BaseModel):
    answer_script_id: str
    status: str
    message: str
