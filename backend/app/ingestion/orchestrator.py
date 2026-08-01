import logging
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database.session import AsyncSessionLocal
from app.database.models import AnswerScript, AnswerScriptStatus, RubricItem, SegmentationRun
from app.ingestion.service import process_pdf_pipeline
from app.segmentation.service import run_segmentation_pipeline
from app.grading.service import grade_question_sync
from app.grading.schemas import GradingJobRequest
from app.review.service import reconcile_evaluations
from app.annotation.service import annotate_script
import os
from app.events import publisher

logger = logging.getLogger(__name__)

async def run_full_pipeline_task(answer_script_id: str, storage_dir: str):
    """
    Background task that orchestrates the entire evaluation pipeline for a single script.
    It manages its own DB session so it can run safely in the background.
    """
    async with AsyncSessionLocal() as db:
        try:
            # 1. Update status to Processing
            script = await db.get(AnswerScript, answer_script_id)
            if not script:
                logger.error(f"Pipeline failed: Script {answer_script_id} not found")
                return

            if script.status in [AnswerScriptStatus.queued, AnswerScriptStatus.uploaded]:
                script.status = AnswerScriptStatus.processing
                await db.commit()
                await publisher.publish("status_update", {"script_id": answer_script_id, "status": "processing", "class_offering_id": script.class_offering_id})
            
            # 2. Ingestion (OCR)
            # process_pdf_pipeline updates status to ocr_done internally
            if script.status != AnswerScriptStatus.ocr_done:
                logger.info(f"Running OCR for {answer_script_id}")
                await process_pdf_pipeline(db, answer_script_id, script.original_file_path, storage_dir)
                await publisher.publish("status_update", {"script_id": answer_script_id, "status": "ocr_done", "class_offering_id": script.class_offering_id})
            
            # 3. Segmentation
            logger.info(f"Running Segmentation for {answer_script_id}")
            seg_run = await run_segmentation_pipeline(db, answer_script_id)
            await publisher.publish("status_update", {"script_id": answer_script_id, "status": "segmented", "class_offering_id": script.class_offering_id})
            
            if not seg_run:
                logger.error(f"Pipeline failed: Segmentation did not complete for {answer_script_id}")
                return

            # 4. Grading
            logger.info(f"Running Dual-Model Grading for {answer_script_id}")
            # Fetch all items from the locked rubric version
            item_res = await db.execute(
                select(RubricItem)
                .where(RubricItem.rubric_version_id == seg_run.rubric_version_id)
            )
            items = item_res.scalars().all()

            for item in items:
                logger.info(f"Grading Q{item.question_number} subpart {item.subpart_id}")
                try:
                    await grade_question_sync(db, GradingJobRequest(
                        answer_script_id=answer_script_id,
                        question_number=item.question_number
                    ))
                except Exception as e:
                    logger.error(f"Grading failed for {answer_script_id} Q{item.question_number}: {e}")
                    # Continue grading other items even if one fails
            
            # 5. Review Reconciliation (Flags & Initial Score)
            logger.info(f"Reconciling Evaluations for {answer_script_id}")
            await reconcile_evaluations(db, answer_script_id)
            
            # 6. Annotation (Draw marks on PDF)
            logger.info(f"Generating Annotated PDF for {answer_script_id}")
            await annotate_script(db, answer_script_id)
            
            await publisher.publish("status_update", {"script_id": answer_script_id, "status": "graded", "class_offering_id": script.class_offering_id})
            await publisher.publish("notification", {
                "class_offering_id": script.class_offering_id, 
                "message": f"Evaluation pipeline complete for script {answer_script_id}", 
                "type": "batch_complete"
            })
            
            logger.info(f"Pipeline completed successfully for {answer_script_id}")

        except Exception as e:
            logger.error(f"Full pipeline task failed for {answer_script_id}: {e}")
            await db.rollback()
            # Optionally mark script as error status if we had one

async def poll_and_reconcile_batch(class_offering_id: str, claude_job_id: str, gemini_job_id: str, requests_data: list):
    """
    Background worker that polls Anthropic batch and waits for Gemini batch to finish.
    Once both are done, reconciles and annotates all scripts in the batch.
    """
    from app.grading.llm import poll_claude_batch, process_gemini_requests
    from app.grading.service import RunType
    from app.database.models import BatchJob, BatchJobStatus, EvaluationRun, UsageLog
    import asyncio
    
    # Run Gemini in the background now
    # Wait, we need the shared rubric text for context caching. We'll simplify for now.
    gemini_results_task = asyncio.create_task(process_gemini_requests(requests_data, "Evaluate strictly."))
    
    # Poll Claude
    claude_results = []
    usage = {}
    while True:
        res = await poll_claude_batch(claude_job_id)
        if res["status"] in ["completed", "ended"]:
            claude_results = res["results"]
            usage = res.get("usage", {})
            break
        elif res["status"] in ["failed", "canceled", "expired"]:
            logger.error(f"Claude batch failed with status: {res['status']}")
            break
        await asyncio.sleep(30) # Poll every 30s
        
    gemini_results = await gemini_results_task
    
    async with AsyncSessionLocal() as db:
        claude_job = await db.get(BatchJob, claude_job_id)
        gemini_job = await db.get(BatchJob, gemini_job_id)
        
        mapping = claude_job.request_mapping
        scripts_to_reconcile = set()
        
        # Save usage log
        if usage:
            usd_cost = (
                (usage.get("input_tokens", 0) * 3 / 1000000) +
                (usage.get("cache_creation_input_tokens", 0) * 3.75 / 1000000) +
                (usage.get("cache_read_input_tokens", 0) * 0.30 / 1000000) +
                (usage.get("output_tokens", 0) * 15 / 1000000)
            )
            log = UsageLog(
                class_offering_id=class_offering_id,
                provider="claude",
                input_tokens=usage.get("input_tokens", 0),
                cache_read_input_tokens=usage.get("cache_read_input_tokens", 0),
                cache_creation_input_tokens=usage.get("cache_creation_input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
                estimated_cost_usd=usd_cost
            )
            db.add(log)
        
        # Parse Claude results
        for item in claude_results:
            custom_id = item.custom_id
            if item.result.type != "succeeded":
                continue
                
            try:
                # Anthropic message response structure
                content = item.result.message.content
                tool_use = next((c for c in content if c.type == "tool_use"), None)
                if not tool_use:
                    continue
                args = tool_use.input
                
                req_map = mapping.get(custom_id)
                if not req_map:
                    continue
                    
                scripts_to_reconcile.add(req_map["script_id"])
                
                # Fetch original schema to parse correctly? We stored marks as int/float.
                marks = args.get("marks_awarded")
                if hasattr(marks, "value"): marks = marks.value
                elif isinstance(marks, dict) and "value" in marks: marks = marks["value"]
                # actually it's a raw dict here
                if isinstance(marks, (int, float)):
                    pass
                elif hasattr(marks, 'name'):
                    marks = float(marks.name.replace('m_', '').replace('_', '.'))
                else:
                    marks = float(str(marks).replace('m_', '').replace('_', '.'))
                    
                run = EvaluationRun(
                    answer_script_id=req_map["script_id"],
                    question_number=req_map["question_number"],
                    subpart_id=req_map["subpart_id"],
                    run_type=RunType.ai_pass_1,
                    marks_awarded=marks,
                    reasoning=args.get("reasoning", ""),
                    evidence_quote=args.get("evidence_quote", ""),
                    batch_job_id=claude_job.id
                )
                db.add(run)
            except Exception as e:
                logger.error(f"Error parsing claude result {custom_id}: {e}")
                
        # Parse Gemini results
        for item in gemini_results:
            custom_id = item.get("custom_id")
            if item.get("status") != "completed":
                continue
                
            try:
                res = item["result"]
                req_map = mapping.get(custom_id)
                if not req_map:
                    continue
                    
                scripts_to_reconcile.add(req_map["script_id"])
                
                marks = res.marks_awarded
                if hasattr(marks, "value"): marks = marks.value
                elif isinstance(marks, dict) and "value" in marks: marks = marks["value"]
                if isinstance(marks, (int, float)):
                    pass
                elif hasattr(marks, 'name'):
                    marks = float(marks.name.replace('m_', '').replace('_', '.'))
                else:
                    marks = float(str(marks).replace('m_', '').replace('_', '.'))
                    
                run = EvaluationRun(
                    answer_script_id=req_map["script_id"],
                    question_number=req_map["question_number"],
                    subpart_id=req_map["subpart_id"],
                    run_type=RunType.ai_pass_2,
                    marks_awarded=marks,
                    reasoning=res.reasoning,
                    evidence_quote=res.evidence_quote,
                    batch_job_id=gemini_job.id
                )
                db.add(run)
            except Exception as e:
                logger.error(f"Error parsing gemini result {custom_id}: {e}")
                
        claude_job.status = BatchJobStatus.completed
        gemini_job.status = BatchJobStatus.completed
        await db.commit()
        
        # Reconcile and annotate all scripts
        for script_id in scripts_to_reconcile:
            await reconcile_evaluations(db, script_id)
            await annotate_script(db, script_id)
            
            script = await db.get(AnswerScript, script_id)
            await publisher.publish("status_update", {"script_id": script_id, "status": "graded", "class_offering_id": script.class_offering_id})
            
        await publisher.publish("notification", {
            "class_offering_id": class_offering_id, 
            "message": f"Batch Evaluation complete for {len(scripts_to_reconcile)} scripts.", 
            "type": "batch_complete"
        })

async def run_batch_pipeline_task(script_ids: list, storage_dir: str, class_offering_id: str):
    """
    Background task that orchestrates batch processing for multiple scripts.
    """
    from app.grading.service import prepare_batch_grading
    
    async with AsyncSessionLocal() as db:
        try:
            # 1. OCR & Segmentation for all
            for script_id in script_ids:
                script = await db.get(AnswerScript, script_id)
                if not script:
                    continue
                if script.status in [AnswerScriptStatus.queued, AnswerScriptStatus.uploaded]:
                    script.status = AnswerScriptStatus.processing
                    await db.commit()
                    await publisher.publish("status_update", {"script_id": script_id, "status": "processing", "class_offering_id": script.class_offering_id})
                    
                if script.status != AnswerScriptStatus.ocr_done:
                    await process_pdf_pipeline(db, script_id, script.original_file_path, storage_dir)
                    await publisher.publish("status_update", {"script_id": script_id, "status": "ocr_done", "class_offering_id": script.class_offering_id})
                    
                await run_segmentation_pipeline(db, script_id)
                await publisher.publish("status_update", {"script_id": script_id, "status": "segmented", "class_offering_id": script.class_offering_id})
                
            # 2. Gather grading requests and dispatch batch
            claude_job_id, gemini_job_id, requests_data = await prepare_batch_grading(db, script_ids, class_offering_id)
            if not claude_job_id:
                logger.error("No questions to grade in batch.")
                return
                
        except Exception as e:
            logger.error(f"Batch prep failed: {e}")
            await db.rollback()
            return
            
    # 3. Poll in the background
    asyncio.create_task(poll_and_reconcile_batch(class_offering_id, claude_job_id, gemini_job_id, requests_data))
