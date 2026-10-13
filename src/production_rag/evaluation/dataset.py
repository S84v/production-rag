import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ChunkAnchor:
    """Content-based reference to a chunk that is stable across re-ingestion.

    ``source_uri`` scopes the search to a single document and ``snippet`` is a
    verbatim excerpt that is resolved to the current chunk ID at evaluation
    time, so clean ingestion or re-chunking no longer invalidates labels.
    """

    source_uri: str
    snippet: str


@dataclass(frozen=True)
class EvaluationExample:
    id: str
    question: str
    reference_answer: str
    relevant_chunks: frozenset[ChunkAnchor]


def _parse_anchor(raw: object, example_id: str) -> ChunkAnchor:
    if isinstance(raw, str):
        raise ValueError(
            f"Example {example_id!r} uses the legacy chunk label {raw!r}. "
            "Evaluation labels are now content anchors; migrate it to "
            '{"source_uri": "<filesystem://...>", "snippet": "<verbatim excerpt>"}. '
            "See docs/evaluation/retrieval_baseline.md."
        )

    if not isinstance(raw, dict):
        raise ValueError(
            f"Example {example_id!r} has an invalid chunk anchor {raw!r}: "
            "expected an object with 'source_uri' and 'snippet'."
        )

    source_uri = raw.get("source_uri")
    snippet = raw.get("snippet")

    if not isinstance(source_uri, str) or not source_uri.strip():
        raise ValueError(
            f"Example {example_id!r} anchor is missing a non-empty "
            f"'source_uri': {raw!r}"
        )

    if not isinstance(snippet, str) or not snippet.strip():
        raise ValueError(
            f"Example {example_id!r} anchor is missing a non-empty 'snippet': {raw!r}"
        )

    return ChunkAnchor(source_uri=source_uri, snippet=snippet)


def load_dataset(path: Path) -> list[EvaluationExample]:
    with path.open(encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, list):
        raise ValueError("Evaluation dataset must contain a JSON array")

    for _ in data:
        if not isinstance(_, dict):
            raise ValueError("Each evaluation example must be a JSON object")

    return [
        EvaluationExample(
            id=raw["id"],
            question=raw["question"],
            reference_answer=raw["reference_answer"],
            relevant_chunks=frozenset(
                _parse_anchor(anchor, raw["id"]) for anchor in raw["relevant_chunks"]
            ),
        )
        for raw in data
    ]
