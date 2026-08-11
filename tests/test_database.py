import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from production_rag.db.session import async_session_factory


@pytest.mark.asyncio
async def test_databse_connection():
    async with async_session_factory() as session:
        assert isinstance(session, AsyncSession)

        result = await session.execute(text("SELECT 1"))
        assert result.scalar_one() == 1
