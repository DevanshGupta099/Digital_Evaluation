"""End-to-end pipeline orchestration for one script.

Runs Stage 2 (OCR) -> Stage 3 (segment + match) -> Stage 4 (grade) ->
Stage 5 (annotate + report), persisting each stage's output as separate
records. Designed to run in a background task (FastAPI BackgroundTasks now;
swap in Celery/RQ without changing stage code).

Unmatched segments are recorded as zero-mark, flagged results — visible in the
review queue, never silently graded or dropped.
"""
from __future__ import annotations

import json
import logging
import os

from sqlalchemy.orm import Session

from .annotation.annotator import ScriptAnnotator
from .config import settings
from .grading.engine import GradingEngine
from .models.entities import EvaluationRecord, OCRSegmentRecord, QuestionBankEntry, Report, Script
from .ocr import OCRResult, get_ocr_provider
from .ocr.preprocess import images_to_pdf, render_document
from .reports.report import build_annotations, build_summary
from .schemas.grading import (
    GradingResult,
    QuestionEvaluation,
    ReviewFlag,
    Rubric,
    RubricPoint,
)
from .segmentation import match_segments, segment_script

logger = logging.getLogger(__name__)


def load_rubrics(session: Session, exam_id: str) -> list[Rubric]:
    entries = (
        session.query(QuestionBankEntry).filter(QuestionBankEntry.exam_id == exam_id).all()
    )
    return [
        Rubric(
            question_number=e.question_number,
            question_text=e.question_text,
            model_answer=e.model_answer,
            points=[RubricPoint(**p) for p in e.rubric_points],
        )
        for e in entries
    ]


def process_script(script_id: str, exam_id: str, session: Session,
                   ocr_provider=None, engine: GradingEngine | None = None) -> None:
    script = session.get(Script, script_id)
    if script is None:
        raise ValueError(f"Unknown script: {script_id}")
    try:
        _process(script, exam_id, session, ocr_provider, engine)
    except Exception as exc:
        logger.exception("Pipeline failed for script %s", script_id)
        script.status = "failed"
        script.error = str(exc)
        session.commit()


def _process(script: Script, exam_id: str, session: Session, ocr_provider, engine) -> None:
    with open(script.original_path, "rb") as fh:
        data = fh.read()

    # Stage 1/2: normalize to page images at high DPI, then OCR with bboxes.
    rendered = render_document(data, script.original_filename)
    page_images = [p.png_bytes for p in rendered]
    if script.original_filename.lower().endswith(".pdf"):
        pdf_bytes = data
    else:
        pdf_bytes = images_to_pdf(page_images)
    normalized_path = os.path.join(settings.storage_dir, f"{script.id}_normalized.pdf")
    with open(normalized_path, "wb") as fh:
        fh.write(pdf_bytes)
    script.normalized_pdf_path = normalized_path

    provider = ocr_provider or get_ocr_provider()
    ocr: OCRResult = provider.recognize(page_images)
    script.status = "ocr_done"
    session.commit()

    # Stage 3: segment and match.
    segments = segment_script(ocr)
    rubrics = load_rubrics(session, exam_id)
    matches = match_segments(segments, rubrics)
    for match in matches:
        qnum = match.rubric.question_number if match.rubric else None
        for idx, page_no, line in match.segment.lines:
            session.add(OCRSegmentRecord(
                script_id=script.id,
                page_number=page_no,
                global_line_index=idx,
                text=line.text,
                bbox={"x0": line.bbox.x0, "y0": line.bbox.y0,
                      "x1": line.bbox.x1, "y1": line.bbox.y1},
                confidence=line.confidence,
                question_number=qnum,
            ))
    script.status = "segmented"
    session.commit()

    # Stage 4: grade matched segments; flag unmatched ones.
    engine = engine or GradingEngine()
    results: list[tuple] = []
    for match in matches:
        if match.rubric is None:
            unmatched = GradingResult(
                question_number=match.segment.label or "?",
                evaluation=QuestionEvaluation(
                    question_number=match.segment.label or "?",
                    point_evaluations=[],
                    overall_confidence=0.0,
                    examiner_note="Segment could not be attributed to a question.",
                ),
                max_marks=0.0,
                flags=[ReviewFlag(question_number=match.segment.label or "?",
                                  reason=match.reason)],
            )
            results.append((match, unmatched))
            continue
        calibration = _load_calibration(session, exam_id, match.rubric.question_number)
        result = engine.grade_question(
            match.rubric,
            match.segment.numbered_lines,
            line_confidences=match.segment.line_confidences,
            calibration_examples=calibration,
        )
        results.append((match, result))

    for match, result in results:
        session.add(EvaluationRecord(
            script_id=script.id,
            question_number=result.question_number,
            max_marks=result.max_marks,
            marks_awarded=result.evaluation.marks_awarded,
            pass1=json.loads(result.evaluation.model_dump_json()),
            pass2=json.loads(result.second_pass.model_dump_json()) if result.second_pass else None,
            flags=[f.model_dump() for f in result.flags],
            overall_confidence=result.evaluation.overall_confidence,
        ))
    script.status = "graded"
    session.commit()

    # Stage 5: annotate a copy of the PDF and write the companion report.
    annotator = ScriptAnnotator(pdf_bytes, ocr)
    annotator.apply(build_annotations(ocr, results))
    summary = build_summary(results)
    annotator.add_total(summary["total_awarded"], summary["total_max"])
    annotated_path = os.path.join(settings.storage_dir, f"{script.id}_annotated.pdf")
    with open(annotated_path, "wb") as fh:
        fh.write(annotator.tobytes())

    session.add(Report(script_id=script.id, annotated_pdf_path=annotated_path, summary=summary))
    script.status = "in_review" if summary["needs_human_review"] else "annotated"
    session.commit()


def _load_calibration(session: Session, exam_id: str, question_number: str) -> list[dict]:
    entry = (
        session.query(QuestionBankEntry)
        .filter(QuestionBankEntry.exam_id == exam_id,
                QuestionBankEntry.question_number == question_number)
        .first()
    )
    return entry.calibration_examples if entry else []
