import json

import pytest
from pydantic import ValidationError

from app.grading.engine import GradingEngine
from app.schemas.grading import PointEvaluation, PointStatus, Rubric, RubricPoint


def test_marks_without_evidence_rejected():
    with pytest.raises(ValidationError):
        PointEvaluation(
            rubric_point_id="1a",
            status=PointStatus.PRESENT,
            marks_awarded=2,
            evidence_line_indices=[],
            confidence=0.9,
        )


def test_zero_marks_without_evidence_allowed():
    ev = PointEvaluation(
        rubric_point_id="1a",
        status=PointStatus.ABSENT,
        marks_awarded=0,
        evidence_line_indices=[],
        confidence=0.9,
    )
    assert ev.marks_awarded == 0


class _FakeBlock:
    type = "text"

    def __init__(self, text):
        self.text = text


class _FakeResponse:
    def __init__(self, payload):
        self.content = [_FakeBlock(json.dumps(payload))]


class _FakeClient:
    """Returns queued payloads, one per messages.create call."""

    def __init__(self, payloads):
        self._payloads = list(payloads)
        self.calls = 0

        outer = self

        class _Messages:
            def create(self, **kwargs):
                outer.calls += 1
                return _FakeResponse(outer._payloads.pop(0))

        self.messages = _Messages()


def _rubric():
    return Rubric(
        question_number="1",
        question_text="Explain photosynthesis.",
        model_answer="Converts light to chemical energy in chloroplasts.",
        points=[
            RubricPoint(id="1a", description="definition", max_marks=2),
            RubricPoint(id="1b", description="location", max_marks=1),
        ],
    )


def _payload(marks_a=2.0, marks_b=1.0, confidence=0.9):
    return {
        "question_number": "1",
        "point_evaluations": [
            {"rubric_point_id": "1a", "status": "present", "marks_awarded": marks_a,
             "evidence_line_indices": [0], "evidence_quote": "converts light energy",
             "confidence": confidence, "reasoning": "definition present"},
            {"rubric_point_id": "1b", "status": "present" if marks_b else "absent",
             "marks_awarded": marks_b,
             "evidence_line_indices": [1] if marks_b else [],
             "evidence_quote": "in the chloroplast" if marks_b else "",
             "confidence": confidence, "reasoning": ""},
        ],
        "overall_confidence": confidence,
        "examiner_note": "",
    }


_LINES = [(0, "photosynthesis converts light energy"), (1, "in the chloroplast")]


def test_dual_pass_agreement_no_flags():
    engine = GradingEngine(client=_FakeClient([_payload(), _payload()]))
    result = engine.grade_question(_rubric(), _LINES)
    assert result.evaluation.marks_awarded == 3.0
    assert result.max_marks == 3.0
    assert result.flags == []
    assert result.second_pass is not None


def test_dual_pass_disagreement_flagged():
    engine = GradingEngine(client=_FakeClient([_payload(2, 1), _payload(0.5, 0)]))
    result = engine.grade_question(_rubric(), _LINES)
    assert any("disagreement" in f.reason.lower() for f in result.flags)


def test_low_confidence_flagged():
    engine = GradingEngine(client=_FakeClient([_payload(confidence=0.4),
                                               _payload(confidence=0.4)]))
    result = engine.grade_question(_rubric(), _LINES)
    assert any("confidence" in f.reason.lower() for f in result.flags)


def test_illegible_evidence_flagged():
    engine = GradingEngine(client=_FakeClient([_payload(), _payload()]))
    result = engine.grade_question(_rubric(), _LINES,
                                   line_confidences={0: 0.3, 1: 0.95})
    assert any("legibility" in f.reason.lower() for f in result.flags)


def test_nonexistent_evidence_line_flagged():
    bad = _payload()
    bad["point_evaluations"][0]["evidence_line_indices"] = [99]
    engine = GradingEngine(client=_FakeClient([bad, bad]))
    result = engine.grade_question(_rubric(), _LINES)
    assert any("nonexistent" in f.reason for f in result.flags)


def test_overmax_marks_rejected_and_flagged():
    bad = _payload(marks_a=5.0)  # max is 2
    engine = GradingEngine(client=_FakeClient([bad, bad]))
    result = engine.grade_question(_rubric(), _LINES)
    assert result.evaluation.marks_awarded == 0
    assert any("failed" in f.reason.lower() for f in result.flags)
