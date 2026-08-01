from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.segmentation.schemas import SegmentationRunResponse
from app.segmentation.service import run_segmentation_pipeline

router = APIRouter(prefix="/segmentation", tags=["segmentation"])

@router.post("/run/{answer_script_id}", response_model=SegmentationRunResponse)
async def trigger_segmentation(
    answer_script_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Manually triggers the segmentation pipeline for a specific answer script.
    The script must have completed OCR (status = ocr_done).
    """
    return await run_segmentation_pipeline(db, answer_script_id)
