# Configuration

Configuration is read from environment variables (and a local `.env` file).
Start from the tracked template:

```bash
cp .env.example .env
```

`.env` is gitignored. Never commit real credentials, endpoints, or keys.

## Application

| Variable | Default | Purpose |
| --- | --- | --- |
| `APP_NAME` | `Production RAG` | Application title |
| `APP_VERSION` | `0.1.0` | Application version |
| `DEBUG` | `false` | Debug flag |
| `ALLOWED_COLLECTIONS` | `fastapi` | Comma-separated collections the public API may serve; an empty value denies all |

`ALLOWED_COLLECTIONS` is the public API's allowlist
([ADR-005](adr/005-public-api-collection-allowlist.md)). Requests for any other
collection return `404`, whether or not the collection exists in Qdrant.

## Database (PostgreSQL)

By default the application connects to a local instance built from the
`POSTGRES_*` settings (the Docker Compose service):

| Variable | Default |
| --- | --- |
| `POSTGRES_USER` | `production_rag` |
| `POSTGRES_PASSWORD` | `production_rag_dev` |
| `POSTGRES_DB` | `production_rag` |
| `POSTGRES_HOST` | `localhost` |
| `POSTGRES_PORT` | `5432` |

To use a hosted database instead, set `DATABASE_URL`, which takes precedence over
`POSTGRES_*`:

```text
DATABASE_URL=postgresql://USER:PASSWORD@HOST/DBNAME?sslmode=require
```

The URL is normalized for the asyncpg driver: the `postgres://` and
`postgresql://` schemes become `postgresql+asyncpg`, and the libpq `sslmode`
parameter is translated to asyncpg's `ssl` (an explicit `ssl` is preserved when
both are present). Neon connection strings used with asyncpg must omit
`channel_binding`: the default Neon string can include `channel_binding=require`,
but asyncpg does not support that parameter, so the application raises a
configuration error rather than silently dropping the requested authentication
setting. Remove `channel_binding=require` and keep `sslmode=require` for TLS.
Other libpq-only parameters are not translated.

## Vector store (Qdrant)

The default connection uses `QDRANT_HOST` / `QDRANT_PORT` (the Docker Compose
service; default `localhost:6333`) and is unauthenticated.

To use a hosted endpoint, set `QDRANT_URL`, which takes precedence; for Qdrant
Cloud also set `QDRANT_API_KEY`:

```text
QDRANT_URL=https://YOUR-CLUSTER.cloud.qdrant.io:6333
QDRANT_API_KEY=YOUR_API_KEY
```

`QDRANT_URL` is passed to the client as `url`, and `QDRANT_API_KEY` is attached
only when `QDRANT_URL` is set and the key is non-blank (the key is ignored in
local mode). TLS is derived from the URL's `https://` scheme, and the port is
taken from the URL, falling back to the client default `6333` when omitted —
include it explicitly when it differs.

## Embeddings

| Variable | Default | Purpose |
| --- | --- | --- |
| `EMBEDDING_MODEL_REVISION` | *(empty)* | Immutable Hugging Face revision for `BAAI/bge-small-en-v1.5` |

The embedding model is `BAAI/bge-small-en-v1.5` (384 dimensions, cosine). It is
loaded with `local_files_only=True`, so the model must already be cached; the
container image bakes it at a pinned revision and sets this variable so the
runtime loads exactly that snapshot. Changing the revision can change the vectors
and requires re-ingestion. See [`deployment.md`](deployment.md).

## DeepSeek

| Variable | Default | Purpose |
| --- | --- | --- |
| `DEEPSEEK_API_KEY` | *(empty)* | API key (required for `/query` generation) |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | API base URL |
| `DEEPSEEK_MODEL` | `deepseek-flash` | Model used for generation |
| `DEEPSEEK_TIMEOUT` | `60` | Request timeout (seconds) |

## Cost and abuse controls

| Variable | Default | Purpose |
| --- | --- | --- |
| `MAX_OUTPUT_TOKENS` | `1024` | Token cap per answer (positive integer) |
| `MAX_CONTEXT_CHARACTERS` | `12000` | Chunk-content cap for the prompt (positive integer) |
| `RATE_LIMIT_REQUESTS` | `10` | `POST /query` requests per client per 60-second window (positive integer) |
| `RATE_LIMIT_TRUST_CLOUD_RUN_X_FORWARDED_FOR` | `false` | Read the client IP from the `X-Forwarded-For` chain (enable only for verified direct Cloud Run ingress) |

See [`api.md`](api.md) for how these are enforced.

## Cross-origin access

| Variable | Default | Purpose |
| --- | --- | --- |
| `CORS_ALLOWED_ORIGINS` | *(empty)* | Comma-separated exact browser origins allowed cross-origin access; empty disables CORS |

Each entry must be an exact origin (`scheme://host[:port]`, no path, no trailing
slash); `*` is rejected. See [`api.md`](api.md#cross-origin-requests-cors).

## Frontend

| Variable | Default | Purpose |
| --- | --- | --- |
| `VITE_API_BASE_URL` | *(empty)* | API base URL baked into the frontend build |

`VITE_API_BASE_URL` is a **public frontend variable, never a secret**. When
unset, the frontend calls the relative `/query` path, which the Vite dev server
proxies to `http://localhost:8000`. Set it for a production build where the
frontend and API are on different origins. Vite inlines `VITE_*` variables at
**build time**, so the frontend must be rebuilt when the value changes.

## Local infrastructure

The Docker Compose configuration also provides Redis (`REDIS_HOST` /
`REDIS_PORT`), which is not part of the RAG request path.
