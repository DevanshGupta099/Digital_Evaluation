import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Expects something like postgresql+asyncpg://user:password@127.0.0.1/digital_evaluation
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@127.0.0.1/digital_evaluation")

# Handle IPv6 resolution issue on Windows by normalizing localhost to 127.0.0.1
if "localhost:5432" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("localhost:5432", "127.0.0.1:5432")
elif "localhost/" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("localhost/", "127.0.0.1/")

engine = create_async_engine(DATABASE_URL, echo=False)


async_session_maker = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def get_db():
    async with async_session_maker() as session:
        yield session
