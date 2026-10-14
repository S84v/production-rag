from types import SimpleNamespace

from production_rag.services import embedding as embedding_module
from production_rag.services.embedding import EmbeddingService

REVISION = "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a"


class RecordingSentenceTransformer:
    def __init__(self, model_name, **kwargs) -> None:
        self.model_name = model_name
        self.kwargs = kwargs


def make_service(monkeypatch, revision: str) -> EmbeddingService:
    monkeypatch.setattr(
        embedding_module, "SentenceTransformer", RecordingSentenceTransformer
    )
    monkeypatch.setattr(
        embedding_module,
        "get_settings",
        lambda: SimpleNamespace(embedding_model_revision=revision),
    )

    return EmbeddingService(vector_store=object())


def test_encoder_uses_configured_revision(monkeypatch):
    service = make_service(monkeypatch, REVISION)

    encoder = service._get_encoder()

    assert encoder.model_name == EmbeddingService.MODEL_NAME
    assert encoder.kwargs == {"revision": REVISION, "local_files_only": True}


def test_encoder_omits_revision_when_setting_is_blank(monkeypatch):
    service = make_service(monkeypatch, "")

    encoder = service._get_encoder()

    assert encoder.kwargs == {"revision": None, "local_files_only": True}


def test_logical_model_name_is_unchanged():
    assert EmbeddingService.MODEL_NAME == "BAAI/bge-small-en-v1.5"
    assert EmbeddingService.MODEL_VERSION == "1"
