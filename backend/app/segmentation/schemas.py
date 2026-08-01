from pydantic import BaseModel, Field
from typing import List

class SegmentationMapping(BaseModel):
    question_number: str = Field(..., description="The question number being answered.")
    pages: List[int] = Field(..., description="List of page numbers where this question is answered. E.g., [1, 3] for non-linear continuation.")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0.")

class OrphanedSegment(BaseModel):
    page: int = Field(..., description="The page number where the orphaned content was found.")
    text_snippet: str = Field(..., description="A snippet of the text that could not be mapped confidently.")
    reason: str = Field(..., description="Reason why this could not be mapped to a question.")

class SegmentationResponse(BaseModel):
    question_mappings: List[SegmentationMapping]
    orphaned_segments: List[OrphanedSegment]
    
class SegmentationRunResponse(BaseModel):
    segmentation_run_id: str
    status: str
    message: str
    flags_generated: int
