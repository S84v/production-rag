"""Collection-scoped reconciliation between Qdrant and PostgreSQL.

Vectors and their metadata are stored in two systems: Qdrant holds the vectors
and PostgreSQL is authoritative for which vectors should exist. Over time the
two drift (a failed ingest, a re-ingested document that produced a new version,
embedding-model changes, or vectors left behind by other workflows).

This module classifies Qdrant points against the authoritative set for one
collection and can delete only the provably non-authoritative points. It never
deletes PostgreSQL records and never touches any other Qdrant collection.
"""

from dataclasses import dataclass, replace
from uuid import UUID

from production_rag.db.session import async_session_factory
from production_rag.repositories.retrieval import (
    FOREIGN_COLLECTION,
    INACTIVE_MODEL,
    SUPERSEDED_VERSION,
    RetrievalRepository,
)
from production_rag.services.embedding import EmbeddingService
from production_rag.services.qdrant import QdrantVectorStore


@dataclass(frozen=True)
class DriftReport:
    """Classification of one collection's Qdrant points against PostgreSQL."""

    collection: str
    model_name: str
    model_version: str
    qdrant_points: int
    authoritative_points: int
    unbacked_points: tuple[UUID, ...] = ()
    superseded_points: tuple[UUID, ...] = ()
    inactive_model_points: tuple[UUID, ...] = ()
    foreign_collection_points: tuple[UUID, ...] = ()
    missing_points: tuple[UUID, ...] = ()
    deleted_points: int = 0

    @property
    def deletable_points(self) -> tuple[UUID, ...]:
        """Points proven non-authoritative for this collection."""

        return (
            self.unbacked_points
            + self.superseded_points
            + self.inactive_model_points
            + self.foreign_collection_points
        )

    @property
    def is_consistent(self) -> bool:
        return not self.deletable_points and not self.missing_points

    def summary(self) -> str:
        lines = [
            f"collection: {self.collection}",
            f"active model: {self.model_name} (version {self.model_version})",
            f"qdrant points: {self.qdrant_points}",
            f"authoritative points present in qdrant: {self.authoritative_points}",
            f"unbacked points (no PostgreSQL embedding record): "
            f"{len(self.unbacked_points)}",
            f"superseded-version points: {len(self.superseded_points)}",
            f"inactive-model points: {len(self.inactive_model_points)}",
            f"foreign-collection points: {len(self.foreign_collection_points)}",
            f"missing authoritative vectors: {len(self.missing_points)}",
        ]

        if self.deleted_points:
            lines.append(f"deleted points: {self.deleted_points}")

        if self.missing_points:
            lines.append(
                "note: missing vectors are repaired by re-running ingestion, "
                "never by reconciliation"
            )

        return "\n".join(lines)


async def find_drift(
    collection_name: str,
    *,
    model_name: str | None = None,
    model_version: str | None = None,
    vector_store: QdrantVectorStore | None = None,
) -> DriftReport:
    """Classify a collection's Qdrant points without modifying anything."""

    model_name = model_name or EmbeddingService.MODEL_NAME
    model_version = model_version or EmbeddingService.MODEL_VERSION
    vector_store = vector_store or QdrantVectorStore()

    if not await vector_store.collection_exists(collection_name):
        raise ValueError(f"Qdrant collection does not exist: {collection_name!r}")

    qdrant_ids = await vector_store.scroll_point_ids(collection_name)

    async with async_session_factory() as session:
        repository = RetrievalRepository(session)

        authoritative = await repository.authoritative_embedding_ids(
            collection_name, model_name, model_version
        )
        classification = await repository.classify_embeddings(
            list(qdrant_ids), collection_name, model_name, model_version
        )

    return categorize_points(
        collection_name=collection_name,
        model_name=model_name,
        model_version=model_version,
        qdrant_ids=qdrant_ids,
        classification=classification,
        authoritative=authoritative,
    )


def categorize_points(
    *,
    collection_name: str,
    model_name: str,
    model_version: str,
    qdrant_ids: set[UUID],
    classification: dict[UUID, str],
    authoritative: set[UUID],
) -> DriftReport:
    """Pure classification of Qdrant points against the authoritative set.

    Points absent from ``classification`` have no PostgreSQL embedding record
    (``unbacked``); the remaining categories distinguish why a point is not
    authoritative.
    """

    unbacked: list[UUID] = []
    superseded: list[UUID] = []
    inactive: list[UUID] = []
    foreign: list[UUID] = []
    authoritative_present = 0

    for point_id in sorted(qdrant_ids, key=str):
        category = classification.get(point_id)

        if category is None:
            unbacked.append(point_id)
        elif category == SUPERSEDED_VERSION:
            superseded.append(point_id)
        elif category == INACTIVE_MODEL:
            inactive.append(point_id)
        elif category == FOREIGN_COLLECTION:
            foreign.append(point_id)
        else:
            authoritative_present += 1

    return DriftReport(
        collection=collection_name,
        model_name=model_name,
        model_version=model_version,
        qdrant_points=len(qdrant_ids),
        authoritative_points=authoritative_present,
        unbacked_points=tuple(unbacked),
        superseded_points=tuple(superseded),
        inactive_model_points=tuple(inactive),
        foreign_collection_points=tuple(foreign),
        missing_points=tuple(sorted(authoritative - qdrant_ids, key=str)),
    )


async def reconcile(
    collection_name: str,
    *,
    apply: bool = False,
    model_name: str | None = None,
    model_version: str | None = None,
    vector_store: QdrantVectorStore | None = None,
) -> DriftReport:
    """Report drift, and with ``apply=True`` delete non-authoritative points.

    Deletion is preceded by a fresh revalidation of the authoritative set, so
    only point ids that are proven non-authoritative at deletion time are
    removed. PostgreSQL is never modified and other collections are untouched.
    """

    vector_store = vector_store or QdrantVectorStore()

    report = await find_drift(
        collection_name,
        model_name=model_name,
        model_version=model_version,
        vector_store=vector_store,
    )

    if not apply:
        return report

    # Revalidate immediately before deleting.
    revalidated = await find_drift(
        collection_name,
        model_name=model_name,
        model_version=model_version,
        vector_store=vector_store,
    )

    deletable = revalidated.deletable_points

    if not deletable:
        return revalidated

    deleted = await vector_store.delete_points(collection_name, list(deletable))

    return replace(revalidated, deleted_points=deleted)
