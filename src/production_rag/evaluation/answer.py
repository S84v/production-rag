import argparse
import asyncio
from dataclasses import dataclass
from pathlib import Path

from production_rag.evaluation.dataset import EvaluationExample, load_dataset
from production_rag.evaluation.retrieval import source_path
from production_rag.services.rag import RAGService, RAGSource


@dataclass(frozen=True)
class AnswerEvaluationResult:
    example_id: str
    question: str
    reference_answer: str
    generated_answer: str
    retrieved_sources: tuple[RAGSource, ...]
    relevant_sources: frozenset[str]
    retrieved_source_names: tuple[str, ...]
    retrieved_hit: bool


async def evaluate_example(
    example: EvaluationExample,
    rag_service: RAGService,
    collection_name: str,
    limit: int,
) -> AnswerEvaluationResult:
    answer_parts: list[str] = []
    retrieved_sources: list[str] = []

    async for event in rag_service.generate(
        query=example.question,
        collection_name=collection_name,
        limit=limit,
    ):
        if event.type == "sources" and event.sources is not None:
            retrieved_sources = event.sources

        elif event.type == "text" and event.text is not None:
            answer_parts.append(event.text)

        retrieved_source_names = tuple(
            dict.fromkeys(
                source_path(source.source_uri) for source in retrieved_sources
            )
        )

        retrieved_hit = bool(set(retrieved_source_names) & example.relevant_sources)

    return AnswerEvaluationResult(
        example_id=example.id,
        question=example.question,
        reference_answer=example.reference_answer,
        generated_answer="".join(answer_parts),
        retrieved_sources=tuple(retrieved_sources),
        relevant_sources=example.relevant_sources,
        retrieved_source_names=retrieved_source_names,
        retrieved_hit=retrieved_hit,
    )


async def evaluate(
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


def print_results(results: list[AnswerEvaluationResult]) -> None:
    print("Answer Evaluation")
    print("=" * 17)
    print(f"Examples: {len(results)}")
    print()

    for result in results:
        print(result.example_id)
        print("-" * len(result.example_id))
        print(f"Question: {result.question}")
        print(f"Reference: {result.reference_answer}")
        print(f"Generated: {result.generated_answer}")
        print(f"Sources: {list(result.relevant_sources)}")
        print()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run answer-generation evaluation.")

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

    results = await evaluate(
        examples=examples,
        collection_name=args.collection,
        limit=args.limit,
    )

    print_results(results)


if __name__ == "__main__":
    asyncio.run(main())
