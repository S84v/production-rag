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
