from uuid import UUID

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, PointIdsList, PointStruct, VectorParams

from production_rag.core.settings import Settings, get_settings

# Bounded batches keep reconciliation and point-existence checks predictable.
SCROLL_BATCH_SIZE = 256
POINT_BATCH_SIZE = 256


def build_qdrant_client_kwargs(settings: Settings) -> dict[str, str | int]:
    """Return ``AsyncQdrantClient`` keyword arguments from settings.

    A hosted ``QDRANT_URL`` takes precedence over the local
    ``QDRANT_HOST``/``QDRANT_PORT`` pair and is passed as ``url``. The API key
    is attached only to a hosted URL and only when it is non-blank; local
    connections stay unauthenticated as before.
    """
    url = settings.qdrant_url.strip()

    if url:
        api_key = settings.qdrant_api_key.strip()

        kwargs: dict[str, str | int] = {"url": url}
        if api_key:
            kwargs["api_key"] = api_key

        return kwargs

    return {"host": settings.qdrant_host, "port": settings.qdrant_port}


class QdrantVectorStore:
    def __init__(self, client: AsyncQdrantClient | None = None) -> None:
        settings = get_settings()

        self.client = client or AsyncQdrantClient(
            **build_qdrant_client_kwargs(settings)
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

    async def count_points(self, collection_name: str) -> int:
        result = await self.client.count(collection_name=collection_name, exact=True)

        return int(result.count)

    async def scroll_point_ids(self, collection_name: str) -> set[UUID]:
        """Return every point id in a collection using bounded pagination."""

        point_ids: set[UUID] = set()
        offset = None

        while True:
            points, offset = await self.client.scroll(
                collection_name=collection_name,
                limit=SCROLL_BATCH_SIZE,
                offset=offset,
                with_payload=False,
                with_vectors=False,
            )

            for point in points:
                point_ids.add(UUID(str(point.id)))

            if offset is None:
                break

        return point_ids

    async def existing_point_ids(
        self, collection_name: str, point_ids: list[UUID]
    ) -> set[UUID]:
        """Return the subset of ``point_ids`` that currently exist in Qdrant."""

        existing: set[UUID] = set()
        as_strings = [str(point_id) for point_id in point_ids]

        for start in range(0, len(as_strings), POINT_BATCH_SIZE):
            batch = as_strings[start : start + POINT_BATCH_SIZE]

            records = await self.client.retrieve(
                collection_name=collection_name,
                ids=batch,
                with_payload=False,
                with_vectors=False,
            )

            existing.update(UUID(str(record.id)) for record in records)

        return existing

    async def delete_points(self, collection_name: str, point_ids: list[UUID]) -> int:
        """Delete specific points from one collection in bounded batches."""

        deleted = 0
        as_strings = [str(point_id) for point_id in point_ids]

        for start in range(0, len(as_strings), POINT_BATCH_SIZE):
            batch = as_strings[start : start + POINT_BATCH_SIZE]

            await self.client.delete(
                collection_name=collection_name,
                points_selector=PointIdsList(points=batch),
            )

            deleted += len(batch)

        return deleted

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
