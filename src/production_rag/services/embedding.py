from sentence_transformers import SentenceTransformer

from production_rag.db.session import async_session_factory
from production_rag.models.chunk import Chunk
from production_rag.models.embedding import Embedding
from production_rag.repositories.embedding import EmbeddingRepository
from production_rag.services.qdrant import QdrantVectorStore


class EmbeddingService:
    MODEL_NAME = "BAAI/bge-small-en-v1.5"
    MODEL_VERSION = "1"

    def __init__(
        self, encoder=None, vector_store: QdrantVectorStore | None = None
    ) -> None:
        self.encoder = encoder
        self.vector_store = vector_store or QdrantVectorStore()

    def _get_encoder(self):
        if self.encoder is None:
            self.encoder = SentenceTransformer(self.MODEL_NAME)

        return self.encoder

    async def embed_chunk(self, chunk: Chunk, collection_name: str) -> Embedding:
        async with async_session_factory() as session, session.begin():
            repository = EmbeddingRepository(session)

            existing = await repository.find_by_chunk_and_model(
                chunk_id=chunk.id,
                model_name=self.MODEL_NAME,
                model_version=self.MODEL_VERSION,
            )

            vector = self._get_encoder().encode(chunk.content)

            if hasattr(vector, "tolist"):
                vector = vector.tolist()

            if existing is not None:
                embedding = existing

            else:
                embedding = await repository.create(
                    chunk_id=chunk.id,
                    model_name=self.MODEL_NAME,
                    model_version=self.MODEL_VERSION,
                    dimensions=len(vector),
                )

                await session.flush()

            await self.vector_store.ensure_collection(
                collection_name=collection_name,
                vector_size=embedding.dimensions,
            )

            await self.vector_store.upsert(
                collection_name=collection_name,
                point_id=embedding.id,
                vector=vector,
                payload={
                    "embedding_id": str(embedding.id),
                    "chunk_id": str(chunk.id),
                    "model_name": embedding.model_name,
                    "model_version": embedding.model_version,
                    "chunk_index": chunk.chunk_index,
                },
            )

            return embedding

    async def embed_chunks(
        self, chunks: list[Chunk], collection_name: str
    ) -> list[Embedding]:
        embeddings = []

        for chunk in chunks:
            embedding = await self.embed_chunk(
                chunk,
                collection_name=collection_name,
            )
            embeddings.append(embedding)

        return embeddings
