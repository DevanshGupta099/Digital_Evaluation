import pytest
import os
import fitz
from httpx import AsyncClient, ASGITransport
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database.models import Base, AnswerScript, OCRPage, AnswerScriptStatus
from app.database.session import get_db

from tests.conftest import TestingSessionLocal

@pytest.fixture
def sample_pdf():
    # Create a simple PDF dynamically with PyMuPDF
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)  # A4 size
    page.insert_text((50, 50), "Test Page 1")
    page.set_rotation(90)
    
    page2 = doc.new_page(width=400, height=600)
    page2.insert_text((50, 50), "Test Page 2")
    
    pdf_path = "test_sample.pdf"
    doc.save(pdf_path)
    doc.close()
    yield pdf_path
    if os.path.exists(pdf_path):
        os.remove(pdf_path)

@pytest.mark.asyncio
async def test_upload_and_pipeline(sample_pdf):
    # Dummy IDs (in a real test we'd create these entities first if relying on FKs)
    # However, SQLite in memory without PRAGMA foreign_keys=ON might ignore FK constraints
    # which is fine for this ingestion pipeline test.
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with open(sample_pdf, "rb") as f:
            response = await client.post(
                "/ingestion/upload",
                data={
                    "student_id": "test_student",
                    "class_offering_id": "test_offering"
                },
                files={"file": ("test_sample.pdf", f, "application/pdf")}
            )
            
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "accepted"
        script_id = data["answer_script_id"]
        
    # Since background tasks in TestClient (using ASGITransport) are not run automatically in some configurations 
    # unless awaited or if using the standard TestClient which runs them in the same thread.
    # To be safe, we sleep briefly or we can invoke the pipeline directly to test it robustly.
    # Let's wait a moment for the background task to complete.
    await asyncio.sleep(2)
    
    async with TestingSessionLocal() as session:
        # Check AnswerScript status
        script = await session.get(AnswerScript, script_id)
        assert script is not None
        assert script.status == AnswerScriptStatus.ocr_done
        
        # Check OCR Pages
        from sqlalchemy import select
        result = await session.execute(select(OCRPage).where(OCRPage.answer_script_id == script_id).order_by(OCRPage.page_number))
        pages = result.scalars().all()
        
        assert len(pages) == 2
        
        p1 = pages[0]
        assert p1.rotation == 90
        # DPI 300 scale factor should be approx 300 / 72 = 4.166
        assert 4.1 < p1.scale_factor < 4.2
        assert len(p1.ocr_json["words"]) == 2  # Mock OCR returns 2 words
        
        p2 = pages[1]
        assert p2.rotation == 0
        assert 4.1 < p2.scale_factor < 4.2
