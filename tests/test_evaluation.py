from production_rag.evaluation.dataset import EvaluationExample
from production_rag.evaluation.retrieval import evaluate_example, summarize


def make_example(relevant_chunks: set[str]) -> EvaluationExample:
    return EvaluationExample(
        id="test-001",
        question="test question",
        reference_answer="test answer",
        relevant_chunks=frozenset(relevant_chunks),
    )


def test_evaluate_example_all_relevant() -> None:
    example = make_example({"chunk-1"})

    result = evaluate_example(
        example,
        ["chunk-1", "chunk-2"],
    )

    assert result.precision == 0.5
    assert result.recall == 1.0
    assert result.reciprocal_rank == 1.0
    assert result.hit == 1.0


def test_evaluate_example_relevant_second() -> None:
    example = make_example({"chunk-1"})

    result = evaluate_example(
        example,
        ["chunk-2", "chunk-1"],
    )

    assert result.precision == 0.5
    assert result.recall == 1.0
    assert result.reciprocal_rank == 0.5
    assert result.hit == 1.0


def test_evaluate_example_no_relevant_result() -> None:
    example = make_example({"chunk-1"})

    result = evaluate_example(example, ["chunk-2"])

    assert result.precision == 0.0
    assert result.recall == 0.0
    assert result.reciprocal_rank == 0.0
    assert result.hit == 0.0


def rest_evaluate_example_multiple_relevant_chunks() -> None:
    example = make_example({"chunk-1", "chunk-2", "chunk-3"})
    result = evaluate_example(
        example,
        ["chunk-1", "chunk-2", "chunk-3", "chunk-4", "chunk-5"],
    )

    assert result.precision == 0.6
    assert result.recall == 1.0
    assert result.reciprocal_rank == 1.0
    assert result.hit == 1.0


def test_summarize() -> None:
    example = make_example({"chunk-1"})

    results = [
        evaluate_example(example, ["chunk-1"]),
        evaluate_example(example, ["chunk-2"]),
    ]

    summary = summarize(results)

    assert summary.precision == 0.5
    assert summary.recall == 0.5
    assert summary.mrr == 0.5
    assert summary.hit_rate == 0.5
