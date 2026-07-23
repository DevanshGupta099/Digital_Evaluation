"""Structured grading schemas.

The evaluation LLM is forced to emit exactly this shape (per rubric point:
mark, evidence line citations, confidence, brief reasoning). A mark may only
be awarded when at least one evidence line index is cited; this invariant is
enforced by validators, not just by the prompt.
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator


class RubricPoint(BaseModel):
    """One sub-point of a question's marking rubric."""

    id: str
    description: str
    max_marks: float = Field(gt=0)
    acceptable_variations: list[str] = Field(default_factory=list)


class Rubric(BaseModel):
    question_number: str
    question_text: str
    model_answer: str
    points: list[RubricPoint]

    @property
    def total_marks(self) -> float:
        return sum(p.max_marks for p in self.points)


class PointStatus(str, Enum):
    PRESENT = "present"
    PARTIAL = "partial"
    ABSENT = "absent"


class PointEvaluation(BaseModel):
    rubric_point_id: str
    status: PointStatus
    marks_awarded: float = Field(ge=0)
    # Global OCR line indices (OCRResult.numbered_lines) grounding this decision.
    evidence_line_indices: list[int] = Field(default_factory=list)
    evidence_quote: str = ""
    confidence: float = Field(ge=0, le=1)
    reasoning: str = ""

    @model_validator(mode="after")
    def _marks_require_evidence(self) -> "PointEvaluation":
        if self.marks_awarded > 0 and not self.evidence_line_indices:
            raise ValueError(
                f"Rubric point {self.rubric_point_id}: marks awarded without cited evidence lines"
            )
        return self


class QuestionEvaluation(BaseModel):
    question_number: str
    point_evaluations: list[PointEvaluation]
    overall_confidence: float = Field(ge=0, le=1)
    examiner_note: str = ""

    @property
    def marks_awarded(self) -> float:
        return sum(p.marks_awarded for p in self.point_evaluations)


class ReviewFlag(BaseModel):
    question_number: str
    reason: str


class GradingResult(BaseModel):
    """Final merged output of the dual-pass evaluation for one question."""

    question_number: str
    evaluation: QuestionEvaluation  # pass-1 evaluation (authoritative until human review)
    second_pass: QuestionEvaluation | None = None
    max_marks: float
    flags: list[ReviewFlag] = Field(default_factory=list)

    @property
    def needs_review(self) -> bool:
        return bool(self.flags)
