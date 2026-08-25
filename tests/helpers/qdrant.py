class FakeQdrantClient:
    def __init__(self, fail_on_upsert: bool = False) -> None:
        self.collections = []
        self.created_collections = []
        self.upserted_points = []
        self.fail_on_upsert = fail_on_upsert

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
