from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import List, Optional

from app.database.session import get_db
from app.database.models import (
    Department, Course, Section, AcademicTerm, Subject, ClassOffering, Student, AnswerScript,
    QuestionPaper, AnswerKey, RubricVersion, RubricStatus
)
import os
import shutil
import fitz  # PyMuPDF
from fastapi import UploadFile, File, HTTPException
from dotenv import load_dotenv

load_dotenv()
STORAGE_DIR = os.getenv("STORAGE_DIR", "./storage")

router = APIRouter(tags=["hierarchy"])

@router.get("/api/hierarchy/filters/departments")
async def get_departments_with_offerings(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Department)
        .join(ClassOffering, ClassOffering.department_id == Department.id)
        .distinct()
    )
    depts = result.scalars().all()
    return [{"id": d.id, "name": d.name} for d in depts]

@router.get("/api/hierarchy/filters/departments/{dept_id}/courses")
async def get_courses_for_department(dept_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Course)
        .join(ClassOffering, ClassOffering.course_id == Course.id)
        .where(ClassOffering.department_id == dept_id)
        .distinct()
    )
    courses = result.scalars().all()
    return [{"id": c.id, "name": c.name} for c in courses]

@router.get("/api/hierarchy/filters/courses/{course_id}/sections")
async def get_sections_for_course(course_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Section)
        .join(ClassOffering, ClassOffering.section_id == Section.id)
        .where(ClassOffering.course_id == course_id)
        .distinct()
    )
    sections = result.scalars().all()
    return [{"id": s.id, "name": s.name} for s in sections]

@router.get("/api/hierarchy/filters/sections/{section_id}/terms")
async def get_terms_for_section(section_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AcademicTerm)
        .join(ClassOffering, ClassOffering.academic_term_id == AcademicTerm.id)
        .where(ClassOffering.section_id == section_id)
        .distinct()
    )
    terms = result.scalars().all()
    
    terms_list = []
    for term in terms:
        terms_list.append({
            "id": term.id, 
            "name": f"Semester {term.semester} ({term.year}-{term.year+1})"
        })
    return terms_list

@router.get("/api/hierarchy/filters/sections/{section_id}/terms/{term_id}/subjects")
async def get_subjects_for_section_and_term(section_id: str, term_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Subject, ClassOffering.id.label("offering_id"))
        .join(ClassOffering, ClassOffering.subject_id == Subject.id)
        .where(ClassOffering.section_id == section_id)
        .where(ClassOffering.academic_term_id == term_id)
    )
    rows = result.all()
    
    subjects_list = []
    for subject, offering_id in rows:
        subjects_list.append({
            "id": subject.id,
            "name": subject.name,
            "class_offering_id": offering_id
        })
    return subjects_list

@router.get("/api/hierarchy")
async def get_hierarchy(db: AsyncSession = Depends(get_db)):
    # Fetch all hierarchy entities
    depts = (await db.execute(select(Department))).scalars().all()
    courses = (await db.execute(select(Course))).scalars().all()
    sections = (await db.execute(select(Section))).scalars().all()
    terms = (await db.execute(select(AcademicTerm))).scalars().all()
    subjects = (await db.execute(select(Subject))).scalars().all()
    offerings_db = (await db.execute(select(ClassOffering))).scalars().all()
    
    # We need to map AcademicTerm to semesters and years for the frontend
    semesters_map = {}
    years_map = {}
    for term in terms:
        sem_name = f"Semester {term.semester}"
        if sem_name not in semesters_map:
            semesters_map[sem_name] = {"id": f"sem_{term.semester}", "name": sem_name, "number": term.semester}
        
        yr_name = f"{term.year}-{term.year+1}"
        if yr_name not in years_map:
            years_map[yr_name] = {"id": f"yr_{term.year}", "name": yr_name, "calendar_year": term.year}

    # Format offerings to match frontend expectations:
    # { id, department: {name}, course: {name}, section: {name}, semester: {name}, year: {name}, subject: {name} }
    offerings = []
    for off in offerings_db:
        # Resolve relations (normally done via joinedload, doing it manually for simplicity if lists are small)
        dept = next((d for d in depts if d.id == off.department_id), None)
        course = next((c for c in courses if c.id == off.course_id), None)
        section = next((s for s in sections if s.id == off.section_id), None)
        term = next((t for t in terms if t.id == off.academic_term_id), None)
        subject = next((s for s in subjects if s.id == off.subject_id), None)
        
        if term:
            sem = {"name": f"Semester {term.semester}"}
            yr = {"name": f"{term.year}-{term.year+1}"}
        else:
            sem = {"name": "Unknown"}
            yr = {"name": "Unknown"}
            
        offerings.append({
            "id": off.id,
            "department_id": off.department_id,
            "course_id": off.course_id,
            "section_id": off.section_id,
            "academic_term_id": off.academic_term_id,
            "subject_id": off.subject_id,
            "department": {"name": dept.name if dept else "Unknown"},
            "course": {"name": course.name if course else "Unknown"},
            "section": {"name": section.name if section else "Unknown"},
            "semester": sem,
            "year": yr,
            "subject": {"name": subject.name if subject else "Unknown"}
        })

    return {
        "departments": [{"id": d.id, "name": d.name} for d in depts],
        "courses": [{"id": c.id, "name": c.name, "department_id": c.department_id} for c in courses],
        "sections": [{"id": s.id, "name": s.name, "course_id": s.course_id} for s in sections],
        "terms": [{"id": t.id, "semester": str(t.semester), "year": int(t.year), "name": f"Semester {t.semester} ({t.year}-{t.year+1})"} for t in terms],
        "semesters": list(semesters_map.values()),
        "years": list(years_map.values()),
        "subjects": [{"id": s.id, "name": s.name} for s in subjects],
        "offerings": offerings
    }

class StudentCreate(BaseModel):
    enrollment_number: str
    full_name: str
    email: Optional[str] = None

@router.get("/api/offerings/{offering_id}/students")
async def get_offering_students(offering_id: str, db: AsyncSession = Depends(get_db)):
    # The original DB model ties Student to section_id. So students for an offering
    # are students in the offering's section.
    offering = await db.get(ClassOffering, offering_id)
    if not offering:
        return []
    
    students = (await db.execute(select(Student).where(Student.section_id == offering.section_id))).scalars().all()
    
    # Fetch all scripts for this offering
    scripts_db = (await db.execute(
        select(AnswerScript).where(AnswerScript.class_offering_id == offering_id)
    )).scalars().all()
    script_ids = [s.id for s in scripts_db]
    script_map = {s.student_id: s for s in scripts_db}
    
    # Fetch flags for all scripts
    from app.database.models import ReviewFlag, FlagStatus, EvaluationRun, RunType, RubricVersion, RubricStatus, RubricItem
    flags_db = (await db.execute(
        select(ReviewFlag)
        .where(ReviewFlag.answer_script_id.in_(script_ids))
        .where(ReviewFlag.status == FlagStatus.open)
    )).scalars().all()
    
    flags_map = {}
    for f in flags_db:
        flags_map[f.answer_script_id] = flags_map.get(f.answer_script_id, 0) + 1

    # Fetch max marks from locked rubric
    locked_rubric_res = await db.execute(
        select(RubricVersion)
        .join(QuestionPaper, QuestionPaper.id == RubricVersion.question_paper_id)
        .where(QuestionPaper.class_offering_id == offering_id)
        .where(RubricVersion.status == RubricStatus.locked)
    )
    locked_rubric = locked_rubric_res.scalars().first()
    max_marks = 0
    if locked_rubric:
        items = (await db.execute(select(RubricItem).where(RubricItem.rubric_version_id == locked_rubric.id))).scalars().all()
        max_marks = sum(float(item.max_marks) for item in items if item.max_marks)
    
    # Fetch ai_pass_1 evaluation runs for awarded marks
    evals_db = (await db.execute(
        select(EvaluationRun)
        .where(EvaluationRun.answer_script_id.in_(script_ids))
        .where(EvaluationRun.run_type == RunType.ai_pass_1)
    )).scalars().all()
    
    marks_map = {}
    for ev in evals_db:
        marks_map[ev.answer_script_id] = marks_map.get(ev.answer_script_id, 0) + float(ev.marks_awarded or 0)

    result = []
    for s in students:
        script = script_map.get(s.id)
        if script:
            script_data = {
                "id": script.id,
                "status": script.status.value,
                "filename": os.path.basename(script.original_file_path) if script.original_file_path else "script.pdf",
                "max_marks": max_marks,
                "marks_awarded": marks_map.get(script.id, 0),
                "flags_count": flags_map.get(script.id, 0)
            }
        else:
            script_data = None
            
        result.append({
            "id": s.id,
            "enrollment_number": s.roll_number,
            "full_name": s.name,
            "email": "",
            "script": script_data
        })
    return result

@router.post("/api/offerings/{offering_id}/students")
async def add_student(offering_id: str, student_data: StudentCreate, db: AsyncSession = Depends(get_db)):
    offering = await db.get(ClassOffering, offering_id)
    if not offering:
        return {"status": "error", "message": "Offering not found"}
        
    existing = (await db.execute(select(Student).where(Student.roll_number == student_data.enrollment_number))).scalars().first()
    if not existing:
        new_student = Student(
            roll_number=student_data.enrollment_number,
            name=student_data.full_name,
            section_id=offering.section_id
        )
        db.add(new_student)
        await db.commit()
    return {"status": "success"}

@router.post("/api/departments")
async def create_department(data: dict, db: AsyncSession = Depends(get_db)):
    d = Department(name=data.get('name', 'New Dept'))
    db.add(d)
    await db.commit()
    return {"id": d.id}

@router.post("/api/courses")
async def create_course(data: dict, db: AsyncSession = Depends(get_db)):
    c = Course(name=data.get('name', 'New Course'), department_id=data.get('department_id'))
    db.add(c)
    await db.commit()
    return {"id": c.id}

@router.post("/api/sections")
async def create_section(data: dict, db: AsyncSession = Depends(get_db)):
    s = Section(name=data.get('name', 'New Section'), course_id=data.get('course_id'))
    db.add(s)
    await db.commit()
    return {"id": s.id}

@router.post("/api/academic-terms")
async def create_term(data: dict, db: AsyncSession = Depends(get_db)):
    t = AcademicTerm(semester=str(data.get('number', '1')), year=int(data.get('calendar_year', 2026)))
    db.add(t)
    await db.commit()
    return {"id": t.id}

@router.post("/api/subjects")
async def create_subject(data: dict, db: AsyncSession = Depends(get_db)):
    s = Subject(name=data.get('name', 'New Subject'))
    db.add(s)
    await db.commit()
    return {"id": s.id}

@router.post("/api/offerings")
async def create_offering(data: dict, db: AsyncSession = Depends(get_db)):
    o = ClassOffering(
        department_id=data.get('department_id'),
        course_id=data.get('course_id'),
        section_id=data.get('section_id'),
        academic_term_id=data.get('semester_id'), # In the frontend this is currently mapped this way
        subject_id=data.get('subject_id')
    )
    db.add(o)
    await db.commit()
    return {"id": o.id}

@router.put("/api/{entity_type}/{id}")
async def update_entity(entity_type: str, id: str, data: dict, db: AsyncSession = Depends(get_db)):
    from sqlalchemy.exc import IntegrityError
    model_map = {
        "departments": Department,
        "courses": Course,
        "sections": Section,
        "academic-terms": AcademicTerm,
        "subjects": Subject
    }
    model = model_map.get(entity_type)
    if not model:
        # Fallback for non-hierarchy entities if they mistakenly hit this
        return {"error": "Invalid entity"}
        
    obj = await db.get(model, id)
    if not obj:
        return {"error": "Not found"}
        
    if entity_type == "academic-terms":
        if 'number' in data: obj.semester = str(data['number'])
        if 'calendar_year' in data: obj.year = int(data['calendar_year'])
    else:
        if 'name' in data: obj.name = data['name']
        
    try:
        await db.commit()
        return {"status": "success"}
    except IntegrityError:
        await db.rollback()
        return {"error": "Update failed due to constraints."}

@router.delete("/api/{entity_type}/{id}")
async def delete_entity(entity_type: str, id: str, db: AsyncSession = Depends(get_db)):
    # Skip if it's students or other specific entities
    if entity_type not in ["departments", "courses", "sections", "academic-terms", "subjects", "offerings"]:
        return {"error": "Invalid entity"}
        
    from sqlalchemy.exc import IntegrityError
    model_map = {
        "departments": Department,
        "courses": Course,
        "sections": Section,
        "academic-terms": AcademicTerm,
        "subjects": Subject,
        "offerings": ClassOffering
    }
    model = model_map.get(entity_type)
    
    obj = await db.get(model, id)
    if not obj:
        return {"error": "Not found"}
        
    try:
        await db.delete(obj)
        await db.commit()
        return {"status": "success"}
    except IntegrityError:
        await db.rollback()
        return {"error": f"Cannot delete. It is currently being used by other records."}

@router.delete("/api/students/{student_id}")
async def delete_student(student_id: str, db: AsyncSession = Depends(get_db)):
    student = await db.get(Student, student_id)
    if student:
        await db.delete(student)
        await db.commit()
    return {"status": "success"}

@router.get("/api/offerings/{offering_id}/rubric")
async def get_offering_rubric(offering_id: str, db: AsyncSession = Depends(get_db)):
    # Check if QuestionPaper and AnswerKey exist
    qp = (await db.execute(select(QuestionPaper).where(QuestionPaper.class_offering_id == offering_id))).scalar_one_or_none()
    ak = (await db.execute(select(AnswerKey).where(AnswerKey.class_offering_id == offering_id))).scalar_one_or_none()
    
    co = (await db.execute(select(ClassOffering).where(ClassOffering.id == offering_id))).scalar_one_or_none()
    subject_id = co.subject_id if co else None

    if not qp or not ak:
        return {
            "status": "Missing Materials",
            "has_qp": qp is not None,
            "has_ak": ak is not None,
            "rubric_data": [],
            "subject_id": subject_id
        }
        
    # Check if there is a rubric version
    rv = (await db.execute(select(RubricVersion).where(RubricVersion.question_paper_id == qp.id).order_by(RubricVersion.version_number.desc()))).scalars().first()
    
    if not rv:
        return {
            "status": "Ready to Generate",
            "has_qp": True,
            "has_ak": True,
            "rubric_data": [],
            "subject_id": subject_id
        }
        
    # Load items
    from sqlalchemy.orm import selectinload
    rv = (await db.execute(
        select(RubricVersion)
        .options(selectinload(RubricVersion.items))
        .where(RubricVersion.id == rv.id)
    )).scalar_one_or_none()
    
    # Check for addendums if locked
    from app.database.models import RubricAddendum
    for item in rv.items:
        addendums = (await db.execute(select(RubricAddendum).where(RubricAddendum.rubric_item_id == item.id))).scalars().all()
        # Bind to object dynamically for serialization
        setattr(item, 'addendums', addendums)

    # Format status string
    return {
        "status": f"Draft (v{rv.version_number})" if rv.status == RubricStatus.draft else "Locked",
        "is_locked": rv.status == RubricStatus.locked,
        "version_id": rv.id,
        "has_qp": True,
        "has_ak": True,
        "rubric_data": rv.items,
        "subject_id": subject_id
    }

@router.post("/api/offerings/{offering_id}/question-paper")
async def upload_question_paper(
    offering_id: str, 
    file: UploadFile = File(...), 
    db: AsyncSession = Depends(get_db)
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are supported.")
        
    # Check if offering exists
    off = await db.get(ClassOffering, offering_id)
    if not off: raise HTTPException(404, "Class offering not found")

    pdf_dir = os.path.join(STORAGE_DIR, "materials")
    os.makedirs(pdf_dir, exist_ok=True)
    
    qp = (await db.execute(select(QuestionPaper).where(QuestionPaper.class_offering_id == offering_id))).scalar_one_or_none()
    
    if not qp:
        qp = QuestionPaper(class_offering_id=offering_id, original_file_path="", page_count=0)
        db.add(qp)
        await db.commit()
        await db.refresh(qp)
        
    file_path = os.path.join(pdf_dir, f"qp_{qp.id}.pdf")
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # Count pages
    doc = fitz.open(file_path)
    page_count = len(doc)
    doc.close()
    
    qp.original_file_path = file_path
    qp.page_count = page_count
    await db.commit()
    
    return {"status": "success", "id": qp.id}

@router.post("/api/offerings/{offering_id}/answer-key")
async def upload_answer_key(
    offering_id: str, 
    file: UploadFile = File(...), 
    db: AsyncSession = Depends(get_db)
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are supported.")
        
    off = await db.get(ClassOffering, offering_id)
    if not off: raise HTTPException(404, "Class offering not found")

    pdf_dir = os.path.join(STORAGE_DIR, "materials")
    os.makedirs(pdf_dir, exist_ok=True)
    
    ak = (await db.execute(select(AnswerKey).where(AnswerKey.class_offering_id == offering_id))).scalar_one_or_none()
    
    if not ak:
        ak = AnswerKey(class_offering_id=offering_id, original_file_path="", page_count=0)
        db.add(ak)
        await db.commit()
        await db.refresh(ak)
        
    file_path = os.path.join(pdf_dir, f"ak_{ak.id}.pdf")
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    doc = fitz.open(file_path)
    page_count = len(doc)
    doc.close()
    
    ak.original_file_path = file_path
    ak.page_count = page_count
    await db.commit()
    
    return {"status": "success", "id": ak.id}
