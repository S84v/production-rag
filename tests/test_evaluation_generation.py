from types import SimpleNamespace

import pytest

from production_rag.evaluation.generation import evaluate_example


class FakeRAGService:
    async def generate(self, query, collection_name, limit):
        yield SimpleNamespace(
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
        )

        yield SimpleNamespace(
            type="text",
            text="FastAPI uses path parameters.",
            sources=None,
        )

        yield SimpleNamespace(
            type="text",
            text=" They are declared using curly braces.",
            sources=None,
        )


@pytest.mark.asyncio
async def test_evaluate_example_collects_answer_and_sources():
    example = SimpleNamespace(
        id="fastapi-001",
        question="How do you declare a path parameter in FastAPI?",
        reference_answer="Use curly braces in the path.",
    )

    result = await evaluate_example(
        rag_service=FakeRAGService(),
        example=example,
        collection_name="fastapi",
        limit=5,
    )

    assert result.example_id == "fastapi-001"
    assert result.answer == (
        "FastAPI uses path parameters. They are declared using curly braces."
    )
    assert len(result.sources) == 1
    assert result.sources[0]["chunk_id"] == "chunk-123"
    assert result.sources[0]["chunk_index"] == 8
    assert result.retrieval_time_ms == 0.0
