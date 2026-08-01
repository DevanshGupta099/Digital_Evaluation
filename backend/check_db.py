import asyncio
from sqlalchemy import select
from dotenv import load_dotenv
load_dotenv()
from app.database.session import async_session_maker
from app.database.models import Department, Course, Section, AcademicTerm, Subject, ClassOffering, Student

async def test():
    async with async_session_maker() as s:
        # Check if already seeded
        depts = (await s.execute(select(Department))).scalars().all()
        if len(depts) > 0:
            print("Already seeded!")
            return
            
        import uuid
        def gen_id(): return uuid.uuid4().hex
        d = Department(id=gen_id(), name="Computer Science")
        s.add(d)
        await s.flush()
        
        c = Course(id=gen_id(), name="B.Tech CS", department_id=d.id)
        s.add(c)
        await s.flush()
        
        sec = Section(id=gen_id(), name="Section A", course_id=c.id)
        s.add(sec)
        await s.flush()
        
        term = AcademicTerm(id=gen_id(), semester="1", year=2026)
        sub = Subject(id=gen_id(), name="Data Structures")
        s.add_all([term, sub])
        await s.flush()
        
        off = ClassOffering(
            department_id=d.id, course_id=c.id, section_id=sec.id,
            academic_term_id=term.id, subject_id=sub.id
        )
        stu1 = Student(roll_number="CS001", name="Alice Smith", section_id=sec.id)
        stu2 = Student(roll_number="CS002", name="Bob Jones", section_id=sec.id)
        
        s.add_all([off, stu1, stu2])
        await s.commit()
        print("Database seeded!")

if __name__ == "__main__":
    asyncio.run(test())
