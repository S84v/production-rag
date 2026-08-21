import uuid

import pytest

from production_rag.services.qdrant import QdrantVectorStore


class FakeQdrantClient:
    def __init__(self) -> None:
        self.collections = []
        self.created_collections = []
        self.upserted_points = []

    async def get_collections(self):
        return type(
            "CollectionResponse",
            (),
            {
                "collections": [
                    type("Collection", (), {"name": name})()
                    for name in self.collections
                ]
            },
        )()

    async def create_collection(self, collection_name, vectors_config):
        self.created_collections.append((collection_name, vectors_config))
        self.collections.append(collection_name)

    async def upsert(self, collection_name, points):
        self.upserted_points.append((collection_name, points))


@pytest.mark.asyncio
async def test_ensure_collection_creates_missing_collection():
    client = FakeQdrantClient()
    store = QdrantVectorStore(client=client)

    await store.ensure_collection("fastapi", 384)

    assert client.created_collections
    assert client.created_collections[0][0] == "fastapi"
    assert client.created_collections[0][1].size == 384


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
