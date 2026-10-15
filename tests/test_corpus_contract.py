"""Contract tests for the prepared FastAPI corpus.

These run against the corpus produced by ``scripts/acquire_corpus.sh`` (the
pinned acquisition and preparation step, which CI runs before the test suite).
They are the deterministic regression guard for the original failure mode: the
corpus used to contain MkDocs include directives instead of the code examples,
so an answer could not be grounded even though the prose was retrievable.
"""

import json
import re
from pathlib import Path

import pytest

from production_rag.corpus.preparation import MANIFEST_NAME, PINNED_REVISION
from production_rag.ingestion.chunker import MarkdownChunker

CORPUS_DIR = Path("data/raw/fastapi")

# The 16 documents that were part of the original corpus. Their paths (and
# therefore their ``filesystem://`` source URIs) must stay stable so existing
# evaluation labels keep resolving.
ORIGINAL_DOCUMENTS = (
    "first-steps.md",
    "path-params.md",
    "path-params-numeric-validations.md",
    "query-params.md",
    "query-params-str-validations.md",
    "body.md",
    "body-fields.md",
    "body-nested-models.md",
    "response-model.md",
    "response-status-code.md",
    "dependencies/index.md",
    "dependencies/sub-dependencies.md",
    "handling-errors.md",
    "middleware.md",
    "security/first-steps.md",
    "security/oauth2-jwt.md",
)

# Examples that must be present as real code, not as include directives. This
# includes the path-parameter declaration example whose absence caused the
# original ungrounded answer.
REQUIRED_EXAMPLES = {
    "path-params.md": '@app.get("/items/{item_id}")',
    "first-steps.md": "app = FastAPI()",
    "dependencies/index.md": "Depends(",
    "handling-errors.md": "HTTPException",
    "middleware.md": "app.add_middleware(",
}

RESIDUAL_DIRECTIVE_PATTERNS = {
    "markdown_include_variants": re.compile(r"^\{\*", re.MULTILINE),
    "mdx_include": re.compile(r"^\{!", re.MULTILINE),
    "mkdocstrings": re.compile(r"^:::\s", re.MULTILINE),
    "admonition": re.compile(r"^///", re.MULTILINE),
    "heading_anchor": re.compile(r"\{\s*#", re.MULTILINE),
    "definition_tag": re.compile(r"<dfn", re.MULTILINE),
}


@pytest.fixture(scope="module")
def corpus_files() -> list[Path]:
    files = sorted(CORPUS_DIR.rglob("*.md"))
    assert files, "prepared FastAPI corpus is required for this test"
    return files


def test_original_documents_keep_their_paths() -> None:
    for relative in ORIGINAL_DOCUMENTS:
        assert (CORPUS_DIR / relative).is_file(), f"missing {relative}"


def test_corpus_is_meaningfully_larger_than_the_initial_subset(corpus_files) -> None:
    # The expansion covers tutorial, advanced, deployment, how-to, and reference.
    assert len(corpus_files) > len(ORIGINAL_DOCUMENTS) * 3

    for section in ("advanced", "deployment", "how-to", "reference"):
        assert list((CORPUS_DIR / section).rglob("*.md")), f"missing {section}/"


def test_no_unresolved_mkdocs_directives_remain(corpus_files) -> None:
    offenders: list[str] = []

    for path in corpus_files:
        text = path.read_text(encoding="utf-8")
        suffix = path.relative_to(CORPUS_DIR).as_posix()

        for name, pattern in RESIDUAL_DIRECTIVE_PATTERNS.items():
            if pattern.search(text):
                offenders.append(f"{suffix}: {name}")

    assert not offenders, f"unresolved MkDocs directives remain: {offenders}"


def test_required_code_examples_are_present() -> None:
    for relative, snippet in REQUIRED_EXAMPLES.items():
        text = (CORPUS_DIR / relative).read_text(encoding="utf-8")
        assert snippet in text, f"{relative} does not contain {snippet!r}"


def test_manifest_matches_the_prepared_files(corpus_files) -> None:
    manifest_path = CORPUS_DIR / MANIFEST_NAME
    assert manifest_path.is_file(), "preparation manifest is missing"

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["pinned_revision"] == PINNED_REVISION

    recorded = set(manifest["files"])
    on_disk = {path.relative_to(CORPUS_DIR).as_posix() for path in corpus_files}

    assert recorded == on_disk, "manifest does not match the prepared corpus"


def test_every_document_is_chunkable(corpus_files) -> None:
    chunker = MarkdownChunker()

    for path in corpus_files:
        chunks = chunker.chunk(path.read_text(encoding="utf-8"))

        assert chunks, f"no chunks produced for {path}"
        assert all(chunk.content.strip() for chunk in chunks), (
            f"empty chunk produced for {path}"
        )
