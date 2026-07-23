"""Bridge from evidence-linked grading output to concrete PDF annotations,
plus the companion JSON summary report.
"""
from __future__ import annotations

from ..annotation.annotator import Annotation, AnnotationKind
from ..ocr.base import OCRLine, OCRResult
from ..schemas.grading import GradingResult, PointStatus
from ..segmentation.matcher import SegmentMatch


def build_annotations(
    ocr: OCRResult,
    results: list[tuple[SegmentMatch, GradingResult]],
) -> list[Annotation]:
    line_lookup: dict[int, tuple[int, OCRLine]] = {
        idx: (page_no, line) for idx, page_no, line in ocr.numbered_lines()
    }
    annotations: list[Annotation] = []
    for match, result in results:
        seg = match.segment
        if seg.lines:
            first_idx, first_page, first_line = seg.lines[0]
            annotations.append(Annotation(
                kind=AnnotationKind.MARKS_BADGE,
                page_number=first_page,
                bbox=first_line.bbox,
                label=f"{result.evaluation.marks_awarded:g}/{result.max_marks:g}",
            ))
        for ev in result.evaluation.point_evaluations:
            for idx in ev.evidence_line_indices:
                located = line_lookup.get(idx)
                if located is None:
                    continue
                page_no, line = located
                if ev.status is PointStatus.PRESENT:
                    kind = AnnotationKind.TICK
                elif ev.status is PointStatus.PARTIAL:
                    kind = AnnotationKind.UNDERLINE
                else:
                    kind = AnnotationKind.CROSS
                annotations.append(Annotation(kind=kind, page_number=page_no, bbox=line.bbox))
    return annotations


def build_summary(results: list[tuple[SegmentMatch, GradingResult]]) -> dict:
    questions = []
    total_awarded = 0.0
    total_max = 0.0
    flags: list[dict] = []
    for match, result in results:
        total_awarded += result.evaluation.marks_awarded
        total_max += result.max_marks
        questions.append({
            "question_number": result.question_number,
            "marks_awarded": result.evaluation.marks_awarded,
            "max_marks": result.max_marks,
            "confidence": result.evaluation.overall_confidence,
            "match_reason": match.reason,
            "points": [
                {
                    "rubric_point_id": ev.rubric_point_id,
                    "status": ev.status.value,
                    "marks_awarded": ev.marks_awarded,
                    "evidence_quote": ev.evidence_quote,
                    "evidence_line_indices": ev.evidence_line_indices,
                    "confidence": ev.confidence,
                    "reasoning": ev.reasoning,
                }
                for ev in result.evaluation.point_evaluations
            ],
        })
        flags.extend({"question_number": f.question_number, "reason": f.reason}
                     for f in result.flags)
    return {
        "total_awarded": total_awarded,
        "total_max": total_max,
        "questions": questions,
        "flags": flags,
        "needs_human_review": bool(flags),
    }
