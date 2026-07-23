"""Versioned, separately-stored records for full traceability:
raw scripts, OCR segments (text + bbox + confidence), question bank (rubrics),
evaluations (both passes + evidence + flags), human reviews (overrides), and
final reports. Nothing is stored as one opaque blob.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Float, ForeignKey, String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Script(Base):
    __tablename__ = "scripts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    student_name: Mapped[str] = mapped_column(String(200), default="")
    original_filename: Mapped[str] = mapped_column(String(400))
    original_path: Mapped[str] = mapped_column(String(600))  # untouched upload
    normalized_pdf_path: Mapped[str] = mapped_column(String(600), default="")
    status: Mapped[str] = mapped_column(String(40), default="uploaded")
    # uploaded -> ocr_done -> segmented -> graded -> annotated -> in_review -> finalized
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    segments: Mapped[list["OCRSegmentRecord"]] = relationship(back_populates="script")
    evaluations: Mapped[list["EvaluationRecord"]] = relationship(back_populates="script")


class OCRSegmentRecord(Base):
    __tablename__ = "ocr_segments"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    script_id: Mapped[str] = mapped_column(ForeignKey("scripts.id"))
    page_number: Mapped[int] = mapped_column()
    global_line_index: Mapped[int] = mapped_column()
    text: Mapped[str] = mapped_column(Text)
    bbox: Mapped[dict] = mapped_column(JSON)  # {x0,y0,x1,y1} image-pixel space
    confidence: Mapped[float] = mapped_column(Float)
    question_number: Mapped[str | None] = mapped_column(String(20), nullable=True)

    script: Mapped[Script] = relationship(back_populates="segments")


class QuestionBankEntry(Base):
    __tablename__ = "question_bank"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    exam_id: Mapped[str] = mapped_column(String(100), default="default", index=True)
    question_number: Mapped[str] = mapped_column(String(20))
    question_text: Mapped[str] = mapped_column(Text)
    model_answer: Mapped[str] = mapped_column(Text)
    rubric_points: Mapped[list] = mapped_column(JSON)  # list[RubricPoint dict]
    calibration_examples: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class EvaluationRecord(Base):
    __tablename__ = "evaluations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    script_id: Mapped[str] = mapped_column(ForeignKey("scripts.id"))
    question_number: Mapped[str] = mapped_column(String(20))
    max_marks: Mapped[float] = mapped_column(Float)
    marks_awarded: Mapped[float] = mapped_column(Float)
    pass1: Mapped[dict] = mapped_column(JSON)  # QuestionEvaluation dict
    pass2: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    flags: Mapped[list] = mapped_column(JSON, default=list)
    overall_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    script: Mapped[Script] = relationship(back_populates="evaluations")
    review: Mapped["HumanReview | None"] = relationship(back_populates="evaluation")


class HumanReview(Base):
    __tablename__ = "human_reviews"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    evaluation_id: Mapped[str] = mapped_column(ForeignKey("evaluations.id"), unique=True)
    reviewer: Mapped[str] = mapped_column(String(200), default="")
    action: Mapped[str] = mapped_column(String(20))  # accepted | overridden
    final_marks: Mapped[float] = mapped_column(Float)
    comment: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    evaluation: Mapped[EvaluationRecord] = relationship(back_populates="review")


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    script_id: Mapped[str] = mapped_column(ForeignKey("scripts.id"))
    annotated_pdf_path: Mapped[str] = mapped_column(String(600))
    summary: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
