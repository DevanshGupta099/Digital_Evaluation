import pytest

from tests.mock_provider import MockOCRProvider
from app.ocr.base import BBox
from app.schemas.grading import Rubric, RubricPoint
from app.segmentation import match_segments, segment_script
from app.segmentation.segmenter import detect_question_label


def test_detect_question_labels():
    assert detect_question_label("Q1. Photosynthesis is ...") == ("1", False)
    assert detect_question_label("Question 12: something") == ("12", False)
    assert detect_question_label("2) The mitochondria") == ("2", False)
    assert detect_question_label("Ans 3 - it works by") == ("3", False)
    assert detect_question_label("Q2 continued from page 1")[1] is True
    assert detect_question_label("just a normal sentence") == (None, False)


def _ocr_two_questions():
    text = (
        "Q1. Photosynthesis converts light energy into chemical energy\n"
        "It happens in the chloroplast using chlorophyll\n"
        "Q2. Mitochondria produce ATP through respiration\n"
        "They are the powerhouse of the cell\n"
    )
    provider = MockOCRProvider(page_texts=[text])
    return provider.recognize([b"fake-image"])


def test_segment_script_splits_by_question():
    segments = segment_script(_ocr_two_questions())
    assert [s.label for s in segments] == ["1", "2"]
    assert len(segments[0].lines) == 2
    assert "chloroplast" in segments[0].text
    assert "powerhouse" in segments[1].text


def test_continued_segment_merges():
    text = (
        "Q1. Photosynthesis converts light\n"
        "Q2. Mitochondria produce ATP\n"
        "Q1 continued more about chlorophyll pigment\n"
    )
    ocr = MockOCRProvider(page_texts=[text]).recognize([b"x"])
    segments = segment_script(ocr)
    labels = [s.label for s in segments]
    assert labels == ["1", "2"]
    assert "chlorophyll" in segments[0].text


def _rubrics():
    return [
        Rubric(
            question_number="1",
            question_text="Explain photosynthesis and where it occurs.",
            model_answer="Photosynthesis converts light energy to chemical energy in chloroplasts.",
            points=[RubricPoint(id="1a", description="definition", max_marks=2)],
        ),
        Rubric(
            question_number="2",
            question_text="What is the role of mitochondria?",
            model_answer="Mitochondria produce ATP via cellular respiration.",
            points=[RubricPoint(id="2a", description="function", max_marks=2)],
        ),
    ]


def test_match_segments_by_label_and_semantics():
    segments = segment_script(_ocr_two_questions())
    matches = match_segments(segments, _rubrics())
    assert matches[0].rubric.question_number == "1"
    assert matches[1].rubric.question_number == "2"


def test_unmatchable_segment_is_flagged_not_dropped():
    ocr = MockOCRProvider(page_texts=["some totally unrelated ramblings about weather\n"]).recognize([b"x"])
    segments = segment_script(ocr)
    matches = match_segments(segments, _rubrics())
    assert len(matches) == 1
    assert matches[0].rubric is None
    assert "human review" in matches[0].reason
