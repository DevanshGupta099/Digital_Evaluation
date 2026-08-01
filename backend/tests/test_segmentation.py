import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.database.models import (
    AnswerScript, OCRPage, RubricVersion, RubricItem, RubricStatus,
    AnswerScriptStatus, ReviewFlag, FlagType, SegmentationRun,
    ClassOffering, QuestionPaper
)
from app.database.session import get_db

@pytest.mark.asyncio
async def test_segmentation_pipeline_mocked(setup_db):
    """
    Tests the segmentation logic:
    1. Setup DB with AnswerScript, OCR pages (incl text with 'continued on page 3').
    2. Setup Rubric mapped to the ClassOffering.
    3. Trigger segmentation.
    4. Assert mappings, orphaned content, and review flags.
    """
    # Overriding DB handled globally in test_ingestion, 
    # but since this runs in the same test suite, `setup_db` creates fresh tables.
    
    # We need an explicit session to seed data
    from tests.conftest import TestingSessionLocal
    async with TestingSessionLocal() as session:
        # Seed ClassOffering
        co = ClassOffering(
            id="co1", department_id="d1", course_id="c1", section_id="s1",
            academic_term_id="a1", subject_id="su1"
        )
        session.add(co)
        
        # Seed QuestionPaper
        qp = QuestionPaper(id="qp1", class_offering_id="co1", original_file_path="", page_count=3)
        session.add(qp)
        
        # Seed RubricVersion & Items
        rv = RubricVersion(id="rv1", question_paper_id="qp1", version_number=1, status=RubricStatus.locked)
        session.add(rv)
        
        # Expecting Q1, Q2, Q3
        session.add_all([
            RubricItem(rubric_version_id="rv1", question_number="Q1", max_marks=10, allowed_increments=[1]),
            RubricItem(rubric_version_id="rv1", question_number="Q2", max_marks=10, allowed_increments=[1]),
            RubricItem(rubric_version_id="rv1", question_number="Q3", max_marks=10, allowed_increments=[1]),
        ])
        
        # Seed AnswerScript (ocr_done)
        script = AnswerScript(
            id="script1", student_id="stu1", class_offering_id="co1",
            original_file_path="", status=AnswerScriptStatus.ocr_done
        )
        session.add(script)
        
        # Seed OCRPages to trigger the non-linear logic mock in llm.py
        p1 = OCRPage(answer_script_id="script1", page_number=1, image_path="", scale_factor=1, rotation=0, ocr_json={"words": [{"text": "Answer 1 part A"}]})
        p2 = OCRPage(answer_script_id="script1", page_number=2, image_path="", scale_factor=1, rotation=0, ocr_json={"words": [{"text": "Random doodle here"}]})
        p3 = OCRPage(answer_script_id="script1", page_number=3, image_path="", scale_factor=1, rotation=0, ocr_json={"words": [{"text": "Continued on page 3 for Q1"}]})
        
        session.add_all([p1, p2, p3])
        await session.commit()
    
    # Trigger the endpoint
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/segmentation/run/script1")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        run_id = data["segmentation_run_id"]
        
    # Verify the database state
    async with TestingSessionLocal() as session:
        # Script status
        script = await session.get(AnswerScript, "script1")
        assert script.status == AnswerScriptStatus.segmented
        
        # SegmentationRun
        run = await session.get(SegmentationRun, run_id)
        assert run is not None
        assert len(run.mappings) == 2
        
        # Check non-linear mapping (Q1 mapped to pages [1, 3])
        q1_map = next((m for m in run.mappings if m["question_number"] == "Q1"), None)
        assert q1_map is not None
        assert set(q1_map["pages"]) == {1, 3}
        assert q1_map["confidence"] == 0.95
        
        # Orphaned content stored properly
        assert len(run.orphaned_content) == 1
        assert run.orphaned_content[0]["page"] == 2
        
        # Review Flags
        from sqlalchemy import select
        flags_result = await session.execute(select(ReviewFlag).where(ReviewFlag.answer_script_id == "script1"))
        flags = flags_result.scalars().all()
        
        # We expect 1 flag for unmapped Q2 (orphaned_content flag)
        assert len(flags) == 1
        assert flags[0].flag_type == FlagType.orphaned_content
        assert flags[0].question_number == "Q2"
