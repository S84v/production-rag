from production_rag.services.embedding import (
    EMBEDDING_ACTION_PERSISTED,
    EMBEDDING_ACTION_REPAIRED,
    EMBEDDING_ACTION_SKIPPED,
    EmbeddingBatch,
    embedding_action,
)


def test_missing_embedding_record_is_persisted() -> None:
    assert (
        embedding_action(record_exists=False, point_exists=False)
        == EMBEDDING_ACTION_PERSISTED
    )


def test_missing_record_ignores_the_point_flag() -> None:
    # A point without a record cannot be authoritative; the record must be
    # created (and the point overwritten by the upsert).
    assert (
        embedding_action(record_exists=False, point_exists=True)
        == EMBEDDING_ACTION_PERSISTED
    )


def test_existing_record_and_point_are_skipped() -> None:
    assert (
        embedding_action(record_exists=True, point_exists=True)
        == EMBEDDING_ACTION_SKIPPED
    )


def test_existing_record_without_point_is_repaired() -> None:
    assert (
        embedding_action(record_exists=True, point_exists=False)
        == EMBEDDING_ACTION_REPAIRED
    )


def test_batch_reports_outcomes_separately_and_is_iterable() -> None:
    first = object()
    second = object()

    batch = EmbeddingBatch(embeddings=[first, second], persisted=1, repaired=1)

    assert len(batch) == 2
    assert list(batch) == [first, second]
    assert (batch.persisted, batch.repaired, batch.skipped) == (1, 1, 0)


def test_empty_batch_is_empty() -> None:
    batch = EmbeddingBatch(embeddings=[])

    assert len(batch) == 0
    assert list(batch) == []
