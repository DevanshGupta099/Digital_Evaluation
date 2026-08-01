import pytest
import os
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, MagicMock

from app.main import app
from app.database.models import (
    AnswerScript, RubricItem, RubricVersion, QuestionPaper, ClassOffering,
    RubricStatus, SegmentationRun, OCRPage, EvaluationRun, RunType, AnswerScriptStatus,
    Annotation, ReviewFlag, FlagType
)
from tests.conftest import TestingSessionLocal

@pytest.mark.asyncio
async def test_annotation_fuzzy_match_and_flag(setup_db, tmp_path):
    """
    Test that a slightly off quote is successfully matched and draws an annotation,
    while a completely bad quote raises an 'unmatched_annotation' flag.
    """
    # Create a dummy pdf file so fitz.open doesn't fail immediately before our mock kicks in, 
    # or we can just patch fitz.open entirely.
    fake_pdf = tmp_path / "dummy.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4\n")
    
    async with TestingSessionLocal() as session:
        # Hierarchy
        co = ClassOffering(
            id="co2", department_id="d1", course_id="c1", section_id="s1",
            academic_term_id="a1", subject_id="su1"
        )
        session.add(co)
        qp = QuestionPaper(id="qp2", class_offering_id="co2", original_file_path=str(fake_pdf), page_count=3)
        session.add(qp)
        rv = RubricVersion(id="rv2", question_paper_id="qp2", version_number=1, status=RubricStatus.locked)
        session.add(rv)
        
        session.add(RubricItem(
            id="ri2", rubric_version_id="rv2", question_number="Q1",
            max_marks=10, allowed_increments=[0.0, 1.0, 2.0]
        ))
        session.add(RubricItem(
            id="ri3", rubric_version_id="rv2", question_number="Q2",
            max_marks=10, allowed_increments=[0.0, 1.0, 2.0]
        ))
        
        script = AnswerScript(
            id="script2", student_id="stu2", class_offering_id="co2",
            original_file_path=str(fake_pdf), status=AnswerScriptStatus.graded
        )
        session.add(script)
        
        # We simulate a paragraph on the page
        ocr_words = [
            {"text": "The", "bbox": [10, 10, 20, 10], "line_id": "L1"},
            {"text": "mitochondria", "bbox": [35, 10, 80, 10], "line_id": "L1"},
            {"text": "is", "bbox": [120, 10, 15, 10], "line_id": "L1"},
            {"text": "the", "bbox": [140, 10, 20, 10], "line_id": "L1"},
            {"text": "powerhouse", "bbox": [10, 30, 80, 10], "line_id": "L2"},
            {"text": "of", "bbox": [95, 30, 15, 10], "line_id": "L2"},
            {"text": "the", "bbox": [115, 30, 20, 10], "line_id": "L2"},
            {"text": "cell.", "bbox": [140, 30, 30, 10], "line_id": "L2"},
        ]
        
        session.add(OCRPage(
            answer_script_id="script2", page_number=1, image_path="",
            scale_factor=2.0, rotation=0, ocr_json={"words": ocr_words}
        ))
        
        session.add(SegmentationRun(
            id="seg2", answer_script_id="script2", rubric_version_id="rv2",
            mappings=[
                {"question_number": "Q1", "pages": [1], "confidence": 0.9},
                {"question_number": "Q2", "pages": [1], "confidence": 0.9}
            ]
        ))
        
        # Good Match Evaluation Run (Q1) - slightly misspelled "mitochodria"
        session.add(EvaluationRun(
            answer_script_id="script2", question_number="Q1", run_type=RunType.ai_pass_1,
            marks_awarded=10.0, evidence_quote="The mitochodria is the powerhouse", reasoning="Correct"
        ))
        
        # Bad Match Evaluation Run (Q2)
        session.add(EvaluationRun(
            answer_script_id="script2", question_number="Q2", run_type=RunType.ai_pass_1,
            marks_awarded=0.0, evidence_quote="Nucleus controls everything", reasoning="Wrong"
        ))
        
        await session.commit()
        
    with patch("app.annotation.service.fitz.open") as mock_fitz:
        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_page.rect.width = 800
        mock_doc.__getitem__.return_value = mock_page
        mock_fitz.return_value = mock_doc
        
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/annotation/run/script2")
            assert resp.status_code == 200
            
            # Check DB
            async with TestingSessionLocal() as session:
                from sqlalchemy import select
                # Should have 1 ReviewFlag for Q2
                flags = (await session.execute(select(ReviewFlag).where(ReviewFlag.answer_script_id == "script2"))).scalars().all()
                assert len(flags) == 1
                assert flags[0].flag_type == FlagType.unmatched_annotation
                assert flags[0].question_number == "Q2"
                
                # Should have Annotation rows for Q1
                anns = (await session.execute(select(Annotation).where(Annotation.answer_script_id == "script2"))).scalars().all()
                assert len(anns) > 0
                
                # We expect 2 lines (L1 and L2) to be matched since "The mitochondria is the" is on L1 and "powerhouse" is on L2
                assert len(anns) == 2
                
                # Verify PyMuPDF drawing was called
                assert mock_page.draw_polyline.call_count == 2
                assert mock_page.draw_rect.call_count == 1 # Question header total
                assert mock_page.insert_text.call_count == 1 # Question header total
