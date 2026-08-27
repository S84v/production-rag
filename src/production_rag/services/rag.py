from collections.abc import AsyncIterator

from production_rag.services.llm import LLMService
from production_rag.services.retrieval import RetrievalService


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
    ) -> AsyncIterator[str]:
        results = await self.retrieval_service.retrieve(
            query=query, collection_name=collection_name, limit=limit
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

        async for chunk in self.llm_service.generate(
            prompt=prompt,
            instructions=instructions,
        ):
            yield chunk
