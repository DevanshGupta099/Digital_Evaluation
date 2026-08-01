from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.database.session import get_db
from app.grading.schemas import GradingJobRequest
from app.grading.service import grade_question_sync

# We'll use a simple dict or response model for EvaluationRun if needed, but for MVP returning dict is fine.
router = APIRouter(prefix="/grading", tags=["grading"])

@router.post("/run-sync")
async def trigger_grading_sync(request: GradingJobRequest, db: AsyncSession = Depends(get_db)):
    """
    Synchronously triggers grading for a specific question on an answer script.
    Fires off requests to both Claude and Gemini concurrently and saves the runs.
    """
    runs = await grade_question_sync(db, request)
    return {
        "status": "success",
        "evaluation_runs": [
            {
                "id": r.id,
                "run_type": r.run_type,
                "marks_awarded": r.marks_awarded,
                "reasoning": r.reasoning,
                "evidence_quote": r.evidence_quote
            } for r in runs
        ]
    }
