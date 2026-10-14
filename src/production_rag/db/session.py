from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from production_rag.core.settings import get_settings
from production_rag.db.url import build_database_url

settings = get_settings()

DATABASE_URL = build_database_url(settings)

engine = create_async_engine(DATABASE_URL, echo=settings.debug)

async_session_factory = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)
