import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, BackgroundTasks

from app.database.models import (
    QuestionPaper, RubricVersion, RubricItem, RubricStatus,
    RubricAddendum, EvaluationRun, AnswerScript, SegmentationRun,
    ReviewFlag, FlagType
)
from app.rubric.llm import generate_rubric_draft_llm
from app.rubric.schemas import RubricGenerateRequest, RubricItemUpdate, RubricAddendumCreate

logger = logging.getLogger(__name__)

import fitz

def extract_pdf_text(filepath: str) -> str:
    try:
        doc = fitz.open(filepath)
        text = "\n".join(page.get_text() for page in doc)
        doc.close()
        return text
    except Exception:
        return ""

async def generate_draft_rubric(db: AsyncSession, request: RubricGenerateRequest) -> RubricVersion:
    """Calls the LLM to draft a rubric and saves it as version 1 (or increments)."""
    from app.database.models import AnswerKey
    qp = (await db.execute(select(QuestionPaper).where(QuestionPaper.class_offering_id == request.class_offering_id))).scalar_one_or_none()
    ak = (await db.execute(select(AnswerKey).where(AnswerKey.class_offering_id == request.class_offering_id))).scalar_one_or_none()
    
    if not qp or not ak:
        raise HTTPException(status_code=400, detail="Both Question Paper and Answer Key must be uploaded first.")
        
    # Check for existing versions to increment version number
    result = await db.execute(
        select(RubricVersion)
        .where(RubricVersion.question_paper_id == qp.id)
        .order_by(RubricVersion.version_number.desc())
    )
    latest_version = result.scalars().first()
    new_version_number = 1 if not latest_version else latest_version.version_number + 1
    
    qp_text = extract_pdf_text(qp.original_file_path)
    ak_text = extract_pdf_text(ak.original_file_path)
    
    # Call LLM
    try:
        draft = await generate_rubric_draft_llm(qp_text, ak_text)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to generate rubric draft")
        
    rv = RubricVersion(
        question_paper_id=qp.id,
        version_number=new_version_number,
        status=RubricStatus.draft
    )
    db.add(rv)
    await db.commit()
    await db.refresh(rv)
    
    # Insert items
    for item_draft in draft.items:
        ri = RubricItem(
            rubric_version_id=rv.id,
            question_number=item_draft.question_number,
            subpart_id=item_draft.subpart_id,
            max_marks=item_draft.max_marks,
            allowed_increments=item_draft.allowed_increments,
            expected_concepts=item_draft.expected_concepts,
            accepted_alternates=item_draft.accepted_alternates,
            example_full=item_draft.example_full,
            example_partial=item_draft.example_partial
        )
        db.add(ri)
    
    await db.commit()
    return rv

async def update_rubric_item(db: AsyncSession, item_id: str, update_data: RubricItemUpdate) -> RubricItem:
    """Updates a rubric item. If locked, rejects mutations to marks/increments."""
    item = await db.get(RubricItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Rubric item not found")
        
    rv = await db.get(RubricVersion, item.rubric_version_id)
    if rv.status in [RubricStatus.locked, RubricStatus.approved]:
        # Enforce Immutability Guard
        if update_data.max_marks is not None and update_data.max_marks != item.max_marks:
            raise HTTPException(status_code=403, detail="Cannot modify max_marks on a locked rubric.")
        if update_data.allowed_increments is not None and update_data.allowed_increments != item.allowed_increments:
            raise HTTPException(status_code=403, detail="Cannot modify allowed_increments on a locked rubric.")
            
    # Apply updates
    update_dict = update_data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(item, key, value)
        
    await db.commit()
    await db.refresh(item)
    return item

async def approve_rubric_version(db: AsyncSession, version_id: str, approver: str) -> RubricVersion:
    """Locks the rubric version for grading."""
    rv = await db.get(RubricVersion, version_id)
    if not rv:
        raise HTTPException(status_code=404, detail="Rubric version not found")
        
    if rv.status == RubricStatus.locked:
        return rv
        
    from datetime import datetime, timezone
    rv.status = RubricStatus.locked
    rv.approved_by = approver
    rv.approved_at = datetime.now(timezone.utc)
    
    await db.commit()
    await db.refresh(rv)
    
    # Audit logging
    from app.database.models import AuditLog, QuestionPaper
    qp = await db.get(QuestionPaper, rv.question_paper_id)
    if qp:
        audit = AuditLog(
            class_offering_id=qp.class_offering_id,
            action_type="rubric_locked",
            user_name=approver,
            user_role="unknown", # We can adjust this if needed
            details={"rubric_version_id": rv.id, "version_number": rv.version_number}
        )
        db.add(audit)
        await db.commit()
        
    return rv

async def clone_rubric_version(db: AsyncSession, version_id: str) -> RubricVersion:
    """Clones a locked version into a new draft."""
    old_rv = await db.get(RubricVersion, version_id)
    if not old_rv:
        raise HTTPException(status_code=404, detail="Rubric version not found")
        
    # Get highest version
    result = await db.execute(
        select(RubricVersion)
        .where(RubricVersion.question_paper_id == old_rv.question_paper_id)
        .order_by(RubricVersion.version_number.desc())
    )
    latest_version = result.scalars().first()
    new_version_number = latest_version.version_number + 1
    
    new_rv = RubricVersion(
        question_paper_id=old_rv.question_paper_id,
        version_number=new_version_number,
        status=RubricStatus.draft
    )
    db.add(new_rv)
    await db.commit()
    await db.refresh(new_rv)
    
    # Clone items
    items_res = await db.execute(select(RubricItem).where(RubricItem.rubric_version_id == old_rv.id))
    for old_item in items_res.scalars().all():
        new_item = RubricItem(
            rubric_version_id=new_rv.id,
            question_number=old_item.question_number,
            subpart_id=old_item.subpart_id,
            max_marks=old_item.max_marks,
            allowed_increments=old_item.allowed_increments,
            expected_concepts=old_item.expected_concepts,
            accepted_alternates=old_item.accepted_alternates,
            example_full=old_item.example_full,
            example_partial=old_item.example_partial
        )
        db.add(new_item)
        
    await db.commit()
    return new_rv

async def clone_rubric_for_offering(db: AsyncSession, old_version_id: str, new_offering_id: str) -> RubricVersion:
    """Clones a locked version into a new draft for a different offering."""
    old_rv = await db.get(RubricVersion, old_version_id)
    if not old_rv:
        raise HTTPException(status_code=404, detail="Previous rubric version not found")
        
    new_qp = (await db.execute(select(QuestionPaper).where(QuestionPaper.class_offering_id == new_offering_id))).scalar_one_or_none()
    if not new_qp:
        raise HTTPException(status_code=400, detail="New offering must have a Question Paper uploaded first.")
        
    # Get highest version for the new question paper
    result = await db.execute(
        select(RubricVersion)
        .where(RubricVersion.question_paper_id == new_qp.id)
        .order_by(RubricVersion.version_number.desc())
    )
    latest_version = result.scalars().first()
    new_version_number = latest_version.version_number + 1 if latest_version else 1
    
    new_rv = RubricVersion(
        question_paper_id=new_qp.id,
        version_number=new_version_number,
        status=RubricStatus.draft
    )
    db.add(new_rv)
    await db.commit()
    await db.refresh(new_rv)
    
    # Clone items
    items_res = await db.execute(select(RubricItem).where(RubricItem.rubric_version_id == old_rv.id))
    for old_item in items_res.scalars().all():
        new_item = RubricItem(
            rubric_version_id=new_rv.id,
            question_number=old_item.question_number,
            subpart_id=old_item.subpart_id,
            max_marks=old_item.max_marks,
            allowed_increments=old_item.allowed_increments,
            expected_concepts=old_item.expected_concepts,
            accepted_alternates=old_item.accepted_alternates,
            example_full=old_item.example_full,
            example_partial=old_item.example_partial
        )
        db.add(new_item)
        
    await db.commit()
    return new_rv

async def flag_affected_scripts_task(item_id: str):
    """Background task to flag previously graded scripts after an addendum."""
    from app.database.session import async_session_maker
    async with async_session_maker() as db:
        item = await db.get(RubricItem, item_id)
        if not item:
            return
            
        # Find all answer scripts that used this rubric version and were graded on this question
        # where marks_awarded < item.max_marks.
        
        # We join EvaluationRun -> AnswerScript -> SegmentationRun
        # where SegmentationRun.rubric_version_id == item.rubric_version_id
        query = (
            select(EvaluationRun)
            .join(AnswerScript, AnswerScript.id == EvaluationRun.answer_script_id)
            .join(SegmentationRun, SegmentationRun.answer_script_id == AnswerScript.id)
            .where(SegmentationRun.rubric_version_id == item.rubric_version_id)
            .where(EvaluationRun.question_number == item.question_number)
        )
        if item.subpart_id:
            query = query.where(EvaluationRun.subpart_id == item.subpart_id)
            
        # We only care about scripts that didn't get full marks
        query = query.where(EvaluationRun.marks_awarded < item.max_marks)
        
        result = await db.execute(query)
        affected_runs = result.scalars().all()
        
        for run in affected_runs:
            flag = ReviewFlag(
                answer_script_id=run.answer_script_id,
                question_number=run.question_number,
                subpart_id=run.subpart_id,
                flag_type=FlagType.rubric_addendum_recheck,
                notes="A new addendum was added to the rubric after this was graded. Re-check if the answer now qualifies."
            )
            db.add(flag)
            
        await db.commit()
        logger.info(f"Flagged {len(affected_runs)} scripts for rubric addendum recheck.")

async def create_addendum(db: AsyncSession, item_id: str, request: RubricAddendumCreate, bg_tasks: BackgroundTasks) -> RubricAddendum:
    item = await db.get(RubricItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Rubric item not found")
        
    # Never mutate the item directly silently, create an addendum row
    addendum = RubricAddendum(
        rubric_item_id=item_id,
        added_text=request.added_text,
        added_by=request.added_by
    )
    db.add(addendum)
    await db.commit()
    await db.refresh(addendum)
    
    # Also append to the item's JSON array so future gradings see it easily
    alts = list(item.accepted_alternates) if item.accepted_alternates else []
    if request.added_text not in alts:
        alts.append(request.added_text)
        item.accepted_alternates = alts
        db.add(item)
        await db.commit()
    
    # Trigger background task to flag older scripts
    bg_tasks.add_task(flag_affected_scripts_task, item_id)
    
    # Audit logging
    from app.database.models import RubricVersion, QuestionPaper, AuditLog
    rv = await db.get(RubricVersion, item.rubric_version_id)
    if rv:
        qp = await db.get(QuestionPaper, rv.question_paper_id)
        if qp:
            audit = AuditLog(
                class_offering_id=qp.class_offering_id,
                action_type="rubric_addendum_added",
                user_name=request.added_by,
                user_role="unknown",
                details={
                    "rubric_item_id": item_id,
                    "question_number": item.question_number,
                    "added_text": request.added_text
                }
            )
            db.add(audit)
            await db.commit()
            
    return addendum
