from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from production_rag.core.settings import get_settings

settings = get_settings()

DATABSE_URL = (
    f"postgresql+asyncpg://"
    f"{settings.postgres_user}:{settings.postgres_password}"
    f"@{settings.postgres_host}:{settings.postgres_port}"
    f"/{settings.postgres_db}"
)

engine = create_async_engine(DATABSE_URL, echo=settings.debug)

async_session_factory = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)
