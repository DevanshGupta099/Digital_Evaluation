import os
import logging
import fitz  # PyMuPDF
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

from app.database.models import AnswerScript, OCRPage, AnswerScriptStatus
from app.ingestion.ocr import get_ocr_provider

logger = logging.getLogger(__name__)

# Retry configuration for OCR: up to 5 attempts, exponential backoff starting at 1 second
ocr_retry = retry(
    wait=wait_exponential(multiplier=1, min=1, max=10),
    stop=stop_after_attempt(5),
    retry=retry_if_exception_type(Exception),
    reraise=True
)

@ocr_retry
async def call_ocr_with_retry(provider, image_path: str):
    return await provider.process_image(image_path)

async def process_pdf_pipeline(
    db_session: AsyncSession,
    answer_script_id: str,
    pdf_path: str,
    storage_dir: str
):
    """
    Background pipeline to process the uploaded PDF.
    Splits into pages, computes specific scale factors, calls OCR, and saves to DB.
    """
    try:
        # Create output directory for images
        script_image_dir = os.path.join(storage_dir, "images", answer_script_id)
        os.makedirs(script_image_dir, exist_ok=True)

        ocr_provider = get_ocr_provider()
        
        # Open PDF with PyMuPDF
        doc = fitz.open(pdf_path)
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            
            # Read point-based dimensions
            rect = page.rect
            pt_width = rect.width
            pt_height = rect.height
            rotation = page.rotation
            
            # Render to PNG at 300 DPI
            pix = page.get_pixmap(dpi=300)
            px_width = pix.width
            px_height = pix.height
            
            # Save PNG
            image_filename = f"page_{page_num + 1}.png"
            image_path = os.path.join(script_image_dir, image_filename)
            pix.save(image_path)
            
            # Compute specific scale factor
            # Typically scale factor = px / pt. We can use X-axis scale.
            # If width is 0 for some corrupted reason, fallback to 1.0
            scale_factor = (px_width / pt_width) if pt_width > 0 else 1.0
            
            # Perform OCR with retries
            try:
                ocr_response = await call_ocr_with_retry(ocr_provider, image_path)
            except Exception as e:
                logger.error(f"OCR failed for script {answer_script_id} page {page_num + 1} after retries: {e}")
                # For now, if one page fails, we raise to fail the whole script process
                raise e

            # Create OCRPage record
            ocr_page = OCRPage(
                answer_script_id=answer_script_id,
                page_number=page_num + 1,
                image_path=image_path,
                scale_factor=scale_factor,
                rotation=rotation,
                ocr_json=ocr_response.model_dump(),
                masked_regions=[]  # Configurable ROI masking can populate this later
            )
            db_session.add(ocr_page)
        
        # All pages processed successfully, update AnswerScript status
        await db_session.execute(
            update(AnswerScript)
            .where(AnswerScript.id == answer_script_id)
            .values(status=AnswerScriptStatus.ocr_done)
        )
        await db_session.commit()
        logger.info(f"Successfully processed and OCR'd answer script {answer_script_id}")

    except Exception as e:
        logger.error(f"Failed to process PDF {pdf_path}: {e}")
        await db_session.rollback()
        # In a robust system, we would mark the script as FAILED, but for now we log it.
        # Could add a FAILED status to AnswerScriptStatus if schema allows, or use notes.
