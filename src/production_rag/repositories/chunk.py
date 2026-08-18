from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from production_rag.models.chunk import Chunk


class ChunkRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def find_by_index(
        self,
        document_version_id: UUID,
        chunk_index: int,
    ) -> Chunk | None:
        statement = select(Chunk).where(
            Chunk.document_version_id == document_version_id,
            Chunk.chunk_index == chunk_index,
        )

        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def create(
        self,
        document_version_id: UUID,
        chunk_index: int,
        content: str,
        token_count: int | None = None,
        chunk_metadata: dict | None = None,
    ) -> Chunk:
        chunk = Chunk(
            document_version_id=document_version_id,
            chunk_index=chunk_index,
            content=content,
            token_count=token_count,
            chunk_metadata=chunk_metadata,
        )
        self.session.add(chunk)
        await self.session.flush()

        return chunk

    async def list_by_document_version(
        self,
        document_version_id: UUID,
    ) -> list[Chunk]:
        statement = (
            select(Chunk)
            .where(Chunk.document_version_id == document_version_id)
            .order_by(Chunk.chunk_index)
        )

        result = await self.session.execute(statement)
        return list(result.scalars().all())
