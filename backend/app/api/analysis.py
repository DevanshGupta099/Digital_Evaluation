from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from ..models import QuestionBankEntry, get_session
from ..ocr.extractor import extract_rubric_from_documents

router = APIRouter()

@router.post("/analyze/materials")
async def analyze_materials(
    question_paper: UploadFile = File(...),
    answer_key: UploadFile = File(...),
    exam_id: str = Form(None),
    session: Session = Depends(get_session)
):
    """
    Accepts a question paper and answer key (images/PDFs), 
    extracts the structured rubric, and saves it to the DB.
    Returns the exam_id.
    """
    if not exam_id:
        exam_id = str(uuid.uuid4())[:8]

    qp_data = await question_paper.read()
    ak_data = await answer_key.read()

    qp_mime = question_paper.content_type or "application/pdf"
    ak_mime = answer_key.content_type or "application/pdf"

    try:
        extracted = extract_rubric_from_documents(
            question_paper_mime_type=qp_mime,
            question_paper_data=qp_data,
            answer_key_mime_type=ak_mime,
            answer_key_data=ak_data
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    # Save to database
    for q in extracted.questions:
        entry = QuestionBankEntry(
            exam_id=exam_id,
            question_number=q.question_number,
            question_text=q.question_text,
            model_answer=q.model_answer,
            rubric_points=[p.model_dump() for p in q.points],
            calibration_examples=[],
        )
        session.add(entry)
    
    session.commit()
    
    return {
        "exam_id": exam_id,
        "questions_extracted": len(extracted.questions),
        "rubrics": [
            {
                "question_number": q.question_number,
                "question_text": q.question_text,
                "points": q.points
            } for q in extracted.questions
        ]
    }
