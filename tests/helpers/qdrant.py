class FakeQdrantClient:
    def __init__(self, fail_on_upsert: bool = False, query_results=None) -> None:
        self.collections = []
        self.created_collections = []
        self.upserted_points = []
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

    async def upsert(self, collection_name, points):
        if self.fail_on_upsert:
            raise RuntimeError("Qdrant upsert failed")

        self.upserted_points.append((collection_name, points))

    async def query_points(
        self, collection_name, query, limit, with_payload, with_vectors
    ):
        return type(
            "QueryResponse",
            (),
            {"points": self.query_results[:limit]},
        )()
