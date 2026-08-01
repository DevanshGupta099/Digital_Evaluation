from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from contextlib import asynccontextmanager

# Load env variables
load_dotenv()

from app.ingestion.routes import router as ingestion_router
from app.ingestion.bulk_routes import router as bulk_router
from app.events import router as events_router
from app.segmentation.routes import router as segmentation_router
from app.rubric.routes import router as rubric_router
from app.grading.routes import router as grading_router
from app.annotation.routes import router as annotation_router
from app.review.routes import router as review_router
from app.analytics.routes import router as analytics_router
from app.hierarchy.routes import router as hierarchy_router
from app.auth.routes import router as auth_router

from app.database.session import get_db, engine
from app.database.models import User, UserRole, Base
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

@asynccontextmanager
async def lifespan(app: FastAPI):
    db_ready = False
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        db_ready = True
    except Exception as e:
        print(f"Error during create_all: {e}")
        
    if db_ready:
        try:
            # Seed default mock users
            from app.database.session import async_session_maker
            async with async_session_maker() as db:
                users = [
                    ("admin", "Admin User", UserRole.admin),
                    ("coordinator", "Coordinator", UserRole.exam_coordinator),
                    ("evaluator", "Faculty Evaluator", UserRole.evaluator),
                    ("viewer", "Read Only Leadership", UserRole.read_only),
                ]
                for username, name, role in users:
                    result = await db.execute(select(User).where(User.username == username))
                    if not result.scalars().first():
                        db.add(User(username=username, name=name, role=role))
                await db.commit()
        except Exception as e:
            print(f"Error seeding default users: {e}")

    yield


app = FastAPI(title="Digital Evaluation System API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingestion_router)
app.include_router(bulk_router)
app.include_router(events_router)
app.include_router(segmentation_router)
app.include_router(rubric_router, prefix="/api")
app.include_router(grading_router)
app.include_router(annotation_router)
app.include_router(review_router, prefix="/api")
app.include_router(analytics_router)
app.include_router(hierarchy_router)
app.include_router(auth_router, prefix="/api")

@app.get("/health")
def health_check():
    return {"status": "ok"}
