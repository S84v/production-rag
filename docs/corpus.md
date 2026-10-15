# Corpus Provenance

## FastAPI Documentation Corpus

### Source

* **Project:** FastAPI
* **Repository:** https://github.com/fastapi/fastapi
* **Documentation:** https://fastapi.tiangolo.com/
* **Documentation source:** `docs/en/docs/` (Markdown), with code examples in
  `docs_src/` and referenced modules in `fastapi/`
* **License:** MIT
* **Pinned commit:** `244d66308d6c525f394d0c2ce32dabceb2ed262b`
* **Acquisition method:** pinned Git sparse checkout + deterministic preparation
* **Prepared corpus retrieval date:** 2026-10-15

### Why preparation is required

The upstream documentation is MkDocs source, not plain Markdown. Runnable
examples are not written inline; they are pulled in with include directives:

```text
{* ../../docs_src/path_params/tutorial001_py310.py hl[6:7] *}   # markdown_include_variants
{!../../docs_src/templates/templates/item.html!}                # mdx_include
```

The rendered documentation also contains content generated at build time
(API reference tables produced by mkdocstrings) that has no Markdown source.

Ingesting the upstream files verbatim therefore yields a corpus whose code
examples are missing and whose text contains build directives. That is the root
cause of the earlier ungrounded answer about path parameters: the prose was
retrievable, but the code example only existed in `docs_src` and was never
acquired.

`scripts/acquire_corpus.sh` performs a pinned sparse checkout and then runs
`production-rag prepare-corpus`, which:

* resolves every `{* ... *}` and `{! ... !}` include against the pinned
  checkout and replaces it with the referenced file's content (fenced when the
  directive stands alone; inlined when it is already inside a fence);
* normalises MkDocs-only syntax that has no meaning in plain Markdown
  (admonition markers, heading anchors, `<dfn>` tags, `{% raw %}` markers);
* drops `:::` mkdocstrings directives and excludes pages that consist of
  generated API reference only;
* fails loudly on unresolved includes, unsupported include target types, or
  unhandled MkDocs constructs instead of silently producing a lossy corpus.

Preparation is deterministic: running it twice produces byte-identical output.
Every path recorded in `.corpus-manifest.json` is validated before anything is
deleted; an entry that is absolute, traverses upwards, or resolves outside the
destination (including through a symlinked parent) aborts the run before any
stale-file cleanup or output write. A later run therefore removes only files it
previously wrote, and unrelated data is never deleted. The checkout's Git `HEAD`
is verified against the pinned revision before preparation, and the manifest
records the pin only when that verification succeeded.

### Selected documents

The corpus covers the English documentation for the user guide, advanced
topics, deployment, how-to guides, the reference pages that contain prose, and
the technical landing pages:

* `tutorial/**`
* `advanced/**`
* `deployment/**`
* `how-to/**`
* `reference/**` (only pages with substantive prose; see exclusions)
* `learn/index.md`
* `features.md`, `python-types.md`, `async.md`, `fastapi-cli.md`,
  `editor-support.md`, `environment-variables.md`, `virtual-environments.md`

At the pinned revision the preparation reports 135 documents, 446 expanded
include directives, and 290 unique snippet files.

### Excluded content and why

* **Generated API reference only** — pages such as `reference/encoders.md`,
  `reference/openapi/docs.md`, and `reference/openapi/models.md` contain nothing
  but `:::` mkdocstrings directives. The rendered tables are generated from
  Python docstrings at build time and are **not** part of the Markdown source, so
  they are excluded rather than ingested as empty content.
* **Templated landing page** — `index.md` is a sponsors/Jinja landing page with
  inline `<style>` and site flags.
* **Project and community pages** — `fastapi-people.md`, `help-fastapi.md`,
  `contributing.md`, `translations.md`, `newsletter.md`, `management.md`,
  `project-generation.md`, `external-links.md`, `translation-banner.md`, and the
  `about/` and `resources/` pages.
* **Non-documentation narrative** — `release-notes.md` (changelog),
  `benchmarks.md`, `alternatives.md`, `history-design-future.md`.
* **Test fixtures and assets** — `_llm-test.md`, `css/`, `js/`, `img/`, and all
  non-English languages.

The preparation report lists every exclusion with its reason.

### Corpus layout and `source_uri` stability

The destination directory is `data/raw/fastapi/`, and `source_uri` values are
derived from a file's path relative to that directory. The mapping is chosen so
the original tutorial `source_uri` values never change (evaluation labels are
scoped to them):

* `tutorial/<name>.md` → `<name>.md` (flattened; e.g. `filesystem://path-params.md`)
* `tutorial/<subdir>/**` → `<subdir>/**` (e.g. `filesystem://dependencies/index.md`)
* `advanced/**`, `deployment/**`, `how-to/**`, `reference/**` → same path
* other pages (for example `features.md`) → `guide/<name>.md`

### Reproducibility

```bash
./scripts/acquire_corpus.sh
```

The script clones the pinned revision as a blobless, sparse checkout of
`docs/en/docs/**`, `docs_src/**`, and `fastapi/**`, verifies the resolved
revision matches the pin, and then runs the preparation step. It requires `git`
and the project environment (`uv sync`). Re-running it is safe and
deterministic.

The raw corpus is intentionally excluded from Git; the acquisition and
preparation logic is versioned in `scripts/acquire_corpus.sh` and
`src/production_rag/corpus/preparation.py`.

### Evaluation labels

Retrieval labels reference this corpus by content, not by database identifier.
Each label anchors a `source_uri` relative to `data/raw/fastapi/` (for example
`filesystem://path-params.md`) to a verbatim snippet.

Expanding include directives changes document content and chunk boundaries, so
every anchor must be re-resolved after a corpus change. The offline check over
the local corpus (`tests/test_anchors.py`) and the corpus contract
(`tests/test_corpus_contract.py`) run in CI; a new baseline is recorded as a
dated artifact rather than overwriting the previous one.
