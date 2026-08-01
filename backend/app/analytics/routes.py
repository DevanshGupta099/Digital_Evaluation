from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import csv
import io

from app.database.session import get_db
from app.database.models import (
    AnswerScript, AnswerScriptStatus, EvaluationRun, RunType, 
    ReviewFlag, FlagStatus, Student, ClassOffering, SegmentationRun, RubricItem, UsageLog
)
from sqlalchemy import func

router = APIRouter(tags=["analytics"])

@router.get("/api/metrics/usage/{class_offering_id}")
async def get_usage_metrics(class_offering_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(
            func.sum(UsageLog.input_tokens).label("input"),
            func.sum(UsageLog.cache_read_input_tokens).label("cache_read"),
            func.sum(UsageLog.cache_creation_input_tokens).label("cache_creation"),
            func.sum(UsageLog.output_tokens).label("output"),
            func.sum(UsageLog.estimated_cost_usd).label("cost")
        ).where(UsageLog.class_offering_id == class_offering_id)
    )
    row = result.first()
    return {
        "input_tokens": row.input or 0,
        "cache_read_input_tokens": row.cache_read or 0,
        "cache_creation_input_tokens": row.cache_creation or 0,
        "output_tokens": row.output or 0,
        "estimated_cost_usd": float(row.cost or 0.0)
    }

@router.get("/api/analytics")
async def get_analytics(offering_id: str = None):
    # Stub for Phase 5 Analytics (backward compatibility for Dashboard.jsx temporarily)
    return {
        "summary": {
            "class_average_percent": 0,
            "pass_rate_percent": 0,
            "total_evaluated": 0,
            "total_flagged_scripts": 0
        }
    }

@router.get("/api/analytics/dashboard/{class_offering_id}")
async def get_dashboard_analytics(class_offering_id: str, db: AsyncSession = Depends(get_db)):
    offering = await db.get(ClassOffering, class_offering_id)
    if not offering:
        raise HTTPException(status_code=404, detail="Class offering not found")
        
    scripts = (await db.execute(
        select(AnswerScript).where(AnswerScript.class_offering_id == class_offering_id)
    )).scalars().all()
    
    script_ids = [s.id for s in scripts]
    if not script_ids:
        return {
            "summary": {
                "class_average": 0.0, "highest_score": 0.0, "lowest_score": 0.0, "pass_rate": 0.0,
                "override_rate": 0.0
            },
            "status_counts": {"graded": 0, "provisional": 0, "final": 0, "pending": 0},
            "question_averages": [],
            "open_flags_by_type": {},
            "results_published": offering.results_published
        }
        
    runs = (await db.execute(
        select(EvaluationRun).where(EvaluationRun.answer_script_id.in_(script_ids))
    )).scalars().all()
    
    flags = (await db.execute(
        select(ReviewFlag).where(ReviewFlag.answer_script_id.in_(script_ids), ReviewFlag.status == FlagStatus.open)
    )).scalars().all()
    
    seg_runs = (await db.execute(
        select(SegmentationRun).where(SegmentationRun.answer_script_id.in_(script_ids))
    )).scalars().all()
    
    rubric_version_ids = list(set([s.rubric_version_id for s in seg_runs if s.rubric_version_id]))
    
    max_marks_total = 0.0
    if rubric_version_ids:
        # Assuming all scripts in offering share same rubric version
        r_items = (await db.execute(
            select(RubricItem).where(RubricItem.rubric_version_id == rubric_version_ids[0])
        )).scalars().all()
        max_marks_total = sum(float(r.max_marks) for r in r_items)
        
    # Aggregate student totals
    student_totals = {}
    
    # Calculate per-question
    # We resolve the final mark for a question: human_final > ai_pass_1
    resolved_marks = {} # (script_id, q_num, sub_id) -> float
    human_overridden_count = 0
    total_evaluated_questions = 0
    
    # Group runs
    run_groups = {}
    for r in runs:
        k = (r.answer_script_id, r.question_number, r.subpart_id)
        if k not in run_groups:
            run_groups[k] = []
        run_groups[k].append(r)
        
    for k, grp in run_groups.items():
        script_id, q, sub = k
        human = next((r for r in grp if r.run_type == RunType.human_final), None)
        ai1 = next((r for r in grp if r.run_type == RunType.ai_pass_1), None)
        
        if ai1:
            total_evaluated_questions += 1
            if human:
                human_overridden_count += 1
                
        final_mark = float(human.marks_awarded) if human else (float(ai1.marks_awarded) if ai1 else 0.0)
        resolved_marks[k] = final_mark
        student_totals[script_id] = student_totals.get(script_id, 0.0) + final_mark
        
    class_scores = list(student_totals.values())
    
    class_average = sum(class_scores) / len(class_scores) if class_scores else 0.0
    highest = max(class_scores) if class_scores else 0.0
    lowest = min(class_scores) if class_scores else 0.0
    
    pass_threshold = 0.40 * max_marks_total if max_marks_total > 0 else 0
    passed = len([s for s in class_scores if s >= pass_threshold])
    pass_rate = (passed / len(class_scores)) * 100 if class_scores else 0.0
    
    override_rate = (human_overridden_count / total_evaluated_questions) * 100 if total_evaluated_questions > 0 else 0.0
    
    status_counts = {"graded": 0, "provisional": 0, "final": 0, "pending": 0}
    for s in scripts:
        status_counts[s.status.value] = status_counts.get(s.status.value, 0) + 1
        
    q_totals = {}
    q_counts = {}
    for k, mark in resolved_marks.items():
        q_label = f"{k[1]}_{k[2]}" if k[2] else k[1]
        q_totals[q_label] = q_totals.get(q_label, 0.0) + mark
        q_counts[q_label] = q_counts.get(q_label, 0) + 1
        
    q_averages = [
        {"question": q, "average": round(q_totals[q] / q_counts[q], 2)}
        for q in sorted(q_totals.keys())
    ]
    
    flag_counts = {}
    for f in flags:
        flag_counts[f.flag_type.value] = flag_counts.get(f.flag_type.value, 0) + 1
        
    return {
        "summary": {
            "class_average": round(class_average, 2),
            "highest_score": round(highest, 2),
            "lowest_score": round(lowest, 2),
            "pass_rate": round(pass_rate, 1),
            "override_rate": round(override_rate, 1)
        },
        "status_counts": status_counts,
        "question_averages": q_averages,
        "open_flags_by_type": flag_counts,
        "results_published": offering.results_published
    }

@router.get("/api/analytics/export/{class_offering_id}")
async def export_class_marks(class_offering_id: str, db: AsyncSession = Depends(get_db)):
    offering = await db.get(ClassOffering, class_offering_id)
    if not offering:
        raise HTTPException(status_code=404, detail="Class offering not found")
        
    scripts = (await db.execute(
        select(AnswerScript).where(AnswerScript.class_offering_id == class_offering_id)
    )).scalars().all()
    
    student_ids = [s.student_id for s in scripts if s.student_id]
    students = []
    if student_ids:
        students = (await db.execute(
            select(Student).where(Student.id.in_(student_ids))
        )).scalars().all()
    stu_map = {s.id: s for s in students}
    
    script_ids = [s.id for s in scripts]
    runs = []
    if script_ids:
        runs = (await db.execute(
            select(EvaluationRun).where(EvaluationRun.answer_script_id.in_(script_ids))
        )).scalars().all()
        
    run_groups = {}
    for r in runs:
        k = (r.answer_script_id, r.question_number, r.subpart_id)
        if k not in run_groups:
            run_groups[k] = []
        run_groups[k].append(r)
        
    resolved_marks = {}
    for k, grp in run_groups.items():
        human = next((r for r in grp if r.run_type == RunType.human_final), None)
        ai1 = next((r for r in grp if r.run_type == RunType.ai_pass_1), None)
        final_mark = float(human.marks_awarded) if human else (float(ai1.marks_awarded) if ai1 else 0.0)
        resolved_marks[k] = final_mark
        
    student_totals = {}
    for k, mark in resolved_marks.items():
        script_id = k[0]
        student_totals[script_id] = student_totals.get(script_id, 0.0) + mark
        
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Student Roll Number", "Student Name", "Status", "Total Marks Awarded"])
    
    for script in scripts:
        stu = stu_map.get(script.student_id)
        roll = stu.roll_number if stu else "Unknown"
        name = stu.name if stu else "Unknown"
        tot = student_totals.get(script.id, 0.0)
        writer.writerow([roll, name, script.status.value, tot])
        
    response = Response(content=output.getvalue(), media_type="text/csv")
    response.headers["Content-Disposition"] = f"attachment; filename=class_marks_{class_offering_id}.csv"
    return response

@router.get("/api/analytics/export/csv/{class_offering_id}")
async def export_class_marks_lms_csv(class_offering_id: str, db: AsyncSession = Depends(get_db)):
    """
    Standardized CSV for LMS integrations.
    Expected Layout: StudentID, FirstName, LastName, TotalScore, Status
    """
    offering = await db.get(ClassOffering, class_offering_id)
    if not offering:
        raise HTTPException(status_code=404, detail="Class offering not found")
        
    scripts = (await db.execute(select(AnswerScript).where(AnswerScript.class_offering_id == class_offering_id))).scalars().all()
    
    student_ids = [s.student_id for s in scripts if s.student_id]
    students = (await db.execute(select(Student).where(Student.id.in_(student_ids)))).scalars().all() if student_ids else []
    stu_map = {s.id: s for s in students}
    
    script_ids = [s.id for s in scripts]
    runs = (await db.execute(select(EvaluationRun).where(EvaluationRun.answer_script_id.in_(script_ids)))).scalars().all() if script_ids else []
        
    run_groups = {}
    for r in runs:
        k = (r.answer_script_id, r.question_number, r.subpart_id)
        if k not in run_groups:
            run_groups[k] = []
        run_groups[k].append(r)
        
    resolved_marks = {}
    for k, grp in run_groups.items():
        human = next((r for r in grp if r.run_type == RunType.human_final), None)
        ai1 = next((r for r in grp if r.run_type == RunType.ai_pass_1), None)
        final_mark = float(human.marks_awarded) if human else (float(ai1.marks_awarded) if ai1 else 0.0)
        resolved_marks[k] = final_mark
        
    student_totals = {}
    for k, mark in resolved_marks.items():
        script_id = k[0]
        student_totals[script_id] = student_totals.get(script_id, 0.0) + mark
        
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["StudentID", "FirstName", "LastName", "TotalScore", "Status"])
    
    for script in scripts:
        stu = stu_map.get(script.student_id)
        roll = stu.roll_number if stu else "Unknown"
        # Split name for LMS format
        name_parts = stu.name.split(" ", 1) if stu and stu.name else ["Unknown", ""]
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ""
        tot = student_totals.get(script.id, 0.0)
        writer.writerow([roll, first_name, last_name, tot, script.status.value])
        
    response = Response(content=output.getvalue(), media_type="text/csv")
    response.headers["Content-Disposition"] = f"attachment; filename=lms_grades_{class_offering_id}.csv"
    return response

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

@router.get("/api/analytics/export/pdf/{class_offering_id}")
async def export_class_marks_pdf(class_offering_id: str, db: AsyncSession = Depends(get_db)):
    offering = await db.get(ClassOffering, class_offering_id)
    if not offering:
        raise HTTPException(status_code=404, detail="Class offering not found")
        
    scripts = (await db.execute(select(AnswerScript).where(AnswerScript.class_offering_id == class_offering_id))).scalars().all()
    
    student_ids = [s.student_id for s in scripts if s.student_id]
    students = (await db.execute(select(Student).where(Student.id.in_(student_ids)))).scalars().all() if student_ids else []
    stu_map = {s.id: s for s in students}
    
    script_ids = [s.id for s in scripts]
    runs = (await db.execute(select(EvaluationRun).where(EvaluationRun.answer_script_id.in_(script_ids)))).scalars().all() if script_ids else []
        
    run_groups = {}
    for r in runs:
        k = (r.answer_script_id, r.question_number, r.subpart_id)
        if k not in run_groups:
            run_groups[k] = []
        run_groups[k].append(r)
        
    resolved_marks = {}
    for k, grp in run_groups.items():
        human = next((r for r in grp if r.run_type == RunType.human_final), None)
        ai1 = next((r for r in grp if r.run_type == RunType.ai_pass_1), None)
        final_mark = float(human.marks_awarded) if human else (float(ai1.marks_awarded) if ai1 else 0.0)
        resolved_marks[k] = final_mark
        
    student_totals = {}
    for k, mark in resolved_marks.items():
        script_id = k[0]
        student_totals[script_id] = student_totals.get(script_id, 0.0) + mark
        
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    
    styles = getSampleStyleSheet()
    title_style = styles['Heading1']
    
    elements.append(Paragraph(f"Official Gradesheet", title_style))
    elements.append(Paragraph(f"Class Offering ID: {class_offering_id}", styles['Normal']))
    elements.append(Spacer(1, 12))
    
    data = [["Roll Number", "Name", "Total Score", "Score Status"]]
    
    for script in scripts:
        stu = stu_map.get(script.student_id)
        roll = stu.roll_number if stu else "Unknown"
        name = stu.name if stu else "Unknown"
        tot = student_totals.get(script.id, 0.0)
        status_label = "FINAL" if script.status == AnswerScriptStatus.final else "PROVISIONAL"
        data.append([roll, name, f"{tot:.2f}", status_label])
        
    table = Table(data, colWidths=[100, 200, 100, 100])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('ALIGN', (0, 1), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    
    elements.append(table)
    doc.build(elements)
    
    pdf = buffer.getvalue()
    buffer.close()
    
    response = Response(content=pdf, media_type="application/pdf")
    response.headers["Content-Disposition"] = f"attachment; filename=gradesheet_{class_offering_id}.pdf"
    return response

from pydantic import BaseModel
from app.database.models import AuditLog
from fastapi import Request

class PublishRequest(BaseModel):
    user_name: str
    user_role: str

@router.post("/api/offerings/{class_offering_id}/publish")
async def publish_results(class_offering_id: str, req: PublishRequest, db: AsyncSession = Depends(get_db)):
    offering = await db.get(ClassOffering, class_offering_id)
    if not offering:
        raise HTTPException(status_code=404, detail="Offering not found")

    # Check if all scripts are final
    scripts_result = await db.execute(select(AnswerScript).where(AnswerScript.class_offering_id == class_offering_id))
    scripts = scripts_result.scalars().all()
    
    if not scripts:
        raise HTTPException(status_code=400, detail="No scripts in this offering to publish")
        
    non_final = [s for s in scripts if s.status != AnswerScriptStatus.final]
    if non_final:
        # In a real app, we might allow publishing with some pending, but requirement said:
        # "only enabled once every script in the roster is "final" (or explicitly excluding a chosen subset)"
        # We will enforce all final here.
        raise HTTPException(status_code=400, detail=f"Cannot publish: {len(non_final)} scripts are not marked final.")

    offering.results_published = True
    
    audit = AuditLog(
        class_offering_id=class_offering_id,
        action_type="results_published",
        user_name=req.user_name,
        user_role=req.user_role,
        details={"total_scripts": len(scripts)}
    )
    db.add(audit)
    await db.commit()
    
    return {"message": "Results published successfully"}

@router.get("/api/analytics/audit/{class_offering_id}")
async def get_audit_logs(class_offering_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.class_offering_id == class_offering_id)
        .order_by(AuditLog.created_at.desc())
    )
    logs = result.scalars().all()
    
    return [
        {
            "id": l.id,
            "action_type": l.action_type,
            "user_name": l.user_name,
            "user_role": l.user_role,
            "details": l.details,
            "created_at": l.created_at.isoformat()
        } for l in logs
    ]
