# Session Handoff

_Current-state snapshot (2026-10-15). Rewrite stale sections; do not append
history. Not a changelog, task plan, or recommendation list. Use exact
paths/identifiers; never include secrets; never claim unobserved verification._

## Repository State

- Branch `main`, HEAD `c365fbd` (`feat: redesign DocAssist frontend`), matching
  the tracked `origin/main` ref (`rev-list --left-right --count` → `0 0`).
- The working tree is **not** clean: an uncommitted corpus/vector-consistency
  change set is in progress (see "Session Boundary"). Nothing has been committed
  or pushed this session.
- Recent commits: `c365fbd` (DocAssist frontend redesign); `35d5755` (handoff);
  `8855015` (frontend API URL + CORS); `0e4d1a9` (backend container image);
  `3d2a964` (CPU-only PyTorch); `e4e929b` (hosted Qdrant URLs); `767c574`
  (hosted PostgreSQL URLs); `19451dc` (rate limit); `29e47d7` (output/context
  bounds); `01be780` (generation failure handling).

## Project State

DocAssist (`production-rag`) is a RAG portfolio demo: a FastAPI service answers
questions grounded in retrieved FastAPI documentation, backed by PostgreSQL
(authoritative metadata/chunks) and Qdrant (vectors),
`BAAI/bge-small-en-v1.5` embeddings, DeepSeek generation, and a
React/TypeScript/Vite frontend (product name **DocAssist**); managed with `uv`.

Stage: local vertical slice, CI, backend container image, the DocAssist frontend
redesign (Ask/About/Project views, system-only theme, Markdown answers), and
public-API safeguards are implemented. **Firebase/Cloud Run deployment is not
configured in-repo.** The expanded pinned corpus has been acquired, prepared and
ingested (135 documents; 1,100 current chunks), and the `fastapi` vector store
reconciled to 1,100 authoritative points with no drift; the anchor-based
retrieval baseline is recorded. Per `AGENTS.md`, verify current status before
asserting.

## Implemented State

- Ingestion: Markdown → SHA-256 → structure-aware chunking (`max_characters=4000`)
  → PostgreSQL → embeddings → Qdrant; idempotent, versioned documents. Embedding
  work is skipped when both the embedding record and its Qdrant point exist, and
  repaired (same embedding id, no duplicate record) when only the point is
  missing.
- Retrieval: query embedding → Qdrant search → PostgreSQL hydration scoped by
  collection, **filtered to the latest document version** using the same rule as
  evaluation.
- API: NDJSON `POST /query` (`sources` → `text`* → one terminal `complete`/`error`);
  identical `404` for disallowed/nonexistent collections; shallow `GET /health`.
- Generation: DeepSeek Responses API; success requires `response.completed`;
  bounded output; failed/incomplete generations emit a terminal `error`.
- Corpus: pinned FastAPI docs acquired by sparse checkout and prepared by
  expanding MkDocs includes (ADR-006).
- Reconciliation: collection-scoped drift report (dry-run default) with
  `--apply` to delete only provably non-authoritative Qdrant points.
- CLI: `production-rag ingest|query|prepare-corpus|reconcile`.
- Frontend: DocAssist SPA (Ask/About/Project), system theme via CSS
  `prefers-color-scheme`, Markdown answers (`react-markdown` + `remark-gfm`,
  no raw HTML), full-width answer box with a 72ch reading measure, footer contact
  links, Vitest + Testing Library suite.
- CI: backend Ruff + corpus acquisition/preparation + service-free tests on
  CPU-only PyTorch; frontend `npm ci` → `lint` → `test` → `build`.

## Current Implementation Details

- Layout: `src/production_rag/{api,core,corpus,db,ingestion,models,repositories,schemas,services,evaluation,telemetry.py,main.py}`,
  `alembic/versions/`, `tests/`, `frontend/`, `docs/{adr,corpus.md,evaluation,deployment.md,images}`,
  `data/{raw,evaluation,tmp}`, `.github/workflows/ci.yml`, `scripts/acquire_corpus.sh`,
  `docker-compose.yml`, `Dockerfile`, `.dockerignore`, `pyproject.toml`, `uv.lock`.
- Corpus preparation: `src/production_rag/corpus/preparation.py`. Pinned revision
  `244d66308d6c525f394d0c2ce32dabceb2ed262b`. Includes `{* path *}` and
  `{!path!}` / `{!> path!}` expand to fenced code (inlined when already inside a
  fence); `:::`, `///`, `{ #anchor }`, `<dfn>`, `{% raw %}` are normalised;
  preparation fails on unresolved includes, unsupported target types, or
  unhandled constructs (content tabs, Jinja blocks/expressions, `!!!`, `--8<--`).
  Layout: `tutorial/**` flattened to the corpus root, other sections mirrored,
  remaining pages under `guide/`. Records `.corpus-manifest.json` and prunes only
  files it previously wrote. Preparation is byte-deterministic.
- `scripts/acquire_corpus.sh` clones a blobless sparse checkout of
  `docs/en/docs/**`, `docs_src/**`, `fastapi/**` into
  `data/tmp/fastapi-checkout` (gitignored), verifies the resolved revision, and
  runs `uv run production-rag prepare-corpus`.
- Authoritative vector set: `RetrievalRepository._latest_version_ids()` defines
  the latest version per document; shared by `list_collection_chunks`,
  `find_chunks_by_embedding_ids`, `authoritative_embedding_ids`, and
  `classify_embeddings`.
- Reconciliation: `services/reconciliation.py` categories are `unbacked`,
  `superseded_version`, `inactive_model`, `foreign_collection`, plus
  `missing_points`. `reconcile(apply=False)` is read-only; `apply=True`
  revalidates then deletes only non-authoritative ids via
  `QdrantVectorStore.delete_points` (bounded batches, single collection). No
  PostgreSQL deletes; other collections untouched.
- Qdrant store additions: `count_points`, `scroll_point_ids`,
  `existing_point_ids`, `delete_points` (`services/qdrant.py`).
- Embedding policy: `services/embedding.py` `embedding_action(record_exists,
  point_exists)` → `persisted` / `skipped` / `repaired`; `embed_chunks` returns
  `EmbeddingBatch(embeddings, persisted, repaired, skipped)` (also iterable and
  sized). Persist writes the record and upserts the point inside one database
  transaction, so a failed upsert rolls the row back; the reverse is not atomic —
  a commit failure after a successful upsert can leave a Qdrant point with no
  database row, which reconciliation reports as a non-authoritative point.
- API contract unchanged: `QueryRequest{query(1..2000), collection(1..128),
  limit(1..20, default 5)}`; NDJSON `sources|text|complete|error`; `404` for
  disallowed/nonexistent.
- Allowlist: `core/settings.py` `allowed_collections` (`ALLOWED_COLLECTIONS`,
  CSV, default `fastapi`); checked in `api/query.py` before any Qdrant lookup;
  empty denies all (ADR-005).
- Generation errors: `services/llm.py` raises `GenerationError(code, message)`
  on `response.failed`/`response.incomplete` and when the stream ends without
  `response.completed`; `services/rag.py` emits a terminal `error` event and
  returns without `complete`.
- Bounds: `max_output_tokens` passed to `responses.create`;
  `services/rag.py` `_within_context_budget` selects a rank-preserving prefix
  within `max_context_characters` for both prompt and `sources` event. Unchanged.
- Rate limit: `api/rate_limit.py` (`RateLimiter`, `client_key`,
  `enforce_rate_limit`, HTTP `429` + `Retry-After`), wired in `api/query.py`;
  limiter created in the app lifespan.
- CORS: `cors_allowed_origins` (`CORS_ALLOWED_ORIGINS`, CSV) with `*` rejected;
  `main.py` `configure_cors` adds `CORSMiddleware` only when origins are set.
- Schema: `collections`, `documents`, `document_versions`, `chunks`, `embeddings`;
  migrations `475d329a606c_create_initial_schema`,
  `4d9a0c20621f_remove_embedding_vector_key`; `Embedding.id` = Qdrant point ID.
- DB wiring: `db/url.py` `build_database_url` (`DATABASE_URL` wins, forces
  `postgresql+asyncpg`, translates `sslmode`→`ssl`, rejects `channel_binding`);
  `db/session.py` and `alembic/env.py` use it.
- Vector wiring: `build_qdrant_client_kwargs` prefers `QDRANT_URL`
  (+ `QDRANT_API_KEY`) and falls back to `QDRANT_HOST`/`QDRANT_PORT`.
- Embeddings: `SentenceTransformer` loaded lazily with `local_files_only=True`
  and `revision=settings.embedding_model_revision or None`; `MODEL_NAME`
  `BAAI/bge-small-en-v1.5`, `MODEL_VERSION` `1`. `encode()` is synchronous
  inside the async path.
- Config keys (`core/settings.py`): `APP_*`, `DEBUG`, `ALLOWED_COLLECTIONS`,
  `CORS_ALLOWED_ORIGINS`, `DATABASE_URL`, `POSTGRES_*`, `QDRANT_*`,
  `EMBEDDING_MODEL_REVISION`, `DEEPSEEK_*`, `MAX_OUTPUT_TOKENS` (1024),
  `MAX_CONTEXT_CHARACTERS` (12000), `RATE_LIMIT_REQUESTS` (10),
  `RATE_LIMIT_TRUST_CLOUD_RUN_X_FORWARDED_FOR`. `MAX_CONTEXT_CHARACTERS` and
  retrieval limits were **not** changed this session.
- CPU PyTorch: `pyproject.toml` extras `cpu`/`gpu` with `[tool.uv] conflicts`
  and a `pytorch-cpu` `[tool.uv.sources]` index.
- Testing: `integration` marker + `--strict-markers`; CI runs
  `-m "not integration"`. New offline tests: `tests/test_corpus_preparation.py`,
  `tests/test_corpus_contract.py`, `tests/test_embedding_policy.py`,
  `tests/test_reconciliation.py`; extended `tests/test_qdrant.py`,
  `tests/test_cli.py`. `tests/helpers/qdrant.py` `FakeQdrantClient` now keeps an
  in-memory point store with `scroll`/`retrieve`/`delete`/`count`.
- Tests that previously wrote vectors into the shared `fastapi` Qdrant
  collection (`tests/test_services.py` embedding tests) now use an in-memory
  Qdrant double.
- Evaluation: `data/evaluation/fastapi.json` has **29** examples (the original
  24 plus advanced/deployment/how-to/testing coverage); `fastapi-001` additionally
  requires the path-parameter code example. Anchors resolve against the latest
  version via `evaluation/anchors.py` (raises on missing/ambiguous). The
  anchor-based retrieval baseline is recorded in
  `data/evaluation/results/fastapi-retrieval-baseline-2026-10-16.json` and
  summarised in `docs/evaluation/retrieval_baseline.md` (K=5 is the application
  default; K=10/K=20 are diagnostic depth measurements); existing result files
  were preserved.
- Frontend: `frontend/src/api.ts` unchanged (`VITE_API_BASE_URL`, throws when the
  stream has no terminal event); `frontend/vite.config.ts` proxies `/query` to
  `http://localhost:8000`; theme is system-only (no selector, no localStorage).
- Container: multi-stage `Dockerfile` with the model baked into `HF_HOME=/opt/hf`,
  `HF_HUB_OFFLINE=1`, non-root `appuser`, `uvicorn --workers 1`. `.dockerignore`
  excludes `.env*` (keeping `.env.example`), `.git`, `.venv`, caches, `data/`,
  `docs/`, `tests/`, `frontend/`.

## Recent Progress

This session (uncommitted):

- Corpus: replaced the 16-file curl acquisition with a pinned sparse checkout plus
  deterministic MkDocs preparation (`production_rag.corpus.preparation`),
  ADR-006, updated `docs/corpus.md`/`README.md`.
- Retrieval consistency: latest-version filter added to runtime hydration.
- Reconciliation tooling and CLI (`reconcile`, dry-run default) with
  collection-scoped classification and deletion.
- Ingestion skip/repair semantics with per-outcome reporting.
- Corpus-contract and offline tests; evaluation dataset extended to 29 examples.
- Test hygiene: integration tests no longer write into the shared `fastapi`
  Qdrant collection.
- Earlier in the same uncommitted range: DocAssist frontend redesign
  (commit `c365fbd`) and the system-theme/empty-answer/answer-width follow-ups.

## Open / Unfinished State

Confirmed against current code and read-only inspection:

- Expanded corpus **ingested and reconciled** (read-only verification): PostgreSQL
  holds 135 documents, 151 versions, 1,309 chunks and 1,309 embeddings for the
  `fastapi` collection — the 16 original documents were re-ingested with expanded
  content, so 209 superseded chunks/embeddings are retained for history.
- **Qdrant `fastapi` collection: 1,100 points, all authoritative.** Read-only
  reconciliation reports 0 unbacked, 0 superseded-version, 0 inactive-model,
  0 foreign-collection and **0 missing** vectors. The previously reported 329
  foreign-collection points (leaked by integration tests) are gone.
- ~74 leftover `test-retrieval-*` Qdrant collections still exist from integration
  test runs. They were not touched; cleanup would be a separate, approved
  destructive operation.
- Anchor-based retrieval baseline recorded (2026-10-16); per-example metrics are
  not recorded in the artifact.
- Generated API-reference tables (mkdocstrings) are excluded from the corpus;
  `reference/encoders.md`, `reference/openapi/docs.md`, and
  `reference/openapi/models.md` are excluded as generated-reference-only.
- No Firebase/Cloud Run deployment configuration in-repo.
- Hosted PostgreSQL/Qdrant configurable; no secret-manager integration; account
  state, quotas, billing unverified.
- Alembic offline mode (`--sql`) uses the placeholder `sqlalchemy.url`.
- CORS read at import; `VITE_API_BASE_URL` baked at frontend build time.
- Embedding model must be pre-baked/cached; `encode()` blocks the event loop.
- Stale DeepSeek model IDs: `deepseek-v4-flash` in `core/settings.py`;
  `deepseek-chat` judge in `evaluation/answer.py`.
- Only `GenerationError` maps to a terminal event.
- Ingestion opens a DB session/transaction per chunk.
- Telemetry console exporter unconditional (emits an `I/O operation on closed
  file` message at interpreter shutdown in tests); `/health` is shallow.
- Frontend renders Markdown but sources show metadata, not content text.
- `data/tmp/fastapi_chunks.tsv` (tracked generated output, now stale relative to
  the prepared corpus) was deliberately retained; `docs/images/streaming.gif`
  is ~13 MB.
- CORS frontend↔backend cross-origin path not exercised end-to-end.

Unresolved external decisions (no account state inspected): reuse vs. create a
Neon project; Firebase/GCP project and billing; hosted Qdrant suitability;
DeepSeek budget.

## Verification

Observed this session (working tree state described above):

- `uv run ruff check .` → All checks passed. `uv run ruff format --check .` →
  96 files already formatted.
- `DEEPSEEK_API_KEY=ci-dummy-key uv run pytest -q -m "not integration"` →
  **194 passed, 23 deselected**.
- `./scripts/acquire_corpus.sh` → 135 documents prepared, 446 include directives
  expanded, 290 unique snippet files, 988,521 bytes, 18 exclusions reported;
  preparation verified byte-deterministic across two runs.
- Corpus checks: 0 residual `{* `, `{!`, `^:::`, `^///`, `{ #`, `<dfn>` in
  `data/raw/fastapi/**`; the original 16 `source_uri` paths preserved;
  `@app.get("/items/{item_id}")` now present in `path-params.md`.
- `uv run production-rag reconcile --collection fastapi` (read-only dry run) →
  printed the category counts above; no deletion.
- `git diff --check` → clean.
- Frontend (from the redesign commit range): `npm run lint`, `npm run test`
  (Vitest, includes system-theme and empty-answer cases), `npm run build` pass;
  browser check confirmed system light/dark switching with no selector.
- Not run this session (require services/paid calls/approval): `-m integration`
  tests, expanded-corpus ingestion, `reconcile --apply`, live DeepSeek
  generation, deployment.

## Authoritative References

- `AGENTS.md` — workflow, permissions, security/cost, public-API,
  corpus/evaluation rules.
- `README.md` — architecture, setup, configuration, commands, baselines, CI.
- `docs/adr/` — 001 multi-collection, 002 embedding entity, 003 structure-aware
  ingestion, 004 selective LangChain, 005 API allowlist,
  006 corpus preparation and vector-store consistency.
- `docs/corpus.md` — corpus scope, preparation, exclusions, layout.
- `docs/deployment.md`; `docs/evaluation/`, `data/evaluation/`.
- `src/production_rag/`, `tests/`, `frontend/`, `alembic/`, `Dockerfile`,
  `.dockerignore`, `.env.example`, `.github/workflows/ci.yml`,
  `scripts/acquire_corpus.sh`, `docker-compose.yml`, `pyproject.toml`, `uv.lock`.

## Session Boundary

- HEAD `c365fbd`; **uncommitted** changes in this working tree:
  `.gitignore`, `README.md`, `SESSION_HANDOFF.md`, `data/evaluation/fastapi.json`,
  `docs/corpus.md`, `docs/evaluation/retrieval_baseline.md`, `scripts/acquire_corpus.sh`,
  `src/production_rag/__init__.py`, `src/production_rag/corpus/`,
  `src/production_rag/repositories/{embedding,retrieval}.py`,
  `src/production_rag/services/{embedding,qdrant,reconciliation}.py`,
  `tests/helpers/qdrant.py`, `tests/test_cli.py`, `tests/test_corpus_contract.py`,
  `tests/test_corpus_preparation.py`, `tests/test_dataset.py`,
  `tests/test_embedding_policy.py`, `tests/test_qdrant.py`,
  `tests/test_reconciliation.py`, `tests/test_services.py`,
  `docs/adr/006-corpus-preparation-and-vector-store-consistency.md`.
- Local state: `.env` holds local configuration (gitignored); prepared corpus at
  `data/raw/fastapi/` (135 docs + `.corpus-manifest.json`); pinned checkout at
  `data/tmp/fastapi-checkout/` (gitignored); HF cache has the embedding model;
  `frontend/node_modules` and ignored `frontend/dist` present; local PostgreSQL
  and Qdrant containers running with the ingested and reconciled `fastapi`
  collection (1,100 authoritative vectors).
- Remaining approvals: none required for the recorded baseline. Cleanup of the
  leftover `test-retrieval-*` Qdrant collections would be a separate, approved
  destructive operation.
