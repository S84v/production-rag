"""Corpus acquisition and preparation utilities.

The package is intentionally small: :mod:`production_rag.corpus.preparation`
owns the deterministic transformation of the pinned upstream documentation into
the plain Markdown that ingestion consumes.
"""

from production_rag.corpus.preparation import (
    PINNED_REVISION,
    PreparationError,
    PreparationReport,
    prepare_corpus,
)

__all__ = [
    "PINNED_REVISION",
    "PreparationError",
    "PreparationReport",
    "prepare_corpus",
]
