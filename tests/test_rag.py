from types import SimpleNamespace

import pytest

from production_rag.services.rag import RAGEvent, RAGService, RAGSource


class FakeRetrievalService:
    def __init__(self, results):
        self.results = results
        self.calls = []

    async def retrieve(self, **kwargs):
        self.calls.append(kwargs)
        return self.results


class FakeLLMService:
    def __init__(self, chunks):
        self.chunks = chunks
        self.calls = []

    async def generate(self, **kwargs):
        self.calls.append(kwargs)

        for chunk in self.chunks:
            yield chunk


@pytest.mark.asyncio
async def test_rag_service_retrieves_context_and_streams_answer():
    retrieval_service = FakeRetrievalService(
        [
            SimpleNamespace(
                chunk=SimpleNamespace(
                    content="FastAPI is a Python web framework.",
                    chunk_index=0,
                ),
                source="fastapi",
                source_uri="docs/index.md",
                score=0.95,
            ),
            SimpleNamespace(
                chunk=SimpleNamespace(
                    content="FastAPI uses standard Python type hints.",
                    chunk_index=1,
                ),
                source="fastapi",
                source_uri="docs/features.md",
                score=0.90,
            ),
        ]
    )

    llm_service = FakeLLMService(
        [
            "FastAPI",
            " is a Python web framework.",
        ]
    )

    service = RAGService(retrieval_service=retrieval_service, llm_service=llm_service)

    events = [
        event
        async for event in service.generate(
            query="What is FastAPI?", collection_name="fastapi", limit=2
        )
    ]

    assert events[0] == RAGEvent(
        type="sources",
        sources=[
            RAGSource(
                source="fastapi",
                source_uri="docs/index.md",
                chunk_index=0,
                score=0.95,
            ),
            RAGSource(
                source="fastapi",
                source_uri="docs/features.md",
                chunk_index=1,
                score=0.90,
            ),
        ],
    )

    text = "".join(
        event.text
        for event in events
        if event.type == "text" and event.text is not None
    )

    assert text == "FastAPI is a Python web framework."

    assert retrieval_service.calls == [
        {
            "query": "What is FastAPI?",
            "collection_name": "fastapi",
            "limit": 2,
        }
    ]

    assert len(llm_service.calls) == 1

    call = llm_service.calls[0]

    assert call["instructions"] == (
        "Answer the question using only the retrieved context. "
        "If the context does not contain enough information to answer, "
        "say that you do not have enough information. "
        "Do not invent facts."
    )

    assert call["prompt"] == (
        "Question:\nWhat is FastAPI?\n\n"
        "Retrieved context:\n"
        "[Source 1]\nFastAPI is a Python web framework.\n\n"
        "[Source 2]\nFastAPI uses standard Python type hints."
    )


@pytest.mark.asyncio
async def test_rag_service_handles_no_retrieved_context():
    retrieval_service = FakeRetrievalService([])
    llm_service = FakeLLMService(["I do not have enough information."])

    service = RAGService(
        retrieval_service=retrieval_service,
        llm_service=llm_service,
    )

    events = [
        event
        async for event in service.generate(
            query="What is FastAPI?", collection_name="fastapi"
        )
    ]

    assert events[0] == RAGEvent(type="sources", sources=[])

    assert events[1] == RAGEvent(
        type="text",
        text="I do not have enough information.",
    )

    assert llm_service.calls[0]["prompt"] == (
        "Question:\nWhat is FastAPI?\n\nRetrieved context:\n"
    )
