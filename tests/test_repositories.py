import uuid

import pytest

from production_rag.db.session import async_session_factory
from production_rag.models.collection import Collection
from production_rag.repositories.document import DocumentRepository
from production_rag.repositories.document_version import DocumentVersionRepository


@pytest.mark.asyncio
async def test_document_repository_find_and_create_by_identity():

    async with async_session_factory() as session:
        collection = Collection(
            name=f"test-repository-{uuid.uuid4()}",
            description="Repository integration test",
        )

        session.add(collection)
        await session.flush()

        repository = DocumentRepository(session)

        document = await repository.create(
            collection_id=collection.id,
            source="fastapi",
            source_uri="fastapi/path-params.md",
        )

        assert document.id is not None
        assert document.collection_id == collection.id
        assert document.source == "fastapi"
        assert document.source_uri == "fastapi/path-params.md"

        found = await repository.find_by_identity(
            collection_id=collection.id,
            source="fastapi",
            source_uri="fastapi/path-params.md",
        )

        assert found is not None
        assert found.id == document.id

        await session.rollback()


@pytest.mark.asyncio
async def test_document_version_repository_create_and_find_by_content_hash():

    async with async_session_factory() as session:
        collection = Collection(
            name=f"test-version-repository-{uuid.uuid4()}",
            description="Document version repository test",
        )

        session.add(collection)
        await session.flush()

        document_repository = DocumentRepository(session)

        document = await document_repository.create(
            collection_id=collection.id,
            source="fastapi",
            source_uri="fastapi/path-params.md",
        )

        version_repository = DocumentVersionRepository(session)

        content_hash = "a" * 64
        source_revision = "244d66308d6c525f394d0c2ce32dabceb2ed262b"

        version = await version_repository.create(
            document_id=document.id,
            content_hash=content_hash,
            title="Path Parameters",
            source_revision=source_revision,
        )

        assert version.id is not None
        assert version.document_id == document.id
        assert version.content_hash == content_hash
        assert version.title == "Path Parameters"
        assert version.source_revision == source_revision

        found = await version_repository.find_by_content_hash(
            document_id=document.id, content_hash=content_hash
        )

        assert found is not None
        assert found.id == version.id

        await session.rollback()
