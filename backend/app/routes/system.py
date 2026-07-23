from fastapi import APIRouter
from app.database import SessionLocal
from app.models import Script

router = APIRouter()

@router.get("/metrics")
def get_metrics():
    db = SessionLocal()
    try:
        scripts_count = db.query(Script).count()
        # Estimate: ~12 API calls per script (OCR + Conceptual Pass + Audit Pass for multiple questions)
        calls_made = scripts_count * 12
        limit = 1500 # Daily free tier limit
        percentage = min(100, int((calls_made / limit) * 100))
        
        return {
            "calls_made": calls_made,
            "limit": limit,
            "percentage": percentage,
            "status": "online" if percentage < 100 else "rate_limited"
        }
    finally:
        db.close()
