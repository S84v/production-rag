import uuid

import pytest
from qdrant_client import AsyncQdrantClient

from production_rag.services.qdrant import QdrantVectorStore


@pytest.mark.asyncio
async def test_qdrant_vector_store_persists_and_queries_point():
    collection_name = f"test-{uuid.uuid4()}"
    point_id = uuid.uuid4()
    vector = [0.0] * 384
    vector[0] = 1.0

    client = AsyncQdrantClient(
        host="localhost",
        port=6333,
    )

    store = QdrantVectorStore(client=client)

    try:
        await store.ensure_collection(
            collection_name=collection_name,
            vector_size=384,
        )

        await store.upsert(
            collection_name=collection_name,
            point_id=point_id,
            vector=vector,
            payload={"chunk_id": str(point_id)},
        )

        result = await client.query_points(
            collection_name=collection_name,
            query=vector,
            limit=1,
        )

        assert len(result.points) == 1
        assert result.points[0].id == str(point_id)
        assert result.points[0].payload == {"chunk_id": str(point_id)}

    finally:
        await client.delete_collection(collection_name)
        await client.close()
