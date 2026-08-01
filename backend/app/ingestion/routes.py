import os
import shutil
import hashlib
from fastapi import APIRouter, Depends, UploadFile, File, Form, BackgroundTasks, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from dotenv import load_dotenv

from app.database.session import get_db
from app.database.models import AnswerScript, AnswerScriptStatus, UserRole, User
from app.auth.dependencies import RequireRole
from app.ingestion.schemas import UploadResponse
from app.ingestion.service import process_pdf_pipeline

load_dotenv()
STORAGE_DIR = os.getenv("STORAGE_DIR", "./storage")

router = APIRouter(prefix="/ingestion", tags=["ingestion"])

@router.post("/upload", response_model=UploadResponse, status_code=202)
async def upload_script(
    background_tasks: BackgroundTasks,
    student_id: str = Form(...),
    class_offering_id: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequireRole([UserRole.admin, UserRole.exam_coordinator]))
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    # Check if student already has a script in this class offering
    existing_student_script = await db.execute(
        select(AnswerScript)
        .where(AnswerScript.student_id == student_id)
        .where(AnswerScript.class_offering_id == class_offering_id)
    )
    if existing_student_script.scalars().first():
        raise HTTPException(status_code=400, detail="Script already uploaded for this student.")

    # Calculate file hash
    sha256_hash = hashlib.sha256()
    content = await file.read()
    sha256_hash.update(content)
    file_hash = sha256_hash.hexdigest()
    
    # Reset file pointer after reading
    await file.seek(0)

    # Check if this exact file was already uploaded in this offering (e.g. for another student)
    existing_hash_script = await db.execute(
        select(AnswerScript)
        .where(AnswerScript.class_offering_id == class_offering_id)
        .where(AnswerScript.file_hash == file_hash)
    )
    if existing_hash_script.scalars().first():
        raise HTTPException(status_code=400, detail="Duplicate file detected: already uploaded for another student.")

    # Create AnswerScript record
    new_script = AnswerScript(
        student_id=student_id,
        class_offering_id=class_offering_id,
        original_file_path="",  # Will update after saving
        file_hash=file_hash,
        status=AnswerScriptStatus.uploaded
    )
    db.add(new_script)
    await db.commit()
    await db.refresh(new_script)

    # Save original PDF
    pdf_dir = os.path.join(STORAGE_DIR, "pdfs")
    os.makedirs(pdf_dir, exist_ok=True)
    file_path = os.path.join(pdf_dir, f"{new_script.id}.pdf")
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # Update file path
    new_script.original_file_path = file_path
    await db.commit()

    # Do not trigger processing automatically; wait for manual trigger.
    # We leave the script in "uploaded" state.

    return UploadResponse(
        answer_script_id=new_script.id,
        status="accepted",
        message="Upload accepted. Ready for analysis."
    )

from pydantic import BaseModel
from typing import List

class AnalyzeRequest(BaseModel):
    answer_script_ids: List[str]

@router.post("/api/offerings/{offering_id}/analyze")
async def trigger_analysis(
    offering_id: str,
    request: AnalyzeRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequireRole([UserRole.admin, UserRole.exam_coordinator]))
):
    from app.ingestion.orchestrator import run_full_pipeline_task, run_batch_pipeline_task
    
    scripts = await db.execute(
        select(AnswerScript).where(AnswerScript.id.in_(request.answer_script_ids))
    )
    scripts = scripts.scalars().all()
    
    valid_scripts = [s for s in scripts if s.status in [AnswerScriptStatus.uploaded, AnswerScriptStatus.queued, AnswerScriptStatus.error]]
    
    if len(valid_scripts) > 1:
        for s in valid_scripts:
            s.status = AnswerScriptStatus.queued
        await db.commit()
        
        background_tasks.add_task(
            run_batch_pipeline_task,
            script_ids=[s.id for s in valid_scripts],
            storage_dir=STORAGE_DIR,
            class_offering_id=offering_id
        )
    else:
        for script in valid_scripts:
            script.status = AnswerScriptStatus.queued
            await db.commit()
            background_tasks.add_task(
                run_full_pipeline_task,
                answer_script_id=script.id,
                storage_dir=STORAGE_DIR
            )
            
    return {"status": "success", "message": f"Queued {len(valid_scripts)} scripts for analysis."}
