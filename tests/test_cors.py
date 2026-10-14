import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient
from pydantic import ValidationError

from production_rag.core.settings import Settings
from production_rag.main import configure_cors

ORIGIN = "https://app.example.com"


def build_app(origins: str) -> FastAPI:
    app = FastAPI()

    @app.post("/query")
    async def query() -> dict[str, bool]:
        return {"ok": True}

    configure_cors(app, Settings(cors_allowed_origins=origins))

    return app


def test_allowed_origin_receives_cors_header_without_credentials():
    client = TestClient(build_app(ORIGIN))

    response = client.post("/query", json={}, headers={"Origin": ORIGIN})

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ORIGIN
    assert "access-control-allow-credentials" not in response.headers


def test_disallowed_origin_receives_no_cors_header():
    client = TestClient(build_app(ORIGIN))

    response = client.post(
        "/query",
        json={},
        headers={"Origin": "https://evil.example.com"},
    )

    assert "access-control-allow-origin" not in response.headers


def test_lookalike_origin_is_not_matched():
    client = TestClient(build_app(ORIGIN))

    response = client.post(
        "/query",
        json={},
        headers={"Origin": "https://app.example.com.evil.test"},
    )

    assert "access-control-allow-origin" not in response.headers


def test_preflight_allows_post_and_content_type():
    client = TestClient(build_app(ORIGIN))

    response = client.options(
        "/query",
        headers={
            "Origin": ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ORIGIN
    assert "POST" in response.headers["access-control-allow-methods"]
    assert "content-type" in response.headers["access-control-allow-headers"].lower()


def test_preflight_from_disallowed_origin_is_rejected():
    client = TestClient(build_app(ORIGIN))

    response = client.options(
        "/query",
        headers={
            "Origin": "https://evil.example.com",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert "access-control-allow-origin" not in response.headers


def test_empty_configuration_adds_no_cors_middleware():
    app = FastAPI()

    @app.post("/query")
    async def query() -> dict[str, bool]:
        return {"ok": True}

    configure_cors(app, Settings(cors_allowed_origins=""))

    assert not any(m.cls is CORSMiddleware for m in app.user_middleware)

    response = TestClient(app).post("/query", json={}, headers={"Origin": ORIGIN})

    assert "access-control-allow-origin" not in response.headers


def test_wildcard_configuration_is_rejected():
    with pytest.raises(ValidationError):
        Settings(cors_allowed_origins="*")
