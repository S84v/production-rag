import pytest
from fastapi.testclient import TestClient

from production_rag.api.query import get_rag_service
from production_rag.main import app


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

        yield "FastAPI"
        yield " is a web framework."


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
    assert response.text == "FastAPI is a web framework."

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
