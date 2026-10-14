import time
from collections.abc import AsyncIterator
from dataclasses import dataclass

from production_rag.core.settings import get_settings
from production_rag.services.llm import GenerationError, LLMService
from production_rag.services.retrieval import RetrievalService
from production_rag.telemetry import get_tracer


@dataclass
class RAGSource:
    source: str
    source_uri: str
    chunk_id: str
    chunk_index: int
    score: float
    content: str


@dataclass
class RAGEvent:
    type: str
    text: str | None = None
    sources: list[RAGSource] | None = None
    retrieval_time_ms: float | None = None
    total_time_ms: float | None = None
    error_code: str | None = None
    error_message: str | None = None


tracer = get_tracer()


def _within_context_budget(results: list, max_characters: int) -> list:
    """Rank-preserving prefix of results whose combined content fits the budget.

    Chunks are kept whole and in retrieval-rank order; the first chunk that
    would exceed the remaining budget stops selection, so lower-ranked chunks
    are never reordered or partially truncated. Only the returned chunks are
    rendered into the prompt and reported in the ``sources`` event.
    """
    included: list = []
    used = 0

    for result in results:
        size = len(result.chunk.content)

        if used + size > max_characters:
            break

        included.append(result)
        used += size

    return included


class RAGService:
    def __init__(
        self,
        retrieval_service: RetrievalService | None = None,
        llm_service: LLMService | None = None,
        max_context_characters: int | None = None,
    ) -> None:
        settings = get_settings()

        self.retrieval_service = retrieval_service or RetrievalService()
        self.llm_service = llm_service or LLMService()
        self.max_context_characters = (
            settings.max_context_characters
            if max_context_characters is None
            else max_context_characters
        )

    async def collection_exists(self, collection_name: str) -> bool:
        return await self.retrieval_service.collection_exists(collection_name)

    async def generate(
        self,
        query: str,
        collection_name: str,
        limit: int = 5,
    ) -> AsyncIterator[RAGEvent]:

        with tracer.start_as_current_span("rag.generate") as span:
            span.set_attribute("rag.collection", collection_name)
            span.set_attribute("rag.limit", limit)

            total_start = time.perf_counter()

            retrieval_start = time.perf_counter()

            results = await self.retrieval_service.retrieve(
                query=query,
                collection_name=collection_name,
                limit=limit,
            )

            retrieval_time_ms = (time.perf_counter() - retrieval_start) * 1000

            included = _within_context_budget(results, self.max_context_characters)

            span.set_attribute("rag.retrieved_chunks", len(results))
            span.set_attribute("rag.context_chunks", len(included))
            span.set_attribute("rag.retrieval_time_ms", retrieval_time_ms)

            sources = [
                RAGSource(
                    source=result.source,
                    source_uri=result.source_uri,
                    chunk_id=str(result.chunk.id),
                    chunk_index=result.chunk.chunk_index,
                    score=result.score,
                    content=result.chunk.content,
                )
                for result in included
            ]

            yield RAGEvent(
                type="sources",
                sources=sources,
                retrieval_time_ms=retrieval_time_ms,
            )

            context = "\n\n".join(
                f"[Source {index}]\n{result.chunk.content}"
                for index, result in enumerate(included, start=1)
            )

            prompt = f"Question:\n{query}\n\nRetrieved context:\n{context}"

            instructions = (
                "Answer the question using only the retrieved context. "
                "If the context does not contain enough information to answer, "
                "say that you do not have enough information. "
                "Do not invent facts."
            )

            try:
                async for text in self.llm_service.generate(
                    prompt=prompt,
                    instructions=instructions,
                ):
                    yield RAGEvent(type="text", text=text)
            except GenerationError as error:
                span.set_attribute("rag.error_code", error.code)

                yield RAGEvent(
                    type="error",
                    error_code=error.code,
                    error_message=error.message,
                )

                return

            total_time_ms = (time.perf_counter() - total_start) * 1000

            span.set_attribute("rag.total_time_ms", total_time_ms)

            yield RAGEvent(
                type="complete",
                retrieval_time_ms=retrieval_time_ms,
                total_time_ms=total_time_ms,
            )

    async def close(self) -> None:
        await self.llm_service.close()
        await self.retrieval_service.vector_store.close()
