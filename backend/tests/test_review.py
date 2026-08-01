import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.database.models import (
    AnswerScript, AnswerScriptStatus, EvaluationRun, RunType,
    ReviewFlag, FlagType, FlagStatus, ClassOffering
)
from tests.conftest import TestingSessionLocal

@pytest.mark.asyncio
async def test_reconciliation_variance_flag(setup_db):
    """
    Test that a large score gap creates a 'high_variance' flag
    and the parent script's status is set to 'provisional',
    and then becomes 'final' upon resolution.
    """
    async with TestingSessionLocal() as session:
        # Seed Class Offering
        co = ClassOffering(
            id="co3", department_id="d1", course_id="c1", section_id="s1",
            academic_term_id="a1", subject_id="su1"
        )
        session.add(co)
        
        # Seed Script
        script = AnswerScript(
            id="script3", student_id="stu1", class_offering_id="co3",
            original_file_path="", status=AnswerScriptStatus.graded
        )
        session.add(script)
        
        # Seed two EvaluationRuns with a large gap (10 vs 5)
        run1 = EvaluationRun(
            answer_script_id="script3", question_number="Q1", run_type=RunType.ai_pass_1,
            marks_awarded=10.0
        )
        run2 = EvaluationRun(
            answer_script_id="script3", question_number="Q1", run_type=RunType.ai_pass_2,
            marks_awarded=5.0
        )
        session.add(run1)
        session.add(run2)
        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Trigger reconciliation
        resp = await client.post("/review/reconcile/script3")
        assert resp.status_code == 200
        
        # Check DB for flag and provisional status
        async with TestingSessionLocal() as session:
            from sqlalchemy import select
            # Should have 1 high_variance flag
            flags = (await session.execute(select(ReviewFlag).where(ReviewFlag.answer_script_id == "script3"))).scalars().all()
            assert len(flags) == 1
            flag = flags[0]
            assert flag.flag_type == FlagType.high_variance
            assert flag.status == FlagStatus.open
            
            # Script status should be provisional
            script_check = await session.get(AnswerScript, "script3")
            assert script_check.status == AnswerScriptStatus.provisional
            
            flag_id = flag.id
            
        # Resolve the flag
        resp = await client.post(f"/review/resolve/{flag_id}", json={
            "resolver_name": "Teacher"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["new_script_status"] == AnswerScriptStatus.final.value
        
        # Verify DB is updated
        async with TestingSessionLocal() as session:
            script_final = await session.get(AnswerScript, "script3")
            assert script_final.status == AnswerScriptStatus.final
            
            flag_final = await session.get(ReviewFlag, flag_id)
            assert flag_final.status == FlagStatus.resolved
            assert flag_final.resolved_by == "Teacher"
