# Session Handoff

_Current-state snapshot (2026-10-16). Rewrite stale sections; do not append
history. Not a changelog, task plan, or recommendation list. Use exact
paths/identifiers; never include secrets; never claim unobserved verification._

## Repository State

- Branch `main`, HEAD `3371c82` (`feat: expand DocAssist corpus and reconcile
  vector consistency`), matching the tracked `origin/main` ref
  (`rev-list --left-right --count` → `0 0`). Working tree clean except this
  `SESSION_HANDOFF.md` rewrite (not staged).
- Recent commits: `3371c82` (pinned corpus preparation, vector-store
  reconciliation, ingestion skip/repair, latest-version retrieval filter,
  evaluation dataset + retrieval baseline); `c365fbd` (DocAssist frontend
  redesign); `35d5755` (handoff); earlier public-API hardening and hosted
  PostgreSQL/Qdrant configuration commits precede those.

## Project State

DocAssist (`production-rag`) is a RAG portfolio demo: a FastAPI service answers
questions grounded in retrieved FastAPI documentation, backed by PostgreSQL
(authoritative metadata/chunks) and Qdrant (vectors),
`BAAI/bge-small-en-v1.5` embeddings, DeepSeek generation, and a
React/TypeScript/Vite frontend (product name **DocAssist**); managed with `uv`.
Implemented stages: local vertical slice, CI, backend container image, the DocAssist
frontend redesign, public-API safeguards, pinned corpus preparation, vector-store
reconciliation, and a recorded anchor-based retrieval baseline. **Firebase/Cloud
Run deployment is not configured in-repo**; hosting is intended, not
implemented/verified. Per `AGENTS.md`, verify current status before asserting.

## Implemented State

- Ingestion: Markdown → SHA-256 → structure-aware chunking (`max_characters=4000`)
  → PostgreSQL → embeddings → Qdrant; idempotent, versioned documents; embedding
  work skipped when the record and Qdrant point both exist, repaired (same
  embedding id) when only the point is missing.
- Retrieval: embedding → Qdrant search → PostgreSQL hydration, scoped by collection
  and filtered to the latest document version (same rule as evaluation).
- API: NDJSON `POST /query` (`sources` → `text`* → one terminal `complete`/`error`);
  `404` for disallowed/nonexistent collections; shallow `GET /health`. Generation:
  DeepSeek Responses API, bounded output, terminal `error` on failure.
- Corpus: pinned FastAPI docs acquired by pinned Git sparse checkout and prepared by
  expanding MkDocs includes (ADR-006). Reconciliation: collection-scoped drift report
  (dry-run default) with `--apply` for provably non-authoritative Qdrant points.
- CLI: `production-rag ingest|query|prepare-corpus|reconcile`.
- Frontend: DocAssist SPA (Ask/About/Project), system-only theme, Markdown answers
  (`react-markdown` + `remark-gfm`, no raw HTML), full-width answer box with a 72ch
  reading measure, footer contact links, Vitest + Testing Library suite.
- CI: backend Ruff + pinned corpus acquisition/preparation + service-free tests on
  CPU-only PyTorch; frontend `npm ci` → `lint` → `test` → `build`.

## Current Implementation Details

- Layout: `src/production_rag/{api,core,corpus,db,ingestion,models,repositories,schemas,services,evaluation,telemetry.py,main.py}`,
  `alembic/versions/`, `tests/`, `frontend/`, `docs/{adr,corpus.md,evaluation,deployment.md,images}`,
  `data/{raw,evaluation,tmp}`, `.github/workflows/ci.yml`, `scripts/acquire_corpus.sh`,
  `docker-compose.yml`, `Dockerfile`, `pyproject.toml`, `uv.lock`.
- Corpus preparation: `src/production_rag/corpus/preparation.py`, pinned revision
  `244d66308d6c525f394d0c2ce32dabceb2ed262b`. `{* path *}` and `{!path!}` includes
  expand to fenced code (inlined inside an existing fence); `:::`, `///`,
  `{ #anchor }`, `<dfn>`, `{% raw %}` are normalised; preparation fails on
  unresolved includes, unsupported target types, or unhandled constructs (content
  tabs, Jinja blocks/expressions, `!!!`, `--8<--`). `tutorial/**` is flattened to
  the corpus root, other sections mirrored, remaining pages under `guide/`.
  `.corpus-manifest.json` records outputs; every recorded and generated path is
  validated (absolute, `..`, or anything resolving outside the destination —
  including through a symlinked parent — aborts before any deletion or write) and a
  symlinked manifest is refused before it is read.
  `prepare_corpus(verify_revision=True)` verifies the checkout's Git `HEAD` against
  the pin before writing, and the manifest records the pin only then. Output is
  byte-deterministic.
- `scripts/acquire_corpus.sh` clones a blobless sparse checkout of
  `docs/en/docs/**`, `docs_src/**`, `fastapi/**` into `data/tmp/fastapi-checkout`
  (gitignored), verifies the revision, then runs `uv run production-rag
  prepare-corpus`.
- Authoritative vector set: `RetrievalRepository._latest_version_ids()` defines the
  latest version per document; shared by `list_collection_chunks`,
  `find_chunks_by_embedding_ids`, `authoritative_embedding_ids`, and
  `classify_embeddings`.
- Reconciliation: `services/reconciliation.py` categories are `unbacked`,
  `superseded_version`, `inactive_model`, `foreign_collection`, plus `missing_points`.
  `apply=True` revalidates then deletes only non-authoritative ids via
  `QdrantVectorStore.delete_points` (bounded batches, single collection); no
  PostgreSQL deletes and other collections untouched. New store methods:
  `count_points`, `scroll_point_ids`, `existing_point_ids`, `delete_points`.
- Embedding policy: `services/embedding.py` `embedding_action(record_exists,
  point_exists)` → `persisted`/`skipped`/`repaired`; `embed_chunks` returns
  `EmbeddingBatch(embeddings, persisted, repaired, skipped)`. Persist writes the
  record and upserts the point in one database transaction, so a failed upsert rolls
  the row back; the reverse is not atomic — a commit failure after a successful
  upsert can leave a Qdrant point with no database row, which reconciliation reports
  as non-authoritative.
- API/config contracts are unchanged from `c365fbd` and documented in `README.md`
  and `docs/adr/`: `QueryRequest{query(1..2000), collection(1..128), limit(1..20,
  default 5)}`; NDJSON `sources|text|complete|error`; allowlist via
  `ALLOWED_COLLECTIONS` (ADR-005); `GenerationError` → terminal `error`;
  `MAX_OUTPUT_TOKENS` (1024) / `MAX_CONTEXT_CHARACTERS` (12000) bounds; per-client
  in-memory rate limit; exact-origin CORS. Schema: `collections`, `documents`,
  `document_versions`, `chunks`, `embeddings` with migrations
  `475d329a606c_create_initial_schema` and `4d9a0c20621f_remove_embedding_vector_key`;
  `Embedding.id` = Qdrant point ID.
- Local data/vector state (observed read-only): prepared corpus of **135** documents
  at `data/raw/fastapi/` with `.corpus-manifest.json`; PostgreSQL holds 135
  documents, 151 versions, 1,309 chunks and 1,309 embeddings for `fastapi` (the 16
  original documents were re-ingested with expanded content, so 209
  chunks/embeddings are superseded history); Qdrant `fastapi` holds **1,100** points,
  all authoritative, zero drift.
- Testing: `integration` marker + `--strict-markers`; CI runs `-m "not integration"`.
  Offline suites: `tests/test_corpus_preparation.py`, `tests/test_corpus_contract.py`,
  `tests/test_corpus_manifest_safety.py`, `tests/test_corpus_revision.py`,
  `tests/test_embedding_policy.py`, `tests/test_reconciliation.py`; extended
  `tests/test_qdrant.py`, `tests/test_cli.py`, `tests/test_dataset.py`.
  `tests/helpers/corpus.py` builds a synthetic checkout; `tests/helpers/qdrant.py`
  `FakeQdrantClient` keeps an in-memory point store with
  `scroll`/`retrieve`/`delete`/`count`.
- Tests that previously wrote vectors into the shared `fastapi` Qdrant collection
  (`tests/test_services.py` embedding tests) now use an in-memory Qdrant double.
- Evaluation: `data/evaluation/fastapi.json` has **29** examples (the original 24
  plus advanced/deployment/how-to/testing coverage); `fastapi-001` additionally
  requires the path-parameter code example. Anchors resolve against the latest
  version via `evaluation/anchors.py` (raises on missing/ambiguous). The
  anchor-based retrieval baseline is recorded in
  `data/evaluation/results/fastapi-retrieval-baseline-2026-10-16.json` and
  summarised in `docs/evaluation/retrieval_baseline.md` (K=5 default; K=10/K=20
  diagnostic depth measurements).
- Frontend: `frontend/src/api.ts` unchanged (`VITE_API_BASE_URL`, throws when the
  stream has no terminal event); `frontend/vite.config.ts` proxies `/query` to
  `http://localhost:8000`; theme is system-only (no selector, no localStorage).
- Container: multi-stage `Dockerfile` with the model baked into `HF_HOME=/opt/hf`,
  `HF_HUB_OFFLINE=1`, non-root `appuser`, `uvicorn --workers 1`.

## Recent Progress

Committed as `3371c82`:

- Corpus: pinned Git sparse checkout plus deterministic MkDocs preparation,
  including manifest-path validation and pinned-revision verification; added
  ADR-006 and updated `docs/corpus.md`.
- Retrieval consistency: runtime hydration filters to the latest document version.
- Reconciliation: collection-scoped drift reporting with dry-run default and
  `--apply` bounded deletion; new `prepare-corpus` and `reconcile` CLI subcommands.
- Ingestion: skip/repair semantics with per-outcome reporting.
- Evaluation: dataset extended 24 → 29 content-anchor examples; anchor-based
  retrieval baseline recorded as a dated artifact; existing result files preserved.
- Test hygiene: integration tests no longer write into the shared `fastapi` Qdrant
  collection; the local `fastapi` collection is now at zero drift (verified
  read-only).
- The DocAssist frontend redesign and its follow-ups are captured in `c365fbd`.

## Open / Unfinished State

Confirmed against current code and read-only inspection:

- ~74 leftover `test-retrieval-*` Qdrant collections remain from integration test
  runs; they were not touched and cleanup would be a separate, approved destructive
  operation.
- Generated API-reference tables (mkdocstrings) are excluded from the corpus;
  `reference/encoders.md`, `reference/openapi/docs.md`, and
  `reference/openapi/models.md` are excluded as generated-reference-only, and the
  baseline records no per-example metrics.
- No Firebase/Cloud Run deployment configuration in-repo; hosted PostgreSQL/Qdrant
  configurable but no secret-manager integration and account state unverified.
- Alembic offline mode (`--sql`) uses the placeholder `sqlalchemy.url`.
- CORS read at import; `VITE_API_BASE_URL` baked at frontend build time.
- Embedding model must be pre-baked/cached; `encode()` blocks the event loop.
- Stale DeepSeek model IDs: `deepseek-v4-flash` in `core/settings.py`;
  `deepseek-chat` judge in `evaluation/answer.py`.
- Only `GenerationError` maps to a terminal event; other exceptions abort the stream
  with no terminal event.
- Ingestion opens a DB session/transaction per chunk.
- Telemetry console exporter unconditional (emits `I/O operation on closed file` at
  interpreter shutdown in tests); `/health` is shallow.
- Frontend renders Markdown but sources show metadata, not content text.
- `data/tmp/fastapi_chunks.tsv` (tracked generated output, stale relative to the
  prepared corpus) was deliberately retained; `docs/images/streaming.gif` is ~13 MB.
- CORS frontend↔backend cross-origin path not exercised end-to-end.

Unresolved external decisions (no account state inspected): reuse vs. create a Neon
project; Firebase/GCP project and billing; hosted Qdrant suitability; DeepSeek
budget.

## Verification

Valid for HEAD `3371c82` (working tree clean apart from this file):

- `uv run ruff check .` → All checks passed!; `uv run ruff format --check .` →
  100 files already formatted.
- `DEEPSEEK_API_KEY=ci-dummy-key uv run pytest -q -m "not integration"` →
  **210 passed, 23 deselected**.
- `./scripts/acquire_corpus.sh` → 135 documents prepared, 446 include directives
  expanded, 290 unique snippet files, 988,521 bytes, 18 exclusions reported;
  preparation verified byte-deterministic across two runs.
- Corpus checks: 0 residual `{* `, `{!`, `^:::`, `^///`, `{ #`, `<dfn>` in
  `data/raw/fastapi/**`; the original 16 `source_uri` paths preserved;
  `@app.get("/items/{item_id}")` present in `path-params.md`.
- `uv run production-rag reconcile --collection fastapi` (read-only dry run) →
  1,100 points, all authoritative; 0 unbacked, 0 superseded-version, 0
  inactive-model, 0 foreign-collection, 0 missing; no deletion.
- Frontend (code unchanged since `c365fbd`): `npm run lint`, `npm run test`
  (Vitest), `npm run build` pass; browser check confirmed system light/dark
  switching with no theme selector.
- `git diff --check` → clean.
- Not run (require services/paid calls/approval): `-m integration` tests, live
  DeepSeek generation, deployment. Corpus ingestion and `reconcile --apply` were
  performed outside this handoff's own work and are evidenced only by the read-only
  checks above.

## Authoritative References

- `AGENTS.md` — workflow, permissions, security/cost, public-API, corpus/evaluation
  rules.
- `README.md` — architecture, setup, configuration, commands, baselines, CI.
- `docs/adr/` — 001 multi-collection, 002 embedding entity, 003 structure-aware
  ingestion, 004 selective LangChain, 005 API allowlist, 006 corpus preparation and
  vector-store consistency.
- `docs/corpus.md` — corpus scope, preparation, exclusions, layout;
  `docs/evaluation/` and `data/evaluation/` — datasets, baselines, results.
- `src/production_rag/`, `tests/`, `frontend/`, `alembic/`, `Dockerfile`,
  `.dockerignore`, `.env.example`, `.github/workflows/ci.yml`,
  `scripts/acquire_corpus.sh`, `docker-compose.yml`, `pyproject.toml`, `uv.lock`.

## Session Boundary

- All implementation work for this session's range is committed at HEAD `3371c82`;
  the only modification from this handoff task is `SESSION_HANDOFF.md` (not staged).
- Local state: `.env` holds local configuration (gitignored); prepared corpus at
  `data/raw/fastapi/` (135 docs + `.corpus-manifest.json`); pinned checkout at
  `data/tmp/fastapi-checkout/` (gitignored); HF cache has the embedding model;
  `frontend/node_modules` and ignored `frontend/dist` present; local PostgreSQL and
  Qdrant containers running with the ingested and reconciled `fastapi` collection.
- Material discrepancy vs. the previous handoff: it described HEAD `c365fbd` with an
  uncommitted corpus/vector change set; that work is now committed as `3371c82` and
  the working tree is clean.
