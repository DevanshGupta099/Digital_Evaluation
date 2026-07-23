"""Stage 4: rubric-based evaluation engine — dual-model cross-check.

Two *independent* LLMs perform the two evaluation passes:
  • Pass 1 (primary)  — Google Gemini  (GEMINI_API_KEY / GEMINI_MODEL)
  • Pass 2 (cross-check) — xAI Grok     (GROK_API_KEY   / GROK_MODEL)

Per question: each model grades independently at temperature 0 against the
structured schema (marks require cited evidence), then results are merged.
Disagreement above threshold, low confidence, low OCR legibility, or schema
violations all produce explicit review flags — nothing is silently averaged
or silently dropped.
"""
from __future__ import annotations

import json
import logging

from ..config import settings
from ..schemas.grading import GradingResult, QuestionEvaluation, ReviewFlag, Rubric
from .prompts import SYSTEM_PROMPT, build_user_prompt

logger = logging.getLogger(__name__)


class EvaluationError(Exception):
    pass


# ---------------------------------------------------------------------------
# Provider adapters — each exposes a single .complete(system, user) -> str
# ---------------------------------------------------------------------------

class _GeminiAdapter:
    """Thin wrapper around the google-genai SDK."""

    def __init__(self, api_key: str, model: str, temperature: float) -> None:
        import google.generativeai as genai  # type: ignore[import]
        genai.configure(api_key=api_key)
        self._model = genai.GenerativeModel(
            model_name=model,
            system_instruction=SYSTEM_PROMPT,
            generation_config=genai.GenerationConfig(
                temperature=temperature,
                response_mime_type="application/json",
            ),
        )

    def complete(self, user_prompt: str) -> str:
        response = self._model.generate_content(user_prompt)
        return response.text


class _GrokAdapter:
    """Thin wrapper around xAI's OpenAI-compatible REST API."""

    _BASE_URL = "https://api.x.ai/v1"

    def __init__(self, api_key: str, model: str, temperature: float) -> None:
        from openai import OpenAI  # type: ignore[import]
        self._client = OpenAI(api_key=api_key, base_url=self._BASE_URL)
        self._model = model
        self._temperature = temperature

    def complete(self, user_prompt: str) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            temperature=self._temperature,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_prompt},
            ],
        )
        return response.choices[0].message.content or ""


# ---------------------------------------------------------------------------
# Grading engine
# ---------------------------------------------------------------------------

class GradingEngine:
    """Orchestrates dual-pass grading: Gemini (pass 1) then Grok (pass 2)."""

    def __init__(
        self,
        primary_adapter=None,
        secondary_adapter=None,
    ) -> None:
        # Allow injection (e.g. for tests); fall back to live clients.
        self._primary = primary_adapter or _GeminiAdapter(
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
            temperature=settings.grading_temperature,
        )
        self._secondary = secondary_adapter or _GrokAdapter(
            api_key=settings.grok_api_key,
            model=settings.grok_model,
            temperature=settings.grading_temperature,
        )

    def grade_question(
        self,
        rubric: Rubric,
        numbered_answer_lines: list[tuple[int, str]],
        line_confidences: dict[int, float] | None = None,
        calibration_examples: list[dict] | None = None,
    ) -> GradingResult:
        flags: list[ReviewFlag] = []
        passes: list[QuestionEvaluation] = []
        errors: list[str] = []

        adapters = [
            ("Gemini (pass 1)", self._primary),
            ("Grok (pass 2)",   self._secondary),
        ]

        for label, adapter in adapters[: max(1, settings.grading_passes)]:
            try:
                passes.append(
                    self._run_pass(rubric, numbered_answer_lines,
                                   calibration_examples, adapter)
                )
            except EvaluationError as exc:
                logger.warning(
                    "Evaluation %s failed for Q%s: %s",
                    label, rubric.question_number, exc,
                )
                errors.append(f"{label}: {exc}")

        if not passes:
            zero = QuestionEvaluation(
                question_number=rubric.question_number,
                point_evaluations=[],
                overall_confidence=0.0,
                examiner_note="Automatic evaluation failed; human grading required.",
            )
            flags.append(ReviewFlag(
                question_number=rubric.question_number,
                reason=f"All evaluation passes failed: {'; '.join(errors)}",
            ))
            return GradingResult(
                question_number=rubric.question_number,
                evaluation=zero,
                max_marks=rubric.total_marks,
                flags=flags,
            )

        primary = passes[0]
        second  = passes[1] if len(passes) > 1 else None

        if errors:
            flags.append(ReviewFlag(
                question_number=rubric.question_number,
                reason=f"An evaluation pass failed: {'; '.join(errors)}",
            ))

        # Cross-check: flag when the two models disagree significantly.
        if second is not None and rubric.total_marks > 0:
            disagreement = (
                abs(primary.marks_awarded - second.marks_awarded) / rubric.total_marks
            )
            if disagreement > settings.disagreement_threshold:
                flags.append(ReviewFlag(
                    question_number=rubric.question_number,
                    reason=(
                        f"Dual-model disagreement (Gemini vs Grok): "
                        f"{primary.marks_awarded:g} vs "
                        f"{second.marks_awarded:g} out of {rubric.total_marks:g}"
                    ),
                ))

        min_conf = min(
            [primary.overall_confidence]
            + ([second.overall_confidence] if second else [])
        )
        if min_conf < settings.confidence_threshold:
            flags.append(ReviewFlag(
                question_number=rubric.question_number,
                reason=(
                    f"Evaluation confidence {min_conf:.2f} below threshold "
                    f"{settings.confidence_threshold:.2f}"
                ),
            ))

        if line_confidences:
            cited = {
                idx
                for ev in primary.point_evaluations
                for idx in ev.evidence_line_indices
            }
            illegible = [
                idx for idx in cited
                if line_confidences.get(idx, 1.0) < settings.ocr_confidence_threshold
            ]
            if illegible:
                flags.append(ReviewFlag(
                    question_number=rubric.question_number,
                    reason=f"Evidence cites low-legibility OCR lines: {sorted(illegible)}",
                ))

        valid_indices = {idx for idx, _ in numbered_answer_lines}
        for ev in primary.point_evaluations:
            bad = [i for i in ev.evidence_line_indices if i not in valid_indices]
            if bad:
                flags.append(ReviewFlag(
                    question_number=rubric.question_number,
                    reason=f"Rubric point {ev.rubric_point_id} cites nonexistent lines {bad}",
                ))

        return GradingResult(
            question_number=rubric.question_number,
            evaluation=primary,
            second_pass=second,
            max_marks=rubric.total_marks,
            flags=flags,
        )

    def _run_pass(
        self,
        rubric: Rubric,
        numbered_answer_lines: list[tuple[int, str]],
        calibration_examples: list[dict] | None,
        adapter,
    ) -> QuestionEvaluation:
        prompt = build_user_prompt(rubric, numbered_answer_lines, calibration_examples)
        try:
            raw = adapter.complete(prompt)
        except Exception as exc:
            raise EvaluationError(f"LLM call failed: {exc}") from exc

        try:
            payload = json.loads(_strip_fences(raw))
            evaluation = QuestionEvaluation.model_validate(payload)
        except Exception as exc:
            raise EvaluationError(f"Model output failed schema validation: {exc}") from exc

        max_by_point = {p.id: p.max_marks for p in rubric.points}
        for ev in evaluation.point_evaluations:
            cap = max_by_point.get(ev.rubric_point_id)
            if cap is None:
                raise EvaluationError(f"Unknown rubric point id: {ev.rubric_point_id}")
            if ev.marks_awarded > cap:
                raise EvaluationError(
                    f"Rubric point {ev.rubric_point_id} awarded "
                    f"{ev.marks_awarded} > max {cap}"
                )
        return evaluation


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.endswith("```"):
            text = text[:-3]
    return text.strip()
