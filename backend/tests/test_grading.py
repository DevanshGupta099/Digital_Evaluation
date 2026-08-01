import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.database.models import (
    AnswerScript, RubricItem, RubricVersion, QuestionPaper, ClassOffering,
    RubricStatus, SegmentationRun, OCRPage, EvaluationRun, RunType, AnswerScriptStatus
)
from app.grading.schemas import build_grading_schema
from tests.conftest import TestingSessionLocal

@pytest.mark.asyncio
async def test_grading_schema_builder():
    """Test that the dynamic schema restricts marks appropriately."""
    allowed_increments = [0.0, 0.5, 1.0, 1.5]
    schema = build_grading_schema(allowed_increments)
    json_schema = schema.model_json_schema()
    
    properties = json_schema["properties"]
    assert "marks_awarded" in properties
    assert "reasoning" in properties
    assert "evidence_quote" in properties
    assert "max_marks" not in properties
    
    # Check that $defs contains the enum values for Marks
    defs = json_schema.get("$defs", {})
    marks_def = defs.get("Marks", {})
    assert "enum" in marks_def
    assert set(marks_def["enum"]) == set(allowed_increments)

@pytest.mark.asyncio
async def test_grading_sync_endpoint(setup_db):
    """
    Test the sync grading endpoint which fires mocks for Claude and Gemini,
    validates the schema constraint, and saves 2 EvaluationRuns.
    """
    async with TestingSessionLocal() as session:
        # Seed basic hierarchy
        co = ClassOffering(
            id="co1", department_id="d1", course_id="c1", section_id="s1",
            academic_term_id="a1", subject_id="su1"
        )
        session.add(co)
        qp = QuestionPaper(id="qp1", class_offering_id="co1", original_file_path="", page_count=3)
        session.add(qp)
        rv = RubricVersion(id="rv1", question_paper_id="qp1", version_number=1, status=RubricStatus.locked)
        session.add(rv)
        
        # Seed RubricItem with allowed increments
        session.add(RubricItem(
            id="ri1", rubric_version_id="rv1", question_number="Q1",
            max_marks=10, allowed_increments=[0.0, 1.0, 2.0, 3.0]
        ))
        
        # Seed AnswerScript & OCR
        script = AnswerScript(
            id="script1", student_id="stu1", class_offering_id="co1",
            original_file_path="", status=AnswerScriptStatus.segmented
        )
        session.add(script)
        
        session.add(OCRPage(
            answer_script_id="script1", page_number=1, image_path="",
            scale_factor=1, rotation=0, ocr_json={"words": [{"text": "Hello world"}]}
        ))
        
        # Seed SegmentationRun mapping Q1 -> Page 1
        session.add(SegmentationRun(
            id="seg1", answer_script_id="script1", rubric_version_id="rv1",
            mappings=[{"question_number": "Q1", "pages": [1], "confidence": 0.9}]
        ))
        await session.commit()
        
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/grading/run-sync", json={
            "answer_script_id": "script1",
            "question_number": "Q1"
        })
        
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        runs = data["evaluation_runs"]
        assert len(runs) == 2
        
        # Ensure we got one of each type
        types = [r["run_type"] for r in runs]
        assert RunType.ai_pass_1.value in types
        assert RunType.ai_pass_2.value in types
        
        # Since the mock selects the first enum value (0.0), both should be 0.0
        assert runs[0]["marks_awarded"] == 0.0
        assert runs[1]["marks_awarded"] == 0.0
