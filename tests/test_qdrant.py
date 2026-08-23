import uuid

import pytest
from qdrant_client.models import Distance

from production_rag.services.qdrant import QdrantVectorStore
from tests.helpers.qdrant import FakeQdrantClient


@pytest.mark.asyncio
async def test_ensure_collection_creates_missing_collection():
    client = FakeQdrantClient()
    store = QdrantVectorStore(client=client)

    await store.ensure_collection("fastapi", 384)

    assert client.created_collections
    assert client.created_collections[0][0] == "fastapi"
    assert client.created_collections[0][1].size == 384
    assert client.created_collections[0][1].distance == Distance.COSINE


@pytest.mark.asyncio
async def test_upsert_creates_qdrant_point():
    client = FakeQdrantClient()
    store = QdrantVectorStore(client=client)

    point_id = uuid.uuid4()
    vector = [0.1, 0.2, 0.3]
    payload = {"chunk_id": str(point_id)}

    await store.upsert(
        collection_name="fastapi",
        point_id=point_id,
        vector=vector,
        payload=payload,
    )

    assert len(client.upserted_points) == 1

    collection_name, points = client.upserted_points[0]

    assert collection_name == "fastapi"
    assert len(points) == 1
    assert points[0].id == str(point_id)
    assert points[0].vector == vector
    assert points[0].payload == payload


@pytest.mark.asyncio
async def test_ensure_collection_does_not_recreate_existing_collection():
    client = FakeQdrantClient()
    client.collections.append("fastapi")

    store = QdrantVectorStore(client=client)

    await store.ensure_collection("fastapi", 384)

    assert client.created_collections == []
