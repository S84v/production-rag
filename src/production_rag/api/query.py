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
    stream: AsyncIterator[str] = rag_service.generate(
        query=request.query,
        collection_name=request.collection,
        limit=request.limit,
    )

    return StreamingResponse(
        stream,
        media_type="text/plain",
    )
