"""Prompt construction for rubric-based evaluation.

Design rules encoded here:
  - the model sees exactly: question text, model answer, decomposed rubric,
    calibration examples, and the student's OCR'd lines (numbered) — nothing else;
  - every awarded/withheld mark must cite the numbered line(s) it is based on;
  - conceptual equivalence is rewarded, keyword matching is explicitly rejected;
  - output is strict JSON matching QuestionEvaluation.
"""
from __future__ import annotations

import json

from ..schemas.grading import Rubric

SYSTEM_PROMPT = """\
You are a meticulous, fair examiner grading a student's handwritten answer that
has been transcribed by OCR. You must behave exactly like an experienced human
evaluator, with these strict rules:

1. GROUNDING: For every rubric point, you may award marks ONLY if you can cite
   the specific numbered line(s) of the student's answer that justify it, with a
   short verbatim quote. If you cannot point to supporting text, the status is
   "absent" and marks_awarded is 0. Never invent content the student did not write.
2. CONCEPTUAL GRADING (CRITICAL): The student's wording will rarely match the model answer exactly. They will use their own unique words, phrases, or structure.
   - You MUST award full marks for conceptually equivalent explanations or correct reasoning expressed in different words.
   - You MUST award partial marks for partially correct answers.
   - NEVER demand exact keyword matching. Focus purely on whether the core meaning and concept are correct.
3. EMPTY OR IRRELEVANT ANSWERS: If the student provided no answer, or only wrote the question heading, or wrote completely irrelevant text, you MUST award exactly 0 marks and status "absent" for all points. Do not hallucinate or assume they know the answer.
3. DECOMPOSITION: Grade each rubric point independently (present / partial /
   absent) and award marks per point. Do not produce a single holistic score.
4. OCR AWARENESS: The text came from handwriting OCR and may contain small
   transcription errors. Give the student the benefit of the doubt on obvious
   OCR artifacts (e.g. "ce11" for "cell"), but not on missing content.
5. CONFIDENCE: Report a 0-1 confidence per point and overall. Lower it when the
   answer is ambiguous, partially legible, or borderline between mark bands.
6. OUTPUT: Respond with ONLY a JSON object matching the requested schema. No
   markdown, no commentary outside the JSON.
"""


def build_user_prompt(
    rubric: Rubric,
    numbered_answer_lines: list[tuple[int, str]],
    calibration_examples: list[dict] | None = None,
) -> str:
    lines_block = "\n".join(f"[{idx}] {text}" for idx, text in numbered_answer_lines)
    rubric_block = json.dumps(
        [
            {
                "id": p.id,
                "description": p.description,
                "max_marks": p.max_marks,
                "acceptable_variations": p.acceptable_variations,
            }
            for p in rubric.points
        ],
        indent=2,
    )
    schema_block = json.dumps(
        {
            "question_number": rubric.question_number,
            "point_evaluations": [
                {
                    "rubric_point_id": "<rubric point id>",
                    "status": "present | partial | absent",
                    "marks_awarded": 0.0,
                    "evidence_line_indices": [0],
                    "evidence_quote": "<verbatim quote from cited lines, empty if absent>",
                    "confidence": 0.0,
                    "reasoning": "<one or two sentences>",
                }
            ],
            "overall_confidence": 0.0,
            "examiner_note": "<brief note to the human reviewer>",
        },
        indent=2,
    )

    calibration_block = ""
    if calibration_examples:
        calibration_block = (
            "\n## Calibration examples (already graded by a human examiner — "
            "match this strictness)\n"
            + json.dumps(calibration_examples, indent=2)
            + "\n"
        )

    return f"""\
## Question {rubric.question_number}
{rubric.question_text}

## Model answer
{rubric.model_answer}

## Marking rubric (grade each point separately)
{rubric_block}
{calibration_block}
## Student's answer (OCR transcription, numbered lines — cite these indices as evidence)
{lines_block if lines_block else "[no legible text was extracted for this question]"}

## Required JSON output schema
{schema_block}

Grade now. Remember: no mark without cited evidence lines; conceptual equivalence
counts; respond with the JSON object only."""
