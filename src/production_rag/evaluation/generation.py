import argparse
import asyncio
from dataclasses import dataclass
from pathlib import Path

from production_rag.evaluation.dataset import EvaluationExample, load_dataset
from production_rag.services.rag import RAGService


@dataclass(frozen=True)
class GenerationResult:
    example_id: str
    question: str
    reference_answer: str
    answer: str
    sources: tuple[dict[str, str | int | float], ...]
    retrieval_time_ms: float
    total_time_ms: float


async def evaluate_example(
    rag_service: RAGService,
    example: EvaluationExample,
    collection_name: str,
    limit: int,
) -> GenerationResult:
    answer_parts: list[str] = []
    sources: tuple[dict[str, str | int | float], ...] = ()
    retrieval_time_ms = 0.0
    total_time_ms = 0.0

    async for event in rag_service.generate(
        query=example.question,
        collection_name=collection_name,
        limit=limit,
    ):
        if event.type == "sources" and event.sources is not None:
            retrieval_time_ms = getattr(event, "retrieval_time_ms", 0.0) or 0.0

            sources = tuple(
                {
                    "source": source.source,
                    "source_uri": source.source_uri,
                    "chunk_index": source.chunk_index,
                    "chunk_id": source.chunk_id,
                    "score": source.score,
                }
                for source in event.sources
            )

        elif event.type == "complete":
            total_time_ms = getattr(event, "total_time_ms", 0.0) or 0.0

        elif event.type == "text" and event.text:
            answer_parts.append(event.text)

    return GenerationResult(
        example_id=example.id,
        question=example.question,
        reference_answer=example.reference_answer,
        answer="".join(answer_parts),
        sources=sources,
        retrieval_time_ms=retrieval_time_ms,
        total_time_ms=total_time_ms,
    )


async def evaluate(
    examples: list[EvaluationExample],
    collection_name: str,
    limit: int,
) -> list[GenerationResult]:
    rag_service = RAGService()

    results: list[GenerationResult] = []

    for example in examples:
        print(f"Evaluating {example.id}...")

        result = await evaluate_example(
            rag_service=rag_service,
            example=example,
            collection_name=collection_name,
            limit=limit,
        )

        results.append(result)

    return results


def write_markdown(
    results: list[GenerationResult],
    path: Path,
) -> None:
    lines = [
        "# Generation Evaluation Results",
        "",
        f"Examples: {len(results)}",
        "",
        "> Generated using the current end-to-end RAG pipeline. "
        "Answers are included for manual evaluation against the reference "
        "answers and retrieved sources.",
        "",
    ]

    for result in results:
        lines.extend(
            [
                f"## {result.example_id}",
                "",
                f"**Question:** {result.question}",
                "",
                "**Reference answer:**",
                "",
                result.reference_answer,
                "",
                "**Generated answer:**",
                "",
                result.answer,
                "",
                f"**Retrieval time:** {result.retrieval_time_ms:.2f} ms",
                "",
                f"**Total RAG time:** {result.total_time_ms:.2f} ms",
                "",
                f"**Retrieved chunks:** {len(result.sources)}",
                "",
                "**Retrieved sources:**",
                "",
            ]
        )

        if result.sources:
            for rank, source in enumerate(result.sources, start=1):
                lines.append(
                    f"{rank}. `{source['source_uri']}` | "
                    f"chunk={source['chunk_index']} | "
                    f"uuid=`{source['chunk_id']}` | "
                    f"score={source['score']:.4f}"
                )
        else:
            lines.append("No sources retrieved.")

        lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate end-to-end RAG generation.")

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

    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/evaluation/generation_results.md"),
    )

    return parser.parse_args()


async def main() -> None:
    args = parse_args()

    examples = load_dataset(args.dataset)

    results = await evaluate(
        examples=examples,
        collection_name=args.collection,
        limit=args.k,
    )

    write_markdown(results, args.output)

    print()
    print("Generation evaluation complete.")
    print(f"Examples: {len(results)}")
    print(f"Output: {args.output}")


if __name__ == "__main__":
    asyncio.run(main())
