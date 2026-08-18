from uuid import UUID

from production_rag.db.session import async_session_factory
from production_rag.ingestion.chunker import MarkdownChunker
from production_rag.models.document import Document
from production_rag.models.document_version import DocumentVersion
from production_rag.repositories.chunk import ChunkRepository
from production_rag.repositories.document import DocumentRepository
from production_rag.repositories.document_version import DocumentVersionRepository


class DocumentIngestionService:
    async def ingest_document(
        self,
        collection_id: UUID,
        source: str,
        source_uri: str,
        content: str,
        content_hash: str,
        title: str | None = None,
        source_revision: str | None = None,
    ) -> tuple[Document, DocumentVersion, bool]:

        async with async_session_factory() as session, session.begin():
            document_repository = DocumentRepository(session)
            version_repository = DocumentVersionRepository(session)

            document = await document_repository.find_by_identity(
                collection_id=collection_id,
                source=source,
                source_uri=source_uri,
            )

            if document is None:
                document = await document_repository.create(
                    collection_id=collection_id, source=source, source_uri=source_uri
                )

            version = await version_repository.find_by_content_hash(
                document_id=document.id,
                content_hash=content_hash,
            )

            if version is not None:
                return document, version, False

            version = await version_repository.create(
                document_id=document.id,
                content_hash=content_hash,
                title=title,
                source_revision=source_revision,
            )

            chunker = MarkdownChunker()
            chunk_repository = ChunkRepository(session)

            chunks = chunker.chunk(content)

            for chunk in chunks:
                await chunk_repository.create(
                    document_version_id=version.id,
                    chunk_index=chunk.chunk_index,
                    content=chunk.content,
                    token_count=chunk.token_count,
                    chunk_metadata=chunk.metadata,
                )

            return document, version, True
