import argparse
import asyncio
import sys
from pathlib import Path

from sqlalchemy import select

from production_rag.db.session import async_session_factory
from production_rag.ingestion.filesystem import FilesystemSource
from production_rag.models.collection import Collection
from production_rag.repositories.chunk import ChunkRepository
from production_rag.services.batch_ingestion import BatchIngestionService
from production_rag.services.document_ingestion import DocumentIngestionService
from production_rag.services.embedding import EmbeddingService
from production_rag.services.rag import RAGService
from production_rag.services.reconciliation import reconcile


async def ingest_corpus(path: Path, collection_name: str) -> None:
    async with async_session_factory() as session:
        result = await session.execute(
            select(Collection).where(Collection.name == collection_name)
        )
        collection = result.scalar_one_or_none()

        if collection is None:
            collection = Collection(name=collection_name)
            session.add(collection)
            await session.flush()

        collection_id = collection.id
        await session.commit()

    source = FilesystemSource(path)

    ingestion_service = BatchIngestionService(DocumentIngestionService())

    results = await ingestion_service.ingest_filesystem(
        collection_id=collection_id, source=source
    )

    embedding_service = EmbeddingService()

    document_count = len(results)
    new_document_count = 0
    chunk_count = 0
    embedding_count = 0
    persisted_count = 0
    repaired_count = 0
    skipped_count = 0

    for _, version, created in results:
        if created:
            new_document_count += 1

        async with async_session_factory() as session:
            repository = ChunkRepository(session)
            chunks = await repository.list_by_document_version(version.id)

        batch = await embedding_service.embed_chunks(
            chunks=chunks, collection_name=collection_name
        )

        chunk_count += len(chunks)
        embedding_count += len(batch.embeddings)
        persisted_count += batch.persisted
        repaired_count += batch.repaired
        skipped_count += batch.skipped

    print(f"Collection: {collection_name}")
    print(f"Documents discovered: {document_count}")
    print(f"New documents: {new_document_count}")
    print(f"Chunks processed: {chunk_count}")
    print(f"Embeddings resolved: {embedding_count}")
    print(f"  persisted: {persisted_count}")
    print(f"  repaired: {repaired_count}")
    print(f"  skipped (unchanged): {skipped_count}")


async def query_rag(query: str, collection_name: str, limit: int) -> None:
    rag_service = RAGService()

    sources = []

    print(f"> {query}")
    print()

    async for event in rag_service.generate(
        query=query,
        collection_name=collection_name,
        limit=limit,
    ):
        if event.type == "sources":
            sources = event.sources or []

        elif event.type == "text" and event.text is not None:
            print(event.text, end="", flush=True)

    print()
    print()
    print("Sources:")

    for source in sources:
        print(
            f"- {source.source_uri} "
            f"(chunk {source.chunk_index}, similarity: {source.score:.3f})"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="production-rag", description="Production RAG command-line interface"
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest_parser = subparsers.add_parser(
        "ingest", help="ingest and embed a Markdown corpus"
    )

    ingest_parser.add_argument(
        "--path", type=Path, required=True, help="path to the Markdown corpus"
    )
    ingest_parser.add_argument(
        "--collection", required=True, help="application collection name"
    )

    query_parser = subparsers.add_parser("query", help="query the RAG system")

    query_parser.add_argument(
        "query",
        help="question to ask",
    )

    query_parser.add_argument(
        "--collection",
        required=True,
        help="application collection name",
    )

    query_parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="number of chunks to retrieve",
    )

    prepare_parser = subparsers.add_parser(
        "prepare-corpus",
        help="expand MkDocs includes into a plain-Markdown corpus",
    )

    prepare_parser.add_argument(
        "--checkout",
        type=Path,
        required=True,
        help="path to the pinned FastAPI source checkout",
    )

    prepare_parser.add_argument(
        "--dest",
        type=Path,
        default=Path("data/raw/fastapi"),
        help="destination directory for the prepared corpus",
    )

    reconcile_parser = subparsers.add_parser(
        "reconcile",
        help=(
            "compare a collection's Qdrant points with PostgreSQL and, with "
            "--apply, delete only points proven non-authoritative"
        ),
    )

    reconcile_parser.add_argument(
        "--collection",
        required=True,
        help="application collection name",
    )

    reconcile_parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "delete non-authoritative points (default is a read-only dry run); "
            "never deletes PostgreSQL rows and never touches other collections"
        ),
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "ingest":
        if not args.path.is_dir():
            parser.error(f"corpus path does not exist: {args.path}")

        asyncio.run(ingest_corpus(path=args.path, collection_name=args.collection))

    elif args.command == "query":
        asyncio.run(
            query_rag(
                query=args.query, collection_name=args.collection, limit=args.limit
            )
        )

    elif args.command == "prepare-corpus":
        from production_rag.corpus.preparation import (
            PreparationError,
            prepare_corpus,
        )

        try:
            report = prepare_corpus(
                checkout_root=args.checkout,
                dest_root=args.dest,
            )
        except PreparationError as error:
            print(str(error), file=sys.stderr)
            raise SystemExit(1) from error

        print(report.summary())

    elif args.command == "reconcile":
        report = asyncio.run(
            reconcile(collection_name=args.collection, apply=args.apply)
        )

        print(report.summary())

        if not args.apply and report.deletable_points:
            print()
            print(
                "dry run: no points deleted; re-run with --apply to delete "
                "non-authoritative points"
            )
