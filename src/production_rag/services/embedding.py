from sentence_transformers import SentenceTransformer

from production_rag.db.session import async_session_factory
from production_rag.models.chunk import Chunk
from production_rag.models.embedding import Embedding
from production_rag.repositories.embedding import EmbeddingRepository


class EmbeddingService:
    def __init__(self, encoder=None) -> None:
        self.encoder = encoder

    def _get_encoder(self):
        if self.encoder is None:
            self.encoder = SentenceTransformer("BAAI/bge-small-en-v1.5")

        return self.encoder

    async def embed_chunk(self, chunk: Chunk) -> Embedding:
        vector = self._get_encoder().encode(chunk.content)

        async with async_session_factory() as session, session.begin():
            repository = EmbeddingRepository(session)

            existing = await repository.find_by_chunk_and_model(
                chunk_id=chunk.id,
                model_name="BAAI/bge-small-en-v1.5",
                model_version="1",
            )

            if existing is not None:
                return existing

            return await repository.create(
                chunk_id=chunk.id,
                model_name="BAAI/bge-small-en-v1.5",
                model_version="1",
                dimensions=len(vector),
                vector_key=str(chunk.id),
            )

    async def embed_chunks(self, chunks: list[Chunk]) -> list[Embedding]:
        embeddings = []

        for chunk in chunks:
            embedding = await self.embed_chunk(chunk)
            embeddings.append(embedding)

        return embeddings
