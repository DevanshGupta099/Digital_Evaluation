"""End-to-end pipeline test with mock OCR and a fake LLM: upload -> OCR ->
segment -> match -> grade -> annotate -> report, all offline."""
import json

import fitz
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.grading.engine import GradingEngine
from app.models.db import Base
from app.models.entities import EvaluationRecord, QuestionBankEntry, Report, Script
from app.ocr.mock_provider import MockOCRProvider
from app.pipeline import process_script

SCRIPT_TEXT = (
    "Q1. Photosynthesis converts light energy into chemical energy\n"
    "It happens inside the chloroplast\n"
    "Q2. Mitochondria make ATP for the cell through respiration\n"
)


class _FakeBlock:
    type = "text"

    def __init__(self, text):
        self.text = text


class _FakeClient:
    def __init__(self):
        class _Messages:
            def create(inner, **kwargs):
                prompt = kwargs["messages"][0]["content"]
                # Determine which question is being graded from the prompt header.
                qnum = prompt.split("## Question ", 1)[1].split("\n", 1)[0].strip()
                # Cite the first numbered line that appears in the prompt.
                answer_block = prompt.split("evidence)\n", 1)[1]
                first_line = int(answer_block.split("[", 1)[1].split("]", 1)[0])
                return type("R", (), {"content": [_FakeBlock(json.dumps({
                    "question_number": qnum,
                    "point_evaluations": [{
                        "rubric_point_id": f"{qnum}a",
                        "status": "present",
                        "marks_awarded": 2.0,
                        "evidence_line_indices": [first_line],
                        "evidence_quote": "cited",
                        "confidence": 0.92,
                        "reasoning": "correct",
                    }],
                    "overall_confidence": 0.92,
                    "examiner_note": "",
                }))]})()

        self.messages = _Messages()


@pytest.fixture
def session(tmp_path, monkeypatch):
    from app import config

    monkeypatch.setattr(config.settings, "storage_dir", str(tmp_path))
    engine = create_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _blank_pdf(pages=1) -> bytes:
    doc = fitz.open()
    for _ in range(pages):
        doc.new_page(width=612, height=792)
    return doc.tobytes()


def test_full_pipeline(session, tmp_path):
    for qnum, qtext, ans in [
        ("1", "Explain photosynthesis and where it occurs",
         "Photosynthesis converts light energy to chemical energy in chloroplasts"),
        ("2", "What do mitochondria do",
         "Mitochondria produce ATP via cellular respiration"),
    ]:
        session.add(QuestionBankEntry(
            exam_id="exam1", question_number=qnum, question_text=qtext, model_answer=ans,
            rubric_points=[{"id": f"{qnum}a", "description": "main point", "max_marks": 2,
                            "acceptable_variations": []}],
            calibration_examples=[],
        ))
    pdf_path = tmp_path / "script.pdf"
    pdf_path.write_bytes(_blank_pdf())
    script = Script(original_filename="script.pdf", original_path=str(pdf_path))
    session.add(script)
    session.commit()

    process_script(
        script.id, "exam1", session,
        ocr_provider=MockOCRProvider(page_texts=[SCRIPT_TEXT]),
        engine=GradingEngine(client=_FakeClient()),
    )

    session.refresh(script)
    assert script.status == "annotated", script.error
    evaluations = session.query(EvaluationRecord).filter_by(script_id=script.id).all()
    assert {e.question_number for e in evaluations} == {"1", "2"}
    assert all(e.marks_awarded == 2.0 for e in evaluations)

    report = session.query(Report).filter_by(script_id=script.id).one()
    assert report.summary["total_awarded"] == 4.0
    assert report.summary["total_max"] == 4.0
    assert report.summary["needs_human_review"] is False

    with fitz.open(report.annotated_pdf_path) as doc:
        assert len(doc[0].get_drawings()) >= 3  # ticks + badges + total box
        assert "Total: 4 / 4" in doc[0].get_text()
