from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict

from app.database.session import get_db
from app.annotation.service import annotate_script

router = APIRouter(prefix="/annotation", tags=["annotation"])

@router.post("/run/{answer_script_id}")
async def trigger_annotation(answer_script_id: str, db: AsyncSession = Depends(get_db)):
    """
    Triggers the annotation process for a fully graded answer script.
    Fuzzy matches evidence quotes, maps them to bounding boxes, and draws ticks/crosses/totals.
    """
    out_path = await annotate_script(db, answer_script_id)
    return {
        "status": "success",
        "annotated_file_path": out_path
    }
