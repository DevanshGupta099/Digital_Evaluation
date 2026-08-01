import asyncio
import os
import shutil
import logging
from dotenv import load_dotenv

load_dotenv()

from app.database.session import async_session_maker
from app.database.models import (
    AnswerScript, AnswerScriptStatus, ClassOffering, Department, Course,
    Section, AcademicTerm, Subject, QuestionPaper, RubricVersion, RubricStatus,
    RubricItem, Student, ReviewFlag, EvaluationRun
)
from app.ingestion.service import process_pdf_pipeline
from app.segmentation.service import run_segmentation_pipeline
from app.grading.service import grade_question_sync
from app.grading.schemas import GradingJobRequest
from app.annotation.service import annotate_script
from app.review.service import reconcile_evaluations, compute_script_status

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run_integration_test():
    async with async_session_maker() as db:
        logger.info("Setting up database with a pre-approved test rubric...")
        
        # 1. Setup Hierarchy
        dept = Department(id="e2e_dept", name="E2E Department")
        course = Course(id="e2e_course", name="E2E Course", department_id="e2e_dept")
        section = Section(id="e2e_sec", name="E2E Section", course_id="e2e_course")
        term = AcademicTerm(id="e2e_term", semester="1", year=2025)
        subj = Subject(id="e2e_subj", name="E2E Subject")
        
        co = ClassOffering(
            id="e2e_offering", department_id="e2e_dept", course_id="e2e_course",
            section_id="e2e_sec", academic_term_id="e2e_term", subject_id="e2e_subj"
        )
        
        stu = Student(id="e2e_stu", roll_number="E2E_001", name="Test Student", section_id="e2e_sec")
        
        qp = QuestionPaper(id="e2e_qp", class_offering_id="e2e_offering", original_file_path="", page_count=5)
        rv = RubricVersion(id="e2e_rv", question_paper_id="e2e_qp", version_number=1, status=RubricStatus.locked)
        
        # Test Rubric Items for Q1 and Q2
        r1 = RubricItem(
            id="e2e_r1", rubric_version_id="e2e_rv", question_number="1", subpart_id="a",
            max_marks=5.0, allowed_increments=[0.0, 1.0, 2.0, 3.0, 4.0, 5.0],
            expected_concepts=["concept 1", "concept 2"], accepted_alternates=["alt 1"]
        )
        r2 = RubricItem(
            id="e2e_r2", rubric_version_id="e2e_rv", question_number="2", subpart_id="a",
            max_marks=3.0, allowed_increments=[0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0],
            expected_concepts=["concept A"], accepted_alternates=[]
        )
        
        try:
            db.add(dept)
            await db.flush()
            db.add(course)
            await db.flush()
            db.add(section)
            await db.flush()
            db.add(term)
            await db.flush()
            db.add(subj)
            await db.flush()
            db.add(co)
            await db.flush()
            db.add(stu)
            await db.flush()
            db.add(qp)
            await db.flush()
            db.add(rv)
            await db.flush()
            db.add(r1)
            db.add(r2)
            await db.commit()
        except Exception as e:
            await db.rollback()
            logger.info(f"Test hierarchy insertion exception: {e}")
            logger.info("Test hierarchy likely exists, proceeding...")
            
        # 2. Setup Answer Script
        sample_pdf_name = "sample_script.pdf"
        sample_pdf_path = f"storage/pdfs/{sample_pdf_name}"
        
        # Let's just pick any existing PDF to act as our sample
        existing_pdfs = [f for f in os.listdir("storage/pdfs") if f.endswith(".pdf") and f != sample_pdf_name]
        if not existing_pdfs:
            logger.error("No PDFs found in storage/pdfs to use as a sample!")
            return
            
        # Copy the first found PDF as our sample
        shutil.copy(f"storage/pdfs/{existing_pdfs[0]}", sample_pdf_path)
        
        import uuid
        script_id = f"e2e_script_{uuid.uuid4().hex[:6]}"
        script = AnswerScript(
            id=script_id, student_id="e2e_stu", class_offering_id="e2e_offering",
            original_file_path=sample_pdf_path, status=AnswerScriptStatus.uploaded
        )
        
        try:
            db.add(script)
            await db.commit()
        except Exception as e:
            await db.rollback()
            logger.info(f"AnswerScript insertion exception: {e}")
            
        logger.info(f"--- Phase 1: Ingestion ---")
        try:
            await process_pdf_pipeline(db, script_id, sample_pdf_path, "storage")
            logger.info("Ingestion complete.")
        except Exception as e:
            logger.error(f"Ingestion failed: {e}")
            return
            
        logger.info(f"--- Phase 2: Segmentation ---")
        try:
            seg_resp = await run_segmentation_pipeline(db, script_id)
            logger.info(f"Segmentation complete: {seg_resp.message}")
        except Exception as e:
            logger.error(f"Segmentation failed: {e}")
            return
            
        logger.info(f"--- Phase 3: Grading ---")
        # Grade each question we have a rubric for
        questions_to_grade = ["1", "2"]
        for q in questions_to_grade:
            logger.info(f"Grading Q{q}...")
            try:
                req = GradingJobRequest(answer_script_id=script_id, question_number=q)
                runs = await grade_question_sync(db, req)
                logger.info(f"Q{q} graded. 2 models evaluated it.")
            except Exception as e:
                logger.error(f"Grading Q{q} failed: {e}")
                
        logger.info(f"--- Phase 4: Reconciliation & Flagging ---")
        await reconcile_evaluations(db, script_id)
        status = await compute_script_status(db, script_id)
        logger.info(f"Reconciliation complete. Final script status: {status}")
        
        logger.info(f"--- Phase 5: Annotation ---")
        try:
            out_pdf = await annotate_script(db, script_id)
            logger.info(f"Annotation complete! Annotated PDF available at: {out_pdf}")
        except Exception as e:
            logger.error(f"Annotation failed: {e}")
            
        logger.info("\n--- E2E Test Completed ---")
        logger.info("You can now open the React UI and navigate to the Review Queue for the 'E2E Subject' to view the flags!")

if __name__ == "__main__":
    asyncio.run(run_integration_test())
