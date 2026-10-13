# Session Handoff

_Current-state snapshot (2026-10-14). Rewrite stale sections; do not append
history. Not a changelog, task plan, or recommendation list. Use exact
paths/identifiers; never include secrets; never claim unobserved verification._

## Repository State

- Branch `main`, HEAD `499fec30049c68efeebf1e8d618f0ec7fec52eea`, matching the
  tracked `origin/main` ref. Working tree clean except this `SESSION_HANDOFF.md`
  rewrite (the only uncommitted change at snapshot time).
- Recent commits: `499fec3` (failed/incomplete generation handling); `0b54ca1`
  (request field caps); `3df7f28` (API collection allowlist); `57fcb82` (CI);
  `3ae76bc` (reproducible retrieval evaluation); `7e4c7fe` (session handoff).

## Project State

Production RAG is a RAG portfolio demo: a FastAPI service answers questions
grounded in retrieved documentation (currently the FastAPI docs), backed by
PostgreSQL, Qdrant, `BAAI/bge-small-en-v1.5` embeddings, DeepSeek generation,
and a React/TypeScript/Vite frontend; managed with `uv`.

Stage: the local vertical slice and **CI are implemented**; the public API is
constrained (collection allowlist, request-length caps, explicit generation
error handling) and retrieval evaluation is content-anchor based. **Deployment
is not configured in-repo** (no backend `Dockerfile`, no Firebase/Cloud Run
config). Hosting topology (Firebase Hosting, Cloud Run, Neon, hosted Qdrant) is
intended, not implemented. Per `AGENTS.md`, verify current status before
asserting.

## Implemented State

- Ingestion: Markdown → SHA-256 → structure-aware chunking (`markdown-it-py`,
  `max_characters=4000`) → PostgreSQL → embeddings → Qdrant; idempotent by
  content hash with document versioning.
- Retrieval: query embedding → Qdrant search → PostgreSQL hydration
  (authoritative metadata), scoped by collection name.
- API: `POST /query` streams NDJSON in fixed order — `sources`, zero or more
  incremental `text`, then exactly one terminal event: `complete` on success or
  `error` on failed/incomplete generation. Disallowed and nonexistent
  collections return an identical `404`. `GET /health` is shallow.
- Generation: DeepSeek via the OpenAI SDK Responses API; success requires an
  explicit `response.completed` event.
- CLI: `production-rag ingest` / `query` (`src/production_rag/__init__.py`).
- Evaluation: content-anchor retrieval labels resolved to current chunk IDs,
  chunk-level retrieval metrics, DeepEval answer metrics.
- Observability: OpenTelemetry with an unconditional console span exporter.
- Frontend: single-page React; plain-text answers and source metadata; handles
  `error` events and treats a stream without a terminal event as a failure.
- CI: GitHub Actions backend (Ruff + service-free tests) and frontend
  (install/lint/build) jobs.

## Current Implementation Details

- Layout: `src/production_rag/{api,core,db,ingestion,models,repositories,schemas,services,evaluation,telemetry.py,main.py}`,
  `alembic/versions/`, `tests/`, `frontend/`, `docs/{adr,corpus.md,evaluation,images}`,
  `data/{raw,evaluation,tmp}`, `.github/workflows/ci.yml`,
  `scripts/acquire_corpus.sh`, `docker-compose.yml`, `pyproject.toml`, `uv.lock`.
- API contract: `QueryRequest{query(min_length=1, max_length=2000),
  collection(min_length=1, max_length=128), limit(1..20, default 5)}`;
  NDJSON `sources|text|complete|error`; `404` for disallowed or nonexistent.
- Allowlist: `core/settings.py` `allowed_collections` (`ALLOWED_COLLECTIONS`,
  CSV, default `fastapi`) with `allowed_collection_names`; checked in
  `api/query.py` before any Qdrant lookup; empty value denies all (ADR-005).
- Generation errors: `services/llm.py` raises `GenerationError(code, message)`
  on `response.failed`/`response.incomplete` and when the stream ends without
  `response.completed`, without reading provider details (codes
  `generation_failed` / `generation_incomplete`). `services/rag.py` converts it
  to a terminal `error` RAG event and returns without `complete`.
- Schema: `collections`, `documents`, `document_versions`, `chunks`, `embeddings`;
  migrations `475d329a606c_create_initial_schema`,
  `4d9a0c20621f_remove_embedding_vector_key`; `Embedding.id` = Qdrant point ID.
- Config: `core/settings.py` keys `POSTGRES_*`, `QDRANT_HOST`/`PORT`,
  `DEEPSEEK_API_KEY`/`BASE_URL`/`MODEL`/`TIMEOUT`, `ALLOWED_COLLECTIONS`,
  `APP_*`, `DEBUG`. `.env.example` omits `DEEPSEEK_API_KEY`/`BASE_URL`/`MODEL`
  (has only `DEEPSEEK_TIMEOUT`) and lists unused `REDIS_*`; local `.env` is
  gitignored.
- DB/vector wiring: `db/session.py` builds `postgresql+asyncpg://…` at import
  (no `DATABASE_URL`/TLS/pool_ping); `services/qdrant.py` takes only `host`/`port`
  (no `url`/`api_key`).
- Embeddings: `services/embedding.py` uses `local_files_only=True`; `encode()`
  is synchronous inside the async path.
- Python/deps: Python 3.12; `uv 0.13.0`, ruff 0.16.2, fastapi 0.141.1,
  sqlalchemy 2.0.51, qdrant-client 1.19.0, sentence-transformers 6.0.0,
  openai 3.5.0, deepeval 4.2.0. Use `uv run` / `.venv/bin/*`.
- Testing: `integration` marker + `--strict-markers` (`pyproject.toml`),
  applied at module level in `test_database.py`, `test_models.py`,
  `test_repositories.py`, `test_retrieval.py`, `test_qdrant_integration.py`,
  `test_services.py`; CI runs `-m "not integration"`.
- Evaluation: `data/evaluation/fastapi.json` (24 examples) uses
  `{source_uri, snippet}` anchors; `evaluation/anchors.py` resolves them (raises
  on missing/ambiguous) against the latest document version via
  `RetrievalRepository.list_collection_chunks`. Legacy UUID baseline is marked
  non-reproducible; the anchor-based baseline is pending a real run
  (`docs/evaluation/retrieval_baseline.md`).
- Corpus: `docs/corpus.md` pins `fastapi/fastapi` commit `244d6630…` (16 tutorial
  files); reproducible via `./scripts/acquire_corpus.sh`; `data/raw/` gitignored.
- CI: `.github/workflows/ci.yml` — backend `uv sync --frozen` → `ruff check` →
  `ruff format --check` → corpus script → `pytest -m "not integration"` (with
  `DEEPSEEK_API_KEY=ci-dummy-key`, a placeholder); frontend Node 24 `npm ci` →
  `npm run lint` → `npm run build`.
- Frontend: `frontend/src/api.ts` posts to relative `/query` (Vite proxy in
  `vite.config.ts`) and throws when the stream ends without `complete`/`error`;
  no API base URL or CORS in `main.py`.

## Recent Progress

- Made retrieval evaluation reproducible: replaced non-reproducible UUID labels
  with content anchors and a resolver, migrated all 24 examples, added loader
  validation and offline anchor tests, and marked the old UUID baseline legacy.
- Added CI with a pinned corpus acquisition script and the `integration` marker
  (strict validation) so CI runs service-free tests only.
- Restricted the public API: collection allowlist with identical `404`
  behavior (ADR-005) and request field-length caps.
- Hardened generation: `response.failed` / `response.incomplete` / missing
  `response.completed` now surface as a terminal NDJSON `error` event (never a
  false `complete`), with frontend handling.
- Updated docs: README (streaming order, allowlist, limits, CI, corpus
  acquisition), `docs/corpus.md`, and an `AGENTS.md` code-style note.

## Open / Unfinished State

Confirmed against current code:

- No deployment artifacts (no backend `Dockerfile`, no Firebase/Cloud Run).
- No CORS or configurable API base URL.
- Hosted-service gaps: Qdrant lacks `url`/`api_key`; Postgres lacks
  `DATABASE_URL`/TLS/pooling; no secret-manager integration.
- Embedding model must be pre-baked/cached; `encode()` blocks the event loop.
- Stale DeepSeek model IDs (`deepseek-v4-flash` in settings; `deepseek-chat`
  judge in `evaluation/answer.py`).
- No output-token cap (deferred until incomplete handling is reliable).
- `evaluation/generation.py` and `evaluation/answer.py` ignore the `error`
  event → an evaluator run could record a partial answer without a signal.
- Only `GenerationError` maps to a terminal event; other unexpected exceptions
  abort the stream with no terminal event (frontend reports "ended unexpectedly").
- Ingestion opens a DB session/transaction per chunk; `ensure_collection`
  re-fetches collections per chunk.
- Telemetry console exporter unconditional; `/health` is shallow.
- Frontend renders plain text only; sources show metadata, not content; no
  frontend test runner.
- `.env.example` drift (see Config); `data/tmp/fastapi_chunks.tsv` is tracked
  generated output; `docs/images/streaming.gif` is ~13 MB.
- Anchor-based retrieval baseline is pending a real evaluation run.

Unresolved external decisions (no account state inspected): reuse vs. create a
Neon project; Firebase/GCP project and billing; hosted Qdrant suitability;
DeepSeek budget.

## Verification

Valid for HEAD `499fec3` (working tree clean apart from this file):

- `uv run ruff check .` → All checks passed!; `uv run ruff format --check .` →
  80 files already formatted.
- `DEEPSEEK_API_KEY=ci-dummy-key uv run pytest -q -m "not integration"` →
  75 passed, 23 deselected.
- Focused: `tests/test_llm.py tests/test_rag.py tests/test_api.py` → 20 passed;
  `tests/test_settings.py` → 5 passed.
- Frontend: `npm run lint` → exit 0; `npm run build` → exit 0.
- `uv lock --check` → lockfile consistent; `./scripts/acquire_corpus.sh` → 16
  files; `git diff --check` → clean.
- Not run (require services/state/paid calls): `-m integration` tests, Docker
  Compose, Alembic migrations, live DeepSeek requests, deployment.

## Authoritative References

- `AGENTS.md` (157 lines) — workflow, permissions, security/cost, public-API,
  corpus/evaluation rules.
- `README.md` — architecture, setup, commands, baselines, CI.
- `docs/adr/` — accepted decisions (001 multi-collection, 002 embedding entity,
  003 structure-aware ingestion, 004 selective LangChain, 005 API allowlist).
- `docs/corpus.md`; `docs/evaluation/`, `data/evaluation/`.
- `src/production_rag/`, `tests/`, `frontend/`, `alembic/`,
  `.github/workflows/ci.yml`, `scripts/acquire_corpus.sh`, `docker-compose.yml`,
  `pyproject.toml`, `uv.lock`.

## Session Boundary

- All session implementation work is committed at HEAD `499fec3`; the only
  uncommitted change is this `SESSION_HANDOFF.md` rewrite (not staged).
- Local state: `.env` holds a real DeepSeek key (gitignored); corpus at
  `data/raw/fastapi/`; HF cache has the embedding model; `frontend/node_modules`
  and ignored `frontend/dist` present.
- Material discrepancy vs. the previous handoff: it described HEAD `78ed31b` and
  a documentation-only tree. The repository has since advanced five commits with
  substantial implementation, CI, and API changes; its open items "no CI",
  "no allowlist/max_length", "LLM ignores `response.failed`/incomplete", "README
  streaming inaccuracies", and "tests require live services without markers" are
  now resolved.
