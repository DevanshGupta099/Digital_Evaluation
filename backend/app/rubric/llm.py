import os
import json
import logging
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)
import google.generativeai as genai
from app.rubric.schemas import RubricGenerationResponse


logger = logging.getLogger(__name__)

def get_genai_model():
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        logger.warning("GOOGLE_API_KEY not set. Using Mock Gemini Model for Rubric.")
        return None
    genai.configure(api_key=api_key)
    # Use Gemini 1.5 Pro for Rubric generation as it requires complex reasoning and extraction
    return genai.GenerativeModel(os.getenv("GEMINI_MODEL", "gemini-3.5-flash"))

async def generate_rubric_draft_llm(question_paper_text: str, answer_key_text: str) -> RubricGenerationResponse:
    """
    Calls the LLM to draft a structured Rubric based on the question paper and answer key.
    """
    model = get_genai_model()
    
    if not model:
        # Return mock data for testing
        import asyncio
        await asyncio.sleep(0.5)
        return RubricGenerationResponse(
            items=[
                {
                    "question_number": "Q1",
                    "subpart_id": None,
                    "expected_concepts": ["Concept A", "Concept B"],
                    "accepted_alternates": ["Idea A", "Idea B"],
                    "max_marks": 10.0,
                    "allowed_increments": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
                    "example_full": "Full marks example.",
                    "example_partial": "Partial marks example."
                }
            ]
        )
        
    prompt = f"""
    You are an expert curriculum designer and grader.
    Your task is to generate a structured grading rubric based on the provided Question Paper and Answer Key.
    
    For each question and subpart, you must output a strict JSON structure conforming to the provided schema.
    Determine the maximum marks, the allowed increments (e.g. if halves are allowed, include them like 0.5, 1.0, 1.5, etc.), 
    expected concepts, accepted alternative valid approaches/phrasings, and provide an example of a full-mark and partial-mark response.
    
    QUESTION PAPER TEXT:
    {question_paper_text}
    
    ANSWER KEY TEXT:
    {answer_key_text}
    """
    
    response_schema = RubricGenerationResponse.model_json_schema()
    
    try:
        response = await model.generate_content_async(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema=RubricGenerationResponse,
                temperature=0.2,
            )
        )
        
        result_dict = json.loads(response.text)
        return RubricGenerationResponse(**result_dict)
        
    except Exception as e:
        logger.error(f"Gemini API call failed for rubric generation: {e}")
        raise e
