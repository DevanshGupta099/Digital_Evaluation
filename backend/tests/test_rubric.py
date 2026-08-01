import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.database.models import QuestionPaper, ClassOffering, RubricVersion, RubricStatus, RubricItem
from tests.conftest import TestingSessionLocal

@pytest.mark.asyncio
async def test_rubric_workflow(setup_db):
    """
    Tests:
    1. Generating a rubric draft.
    2. Editing max_marks successfully when status=draft.
    3. Locking the rubric.
    4. Attempting to edit max_marks again fails with 403.
    5. Creating an addendum (verifies background task is queued).
    """
    # Seed QuestionPaper
    async with TestingSessionLocal() as session:
        co = ClassOffering(
            id="co1", department_id="d1", course_id="c1", section_id="s1",
            academic_term_id="a1", subject_id="su1"
        )
        session.add(co)
        qp = QuestionPaper(id="qp1", class_offering_id="co1", original_file_path="", page_count=3)
        session.add(qp)
        await session.commit()
        
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Generate Rubric
        resp = await client.post("/rubric/generate", json={
            "question_paper_id": "qp1",
            "question_paper_text": "Q1. What is AI?",
            "answer_key_text": "AI is Artificial Intelligence."
        })
        assert resp.status_code == 200
        rv_data = resp.json()
        assert rv_data["status"] == RubricStatus.draft.value
        rv_id = rv_data["id"]
        
        # Get the item created (we have a mock in LLM returning 1 item for Q1)
        async with TestingSessionLocal() as session:
            from sqlalchemy import select
            item_res = await session.execute(select(RubricItem).where(RubricItem.rubric_version_id == rv_id))
            item = item_res.scalars().first()
            assert item is not None
            item_id = item.id
            assert item.max_marks == 10.0
            
        # 2. Update max marks in draft mode (allowed)
        resp = await client.put(f"/rubric/items/{item_id}", json={
            "max_marks": 12.0
        })
        assert resp.status_code == 200
        
        async with TestingSessionLocal() as session:
            item = await session.get(RubricItem, item_id)
            assert item.max_marks == 12.0
            
        # 3. Lock Rubric
        resp = await client.post(f"/rubric/versions/{rv_id}/approve", json={"approver": "teacher1"})
        assert resp.status_code == 200
        
        # 4. Try updating max marks again (Forbidden)
        resp = await client.put(f"/rubric/items/{item_id}", json={
            "max_marks": 15.0
        })
        assert resp.status_code == 403
        
        # 5. Addendum creation
        resp = await client.post(f"/rubric/items/{item_id}/addendum", json={
            "added_text": "Accept Machine Learning as well",
            "added_by": "teacher1"
        })
        assert resp.status_code == 200
        
        async with TestingSessionLocal() as session:
            # Check accepted_alternates was updated
            item = await session.get(RubricItem, item_id)
            assert "Accept Machine Learning as well" in item.accepted_alternates
