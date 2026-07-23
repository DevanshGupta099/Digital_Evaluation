"""LLM-powered extraction of Question Papers and Answer Keys."""
from __future__ import annotations

import json
from pydantic import BaseModel, Field
import google.generativeai as genai
from ..config import settings
from ..schemas.grading import RubricPoint
import io
import docx

# Ensure API key is configured
if settings.gemini_api_key:
    genai.configure(api_key=settings.gemini_api_key)


class ExtractedQuestion(BaseModel):
    question_number: str
    question_text: str
    model_answer: str
    points: list[RubricPoint]


class ExtractedRubric(BaseModel):
    questions: list[ExtractedQuestion]


EXTRACTION_PROMPT = """
You are an expert academic evaluator. Your task is to extract a structured grading rubric from the provided Question Paper and Answer Key documents.

CRITICAL INSTRUCTIONS for JSON generation:
You MUST output a valid JSON object containing a list of `questions`.
For EACH question you find in the document, you MUST provide ALL of the following fields:
1. `question_number`: The question number or ID (e.g., "1", "2a").
2. `question_text`: The exact text of the question from the question paper.
3. `model_answer`: The correct answer text provided in the answer key.
4. `points`: A list of specific grading criteria (RubricPoints) for this question.

For EACH point in the `points` list, you MUST provide:
- `id`: A unique string ID (e.g. "1a", "1b").
- `description`: What the student needs to write to get the mark.
- `max_marks`: The maximum marks awarded for this specific sub-point (must be a number).
- `acceptable_variations`: A list of alternative phrases or concepts that are also correct (can be empty list []).

EXAMPLE JSON FORMAT (Do not copy this data, only the structure):
{
  "questions": [
    {
      "question_number": "1",
      "question_text": "What is the capital of France?",
      "model_answer": "Paris is the capital of France.",
      "points": [
        {
          "id": "1a",
          "description": "Mentions Paris",
          "max_marks": 1.0,
          "acceptable_variations": ["City of Paris"]
        }
      ]
    }
  ]
}

Do NOT lump multiple questions into one. Separate them into distinct objects in the `questions` array. Ensure all required fields (`question_number`, `question_text`, `model_answer`, `points`) are present in every question object.
"""


def extract_rubric_from_documents(
    question_paper_mime_type: str,
    question_paper_data: bytes,
    answer_key_mime_type: str,
    answer_key_data: bytes
) -> ExtractedRubric:
    """Uses Gemini 2.5 Pro multimodal capabilities to parse documents."""
    if not settings.gemini_api_key:
        raise ValueError("GEMINI_API_KEY is not set.")

    model = genai.GenerativeModel(
        model_name=settings.gemini_model,
        system_instruction=EXTRACTION_PROMPT,
        generation_config=genai.GenerationConfig(
            temperature=0.1,
            response_mime_type="application/json",
        ),
    )

    def prepare_content(mime: str, data: bytes, label: str):
        if "wordprocessingml" in mime or mime == "application/msword":
            try:
                doc = docx.Document(io.BytesIO(data))
                text = "\n".join([p.text for p in doc.paragraphs])
                return f"--- {label} ---\n{text}"
            except Exception:
                # Fallback if it fails to parse as docx
                return {"mime_type": "text/plain", "data": data}
        elif mime == "text/plain":
            return f"--- {label} ---\n{data.decode('utf-8', errors='ignore')}"
        return {"mime_type": mime, "data": data}

    contents = [
        prepare_content(question_paper_mime_type, question_paper_data, "Question Paper"),
        prepare_content(answer_key_mime_type, answer_key_data, "Answer Key"),
        "Extract the structured rubric combining these two documents."
    ]

    response = model.generate_content(contents)
    try:
        return ExtractedRubric.model_validate_json(response.text)
    except Exception as exc:
        raise ValueError(f"Failed to parse LLM output: {exc}\nRaw: {response.text}") from exc
