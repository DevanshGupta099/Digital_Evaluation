"""Stage 3b: match detected answer segments to question-paper questions.

Semantic matching, not just number matching: a segment's written label is a
strong prior but is verified against lexical overlap with the question text,
since students mislabel or renumber. Segments below the match-confidence
threshold are returned as unmatched and must go to human review — they are
never silently graded against a guessed rubric, and never silently dropped.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..schemas.grading import Rubric
from .segmenter import AnswerSegment

_MATCH_THRESHOLD = 0.55
_STOPWORDS = {
    "the", "a", "an", "of", "and", "or", "in", "on", "to", "is", "are", "was",
    "what", "why", "how", "which", "with", "for", "that", "this", "it", "be",
}


@dataclass
class SegmentMatch:
    segment: AnswerSegment
    rubric: Rubric | None
    score: float
    reason: str


def match_segments(segments: list[AnswerSegment], rubrics: list[Rubric]) -> list[SegmentMatch]:
    by_number = {r.question_number: r for r in rubrics}
    matches: list[SegmentMatch] = []
    for seg in segments:
        candidates: list[tuple[float, Rubric, str]] = []
        for rubric in rubrics:
            semantic = _overlap_score(seg.text, rubric.question_text + " " + rubric.model_answer)
            label_bonus = 0.5 if seg.label == rubric.question_number else 0.0
            candidates.append((min(1.0, semantic + label_bonus), rubric, "label+semantic"))
        candidates.sort(key=lambda c: c[0], reverse=True)
        best_score, best_rubric, how = candidates[0] if candidates else (0.0, None, "no rubrics")

        if seg.label and seg.label in by_number and best_rubric is by_number[seg.label]:
            matches.append(SegmentMatch(seg, best_rubric, best_score,
                                        f"label Q{seg.label} confirmed by {how}"))
        elif best_score >= _MATCH_THRESHOLD and best_rubric is not None:
            matches.append(SegmentMatch(seg, best_rubric, best_score,
                                        f"semantic match to Q{best_rubric.question_number} "
                                        f"(score {best_score:.2f})"))
        else:
            matches.append(SegmentMatch(
                seg, None, best_score,
                "could not confidently attribute segment to a question; needs human review",
            ))
    return matches


def _tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w for w in words if len(w) > 2 and w not in _STOPWORDS}


def _overlap_score(answer_text: str, question_text: str) -> float:
    a, q = _tokens(answer_text), _tokens(question_text)
    if not a or not q:
        return 0.0
    return len(a & q) / min(len(a), len(q))
