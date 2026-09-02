from uuid import UUID

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from production_rag.core.settings import get_settings


class QdrantVectorStore:
    def __init__(self, client: AsyncQdrantClient | None = None) -> None:
        settings = get_settings()

        self.client = client or AsyncQdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
        )

    async def ensure_collection(self, collection_name: str, vector_size: int) -> None:
        collections = await self.client.get_collections()

        if any(
            collection.name == collection_name for collection in collections.collections
        ):
            return

        await self.client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )

    async def upsert(
        self, collection_name: str, point_id: UUID, vector: list[float], payload: dict
    ) -> None:
        await self.client.upsert(
            collection_name=collection_name,
            points=[PointStruct(id=str(point_id), vector=vector, payload=payload)],
        )

    async def collection_exists(self, collection_name: str) -> bool:
        collections = await self.client.get_collections()

        return any(
            collection.name == collection_name for collection in collections.collections
        )

    async def search(
        self, collection_name: str, vector: list[float], limit: int
    ) -> list[tuple[UUID, float]]:

        response = await self.client.query_points(
            collection_name=collection_name,
            query=vector,
            limit=limit,
            with_payload=False,
            with_vectors=False,
        )

        return [(UUID(str(point.id)), point.score) for point in response.points]

    async def close(self) -> None:
        await self.client.close()
