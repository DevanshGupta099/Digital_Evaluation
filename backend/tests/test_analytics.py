import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.database.models import (
    AnswerScript, AnswerScriptStatus, EvaluationRun, RunType,
    ReviewFlag, FlagType, FlagStatus, ClassOffering, Student,
    Department, Course, Section, AcademicTerm, Subject
)
from tests.conftest import TestingSessionLocal

@pytest.mark.asyncio
async def test_analytics_dashboard_metrics(setup_db):
    async with TestingSessionLocal() as session:
        # Seed Hierarchy
        d = Department(id="d_a", name="Dept A")
        c = Course(id="c_a", name="Course A", department_id="d_a")
        s = Section(id="s_a", name="Section A", course_id="c_a")
        t = AcademicTerm(id="t_a", semester="1", year=2024)
        su = Subject(id="su_a", name="Subj A")
        
        co = ClassOffering(
            id="co_analytics", department_id="d_a", course_id="c_a", section_id="s_a",
            academic_term_id="t_a", subject_id="su_a"
        )
        session.add_all([d, c, s, t, su, co])
        
        # Student
        stu = Student(id="stu_a", roll_number="R1", name="S1", section_id="s_a")
        session.add(stu)
        
        # Script
        script = AnswerScript(
            id="sc_a", student_id="stu_a", class_offering_id="co_analytics",
            original_file_path="", status=AnswerScriptStatus.provisional
        )
        session.add(script)
        
        # Evaluation Runs (simulate 1 question, 2 subparts)
        # Q1a: AI 1 gets 4.0, human overrides to 5.0
        ai_1a = EvaluationRun(
            id="run1", answer_script_id="sc_a", question_number="1", subpart_id="a",
            run_type=RunType.ai_pass_1, marks_awarded="4.0"
        )
        hum_1a = EvaluationRun(
            id="run2", answer_script_id="sc_a", question_number="1", subpart_id="a",
            run_type=RunType.human_final, marks_awarded="5.0"
        )
        
        # Q1b: AI 1 gets 2.0, no override
        ai_1b = EvaluationRun(
            id="run3", answer_script_id="sc_a", question_number="1", subpart_id="b",
            run_type=RunType.ai_pass_1, marks_awarded="2.0"
        )
        session.add_all([ai_1a, hum_1a, ai_1b])
        
        # Open flag
        f = ReviewFlag(
            id="f1", answer_script_id="sc_a", question_number="1", subpart_id="a",
            flag_type=FlagType.high_variance, status=FlagStatus.open, notes="{}"
        )
        session.add(f)
        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Check Dashboard
        res = await client.get("/api/analytics/dashboard/co_analytics")
        assert res.status_code == 200
        data = res.json()
        
        sum_data = data["summary"]
        # Expected total for S1: 5.0 + 2.0 = 7.0
        assert sum_data["class_average"] == 7.0
        assert sum_data["highest_score"] == 7.0
        assert sum_data["lowest_score"] == 7.0
        
        # Override rate: 1 override out of 2 AI-evaluated questions = 50.0%
        assert sum_data["override_rate"] == 50.0
        
        assert data["status_counts"]["provisional"] == 1
        assert data["open_flags_by_type"]["high_variance"] == 1
        
        # Check hierarchy filters
        res = await client.get("/api/hierarchy/filters/departments")
        assert res.status_code == 200
        assert len(res.json()) >= 1
        assert res.json()[-1]["id"] == "d_a"
        
        res = await client.get("/api/hierarchy/filters/departments/d_a/courses")
        assert res.status_code == 200
        assert res.json()[0]["id"] == "c_a"
        
        res = await client.get("/api/hierarchy/filters/courses/c_a/sections")
        assert res.status_code == 200
        
        res = await client.get("/api/hierarchy/filters/sections/s_a/terms")
        assert res.status_code == 200
        
        res = await client.get("/api/hierarchy/filters/sections/s_a/terms/t_a/subjects")
        assert res.status_code == 200
        # Check that it resolves the offering correctly
        subj = res.json()[0]
        assert subj["id"] == "su_a"
        assert subj["class_offering_id"] == "co_analytics"
