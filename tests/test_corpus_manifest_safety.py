"""Manifest cleanup must never delete or overwrite files outside the destination.

The preparation step removes files recorded in the previous run's
``.corpus-manifest.json``. These tests prove that a malformed or malicious
manifest cannot escape the destination directory, while the existing guarantee
(only previously manifested generated files are removed) still holds.
"""

import json
from pathlib import Path

import pytest

from production_rag.corpus.preparation import (
    MANIFEST_NAME,
    PreparationError,
    prepare_corpus,
)
from tests.helpers.corpus import build_checkout


def write_manifest(dest: Path, files: object) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    (dest / MANIFEST_NAME).write_text(
        json.dumps({"pinned_revision": None, "files": files}),
        encoding="utf-8",
    )


def run_prepare(root: Path, dest: Path) -> None:
    prepare_corpus(checkout_root=root, dest_root=dest, verify_revision=False)


def make_sentinel(outside: Path) -> Path:
    outside.mkdir(parents=True, exist_ok=True)
    sentinel = outside / "sentinel.txt"
    sentinel.write_text("keep me", encoding="utf-8")
    return sentinel


def test_absolute_manifest_entry_is_rejected(tmp_path: Path) -> None:
    root = build_checkout(tmp_path)
    sentinel = make_sentinel(tmp_path / "outside")
    dest = tmp_path / "out"
    write_manifest(dest, [str(sentinel)])

    with pytest.raises(PreparationError) as excinfo:
        run_prepare(root, dest)

    assert "absolute paths are not allowed" in str(excinfo.value)
    assert sentinel.read_text(encoding="utf-8") == "keep me"
    assert not (dest / "example.md").exists()


def test_parent_traversal_manifest_entry_is_rejected(tmp_path: Path) -> None:
    root = build_checkout(tmp_path)
    sentinel = make_sentinel(tmp_path / "outside")
    dest = tmp_path / "out"
    write_manifest(dest, ["../outside/sentinel.txt"])

    with pytest.raises(PreparationError) as excinfo:
        run_prepare(root, dest)

    assert "parent traversal" in str(excinfo.value)
    assert sentinel.read_text(encoding="utf-8") == "keep me"
    assert not (dest / "example.md").exists()


def test_symlinked_parent_escape_is_rejected(tmp_path: Path) -> None:
    root = build_checkout(tmp_path)
    sentinel = make_sentinel(tmp_path / "outside")
    dest = tmp_path / "out"
    dest.mkdir(parents=True)
    (dest / "link").symlink_to(sentinel.parent, target_is_directory=True)

    write_manifest(dest, ["link/sentinel.txt"])

    with pytest.raises(PreparationError) as excinfo:
        run_prepare(root, dest)

    assert "resolves outside" in str(excinfo.value)
    assert sentinel.read_text(encoding="utf-8") == "keep me"
    assert (dest / "link").is_symlink()
    assert not (dest / "example.md").exists()


def test_symlinked_manifest_is_rejected_before_it_is_read(tmp_path: Path) -> None:
    root = build_checkout(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()

    # The link target is a valid manifest naming a file in the destination: if
    # the link were followed, that entry would be treated as stale and deleted.
    sentinel = outside / "manifest-target.json"
    sentinel_contents = json.dumps({"pinned_revision": None, "files": ["survive.md"]})
    sentinel.write_text(sentinel_contents, encoding="utf-8")

    dest = tmp_path / "out"
    dest.mkdir()
    (dest / "survive.md").write_text("survive", encoding="utf-8")
    (dest / "existing.md").write_text("existing", encoding="utf-8")
    (dest / MANIFEST_NAME).symlink_to(sentinel)

    with pytest.raises(PreparationError) as excinfo:
        run_prepare(root, dest)

    message = str(excinfo.value)
    assert "symbolic link" in message
    # A read through the link would have produced a different error/behaviour.
    assert "cannot read" not in message

    assert sentinel.read_text(encoding="utf-8") == sentinel_contents
    assert (dest / MANIFEST_NAME).is_symlink()
    assert (dest / "survive.md").read_text(encoding="utf-8") == "survive"
    assert (dest / "existing.md").read_text(encoding="utf-8") == "existing"
    assert not (dest / "example.md").exists()


def test_manifest_with_non_string_entries_is_rejected(tmp_path: Path) -> None:
    root = build_checkout(tmp_path)
    dest = tmp_path / "out"
    write_manifest(dest, [123])

    with pytest.raises(PreparationError) as excinfo:
        run_prepare(root, dest)

    assert "list of relative paths" in str(excinfo.value)


def test_corrupt_manifest_fails_before_overwriting_prepared_files(
    tmp_path: Path,
) -> None:
    root = build_checkout(tmp_path)
    dest = tmp_path / "out"
    dest.mkdir()
    (dest / MANIFEST_NAME).write_text("{not json", encoding="utf-8")
    (dest / "example.md").write_text("previously prepared", encoding="utf-8")

    with pytest.raises(PreparationError) as excinfo:
        run_prepare(root, dest)

    assert "cannot read" in str(excinfo.value)
    assert (dest / "example.md").read_text(encoding="utf-8") == "previously prepared"


def test_invalid_entry_prevents_all_deletion_and_writing(tmp_path: Path) -> None:
    root = build_checkout(tmp_path)
    dest = tmp_path / "out"
    dest.mkdir()
    (dest / "stale.md").write_text("stale", encoding="utf-8")

    # One valid stale entry and one invalid entry: the run must abort before
    # either deletion or writing.
    write_manifest(dest, ["stale.md", "..\\escape.md"])

    with pytest.raises(PreparationError):
        run_prepare(root, dest)

    assert (dest / "stale.md").exists()
    assert not (dest / "example.md").exists()


def test_only_previously_manifested_files_are_removed(tmp_path: Path) -> None:
    root = build_checkout(tmp_path)
    dest = tmp_path / "out"
    dest.mkdir()
    (dest / "stale.md").write_text("stale", encoding="utf-8")
    (dest / "unrelated.txt").write_text("unrelated", encoding="utf-8")

    write_manifest(dest, ["stale.md", "example.md"])

    run_prepare(root, dest)

    assert not (dest / "stale.md").exists()
    assert (dest / "unrelated.txt").read_text(encoding="utf-8") == "unrelated"
    assert (dest / "example.md").is_file()

    manifest = json.loads((dest / MANIFEST_NAME).read_text(encoding="utf-8"))
    assert "example.md" in manifest["files"]
    assert "stale.md" not in manifest["files"]
