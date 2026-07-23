from __future__ import annotations

import os

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import settings
from ..models import EvaluationRecord, HumanReview, QuestionBankEntry, Report, Script, get_session
from ..models.db import SessionLocal
from ..pipeline import process_script
from ..schemas.grading import RubricPoint

router = APIRouter()


# ---- Question bank (rubrics) ----

class RubricUpload(BaseModel):
    exam_id: str = "default"
    question_number: str
    question_text: str
    model_answer: str
    points: list[RubricPoint]
    calibration_examples: list[dict] = []


@router.post("/rubrics")
def create_rubric(payload: RubricUpload, session: Session = Depends(get_session)):
    entry = QuestionBankEntry(
        exam_id=payload.exam_id,
        question_number=payload.question_number,
        question_text=payload.question_text,
        model_answer=payload.model_answer,
        rubric_points=[p.model_dump() for p in payload.points],
        calibration_examples=payload.calibration_examples,
    )
    session.add(entry)
    session.commit()
    return {"id": entry.id}


@router.get("/rubrics")
def list_rubrics(exam_id: str = "default", session: Session = Depends(get_session)):
    entries = session.query(QuestionBankEntry).filter_by(exam_id=exam_id).all()
    return [
        {
            "id": e.id,
            "question_number": e.question_number,
            "question_text": e.question_text,
            "model_answer": e.model_answer,
            "points": e.rubric_points,
        }
        for e in entries
    ]


# ---- Scripts (upload + pipeline) ----

@router.post("/scripts")
async def upload_script(
    file: UploadFile,
    background: BackgroundTasks,
    exam_id: str = "default",
    student_name: str = "",
    session: Session = Depends(get_session),
):
    os.makedirs(settings.storage_dir, exist_ok=True)
    data = await file.read()
    script = Script(student_name=student_name, original_filename=file.filename or "upload.pdf",
                    original_path="")
    session.add(script)
    session.flush()
    original_path = os.path.join(settings.storage_dir, f"{script.id}_original_{script.original_filename}")
    with open(original_path, "wb") as fh:
        fh.write(data)
    script.original_path = original_path
    session.commit()

    background.add_task(_run_pipeline, script.id, exam_id)
    return {"id": script.id, "status": script.status}


def _run_pipeline(script_id: str, exam_id: str) -> None:
    session = SessionLocal()
    try:
        process_script(script_id, exam_id, session)
    finally:
        session.close()


@router.get("/scripts")
def list_scripts(session: Session = Depends(get_session)):
    scripts = session.query(Script).order_by(Script.created_at.desc()).all()
    return [
        {"id": s.id, "student_name": s.student_name, "filename": s.original_filename,
         "status": s.status, "error": s.error}
        for s in scripts
    ]


@router.get("/scripts/{script_id}")
def get_script(script_id: str, session: Session = Depends(get_session)):
    script = session.get(Script, script_id)
    if script is None:
        raise HTTPException(404, "script not found")
    report = session.query(Report).filter_by(script_id=script_id).first()
    evaluations = session.query(EvaluationRecord).filter_by(script_id=script_id).all()
    return {
        "id": script.id,
        "student_name": script.student_name,
        "status": script.status,
        "error": script.error,
        "summary": report.summary if report else None,
        "evaluations": [
            {
                "id": ev.id,
                "question_number": ev.question_number,
                "marks_awarded": ev.marks_awarded,
                "max_marks": ev.max_marks,
                "confidence": ev.overall_confidence,
                "pass1": ev.pass1,
                "pass2": ev.pass2,
                "flags": ev.flags,
                "review": (
                    {"action": ev.review.action, "final_marks": ev.review.final_marks,
                     "reviewer": ev.review.reviewer, "comment": ev.review.comment}
                    if ev.review else None
                ),
            }
            for ev in evaluations
        ],
    }


@router.get("/scripts/{script_id}/annotated.pdf")
def get_annotated_pdf(script_id: str, session: Session = Depends(get_session)):
    report = session.query(Report).filter_by(script_id=script_id).first()
    if report is None or not os.path.exists(report.annotated_pdf_path):
        raise HTTPException(404, "annotated PDF not ready")
    return FileResponse(report.annotated_pdf_path, media_type="application/pdf")


@router.get("/scripts/{script_id}/original.pdf")
def get_original_pdf(script_id: str, session: Session = Depends(get_session)):
    script = session.get(Script, script_id)
    if script is None or not os.path.exists(script.normalized_pdf_path or ""):
        raise HTTPException(404, "original PDF not found")
    return FileResponse(script.normalized_pdf_path, media_type="application/pdf")


# ---- Stage 6: human review ----

class ReviewDecision(BaseModel):
    action: str  # "accepted" | "overridden"
    final_marks: float
    reviewer: str = ""
    comment: str = ""


@router.post("/evaluations/{evaluation_id}/review")
def review_evaluation(evaluation_id: str, decision: ReviewDecision,
                      session: Session = Depends(get_session)):
    evaluation = session.get(EvaluationRecord, evaluation_id)
    if evaluation is None:
        raise HTTPException(404, "evaluation not found")
    if decision.action not in ("accepted", "overridden"):
        raise HTTPException(400, "action must be 'accepted' or 'overridden'")
    if evaluation.review is not None:
        raise HTTPException(409, "evaluation already reviewed")
    session.add(HumanReview(
        evaluation_id=evaluation.id,
        reviewer=decision.reviewer,
        action=decision.action,
        final_marks=decision.final_marks,
        comment=decision.comment,
    ))
    session.commit()

    script = session.get(Script, evaluation.script_id)
    remaining = [
        ev for ev in session.query(EvaluationRecord).filter_by(script_id=evaluation.script_id)
        if ev.review is None
    ]
    if script and not remaining:
        script.status = "finalized"
        session.commit()
    return {"ok": True, "script_status": script.status if script else None}
