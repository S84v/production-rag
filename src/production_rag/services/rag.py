import time
from collections.abc import AsyncIterator
from dataclasses import dataclass

from production_rag.services.llm import LLMService
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


tracer = get_tracer()


class RAGService:
    def __init__(
        self,
        retrieval_service: RetrievalService | None = None,
        llm_service: LLMService | None = None,
    ) -> None:
        self.retrieval_service = retrieval_service or RetrievalService()
        self.llm_service = llm_service or LLMService()

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

            span.set_attribute("rag.retrieved_chunks", len(results))
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
                for result in results
            ]

            yield RAGEvent(
                type="sources",
                sources=sources,
                retrieval_time_ms=retrieval_time_ms,
            )

            context = "\n\n".join(
                f"[Source {index}]\n{result.chunk.content}"
                for index, result in enumerate(results, start=1)
            )

            prompt = f"Question:\n{query}\n\nRetrieved context:\n{context}"

            instructions = (
                "Answer the question using only the retrieved context. "
                "If the context does not contain enough information to answer, "
                "say that you do not have enough information. "
                "Do not invent facts."
            )

            async for text in self.llm_service.generate(
                prompt=prompt,
                instructions=instructions,
            ):
                yield RAGEvent(type="text", text=text)

            total_time_ms = (time.perf_counter() - total_start) * 1000

            span.set_attribute("rag.total_time_ms", total_time_ms)

            yield RAGEvent(
                type="complete",
                total_time_ms=total_time_ms,
            )

    async def close(self) -> None:
        await self.llm_service.close()
        await self.retrieval_service.vector_store.close()
