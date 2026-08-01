from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional

from app.database.session import get_db
from app.database.models import UserRole, User
from app.auth.dependencies import RequireRole
from app.rubric.schemas import (
    RubricGenerateRequest, RubricItemUpdate, RubricAddendumCreate
)
from app.rubric.service import (
    generate_draft_rubric, update_rubric_item, approve_rubric_version,
    clone_rubric_version, create_addendum, clone_rubric_for_offering
)

router = APIRouter(prefix="/rubric", tags=["rubric"])

class ApproveRequest(BaseModel):
    approver: str

@router.post("/generate")
async def draft_rubric(
    request: RubricGenerateRequest, 
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequireRole([UserRole.admin, UserRole.exam_coordinator]))
):
    """Generates a structured grading rubric draft using Gemini 1.5 Pro."""
    return await generate_draft_rubric(db, request)

@router.put("/items/{item_id}")
async def update_item(
    item_id: str, 
    request: RubricItemUpdate, 
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequireRole([UserRole.admin, UserRole.exam_coordinator]))
):
    """Updates a draft rubric item. Rejects mutation of marks if locked."""
    return await update_rubric_item(db, item_id, request)

@router.post("/versions/{version_id}/approve")
async def approve_rubric(
    version_id: str, 
    request: ApproveRequest, 
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequireRole([UserRole.admin, UserRole.exam_coordinator]))
):
    """Approves a draft rubric, setting status to locked and enabling strict immutability."""
    return await approve_rubric_version(db, version_id, request.approver)

@router.post("/versions/{version_id}/clone")
async def clone_rubric(
    version_id: str, 
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequireRole([UserRole.admin, UserRole.exam_coordinator]))
):
    """Clones a locked rubric into a new draft version for editing."""
    return await clone_rubric_version(db, version_id)

@router.post("/items/{item_id}/addendum")
async def add_rubric_addendum(
    item_id: str, 
    request: RubricAddendumCreate, 
    bg_tasks: BackgroundTasks, 
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequireRole([UserRole.admin, UserRole.exam_coordinator]))
):
    """Adds an addendum mid-flight, and triggers a background check to flag affected scripts."""
    return await create_addendum(db, item_id, request, bg_tasks)

from app.database.models import ClassOffering, QuestionPaper, RubricVersion, RubricStatus
from sqlalchemy import select

@router.get("/subject/{subject_id}")
async def get_subject_rubrics(
    subject_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequireRole([UserRole.admin, UserRole.exam_coordinator]))
):
    """Fetches previously locked rubrics for a given subject."""
    query = (
        select(RubricVersion, ClassOffering)
        .join(QuestionPaper, RubricVersion.question_paper_id == QuestionPaper.id)
        .join(ClassOffering, QuestionPaper.class_offering_id == ClassOffering.id)
        .where(
            ClassOffering.subject_id == subject_id,
            RubricVersion.status == RubricStatus.locked
        )
        .order_by(RubricVersion.created_at.desc())
    )
    result = await db.execute(query)
    rows = result.all()
    
    return [
        {
            "rubric_version_id": rv.id,
            "version_number": rv.version_number,
            "created_at": rv.created_at,
            "class_offering_id": co.id
        }
        for rv, co in rows
    ]

@router.post("/offerings/{class_offering_id}/clone/{previous_version_id}")
async def clone_rubric_to_offering(
    class_offering_id: str,
    previous_version_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequireRole([UserRole.admin, UserRole.exam_coordinator]))
):
    """Clones a locked rubric into a new draft for the given offering."""
    return await clone_rubric_for_offering(db, previous_version_id, class_offering_id)
