from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from production_rag.models.embedding import Embedding


class EmbeddingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def find_by_chunk_and_model(
        self,
        chunk_id: UUID,
        model_name: str,
        model_version: str,
    ) -> Embedding | None:

        statement = select(Embedding).where(
            Embedding.chunk_id == chunk_id,
            Embedding.model_name == model_name,
            Embedding.model_version == model_version,
        )

        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def create(
        self,
        chunk_id: UUID,
        model_name: str,
        model_version: str,
        dimensions: int,
        vector_key: str,
    ) -> Embedding:

        embedding = Embedding(
            chunk_id=chunk_id,
            model_name=model_name,
            model_version=model_version,
            dimensions=dimensions,
            vector_key=vector_key,
        )

        self.session.add(embedding)
        await self.session.flush()

        return embedding
