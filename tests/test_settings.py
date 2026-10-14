import pytest
from pydantic import ValidationError

from production_rag.core.settings import Settings


def test_qdrant_settings_defaults():
    settings = Settings()

    assert settings.qdrant_host == "localhost"
    assert settings.qdrant_port == 6333


def test_allowed_collections_defaults_to_fastapi(monkeypatch):
    monkeypatch.delenv("ALLOWED_COLLECTIONS", raising=False)
    settings = Settings(_env_file=None)

    assert settings.allowed_collections == "fastapi"
    assert settings.allowed_collection_names == frozenset({"fastapi"})


def test_allowed_collections_parses_comma_separated_names():
    settings = Settings(allowed_collections="fastapi, extra ,  ")

    assert settings.allowed_collection_names == frozenset({"fastapi", "extra"})


def test_allowed_collections_empty_denies_all():
    settings = Settings(allowed_collections="")

    assert settings.allowed_collection_names == frozenset()


def test_allowed_collections_reads_environment(monkeypatch):
    monkeypatch.setenv("ALLOWED_COLLECTIONS", "fastapi,demo")

    settings = Settings()

    assert settings.allowed_collection_names == frozenset({"fastapi", "demo"})


def test_cost_bounds_defaults(monkeypatch):
    monkeypatch.delenv("MAX_OUTPUT_TOKENS", raising=False)
    monkeypatch.delenv("MAX_CONTEXT_CHARACTERS", raising=False)

    settings = Settings(_env_file=None)

    assert settings.max_output_tokens == 1024
    assert settings.max_context_characters == 12000


def test_max_output_tokens_must_be_positive():
    with pytest.raises(ValidationError):
        Settings(max_output_tokens=0)


def test_max_context_characters_must_be_positive():
    with pytest.raises(ValidationError):
        Settings(max_context_characters=0)


def test_cost_bounds_read_environment(monkeypatch):
    monkeypatch.setenv("MAX_OUTPUT_TOKENS", "512")
    monkeypatch.setenv("MAX_CONTEXT_CHARACTERS", "8000")

    settings = Settings(_env_file=None)

    assert settings.max_output_tokens == 512
    assert settings.max_context_characters == 8000


def test_database_url_defaults_to_empty(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)

    settings = Settings(_env_file=None)

    assert settings.database_url == ""


def test_database_url_reads_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@host/db")

    settings = Settings(_env_file=None)

    assert settings.database_url == "postgresql://user:pass@host/db"


def test_qdrant_hosted_settings_default_to_empty(monkeypatch):
    monkeypatch.delenv("QDRANT_URL", raising=False)
    monkeypatch.delenv("QDRANT_API_KEY", raising=False)

    settings = Settings(_env_file=None)

    assert settings.qdrant_url == ""
    assert settings.qdrant_api_key == ""


def test_qdrant_hosted_settings_read_environment(monkeypatch):
    monkeypatch.setenv("QDRANT_URL", "https://example.cloud.qdrant.io:6333")
    monkeypatch.setenv("QDRANT_API_KEY", "example-key")

    settings = Settings(_env_file=None)

    assert settings.qdrant_url == "https://example.cloud.qdrant.io:6333"
    assert settings.qdrant_api_key == "example-key"


def test_embedding_model_revision_defaults_to_empty(monkeypatch):
    monkeypatch.delenv("EMBEDDING_MODEL_REVISION", raising=False)

    settings = Settings(_env_file=None)

    assert settings.embedding_model_revision == ""


def test_embedding_model_revision_reads_environment(monkeypatch):
    revision = "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a"
    monkeypatch.setenv("EMBEDDING_MODEL_REVISION", revision)

    settings = Settings(_env_file=None)

    assert settings.embedding_model_revision == revision


def test_cors_allowed_origins_defaults_to_empty(monkeypatch):
    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)

    settings = Settings(_env_file=None)

    assert settings.cors_allowed_origins == ""
    assert settings.cors_allowed_origin_list == []


def test_cors_allowed_origins_parses_comma_separated():
    settings = Settings(
        cors_allowed_origins=" https://a.example.com ,, https://b.example.com ,"
    )

    assert settings.cors_allowed_origin_list == [
        "https://a.example.com",
        "https://b.example.com",
    ]


def test_cors_allowed_origins_reads_environment(monkeypatch):
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://app.example.com")

    settings = Settings(_env_file=None)

    assert settings.cors_allowed_origin_list == ["https://app.example.com"]


def test_cors_allowed_origins_rejects_wildcard():
    with pytest.raises(ValidationError):
        Settings(cors_allowed_origins="https://app.example.com,*")
