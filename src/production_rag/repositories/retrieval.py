from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from production_rag.models.chunk import Chunk
from production_rag.models.collection import Collection
from production_rag.models.document import Document
from production_rag.models.document_version import DocumentVersion
from production_rag.models.embedding import Embedding

# Embedding classification outcomes. The authoritative set is defined once and
# reused by runtime retrieval and by reconciliation so both agree.
AUTHORITATIVE = "authoritative"
FOREIGN_COLLECTION = "foreign_collection"
SUPERSEDED_VERSION = "superseded_version"
INACTIVE_MODEL = "inactive_model"


class RetrievalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _latest_version_ids() -> Select:
        """Select the latest version id per document.

        The version-selection rule is shared by every collection-scoped query
        so runtime retrieval, evaluation, and reconciliation agree on which
        content is current.
        """

        return (
            select(DocumentVersion.id)
            .distinct(DocumentVersion.document_id)
            .order_by(
                DocumentVersion.document_id,
                DocumentVersion.created_at.desc(),
                DocumentVersion.id.desc(),
            )
            .subquery()
        )

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

        latest_version_ids = self._latest_version_ids()

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

        latest_version_ids = self._latest_version_ids()

        statement = (
            select(Embedding.id, Chunk, Document.source, Document.source_uri)
            .join(Chunk, Chunk.id == Embedding.chunk_id)
            .join(DocumentVersion, DocumentVersion.id == Chunk.document_version_id)
            .join(Document, Document.id == DocumentVersion.document_id)
            .join(Collection, Collection.id == Document.collection_id)
            .where(
                Embedding.id.in_(embedding_ids),
                Collection.name == collection_name,
                # Superseded versions are retained for history but must never be
                # returned: evaluation scores the latest version only, so
                # runtime hydration has to use the same rule.
                Chunk.document_version_id.in_(select(latest_version_ids.c.id)),
            )
        )

        result = await self.session.execute(statement)

        return {
            embedding_id: (chunk, source, source_uri)
            for embedding_id, chunk, source, source_uri in result.all()
        }

    async def authoritative_embedding_ids(
        self,
        collection_name: str,
        model_name: str,
        model_version: str,
    ) -> set[UUID]:
        """Return the embedding ids that are authoritative for a collection.

        Authoritative means the embedding belongs to a chunk of the latest
        version of a document in the collection and was produced by the active
        embedding model and version.
        """

        latest_version_ids = self._latest_version_ids()

        statement = (
            select(Embedding.id)
            .join(Chunk, Chunk.id == Embedding.chunk_id)
            .join(DocumentVersion, DocumentVersion.id == Chunk.document_version_id)
            .join(Document, Document.id == DocumentVersion.document_id)
            .join(Collection, Collection.id == Document.collection_id)
            .where(
                Collection.name == collection_name,
                Embedding.model_name == model_name,
                Embedding.model_version == model_version,
                Chunk.document_version_id.in_(select(latest_version_ids.c.id)),
            )
        )

        return set((await self.session.execute(statement)).scalars())

    async def classify_embeddings(
        self,
        embedding_ids: list[UUID],
        collection_name: str,
        model_name: str,
        model_version: str,
    ) -> dict[UUID, str]:
        """Classify embeddings relative to a collection's authoritative set.

        Ids absent from the result have no PostgreSQL records at all.
        """

        if not embedding_ids:
            return {}

        latest_version_ids = self._latest_version_ids()

        statement = (
            select(
                Embedding.id,
                Embedding.model_name,
                Embedding.model_version,
                Collection.name,
                Chunk.document_version_id.in_(select(latest_version_ids.c.id)),
            )
            .join(Chunk, Chunk.id == Embedding.chunk_id)
            .join(DocumentVersion, DocumentVersion.id == Chunk.document_version_id)
            .join(Document, Document.id == DocumentVersion.document_id)
            .join(Collection, Collection.id == Document.collection_id)
            .where(Embedding.id.in_(embedding_ids))
        )

        classification: dict[UUID, str] = {}

        for (
            embedding_id,
            record_model_name,
            record_model_version,
            record_collection_name,
            is_latest,
        ) in (await self.session.execute(statement)).all():
            if record_collection_name != collection_name:
                category = FOREIGN_COLLECTION
            elif not is_latest:
                category = SUPERSEDED_VERSION
            elif (
                record_model_name != model_name or record_model_version != model_version
            ):
                category = INACTIVE_MODEL
            else:
                category = AUTHORITATIVE

            classification[embedding_id] = category

        return classification
