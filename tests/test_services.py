import uuid

import pytest

from production_rag.db.session import async_session_factory
from production_rag.models.collection import Collection
from production_rag.services.document_ingestion import DocumentIngestionService


async def create_test_collection() -> uuid.UUID:
    async with async_session_factory() as session, session.begin():
        collection = Collection(
            name=f"test-service-{uuid.uuid4()}",
            description="Document ingestion test service",
        )
        session.add(collection)
        await session.flush()

        return collection.id


@pytest.mark.asyncio
async def test_document_ingestion_creates_document_and_version():

    collection_id = await create_test_collection()
    service = DocumentIngestionService()

    document, version, created = await service.ingest_document(
        collection_id=collection_id,
        source="fastapi",
        source_uri=f"fastapi/test-{uuid.uuid4()}.md",
        content_hash="a" * 64,
        title="Test Document",
        source_revision="244d66308d6c525f394d0c2ce32dabceb2ed262b",
    )

    assert created is True
    assert document.collection_id == collection_id
    assert document.source == "fastapi"
    assert version.document_id == document.id
    assert version.content_hash == "a" * 64
    assert version.title == "Test Document"
    assert version.source_revision == "244d66308d6c525f394d0c2ce32dabceb2ed262b"


@pytest.mark.asyncio
async def test_document_ingestion_is_idempotent_and_creates_new_versions():
    collection_id = await create_test_collection()
    service = DocumentIngestionService()
    source_uri = f"fastapi/test-{uuid.uuid4()}.md"

    first_document, first_version, first_created = await service.ingest_document(
        collection_id=collection_id,
        source="fastapi",
        source_uri=source_uri,
        content_hash="b" * 64,
    )

    second_document, second_version, second_created = await service.ingest_document(
        collection_id=collection_id,
        source="fastapi",
        source_uri=source_uri,
        content_hash="b" * 64,
    )

    third_document, third_version, third_created = await service.ingest_document(
        collection_id=collection_id,
        source="fastapi",
        source_uri=source_uri,
        content_hash="c" * 64,
    )

    assert first_created is True
    assert second_created is False
    assert third_created is True

    assert second_document.id == first_document.id
    assert second_version.id == first_version.id

    assert third_document.id == first_document.id
    assert third_version.id != first_version.id
    assert third_version.document_id == first_document.id
