import argparse
import asyncio
from dataclasses import dataclass
from pathlib import Path

from production_rag.db.session import async_session_factory
from production_rag.evaluation.anchors import (
    ChunkRecord,
    resolve_example_relevant_chunk_ids,
)
from production_rag.evaluation.dataset import EvaluationExample, load_dataset
from production_rag.repositories.retrieval import RetrievalRepository
from production_rag.services.retrieval import RetrievalService


@dataclass(frozen=True)
class RetrievedChunk:
    source_uri: str
    chunk_index: int
    chunk_id: str
    score: float


@dataclass(frozen=True)
class RetrievalEvaluationResult:
    example_id: str
    retrieved_chunks: tuple[RetrievedChunk, ...]
    relevant_chunk_ids: frozenset[str]
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
    example_id: str,
    relevant_chunk_ids: frozenset[str],
    retrieved_chunks: list[RetrievedChunk],
) -> RetrievalEvaluationResult:
    relevant = relevant_chunk_ids
    retrieved_ids = [chunk.chunk_id for chunk in retrieved_chunks]

    relevant_retrieved = sum(chunk_id in relevant for chunk_id in retrieved_ids)

    precision = relevant_retrieved / len(retrieved_ids) if retrieved_ids else 0.0

    recall = relevant_retrieved / len(relevant) if relevant else 0.0

    reciprocal_rank = 0.0

    for rank, chunk_id in enumerate(retrieved_ids, start=1):
        if chunk_id in relevant:
            reciprocal_rank = 1.0 / rank
            break

    hit = 1.0 if relevant_retrieved > 0 else 0.0

    return RetrievalEvaluationResult(
        example_id=example_id,
        retrieved_chunks=tuple(retrieved_chunks),
        relevant_chunk_ids=relevant,
        precision=precision,
        recall=recall,
        reciprocal_rank=reciprocal_rank,
        hit=hit,
    )


def summarize(
    results: list[RetrievalEvaluationResult],
) -> RetrievalEvaluationSummary:
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


async def load_collection_chunk_records(collection_name: str) -> list[ChunkRecord]:
    async with async_session_factory() as session:
        repository = RetrievalRepository(session)
        rows = await repository.list_collection_chunks(collection_name)

    return [
        ChunkRecord(chunk_id=str(chunk_id), source_uri=source_uri, content=content)
        for chunk_id, source_uri, content in rows
    ]


async def evaluate(
    examples: list[EvaluationExample],
    collection_name: str,
    limit: int,
) -> RetrievalEvaluationSummary:
    chunk_records = await load_collection_chunk_records(collection_name)

    retrieval_service = RetrievalService()

    results: list[RetrievalEvaluationResult] = []

    for example in examples:
        relevant_chunk_ids = resolve_example_relevant_chunk_ids(
            example,
            chunk_records,
        )

        retrieved = await retrieval_service.retrieve(
            query=example.question,
            collection_name=collection_name,
            limit=limit,
        )

        retrieved_chunks = [
            RetrievedChunk(
                source_uri=result.source_uri,
                chunk_index=result.chunk.chunk_index,
                chunk_id=str(result.chunk.id),
                score=result.score,
            )
            for result in retrieved
        ]

        results.append(
            evaluate_example(
                example_id=example.id,
                relevant_chunk_ids=relevant_chunk_ids,
                retrieved_chunks=retrieved_chunks,
            )
        )

    return summarize(results)


def print_summary(
    summary: RetrievalEvaluationSummary,
    limit: int,
) -> None:
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

            print("Retrieved chunks:")

            for rank, chunk in enumerate(
                result.retrieved_chunks,
                start=1,
            ):
                print(
                    f"  {rank}. "
                    f"{chunk.source_uri} | "
                    f"chunk={chunk.chunk_index} | "
                    f"uuid={chunk.chunk_id} | "
                    f"score={chunk.score:.4f}"
                )

            print(f"Relevant chunk IDs: {sorted(result.relevant_chunk_ids)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate retrieval quality against a labeled dataset."
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
        "--k",
        type=int,
        default=5,
    )

    return parser.parse_args()


async def main() -> None:
    args = parse_args()

    examples = load_dataset(args.dataset)

    summary = await evaluate(
        examples=examples,
        collection_name=args.collection,
        limit=args.k,
    )

    print_summary(summary, args.k)


if __name__ == "__main__":
    asyncio.run(main())
