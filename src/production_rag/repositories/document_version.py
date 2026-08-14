from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from production_rag.models.document_version import DocumentVersion


class DocumentVersionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def find_by_content_hash(
        self, document_id: UUID, content_hash: str
    ) -> DocumentVersion | None:

        statement = select(DocumentVersion).where(
            DocumentVersion.document_id == document_id,
            DocumentVersion.content_hash == content_hash,
        )

        result = await self.session.execute(statement)

        return result.scalar_one_or_none()

    async def create(
        self,
        document_id: UUID,
        content_hash: str,
        title: str | None = None,
        source_revision: str | None = None,
    ) -> DocumentVersion:

        version = DocumentVersion(
            document_id=document_id,
            content_hash=content_hash,
            title=title,
            source_revision=source_revision,
        )

        self.session.add(version)
        await self.session.flush()

        return version
