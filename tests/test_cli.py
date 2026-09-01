from pathlib import Path

import pytest

from production_rag import build_parser
from production_rag.services.rag import RAGEvent, RAGSource


class FakeRAGService:
    async def generate(
        self,
        query: str,
        collection_name: str,
        limit: int = 5,
    ):
        assert query == "What is FastAPI?"
        assert collection_name == "fastapi"
        assert limit == 5

        yield RAGEvent(
            type="sources",
            sources=[
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
                    source_uri="docs/tutorial/first-steps.md",
                    chunk_id="00000000-0000-0000-0000-000000000002",
                    chunk_index=2,
                    score=0.91,
                    content="This is the FastAPI first steps tutorial.",
                ),
            ],
        )

        yield RAGEvent(type="text", text="FastAPI ")
        yield RAGEvent(type="text", text="is a web framework.")


@pytest.mark.asyncio
async def test_query_rag_prints_stream_and_sources(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from production_rag import query_rag

    monkeypatch.setattr(
        "production_rag.RAGService",
        lambda: FakeRAGService(),
    )

    await query_rag(
        query="What is FastAPI?",
        collection_name="fastapi",
        limit=5,
    )

    output = capsys.readouterr().out

    assert output == (
        "> What is FastAPI?\n"
        "\n"
        "FastAPI is a web framework.\n\n"
        "Sources:\n"
        "- docs/index.md (chunk 0, similarity: 0.950)\n"
        "- docs/tutorial/first-steps.md (chunk 2, similarity: 0.910)\n"
    )


def test_ingest_command_parses_arguments():
    parser = build_parser()

    args = parser.parse_args(
        [
            "ingest",
            "--path",
            "data/raw/fastapi",
            "--collection",
            "fastapi",
        ]
    )

    assert args.command == "ingest"
    assert args.path == Path("data/raw/fastapi")
    assert args.collection == "fastapi"


def test_query_command_parses_arguments():
    parser = build_parser()

    args = parser.parse_args(
        [
            "query",
            "What is FastAPI?",
            "--collection",
            "fastapi",
            "--limit",
            "3",
        ]
    )

    assert args.command == "query"
    assert args.query == "What is FastAPI?"
    assert args.collection == "fastapi"
    assert args.limit == 3


def test_query_command_uses_default_limit():
    parser = build_parser()

    args = parser.parse_args(
        [
            "query",
            "What is FastAPI?",
            "--collection",
            "fastapi",
        ]
    )

    assert args.limit == 5
