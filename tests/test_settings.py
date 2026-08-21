from production_rag.core.settings import Settings


def test_qdrant_settings_defaults():
    settings = Settings()

    assert settings.qdrant_host == "localhost"
    assert settings.qdrant_port == 6333
