import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import router
from .config import settings
from .models import init_db

app = FastAPI(title="AI Answer Script Grader")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")


@app.on_event("startup")
def startup() -> None:
    os.makedirs(settings.storage_dir, exist_ok=True)
    init_db()


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}
