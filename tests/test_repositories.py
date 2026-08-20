import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from production_rag.db.session import async_session_factory
from production_rag.models.collection import Collection
from production_rag.repositories.chunk import ChunkRepository
from production_rag.repositories.document import DocumentRepository
from production_rag.repositories.document_version import DocumentVersionRepository
from production_rag.repositories.embedding import EmbeddingRepository


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


@pytest.mark.asyncio
async def test_chunk_repository_create_find_and_list():

    async with async_session_factory() as session:
        collection = Collection(
            name=f"test-chunk-repository-{uuid.uuid4()}",
            description="Chunk repository integration test",
        )

        session.add(collection)
        await session.flush()

        document_repository = DocumentRepository(session)

        document = await document_repository.create(
            collection_id=collection.id,
            source="fastapi",
            source_uri="fastapi/chunk-test.md",
        )

        version_repository = DocumentVersionRepository(session)

        version = await version_repository.create(
            document_id=document.id,
            content_hash="d" * 64,
        )

        chunk_repository = ChunkRepository(session)

        chunk_1 = await chunk_repository.create(
            document_version_id=version.id,
            chunk_index=1,
            content="Second chunk",
            token_count=2,
            chunk_metadata={"heading": "Second"},
        )

        chunk_0 = await chunk_repository.create(
            document_version_id=version.id,
            chunk_index=0,
            content="First chunk",
            token_count=2,
            chunk_metadata={"heading": "First"},
        )

        found = await chunk_repository.find_by_index(
            document_version_id=version.id, chunk_index=1
        )

        assert found is not None
        assert found.id == chunk_1.id
        assert found.content == "Second chunk"

        chunks = await chunk_repository.list_by_document_version(
            document_version_id=version.id
        )

        assert [chunk.id for chunk in chunks] == [
            chunk_0.id,
            chunk_1.id,
        ]

        assert [chunk.chunk_index for chunk in chunks] == [0, 1]

        await session.rollback()


@pytest.mark.asyncio
async def test_embedding_repository_create_and_find_by_chunk_and_model():
    async with async_session_factory() as session:
        collection = Collection(
            name=f"test-embedding-repository-{uuid.uuid4()}",
            description="Embedding repository integration test",
        )

        session.add(collection)
        await session.flush()

        document_repository = DocumentRepository(session)

        document = await document_repository.create(
            collection_id=collection.id,
            source="fastapi",
            source_uri="fastapi/embedding-test.md",
        )

        version_repository = DocumentVersionRepository(session)

        version = await version_repository.create(
            document_id=document.id,
            content_hash="e" * 64,
        )

        chunk_repository = ChunkRepository(session)

        chunk = await chunk_repository.create(
            document_version_id=version.id,
            chunk_index=0,
            content="Embedding test chunk",
        )

        embedding_repository = EmbeddingRepository(session)

        embedding = await embedding_repository.create(
            chunk_id=chunk.id,
            model_name="BAAI/bge-small-en-v1.5",
            model_version="1",
            dimensions=384,
            vector_key=str(chunk.id),
        )

        assert embedding.id is not None
        assert embedding.chunk_id == chunk.id
        assert embedding.model_name == "BAAI/bge-small-en-v1.5"
        assert embedding.model_version == "1"
        assert embedding.dimensions == 384
        assert embedding.vector_key == str(chunk.id)

        found = await embedding_repository.find_by_chunk_and_model(
            chunk_id=chunk.id,
            model_name="BAAI/bge-small-en-v1.5",
            model_version="1",
        )

        assert found is not None
        assert found.id == embedding.id

        await session.rollback()


@pytest.mark.asyncio
async def test_embedding_repository_rejects_duplicate_chunk_model_version():

    async with async_session_factory() as session:
        collection = Collection(
            name=f"test-embedding-uniqie-{uuid.uuid4()}",
            description="Embedding uniqueness integration test",
        )

        session.add(collection)
        await session.flush()

        document_repository = DocumentRepository(session)

        document = await document_repository.create(
            collection_id=collection.id,
            source="fastapi",
            source_uri="fastapi/embedding-unique-test.md",
        )

        version_repository = DocumentVersionRepository(session)

        version = await version_repository.create(
            document_id=document.id,
            content_hash="f" * 64,
        )

        chunk_repository = ChunkRepository(session)

        chunk = await chunk_repository.create(
            document_version_id=version.id,
            chunk_index=0,
            content="Embedding uniquenes test chunk",
        )

        embedding_repository = EmbeddingRepository(session)

        await embedding_repository.create(
            chunk_id=chunk.id,
            model_name="BAAI/bge-small-en-v1.5",
            model_version="1",
            dimensions=384,
            vector_key=str(chunk.id),
        )

        with pytest.raises(IntegrityError):
            await embedding_repository.create(
                chunk_id=chunk.id,
                model_name="BAAI/bge-small-en-v1.5",
                model_version="1",
                dimensions=384,
                vector_key=str(chunk.id),
            )

        await session.rollback()
