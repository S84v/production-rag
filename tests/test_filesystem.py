from production_rag.ingestion.filesystem import FilesystemSource


def test_filesystem_source_discovers_markdown_files_recursively(tmp_path):
    (tmp_path / "first.md").write_text("# First", encoding="utf-8")
    nested_dir = tmp_path / "nested"
    nested_dir.mkdir()
    (nested_dir / "second.md").write_text("# Second", encoding="utf-8")

    (tmp_path / "ignored.txt").write_text("ignore me", encoding="utf-8")

    source = FilesystemSource(tmp_path)

    paths = source.discover()

    assert paths == [tmp_path / "first.md", nested_dir / "second.md"]


def test_filesystem_source_discovers_files_in_deterministic_order(tmp_path):
    (tmp_path / "z.md").write_text("# Z", encoding="utf-8")
    (tmp_path / "a.md").write_text("# A", encoding="utf-8")

    nested_dir = tmp_path / "nested"
    nested_dir.mkdir()
    (nested_dir / "m.md").write_text("# M", encoding="utf-8")

    source = FilesystemSource(tmp_path)

    assert source.discover() == [
        tmp_path / "a.md",
        nested_dir / "m.md",
        tmp_path / "z.md",
    ]
