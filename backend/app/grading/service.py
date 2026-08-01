import logging
import asyncio
from typing import Optional, List, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException

from app.database.models import (
    AnswerScript, RubricItem, RubricAddendum,
    SegmentationRun, OCRPage, EvaluationRun, RunType
)
from app.grading.schemas import build_grading_schema, GradingJobRequest
from app.grading.llm import evaluate_with_claude, evaluate_with_gemini

logger = logging.getLogger(__name__)

def _build_prompt(item: RubricItem, addenda: List[RubricAddendum], ocr_text: str) -> str:
    alts = item.accepted_alternates or []
    addenda_texts = [a.added_text for a in addenda]
    all_alts = alts + addenda_texts
    
    return f"""
    You are an expert academic grader. Your task is to evaluate a student's answer against a strict rubric.
    
    QUESTION NUMBER: {item.question_number}
    SUBPART: {item.subpart_id or 'N/A'}
    
    EXPECTED CONCEPTS:
    {chr(10).join(['- ' + c for c in (item.expected_concepts or [])])}
    
    ACCEPTED ALTERNATIVE APPROACHES:
    {chr(10).join(['- ' + c for c in all_alts])}
    
    EXAMPLE FULL MARKS ANSWER:
    {item.example_full or 'N/A'}
    
    EXAMPLE PARTIAL MARKS ANSWER:
    {item.example_partial or 'N/A'}
    
    STUDENT OCR TEXT:
    {ocr_text}
    
    RULES:
    1. If part of the answer appears crossed out, cancelled, or struck through, ignore it as the student's final answer.
    2. If the sub-part has no corresponding content at all in the text (or image), return exactly 0 marks and note this in reasoning.
    3. You must select a mark STRICTLY from the allowed schema enum values.
    4. Provide a brief reasoning string.
    5. Provide an evidence_quote: the exact substring from the OCR text (or description of image if visually grading) relied upon.
    6. Do NOT return coordinates, bounding boxes, or spatial reasoning.
    """

async def grade_question_sync(db: AsyncSession, request: GradingJobRequest) -> List[EvaluationRun]:
    """
    Synchronously fetches data, builds dynamic schema, runs both models, and saves results.
    Can be broken down later for batch API usage.
    """
    # 1. Fetch Script and Segmentation
    script = await db.get(AnswerScript, request.answer_script_id)
    if not script:
        raise HTTPException(status_code=404, detail="Answer script not found")
        
    seg_run_res = await db.execute(
        select(SegmentationRun)
        .where(SegmentationRun.answer_script_id == request.answer_script_id)
        .order_by(SegmentationRun.created_at.desc())
    )
    seg_run = seg_run_res.scalars().first()
    if not seg_run:
        raise HTTPException(status_code=400, detail="Script not segmented yet")
        
    # 2. Fetch Rubric Item
    # For MVP, assume the question matches exactly 1 RubricItem in the locked rubric.
    # If subparts exist, we grade them individually. The prompt asked for "per-question".
    item_res = await db.execute(
        select(RubricItem)
        .where(RubricItem.rubric_version_id == seg_run.rubric_version_id)
        .where(RubricItem.question_number == request.question_number)
    )
    items = item_res.scalars().all()
    if not items:
        raise HTTPException(status_code=404, detail="Question not found in rubric")
        
    # To simplify, we grade the first item found (if multiple subparts, the API should handle them or batch).
    item = items[0]
    
    # Fetch addenda
    addenda_res = await db.execute(select(RubricAddendum).where(RubricAddendum.rubric_item_id == item.id))
    addenda = addenda_res.scalars().all()
    
    # 3. Find mapped pages
    mapped_pages = []
    for mapping in seg_run.mappings:
        if mapping.get("question_number") == request.question_number:
            mapped_pages.extend(mapping.get("pages", []))
            
    mapped_pages = list(set(mapped_pages))
    
    # 4. Fetch OCR & Image data
    ocr_texts = []
    base64_image = None
    if mapped_pages:
        pages_res = await db.execute(
            select(OCRPage)
            .where(OCRPage.answer_script_id == request.answer_script_id)
            .where(OCRPage.page_number.in_(mapped_pages))
            .order_by(OCRPage.page_number)
        )
        for page in pages_res.scalars().all():
            words = page.ocr_json.get("words", [])
            ocr_texts.append(" ".join(w.get("text", "") for w in words))
            
            # If visual is required, we grab the first mapped page's image (MVP).
            # In production, we might stitch or send multiple.
            if item.requires_visual and not base64_image:
                try:
                    import base64
                    with open(page.image_path, "rb") as f:
                        base64_image = base64.b64encode(f.read()).decode("utf-8")
                except Exception as e:
                    logger.error(f"Failed to load image for visual grading: {e}")
                    
    ocr_text = "\n".join(ocr_texts)
    if not ocr_text.strip():
        ocr_text = "[NO OCR TEXT EXTRACTED]"
        
    # 5. Build Dynamic Schema & Prompt
    grading_schema = build_grading_schema(item.allowed_increments)
    prompt = _build_prompt(item, addenda, ocr_text)
    
    # 6. Execute Both Models Concurrently
    try:
        claude_res, gemini_res = await asyncio.gather(
            evaluate_with_claude(prompt, grading_schema, base64_image),
            evaluate_with_gemini(prompt, grading_schema, base64_image)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM Evaluation failed: {e}")
        
    # 7. Store Evaluation Runs
    # Retrieve float value from Enum
    claude_marks = claude_res.marks_awarded.value
    gemini_marks = gemini_res.marks_awarded.value
    
    run_claude = EvaluationRun(
        answer_script_id=script.id,
        question_number=item.question_number,
        subpart_id=item.subpart_id,
        run_type=RunType.ai_pass_1,
        marks_awarded=claude_marks,
        reasoning=claude_res.reasoning,
        evidence_quote=claude_res.evidence_quote
    )
    
    run_gemini = EvaluationRun(
        answer_script_id=script.id,
        question_number=item.question_number,
        subpart_id=item.subpart_id,
        run_type=RunType.ai_pass_2,
        marks_awarded=gemini_marks,
        reasoning=gemini_res.reasoning,
        evidence_quote=gemini_res.evidence_quote
    )
    
    db.add(run_claude)
    db.add(run_gemini)
    await db.commit()
    await db.refresh(run_claude)
    await db.refresh(run_gemini)
    
    return [run_claude, run_gemini]

from app.database.models import BatchJob, BatchJobStatus
from app.grading.llm import create_claude_batch, process_gemini_requests
import json

async def prepare_batch_grading(db: AsyncSession, script_ids: List[str], class_offering_id: str) -> tuple:
    """
    Prepares and dispatches batches for Claude and Gemini.
    Returns (claude_batch_job_id, gemini_batch_job_id).
    """
    requests_data = []
    custom_id_counter = 1
    request_mapping = {} # custom_id -> {"script_id": x, "question_number": y, "subpart_id": z}
    
    for script_id in script_ids:
        script = await db.get(AnswerScript, script_id)
        if not script:
            continue
            
        seg_run_res = await db.execute(select(SegmentationRun).where(SegmentationRun.answer_script_id == script_id).order_by(SegmentationRun.created_at.desc()))
        seg_run = seg_run_res.scalars().first()
        if not seg_run:
            continue
            
        item_res = await db.execute(select(RubricItem).where(RubricItem.rubric_version_id == seg_run.rubric_version_id))
        items = item_res.scalars().all()
        
        for item in items:
            addenda_res = await db.execute(select(RubricAddendum).where(RubricAddendum.rubric_item_id == item.id))
            addenda = addenda_res.scalars().all()
            
            mapped_pages = []
            for mapping in seg_run.mappings:
                if mapping.get("question_number") == item.question_number:
                    mapped_pages.extend(mapping.get("pages", []))
                    
            mapped_pages = list(set(mapped_pages))
            
            ocr_texts = []
            base64_image = None
            if mapped_pages:
                pages_res = await db.execute(
                    select(OCRPage)
                    .where(OCRPage.answer_script_id == script_id)
                    .where(OCRPage.page_number.in_(mapped_pages))
                    .order_by(OCRPage.page_number)
                )
                for page in pages_res.scalars().all():
                    words = page.ocr_json.get("words", [])
                    ocr_texts.append(" ".join(w.get("text", "") for w in words))
                    
                    if item.requires_visual and not base64_image:
                        try:
                            import base64
                            with open(page.image_path, "rb") as f:
                                base64_image = base64.b64encode(f.read()).decode("utf-8")
                        except Exception:
                            pass
                            
            ocr_text = "\n".join(ocr_texts)
            if not ocr_text.strip():
                ocr_text = "[NO OCR TEXT EXTRACTED]"
                
            grading_schema = build_grading_schema(item.allowed_increments)
            prompt = _build_prompt(item, addenda, ocr_text)
            
            custom_id = f"req_{custom_id_counter}"
            custom_id_counter += 1
            
            requests_data.append({
                "custom_id": custom_id,
                "prompt": prompt,
                "schema": grading_schema,
                "base64_image": base64_image
            })
            
            request_mapping[custom_id] = {
                "script_id": script_id,
                "question_number": item.question_number,
                "subpart_id": item.subpart_id
            }

    if not requests_data:
        return None, None

    # Claude Batch
    claude_external_id = await create_claude_batch(requests_data)
    claude_job = BatchJob(
        class_offering_id=class_offering_id,
        provider="claude",
        external_batch_id=claude_external_id,
        status=BatchJobStatus.in_progress,
        total_requests=len(requests_data),
        request_mapping=request_mapping
    )
    db.add(claude_job)
    
    # Gemini (Internal Async Queue) - we process this in the background later or store it
    # We create a job just to track it
    gemini_job = BatchJob(
        class_offering_id=class_offering_id,
        provider="gemini",
        external_batch_id=None, # internal
        status=BatchJobStatus.in_progress,
        total_requests=len(requests_data),
        request_mapping=request_mapping
    )
    db.add(gemini_job)
    
    await db.commit()
    
    # Trigger Gemini internal process via asyncio task
    # To avoid circular imports, we just run it here or in orchestrator.
    # We will let orchestrator handle it or we can dispatch it.
    
    return claude_job.id, gemini_job.id, requests_data
