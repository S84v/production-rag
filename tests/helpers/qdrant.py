class FakePoint:
    def __init__(self, id, payload=None, vector=None) -> None:
        self.id = id
        self.payload = payload
        self.vector = vector


class FakeCollectionCount:
    def __init__(self, count: int) -> None:
        self.count = count


class FakeQdrantClient:
    """In-memory Qdrant double used by unit and integration tests.

    ``points`` is the stored state (collection -> point id -> record) while
    ``upserted_points`` and ``deleted_points`` are append-only logs used by
    assertions.
    """

    def __init__(
        self,
        fail_on_upsert: bool = False,
        query_results=None,
        collections=None,
    ) -> None:
        self.collections = list(collections or [])
        self.created_collections = []
        self.upserted_points = []
        self.deleted_points = []
        self.points: dict[str, dict[str, FakePoint]] = {}
        self.fail_on_upsert = fail_on_upsert
        self.query_results = query_results or []

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
        self.points.setdefault(collection_name, {})

    async def upsert(self, collection_name, points):
        if self.fail_on_upsert:
            raise RuntimeError("Qdrant upsert failed")

        self.upserted_points.append((collection_name, points))
        store = self.points.setdefault(collection_name, {})

        for point in points:
            store[str(point.id)] = FakePoint(
                id=str(point.id),
                payload=point.payload,
                vector=point.vector,
            )

    async def collection_exists(self, collection_name):
        return collection_name in self.collections

    async def count(self, collection_name, exact: bool = True):
        return FakeCollectionCount(len(self.points.get(collection_name, {})))

    async def scroll(
        self,
        collection_name,
        limit,
        offset=None,
        with_payload: bool = False,
        with_vectors: bool = False,
    ):
        stored = sorted(self.points.get(collection_name, {}).items())

        start = 0
        if offset is not None:
            ids = [point_id for point_id, _ in stored]
            start = ids.index(offset) + 1 if offset in ids else len(ids)

        batch = stored[start : start + limit]
        next_offset = batch[-1][0] if start + limit < len(stored) else None

        points = [
            FakePoint(
                id=point_id,
                payload=record.payload if with_payload else None,
                vector=record.vector if with_vectors else None,
            )
            for point_id, record in batch
        ]

        return points, next_offset

    async def retrieve(
        self,
        collection_name,
        ids,
        with_payload: bool = False,
        with_vectors: bool = False,
    ):
        store = self.points.get(collection_name, {})

        return [
            FakePoint(
                id=str(point_id),
                payload=store[str(point_id)].payload if with_payload else None,
                vector=store[str(point_id)].vector if with_vectors else None,
            )
            for point_id in ids
            if str(point_id) in store
        ]

    async def delete(self, collection_name, points_selector):
        store = self.points.setdefault(collection_name, {})
        ids = list(getattr(points_selector, "points", points_selector))
        self.deleted_points.append((collection_name, ids))

        for point_id in ids:
            store.pop(str(point_id), None)

    async def query_points(
        self, collection_name, query, limit, with_payload, with_vectors
    ):
        return type(
            "QueryResponse",
            (),
            {"points": self.query_results[:limit]},
        )()

    # Test helpers -----------------------------------------------------------

    def remove_point(self, collection_name: str, point_id) -> None:
        """Simulate a vector disappearing from Qdrant (for repair tests)."""

        self.points.get(collection_name, {}).pop(str(point_id), None)

    def seed_point(self, collection_name: str, point_id, payload=None) -> None:
        if collection_name not in self.collections:
            self.collections.append(collection_name)

        store = self.points.setdefault(collection_name, {})
        store[str(point_id)] = FakePoint(id=str(point_id), payload=payload)
