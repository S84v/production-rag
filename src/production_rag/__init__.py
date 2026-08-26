import argparse
import asyncio
from pathlib import Path

from sqlalchemy import select

from production_rag.db.session import async_session_factory
from production_rag.ingestion.filesystem import FilesystemSource
from production_rag.models.collection import Collection
from production_rag.repositories.chunk import ChunkRepository
from production_rag.services.batch_ingestion import BatchIngestionService
from production_rag.services.document_ingestion import DocumentIngestionService
from production_rag.services.embedding import EmbeddingService


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

    for _, version, created in results:
        if created:
            new_document_count += 1

        async with async_session_factory() as session:
            repository = ChunkRepository(session)
            chunks = await repository.list_by_document_version(version.id)

        embeddings = await embedding_service.embed_chunks(
            chunks=chunks, collection_name=collection_name
        )

        chunk_count += len(chunks)
        embedding_count += len(embeddings)

    print(f"Collection: {collection_name}")
    print(f"Documents discovered: {document_count}")
    print(f"New documents: {new_document_count}")
    print(f"Chunks processed: {chunk_count}")
    print(f"Embeddings persisted: {embedding_count}")


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

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "ingest":
        if not args.path.is_dir():
            parser.error(f"corpus path does not exist: {args.path}")

        asyncio.run(ingest_corpus(path=args.path, collection_name=args.collection))
