# ADR-006: Corpus Preparation and Vector-Store Consistency

- **Status:** Accepted
- **Date:** 2026-10-15

## Context

The retrieval corpus is the official FastAPI documentation, pinned to commit
`244d66308d6c525f394d0c2ce32dabceb2ed262b`. An evaluation case ("How do you
declare a path parameter in FastAPI?") produced an answer that admitted it
lacked the declaration syntax, even though `path-params.md` was in the corpus and
ranked first in retrieval.

Investigation showed the cause was not corpus size. The upstream documentation
is MkDocs source in which runnable examples are pulled in through include
directives (`{* ../../docs_src/... *}`, `{! ... !}`); the acquisition script
fetched only `docs/en/docs/tutorial/**/*.md`, so the code examples were never
part of the corpus. The existing evaluation label for that case anchored a prose
line, which was present and retrievable, so retrieval metrics passed while the
question was unanswerable.

Two further consistency problems existed:

* The local Qdrant `fastapi` collection contained 538 points while PostgreSQL
  held 209 embeddings for the collection. Read-only inspection classified all
  329 unmatched points as vectors belonging to other (integration-test)
  PostgreSQL collections that were written into the `fastapi` collection by
  tests that hardcoded `collection_name="fastapi"`. None were unbacked, and none
  were missing from the authoritative set.
* Re-ingesting a document whose content changed creates a new document version,
  while old versions' chunks and embeddings are retained. Runtime hydration did
  not filter to the latest version, but retrieval evaluation did, so runtime
  retrieval and evaluation could disagree about which content is current.

## Decision

**Corpus preparation.** The pinned corpus is acquired with a Git sparse checkout
of `docs/en/docs/**`, `docs_src/**`, and `fastapi/**`, then transformed by
`production_rag.corpus.preparation`:

* include directives are resolved against the pinned checkout and replaced with
  the referenced file content (fenced when the directive stands alone, inlined
  when it is already inside a fence);
* only referenced examples are expanded, so unreferenced `_py310`/`_an` variants
  do not create near-duplicate chunks;
* MkDocs-only syntax is normalised, and preparation fails on unresolved
  includes, unsupported include target types, or unhandled constructs;
* pages consisting only of generated `:::` API-reference directives are
  excluded, because the rendered tables are generated from Python docstrings and
  are not part of the Markdown source;
* the destination layout preserves the existing `source_uri` values for the
  original tutorial documents (tutorial is flattened; other sections are
  mirrored; remaining pages are namespaced under `guide/`).

Preparation is deterministic and records a manifest of the files it wrote. On
re-run it removes only files it previously wrote, after validating every recorded
path first: an entry that is absolute, traverses upwards, or resolves outside the
destination (including through a symlinked parent) aborts the run before anything
is written or deleted. The checkout's Git `HEAD` is verified against the pinned
revision before preparation, and the manifest records the pin only when that
verification succeeded.

**Authoritative vectors.** For a collection, the authoritative set is the set of
embedding records that (a) belong to a chunk of the latest version of a document
in that collection and (b) were produced by the active embedding model and
version. This rule is defined once (`RetrievalRepository._latest_version_ids`)
and shared by runtime hydration, retrieval evaluation, and reconciliation.

**Retrieval.** Runtime hydration filters to the latest document version, matching
evaluation. Superseded content can no longer be returned and cannot starve
retrieval once reconciliation has removed its vectors.

**Reconciliation.** `production-rag reconcile --collection <name>` reports drift
in four non-authoritative categories plus missing vectors:

| Category | Meaning |
| --- | --- |
| unbacked | Qdrant point with no PostgreSQL embedding record |
| superseded-version | embedding record exists but belongs to a non-latest version |
| inactive-model | embedding exists for the latest version but a different model/version |
| foreign-collection | embedding belongs to a different collection |
| missing | authoritative embedding id with no Qdrant point |

It defaults to a read-only dry run. With `--apply` it revalidates the
authoritative set immediately before deleting and removes only point ids that
are proven non-authoritative, in bounded batches, within the named collection.
It never deletes PostgreSQL records and never touches another collection.
Missing vectors are reported for repair by ingestion, never created by
reconciliation.

**Ingestion.** Per chunk, ingestion skips encoding only when both the expected
embedding record and its Qdrant point exist. With a record but no point it
re-encodes and upserts using the existing embedding id, without creating a
duplicate record. Outcomes are reported separately as persisted, repaired, and
skipped.

## Rationale

Expanding includes at acquisition time keeps the ingestion chunker generic
(ADR-003) and keeps the transformation deterministic and offline-testable.

Defining the authoritative set once avoids the runtime/evaluation divergence
that appears as soon as a document is re-ingested with changed content.

Distinguishing the drift categories lets the operator see the actual cause
(for example vectors leaked by tests) instead of assuming "orphans", and lets
deletion be proven-safe rather than heuristic.

## Consequences

The corpus is larger (135 documents at the pinned revision), so ingestion grows
accordingly; embedding runs locally and costs no API calls.

Evaluation labels are content anchors and must be re-resolved whenever the corpus
changes; the offline anchor and corpus-contract tests enforce this in CI.

Superseded versions and their PostgreSQL embedding rows are retained for
history; their vectors are removed by reconciliation, and re-encoding can
recreate them if ever needed.

Tests that previously wrote into the shared `fastapi` Qdrant collection now use
an in-memory Qdrant double, so the corpus collection is no longer polluted by
test runs.
