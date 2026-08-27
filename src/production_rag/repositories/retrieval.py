from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from production_rag.models.chunk import Chunk
from production_rag.models.collection import Collection
from production_rag.models.document import Document
from production_rag.models.document_version import DocumentVersion
from production_rag.models.embedding import Embedding


class RetrievalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def find_chunks_by_embedding_ids(
        self, embedding_ids: list[UUID], collection_name: str
    ) -> dict[UUID, tuple[Chunk, str, str]]:

        if not embedding_ids:
            return {}

        statement = (
            select(Embedding.id, Chunk, Document.source, Document.source_uri)
            .join(Chunk, Chunk.id == Embedding.chunk_id)
            .join(DocumentVersion, DocumentVersion.id == Chunk.document_version_id)
            .join(Document, Document.id == DocumentVersion.document_id)
            .join(Collection, Collection.id == Document.collection_id)
            .where(
                Embedding.id.in_(embedding_ids),
                Collection.name == collection_name,
            )
        )

        result = await self.session.execute(statement)

        return {
            embedding_id: (chunk, source, source_uri)
            for embedding_id, chunk, source, source_uri in result.all()
        }
