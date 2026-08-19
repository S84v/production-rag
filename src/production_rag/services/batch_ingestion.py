from uuid import UUID

from production_rag.ingestion.filesystem import FilesystemSource
from production_rag.models.document import Document
from production_rag.models.document_version import DocumentVersion
from production_rag.services.document_ingestion import DocumentIngestionService


class BatchIngestionService:
    def __init__(self, document_ingestion_service: DocumentIngestionService) -> None:
        self.document_ingestion_service = document_ingestion_service

    async def ingest_filesystem(
        self,
        collection_id: UUID,
        source: FilesystemSource,
    ) -> list[tuple[Document, DocumentVersion, bool]]:

        results = []

        for path in source.discover():
            source_document = source.acquire(path)
            result = await self.document_ingestion_service.ingest_source_document(
                collection_id=collection_id,
                source_document=source_document,
            )

            results.append(result)

        return results
