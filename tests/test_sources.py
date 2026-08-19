import hashlib

import pytest

from production_rag.ingestion.filesystem import FilesystemSource


def test_filesystem_source_reads_markdown_file(tmp_path):
    content = "# FastAPI\n\nA web framework for building APIs."
    document_path = tmp_path / "fastapi.md"
    document_path.write_text(content, encoding="utf-8")

    source = FilesystemSource(tmp_path)

    document = source.acquire(document_path)

    assert document.source == "filesystem"
    assert document.source_uri == "filesystem://fastapi.md"
    assert document.content == content
    assert document.content_hash == hashlib.sha256(content.encode("utf-8")).hexdigest()
    assert document.title == "fastapi.md"
    assert document.source_revision is not None


def test_filesystem_source_uses_relative_deterministic_uri(tmp_path):
    nested_dir = tmp_path / "fastapi"
    nested_dir.mkdir()

    document_path = nested_dir / "body.md"
    document_path.write_text("# Body", encoding="utf-8")

    source = FilesystemSource(tmp_path)

    document = source.acquire(document_path)

    assert document.source_uri == "filesystem://fastapi/body.md"


def test_filesystem_source_rejects_path_outside_root(tmp_path):
    root = tmp_path / "source"
    root.mkdir()

    outside_file = tmp_path / "outside.md"
    outside_file.write_text("# Outside", encoding="utf-8")

    source = FilesystemSource(root)

    with pytest.raises(ValueError, match="inside source root"):
        source.acquire(outside_file)
