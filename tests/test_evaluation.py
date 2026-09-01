from production_rag.evaluation.dataset import EvaluationExample
from production_rag.evaluation.retrieval import (
    RetrievedChunk,
    evaluate_example,
    summarize,
)


def make_example(relevant_chunks: set[str]) -> EvaluationExample:
    return EvaluationExample(
        id="test-001",
        question="test question",
        reference_answer="test answer",
        relevant_chunks=frozenset(relevant_chunks),
    )


def make_retrieved_chunks(*chunk_ids: str) -> list[RetrievedChunk]:
    return [
        RetrievedChunk(
            source="test",
            chunk_index=index,
            chunk_id=chunk_id,
            score=1.0 - (index * 0.1),
        )
        for index, chunk_id in enumerate(chunk_ids)
    ]


def test_evaluate_example_all_relevant() -> None:
    example = make_example({"chunk-1"})

    result = evaluate_example(
        example,
        make_retrieved_chunks("chunk-1", "chunk-2"),
    )

    assert result.example_id == "test-001"
    assert result.retrieved_chunks[0].chunk_id == "chunk-1"
    assert result.retrieved_chunks[1].chunk_id == "chunk-2"
    assert result.relevant_chunks == frozenset({"chunk-1"})
    assert result.precision == 0.5
    assert result.recall == 1.0
    assert result.reciprocal_rank == 1.0
    assert result.hit == 1.0


def test_evaluate_example_relevant_second() -> None:
    example = make_example({"chunk-1"})

    result = evaluate_example(
        example,
        make_retrieved_chunks("chunk-2", "chunk-1"),
    )

    assert result.precision == 0.5
    assert result.recall == 1.0
    assert result.reciprocal_rank == 0.5
    assert result.hit == 1.0


def test_evaluate_example_no_relevant_result() -> None:
    example = make_example({"chunk-1"})

    result = evaluate_example(
        example,
        make_retrieved_chunks("chunk-2"),
    )

    assert result.precision == 0.0
    assert result.recall == 0.0
    assert result.reciprocal_rank == 0.0
    assert result.hit == 0.0


def test_evaluate_example_empty_results() -> None:
    example = make_example({"chunk-1"})

    result = evaluate_example(
        example,
        [],
    )

    assert result.retrieved_chunks == ()
    assert result.precision == 0.0
    assert result.recall == 0.0
    assert result.reciprocal_rank == 0.0
    assert result.hit == 0.0


def test_summarize() -> None:
    example = make_example({"chunk-1"})

    results = [
        evaluate_example(
            example,
            make_retrieved_chunks("chunk-1"),
        ),
        evaluate_example(
            example,
            make_retrieved_chunks("chunk-2"),
        ),
    ]

    summary = summarize(results)

    assert len(summary.results) == 2
    assert summary.precision == 0.5
    assert summary.recall == 0.5
    assert summary.mrr == 0.5
    assert summary.hit_rate == 0.5


def test_summarize_empty_results() -> None:
    try:
        summarize([])
    except ValueError as exc:
        assert str(exc) == "Cannot summarize an empty evaluation"
    else:
        raise AssertionError("Expected ValueError")
