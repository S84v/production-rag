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
