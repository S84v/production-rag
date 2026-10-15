from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from production_rag.models.embedding import Embedding


class EmbeddingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_by_chunk_ids(
        self,
        chunk_ids: list[UUID],
        model_name: str,
        model_version: str,
    ) -> dict[UUID, Embedding]:
        """Return existing embeddings for ``chunk_ids`` keyed by chunk id.

        Used by ingestion to decide, per chunk, whether an embedding record
        already exists for the active model and version.
        """

        if not chunk_ids:
            return {}

        statement = select(Embedding).where(
            Embedding.chunk_id.in_(chunk_ids),
            Embedding.model_name == model_name,
            Embedding.model_version == model_version,
        )

        result = await self.session.execute(statement)

        return {embedding.chunk_id: embedding for embedding in result.scalars().all()}

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
    ) -> Embedding:

        embedding = Embedding(
            chunk_id=chunk_id,
            model_name=model_name,
            model_version=model_version,
            dimensions=dimensions,
        )

        self.session.add(embedding)
        await self.session.flush()

        return embedding
