import os
import shutil
import uuid
import csv
import io
import json
import asyncio
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
import fitz

from app.database.session import get_db
from app.database.models import Student, ClassOffering, AnswerScript, AnswerScriptStatus, UserRole, User
from app.auth.dependencies import RequireRole

STORAGE_DIR = os.getenv("STORAGE_DIR", "./storage")
TEMP_DIR = os.path.join(STORAGE_DIR, "temp_uploads")
os.makedirs(TEMP_DIR, exist_ok=True)

router = APIRouter(tags=["bulk"])

# --- BULK ROSTER ---

@router.post("/api/offerings/{offering_id}/students/bulk-validate")
async def bulk_validate_students(
    offering_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequireRole([UserRole.admin, UserRole.exam_coordinator]))
):
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported.")
        
    offering = await db.get(ClassOffering, offering_id)
    if not offering:
        raise HTTPException(status_code=404, detail="Offering not found")

    content = await file.read()
    try:
        text = content.decode("utf-8-sig")  # handle BOM
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    # existing students
    existing_students = (await db.execute(select(Student).where(Student.section_id == offering.section_id))).scalars().all()
    existing_rolls = set(s.roll_number.lower() for s in existing_students)
    
    seen_rolls = set()
    rows = []
    
    reader = csv.DictReader(io.StringIO(text))
    # attempt to find keys regardless of case
    fieldnames = [f.strip().lower() for f in (reader.fieldnames or [])]
    
    # Try to identify roll_number and name columns
    roll_col = next((c for c in fieldnames if "roll" in c or "enroll" in c or "id" in c), None)
    name_col = next((c for c in fieldnames if "name" in c or "student" in c), None)
    
    if not roll_col or not name_col:
        raise HTTPException(status_code=400, detail="Could not identify 'roll_number' or 'name' columns in CSV.")

    raw_reader = csv.DictReader(io.StringIO(text))
    
    for row in raw_reader:
        # Get values using the original keys
        orig_keys = list(row.keys())
        roll_val = None
        name_val = None
        for k in orig_keys:
            if k and k.strip().lower() == roll_col:
                roll_val = row[k]
            if k and k.strip().lower() == name_col:
                name_val = row[k]
                
        roll_val = str(roll_val).strip() if roll_val else ""
        name_val = str(name_val).strip() if name_val else ""
        
        status = "valid"
        reason = ""
        
        if not roll_val or not name_val:
            status = "error"
            reason = "Missing roll number or name"
        elif roll_val.lower() in existing_rolls:
            status = "duplicate"
            reason = "Student already in roster"
        elif roll_val.lower() in seen_rolls:
            status = "duplicate"
            reason = "Duplicate roll number in CSV"
        
        if roll_val:
            seen_rolls.add(roll_val.lower())
            
        rows.append({
            "roll_number": roll_val,
            "full_name": name_val,
            "status": status,
            "reason": reason
        })

    return {"rows": rows}

class BulkCommitRequest(BaseModel):
    students: List[Dict[str, str]]

@router.post("/api/offerings/{offering_id}/students/bulk-commit")
async def bulk_commit_students(
    offering_id: str,
    request: BulkCommitRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequireRole([UserRole.admin, UserRole.exam_coordinator]))
):
    offering = await db.get(ClassOffering, offering_id)
    if not offering:
        raise HTTPException(status_code=404, detail="Offering not found")

    existing_students = (await db.execute(select(Student).where(Student.section_id == offering.section_id))).scalars().all()
    existing_rolls = set(s.roll_number.lower() for s in existing_students)

    added = 0
    for s_data in request.students:
        roll = s_data.get("roll_number", "").strip()
        name = s_data.get("full_name", "").strip()
        
        if not roll or not name or roll.lower() in existing_rolls:
            continue
            
        new_student = Student(roll_number=roll, name=name, section_id=offering.section_id)
        db.add(new_student)
        existing_rolls.add(roll.lower())
        added += 1
        
    await db.commit()
    return {"status": "success", "added": added}


# --- BULK SCRIPTS ---

@router.post("/api/ingestion/bulk-scripts/validate")
async def bulk_validate_scripts(
    offering_id: str = Form(...),
    files: List[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequireRole([UserRole.admin, UserRole.exam_coordinator, UserRole.evaluator]))
):
    offering = await db.get(ClassOffering, offering_id)
    if not offering:
        raise HTTPException(status_code=404, detail="Offering not found")
        
    batch_id = uuid.uuid4().hex
    batch_dir = os.path.join(TEMP_DIR, batch_id)
    os.makedirs(batch_dir, exist_ok=True)
    
    students = (await db.execute(select(Student).where(Student.section_id == offering.section_id))).scalars().all()
    student_map = {s.roll_number.lower(): s for s in students}
    
    # Check for existing scripts to flag conflicts
    existing_scripts = (await db.execute(select(AnswerScript).where(AnswerScript.class_offering_id == offering_id))).scalars().all()
    existing_student_scripts = {s.student_id: s for s in existing_scripts}

    results = []
    
    import google.generativeai as genai
    from PIL import Image
    model = genai.GenerativeModel("gemini-3.5-flash")
    
    async def process_file(file: UploadFile):
        file_id = uuid.uuid4().hex
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in [".pdf", ".jpg", ".jpeg", ".png"]:
            return {"filename": file.filename, "status": "error", "reason": "Unsupported format"}
            
        temp_path = os.path.join(batch_dir, f"{file_id}{ext}")
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # OCR the first page to find roll number
        found_roll = None
        try:
            img = None
            if ext == ".pdf":
                doc = fitz.open(temp_path)
                page = doc.load_page(0)
                pix = page.get_pixmap(dpi=150)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                doc.close()
            else:
                img = Image.open(temp_path)
                
            # Crop to top 30% to speed up and focus on header
            w, h = img.size
            img_cropped = img.crop((0, 0, w, int(h * 0.3)))
            
            prompt = "Extract the student Roll Number or Enrollment Number from this exam header. Return ONLY the roll number text, nothing else. If not found, return 'NOT_FOUND'."
            # For simplicity, running synchronously in executor
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, lambda: model.generate_content([prompt, img_cropped]))
            res_text = response.text.strip()
            
            if res_text and "NOT_FOUND" not in res_text:
                # Clean up extracted text (remove spaces, etc)
                found_roll = res_text.replace(" ", "").upper()
                
        except Exception as e:
            print(f"Error OCRing {file.filename}: {e}")

        # Match with roster
        student = None
        conflict = False
        if found_roll:
            # Try exact or partial match
            student = student_map.get(found_roll.lower())
            if not student:
                # partial match fallback
                for roll, s in student_map.items():
                    if roll in found_roll.lower() or found_roll.lower() in roll:
                        student = s
                        break
        
        if student:
            if student.id in existing_student_scripts:
                conflict = True
                
        return {
            "temp_file_id": f"{file_id}{ext}",
            "filename": file.filename,
            "status": "matched" if student else "unmatched",
            "extracted_roll": found_roll,
            "matched_student_id": student.id if student else None,
            "matched_student_name": student.name if student else None,
            "matched_student_roll": student.roll_number if student else None,
            "conflict": conflict
        }

    # Process all files concurrently
    tasks = [process_file(f) for f in files]
    results = await asyncio.gather(*tasks)

    return {
        "batch_id": batch_id,
        "files": results
    }


class BulkScriptCommitRequest(BaseModel):
    batch_id: str
    offering_id: str
    mappings: List[Dict[str, Any]]  # temp_file_id -> student_id, action (replace/skip)

@router.post("/api/ingestion/bulk-scripts/commit")
async def bulk_commit_scripts(
    request: BulkScriptCommitRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequireRole([UserRole.admin, UserRole.exam_coordinator, UserRole.evaluator]))
):
    batch_dir = os.path.join(TEMP_DIR, request.batch_id)
    if not os.path.exists(batch_dir):
        raise HTTPException(status_code=404, detail="Batch not found or expired")
        
    pdf_dir = os.path.join(STORAGE_DIR, "pdfs")
    os.makedirs(pdf_dir, exist_ok=True)
    
    existing_scripts = (await db.execute(select(AnswerScript).where(AnswerScript.class_offering_id == request.offering_id))).scalars().all()
    existing_map = {s.student_id: s for s in existing_scripts}
    
    processed = 0
    skipped = 0
    
    for mapping in request.mappings:
        action = mapping.get("action", "commit") # commit, replace, skip
        if action == "skip":
            skipped += 1
            continue
            
        student_id = mapping.get("student_id")
        temp_file_id = mapping.get("temp_file_id")
        filename = mapping.get("filename")
        
        if not student_id or not temp_file_id:
            continue
            
        temp_path = os.path.join(batch_dir, temp_file_id)
        if not os.path.exists(temp_path):
            continue
            
        # Handle conflict
        if student_id in existing_map:
            if action == "replace":
                old_script = existing_map[student_id]
                # Keep ID, overwrite file
                target_path = os.path.join(pdf_dir, f"{old_script.id}.pdf")
                shutil.copyfile(temp_path, target_path)
                old_script.original_file_path = target_path
                old_script.status = AnswerScriptStatus.uploaded
                processed += 1
            else:
                skipped += 1
        else:
            new_script = AnswerScript(
                student_id=student_id,
                class_offering_id=request.offering_id,
                original_file_path="",
                status=AnswerScriptStatus.uploaded
            )
            db.add(new_script)
            await db.commit()
            await db.refresh(new_script)
            
            target_path = os.path.join(pdf_dir, f"{new_script.id}.pdf")
            shutil.copyfile(temp_path, target_path)
            new_script.original_file_path = target_path
            processed += 1

    await db.commit()
    
    # Cleanup temp dir
    try:
        shutil.rmtree(batch_dir)
    except:
        pass
        
    return {"status": "success", "processed": processed, "skipped": skipped}
