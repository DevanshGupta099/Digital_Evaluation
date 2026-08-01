from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class ResolveFlagRequest(BaseModel):
    resolver_name: str
    notes: Optional[str] = None
    # If resolving high_variance, we might need to specify the final marks awarded here.
    # We can add that later if needed. For now just standard resolution.

class ReviewFlagResponse(BaseModel):
    id: str
    answer_script_id: str
    question_number: Optional[str] = None
    subpart_id: Optional[str] = None
    flag_type: str
    status: str
    notes: Optional[str] = None
    priority_tier: int = 3 # Added in service layer
    
class UnifiedQueueResponse(BaseModel):
    class_offering_id: str
    flags: List[ReviewFlagResponse]

class OverrideSubmitRequest(BaseModel):
    action: str
    final_marks: float
    reviewer: str
    comment: Optional[str] = None

class PointEvaluationSchema(BaseModel):
    rubric_point_id: str
    marks_awarded: float
    evidence_quote: Optional[str] = None
    reasoning: Optional[str] = None

class ModelPassResponse(BaseModel):
    point_evaluations: List[PointEvaluationSchema]

class OverrideDetail(BaseModel):
    action: str
    reviewer: str
    final_marks: float
    comment: Optional[str] = None

class QuestionEvaluationResponse(BaseModel):
    id: str
    question_number: str
    subpart_id: Optional[str] = None
    max_marks: float
    marks_awarded: float
    confidence: float
    flags: List[dict] = Field(default_factory=list)
    pass1: Optional[ModelPassResponse] = None
    pass2: Optional[ModelPassResponse] = None
    review: Optional[OverrideDetail] = None
    allowed_increments: List[float] = Field(default_factory=list)

class ScriptDetailResponse(BaseModel):
    id: str
    student_name: Optional[str] = None
    status: str
    evaluations: List[QuestionEvaluationResponse]
    summary: dict = Field(default_factory=dict)

class BulkAcceptRequest(BaseModel):
    reviewer: str
    confidence_threshold: float = 0.90

class PeerComparisonItem(BaseModel):
    script_id: str
    marks_awarded: float
    evidence_quote: Optional[str] = None

class PeerComparisonResponse(BaseModel):
    peers: List[PeerComparisonItem]
