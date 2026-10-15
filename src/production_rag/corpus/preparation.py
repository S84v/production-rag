"""Deterministic preparation of the pinned FastAPI documentation corpus.

The upstream documentation is authored for MkDocs: runnable examples live in
``docs_src`` and ``fastapi`` and are pulled into the Markdown through include
directives, and MkDocs-specific syntax is used for admonitions, heading
anchors, and generated API reference.

Ingestion needs plain Markdown, so this module performs a deterministic,
offline transformation:

* ``{* <path> <options> *}`` (``markdown_include_variants``) and
  ``{!<path>!}`` / ``{!> <path>!}`` (``mdx_include``) are replaced by the
  referenced file content. A directive on its own line becomes a fenced code
  block; a directive already inside a fence is inlined so the surrounding fence
  keeps providing the code block.
* ``:::` (mkdocstrings) lines are dropped; pages that contain nothing else are
  excluded, because the rendered API tables are generated from Python
  docstrings at build time and are not part of the Markdown source.
* MkDocs-only syntax with no meaning in plain Markdown is normalised.

Constructs that cannot be handled safely raise :class:`PreparationError`
instead of silently producing a lossy corpus. Transformations are skipped
inside fenced code blocks so example code is never rewritten.

Include paths are written for the MkDocs build, where the staged stage root
contains both ``docs_src`` and the language directory. In a source checkout the
equivalent target is the repository root, so a path such as
``../../docs_src/x.py`` resolves to ``<checkout>/docs_src/x.py``.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

PINNED_REVISION = "244d66308d6c525f394d0c2ce32dabceb2ed262b"

MANIFEST_NAME = ".corpus-manifest.json"

DOCS_SUBDIR = Path("docs/en/docs")

# Documentation sections that mirror their upstream directory name.
SECTION_DIRECTORIES = ("advanced", "deployment", "how-to", "reference")

# ``tutorial`` is flattened to the corpus root so existing evaluation labels
# (``filesystem://path-params.md``) and ``source_uri`` values stay stable.
FLATTENED_DIRECTORY = "tutorial"

# Non-section pages are namespaced under ``guide`` to avoid collisions with the
# flattened tutorial pages (for example ``tutorial/index.md`` vs ``index.md``).
GUIDE_DIRECTORY = "guide"

INCLUDED_ROOT_PAGES = (
    "features.md",
    "python-types.md",
    "async.md",
    "fastapi-cli.md",
    "editor-support.md",
    "environment-variables.md",
    "virtual-environments.md",
)

INCLUDED_EXTRA_PAGES = ("learn/index.md",)

# Pages excluded deliberately, keyed by their path relative to ``docs/en/docs``.
EXCLUDED_PAGES: dict[str, str] = {
    "_llm-test.md": "translation test fixture, not documentation",
    "translation-banner.md": "translation banner fragment",
    "fastapi-people.md": "project/community page",
    "help-fastapi.md": "project/community page",
    "contributing.md": "project/community page",
    "translations.md": "project/community page",
    "newsletter.md": "project/community page",
    "management.md": "project/community page",
    "release-notes.md": "changelog, not documentation",
    "benchmarks.md": "project narrative, not API documentation",
    "alternatives.md": "project narrative, not API documentation",
    "history-design-future.md": "project narrative, not API documentation",
    "project-generation.md": "project/community page",
    "external-links.md": "curated third-party link list",
    "index.md": "templated landing page (Jinja sponsors blocks, <style>, site flags)",
}

# Ordered alternation is unnecessary: a line matches at most one directive form.
CODE_INCLUDE_RE = re.compile(r"^\{\*\s*(\S+)\s*(.*?)\s*\*\}$")
MDX_INCLUDE_RE = re.compile(r"^\{!(?:>)?\s*(\S+?)\s*!\}$")
INCLUDE_RE = re.compile(
    r"^(?:\{\*\s*(?P<star>\S+)\s*(?:.*?)\s*\*\}"
    r"|\{!(?:>)?\s*(?P<mdx>\S+?)\s*!\})$"
)

FENCE_RE = re.compile(r"^\s*(?:```|~~~)")
ADMONITION_RE = re.compile(r"^///.*$")
MKDOCSTRINGS_RE = re.compile(r"^:::\s*\S*.*$")
HEADING_ANCHOR_RE = re.compile(r"^(#{1,6}\s+.*?)\s*\{\s*#.*?\}\s*$")
DEFINITION_TAG_RE = re.compile(r"<dfn[^>]*>(.*?)</dfn>", re.DOTALL)
JINJA_RAW_RE = re.compile(r"^\s*\{%\s*(?:end)?raw\s*%\}\s*$")
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)

# Constructs that are not handled and must fail loudly rather than be mangled.
UNSUPPORTED_CONSTRUCTS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r'^===\s+"'),
        'content tab ("=== \\"Title\\"") is not handled by the corpus '
        "preparation; extend production_rag.corpus.preparation",
    ),
    (
        re.compile(r"^\s*\{%"),
        "Jinja block directive is not handled by the corpus preparation "
        "(only {% raw %} / {% endraw %} markers are stripped)",
    ),
    (
        re.compile(r"\{\{"),
        "Jinja expression is not handled by the corpus preparation",
    ),
    (
        re.compile(r"^!!!\s"),
        "bang-style admonition is not handled by the corpus preparation",
    ),
    (
        re.compile(r"^--8<--"),
        "pymdownx snippet macro is not handled by the corpus preparation",
    ),
)

LANGUAGE_BY_SUFFIX: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".mjs": "javascript",
    ".ts": "typescript",
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".sql": "sql",
    ".sh": "bash",
    ".bash": "bash",
    ".ini": "ini",
    ".cfg": "ini",
    ".txt": "text",
    ".md": "markdown",
}

# A page whose normalised content has fewer prose words than this is treated as
# generated API reference only and is excluded.
MIN_PROSE_WORDS = 20

WORD_RE = re.compile(r"[A-Za-z]{3,}")
FENCED_BLOCK_RE = re.compile(r"```.*?```", re.DOTALL)

IncludeLoader = Callable[[str], tuple[Path, str]]


class PreparationError(RuntimeError):
    """Raised when the corpus cannot be prepared without losing fidelity."""

    def __init__(self, problems: Iterable[str]) -> None:
        self.problems = list(problems)
        super().__init__(
            "Corpus preparation failed:\n"
            + "\n".join(f"  - {problem}" for problem in self.problems)
        )


@dataclass
class ExcludedPage:
    path: str
    reason: str


@dataclass
class PreparationReport:
    documents: int = 0
    directives: int = 0
    snippets: int = 0
    bytes_written: int = 0
    excluded: list[ExcludedPage] = field(default_factory=list)
    snippet_suffixes: dict[str, int] = field(default_factory=dict)
    # Recorded only when the checkout revision was verified, so the manifest
    # never claims a pin the checkout was not checked against.
    checkout_revision: str | None = None

    def summary(self) -> str:
        lines = [
            f"checkout revision: {self.checkout_revision or 'unverified'}",
            f"documents prepared: {self.documents}",
            f"include directives expanded: {self.directives}",
            f"unique snippet files: {self.snippets}",
            f"bytes written: {self.bytes_written}",
            "snippet target types: "
            + ", ".join(
                f"{suffix}={count}"
                for suffix, count in sorted(self.snippet_suffixes.items())
            ),
            f"excluded pages: {len(self.excluded)}",
        ]
        lines.extend(
            f"  - {excluded.path}: {excluded.reason}" for excluded in self.excluded
        )
        return "\n".join(lines)


def _strip_leading_parents(target: str) -> str:
    stripped = target
    while stripped.startswith("../"):
        stripped = stripped[3:]
    return stripped


def verify_checkout_revision(
    checkout_root: Path,
    *,
    expected_revision: str = PINNED_REVISION,
) -> str:
    """Return the checkout's Git ``HEAD``, or raise :class:`PreparationError`.

    Reads the revision locally (``git rev-parse HEAD``); no network access is
    performed. Failing here prevents preparing (and recording a manifest for) a
    checkout that is not the pinned revision.
    """

    checkout_root = checkout_root.resolve()

    try:
        result = subprocess.run(
            ["git", "-C", str(checkout_root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except FileNotFoundError as error:
        raise PreparationError(
            [
                "git executable not found; a Git checkout is required to verify "
                "the pinned revision"
            ]
        ) from error
    except (OSError, subprocess.SubprocessError) as error:
        raise PreparationError(
            [f"failed to read the Git revision of {checkout_root}: {error}"]
        ) from error

    if result.returncode != 0:
        stderr = (result.stderr or "").strip()

        if "not a git repository" in stderr.lower():
            raise PreparationError(
                [
                    f"{checkout_root} is not a Git checkout: "
                    f"{stderr or 'no repository found'}"
                ]
            )

        raise PreparationError(
            [
                f"failed to read the Git revision of {checkout_root}: "
                f"{stderr or 'git rev-parse HEAD failed'}"
            ]
        )

    revision = result.stdout.strip()

    if not revision:
        raise PreparationError(
            [f"failed to read the Git revision of {checkout_root}: empty output"]
        )

    if revision != expected_revision:
        raise PreparationError(
            [
                f"{checkout_root} is at revision {revision}, expected the pinned "
                f"revision {expected_revision}"
            ]
        )

    return revision


def resolve_include(
    *,
    checkout_root: Path,
    docs_root: Path,
    document: Path,
    target: str,
) -> Path:
    """Resolve an include target to exactly one file inside the checkout.

    MkDocs stages the documentation so that the stage root contains both
    ``docs_src`` and the language directory, which makes ``../../docs_src/...``
    resolve against the repository root in a source checkout.
    """

    checkout_root = checkout_root.resolve()
    candidates = (
        document.parent / target,
        docs_root / target,
        checkout_root / _strip_leading_parents(target),
    )

    resolved: list[Path] = []
    for candidate in candidates:
        try:
            path = candidate.resolve()
        except OSError:
            continue
        if path not in resolved and path.is_file():
            resolved.append(path)

    if len(resolved) == 1:
        path = resolved[0]
        if not path.is_relative_to(checkout_root):
            raise PreparationError(
                [
                    f"include target {target!r} resolves outside the checkout ({path})",
                ]
            )
        return path

    if not resolved:
        raise PreparationError(
            [
                f"include target {target!r} was not found; tried "
                + ", ".join(str(candidate) for candidate in candidates),
            ]
        )

    raise PreparationError(
        [
            f"include target {target!r} is ambiguous; matched "
            + ", ".join(str(path) for path in resolved),
        ]
    )


def _render_code_block(content: str, language: str) -> str:
    body = content.strip("\n")
    fence = "```"
    while any(line.startswith(fence) for line in body.splitlines()):
        fence += "`"
    return f"{fence}{language}\n{body}\n{fence}"


def _language_for(path: Path, directive: str) -> str:
    language = LANGUAGE_BY_SUFFIX.get(path.suffix.lower())
    if language is None:
        raise PreparationError(
            [
                f"unsupported include target type {path.suffix!r} for directive "
                f"{directive!r} ({path}); add a language mapping in "
                "production_rag.corpus.preparation or exclude the document",
            ]
        )
    return language


def expand_includes(
    text: str,
    *,
    load: IncludeLoader,
    report: PreparationReport | None = None,
) -> str:
    """Replace include directives with the referenced file content."""

    output: list[str] = []
    fenced = False

    for line in text.split("\n"):
        if FENCE_RE.match(line):
            fenced = not fenced
            output.append(line)
            continue

        match = INCLUDE_RE.match(line)

        if match is None:
            output.append(line)
            continue

        target = match.group("star") or match.group("mdx")
        path, content = load(target)

        if report is not None:
            report.directives += 1
            suffix = path.suffix.lower()
            report.snippet_suffixes[suffix] = report.snippet_suffixes.get(suffix, 0) + 1

        if fenced:
            # The surrounding fence already provides the code block.
            output.append(content.strip("\n"))
        else:
            output.append(_render_code_block(content, _language_for(path, line)))

    return "\n".join(output)


def normalize_markdown(text: str) -> str:
    """Remove MkDocs-only syntax that has no meaning in plain Markdown."""

    lines: list[str] = []
    fenced = False

    for line in text.split("\n"):
        if FENCE_RE.match(line):
            fenced = not fenced
            lines.append(line)
            continue

        if not fenced:
            # Known-benign markers are handled before the unsupported-construct
            # checks so that {% raw %} is not reported as an unhandled directive.
            if JINJA_RAW_RE.match(line):
                continue

            for pattern, message in UNSUPPORTED_CONSTRUCTS:
                if pattern.search(line):
                    raise PreparationError(
                        [f"unsupported MkDocs construct in {line!r}: {message}"]
                    )

            if ADMONITION_RE.match(line):
                continue
            if MKDOCSTRINGS_RE.match(line):
                continue

            heading = HEADING_ANCHOR_RE.match(line)
            if heading is not None:
                line = heading.group(1)

            line = DEFINITION_TAG_RE.sub(r"\1", line)

        lines.append(line)

    text = "\n".join(lines)
    text = HTML_COMMENT_RE.sub("", text)
    text = re.sub(r"[ \t]+$", "", text, flags=re.MULTILINE)
    return re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"


def prose_word_count(text: str) -> int:
    without_code = FENCED_BLOCK_RE.sub("", text)
    return len(WORD_RE.findall(without_code))


def relative_destination(relative_path: Path) -> Path:
    """Map a ``docs/en/docs`` relative path to its corpus destination."""

    parts = relative_path.parts

    if parts[0] == FLATTENED_DIRECTORY:
        return Path(*parts[1:])

    if parts[0] in SECTION_DIRECTORIES:
        return relative_path

    return Path(GUIDE_DIRECTORY) / relative_path


def select_documents(docs_root: Path) -> tuple[list[Path], list[ExcludedPage]]:
    """Return the selected Markdown files and the exclusions with reasons."""

    selected: list[Path] = []

    for section in (FLATTENED_DIRECTORY, *SECTION_DIRECTORIES):
        selected.extend(sorted((docs_root / section).rglob("*.md")))

    for relative in (*INCLUDED_EXTRA_PAGES, *INCLUDED_ROOT_PAGES):
        candidate = docs_root / relative
        if candidate.is_file():
            selected.append(candidate)

    excluded: list[ExcludedPage] = []
    kept: list[Path] = []

    for path in sorted(set(selected)):
        relative = path.relative_to(docs_root).as_posix()
        reason = EXCLUDED_PAGES.get(relative)
        if reason is not None:
            excluded.append(ExcludedPage(relative, reason))
            continue
        kept.append(path)

    # Report deliberate exclusions that were never part of the positive
    # selection so the reason is still visible in the preparation report.
    reported = {item.path for item in excluded}
    for relative, reason in sorted(EXCLUDED_PAGES.items()):
        if relative in reported:
            continue
        if (docs_root / relative).is_file():
            excluded.append(ExcludedPage(relative, reason))

    return kept, excluded


def prepare_corpus(
    *,
    checkout_root: Path,
    dest_root: Path,
    docs_root: Path | None = None,
    verify_revision: bool = True,
) -> PreparationReport:
    """Prepare the corpus and write it under ``dest_root``.

    Only files recorded in the previous run's manifest are ever removed, so
    unrelated data under ``dest_root`` is preserved.

    Unless ``verify_revision`` is disabled (used by tests with synthetic
    checkouts), the checkout's Git ``HEAD`` must equal :data:`PINNED_REVISION`
    before anything is written, and only then does the manifest record the pin.
    """

    checkout_root = checkout_root.resolve()
    docs_root = (docs_root or checkout_root / DOCS_SUBDIR).resolve()
    dest_root = dest_root.resolve()

    checkout_revision: str | None = None
    if verify_revision:
        checkout_revision = verify_checkout_revision(checkout_root)

    if not docs_root.is_dir():
        raise PreparationError([f"documentation directory not found: {docs_root}"])

    documents, excluded = select_documents(docs_root)

    report = PreparationReport(
        excluded=excluded,
        checkout_revision=checkout_revision,
    )
    problems: list[str] = []
    outputs: dict[Path, str] = {}
    snippets: set[Path] = set()

    for document in documents:
        relative = document.relative_to(docs_root)

        try:

            def load(target: str, _document: Path = document) -> tuple[Path, str]:
                path = resolve_include(
                    checkout_root=checkout_root,
                    docs_root=docs_root,
                    document=_document,
                    target=target,
                )
                snippets.add(path)
                return path, path.read_text(encoding="utf-8")

            expanded = expand_includes(
                document.read_text(encoding="utf-8"),
                load=load,
                report=report,
            )
            normalized = normalize_markdown(expanded)

            if prose_word_count(normalized) < MIN_PROSE_WORDS:
                report.excluded.append(
                    ExcludedPage(
                        str(relative),
                        "generated API reference only (no substantive prose once "
                        "mkdocstrings directives are removed)",
                    )
                )
                continue

            outputs[relative_destination(relative)] = normalized
        except PreparationError as error:
            problems.extend(f"{relative}: {problem}" for problem in error.problems)

    if problems:
        raise PreparationError(problems)

    report.documents = len(outputs)
    report.snippets = len(snippets)

    _write_outputs(dest_root, outputs, report)

    return report


def _read_manifest(manifest_path: Path) -> list[str]:
    """Read the recorded file list, failing loudly on an unreadable manifest.

    A manifest that cannot be trusted must stop preparation rather than silently
    discard the "only remove what we wrote" guarantee.
    """

    if not manifest_path.is_file():
        return []

    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as error:
        raise PreparationError(
            [
                f"cannot read {MANIFEST_NAME}: {error}; remove or repair "
                f"{manifest_path} before preparing the corpus"
            ]
        ) from error

    if not isinstance(data, dict):
        raise PreparationError([f"{MANIFEST_NAME} must contain a JSON object"])

    files = data.get("files")

    if not isinstance(files, list) or not all(
        isinstance(entry, str) for entry in files
    ):
        raise PreparationError(
            [f"{MANIFEST_NAME} 'files' must be a list of relative paths"]
        )

    return files


_ABSOLUTE_OR_DRIVE_RE = re.compile(r"^(?:[A-Za-z]:|[\\/])")
_PATH_SEPARATOR_RE = re.compile(r"[\\/]+")


def _validate_relative_path(raw: object, *, role: str) -> Path:
    """Return a safe destination-relative path, or raise :class:`PreparationError`.

    Absolute paths, Windows drive prefixes, and any ``..`` component are
    rejected so a manifest entry can never point outside the destination.
    """

    if not isinstance(raw, str) or not raw.strip():
        raise PreparationError(
            [f"invalid {role} entry {raw!r}: expected a non-empty relative path"]
        )

    candidate = raw.strip()

    if _ABSOLUTE_OR_DRIVE_RE.match(candidate):
        raise PreparationError(
            [f"invalid {role} entry {raw!r}: absolute paths are not allowed"]
        )

    parts = [
        part for part in _PATH_SEPARATOR_RE.split(candidate) if part not in ("", ".")
    ]

    if not parts:
        raise PreparationError([f"invalid {role} entry {raw!r}: not a file path"])

    if ".." in parts:
        raise PreparationError(
            [f"invalid {role} entry {raw!r}: parent traversal ('..') is not allowed"]
        )

    return Path(*parts)


def _resolve_within(dest_root: Path, relative: Path) -> Path:
    """Resolve ``relative`` under ``dest_root`` and reject escapes.

    ``Path.resolve`` follows existing symlinks, so a symlinked parent directory
    that points outside the destination is rejected as well.
    """

    resolved = (dest_root / relative).resolve()

    if not resolved.is_relative_to(dest_root):
        raise PreparationError(
            [
                f"refusing to touch {relative.as_posix()!r}: it resolves outside "
                f"the destination {dest_root}"
            ]
        )

    return resolved


def _validate_manifest_path(dest_root: Path, manifest_path: Path) -> None:
    """Reject a manifest path that could read or write outside the destination.

    The manifest is read at the start of every run and rewritten at the end, so a
    ``.corpus-manifest.json`` symbolic link would follow an external file in both
    directions. It is refused before the manifest is read or anything is mutated.
    """

    if manifest_path.is_symlink():
        raise PreparationError(
            [
                f"refusing to use {MANIFEST_NAME} at {manifest_path}: it is a "
                "symbolic link, which could read or overwrite a file outside the "
                f"destination {dest_root}; remove the link before preparing the "
                "corpus"
            ]
        )

    if _resolve_within(dest_root, Path(MANIFEST_NAME)) != manifest_path:
        raise PreparationError(
            [
                f"refusing to use {MANIFEST_NAME} at {manifest_path}: it does not "
                f"resolve inside the destination {dest_root}"
            ]
        )


def _write_outputs(
    dest_root: Path,
    outputs: dict[Path, str],
    report: PreparationReport,
) -> None:
    dest_root = dest_root.resolve()
    manifest_path = dest_root / MANIFEST_NAME

    # The manifest is read first and rewritten last, so its own path must be
    # validated before either happens (and before any prepared output changes).
    _validate_manifest_path(dest_root, manifest_path)

    previously_written = _read_manifest(manifest_path)
    new_files = {path.as_posix() for path in outputs}

    # Validate every path before mutating anything. A manifest entry that is
    # absolute, traverses upwards, or resolves outside the destination (including
    # through a symlinked parent) aborts the run instead of deleting files.
    problems: list[str] = []

    validated_outputs: list[tuple[Path, str]] = []
    for relative, text in outputs.items():
        try:
            checked = _validate_relative_path(
                relative.as_posix(), role="prepared document"
            )
            validated_outputs.append((_resolve_within(dest_root, checked), text))
        except PreparationError as error:
            problems.extend(error.problems)

    stale_targets: list[Path] = []
    for raw in sorted(set(previously_written)):
        try:
            checked = _validate_relative_path(raw, role="manifest file")
            resolved = _resolve_within(dest_root, checked)
        except PreparationError as error:
            problems.extend(error.problems)
            continue

        if checked.as_posix() not in new_files:
            stale_targets.append(resolved)

    if problems:
        raise PreparationError(problems)

    # Only files recorded in the previous manifest are removed, so unrelated
    # data under the destination is preserved.
    for target in stale_targets:
        if target.is_file():
            target.unlink()

    total_bytes = 0
    for target, text in validated_outputs:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        total_bytes += len(text.encode("utf-8"))

    report.bytes_written = total_bytes

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(
            {
                "pinned_revision": report.checkout_revision,
                "files": sorted(new_files),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="production-rag prepare-corpus",
        description=(
            "Expand MkDocs include directives in the pinned FastAPI "
            "documentation and write a plain-Markdown corpus."
        ),
    )
    parser.add_argument(
        "--checkout",
        type=Path,
        required=True,
        help="path to the pinned FastAPI source checkout",
    )
    parser.add_argument(
        "--dest",
        type=Path,
        default=Path("data/raw/fastapi"),
        help="destination directory for the prepared corpus",
    )

    args = parser.parse_args(argv)

    try:
        report = prepare_corpus(checkout_root=args.checkout, dest_root=args.dest)
    except PreparationError as error:
        print(str(error), file=sys.stderr)
        return 1

    print(report.summary())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
