import json
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from production_rag.schemas.query import QueryRequest
from production_rag.services.rag import RAGService

router = APIRouter()


def get_rag_service() -> RAGService:
    return RAGService()


@router.post("/query")
async def query(
    request: QueryRequest, rag_service: Annotated[RAGService, Depends(get_rag_service)]
) -> StreamingResponse:
    async def stream_response() -> AsyncIterator[str]:
        text_parts: list[str] = []

        async for event in rag_service.generate(
            query=request.query,
            collection_name=request.collection,
            limit=request.limit,
        ):
            if event.type == "sources":
                payload: dict[str, object] = {
                    "type": "sources",
                    "sources": [
                        {
                            "source": source.source,
                            "source_uri": source.source_uri,
                            "chunk_index": source.chunk_index,
                            "score": source.score,
                        }
                        for source in event.sources or []
                    ],
                }
                yield json.dumps(payload) + "\n"

            elif event.type == "text" and event.text is not None:
                text_parts.append(event.text)

        yield (
            json.dumps(
                {
                    "type": "text",
                    "text": "".join(text_parts),
                }
            )
            + "\n"
        )

    return StreamingResponse(
        stream_response(),
        media_type="application/x-ndjson",
    )
