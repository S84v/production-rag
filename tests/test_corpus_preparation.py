import json
from pathlib import Path

import pytest

from production_rag.corpus.preparation import (
    MANIFEST_NAME,
    PreparationError,
    expand_includes,
    normalize_markdown,
    prepare_corpus,
    relative_destination,
    resolve_include,
)
from tests.helpers.corpus import PROSE, build_checkout


def test_expand_includes_wraps_in_fenced_block(tmp_path: Path) -> None:
    root = build_checkout(tmp_path)
    document = root / "docs/en/docs/tutorial/example.md"

    def load(target: str):
        path = resolve_include(
            checkout_root=root,
            docs_root=root / "docs/en/docs",
            document=document,
            target=target,
        )
        return path, path.read_text(encoding="utf-8")

    expanded = expand_includes(
        "Text\n\n{* ../../docs_src/demo/example.py hl[6:7] *}\n",
        load=load,
    )

    assert "```python" in expanded
    assert '@app.get("/items/{item_id}")' in expanded
    assert "{*" not in expanded


def test_expand_includes_inside_fence_keeps_surrounding_fence(tmp_path: Path) -> None:
    root = build_checkout(tmp_path)
    document = root / "docs/en/docs/tutorial/example.md"

    def load(target: str):
        path = resolve_include(
            checkout_root=root,
            docs_root=root / "docs/en/docs",
            document=document,
            target=target,
        )
        return path, path.read_text(encoding="utf-8")

    expanded = expand_includes(
        "```python\n{!../../docs_src/demo/example.py!}\n```\n",
        load=load,
    )

    assert expanded.count("```") == 2
    assert "app = FastAPI()" in expanded


def test_resolve_include_fails_when_target_is_missing(tmp_path: Path) -> None:
    root = build_checkout(tmp_path)

    with pytest.raises(PreparationError) as excinfo:
        resolve_include(
            checkout_root=root,
            docs_root=root / "docs/en/docs",
            document=root / "docs/en/docs/tutorial/example.md",
            target="../../docs_src/demo/missing.py",
        )

    assert "was not found" in str(excinfo.value)


def test_expand_includes_rejects_unsupported_target_type(tmp_path: Path) -> None:
    root = build_checkout(tmp_path)
    (root / "docs_src/demo/blob.bin").write_text("binary-ish", encoding="utf-8")

    with pytest.raises(PreparationError) as excinfo:
        expand_includes(
            "{* ../../docs_src/demo/blob.bin *}\n",
            load=lambda target: (root / "docs_src/demo/blob.bin", "binary-ish"),
        )

    assert "unsupported include target type" in str(excinfo.value)


def test_normalize_markdown_removes_mkdocs_syntax() -> None:
    text = (
        "# Title { #title }\n\n"
        "/// tip\n\n"
        'Some <dfn title="definition">marked</dfn> text.\n\n'
        "///\n\n"
        "{% raw %}\n"
    )

    normalized = normalize_markdown(text)

    assert normalized.startswith("# Title\n")
    assert "///" not in normalized
    assert "{ #title }" not in normalized
    assert "<dfn" not in normalized
    assert "marked" in normalized
    assert "{% raw %}" not in normalized


def test_normalize_markdown_keeps_fenced_content_untouched() -> None:
    text = "```jinja\nItem ID: {{ id }}\n```\n"

    assert "{{ id }}" in normalize_markdown(text)


def test_normalize_markdown_rejects_unhandled_jinja_block() -> None:
    with pytest.raises(PreparationError) as excinfo:
        normalize_markdown("{% for sponsor in sponsors.gold %}\n")

    assert "Jinja block directive" in str(excinfo.value)


def test_normalize_markdown_rejects_content_tabs() -> None:
    with pytest.raises(PreparationError):
        normalize_markdown('=== "Python 3.10+"\n')


def test_relative_destination_preserves_existing_uris() -> None:
    assert relative_destination(Path("tutorial/path-params.md")) == Path(
        "path-params.md"
    )
    assert relative_destination(Path("tutorial/security/index.md")) == Path(
        "security/index.md"
    )
    assert relative_destination(Path("advanced/events.md")) == Path(
        "advanced/events.md"
    )
    assert relative_destination(Path("features.md")) == Path("guide/features.md")


def test_prepare_corpus_is_deterministic_and_reports_exclusions(
    tmp_path: Path,
) -> None:
    root = build_checkout(tmp_path)
    dest = tmp_path / "out"

    def snapshot() -> dict[str, bytes]:
        return {
            path.relative_to(dest).as_posix(): path.read_bytes()
            for path in sorted(dest.rglob("*.md"))
        }

    first = prepare_corpus(checkout_root=root, dest_root=dest, verify_revision=False)
    first_bytes = snapshot()

    second = prepare_corpus(checkout_root=root, dest_root=dest, verify_revision=False)
    second_bytes = snapshot()

    assert first_bytes == second_bytes
    assert first.documents == second.documents == 3
    assert first.directives == 2
    assert (dest / "example.md").is_file()
    assert (dest / "advanced/example.md").is_file()
    assert (dest / "guide/features.md").is_file()

    excluded = {item.path: item.reason for item in second.excluded}
    assert "reference/stub.md" in excluded
    assert "generated API reference only" in excluded["reference/stub.md"]


def test_prepare_corpus_preserves_unrelated_files_and_prunes_stale(
    tmp_path: Path,
) -> None:
    root = build_checkout(tmp_path)
    dest = tmp_path / "out"
    dest.mkdir()
    (dest / "unrelated.txt").write_text("do not delete", encoding="utf-8")

    prepare_corpus(checkout_root=root, dest_root=dest, verify_revision=False)
    assert (dest / "advanced/example.md").is_file()

    # Removing a selected document must prune only previously managed files.
    (root / "docs/en/docs/advanced/example.md").unlink()
    prepare_corpus(checkout_root=root, dest_root=dest, verify_revision=False)

    assert not (dest / "advanced/example.md").exists()
    assert (dest / "unrelated.txt").read_text(encoding="utf-8") == "do not delete"

    manifest = json.loads((dest / MANIFEST_NAME).read_text(encoding="utf-8"))
    assert "pinned_revision" in manifest
    assert "advanced/example.md" not in manifest["files"]


def test_prepare_corpus_fails_on_unresolved_include(tmp_path: Path) -> None:
    root = build_checkout(tmp_path)
    (root / "docs/en/docs/tutorial/example.md").write_text(
        f"# Broken\n\n{{* ../../docs_src/demo/missing.py *}}\n\n{PROSE}\n",
        encoding="utf-8",
    )

    with pytest.raises(PreparationError) as excinfo:
        prepare_corpus(
            checkout_root=root, dest_root=tmp_path / "out", verify_revision=False
        )

    assert "was not found" in str(excinfo.value)
