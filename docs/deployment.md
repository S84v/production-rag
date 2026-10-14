# Deployment

Operational notes for the backend container. This guide covers **building and
running the image locally**. Hosting on Cloud Run is the intended direction but
**is not implemented or verified here**; treat the Cloud Run section as notes,
not evidence.

## Scope and status

- The image serves the FastAPI backend only (PostgreSQL, Qdrant, DeepSeek, and
  Sentence Transformers stay external).
- No cloud resources, quotas, billing, permissions, or free-tier allowances are
  assumed or verified.
- Cross-origin access is configurable via `CORS_ALLOWED_ORIGINS` (exact
  origins; empty by default). CORS is not authentication and does not replace
  the API's abuse controls. Building and serving the frontend (Firebase) and the
  Cloud Run deployment remain separate, unverified tasks.

## Prerequisites

- Docker with BuildKit.
- The repository checkout (build context is the repo root).

No credentials are needed to build; `uv.lock` and the pinned model revision are
baked in.

## Build the image (Linux AMD64)

Cloud Run runs `linux/amd64`, so build for that platform explicitly:

```bash
docker build --platform linux/amd64 -t production-rag:local .
```

The build uses Python 3.12 (Bookworm slim), the pinned `uv 0.13.0`, the locked
dependencies with the CPU-only PyTorch extra, and bakes the embedding model.

## Configuration

Runtime configuration uses the same environment variables as the local
application (see the README "Environment configuration" section). The most
relevant for the container:

```text
DEEPSEEK_API_KEY                 # required for /query generation
ALLOWED_COLLECTIONS              # default: fastapi
DATABASE_URL                     # hosted PostgreSQL, or POSTGRES_* for local
QDRANT_URL / QDRANT_API_KEY      # hosted Qdrant, or QDRANT_HOST/PORT for local
```

`PORT`, `HF_HOME`, `HF_HUB_OFFLINE`, and `EMBEDDING_MODEL_REVISION` are set in
the image; `PORT` defaults to `8080`.

Whenever `DATABASE_URL` is set, apply migrations separately (see below) — the
application does not run migrations at startup.

## Frontend and CORS

The React frontend reads its API base URL from `VITE_API_BASE_URL`, a public
**build-time** variable baked into the bundle (locally via `frontend/.env.local`,
which is gitignored). When unset, the frontend calls the relative `/query` path
handled by the Vite dev proxy. For a production cross-origin deployment, build
the frontend with `VITE_API_BASE_URL` set to the backend origin, and list the
frontend's origin in the backend's `CORS_ALLOWED_ORIGINS`.

`CORS_ALLOWED_ORIGINS` accepts comma-separated **exact** origins
(`scheme://host[:port]`, no path or trailing slash); `*` is rejected and there is
no substring or regex matching. CORS is **not authentication** and is not a
substitute for the request limits, collection allowlist, and rate limiting — it
is enforced by the browser, not the server.

## Run locally

The application only queries PostgreSQL, Qdrant, and DeepSeek when a request is
made. Note that the **Qdrant client is created during startup and may attempt a
compatibility check** against the configured endpoint; with no reachable Qdrant
this logs a `Failed to obtain server version` warning but does not prevent
startup.

`/health` is **shallow**: it returns `{"status": "ok"}` when the process is
serving and does **not** verify PostgreSQL, Qdrant, DeepSeek, or the embedding
model. A dummy DeepSeek key is enough to start the app and check health:

```bash
docker run --rm \
  -e DEEPSEEK_API_KEY=dummy \
  -e ALLOWED_COLLECTIONS=fastapi \
  -p 8080:8080 \
  production-rag:local
```

Check health from another shell:

```bash
curl -fsS http://localhost:8080/health
```

To exercise `/query`, provide real `DATABASE_URL`, `QDRANT_URL`/`QDRANT_API_KEY`,
and `DEEPSEEK_API_KEY` for a reachable environment. Never bake secrets into the
image; pass them at run time.

## Baked model

The embedding model `BAAI/bge-small-en-v1.5` is downloaded at build time into
`HF_HOME=/opt/hf` at the immutable revision
`5c38ec7c405ec4b44b94cc5a9bb96e735b38267a`. The runtime sets
`EMBEDDING_MODEL_REVISION` to the same revision and `HF_HUB_OFFLINE=1`, so the
application loads the baked snapshot and cannot download models at run time
(`local_files_only=True`).

**Changing the model revision** can change embedding vectors and invalidates
existing vectors in Qdrant. If you bump it, review embedding-version
compatibility and re-ingest the corpus; update both `HF_MODEL_REVISION`
(build argument) and `EMBEDDING_MODEL_REVISION` (runtime environment) together.

## Database migrations

Migrations run **separately** from the application using the same image, and
require a reachable PostgreSQL:

```bash
docker run --rm \
  -e DATABASE_URL=postgresql://USER:PASSWORD@HOST/DBNAME?sslmode=require \
  --entrypoint alembic \
  production-rag:local upgrade head
```

`alembic/` and `alembic.ini` are included for this. Online migrations use
`DATABASE_URL`. Offline SQL generation (`--sql`) is not wired to the runtime
configuration and must not be relied on.

## Inspect the image

```bash
docker image inspect production-rag:local --format '{{.Size}}'
docker run --rm --entrypoint python production-rag:local \
  -c "import torch, production_rag; print(torch.__version__, torch.cuda.is_available())"
```

## Troubleshooting

- **Model fails to load**: confirm the snapshot exists under
  `/opt/hf/hub/models--BAAI--bge-small-en-v1.5/snapshots/<revision>` and that
  `EMBEDDING_MODEL_REVISION` matches it. `HF_HUB_OFFLINE=1` makes any missing
  file fail loudly rather than downloading.
- **`libgomp` error from PyTorch**: the runtime image must include `libgomp1`.
- **Permission errors reading the model**: `/opt/hf` must be readable by the
  non-root `appuser`.
- **Wrong port**: the process binds `0.0.0.0:${PORT:-8080}`.

## Cloud Run notes (future, unverified)

- Cloud Run sets `PORT`; the container already honors it and binds `0.0.0.0`.
- Run one Uvicorn worker per instance: the embedding model (~130 MB) is loaded
  per instance/worker, and the in-memory rate limiter is per instance — it is
  best-effort, not a global limit.
- Client IPs behind Cloud Run require `RATE_LIMIT_TRUST_CLOUD_RUN_X_FORWARDED_FOR`
  only after verifying the proxy header chain (see the README rate-limiting
  section).
- Set Cloud Run memory at least 1 GiB (2 GiB is safer) for PyTorch plus the
  model, and expect a cold-start cost for the first request.
- The console OpenTelemetry exporter remains; it writes span JSON to stdout,
  which Cloud Run forwards to Cloud Logging.
