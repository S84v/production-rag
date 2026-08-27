import uuid

import pytest

from production_rag.db.session import async_session_factory
from production_rag.models.collection import Collection
from production_rag.repositories.chunk import ChunkRepository
from production_rag.services.document_ingestion import DocumentIngestionService
from production_rag.services.embedding import EmbeddingService
from production_rag.services.retrieval import RetrievalService


async def create_test_collection() -> Collection:
    async with async_session_factory() as session, session.begin():
        collection = Collection(
            name=f"test-retrieval-{uuid.uuid4()}",
            description="Retrieval integration test",
        )
        session.add(collection)
        await session.flush()

        return collection


@pytest.mark.asyncio
async def test_retrieval_service_retrieves_hydrated_chunk_from_qdrant():
    collection = await create_test_collection()

    ingestion_service = DocumentIngestionService()

    _, version, created = await ingestion_service.ingest_document(
        collection_id=collection.id,
        source="test",
        source_uri=f"test/retrieval-{uuid.uuid4()}.md",
        content=(
            "# FastAPI Applications\n\n"
            "FastAPI is a modern web framework for building APIs"
            "with Python based on standard Python type hints."
        ),
        content_hash=uuid.uuid4().hex + uuid.uuid4().hex,
        title="FastAPI Applications",
    )

    assert created is True

    async with async_session_factory() as session:
        chunk_repository = ChunkRepository(session)
        chunks = await chunk_repository.list_by_document_version(version.id)

    assert len(chunks) == 1

    embedding_service = EmbeddingService()

    await embedding_service.embed_chunks(
        chunks=chunks,
        collection_name=collection.name,
    )

    retrieval_service = RetrievalService()

    results = await retrieval_service.retrieve(
        query="How do I build an API with FastAPI?",
        collection_name=collection.name,
        limit=1,
    )

    assert len(results) == 1
    assert results[0].chunk.id == chunks[0].id
    assert results[0].chunk.content == chunks[0].content
    assert results[0].score > 0
