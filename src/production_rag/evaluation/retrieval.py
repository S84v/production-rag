import argparse
import asyncio
from dataclasses import dataclass
from pathlib import Path

from production_rag.evaluation.dataset import EvaluationExample, load_dataset
from production_rag.services.retrieval import RetrievalService


@dataclass(frozen=True)
class RetrievalEvaluationResult:
    example_id: str
    retrieved_chunks: tuple[str, ...]
    relevant_chunks: frozenset[str]
    precision: float
    recall: float
    reciprocal_rank: float
    hit: float


@dataclass(frozen=True)
class RetrievalEvaluationSummary:
    results: tuple[RetrievalEvaluationResult, ...]
    precision: float
    recall: float
    mrr: float
    hit_rate: float


def evaluate_example(
    example: EvaluationExample,
    retrieved_chunks: list[str],
) -> RetrievalEvaluationResult:
    relevant = example.relevant_chunks
    retrieved = retrieved_chunks

    relevant_retrieved = sum(chunk_id in relevant for chunk_id in retrieved)

    precision = relevant_retrieved / len(retrieved) if retrieved else 0.0

    recall = relevant_retrieved / len(relevant) if relevant else 0.0

    reciprocal_rank = 0.0

    for rank, chunk_id in enumerate(retrieved, start=1):
        if chunk_id in relevant:
            reciprocal_rank = 1.0 / rank
            break

    hit = 1.0 if relevant_retrieved > 0 else 0.0

    return RetrievalEvaluationResult(
        example_id=example.id,
        retrieved_chunks=tuple(retrieved),
        relevant_chunks=relevant,
        precision=precision,
        recall=recall,
        reciprocal_rank=reciprocal_rank,
        hit=hit,
    )


def summarize(results: list[RetrievalEvaluationResult]) -> RetrievalEvaluationSummary:
    if not results:
        raise ValueError("Cannot summarize an empty evaluation")

    count = len(results)

    return RetrievalEvaluationSummary(
        results=tuple(results),
        precision=sum(r.precision for r in results) / count,
        recall=sum(r.recall for r in results) / count,
        mrr=sum(r.reciprocal_rank for r in results) / count,
        hit_rate=sum(r.hit for r in results) / count,
    )


async def evaluate(
    examples: list[EvaluationExample],
    collection_name: str,
    limit: int,
) -> RetrievalEvaluationSummary:
    retrieval_service = RetrievalService()

    results: list[RetrievalEvaluationResult] = []

    for example in examples:
        retrieved = await retrieval_service.retrieve(
            query=example.question,
            collection_name=collection_name,
            limit=limit,
        )

        retrieved_chunks = [str(result.chunk.id) for result in retrieved]

        results.append(
            evaluate_example(example=example, retrieved_chunks=retrieved_chunks)
        )

    return summarize(results)


def print_summary(summary: RetrievalEvaluationSummary, limit: int) -> None:
    print("Retrieval Evaluation")
    print("=" * 20)
    print(f"Examples: {len(summary.results)}")
    print(f"Top-K: {limit}")
    print(f"Precision@{limit} Chunks: {summary.precision:.4f}")
    print(f"Recall@{limit} Chunks: {summary.recall:.4f}")
    print(f"Hit@{limit} Chunks: {summary.hit_rate:.4f}")
    print(f"MRR: {summary.mrr:.4f}")

    failures = [result for result in summary.results if result.recall < 1.0]

    if failures:
        print()
        print("Recall failures")
        print("-" * 15)

        for result in failures:
            print(f"\n{result.example_id}")
            print(f"Retrieved chunks: {list(result.retrieved_chunks)}")
            print(f"Relevant chunks: {list(result.relevant_chunks)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate retrieval quality against a labeled dataset."
    )

    parser.add_argument(
        "--dataset", type=Path, default=Path("data/evaluation/fastapi.json")
    )

    parser.add_argument(
        "--collection",
        default="fastapi",
    )

    parser.add_argument(
        "--k",
        type=int,
        default=5,
    )

    return parser.parse_args()


async def main() -> None:
    args = parse_args()

    examples = load_dataset(args.dataset)

    summary = await evaluate(
        examples=examples, collection_name=args.collection, limit=args.k
    )

    print_summary(summary, args.k)


if __name__ == "__main__":
    asyncio.run(main())
