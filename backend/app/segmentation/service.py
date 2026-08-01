import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from fastapi import HTTPException

from app.database.models import (
    AnswerScript, OCRPage, RubricVersion, RubricItem, RubricStatus,
    SegmentationRun, ReviewFlag, FlagType, AnswerScriptStatus
)
from app.segmentation.llm import predict_segmentation
from app.segmentation.schemas import SegmentationRunResponse

logger = logging.getLogger(__name__)

async def run_segmentation_pipeline(db: AsyncSession, answer_script_id: str) -> SegmentationRunResponse:
    # 1. Fetch the Answer Script
    script = await db.get(AnswerScript, answer_script_id)
    if not script:
        raise HTTPException(status_code=404, detail="Answer script not found")
        
    if script.status == AnswerScriptStatus.uploaded:
        raise HTTPException(status_code=400, detail="Script OCR is not completed yet.")

    # 2. Fetch OCR Pages
    result = await db.execute(
        select(OCRPage)
        .where(OCRPage.answer_script_id == answer_script_id)
        .order_by(OCRPage.page_number)
    )
    pages = result.scalars().all()
    if not pages:
        raise HTTPException(status_code=404, detail="No OCR pages found for this script.")

    # 3. Fetch Active Rubric items
    # Typically, a rubric is linked to the QuestionPaper which is linked to the ClassOffering.
    # For simplicity, we find the active rubric for the script's class_offering_id.
    from app.database.models import QuestionPaper
    qp_result = await db.execute(
        select(QuestionPaper).where(QuestionPaper.class_offering_id == script.class_offering_id)
    )
    question_paper = qp_result.scalar_one_or_none()
    if not question_paper:
        raise HTTPException(status_code=404, detail="No question paper mapped to this class offering.")

    rubric_result = await db.execute(
        select(RubricVersion)
        .where(RubricVersion.question_paper_id == question_paper.id)
        .where(RubricVersion.status == RubricStatus.locked) # Must be locked to grade/segment
        .order_by(RubricVersion.version_number.desc())
    )
    active_rubric = rubric_result.scalars().first()
    if not active_rubric:
        raise HTTPException(status_code=404, detail="No locked rubric version found.")

    items_result = await db.execute(
        select(RubricItem).where(RubricItem.rubric_version_id == active_rubric.id)
    )
    rubric_items = items_result.scalars().all()
    expected_questions = list(set([item.question_number for item in rubric_items]))
    
    if not expected_questions:
        raise HTTPException(status_code=400, detail="Rubric has no questions defined.")

    # 4. Assemble OCR Text Stream
    text_stream = []
    for page in pages:
        text_stream.append(f"--- PAGE {page.page_number} ---")
        # Extract text from the normalized OCR JSON
        # Assuming OCR JSON has "words": [{"text": "word", ...}]
        words_data = page.ocr_json.get("words", [])
        page_text = " ".join([w.get("text", "") for w in words_data])
        text_stream.append(page_text)
        
    full_text = "\n".join(text_stream)

    # 5. Call LLM
    try:
        segmentation_response = await predict_segmentation(full_text, expected_questions)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM segmentation failed: {str(e)}")

    flags_generated = 0

    # 6. Pre-flight sanity check
    mapped_questions = [m.question_number for m in segmentation_response.question_mappings]
    unique_mapped_questions = set(mapped_questions)
    
    mapping_ratio = len(unique_mapped_questions) / len(expected_questions) if expected_questions else 0
    if mapping_ratio < 0.3:
        # Flag and halt
        flag = ReviewFlag(
            answer_script_id=answer_script_id,
            flag_type=FlagType.possible_wrong_upload,
            notes=f"Only {mapping_ratio*100:.1f}% of questions mapped. Pipeline halted to prevent wasted grading passes."
        )
        db.add(flag)
        await db.commit()
        return SegmentationRunResponse(
            segmentation_run_id="",
            status="halted",
            message="Possible wrong upload. Review flag created.",
            flags_generated=1
        )

    # 7. Create Review Flags for specific issues
    
    # 7a. Uncertain segmentation (Mapping exists, but confidence < 0.7)
    for mapping in segmentation_response.question_mappings:
        if mapping.confidence < 0.7:
            flag = ReviewFlag(
                answer_script_id=answer_script_id,
                question_number=mapping.question_number,
                flag_type=FlagType.uncertain_segmentation,
                notes=f"Low confidence ({mapping.confidence}) for mapping pages {mapping.pages}"
            )
            db.add(flag)
            flags_generated += 1

    # 7b. Orphaned Content mapping (Question has zero mapped pages)
    unmapped_questions = set(expected_questions) - unique_mapped_questions
    for q_num in unmapped_questions:
        flag = ReviewFlag(
            answer_script_id=answer_script_id,
            question_number=q_num,
            flag_type=FlagType.orphaned_content,
            notes="check orphaned content — may be misfiled"
        )
        db.add(flag)
        flags_generated += 1

    # 8. Store the Segmentation Run
    seg_run = SegmentationRun(
        answer_script_id=answer_script_id,
        rubric_version_id=active_rubric.id,
        mappings=[m.model_dump() for m in segmentation_response.question_mappings],
        orphaned_content=[o.model_dump() for o in segmentation_response.orphaned_segments]
    )
    db.add(seg_run)
    
    # 9. Update Script Status
    script.status = AnswerScriptStatus.segmented
    db.add(script)
    
    await db.commit()
    await db.refresh(seg_run)
    
    return SegmentationRunResponse(
        segmentation_run_id=seg_run.id,
        status="success",
        message="Segmentation completed successfully.",
        flags_generated=flags_generated
    )
