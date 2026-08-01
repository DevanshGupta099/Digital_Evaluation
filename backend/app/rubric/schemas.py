from pydantic import BaseModel, Field
from typing import List, Optional

class RubricItemDraft(BaseModel):
    question_number: str = Field(..., description="The main question number, e.g., 'Q1'.")
    subpart_id: Optional[str] = Field(None, description="The subpart, e.g., 'a', 'b'. Null if it's a whole question.")
    expected_concepts: List[str] = Field(default_factory=list, description="List of expected core concepts.")
    accepted_alternates: List[str] = Field(default_factory=list, description="List of accepted alternative phrasings or valid approaches.")
    max_marks: float = Field(..., description="The maximum marks for this item.")
    allowed_increments: List[float] = Field(..., description="List of allowed mark increments, e.g., [0, 0.5, 1.0].")
    example_full: Optional[str] = Field(None, description="Example of an answer deserving full marks.")
    example_partial: Optional[str] = Field(None, description="Example of an answer deserving partial marks.")

class RubricGenerationResponse(BaseModel):
    items: List[RubricItemDraft]

class RubricGenerateRequest(BaseModel):
    class_offering_id: str

class RubricItemUpdate(BaseModel):
    expected_concepts: Optional[List[str]] = None
    accepted_alternates: Optional[List[str]] = None
    max_marks: Optional[float] = None
    allowed_increments: Optional[List[float]] = None
    example_full: Optional[str] = None
    example_partial: Optional[str] = None

class RubricAddendumCreate(BaseModel):
    added_text: str
    added_by: str
