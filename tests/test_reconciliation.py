from uuid import UUID, uuid4

import pytest

from production_rag.repositories.retrieval import (
    AUTHORITATIVE,
    FOREIGN_COLLECTION,
    INACTIVE_MODEL,
    SUPERSEDED_VERSION,
)
from production_rag.services.qdrant import QdrantVectorStore
from production_rag.services.reconciliation import (
    DriftReport,
    categorize_points,
    find_drift,
    reconcile,
)
from tests.helpers.qdrant import FakeQdrantClient

MODEL_NAME = "BAAI/bge-small-en-v1.5"
MODEL_VERSION = "1"


def build_report(**overrides) -> DriftReport:
    defaults = {
        "collection": "fastapi",
        "model_name": MODEL_NAME,
        "model_version": MODEL_VERSION,
        "qdrant_points": 0,
        "authoritative_points": 0,
    }
    defaults.update(overrides)
    return DriftReport(**defaults)


def test_categorize_points_separates_every_drift_state() -> None:
    authoritative_point = uuid4()
    unbacked = uuid4()
    superseded = uuid4()
    inactive = uuid4()
    foreign = uuid4()
    missing = uuid4()

    report = categorize_points(
        collection_name="fastapi",
        model_name=MODEL_NAME,
        model_version=MODEL_VERSION,
        qdrant_ids={authoritative_point, unbacked, superseded, inactive, foreign},
        classification={
            authoritative_point: AUTHORITATIVE,
            superseded: SUPERSEDED_VERSION,
            inactive: INACTIVE_MODEL,
            foreign: FOREIGN_COLLECTION,
        },
        authoritative={authoritative_point, missing},
    )

    assert report.qdrant_points == 5
    assert report.authoritative_points == 1
    assert report.unbacked_points == (unbacked,)
    assert report.superseded_points == (superseded,)
    assert report.inactive_model_points == (inactive,)
    assert report.foreign_collection_points == (foreign,)
    assert report.missing_points == (missing,)
    assert not report.is_consistent


def test_deletable_points_excludes_authoritative_and_missing() -> None:
    authoritative_point = uuid4()
    unbacked = uuid4()

    report = categorize_points(
        collection_name="fastapi",
        model_name=MODEL_NAME,
        model_version=MODEL_VERSION,
        qdrant_ids={authoritative_point, unbacked},
        classification={authoritative_point: AUTHORITATIVE},
        authoritative={authoritative_point},
    )

    assert report.deletable_points == (unbacked,)


def test_report_is_consistent_when_only_authoritative_points_remain() -> None:
    point = uuid4()

    report = categorize_points(
        collection_name="fastapi",
        model_name=MODEL_NAME,
        model_version=MODEL_VERSION,
        qdrant_ids={point},
        classification={point: AUTHORITATIVE},
        authoritative={point},
    )

    assert report.is_consistent
    assert report.deletable_points == ()


@pytest.mark.asyncio
async def test_find_drift_rejects_unknown_collection() -> None:
    store = QdrantVectorStore(client=FakeQdrantClient())

    with pytest.raises(ValueError, match="does not exist"):
        await find_drift("fastapi", vector_store=store)


@pytest.mark.asyncio
async def test_reconcile_dry_run_never_deletes(monkeypatch) -> None:
    unbacked = uuid4()
    client = FakeQdrantClient(collections=["fastapi"])
    client.seed_point("fastapi", unbacked)
    store = QdrantVectorStore(client=client)

    async def fake_find_drift(collection_name, **kwargs):
        return build_report(
            collection=collection_name,
            qdrant_points=1,
            unbacked_points=(unbacked,),
        )

    monkeypatch.setattr(
        "production_rag.services.reconciliation.find_drift", fake_find_drift
    )

    report = await reconcile("fastapi", apply=False, vector_store=store)

    assert client.deleted_points == []
    assert report.deleted_points == 0
    assert report.deletable_points == (unbacked,)
    assert client.points["fastapi"], "dry run must not remove the point"


@pytest.mark.asyncio
async def test_reconcile_apply_deletes_only_non_authoritative_points(
    monkeypatch,
) -> None:
    unbacked = uuid4()
    superseded = uuid4()
    authoritative_point = uuid4()

    client = FakeQdrantClient(collections=["fastapi"])
    for point_id in (unbacked, superseded, authoritative_point):
        client.seed_point("fastapi", point_id)

    store = QdrantVectorStore(client=client)
    calls = {"count": 0}

    async def fake_find_drift(collection_name, **kwargs):
        calls["count"] += 1
        return build_report(
            collection=collection_name,
            qdrant_points=3,
            authoritative_points=1,
            unbacked_points=(unbacked,),
            superseded_points=(superseded,),
        )

    monkeypatch.setattr(
        "production_rag.services.reconciliation.find_drift", fake_find_drift
    )

    report = await reconcile("fastapi", apply=True, vector_store=store)

    # The authoritative set is revalidated before deleting.
    assert calls["count"] == 2

    deleted_collections = {name for name, _ in client.deleted_points}
    deleted_ids = {point_id for _, ids in client.deleted_points for point_id in ids}

    assert deleted_collections == {"fastapi"}
    assert deleted_ids == {str(unbacked), str(superseded)}
    assert str(authoritative_point) not in deleted_ids
    assert report.deleted_points == 2
    remaining = {UUID(point_id) for point_id in client.points["fastapi"]}
    assert remaining == {authoritative_point}


@pytest.mark.asyncio
async def test_reconcile_apply_is_a_no_op_when_consistent(monkeypatch) -> None:
    client = FakeQdrantClient(collections=["fastapi"])
    store = QdrantVectorStore(client=client)

    async def fake_find_drift(collection_name, **kwargs):
        return build_report(collection=collection_name)

    monkeypatch.setattr(
        "production_rag.services.reconciliation.find_drift", fake_find_drift
    )

    report = await reconcile("fastapi", apply=True, vector_store=store)

    assert client.deleted_points == []
    assert report.deleted_points == 0
    assert report.is_consistent
