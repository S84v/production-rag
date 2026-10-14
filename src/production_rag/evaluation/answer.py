import argparse
import asyncio
from dataclasses import dataclass
from pathlib import Path

from deepeval import evaluate as deepeval_evaluate
from deepeval.metrics import (
    AnswerRelevancyMetric,
    ContextualPrecisionMetric,
    ContextualRecallMetric,
    FaithfulnessMetric,
)
from deepeval.models import DeepSeekModel
from deepeval.test_case import LLMTestCase

from production_rag.core.settings import get_settings
from production_rag.evaluation import (
    TERMINAL_EVENT_MISSING_CODE,
    TERMINAL_EVENT_MISSING_MESSAGE,
)
from production_rag.evaluation.dataset import EvaluationExample, load_dataset
from production_rag.services.rag import RAGService, RAGSource


@dataclass(frozen=True)
class AnswerEvaluationResult:
    example_id: str
    question: str
    reference_answer: str
    generated_answer: str
    retrieved_sources: tuple[RAGSource, ...]
    error_code: str | None = None
    error_message: str | None = None

    @property
    def failed(self) -> bool:
        """Whether generation ended in a terminal error instead of completion."""
        return self.error_code is not None


async def evaluate_example(
    example: EvaluationExample,
    rag_service: RAGService,
    collection_name: str,
    limit: int,
) -> AnswerEvaluationResult:
    answer_parts: list[str] = []
    retrieved_sources: list[RAGSource] = []
    error_code: str | None = None
    error_message: str | None = None
    terminal = False

    async for event in rag_service.generate(
        query=example.question,
        collection_name=collection_name,
        limit=limit,
    ):
        if event.type == "sources" and event.sources is not None:
            retrieved_sources = event.sources

        elif event.type == "complete":
            terminal = True

        elif event.type == "error":
            error_code = event.error_code or TERMINAL_EVENT_MISSING_CODE
            error_message = event.error_message
            terminal = True

        elif event.type == "text" and event.text is not None:
            answer_parts.append(event.text)

    if not terminal:
        # The RAG contract guarantees exactly one terminal event, so a stream
        # that ends without one was interrupted and must not be treated as a
        # partial success.
        error_code = TERMINAL_EVENT_MISSING_CODE
        error_message = TERMINAL_EVENT_MISSING_MESSAGE

    return AnswerEvaluationResult(
        example_id=example.id,
        question=example.question,
        reference_answer=example.reference_answer,
        generated_answer="".join(answer_parts),
        retrieved_sources=tuple(retrieved_sources),
        error_code=error_code,
        error_message=error_message,
    )


async def collect_results(
    examples: list[EvaluationExample],
    collection_name: str,
    limit: int,
) -> list[AnswerEvaluationResult]:
    rag_service = RAGService()

    results: list[AnswerEvaluationResult] = []

    for example in examples:
        result = await evaluate_example(
            example=example,
            rag_service=rag_service,
            collection_name=collection_name,
            limit=limit,
        )

        results.append(result)

    return results


def build_test_cases(
    results: list[AnswerEvaluationResult],
) -> list[LLMTestCase]:
    """Build DeepEval cases, excluding examples whose generation failed.

    A failed or incomplete generation produces a partial or empty answer, which
    must never be scored as if it were a valid response.
    """

    return [
        LLMTestCase(
            input=result.question,
            actual_output=result.generated_answer,
            expected_output=result.reference_answer,
            retrieval_context=[
                source.content for source in result.retrieved_sources if source.content
            ],
        )
        for result in results
        if not result.failed
    ]


def build_metrics() -> list:
    settings = get_settings()

    judge_model = DeepSeekModel(
        model="deepseek-chat",
        api_key=settings.deepseek_api_key,
        temperature=0,
    )

    return [
        ContextualRecallMetric(
            model=judge_model,
            threshold=0.7,
            include_reason=True,
        ),
        ContextualPrecisionMetric(
            model=judge_model,
            threshold=0.7,
            include_reason=True,
        ),
        AnswerRelevancyMetric(
            model=judge_model,
            threshold=0.7,
            include_reason=True,
        ),
        FaithfulnessMetric(
            model=judge_model,
            threshold=0.7,
            include_reason=True,
        ),
    ]


def print_input_summary(results: list[AnswerEvaluationResult]) -> None:
    failed_count = sum(1 for result in results if result.failed)

    print("Answer Evaluation")
    print("=" * 17)
    print(f"Examples: {len(results)}")
    print(f"Failed: {failed_count}")
    print()


def print_results(results: list[AnswerEvaluationResult]) -> None:
    for result in results:
        print(result.example_id)
        print("-" * len(result.example_id))
        print(f"Question: {result.question}")
        print(f"Reference: {result.reference_answer}")

        if result.failed:
            print(f"Status: generation failed ({result.error_code})")
            if result.error_message:
                print(f"Error: {result.error_message}")
            print()
            continue

        print(f"Generated: {result.generated_answer}")
        print("Retrieved:")

        for rank, source in enumerate(result.retrieved_sources, start=1):
            print(
                f"  {rank}. "
                f"{source.source_uri} | "
                f"chunk={source.chunk_index} | "
                f"uuid={source.chunk_id}"
            )

        print()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run RAG answer-generation evaluation."
    )

    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("data/evaluation/fastapi.json"),
    )

    parser.add_argument(
        "--collection",
        default="fastapi",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=5,
    )

    return parser.parse_args()


async def main() -> None:
    args = parse_args()

    examples = load_dataset(args.dataset)

    results = await collect_results(
        examples=examples,
        collection_name=args.collection,
        limit=args.limit,
    )

    print_input_summary(results)
    print_results(results)

    test_cases = build_test_cases(results)

    if not test_cases:
        print("No successful generations to score; skipping DeepEval evaluation.")
        return

    metrics = build_metrics()

    deepeval_evaluate(
        test_cases=test_cases,
        metrics=metrics,
        identifier="production-rag-answer-evaluation",
        hyperparameters={
            "collection": args.collection,
            "retrieval_limit": args.limit,
            "judge_model": "deepseek-chat",
        },
    )


if __name__ == "__main__":
    asyncio.run(main())
