from collections.abc import Iterable
from dataclasses import dataclass

from production_rag.evaluation.dataset import ChunkAnchor, EvaluationExample


@dataclass(frozen=True)
class ChunkRecord:
    """A current chunk as seen by the evaluator (independent of the DB layer)."""

    chunk_id: str
    source_uri: str
    content: str


def normalize_whitespace(text: str) -> str:
    """Collapse all whitespace runs so anchors are insensitive to formatting."""

    return " ".join(text.split())


class AnchorResolutionError(ValueError):
    """An anchor did not resolve to exactly one current chunk.

    Raised instead of dropping a label or picking an arbitrary match, so an
    invalid dataset fails loudly rather than reporting misleading metrics.
    """

    def __init__(
        self,
        message: str,
        *,
        example_id: str | None,
        anchor: ChunkAnchor,
        candidates: Iterable[str] = (),
    ) -> None:
        prefix = f"Example {example_id!r}: " if example_id is not None else ""
        super().__init__(prefix + message)
        self.example_id = example_id
        self.anchor = anchor
        self.candidates = tuple(candidates)


def resolve_anchors(
    anchors: Iterable[ChunkAnchor],
    chunks: Iterable[ChunkRecord],
    *,
    example_id: str | None = None,
) -> dict[ChunkAnchor, str]:
    """Resolve content anchors to the IDs of the chunks that currently contain them.

    Matching is scoped to ``source_uri`` and compared on whitespace-normalized
    text. An anchor that matches no chunk, or more than one chunk, raises
    :class:`AnchorResolutionError` identifying the example and the anchor.
    """

    index: dict[str, list[tuple[str, str]]] = {}

    for chunk in chunks:
        index.setdefault(chunk.source_uri, []).append(
            (chunk.chunk_id, normalize_whitespace(chunk.content))
        )

    resolved: dict[ChunkAnchor, str] = {}

    for anchor in anchors:
        snippet = normalize_whitespace(anchor.snippet)

        if not snippet:
            raise AnchorResolutionError(
                "anchor snippet is empty after whitespace normalization",
                example_id=example_id,
                anchor=anchor,
            )

        candidates = [
            chunk_id
            for chunk_id, content in index.get(anchor.source_uri, [])
            if snippet in content
        ]

        if not candidates:
            raise AnchorResolutionError(
                f"no chunk in {anchor.source_uri!r} contains the snippet "
                f"{anchor.snippet!r}",
                example_id=example_id,
                anchor=anchor,
            )

        if len(candidates) > 1:
            raise AnchorResolutionError(
                f"snippet {anchor.snippet!r} matches {len(candidates)} chunks in "
                f"{anchor.source_uri!r}: {candidates}",
                example_id=example_id,
                anchor=anchor,
                candidates=candidates,
            )

        resolved[anchor] = candidates[0]

    return resolved


def resolve_example_relevant_chunk_ids(
    example: EvaluationExample,
    chunks: Iterable[ChunkRecord],
) -> frozenset[str]:
    """Resolve one example's anchors to the current chunk IDs that are relevant."""

    resolved = resolve_anchors(
        example.relevant_chunks,
        chunks,
        example_id=example.id,
    )

    return frozenset(resolved.values())
