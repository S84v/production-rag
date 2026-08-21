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
