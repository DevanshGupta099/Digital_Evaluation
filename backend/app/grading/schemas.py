from pydantic import BaseModel, create_model, Field
from typing import List, Type, Dict, Any
from enum import Enum

class GradingJobRequest(BaseModel):
    answer_script_id: str
    question_number: str

def build_grading_schema(allowed_increments: List[float]) -> Type[BaseModel]:
    """
    Dynamically generates a Pydantic model where `marks_awarded` must be 
    exactly one of the values in `allowed_increments`.
    We generate a dynamic Enum so that the JSON schema strictly enforces it.
    """
    # Create a dynamic Enum from the float values
    # e.g., Enum('Marks', {'M_0_0': 0.0, 'M_0_5': 0.5})
    enum_dict = {f"M_{str(val).replace('.', '_')}": val for val in allowed_increments}
    MarksEnum = Enum('Marks', enum_dict)
    
    return create_model(
        'GradingResponse',
        marks_awarded=(MarksEnum, Field(..., description="The exact marks awarded. Must be from the allowed list.")),
        reasoning=(str, Field(..., description="Brief reasoning for why these marks were awarded.")),
        evidence_quote=(str, Field(..., description="Exact substring from the OCR text relied upon for this grade."))
    )
