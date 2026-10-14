from types import SimpleNamespace

import pytest

from production_rag.evaluation import (
    TERMINAL_EVENT_MISSING_CODE,
    TERMINAL_EVENT_MISSING_MESSAGE,
)
from production_rag.evaluation.generation import (
    GenerationResult,
    evaluate_example,
    write_markdown,
)


class FakeRAGService:
    def __init__(self, events):
        self.events = events

    async def generate(self, query, collection_name, limit):
        for event in self.events:
            yield event


def make_example():
    return SimpleNamespace(
        id="fastapi-001",
        question="How do you declare a path parameter in FastAPI?",
        reference_answer="Use curly braces in the path.",
    )


def make_sources_event(retrieval_time_ms=0.0):
    return SimpleNamespace(
        type="sources",
        text=None,
        sources=[
            SimpleNamespace(
                source="body.md",
                source_uri="filesystem://body.md",
                chunk_index=8,
                chunk_id="chunk-123",
                score=0.91,
            )
        ],
        retrieval_time_ms=retrieval_time_ms,
    )


def make_text_event(text):
    return SimpleNamespace(type="text", text=text, sources=None)


def make_complete_event(total_time_ms=0.0):
    return SimpleNamespace(
        type="complete",
        text=None,
        sources=None,
        total_time_ms=total_time_ms,
    )


def make_error_event(code, message):
    return SimpleNamespace(
        type="error",
        text=None,
        sources=None,
        error_code=code,
        error_message=message,
    )


@pytest.mark.asyncio
async def test_evaluate_example_collects_answer_sources_and_timing():
    rag_service = FakeRAGService(
        [
            make_sources_event(retrieval_time_ms=12.5),
            make_text_event("FastAPI uses path parameters."),
            make_text_event(" They are declared using curly braces."),
            make_complete_event(total_time_ms=345.6),
        ]
    )

    result = await evaluate_example(
        rag_service=rag_service,
        example=make_example(),
        collection_name="fastapi",
        limit=5,
    )

    assert result.failed is False
    assert result.error_code is None
    assert result.answer == (
        "FastAPI uses path parameters. They are declared using curly braces."
    )
    assert len(result.sources) == 1
    assert result.sources[0]["chunk_id"] == "chunk-123"
    assert result.sources[0]["chunk_index"] == 8
    assert result.retrieval_time_ms == 12.5
    assert result.total_time_ms == 345.6


@pytest.mark.asyncio
async def test_evaluate_example_records_terminal_error():
    rag_service = FakeRAGService(
        [
            make_sources_event(retrieval_time_ms=10.0),
            make_text_event("Partial answer"),
            make_error_event(
                "generation_incomplete",
                "The answer was incomplete. Please try again.",
            ),
        ]
    )

    result = await evaluate_example(
        rag_service=rag_service,
        example=make_example(),
        collection_name="fastapi",
        limit=5,
    )

    assert result.failed is True
    assert result.error_code == "generation_incomplete"
    assert result.error_message == "The answer was incomplete. Please try again."
    # No completion event means no total timing; a failed example must never
    # report a successful-looking total.
    assert result.total_time_ms is None
    # The partial text is retained for diagnostics only, never as a result.
    assert result.answer == "Partial answer"


@pytest.mark.asyncio
async def test_evaluate_example_records_missing_terminal_event():
    rag_service = FakeRAGService(
        [
            make_sources_event(retrieval_time_ms=10.0),
            make_text_event("Partial answer"),
        ]
    )

    result = await evaluate_example(
        rag_service=rag_service,
        example=make_example(),
        collection_name="fastapi",
        limit=5,
    )

    assert result.failed is True
    assert result.error_code == TERMINAL_EVENT_MISSING_CODE
    assert result.error_message == TERMINAL_EVENT_MISSING_MESSAGE
    assert result.total_time_ms is None


def make_result(
    *,
    example_id,
    answer,
    retrieval_time_ms,
    total_time_ms,
    error_code=None,
    error_message=None,
):
    return GenerationResult(
        example_id=example_id,
        question="Question",
        reference_answer="Reference",
        answer=answer,
        sources=(),
        retrieval_time_ms=retrieval_time_ms,
        total_time_ms=total_time_ms,
        error_code=error_code,
        error_message=error_message,
    )


def test_write_markdown_marks_failed_examples(tmp_path):
    success = make_result(
        example_id="ok-001",
        answer="Good answer.",
        retrieval_time_ms=5.0,
        total_time_ms=42.0,
    )
    failed = make_result(
        example_id="bad-001",
        answer="Partial answer",
        retrieval_time_ms=5.0,
        total_time_ms=None,
        error_code="generation_failed",
        error_message="The answer could not be generated. Please try again.",
    )

    path = tmp_path / "generation_results.md"
    write_markdown([success, failed], path)
    text = path.read_text(encoding="utf-8")

    assert "Examples: 2" in text
    assert "Failed: 1" in text
    assert "**Total RAG time:** 42.00 ms" in text

    failed_section = text.split("## bad-001")[1]
    assert "**Generation failed:** `generation_failed`" in failed_section
    assert "The answer could not be generated. Please try again." in failed_section
    # A failed generation must not be presented as a successful result.
    assert "Partial answer" not in failed_section
    assert "**Generated answer:**" not in failed_section
    assert "**Total RAG time:**" not in failed_section
    assert "**Retrieved chunks:**" not in failed_section
