import asyncio
from dotenv import load_dotenv
load_dotenv()
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.database.session import DATABASE_URL
from app.database.models import Base

engine = create_async_engine(DATABASE_URL, echo=True)

async def main():
    try:
        async with engine.begin() as conn:
            await conn.execute(text("ALTER TABLE evaluation_runs ADD COLUMN batch_job_id VARCHAR(32);"))
    except Exception as e:
        print(f"Skipping alter column: {e}")

    try:
        async with engine.begin() as conn:
            await conn.execute(text("ALTER TABLE class_offerings ADD COLUMN results_published BOOLEAN DEFAULT FALSE NOT NULL;"))
    except Exception as e:
        print(f"Skipping alter column results_published: {e}")
        
    # Create new tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

if __name__ == "__main__":
    asyncio.run(main())
