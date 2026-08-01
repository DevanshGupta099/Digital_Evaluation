from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.database.session import get_db
from app.database.models import UserRole, User
from app.auth.dependencies import RequireRole
from app.review.schemas import UnifiedQueueResponse, ResolveFlagRequest, ReviewFlagResponse
from app.review.service import get_review_queue, resolve_flag, reconcile_evaluations

router = APIRouter(prefix="/review", tags=["review"])

@router.post("/reconcile/{answer_script_id}")
async def trigger_reconciliation(answer_script_id: str, db: AsyncSession = Depends(get_db)):
    """
    Triggers the variance check and status computation for a graded script.
    """
    await reconcile_evaluations(db, answer_script_id)
    return {"status": "success", "message": "Reconciliation completed"}

@router.get("/queue/{class_offering_id}", response_model=UnifiedQueueResponse)
async def fetch_unified_queue(class_offering_id: str, db: AsyncSession = Depends(get_db)):
    """
    Fetches the unified queue of open flags for a class offering.
    """
    flags = await get_review_queue(db, class_offering_id)
    return UnifiedQueueResponse(class_offering_id=class_offering_id, flags=flags)

@router.post("/resolve/{flag_id}")
async def mark_flag_resolved(
    flag_id: str, 
    request: ResolveFlagRequest, 
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequireRole([UserRole.admin, UserRole.evaluator]))
):
    """
    Resolves a specific flag and re-evaluates the parent script's status.
    """
    new_status = await resolve_flag(db, flag_id, request.resolver_name, request.notes)
    return {
        "status": "success", 
        "message": "Flag resolved",
        "new_script_status": new_status
    }

from app.review.schemas import ScriptDetailResponse, OverrideSubmitRequest
from app.review.service import get_script_full_detail, submit_human_override, finalize_script

@router.get("/scripts/{script_id}", response_model=ScriptDetailResponse)
async def fetch_script_full_detail(script_id: str, db: AsyncSession = Depends(get_db)):
    """
    Fetches the full detail for a script, returning the ScriptDetailResponse.
    """
    return await get_script_full_detail(db, script_id)

@router.post("/evaluations/{run_id}/override")
async def handle_submit_human_override(
    run_id: str, 
    request: OverrideSubmitRequest, 
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequireRole([UserRole.admin, UserRole.evaluator]))
):
    """
    Endpoint to submit a human override for an evaluation run.
    """
    return await submit_human_override(db, run_id, request)

@router.post("/scripts/{script_id}/finalize")
async def handle_finalize_script(
    script_id: str, 
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequireRole([UserRole.admin, UserRole.evaluator]))
):
    """
    Endpoint to manually finalize a script.
    """
    return await finalize_script(db, script_id)

from app.review.schemas import BulkAcceptRequest, PeerComparisonResponse
from app.review.service import bulk_accept_evaluations, get_peer_comparisons

@router.post("/scripts/{script_id}/bulk-accept")
async def handle_bulk_accept(
    script_id: str,
    request: BulkAcceptRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequireRole([UserRole.admin, UserRole.evaluator]))
):
    """
    Bulk accept evaluations where models agree and confidence is above a threshold.
    """
    return await bulk_accept_evaluations(db, script_id, request)

@router.get("/peer-comparison/{offering_id}", response_model=PeerComparisonResponse)
async def fetch_peer_comparisons(
    offering_id: str,
    question_number: str,
    subpart_id: str = None,
    exclude_script_id: str = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequireRole([UserRole.admin, UserRole.evaluator]))
):
    """
    Fetch 2-3 other students' answers and marks for peer comparison.
    """
    return await get_peer_comparisons(db, offering_id, question_number, subpart_id, exclude_script_id)

