# Session Handoff

_Current-state snapshot (2026-10-13). Rewrite stale sections; do not append
history. Not a changelog, task plan, or recommendation list. Use exact
paths/identifiers; never include secrets; never claim unobserved verification._

## Repository State

- Branch `main`, HEAD `78ed31bed97dc983267a4381d764551d939a526a`, up to date with
  `origin/main`; working tree clean (no staged or stray files besides this file).
- Recent commits: `78ed31b docs: add project-specific AI development guidelines`
  (adds `AGENTS.md`, 152 lines); `e19c19c docs: update README.md`.

## Project State

Production RAG is a production-oriented RAG portfolio demo: a FastAPI service
answers questions grounded in retrieved documentation (currently the FastAPI docs),
backed by PostgreSQL, Qdrant, `BAAI/bge-small-en-v1.5` embeddings, DeepSeek
generation, and a React/TypeScript/Vite frontend; managed with `uv`.

Stage: the **local vertical slice is implemented**; **deployment is not configured
in-repo** — as of the last audit there is no backend `Dockerfile`, no CI/workflows,
and no Firebase/Cloud Run configuration. Hosting topology (Firebase Hosting, Cloud
Run, Neon, hosted Qdrant) is intended, not implemented. Per `AGENTS.md`, verify
current status before asserting. No application, test, or config code has changed
in the recent documentation-only work.

## Implemented State

- Ingestion: Markdown → SHA-256 → structure-aware chunking (`markdown-it-py`,
  `max_characters=4000`) → PostgreSQL → embeddings → Qdrant; idempotent by content
  hash with document versioning.
- Retrieval: query embedding → Qdrant search → PostgreSQL hydration (authoritative
  source/chunk metadata), scoped by collection name.
- API: `POST /query` streams NDJSON (`sources` → per-delta `text` → `complete`);
  DeepSeek via OpenAI SDK Responses API. `GET /health` is shallow.
- CLI: `production-rag ingest` / `query` (`src/production_rag/__init__.py`).
- Evaluation: custom chunk-level retrieval metrics + DeepEval answer metrics.
- Observability: OpenTelemetry, unconditional console span exporter.
- Frontend: single-page React; renders plain-text answers and source metadata only
  (no Markdown/code rendering, no chunk content shown).

## Current Implementation Details

- Layout: `src/production_rag/{api,core,db,ingestion,models,repositories,schemas,services,evaluation,telemetry.py,main.py}`,
  `alembic/versions/`, `tests/`, `frontend/`, `docs/{adr,corpus.md,evaluation,images}`,
  `data/{raw,evaluation,tmp}`, `docker-compose.yml`, `pyproject.toml`, `uv.lock`.
- API contract: `POST /query` `QueryRequest{query(min_length=1), collection,
  limit(1..20, default 5)}` (`schemas/query.py`); NDJSON `sources|text|complete`;
  `404` for unknown collection; `GET /health` → `{"status":"ok"}`.
- Schema: `collections`, `documents`, `document_versions`, `chunks`, `embeddings`;
  migrations `475d329a606c_create_initial_schema`,
  `4d9a0c20621f_remove_embedding_vector_key`. `Embedding.id` = Qdrant point ID;
  `Chunk.id`/`Embedding.id` default to `uuid.uuid4`.
- Config: `core/settings.py`, env-driven; keys `POSTGRES_*`, `QDRANT_HOST`/`PORT`,
  `DEEPSEEK_API_KEY`/`BASE_URL`/`MODEL`/`TIMEOUT`, `APP_*`, `DEBUG`. `.env.example`
  is incomplete vs. settings; local `.env` holds a DeepSeek key (gitignored).
- DB/vector wiring: `db/session.py` builds `postgresql+asyncpg://…` at import (no
  `DATABASE_URL`/TLS/`pool_pre_ping`); `services/qdrant.py` takes only `host`/`port`
  (no `url`/`api_key`, so Qdrant Cloud is unsupported as-is).
- Embeddings: `services/embedding.py` uses `local_files_only=True`; `encode()` is
  synchronous inside the async path. HF cache holds `BAAI/bge-small-en-v1.5` and an
  unused cross-encoder (reranker removed; stale `services/__pycache__/reranker.*`).
- Python/deps: project Python 3.12 (`.python-version`; `.venv` 3.12.13); system
  `python3` is 3.14 — use `uv run` / `.venv/bin/*`. Key versions: fastapi 0.141.1,
  sqlalchemy 2.0.51, qdrant-client 1.19.0, sentence-transformers 6.0.0, openai
  3.5.0, deepeval 4.2.0, ruff 0.16.2.
- Testing: unit tests use fakes; integration tests hit live Postgres/Qdrant + the
  model cache with no markers (`test_database.py`, `test_repositories.py`,
  `test_retrieval.py`, `test_qdrant_integration.py`, parts of `test_services.py`).
- Evaluation data: `data/evaluation/fastapi.json` (24 examples) labels relevant
  chunks by random UUID; `chunk_index` also shifts on re-chunking, so baselines in
  `docs/evaluation/` and `data/evaluation/results/` are not reproducible from a
  clean build.
- Corpus: `docs/corpus.md` (pinned `fastapi/fastapi` commit `244d6630…`, 16
  tutorial files); acquisition is manual (no script); `data/raw/` is not in Git.
- Frontend: `frontend/src/api.ts` posts to relative `/query` (Vite proxy in
  `vite.config.ts`); no API base URL and no CORS in `main.py`.

## Recent Progress

- Completed a read-only repository audit; findings below are open and no code or
  config was changed.
- Authored root `AGENTS.md` (agent workflow, permissions, security/cost rules,
  public-API safeguards, corpus/evaluation rules, conditional MCP guidance),
  iterated to a durable 152-line form, committed by the operator as `78ed31b`.
- Created this `SESSION_HANDOFF.md` (documentation-only).

## Open / Unfinished State

Confirmed issues (audit findings; not re-verified since, code unchanged):

- Evaluation labels/identifiers are non-reproducible (UUID labels; unstable
  `chunk_index`); baselines cannot be reproduced from a clean rebuild.
- No CORS / configurable API base URL → separately hosted frontend and API cannot
  communicate.
- No abuse/cost controls: no `max_length` on `query`/`collection`, no fixed
  collection allowlist, no `max_output_tokens`, no rate limiting/quotas.
- No deployment artifacts (no backend Dockerfile, CI, Firebase/Cloud Run config).
- Hosted-service gaps: Qdrant client lacks `url`/`api_key`; Postgres lacks
  `DATABASE_URL`/TLS/pooling; no secret-manager integration.
- Embedding model must be pre-baked/cached; `encode()` blocks the event loop.
- DeepSeek model IDs stale (`deepseek-v4-flash` alias in settings; `deepseek-chat`
  judge in `evaluation/answer.py`).
- LLM stream ignores `response.failed`/`incomplete`; API stream lacks error
  wrapping; frontend `JSON.parse` in `api.ts` is unguarded.
- Ingestion opens a DB session/transaction per chunk; `ensure_collection`
  re-fetches collections per chunk.
- Telemetry exports spans to stdout unconditionally.
- Frontend renders plain text only; sources show metadata, not content.
- README inaccuracies: streaming semantics/event order, `.env.example` mismatch, no
  frontend section. `data/tmp/fastapi_chunks.tsv` (168 KB) is tracked generated
  output; `docs/images/streaming.gif` is ~13 MB.
- Tests require live services without markers; `/health` is shallow.

Unresolved external decisions (not resolvable from the repo; no account state
inspected): reuse vs. create a Neon project; Firebase/GCP project and billing;
hosted Qdrant plan suitability; DeepSeek budget.

## Verification

- Ran (read-only) against the code state at `e19c19c` (unchanged since): git
  inspection (`status`/`log`/`rev-parse`/`ls-files`/`check-ignore`),
  `find`/`ls`/`du`, `cat`/`grep`, JSON parse of evaluation data,
  `.venv/bin/ruff check --no-cache .` → All checks passed!,
  `.venv/bin/ruff format --check --no-cache .` → 74 files already formatted.
- Not run (require services/state/paid calls): `pytest`, `uv sync`,
  `docker compose`, `alembic`, frontend lint/build, live DeepSeek requests.

## Authoritative References

- `AGENTS.md` — agent workflow, permissions, security/cost/corpus rules.
- `README.md` — architecture overview, setup, commands, baseline tables.
- `docs/adr/` — accepted decisions (multi-collection, embedding entity, chunking,
  selective LangChain).
- `docs/corpus.md` — corpus provenance and pinned revision.
- `docs/evaluation/`, `data/evaluation/` — evaluation methodology, dataset, results.
- `src/production_rag/`, `tests/`, `frontend/`, `alembic/`, `docker-compose.yml`,
  `pyproject.toml`, `uv.lock` — current behavior and prerequisites.

## Session Boundary

- Changed this session: `AGENTS.md` (committed `78ed31b`) and `SESSION_HANDOFF.md`
  (new, untracked). No implementation, test, or config files changed.
- Local state: `.env` holds a real `DEEPSEEK_API_KEY` (gitignored); HF cache has
  the embedding model; `frontend/node_modules` and ignored stale `frontend/dist`
  exist.
- Decisions made but not in code: the deferred architecture decisions above remain
  pending.
- Discrepancy: none; committed `AGENTS.md` (152 lines) matches the in-session version; tree clean.
