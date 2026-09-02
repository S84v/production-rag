import json

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from production_rag.api.query import get_rag_service
from production_rag.main import app
from production_rag.services.rag import RAGEvent, RAGSource


class FakeRAGService:
    def __init__(self) -> None:
        self.calls = []

    async def generate(self, query: str, collection_name: str, limit: int = 5):
        self.calls.append(
            {
                "query": query,
                "collection_name": collection_name,
                "limit": limit,
            }
        )

        yield RAGEvent(
            type="sources",
            sources=[
                RAGSource(
                    source="fastapi",
                    source_uri="docs/index.md",
                    chunk_id="00000000-0000-0000-0000-000000000001",
                    chunk_index=0,
                    score=0.95,
                    content="FastAPI is a Python web framework.",
                )
            ],
        )

        yield RAGEvent(type="text", text="FastAPI")
        yield RAGEvent(type="text", text=" is a web framework.")

        yield RAGEvent(
            type="complete",
            retrieval_time_ms=100.0,
            total_time_ms=500.0,
        )


@pytest.fixture
def fake_rag_service() -> FakeRAGService:
    return FakeRAGService()


@pytest.fixture
def client(fake_rag_service: FakeRAGService) -> TestClient:
    app.dependency_overrides[get_rag_service] = lambda: fake_rag_service

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def test_query_endpoint_streams_rag_response(
    client: TestClient,
    fake_rag_service: FakeRAGService,
) -> None:
    response = client.post(
        "/query",
        json={
            "query": "What is FastAPI?",
            "collection": "fastapi",
            "limit": 3,
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/x-ndjson"

    events = [json.loads(line) for line in response.text.splitlines()]

    assert events == [
        {
            "type": "sources",
            "sources": [
                {
                    "source": "fastapi",
                    "source_uri": "docs/index.md",
                    "chunk_id": "00000000-0000-0000-0000-000000000001",
                    "chunk_index": 0,
                    "score": 0.95,
                }
            ],
        },
        {
            "type": "complete",
            "retrieval_time_ms": 100.0,
            "total_time_ms": 500.0,
        },
        {
            "type": "text",
            "text": "FastAPI is a web framework.",
        },
    ]

    assert fake_rag_service.calls == [
        {
            "query": "What is FastAPI?",
            "collection_name": "fastapi",
            "limit": 3,
        }
    ]


def test_query_endpoint_rejects_empty_query(client: TestClient) -> None:
    response = client.post(
        "/query",
        json={
            "query": "",
            "collection": "fastapi",
        },
    )

    assert response.status_code == 422


def test_get_rag_service_returns_application_service(
    client: TestClient,
) -> None:
    expected_service = app.state.rag_service

    request = Request(
        {
            "type": "http",
            "app": app,
        }
    )

    assert get_rag_service(request) is expected_service
