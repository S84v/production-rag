# Session Handoff

_Current-state snapshot (2026-10-15). Rewrite stale sections; do not append
history. Not a changelog, task plan, or recommendation list. Use exact
paths/identifiers; never include secrets; never claim unobserved verification._

## Repository State

- Branch `main`, HEAD `885501511bf7c42415db93e73d64c1922b77c4c6`
  (`feat: configure frontend API URL and CORS`), matching the tracked
  `origin/main` ref. Working tree clean at snapshot time except this
  `SESSION_HANDOFF.md` rewrite (not staged).
- Recent commits: `8855015` (frontend API URL + CORS); `0e4d1a9` (backend
  container image); `3d2a964` (CPU-only PyTorch option); `e4e929b` (hosted Qdrant
  URLs); `767c574` (hosted PostgreSQL URLs); `19451dc` (public-API rate limit);
  `29e47d7` (generation/context bounds); `01be780` (evaluation failure handling).

## Project State

Production RAG is a RAG portfolio demo: a FastAPI service answers questions
grounded in retrieved documentation (currently the FastAPI docs), backed by
PostgreSQL (authoritative metadata/chunks) and Qdrant (vectors),
`BAAI/bge-small-en-v1.5` embeddings, DeepSeek generation, and a
React/TypeScript/Vite frontend; managed with `uv`.

Stage: the local vertical slice, CI, and a **backend container image** are
implemented; the public API is constrained (collection allowlist, request
caps, generation error handling, bounded output/context, in-memory rate limit);
retrieval evaluation is content-anchor based; hosted PostgreSQL/Qdrant and CORS
are configurable. **Firebase/Cloud Run deployment is not configured in-repo**;
hosting topology (Firebase Hosting, Cloud Run, Neon, hosted Qdrant) is intended,
not implemented/verified. Per `AGENTS.md`, verify current status before
asserting.

## Implemented State

- Ingestion: Markdown → SHA-256 → structure-aware chunking (`max_characters=4000`)
  → PostgreSQL → embeddings → Qdrant; idempotent, versioned documents.
- Retrieval: query embedding → Qdrant search → PostgreSQL hydration, scoped by collection.
- API: NDJSON `POST /query` (`sources` → `text`* → one terminal `complete`/`error`);
  identical `404` for disallowed/nonexistent collections; shallow `GET /health`.
- Generation: DeepSeek Responses API; success requires `response.completed`;
  bounded output; failed/incomplete generations emit a terminal `error`.
- Public-API safeguards: collection allowlist, request caps, output/context
  bounds, per-client in-memory rate limit, and configurable exact-origin CORS.
- CLI (`production-rag ingest|query`); content-anchor retrieval evaluation plus
  DeepEval answer metrics; OpenTelemetry console spans.
- Frontend: React SPA using `VITE_API_BASE_URL` (relative `/query` by default),
  plain-text answers with source metadata, treats a missing terminal event as a
  failure.
- CI (Ruff + service-free tests on CPU-only PyTorch; frontend lint/build) and a
  multi-stage Linux AMD64 `Dockerfile` with the embedding model baked in.

## Current Implementation Details

- Layout: `src/production_rag/{api,core,db,ingestion,models,repositories,schemas,services,evaluation,telemetry.py,main.py}`,
  `alembic/versions/`, `tests/`, `frontend/`, `docs/{adr,corpus.md,evaluation,deployment.md,images}`,
  `data/{raw,evaluation,tmp}`, `.github/workflows/ci.yml`, `scripts/acquire_corpus.sh`,
  `docker-compose.yml`, `Dockerfile`, `.dockerignore`, `pyproject.toml`, `uv.lock`.
- API contract: `QueryRequest{query(min_length=1, max_length=2000),
  collection(min_length=1, max_length=128), limit(1..20, default 5)}`;
  NDJSON `sources|text|complete|error`; `404` for disallowed or nonexistent.
- Allowlist: `core/settings.py` `allowed_collections` (`ALLOWED_COLLECTIONS`,
  CSV, default `fastapi`) with `allowed_collection_names`; checked in
  `api/query.py` before any Qdrant lookup; empty value denies all (ADR-005).
- Generation errors: `services/llm.py` raises `GenerationError(code, message)`
  on `response.failed`/`response.incomplete` and when the stream ends without
  `response.completed` (codes `generation_failed` / `generation_incomplete`);
  `services/rag.py` emits a terminal `error` RAG event and returns without
  `complete`.
- Bounds: `services/llm.py` passes `settings.max_output_tokens` to
  `responses.create`; `services/rag.py` `_within_context_budget` selects a
  rank-preserving prefix of chunks within `max_context_characters` and builds
  both the prompt and the `sources` event from the same selection.
- Rate limit: `api/rate_limit.py` `RateLimiter` (per-client fixed window,
  bounded/expired state, synchronous `check`, injectable `now`), `client_key`
  (direct peer default; opt-in trusted Cloud Run `X-Forwarded-For` suffix), and
  `enforce_rate_limit` (HTTP `429` + `Retry-After`); wired in `api/query.py`
  before collection lookup; limiter created in the app lifespan
  (`app.state.rate_limiter`).
- CORS: `core/settings.py` `cors_allowed_origins` (`CORS_ALLOWED_ORIGINS`, CSV)
  with `cors_allowed_origin_list`; a `field_validator` rejects `*`. `main.py`
  `configure_cors(app, settings=None)` adds `CORSMiddleware` only when origins
  are configured (`allow_methods=["POST"]`, `allow_headers=["Content-Type"]`,
  `allow_credentials=False`).
- Schema: `collections`, `documents`, `document_versions`, `chunks`, `embeddings`;
  migrations `475d329a606c_create_initial_schema`,
  `4d9a0c20621f_remove_embedding_vector_key`; `Embedding.id` = Qdrant point ID.
- DB wiring: `db/url.py` `build_database_url` uses `DATABASE_URL` when set
  (forces `postgresql+asyncpg`, translates `sslmode`→`ssl`, rejects
  `channel_binding`), else composes the local URL from `POSTGRES_*`;
  `db/session.py` and `alembic/env.py` use it.
- Vector wiring: `services/qdrant.py` `build_qdrant_client_kwargs` prefers
  `QDRANT_URL` (+ `QDRANT_API_KEY` when non-blank) and falls back to
  `QDRANT_HOST`/`QDRANT_PORT`.
- Embeddings: `services/embedding.py` loads `SentenceTransformer` lazily with
  `local_files_only=True` and `revision=settings.embedding_model_revision or None`;
  `encode()` is synchronous inside the async path; `MODEL_NAME`/`MODEL_VERSION`
  are unchanged and used for persisted embedding metadata.
- Config keys (`core/settings.py`): `APP_*`, `DEBUG`, `ALLOWED_COLLECTIONS`,
  `CORS_ALLOWED_ORIGINS`, `DATABASE_URL`, `POSTGRES_*`, `QDRANT_*`,
  `EMBEDDING_MODEL_REVISION`, `DEEPSEEK_*`, `MAX_OUTPUT_TOKENS`/
  `MAX_CONTEXT_CHARACTERS`, `RATE_LIMIT_REQUESTS`,
  `RATE_LIMIT_TRUST_CLOUD_RUN_X_FORWARDED_FOR`. `.env.example` omits
  `DEEPSEEK_API_KEY`/`BASE_URL`/`MODEL` and lists unused `REDIS_*`; `.env` is
  gitignored.
- CPU PyTorch: `pyproject.toml` extras `cpu`/`gpu` with `[tool.uv] conflicts`
  and a `pytorch-cpu` `[tool.uv.sources]` index; `uv sync --extra cpu` selects
  the CPU wheel, a plain `uv sync` keeps the default PyPI build.
- Testing: `integration` marker + `--strict-markers` (`pyproject.toml`), applied
  at module level in `test_database.py`, `test_models.py`, `test_repositories.py`,
  `test_retrieval.py`, `test_qdrant_integration.py`, `test_services.py`; CI runs
  `-m "not integration"`.
- Evaluation: `data/evaluation/fastapi.json` (24 examples) uses
  `{source_uri, snippet}` anchors; `evaluation/anchors.py` resolves them (raises
  on missing/ambiguous) against the latest document version; failed/incomplete
  generations are recorded (`failed` property, `terminal_event_missing`) and
  excluded from DeepEval test cases (`evaluation/answer.py`). Legacy UUID
  baseline is marked non-reproducible; the anchor-based baseline is pending a
  real run (`docs/evaluation/retrieval_baseline.md`).
- Corpus: `docs/corpus.md` pins `fastapi/fastapi` commit `244d6630…` (16 tutorial
  files); reproducible via `./scripts/acquire_corpus.sh`; `data/raw/` gitignored.
- CI: `.github/workflows/ci.yml` — backend `uv sync --frozen --extra cpu` →
  `ruff check` → `ruff format --check` → corpus script → `pytest -m "not integration"`
  (`DEEPSEEK_API_KEY=ci-dummy-key` placeholder); frontend Node 24 `npm ci` →
  `npm run lint` → `npm run build`.
- Frontend: `frontend/src/api.ts` builds the URL from `VITE_API_BASE_URL`
  (trailing slashes stripped; unset → relative `/query`) and throws when the
  stream ends without `complete`/`error`; `frontend/vite.config.ts` proxies
  `/query` to `http://localhost:8000` in dev.
- Container: multi-stage `Dockerfile` (builder `python:3.12-slim-bookworm` +
  `uv 0.13.0`; `uv sync --frozen --extra cpu --no-dev`, first
  `--no-install-project` then `--no-editable`) bakes the model into
  `HF_HOME=/opt/hf` via `huggingface_hub.snapshot_download`; runtime sets
  `HF_HUB_OFFLINE=1`, derives `EMBEDDING_MODEL_REVISION` from the
  `HF_MODEL_REVISION` arg, runs non-root `appuser`, and
  `exec uvicorn … --host 0.0.0.0 --port ${PORT:-8080} --workers 1`.
  `.dockerignore` excludes `.env*` (keeping `.env.example`), `.git`, `.venv`,
  caches, `data/`, `docs/`, `tests/`, `frontend/`.

## Recent Progress

Reconciled from commits `01be780`…`8855015`:

- Hardened the public API: allowlist, request caps, explicit generation errors,
  bounded output/context, and a per-client in-memory rate limit.
- Added optional hosted `DATABASE_URL` (asyncpg normalization; Neon `sslmode`
  TLS; `channel_binding` rejected) and `QDRANT_URL`/`QDRANT_API_KEY`, preserving
  local Docker defaults.
- Evaluation records failed/incomplete generations and excludes them from scoring.
- Build: CPU-only PyTorch extra; reproducible Linux AMD64 container image with
  the model baked at a pinned revision (`EMBEDDING_MODEL_REVISION`).
- Frontend/cross-origin: `VITE_API_BASE_URL` and backend `CORS_ALLOWED_ORIGINS`
  (`configure_cors`; exact origins only, `*` rejected).

## Open / Unfinished State

Confirmed against current code:

- No Firebase/Cloud Run deployment configuration in-repo; the container is
  built/verified locally only.
- Hosted PostgreSQL/Qdrant are configurable but no secret-manager integration;
  account state, quotas, billing, and free-tier allowances are unverified.
- Alembic offline mode (`--sql`) uses the placeholder `sqlalchemy.url`, not
  `DATABASE_URL`; only online `alembic upgrade head` is wired.
- CORS is read at import (restart required on change) and is not authentication;
  `VITE_API_BASE_URL` is baked at frontend build time (rebuild to change).
- Embedding model must be pre-baked/cached; `encode()` blocks the event loop.
- Stale DeepSeek model IDs: `deepseek-v4-flash` in `core/settings.py`; the
  `deepseek-chat` judge in `evaluation/answer.py`.
- Only `GenerationError` maps to a terminal event; other unexpected exceptions
  abort the stream with no terminal event (frontend reports "ended unexpectedly").
- Ingestion opens a DB session/transaction per chunk; `ensure_collection`
  re-fetches collections per chunk.
- Telemetry console exporter unconditional; `/health` is shallow and does not
  verify PostgreSQL/Qdrant/DeepSeek/model health.
- Frontend renders plain text only; sources show metadata, not content; no
  frontend test runner.
- `data/tmp/fastapi_chunks.tsv` is tracked generated output;
  `docs/images/streaming.gif` is ~13 MB.
- Anchor-based retrieval baseline is pending a real evaluation run.
- CORS frontend↔backend cross-origin path not exercised end-to-end.

Unresolved external decisions (no account state inspected): reuse vs. create a
Neon project; Firebase/GCP project and billing; hosted Qdrant suitability;
DeepSeek budget.

## Verification

Valid for HEAD `8855015` (working tree clean apart from this file):

- `uv run ruff check .` → All checks passed!; `uv run ruff format --check .` →
  89 files already formatted.
- `DEEPSEEK_API_KEY=ci-dummy-key uv run pytest -q -m "not integration"` →
  156 passed, 23 deselected. Focused `tests/test_cors.py tests/test_settings.py
  tests/test_api.py tests/test_health.py` → 45 passed.
- Frontend: `npm run lint` → exit 0; `npm run build` → exit 0. Build with
  `VITE_API_BASE_URL=https://api.example.com/` inlines the base URL (trailing
  slash stripped); the default build contains no baked base URL (relative path).
- `uv lock --check` → consistent (locked 140 packages after the CPU-torch extra).
- Container (built and verified at `0e4d1a9`, before the CORS change): `docker
  build --platform linux/amd64` succeeded; image size 2.35 GB; `torch 2.13.0+cpu`
  with `torch.cuda.is_available() == False`; no `nvidia`/`triton`/`cuda` packages;
  baked snapshot `5c38ec7c405ec4b44b94cc5a9bb96e735b38267a` present with no
  `refs/` dir; offline model load under `--network none` returned dim 384;
  `/health` → `{"status":"ok"}` as uid 10001; `alembic heads` → `4d9a0c20621f`;
  `/app` contained only `.venv`, `alembic`, `alembic.ini`.
- `git diff --check` → clean.
- Not run (require services/state/paid calls): `-m integration` tests, Docker
  Compose, real Alembic migrations, live DeepSeek requests, deployment.

## Authoritative References

- `AGENTS.md` — workflow, permissions, security/cost, public-API,
  corpus/evaluation rules.
- `README.md` — architecture, setup, configuration, commands, baselines, CI.
- `docs/adr/` — accepted decisions (001 multi-collection, 002 embedding entity,
  003 structure-aware ingestion, 004 selective LangChain, 005 API allowlist).
- `docs/deployment.md` — container build/run, baked model, migrations, CORS.
- `docs/corpus.md`; `docs/evaluation/`, `data/evaluation/`.
- `src/production_rag/`, `tests/`, `frontend/`, `alembic/`, `Dockerfile`,
  `.dockerignore`, `.env.example`, `.github/workflows/ci.yml`,
  `scripts/acquire_corpus.sh`, `docker-compose.yml`, `pyproject.toml`, `uv.lock`.

## Session Boundary

- All session implementation work is committed at HEAD `8855015`; the only
  uncommitted change is this `SESSION_HANDOFF.md` rewrite (not staged).
- Local state: `.env` holds local configuration (gitignored); corpus at
  `data/raw/fastapi/`; HF cache has the embedding model; `frontend/node_modules`
  and ignored `frontend/dist` present; a local `production-rag:local` image
  (Linux AMD64) exists from the last build.
- Material discrepancy vs. the previous handoff: it described HEAD `499fec3` and
  listed items now resolved — no `Dockerfile`; no CORS or configurable API base
  URL; Postgres lacking `DATABASE_URL`/TLS; Qdrant lacking `url`/`api_key`; no
  output-token cap; evaluators ignoring the `error` event. The repository has
  advanced eight commits (`01be780`…`8855015`) implementing all of those.
