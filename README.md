<div align="center">

  <img src="frontend/public/favicon.svg" alt="DocAssist" width="64" height="64" />

  <h1>DocAssist</h1>

  <hr />

  <p><em>Source-grounded answers from technical documentation.</em></p>

  <p>
    <a href="https://github.com/S84v/production-rag/actions/workflows/ci.yml">
      <img src="https://img.shields.io/github/actions/workflow/status/S84v/production-rag/ci.yml?branch=main&style=flat-square&logo=githubactions&logoColor=white&label=CI" alt="CI">
    </a>
    <img src="https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.12">
    <img src="https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI">
    <img src="https://img.shields.io/badge/PostgreSQL-17-4169E1?style=flat-square&logo=postgresql&logoColor=white" alt="PostgreSQL 17">
    <img src="https://img.shields.io/badge/Qdrant-vectors-DC244C?style=flat-square" alt="Qdrant">
    <img src="https://img.shields.io/badge/React-19-61DAFB?style=flat-square&logo=react&logoColor=111827" alt="React 19">
    <img src="https://img.shields.io/badge/TypeScript-3178C6?style=flat-square&logo=typescript&logoColor=white" alt="TypeScript">
  </p>

</div>

DocAssist is a production-oriented Retrieval-Augmented Generation (RAG) service
that answers natural-language questions about the **official FastAPI
documentation** and returns the documentation sources behind every answer.
**▶ [Try DocAssist — live demo](https://docassist-prod-2026.web.app/)**

![DocAssist answering a question with streaming output](docs/images/streaming.gif)

---

## What DocAssist does

DocAssist answers questions from an indexed documentation corpus instead of from
general model knowledge. It retrieves the most relevant passages, asks a language
model to answer using **only** that retrieved context, and returns the passages it
used so the answer can be checked against the original text. When the retrieved
context does not contain the answer, the model is expected to say so.

The current corpus is the **official FastAPI documentation** — 135 prepared
documents covering the tutorial, advanced topics, deployment, how-to guides, and
reference pages — pinned to a specific revision for reproducibility. See
[`docs/corpus.md`](docs/corpus.md).

The architecture supports multiple collections, but **only the `fastapi`
collection is currently indexed and served**, and the public API only serves
collections on a fixed allowlist. There is no document upload and no collection
picker in the interface.

## Architecture

```text
Markdown corpus → ingestion (hashing, structure-aware chunking) → PostgreSQL
                                   │
                                   ▼
                     BGE-small embeddings → Qdrant (vectors)

Query → embed → Qdrant search → PostgreSQL hydration → context → DeepSeek
                                                              → NDJSON stream
```

PostgreSQL is the authoritative store for document metadata and chunk text;
Qdrant stores the vectors used for similarity search. Qdrant payloads are not
treated as the metadata source of truth.

The full component map, request flow, ingestion pipeline, and lifecycle are in
[`docs/architecture.md`](docs/architecture.md).

## Tech stack

| Area | Technology |
| --- | --- |
| Language | Python 3.12+ |
| API | FastAPI |
| Database | PostgreSQL 17 |
| Vector database | Qdrant |
| ORM / migrations | SQLAlchemy 2 / Alembic |
| Embeddings | `BAAI/bge-small-en-v1.5` (384 dims, cosine) |
| LLM | DeepSeek (OpenAI Python SDK client) |
| Markdown parsing | markdown-it-py |
| Observability | OpenTelemetry |
| Web frontend | React 19 + TypeScript + Vite |
| Frontend testing | Vitest + React Testing Library |
| Backend testing / linting | pytest / Ruff |
| Package management | uv |

Redis is included in the local Docker Compose stack but is not part of the RAG
request path.

## Key engineering decisions

| Decision | ADR |
| --- | --- |
| Collections map to independent Qdrant collections | [ADR-001](docs/adr/001-multi-collection-workspaces.md) |
| Embeddings modeled as a separate domain entity | [ADR-002](docs/adr/002-embeddings-as-separate-domain-entity.md) |
| Structure-aware Markdown ingestion | [ADR-003](docs/adr/003-structure-aware-markdown-ingestion.md) |
| Selective (not blanket) use of LangChain | [ADR-004](docs/adr/004-selective-use-of-langchain.md) |
| Public API collection allowlist | [ADR-005](docs/adr/005-public-api-collection-allowlist.md) |
| Corpus preparation and vector-store consistency | [ADR-006](docs/adr/006-corpus-preparation-and-vector-store-consistency.md) |

The records are indexed in [`docs/adr/`](docs/adr/README.md).

## How a query works

1. The client sends a question to `POST /query`, which validates the request and
   checks the collection allowlist.
2. The query is embedded with `BAAI/bge-small-en-v1.5`.
3. Qdrant returns the nearest vectors; the corresponding chunks and metadata are
   hydrated from PostgreSQL (latest document version only).
4. The retrieved chunks are added to the prompt within a bounded context budget,
   and DeepSeek generates the answer.
5. The response streams back as newline-delimited JSON: the `sources` event,
   incremental `text` events, and one terminal `complete` or `error` event.

The precise contract — request fields, status codes, rate limiting, and CORS — is
in [`docs/api.md`](docs/api.md).

## Getting started

Requirements: Python 3.12+, [uv](https://docs.astral.sh/uv/), Docker, and Docker
Compose.

```bash
# 1. Install dependencies and create the local environment file
uv sync
cp .env.example .env          # set DEEPSEEK_API_KEY for /query

# 2. Start PostgreSQL and Qdrant
docker compose up -d

# 3. Apply database migrations
uv run alembic upgrade head

# 4. Acquire and prepare the pinned FastAPI corpus, then ingest it
./scripts/acquire_corpus.sh
uv run production-rag ingest --path data/raw/fastapi --collection fastapi

# 5. Run the API
uv run uvicorn production_rag.main:app --reload
```

Query it:

```bash
curl -N -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query":"How do I create a FastAPI application?","collection":"fastapi","limit":5}'
```

Configuration (database, Qdrant, DeepSeek, cost and rate limits, CORS, and the
frontend API URL) is documented in [`docs/configuration.md`](docs/configuration.md).
For CPU-only environments, `uv sync --extra cpu` resolves PyTorch from the
official CPU-only index.

The CLI also supports `production-rag query`, `production-rag prepare-corpus`,
and `production-rag reconcile`. `reconcile` is a read-only dry run by default and
reports drift between PostgreSQL (authoritative) and Qdrant; `--apply` deletes
only points that are proven non-authoritative within the named collection.

## Testing

```bash
uv run pytest -q                 # full suite (needs PostgreSQL, Qdrant, cached model)
uv run pytest -m "not integration"   # service-free tests only (as CI runs)
uv run ruff check . && uv run ruff format --check .
```

Tests that need live PostgreSQL, Qdrant, or the cached embedding model are marked
`integration`. Tests that read the prepared corpus require
`./scripts/acquire_corpus.sh` first.

The frontend has its own checks:

```bash
cd frontend && npm ci && npm run lint && npm run test && npm run build
```

## Evaluation

DocAssist measures retrieval quality with chunk-level Precision@K, Recall@K,
Hit@K, and MRR against a 29-example dataset whose labels are **content anchors**
(verbatim excerpts tied to a source document) rather than runtime chunk IDs, so
the dataset stays reproducible across re-chunking.

The current reproducible baseline is the **anchor-based retrieval baseline
recorded on 2026-10-16**, with no reranker. At the application's default depth
(`K = 5`):

| Retrieval depth | Precision | Recall | Hit rate | MRR |
| --------------: | --------: | -----: | -------: | --: |
| 5 | 0.1310 | 0.5977 | 0.6552 | 0.5316 |

`K = 10` and `K = 20` are diagnostic candidate-depth measurements that the
application does not use.

The generation/answer evaluation artifacts in the repository were recorded
**before the corpus expansion** and cover **24** examples; they are historical and
must not be read as current metrics. Everything is indexed, with provenance and
run commands, in [`docs/evaluation/`](docs/evaluation/README.md).

## Deployment

DocAssist is deployed as a static frontend on Firebase Hosting with a FastAPI
backend on Google Cloud Run, backed by managed PostgreSQL (Neon), Qdrant Cloud,
and the DeepSeek API:

- Live app: **<https://docassist-prod-2026.web.app/>**
- Backend health: `GET /health` returns `{"status":"ok"}`

`.github/workflows/cd.yml` deploys a commit after the `CI` workflow succeeds on
`main`: it builds a commit-SHA image, runs `alembic upgrade head` as a separate
Cloud Run job (a migration failure blocks the deploy), deploys the new revision
with no traffic and promotes it only after health checks pass, then stages and
verifies the frontend before promoting it. Authentication uses GitHub OIDC with
Workload Identity Federation (no long-lived keys). The pipeline has completed
successful runs for `main`; the original deployment was established by hand, and
subsequent deploys are automated.

Production targets, required configuration, IAM, and rollback are documented in
[`docs/deployment.md`](docs/deployment.md).

## Limitations

- Only the `fastapi` collection is indexed and served; other corpora are not
  available, and there is no upload or collection-selection UI.
- The request rate limit is held in memory per process, so it is not a global
  limit across instances (see [`docs/api.md`](docs/api.md)).
- The embedding model is loaded lazily and cached per process, so the first query
  after a cold start pays the load cost, and the model must be available locally
  (the container bakes it in).
- Hosted database and vector-store endpoints are configurable, but account,
  quota, and billing state are not verified by the application.
- Retrieval uses a single bi-encoder ranking with no reranker.

## Project structure

```text
production-rag/
├── .github/workflows/     CI and CD workflows
├── alembic/               Database migrations
├── data/
│   ├── evaluation/        Dataset and dated result artifacts
│   └── raw/               Prepared corpus (not tracked)
├── docs/                  Architecture, API, configuration, corpus, evaluation, deployment, ADRs
├── frontend/              React + TypeScript + Vite SPA
├── scripts/               Corpus acquisition
├── src/production_rag/    API, ingestion, services, repositories, models, evaluation
├── tests/                 pytest suite
├── Dockerfile             Backend container image
├── docker-compose.yml     Local PostgreSQL, Qdrant, Redis
├── firebase.json          Firebase Hosting configuration
├── pyproject.toml         Dependencies and tool configuration
└── uv.lock                Locked dependencies
```

## Further reading

- [`docs/architecture.md`](docs/architecture.md) — components, request flow, persistence boundary.
- [`docs/api.md`](docs/api.md) — `POST /query` contract, validation, rate limiting, CORS.
- [`docs/configuration.md`](docs/configuration.md) — every environment variable.
- [`docs/corpus.md`](docs/corpus.md) — corpus scope, preparation, exclusions, layout.
- [`docs/evaluation/`](docs/evaluation/README.md) — datasets, baselines, and provenance.
- [`docs/deployment.md`](docs/deployment.md) — production environment and the CD workflow.
- [`docs/adr/`](docs/adr/README.md) — architecture decision records.

## Contact

- LinkedIn — <https://www.linkedin.com/in/sarang-dave/>
- GitHub — <https://github.com/S84v>
- Email — <davesarang08@gmail.com>
