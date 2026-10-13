import json

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from production_rag.api.query import get_rag_service
from production_rag.core.settings import Settings, get_settings
from production_rag.main import app
from production_rag.services.rag import RAGEvent, RAGSource


class FakeRAGService:
    def __init__(
        self,
        existing_collections: tuple[str, ...] = ("fastapi",),
        emit_error: bool = False,
    ) -> None:
        self.existing_collections = set(existing_collections)
        self.emit_error = emit_error
        self.calls = []
        self.exists_calls = []

    async def collection_exists(self, collection_name: str) -> bool:
        self.exists_calls.append(collection_name)
        return collection_name in self.existing_collections

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

        if self.emit_error:
            yield RAGEvent(
                type="error",
                error_code="generation_failed",
                error_message="The answer could not be generated. Please try again.",
            )
            return

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
            "type": "text",
            "text": "FastAPI",
        },
        {
            "type": "text",
            "text": " is a web framework.",
        },
        {
            "type": "complete",
            "retrieval_time_ms": 100.0,
            "total_time_ms": 500.0,
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


def test_query_endpoint_rejects_nonexistent_collection(
    client: TestClient,
) -> None:
    response = client.post(
        "/query",
        json={
            "query": "What is FastAPI?",
            "collection": "does-not-exist",
            "limit": 5,
        },
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Collection 'does-not-exist' not found"}


def test_query_endpoint_rejects_disallowed_collection_before_existence_check(
    client: TestClient,
    fake_rag_service: FakeRAGService,
) -> None:
    # The backend knows this collection, but it is not on the API allowlist.
    fake_rag_service.existing_collections.add("internal")

    response = client.post(
        "/query",
        json={"query": "What is FastAPI?", "collection": "internal"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Collection 'internal' not found"}
    # Enforced before any Qdrant existence check or generation.
    assert fake_rag_service.exists_calls == []
    assert fake_rag_service.calls == []


def test_query_endpoint_rejects_allowed_but_nonexistent_collection(
    client: TestClient,
    fake_rag_service: FakeRAGService,
) -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(
        allowed_collections="fastapi,missing"
    )

    response = client.post(
        "/query",
        json={"query": "What is FastAPI?", "collection": "missing"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Collection 'missing' not found"}
    # An allowed collection reaches the existence check.
    assert fake_rag_service.exists_calls == ["missing"]
    assert fake_rag_service.calls == []


def test_query_endpoint_rejects_oversized_query(
    client: TestClient,
    fake_rag_service: FakeRAGService,
) -> None:
    response = client.post(
        "/query",
        json={"query": "a" * 2001, "collection": "fastapi"},
    )

    assert response.status_code == 422
    assert fake_rag_service.exists_calls == []
    assert fake_rag_service.calls == []


def test_query_endpoint_rejects_oversized_collection(
    client: TestClient,
    fake_rag_service: FakeRAGService,
) -> None:
    response = client.post(
        "/query",
        json={"query": "What is FastAPI?", "collection": "a" * 129},
    )

    assert response.status_code == 422
    assert fake_rag_service.exists_calls == []
    assert fake_rag_service.calls == []


def test_query_endpoint_accepts_query_at_max_length(
    client: TestClient,
    fake_rag_service: FakeRAGService,
) -> None:
    query = "a" * 2000

    response = client.post(
        "/query",
        json={"query": query, "collection": "fastapi"},
    )

    assert response.status_code == 200
    assert fake_rag_service.calls[0]["query"] == query


def test_query_endpoint_accepts_collection_at_max_length(
    client: TestClient,
    fake_rag_service: FakeRAGService,
) -> None:
    collection = "a" * 128
    fake_rag_service.existing_collections.add(collection)
    app.dependency_overrides[get_settings] = lambda: Settings(
        allowed_collections=collection
    )

    response = client.post(
        "/query",
        json={"query": "What is FastAPI?", "collection": collection},
    )

    assert response.status_code == 200
    assert fake_rag_service.exists_calls == [collection]


def test_query_endpoint_rejects_empty_collection(
    client: TestClient,
    fake_rag_service: FakeRAGService,
) -> None:
    response = client.post(
        "/query",
        json={"query": "What is FastAPI?", "collection": ""},
    )

    assert response.status_code == 422
    assert fake_rag_service.exists_calls == []
    assert fake_rag_service.calls == []


def test_query_endpoint_streams_error_event_without_completion(
    client: TestClient,
    fake_rag_service: FakeRAGService,
) -> None:
    fake_rag_service.emit_error = True

    response = client.post(
        "/query",
        json={"query": "What is FastAPI?", "collection": "fastapi"},
    )

    assert response.status_code == 200

    events = [json.loads(line) for line in response.text.splitlines()]

    assert events[-1] == {
        "type": "error",
        "code": "generation_failed",
        "message": "The answer could not be generated. Please try again.",
    }
    # A failed generation must not emit a completion event.
    assert all(event["type"] != "complete" for event in events)
