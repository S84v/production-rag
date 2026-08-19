import uuid
from pathlib import Path

import pytest

from production_rag.db.session import async_session_factory
from production_rag.ingestion.filesystem import FilesystemSource
from production_rag.models.collection import Collection
from production_rag.repositories.chunk import ChunkRepository
from production_rag.services.batch_ingestion import BatchIngestionService
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
        content="# Test Document\n\nThis is test content.",
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
    content = "# Test Document\n\nThis is test content."
    updated_content = "# Test Document\n\nThis is updated content."
    collection_id = await create_test_collection()
    service = DocumentIngestionService()
    source_uri = f"fastapi/test-{uuid.uuid4()}.md"

    first_document, first_version, first_created = await service.ingest_document(
        collection_id=collection_id,
        source="fastapi",
        source_uri=source_uri,
        content=content,
        content_hash="b" * 64,
    )

    second_document, second_version, second_created = await service.ingest_document(
        collection_id=collection_id,
        source="fastapi",
        source_uri=source_uri,
        content=content,
        content_hash="b" * 64,
    )

    third_document, third_version, third_created = await service.ingest_document(
        collection_id=collection_id,
        source="fastapi",
        source_uri=source_uri,
        content=updated_content,
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

    async with async_session_factory() as session:
        chunk_repository = ChunkRepository(session)

        first_chunks = await chunk_repository.list_by_document_version(first_version.id)

        third_chunks = await chunk_repository.list_by_document_version(third_version.id)

    assert len(first_chunks) > 0
    assert len(third_chunks) > 0

    assert [chunk.chunk_index for chunk in first_chunks] == list(
        range(len(first_chunks))
    )

    assert [chunk.chunk_index for chunk in third_chunks] == list(
        range(len(third_chunks))
    )


@pytest.mark.asyncio
async def test_document_ingestion_creates_chunks_for_new_version():
    collection_id = await create_test_collection()
    service = DocumentIngestionService()

    content = """# Introduction

                FastAPI is a web framework.

                ## Installation

                Install FastAPI with pip.
            """

    document, version, created = await service.ingest_document(
        collection_id=collection_id,
        source="fastapi",
        source_uri=f"fastapi/test-{uuid.uuid4()}.md",
        content=content,
        content_hash="d" * 64,
        title="Test Document",
        source_revision="244d66308d6c525f394d0c2ce32dabceb2ed262b",
    )

    assert created is True

    async with async_session_factory() as session:
        chunk_repository = ChunkRepository(session)

        chunks = await chunk_repository.list_by_document_version(version.id)

    assert len(chunks) > 0
    assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))
    assert chunks[0].content.startswith("# Introduction")


@pytest.mark.asyncio
async def test_source_document_can_be_ingested(tmp_path):
    content = "# Introduction\n\nFastAPI is a web framework."
    document_path = tmp_path / "fastapi.md"
    document_path.write_text(content, encoding="utf-8")

    source = FilesystemSource(tmp_path)
    source_document = source.acquire(document_path)

    collection_id = await create_test_collection()
    service = DocumentIngestionService()

    document, version, created = await service.ingest_source_document(
        collection_id=collection_id, source_document=source_document
    )

    assert created is True
    assert document.collection_id == collection_id
    assert document.source == "filesystem"
    assert document.source_uri == "filesystem://fastapi.md"

    assert version.document_id == document.id
    assert version.content_hash == source_document.content_hash

    async with async_session_factory() as session:
        chunk_repository = ChunkRepository(session)

        chunks = await chunk_repository.list_by_document_version(version.id)

    assert len(chunks) > 0
    assert chunks[0].content.startswith("# Introduction")


@pytest.mark.asyncio
async def test_source_document_ingestion_is_idempotent(tmp_path):
    content = "# FastAPI\n\nA web framework."
    document_path = tmp_path / "fastapi.md"
    document_path.write_text(content, encoding="utf-8")

    source = FilesystemSource(tmp_path)
    source_document = source.acquire(document_path)

    collection_id = await create_test_collection()
    service = DocumentIngestionService()

    (
        first_document,
        first_version,
        first_created,
    ) = await service.ingest_source_document(
        collection_id=collection_id,
        source_document=source_document,
    )

    (
        second_document,
        second_version,
        second_created,
    ) = await service.ingest_source_document(
        collection_id=collection_id,
        source_document=source_document,
    )

    assert first_created is True
    assert second_created is False

    assert second_document.id == first_document.id
    assert second_version.id == first_version.id


@pytest.mark.asyncio
async def test_filesystem_batch_ingestion_processes_all_markdown_files(tmp_path):
    first_path = tmp_path / "first.md"
    nested_path = tmp_path / "nested" / "second.md"

    nested_path.parent.mkdir()

    first_path.write_text("# First Document\n\nFirst content.", encoding="utf-8")

    nested_path.write_text("# Second Document\n\nSecond content.", encoding="utf-8")

    source = FilesystemSource(tmp_path)
    collection_id = await create_test_collection()

    document_ingestion_service = DocumentIngestionService()
    batch_service = BatchIngestionService(document_ingestion_service)

    results = await batch_service.ingest_filesystem(
        collection_id=collection_id,
        source=source,
    )

    assert len(results) == 2
    assert all(created for _, _, created in results)

    assert [document.source_uri for document, _, _ in results] == [
        "filesystem://first.md",
        "filesystem://nested/second.md",
    ]


@pytest.mark.asyncio
async def test_filesystem_batch_ingestion_is_idempotent(tmp_path):
    first_path = tmp_path / "first.md"
    second_path = tmp_path / "nested" / "second.md"

    second_path.parent.mkdir()

    first_path.write_text("# First Document\n\nFirst content.", encoding="utf8")
    second_path.write_text("# Second Document\n\nSecond content.", encoding="utf8")

    source = FilesystemSource(tmp_path)
    collection_id = await create_test_collection()

    document_ingestion_service = DocumentIngestionService()
    batch_service = BatchIngestionService(document_ingestion_service)

    first_results = await batch_service.ingest_filesystem(
        collection_id=collection_id,
        source=source,
    )

    second_results = await batch_service.ingest_filesystem(
        collection_id=collection_id,
        source=source,
    )

    assert len(first_results) == 2
    assert len(second_results) == 2

    assert all(created for _, _, created in first_results)
    assert all(not created for _, _, created in second_results)

    assert [document.id for document, _, _ in second_results] == [
        document.id for document, _, _ in first_results
    ]

    assert [version.id for _, version, _ in second_results] == [
        version.id for _, version, _ in first_results
    ]


@pytest.mark.asyncio
async def test_filesystem_batch_ingestion_processes_fastapi_corpus():
    corpus_root = Path("data/raw/fastapi")

    source = FilesystemSource(corpus_root)
    collection_id = await create_test_collection()

    document_ingestion_service = DocumentIngestionService()
    batch_service = BatchIngestionService(document_ingestion_service)

    results = await batch_service.ingest_filesystem(
        collection_id=collection_id,
        source=source,
    )

    assert results
    assert all(created for _, _, created in results)

    discovered_paths = source.discover()

    assert len(results) == len(discovered_paths)
