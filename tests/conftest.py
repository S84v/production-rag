import pytest_asyncio

from production_rag.db.session import engine


@pytest_asyncio.fixture(autouse=True)
async def cleanup_database_engine():
    yield
    await engine.dispose()
