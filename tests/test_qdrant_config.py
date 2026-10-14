from production_rag.core.settings import Settings
from production_rag.services import qdrant as qdrant_module
from production_rag.services.qdrant import (
    QdrantVectorStore,
    build_qdrant_client_kwargs,
)


def make_settings(**overrides) -> Settings:
    defaults = {
        "qdrant_host": "localhost",
        "qdrant_port": 6333,
        "qdrant_url": "",
        "qdrant_api_key": "",
    }
    defaults.update(overrides)
    return Settings(_env_file=None, **defaults)


def test_local_fallback_uses_host_and_port():
    kwargs = build_qdrant_client_kwargs(make_settings())

    assert kwargs == {"host": "localhost", "port": 6333}


def test_local_fallback_respects_custom_host_and_port():
    kwargs = build_qdrant_client_kwargs(
        make_settings(qdrant_host="qdrant.internal", qdrant_port=7000)
    )

    assert kwargs == {"host": "qdrant.internal", "port": 7000}


def test_whitespace_url_falls_back_to_local():
    kwargs = build_qdrant_client_kwargs(make_settings(qdrant_url="   "))

    assert kwargs == {"host": "localhost", "port": 6333}


def test_hosted_url_takes_precedence_over_local_settings():
    kwargs = build_qdrant_client_kwargs(
        make_settings(
            qdrant_url="https://example.cloud.qdrant.io:6333",
            qdrant_host="localhost",
            qdrant_port=6333,
        )
    )

    assert kwargs == {"url": "https://example.cloud.qdrant.io:6333"}


def test_hosted_url_includes_api_key():
    kwargs = build_qdrant_client_kwargs(
        make_settings(
            qdrant_url="https://example.cloud.qdrant.io:6333",
            qdrant_api_key="secret-key",
        )
    )

    assert kwargs == {
        "url": "https://example.cloud.qdrant.io:6333",
        "api_key": "secret-key",
    }


def test_hosted_url_without_key_omits_api_key():
    kwargs = build_qdrant_client_kwargs(
        make_settings(qdrant_url="http://localhost:6333", qdrant_api_key="")
    )

    assert kwargs == {"url": "http://localhost:6333"}
    assert "api_key" not in kwargs


def test_whitespace_only_api_key_is_unset():
    kwargs = build_qdrant_client_kwargs(
        make_settings(
            qdrant_url="https://example.cloud.qdrant.io:6333",
            qdrant_api_key="   ",
        )
    )

    assert kwargs == {"url": "https://example.cloud.qdrant.io:6333"}


def test_local_mode_ignores_api_key():
    kwargs = build_qdrant_client_kwargs(
        make_settings(qdrant_url="", qdrant_api_key="secret-key")
    )

    assert kwargs == {"host": "localhost", "port": 6333}


class RecordingQdrantClient:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs


def test_vector_store_builds_hosted_client(monkeypatch):
    monkeypatch.setattr(qdrant_module, "AsyncQdrantClient", RecordingQdrantClient)
    monkeypatch.setattr(
        qdrant_module,
        "get_settings",
        lambda: make_settings(
            qdrant_url="https://example.cloud.qdrant.io:6333",
            qdrant_api_key="secret-key",
        ),
    )

    store = QdrantVectorStore()

    assert isinstance(store.client, RecordingQdrantClient)
    assert store.client.kwargs == {
        "url": "https://example.cloud.qdrant.io:6333",
        "api_key": "secret-key",
    }


def test_vector_store_builds_local_client(monkeypatch):
    monkeypatch.setattr(qdrant_module, "AsyncQdrantClient", RecordingQdrantClient)
    monkeypatch.setattr(
        qdrant_module,
        "get_settings",
        lambda: make_settings(qdrant_host="qdrant.internal", qdrant_port=7000),
    )

    store = QdrantVectorStore()

    assert store.client.kwargs == {"host": "qdrant.internal", "port": 7000}


def test_injected_client_is_used_without_constructing_a_remote_client(monkeypatch):
    def fail(**_kwargs):
        raise AssertionError("AsyncQdrantClient must not be constructed")

    monkeypatch.setattr(qdrant_module, "AsyncQdrantClient", fail)
    monkeypatch.setattr(
        qdrant_module,
        "get_settings",
        lambda: make_settings(qdrant_url="https://example.cloud.qdrant.io:6333"),
    )

    client = object()
    store = QdrantVectorStore(client=client)

    assert store.client is client
