from pathlib import Path

import pytest

from production_rag.evaluation.anchors import (
    AnchorResolutionError,
    ChunkRecord,
    normalize_whitespace,
    resolve_anchors,
    resolve_example_relevant_chunk_ids,
)
from production_rag.evaluation.dataset import (
    ChunkAnchor,
    EvaluationExample,
    load_dataset,
)
from production_rag.ingestion.chunker import MarkdownChunker

DATASET_PATH = Path("data/evaluation/fastapi.json")
CORPUS_DIR = Path("data/raw/fastapi")


def make_records(*rows: tuple[str, str, str]) -> list[ChunkRecord]:
    return [
        ChunkRecord(chunk_id=chunk_id, source_uri=source_uri, content=content)
        for chunk_id, source_uri, content in rows
    ]


def test_normalize_whitespace_collapses_runs() -> None:
    assert normalize_whitespace("a\n\n  b\tc ") == "a b c"


def test_resolve_anchors_unique_match() -> None:
    anchor = ChunkAnchor(
        source_uri="filesystem://a.md", snippet="declare a path parameter"
    )
    records = make_records(
        (
            "id-1",
            "filesystem://a.md",
            "You declare a path parameter with curly braces.",
        ),
        ("id-2", "filesystem://a.md", "Something unrelated."),
    )

    resolved = resolve_anchors([anchor], records, example_id="fastapi-001")

    assert resolved == {anchor: "id-1"}


def test_resolve_anchors_normalizes_whitespace() -> None:
    anchor = ChunkAnchor(
        source_uri="filesystem://a.md", snippet="body as JSON and validates"
    )
    records = make_records(
        (
            "id-1",
            "filesystem://a.md",
            "FastAPI reads the\nbody as   JSON and validates it.",
        ),
    )

    resolved = resolve_anchors([anchor], records, example_id="fastapi-001")

    assert resolved[anchor] == "id-1"


def test_resolve_anchors_missing_raises_with_example_and_anchor() -> None:
    anchor = ChunkAnchor(source_uri="filesystem://a.md", snippet="not present anywhere")
    records = make_records(("id-1", "filesystem://a.md", "Some other content."))

    with pytest.raises(AnchorResolutionError) as excinfo:
        resolve_anchors([anchor], records, example_id="fastapi-007")

    error = excinfo.value
    assert error.example_id == "fastapi-007"
    assert error.anchor == anchor
    assert error.candidates == ()
    message = str(error)
    assert "fastapi-007" in message
    assert "filesystem://a.md" in message
    assert "not present anywhere" in message


def test_resolve_anchors_ambiguous_raises_with_candidates() -> None:
    anchor = ChunkAnchor(source_uri="filesystem://a.md", snippet="repeated sentence")
    records = make_records(
        ("id-1", "filesystem://a.md", "A repeated sentence appears here."),
        ("id-2", "filesystem://a.md", "And a repeated sentence appears here too."),
    )

    with pytest.raises(AnchorResolutionError) as excinfo:
        resolve_anchors([anchor], records, example_id="fastapi-002")

    error = excinfo.value
    assert error.example_id == "fastapi-002"
    assert set(error.candidates) == {"id-1", "id-2"}
    assert "matches 2 chunks" in str(error)


def test_resolve_anchors_wrong_source_uri_is_missing() -> None:
    anchor = ChunkAnchor(
        source_uri="filesystem://b.md", snippet="declare a path parameter"
    )
    records = make_records(
        ("id-1", "filesystem://a.md", "You declare a path parameter here."),
    )

    with pytest.raises(AnchorResolutionError):
        resolve_anchors([anchor], records, example_id="fastapi-003")


def test_resolve_anchors_empty_snippet_raises() -> None:
    anchor = ChunkAnchor(source_uri="filesystem://a.md", snippet="   ")
    records = make_records(("id-1", "filesystem://a.md", "content"))

    with pytest.raises(AnchorResolutionError):
        resolve_anchors([anchor], records, example_id="fastapi-004")


def test_resolve_example_relevant_chunk_ids() -> None:
    example = EvaluationExample(
        id="fastapi-001",
        question="q",
        reference_answer="a",
        relevant_chunks=frozenset(
            {
                ChunkAnchor(source_uri="filesystem://a.md", snippet="alpha"),
                ChunkAnchor(source_uri="filesystem://a.md", snippet="beta"),
            }
        ),
    )
    records = make_records(
        ("id-1", "filesystem://a.md", "alpha content"),
        ("id-2", "filesystem://a.md", "beta content"),
    )

    resolved = resolve_example_relevant_chunk_ids(example, records)

    assert resolved == frozenset({"id-1", "id-2"})


def test_dataset_anchors_resolve_against_local_corpus() -> None:
    files = sorted(CORPUS_DIR.rglob("*.md"))
    assert files, "local FastAPI corpus is required for this test"

    chunker = MarkdownChunker()
    records: list[ChunkRecord] = []

    for path in files:
        source_uri = f"filesystem://{path.relative_to(CORPUS_DIR).as_posix()}"
        for index, chunk in enumerate(chunker.chunk(path.read_text(encoding="utf-8"))):
            records.append(
                ChunkRecord(
                    chunk_id=f"{source_uri}#{index}",
                    source_uri=source_uri,
                    content=chunk.content,
                )
            )

    examples = load_dataset(DATASET_PATH)

    # Every anchor must resolve to exactly one current chunk. Missing or
    # ambiguous anchors fail loudly rather than silently skewing metrics.
    for example in examples:
        resolve_example_relevant_chunk_ids(example, records)
