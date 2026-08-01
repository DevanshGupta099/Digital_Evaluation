import os
import json
import logging
import asyncio
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)
from typing import Type, Optional, List, Dict
from pydantic import BaseModel
from anthropic import AsyncAnthropic
import google.generativeai as genai


logger = logging.getLogger(__name__)

async def _mock_response(schema: Type[BaseModel]):
    import asyncio
    await asyncio.sleep(0.1)
    marks_enum_class = schema.model_fields['marks_awarded'].annotation
    first_valid_mark = list(marks_enum_class)[0].value
    
    return schema(
        marks_awarded=first_valid_mark,
        reasoning="Mock reasoning for test.",
        evidence_quote="Mock quote."
    )

async def evaluate_with_claude(prompt: str, schema: Type[BaseModel], base64_image: Optional[str] = None) -> BaseModel:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not set. Using Mock for Claude.")
        return await _mock_response(schema)
        
    client = AsyncAnthropic(api_key=api_key)
    
    content = [
        {
            "type": "text", 
            "text": prompt,
            "cache_control": {"type": "ephemeral"}
        }
    ]
    if base64_image:
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": base64_image
            }
        })
        
    schema_json = schema.model_json_schema()
    tool = {
        "name": "record_evaluation",
        "description": "Records the final grade and reasoning for the student's answer.",
        "input_schema": schema_json
    }
    
    try:
        response = await client.messages.create(
            model=os.getenv("CLAUDE_MODEL", "claude-sonnet-5"),
            max_tokens=1024,
            tools=[tool],
            tool_choice={"type": "tool", "name": "record_evaluation"},
            messages=[{"role": "user", "content": content}]
        )
        
        tool_use = next((c for c in response.content if c.type == "tool_use"), None)
        if not tool_use:
            raise ValueError("Claude failed to use the required tool.")
            
        return schema(**tool_use.input)
    except Exception as e:
        logger.error(f"Claude Evaluation failed: {e}")
        raise e

async def create_claude_batch(requests_data: list) -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not set. Cannot use Claude batch.")
        return "mock_batch_id"

    client = AsyncAnthropic(api_key=api_key)
    batch_requests = []
    
    for req in requests_data:
        content = [
            {
                "type": "text", 
                "text": req["prompt"],
                "cache_control": {"type": "ephemeral"}
            }
        ]
        if req.get("base64_image"):
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": req["base64_image"]
                }
            })
            
        schema_json = req["schema"].model_json_schema()
        tool = {
            "name": "record_evaluation",
            "description": "Records the final grade and reasoning for the student's answer.",
            "input_schema": schema_json
        }
        
        batch_requests.append({
            "custom_id": req["custom_id"],
            "params": {
                "model": os.getenv("CLAUDE_MODEL", "claude-sonnet-5"),
                "max_tokens": 1024,
                "tools": [tool],
                "tool_choice": {"type": "tool", "name": "record_evaluation"},
                "messages": [{"role": "user", "content": content}]
            }
        })
        
    try:
        batch = await client.messages.batches.create(
            requests=batch_requests
        )
        return batch.id
    except Exception as e:
        logger.error(f"Failed to create Claude batch: {e}")
        raise e

async def poll_claude_batch(batch_id: str):
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return {"status": "mock_completed", "results": []}

    client = AsyncAnthropic(api_key=api_key)
    
    batch = await client.messages.batches.retrieve(batch_id)
    if batch.processing_status in ["ended", "completed"]:
        results = []
        async for result in client.messages.batches.results(batch_id):
            results.append(result)
        return {"status": "completed", "results": results, "usage": batch.request_counts}
    
    return {"status": batch.processing_status, "results": []}

async def evaluate_with_gemini(prompt: str, schema: Type[BaseModel], base64_image: Optional[str] = None) -> BaseModel:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        logger.warning("GOOGLE_API_KEY not set. Using Mock for Gemini.")
        return await _mock_response(schema)
        
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(os.getenv("GEMINI_MODEL", "gemini-3.5-flash"))
    
    content = [prompt]
    if base64_image:
        content.append({"mime_type": "image/png", "data": base64_image})
        
    try:
        response = await model.generate_content_async(
            content,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema=schema,
                temperature=0.1,
            )
        )
        result_dict = json.loads(response.text)
        return schema(**result_dict)
    except Exception as e:
        logger.error(f"Gemini Evaluation failed: {e}")
        raise e

async def process_gemini_requests(requests_data: list, shared_rubric_text: str):
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return [{"custom_id": r["custom_id"], "marks_awarded": 0, "reasoning": "mock", "evidence_quote": "mock"} for r in requests_data]
        
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(os.getenv("GEMINI_MODEL", "gemini-3.5-flash"))
    
    sem = asyncio.Semaphore(5)
    
    async def process_single(req):
        async with sem:
            prompt = shared_rubric_text + "\n\n" + req["prompt"]
            content = [prompt]
            if req.get("base64_image"):
                content.append({"mime_type": "image/png", "data": req["base64_image"]})
                
            try:
                response = await model.generate_content_async(
                    content,
                    generation_config=genai.GenerationConfig(
                        response_mime_type="application/json",
                        response_schema=req["schema"],
                        temperature=0.1,
                    )
                )
                result_dict = json.loads(response.text)
                return {"custom_id": req["custom_id"], "result": req["schema"](**result_dict), "status": "completed"}
            except Exception as e:
                logger.error(f"Gemini evaluation failed for {req['custom_id']}: {e}")
                return {"custom_id": req["custom_id"], "error": str(e), "status": "failed"}
                
    results = await asyncio.gather(*(process_single(r) for r in requests_data))
    return results
