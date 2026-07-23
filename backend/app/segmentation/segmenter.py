"""Stage 3a: detect question boundaries in the OCR'd script.

Heuristic pass: question-number patterns ("Q2", "2.", "Ans 2", "Question 2",
"Q2 continued") at line starts, combined with vertical spacing gaps. Segments
that can't be attributed to a question are still emitted (label=None) so the
matcher / review flags handle them explicitly rather than dropping them.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..ocr.base import OCRLine, OCRResult

_QNUM_PATTERNS = [
    re.compile(r"^\s*(?:q|question|ques|ans(?:wer)?)[\s.:\-]*?(\d{1,2})\b(?P<cont>.*continued)?",
               re.IGNORECASE),
    re.compile(r"^\s*(\d{1,2})[\s]*[).:\-]"),
]

# Vertical gap (multiples of median line height) treated as a section break cue.
_GAP_FACTOR = 2.2


@dataclass
class AnswerSegment:
    label: str | None  # question number as written by the student, None if unknown
    continued: bool
    # (global_line_index, page_number, line) tuples belonging to this segment
    lines: list[tuple[int, int, OCRLine]] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(line.text for _, _, line in self.lines)

    @property
    def numbered_lines(self) -> list[tuple[int, str]]:
        return [(idx, line.text) for idx, _, line in self.lines]

    @property
    def line_confidences(self) -> dict[int, float]:
        return {idx: line.confidence for idx, _, line in self.lines}


def detect_question_label(text: str) -> tuple[str | None, bool]:
    for pattern in _QNUM_PATTERNS:
        m = pattern.match(text)
        if m:
            continued = bool(m.groupdict().get("cont")) or "continued" in text.lower()
            return m.group(1), continued
    return None, False


def segment_script(ocr: OCRResult) -> list[AnswerSegment]:
    numbered = ocr.numbered_lines()
    if not numbered:
        return []

    heights = sorted(line.bbox.height for _, _, line in numbered if line.bbox.height > 0)
    median_height = heights[len(heights) // 2] if heights else 0.0

    segments: list[AnswerSegment] = []
    current: AnswerSegment | None = None
    prev: tuple[int, int, OCRLine] | None = None

    for idx, page_no, line in numbered:
        label, continued = detect_question_label(line.text)
        big_gap = (
            prev is not None
            and prev[1] == page_no
            and median_height > 0
            and (line.bbox.y0 - prev[2].bbox.y1) > _GAP_FACTOR * median_height
        )
        if label is not None or current is None or (big_gap and label is not None):
            if label is not None or current is None:
                current = AnswerSegment(label=label, continued=continued)
                segments.append(current)
        current.lines.append((idx, page_no, line))
        prev = (idx, page_no, line)

    # Merge "continued" segments into the earlier segment with the same label.
    merged: list[AnswerSegment] = []
    by_label: dict[str, AnswerSegment] = {}
    for seg in segments:
        if seg.label is not None and seg.continued and seg.label in by_label:
            by_label[seg.label].lines.extend(seg.lines)
            continue
        if seg.label is not None and seg.label not in by_label:
            by_label[seg.label] = seg
        merged.append(seg)
    return merged
