from types import SimpleNamespace

import pytest

from production_rag.services.llm import GenerationError
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


class FakeFailingLLMService:
    def __init__(self, chunks: list[str], error: GenerationError) -> None:
        self.chunks = chunks
        self.error = error

    async def generate(self, **kwargs):
        for chunk in self.chunks:
            yield chunk

        raise self.error


@pytest.mark.asyncio
async def test_rag_service_retrieves_context_and_streams_answer():
    retrieval_service = FakeRetrievalService(
        [
            SimpleNamespace(
                chunk=SimpleNamespace(
                    id="00000000-0000-0000-0000-000000000001",
                    content="FastAPI is a Python web framework.",
                    chunk_index=0,
                ),
                source="fastapi",
                source_uri="docs/index.md",
                score=0.95,
            ),
            SimpleNamespace(
                chunk=SimpleNamespace(
                    id="00000000-0000-0000-0000-000000000002",
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

    assert events[0].type == "sources"
    assert events[0].sources == [
        RAGSource(
            source="fastapi",
            source_uri="docs/index.md",
            chunk_id="00000000-0000-0000-0000-000000000001",
            chunk_index=0,
            score=0.95,
            content="FastAPI is a Python web framework.",
        ),
        RAGSource(
            source="fastapi",
            source_uri="docs/features.md",
            chunk_id="00000000-0000-0000-0000-000000000002",
            chunk_index=1,
            score=0.90,
            content="FastAPI uses standard Python type hints.",
        ),
    ]
    assert events[0].retrieval_time_ms is not None
    assert events[0].retrieval_time_ms >= 0

    assert events[-1] == RAGEvent(
        type="complete",
        retrieval_time_ms=events[-1].retrieval_time_ms,
        total_time_ms=events[-1].total_time_ms,
    )

    assert events[-1].total_time_ms is not None
    assert events[-1].total_time_ms >= 0

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

    assert events[0].type == "sources"
    assert events[0].sources == []
    assert events[0].retrieval_time_ms is not None
    assert events[0].retrieval_time_ms >= 0

    assert events[-1].type == "complete"
    assert events[-1].total_time_ms is not None
    assert events[-1].total_time_ms >= 0

    assert events[1] == RAGEvent(
        type="text",
        text="I do not have enough information.",
    )

    assert llm_service.calls[0]["prompt"] == (
        "Question:\nWhat is FastAPI?\n\nRetrieved context:\n"
    )


@pytest.mark.asyncio
async def test_rag_service_emits_error_event_and_no_completion():
    retrieval_service = FakeRetrievalService(
        [
            SimpleNamespace(
                chunk=SimpleNamespace(
                    id="00000000-0000-0000-0000-000000000001",
                    content="FastAPI is a Python web framework.",
                    chunk_index=0,
                ),
                source="fastapi",
                source_uri="docs/index.md",
                score=0.95,
            )
        ]
    )

    llm_service = FakeFailingLLMService(
        ["partial"],
        GenerationError(
            code="generation_failed",
            message="The answer could not be generated. Please try again.",
        ),
    )

    service = RAGService(retrieval_service=retrieval_service, llm_service=llm_service)

    events = [
        event
        async for event in service.generate(
            query="What is FastAPI?", collection_name="fastapi", limit=1
        )
    ]

    assert events[0].type == "sources"
    assert [event.text for event in events if event.type == "text"] == ["partial"]

    assert events[-1].type == "error"
    assert events[-1].error_code == "generation_failed"
    assert (
        events[-1].error_message
        == "The answer could not be generated. Please try again."
    )

    # A failed generation must never look like a successful completion.
    assert all(event.type != "complete" for event in events)


def make_retrieved_result(
    *,
    chunk_id: str,
    content: str,
    chunk_index: int,
    source_uri: str,
    score: float = 0.9,
):
    return SimpleNamespace(
        chunk=SimpleNamespace(
            id=chunk_id,
            content=content,
            chunk_index=chunk_index,
        ),
        source="fastapi",
        source_uri=source_uri,
        score=score,
    )


@pytest.mark.asyncio
async def test_rag_service_bounds_context_and_aligns_sources():
    retrieval_service = FakeRetrievalService(
        [
            make_retrieved_result(
                chunk_id="c1", content="alpha", chunk_index=0, source_uri="a.md"
            ),
            make_retrieved_result(
                chunk_id="c2", content="beta", chunk_index=1, source_uri="b.md"
            ),
            make_retrieved_result(
                chunk_id="c3", content="gamma", chunk_index=2, source_uri="c.md"
            ),
        ]
    )
    llm_service = FakeLLMService(["ok"])

    service = RAGService(
        retrieval_service=retrieval_service,
        llm_service=llm_service,
        max_context_characters=9,
    )

    events = [
        event async for event in service.generate(query="q", collection_name="fastapi")
    ]

    # "alpha" (5) + "beta" (4) == 9; "gamma" would exceed the budget and is
    # excluded from both the sources event and the prompt.
    assert [source.source_uri for source in events[0].sources] == ["a.md", "b.md"]

    assert llm_service.calls[0]["prompt"] == (
        "Question:\nq\n\nRetrieved context:\n[Source 1]\nalpha\n\n[Source 2]\nbeta"
    )


@pytest.mark.asyncio
async def test_rag_service_context_budget_boundary_is_strict():
    results = [
        make_retrieved_result(
            chunk_id="c1", content="alpha", chunk_index=0, source_uri="a.md"
        ),
        make_retrieved_result(
            chunk_id="c2", content="beta", chunk_index=1, source_uri="b.md"
        ),
    ]

    # Exactly the combined size of both chunks includes both.
    service = RAGService(
        retrieval_service=FakeRetrievalService(results),
        llm_service=FakeLLMService(["ok"]),
        max_context_characters=9,
    )
    events = [
        event async for event in service.generate(query="q", collection_name="fastapi")
    ]
    assert [source.source_uri for source in events[0].sources] == ["a.md", "b.md"]

    # One character short includes only the first whole chunk.
    service = RAGService(
        retrieval_service=FakeRetrievalService(results),
        llm_service=FakeLLMService(["ok"]),
        max_context_characters=8,
    )
    events = [
        event async for event in service.generate(query="q", collection_name="fastapi")
    ]
    assert [source.source_uri for source in events[0].sources] == ["a.md"]


@pytest.mark.asyncio
async def test_rag_service_context_selection_preserves_rank_and_stops():
    retrieval_service = FakeRetrievalService(
        [
            make_retrieved_result(
                chunk_id="c1", content="a" * 5, chunk_index=0, source_uri="a.md"
            ),
            make_retrieved_result(
                chunk_id="c2", content="b" * 100, chunk_index=1, source_uri="b.md"
            ),
            make_retrieved_result(
                chunk_id="c3", content="c" * 5, chunk_index=2, source_uri="c.md"
            ),
        ]
    )
    llm_service = FakeLLMService(["ok"])

    service = RAGService(
        retrieval_service=retrieval_service,
        llm_service=llm_service,
        max_context_characters=20,
    )

    events = [
        event async for event in service.generate(query="q", collection_name="fastapi")
    ]

    # The second chunk does not fit, so selection stops; the smaller third
    # chunk is never pulled forward (rank order is preserved).
    assert [source.source_uri for source in events[0].sources] == ["a.md"]

    prompt = llm_service.calls[0]["prompt"]
    assert ("b" * 100) not in prompt
    assert ("c" * 5) not in prompt
