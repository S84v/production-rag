from production_rag.evaluation.dataset import EvaluationExample
from production_rag.evaluation.retrieval import evaluate_example, summarize


def make_example(relevant_sources: set[str]) -> EvaluationExample:
    return EvaluationExample(
        id="test-001",
        question="test question",
        reference_answer="test answer",
        relevant_sources=frozenset(relevant_sources),
    )


def test_evaluate_example_all_relevant() -> None:
    example = make_example({"body.md"})

    result = evaluate_example(
        example,
        ["body.md", "other.md"],
    )

    assert result.precision == 0.5
    assert result.recall == 1.0
    assert result.reciprocal_rank == 1.0


def rest_evaluate_example_relevant_second() -> None:
    example = make_example({"body.md"})

    result = evaluate_example(
        example,
        ["other.md", "body.md"],
    )

    assert result.precision == 0.5
    assert result.recall == 1.0
    assert result.reciprocal_rank == 0.5


def rest_evaluare_example_no_relevant_result() -> None:
    example = make_example({"body.md"})

    result = evaluate_example(example, ["other.md"])

    assert result.precision == 0.0
    assert result.recall == 0.0
    assert result.reciprocal_rank == 0.0


def test_summarize() -> None:
    example = make_example({"body.md"})

    results = [
        evaluate_example(example, ["body.md"]),
        evaluate_example(example, ["other.md"]),
    ]

    summary = summarize(results)

    assert summary.precision == 0.5
    assert summary.recall == 0.5
    assert summary.mrr == 0.5
