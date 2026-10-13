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

    async def list_collection_chunks(
        self, collection_name: str
    ) -> list[tuple[UUID, str, str]]:
        """Return ``(chunk_id, source_uri, content)`` for the current collection state.

        Only the latest version of each document is returned. PostgreSQL keeps
        superseded document versions, so without this the same content could be
        matched in both an old and a new version, making anchor resolution
        ambiguous. The latest version is chosen deterministically by
        ``created_at`` then ``id``.
        """

        latest_version_ids = (
            select(DocumentVersion.id)
            .distinct(DocumentVersion.document_id)
            .order_by(
                DocumentVersion.document_id,
                DocumentVersion.created_at.desc(),
                DocumentVersion.id.desc(),
            )
            .subquery()
        )

        statement = (
            select(Chunk.id, Document.source_uri, Chunk.content)
            .join(DocumentVersion, DocumentVersion.id == Chunk.document_version_id)
            .join(Document, Document.id == DocumentVersion.document_id)
            .join(Collection, Collection.id == Document.collection_id)
            .where(
                Collection.name == collection_name,
                Chunk.document_version_id.in_(select(latest_version_ids.c.id)),
            )
            .order_by(Document.source_uri, Chunk.chunk_index)
        )

        result = await self.session.execute(statement)

        return [
            (chunk_id, source_uri, content)
            for chunk_id, source_uri, content in result.all()
        ]

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
