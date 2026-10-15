from dataclasses import dataclass

from sentence_transformers import SentenceTransformer

from production_rag.core.settings import get_settings
from production_rag.db.session import async_session_factory
from production_rag.models.chunk import Chunk
from production_rag.models.embedding import Embedding
from production_rag.repositories.embedding import EmbeddingRepository
from production_rag.services.qdrant import QdrantVectorStore

# Ingestion outcomes per chunk. Reported separately so an idempotent re-run is
# observable and a missing vector is repaired rather than duplicated.
EMBEDDING_ACTION_PERSISTED = "persisted"
EMBEDDING_ACTION_REPAIRED = "repaired"
EMBEDDING_ACTION_SKIPPED = "skipped"


def embedding_action(*, record_exists: bool, point_exists: bool) -> str:
    """Decide what ingestion must do for a single chunk.

    * no embedding record -> persist: create the record, encode, and upsert.
    * record and point exist -> skip: do not encode and do not upsert.
    * record exists but its point is missing -> repair: re-encode and upsert
      using the existing embedding id, without creating another record.
    """

    if not record_exists:
        return EMBEDDING_ACTION_PERSISTED

    if point_exists:
        return EMBEDDING_ACTION_SKIPPED

    return EMBEDDING_ACTION_REPAIRED


@dataclass(frozen=True)
class EmbeddingBatch:
    embeddings: list[Embedding]
    persisted: int = 0
    repaired: int = 0
    skipped: int = 0

    def __iter__(self):
        return iter(self.embeddings)

    def __len__(self) -> int:
        return len(self.embeddings)


class EmbeddingService:
    MODEL_NAME = "BAAI/bge-small-en-v1.5"
    MODEL_VERSION = "1"

    def __init__(
        self, encoder=None, vector_store: QdrantVectorStore | None = None
    ) -> None:
        self.revision = get_settings().embedding_model_revision or None
        self.encoder = encoder
        self.vector_store = vector_store or QdrantVectorStore()

    def _get_encoder(self):
        if self.encoder is None:
            from transformers import logging

            logging.set_verbosity_error()
            logging.disable_progress_bar()

            self.encoder = SentenceTransformer(
                self.MODEL_NAME,
                revision=self.revision,
                local_files_only=True,
            )

        return self.encoder

    def _encode(self, text: str) -> list[float]:
        vector = self._get_encoder().encode(text)

        if hasattr(vector, "tolist"):
            vector = vector.tolist()

        return vector

    def encode_query(self, query: str) -> list[float]:
        return self._encode(query)

    async def embed_chunk(self, chunk: Chunk, collection_name: str) -> Embedding:
        batch = await self._embed_chunks([chunk], collection_name)

        return batch.embeddings[0]

    async def embed_chunks(
        self, chunks: list[Chunk], collection_name: str
    ) -> EmbeddingBatch:
        return await self._embed_chunks(chunks, collection_name)

    async def _embed_chunks(
        self, chunks: list[Chunk], collection_name: str
    ) -> EmbeddingBatch:

        if not chunks:
            return EmbeddingBatch(embeddings=[])

        async with async_session_factory() as session:
            repository = EmbeddingRepository(session)

            records = await repository.list_by_chunk_ids(
                chunk_ids=[chunk.id for chunk in chunks],
                model_name=self.MODEL_NAME,
                model_version=self.MODEL_VERSION,
            )

        # Batched existence check: only chunks that already have a record need
        # their Qdrant point looked up, and skipped chunks are never encoded.
        collection_exists = await self.vector_store.collection_exists(collection_name)

        existing_points: set = set()
        if collection_exists and records:
            existing_points = await self.vector_store.existing_point_ids(
                collection_name,
                [record.id for record in records.values()],
            )

        embeddings: list[Embedding] = []
        persisted = repaired = skipped = 0

        for chunk in chunks:
            record = records.get(chunk.id)
            action = embedding_action(
                record_exists=record is not None,
                point_exists=record is not None and record.id in existing_points,
            )

            if action == EMBEDDING_ACTION_SKIPPED:
                assert record is not None
                embeddings.append(record)
                skipped += 1
                continue

            vector = self._encode(chunk.content)

            if action == EMBEDDING_ACTION_PERSISTED:
                embeddings.append(
                    await self._persist_embedding(
                        collection_name=collection_name,
                        chunk=chunk,
                        vector=vector,
                    )
                )
                persisted += 1
            else:
                assert record is not None
                embeddings.append(
                    await self._repair_embedding(
                        collection_name=collection_name,
                        chunk=chunk,
                        vector=vector,
                        embedding=record,
                    )
                )
                repaired += 1

        return EmbeddingBatch(
            embeddings=embeddings,
            persisted=persisted,
            repaired=repaired,
            skipped=skipped,
        )

    async def _persist_embedding(
        self,
        *,
        collection_name: str,
        chunk: Chunk,
        vector: list[float],
    ) -> Embedding:
        """Create the embedding record, then write its Qdrant point.

        The upsert runs inside the open database transaction. A failed upsert
        therefore raises before the transaction commits, so the new embedding row
        is rolled back and no record is left without a vector.

        The reverse is not guaranteed. Qdrant is written before the database
        commit, so a commit that fails after a successful upsert can leave a
        Qdrant point with no corresponding database row. There is no distributed
        transaction; such a point is non-authoritative and
        ``production-rag reconcile`` reports it (and can delete it with
        ``--apply``).
        """

        async with async_session_factory() as session, session.begin():
            repository = EmbeddingRepository(session)

            embedding = await repository.create(
                chunk_id=chunk.id,
                model_name=self.MODEL_NAME,
                model_version=self.MODEL_VERSION,
                dimensions=len(vector),
            )

            await session.flush()

            await self._upsert_point(
                collection_name=collection_name,
                chunk=chunk,
                vector=vector,
                embedding=embedding,
            )

            return embedding

    async def _repair_embedding(
        self,
        *,
        collection_name: str,
        chunk: Chunk,
        vector: list[float],
        embedding: Embedding,
    ) -> Embedding:
        """Re-encode a chunk whose Qdrant point is missing.

        The existing embedding id is reused so no duplicate record is created
        and the point keeps the identity the database expects. No database row is
        written here, so a failed upsert simply leaves the point missing, which
        is the state this method repairs.
        """

        async with async_session_factory() as session, session.begin():
            await self._upsert_point(
                collection_name=collection_name,
                chunk=chunk,
                vector=vector,
                embedding=embedding,
            )

            return embedding

    async def _upsert_point(
        self,
        *,
        collection_name: str,
        chunk: Chunk,
        vector: list[float],
        embedding: Embedding,
    ) -> None:
        await self.vector_store.ensure_collection(
            collection_name=collection_name,
            vector_size=len(vector),
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
