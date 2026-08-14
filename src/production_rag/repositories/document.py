from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from production_rag.models.document import Document


class DocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def find_by_identity(
        self, collection_id: UUID, source: str, source_uri: str
    ) -> Document | None:
        statement = select(Document).where(
            Document.collection_id == collection_id,
            Document.source == source,
            Document.source_uri == source_uri,
        )

        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def create(
        self, collection_id: UUID, source: str, source_uri: str
    ) -> Document:
        document = Document(
            collection_id=collection_id, source=source, source_uri=source_uri
        )
        self.session.add(document)
        await self.session.flush()

        return document
