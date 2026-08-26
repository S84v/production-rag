from dataclass import dataclass

from production_rag.db.session import async_session_factory
from production_rag.modles.chunk import Chunk
from production_rag.repositories.retrieval import RetrievalRepository
from production_rag.services.embedding import EmbeddingService
from production_rag.services.qdrant import QdrantVectorStore


@dataclass
class RetrievalResult:
    chunk: Chunk
    score: float


class RetrievalService:
    def __init__(
        self,
        embedding_service: EmbeddingService | None = None,
        vector_store: QdrantVectorStore | None = None,
    ) -> None:

        self.embedding_service = embedding_service or EmbeddingService()
        self.vector_store = vector_store or QdrantVectorStore()

    async def retrieval(
        self, query: str, collection_name: str, limit: int = 5
    ) -> list[RetrievalResult]:
        vector = self.embedding_service.encode_query(query)

        hits = await self.vector_store.search(
            collection_name=collection_name, vector=vector, limit=limit
        )

        embedding_ids = [embedding_id for embedding_id, _ in hits]

        async with async_session_factory() as session:
            repository = RetrievalRepository(session)

            chunks_by_embedding_id = await repository.find_chunks_by_embedding_ids(
                embedding_ids=embedding_ids, collection_name=collection_name
            )

            return [
                RetrievalResult(chunk=chunks_by_embedding_id[embedding_id], score=score)
                for embedding_id, score in hits
                if embedding_id in chunks_by_embedding_id
            ]
